# Changelog

## 0.4.0 - 2026-09-17

- **Breaking: `hyperlink` is gone and the `link` names have been reassigned,**
  with no deprecated aliases and no compatibility entries, as requested. The
  set now uses one word for one shape:

  | was | is | artwork |
  | --- | --- | --- |
  | `hyperlink_24_regular` | *removed* | |
  | `link_24_regular` | `links_24_regular` | the 45-degree chain |
  | `book_link_24_{regular,filled}` | `book_links_24_{regular,filled}` | the chain on a book |
  | `book_hyperlink_24_{regular,filled}` | `book_link_24_{regular,filled}` | the single link on a book |
  | `books_stacked_low_24_regular` | `books_stacked_low_24_filled` | the solid low stack |

  The last of those is a correction rather than a redesign: that icon was drawn
  solid and had been the family's only "regular". It keeps its codepoint under
  the name its artwork always deserved, and the name it vacates is taken by the
  outline drawing described below - so an application that asks for
  `books_stacked_low_24_regular` still compiles and now gets an outline icon
  where it used to get a solid one.

  Renaming is not reallocation - each of those keeps the codepoint its artwork
  already had, so nothing downstream shifts for them. **Removing** one does
  shift things: codepoints are a dense run from `U+E000`, so the 41 icons up to
  `U+E028` keep theirs and **104 shift down by one**. `links_24_regular` takes
  `U+E029`, the slot `hyperlink_24_regular` vacated. Any application that
  stored a codepoint rather than a constant must be rebuilt against this
  version.

- Added **thirty-four** icons (`U+E092`-`U+E0B3`). The set now ships **180**
  icons over a contiguous `U+E000`-`U+E0B3`.

  * `books_stacked_low_24_regular` - the low stack as an outline drawing, so
    that family has a pair like every other. It is not a second drawing: each
    of the solid's three closed contours is its own book, already cut where the
    book above covers it, so stroking them one at a time with a 0.75-unit line
    draws exactly the lines a reader would see and none of the hidden ones.

  * Three pairs of letters, all on `alef_alef_24_regular`'s grid - two letters
    10.80 units wide at x 0.95 and x 12.25, the Hebrew one on the right, each
    fitted to the same vertical band so the pair shares a baseline and a cap
    line: `alef_near_alef_stam_24_regular`, `alef_near_alef_rashi_24_regular`
    and `alef_latin_a_24_regular`. The Latin A is Fluent's, lifted out of
    `local_language_24_filled`.

  * `link_alef_24_regular` and `alef_lock_24_regular` - the alef on the link's
    disc, and a padlock on the alef's.

    The padlock is the one badge mark in the set that is drawn rather than
    taken from Fluent, and it is drawn because reducing Fluent's cannot work:
    `lock_closed_24_filled` is a 1.5-unit shackle around a 3-unit opening, and
    at the 0.29 a badge mark is scaled to, that opening falls under a unit and
    closes as soon as the stroke is put back. What is left is a rounded blob
    with a dot in it - the body, without the one feature that says lock. So the
    mark is drawn at badge size, as Fluent itself does for `lock_shield`: a
    narrow body, because its bottom corners are the farthest ink from the
    centre and so are what the fitting scales against, and above it a shackle
    whose opening is deliberately the largest thing in the mark. There is no
    keyhole: at 16 px it would be a fifth of a pixel of black inside a
    three-pixel white mark, and all it would do is grey the mark down.

  * Six more filled icons: `book_open_small_24_filled`,
    `book_open_small_line_24_filled`, `book_open_medium_search_24_filled`,
    `otzaria_icon_2_page_line_24_filled`, `otzaria_icon_empty_24_filled` and
    `books_stacked_high_24_filled`, each turned inside out from its regular twin
    by the one rule described below.

  * Seven more badged alefs, on the same disc in the same place as
    `alef_copy` and `alef_with_information`: `alef_scissors_24_regular`,
    `alef_lips_24_regular` (read aloud), `alef_marker_24_regular`,
    `alef_eye_24_regular` (show / hide), `alef_with_exclamation_24_regular`
    and `alef_addition_24_regular`, plus a rebuilt eraser described below.

    Four of those marks are Fluent's own - `cut`, `eraser`, `highlight` and
    `eye` - rather than drawings of the same idea; see the note on Fluent
    artwork below. The exclamation is drawn, rather than mirrored from the
    information badge: that "i" has a serif foot, and mirroring it puts the
    serif on top, where it reads as a bracket instead of a stroke. The addition
    badge is likewise not `alef_deletion`'s cross rotated - rotating a cross
    about its centre puts the arm ends on the axes and makes the mark 1.41x
    wider, and scaling that back down thins every stroke by the same factor,
    which is a lighter badge rather than the same badge stood upright. It is
    drawn to the cross's own measurements instead: the same arm half-length,
    and the bar thickness solved from the cross's filled area for a cross of
    that reach (1.91 units).

  * `alef_half_filled_24_regular` - the letter in both weights at once. The cut
    is the diagonal from the canvas's top-right corner to its bottom-left,
    through the letter's own centre, with the solid half below and to the right
    of it. That is the diagonal *across* the alef's dominant stroke rather than
    along it, which is what makes the two weights read as two halves of one
    letter instead of as one stroke inked and another not. The halves are
    butted rather than gapped: a seam wide enough to see at 300 px is a fifth
    of a pixel at 24 px, while still leaving slivers where the cut grazes a
    stroke.

  * `document_alef_24_{regular,filled}` and
    `document_download_24_{regular,filled}` - the `document_word` page with a
    new mark, in the block the tet occupies (x 8.43-15.57, y 10.10-19.10). The
    alef is the family's letterform fitted to that block; the arrow is
    `book_download`'s own arrow at the same height. Each filled variant knocks
    its mark out of the solid page.

  * `book_open_medium_24_filled` and `book_open_medium_line_24_filled`, by the
    same rule as the rest.

  * Nine badged links: `link_copy_24_regular`, `link_with_eraser_24_regular`,
    `link_marker_24_regular`, `link_with_information_24_regular`,
    `link_quote_24_regular`, `link_document_24_regular`,
    `link_scissors_24_regular`, `link_deletion_24_regular` and
    `link_eye_24_regular`.

    Fluent already badges its own link, and with exactly this concept: a solid
    disc at the bottom right, the mark knocked out of it, the link itself cut
    back to clear the disc. So `link_dismiss_24_regular` is taken apart and
    reassembled rather than imitated - the link comes back with Fluent's own
    cut-back, and the disc is Fluent's own circle (a true circle, r 5.495 at
    17.495, 17.495) in Fluent's own place. `link_deletion` carries that
    template's own cross, so it *is* Fluent's dismiss.

    `link_copy` is the exception among the marks: it uses the copy this set
    already draws on the alef's disc rather than Fluent's. Fluent's copy is two
    outlined sheets, and at badge scale its rings vanish; the adaptation that
    cuts the sheets out solid is already the right drawing for a disc this size.

    `link_quote` carries Fluent's quote marks rather than straight Hebrew
    gershayim, which is what `search_in_the_quote_24_regular` already uses, so
    the two agree.

