#!/usr/bin/env python3
"""Find the defects that years of patching left behind in the icon outlines.

WHY THIS EXISTS
---------------
These sources were drawn in several different programs and then edited many
times. Each edit left something behind. The icons look right at a glance, so
none of it was ever caught, but the debris is there and it does two things:
it shows up as stray pips and hairlines when an icon is displayed large, and it
turns into mush when an icon is displayed at 16 px.

This reports six kinds of defect, all of which are consequences of patching
rather than of design:

  speck          A tiny separate filled blob, far too small to be part of the
                 design. Left behind by a boolean operation or a stray click.

  spike          A run of very short segments that turns sharply and comes back
                 - a whisker sticking out of an otherwise smooth outline. Only
                 visible when the icon is drawn large.

  needle         Two points on top of each other with a sliver between them: a
                 zero-width tail on a contour.

  self-crossing  A contour that crosses itself. It renders correctly today only
                 because the coordinates happen to land where they do; any edit
                 near it can flip a large area black or white without warning.
                 This is the one to fix first - it is a trap for the next
                 person to touch the file.

  thin ink       The narrowest filled feature in the icon. Below about one unit
                 it cannot survive being drawn at 16 px, where one unit is
                 two thirds of a pixel: the stroke fades or breaks up.

  thin gap       The narrowest gap between two filled areas. Below about one
                 unit the two areas visually merge at 16 px and the icon loses
                 its detail.

Nothing here is changed automatically. Every one of these is a judgement about
the artwork, and fixing one moves pixels - which is exactly what the structural
work is required not to do. This tool says where to look and why.

USAGE
-----
  python3 tool/audit_geometry.py                    # audit every source
  python3 tool/audit_geometry.py a.svg b.svg        # audit specific sources
  python3 tool/audit_geometry.py --kind self-crossing
  python3 tool/audit_geometry.py --verbose          # include clean icons

Requires: skia-pathops, fonttools.
"""
import sys, os, re, glob, math, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pathops
    from fontTools.svgLib.path import parse_path
    from region_diff import region_of_file, _flatten, SAMPLE_STEP
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")
D_RE = re.compile(r'\bd\s*=\s*"([^"]*)"', re.S)

# --- thresholds, all in canvas units on the 24x24 grid ---------------------

# A filled blob smaller than this is debris. 0.05 square units is a 0.22-unit
# square: a seventh of a pixel at 24 px, invisible except as a speck when the
# icon is blown up.
SPECK_AREA = 0.05

# A turn sharper than this, between two segments both shorter than SPIKE_LENGTH,
# is a whisker rather than a corner of the design.
SPIKE_ANGLE = math.radians(115)
SPIKE_LENGTH = 0.2

# Two consecutive on-curve points closer than this are the same point.
NEEDLE_DISTANCE = 0.01

# Features narrower than this cannot hold up at 16 px, where one canvas unit is
# 0.67 px. Reported, not enforced: a deliberately fine hairline may be fine.
THIN_FEATURE = 1.0

# When measuring how narrow a feature is, only compare parts of the outline that
# are at least this far apart along the outline itself. Without it every point
# measures zero distance against its own neighbours.
ARC_SEPARATION = 1.5


def contour_paths(region):
    """Split a resolved region into one pathops.Path per contour."""
    out, current = [], None
    for verb, points in region:
        if verb == pathops.PathVerb.MOVE:
            if current is not None:
                out.append(current)
            current = pathops.Path()
            current.getPen().moveTo(tuple(points[0]))
        elif current is None:
            continue
        elif verb == pathops.PathVerb.LINE:
            current.getPen().lineTo(tuple(points[0]))
        elif verb == pathops.PathVerb.CUBIC:
            current.getPen().curveTo(*[tuple(p) for p in points])
        elif verb == pathops.PathVerb.QUAD:
            current.getPen().qCurveTo(*[tuple(p) for p in points])
        elif verb == pathops.PathVerb.CLOSE:
            current.getPen().closePath()
    if current is not None:
        out.append(current)
    return out


def find_specks(region):
    out = []
    for contour in contour_paths(region):
        area = abs(contour.area)
        if 0 < area < SPECK_AREA:
            segs, _ = _flatten(contour)
            if segs:
                x, y = segs[0][0]
                out.append(("speck", "area %.4f sq units at (%.2f, %.2f)"
                            % (area, x, y)))
    return out


