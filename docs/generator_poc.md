# Generator proof of concept

Date: 2026-07-16

Toolchain:

- Flutter 3.44.0
- Dart 3.12.0
- `icon_font_generator` 4.1.0 (exactly pinned)

Inputs, in controlled `svgMap` insertion order:

1. `book_24_filled.svg`
2. `book_24_regular.svg`

Observed output:

| Index | SVG name | Glyph metadata name | Codepoint |
| ---: | --- | --- | --- |
| 0 | `book_24_filled` | `book_24_filled` | `0xE000` |
| 1 | `book_24_regular` | `book_24_regular` | `0xE001` |

The package source and runtime result agree: version 4.1.0 assigns
`0xE000 + index`. The insertion order of the supplied `Map` is preserved.

Version 4.1.0 also interprets one-argument `scale(s)` as `scale(s, 0)`.
Source transforms are therefore prohibited; paths must be flattened into native
24×24 coordinates before generation.

Decision:

- `icon_manifest.yaml` is the source of truth.
- `tool/generate.dart` sorts manifest entries by codepoint and constructs the
  `svgMap` in that exact order.
- Generation fails if glyph name or codepoint differs from the manifest.
- The generator fixes the OTF `head` timestamp so identical inputs produce
  byte-for-byte identical output.
- Existing SVG entries cannot be removed silently.
- Version 4.1.0 only supports contiguous codepoints through this API. A future
  need for tombstones or gaps requires either retaining placeholder glyphs or
  rewriting the generated font's cmap; it must not be handled silently.

The tool's built-in Flutter class generator converts names to camelCase. It is
therefore deliberately not used for the public API. Our generator writes
`otzaria_icons_data.dart` directly from the manifest so fields remain compatible
with Fluent's `snake_case` convention.
