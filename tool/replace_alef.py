#!/usr/bin/env python3
"""Swap the alef letterform for a new drawing, everywhere it appears.

WHAT THIS DOES
--------------
The same alef is drawn into seventeen sources - on its own, beside a second
alef, behind one, inside a book, under a score, next to an eraser - at full size
in most of them and reduced in a few. Replacing the letterform by hand means
finding it seventeen times and getting the scale and the placement right each
time, which is exactly the kind of edit that silently leaves one icon behind.

Given the old letterform and the new one, this finds every instance and swaps
it.

HOW AN INSTANCE IS FOUND
------------------------
By shape, not by bounding box. A contour is an instance if, once it is scaled
and placed onto the old letterform's own box, the area where the two disagree is
under MATCH_TOL of the letterform's area. A box test is not enough: the family
holds book covers, document bodies and a tet whose boxes are the same
proportion as the alef's and which are not alefs at all - a plain box test
matches more than forty of them.

HOW IT IS PLACED
----------------
The new letterform is scaled by one factor on both axes, so it is never
squashed to fill a box it does not have the proportions for, and it is centred
on the box the old instance occupied. The two drawings differ slightly in
proportion, so an instance's box moves by a few hundredths; its centre does not.

THE OUTLINED ALEF
-----------------
alef_24_regular is not a copy of the letterform: it is the letterform with its
three strokes hollowed out. That hollow is a uniform inset - measured against
the drawn one at 0.48 units, matching it to within 4% of its area - so it is
rebuilt here as the new letterform minus its own inset rather than substituted.

USAGE
-----
  python3 tool/replace_alef.py --old OLD.svg --check     # report, change nothing
  python3 tool/replace_alef.py --old OLD.svg             # rewrite the family
  python3 tool/replace_alef.py --old OLD.svg --new N.svg

Run tool/format_svg.py afterwards, then tool/unify_shared_parts.py, then
dart run tool/generate.dart.

Requires: skia-pathops, fonttools.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pathops
    from fontTools.svgLib.path import parse_path
    from format_svg import clean_contour, emit_contour, parse_segments
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")
REFERENCE = "alef_24_filled"
OUTLINED = "alef_24_regular"

PATH_RE = re.compile(r'(<path\b)([^>]*?)(/?>)', re.S)
D_RE = re.compile(r'(\bd\s*=\s*")([^"]*)(")', re.S)

MATCH_TOL = 0.05       # of the letterform's area, for a contour to be an instance
MIN_SCALE = 0.20       # instances smaller than this are not searched for
MAX_SCALE = 1.20
INSET = 0.48           # the outlined alef's stroke, in canvas units
PRECISION = 6

# Four alefs in the family are not copies of the letterform: they are separate,
# simpler drawings of it, made small enough that the letterform's own detail
# would not have survived. They sit between 0.13 and 0.46 away from it, well
# past anything the shape test should accept on its own, so they are named here
# instead - and they do have to be replaced, because each one shares an icon
# with a full-size alef and would otherwise be the old letterform standing
# beside the new one.
SIMPLIFIED = {
    ("alef_near_alef_24_regular", 1, 0),
    ("alef_behind_alef_24_regular", 1, 0),
    ("book_alef_24_filled", 2, 0),
    ("book_alef_24_regular", 0, 2),
    ("search_in_the_text_24_regular", 0, 2),
}


def path_of(d, fill=pathops.FillType.WINDING):
    p = pathops.Path()
    parse_path(d, p.getPen())
    p.fillType = fill
    return pathops.simplify(p)


def contours_of(d):
    out = []
    for a, b in parse_segments(d):
        start, segs = clean_contour(a, b, PRECISION)
        if segs:
            out.append((start, segs))
    return out


def bbox(start, segs):
    xs = [p[0] for p in [start] + [s[2] for s in segs]]
    ys = [p[1] for p in [start] + [s[2] for s in segs]]
    return min(xs), min(ys), max(xs), max(ys)


def emit(start, segs):
    return emit_contour(start, segs, PRECISION)


def transform(start, segs, s, dx, dy):
    def t(p):
        return (p[0] * s + dx, p[1] * s + dy)
    return t(start), [(k, tuple(t(c) for c in ctrl), t(end))
                      for k, ctrl, end in segs]


def fit_into(start, segs, box):
    """Scale uniformly by height and centre on `box`."""
    x0, y0, x1, y1 = bbox(start, segs)
    s = (box[3] - box[1]) / (y1 - y0)
    w, h = (x1 - x0) * s, (y1 - y0) * s
    dx = (box[0] + box[2]) / 2 - w / 2 - x0 * s
    dy = (box[1] + box[3]) / 2 - h / 2 - y0 * s
    return transform(start, segs, s, dx, dy)


def signed_area(start, segs):
    pts = [start] + [s[2] for s in segs]
    n = len(pts)
    return sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
               for i in range(n)) / 2


def reverse_contour(start, segs):
    """The same outline walked the other way round.

    Several of the alefs are interior knockouts - the alef inside a book cover
    is white because its winding cancels the cover's. Dropping in a replacement
    that runs the other way turns the hole into a second solid shape, so a
    replacement always takes the direction the contour it stands in for had."""
    pts = [start] + [s[2] for s in segs]
    out = []
    for i in range(len(segs) - 1, -1, -1):
        kind, ctrl, _ = segs[i]
        out.append((kind, tuple(reversed(ctrl)), pts[i]))
    return pts[-1], out


def matched_direction(start, segs, like_start, like_segs):
    a, b = signed_area(start, segs), signed_area(like_start, like_segs)
    if a == 0 or b == 0 or (a > 0) == (b > 0):
        return start, segs
    return reverse_contour(start, segs)


def mismatch(cand, ref_start, ref_segs, ref_area):
    """Area where a candidate contour and the letterform disagree, once the
    candidate is placed on the letterform's own box.

    Measured as the two one-way differences added together, not as XOR: the
    letterform's contours run anticlockwise, and pathops' XOR and UNION on two
    anticlockwise paths return a signed area that is not the symmetric
    difference at all - it reported 90 units of disagreement between two
    drawings that differ by 0.4."""
    box = bbox(ref_start, ref_segs)
    placed = fit_into(cand[0], cand[1], box)
    a = path_of(emit(*placed))
    b = path_of(emit(ref_start, ref_segs))
    lost = abs(pathops.op(b, a, pathops.PathOp.DIFFERENCE).area)
    gained = abs(pathops.op(a, b, pathops.PathOp.DIFFERENCE).area)
    return (lost + gained) / ref_area


def erode(shape, t):
    band = pathops.Path()
    shape.draw(band.getPen())
    band.stroke(2 * t, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    band.convertConicsToQuads()
    return pathops.op(shape, pathops.simplify(band), pathops.PathOp.DIFFERENCE)


class Pen:
    def __init__(self):
        self.out = []

    def moveTo(self, p):
        self.out.append("M%.4f %.4f" % p)

    def lineTo(self, p):
        self.out.append("L%.4f %.4f" % p)

    def curveTo(self, *pts):
        self.out.append("C" + " ".join("%.4f %.4f" % q for q in pts))

    def qCurveTo(self, *pts):
        self.out.append("Q" + " ".join("%.4f %.4f" % q for q in pts))

    def closePath(self):
        self.out.append("Z")

    endPath = closePath


def outlined(new_d, inset):
    solid = path_of(new_d)
    ring = pathops.op(solid, erode(solid, inset), pathops.PathOp.DIFFERENCE)
    pen = Pen()
    pathops.simplify(ring).draw(pen)
    return " ".join(pen.out)


def load_letterform(path):
    d = re.search(r'd="([^"]*)"', open(path, encoding="utf-8").read(),
                  re.S).group(1)
    cs = contours_of(d)
    if len(cs) != 1:
        sys.exit("%s should hold one contour, found %d" % (path, len(cs)))
    return cs[0], d


def main(argv):
    check = "--check" in argv

    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    old_path = opt("--old", None)
    new_path = opt("--new", os.path.join(SVG_DIR, REFERENCE + ".svg"))
    if not old_path:
        sys.exit("--old FILE is required: the letterform being replaced")

    (os_, oseg), old_d = load_letterform(old_path)
    (ns, nseg), new_d = load_letterform(new_path)
    ref_area = abs(path_of(old_d).area)
    ob = bbox(os_, oseg)
    nb = bbox(ns, nseg)
    print("old letterform %.3f x %.3f, new %.3f x %.3f, area %.3f"
          % (ob[2] - ob[0], ob[3] - ob[1], nb[2] - nb[0], nb[3] - nb[1],
             ref_area))

    total = 0
    for f in sorted(glob.glob(os.path.join(SVG_DIR, "*.svg"))):
        base = os.path.splitext(os.path.basename(f))[0]
        if base == REFERENCE:
            continue
        text = open(f, encoding="utf-8").read()
        if base == OUTLINED:
            d = outlined(new_d, INSET)
            print("%-42s rebuilt as the letterform inset by %.2f"
                  % (base, INSET))
            if not check:
                m = PATH_RE.search(text)
                dm = D_RE.search(m.group(2))
                attrs = (m.group(2)[:dm.start(1)] + dm.group(1) + d
                         + dm.group(3) + m.group(2)[dm.end(3):])
                open(f, "w", encoding="utf-8", newline="\n").write(
                    text[:m.start(0)] + m.group(1) + attrs + m.group(3)
                    + text[m.end(0):])
            total += 1
            continue

        pieces, last, hits = [], 0, []
        for pi, m in enumerate(PATH_RE.finditer(text)):
            dm = D_RE.search(m.group(2))
            if not dm:
                continue
            cs = contours_of(dm.group(2))
            if not cs:
                continue
            outc, changed = [], False
            for ci, (start, segs) in enumerate(cs):
                x0, y0, x1, y1 = bbox(start, segs)
                s = (y1 - y0) / (ob[3] - ob[1])
                named = (base, pi, ci) in SIMPLIFIED
                if named or MIN_SCALE <= s <= MAX_SCALE:
                    err = mismatch((start, segs), os_, oseg, ref_area)
                    if named or err < MATCH_TOL:
                        placed = fit_into(ns, nseg, (x0, y0, x1, y1))
                        placed = matched_direction(placed[0], placed[1],
                                                   start, segs)
                        outc.append(emit(*placed))
                        hits.append("scale %.3f at (%.2f, %.2f), shape "
                                    "distance %.3f%s"
                                    % (s, x0, y0, err,
                                       " [named]" if named else ""))
                        changed = True
                        continue
                outc.append(emit(start, segs))
            if not changed:
                continue
            new_block = "\n       ".join(outc)
            attrs = (m.group(2)[:dm.start(1)] + dm.group(1) + new_block
                     + dm.group(3) + m.group(2)[dm.end(3):])
            pieces.append(text[last:m.start(0)])
            pieces.append(m.group(1) + attrs + m.group(3))
            last = m.end(0)
        if not hits:
            continue
        pieces.append(text[last:])
        print("%-42s %s" % (base, "; ".join(hits)))
        total += len(hits)
        if not check:
            open(f, "w", encoding="utf-8", newline="\n").write("".join(pieces))

    print("%d instance(s) %s" % (total, "found" if check else "replaced"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
