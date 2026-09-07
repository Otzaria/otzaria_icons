#!/usr/bin/env python3
"""Remove the debris that years of patching left in the icon outlines.

WHY THIS EXISTS
---------------
tool/audit_geometry.py reports what repeated hand-editing left behind in these
sources. This removes it. The two are deliberately separate: the audit judges,
this one acts, and each category of defect is handled by its own pass with its
own justification and its own limit on how far the outline is allowed to move.

The passes, in the order they run:

  crossings   A contour that crosses itself is replaced by the outline its own
              winding rule already resolves to. This is the one pass that
              changes *nothing* at all: nonzero fill already paints the resolved
              region, and the font pipeline already unions everything, so the
              rendered result is identical by construction. What it removes is a
              trap - geometry that renders correctly only because its
              coordinates happen to land where they do, where any nearby edit
              can flip a large area black or white without warning.

  specks      Separate filled contours far too small to be part of the design
              are deleted. The measured threshold is unambiguous here: the
              sources contain 73 contours below 0.01 square units (median
              0.00005 - slivers that paint nothing), then *nothing at all*
              between 0.01 and 0.05, then real design elements from 0.05 up. The
              cut sits in an empty gap, not in a judgement call.

  needles     Consecutive on-curve points sitting on top of each other, with a
              zero-width sliver of outline between them. The duplicate is
              dropped. Every one in these sources is within 0.01 units.

  spikes      A vertex that juts off an otherwise smooth outline between two very
              short segments - a whisker. It is removed by joining its
              neighbours. Only vertices whose protrusion is under `--max-spike`
              are touched, which is what separates debris from a sharp corner
              that belongs to the design: a shallow bump can be flattened
              invisibly, a real point cannot be flattened at all without
              redrawing the icon.

WHAT THIS DOES NOT TOUCH
------------------------
The audit also reports "thin ink" and "thin gap" - features too narrow to hold
up at 16 px. Those are not patch debris, they are how the icon was designed, and
widening a stroke or opening a gap is a redraw. They stay in the audit report for
a person to decide on.

SAFETY
------
Every edit is verified against the resolved region before the edit, and is kept
only if the icon moved less than that pass's limit. Edits are applied one pass at
a time per file, and if a pass does not fit it is retried edit by edit, so one
ill-fitting spike costs only itself. Limits are in canvas units on the 24x24
grid; one unit is 0.67 px at 16 px.

USAGE
-----
  python3 tool/repair_artifacts.py --check         # report, change nothing
  python3 tool/repair_artifacts.py                 # all passes
  python3 tool/repair_artifacts.py --only crossings
  python3 tool/repair_artifacts.py --max-spike 0.02
  python3 tool/repair_artifacts.py --lossless      # only the crossings pass

Run tool/format_svg.py afterwards to restore the canonical written form.

Requires: skia-pathops, fonttools.
"""
import sys, os, re, glob, math, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pathops
    from fontTools.pens.svgPathPen import SVGPathPen
    from format_svg import (parse_segments, clean_contour, emit_contour,
                            format_svg, fnum)
    from region_diff import (resolve_region, max_boundary_shift,
                             symmetric_difference_area, simplified)
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")
PATH_RE = re.compile(r"(<path\b[^>]*?/?>)", re.S)
D_RE = re.compile(r'(\bd\s*=\s*")([^"]*)(")', re.S)
FR_RE = re.compile(r'fill-rule\s*=\s*"([^"]*)"')

# Geometry is rewritten at this precision so a pass never loses detail; the
# canonical per-file precision is restored afterwards by tool/format_svg.py.
WORK_PRECISION = 6

# How many times the passes may sweep a file before giving up on reaching a
# fixed point. See the loop in main() for why more than one sweep is needed.
MAX_SWEEPS = 6

# --- what counts as debris, from the measured distributions ----------------

# A separate contour below this area is debris. Chosen inside the empty gap
# between the debris cluster (73 contours, all under 0.01) and the smallest real
# design element (0.05+).
SPECK_AREA = 0.01
# ... provided it is also physically tiny, so a long thin design stroke of small
# area is never mistaken for a speck.
SPECK_SIZE = 0.35

# Two consecutive on-curve points closer than this are one point.
NEEDLE_DISTANCE = 0.01