def _on_curve_points(d):
    """On-curve points of each contour of a raw `d` string, in order."""
    pen_path = pathops.Path()
    parse_path(d, pen_path.getPen())
    contours, current = [], None
    for verb, points in pen_path:
        if verb == pathops.PathVerb.MOVE:
            if current:
                contours.append(current)
            current = [tuple(points[0])]
        elif current is None:
            continue
        elif verb == pathops.PathVerb.CLOSE:
            contours.append(current)
            current = None
        else:
            current.append(tuple(points[-1]))
    if current:
        contours.append(current)
    # A closed contour usually ends on the point it started from. That is what
    # closing means, not a duplicate point, so it must not be reported as one.
    trimmed = []
    for pts in contours:
        while len(pts) > 1 and math.hypot(pts[-1][0] - pts[0][0],
                                          pts[-1][1] - pts[0][1]) < 1e-9:
            pts = pts[:-1]
        trimmed.append(pts)
    return trimmed


def find_spikes_and_needles(d):
    out = []
    for pts in _on_curve_points(d):
        n = len(pts)
        if n < 3:
            continue
        for i in range(n):
            a, b, c = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
            ab = math.hypot(b[0] - a[0], b[1] - a[1])
            bc = math.hypot(c[0] - b[0], c[1] - b[1])
            if ab < NEEDLE_DISTANCE and bc > NEEDLE_DISTANCE:
                out.append(("needle",
                            "duplicate point at (%.3f, %.3f), gap %.4f"
                            % (b[0], b[1], ab)))
                continue
            if ab == 0 or bc == 0 or ab > SPIKE_LENGTH or bc > SPIKE_LENGTH:
                continue
            cos = ((a[0] - b[0]) * (c[0] - b[0]) +
                   (a[1] - b[1]) * (c[1] - b[1])) / (ab * bc)
            angle = math.acos(max(-1.0, min(1.0, cos)))
            # A small interior angle means the outline doubles back on itself.
            if angle < math.pi - SPIKE_ANGLE:
                out.append(("spike",
                            "%.0f degree turn at (%.3f, %.3f) between %.3f and "
                            "%.3f unit segments"
                            % (math.degrees(angle), b[0], b[1], ab, bc)))
    return out


def find_self_crossings(d):
    """A contour that crosses itself changes area when resolved on its own."""
    out = []
    for index, contour in enumerate(contour_paths_from_d(d)):
        raw = abs(contour.area)
        resolved = pathops.Path()
        try:
            pathops.union([contour], resolved.getPen())
        except pathops.PathOpsError:
            out.append(("self-crossing",
                        "contour %d is too tangled for the boolean engine to "
                        "resolve" % index))
            continue
        clean = abs(resolved.area)
        if raw > 1e-9 and abs(raw - clean) / raw > 0.01:
            out.append(("self-crossing",
                        "contour %d encloses %.3f sq units but resolves to "
                        "%.3f: it crosses itself" % (index, raw, clean)))
    return out


def contour_paths_from_d(d):
    path = pathops.Path()
    parse_path(d, path.getPen())
    return contour_paths(path)


