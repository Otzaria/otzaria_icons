# Source structure

This document describes the shape every file in `assets_src/svg/` is kept in,
why it is that shape, and the tools that maintain it.

It is about how the artwork is *written*, not about how it looks. The rules here
never change what an icon draws.

## The problem this solves

The sources were produced by several different editors over the life of the
project and then patched by hand many times. They rendered correctly, but they
had become very hard to work on:

- every file was a single unbroken line of text;
- coordinates carried up to sixteen decimals of float noise, so a corner that
  was meant to be at `22` was written `21.999998`;
- absolute and relative commands, arcs and smooth-curve shorthands were mixed
  arbitrarily between files;
- repeated edits had left zero-length segments and duplicated points behind;
- and the pieces icons share had drifted apart. The same book cover existed in
  six different spellings of the same shape, the same document body in nine, so
  changing a shared part meant finding and editing every copy by hand.

## The canonical form

Every source is written like this:

```svg
<svg xmlns="http://www.w3.org/2000/svg"
     width="24"
     height="24"
     viewBox="0 0 24 24">
  <path d="M20 4.5 V19.5 C20 20.88 18.88 22 17.5 22 H4.251 C3.833 22 3.5 21.667 3.5 21.251 Z
       M18.5 18 V4.5 C18.5 3.948 18.052 3.5 17.5 3.5 H6 C5.448 3.5 5 3.948 5 4.5 V18 Z"/>
</svg>
```

The rules:

- **Absolute commands only.** No relative commands, no `S`/`T` shorthand, no
  arcs. An OpenType glyph has no arc operator, so the font already sees arcs as
  cubics; resolving them in the source removes a difference that was never real.
- **One contour per line.** A contour is a closed loop, so a line of path data is
  a shape you can find, read, and edit without untangling anything around it.
  This is also what lets shared parts be compared and swapped line by line.
- **`H` and `V` for axis-aligned lines.** Most of this artwork is rectilinear,
  and `V19.5` says "straight down" in a way `L20 19.5` does not.
- **Fixed decimal precision per file**, chosen automatically - see below.
- **No degenerate geometry**: no zero-length segments, no points repeated on top
  of each other, no curves that are actually straight.

Everything already required by [svg_requirements.md](svg_requirements.md) still
applies: a `0 0 24 24` canvas, filled outlines only, no strokes, groups,
transforms, or primitive shapes.

### Precision is chosen per file

Three decimals is what a person can read, and it is enough for icons drawn on a
24-unit canvas with half-unit geometry - which is most of them. But a few
sources were traced from font glyphs and carry real detail below a thousandth of
a unit; rounding those to three decimals visibly moves their outline.

So each file gets the coarsest precision that provably does not move it,
starting at three and escalating only when it has to. In practice:

| Decimals | Files |
| --- | --- |
| 3 | 131 |
| 4 | 2 |
| 5 | 3 |
| 6 | 1 |

