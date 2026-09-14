#!/usr/bin/env python3
"""Build the composed icon sources from the artwork already in the set.

Each recipe below states one icon as an operation on committed sources, so the
shared parts of a family stay identical rather than merely similar, and a later
change to a shared part (the alef was redrawn twice already) propagates by
re-running this instead of by hand-patching every file that carries it.

  python3 tool/compose_sources.py                 # rebuild every composed icon
  python3 tool/compose_sources.py alef_scissors_24_regular ...
  python3 tool/compose_sources.py --list

Some recipes draw on Microsoft's Fluent artwork (see `tool/fluent_art.py`), and
that has to be recorded per icon. The full sequence is:

  python3 tool/compose_sources.py       # sources
  python3 tool/format_svg.py            # canonical written form
  dart run tool/generate.dart           # allocates records, builds everything
  python3 tool/compose_sources.py --provenance   # records what came from where
  dart run tool/generate.dart           # regenerates THIRD_PARTY_NOTICES.md

`--provenance` writes no source of its own, so it can be run after the sources
have been formatted without undoing that.

Requires: skia-pathops, fonttools.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import icon_compose as ic
import fluent_art
from icon_compose import (Art, circle, glyph, part, polygon, round_rect,
                          taper, write)

# --------------------------------------------------------------------------
# The badge
# --------------------------------------------------------------------------
# The alef family already carries three badged icons. Two of them (alef_copy,
# alef_with_information) share one disc; alef_deletion was drawn with a slightly
# different one (0.2 units right, 0.15 up, a shade larger). The shared one is
# the canonical disc, and every alef badge composed here is placed on that exact
# path, so the badges line up across the family instead of drifting further.
BADGE_SOURCE = ("alef_copy_24_regular", 1)
BADGE_CX, BADGE_CY = 16.415, 17.667

# How far a mark's ink may reach from the disc's centre, as a fraction of the
# disc's radius. A mark going into a round badge is fitted by reach, not into a
# square box: the corners a box reserves fall outside the circle anyway, so
# box-fitting leaves a wide flat mark - an eye, a pair of lips - visibly
# undersized beside a compact one. Set from what is already on these discs:
# Fluent's cross reaches 3.56 of its disc's 5.495, and this set's copy badge
# 3.2 of 4.19.
SYMBOL_REACH = 0.68

# What a mark's ink must not fall below once it is badge-sized. Fluent's marks
# are drawn with 1.5-unit strokes for a 24-unit canvas; scaled into a badge a
# quarter that size those strokes land near 0.43 units, which is under half a
# pixel at 24 px and simply disappears. Fluent solves this in its own badged
# icons by redrawing the mark at badge scale - `link_person`'s person is a plain
# solid head and body, not the person icon shrunk. Here the shape is kept and
# the weight is put back: the mark is offset outward until its mean stroke
# reaches this.
#
# It is deliberately modest, because restoring stroke weight is also what
# closes a mark's gaps: growing the ink thickens it on *both* sides of every
# black line inside the mark. At this size the two cannot both be had. A
# Fluent mark fitted to the disc is scaled to about 0.29, so its 1.5-unit lines
# land at 0.43; carrying a 0.9-unit stroke and a 0.8-unit gap would need a
# period of 1.7 units where Fluent uses 3.0, which is a mark reaching 5.7 units
# inside a disc whose radius is 4.19. So the gap is given priority - it is what
# disappears first at 16 px - and the stroke is only brought up to here.
BADGE_MIN_STROKE = 0.85

# An enclosed hole below this area is filled instead of kept. At badge scale the
# eyes of the scissors' handles land at about a third of a unit across, which
# prints as a smudge rather than as a hole; Fluent redraws marks at badge size
# for the same reason.
BADGE_MIN_HOLE = 0.55


def badge():
    return part(*BADGE_SOURCE)


def alef_solid():
    """The solid alef exactly as the existing badged icons spell it."""
    return part("alef_copy_24_regular", 0)


def place(art):
    """Centre a symbol drawn about the origin on the badge."""
    return art.centred_on(BADGE_CX, BADGE_CY)


def weighted(art, reach, weight=BADGE_MIN_STROKE):
    """Fit a mark to `reach` units of ink from its centre, then put its stroke
    weight back, and centre it on the origin ready for `place`.

    Re-growing after scaling also closes the counters of an outlined mark -
    which is what makes the eraser and the copy sheets read as solid shapes
    rather than as rings too fine to survive - so the result is the Fluent
    drawing at badge scale, not a Fluent drawing with detail too small to print.
    """
    art = art.fit_radius(reach)
    have = art.mean_stroke()
    if have and have < weight:
        art = art.grow((weight - have) / 2)
    return art.fill_holes(BADGE_MIN_HOLE).centred_on(0, 0)


# Which Fluent icons the recipe currently building has drawn on. Provenance has
# to be recorded per icon and must not drift from what was actually used, so it
# is collected as the artwork is fetched rather than kept in a second list that
# someone has to remember to update.
_USED = []


def use_fluent(name):
    if name not in _USED:
        _USED.append(name)
    return fluent_art.art(name)


def fluent(name, reach, weight=BADGE_MIN_STROKE):
    return weighted(use_fluent(name), reach, weight)


# --------------------------------------------------------------------------
# Badge symbols, drawn about the origin
# --------------------------------------------------------------------------
def sym_cross():
    """The deletion cross, recentred from its own slightly-offset disc."""
    return part("alef_deletion_24_regular", 2)


def sym_plus():
    """The deletion cross stood upright.

    Not the cross rotated: rotating it about its centre would put the arm ends
    on the axes and make the mark 1.41x wider, and scaling that back down would
    thin every stroke by the same factor - a lighter badge, not the same badge
    turned. So the plus is drawn to the cross's own measurements instead: the
    same arm half-length (its bbox half-width) and the same bar thickness,
    solved from its filled area for a cross of that reach.
    """
    x0, y0, x1, y1 = sym_cross().bounds
    a = max(x1 - x0, y1 - y0) / 2           # arm half-length
    area = sym_cross().area
    # area of a plus with arm half-length a and bar thickness t: 4at - t^2
    t = (4 * a - ((4 * a) ** 2 - 4 * area) ** 0.5) / 2
    r = t * 0.16                            # the cross's ends are barely eased
    return (round_rect(-a, -t / 2, a, t / 2, r)
            | round_rect(-t / 2, -a, t / 2, a, r))


def sym_exclamation():
    """A bar over a dot, at the "i"'s weights so the pair reads as one family.

    Drawn rather than mirrored from the information badge: that "i" has a serif
    foot, and mirroring puts the serif on top of the exclamation, where it reads
    as a bracket instead of a stroke.
    """
    bar = (taper((0, -2.35), (0, 0.45), 1.40, 1.00)
           | circle(0, -2.35, 0.70)
           | circle(0, 0.45, 0.50))
    return bar | circle(0, 2.15, 0.78)


# Marks taken from Fluent rather than drawn. Fluent's own filled style is the
# right source for a knockout: the regular style is an outline, and an outline
# reduced to badge scale is a ring too fine to print.
FLUENT_SYMBOLS = {
    # Laid almost on their side. Fluent draws cut with the blades up and the
    # handles down; upright inside a badge the two rings stack under the blades
    # and the mark reads as a keyhole. Turned this far the blades lead left and
    # the handles sit behind them, which is the silhouette that says scissors.
    "scissors": ("cut_24_filled", -75),
    "eraser": ("eraser_24_filled", 0),
    # Fluent draws the highlighter head-on and upright. A pen held upright in a
    # badge reads as a bottle; on the diagonal it reads as a pen, and it is also
    # the angle the eraser beside it already sits at.
    "marker": ("highlight_24_filled", -40),
    "eye": ("eye_24_filled", 0),
    "quote": ("text_quote_24_filled", 0),
    "document": ("document_24_filled", 0),
    # Fluent's info "i" is a fine stroke inside a disc; on a badge it needs more
    # weight than the marks that are shapes rather than letters.
    "information": ("info_24_filled", 0),
}

# Marks that want a heavier stroke than the default, because they are letters or
# fine rules rather than solid shapes.
SYMBOL_WEIGHT = {"information": 1.25}


def sym_fluent(kind, reach):
    name, turn = FLUENT_SYMBOLS[kind]
    # Turn before fitting, so `reach` still means what it says: a mark measured
    # upright and then rotated reaches further than it was fitted to.
    art = use_fluent(name)
    if turn:
        art = art.rotate(turn, about=art.centre)
    return weighted(art, reach, SYMBOL_WEIGHT.get(kind, BADGE_MIN_STROKE))


def sym_eye(reach):
    """Fluent's eye, with the pupil pulled back off the lid.

    Fluent draws it as a lid arc with a solid pupil under it, and leaves about
    1.2 units between them. Restoring the arc's weight at badge scale spends
    most of that, and the two run together into a blob - the thing that stopped
    this reading as an eye. Since the pupil is a disc, its own size is a free
    parameter the arc's is not: taking a little off it opens the gap back up
    without touching the shape that carries the reading.
    """
    art = weighted(use_fluent("eye_24_filled"), reach)
    parts = ic.contours(art)
    pupil = min(parts, key=lambda c: c.area)
    lid = Art()
    for c in parts:
        if c is not pupil:
            lid = lid | c
    return (lid | pupil.shrink(0.20)).centred_on(0, 0)


def sym_copy():
    """The copy mark this set already draws, reused rather than replaced.

    Fluent's own copy is two outlined sheets; at badge scale its 1.5-unit rings
    fall to 0.4 and vanish, so `alef_copy_24_regular` cuts the sheets out solid
    with badge ink between them instead. That adaptation is already the right
    drawing for a disc this size, so the link badge takes it rather than
    reducing Fluent's again and getting a different answer.
    """
    return part("alef_copy_24_regular", 2)


def sym_cross_mark():
    """The cross Fluent knocks out of its own badged link, taken from the
    template rather than drawn, so `link_deletion` is Fluent's dismiss exactly.
    """
    _, disc, inside = link_plate()
    return inside


def sym_lips(reach):
    """Lips, drawn to Fluent's rules because Fluent has no lips icon to take.

    Those rules are what the rest of the badge marks are made of: a 1.5-unit
    stroke on the 24-unit canvas, ends and joins rounded, no taper inside a
    stroke. So the mouth is one stroke of that weight, closed at the corners,
    with the cupid's bow bent into its upper edge and the fuller curve of the
    lower lip below - not two solid lenses, which is what made the first attempt
    read as a coin slot. It is scaled and re-weighted by the same path every
    Fluent mark here takes, so it carries the same ink.
    """
    outer = Art.from_d(
        "M 2.00 11.60 "
        "C 4.60 7.40 6.90 5.60 8.90 6.20 "
        "C 10.40 6.65 11.43 7.75 12.00 9.50 "
        "C 12.57 7.75 13.60 6.65 15.10 6.20 "
        "C 17.10 5.60 19.40 7.40 22.00 11.60 "
        "C 19.40 16.60 16.07 19.10 12.00 19.10 "
        "C 7.93 19.10 4.60 16.60 2.00 11.60 Z")
    # The mouth is cut wider than a Fluent stroke on purpose. It is the one
    # line that carries the whole reading - close it up and the mark is an
    # almond - and `widen_gaps` afterwards would open it anyway; cutting it here
    # instead keeps the two lips the shape they were drawn, rather than having
    # both of them pushed back from a line that started too fine.
    mouth = ic.curve([(2.00, 11.60), (7.00, 13.10), (17.00, 13.10),
                      (22.00, 11.60)], 2.60)
    return weighted(outer - mouth, reach)


# Marks already drawn at badge scale for the alef's disc, which is the only disc
# they go on: they take neither scaling nor re-weighting.
DRAWN_SYMBOLS = {
    "plus": sym_plus,
    "exclamation": sym_exclamation,
}


def symbol(kind, reach):
    """The mark for `kind`, centred on the origin, reaching `reach` units."""
    if kind in DRAWN_SYMBOLS:
        return DRAWN_SYMBOLS[kind]().centred_on(0, 0)
    if kind == "copy":
        # Already at badge weight; it only needs the disc it is going on.
        return sym_copy().fit_radius(reach).centred_on(0, 0)
    if kind == "lips":
        return sym_lips(reach)
    if kind == "cross":
        return weighted(sym_cross_mark(), reach)
    if kind == "eye":
        return sym_eye(reach)
    return sym_fluent(kind, reach)


def badged(base, kind):
    """base + the alef family's disc, with `kind` knocked out of the disc."""
    disc = badge()
    return base | disc, [place(symbol(kind, disc.radius() * SYMBOL_REACH))]