- **Redrew the text rules on seven open books** (same names and codepoints,
  visual change). `otzaria_icon_line`, `otzaria_icon_2_page_line`,
  `book_open_large_lines`, `book_open_large_search` and `book_open_small_line`
  showed their text as six or seven rules half a unit thick and 1.5 apart -
  bands of ink and paper almost equal in width, which below 24 px close into a
  grey slab, and which go first in the filled variants where they are white on
  black. `book_open_medium_line` already had it right: three rules at 1.25 with
  1.75 of paper between them, a gap 1.4 times the ink. Every rule in the set is
  now a stadium with ends rounded to exactly half its height, and they are laid
  out one of two ways.

  `book_open_large_lines` and `book_open_large_search` carry **four rules** at
  that ratio, centred on the block the originals occupied so the text stays
  where the designer put it. The two `book_open_medium` icons keep their three
  and are only **shortened, to 4.40** - a rule 3.5 times its own height, so its
  round ends are a third of it and read as ends. At the 5.75 they were drawn at
  the filled variant's knockouts ran into its white band; at 5.15 they cleared
  it but still read as cut rectangles.

  The other three set their text over the **whole page** rather than as a block
  in the top of it. `otzaria_icon_line` and `otzaria_icon_2_page_line` carry
  five rules and `book_open_small_line` four, in each case with the same gap
  above the first, between each pair and below the last, measured from the
  frame lines the page is actually drawn between rather than from the canvas.
  `book_open_small_line`'s are also narrowed to 4.00 and centred on the paper:
  at 4.80 in a page 5.52 across they left a quarter of a unit beside them and
  read as running into the book's own uprights.

  The gap is stated as a ratio of the rule's own height rather than as a pitch,
  and the height is solved from the opening. That is what lets these icons be
  scaled afterwards without the text falling out of step with the drawing - and
  three of them are scaled, below.

- **Restored the back of `beit_24_regular`** (same name and codepoint, visual
  change). The letter was made by scaling the small beit inside
  `beit_near_alef_24_regular` up to letter size and eroding it 0.45 units on
  every flank - 0.90 off every stroke - and the back could not afford it. It
  measured 2.95 at the shoulder but **0.22** at y=16, a fifth of a pixel at
  24 px, so the letter read as a top and a base joined by a hair. Neither the
  alef nor the tet has ink under 0.9 anywhere.

  Exactly the 0.90 the erosion took is given back, which puts the back on the
  letterform's own proportions - 1.25 at mid-height - rather than on a width
  picked by eye. It is added by moving that one stroke's left edge, not by
  growing the letter: a grow moves every edge, and restricted to a box it
  leaves a step where the box ends.

  The new edge is a **fitted curve**, not a smoothed copy of the old one. That
  distinction is the whole repair. The letterform is hand-drawn and carries
  small nicks along that edge, and a traced edge - even averaged - carries every
  one of them into the result, which is what the first version of this shipped:
  a back with tremors in it, and a hook where the padding eased off into the
  base. A degree-5 polynomial has nothing to carry: it is smooth by
  construction, it cannot reproduce a defect in its input, and over the length
  of one stroke it still follows the drawing to a few hundredths. The padding
  eases in over 1.6 units under the bar and does **not** ease out at the foot,
  because the foot is a junction with the base rather than a free end.

