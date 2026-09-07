# Changelog

## Unreleased

- **Set the alef letterform lighter** across the 16 icons that carry it (same
  names and codepoints, visual change): every stroke is 15% thinner, the
  upper-right leg is 0.6 units shorter, and the outline has had a finishing
  pass. The letter is the same letter, in a regular weight instead of a bold
  one.

  Three rules do the work, and each replaced something that looked wrong:

  * **One factor for every stroke.** Grading it - thinning a leg's thick end
    more than its thin end - was tried twice and looked wrong both times. The
    only available measure of local stroke width is the inscribed circle, and
    along these legs it is not monotone (0.36, 0.87, 0.39, 0.82, 1.58, 0.47)
    because the outline turns concave. A factor keyed to it jumps, and a
    displacement that jumps along an edge tilts that edge instead of thinning
    it: the concave sweep below the upper-right leg came out as a straight
    chord with a corner at each end. The first attempt also flattened the legs'
    width contrast from 6.6:1 to 2.1:1, which turns a calligraphic hand into a
    nearly monolinear one - a different letter, not a lighter one.

  * **Joins are held, not thinned.** A flat percentage takes ink off the joins
    too, and the joins are the thinnest places in the letter: the lower-left
    join dropped from 0.697 units of ink to 0.550 until it read as a gap. No
    point may now move so far inward that the ink anywhere falls below the
    letter's own original minimum of 0.70 units. The join measures 0.701 in the
    result.

  * **The outline is finished, not just moved.** Joins drawn smooth are made
    exactly smooth, node tremor is eased out within a bounded 0.11 units, and
    every corner the designer drew is kept at its drawn angle. The median kink
    at a node is now 0.00 degrees against 0.74 as digitised, and three quarters
    of all nodes are perfectly smooth, while the sharpest corners are unchanged
    at 101.6 and 112.6 degrees.

  Quadratic segments are elevated to cubics first. A quadratic's single control
  point governs the tangent at both of its ends, so a correction at one end
  undoes the other; that alone had capped smoothing at a 2.45-degree median.

  Two icons keep a hairline artefact where the thinned letter pulled away from
  a shape behind it: `alef_behind_alef_24_regular` (0.012 sq units) and
  `alef_24_regular` (0.003 sq units, emergent from its counter pinching). Both
  are far below one pixel at icon sizes.

  `alef_stam` and `alef_rashi` are different letterforms and were excluded. The
  reduced alef inside `book_alef_24_{regular,filled}` and the alef in
  `text_alef_bet_list_24_regular` are separately drawn letters rather than
  copies of this one - shape distance 0.139 and higher, where every icon above
  matches at 0.000 - so they were left alone and need their own pass.

- Added `tool/restroke_alef.py`, which performs the above and records why each
  rule is there.

- Restructured every source in `assets_src/svg/` into one canonical written
  form, with **no change to what any icon draws**. The files had been produced
  by several different editors and patched by hand over years: each was a single
  unbroken line, coordinates carried up to sixteen decimals of float noise
  (a corner meant to sit at `22` was written `21.999998`), absolute and relative
  commands and arcs and smooth-curve shorthands were mixed arbitrarily, and
  repeated edits had left zero-length segments and duplicated points behind.
  Sources are now absolute-only, one contour per line, `H`/`V` for axis-aligned
  edges, free of degenerate geometry, and rounded to a decimal precision chosen
  per file - the coarsest that provably does not move that file's outline (three
  decimals for 131 of 137 sources). Source size dropped from 819 KB to 575 KB.
  See [docs/source_structure.md](docs/source_structure.md).

- Gave shared artwork one spelling across each family: 94 contours in 36 files.
  The same book cover had existed in six different spellings of the same shape
  and the same document body in nine, so changing a shared part meant finding
  and editing every copy by hand. The book cover is now one identical contour
  across 32 icons. Only contours that were already the same shape were touched,
  so nothing was redrawn.

- The font, catalog, gallery and golden were regenerated from the restructured
  sources. Every icon is graphically unchanged: the resolved outline moves at
  most 0.002 canvas units anywhere (0.002 px at 24 px), verified two independent
  ways - an exact vector-region comparison and an Inkscape pixel comparison at
  16, 20, 24, 32 and 48 px, whose worst case is 9 of 576 pixels differing by at
  most 7% of one grey level, the signature of a subpixel edge shift.

