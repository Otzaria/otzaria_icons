#!/usr/bin/env python3
"""Rewrite icon sources into one canonical, hand-editable form.

WHY THIS EXISTS
---------------
The sources were produced by several different editors and export pipelines over
time, then patched by hand. The result renders correctly but is very hard to
work on: every file is a single unbroken line, coordinates carry up to sixteen
decimals of float noise, commands mix absolute and relative forms, arcs and
smooth-curve shorthands appear in some files and not others, and repeated edits
have left zero-length segments and duplicate points behind.

This tool rewrites each source into one shape everybody can read and edit:

  * absolute commands only, no relative or smooth-curve shorthand;
  * arcs resolved to cubics (an OpenType glyph has no arc operator anyway, so
    the font already sees them this way);
  * coordinates rounded to a fixed decimal precision;
  * degenerate leftovers dropped - zero-length segments, curves that collapse to
    a point, and points repeated on top of each other;
  * curves that are geometrically straight written as lines, and axis-aligned
    lines written as H/V, which is what makes a rectilinear icon readable;
  * one subpath per line, indented, so a contour can actually be found and
    edited by eye.

It changes how the geometry is *written*, never which region it covers. Every
run is checked against tool/region_diff.py, which resolves both the old and the
new file to the exact filled region the font is built from and refuses any
rewrite whose region moved.

USAGE
-----
  python3 tool/format_svg.py                    # format every source in place
  python3 tool/format_svg.py a.svg b.svg        # format specific files
  python3 tool/format_svg.py --check            # report, change nothing
  python3 tool/format_svg.py --precision 4      # override decimal precision

Requires: skia-pathops, fonttools.
"""
import sys, os, re, glob, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fontTools.svgLib.path import parse_path
    from fontTools.pens.recordingPen import RecordingPen
    from region_diff import resolve_region, max_boundary_shift
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")

PATH_RE = re.compile(r"<path\b([^>]*?)/?>", re.S)
ATTR_RE = re.compile(r'([-\w:.]+)\s*=\s*"([^"]*)"', re.S)
SVG_OPEN_RE = re.compile(r"<svg\b([^>]*)>", re.S)

# Precision is chosen per file, not fixed. Three decimals is what a person can
# actually read and edit, and it is enough for icons drawn on a 24-unit canvas
# with half-unit geometry - which is most of them. But a few sources were traced
# from font glyphs and carry real detail below a thousandth of a unit; rounding
# those to three decimals visibly moves their outline. So each file is formatted
# at the coarsest precision that provably does not move it, starting at three.
PRECISIONS = (3, 4, 5, 6)
PRECISION = PRECISIONS[0]

# How far the outline may move, in canvas units, for a rewrite to count as
# graphically identical. 0.002 is a twelve-thousandth of the icon: 0.002 px when
# the icon is drawn at 24 px, and still only 0.04 px blown up to 512 px, which
# is below one subpixel of the highest-resolution rendering the package makes.
# Nothing at or under this can be seen at any size.
SHIFT_TOL = 0.002

# Every tolerance below is derived from the rounding grid rather than fixed, and
# always sits strictly under half a grid step. That is what keeps the cleanup
# passes honest: after rounding, two distinct coordinates differ by at least one
# full grid step, so these tests can only ever collapse points that rounding
# already made identical, or straighten a curve rounding already flattened. The
# rounding is then the single geometric change the tool makes, which is the one
# thing region_diff.py has to verify. A fixed epsilon larger than the grid would
# silently move points instead, and did: it moved whole edges on the icons whose
# outlines run within a thousandth of a unit of each other.
def epsilons(precision):
    """(point_eps, flatness_eps) for a rounding grid of `precision` decimals."""
    grid = 10.0 ** -precision
    return grid * 0.5, grid * 0.5

# Attribute order on the root <svg>, so every file opens the same way.
SVG_ATTR_ORDER = ["xmlns", "width", "height", "viewBox", "fill", "data-preserve-overlap"]
# Attribute order on each <path>. `id` first: it is the label a person reads.
PATH_ATTR_ORDER = ["id", "fill", "fill-rule", "d"]


# --------------------------------------------------------------------------
# number formatting
# --------------------------------------------------------------------------

def fnum(v, precision=PRECISION):
    """Shortest readable spelling of a coordinate: no trailing zeros, no '-0',
    and no exponent notation."""
    r = round(v + 0.0, precision)
    if r == 0:
        return "0"
    if r == int(r):
        return str(int(r))
    return ("%.*f" % (precision, r)).rstrip("0").rstrip(".")


def rnum(v, precision=PRECISION):
    return float(fnum(v, precision))


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def same_point(a, b, eps):
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= eps


