# Architecture

## Sources of truth

The system has three separate concerns:

- `assets_src/svg/`: vector geometry;
- `icon_manifest.yaml`: stable icon identity, API metadata, codepoint,
  provenance, licensing, and upstream state;
- `tool/config.yaml`: package and generator paths, names, canvas, and starting
  codepoint.

Generated files are outputs, never sources.

## Manifest guarantees

`schema_version` protects against silently interpreting an incompatible format.
Each icon has an immutable opaque `id`, stable public `name`, stable codepoint,
source path, size/variant, directionality/deprecation state, upstream tracking,
and licensing provenance.

Codepoints live in Unicode's Private Use Area (`0xE000–0xF8FF`). The current
generator API requires contiguous allocation, so deletion and reuse are
forbidden. Aliases must preserve the original glyph and constant.

## Font generation

`tool/generate.dart` calls `svgToOtf` programmatically. It constructs an ordered
map from manifest codepoint order and verifies the returned glyph metadata
against every manifest record. The OTF timestamp is fixed so identical inputs
produce byte-identical output.

`icon_font_generator` is pinned exactly to 4.1.0 because ordering, naming, and
font bytes are build-system behavior. Upgrading it requires repeating the
generator and codepoint proof of concept.

As its final step, `generate.dart` runs `tool/repair_glyphs.py`, which rewrites
each non-knockout glyph outline directly from its source SVG (24×24 mapped onto
the em, y-flipped, no re-fitting). The pinned generator's outline converter
distorts a few complex glyphs — a horizontal shift on
`book_open_large_search_24_filled`, contour damage on `stander` and
`search_in_the_text` — even from clean, correctly wound sources; this step makes
the font geometry byte-for-byte what the sources and `docs/icon_catalog.svg`
show. Interior-knockout icons are rebuilt as a boolean difference (body minus
the cut) so the cut stays transparent regardless of source winding. It is
deterministic, preserves the fixed head timestamp and all generator metadata,
and therefore requires Python 3 with `skia-pathops` and `fonttools`.

## Public API

`lib/otzaria_icons.dart` exports only generated icon constants. Gallery catalogs
and all-icon maps stay outside production library code to preserve tree-shaking.
Handwritten future helpers belong outside `lib/src/generated/`.

Each constant is compile-time `IconData` containing codepoint, font family, and
font package. The package intentionally has no runtime dependency on Fluent UI
System Icons.

## Determinism

`dart run tool/generate.dart --check` repeats the pipeline in an isolated
temporary copy and compares validated SVG sources plus every generated artifact.
CI uses this read-only mode. A clean check proves contributors committed the
output corresponding to current SVG, manifest, config, and generator code.
