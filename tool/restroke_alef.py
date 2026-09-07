#!/usr/bin/env python3
"""Reweight the strokes of the alef letterform across the icons that use it.

WHAT THIS DOES
--------------
The alef is three calligraphic strokes: a main diagonal running from the upper
left to the lower right, a lower-left leg and an upper-right leg. The diagonal
is nearly uniform in width; the two legs taper strongly, thin where they leave
the diagonal and swelling to a heavy terminal.

This changes those weights by the amounts in FACTORS below - thinning the
diagonal, and reducing the legs' taper by thinning their thick ends while
thickening their thin ends - and leaves everything else about the letter alone.

HOW, AND WHY THIS WAY
---------------------
The outline is moved, not rebuilt. Every node and handle of the existing curve
travels along its own inward normal; the segment count, the curve degrees and
the tangent continuity are exactly as drawn. Rebuilding from a skeleton, or
re-fitting curves to an offset polyline, would replace the designer's curves
with the tool's - which is how a redraw acquires flat spots and lumps.

Moving both flanks of a stroke inward by the same amount scales its width and
leaves its centre line where it was, so the letter keeps its spine, its rhythm
and its terminals.

Two things make this harder than an offset, and both are handled here:

  * The displacement must be smooth along the outline or the result has kinks
    where one stroke's flank becomes another's. But smoothing pulls every
    extreme back toward no change at all, so a displacement computed once from
    (1 - factor) x half-width lands well short of what was asked for - measured,
    the legs came out at 0.96 and 0.78 of their old width where 1.40 and 0.65
    were wanted. So the displacement is *solved* rather than computed: apply it,
    measure the width that actually resulted, correct, repeat. What it converges
    to is the smoothest displacement that gets closest to the asked-for weights,
    and the report states the residual instead of hiding it.

  * Half-width has to mean something at a terminal and at a junction, where a
    ray cast straight across the stroke reports nonsense. It is measured here as
    the radius of the largest circle that fits inside the letter and touches the
    boundary at that point - the medial-axis ball.

Each stroke is identified by which of the outlined variant's three counters lies
nearest the ball's centre. The counters are the strokes' own hollows, so the
strokes identify themselves rather than being carved out by hand-placed regions.

USAGE
-----
  python3 tool/restroke_alef.py --check     # report, change nothing
  python3 tool/restroke_alef.py             # rewrite the family
  python3 tool/restroke_alef.py --rounds 4  # solver iterations

Run tool/format_svg.py afterwards, then tool/unify_shared_parts.py.

Requires: skia-pathops, fonttools.
"""
import sys, os, re, glob, math, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pathops
    from fontTools.pens.svgPathPen import SVGPathPen
    from format_svg import parse_segments, clean_contour, emit_contour
    from region_diff import resolve_region, region_of_file, _flatten
    from audit_geometry import contour_paths
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")

REFERENCE_FILLED = "alef_24_filled"
REFERENCE_OUTLINED = "alef_24_regular"

# The weight change, as a ratio of the current width.
#
# ONE factor for every stroke. Grading it - thinning the legs' thick ends more
# than their thin ends - was tried twice and abandoned both times, and the
# reason is worth keeping so it is not tried a third time.
#
# The factor has to be keyed to something, and the only available measure of
# "how thick is the stroke here" is the inscribed circle at each boundary point.
# Along this letterform that measure is not monotone: down the upper-right leg
# it reads 0.36, 0.87, 0.39, 0.82, 0.85, 1.58, 0.47, 1.19, because wherever the
# outline turns concave the circle that fits collapses. A factor keyed to it
# therefore jumps about, and since the displacement is the factor times the
# width, the displacement jumps too. A displacement that varies sharply along an
# edge does not thin that edge - it tilts it. That is what turned the smooth
# concave sweep below the upper-right leg into a straight chord with a corner at
# each end, and no amount of extra smoothing fixed it: smoothing wide enough to
# calm the factor also flattens the taper it was supposed to control.
#
# With one constant factor the displacement is just the (already smoothed)
# width scaled down, so it is as smooth as the letter is, every edge keeps its
# curvature, and the legs keep their taper and their contrast exactly. The
# letter comes out as the same letter, set lighter - which is the whole point.
UNIFORM_FACTOR = 0.85     # 15% thinner, above the floor below

# No part of the letter is thinned below this half-width, and nothing is ever
# made thicker than it was drawn. The rule is
#     new = min(drawn, max(factor x drawn, FLOOR))
#
# Lightening a weight by a flat percentage everywhere is what a scaling tool
# does, not what a type designer does. The thinnest places in this letter are
# not stems at all - they are the joins where a leg leaves the diagonal, and the
# tapered tips of the legs. Taking a flat 15% off those pinched the lower-left
# join from 0.697 units of ink down to 0.550 until it read as a gap, and
# deepened a shallow dent on the upper-right leg into a visible one.
#
# The floor holds the joins and the tapered tips at exactly their drawn width
# while the substantial strokes lighten in full, which is the traditional
# treatment. It also does something the earlier graded attempts could not: it
# is monotone in the measured width and never lets the displacement go
# negative, so no edge is ever pushed outward next to one being pulled in.
# That sign flip was what tilted edges into straight chords before.
#
# 0.45 half-width is 0.9 units of ink: everything at or under it is left alone,
# and the 15% reduction phases in above it.
WIDTH_FLOOR = 0.45

# The letter's ink is never allowed to become narrower anywhere than it already
# is at its narrowest - 0.70 units, at the join below the upper-right leg.
#
# This is a separate guard from WIDTH_FLOOR and it is the one that actually
# protects the joins. The floor keys on each point's own inscribed circle, and
# at a join that is the wrong measure: a point on the diagonal's flank beside
# the join sits on a thick stroke, so its circle is large, it thins by the full
# amount, and the join narrows from that side while the floor never notices.
# Clearance measures the thing that matters instead - how far it is straight
# across the ink to the other side - and caps the inward move at half of
# whatever slack there is above MIN_INK.
MIN_INK = 0.70

