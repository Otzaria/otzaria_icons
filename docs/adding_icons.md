# Adding icons

> **Prefer a one-click flow?** Run the graphical build helper — double-click
> `otzaria_build.bat` (Windows) or run `python otzaria_build.py`, and pick
> "After adding / editing icons". It runs every step below in order. See
> `docs/build_helper.md`. The manual steps follow for reference.

## Quick workflow

One-time setup: install the pinned Python tools used by generation.

```console
python3 -m pip install -r tool/requirements.txt
```

Then, for each new icon:

1. Drop a valid `<name>_24_<regular|filled>.svg` into `assets_src/svg/`
   (exactly `width="24" height="24" viewBox="0 0 24 24"`, filled `<path>`s only).
2. Clean overlapping/seaming paths: `python3 tool/normalize_svg_overlaps.py`
   (run `--check` first to see which files need it).
3. Generate: `dart run tool/generate.dart`. The final glyph-repair step rebuilds
   every glyph — including interior knockouts — directly from your SVG, so the
   font always matches the source; no `icon_font_generator` distortion can slip
   through.
4. Verify: `dart run tool/generate.dart --check`, `flutter analyze`, `flutter test`.
5. If any glyph changed, regenerate the visual golden **on Windows** and review
   it: `flutter test --update-goldens test/icon_gallery_golden_test.dart`.
6. Update `CHANGELOG.md` and commit the SVG plus every regenerated artifact.

**Important:** always run generation with the pinned tools
(`pip install -r tool/requirements.txt` first). A different `fonttools`/`skia-pathops`
version produces a different font byte-for-byte and makes `--check` fail in CI.
Never hand-edit generated files (the OTF, the `lib/src/generated/` Dart, the
catalog, `index.html`); edit the source or the generator and regenerate.

The sections below explain each step in detail.

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
intended knockout icons — a whole shape sitting inside a solid body meant to be
transparent, e.g. the alef in `book_open_alef_24_filled` or the "W" in
`document_word_24_filled`. Those keep their separate paths so the glyph-repair
step (section 2) can rebuild them as a boolean difference (body minus the cut),
which makes the cut transparent regardless of source winding. Requires
`pip install -r tool/requirements.txt`. CI runs `--check` and fails if any
committed source still overlaps.

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
registered icon is rendered at all five production sizes. When a glyph changes,
`flutter test` fails on `test/goldens/icon_gallery.png`. Regenerate it **on
Windows** (the golden is pinned to one OS to avoid rasterization differences,
and the test is skipped elsewhere):

```console
flutter test --update-goldens test/icon_gallery_golden_test.dart
```

Accept the new golden only after checking for blank, clipped, crowded, or
unexpectedly filled glyphs, then commit `test/goldens/icon_gallery.png`.

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