A file that needs five or six decimals is telling you something: its outline
carries detail far finer than anything that can be seen, which is a symptom of
tracing rather than drawing. Those are the same files
[the geometry audit](#auditing-for-defects) has the most to say about.

## Layered sources

An icon may be written as several `<path>` elements. This is often much clearer
than one merged outline - the book and the alef on top of it are two ideas, and
two paths say so.

The font merges every path into one glyph, so how the paths combine matters:

- **Overlapping black layers** are unioned. Mark the file
  `data-preserve-overlap="true"` on the root `<svg>`, which tells
  `normalize_svg_overlaps.py` the overlap is deliberate and must not be
  flattened.
- **Interior knockouts** - a shape cut out of a solid body - are marked
  `fill="white"` on the path being cut out. `repair_glyphs.py` subtracts them
  with a boolean difference, so the cut is transparent regardless of winding.
- **Disjoint pieces** need no marking at all.

## The tools

All of them live in `tool/` and need `skia-pathops` and `fonttools`
(`pip install -r tool/requirements.txt`).

### Keeping the canonical form

```console
python3 tool/format_svg.py            # rewrite every source canonically
python3 tool/format_svg.py --check    # report, change nothing
```

Idempotent: running it on already-formatted sources reports every one of them
unchanged.

### Unifying shared parts

```console
python3 tool/unify_shared_parts.py            # give shared parts one spelling
python3 tool/unify_shared_parts.py --check    # report, change nothing
```

Where two icons contain the same shape written differently, this gives them one
spelling, so a future edit to a shared part is one search-and-replace instead of
nineteen judgement calls. It only ever touches contours that are *already* the
same shape, so it redraws nothing.

### Seeing what the families share

```console
python3 tool/family_report.py --unifiable   # same shape, different spelling
python3 tool/family_report.py --drift       # genuinely different shapes
```

`--drift` is the interesting half: it lists parts of the design that appear in
several icons and do **not** match, which is a question about the artwork rather
than about the code. Nothing is changed automatically.

### Auditing for defects

```console
python3 tool/audit_geometry.py
python3 tool/audit_geometry.py --kind self-crossing
```

Reports the debris that patching leaves behind - specks, spikes, slivers,
needles, self-crossing contours - and the features too thin to survive at 16 px.
It only judges; nothing is changed.

### Removing the debris

```console
python3 tool/repair_artifacts.py --check      # report, change nothing
python3 tool/repair_artifacts.py             # all passes
python3 tool/repair_artifacts.py --lossless  # only the crossings pass
python3 tool/repair_artifacts.py --only slivers
```

Acts on what the audit finds. Each category is a separate pass with its own
justification and its own limit on how far the icon may move:

| Pass | What it removes | Limit |
| --- | --- | --- |
| `crossings` | a contour that crosses itself, replaced by the outline its own winding rule already resolves to | exact - nothing moves |
| `specks` | separate contours far too small to be design | 0.01 sq units of area each |
| `needles` | consecutive points sitting on top of each other | 0.01 units |
| `slivers` | a vertex where the outline doubles back on itself - a hairline enclosing no area | 0.004 sq units of area |
| `spikes` | a whisker jutting off an otherwise smooth outline | 0.05 units |

Two of the passes are bounded by **area removed** rather than by how far the
outline moves, and that distinction matters. A speck sitting a unit away from
the body is a whole unit from the remaining outline, and a sliver's vertex can
stick out a quarter of a unit while the ink it adds is zero. A displacement
limit would refuse to remove exactly the defects that are most obviously debris,
so those two are judged by how much ink actually leaves the icon.

The passes feed each other - merging a duplicate point leaves a vertex that is
now a whisker - so they sweep until nothing changes. Run `tool/format_svg.py`
afterwards to restore the canonical written form, then `tool/unify_shared_parts.py`.

The audit's **thin ink** and **thin gap** findings are deliberately *not*
repaired. Those are not debris, they are how the icon was drawn, and widening a
stroke or opening a gap is a redraw. They stay in the report for a person to
decide on.

## Changing a letterform's weight

```console
python3 tool/restroke_alef.py --check    # report, change nothing
python3 tool/restroke_alef.py            # reweight the family
```

Unlike everything else here this tool *is* meant to change the artwork: it sets
the alef lighter and shortens its upper-right leg. It is documented because the
method generalises to any letterform in this set, and because four of its rules
were each arrived at by getting the result visibly wrong first.

**The outline is moved, never rebuilt.** Each node and handle travels along its
own inward normal, so segment count, curve degrees and tangent continuity all
survive. Rebuilding from a skeleton or re-fitting curves to an offset polyline
replaces the designer's curves with the tool's, which is how a redraw picks up
flat spots and lumps.

**Use one factor for every stroke.** The temptation is to grade it - thin the
heavy end of a stroke more than its fine end. Do not. The only available measure
of local width is the inscribed circle, and along a tapering stroke that measure
is not monotone: wherever the outline turns concave the circle collapses, so it
reads 0.36, 0.87, 0.39, 0.82, 1.58, 0.47 down one leg of this alef. A factor
keyed to it jumps, the displacement jumps with it, and a displacement that
varies sharply along an edge *tilts* the edge rather than thinning it - smooth
concave sweeps come out as straight chords with a corner at each end. Grading
also flattens the letter's width contrast, which reads as a different design
rather than a lighter one.

**Hold the joins.** Taking a flat percentage off everything takes it off the
joins too, and the joins are the thinnest ink in a letter - thinning them makes
a join read as a gap. Every point's inward move is capped so the ink nowhere
falls below the letter's own original minimum. Note the cap must be keyed to
*clearance* - the distance straight across the ink - and not to the inscribed
circle: beside a join the circle sits on the thick stroke, is large, and never
notices that the join is narrowing from the other side.

**Finish the outline, do not merely move it.** A digitised source carries a few
degrees of kink at every join that was drawn smooth, and that scatter is what
reads as wobble when an icon is enlarged. The finishing pass makes joins drawn
smooth exactly smooth, eases node tremor within a bounded distance, and leaves
every drawn corner at its drawn angle. Elevate quadratics to cubics before doing
any of this: a quadratic's single control point governs the tangent at both ends
of its segment, so correcting one end undoes the other and the curve stays
faceted no matter how many passes are run.

Every threshold has its measured justification in the constants at the top of
the file.

## Composing an icon out of the artwork already here

```console
python3 tool/compose_sources.py --list     # what is composed
python3 tool/compose_sources.py            # rebuild all of it
python3 tool/compose_sources.py <name>     # rebuild one
python3 tool/format_svg.py                 # then canonicalise the output
```

Most icons in this set are not drawn from nothing. They are an existing
letterform, page or chain with a badge added, a letter swapped, or a weight
changed. Copying a path into a new file by hand is what makes a family drift —
the alef badge disc already exists in two slightly different spellings from
exactly that, one of them 0.2 units off the other. So an icon of that kind is
written as a **recipe against the committed sources**: the disc in a new badge
icon is not a copy of the disc, it *is* the disc, read out of
`alef_copy_24_regular.svg` at build time. When the alef is redrawn again — it
has been twice — every composed icon that carries one picks the new letter up on
the next run.

`tool/icon_compose.py` is the toolkit the recipes are written in, and
`tool/compose_sources.py` holds the recipes. Three things in it are worth
knowing before writing another one.

**Everything works on the resolved region.** An icon's ink is the union of its
solid paths *minus* its `fill="white"` knockouts, which is what
`repair_glyphs.py` builds the glyph from. Reading raw `<path>` elements instead
treats a knockout as ink, and every filled letter icon comes back as a blob.
`glyph(name)` resolves it; `silhouette(name)` fills the knockouts back in.

**`grow` and `shrink` are real outline offsets**, built by stroking the region's
own boundary and unioning or subtracting the band. That is what lets a filled
variant be *derived* from a regular one rather than redrawn beside it:
`book_open_medium_24_filled` is the regular icon's silhouette with a black ring
taken out of its edge, a white band behind that, and the regular icon's own
black lines knocked out of what is left — so the pair cannot drift apart or
differ in optical size.

**But the offset is not always trustworthy, and it does not announce it.** Skia's
stroker returns wrong answers on hand-drawn outlines full of near-degenerate
detail. Eroding the `otzaria_icon` cover — 351 square units — by 0.50 returns
36; by 0.80 it returns 294; by 1.00 it fails outright. Three defences, in order
of preference:

- **Don't offset what you don't have to.** The filled `otzaria_icon` variants
  take the white band's inner edge from the boundary the designer already drew,
  and construct only the outer line, from a scaled copy of the cover. Exact
  arithmetic cannot go wrong quietly.
- **`deburr()` before offsetting.** An opening of 0.03 units — a thirtieth of a
  pixel at 24 px — clears the doubled points and almost-touching edges that the
  offset would otherwise amplify. It took the open books from 114 fragments to
  one. Use `despeckle()` for whatever survives.
- **Fail loudly.** `shrink` raises rather than returning an empty region when a
  small erosion consumes everything, and `write()` refuses a source with under
  one square unit of ink. Both exist because a silent collapse shipped a blank
  glyph once.

Three more operations exist for the same reason — they do one thing to a whole
region, and the recipes state *what* rather than *how*. `fill_holes(max_area)`
closes an enclosed hole too small to print; `despeckle(min_area)` drops ink too
small to be design, by **subtracting** the small contours rather than rebuilding
the region from the large ones — a speck sits inside the area a large contour
encloses, so a rebuild puts it straight back; and `filled()` / `holes()` separate
a region from what it encloses. `contours()` simplifies each contour on its own,
which is what makes those last two work: a contour that was a hole in the
original is still wound the other way, and unioning it cancels instead of
covering.

`round_corners(outer, inner)` eases a shape: an *opening* rounds the convex
corners and can never spread the region, so it is safe at any radius the strokes
can afford; a *closing* rounds the concave ones but bridges anything narrower
than twice its radius, so `inner` must stay under half the smallest gap in the
artwork. Both are idempotent in principle — which is why the letter recipes can
be re-run — though in practice they are re-run on their own offset output, and
skia refuses that, so they check first whether there is anything left to ease.

**A recipe whose input is its own output is not idempotent.** Widening the Rashi
alef reads `alef_rashi_24_regular` and writes it back, so a second run widens it
twice. That one carries an explicit guard that refuses to run on a letter that
is already wide; any future in-place recipe needs the same, because
`compose_sources.py` with no arguments rebuilds everything.

New sources are written with plain absolute path data and are expected to be run
through `format_svg.py` afterwards, which canonicalises them and — because it
checks every rewrite against `region_diff.py` — also proves the canonical form
did not move what the composer produced.

### Marks taken from Fluent

Some of these icons put a small Fluent mark on Otzaria artwork — a highlighter,
an eraser, a pair of scissors. Drawing those by hand does not work: they come
out as *a* highlighter rather than *the* highlighter, and beside the rest of a
Fluent toolbar they read as a different hand. The only way to match the line is
to use the line.

Fluent ships no SVG in its Dart package, but a glyph outline is the same
artwork. `tool/fluent_art.py` reads a glyph out of `FluentSystemIcons-*.ttf` in
the pub cache and maps it back onto the 24×24 canvas. Three things it settles:

- **Take the mark from the *filled* font.** Fluent's regular style is an
  outline drawn with 1.5-unit strokes for a 24-unit canvas. Reduced to a badge a
  fifth that size those strokes land near 0.3 units — a third of a pixel at
  24 px — and the mark comes out as a ring too fine to print.
- **Put the weight back after scaling.** `weighted()` fits the mark by *reach*
  (how far its ink gets from the centre, which is the right measure for a round
  badge) and then offsets it outward until its mean stroke is back above
  `BADGE_MIN_STROKE`. Fluent solves the same problem by redrawing the mark at
  badge scale — `link_person`'s person is a plain solid head and body, not the
  person icon shrunk — this keeps the drawing and restores the ink.
- **Record it.** Anything built on Fluent is `modified_fluent` in the manifest
  and must carry `based_on` and `upstream_commit`; `THIRD_PARTY_NOTICES.md` is
  generated from those fields. `compose_sources.py --provenance` writes them
  from what the recipes actually fetched, so the record cannot drift from the
  artwork. It writes no source, so it is safe to run after `format_svg.py`.

Fluent also badges its own `link`, with exactly the concept this set uses — a
solid disc at the bottom right, the mark knocked out of it, the base cut back to
clear it. `link_dismiss_24_regular` is taken apart and reassembled rather than
imitated, so the `link_*` family here carries Fluent's own cut-back and Fluent's
own circle in Fluent's own place.

## Proving that nothing changed

Restructuring artwork is only safe if "nothing changed" can be demonstrated
rather than hoped for. Two independent tools do that, and both are used on every
change to these sources.

### The vector proof

```console
python3 tool/region_diff.py old.svg new.svg
python3 tool/region_diff.py --baseline DIR
```

`repair_glyphs.py` builds each glyph straight from the source geometry, so the
rendered icon depends on exactly one thing: the filled region the source
resolves to. Path count, command types, coordinate precision, ordering, and
layering are all invisible to the output.

`region_diff.py` resolves both versions to that same region and measures how far
the outline moved, in canvas units. This is the primary check, and it is the
stronger one: it compares exact vector regions rather than one sampled
resolution.

`format_svg.py` and `unify_shared_parts.py` both call it on every file they
touch and refuse any rewrite that moves the outline further than 0.002 canvas
units - a twelve-thousandth of the icon, which is 0.002 px at 24 px and still
only 0.04 px blown up to 512 px.

### The pixel proof

```console
python3 tool/raster_diff.py --baseline DIR --sizes 16,20,24,32,48
```

Renders both versions with Inkscape and compares the bitmaps. It reaches the
same answer along a completely separate path - a different renderer, no shared
geometry engine - which is what makes "no graphical change" a claim rather than
a hope. Set `INKSCAPE` if it is not on `PATH`.

Do not treat a non-zero pixel count here as a failure on its own. An edge that
moves by a thousandth of a unit still changes the antialiasing of the pixels it
crosses. Read the magnitude: a handful of pixels changing by a few percent of
one grey level is a subpixel edge shift, while a real change to a shape shows up
as its recognisable outline in the diff.
