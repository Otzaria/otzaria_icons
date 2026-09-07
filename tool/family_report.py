#!/usr/bin/env python3
"""Find the parts icons share, and where those parts have drifted apart.

WHY THIS EXISTS
---------------
Most of these icons are built from a small set of recurring pieces: the book
cover behind nineteen of them, the alef glyph inside eleven, the magnifier on
the eight `search_in_*` icons, the document body under the clipboard set. Those
pieces were copied between files over years of separate edits, so many of them
no longer match: the same book cover exists in six slightly different spellings,
and the same document body in nine.

Some of that divergence is invisible - the same shape written with a different
number of segments, or a coordinate that drifted in the sixth decimal. Some of
it is real, and the icons genuinely do not line up.

Telling those two cases apart is the whole point of this report, because they
call for opposite treatment. Pieces that are geometrically the same may be
unified onto one canonical spelling with no graphical change at all. Pieces that
genuinely differ must not be silently unified, because that would redraw the
icon - they are reported for a person to decide.

WHAT COUNTS AS "THE SAME"
-------------------------
Two contours are the same when no point on either outline is further than
`--tol` canvas units from the other outline. The default matches the tolerance
tool/format_svg.py uses: far below one subpixel at any size the package renders.

USAGE
-----
  python3 tool/family_report.py                 # full report
  python3 tool/family_report.py --unifiable     # only what can be unified safely
  python3 tool/family_report.py --drift         # only genuine visual drift
  python3 tool/family_report.py --tol 0.002

Requires: skia-pathops, fonttools.
"""
import sys, os, re, glob, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pathops
    from fontTools.svgLib.path import parse_path
    from format_svg import parse_segments, clean_contour, emit_contour, PRECISION
    from region_diff import max_boundary_shift
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")
D_RE = re.compile(r'\bd\s*=\s*"([^"]*)"', re.S)

TOL = 0.002
# Contours whose bounding boxes differ by more than this are not the same piece,
# so they are never compared. Keeps the pairwise work small and stops unrelated
# shapes of similar size from being grouped together.
BBOX_TOL = 0.35


def path_of(d):
    p = pathops.Path()
    parse_path(d, p.getPen())
    return p


def contour_bbox(d):
    xs, ys = [], []
    for start, segments in parse_segments(d):
        xs.append(start[0])
        ys.append(start[1])
        for segment in segments:
            end = segment[-1]
            xs.append(end[0])
            ys.append(end[1])
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)


def contour_lines(text):
    """The contours of a formatted source, exactly as they are written in it.

    tool/format_svg.py writes one contour per line, so a line of path data is a
    contour and can be swapped for another spelling of the same shape without
    touching anything around it. That is what makes unification a line-level
    edit rather than a rewrite of the file."""
    out = []
    for d in D_RE.findall(text):
        for line in d.split("\n"):
            line = line.strip()
            if line:
                out.append(line)
    return out


