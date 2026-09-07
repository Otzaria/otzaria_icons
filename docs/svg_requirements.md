# SVG requirements

An SVG is accepted only when it satisfies the mechanical rules below and passes
visual review.

Committed sources are additionally kept in one canonical written form - absolute
commands, one contour per line, a fixed decimal precision per file, and shared
parts spelled identically across a family. Run `python3 tool/format_svg.py`
after adding or editing a file; see
[source_structure.md](source_structure.md) for that form and the tools that
maintain and verify it.

## File and naming

- Store files directly in `assets_src/svg/`; do not create one directory per
  icon.
- Use lowercase `snake_case`.
- Use the form `<name>_24_regular.svg` or `<name>_24_filled.svg`.
- Names must match `^[a-z][a-z0-9_]*_24_(regular|filled)$`.
- Avoid uppercase letters, hyphens, spaces, consecutive underscores, leading
  digits, missing size/variant, and Dart reserved words.

## Canvas and geometry

- Final `viewBox` must be exactly `0 0 24 24`.
- Keep geometry visually centered with a typical 20×20 optical area.
- Convert large source canvases into final 24×24 path coordinates in the vector
  editor before adding them.
- Avoid geometry touching the canvas edge unless the design explicitly demands
  it.
- Multiple `<path>` elements are allowed, but they must not rely on being
  painted as separate layers. The font merges every path into one nonzero-fill
  glyph, so overlapping black layers with opposing winding cancel to unintended
  white holes and touching sub-paths leave hairline seams — both invisible in a
  browser and in `docs/icon_catalog.svg`, both corrupt in the font. Resolve them
  into one clean outline with `tool/normalize_svg_overlaps.py` (see
  `docs/adding_icons.md`). Genuine interior knockouts are exempt; see below.
- Committed source paths must use the final 24×24 coordinate system. A
  large-coordinate path wrapped in `<g transform="... scale(...)">` is rejected
  even if it appears to fit the canvas, because font conversion and hinting can
  produce poor small-size results.

## Paths

- Convert all strokes to closed, filled outlines before adding the file.
- The root `<svg>` should contain only one or more direct `<path>` children.
- Do not leave groups, transforms, `stroke`, `stroke-width`, primitive shapes,
  text, fonts, raster images, clipping, masks, filters, scripts, symbols,
  external references, or embedded styles.
- Use explicit `fill-rule="evenodd"` only where interior holes truly require
  it; otherwise prefer non-zero winding paths for maximum font compatibility.
- The generated font is monochrome. Color is supplied by Flutter's `Icon`.

### Minimal valid structure

```svg
<svg xmlns="http://www.w3.org/2000/svg"
     width="24"
     height="24"
     viewBox="0 0 24 24">
  <path d="M4 3h16v18H4Z"/>
</svg>
```

### Invalid transformed structure

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

The invalid example still contains a large-coordinate drawing. A browser can
scale it correctly, but font conversion and small-size rasterization may not.
Transforms must be applied to the actual path data before the SVG is committed.

## Safe sanitation

`tool/sanitize.dart` performs conservative cleanup. It only flattens a sole
wrapper group when doing so cannot discard transforms, clipping, identifiers, or
nested group behavior. It intentionally does not rewrite ambiguous geometry.

`tool/normalize_canvas.dart` is now a guard: it rejects non-24 canvases instead
of creating scale transforms. This policy was adopted after real transformed
glyphs rendered poorly at 16–24 px despite looking acceptable at 80 px.

### Preparing incompatible exports

If visually final artwork was exported with strokes, text, masks, primitive
shapes, nested transforms, or a different canvas, use the explicit preparation
tool before generation:

```console
dart run tool/prepare_svg_sources.dart assets_src/svg/example_24_regular.svg
```

The tool requires Inkscape. Set `INKSCAPE` to its executable when it is not on
`PATH`. It uses Inkscape's vector engine to convert text and strokes to
outlines, resolve masks, apply nested transforms, map the viewport to 24x24,
and write direct filled paths. It rejects results that still contain raster
images, text, masks, or filters.

Stroke settings may be declared directly on each path or inherited from the
root `<svg>` or a parent group. Do not move or delete inherited `stroke`,
`stroke-width`, `stroke-linecap`, or `stroke-linejoin` attributes manually.
The preparation tool preserves and expands them together, so rounded caps,
joins, widths, transforms, and proportions remain unchanged.

White artwork inside a filled icon is treated as a knockout, not as another
black shape. The preparation tool converts white mask/stroke geometry into an
even-odd transparent hole suitable for a monochrome font. Never replace white
eraser geometry with black before the compound path has been created.

This is a preparation step, not part of CI and not a substitute for review.
Compare the source and prepared artwork visually before committing. Keep the
source under version control while running the command so an unintended result
can be reverted.

## Common export mistakes

| Problem | Why it fails | Correct action |
| --- | --- | --- |
| A 512x512 or other large `viewBox` | Font metrics and small-size rasterization become inconsistent | Export native 24x24 coordinates or run the preparation tool |
| A transformed group around large paths | Stored geometry is not actually 24x24 | Apply the transform to every path |
| `stroke`, `stroke-width`, or `<line>` | The font consumes filled contours | Convert strokes to paths while preserving caps and joins |
| Stroke styling only on the root `<svg>` | Child paths inherit it even without a local `stroke` attribute | Preserve the root styling and run the preparation tool; never copy only the bare path data |
| `<rect>`, `<circle>`, `<polygon>`, or `<polyline>` | These are not canonical committed sources | Convert every shape to a path |
| `<text>` | Rendering depends on a local font and text engine | Convert text to outlines where its appearance is approved |
| A mask, clipping path, or filter | OpenType glyphs do not retain SVG compositing | Resolve it to paths; use `evenodd` for intentional holes |
| `transform-origin="center"` with a flip | Renderer support differs | Bake the flip into path coordinates |
| Width/height other than exact `24` | Package metrics must be deterministic | Commit `width="24"` and `height="24"` |
| A suffix such as `_reguiar` | It creates an invalid public name | Use exactly `_24_regular` or `_24_filled` |
| A semantic typo such as `saerch` | Names become permanent after release | Correct spelling before first generation |
| White paths used as erasers | Fonts are monochrome, so white becomes filled | Use compound paths and correct winding or `evenodd` |
| A bitmap or data URI | Raster data cannot become a scalable glyph losslessly | Replace it with original vector artwork; tracing is not accepted |

## Validation levels

Errors block generation: invalid XML, wrong name/viewBox, strokes, missing
paths, duplicate names/IDs/codepoints, bad provenance, or codepoints outside
`0xE000–0xF8FF`.

Warnings highlight suspicious but potentially valid content, such as an
unusually high path count. A warning requires human review even when generation
continues.

## Visual acceptance

Inspect regular and filled variants together at 16, 20, 24, 32, and 48 pixels,
in light/dark and LTR/RTL modes. Confirm optical centering, recognizability,
interior holes, consistent weight, spacing, and selected-state relationship.
