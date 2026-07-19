# Usage

## Basic use

Every public value is a compile-time constant:

```dart
const Icon(OtzariaIcons.search_24_regular);
```

Pass normal `Icon` properties for size, color, accessibility, and direction:

```dart
const Icon(
  OtzariaIcons.book_search_24_regular,
  size: 20,
  color: Color(0xFF005FB8),
  semanticLabel: 'Search the library',
);
```

## Variants

Use `regular` for the default state and `filled` when the product needs a
selected or emphasized state. Not every icon must have both variants.

```dart
Icon(
  selected
      ? OtzariaIcons.book_open_large_lines_24_filled
      : OtzariaIcons.book_open_large_lines_24_regular,
);
```

## Sizes

The source canvas is 24×24. Flutter may render the vector glyph at other sizes;
the gallery checks 16, 20, 24, 32, and 48 logical pixels. Prefer a size supported
by the surrounding control and visually inspect unusually small rendering.

## RTL behavior

Icons are not mirrored merely because the application is RTL. The manifest's
`match_text_direction` field records whether an icon is directional. Current
icons set it to `false`. If a future icon needs automatic mirroring, the
generator and public `IconData` output must be updated deliberately and covered
by gallery/tests.

## Accessibility

An icon that conveys meaning needs a semantic label unless the surrounding
button or control already supplies one. Decorative icons should be excluded
from semantics:

```dart
const ExcludeSemantics(
  child: Icon(OtzariaIcons.book_open_large_24_regular),
);
```

Do not rely on shape or color alone to communicate selected/error states.

## Semantic application aliases

This package exposes visual names. Product meaning belongs in Otzaria:

```dart
abstract final class AppIcons {
  static const library = OtzariaIcons.book_open_large_24_regular;
  static const librarySelected = OtzariaIcons.book_open_large_24_filled;
}
```

This allows the product to change its chosen visual icon without renaming the
font package's stable public API.

## Tree-shaking

Reference generated constants directly. Do not export a production list or map
that references every icon, because such a catalog can keep every glyph alive.
The complete catalog exists only inside `example/`.

The generated `IconData` retains both `fontFamily` and `fontPackage`; these are
required for package font lookup and icon tree-shaking.