def contours_of(path):
    """Every contour in a source, as (d_string, bbox)."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return [(line, contour_bbox(line)) for line in contour_lines(text)]


def bbox_close(a, b, tol=BBOX_TOL):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def shape_distance(d1, d2):
    """How far apart two contours are, in canvas units."""
    if d1 == d2:
        return 0.0
    return max_boundary_shift(path_of(d1), path_of(d2))


def build_groups(tol):
    """Cluster every contour in the package by shape.

    Returns a list of groups; each group is a list of (icon, d, bbox) that are
    all within `tol` of each other."""
    entries = []
    for path in sorted(glob.glob(os.path.join(SVG_DIR, "*.svg"))):
        icon = os.path.basename(path)[:-4]
        for d, bb in contours_of(path):
            entries.append((icon, d, bb))

    # Bucket by rounded bbox first so only plausible matches are compared.
    buckets = collections.defaultdict(list)
    for entry in entries:
        key = tuple(round(v * 2) / 2 for v in entry[2])
        buckets[key].append(entry)
    # A contour can sit on a bucket boundary, so also consider neighbours.
    merged, seen = [], set()
    keys = sorted(buckets)
    for key in keys:
        if key in seen:
            continue
        group = list(buckets[key])
        seen.add(key)
        for other in keys:
            if other in seen or not bbox_close(key, other, BBOX_TOL):
                continue
            group.extend(buckets[other])
            seen.add(other)
        merged.append(group)

    groups = []
    for candidates in merged:
        remaining = list(candidates)
        while remaining:
            seed = remaining.pop(0)
            cluster, rest = [seed], []
            for entry in remaining:
                if bbox_close(seed[2], entry[2]) and \
                        shape_distance(seed[1], entry[1]) <= tol:
                    cluster.append(entry)
                else:
                    rest.append(entry)
            remaining = rest
            groups.append(cluster)
    return groups


def canonical_spelling(cluster):
    """The spelling a unified group should adopt: the one already used by the
    most icons, then the shortest, then alphabetical. Preferring the majority
    keeps the diff small and keeps whichever version was already the norm."""
    counts = collections.Counter(d for _, d, _ in cluster)
    return min(counts, key=lambda d: (-counts[d], len(d), d))


def report(tol, want_unifiable=True, want_drift=True):
    groups = build_groups(tol)

    unifiable, singletons = [], 0
    for cluster in groups:
        icons = sorted({icon for icon, _, _ in cluster})
        spellings = {d for _, d, _ in cluster}
        if len(icons) < 2:
            singletons += 1
            continue
        if len(spellings) > 1:
            unifiable.append((icons, cluster, spellings))

    # Genuine drift: clusters that did NOT merge but sit on the same footprint,
    # i.e. the same piece of artwork drawn differently enough to see.
    by_footprint = collections.defaultdict(list)
    for cluster in groups:
        key = tuple(round(v, 1) for v in cluster[0][2])
        by_footprint[key].append(cluster)
    drift = []
    for key, clusters in by_footprint.items():
        if len(clusters) < 2:
            continue
        icons = sorted({i for c in clusters for i, _, _ in c})
        if len(icons) < 2:
            continue
        worst = 0.0
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                worst = max(worst, shape_distance(clusters[i][0][1],
                                                  clusters[j][0][1]))
        drift.append((worst, key, clusters))
    drift.sort(reverse=True)

    if want_unifiable:
        print("=" * 78)
        print("SHARED PARTS THAT CAN BE UNIFIED WITH NO GRAPHICAL CHANGE")
        print("=" * 78)
        print("Same shape (within %.4f units), written differently. Unifying "
              "these\nchanges no pixels and makes the family literally "
              "identical where it should be.\n" % tol)
        total_icons = set()
        for icons, cluster, spellings in sorted(unifiable, key=lambda g: -len(g[0])):
            total_icons.update(icons)
            print("  %2d icons, %d spellings -> 1   [%.1f %.1f %.1f %.1f]"
                  % (len(icons), len(spellings), *cluster[0][2]))
            print("     %s" % ", ".join(icons))
        print("\n  %d shared parts across %d icons can be unified losslessly."
              % (len(unifiable), len(total_icons)))

    if want_drift:
        print()
        print("=" * 78)
        print("GENUINE VISUAL DRIFT - NEEDS A HUMAN DECISION")
        print("=" * 78)
        print("The same part of the design, drawn differently enough to see. "
              "Unifying these\nWOULD change the artwork, so nothing here is "
              "touched automatically.\n")
        for worst, key, clusters in drift:
            icons_by_variant = [sorted({i for i, _, _ in c}) for c in clusters]
            print("  footprint [%.1f %.1f %.1f %.1f]  %d variants, "
                  "worst separation %.3f units" % (*key, len(clusters), worst))
            for variant in sorted(icons_by_variant, key=lambda v: -len(v)):
                print("     %2d: %s" % (len(variant), ", ".join(variant)))
        print("\n  %d parts show visible drift." % len(drift))


def main(argv):
    tol = TOL
    if "--tol" in argv:
        i = argv.index("--tol")
        tol = float(argv[i + 1])
        del argv[i:i + 2]
    want_unifiable = "--drift" not in argv
    want_drift = "--unifiable" not in argv
    report(tol, want_unifiable, want_drift)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