# --------------------------------------------------------------------------
# Recipes
# --------------------------------------------------------------------------
def alef_badge(kind):
    def build():
        solid, cuts = badged(alef_solid(), kind)
        return solid, cuts, True
    return build


# --------------------------------------------------------------------------
# The link plate: Fluent's own badged-link layout
# --------------------------------------------------------------------------
# Fluent already badges its link, and does it with exactly this concept - a
# solid disc at the bottom right with the mark knocked out of it, and the link
# itself cut back to clear the disc. `link_dismiss_24_regular` is that layout
# with a cross in the disc, so it is taken apart and reassembled rather than
# imitated: the link comes back with Fluent's own cut-back, and the disc is
# Fluent's own circle in Fluent's own place.
LINK_TEMPLATE = "link_dismiss_24_regular"

def link_plate():
    """(cut-back link, disc, the mark in the disc) from Fluent's badged-link
    template.

    The template's contours are the disc, the link's three pieces, and the
    cross knocked out of the disc. They are told apart by containment rather
    than by index: the disc is the contour that holds another, the mark is what
    it holds, and the link is everything else - which stays true if Fluent
    renumbers its outline.
    """
    art = use_fluent(LINK_TEMPLATE)
    cs = ic.contours(art)
    disc = max(cs, key=lambda c: c.area)
    held = [c for c in cs if c is not disc and (c & disc).area > 0.9 * c.area]
    rest = [c for c in cs if c is not disc and c not in held]
    link, mark = Art(), Art()
    for c in rest:
        link = link | c
    for c in held:
        mark = mark | c
    return link, disc, mark


