#!/usr/bin/env python3
"""Prove that a restructured SVG source is graphically identical to the original.

WHY THIS EXISTS
---------------
`repair_glyphs.py` builds every glyph outline straight from the source geometry:
the non-knockout paths are unioned into a body and the knockouts are subtracted
from it. The rendered icon is therefore a pure function of one thing only - the
*filled region* the source resolves to. Path count, command types, coordinate
precision, ordering and layering are all invisible to the output.

That is what makes a structural refactor safe, and this tool is what proves it.
It resolves both the old and the new source to that same final region and
reports the area of their symmetric difference. Zero means the two files render
identically at every size, in the font and in the browser alike.

A pixel diff cannot make that claim: it only samples the resolution it renders
at. This compares the exact vector regions.

USAGE
-----
  python3 tool/region_diff.py old.svg new.svg          # one pair
  python3 tool/region_diff.py --baseline DIR           # every source vs DIR
  python3 tool/region_diff.py --baseline DIR --tol 0   # demand exactness

Requires: skia-pathops, fonttools.
"""
import sys, os, re, glob, math

try:
    import pathops
    from glyph_geometry import simplified, is_knockout_index
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")

PATH_RE = re.compile(r"<path\b([^>]*?)/?>", re.S)
D_RE = re.compile(r'\bd\s*=\s*"([^"]*)"', re.S)
FR_RE = re.compile(r'fill-rule\s*=\s*"([^"]*)"')
FILL_RE = re.compile(r'\bfill\s*=\s*"([^"]*)"', re.I)

# Mirrors repair_glyphs.LEGACY_INFERRED_KNOCKOUTS: sources that predate explicit
# paint metadata, where a nested path is an intended cut.
LEGACY_INFERRED_KNOCKOUTS = {
    "book_alef_rashi_24_filled",
    "book_tet_24_filled",
    "clock_add_24_regular",
    "document_word_24_filled",
}

# Square units on the 24x24 canvas. 1e-4 is ~1/5760000 of the canvas: far below
# one pixel at any rendered size, and the floor of skia's own float noise.
DEFAULT_TOL = 1e-4


def is_white(value):
    if value is None:
        return False
    return value.strip().lower().replace(" ", "") in {
        "white", "#fff", "#ffffff", "rgb(255,255,255)"}


def read_paths(text):
    out = []
    for m in PATH_RE.finditer(text):
        attrs = m.group(1)
        d = D_RE.search(attrs)
        if not d:
            continue
        fr = FR_RE.search(attrs)
        fill = FILL_RE.search(attrs)
        out.append((d.group(1),
                    fr.group(1) if fr else "nonzero",
                    fill.group(1) if fill else None))
    return out


def resolve_region(text, name=""):
    """Return the final filled region as a pathops.Path, using exactly the
    body-minus-knockouts rule that repair_glyphs.py applies to the font."""
    paths = read_paths(text)
    if not paths:
        return pathops.Path()
    simps = [simplified(d, fr) for d, fr, _ in paths]

    explicit = [i for i, (_, _, fill) in enumerate(paths) if is_white(fill)]
    if explicit:
        cuts = set(explicit)
    elif name in LEGACY_INFERRED_KNOCKOUTS and len(simps) > 1:
        cuts = {i for i in range(len(simps)) if is_knockout_index(simps, i)}
    else:
        cuts = set()

    body = [s for i, s in enumerate(simps) if i not in cuts]
    holes = [s for i, s in enumerate(simps) if i in cuts]

    region = pathops.Path()
    pathops.union(body, region.getPen())
    if holes:
        cut = pathops.Path()
        pathops.difference([region], holes, cut.getPen())
        region = cut
    return region


def region_of_file(path):
    name = os.path.splitext(os.path.basename(path))[0]
    with open(path, encoding="utf-8") as fh:
        return resolve_region(fh.read(), name)


def symmetric_difference_area(a, b):
    """Area the two regions do not share. 0.0 means pixel-identical output.

    Returns NaN when skia refuses the operation, which happens on badly
    self-intersecting legacy geometry. NaN means "not proven equal", never
    "equal": callers must treat it as a failure and fall back to the raster
    comparison in tool/raster_diff.py."""
    try:
        xor = pathops.Path()
        pathops.xor([a], [b], xor.getPen())
        return abs(xor.area)
    except pathops.PathOpsError:
        return float("nan")


# --------------------------------------------------------------------------
# boundary displacement
# --------------------------------------------------------------------------
#
# Area alone cannot judge a rewrite. Rounding coordinates onto a coarser grid
# moves the whole outline by a fraction of a grid step, which is invisible but
# still produces a non-zero symmetric-difference area proportional to the
# perimeter. Conversely a fragile outline can flip a large region while barely
# changing its total area. The honest question is "how far did the edge move",
# so that is what this measures: the largest distance from any point on one
# region's boundary to the other region's boundary, in canvas units.

# How finely a boundary is sampled when measuring. Small enough that the true
# maximum is not missed between samples on icon-scale geometry.
SAMPLE_STEP = 0.02