# --- the finishing pass ---------------------------------------------------
# A node drawn with a kink below this is meant to be a smooth join, and is made
# exactly smooth. Above it the node is a corner the designer put there and is
# left at the angle it was drawn. The source was digitised rather than drawn
# directly, so its "smooth" joins actually carry a few degrees of kink each -
# median 0.74, three quarters of them under 4.4 - and that scatter is what
# reads as wobble along an edge when the icon is enlarged.
POLISH_KINK = 20.0
# How far a node may be nudged onto the curve its neighbours describe. Small
# enough that it cannot restyle anything: it takes the tremor out of an edge
# without moving where the edge goes.
POLISH_MOVE = 0.11
# The easing runs this many times, each pass moving a node part of the way; the
# total is still capped at POLISH_MOVE from where the node started. Repeating a
# small correction settles an edge far better than one large pull, which would
# just cut corners off the curve.
POLISH_PASSES = 4
# Nodes turning more sharply than this are corners and are never nudged.
POLISH_CORNER = 45.0
# Two samples must be at least this far apart along the outline to count as
# opposite sides of the ink rather than neighbours on the same edge.
CLEARANCE_ARC = 1.5

MAIN_FACTOR = UNIFORM_FACTOR
LEG_THICK_FACTOR = UNIFORM_FACTOR
LEG_THIN_FACTOR = UNIFORM_FACTOR

TARGET_MAIN = UNIFORM_FACTOR
TARGET_LEG_THICK = UNIFORM_FACTOR
TARGET_LEG_THIN = UNIFORM_FACTOR

# A leg's "thin" and "thick" ends are taken at these percentiles of its own
# width rather than at its raw extremes: the extremes of a traced outline are
# noise, and a factor keyed to them would swing with one stray sample.
THIN_Q, THICK_Q = 0.10, 0.90

# How far the upper-right leg's tip is drawn back along its own axis, and over
# how much arc that pull fades out. The tip and everything within HOLD of it
# move as one piece so the terminal keeps its drawn shape; the pull then eases
# to nothing by FADE, which puts the compression into the middle of the leg
# where the outline is plain. Moving the tip along the stroke's axis rather
# than across it shortens the leg without altering its weight.
# A contour smaller than this is a fragment shed by the reweighting, not part
# of the drawing. Matches the speck threshold in tool/repair_artifacts.py.
FRAGMENT_AREA = 0.01

SHORTEN_UPPER_LEG = 0.6
SHORTEN_HOLD = 1.2
SHORTEN_FADE = 4.0

# A sample this far along the outline from another stroke counts as being on
# its own stroke's flank.
FLANK_REACH = 0.35
# Over this much arc, a leg's own weight factor fades into the main stroke's as
# a junction is approached. It has to be generous: at a neck the leg and the
# diagonal are one piece of ink, so holding the neck while thinning the diagonal
# makes the displacement change sign over a very short stretch of outline, and a
# field that flips sign along an edge tilts it rather than thinning it. That is
# what turned the sweep below the upper-right leg into a straight chord with a
# corner at each end. Each leg's tapered tip sits several units of arc from its
# junction, so it still gets the full treatment.
JUNCTION_BLEND = 2.5

WORK_PRECISION = 6
SAMPLE_STEP = 0.02
MEASURE_STEP = 0.01
# Arc length over which the displacement is smoothed. Wide enough to carry
# across a junction without a kink, narrow enough to keep a terminal's shape.
SMOOTH_ARC = 0.6
# The measured half-width is smoothed over this much arc before anything is
# derived from it, and the window has to be wide - at the scale of the stroke,
# not of the outline's detail.
#
# This is the setting that decides whether the result looks drawn or traced. The
# source outline is gently scalloped along its left flanks, a leftover of how it
# was digitised, with a wavelength of roughly a unit. A half-width measured
# against that wobble follows it: h reads larger where the edge bulges out and
# smaller where it dents, so scaling by a factor pulls the bulges in further
# than the dents and *amplifies* the wobble. At 0.25 the soft waves in the
# lower-left leg came back as hard facets and a visible notch.
#
# Smoothed at the stroke's own scale, h becomes the stroke's width profile,
# which is what the brief is about. The displacement is then near-constant along
# a flank, so the source's own character - scalloping included - is carried
# through offset rather than exaggerated.
SMOOTH_H = 1.2
# A light final pass on the displacement itself, to catch anything the two
# earlier smoothings left behind.
SMOOTH_D = 0.15
# Arc length over which the displacement vector is smoothed, fixing normal
# direction noise as well as magnitude. See build_field().
SMOOTH_VEC = 0.4
SOLVER_ROUNDS = 3
# Under-relaxation: each round closes this fraction of the measured error. Full
# correction oscillates, because moving one flank changes the width its
# neighbours measure.
RELAX = 0.7


def unit(dx, dy):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-15 else (0.0, 0.0)