def link_badge(kind):
    """Fluent's link, cut back, with `kind` knocked out of Fluent's disc."""
    def build():
        link, disc, _ = link_plate()
        x0, y0, x1, y1 = disc.bounds
        mark = symbol(kind, disc.radius() * SYMBOL_REACH).centred_on(
            (x0 + x1) / 2, (y0 + y1) / 2)
        return link | disc, [mark], True
    return build


# --------------------------------------------------------------------------
# The alef in two weights at once
# --------------------------------------------------------------------------
def alef_half():
    """alef_24_filled on one side of a falling diagonal, alef_24_regular on the
    other.

    The cut is the line x + y = k through the letter's own centre: the diagonal
    from the canvas's top-right corner to its bottom-left, with the solid half
    below and to the right of it. That is the diagonal *across* the alef's
    dominant stroke rather than along it, which is what makes the two weights
    read as two halves of one letter instead of as one stroke inked and another
    not.

    The two halves are butted, not gapped. A seam wide enough to see at 300 px
    is a fifth of a pixel at 24 px - invisible where the icon is actually used,
    while still producing slivers in the outline half where the cut grazes a
    stroke.
    """
    filled, outline = glyph("alef_24_filled"), glyph("alef_24_regular")
    cx, cy = filled.centre
    k = cx + cy

    def half(sign):
        # A polygon covering the canvas on one side of the line: along it runs
        # from (k+50, -50) to (k-60, 60), and `sign` picks which side to sweep.
        edge = 200 * sign
        return polygon([(k + 50, -50), (k - 60, 60), (edge, 60), (edge, -50)])

    return (filled & half(+1)) | (outline & half(-1))


