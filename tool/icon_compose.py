#!/usr/bin/env python3
"""Geometry toolkit for composing a new icon out of existing artwork.

WHY THIS EXISTS
---------------
Most new icons in this set are not drawn from nothing. They are an existing
letterform, page or chain with a badge added, a letter swapped, or a stroke
weight changed - and the value of the family is that the shared parts stay
*identical*, not merely similar. Hand-copying a path into a new file is how a
family drifts: the alef badge disc already exists in two subtly different
spellings because of exactly that.

So a composed icon is written as a recipe against the committed sources. The
disc in a new badge icon is not a copy of the disc, it *is* the disc, read out
of `alef_copy_24_regular.svg` at build time. Redraw the alef again and every
composed icon that carries one picks the new letter up on the next run.

WHAT IT GIVES YOU
-----------------
`Art` wraps a `pathops.Path` with the operations these recipes actually need -
union / difference, affine placement, fit-into-a-box, and a real outline offset
(`grow`/`shrink`) built on skia's stroker, which is what lets a filled variant be
derived from a regular one instead of redrawn beside it.

Everything works on the *resolved region* - the union of an icon's solid paths
minus its `fill="white"` knockouts - because that is what the font is built
from; see `tool/repair_glyphs.py`. Reading raw `<path>` elements instead would
treat a knockout as ink.

Output is written as plain absolute path data. Run `tool/format_svg.py` over the
result to get the canonical written form; it verifies the region is unchanged.

Requires: skia-pathops, fonttools.
"""
import math
import os
import xml.etree.ElementTree as ET

import pathops

from glyph_geometry import simplified, is_knockout_index

# The widest single outward offset `grow` will ask skia's stroker for; see the
# note there.
GROW_STEP = 0.55

SVG_NS = "http://www.w3.org/2000/svg"
SVG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets_src", "svg")