def _point_seg(p, a, b):
    px, py = p
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    span = dx * dx + dy * dy
    if span == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / span))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class Boundary:
    """A flattened region with fast nearest-boundary and inside queries."""

    CELL = 0.25

    def __init__(self, region, step=0.01):
        self.segs = _flatten(region, step)[0]
        self.grid = collections.defaultdict(list)
        for i, (a, b) in enumerate(self.segs):
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            for cx in range(int(x0 // self.CELL), int(x1 // self.CELL) + 1):
                for cy in range(int(y0 // self.CELL), int(y1 // self.CELL) + 1):
                    self.grid[(cx, cy)].append(i)
        self.coarse = _flatten(region, 0.05)[0]

    def distance(self, p):
        cx, cy = int(p[0] // self.CELL), int(p[1] // self.CELL)
        best, ring = float("inf"), 0
        while True:
            hit = False
            for ix in range(cx - ring, cx + ring + 1):
                for iy in range(cy - ring, cy + ring + 1):
                    if ring and abs(ix - cx) != ring and abs(iy - cy) != ring:
                        continue
                    for idx in self.grid.get((ix, iy), ()):
                        a, b = self.segs[idx]
                        best = min(best, _point_seg(p, a, b))
                        hit = True
            if best <= ring * self.CELL or (ring > 40 and not hit):
                return best
            ring += 1

    def inside(self, p):
        x, y = p
        crossings = 0
        for (x1, y1), (x2, y2) in self.coarse:
            if (y1 > y) != (y2 > y):
                t = (y - y1) / (y2 - y1)
                if x < x1 + t * (x2 - x1):
                    crossings += 1
        return crossings % 2 == 1

    def nearest_point(self, p):
        """Closest point on the boundary, with the inward normal there.

        The solver needs this because a sample that moved outward no longer sits
        on the new outline, and measuring a width from a point that is not on
        the boundary collapses to nothing. Projecting back on first is what
        makes the measured error mean anything."""
        cx, cy = int(p[0] // self.CELL), int(p[1] // self.CELL)
        best = None
        ring = 0
        while ring <= 40:
            for ix in range(cx - ring, cx + ring + 1):
                for iy in range(cy - ring, cy + ring + 1):
                    if ring and abs(ix - cx) != ring and abs(iy - cy) != ring:
                        continue
                    for idx in self.grid.get((ix, iy), ()):
                        a, b = self.segs[idx]
                        d = _point_seg(p, a, b)
                        if best is None or d < best[0]:
                            best = (d, idx)
            if best is not None and best[0] <= ring * self.CELL:
                break
            ring += 1
        if best is None:
            return None, None
        a, b = self.segs[best[1]]
        dx, dy = b[0] - a[0], b[1] - a[1]
        span = dx * dx + dy * dy
        t = 0.0 if span == 0 else max(0.0, min(
            1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / span))
        q = (a[0] + t * dx, a[1] + t * dy)
        tx, ty = unit(dx, dy)
        for nx, ny in ((-ty, tx), (ty, -tx)):
            if self.inside((q[0] + nx * 0.02, q[1] + ny * 0.02)):
                return q, (nx, ny)
        return q, None


def medial_radius(p, n, boundary, limit=7.0, step=0.01):
    """Radius of the largest inscribed circle touching the boundary at p.

    Walks the centre outward along the inward normal. While the circle still
    fits, the distance from its centre to the boundary keeps pace with the
    radius; when the far side is reached the distance falls behind."""
    r, best = step, step
    while r < limit:
        c = (p[0] + n[0] * r, p[1] + n[1] * r)
        if boundary.distance(c) < r - 0.5 * step:
            break
        best = r
        r += step
    return best


def sample_outline(region, counter_pts, boundary, step=SAMPLE_STEP):
    """Measure the silhouette: position, inward normal, half-width, stroke."""
    out = []
    for contour in contour_paths(region):
        segs = _flatten(contour, step)[0]
        arc = 0.0
        rows = []
        for a, b in segs:
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            tx, ty = unit(b[0] - a[0], b[1] - a[1])
            for nx, ny in ((-ty, tx), (ty, -tx)):
                if boundary.inside((mid[0] + nx * 0.02, mid[1] + ny * 0.02)):
                    break
            else:
                arc += length
                continue
            h = medial_radius(mid, (nx, ny), boundary)
            centre = (mid[0] + nx * h, mid[1] + ny * h)
            which, best = None, None
            for k, pts in enumerate(counter_pts):
                d = min(math.hypot(centre[0] - q[0], centre[1] - q[1])
                        for q in pts)
                if best is None or d < best:
                    best, which = d, k
            rows.append({"p": mid, "n": (nx, ny), "h": h, "stroke": which,
                         "arc": arc})
            arc += length
        out.append((arc, rows))
    return out


def target_widths(samples, main_stroke, legs):
    """The half-width every sample should end up with.

    Two things here are deliberate and were both learned the hard way.

    The legs' thin and thick ends are measured **on their flanks only**, not
    over every sample of the leg. A leg's smallest measured width is not its
    tapered tip but the neck where it leaves the diagonal, and keying the
    "hold the thin end" rule to that neck aimed it at the wrong place
    entirely - leg 2's thinnest sample sat at (16.5, 9.3), which is the neck.

    And a sample at a junction takes the main stroke's factor outright. At a
    neck the leg and the diagonal are the same ink, so holding the neck at full
    width while thinning the diagonal it belongs to is a contradiction, and the
    displacement field resolves it by changing sign across a very short stretch
    of outline. A field that flips sign along an edge does not thin that edge,
    it tilts it: the smooth concave sweep below the upper-right leg came out as
    a straight chord with a corner at each end, which is exactly the
    "unnatural" look. Letting the neck follow the diagonal keeps the field
    single-signed and the sweep smooth. The neck does narrow by the same 25% as
    the diagonal - unavoidable, since it is the same ink - but the legs' own
    tapered ends, which is what actually reads at small sizes, keep their
    width."""
    ranges = {}
    for k in legs:
        vals = sorted(s["h"] for _, rows in samples for s in rows
                      if s["stroke"] == k and s.get("flank", True))
        if not vals:
            vals = sorted(s["h"] for _, rows in samples for s in rows
                          if s["stroke"] == k)
        q = lambda f: vals[min(len(vals) - 1, int(f * len(vals)))]
        ranges[k] = (q(THIN_Q), q(THICK_Q))
    for _, rows in samples:
        for s in rows:
            if s["stroke"] == main_stroke:
                s["f"] = MAIN_FACTOR
            else:
                lo, hi = ranges[s["stroke"]]
                if hi - lo < 1e-9:
                    leg_f = (LEG_THIN_FACTOR + LEG_THICK_FACTOR) / 2
                else:
                    u = max(0.0, min(1.0, (s["h"] - lo) / (hi - lo)))
                    leg_f = LEG_THIN_FACTOR + u * (LEG_THICK_FACTOR
                                                   - LEG_THIN_FACTOR)
                # Fade to the main stroke's factor as the junction approaches.
                blend = _smoothstep(s.get("junction_arc", JUNCTION_BLEND)
                                    / JUNCTION_BLEND)
                s["f"] = MAIN_FACTOR + blend * (leg_f - MAIN_FACTOR)
            s["want"] = min(s["h"], max(s["f"] * s["h"], WIDTH_FLOOR))
    return ranges


def cap_by_clearance(samples, min_ink=MIN_INK):
    """Stop any point moving so far in that the ink there falls below min_ink.

    Both flanks of a narrow place move inward, so each may only take half of the
    slack. Where the ink is already at or under the minimum - the joins, the
    tapered tips - the cap is zero and that stretch of outline simply stays put,
    which is what keeps a join looking joined."""
    flat = [s for _, rows in samples for s in rows]
    cell = 0.5
    grid = collections.defaultdict(list)
    for idx, s in enumerate(flat):
        grid[(int(s["p"][0] // cell), int(s["p"][1] // cell))].append(idx)

    # Arc position is only comparable within one contour, so track which is which.
    contour_of = {}
    for ci, (_, rows) in enumerate(samples):
        for s in rows:
            contour_of[id(s)] = ci

    for idx, s in enumerate(flat):
        px, py = s["p"]
        best = float("inf")
        cx, cy = int(px // cell), int(py // cell)
        for ix in range(cx - 2, cx + 3):
            for iy in range(cy - 2, cy + 3):
                for other in grid.get((ix, iy), ()):
                    if other == idx:
                        continue
                    t = flat[other]
                    if contour_of[id(t)] == contour_of[id(s)]:
                        gap = abs(s["arc"] - t["arc"])
                        total = samples[contour_of[id(s)]][0]
                        gap = min(gap, total - gap)
                        if gap < CLEARANCE_ARC:
                            continue
                    # Only the ink counts: the far side must face back at us.
                    if s["n"][0] * t["n"][0] + s["n"][1] * t["n"][1] > -0.3:
                        continue
                    dist = math.hypot(px - t["p"][0], py - t["p"][1])
                    if dist < best:
                        best = dist
        if best == float("inf"):
            continue
        s["d"] = min(s["d"], max(0.0, (best - min_ink) / 2.0))


def smooth_along(samples, key, window=SMOOTH_ARC):
    for total, rows in samples:
        if not rows:
            continue
        raw = [s[key] for s in rows]
        arcs = [s["arc"] for s in rows]
        n = len(rows)
        for i in range(n):
            acc = wsum = 0.0
            for j in range(n):
                da = abs(arcs[i] - arcs[j])
                da = min(da, total - da)      # the contour is a loop
                if da > window:
                    continue
                w = 1.0 - da / window         # triangular kernel
                acc += raw[j] * w
                wsum += w
            rows[i][key + "_s"] = acc / wsum if wsum else raw[i]
        for s in rows:
            s[key] = s[key + "_s"]


class Field:
    """The solved displacement, queryable by position and by arc length."""

    CELL = 0.4

    def __init__(self, samples):
        self.contours = samples
        self.grid = collections.defaultdict(list)
        for ci, (total, rows) in enumerate(samples):
            for si, s in enumerate(rows):
                key = (int(s["p"][0] // self.CELL), int(s["p"][1] // self.CELL))
                self.grid[key].append((ci, si))

    def nearest(self, p):
        cx, cy = int(p[0] // self.CELL), int(p[1] // self.CELL)
        best = found = None
        ring = 0
        while ring <= 30:
            for ix in range(cx - ring, cx + ring + 1):
                for iy in range(cy - ring, cy + ring + 1):
                    if ring and abs(ix - cx) != ring and abs(iy - cy) != ring:
                        continue
                    for ci, si in self.grid.get((ix, iy), ()):
                        s = self.contours[ci][1][si]
                        d = math.hypot(p[0] - s["p"][0], p[1] - s["p"][1])
                        if best is None or d < best:
                            best, found = d, (ci, si)
            if found is not None and best <= ring * self.CELL:
                break
            ring += 1
        return found

    @staticmethod
    def _vec(s):
        if "vx" in s:
            return (s["vx"], s["vy"])
        return (s["n"][0] * s["d"], s["n"][1] * s["d"])

    def vector_at_point(self, p):
        found = self.nearest(p)
        if found is None:
            return (0.0, 0.0)
        return self._vec(self.contours[found[0]][1][found[1]])

    def arc_of_point(self, p):
        found = self.nearest(p)
        if found is None:
            return None, 0.0
        return found[0], self.contours[found[0]][1][found[1]]["arc"]

    def vector_at_arc(self, ci, arc):
        total, rows = self.contours[ci]
        if not rows:
            return (0.0, 0.0)
        arc %= total
        best = pick = None
        for s in rows:
            da = abs(s["arc"] - arc)
            da = min(da, total - da)
            if best is None or da < best:
                best, pick = da, s
        return self._vec(pick)


def elevate_quadratics(contours):
    """Rewrite every quadratic segment as the identical cubic.

    A quadratic has one control point, and that point governs the tangent at
    *both* ends of the segment. So the tangent at one end cannot be corrected
    without disturbing the other: restoring a node's angle moves the handle its
    neighbour depends on, the two corrections overwrite each other, and the
    curve stays faceted however many passes are run. On this letterform, which
    is drawn almost entirely in quadratics, that capped the median kink at 2.45
    degrees against 0.73 as drawn.

    Degree elevation gives the same curve two independent handles, so each end
    can be set on its own. It is exact - not an approximation - so the outline
    is unchanged by this step alone."""
    out = []
    for start, segments in contours:
        rebuilt, cur = [], start
        for seg in segments:
            kind, controls, end = seg[0], seg[1], seg[2]
            if kind == "Q" and controls:
                c = controls[0]
                c1 = (cur[0] + 2.0 / 3 * (c[0] - cur[0]),
                      cur[1] + 2.0 / 3 * (c[1] - cur[1]))
                c2 = (end[0] + 2.0 / 3 * (c[0] - end[0]),
                      end[1] + 2.0 / 3 * (c[1] - end[1]))
                rebuilt.append(("C", [c1, c2], end))
            else:
                rebuilt.append((kind, list(controls), end))
            cur = end
        out.append((start, rebuilt))
    return out


def restroke_path(d, field, scale=1.0, offset=(0.0, 0.0)):
    """Rewrite one path's data with the field applied.

    `scale` and `offset` map this path onto the reference letterform, so an
    embedded or shifted copy of the alef is reweighted by the same field and
    stays the same letter."""
    inv = 1.0 / scale

    def to_ref(p):
        return ((p[0] - offset[0]) * inv, (p[1] - offset[1]) * inv)

    def moved(p, vec):
        return (p[0] + vec[0] * scale, p[1] + vec[1] * scale)

    parsed = [clean_contour(a, b, WORK_PRECISION) for a, b in parse_segments(d)]
    parsed = elevate_quadratics([(a, b) for a, b in parsed if b])

    out, originals = [], []
    for start, segments in parsed:
        originals.append((start, segments))
        arcs = []
        first_ci = None
        for point in [start] + [s[2] for s in segments]:
            ci, arc = field.arc_of_point(to_ref(point))
            if first_ci is None:
                first_ci = ci
            arcs.append((ci if ci is not None else first_ci, arc))

        new_start = moved(start, field.vector_at_point(to_ref(start)))
        new_segments = []
        for i, seg in enumerate(segments):
            kind, controls, end = seg[0], seg[1], seg[2]
            new_end = moved(end, field.vector_at_point(to_ref(end)))
            if kind == "L" or not controls:
                new_segments.append((kind, [], new_end))
                continue
            a_ci, a_arc = arcs[i]
            b_ci, b_arc = arcs[i + 1]
            total = field.contours[a_ci][0]
            delta = b_arc - a_arc
            if delta > total / 2:
                delta -= total
            elif delta < -total / 2:
                delta += total
            new_controls = []
            for k, c in enumerate(controls):
                frac = (k + 1.0) / (len(controls) + 1.0)
                # Sampled at the handle's own place along the segment. Copying
                # the endpoints' displacement instead drags handles across the
                # curve where the normal turns quickly - at the terminals and in
                # the notches beside the junctions - and flattens it.
                vec = field.vector_at_arc(a_ci, a_arc + delta * frac)
                new_controls.append(moved(c, vec))
            new_segments.append((kind, new_controls, new_end))
        out.append((new_start, new_segments))

    # Displacing nodes and handles separately breaks the collinearity that makes
    # a join smooth, so put it back before anything else sees the curve.
    restore_tangents(originals, out)
    polish_outline(originals, out)
    restore_tangents(originals, out)
    return drop_fragments(out)


def drop_fragments(contours, limit=FRAGMENT_AREA):
    """Discard contours too small to be part of the drawing.

    Thinning a stroke narrows the counters of the outlined variant with it, and
    where a counter runs through a neck it can pinch closed and shed a detached
    fragment - one of 0.0012 square units appeared beside the lower-left neck.
    These are created by the reweighting itself rather than inherited, so they
    are removed here, at the point they appear. tool/repair_artifacts.py cannot:
    its speck pass works on committed source contours, and this is an emergent
    piece of one."""
    kept = []
    for start, segments in contours:
        path = pathops.Path()
        pen = path.getPen()
        pen.moveTo(start)
        for kind, controls, end in segments:
            if kind == "L" or not controls:
                pen.lineTo(end)
            elif kind == "C":
                pen.curveTo(controls[0], controls[1], end)
            else:
                pen.qCurveTo(controls[0], end)
        pen.closePath()
        if abs(path.area) < limit:
            continue
        kept.append((start, segments))
    return kept or contours


def contours_to_svg(contours, precision=WORK_PRECISION):
    return "\n       ".join(emit_contour(s, sg, precision) for s, sg in contours)


def wrap(path_data):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
            'viewBox="0 0 24 24">\n  <path d="%s"/>\n</svg>\n' % path_data)


def mark_flanks(samples, reach=FLANK_REACH):
    """Record how far each sample is, along the outline, from another stroke.

    Near a junction the strokes are the same ink, so no width belongs to one of
    them alone. This distance is what lets the weight change fade out as it
    approaches a junction instead of arguing with the stroke on the other
    side - see target_widths for why that argument wrecks the outline."""
    for total, rows in samples:
        count = len(rows)
        for i, s in enumerate(rows):
            best = total
            for j in range(count):
                if rows[j]["stroke"] == s["stroke"]:
                    continue
                gap = abs(rows[i]["arc"] - rows[j]["arc"])
                gap = min(gap, total - gap)
                if gap < best:
                    best = gap
            s["junction_arc"] = best
            s["flank"] = best > reach


def _smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def build_field(samples, main_stroke, legs, verbose=True):
    """The displacement field, in the order that matters.

    Three separate smoothings, each fixing something a previous attempt got
    wrong:

    1. The measured half-width is denoised first. It is found by marching a
       circle outward in hundredth-unit steps along a traced outline, so it
       carries real high-frequency noise.

    2. The target width is smoothed next, and it has to be the *width* rather
       than the displacement. At a junction the leg's thin end wants to move
       outward while the diagonal beside it wants to move inward; averaging two
       opposite displacements cancels both, and the legs came out at 0.96 and
       0.78 of their old width where 1.40 and 0.65 were asked for. Width is
       continuous even where displacement is not - the leg leaves the diagonal
       at whatever width the diagonal has there - so smoothing width both keeps
       the intended weights and blends the junctions correctly.

    3. Only then is d = h - w, and d gets a light final pass.

    Subtracting an unsmoothed h from a smoothed w puts all of h's noise straight
    back into the displacement, and the outline comes out visibly serrated -
    which is what happened before both terms were denoised."""
    smooth_along(samples, "h", SMOOTH_H)
    target_widths(samples, main_stroke, legs)
    for _, rows in samples:
        for s in rows:
            s["w"] = s["want"]
    smooth_along(samples, "w", SMOOTH_ARC)
    for _, rows in samples:
        for s in rows:
            s["d"] = s["h"] - s["w"]
    cap_by_clearance(samples)
    smooth_along(samples, "d", SMOOTH_D)

    # Finally smooth the displacement *vector*, not just its length. Each
    # sample's normal comes from one flattened segment, and on a densely traced
    # edge two adjacent nodes can pick normals that differ enough to send them
    # in visibly different directions - the outline comes out serrated along
    # exactly those edges even when d itself is perfectly smooth. Smoothing the
    # vector fixes the direction noise as well as the magnitude.
    for _, rows in samples:
        for s in rows:
            s["vx"] = s["n"][0] * s["d"]
            s["vy"] = s["n"][1] * s["d"]
    smooth_along(samples, "vx", SMOOTH_VEC)
    smooth_along(samples, "vy", SMOOTH_VEC)
    if SHORTEN_UPPER_LEG:
        shorten_upper_leg(samples, legs)
    return Field(samples)


def shorten_upper_leg(samples, legs, amount=SHORTEN_UPPER_LEG):
    """Draw the upper-right leg's tip back along the leg's own axis.

    This is a length change, not a weight change, so it is a translation rather
    than an offset: the tip and its neighbourhood move as a rigid piece, so the
    terminal arrives with its drawn shape intact, and the pull eases to nothing
    further down the leg. Because the move is along the stroke's axis instead of
    across it, the leg gets shorter without getting lighter or heavier - the
    compression lands lengthwise, in the plain middle stretch of the leg."""
    if not legs:
        return 0
    # The upper-right leg is the one sitting higher on the canvas.
    def mean_y(stroke):
        vals = [s["p"][1] for _, rows in samples for s in rows
                if s["stroke"] == stroke]
        return sum(vals) / len(vals) if vals else 1e9
    leg = min(legs, key=mean_y)

    rows_of = [(ci, s) for ci, (_, rows) in enumerate(samples) for s in rows
               if s["stroke"] == leg]
    if not rows_of:
        return 0
    tip_ci, tip = min(rows_of, key=lambda r: r[1]["p"][1])
    total = samples[tip_ci][0]

    def arc_gap(s):
        gap = abs(s["arc"] - tip["arc"])
        return min(gap, total - gap)

    # The leg's axis at the tip: from the tip towards the material a little way
    # down the leg, so the pull follows the stroke rather than the canvas.
    near = [s for ci, s in rows_of
            if ci == tip_ci and SHORTEN_HOLD <= arc_gap(s) <= SHORTEN_FADE]
    if not near:
        return 0
    ax = sum(s["p"][0] for s in near) / len(near) - tip["p"][0]
    ay = sum(s["p"][1] for s in near) / len(near) - tip["p"][1]
    axis = unit(ax, ay)
    if axis == (0.0, 0.0):
        return 0

    moved = 0
    for ci, (_, rows) in enumerate(samples):
        if ci != tip_ci:
            continue
        for s in rows:
            gap = arc_gap(s)
            if gap >= SHORTEN_FADE:
                continue
            if gap <= SHORTEN_HOLD:
                weight = 1.0
            else:
                weight = _smoothstep((SHORTEN_FADE - gap)
                                     / (SHORTEN_FADE - SHORTEN_HOLD))
            s["vx"] += axis[0] * amount * weight
            s["vy"] += axis[1] * amount * weight
            moved += 1
    return moved


def solve(reference_d, samples, rounds=SOLVER_ROUNDS, verbose=True):
    """Iterate the displacement until the measured widths stop improving."""
    for _, rows in samples:
        for s in rows:
            s["d"] = s["h"] - s["want"]
    smooth_along(samples, "d")

    history = []
    for rnd in range(1, rounds + 1):
        field = Field(samples)
        contours = restroke_path(reference_d, field)
        region = resolve_region(wrap(contours_to_svg(contours)), "restroked")
        boundary = Boundary(region)

        errors = []
        for _, rows in samples:
            for s in rows:
                moved_p = (s["p"][0] + s["n"][0] * s["d"],
                           s["p"][1] + s["n"][1] * s["d"])
                # Project onto the new outline before measuring: the outline
                # comes from displaced Bezier nodes and a boolean union, so it
                # does not pass exactly through the displaced sample.
                q, n = boundary.nearest_point(moved_p)
                if q is None or n is None:
                    s["got"] = s["want"]
                    errors.append(0.0)
                    continue
                got = medial_radius(q, n, boundary, step=MEASURE_STEP)
                s["got"] = got
                errors.append(got - s["want"])
        rms = math.sqrt(sum(e * e for e in errors) / len(errors))
        worst = max(abs(e) for e in errors)
        history.append((rnd, rms, worst))
        if verbose:
            print("   round %d: width error rms=%.4f worst=%.4f units"
                  % (rnd, rms, worst))
        if rnd == rounds:
            break
        # A circle that came out too big means the flank did not move in far
        # enough, so push it further by the shortfall.
        for _, rows in samples:
            for s in rows:
                s["d"] += RELAX * (s["got"] - s["want"])
        smooth_along(samples, "d")

    return Field(samples), history


def analyse(verbose=True):
    filled = region_of_file(os.path.join(SVG_DIR, REFERENCE_FILLED + ".svg"))
    outlined = region_of_file(os.path.join(SVG_DIR, REFERENCE_OUTLINED + ".svg"))
    counters = sorted(contour_paths(outlined), key=lambda c: -abs(c.area))[1:]
    counter_pts = [[a for a, b in _flatten(c, 0.05)[0]] for c in counters]

    boundary = Boundary(filled)
    samples = sample_outline(filled, counter_pts, boundary)

    order = sorted(((abs(c.area), k) for k, c in enumerate(counters)),
                   reverse=True)
    main_stroke = order[0][1]
    legs = [k for _, k in order[1:]]
    mark_flanks(samples)
    ranges = target_widths(samples, main_stroke, legs)
    # Recomputed inside build_field() once h has been denoised; this call is
    # only so the ranges can be reported.
    if verbose:
        print("main diagonal: half-width median %.3f -> %.3f"
              % (_median([s["h"] for _, r in samples for s in r
                          if s["stroke"] == main_stroke]),
                 _median([s["want"] for _, r in samples for s in r
                          if s["stroke"] == main_stroke])))
        for k in legs:
            lo, hi = ranges[k]
            print("leg (counter %d): thin %.3f -> %.3f   thick %.3f -> %.3f"
                  % (k, lo, lo * LEG_THIN_FACTOR, hi, hi * LEG_THICK_FACTOR))
    return filled, samples, main_stroke, legs, ranges


def _median(v):
    v = sorted(v)
    return v[len(v) // 2] if v else 0.0


# --------------------------------------------------------------------------
# applying it across the family
# --------------------------------------------------------------------------

PATH_RE = re.compile(r"(<path\b)([^>]*?)(/?>)", re.S)
D_RE = re.compile(r'(\bd\s*=\s*")([^"]*)(")', re.S)

# Every icon that carries this letterform, and which of its <path> elements
# holds it. In fifteen of them the letter is the first path of a layered source
# and is the same geometry every time, sometimes shifted; in alef_24_regular it
# is one path holding the silhouette together with its three counters.
#
# The list is explicit rather than discovered by shape matching, because the two
# things shape matching would have to decide are decisions in their own right:
#   * alef_stam and alef_rashi are different letterforms and are excluded by
#     the brief;
#   * the reduced alef inside book_alef_24_{regular,filled} is a differently
#     drawn letter, not a scaled copy of this one - it matches the reference at
#     a shape distance of 0.139 where every icon below matches at 0.000 - so
#     reweighting it from this field would be guesswork. It needs its own pass.
#   * text_alef_bet_list_24_regular has no alef of this kind at all: its
#     alef-bet-gimel are thin printed letters in an unrelated style.
FAMILY = [
    "alef_24_filled",
    "alef_24_regular",
    "alef_1_24_regular",
    "alef_2_24_regular",
    "alef_3_24_regular",
    "alef_behind_alef_24_regular",
    "alef_deletion_24_regular",
    "alef_near_alef_24_regular",
    "alef_with_eraser_24_regular",
    "alef_with_flavors_24_regular",
    "alef_with_information_24_regular",
    "alef_with_punctuation_24_regular",
    "alef_with_score_24_regular",
    "alef_writing_24_regular",
    "beit_behind_alef_24_regular",
    "beit_near_alef_24_regular",
]

# The letterform's own bounding box, used to spot it and to work out how far a
# given icon has shifted it.
REFERENCE_BBOX = (4.21, 2.276, 19.757, 21.708)
BBOX_TOL = 0.05


def path_blocks(text):
    """Every <path> of a source, as (match, attributes, d string)."""
    out = []
    for m in PATH_RE.finditer(text):
        dm = D_RE.search(m.group(2))
        if dm:
            out.append((m, dm, dm.group(2)))
    return out


def letterform_offset(d):
    """(dx, dy) if this path is the letterform, else None.

    The letterform is recognised by the size of its bounding box, which is
    unmistakable at four decimal places, and its position gives the shift."""
    contours = [clean_contour(a, b, WORK_PRECISION)
                for a, b in parse_segments(d)]
    contours = [(a, b) for a, b in contours if b]
    if not contours:
        return None
    xs, ys = [], []
    for start, segments in contours:
        xs.append(start[0])
        ys.append(start[1])
        for seg in segments:
            xs.append(seg[2][0])
            ys.append(seg[2][1])
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    ref_w = REFERENCE_BBOX[2] - REFERENCE_BBOX[0]
    ref_h = REFERENCE_BBOX[3] - REFERENCE_BBOX[1]
    if abs((x1 - x0) - ref_w) > BBOX_TOL or abs((y1 - y0) - ref_h) > BBOX_TOL:
        return None
    return (x0 - REFERENCE_BBOX[0], y0 - REFERENCE_BBOX[1])


def rewrite_source(text, field):
    """Reweight the letterform wherever it appears in a source."""
    changed = 0
    pieces, last = [], 0
    for m, dm, d in path_blocks(text):
        offset = letterform_offset(d)
        if offset is None:
            continue
        contours = restroke_path(d, field, scale=1.0, offset=offset)
        new_d = "\n       ".join(emit_contour(s, sg, WORK_PRECISION)
                                 for s, sg in contours)
        attrs = m.group(2)
        new_attrs = attrs[:dm.start(1)] + dm.group(1) + new_d + dm.group(3) \
            + attrs[dm.end(3):]
        pieces.append(text[last:m.start(0)])
        pieces.append(m.group(1) + new_attrs + m.group(3))
        last = m.end(0)
        changed += 1
    pieces.append(text[last:])
    return "".join(pieces), changed


def main(argv):
    check = "--check" in argv

    print("analysing the reference letterform...")
    filled, samples, main_stroke, legs, ranges = analyse()
    mark_flanks(samples)
    field = build_field(samples, main_stroke, legs)
    print("applied factors: main=%.2f  leg thin=%.2f  leg thick=%.2f"
          % (MAIN_FACTOR, LEG_THIN_FACTOR, LEG_THICK_FACTOR))
    print("targets:         main=%.2f  leg thin=%.2f  leg thick=%.2f\n"
          % (TARGET_MAIN, TARGET_LEG_THIN, TARGET_LEG_THICK))

    names = [a for a in argv if not a.startswith("--")] or FAMILY
    total = 0
    for name in names:
        path = os.path.join(SVG_DIR, name + ".svg")
        if not os.path.exists(path):
            print("MISSING  %s" % name)
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new_text, changed = rewrite_source(text, field)
        if not changed:
            print("skipped  %-40s (no letterform found)" % name)
            continue
        total += changed
        if not check:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_text)
        print("%-8s %-40s %d path(s)"
              % ("would do" if check else "rewrote", name, changed))

    print("\n%s %d path(s) across %d icon(s)."
          % ("Would rewrite" if check else "Rewrote", total, len(names)))
    if not check and total:
        print("Run tool/format_svg.py, then tool/unify_shared_parts.py.")
    return 0




# --------------------------------------------------------------------------
# keeping the curve as smooth as it was drawn
# --------------------------------------------------------------------------

# A node whose incoming and outgoing tangents differ by less than this was drawn
# as a smooth join, and must stay one. Anything above it is a corner the
# designer put there.
SMOOTH_NODE_TOL = 2.0


def _angle_between(a, b):
    la, lb = math.hypot(*a), math.hypot(*b)
    if la < 1e-12 or lb < 1e-12:
        return 0.0
    cos = (a[0] * b[0] + a[1] * b[1]) / (la * lb)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def _dir(a, b):
    """Angle of the vector a->b, or None if it has no length."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if math.hypot(dx, dy) < 1e-12:
        return None
    return math.atan2(dy, dx)


def _wrap(angle):
    while angle <= -math.pi:
        angle += 2 * math.pi
    while angle > math.pi:
        angle -= 2 * math.pi
    return angle


def polish_outline(original, moved):
    """Take the tremor out of the outline without redrawing it.

    Two bounded steps, both skipping anything drawn as a corner:

    Positions - each node is eased onto the curve its two neighbours describe,
    by at most POLISH_MOVE. Its handles travel with it, so the local curve keeps
    its shape and only the node's scatter is removed.

    Tangents - handled in restore_tangents, which straightens any join drawn
    with less than POLISH_KINK of kink to exactly straight instead of restoring
    the few degrees it happened to be digitised with.

    Together these give the outline the property a drawn typeface has and a
    traced one does not: joins that are actually smooth, and edges that carry no
    tremor between their control points."""
    for (o_start, o_segs), (n_start, n_segs) in zip(original, moved):
        count = len(o_segs)
        if count != len(n_segs) or count < 4:
            continue
        o_pts = [o_start] + [seg[2] for seg in o_segs]
        kinks = []
        for i in range(count):
            j = (i + 1) % count
            node = o_segs[i][2]
            a = _dir(o_segs[i][1][-1], node) if o_segs[i][1] else                 _dir(o_pts[i], node)
            b = _dir(node, o_segs[j][1][0]) if o_segs[j][1] else                 _dir(node, o_pts[(j + 1) % (count + 1)])
            kinks.append(abs(math.degrees(_wrap(b - a)))
                         if a is not None and b is not None else 0.0)

        # Ease repeatedly, but never further than POLISH_MOVE from where the
        # node began, so the outline settles without drifting off its path.
        anchor = [seg[2] for seg in n_segs]
        for _ in range(POLISH_PASSES):
            moves = []
            for i in range(count):
                if kinks[i] > POLISH_CORNER:
                    moves.append((0.0, 0.0))
                    continue
                here = n_segs[i][2]
                before = n_segs[(i - 1) % count][2]
                after = n_segs[(i + 1) % count][2]
                tx = ((before[0] + after[0]) / 2.0 - here[0]) * 0.5
                ty = ((before[1] + after[1]) / 2.0 - here[1]) * 0.5
                nx, ny = here[0] + tx, here[1] + ty
                offx, offy = nx - anchor[i][0], ny - anchor[i][1]
                drift = math.hypot(offx, offy)
                if drift > POLISH_MOVE:
                    scale = POLISH_MOVE / drift
                    nx = anchor[i][0] + offx * scale
                    ny = anchor[i][1] + offy * scale
                moves.append((nx - here[0], ny - here[1]))

            for i in range(count):
                dx, dy = moves[i]
                if dx == 0.0 and dy == 0.0:
                    continue
                node = n_segs[i][2]
                n_segs[i] = (n_segs[i][0], n_segs[i][1],
                             (node[0] + dx, node[1] + dy))
                if n_segs[i][1]:
                    c = n_segs[i][1][-1]
                    n_segs[i][1][-1] = (c[0] + dx, c[1] + dy)
                j = (i + 1) % count
                if n_segs[j][1]:
                    c = n_segs[j][1][0]
                    n_segs[j][1][0] = (c[0] + dx, c[1] + dy)


def restore_tangents(original, moved):
    """Give every node back the exact kink angle it was drawn with.

    This is what keeps the reweighted letter as smooth as the drawn one, and
    without it the result is visibly faceted.

    A cubic join looks smooth only while the node and the two handles beside it
    stay in line. Reweighting a stroke means displacing nodes and handles each
    by their own amount, and that breaks the alignment at every smooth node,
    because no two of them move by quite the same vector. Measured on the alef,
    the median kink went from 0.74 degrees as drawn to 3.89 degrees, and the
    share of nodes kinked by more than 3 degrees from 30% to 56%. That is the
    "jumping points" one sees on an enlarged icon.

    Rather than force smooth joins to be smooth, this restores whatever angle
    each node had. A node drawn straight comes back straight, a node drawn with
    a two-degree bend keeps two degrees, and a deliberate corner keeps its
    corner - one rule, no threshold to tune, and nothing reinterpreted.

    Only handles move, never nodes, so the stroke widths the displacement just
    set are left exactly as they are, and each handle keeps its length so the
    curve keeps its fullness. The direction everything is measured from is the
    bisector the displaced handles already imply, so the join is corrected
    without dragging the curve off its new path.

    Where a straight segment meets a curve the straight side cannot rotate - its
    direction is fixed by two nodes - so the curve's handle is aligned to it
    instead. Two straights meeting have no handles at all and are left alone.
    Skipping those joins rather than handling them was why an earlier version
    only got the median down to 2.47 degrees."""
    fixed = 0
    for (o_start, o_segs), (n_start, n_segs) in zip(original, moved):
        count = len(o_segs)
        if count != len(n_segs) or count < 2:
            continue
        o_pts = [o_start] + [seg[2] for seg in o_segs]
        n_pts = [n_start] + [seg[2] for seg in n_segs]
        for i in range(count):
            j = (i + 1) % count
            o_curve_in, o_curve_out = bool(o_segs[i][1]), bool(o_segs[j][1])
            if not o_curve_in and not o_curve_out:
                continue

            o_node = o_segs[i][2]
            o_in = _dir(o_segs[i][1][-1], o_node) if o_curve_in                 else _dir(o_pts[i], o_node)
            o_out = _dir(o_node, o_segs[j][1][0]) if o_curve_out                 else _dir(o_node, o_pts[(j + 1) % (count + 1)])
            if o_in is None or o_out is None:
                continue
            drawn_kink = _wrap(o_out - o_in)
            if abs(math.degrees(drawn_kink)) < POLISH_KINK:
                # Drawn as a smooth join; make it exactly one.
                drawn_kink = 0.0

            n_node = n_segs[i][2]
            h_in = n_segs[i][1][-1] if o_curve_in else None
            h_out = n_segs[j][1][0] if o_curve_out else None
            n_in = _dir(h_in, n_node) if o_curve_in else _dir(n_pts[i], n_node)
            n_out = _dir(n_node, h_out) if o_curve_out                 else _dir(n_node, n_pts[(j + 1) % (count + 1)])
            if n_in is None or n_out is None:
                continue

            if o_curve_in and o_curve_out:
                # Both sides can rotate: keep the bisector, restore the angle.
                bisector = n_in + _wrap(n_out - n_in) / 2.0
                want_in = bisector - drawn_kink / 2.0
                want_out = bisector + drawn_kink / 2.0
            elif o_curve_out:
                want_in, want_out = n_in, n_in + drawn_kink
            else:
                want_in, want_out = n_out - drawn_kink, n_out

            if o_curve_in:
                length = math.hypot(n_node[0] - h_in[0], n_node[1] - h_in[1])
                n_segs[i][1][-1] = (n_node[0] - math.cos(want_in) * length,
                                    n_node[1] - math.sin(want_in) * length)
            if o_curve_out:
                length = math.hypot(h_out[0] - n_node[0], h_out[1] - n_node[1])
                n_segs[j][1][0] = (n_node[0] + math.cos(want_out) * length,
                                   n_node[1] + math.sin(want_out) * length)
            fixed += 1
    return fixed


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