# A whisker's two segments are both shorter than this...
SPIKE_SEGMENT = 0.2
# ...and it turns at least this sharply.
SPIKE_ANGLE = 65.0

# Below this angle the outline is not turning a corner, it is doubling back
# along itself: a hairline that encloses no area and paints nothing.
SLIVER_ANGLE = 15.0
# How long such a hairline may be and still be removed. It is allowed to be much
# longer than a whisker is tall because its width, and so its ink, is zero.
SLIVER_LENGTH = 0.25
# How far a whisker may stick out and still be flattened. This is capped by
# SPIKE_SEGMENT rather than chosen freely: a vertex only qualifies as a whisker
# when *both* its segments are under 0.2 units and it turns sharply, so whatever
# it is, it is a feature no more than 0.2 units across - 0.13 px at 16 px and
# 0.4 px at 48 px. Nothing that small can be a design feature at any size the
# package ships, which is why the limit can sit at the cap. Verified by eye too:
# flattening every whisker in the alef, the bookshelf and the dependent-library
# icons leaves all three pixel-identical at 500 px. Lower it with --max-spike to
# be more conservative on new artwork.
MAX_SPIKE = SPIKE_SEGMENT

# --- how far each pass may move the icon -----------------------------------

# The crossings pass must be exact. It only rewrites a contour as the region its
# own fill rule already paints, so any movement at all means a bug.
LIMIT_CROSSINGS = 1e-6
LIMIT_NEEDLES = NEEDLE_DISTANCE
LIMIT_SPIKES = MAX_SPIKE
# Specks are judged by the area removed, not by boundary movement: a speck sitting
# a unit away from the body is a whole unit from the remaining outline, so a
# displacement metric would report its distance rather than its size. Deleting it
# removes exactly its own area, and that is what is bounded.
LIMIT_SPECK_AREA = SPECK_AREA
# Slivers are judged the same way and for the same reason: the vertex is allowed
# to move a quarter of a unit because the hairline it sits on has no width, so
# what leaves the icon is area, and there is almost none of it. A generous
# fraction of a speck still bounds it far below anything visible.
LIMIT_SLIVER_AREA = 0.004


def path_fill_rule(tag):
    m = FR_RE.search(tag)
    return m.group(1) if m else "nonzero"


def contour_of(start, segments):
    """One parsed contour as a pathops.Path."""
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo(start)
    for segment in segments:
        kind, controls, end = segment[0], segment[1], segment[2]
        if kind == "L":
            pen.lineTo(end)
        elif kind == "C":
            pen.curveTo(controls[0], controls[1], end)
        else:
            pen.qCurveTo(controls[0], end)
    pen.closePath()
    return path


def contour_area(start, segments):
    return abs(contour_of(start, segments).area)


def contour_size(start, segments):
    xs = [start[0]] + [s[2][0] for s in segments]
    ys = [start[1]] + [s[2][1] for s in segments]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def parsed_contours(d):
    out = []
    for start, segments in parse_segments(d):
        start, segments = clean_contour(start, segments, WORK_PRECISION)
        if segments:
            out.append((start, segments))
    return out


def emit_contours(contours):
    return "\n       ".join(emit_contour(s, sg, WORK_PRECISION)
                            for s, sg in contours)


# --------------------------------------------------------------------------
# the passes: each returns (new_contours, [descriptions])
# --------------------------------------------------------------------------

def self_crossing(start, segments, fill_rule):
    """True when the contour's outline crosses itself."""
    raw = contour_of(start, segments)
    area = abs(raw.area)
    resolved = pathops.Path()
    try:
        raw.fillType = (pathops.FillType.EVEN_ODD if fill_rule == "evenodd"
                        else pathops.FillType.WINDING)
        pathops.union([raw], resolved.getPen())
    except pathops.PathOpsError:
        return True, None
    if area > 1e-9 and abs(area - abs(resolved.area)) / area > 0.01:
        return True, resolved
    return False, None