- **Three families now fill the canvas** (same names and codepoints, visual
  change to twenty icons): every `book_open_large`, every `otzaria_icon` and
  every `books_stacked`, regular and filled alike, is scaled about its own
  centre until its longer side is 23 units and then centred on the canvas. Half
  a unit of air on each side is enough that a round terminal does not look
  cropped at 16 px and close enough to the box that the drawing is the icon
  rather than a drawing inside it. `otzaria_icon` gains the most - it was 19.73
  across - and the Torah scroll was already brought to the same 23, so the
  number is now shared rather than restated in two places.

  A derived filled icon is scaled *after* its outer line is added, so the pair
  fills the same box rather than the filled one standing half a line proud of
  its twin.

- **`otzaria_icon_24_filled` is a derived icon again.** It was briefly restored
  to the drawing it had been, to get back the wider paper gap the drawing
  carries between its outer line and the cover. The cost of that is the reason
  it did not stay: a drawing does not follow its regular. Every other icon in
  the set is redrawn by re-running the composer, and that one would have had to
  be redrawn by hand every time the regular moved.

- **Thinned `bookshelf_24_regular` by 15%** (same name and codepoint, visual
  change), and nothing else: a uniform inward offset moves every point of the
  outline along its own normal, so the books' widths, their lean and the shelf
  are untouched and only the weight changes. The mean stroke goes from 1.042 to
  0.843.

- **Every filled variant is now derived by one rule, stated rather than
  inferred** (same names and codepoints, visual change to all fifteen):

  > every white area inside the icon, except the big one outside it, turns
  > black; every black line turns white; and a thin black line is added around
  > the outermost white lines.

  Read literally, that needs **no offset of the artwork at all**. The white
  lines of a filled icon are the black lines of its regular twin, exactly where
  the designer drew them - same widths, same curves, same corners - so the pair
  cannot differ in the ways the earlier versions did. The only constructed part
  is the outer black line, and that is a *grow* of the silhouette, which unlike
  a shrink cannot collapse or fold. It is 0.55 units everywhere except on
  `book_open_medium` and `book_open_large`, whose covers are the heaviest
  drawings in the set and against which a line that fine read as a hairline;
  there it is **1.10, added outward only**, so nothing inside the icon moves.

  `book_open_large`'s three filled icons join the rule here. They had been
  drawings of their own, and the drawings had never picked up a change their
  regular twins did: they were still showing six text rules against four.

  Three separate derivations, each offsetting its own cover, are replaced by
  that one function. They were the cause of every complaint about this family:
  a black line cutting across the white gutter of `book_open_medium`, tops that
  did not match the regular in `book_open_small` and `otzaria_icon`, and a
  `books_stacked_high` that read as a texture. It also means the text-rule
  changes below reach the filled variants on their own, because a filled icon
  now reads its regular twin.

  `otzaria_icon_2_page_24_filled` was worse than wrong: it had 21.6 square units
  of ink against its regular twin's 113, so it was shipping as a hairline
  outline rather than as a filled icon at all.

  Worth recording for the next person: **skia's offset is not reliable on these
  covers, and does not say so.** Eroding the otzaria cover's 351 units by 0.50
  returns 36, by 0.80 returns 294, and by 1.00 fails outright. Growing
  `book_open_large_lines`'s cover by 1.10 in one call returned **eleven
  fragments with a whole flank of the icon missing** - which shipped, briefly,
  as a filled book with no right-hand cover. The same offset taken in two
  halves returns the single contour it should, to within four hundredths of a
  square unit, so `grow` now takes any offset over 0.55 in steps. The erosion
  has carried a loud guard since the first time it collapsed silently.

- **Eased the square corners of `book_open_large`** (same names and codepoints,
  visual change to all six). That family draws its cover as a stepped frame and
  cut every step square, which beside the rest of the set - and beside Fluent,
  where nothing is square - reads as a spike. Each corner now has 0.85 cut off
  each of its edges, bridged by a curve through the point they used to meet at.

  This is the operation an earlier attempt at the same thing needed and did not
  have. That attempt - on the Latin letters of `document_word`, `document_html`,
  `document_md`, `book_word`, `book_md`, `book_pdf`, `book_zim` and
  `book_number` - was built on a morphological opening, which cannot tell a
  sharp corner that should be rounded from a thin stroke that should be kept:
  the W's strokes are 0.50 units, the safe radius was 0.09, the one used was
  0.30, and part of the letter was erased. All sixteen of those icons were put
  back as they were and are unchanged in this release.

  The measurements say the same thing about the books. A morphological rounding
  of `book_open_large` at 0.25 units already takes 99 square units off it, and
  at 0.35 skia refuses the operation outright. Filleting works on the path
  instead: where two straight segments meet at more than 25 degrees, each is
  trimmed and the gap bridged, and nothing but the corner moves. No stroke can
  be thinned and none can be erased, however fine it is. It is also exactly
  idempotent - a filleted corner is a curve, and a curve is not a corner - which
  is what lets a recipe that rewrites its own source recognise its own output.

- **Redrew the text on `torah_scroll_24_regular`** (same name and codepoint,
  visual change). At five rows the 1.64-unit pitch left 0.84 units of parchment
  between rules 0.80 thick - almost equal bands - so below 24 px the text block
  closed into a grey slab. It now carries **four rows at a 2.10 pitch**, leaving
  1.30 between them, which is the ratio that still reads as separate lines when
  each one is under a pixel. The block is centred in the parchment's own opening
  rather than on the canvas, so it stays centred if the scroll is redrawn.

  The scroll is then scaled up about the canvas centre until it fills it, and
  offset outward 0.04 afterwards: the enlargement thickens every line by the
  same factor it grows the drawing, and the offset adds about 10% on top of
  that.

