#!/usr/bin/env python3
"""Rewrite each glyph outline in the generated OTF directly from its source SVG.

WHY THIS EXISTS
---------------
`icon_font_generator` builds the OTF from the SVG sources, but its outline
converter distorts a few complex glyphs even when the source is a clean, single,
correctly-wound path: it translated `book_open_large_search_24_filled` ~4 units
left and mangled contours in `stander_24_filled` / `search_in_the_text_24_regular`.
These defects are internal to the pinned generator and unrelated to the source.

This step runs AFTER `dart run tool/generate.dart`. For every icon it rebuilds
the CFF charstring straight from the committed source, mapping the 24x24 canvas
onto the em (y-flipped) with no re-fitting, so the font geometry is byte-for-byte
what the source (and docs/icon_catalog.svg) show. All font structure, names,
codepoints, advance widths, and metadata produced by the generator are preserved.

Interior-knockout icons (document_word, document_bullet_list, book_open_alef) are
rebuilt as `body` minus the knocked-out shapes via a boolean difference, so the
cut is transparent regardless of the source winding. This is what fixed the alef
in book_open_alef_24_filled, which the generator had filled solid black.

Deterministic: identical sources produce an identical charstring, and the OTF
head timestamp set by the generator is preserved, so `generate.dart --check`
stays reproducible when this step is part of the pipeline.

Requires: skia-pathops, fonttools.
"""
import sys, os, re, yaml

try:
    import pathops
    from fontTools.ttLib import TTFont
    from fontTools.svgLib.path import parse_path
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.pens.transformPen import TransformPen
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH_RE = re.compile(r'<path\b([^>]*?)/?>')
D_RE = re.compile(r'\bd\s*=\s*"([^"]*)"')
FR_RE = re.compile(r'fill-rule\s*=\s*"([^"]*)"')


def read_paths(text):
    out = []
    for m in PATH_RE.finditer(text):
        d = D_RE.search(m.group(1))
        fr = FR_RE.search(m.group(1))
        if d:
            out.append((d.group(1), fr.group(1) if fr else "nonzero"))
    return out


def _simplified(d, fr):
    p = pathops.Path()
    parse_path(d, p.getPen())
    p.fillType = (pathops.FillType.EVEN_ODD if fr == "evenodd"
                  else pathops.FillType.WINDING)
    return pathops.simplify(p)


def knockout_outline(paths):
    """For an interior-knockout icon, return a pathops.Path of (body minus the
    knocked-out shapes) so the cut renders transparent regardless of the source
    winding; otherwise return None (the glyph is drawn straight from its paths).

    A path whose filled area sits >97% inside the union of the other paths is
    treated as a knockout (the alef in book_open_alef_24_filled, the "W" in
    document_word_24_filled, the bullets in document_bullet_list_24_filled).
    """
    if len(paths) < 2:
        return None
    simps = [_simplified(d, fr) for d, fr in paths]
    holes, body = [], []
    for i, s in enumerate(simps):
        others = [x for j, x in enumerate(simps) if j != i]
        u = pathops.Path()
        pathops.union(others, u.getPen())
        inter = pathops.Path()
        pathops.intersection([s], [u], inter.getPen())
        inside = abs(inter.area) / abs(s.area) if abs(s.area) > 1e-6 else 0
        (holes if inside > 0.97 else body).append(s)
    if not holes:
        return None
    solid = pathops.Path()
    pathops.union(body, solid.getPen())
    cut = pathops.Path()
    pathops.union(holes, cut.getPen())
    result = pathops.Path()
    pathops.difference([solid], [cut], result.getPen())
    return result


def main(argv):
    check = "--check" in argv
    cfg = yaml.safe_load(open(os.path.join(ROOT, "tool", "config.yaml")))
    font_path = os.path.join(ROOT, cfg["font_file"])
    src_dir = os.path.join(ROOT, cfg["source_directory"])
    manifest = yaml.safe_load(open(os.path.join(ROOT, cfg["manifest_file"])))

    # recalcTimestamp=False preserves the generator's fixed head timestamp so
    # the repaired OTF stays byte-for-byte reproducible.
    font = TTFont(font_path, recalcTimestamp=False)
    upm = font["head"].unitsPerEm
    scale = upm / 24.0
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    cff = font["CFF "].cff
    top = cff[cff.fontNames[0]]
    charStrings = top.CharStrings
    # 24x24 canvas (y-down) -> em (y-up): scale(scale,-scale), translate(0,upm)
    transform = (scale, 0, 0, -scale, 0, upm)

    rebuilt, knockouts = [], 0
    for icon in manifest["icons"]:
        name = icon["name"]
        glyph_name = cmap[icon["codepoint"]]
        paths = read_paths(open(os.path.join(src_dir, name + ".svg")).read())
        advance = hmtx[glyph_name][0]
        pen = T2CharStringPen(advance, None)
        tpen = TransformPen(pen, transform)
        outline = knockout_outline(paths)
        if outline is not None:
            outline.draw(tpen)  # body minus transparent cuts
            knockouts += 1
        else:
            for d, _ in paths:
                parse_path(d, tpen)
        cs = pen.getCharString(private=top.Private)
        rebuilt.append((glyph_name, cs, name))

    if check:
        # Report only whether the on-disk glyphs already match the sources.
        mismatched = []
        for glyph_name, cs, name in rebuilt:
            if charStrings[glyph_name].compile() != cs.compile():
                mismatched.append(name)
        for n in mismatched:
            print("STALE-GLYPH  %s" % n)
        print("%d glyph(s) differ from source." % len(mismatched))
        return 1 if mismatched else 0

    for glyph_name, cs, _ in rebuilt:
        charStrings[glyph_name] = cs
    font.save(font_path)
    print("Repaired %d glyph(s) from source (%d interior knockouts)."
          % (len(rebuilt), knockouts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
