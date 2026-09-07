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

Idempotent: running it on already-formatted sources reports 137 unchanged.

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

Reports the debris that patching leaves behind - specks, spikes, needles,
self-crossing contours - and the features too thin to survive at 16 px. Fixing
any of these moves pixels, so nothing is changed automatically.

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