- **Rebuilt `alef_with_eraser_24_regular` onto the badge** (same name and
  codepoint, visual change). It was the one alef in the family whose mark was
  not in a disc, and its eraser ran off the canvas: the artwork reached
  `x = 24.78`, three quarters of a unit past the 24-unit edge, and shipped
  clipped. The eraser is now Fluent's own, inside the disc.

- **Badge marks are taken from Fluent rather than drawn to resemble it.**
  A hand-drawn highlighter comes out as *a* highlighter rather than *the*
  highlighter, and beside the rest of a Fluent toolbar it reads as a different
  hand. Fluent ships no SVG in its Dart package, but a glyph outline is the
  same artwork, so `tool/fluent_art.py` reads the glyph out of
  `FluentSystemIcons-*.ttf` and maps it back onto the 24x24 canvas.

  Three things this needs, all in `docs/source_structure.md`. The mark comes
  from Fluent's **filled** font: the regular style is an outline drawn with
  1.5-unit strokes for a 24-unit canvas, and reduced to a badge a quarter that
  size those strokes land near 0.43 units - under half a pixel at 24 px - and
  print as nothing. The weight is **put back after scaling**: each mark is
  fitted by how far its ink reaches from the centre, which is the right measure
  for a round badge, then offset outward until its mean stroke is back near a
  pixel. And a hole too small to print - the eyes of the scissors' handles land
  at about a third of a unit - is **filled rather than kept**. Fluent solves the
  same problem by redrawing the mark at badge scale; `link_person`'s person is a
  plain solid head and body, not the person icon shrunk.

  There is a limit here worth recording, because it decides the rest. Restoring
  a stroke is also what closes a mark's gaps - growing the ink thickens it on
  *both* sides of every black line inside the mark - and at this size the two
  cannot both be had. A mark fitted to the alef's disc is scaled to about 0.29,
  so carrying a 0.9-unit stroke and a 0.8-unit gap would need a period of 1.7
  units where Fluent uses 3.0: a mark reaching 5.7 units inside a disc whose
  radius is 4.19. **So the gap wins** - it is what disappears first at 16 px -
  and the stroke is only brought up to 0.85. Two marks needed more than that
  rule alone: the eye's pupil is pulled back 0.20 off its lid, since a disc's
  size is a free parameter its lid's is not, and the lips' mouth is cut at 2.60
  rather than a Fluent stroke, being the one line the whole mark reads by.

  The mark takes 80% of the disc's radius, not the 68% it started at: at 16 px
  the badge is 5.6 pixels across, and a mark using two thirds of that is three.
  At 80% the ring of badge ink is still 0.85 units, which is what keeps the disc
  reading as a disc, and the minimum stroke goes to 1.00 with it.

  The marks that are objects rather than letters are turned: the highlighter
  sits at 45 degrees clockwise, nib to the lower left and barrel up to the
  right, which is the angle a pen is actually held at - upright it reads as a
  bottle - and the scissors lie almost flat at -95, where the blades lead and
  the handles sit behind them. Upright, their two rings stack under the blades and
  the mark reads as a keyhole. The scissors are also the one mark left *below*
  the default weight, at 0.62: Fluent's cut is already the heaviest mark here -
  a 1.88 mean stroke against the others' 1.0 to 1.5 - and bringing it up to the
  default fattened the blades into each other and cost the mark its point.

  The information badge is the one place Fluent's glyph could not be used
  whole. `info_24_filled` is a disc with the letter knocked out of it, so on a
  badge that is already a disc it produced a ring with a dark letter lost in the
  middle. What such a badge needs is the letter alone - the hole in Fluent's
  glyph - which can then be set far larger, and the whole badge reads as one
  mark.

  The sixteen icons that do this are `modified_fluent` in the manifest and are
  listed in `THIRD_PARTY_NOTICES.md`. `compose_sources.py --provenance` writes
  those fields from what the recipes actually fetched, so the record cannot
  drift from the artwork.

  Two marks are the exception and stay `custom`. Fluent has no lips icon, so
  `alef_lips_24_regular` is drawn - but to Fluent's rules, as one stroke of
  Fluent's weight with rounded ends and no taper, and put through the same
  fitting and re-weighting every Fluent mark here takes. And
  `alef_lock_24_regular`'s padlock is drawn because Fluent's cannot survive the
  reduction, for the reason given above.

- **Checked whether this set's existing link artwork was Fluent's, and it is
  not.** Worth knowing, because it is a licensing claim: `links_24_regular` was
  compared against Fluent's `link`, `link_multiple` and `link_square` and
  differs from the closest by 87% of its area, and the mark inside
  `book_link_24_regular` differs from Fluent's link, scaled onto the same box,
  by 44%. Both are the same idea drawn independently. Their `origin: custom` is
  correct and is left alone.

- **Widened and weighted `alef_rashi_24_regular`** (same name and codepoint,
  visual change). It was the narrowest letter in the set at 10.32 units across,
  against the square alef's 14.85, and the lightest at a mean stroke of 1.64
  against 2.08 - so beside its siblings it read as a finer hand rather than as
  the same letter in another script. It is widened 22% horizontally, which is
  what a Rashi alef's proportions will take, and then offset outward 0.13 units
  everywhere, which adds 0.26 to every stroke including the horizontal ones the
  widening left alone. The result is 12.84 units across at a mean stroke of
  2.09, which is the square alef's weight to within 0.02.