def _point_line_distance(p, a, b, eps):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    span = math.hypot(dx, dy)
    if span <= eps:
        return math.hypot(px - ax, py - ay)
    return abs(dy * (px - ax) - dx * (py - ay)) / span


def is_flat(start, controls, end, eps):
    """True if every control point lies on the segment start->end, i.e. the
    curve traces the straight line and can be written as one."""
    return all(_point_line_distance(c, start, end, eps) <= eps for c in controls)


# --------------------------------------------------------------------------
# path parsing and cleanup
# --------------------------------------------------------------------------

def parse_segments(d):
    """Parse a `d` string into absolute contours using the same parser the font
    pipeline uses, so nothing is reinterpreted along the way.

    Returns a list of contours; each contour is (start_point, [segments]) where
    a segment is ('L', end), ('C', c1, c2, end) or ('Q', c, end)."""
    pen = RecordingPen()
    parse_path(d, pen)

    contours, current, start = [], None, None
    last = None
    for op, args in pen.value:
        if op == "moveTo":
            if current is not None:
                contours.append((start, current))
            start = tuple(args[0])
            last = start
            current = []
        elif op == "lineTo":
            end = tuple(args[0])
            current.append(("L", end))
            last = end
        elif op == "curveTo":
            pts = [tuple(p) for p in args]
            # A pen may emit a TrueType-style chain; split it into cubics.
            for i in range(0, len(pts) - 2, 2):
                current.append(("C", pts[i], pts[i + 1], pts[i + 2]))
                last = pts[i + 2]
            if len(pts) == 1:
                current.append(("L", pts[0]))
                last = pts[0]
        elif op == "qCurveTo":
            pts = [tuple(p) for p in args if p is not None]
            if len(pts) == 1:
                current.append(("L", pts[0]))
                last = pts[0]
            else:
                # Implied on-curve points sit midway between consecutive
                # off-curve points; this is the standard TrueType expansion.
                for i in range(len(pts) - 1):
                    ctrl = pts[i]
                    if i == len(pts) - 2:
                        end = pts[-1]
                    else:
                        nxt = pts[i + 1]
                        end = ((ctrl[0] + nxt[0]) / 2.0, (ctrl[1] + nxt[1]) / 2.0)
                    current.append(("Q", ctrl, end))
                    last = end
        elif op in ("closePath", "endPath"):
            if current is not None:
                contours.append((start, current))
            current, start, last = None, None, None
    if current is not None:
        contours.append((start, current))
    return [c for c in contours if c[0] is not None]


def clean_contour(start, segments, precision):
    """Round, then drop what rounding revealed to be nothing: segments that end
    where they began, curves that collapsed onto their endpoints, and curves
    that are straight."""
    point_eps, flat_eps = epsilons(precision)

    def R(p):
        return (rnum(p[0], precision), rnum(p[1], precision))

    start = R(start)
    out, cur = [], start
    for seg in segments:
        kind = seg[0]
        pts = [R(p) for p in seg[1:]]
        end = pts[-1]
        controls = pts[:-1]

        if same_point(cur, end, point_eps) and \
                all(same_point(c, cur, point_eps) for c in controls):
            continue  # the whole segment collapsed to a point
        if kind in ("C", "Q") and is_flat(cur, controls, end, flat_eps):
            kind, controls = "L", []
        out.append((kind, controls, end))
        cur = end

    # A trailing line back onto the start point is what Z already means.
    while out and out[-1][0] == "L" and same_point(out[-1][2], start, point_eps):
        out.pop()
    return start, out


def contour_area(start, segments):
    """Signed polygon area of the contour's on-curve points; used only to spot
    contours that have shrunk to nothing."""
    pts = [start] + [s[2] for s in segments]
    total = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


# --------------------------------------------------------------------------
# emitting
# --------------------------------------------------------------------------

def emit_contour(start, segments, precision):
    """Write one contour as a single readable line of path data."""
    N = lambda v: fnum(v, precision)
    point_eps, _ = epsilons(precision)
    parts = ["M%s %s" % (N(start[0]), N(start[1]))]
    cur = start
    for kind, controls, end in segments:
        if kind == "L":
            if abs(end[1] - cur[1]) < point_eps:
                parts.append("H%s" % N(end[0]))
            elif abs(end[0] - cur[0]) < point_eps:
                parts.append("V%s" % N(end[1]))
            else:
                parts.append("L%s %s" % (N(end[0]), N(end[1])))
        elif kind == "C":
            (c1, c2) = controls
            parts.append("C%s %s %s %s %s %s" % (
                N(c1[0]), N(c1[1]), N(c2[0]), N(c2[1]), N(end[0]), N(end[1])))
        elif kind == "Q":
            c = controls[0]
            parts.append("Q%s %s %s %s" % (N(c[0]), N(c[1]), N(end[0]), N(end[1])))
        cur = end
    parts.append("Z")
    return " ".join(parts)


