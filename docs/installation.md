# Installation

## Tagged Git dependency

Otzaria Icons is currently distributed directly from GitHub. Pin the dependency
to an immutable release tag:

```yaml
dependencies:
  otzaria_icons:
    git:
      url: https://github.com/Otzaria/otzaria_icons
      ref: v0.2.1
```

Run `flutter pub get`, then import:

```dart
import 'package:otzaria_icons/otzaria_icons.dart';
```

The tag must match the package version (`0.2.1` → `v0.2.1`). Do not depend on
`main`, because a moving branch makes builds non-reproducible and may introduce
API or glyph changes without changing the consuming application's lockfile.

## Using it with Fluent UI System Icons

The packages are separate and can coexist:

```yaml
dependencies:
  fluentui_system_icons: ^1.1.273
  otzaria_icons:
    git:
      url: https://github.com/Otzaria/otzaria_icons
      ref: v0.2.1
```

There is no codepoint collision even if both fonts use the Unicode Private Use
Area. Flutter resolves each glyph by both codepoint and font family.

## Local development

When testing an unreleased change from a neighboring checkout:

```yaml
dependencies:
  otzaria_icons:
    path: ../otzaria_icons
```

Use this only while developing locally. Restore the tagged Git dependency before
committing changes to the consuming application.

## Updating

1. Read `CHANGELOG.md`.
2. Change `ref` to the new version tag.
3. Run `flutter pub get`.
4. Run the consuming application's analysis and tests.
5. Review any visual changes in the affected screens.

Do not edit the package's generated font registration in the consuming app.
Flutter loads the font through the package metadata automatically.

## Troubleshooting

- **A square/missing-glyph box appears:** verify the import uses the generated
  constant and that `flutter pub get` completed. Do not recreate `IconData`.
- **An old icon remains after updating:** run `flutter clean`, then
  `flutter pub get`, and rebuild.
- **Git dependency cannot be resolved:** verify the repository URL and that the
  requested tag exists remotely.
- **The icon has the wrong color:** set `Icon.color` or an `IconTheme`; the font
  is monochrome.