- **Fixed a latent bug in `tool/generate.dart`'s manifest writer.** Provenance
  is free text, and one field already contains `": "` - the `based_on` of
  `search_in_the_quote_24_regular` names a path inside the Fluent repository.
  The writer emitted every such field bare, so that value came back out as a
  nested mapping key and the manifest stopped parsing. It only surfaced now
  because it takes appending an icon *after* that record to trigger a rewrite.
  Free-text fields are now quoted when writing them bare would not read back as
  the same string.

- **Checked the rounded ends on the `document` family's rules, and they were
  already even.** Every rule in `document_column`, `document_bullet_list` and
  the `text_*` / `list_*` / `clipboard_*` icons that share their construction is
  an exact stadium: measuring each rule's four corner radii from its own
  bounding box gives 0.750 at every corner of a 1.500-unit rule, top and bottom
  alike. Nothing needed changing. Two findings from the same sweep are left for
  a decision rather than repaired here: the rules inside
  `book_open_large_lines`, `book_open_large_search` and `book_open_small_line`
  are hand-drawn and their radii scatter between 0.16 and 0.74 within a single
  icon, and one corner of the top rule in `list_24_filled` is 1.066 where its
  other three are 1.000.

- **The composer builds in dependency order, and treatments compose.** A filled
  icon is built from its regular's *file*, and several regulars are recipes that
  rewrite their own file - so in plain alphabetical order every filled icon was
  built from the previous run's regular and caught up only on the run after.
  Recipes now declare what they read and are ordered by it, so one run is
  enough. An icon's recipe is likewise a chain of steps rather than one
  function: redraw the text, ease the corners, fill the canvas. Each step knows
  how to recognise its own output and stand down, and the icon is reported
  unchanged only when every step has.