# --------------------------------------------------------------------------
# The document page, and what sits on it
# --------------------------------------------------------------------------
# Every document_* icon is the same page carrying a different mark, so the page
# is taken from one of them rather than respelled: the tet page with the tet
# lifted back out of it.
def page_regular():
    return glyph("document_tet_24_regular") - part("document_tet_24_filled", 1)


def page_filled():
    return part("document_tet_24_filled", 0)


# The block a document_* mark occupies: the tet's own box, which the changelog
# records as the 9.00-unit letter placed as in book_tet_24_regular.
MARK_BOX = (8.428, 10.100, 15.571, 19.100)


def document(mark, filled):
    """The page with `mark` on it - knocked out of a solid page for the filled
    variant, drawn on an open one for the regular."""
    if filled:
        return page_filled(), [mark]
    return page_regular() | mark, []


def mark_alef():
    """The alef at the tet's height and centre, so the two documents pair."""
    x0, y0, x1, y1 = MARK_BOX
    return alef_solid().fit((x0, y0, x1, y1))


def mark_download():
    """book_download's arrow, at the mark block's height and centred on it."""
    arrow = Art.from_d("M10.5 6 V12 H7.5 L12 16.5 L16.5 12 H13.5 V6 Z")
    x0, y0, x1, y1 = MARK_BOX
    return arrow.fit((x0, y0, x1, y1))


# --------------------------------------------------------------------------
# A filled book from an open one
# --------------------------------------------------------------------------
# The black line round the outside, and the white band behind it. Both are taken
# *out of* the existing silhouette rather than added around it, so a filled
# variant occupies exactly the space its regular twin does; a pair that differed
# in optical size would not sit together in a toolbar. The white band is the
# wider of the two because it is the one that has to survive: at 16 px a 1.0
# unit band is two thirds of a pixel, and it was disappearing.
BOOK_OUTER, BOOK_WHITE = 0.80, 1.45

# How far a knocked-out rule must stay clear of the white band. Without it a
# rule that runs close to the edge opens into the band and the two merge into
# one white shape, which reads as a hole in the book rather than as a line on it.
BOOK_RULE_MARGIN = 0.55

# Anything below this is debris from the offsetting, not artwork. Offsetting the
# otzaria_icon cover leaves forty-odd fragments none of them a thirtieth of a
# square unit, against a smallest real feature - one text rule - of 5.5. There
# is three orders of magnitude between the two, so the threshold does not need
# to be delicate; it needs to be well clear of the debris, which at 0.01 it was
# not.
SPECK = 0.5