def pass_crossings(contours, fill_rule):
    """Resolve a path whose outline crosses itself.

    This resolves the path as a whole, not contour by contour, and that is not a
    detail. Under nonzero winding the contours of one path are read together: a
    contour wound against its neighbour is a hole in it. Resolving a single
    contour on its own normalises its winding and destroys that relationship, so
    a hole in the artwork silently fills in. Resolving the whole path preserves
    exactly the region the path already paints - which is also precisely what
    the font pipeline computes from it - so the icon cannot move at all."""
    crossing = [self_crossing(start, segments, fill_rule)[0]
                for start, segments in contours]
    if not any(crossing):
        return contours, []

    whole = pathops.Path()
    pen = whole.getPen()
    for start, segments in contours:
        contour_of(start, segments).draw(pen)
    whole.fillType = (pathops.FillType.EVEN_ODD if fill_rule == "evenodd"
                      else pathops.FillType.WINDING)
    try:
        resolved = pathops.simplify(whole)
    except pathops.PathOpsError:
        return contours, ["outline too tangled to resolve; left as it was"]

    svg_pen = SVGPathPen(None)
    resolved.draw(svg_pen)
    replacement = parsed_contours(svg_pen.getCommands())
    if not replacement:
        return contours, ["resolving the outline emptied it; left as it was"]
    return replacement, [
        "resolved %d self-crossing contour(s): %d contour(s) in, %d clean out"
        % (sum(crossing), len(contours), len(replacement))]


def pass_specks(contours, fill_rule):
    out, notes = [], []
    for start, segments in contours:
        area = contour_area(start, segments)
        if area < SPECK_AREA and contour_size(start, segments) < SPECK_SIZE:
            notes.append("dropped a speck of %.6f sq units at (%.2f, %.2f)"
                         % (area, start[0], start[1]))
            continue
        out.append((start, segments))
    return out, notes


MIN_CONTOUR_SEGMENTS = 3


def pass_needles(contours, fill_rule):
    out, notes = [], []
    for start, segments in contours:
        # A contour needs three segments to enclose anything, so stop merging
        # once removing another would collapse the shape itself rather than a
        # duplicate point in it.
        removable = len(segments) - MIN_CONTOUR_SEGMENTS
        kept, cur = [], start
        for segment in segments:
            end = segment[2]
            if removable > 0 and \
                    math.hypot(end[0] - cur[0], end[1] - cur[1]) < NEEDLE_DISTANCE:
                notes.append("merged a duplicate point at (%.3f, %.3f)"
                             % (end[0], end[1]))
                removable -= 1
                continue
            kept.append(segment)
            cur = end
        out.append((start, kept if kept else segments))
    return out, notes


def spike_protrusion(a, b, c):
    """How far vertex b sticks out from the straight line a->c."""
    dx, dy = c[0] - a[0], c[1] - a[1]
    span = math.hypot(dx, dy)
    if span < 1e-12:
        return max(math.hypot(b[0] - a[0], b[1] - a[1]),
                   math.hypot(c[0] - b[0], c[1] - b[1]))
    return abs(dy * (b[0] - a[0]) - dx * (b[1] - a[1])) / span


def pass_slivers(contours, fill_rule):
    """Remove a vertex where the outline doubles back on itself.

    A turn this sharp is not a whisker with width, it is a hairline: the outline
    runs out and comes straight back along its own path, enclosing no area. It
    paints nothing at any size, so it is judged by the area it removes rather
    than by how far the vertex moves - the vertex can sit a fifth of a unit out
    while the ink it adds is zero, and a displacement limit would refuse to
    remove exactly the defects that are most clearly debris."""
    return _remove_vertices(contours, max_turn=SLIVER_ANGLE,
                            max_height=SLIVER_LENGTH, label="sliver")


