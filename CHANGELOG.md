# Changelog

## Unreleased

- Fixed glyph corruption affecting 34 icons whose independent `<path>` layers
  overlapped or seamed: correct in the browser and catalog, but merged into one
  nonzero-fill glyph the font rendered unintended white holes, hairline seams,
  and (worst case, `book_open_large_search_24_filled`) a shredded quadrant.
- Added `tool/normalize_svg_overlaps.py`, which `simplify`s and boolean-unions
  each icon's paths into one clean, non-overlapping, consistently-wound outline
  identical to the catalog, and normalized all 107 affected/at-risk sources.
- Preserved the three intended interior knockouts (`document_word_24_filled`,
  `document_bullet_list_24_filled`, `book_open_alef_24_filled`), which the tool
  detects and skips.
- Added a CI check (`normalize_svg_overlaps.py --check`) that fails when a
  committed source still contains overlapping or seaming paths.
- Added `tool/repair_glyphs.py`, run as the final generation step, which
  rewrites every glyph outline directly from its source SVG. The pinned
  `icon_font_generator` distorts some complex glyphs during outline conversion
  (a ~4-unit horizontal shift on `book_open_large_search_24_filled`, contour
  damage on `stander_24_filled` and `search_in_the_text_24_regular`) even from
  clean sources; this makes every glyph match the catalog exactly. Interior
  knockouts (`document_word`, `document_bullet_list`, `book_open_alef`) are
  rebuilt as a boolean difference (body minus the cut) so the cut is transparent
  regardless of source winding — this fixed the alef in `book_open_alef_24_filled`,
  which had rendered solid black. Deterministic; preserves the fixed font
  timestamp and all generator metadata. Generation now requires Python 3 with
  pinned `skia-pathops` and `fonttools` (`tool/requirements.txt`).

## 0.2.1 - 2026-07-19

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