def book_open_filled(base, outer=BOOK_OUTER, white=BOOK_WHITE):
    """Turn an open book inside out.

    The regular icon is a black frame around white pages. The filled one
    inverts that reading without changing the silhouette: a black line runs
    round the outside, the frame behind it is now white, the pages behind that
    are solid, and every line that used to be black - the gutter, and the text
    rules in a *_line variant - is knocked out of them.
    """
    art = glyph(base)
    body = ic.contours(art)[0]          # the silhouette, holes filled
    # Regularise the outline before offsetting it: these covers were drawn by
    # hand, and offsetting amplifies micro-defects far too small to see.
    body = body.deburr()
    ring = (body - body.shrink(outer)).despeckle(SPECK)
    core = body.shrink(outer + white).despeckle(SPECK)
    # The two bands are disjoint by construction, but an offset of a hand-drawn
    # cover can pinch the band shut where the outline turns sharply - and two
    # contours that merely touch are what the font merges into one shape and
    # what normalize_svg_overlaps.py refuses to resolve. Holding them apart
    # explicitly costs a twentieth of a unit and removes the whole class.
    core = (core - ring.grow(0.05)).despeckle(SPECK)
    rules = art & core.shrink(BOOK_RULE_MARGIN).despeckle(SPECK)
    return (ring | (core - rules)).despeckle(SPECK), []


# --------------------------------------------------------------------------
# The Latin letters on a document or a book
# --------------------------------------------------------------------------
# W, H, MD, PDF, ZIM and the hash were drawn with square corners and square
# terminals, which is not the hand the rest of the set is in: every rule, badge
# and page corner here is eased, and so is every terminal in Fluent. These are
# the two radii that put the letters in the same hand.
LETTER_OUTER, LETTER_INNER = 0.30, 0.14

# The letter block is found from the artwork, but a document's folded corner is
# also a small shape clear of the frame, so on a page the search starts below
# the fold.
LETTER_FLOOR = {"document": 9.0}


def letter_box(name, region):
    """The box the letters occupy, drawn round their own contours.

    The letters are isolated by a box rather than by collecting their contours,
    because a letter's counters - the bowl of a D, the openings of a hash - are
    contours too, and unioning those would fill them in.
    """
    gx0, gy0, gx1, gy1 = glyph(name).bounds
    floor = gy0 + 1.4
    for prefix, y in LETTER_FLOOR.items():
        if name.startswith(prefix):
            floor = max(floor, y)
    marks = [c for c in ic.contours(region)
             if c.area < 60
             and c.bounds[0] > gx0 + 1.4 and c.bounds[1] > floor
             and c.bounds[2] < gx1 - 1.4 and c.bounds[3] < gy1 - 1.4]
    if not marks:
        return None
    pad = 0.35
    return ic.rect(min(c.bounds[0] for c in marks) - pad,
                   min(c.bounds[1] for c in marks) - pad,
                   max(c.bounds[2] for c in marks) + pad,
                   max(c.bounds[3] for c in marks) + pad)


def polish_letters(name):
    """Ease the corners of the letters, leaving the page or cover alone.

    A lettered icon spells its letters one of three ways, and all three have to
    be handled or the wrong thing gets eased: on a page they are ink; on a
    filled page they are a `fill="white"` layer; on a filled book they are
    neither, but a hole in one merged path. The last is the one that bites -
    treated as ink it eases the *cover* around the letters and welds them shut.

    This rewrites its own source, so it checks first whether there is anything
    left to ease. An opening is idempotent in principle, so a second pass
    *should* be a no-op - but it is run on the offset output of the first, and
    skia's stroker fails outright on geometry like that. The test is the
    opening itself: on a square-cornered letter it takes 0.05 to 0.35 square
    units off, and on an eased one it takes nothing measurable.
    """
    solids, cuts = ic.layers(name)
    if cuts:
        body = Art()
        for layer in solids:
            body = body | layer
        cut = Art()
        for layer in cuts:
            cut = cut | layer
        _require_square(name, cut)
        return body, [cut.round_corners(LETTER_OUTER, LETTER_INNER)]

    g = glyph(name)
    hollow = g.holes()
    if name.endswith("_filled") and not hollow.is_empty:
        box = letter_box(name, hollow)
        if box is None:
            raise Restated("%s: no letter block found to ease" % name)
        letters = hollow & box
        _require_square(name, letters)
        return (g | letters) - letters.round_corners(LETTER_OUTER,
                                                     LETTER_INNER), []

    box = letter_box(name, g)
    if box is None:
        raise Restated("%s: no letter block found to ease" % name)
    letters = g & box
    _require_square(name, letters)
    return (g - box) | letters.round_corners(LETTER_OUTER, LETTER_INNER), []


def _require_square(name, letters):
    """Refuse to ease letters that have already been eased.

    The offset the test itself needs is the one that fails on already-offset
    geometry, so a failure here answers the question as surely as a zero does:
    either way there is nothing left to do.
    """
    try:
        opened = letters.shrink(LETTER_OUTER).grow(LETTER_OUTER)
    except Exception as exc:            # skia refuses an already-offset outline
        raise Restated("%s: the letters are already eased (%s)"
                       % (name, type(exc).__name__))
    if abs(letters.area - opened.area) < 0.01:
        raise Restated("%s: the letters are already eased" % name)