- Added the composition tooling: `tool/icon_compose.py`, the geometry toolkit,
  `tool/fluent_art.py`, which reads a Fluent glyph out of the pub cache's font,
  and `tool/compose_sources.py`, which states each composed icon as a recipe
  against the committed sources and rebuilds it. The badge disc in a new icon is
  not a copy of the disc, it *is* the disc, read out of `alef_copy_24_regular`
  at build time - so redrawing the alef a third time will carry into every icon
  that holds one. See
  [docs/source_structure.md](docs/source_structure.md#composing-an-icon-out-of-the-artwork-already-here).

- Added nine icons, which the reallocation above placed at
  `U+E08A`-`U+E091`.

  * `beit_24_regular` - the beit as a letter icon in its own right. The
    letterform is the one already drawn in `beit_near_alef_24_regular`, where it
    stands beside a full-size alef at roughly half its height. Enlarged to a
    19.20 unit height it carries far too much ink for the family, so every flank
    of the outline is then eroded 0.45 units - one amount for every stroke,
    never graded - which takes 0.90 off each stroke's width while leaving its
    centre line, and so the letter's spine, exactly where it was. The result is
    13.67 x 18.17, the tallest letter in the set after the alef (19.26) and the
    lightest (mean stroke 2.45 units against alef's 2.61 and tet's 2.69).

  * `document_html_24_{regular,filled}`, `document_md_24_{regular,filled}` and
    `document_tet_24_{regular,filled}` - the `document_word` page, unchanged
    down to the folded corner, with a new letter block. The single letters keep
    the W's cap height and baseline (6.44 units tall, y 11.06-17.50); `MD` is
    two letters, so it drops to 4.63 units to hold the same 1.5 unit margin from
    the page's inner rule that the `book_*` letter blocks use. `MD` reuses the
    letterforms from `book_md_24_regular` and the tet is the `tet_24_regular`
    letter at 9.00 units, placed like the tet in `book_tet_24_regular`. Each
    filled variant knocks its letters out of the solid page.

  * `search_in_the_quote_24_regular` - the family's magnifier with a pair of
    quote marks in the lens, scaled so their ink reaches 4.96 units from the
    lens centre, within the 4.6-5.1 the rest of the family's lens content uses.
    This is the package's first `modified_fluent` icon: the marks come from
    Fluent's `text_quote_24_regular`, so `THIRD_PARTY_NOTICES.md` is no longer
    empty.

  * `alef_copy_24_regular` - the solid alef with a copy badge at the bottom
    right, on the same badge in the same place as `alef_deletion_24_regular` and
    `alef_with_information_24_regular`. Fluent draws copy as two outlined
    sheets; at badge scale its 1.5-unit rings would fall to 0.4 and vanish, so
    the sheets are cut out solid with 0.6 units of badge ink between them.

- Doubled the line weight in `torah_scroll_24_regular` (same name and codepoint,
  visual change). The ten lines of text went from 0.41 to 0.80 units and the
  parchment's top and bottom rails from 0.42/0.46 to 0.80, thickened inwards so
  the scroll's silhouette is untouched. At 0.41 the text was invisible below
  32 px and read lighter than the rollers it sits between; 1.00 was tried and
  closed the 1.64-unit line pitch into a barcode.

- **Redrew the alef letterform** across the 21 icons that carry it (same names
  and codepoints, visual change). The letter is no longer the one that has been
  patched stroke by stroke since 0.3.0: it is traced from a drawing supplied by
  the maintainer, so its curves are the drawing's curves rather than the
  accumulated result of a dozen local corrections.

  The trace reads the drawing's greyscale, not a thresholded bitmap: every
  boundary point sits where the ink crosses half coverage, which is accurate to
  a fraction of a pixel and leaves no staircase to smooth away afterwards. It is
  refitted as **78 cubics over 5 corners** at a tolerance of 0.025 units.
  Rendered back at the drawing's own resolution, 1.4% of the letter's pixels
  differ from it, and every one of them is in a rim less than a pixel wide.

  The letter is placed at the family's own alef height and centre: 14.85 x 19.20
  units against 15.17 x 19.26 before, so its box narrows by 0.32 and its centre
  does not move. Fitting it to the old box instead would have stretched it by
  2% in one axis only.

  `tool/replace_alef.py` found and swapped all 23 instances. It matches by shape
  - a contour is an instance when, scaled and placed on the letterform's box, it
  differs from it by under 5% of its area - because the family holds book
  covers, document bodies and a tet whose boxes have the alef's proportions and
  which a bounding-box test matches by the dozen. Four small alefs are not
  copies of the letterform but separate, simpler drawings of it, 0.13 to 0.46
  away; they are named explicitly in the tool and replaced too, because each one
  shares an icon with a full-size alef and would otherwise have left the old
  letterform standing beside the new one.

  `alef_24_regular` is the letterform hollowed out rather than a copy of it, so
  it is rebuilt as the new letterform minus its own 0.48-unit inset - the width
  that reproduces the drawn outline to within 4% of its area.
  `alef_stam_24_regular` and `alef_rashi_24_regular` are different letterforms
  and are untouched.

## 0.3.0 - 2026-09-08

- Added `alef_alef_24_regular` (`U+E089`): two alefs of equal size side by side,
  laid out to match `tet_tet_24_regular` exactly - each letter 10.80 units wide
  at x 0.95 and x 12.25, a 0.5 unit gap, optically centred. The set now ships
  **138** icons over a contiguous `U+E000`-`U+E089`.

- Opened up `document_column_24_{regular,filled}`: the gap between the two
  columns goes from 0.5 to 1.0 units and the gap between rows from 1.5 to 2.0
  (row pitch 3.0 to 3.5). The bar block keeps its position and extent, so the
  bars shorten from 5.0 to 4.5 units. The filled variant's bars are knocked out
  of the document rather than drawn on it, and that winding is preserved.

- Removed committed temporary files and stopped them recurring: Flutter's
  golden-comparison output in `test/failures/` and the Python bytecode in
  `tool/__pycache__/` were both tracked. Both are now in `.gitignore`.

- Documented every tool. `docs/architecture.md` now carries a complete inventory
  of `tool/`, grouped by whether the generator runs it, it maintains sources, or
  it is one-off preparation. `flatten_svg_transforms.dart` and
  `scale_svg_paths.dart` had no documentation at all; `glyph_geometry.py` and
  `check_glyph_coverage.py` appeared only in a historical review.

- **Set the alef letterform lighter** across the 16 icons that carry it (same
  names and codepoints, visual change): every stroke is 15% thinner, the
  upper-right leg is 0.6 units shorter, and the outline has had a finishing
  pass. The letter is the same letter, in a regular weight instead of a bold
  one.

  Three rules do the work, and each replaced something that looked wrong:

  * **One factor for every stroke.** Grading it - thinning a leg's thick end
    more than its thin end - was tried twice and looked wrong both times. The
    only available measure of local stroke width is the inscribed circle, and
    along these legs it is not monotone (0.36, 0.87, 0.39, 0.82, 1.58, 0.47)
    because the outline turns concave. A factor keyed to it jumps, and a
    displacement that jumps along an edge tilts that edge instead of thinning
    it: the concave sweep below the upper-right leg came out as a straight
    chord with a corner at each end. The first attempt also flattened the legs'
    width contrast from 6.6:1 to 2.1:1, which turns a calligraphic hand into a
    nearly monolinear one - a different letter, not a lighter one.

  * **Joins are held, not thinned.** A flat percentage takes ink off the joins
    too, and the joins are the thinnest places in the letter: the lower-left
    join dropped from 0.697 units of ink to 0.550 until it read as a gap. No
    point may now move so far inward that the ink anywhere falls below the
    letter's own original minimum of 0.70 units. The join measures 0.701 in the
    result.

  * **The outline is finished, not just moved.** Joins drawn smooth are made
    exactly smooth, node tremor is eased out within a bounded 0.11 units, and
    every corner the designer drew is kept at its drawn angle. The median kink
    at a node is now 0.00 degrees against 0.74 as digitised, and three quarters
    of all nodes are perfectly smooth, while the sharpest corners are unchanged
    at 101.6 and 112.6 degrees.

  Quadratic segments are elevated to cubics first. A quadratic's single control
  point governs the tangent at both of its ends, so a correction at one end
  undoes the other; that alone had capped smoothing at a 2.45-degree median.

  Two icons keep a hairline artefact where the thinned letter pulled away from
  a shape behind it: `alef_behind_alef_24_regular` (0.012 sq units) and
  `alef_24_regular` (0.003 sq units, emergent from its counter pinching). Both
  are far below one pixel at icon sizes.

  `alef_stam` and `alef_rashi` are different letterforms and were excluded. The
  reduced alef inside `book_alef_24_{regular,filled}` and the alef in
  `text_alef_bet_list_24_regular` are separately drawn letters rather than
  copies of this one - shape distance 0.139 and higher, where every icon above
  matches at 0.000 - so they were left alone and need their own pass.

- Added `tool/restroke_alef.py`, which performs the above and records why each
  rule is there.

- Restructured every source in `assets_src/svg/` into one canonical written
  form, with **no change to what any icon draws**. The files had been produced
  by several different editors and patched by hand over years: each was a single
  unbroken line, coordinates carried up to sixteen decimals of float noise
  (a corner meant to sit at `22` was written `21.999998`), absolute and relative
  commands and arcs and smooth-curve shorthands were mixed arbitrarily, and
  repeated edits had left zero-length segments and duplicated points behind.
  Sources are now absolute-only, one contour per line, `H`/`V` for axis-aligned
  edges, free of degenerate geometry, and rounded to a decimal precision chosen
  per file - the coarsest that provably does not move that file's outline (three
  decimals for 131 of 137 sources). Source size dropped from 819 KB to 575 KB.
  See [docs/source_structure.md](docs/source_structure.md).

