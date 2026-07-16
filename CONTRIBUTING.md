# Contributing

Thank you for helping extend Otzaria's icon vocabulary. Contributions must keep
the public API, font mapping, visual style, and licensing record stable.

## Before starting

- Search Microsoft Fluent UI System Icons for an existing equivalent.
- Search this package's manifest for an existing or deprecated equivalent.
- Confirm the icon has a concrete Otzaria use case.
- Decide whether a regular variant, filled variant, or both are needed.

This repository is an unofficial extension and is not affiliated with or
endorsed by Microsoft.

## Contribution license

Every icon, SVG, code change, document, or other contribution submitted for
inclusion is licensed automatically under **GPL-3.0-only**, the same license as
the library. By opening a pull request or otherwise submitting a contribution,
you confirm that:

- you own the contribution or have sufficient rights to license it;
- the project may copy, modify, redistribute, and publish it under
  GPL-3.0-only;
- no additional restriction, incompatible license, trademark condition, or
  confidential material applies to it; and
- all third-party or derivative material is identified with complete source,
  author, license, and revision information.

Acceptance into the repository does not transfer copyright ownership, but the
contribution remains available under GPL-3.0-only. Maintainers may reject
material whose origin or licensing cannot be verified.

## Preparing SVG files

Add SVGs directly to `assets_src/svg/`. Follow the exact
`<name>_24_<regular|filled>.svg` naming scheme, convert strokes to filled paths,
and satisfy [SVG requirements](docs/svg_requirements.md) and the
[visual design specification](docs/icon_design_spec.md).

The committed SVG must already use final 24x24 coordinates. Its preferred
structure is a single `<svg>` root containing one or more direct `<path>`
children:

```svg
<svg xmlns="http://www.w3.org/2000/svg"
     width="24"
     height="24"
     viewBox="0 0 24 24">
  <path d="M4 3h16v18H4Z"/>
</svg>
```

Required:

- exact `width="24"`, `height="24"`, and `viewBox="0 0 24 24"`;
- one or more filled `<path>` elements using native 24x24 coordinates;
- closed outlines in place of strokes;
- multiple paths only when they are genuinely needed;
- `fill-rule="evenodd"` only when holes require it.

Do not submit transforms, large source coordinates hidden behind a scale,
wrapper groups, strokes, shapes that have not been converted to paths, text,
fonts, raster images, clipping, masks, filters, scripts, embedded CSS, symbols,
or external references. For example, this is invalid even though a browser may
display it at the correct apparent size:

```svg
<svg xmlns="http://www.w3.org/2000/svg"
     width="24"
     height="24"
     viewBox="0 0 24 24">
  <g transform="translate(2 2) scale(0.04)">
    <path d="M50 50 ..."/>
  </g>
</svg>
```

Such transforms can survive differently during font conversion and cause poor
rendering or overflow at 16-24 px. Export the final path coordinates from the
vector editor before submission, then inspect the actual generated font at all
required sizes.

## Generation workflow

```console
flutter pub get
dart run tool/generate.dart
dart run tool/generate.dart --check
flutter analyze
flutter test
```

The generator allocates IDs/codepoints and updates all derived artifacts. Review
the new `icon_manifest.yaml` record. Do not edit generated Dart, font, catalog,
expectations, or notices files manually.

Existing IDs, names, and codepoints are immutable. Never reuse a codepoint or
delete a glyph to close a gap. A rename is implemented as a deprecated alias,
not as removal of the old API.

## Visual review

Run `example/` and inspect every new icon:

- regular and filled variants together;
- 16, 20, 24, 32, and 48 logical pixels;
- light and dark themes;
- LTR and RTL directions;
- optical alignment beside nearby Fluent icons;
- interior holes and small gaps;
- selected/unselected state relationship.

Update the Windows golden only after confirming the difference is intentional.

## Manifest provenance

Every record must accurately describe:

- stable `id`, public `name`, source, and codepoint;
- variant, size, directionality, and deprecation;
- whether Fluent now provides an equivalent;
- `custom` versus `modified_fluent` origin;
- author, license, and any upstream source/commit.

The release maintainer is responsible for reviewing `upstream_status` before
every release. If Fluent adds an equivalent, record it, deprecate the local API
with a migration path, and do not silently remove the glyph.

## Pull request checklist

- Generation check, analysis, and tests pass.
- Gallery review is complete.
- `CHANGELOG.md` describes the addition/change.
- Provenance and GPL compatibility are confirmed.
- The contributor has the right to submit the work under GPL-3.0-only.
- No cache, local SDK, build output, or IDE files are included.
- Public names remain Fluent-compatible `snake_case`.

See [Adding icons](docs/adding_icons.md), [Testing and CI](docs/testing_and_ci.md),
and [Release process](docs/release_process.md).
