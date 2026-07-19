# Tree-shaking proof of concept

Date: 2026-07-16

The app under `test_apps/minimal/` references only:

```dart
Icon(OtzariaIcons.book_open_large_24_regular)
```

A Flutter 3.44.0 Web release build completed without a non-constant `IconData`
warning. Flutter reported:

```text
otzaria_icons.otf: 3296 bytes -> 2124 bytes (35.6% reduction)
```

This proves that the package's public `static const IconData` fields permit
Flutter to subset the package font. The full example gallery must not be used for
this test because it intentionally references every icon.
