# Adding icons

## 1. Prepare source files

Place all SVGs directly in `assets_src/svg/`. A batch may contain one icon or
regular/filled pairs. Follow `docs/svg_requirements.md`.

Run validation before generation. If final artwork contains unsupported SVG
structure, prepare only those files and validate again:

```console
dart run tool/validate.dart
dart run tool/prepare_svg_sources.dart assets_src/svg/example_24_regular.svg
dart run tool/validate.dart
```

Do not run preparation blindly over canonical icons. Review converted files at
16, 20, 24, 32, and 48 pixels. Correct spelling before first generation because
the generated name and codepoint become public API.

### Resolve overlapping / seaming paths

The font merges every `<path>` of an icon into a single glyph filled with the
nonzero winding rule. Independent black layers that overlap, or sub-paths that
merely touch, look fine in a browser and in `docs/icon_catalog.svg` (each path is
painted separately) but corrupt in the font: overlaps with opposing winding
knock out unintended white holes, and touching edges leave hairline seams. Check
new artwork and normalize it into one clean, font-safe outline:

```console
python3 tool/normalize_svg_overlaps.py --check                       # report only
python3 tool/normalize_svg_overlaps.py assets_src/svg/example_24_regular.svg
```

The tool `simplify`s each path (honouring its fill-rule) and boolean-unions them
into a single non-overlapping, consistently-wound path whose filled area is
exactly what the catalog shows. It is idempotent, and it automatically **skips**
intended knockout icons (a whole white shape sitting inside a solid body, e.g.
`document_word_24_filled`), which rely on the font's winding cancellation and
must keep their separate paths. Requires `pip install -r tool/requirements.txt`.
CI runs `--check` and fails if any committed source still overlaps.

## 2. Run generation

From the repository root:

```console
flutter pub get
dart run tool/generate.dart
```

Generation requires Python 3 with `skia-pathops` and `fonttools`
(`pip install -r tool/requirements.txt`) for the final glyph-repair step.

Generation performs this sequence:

1. verify native 24×24 canvas coordinates;
2. safely sanitize SVG structure;
3. validate SVG and existing manifest metadata;
4. add new manifest records and allocate `max(codepoint) + 1`;
5. build the OTF in explicit manifest/codepoint order;
6. verify actual generated glyph names and codepoints;
7. regenerate the public Dart API, gallery catalog, test expectations, and
   third-party notices;
8. format and analyze the generated public API;
9. repair glyph outlines from source (`tool/repair_glyphs.py`): the pinned
   `icon_font_generator` distorts a few complex glyphs during outline
   conversion — a horizontal shift on `book_open_large_search_24_filled`,
   contour damage on `stander` and `search_in_the_text` — even from clean
   sources. This step rewrites each glyph's outline directly from its SVG so the
   font matches the catalog exactly. Interior knockouts are rebuilt as a boolean
   difference (body minus the cut) so the cut stays transparent regardless of
   source winding. It is deterministic and preserves all generator metadata.

New records receive an opaque stable ID such as `icon-0011`. Never change an ID
after allocation. Complete or correct the new manifest record if its provenance,
directionality, author, or upstream state differs from the defaults.

## 3. Review generated changes

Expected changes may include:

- `icon_manifest.yaml`;
- `lib/fonts/otzaria_icons.otf`;
- `lib/src/generated/otzaria_icons_data.dart`;
- `example/lib/generated/icon_catalog.dart`;
- `test/generated/icon_expectations.dart`;
- `THIRD_PARTY_NOTICES.md`.

Do not hand-edit generated artifacts. Fix the SVG, manifest, config, or generator
and regenerate.

## 4. Validate

```console
dart run tool/generate.dart --check
flutter analyze
flutter test
```

The `--check` mode generates in a temporary directory, compares all derived
artifacts, and leaves repository files untouched.

The Windows golden surface grows automatically with the manifest, so every
registered icon is rendered at all five production sizes. Accept a new golden
only after checking for blank, clipped, crowded, or unexpectedly filled glyphs.

Run the example gallery and inspect every new glyph. Also build
`test_apps/minimal/` when generation or public `IconData` construction changes,
because it proves icon font tree-shaking.

## 5. Document and submit

- Add a `CHANGELOG.md` entry under the unreleased version.
- Explain the icon's intended product use in the pull request.
- Confirm authorship and GPL-3.0-only licensing, or provide complete third-party
  provenance.
- Include screenshots for visual changes when practical.

Existing codepoints are immutable. Never reorder, recycle, silently remove, or
manually compact them.
