# Changelog

## 0.2.1 - 2026-07-19

- Removed the 10 legacy icon names from the former personal repository; their
  artwork now exists under the renamed official icon set.
- Reallocated the official icon manifest from `U+E000` without deprecated
  aliases or backward-compatibility entries.
- Added a generated, searchable Hebrew icon catalog for GitHub Pages with an
  adjustable preview size.

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