- Removed the geometric debris that years of hand-patching had left in the
  outlines. Across the set: **67 specks** (separate filled contours far too
  small to be design - median 0.00005 square units, slivers that paint
  nothing), **6 self-crossing contours**, **3 hairline slivers** where an
  outline doubled back on itself, **412 duplicated points**, and **140
  whiskers** jutting off otherwise smooth outlines. The self-crossings mattered
  most: they rendered correctly only because their coordinates happened to land
  where they did, so any nearby edit could have flipped a large area black or
  white without warning.

  This is the one change in this release that touches the artwork, and it stays
  far below anything visible: at 16 px only two icons change at all, by at most
  3 pixels of 256 and 4% of one grey level. Removing every whisker from the
  alef, bookshelf and dependent-library icons leaves all three pixel-identical
  at 500 px. What is gone is only visible under heavy magnification, which is
  where it was showing up.

  A side effect confirms the debris was debris: before the cleanup, six sources
  carried "detail" below a thousandth of a unit and needed 4-6 decimals to write
  losslessly. Afterwards 136 of 137 fit in three decimals.

  The audit's `thin ink` and `thin gap` findings were deliberately left alone -
  those are design decisions, not debris, and widening a stroke is a redraw.

- Added the tooling that produced and verifies all of the above:
  `tool/format_svg.py` (canonical form), `tool/unify_shared_parts.py` (one
  spelling per shared part), `tool/family_report.py` (what families share and
  where they have drifted), `tool/audit_geometry.py` (specks, spikes, slivers,
  needles, self-crossing contours, and features too thin to survive at 16 px),
  `tool/repair_artifacts.py` (removes that debris, one bounded pass per defect
  category), `tool/region_diff.py` and `tool/raster_diff.py` (the two
  independent proofs of what a rewrite did and did not change). Every tool
  verifies each edit against the resolved region and keeps it only if the icon
  stayed inside that pass's limit.

- Refined `book_open_tzurat_hadaf_24_{regular,filled}` further (same names
  and codepoints, visual-only): the glyph is ~1.2x larger, and the center
  block is now a portrait rectangle (taller than wide, like an actual page)
  rather than a square, since the top arm has far less vertical room before
  its own tab than the bottom arm does. The horizontal gap grew a little at
  the expense of the page arms' width; the bottom vertical gap shrank in
  favor of a taller bottom arm. The `regular` outline is now one constant
  stroke thickness applied as a true offset everywhere, replacing a
  hand-placed inner boundary that varied between 0.75 and 0.9 per segment.

- Redrawn `book_open_tzurat_hadaf_24_{regular,filled}` (same names and
  codepoints): the center block no longer straddles the two page columns —
  the columns now recess around it with a uniform gap, removing the 3D
  "square resting on cylinders" look reported in Otzaria issue #904.

- Renamed `book_open_alef_24_{filled,regular}` to `book_alef_24_{filled,regular}`
  (same codepoints `U+E068`/`U+E069`; no backward-compatible aliases).
- Added `clock_add_24_regular` and `search_in_the_person_24_regular`.
- Expanded the set to **110 icons** (from 62), adding the `alef_*` family,
  additional book/document/list variants, `calendar`, `person`, `search`,
  clipboard/task-list and RTL text-list icons. Codepoints were appended after
  the existing range (through `U+E06D`); no previously shipped codepoint was
  reassigned.
- Fixed glyph corruption affecting 34 icons whose independent `<path>` layers
  overlapped or seamed: correct in the browser and catalog, but merged into one
  nonzero-fill glyph the font rendered unintended white holes, hairline seams,
  and (worst case, `book_open_large_search_24_filled`) a shredded quadrant.
- Added `tool/normalize_svg_overlaps.py`, which `simplify`s and boolean-unions
  each icon's paths into one clean, non-overlapping, consistently-wound outline
  identical to the catalog, and normalized all 107 affected/at-risk sources.
- Preserved the three intended interior knockouts (`document_word_24_filled`,
  `document_bullet_list_24_filled`, `book_alef_24_filled`), which the tool
  detects and skips.
- Added a CI check (`normalize_svg_overlaps.py --check`) that fails when a
  committed source still contains overlapping or seaming paths.