def format_path_data(d, precision=PRECISION, indent="    "):
    """Return the canonical multi-line form of a `d` string."""
    point_eps, _ = epsilons(precision)
    lines = []
    for start, segments in parse_segments(d):
        start, segments = clean_contour(start, segments, precision)
        if not segments:
            continue  # contour collapsed away entirely
        if abs(contour_area(start, segments)) < point_eps and \
                all(s[0] == "L" for s in segments):
            continue  # a zero-area sliver of straight lines paints nothing
        lines.append(emit_contour(start, segments, precision))
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0]
    sep = "\n" + indent + "   "
    return sep.join(lines)


# --------------------------------------------------------------------------
# document rewriting
# --------------------------------------------------------------------------

def format_svg(text, precision=PRECISION):
    """Return the canonical form of a whole icon source."""
    svg_open = SVG_OPEN_RE.search(text)
    svg_attrs = dict(ATTR_RE.findall(svg_open.group(1))) if svg_open else {}
    svg_attrs.setdefault("xmlns", "http://www.w3.org/2000/svg")
    svg_attrs["width"] = "24"
    svg_attrs["height"] = "24"
    svg_attrs["viewBox"] = "0 0 24 24"

    paths = []
    for m in PATH_RE.finditer(text):
        attrs = dict(ATTR_RE.findall(m.group(1)))
        if "d" not in attrs:
            continue
        attrs["d"] = format_path_data(attrs["d"], precision)
        if not attrs["d"]:
            continue
        paths.append(attrs)

    def render_attrs(attrs, order, sep):
        keys = [k for k in order if k in attrs] + \
               [k for k in sorted(attrs) if k not in order]
        return sep.join('%s="%s"' % (k, attrs[k]) for k in keys)

    out = ["<svg " + render_attrs(svg_attrs, SVG_ATTR_ORDER, "\n     ") + ">"]
    for attrs in paths:
        out.append("  <path " + render_attrs(attrs, PATH_ATTR_ORDER, "\n        ") + "/>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def choose_format(original, name, precisions, tol):
    """Format at the coarsest precision that provably does not move the outline.

    Returns (text, precision, shift), or (None, None, shift) when even the
    finest precision cannot reproduce the source - which never happens on
    well-formed geometry and means the file needs a human."""
    baseline = resolve_region(original, name)
    worst = float("inf")
    for precision in precisions:
        candidate = format_svg(original, precision)
        shift = max_boundary_shift(baseline, resolve_region(candidate, name))
        worst = min(worst, shift)
        if shift <= tol:
            return candidate, precision, shift
    return None, None, worst


def process(path, precisions, check, tol):
    name = os.path.splitext(os.path.basename(path))[0]
    with open(path, encoding="utf-8") as fh:
        original = fh.read()

    formatted, precision, shift = choose_format(original, name, precisions, tol)
    if formatted is None:
        return "REFUSED", None, shift
    if formatted == original:
        return "unchanged", precision, shift
    if not check:
        # newline="\n" because .gitattributes pins *.svg to LF; without it
        # Python rewrites every line ending on Windows and each run shows up as
        # a whole-file diff.
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(formatted)
    return "formatted", precision, shift


def main(argv):
    check = "--check" in argv
    precisions = PRECISIONS
    tol = SHIFT_TOL
    if "--precision" in argv:
        i = argv.index("--precision")
        precisions = (int(argv[i + 1]),)
        del argv[i:i + 2]
    if "--tol" in argv:
        i = argv.index("--tol")
        tol = float(argv[i + 1])
        del argv[i:i + 2]

    files = [a for a in argv if not a.startswith("--")] or \
        sorted(glob.glob(os.path.join(SVG_DIR, "*.svg")))

    counts, by_precision, refused, worst = {}, {}, [], 0.0
    for path in files:
        status, precision, shift = process(path, precisions, check, tol)
        counts[status] = counts.get(status, 0) + 1
        if status == "REFUSED":
            refused.append(os.path.basename(path))
            print("REFUSED  %-46s best shift=%.5f" % (os.path.basename(path), shift))
            continue
        by_precision[precision] = by_precision.get(precision, 0) + 1
        worst = max(worst, shift)

    print("%s: %s" % ("check" if check else "format",
                      ", ".join("%d %s" % (v, k) for k, v in sorted(counts.items()))))
    print("precision used: %s" % ", ".join(
        "%d decimals: %d files" % (p, n) for p, n in sorted(by_precision.items())))
    print("worst outline movement: %.5f canvas units (limit %.5f)" % (worst, tol))
    if refused:
        print("Refused files were left untouched.")
        return 1
    if check and counts.get("formatted"):
        print("Run: python3 tool/format_svg.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