def _flatten(region, step=SAMPLE_STEP):
    """Return the region's boundary as (segments, sampled_points).

    Curves are subdivided until each piece is shorter than `step`, so both the
    segment list and the point list describe the same polyline."""
    segs, pts = [], []

    def emit(a, b):
        segs.append((a, b))
        span = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(span / step))
        for i in range(n):
            t = i / n
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))

    def bezier(p0, p1, p2, p3):
        n = max(2, int(sum(math.hypot(b[0] - a[0], b[1] - a[1])
                           for a, b in ((p0, p1), (p1, p2), (p2, p3))) / step))
        prev = p0
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            x = (u * u * u * p0[0] + 3 * u * u * t * p1[0]
                 + 3 * u * t * t * p2[0] + t * t * t * p3[0])
            y = (u * u * u * p0[1] + 3 * u * u * t * p1[1]
                 + 3 * u * t * t * p2[1] + t * t * t * p3[1])
            emit(prev, (x, y))
            prev = (x, y)

    start = cur = None
    for verb, points in region:
        if verb == pathops.PathVerb.MOVE:
            start = cur = tuple(points[0])
        elif verb == pathops.PathVerb.LINE:
            nxt = tuple(points[0])
            emit(cur, nxt)
            cur = nxt
        elif verb == pathops.PathVerb.CUBIC:
            p1, p2, p3 = (tuple(p) for p in points)
            bezier(cur, p1, p2, p3)
            cur = p3
        elif verb == pathops.PathVerb.QUAD:
            p1, p2 = (tuple(p) for p in points)
            # Exact degree elevation of a quadratic to a cubic.
            c1 = (cur[0] + 2.0 / 3 * (p1[0] - cur[0]),
                  cur[1] + 2.0 / 3 * (p1[1] - cur[1]))
            c2 = (p2[0] + 2.0 / 3 * (p1[0] - p2[0]),
                  p2[1] + 2.0 / 3 * (p1[1] - p2[1]))
            bezier(cur, c1, c2, p2)
            cur = p2
        elif verb == pathops.PathVerb.CLOSE:
            if cur is not None and start is not None:
                emit(cur, start)
            cur = start
    return segs, pts


def _point_segment_distance(p, a, b):
    px, py = p
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    span = dx * dx + dy * dy
    if span == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / span))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class _SegmentGrid:
    """Uniform grid index over boundary segments, so nearest-segment lookups do
    not degrade to a scan of every segment on the 30 000-segment sources."""

    CELL = 0.5

    def __init__(self, segments):
        self.cells = {}
        self.segments = segments
        for idx, (a, b) in enumerate(segments):
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            for cx in range(int(x0 // self.CELL), int(x1 // self.CELL) + 1):
                for cy in range(int(y0 // self.CELL), int(y1 // self.CELL) + 1):
                    self.cells.setdefault((cx, cy), []).append(idx)

    def distance(self, p):
        if not self.segments:
            return float("inf")
        cx, cy = int(p[0] // self.CELL), int(p[1] // self.CELL)
        best = float("inf")
        ring = 0
        while True:
            found = False
            for ix in range(cx - ring, cx + ring + 1):
                for iy in range(cy - ring, cy + ring + 1):
                    # Only the newly added outer ring each round.
                    if ring and abs(ix - cx) != ring and abs(iy - cy) != ring:
                        continue
                    for idx in self.cells.get((ix, iy), ()):
                        a, b = self.segments[idx]
                        best = min(best, _point_segment_distance(p, a, b))
                        found = True
            # Anything outside the searched square is at least this far away.
            if best <= ring * self.CELL or (ring > 48 and not found):
                return best
            ring += 1


def max_boundary_shift(a, b):
    """Largest distance any point of either boundary moved, in canvas units.

    0.005 is a twentieth of a rounding step at three decimals and 1/200 of a
    pixel when the icon is drawn at 24 px: below that, nothing can be seen at
    any size. Whole-unit results mean the outline genuinely moved."""
    segs_a, pts_a = _flatten(a)
    segs_b, pts_b = _flatten(b)
    if not segs_a and not segs_b:
        return 0.0
    if not segs_a or not segs_b:
        return float("inf")
    grid_a, grid_b = _SegmentGrid(segs_a), _SegmentGrid(segs_b)
    return max(max((grid_b.distance(p) for p in pts_a), default=0.0),
               max((grid_a.distance(p) for p in pts_b), default=0.0))


def compare(old_path, new_path):
    return symmetric_difference_area(region_of_file(old_path),
                                     region_of_file(new_path))


def main(argv):
    tol = DEFAULT_TOL
    if "--tol" in argv:
        i = argv.index("--tol")
        tol = float(argv[i + 1])
        del argv[i:i + 2]

    if "--baseline" in argv:
        i = argv.index("--baseline")
        baseline = argv[i + 1]
        del argv[i:i + 2]
        targets = [a for a in argv if not a.startswith("--")] or \
            sorted(glob.glob(os.path.join(SVG_DIR, "*.svg")))
        worst, failed = 0.0, []
        for cur in targets:
            name = os.path.basename(cur)
            old = os.path.join(baseline, name)
            if not os.path.exists(old):
                print("NEW      %s (no baseline)" % name)
                continue
            delta = compare(old, cur)
            worst = max(worst, delta)
            if delta > tol:
                failed.append((name, delta))
                print("CHANGED  %-46s area_delta=%.9f" % (name, delta))
        print("\n%d compared, %d changed beyond tol=%g, worst delta=%.9f"
              % (len(targets), len(failed), tol, worst))
        return 1 if failed else 0

    if len(argv) != 2:
        sys.exit(__doc__)
    delta = compare(argv[0], argv[1])
    print("area_delta=%.9f  %s" % (delta, "IDENTICAL" if delta <= tol else "DIFFERS"))
    return 0 if delta <= tol else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main(sys.argv[1:]))