- Gave shared artwork one spelling across each family: 94 contours in 36 files.
  The same book cover had existed in six different spellings of the same shape
  and the same document body in nine, so changing a shared part meant finding
  and editing every copy by hand. The book cover is now one identical contour
  across 32 icons. Only contours that were already the same shape were touched,
  so nothing was redrawn.

- The font, catalog, gallery and golden were regenerated from the restructured
  sources. Every icon is graphically unchanged: the resolved outline moves at
  most 0.002 canvas units anywhere (0.002 px at 24 px), verified two independent
  ways - an exact vector-region comparison and an Inkscape pixel comparison at
  16, 20, 24, 32 and 48 px, whose worst case is 9 of 576 pixels differing by at
  most 7% of one grey level, the signature of a subpixel edge shift.

- Removed the geometric debris that years of hand-patching had left in the
  outlines. Across the set: **67 specks** (separate filled contours far too
  small to be design - median 0.00005 square units, slivers that paint
  nothing), **6 self-crossing contours**, **3 hairline slivers** where an
  outline doubled back on itself, **412 duplicated points**, and **140
  whiskers** jutting off otherwise smooth outlines. The self-crossings mattered
  most: they rendered correctly only because their coordinates happened to land
  where they did, so any nearby edit could have flipped a large area black or
  white without warning.

  This is the one change in this release that touches the artwork, and it stays
  far below anything visible: at 16 px only two icons change at all, by at most
  3 pixels of 256 and 4% of one grey level. Removing every whisker from the
  alef, bookshelf and dependent-library icons leaves all three pixel-identical
  at 500 px. What is gone is only visible under heavy magnification, which is
  where it was showing up.

  A side effect confirms the debris was debris: before the cleanup, six sources
  carried "detail" below a thousandth of a unit and needed 4-6 decimals to write
  losslessly. Afterwards 136 of 137 fit in three decimals.

  The audit's `thin ink` and `thin gap` findings were deliberately left alone -
  those are design decisions, not debris, and widening a stroke is a redraw.

- Added the tooling that produced and verifies all of the above:
  `tool/format_svg.py` (canonical form), `tool/unify_shared_parts.py` (one
  spelling per shared part), `tool/family_report.py` (what families share and
  where they have drifted), `tool/audit_geometry.py` (specks, spikes, slivers,
  needles, self-crossing contours, and features too thin to survive at 16 px),
  `tool/repair_artifacts.py` (removes that debris, one bounded pass per defect
  category), `tool/region_diff.py` and `tool/raster_diff.py` (the two
  independent proofs of what a rewrite did and did not change). Every tool
  verifies each edit against the resolved region and keeps it only if the icon
  stayed inside that pass's limit.

- Refined `book_open_tzurat_hadaf_24_{regular,filled}` further (same names
  and codepoints, visual-only): the glyph is ~1.2x larger, and the center
  block is now a portrait rectangle (taller than wide, like an actual page)
  rather than a square, since the top arm has far less vertical room before
  its own tab than the bottom arm does. The horizontal gap grew a little at
  the expense of the page arms' width; the bottom vertical gap shrank in
  favor of a taller bottom arm. The `regular` outline is now one constant
  stroke thickness applied as a true offset everywhere, replacing a
  hand-placed inner boundary that varied between 0.75 and 0.9 per segment.

- Redrawn `book_open_tzurat_hadaf_24_{regular,filled}` (same names and
  codepoints): the center block no longer straddles the two page columns —
  the columns now recess around it with a uniform gap, removing the 3D
  "square resting on cylinders" look reported in Otzaria issue #904.

- Renamed `book_open_alef_24_{filled,regular}` to `book_alef_24_{filled,regular}`
  (same codepoints `U+E068`/`U+E069`; no backward-compatible aliases).
- Added `clock_add_24_regular` and `search_in_the_person_24_regular`.
- Expanded the set to **110 icons** (from 62), adding the `alef_*` family,
  additional book/document/list variants, `calendar`, `person`, `search`,
  clipboard/task-list and RTL text-list icons. Codepoints were appended after
  the existing range (through `U+E06D`); no previously shipped codepoint was
  reassigned.