# --------------------------------------------------------------------------
# The Torah scroll
# --------------------------------------------------------------------------
# The parchment's opening, taken from the source rather than restated: the text
# block is centred in it, so if the scroll is ever redrawn the lines follow.
SCROLL_ROWS = 4
SCROLL_PITCH = 2.10          # against 1.6445 for the five rows it replaces
SCROLL_GROW = 0.04           # ~10% on every line, on top of the enlargement


def scroll_bars(art):
    """The ten text rules, found by their measurements."""
    out = Art()
    for c in ic.contours(art):
        x0, y0, x1, y1 = c.bounds
        if 3.0 < x1 - x0 < 4.5 and 0.5 < y1 - y0 < 1.2:
            out = out | c
    return out


# --------------------------------------------------------------------------
# A filled otzaria_icon, built without offsetting its cover
# --------------------------------------------------------------------------
# The same construction as the open book above, by a different route, because
# this cover's outline cannot be offset. Skia's stroker does not merely fail on
# it - it returns wrong answers without saying so: eroding the 351-unit cover by
# 0.50 gives back 36 units, by 0.80 gives 294, and by 1.00 fails outright. The
# outline is hand-drawn and full of near-degenerate detail, and there is no
# amount of deburring that makes an offset of it trustworthy.
#
# So nothing here is offset. The white band's inner edge is the boundary the
# designer already drew - the regular icon's own inner contour - and only the
# outer black line needs constructing, from a scaled copy of the cover. A scaled
# inset is not a true offset, so the line varies a little in width across a
# shape this tall, but it is exact arithmetic and cannot go wrong quietly.
OTZARIA_OUTER = 0.80


def _depth_one(contours, outer):
    """The contours immediately inside `outer`: the icon's interior regions,
    skipping anything nested deeper (a counter, a detail inside a page)."""
    out = []
    for c in contours:
        if c is outer:
            continue
        if (c & outer).area < 0.95 * c.area:
            continue
        if any(o is not c and o is not outer
               and (c & o).area > 0.95 * c.area for o in contours):
            continue
        out.append(c)
    return out


def otzaria_filled(base):
    art = glyph(base)
    cs = ic.contours(art)
    cover = cs[0]
    inner = _depth_one(cs, cover)
    if not inner:
        raise Restated("%s: no interior contour to build a filled variant from"
                       % base)
    core = Art()
    for c in inner:
        core = core | c

    x0, y0, x1, y1 = cover.bounds
    k = 1 - 2 * OTZARIA_OUTER / max(x1 - x0, y1 - y0)
    line = cover - cover.scale(k, about=((x0 + x1) / 2, (y0 + y1) / 2))
    return (line | (core - art)).despeckle(SPECK), []


class Restated(Exception):
    """A recipe that edits its own source refusing to run a second time."""


RECIPES = {}


def recipe(name):
    def deco(fn):
        RECIPES[name] = fn
        return fn
    return deco


@recipe("alef_rashi_24_regular")
def _alef_rashi():
    """Widened and given a little more weight.

    The Rashi alef was the narrowest letter in the set (10.32 units against the
    square alef's 14.89) and the lightest (mean stroke 1.64 against 2.08), so
    beside its siblings it read as a different, finer hand rather than as the
    same letter in another script. It is widened 22% - horizontally only, which
    is what a Rashi alef's proportions will take - and then offset outward
    0.13 units everywhere, which adds 0.26 to every stroke including the
    horizontal ones the widening left alone.

    This is the one recipe whose input is its own output, so running it twice
    would widen the letter twice. It refuses to run on a letter that is already
    wide, which is the state its own output leaves behind.
    """
    a = glyph("alef_rashi_24_regular")
    if a.size[0] > 11.5:
        raise Restated("alef_rashi_24_regular is already widened (%.2f units "
                       "across); rebuilding it would widen it again"
                       % a.size[0])
    return a.scale(1.22, 1.0, about=a.centre).grow(0.13), [], False


@recipe("alef_half_filled_24_regular")
def _alef_half():
    return alef_half(), [], False