def _polyfit(xs, ys, degree):
    """Least squares coefficients of y = c0 + c1 x + ... + cn x^n.

    Solved through the normal equations by Gaussian elimination with partial
    pivoting - a dependency-free numpy.polyfit for the one place that needs it.
    The caller centres its samples, which is what keeps a Vandermonde system
    this small well conditioned.
    """
    n = degree + 1
    a = [[sum(x ** (i + j) for x in xs) for j in range(n)] for i in range(n)]
    b = [sum(y * x ** i for x, y in zip(xs, ys)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(a[r][i]))
        a[i], a[p] = a[p], a[i]
        b[i], b[p] = b[p], b[i]
        if not a[i][i]:
            raise ArithmeticError("polyfit: singular system at row %d" % i)
        for r in range(i + 1, n):
            f = a[r][i] / a[i][i]
            for c in range(i, n):
                a[r][c] -= f * a[i][c]
            b[r] -= f * b[i]
    out = [0.0] * n
    for i in range(n - 1, -1, -1):
        out[i] = (b[i] - sum(a[i][j] * out[j]
                             for j in range(i + 1, n))) / a[i][i]
    return out


# --------------------------------------------------------------------------
# Art: a filled region you can transform and combine
# --------------------------------------------------------------------------
class Art:
    """A filled region on the 24x24 canvas, with the operations recipes need."""

    __slots__ = ("p",)

    def __init__(self, p=None):
        self.p = p if p is not None else pathops.Path()

    # -- construction ------------------------------------------------------
    @staticmethod
    def from_d(d, fill_rule=None):
        return Art(simplified(d, fill_rule))

    @staticmethod
    def empty():
        return Art()

    def copy(self):
        q = pathops.Path()
        q.addPath(self.p)
        return Art(q)

    # -- combination -------------------------------------------------------
    def __or__(self, other):
        out = pathops.Path()
        pathops.union([self.p, other.p], out.getPen())
        return Art(out)

    def __sub__(self, other):
        out = pathops.Path()
        pathops.difference([self.p], [other.p], out.getPen())
        return Art(out)

    def __and__(self, other):
        out = pathops.Path()
        pathops.intersection([self.p], [other.p], out.getPen())
        return Art(out)

    # -- measurement -------------------------------------------------------
    @property
    def bounds(self):
        return self.p.bounds

    @property
    def area(self):
        return abs(self.p.area)

    @property
    def is_empty(self):
        return not list(self.p.segments)

    @property
    def centre(self):
        x0, y0, x1, y1 = self.bounds
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    @property
    def size(self):
        x0, y0, x1, y1 = self.bounds
        return (x1 - x0, y1 - y0)

    def mean_stroke(self):
        """2*area/perimeter - the usable weight number for matching a letter to
        the family (alef 2.61, tet 2.69, alef_stam 2.72). See the project notes
        in docs/source_structure.md."""
        per = _perimeter(self.p)
        return 2 * self.area / per if per else 0.0

    # -- placement ---------------------------------------------------------
    def transform(self, a, b, c, d, e, f):
        # Path.transform returns a new path rather than mutating in place.
        return Art(pathops.simplify(self.p.transform(a, b, c, d, e, f)))

    def translate(self, dx, dy):
        return self.transform(1, 0, 0, 1, dx, dy)

    def scale(self, sx, sy=None, about=None):
        sy = sx if sy is None else sy
        cx, cy = about if about else (0.0, 0.0)
        return self.transform(sx, 0, 0, sy,
                              cx - sx * cx, cy - sy * cy)

    def rotate(self, degrees, about=None):
        t = math.radians(degrees)
        co, si = math.cos(t), math.sin(t)
        cx, cy = about if about else self.centre
        return self.transform(co, si, -si, co,
                              cx - co * cx + si * cy,
                              cy - si * cx - co * cy)

    def centred_on(self, x, y):
        cx, cy = self.centre
        return self.translate(x - cx, y - cy)

    def fit(self, box, keep_aspect=True, align="centre"):
        """Scale into (x0, y0, x1, y1). With keep_aspect the art is centred in
        the box on the axis with slack, so a letter never gets stretched in one
        direction only."""
        bx0, by0, bx1, by1 = box
        x0, y0, x1, y1 = self.bounds
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0:
            return self
        sx, sy = (bx1 - bx0) / w, (by1 - by0) / h
        if keep_aspect:
            sx = sy = min(sx, sy)
        out = self.transform(sx, 0, 0, sy, -x0 * sx, -y0 * sy)
        ox0, oy0, ox1, oy1 = out.bounds
        dx = bx0 - ox0 + ((bx1 - bx0) - (ox1 - ox0)) / 2
        dy = by0 - oy0 + ((by1 - by0) - (oy1 - oy0)) / 2
        if align == "top":
            dy = by0 - oy0
        elif align == "bottom":
            dy = by1 - oy1
        return out.translate(dx, dy)

    def radius(self):
        """The farthest the ink reaches from the region's bounding-box centre.

        Measured on the flattened outline, not on the control points: a control
        point sits outside the curve it steers, so using one would report a
        radius the ink never reaches and quietly undersize everything fitted to
        it.
        """
        cx, cy = self.centre
        return max((math.hypot(pt[0] - cx, pt[1] - cy)
                    for pt in _flatten(self.p) if pt is not None),
                   default=0.0)

    def fit_radius(self, r, about=None):
        """Scale so the ink reaches exactly `r` from its centre.

        The right rule for a mark going inside a round badge: fitting to a
        square box leaves a wide flat mark - an eye, a pair of lips - looking
        undersized, because the corners the box reserves are outside the circle
        anyway.
        """
        have = self.radius()
        if have <= 0:
            return self
        cx, cy = about if about else self.centre
        return self.scale(r / have, about=(cx, cy))

    # -- weight ------------------------------------------------------------
    def grow(self, delta):
        """Offset the outline outward by `delta`, everywhere, by unioning the
        region with a band stroked along its own boundary. Round joins, so a
        corner grows into a fillet instead of a spike.

        Wide offsets are taken in steps, because skia's stroker comes apart on
        a hand-drawn outline once the width gets near the size of the features
        it is tracing: growing `book_open_large_lines`'s cover by 1.1 in one go
        returned eleven fragments with a whole flank missing, and the same
        offset in two halves returns the one contour it should, to within four
        hundredths of a square unit. The step is the widest that has been seen
        to hold on this artwork.
        """
        if delta <= 0:
            return self.shrink(-delta) if delta < 0 else self
        steps = int(math.ceil(delta / GROW_STEP))
        out, part = self, delta / steps
        for _ in range(steps):
            out = out | _band(out.p, part * 2)
        return out

    def shrink(self, delta):
        """The inverse: erode the outline inward by `delta`.

        An erosion this small cannot legitimately consume the whole region, so
        if it does, skia's stroker has handed back a band that covers the shape
        instead of hugging its boundary - which it will, on geometry that has
        already been offset once. That used to pass silently and write a blank
        glyph; now it stops here, where the cause is still visible.
        """
        if delta <= 0:
            return self.grow(-delta) if delta < 0 else self
        out = self - _band(self.p, delta * 2)
        if out.is_empty and not self.is_empty:
            x0, y0, x1, y1 = self.bounds
            if delta < min(x1 - x0, y1 - y0) / 4:
                raise ArithmeticError(
                    "eroding %.2f x %.2f units of ink by %g consumed all of it; "
                    "the offset is unreliable on this outline"
                    % (x1 - x0, y1 - y0, delta))
        return out

    def round_corners(self, outer, inner=None):
        """Ease the region's corners: `outer` on the convex ones, `inner` on the
        concave ones.

        Two morphological steps, and the order and the two radii both matter.
        An *opening* - shrink then grow - rounds every convex corner to `outer`
        and can never spread the region, so it is safe at any radius the strokes
        can afford. A *closing* - grow then shrink - rounds the concave ones,
        but it also bridges anything narrower than twice its radius, so `inner`
        has to stay under half the smallest gap in the artwork or the M and the
        D of a letter pair weld together.
        """
        inner = outer * 0.55 if inner is None else inner
        art = self.shrink(outer).grow(outer)
        if inner > 0:
            art = art.grow(inner).shrink(inner)
        return art

    def pad_left_edge(self, y0, y1, xlo, xhi, amount, ease=1.6, ease_end=0.0,
                      degree=5, step=0.04):
        """Move the left edge of one stroke outward, along a fitted curve.

        For thickening a single stroke of a letter without touching the rest.
        `grow` cannot do it - it moves every edge, and restricted to a box it
        leaves a step where the box ends. Here the stroke's own left edge is
        traced between y0 and y1 (the rightmost run of ink inside `xlo`..`xhi`),
        pushed out by `amount`, eased in over `ease` units at the top and
        `ease_end` at the bottom, and then *replaced by a polynomial least
        squares fit of that target*.

        The fit is the point. A traced edge is a staircase - it is sampled on a
        fixed grid - and a staircase unioned into an outline is a tremor; a
        moving average over it is still a polyline that inherits every wobble
        of a hand-drawn outline, which is what the first version of this shipped.
        A degree-5 polynomial has no wobble to inherit: it is smooth everywhere
        by construction, it cannot reproduce a defect in its input, and over the
        length of one stroke it still follows the drawing to a few hundredths.

        `ease_end` defaults to 0 because the usual bottom end is not a free
        edge at all but a junction with another stroke, and easing the padding
        off into a junction is what produced a hook there: the fitted edge
        turned back out while the letter's own flare turned in.

        The polygon's other side follows the traced edge inward by a quarter
        unit, but never past the stroke's own right edge - so it can neither
        leave a gap the union would show as a notch nor spill out of the letter
        where the stroke is thinner than the inset.
        """
        def smootherstep(t):
            t = min(1.0, max(0.0, t))
            return t * t * t * (t * (t * 6 - 15) + 10)

        # Trace the stroke. Where the probe crosses more than one run of ink -
        # near the top, where this stroke passes the letter's own bar - the
        # stroke wanted is the rightmost, so that is the run measured.
        ys, lo, hi = [], [], []
        y = y0
        while y <= y1 + 1e-9:
            runs = sorted((c.bounds[0], c.bounds[2])
                          for c in contours(self & rect(xlo, y, xhi, y + step)))
            if runs:
                ys.append(y + step / 2)
                lo.append(runs[-1][0])
                hi.append(runs[-1][1])
            y += step
        if len(ys) < degree + 2:
            return self

        target = [lo[i] - amount * min(smootherstep((ys[i] - y0) / ease),
                                       smootherstep((y1 - ys[i]) / ease_end)
                                       if ease_end else 1.0)
                  for i in range(len(ys))]
        # Fit about the middle of the span rather than about y=0, so the powers
        # stay near 1 and the normal equations stay well conditioned.
        mid = (ys[0] + ys[-1]) / 2
        coeffs = _polyfit([y - mid for y in ys], target, degree)

        def fitted(y):
            t, out = 1.0, 0.0
            for c in coeffs:
                out += c * t
                t *= (y - mid)
            return out

        pts = [(fitted(y), y) for y in ys]
        pts += [(min(lo[i] + 0.25, hi[i] - 0.02), ys[i])
                for i in range(len(ys) - 1, -1, -1)]
        return (self | polygon(pts)).despeckle(0.02).fill_holes(0.02)

    def fillet(self, distance, min_turn=25.0, max_share=0.4):
        """Ease the sharp corners of the outline, by cutting each one.

        The right tool for this, and the second one tried. A morphological
        rounding - `round_corners` - cannot tell a corner from a thin stroke,
        because both disappear under the same erosion: at 0.25 units it already
        takes 99 square units off `book_open_large`, and at 0.35 skia refuses
        the operation outright. This works on the path instead. Where two
        straight segments meet at more than `min_turn` degrees, `distance` is
        trimmed off each of them and the gap is bridged by a quadratic through
        the old corner. Nothing but the corner moves, so no stroke can be
        thinned and none can be erased, however fine it is.

        A corner is only eased as far as its own edges allow: the trim is capped
        at `max_share` of the shorter of the two, so a short segment between two
        corners keeps its middle. Curved joins are left alone - they are already
        round - which also means a second run finds almost nothing to do.
        """
        out = pathops.Path()
        turn = math.cos(math.radians(180.0 - min_turn))
        # Walked straight off this path rather than through `contours`, because
        # that normalises each contour's winding and a hole rebuilt clockwise
        # fills itself in. Here every contour keeps the direction it was drawn.
        runs, cur = [], None
        for verb, pts in segments(self.p):
            if verb == "moveTo":
                cur = [pts[0], [], False]
                runs.append(cur)
            elif cur is None:
                continue
            elif verb == "closePath":
                cur[2] = True
            else:
                cur[1].append([verb, list(pts)])
        for start, segs, closed in runs:
            if start is None or not segs:
                continue
            if closed and segs[-1][1][-1] != start:
                segs.append(["lineTo", [start]])
            ends = [s[1][-1] for s in segs]
            befores = [start] + ends[:-1]
            n = len(segs)

            def trim_at(i):
                """How far back from vertex i each of its two edges is cut."""
                nxt = (i + 1) % n
                if not closed and i == n - 1:
                    return 0.0
                if segs[i][0] != "lineTo" or segs[nxt][0] != "lineTo":
                    return 0.0
                v, a, b = ends[i], befores[i], ends[nxt]
                ua, ub = (a[0] - v[0], a[1] - v[1]), (b[0] - v[0], b[1] - v[1])
                la = math.hypot(*ua)
                lb = math.hypot(*ub)
                if la < 1e-9 or lb < 1e-9:
                    return 0.0
                cos = (ua[0] * ub[0] + ua[1] * ub[1]) / (la * lb)
                if cos < turn:              # too nearly straight to be a corner
                    return 0.0
                return min(distance, max_share * la, max_share * lb)

            cut = [trim_at(i) for i in range(n)]

            def along(frm, to, d):
                dx, dy = to[0] - frm[0], to[1] - frm[1]
                l = math.hypot(dx, dy)
                return (frm[0] + dx / l * d, frm[1] + dy / l * d)

            # Each line is drawn from where the previous corner released it to
            # where its own corner takes it back; every eased corner then adds
            # one quadratic through the point the two lines used to meet at.
            first = (along(start, ends[0], cut[-1]) if closed and cut[-1]
                     else start)
            out.moveTo(*first)
            for i, (verb, pts) in enumerate(segs):
                v = ends[i]
                if verb == "lineTo":
                    out.lineTo(*(along(v, befores[i], cut[i]) if cut[i] else v))
                elif verb == "curveTo":
                    out.cubicTo(*[k for p in pts for k in p])
                elif verb == "qCurveTo":
                    for ctrl, end in _quads(pts):
                        out.quadTo(*ctrl, *end)
                if cut[i]:
                    out.quadTo(*v, *along(v, ends[(i + 1) % n], cut[i]))
            if closed:
                out.close()
        return Art(pathops.simplify(out))

    def outlined(self, width):
        """The region's own boundary drawn as a line `width` across, centred on
        it - a solid drawing turned into an outline one.

        Deliberately not `self - self.shrink(width)`, which is the same picture
        in principle. An inward offset of a hand-drawn silhouette is the one
        thing skia's stroker gets wrong here, and on the middle book of
        `books_stacked_low` it gets it wrong loudly: eroding 21 x 9 units of ink
        by 1.1 comes back empty. Stroking the boundary asks the same stroker for
        the thing it is reliable at, and every contour keeps its own shape.
        """
        out = Art()
        for c in contours(self):
            out = out | _band(c.p, width)
        return out

    def deburr(self, delta=0.03):
        """Remove the micro-defects a hand-drawn outline carries, so that
        offsetting it does not amplify them.

        Only the opening half of a rounding, and deliberately: doubled points
        and edges that almost touch show up as spikes, which an opening removes,
        and the closing that would round the notches is the half that fails on
        an outline which has already been through one boolean pass. Offsetting
        the otzaria cover raw produced a hundred and fourteen fragments; after
        this, one.
        """
        return self.shrink(delta).grow(delta)

    def prune(self, eps=1e-6):
        """Drop contours that enclose nothing, keeping every other one exactly.

        An offset can leave a contour that traces out and straight back: it
        encloses no area, so it paints nothing and `despeckle` cannot remove it
        - subtracting an empty region is a no-op. It is still geometry, though,
        and `normalize_svg_overlaps.py` counts it as a contour welded to its
        neighbour and refuses the source. This rewrites the path without them,
        which cannot change what the icon draws.

        Done on the raw path rather than through `contours()`, so that a real
        hole keeps its own winding instead of being re-unioned as ink.
        """
        out, cur, area, start, prev = pathops.Path(), [], 0.0, None, None
        kept = []
        for verb, pts in segments(self.p):
            if verb == "moveTo":
                cur, start, prev = [(verb, pts)], pts[0], pts[0]
                area = 0.0
                continue
            if cur is None:
                continue
            cur.append((verb, pts))
            if verb == "closePath":
                area += (prev[0] * start[1] - start[0] * prev[1]) / 2
                if abs(area) > eps:
                    kept.append(cur)
                cur = None
            else:
                for q in (pts if verb != "qCurveTo" else
                          [e for _, e in _quads(pts)]):
                    if q:
                        area += (prev[0] * q[1] - q[0] * prev[1]) / 2
                        prev = q
        for contour in kept:
            for verb, pts in contour:
                if verb == "moveTo":
                    out.moveTo(*pts[0])
                elif verb == "lineTo":
                    out.lineTo(*pts[0])
                elif verb == "curveTo":
                    out.cubicTo(*[c for q in pts for c in q])
                elif verb == "qCurveTo":
                    for c, e in _quads(pts):
                        out.quadTo(c[0], c[1], e[0], e[1])
                elif verb == "closePath":
                    out.close()
        return Art(out)

    def despeckle(self, min_area=0.01):
        """Drop ink too small to be design.

        An offset of a hand-drawn outline sheds slivers: eroding the
        otzaria_icon cover leaves the shape plus forty fragments, none of them a
        thirtieth of a square unit. They paint nothing, but they are enough
        geometry to make skia's own boolean ops fail on the next operation and
        to make `normalize_svg_overlaps.py` refuse the source, so they are
        cleared as soon as they appear.

        Subtracting the small contours is what does it, rather than rebuilding
        the region from the large ones: a speck sits *inside* the area a large
        contour encloses, so a rebuild puts it straight back. Subtracting a
        contour that was a small hole rather than a speck is a no-op, which is
        why one rule covers both - filling a hole too small to print is a
        different decision, and `fill_holes` makes it.
        """
        specks = Art()
        for c in contours(self):
            if c.area < min_area:
                specks = specks | c
        return self - specks if not specks.is_empty else self

    # -- interior detail ----------------------------------------------------
    def filled(self):
        """The region with every enclosed hole filled in."""
        out = Art()
        for c in contours(self):
            out = out | c
        return out

    def holes(self):
        """The enclosed black regions inside the region.

        Holes are worth separating from *gaps* - the open channels between two
        parts of a mark - because a hole is unambiguous: it is bounded by the
        mark on every side, so it can be measured and filled without any risk of
        touching the silhouette. There is no equally safe test for a gap, and
        trying to find one morphologically does not work: a closing wide enough
        to bridge the gaps in a mark this small turns the whole mark into a
        blob, and the "gaps" it then reports are its own outline.
        """
        return self.filled() - self

    def fill_holes(self, max_area):
        """Fill the enclosed holes whose area is below `max_area`.

        At badge scale a hole from Fluent's own drawing - the eyes of a pair of
        scissors' handles, say - lands well under a pixel across and prints as a
        smudge rather than as a hole. Closing it is what Fluent itself does when
        it redraws a mark small, and it costs nothing: the silhouette is
        untouched.
        """
        out = self
        for h in contours(self.holes()):
            if h.area < max_area:
                out = out | h
        return out

    # -- output ------------------------------------------------------------
    def d(self, precision=4):
        return _to_d(self.p, precision)


# Skia's stroker emits conics, which the boolean ops cannot consume. Convert
# them to quadratics first, at a tolerance far below anything this canvas can
# show: 0.25 (the default) is a quarter of a unit, which is a visible error at
# 24 units across.
CONIC_TOLERANCE = 0.002


def _dequadded(p):
    out = p.convertConicsToQuads(CONIC_TOLERANCE)
    return p if out is None else out


def _stroked(p, width, cap, join=None):
    """Stroke a path and resolve the result into a filled region.

    Skia's stroker will occasionally hand back geometry its own boolean ops then
    refuse, with nothing more specific than "operation did not succeed". It
    happens on near-degenerate input - an outline that has already been offset
    once, a hand-drawn cover eroded until parts of it nearly meet - which is
    exactly the input these recipes feed it. Simplifying the path first clears
    it in every case seen here; nudging the width by a ten-thousandth of a unit
    is the fallback, being far below anything this canvas can express.
    """
    join = join or pathops.LineJoin.ROUND_JOIN
    for attempt, w in enumerate((width, width, width * 1.0001)):
        q = pathops.Path()
        q.addPath(pathops.simplify(_dequadded(p)) if attempt else p)
        q.stroke(w, cap, join, 4.0)
        try:
            return Art(pathops.simplify(_dequadded(q)))
        except pathops.PathOpsError:
            continue
    raise pathops.PathOpsError(
        "skia could not resolve a stroke of width %g; the input is probably "
        "degenerate" % width)


def _band(p, width):
    """The closed region swept by stroking p's boundary with `width`, centred on
    it: half falls outside the region and half inside."""
    q = pathops.Path()
    q.addPath(p)
    return _stroked(q, width, pathops.LineCap.ROUND_CAP)


def _flatten(p, n=16):
    """The outline as points, curves subdivided into `n` steps each.

    Yields None where one contour ends and the next begins, so a caller
    measuring along the outline does not also measure the jump between them.
    """
    start = cur = None
    for verb, q in segments(p):
        if verb == "moveTo":
            cur = start = q[0]
            yield None
            yield cur
        elif verb == "lineTo":
            cur = q[0]
            yield cur
        elif verb in ("curveTo", "qCurveTo"):
            pieces = ([[cur] + list(q)] if verb == "curveTo"
                      else [[cur, c, e] for c, e in _quads(q)])
            for ctrl in pieces:
                for i in range(1, n + 1):
                    t = i / n
                    a = ctrl
                    while len(a) > 1:
                        a = [((1 - t) * a[k][0] + t * a[k + 1][0],
                              (1 - t) * a[k][1] + t * a[k + 1][1])
                             for k in range(len(a) - 1)]
                    yield a[0]
                cur = ctrl[-1]
        elif verb == "closePath" and start is not None:
            cur = start
            yield cur


def _perimeter(p, n=16):
    total, prev = 0.0, None
    for pt in _flatten(p, n):
        if pt is not None and prev is not None:
            total += math.dist(prev, pt)
        prev = pt
    return total


def _quads(pts):
    """Split one pen `qCurveTo` into plain (control, end) quadratics.

    A pen's qCurveTo carries TrueType-style points: consecutive off-curve
    controls with their on-curve midpoints left implied. Writing those straight
    out as an SVG polybezier `Q` treats every point as explicit and draws a
    different curve, so they have to be decomposed first.
    """
    return pathops.decompose_quadratic_segment(tuple(pts))


def segments(p):
    """`path.segments` with TrueType's implied points made explicit.

    A closed contour drawn entirely from off-curve points - the pupil of
    Fluent's eye is one - arrives as a bare `qCurveTo` whose final element is
    `None`, with no `moveTo` before it. Its on-curve start is implied: the
    midpoint of the last control and the first. Every consumer below reads the
    stream through here so that case cannot be missed silently.
    """
    for verb, pts in p.segments:
        if verb == "qCurveTo" and pts and pts[-1] is None:
            off = tuple(pts[:-1])
            start = ((off[-1][0] + off[0][0]) / 2,
                     (off[-1][1] + off[0][1]) / 2)
            yield "moveTo", (start,)
            yield "qCurveTo", off + (start,)
        else:
            yield verb, pts


def _fmt(v, precision):
    s = ("%.*f" % (precision, v)).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _to_d(p, precision=4):
    out, f = [], lambda v: _fmt(v, precision)
    for verb, q in segments(p):
        if verb == "moveTo":
            out.append("M %s %s" % (f(q[0][0]), f(q[0][1])))
        elif verb == "lineTo":
            out.append("L %s %s" % (f(q[0][0]), f(q[0][1])))
        elif verb == "curveTo":
            out.append("C " + " ".join("%s %s" % (f(x), f(y)) for x, y in q))
        elif verb == "qCurveTo":
            for c, e in _quads(q):
                out.append("Q %s %s %s %s" % (f(c[0]), f(c[1]),
                                              f(e[0]), f(e[1])))
        elif verb == "closePath":
            out.append("Z")
    return " ".join(out)


# --------------------------------------------------------------------------
# Reading the committed sources
# --------------------------------------------------------------------------
def _paths_of(name):
    tree = ET.parse(os.path.join(SVG_DIR, name + ".svg"))
    root = tree.getroot()
    out = []
    for el in root.iter("{%s}path" % SVG_NS):
        d = el.get("d")
        if d:
            out.append(((el.get("fill") or "").strip().lower(),
                        simplified(d, el.get("fill-rule") or root.get("fill-rule"))))
    return out


def layers(name):
    """(solids, knockouts) for a source, as lists of Art.

    A path counts as a knockout when it says fill="white" or when it sits
    wholly inside the others - the same test repair_glyphs.py applies, so what
    comes back is what the font will treat as a cut.
    """
    ps = _paths_of(name)
    simps = [p for _, p in ps]
    solids, cuts = [], []
    for i, (fill, p) in enumerate(ps):
        if fill == "white" or (len(simps) > 1 and is_knockout_index(simps, i)):
            cuts.append(Art(p))
        else:
            solids.append(Art(p))
    return solids, cuts


def glyph(name):
    """The region the font fills for `name`: solids minus knockouts."""
    solids, cuts = layers(name)
    out = Art()
    for s in solids:
        out = out | s
    for c in cuts:
        out = out - c
    return out


def silhouette(name):
    """Every layer unioned, knockouts filled in - the icon's outer shape."""
    solids, cuts = layers(name)
    out = Art()
    for s in solids + cuts:
        out = out | s
    return out


def part(name, index):
    """One raw `<path>` of a source, in file order. Use when a recipe wants a
    specific component (the badge disc, a letter) rather than the whole icon."""
    return Art(_paths_of(name)[index][1])


def contours(art):
    """Split a region into its separate closed contours, largest area first."""
    out, cur = [], None
    for verb, pts in segments(art.p):
        if verb == "moveTo":
            if cur is not None:
                out.append(cur)
            cur = pathops.Path()
            cur.moveTo(*pts[0])
        elif verb == "lineTo":
            cur.lineTo(*pts[0])
        elif verb == "curveTo":
            cur.cubicTo(*[c for q in pts for c in q])
        elif verb == "qCurveTo":
            for c, e in _quads(pts):
                cur.quadTo(c[0], c[1], e[0], e[1])
        elif verb == "closePath":
            cur.close()
    if cur is not None:
        out.append(cur)
    # Each contour is simplified on its own so it comes back as the region it
    # encloses, wound positively. Without that, a contour that was a hole in the
    # original is still wound the other way, and unioning it cancels instead of
    # covering - which makes `filled()` return the region it started from and
    # `holes()` claim an icon has none.
    return sorted((Art(pathops.simplify(c)) for c in out), key=lambda a: -a.area)


# --------------------------------------------------------------------------
# Primitives, for the parts that genuinely are new drawing
# --------------------------------------------------------------------------
def rect(x0, y0, x1, y1):
    p = pathops.Path()
    p.moveTo(x0, y0)
    p.lineTo(x1, y0)
    p.lineTo(x1, y1)
    p.lineTo(x0, y1)
    p.close()
    return Art(p)


def round_rect(x0, y0, x1, y1, r):
    """A rectangle with equal circular corners; r is clamped to fit, so r=h/2
    gives a stadium."""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    k = r * 0.5522847498307936
    p = pathops.Path()
    p.moveTo(x0 + r, y0)
    p.lineTo(x1 - r, y0)
    p.cubicTo(x1 - r + k, y0, x1, y0 + r - k, x1, y0 + r)
    p.lineTo(x1, y1 - r)
    p.cubicTo(x1, y1 - r + k, x1 - r + k, y1, x1 - r, y1)
    p.lineTo(x0 + r, y1)
    p.cubicTo(x0 + r - k, y1, x0, y1 - r + k, x0, y1 - r)
    p.lineTo(x0, y0 + r)
    p.cubicTo(x0, y0 + r - k, x0 + r - k, y0, x0 + r, y0)
    p.close()
    return Art(pathops.simplify(p))


def circle(cx, cy, r):
    return ellipse(cx, cy, r, r)


def ellipse(cx, cy, rx, ry):
    kx, ky = rx * 0.5522847498307936, ry * 0.5522847498307936
    p = pathops.Path()
    p.moveTo(cx, cy - ry)
    p.cubicTo(cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy)
    p.cubicTo(cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry)
    p.cubicTo(cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy)
    p.cubicTo(cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry)
    p.close()
    return Art(pathops.simplify(p))


def polygon(points):
    p = pathops.Path()
    p.moveTo(*points[0])
    for q in points[1:]:
        p.lineTo(*q)
    p.close()
    return Art(pathops.simplify(p))


def taper(p0, p1, w0, w1):
    """A straight stroke from p0 to p1 whose width goes w0 -> w1: the shape a
    blade or a calligraphic mark needs, which a uniform stroke cannot give."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L == 0:
        return Art()
    nx, ny = -dy / L, dx / L
    return polygon([(x0 + nx * w0 / 2, y0 + ny * w0 / 2),
                    (x1 + nx * w1 / 2, y1 + ny * w1 / 2),
                    (x1 - nx * w1 / 2, y1 - ny * w1 / 2),
                    (x0 - nx * w0 / 2, y0 - ny * w0 / 2)])


def stroke_line(points, width, closed=False, cap="round"):
    """A polyline stroked to a filled region, for thin details."""
    p = pathops.Path()
    p.moveTo(*points[0])
    for q in points[1:]:
        p.lineTo(*q)
    if closed:
        p.close()
    caps = {"round": pathops.LineCap.ROUND_CAP, "butt": pathops.LineCap.BUTT_CAP}
    return _stroked(p, width, caps[cap])


def curve(points, width, cap="round"):
    """A cubic through `points` = [p0, c0, c1, p1, c2, c3, p2, ...], stroked."""
    p = pathops.Path()
    p.moveTo(*points[0])
    for i in range(1, len(points), 3):
        p.cubicTo(*[c for q in points[i:i + 3] for c in q])
    caps = {"round": pathops.LineCap.ROUND_CAP, "butt": pathops.LineCap.BUTT_CAP}
    return _stroked(p, width, caps[cap])


def lens(x0, x1, cy, rise, drop):
    """A closed almond: a cubic bulging `rise` above the chord x0..x1 at height
    cy, and one dropping `drop` below it. The eye, and each lip."""
    w = x1 - x0
    k = w * 0.28
    p = pathops.Path()
    p.moveTo(x0, cy)
    p.cubicTo(x0 + k, cy - rise * 1.34, x1 - k, cy - rise * 1.34, x1, cy)
    p.cubicTo(x1 - k, cy + drop * 1.34, x0 + k, cy + drop * 1.34, x0, cy)
    p.close()
    return Art(pathops.simplify(p))


# --------------------------------------------------------------------------
# Writing a source
# --------------------------------------------------------------------------
HEADER = ('<svg xmlns="http://www.w3.org/2000/svg"\n'
          '     width="24"\n'
          '     height="24"\n'
          '     viewBox="0 0 24 24"')


def write(name, solid, cuts=(), preserve_overlap=False, precision=4):
    """Write a source. `cuts` are emitted as fill="white" paths.

    A new icon whose detail is cut out of a solid body *must* declare that with
    fill="white": the geometric "is it inside" inference is kept only for four
    legacy sources, so an unmarked cut would ship as ink on ink. The white fill
    also makes normalize_svg_overlaps.py leave the layers alone.
    """
    if solid.is_empty or solid.area < 1.0:
        raise ValueError(
            "%s: the recipe produced %.4f square units of ink. Something "
            "collapsed - a boolean op on near-degenerate geometry can return "
            "an empty region rather than failing - and writing it would ship a "
            "blank glyph." % (name, solid.area))
    cuts = [c for c in cuts if not c.is_empty]
    root = HEADER
    if preserve_overlap:
        root += '\n     data-preserve-overlap="true"'
    root += ">\n"
    body = ['  <path d="%s"/>\n' % solid.d(precision)]
    for c in cuts:
        body.append('  <path fill="white"\n        d="%s"/>\n' % c.d(precision))
    text = root + "".join(body) + "</svg>\n"
    path = os.path.join(SVG_DIR, name + ".svg")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path
