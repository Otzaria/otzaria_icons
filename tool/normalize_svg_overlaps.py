#!/usr/bin/env python3
"""Normalize overlapping/seaming SVG paths into one clean, font-safe outline.

WHY THIS EXISTS
---------------
The font generator merges every <path> of an icon into a single glyph outline
filled with the nonzero winding rule. In a browser (and in docs/icon_catalog.svg)
each <path> is painted independently, so overlapping black layers and touching
seams are invisible. But once merged into one glyph, overlapping contours with
opposing winding cancel to unintended white holes, and touching sub-paths leave
hairline seams. The generator's winding normalization only copes with fully
*nested* holes, not partial overlaps, so those icons render corrupted in the OTF.

This tool resolves each icon's geometry the way Google's picosvg/nanoemoji do:
it `simplify`s every path (honouring its own fill-rule) and boolean-UNIONs them
into a single non-overlapping, consistently-wound path whose filled area is
byte-for-byte what the catalog/browser shows. That single clean path is the
safest possible input for the font: no overlaps, no seams, no winding conflicts.

INTENDED KNOCKOUTS ARE PRESERVED
--------------------------------
Some icons deliberately knock a white shape out of a solid body (e.g. the "W" in
document_word, the bullets in document_bullet_list, the alef in book_alef).
That white cut only exists in the font, via winding cancellation, and the catalog
actually hides it. Unioning would fill it in. Such icons are detected (a whole
path sitting inside another) and SKIPPED, leaving them untouched.

USAGE
-----
  python3 tool/normalize_svg_overlaps.py                 # normalize all sources
  python3 tool/normalize_svg_overlaps.py a.svg b.svg     # normalize specific files
  python3 tool/normalize_svg_overlaps.py --check          # report, change nothing
                                                          # (exit 1 if any file
                                                          #  needs normalization)

Requires: skia-pathops, fonttools  (pip install skia-pathops fonttools)
This is a preparation step, like tool/prepare_svg_sources.dart. It is idempotent:
re-running on an already-normalized file produces no change. Always review the
result visually and keep sources under version control while running it.
"""
import sys, os, re, glob

try:
    import pathops
    from fontTools.pens.svgPathPen import SVGPathPen
    from glyph_geometry import simplified, is_knockout_index
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

SVG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets_src", "svg")
PATH_RE = re.compile(r'<path\b([^>]*?)/?>')
D_RE = re.compile(r'\bd\s*=\s*"([^"]*)"')
FR_RE = re.compile(r'fill-rule\s*=\s*"([^"]*)"')
FILL_RE = re.compile(r'\bfill\s*=\s*"([^"]*)"', re.IGNORECASE)
NUM_RE = re.compile(r'-?\d+\.?\d*(?:e-?\d+)?')

LEGACY_INFERRED_KNOCKOUTS = {
    "book_alef_rashi_24_filled.svg",
    "book_tet_24_filled.svg",
    "clock_add_24_regular.svg",
    "document_word_24_filled.svg",
}


def is_white(value):
    if value is None:
        return False
    value = value.strip().lower().replace(" ", "")
    return value in {"white", "#fff", "#ffffff", "rgb(255,255,255)"}


def read_paths(text):
    out = []
    for m in PATH_RE.finditer(text):
        attrs = m.group(1)
        d = D_RE.search(attrs)
        fr = FR_RE.search(attrs)
        fill = FILL_RE.search(attrs)
        if d:
            out.append((
                d.group(1),
                fr.group(1) if fr else "nonzero",
                fill.group(1) if fill else None,
            ))
    return out


def is_knockout(paths, name=""):
    """True if a whole path sits inside the union of the others: an intended
    white knockout that unioning would destroy. Threshold and detection live in
    glyph_geometry so this stays in lockstep with repair_glyphs.py."""
    if len(paths) < 2:
        return False
    simps = [simplified(d, fr) for d, fr, _ in paths]
    return any(is_white(fill) for _, _, fill in paths) or (
        name in LEGACY_INFERRED_KNOCKOUTS
        and any(is_knockout_index(simps, i) for i in range(len(simps)))
    )


