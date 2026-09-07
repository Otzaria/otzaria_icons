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

## The tools

Everything in `tool/` falls into one of three groups. The Python tools need
`skia-pathops`, `fonttools` and `pyyaml` (`pip install -r tool/requirements.txt`).

**Run by the generator.** These execute as part of
`dart run tool/generate.dart` and need no separate invocation:

| Tool | Role |
| --- | --- |
| `generate.dart` | The pipeline itself: validates, sanitizes, allocates codepoints, builds the OTF, and regenerates the Dart API, catalog, gallery and notices. |
| `validate.dart` | Enforces names, canvas, path rules, manifest integrity and codepoint allocation. Also runs standalone in CI. |
| `sanitize.dart` | Conservative cleanup of a source: flattens a sole wrapper group only where nothing can be lost. |
| `normalize_canvas.dart` | Guard that rejects any source not already on a native 24x24 canvas. |
| `normalize_svg_overlaps.py` | Resolves overlapping or seaming paths into one clean outline. `--check` is the CI gate. |
| `repair_glyphs.py` | Rewrites every glyph outline in the finished OTF directly from its source, and cuts the interior knockouts. |
| `glyph_geometry.py` | Shared helper: the single definition of what counts as an interior knockout, used by both of the two above. |

**Source maintenance.** Run by hand when working on artwork; each is
described in [source_structure.md](source_structure.md):

| Tool | Role |
| --- | --- |
| `format_svg.py` | Rewrites sources into the canonical written form. |
| `unify_shared_parts.py` | Gives artwork shared between icons one spelling. |
| `family_report.py` | Reports what families share, and where they have drifted apart. |
| `audit_geometry.py` | Reports specks, spikes, slivers, needles, self-crossing contours, and features too thin for 16 px. |
| `repair_artifacts.py` | Removes that debris, one bounded pass per defect category. |
| `restroke_alef.py` | Changes a letterform's stroke weights and length. |
| `region_diff.py` | Proves a rewrite did not change what an icon draws, by comparing exact vector regions. |
| `raster_diff.py` | The same question answered independently, by rendering both versions and comparing pixels. |

**One-off preparation.** For bringing outside artwork into the set. None are
part of any routine build:

| Tool | Role |
| --- | --- |
| `prepare_svg_sources.dart` | Converts an incompatible export - strokes, text, masks, transforms, a foreign canvas - into direct filled paths, using Inkscape. |
| `flatten_svg_transforms.dart` | Applies the simple translate/scale wrapper some legacy artwork carries, preserving the geometry exactly rather than redrawing it. |
| `scale_svg_paths.dart` | Uniformly scales path geometry about the centre of the 24x24 canvas. |
| `check_glyph_coverage.py` | Asserts every manifest codepoint maps to a non-empty outline in the committed font, so a blank glyph cannot ship. Run in CI. |
| `check_font_subset.dart` | Confirms tree shaking actually subset the font in a release build. Run in CI. |

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
