#!/usr/bin/env python3
"""Make the parts icons share literally identical, without redrawing anything.

WHY THIS EXISTS
---------------
The same book cover appears in nineteen icons, the same alef in eleven, the same
magnifier in eight. Those pieces were copied from file to file over years of
separate edits, and they no longer match: the book cover exists in six different
spellings of the same shape, the document body in nine.

The shapes are the same - the *text* is not. So changing the book cover means
finding and editing nineteen slightly different versions of it by hand, and
getting one of them subtly wrong is invisible until someone looks closely at one
icon. That is the single biggest reason this artwork is hard to maintain.

This tool gives every shared part one spelling. It only ever touches contours
that are already the same shape within `--tol`, so it redraws nothing: after it
runs, the icons that agreed geometrically now also agree character for
character, and a future edit to a shared part is one search-and-replace instead
of nineteen judgement calls.

Parts that genuinely differ are left completely alone. `tool/family_report.py
--drift` lists those separately, because deciding whether two nearly-identical
book covers *should* become one is a question about the artwork, not about the
code, and unifying them would move pixels.

SAFETY
------
Every file is verified after rewriting: the resolved region is compared against
the region before the run, and any file whose outline moved further than the
tolerance is restored untouched. A canonical spelling is only adopted where it
provably fits.

USAGE
-----
  python3 tool/unify_shared_parts.py            # unify in place
  python3 tool/unify_shared_parts.py --check    # report, change nothing
  python3 tool/unify_shared_parts.py --tol 0.002

Requires: skia-pathops, fonttools.
"""
import sys, os, re, glob, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from family_report import (contour_lines, contour_bbox, bbox_close,
                               shape_distance, canonical_spelling, TOL)
    from region_diff import resolve_region, max_boundary_shift
except ImportError as e:
    sys.exit("Missing dependency: %s. Run: pip install skia-pathops fonttools" % e)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")


def load(files):
    """(icon name, text, [contour lines]) for every source."""
    out = []
    for path in files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        out.append((path, os.path.basename(path)[:-4], text, contour_lines(text)))
    return out


def build_canonical_map(sources, tol):
    """Map every contour spelling to the one spelling its shape should use.

    Clustering works on distinct spellings, not on occurrences, so one spelling
    can never be pulled into two different clusters. Grouping by nearness is
    greedy and therefore not transitive - a chain of contours each within
    tolerance of the next can span more than the tolerance end to end - so every
    mapping is finally checked directly against the canonical it points at, and
    dropped if it does not match. Without that check a contour can be replaced
    by a shape that is genuinely different, which is a redraw, not a rename."""
    users = collections.defaultdict(set)
    for _, icon, _, lines in sources:
        for line in lines:
            users[line].add(icon)
    spellings = {d: contour_bbox(d) for d in users}

    # Compare only contours that occupy the same place on the canvas.
    buckets = collections.defaultdict(list)
    for d, bb in spellings.items():
        buckets[tuple(round(v * 2) / 2 for v in bb)].append(d)

    keys = sorted(buckets)
    mapping, groups, seen = {}, [], set()
    for key in keys:
        if key in seen:
            continue
        pool = []
        for other in keys:
            if other not in seen and bbox_close(key, other):
                pool.extend(buckets[other])
                seen.add(other)
        while pool:
            seed = pool.pop(0)
            cluster, rest = [seed], []
            for d in pool:
                if bbox_close(spellings[seed], spellings[d]) and \
                        shape_distance(seed, d) <= tol:
                    cluster.append(d)
                else:
                    rest.append(d)
            pool = rest

            icons = set().union(*(users[d] for d in cluster))
            if len(icons) < 2 or len(cluster) < 2:
                continue
            canonical = canonical_spelling(
                [(icon, d, spellings[d]) for d in cluster for icon in users[d]])
            adopted = []
            for d in cluster:
                if d == canonical:
                    continue
                if shape_distance(d, canonical) <= tol:
                    mapping[d] = canonical
                    adopted.append(d)
            if adopted:
                groups.append((sorted(icons), len(adopted) + 1))
    return mapping, groups


def replaceable(text, mapping):
    """Line indices whose contour has a canonical spelling to adopt."""
    out = []
    for index, line in enumerate(text.split("\n")):
        stripped = line.strip()
        # A contour line inside a `d` attribute; the first one carries the
        # attribute prefix, so match on the geometry that follows it.
        for candidate in (stripped, stripped.split('d="')[-1]):
            body = candidate.rstrip('"/>').strip()
            if body in mapping and mapping[body] != body:
                out.append((index, body, mapping[body]))
                break
    return out


def apply_one(text, index, body, canonical):
    lines = text.split("\n")
    lines[index] = lines[index].replace(body, canonical)
    return "\n".join(lines)


def unify_file(text, icon, mapping, tol):
    """Adopt every canonical spelling that provably fits, one at a time.

    A contour that matches its canonical within tolerance in isolation can still
    move the icon when swapped in, because these outlines meet each other
    exactly: shifting one contour by a thousandth of a unit can break a seam it
    shared with its neighbour, and the boolean union then resolves the two
    differently. Only the whole resolved icon can settle it, so each replacement
    is verified against the whole icon and kept only if the icon did not move.
    Checking replacements one by one rather than all together means one
    ill-fitting contour costs only itself, instead of discarding every other
    unification in the same file."""
    baseline = resolve_region(text, icon)
    current, kept, skipped, worst = text, 0, 0, 0.0
    for index, body, canonical in replaceable(text, mapping):
        candidate = apply_one(current, index, body, canonical)
        shift = max_boundary_shift(baseline, resolve_region(candidate, icon))
        if shift <= tol:
            current, kept = candidate, kept + 1
            worst = max(worst, shift)
        else:
            skipped += 1
    return current, kept, skipped, worst


def main(argv):
    check = "--check" in argv
    tol = TOL
    if "--tol" in argv:
        i = argv.index("--tol")
        tol = float(argv[i + 1])
        del argv[i:i + 2]

    files = [a for a in argv if not a.startswith("--")] or \
        sorted(glob.glob(os.path.join(SVG_DIR, "*.svg")))

    sources = load(files)
    mapping, groups = build_canonical_map(sources, tol)

    print("%d shared part(s) have more than one spelling, across %d icons."
          % (len(groups), len({i for icons, _ in groups for i in icons})))

    unified_files, total_kept, total_skipped, worst = 0, 0, 0, 0.0
    for path, icon, text, _ in sources:
        if not replaceable(text, mapping):
            continue
        new_text, kept, skipped, shift = unify_file(text, icon, mapping, tol)
        total_kept += kept
        total_skipped += skipped
        worst = max(worst, shift)
        if kept:
            unified_files += 1
            if not check:
                # newline="\n" to match .gitattributes, which pins *.svg to LF.
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(new_text)
        note = "%d contour(s)" % kept
        if skipped:
            note += ", %d left alone (would move the icon)" % skipped
        print("%-9s %-46s %s"
              % ("would fix" if check else "unified", icon, note))

    print("\n%s %d contour(s) across %d file(s); worst outline movement "
          "%.5f units (limit %.5f)."
          % ("Would unify" if check else "Unified", total_kept, unified_files,
             worst, tol))
    if total_skipped:
        print("%d contour(s) kept their own spelling: adopting the shared one "
              "would have moved the icon." % total_skipped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