def _count_moves(path):
    return sum(1 for verb, _ in path if verb == pathops.PathVerb.MOVE)


def _count_d_subpaths(d):
    return len(re.findall(r"[Mm]", d))


def overlap_risk(paths):
    """Geometric risk that this icon will corrupt when merged into one glyph.

    Two independent signals, both stable/idempotent (a normalized single clean
    path scores zero):
      * overlap area - the paths' filled regions overlap (area of the parts
        summed exceeds the area of their union), so opposing winding can knock
        holes when the font merges them;
      * welding - the boolean union collapses touching/overlapping sub-paths
        into fewer contours than the sources declare, i.e. hairline seams.
    Returns (overlap_area, weld_count).
    """
    simps = [simplified(d, fr) for d, fr, _ in paths]
    area_sum = sum(abs(s.area) for s in simps)
    u = pathops.Path()
    pathops.union(simps, u.getPen())
    overlap = area_sum - abs(u.area)
    raw = sum(_count_d_subpaths(d) for d, _, _ in paths)
    weld = raw - _count_moves(u)
    return overlap, weld


def _round(dstr, ndigits=6):
    def repl(m):
        v = float(m.group(0))
        r = round(v, ndigits)
        if r == int(r):
            return str(int(r))
        return ("%.*f" % (ndigits, r)).rstrip("0").rstrip(".")
    return NUM_RE.sub(repl, dstr)


def union_d(paths):
    contours = [simplified(d, fr) for d, fr, _ in paths]
    result = pathops.Path()
    pathops.union(contours, result.getPen())
    pen = SVGPathPen(None)
    result.draw(pen)
    return _round(pen.getCommands())


def normalized_svg(text, name=""):
    """Return (new_svg_text or None, reason). None means leave file unchanged."""
    paths = read_paths(text)
    if not paths:
        return None, "no <path> elements"
    if is_knockout(paths, name):
        return None, "intended knockout (skipped)"
    d = union_d(paths)
    new = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
           'viewBox="0 0 24 24"><path d="%s"/></svg>' % d)
    return new, "normalized"


OVERLAP_EPS = 0.02  # square units in the 24x24 canvas; below this is float noise


def main(argv):
    check = "--check" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        files = sorted(glob.glob(os.path.join(SVG_DIR, "*.svg")))

    if check:
        # Geometric, idempotent gate: flag any source whose paths overlap or
        # weld together (would corrupt in the merged glyph). A normalized single
        # clean path scores zero. Intended knockouts are reported as skipped.
        need, skipped = [], []
        for path in files:
            name = os.path.basename(path)
            paths = read_paths(open(path, encoding="utf-8").read())
            if not paths:
                skipped.append((name, "no <path> elements"))
                continue
            if is_knockout(paths, name):
                skipped.append((name, "intended knockout"))
                continue
            overlap, weld = overlap_risk(paths)
            if overlap > OVERLAP_EPS or weld > 0:
                need.append((name, overlap, weld))
        for n, r in skipped:
            print("SKIP  %s: %s" % (n, r))
        for n, ov, wl in need:
            print("NEEDS-NORMALIZE  %s (overlap_area=%.3f, welded_contours=%d)"
                  % (n, ov, wl))
        print("%d file(s) need normalization, %d skipped (knockout/empty)."
              % (len(need), len(skipped)))
        if need:
            print("Run: python3 tool/normalize_svg_overlaps.py  then regenerate.")
        return 1 if need else 0

    changed, skipped = [], []
    for path in files:
        text = open(path, encoding="utf-8").read()
        name = os.path.basename(path)
        new, reason = normalized_svg(text, name)
        if new is None:
            skipped.append((name, reason))
            continue
        if new.strip() == text.strip():
            continue  # already normalized
        open(path, "w", encoding="utf-8").write(new + "\n")
        changed.append(name)
    for n, r in skipped:
        print("skip   %s (%s)" % (n, r))
    for n in changed:
        print("rewrote %s" % n)
    print("Normalized %d file(s); skipped %d." % (len(changed), len(skipped)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
