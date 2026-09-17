# Icon design specification

## Canvas and optical bounds

- Canvas: 24×24 with `viewBox="0 0 24 24"`.
- Export final path geometry directly in 24×24 coordinates, with a centered
  20×20 optical area. Transform-based downscaling is not accepted.
- Keep geometry within the visual safe area; use optical centering.
- Geometry may exceed the nominal 2-unit margin only when required for optical
  balance and after visual review at small sizes.
- Some families are deliberately drawn to a 23-unit box centred on the canvas -
  `book_open_large`, `otzaria_icon`, `books_stacked` and `torah_scroll` - where
  the drawing is meant to *be* the icon rather than sit inside it. Half a unit
  of air is the minimum: less and a round terminal looks cropped at 16 px.

## Weight and shape

- Regular icons should visually match Fluent UI's regular weight, approximately
  the visual result of a 1.5-unit stroke before expansion.
- Convert strokes to closed, filled paths before committing.
- Use explicit `fill-rule` for shapes with interior holes.
- Avoid unnecessary groups, transforms, masks, clipping, and embedded styles.
- Prefer Fluent-like rounded joins/endings and consistent corner radii; compare
  related icons side by side instead of applying a radius mechanically.
- Keep meaningful gaps visible at common sizes (16, 20, 24, and 32 px).
- Keep gaps around 1.5 units or larger where possible so they survive 16 px
  rendering.
- Use whole or half-pixel coordinates intentionally; avoid accidental precision
  noise from editor exports.

## Regular and filled relationship

- A filled variant is added only when the product needs a selected/active state.
- A filled variant is an **inversion of its regular twin, not a redrawing of
  it**: every white area inside the icon except the one outside it turns black,
  every black line turns white, and a thin black line is added around the
  outermost white lines. Stated that way it needs no offset of the artwork, so
  the two cannot drift apart. `compose_sources.inverted()` is the one
  implementation; do not derive a filled icon any other way.
- The outer black line is 0.55 units, or 1.10 on the two `book_open` families
  whose covers are heavy enough that a finer line reads as a hairline. It is
  added outward only.
- Interior negative space may be simplified in filled variants, but the icon
  must remain recognizable at 16 px.

## Directionality

- Directional icons may have an RTL-mirrored counterpart; non-directional icons
  must not be mirrored automatically.
- Record intended mirroring in `match_text_direction`; do not infer it only from
  the current gallery language.

## Acceptance

Review at 16, 20, 24, 32, and 48 px in light/dark and LTR/RTL modes. Compare
baseline, perceived weight, spacing, corner language, and silhouette with nearby
official Fluent icons.