def _remove_vertices(contours, max_turn, max_height, label, min_turn=0.0):
    """Drop vertices that turn sharply between two short segments.

    `max_turn` is the widest interior angle still considered a defect and
    `min_turn` the narrowest, so the sliver pass (0 to 15 degrees, doubling
    back) and the whisker pass (15 to 65 degrees, a zigzag) can share this
    without overlapping."""
    out, notes = [], []
    for start, segments in contours:
        points = [start] + [s[2] for s in segments]
        n = len(segments)
        if n < 4:
            out.append((start, segments))
            continue
        drop = set()
        for i in range(n):
            # Segment i runs points[i] -> points[i+1], so it ends at the vertex
            # it shares with segment i+1.
            a, b, c = points[i], points[(i + 1) % n], points[(i + 2) % n]
            ab = math.hypot(b[0] - a[0], b[1] - a[1])
            bc = math.hypot(c[0] - b[0], c[1] - b[1])
            if ab == 0 or bc == 0 or ab > SPIKE_SEGMENT or bc > SPIKE_SEGMENT:
                continue
            cos = ((a[0] - b[0]) * (c[0] - b[0]) +
                   (a[1] - b[1]) * (c[1] - b[1])) / (ab * bc)
            angle = math.degrees(math.acos(max(-1.0, min(1.0, cos))))
            if not (min_turn <= angle < max_turn):
                continue
            height = spike_protrusion(a, b, c)
            if height > max_height:
                continue
            # Never flatten two adjacent vertices in one go; once one moves, its
            # neighbour's measurement no longer describes the outline.
            if i in drop or (i - 1) % n in drop:
                continue
            drop.add(i)
            notes.append("removed a %.0f degree %s of %.4f units at "
                         "(%.3f, %.3f)" % (angle, label, height, b[0], b[1]))
        if not drop:
            out.append((start, segments))
            continue
        kept, skip_next = [], False
        for i, segment in enumerate(segments):
            if skip_next:
                skip_next = False
                continue
            if i in drop and i + 1 < len(segments):
                # Replace this segment and the next with one straight join.
                kept.append(("L", [], segments[i + 1][2]))
                skip_next = True
                continue
            kept.append(segment)
        out.append((start, kept))
    return out, notes


def pass_spikes(contours, fill_rule, max_spike=MAX_SPIKE):
    return _remove_vertices(contours, max_turn=SPIKE_ANGLE,
                            max_height=max_spike, label="whisker",
                            min_turn=SLIVER_ANGLE)


PASSES = collections.OrderedDict([
    ("crossings", (pass_crossings, LIMIT_CROSSINGS, "shift")),
    ("specks", (pass_specks, LIMIT_SPECK_AREA, "area")),
    ("needles", (pass_needles, LIMIT_NEEDLES, "shift")),
    ("slivers", (pass_slivers, LIMIT_SLIVER_AREA, "area")),
    ("spikes", (pass_spikes, LIMIT_SPIKES, "shift")),
])


# --------------------------------------------------------------------------
# applying a pass to a file, with verification
# --------------------------------------------------------------------------

def rewrite_path_data(text, transform):
    """Apply `transform(d, fill_rule) -> (new_d, notes)` to every <path>."""
    notes = []
    out, last = [], 0
    for m in PATH_RE.finditer(text):
        tag = m.group(1)
        fill_rule = path_fill_rule(tag)
        dm = D_RE.search(tag)
        if not dm:
            continue
        new_d, tag_notes = transform(dm.group(2), fill_rule)
        notes.extend(tag_notes)
        if new_d is None:
            continue
        new_tag = tag[:dm.start(2)] + new_d + tag[dm.end(2):]
        out.append(text[last:m.start(1)])
        out.append(new_tag)
        last = m.end(1)
    out.append(text[last:])
    return "".join(out), notes


def measure(before, after, metric):
    if metric == "area":
        return symmetric_difference_area(before, after)
    return max_boundary_shift(before, after)


def apply_pass(text, icon, name, max_spike):
    """Run one pass over a file, verifying the result.

    Tries the whole pass first, and falls back to one edit at a time if the
    batch does not fit, so a single bad edit does not discard the good ones."""
    func, limit, metric = PASSES[name]
    kwargs = {}
    if name == "spikes":
        # --max-spike is how tall a whisker may be to be removed at all, so it
        # has to raise the acceptance limit with it. Leaving the limit fixed
        # would let the flag find larger whiskers and then always refuse them.
        kwargs["max_spike"] = max_spike
        limit = max_spike

    def transform(d, fill_rule):
        contours = parsed_contours(d)
        new_contours, notes = func(contours, fill_rule, **kwargs)
        if not new_contours:
            # Never empty a path; that would delete artwork rather than debris.
            return emit_contours(contours), []
        return emit_contours(new_contours), notes

    baseline = resolve_region(text, icon)
    candidate, notes = rewrite_path_data(text, transform)
    if not notes:
        return text, [], 0.0, 0

    # Boundary movement does not accumulate across independent local edits, so
    # the batch limit is the per-edit limit. Removed area does accumulate, so
    # there the budget scales with the number of edits.
    budget = limit * len(notes) if metric == "area" else limit
    delta = measure(baseline, resolve_region(candidate, icon), metric)
    if delta <= budget:
        return candidate, notes, delta, 0

    # The batch moved the icon too far. Redo it one edit at a time.
    kept_notes, worst, skipped = [], 0.0, 0
    current = text
    for index in range(len(notes)):
        counter = {"n": 0}

        def single(d, fill_rule, index=index, counter=counter):
            contours = parsed_contours(d)
            new_contours, produced = func(contours, fill_rule, **kwargs)
            if not produced:
                return emit_contours(contours), []
            start = counter["n"]
            counter["n"] += len(produced)
            if not (start <= index < counter["n"]):
                return emit_contours(contours), []
            return emit_contours(new_contours), [produced[index - start]]

        trial, produced = rewrite_path_data(current, single)
        if not produced:
            continue
        delta = measure(resolve_region(current, icon),
                        resolve_region(trial, icon), metric)
        if delta <= limit:
            current = trial
            kept_notes.extend(produced)
            worst = max(worst, delta)
        else:
            skipped += 1
    return current, kept_notes, worst, skipped


