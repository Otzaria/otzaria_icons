# Release validation

> **Point-in-time record.** The results below were captured on 2026-07-16 when
> the font contained 10 glyphs; the package now ships 138. Re-run the steps and
> record fresh results per release rather than reading these figures as current.

## Local results — 2026-07-16

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
