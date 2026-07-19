# Development status

## Completed

- Confirmed Otzaria compatibility: Dart `>=3.2.6 <4.0.0`.
- Confirmed Otzaria currently uses `fluentui_system_icons: ^1.1.273`.
- Confirmed local tested toolchain: Flutter 3.44.0 and Dart 3.12.0.
- Chosen API: `OtzariaIcons` with Fluent-compatible `snake_case` fields.
- Chosen one font containing only variants that are actually required.
- Created the Flutter package structure.
- Pinned `icon_font_generator` to exactly 4.1.0.
- Separated source SVG, generated Dart, font output, manifest, and build config.
- Added initial SVG and manifest validation.
- Added contributor, design, changelog, and licensing documentation.
- Restored and locked development dependencies.
- Completed the generator ordering/codepoint POC with two real SVG files.
- Implemented manifest-driven font and Dart generation.
- Added metadata, manifest, and render tests.
- Added a light/dark, LTR/RTL, resizable example gallery and widget test.
- Added a one-icon minimal app and proved real font tree-shaking in Web release.
- Made the example gallery catalog generated from the manifest.
- Added CI for minimum/current Flutter, generation drift, gallery, tree-shaking,
  Android release, and Windows release.
- Passed a local Windows x64 release build.
- Passed a local Windows x64 release build of the full gallery.
- Added a numeric CI assertion that the minimal release font is smaller than
  the source font.
- Added generated all-icon metadata expectations to keep manifest and API in
  lockstep.
- Added safe automatic wrapper-group SVG sanitation.
- Imported five regular/filled pairs (ten icons) under GPL-3.0-only.
- Replaced transform-based large-canvas normalization with a strict native
  24×24 geometry requirement after small-size rendering validation.
- Added a Windows visual baseline covering every glyph.
- Installed an isolated Android API 36 toolchain and passed local release builds
  for the minimal app and full gallery.
- Included the canonical GPLv3 text in `LICENSE`.
- Expanded the manifest with immutable IDs, full provenance, directionality,
  deprecation, and upstream metadata.
- Made `tool/config.yaml` the generator configuration source.
- Added a read-only `generate.dart --check` mode.
- Made `THIRD_PARTY_NOTICES.md` a generated artifact.
- Added comprehensive installation, usage, SVG, architecture, CI, and release
  documentation.
- Added Linux/macOS application projects and a manual pre-release workflow.
- Added GitHub pull request and issue templates.
- Removed local SDKs, downloads, build output, IDE files, and caches.

## Next

1. Import and review additional icon batches.
2. Configure Git author identity, create the initial commit, and create the
   GitHub repository when approved.
3. Run CI plus Linux/macOS release validation on GitHub.
4. Create a version tag only after every required check passes.

## Current release gates

- The GitHub repository and initial commit do not exist yet.
- Linux and macOS release builds must run on GitHub-hosted runners.
- A release tag must be created only after those checks pass.