def main(argv):
    check = "--check" in argv
    max_spike = MAX_SPIKE
    names = list(PASSES)
    if "--lossless" in argv:
        names = ["crossings"]
    if "--only" in argv:
        i = argv.index("--only")
        names = [argv[i + 1]]
        del argv[i:i + 2]
    if "--max-spike" in argv:
        i = argv.index("--max-spike")
        max_spike = float(argv[i + 1])
        del argv[i:i + 2]
    for name in names:
        if name not in PASSES:
            sys.exit("Unknown pass %r. Available: %s"
                     % (name, ", ".join(PASSES)))

    files = [a for a in argv if not a.startswith("--")] or \
        sorted(glob.glob(os.path.join(SVG_DIR, "*.svg")))

    totals = collections.Counter()
    skipped_total = collections.Counter()
    worst = collections.defaultdict(float)
    touched = set()

    for path in files:
        icon = os.path.basename(path)[:-4]
        with open(path, encoding="utf-8") as fh:
            original = fh.read()
        text = original
        file_notes = []
        # The passes feed each other: merging a duplicate point leaves a vertex
        # that is now a whisker, and flattening a whisker can leave two points
        # on top of each other. One sweep therefore stops short of clean, so
        # sweep until nothing changes. The cap only guards against a pair of
        # passes undoing each other; in practice this settles in two or three.
        counted, moved, left = collections.Counter(), {}, collections.Counter()
        for sweep in range(MAX_SWEEPS):
            before = text
            for name in names:
                text, notes, delta, skipped = apply_pass(text, icon, name,
                                                         max_spike)
                if notes:
                    counted[name] += len(notes)
                    moved[name] = max(moved.get(name, 0.0), delta)
                    file_notes.extend("[%s] %s" % (name, n) for n in notes)
                # Only the first sweep's leftovers are genuinely left alone;
                # later sweeps re-examine the same geometry.
                if sweep == 0:
                    left[name] += skipped
            if text == before:
                break

        for name, count in left.items():
            skipped_total[name] += count
        if text == original:
            # A pass can report an edit that turns out to make no difference to
            # the file - flattening a vertex that was already collinear, say.
            # Counting those would overstate what was actually repaired.
            continue
        for name, count in counted.items():
            totals[name] += count
            worst[name] = max(worst[name], moved[name])
        touched.add(icon)
        print("%s" % icon)
        for note in file_notes[:4]:
            print("   %s" % note)
        if len(file_notes) > 4:
            print("   ... and %d more" % (len(file_notes) - 4))
        if not check:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)

    print("\n%s %d icon(s):" % ("Would repair" if check else "Repaired",
                                len(touched)))
    for name in names:
        if not totals[name] and not skipped_total[name]:
            continue
        unit = "sq units of area" if PASSES[name][2] == "area" else "units"
        print("   %-10s %4d fixed, worst %.6f %s (limit %.6f)%s"
              % (name, totals[name], worst[name], unit, PASSES[name][1],
                 ", %d left alone" % skipped_total[name]
                 if skipped_total[name] else ""))
    if not check and touched:
        print("\nRun tool/format_svg.py to restore the canonical written form.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