@recipe("torah_scroll_24_regular")
def _torah_scroll():
    """Four lines of text instead of five, and the whole scroll opened up.

    At five rows the 1.64-unit pitch left 0.84 units of parchment between rules
    0.80 thick - almost equal bands - so below 24 px the text block closed into
    a grey slab. Four rows at 2.10 leave 1.30 between them, which is the ratio
    that still reads as separate lines when each one is under a pixel.

    The block is centred in the parchment's own opening rather than on the
    canvas, so it stays centred if the scroll is redrawn. The scroll is then
    scaled up about the canvas centre until it fills it, and offset outward
    afterwards: the enlargement thickens every line by the same factor it grows
    the drawing, and the offset is what adds weight on top of that.

    This recipe rewrites its own source, so it refuses a second run - the test
    is the row count it has already produced.
    """
    art = glyph("torah_scroll_24_regular")
    bars = scroll_bars(art)
    rows = ic.contours(bars)
    if len(rows) != 10:
        raise Restated("torah_scroll_24_regular has %d text rules, not the 10 "
                       "this rebuilds from" % len(rows))

    # One row's geometry, and the parchment opening the block sits in.
    x0, y0, x1, y1 = rows[0].bounds
    height = y1 - y0
    columns = sorted({round(c.bounds[0], 3) for c in rows})
    width = max(c.bounds[2] for c in rows) - max(columns)
    hole = max((h for h in ic.contours((art | bars).holes())),
               key=lambda h: h.area)
    _, hy0, _, hy1 = hole.bounds

    block = (SCROLL_ROWS - 1) * SCROLL_PITCH + height
    top = (hy0 + hy1) / 2 - block / 2
    text = Art()
    for r in range(SCROLL_ROWS):
        y = top + r * SCROLL_PITCH
        for x in columns:
            text = text | round_rect(x, y, x + width, y + height, height / 2)

    scroll = (art - bars) | text
    bx0, by0, bx1, by1 = scroll.bounds
    s = min(23.0 / (bx1 - bx0), 23.0 / (by1 - by0))
    scroll = scroll.scale(s, about=((bx0 + bx1) / 2, (by0 + by1) / 2))
    scroll = scroll.centred_on(12, 12).grow(SCROLL_GROW)
    return scroll, [], False


@recipe("document_alef_24_regular")
def _doc_alef_r():
    solid, cuts = document(mark_alef(), filled=False)
    return solid, cuts, False


@recipe("document_alef_24_filled")
def _doc_alef_f():
    solid, cuts = document(mark_alef(), filled=True)
    return solid, cuts, False


@recipe("document_download_24_regular")
def _doc_dl_r():
    solid, cuts = document(mark_download(), filled=False)
    return solid, cuts, False


@recipe("document_download_24_filled")
def _doc_dl_f():
    solid, cuts = document(mark_download(), filled=True)
    return solid, cuts, False


@recipe("book_open_medium_24_filled")
def _bom_f():
    solid, cuts = book_open_filled("book_open_medium_24_regular")
    return solid, cuts, False


@recipe("book_open_medium_line_24_filled")
def _boml_f():
    solid, cuts = book_open_filled("book_open_medium_line_24_regular")
    return solid, cuts, False


# The otzaria_icon family is the same construction and was drawn with the same
# intent, but by hand and far too tight: its white band measured about half a
# unit, a third of a pixel at 24 px, and `otzaria_icon_2_page_24_filled` had
# collapsed altogether - 21.6 units of ink against its regular twin's 200, so it
# shipped as a hairline outline rather than as a filled icon. Deriving all three
# from their regular twins by the rule above fixes both at once and keeps the
# two families reading alike.
for _name in ["otzaria_icon_24_filled",
              "otzaria_icon_line_24_filled",
              "otzaria_icon_2_page_24_filled"]:
    def _otz(base=_name.replace("_filled", "_regular")):
        solid, cuts = otzaria_filled(base)
        return solid, cuts, False
    RECIPES[_name] = _otz


# The lettered document and book icons. These rewrite their own sources, which
# would normally need the guard the Rashi alef carries - but a morphological
# opening and a closing are both idempotent, so easing a corner that is already
# eased does nothing, and a second run is a no-op rather than a second rounding.
for _name in ["document_word_24_regular", "document_word_24_filled",
              "document_html_24_regular", "document_html_24_filled",
              "document_md_24_regular", "document_md_24_filled",
              "book_word_24_regular", "book_word_24_filled",
              "book_md_24_regular", "book_md_24_filled",
              "book_pdf_24_regular", "book_pdf_24_filled",
              "book_zim_24_regular", "book_zim_24_filled",
              "book_number_24_regular", "book_number_24_filled"]:
    def _letters(n=_name):
        solid, cuts = polish_letters(n)
        return solid, cuts, False
    RECIPES[_name] = _letters


for _kind, _name in [("scissors", "alef_scissors_24_regular"),
                     ("lips", "alef_lips_24_regular"),
                     ("marker", "alef_marker_24_regular"),
                     ("eye", "alef_eye_24_regular"),
                     ("eraser", "alef_with_eraser_24_regular"),
                     ("exclamation", "alef_with_exclamation_24_regular"),
                     ("plus", "alef_addition_24_regular")]:
    RECIPES[_name] = alef_badge(_kind)

