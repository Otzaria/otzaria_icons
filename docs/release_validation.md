# Release validation

> **Point-in-time record.** Each section below is the state at one date. Re-run
> the steps and add a section per release rather than reading older figures as
> current.

## Local results — 2026-09-17, for 0.4.0 (180 icons)

| Step | Result | Notes |
| --- | --- | --- |
| `dart format --set-exit-if-changed` | Passed | 21 files, 0 changed |
| `dart run tool/validate.dart` | Passed | 180 SVGs, 0 errors, 0 warnings |
| `normalize_svg_overlaps.py --check` | Passed | 0 need normalization, 45 skipped |
| `format_svg.py --check` | Passed | worst outline movement 0.00135 of the 0.00200 limit |
| `check_glyph_coverage.py` | Passed | 0 missing codepoints, 0 empty glyphs, no tofu |
| `dart run tool/generate.dart --check` | Passed | repository files unchanged |
| `flutter analyze` / `flutter test` | Passed | 7 tests, package |
| Example gallery | Passed | analyze clean, gallery lists every current icon |
| `test_apps/minimal` | Passed | analyze clean, 1 test |
| Web release (minimal) | Passed | built; see the note below |
| `check_font_subset.dart` | Passed | 131740 → 125844 bytes |
| Manifest audit | Passed | 180 records, codepoints `U+E000`-`U+E0B3` dense and unique, no duplicate names, every record authored and licensed, 16 `modified_fluent` matching `THIRD_PARTY_NOTICES.md` |
| CI on `main` (`96b4a9c`) | Passed | all seven jobs: package, consumer on Flutter 3.16.9, generated-files check, example gallery, minimal app + web release, Android release, Windows release |
| Release validation on `v0.4.0` | Passed | package integrity, Linux release, macOS release |

**Open finding — icon tree-shaking removes no glyphs.** The minimal application
references exactly one icon, and the font Flutter ships with it still contains
**all 182 glyphs**; the 4.5% it does save is metadata. `check_font_subset.dart`
passes because it only asserts the release font is smaller than the source. This
is not new in 0.4.0 - the same gate has been passing on the same weak condition
since the font grew past its 10-glyph proof of concept - but the gate should
compare glyph counts, not bytes, and the cause is worth finding before 1.0.

## Local results — 2026-07-16 (10 glyphs)

> Captured during early bring-up, when the font contained 10 glyphs.

| Target | Result | Notes |
| --- | --- | --- |
| Package analyze | Passed | No issues |
| Package tests | Passed | Metadata, manifest, and real glyph render |
| Example gallery | Passed | Analyze and widget test |
| Web release | Passed | Font subset from 3296 to 2124 bytes |
| Windows x64 release | Passed | Minimal app and full gallery built |
| Android release | Passed | Minimal app and full gallery APKs built and verified |
| Linux release | Pending GitHub | Platform projects and workflow prepared |
| macOS release | Pending GitHub | Platform projects and workflow prepared |

The local Android build used API 36, Build Tools 36.0.0, and NDK
28.2.13676358. Both APKs passed `apksigner verify` using v2 signatures. These
test applications intentionally use Flutter's generated debug signing
configuration; they are validation artifacts, not store-release binaries.

The Windows-only visual baseline contains all ten current glyphs. The explicit
even-odd magnifier glyph was visually verified to preserve its interior hole in
the generated OTF despite the generator's generic warning.