def narrowest_features(region):
    """Return (thinnest_ink, thinnest_gap) as (distance, point) pairs.

    Walks the outline and, for each sampled point, finds the closest other point
    of the outline that is well away from it along the outline. The midpoint
    between the two decides whether the narrow place is ink or a gap."""
    segs, _ = _flatten(region, SAMPLE_STEP)
    if not segs:
        return None, None

    # Re-walk contour by contour so arc length is measured along each outline.
    samples = []  # (point, contour_index, arc_length)
    perimeter = {}
    for ci, contour in enumerate(contour_paths(region)):
        csegs, _ = _flatten(contour, SAMPLE_STEP)
        arc = 0.0
        for a, b in csegs:
            samples.append((a, ci, arc))
            arc += math.hypot(b[0] - a[0], b[1] - a[1])
        perimeter[ci] = arc

    cell = 1.0
    grid = collections.defaultdict(list)
    for idx, (p, ci, arc) in enumerate(samples):
        grid[(int(p[0] // cell), int(p[1] // cell))].append(idx)

    # Gather every narrow pair first and decide ink-or-gap afterwards. Deciding
    # inside the loop means a point-in-region test per pair, and there are tens
    # of thousands of pairs on the larger icons.
    candidates = []
    for idx, (p, ci, arc) in enumerate(samples):
        cx, cy = int(p[0] // cell), int(p[1] // cell)
        for ix in range(cx - 1, cx + 2):
            for iy in range(cy - 1, cy + 2):
                for other in grid.get((ix, iy), ()):
                    if other <= idx:
                        continue
                    q, cj, arc_q = samples[other]
                    if ci == cj:
                        # A contour is a loop, so the two ends of the arc-length
                        # scale are the same place. Without wrapping, every
                        # contour reports a zero-width feature at its seam.
                        along = abs(arc - arc_q)
                        along = min(along, perimeter[ci] - along)
                        if along < ARC_SEPARATION:
                            continue
                    dist = math.hypot(p[0] - q[0], p[1] - q[1])
                    if dist < THIN_FEATURE:
                        candidates.append(
                            (dist, ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)))

    candidates.sort(key=lambda c: c[0])
    outline = _flatten(region, 0.5)[0]
    best_ink = best_gap = None
    for dist, mid in candidates:
        if point_inside(outline, mid):
            if best_ink is None:
                best_ink = (dist, mid)
        elif best_gap is None:
            best_gap = (dist, mid)
        if best_ink and best_gap:
            break
    return best_ink, best_gap


def point_inside(outline, point):
    """Even-odd ray cast against an already-flattened outline. The region comes
    out of a boolean union, so its contours do not overlap and this is exact."""
    x, y = point
    crossings = 0
    for (x1, y1), (x2, y2) in outline:
        if (y1 > y) != (y2 > y):
            t = (y - y1) / (y2 - y1)
            if x < x1 + t * (x2 - x1):
                crossings += 1
    return crossings % 2 == 1


def audit(path):
    name = os.path.basename(path)[:-4]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    region = region_of_file(path)

    findings = list(find_specks(region))
    for d in D_RE.findall(text):
        findings.extend(find_spikes_and_needles(d))
        findings.extend(find_self_crossings(d))

    ink, gap = narrowest_features(region)
    if ink and ink[0] < THIN_FEATURE:
        findings.append(("thin ink", "%.3f units wide at (%.2f, %.2f) - %.2f px "
                         "at 16 px" % (ink[0], ink[1][0], ink[1][1],
                                       ink[0] * 16 / 24)))
    if gap and gap[0] < THIN_FEATURE:
        findings.append(("thin gap", "%.3f units at (%.2f, %.2f) - %.2f px at "
                         "16 px" % (gap[0], gap[1][0], gap[1][1],
                                    gap[0] * 16 / 24)))
    return name, findings


def main(argv):
    kinds = None
    verbose = "--verbose" in argv
    if "--kind" in argv:
        i = argv.index("--kind")
        kinds = {argv[i + 1]}
        del argv[i:i + 2]

    files = [a for a in argv if not a.startswith("--")] or \
        sorted(glob.glob(os.path.join(SVG_DIR, "*.svg")))

    totals = collections.Counter()
    affected = 0
    for path in files:
        name, findings = audit(path)
        if kinds:
            findings = [f for f in findings if f[0] in kinds]
        # Many spikes on one icon are one defect, not fifty: collapse the noise.
        grouped = collections.defaultdict(list)
        for kind, detail in findings:
            grouped[kind].append(detail)
        if not grouped:
            if verbose:
                print("clean    %s" % name)
            continue
        affected += 1
        print("%s" % name)
        for kind in sorted(grouped):
            details = grouped[kind]
            totals[kind] += len(details)
            print("   %-14s %d" % (kind, len(details)))
            for detail in details[:3]:
                print("      %s" % detail)
            if len(details) > 3:
                print("      ... and %d more" % (len(details) - 3))

    print("\n%d of %d icons have findings." % (affected, len(files)))
    for kind, count in sorted(totals.items(), key=lambda kv: -kv[1]):
        print("   %-14s %d" % (kind, count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