- Fixed glyph corruption affecting 34 icons whose independent `<path>` layers
  overlapped or seamed: correct in the browser and catalog, but merged into one
  nonzero-fill glyph the font rendered unintended white holes, hairline seams,
  and (worst case, `book_open_large_search_24_filled`) a shredded quadrant.
- Added `tool/normalize_svg_overlaps.py`, which `simplify`s and boolean-unions
  each icon's paths into one clean, non-overlapping, consistently-wound outline
  identical to the catalog, and normalized all 107 affected/at-risk sources.
- Preserved the three intended interior knockouts (`document_word_24_filled`,
  `document_bullet_list_24_filled`, `book_alef_24_filled`), which the tool
  detects and skips.
- Added a CI check (`normalize_svg_overlaps.py --check`) that fails when a
  committed source still contains overlapping or seaming paths.
- Added `tool/repair_glyphs.py`, run as the final generation step, which
  rewrites every glyph outline directly from its source SVG. The pinned
  `icon_font_generator` distorts some complex glyphs during outline conversion
  (a ~4-unit horizontal shift on `book_open_large_search_24_filled`, contour
  damage on `stander_24_filled` and `search_in_the_text_24_regular`) even from
  clean sources; this makes every glyph match the catalog exactly. Interior
  knockouts (`document_word`, `document_bullet_list`, `book_alef`) are
  rebuilt as a boolean difference (body minus the cut) so the cut is transparent
  regardless of source winding — this fixed the alef in `book_alef_24_filled`,
  which had rendered solid black. Deterministic; preserves the fixed font
  timestamp and all generator metadata. Generation now requires Python 3 with
  pinned `skia-pathops` and `fonttools` (`tool/requirements.txt`).

- Hardened the generation pipeline: `generate.dart` now runs the
  `normalize_svg_overlaps.py --check` gate so overlapping/seaming sources can no
  longer be generated, `validate.dart` enforces append-only contiguous
  codepoints from `U+E000`, and the manifest's `deprecated` /
  `match_text_direction` flags now flow into the generated API.
- Removed the 10 legacy icon names from the former personal repository; their
  artwork now exists under the renamed official icon set.
- Reallocated the official icon manifest from `U+E000` without deprecated
  aliases or backward-compatibility entries.
- Added a generated, searchable Hebrew icon catalog for GitHub Pages with an
  adjustable preview size.
- Corrected stroke expansion for 11 restored source icons and preserved
  presentation attributes inherited from the root SVG element.
- Preserved white mask and stroke artwork as transparent knockouts in filled
  monochrome glyphs, including PDF, Word, ZIM, upload, search, and link marks.

## 0.2.0 - 2026-07-19

- Added 52 original Otzaria icons while preserving all 10 previously published
  names and codepoints.
- Moved repository metadata and installation links to the official
  `Otzaria/otzaria_icons` repository.
- Added a vector-safe Inkscape preparation tool for strokes, text, masks,
  shapes, transforms, and non-24 canvases.
- Canonicalized every committed SVG to direct filled 24x24 paths without
  retaining raster data or renderer-dependent SVG features.
- Corrected spelling in new public names before allocation and documented
  common SVG export mistakes and their safe fixes.
- Made the multi-size Windows golden grow automatically with the icon manifest.

## 0.1.3 - 2026-07-17

- Increased the optical size of the restored `book_open_lines`,
  `book_open_lines_search`, and `search_full` designs by 12% around the canvas
  center, preserving their proportions and native 24x24 geometry.
- Replaced the overly dense `book_open_lines_24_filled` geometry with the
  original readable regular outline so it remains recognizable at 16-24 px.
- Added a reusable native-path scaling tool and updated the multi-size visual
  golden.

## 0.1.2 - 2026-07-16

- Restored the original visual designs of `book_open_lines`,
  `book_open_lines_search`, and `search_full` in both variants.
- Flattened their existing transforms mathematically into native 24x24 path
  coordinates without redrawing or simplifying the artwork.
- Consolidated the GPLv3 license into one canonical `LICENSE` file.
- Documented automatic GPL-3.0-only licensing for accepted contributions and
  the required valid SVG structure.
- Strengthened SVG validation and added a reusable transform-flattening tool.

## 0.1.1 - 2026-07-16

- Rebuilt `book_open_lines`, `book_open_lines_search`, and `search_full`
  regular/filled glyphs with native 24×24 geometry for correct 16–24 px
  rendering.
- Replaced the 80 px-only golden with coverage at 16, 20, 24, 32, and 48 px.
- Reject SVG transforms and non-native canvases to prevent small-size glyph
  regressions.
- Added a generated visual icon catalog and links to Otzaria and Microsoft
  Fluent UI System Icons.

## 0.1.0 - 2026-07-16

- Initial package structure and SVG validation pipeline.
- Manifest-driven deterministic OTF and Dart generation.
- Five initial regular/filled icon pairs.
- GPL-3.0-only licensing for the package and original icon artwork.
- Example gallery and minimal tree-shaking proof application.
- Windows, Android, and Web release validation.
- Detailed installation, usage, SVG, contribution, testing, architecture, and
  release documentation.
- Read-only generation drift checks and generated provenance notices.
- GitHub CI plus manual Linux/macOS pre-release validation.