- Added `tool/repair_glyphs.py`, run as the final generation step, which
  rewrites every glyph outline directly from its source SVG. The pinned
  `icon_font_generator` distorts some complex glyphs during outline conversion
  (a ~4-unit horizontal shift on `book_open_large_search_24_filled`, contour
  damage on `stander_24_filled` and `search_in_the_text_24_regular`) even from
  clean sources; this makes every glyph match the catalog exactly. Interior
  knockouts (`document_word`, `document_bullet_list`, `book_alef`) are
  rebuilt as a boolean difference (body minus the cut) so the cut is transparent
  regardless of source winding — this fixed the alef in `book_alef_24_filled`,
  which had rendered solid black. Deterministic; preserves the fixed font
  timestamp and all generator metadata. Generation now requires Python 3 with
  pinned `skia-pathops` and `fonttools` (`tool/requirements.txt`).

- Hardened the generation pipeline: `generate.dart` now runs the
  `normalize_svg_overlaps.py --check` gate so overlapping/seaming sources can no
  longer be generated, `validate.dart` enforces append-only contiguous
  codepoints from `U+E000`, and the manifest's `deprecated` /
  `match_text_direction` flags now flow into the generated API.
- Removed the 10 legacy icon names from the former personal repository; their
  artwork now exists under the renamed official icon set.
- Reallocated the official icon manifest from `U+E000` without deprecated
  aliases or backward-compatibility entries.
- Added a generated, searchable Hebrew icon catalog for GitHub Pages with an
  adjustable preview size.
- Corrected stroke expansion for 11 restored source icons and preserved
  presentation attributes inherited from the root SVG element.
- Preserved white mask and stroke artwork as transparent knockouts in filled
  monochrome glyphs, including PDF, Word, ZIM, upload, search, and link marks.

## 0.2.0 - 2026-07-19

- Added 52 original Otzaria icons while preserving all 10 previously published
  names and codepoints.
- Moved repository metadata and installation links to the official
  `Otzaria/otzaria_icons` repository.
- Added a vector-safe Inkscape preparation tool for strokes, text, masks,
  shapes, transforms, and non-24 canvases.
- Canonicalized every committed SVG to direct filled 24x24 paths without
  retaining raster data or renderer-dependent SVG features.
- Corrected spelling in new public names before allocation and documented
  common SVG export mistakes and their safe fixes.
- Made the multi-size Windows golden grow automatically with the icon manifest.

## 0.1.3 - 2026-07-17

- Increased the optical size of the restored `book_open_lines`,
  `book_open_lines_search`, and `search_full` designs by 12% around the canvas
  center, preserving their proportions and native 24x24 geometry.
- Replaced the overly dense `book_open_lines_24_filled` geometry with the
  original readable regular outline so it remains recognizable at 16-24 px.
- Added a reusable native-path scaling tool and updated the multi-size visual
  golden.

## 0.1.2 - 2026-07-16

- Restored the original visual designs of `book_open_lines`,
  `book_open_lines_search`, and `search_full` in both variants.
- Flattened their existing transforms mathematically into native 24x24 path
  coordinates without redrawing or simplifying the artwork.
- Consolidated the GPLv3 license into one canonical `LICENSE` file.
- Documented automatic GPL-3.0-only licensing for accepted contributions and
  the required valid SVG structure.
- Strengthened SVG validation and added a reusable transform-flattening tool.

## 0.1.1 - 2026-07-16

- Rebuilt `book_open_lines`, `book_open_lines_search`, and `search_full`
  regular/filled glyphs with native 24×24 geometry for correct 16–24 px
  rendering.
- Replaced the 80 px-only golden with coverage at 16, 20, 24, 32, and 48 px.
- Reject SVG transforms and non-native canvases to prevent small-size glyph
  regressions.
- Added a generated visual icon catalog and links to Otzaria and Microsoft
  Fluent UI System Icons.

## 0.1.0 - 2026-07-16

- Initial package structure and SVG validation pipeline.
- Manifest-driven deterministic OTF and Dart generation.
- Five initial regular/filled icon pairs.
- GPL-3.0-only licensing for the package and original icon artwork.
- Example gallery and minimal tree-shaking proof application.
- Windows, Android, and Web release validation.
- Detailed installation, usage, SVG, contribution, testing, architecture, and
  release documentation.
- Read-only generation drift checks and generated provenance notices.
- GitHub CI plus manual Linux/macOS pre-release validation.