for _kind, _name in [("copy", "link_copy_24_regular"),
                     ("eraser", "link_with_eraser_24_regular"),
                     ("marker", "link_marker_24_regular"),
                     ("information", "link_with_information_24_regular"),
                     ("quote", "link_quote_24_regular"),
                     ("document", "link_document_24_regular"),
                     ("scissors", "link_scissors_24_regular"),
                     ("cross", "link_deletion_24_regular"),
                     ("eye", "link_eye_24_regular")]:
    RECIPES[_name] = link_badge(_kind)


# --------------------------------------------------------------------------
# Recording where the artwork came from
# --------------------------------------------------------------------------
MANIFEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "icon_manifest.yaml")


CUSTOM = {"origin": "custom", "based_on": "null",
          "license": "GPL-3.0-only", "upstream_commit": "null"}


def _records(text):
    """Split the manifest into (head, [record, ...]) on the record boundary.

    Worth doing properly: a regex that tries to reach a named record from the
    top of the file spans every record before it, and editing "that match" then
    rewrites all of them. Records are split first, then matched one at a time.
    """
    lines = text.split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("  - id:"))
    head, blocks, cur = lines[:start], [], None
    for l in lines[start:]:
        if l.startswith("  - id:"):
            if cur is not None:
                blocks.append(cur)
            cur = [l]
        else:
            cur.append(l)
    if cur is not None:
        blocks.append(cur)
    return head, blocks


def _write_provenance(used):
    """Set origin / based_on / license / upstream_commit on each composed
    record from what its recipe actually drew on, and reset any that no longer
    draws on anything.

    Only records this tool builds are touched, and only these four fields; the
    generator owns everything else about the file's shape. It exists because
    those four are the ones the generator fills with a default it has no way of
    knowing is wrong, and THIRD_PARTY_NOTICES.md is generated from them.
    """
    head, blocks = _records(open(MANIFEST, encoding="utf-8").read())
    changed = []
    for block in blocks:
        name = next((l.split(": ", 1)[1] for l in block
                     if l.startswith("    name: ")), None)
        if name not in RECIPES:
            continue
        if used.get(name):
            fields = fluent_art.provenance(*used[name])
            fields["based_on"] = "'%s'" % fields["based_on"].replace("'", "''")
        else:
            fields = dict(CUSTOM)
        before = list(block)
        for i, l in enumerate(block):
            for key, value in fields.items():
                if l.startswith("    %s: " % key):
                    block[i] = "    %s: %s" % (key, value)
        if block != before:
            changed.append(name)
    if changed:
        out = head + [l for b in blocks for l in b]
        open(MANIFEST, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    return changed


def main(argv):
    names = [a for a in argv if not a.startswith("-")]
    if "--list" in argv:
        for n in sorted(RECIPES):
            print(n)
        return 0
    if not names:
        names = sorted(RECIPES)
    unknown = [n for n in names if n not in RECIPES]
    if unknown:
        print("no recipe for: %s" % ", ".join(unknown), file=sys.stderr)
        return 2
    # --provenance only records where the artwork came from. It runs the
    # recipes to find that out but writes no source, so it can be run after
    # generation has allocated the records without putting the freshly
    # formatted sources back into their pre-format_svg spelling.
    record_only = "--provenance" in argv
    skipped, used = 0, {}
    for n in names:
        del _USED[:]
        try:
            solid, cuts, overlap = RECIPES[n]()
        except Restated as e:
            if not record_only:
                print("%-40s skipped: %s" % (n + ".svg", e))
                skipped += 1
            continue
        used[n] = list(_USED)
        if record_only:
            continue
        path = write(n, solid, cuts, preserve_overlap=overlap)
        x0, y0, x1, y1 = solid.bounds
        print("%-40s bbox %6.2f %6.2f %6.2f %6.2f  %d cut(s)%s"
              % (os.path.basename(path), x0, y0, x1, y1, len(cuts),
                 "  fluent: " + ", ".join(_USED) if _USED else ""))
    if skipped:
        print("%d recipe(s) skipped; they edit their own source and it has "
              "already been edited." % skipped)
    if "--provenance" in argv:
        changed = _write_provenance(used)
        print("provenance updated for %d record(s)%s"
              % (len(changed), ": " + ", ".join(changed) if changed else ""))
    elif any(used.values()):
        print("\nSome of these draw on Fluent artwork. After `dart run "
              "tool/generate.dart` has allocated their records, run\n"
              "  python3 tool/compose_sources.py --provenance\n"
              "to record it; THIRD_PARTY_NOTICES.md is generated from those "
              "fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
