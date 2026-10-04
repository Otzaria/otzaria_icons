#!/usr/bin/env python3
"""Build the composed icon sources from the artwork already in the set.

Each recipe below states one icon as an operation on committed sources, so the
shared parts of a family stay identical rather than merely similar, and a later
change to a shared part (the alef was redrawn twice already) propagates by
re-running this instead of by hand-patching every file that carries it.

  python3 tool/compose_sources.py                 # rebuild every composed icon
  python3 tool/compose_sources.py alef_scissors_24_filled ...
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
import glob
import math
import sys
import os

import pathops

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
BADGE_SOURCE = ("alef_copy_24_filled", 1)
BADGE_CX, BADGE_CY = 16.415, 17.667

# How far a mark's ink may reach from the disc's centre, as a fraction of the
# disc's radius. A mark going into a round badge is fitted by reach, not into a
# square box: the corners a box reserves fall outside the circle anyway, so
# box-fitting leaves a wide flat mark - an eye, a pair of lips - visibly
# undersized beside a compact one. Set from what is already on these discs:
# Fluent's cross reaches 3.56 of its disc's 5.495, and this set's copy badge
# 3.2 of 4.19 - and then pushed past both, because at 16 px the badge is 5.6
# pixels across and a mark using two thirds of that is three. At 0.80 the ring
# of badge ink is still 0.85 units, which is what keeps the disc reading as a
# disc.
SYMBOL_REACH = 0.80

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
BADGE_MIN_STROKE = 1.00

# An enclosed hole below this area is filled instead of kept. At badge scale the
# eyes of the scissors' handles land at about a third of a unit across, which
# prints as a smudge rather than as a hole; Fluent redraws marks at badge size
# for the same reason.
BADGE_MIN_HOLE = 0.55


# How much bigger the alef family's badge disc (+ its knockout mark) is drawn
# than the disc `alef_copy_24_filled` carries, and the link family's own disc
# taken from Fluent's template. Both are scaled as one unit - the disc and the
# mark inside it together - about the canvas corner the badge sits nearest, so
# the badge grows toward the centre of the icon instead of drifting toward, or
# past, the edge it is anchored to.
ALEF_BADGE_SCALE = 1.20
LINK_BADGE_SCALE = 1.15


def _anchor_corner(bounds):
    """The canvas corner (0 or 24 on each axis) nearest a badge's own centre."""
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return (24.0 if cx > 12 else 0.0, 24.0 if cy > 12 else 0.0)


def fill_canvas_pair(solid, cuts):
    """`fill_canvas`, but for a (solid, [cut, ...]) pair built in memory rather
    than read back from a file: both are scaled and translated by the same
    transform, measured on their union, so a cut stays exactly registered on
    the solid it is knocked out of."""
    combo = solid
    for c in cuts:
        combo = combo | c
    x0, y0, x1, y1 = combo.bounds
    s = min(CANVAS_BOX / (x1 - x0), CANVAS_BOX / (y1 - y0))
    about = ((x0 + x1) / 2, (y0 + y1) / 2)
    solid2 = solid.scale(s, about=about)
    cuts2 = [c.scale(s, about=about) for c in cuts]
    combo2 = solid2
    for c in cuts2:
        combo2 = combo2 | c
    cx0, cy0, cx1, cy1 = combo2.bounds
    dx, dy = 12 - (cx0 + cx1) / 2, 12 - (cy0 + cy1) / 2
    return solid2.translate(dx, dy), [c.translate(dx, dy) for c in cuts2]


def badge():
    return part(*BADGE_SOURCE)


def alef_solid():
    """The solid alef exactly as the existing badged icons spell it."""
    return part("alef_copy_24_filled", 0)


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
    """The deletion cross, recentred from its own slightly-offset disc.

    Read as "whichever solid the file marks as the knockout" rather than by a
    fixed path index: `alef_deletion_24_filled` is a hand-authored source
    (letter, disc, cut), but its badge has since been enlarged in place by
    unioning the letter and the disc into one path, which shifts the cut from
    index 2 to index 1. `ic.layers` finds the same cut by its fill="white"
    marker instead, so it is not tied to how many separate solids the file
    happens to carry.
    """
    _, cuts = ic.layers("alef_deletion_24_filled")
    return cuts[0]


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
    "scissors": ("cut_24_filled", -95),
    "eraser": ("eraser_24_filled", 0),
    # Fluent draws the highlighter head-on and upright, where it reads as a
    # bottle. Turned 45 degrees clockwise the nib goes to the lower left and the
    # barrel up to the right - the angle a pen is actually held at.
    "marker": ("highlight_24_filled", 45),
    "eye": ("eye_24_filled", 0),
    "quote": ("text_quote_24_filled", 0),
    "document": ("document_24_filled", 0),
    # Fluent's info "i" is a fine stroke inside a disc; on a badge it needs more
    # weight than the marks that are shapes rather than letters.
    "information": ("info_24_filled", 0),
}

# Per-mark stroke weights, where the default does not suit.
SYMBOL_WEIGHT = {
    # Fluent's cut is already the heaviest mark here - a 1.88 mean stroke
    # against the others' 1.0 to 1.5 - so it arrives at badge scale needing no
    # help. Bringing it up to the default anyway fattened the blades into each
    # other and cost the mark its point, which is the one thing that says
    # scissors.
    "scissors": 0.62,
}


def sym_fluent(kind, reach):
    name, turn = FLUENT_SYMBOLS[kind]
    # Turn before fitting, so `reach` still means what it says: a mark measured
    # upright and then rotated reaches further than it was fitted to.
    art = use_fluent(name)
    if turn:
        art = art.rotate(turn, about=art.centre)
    return weighted(art, reach, SYMBOL_WEIGHT.get(kind, BADGE_MIN_STROKE))


def sym_information(reach):
    """Fluent's "i", not Fluent's info icon.

    `info_24_filled` is a disc with the letter knocked out of it, so using it
    whole put a disc inside a disc: the badge came out as a black ring with a
    dark letter in the middle of it, and the letter ended up the smallest thing
    on the icon. The badge already *is* the disc, so what it needs is the letter
    alone - which is exactly the hole in Fluent's glyph. Taken that way it can
    be set far larger, and the whole badge reads as one mark.
    """
    letter = use_fluent("info_24_filled").holes()
    return weighted(letter, reach, weight=1.15)


def sym_eye(reach):
    """Fluent's eye, with the pupil pulled back off the lid.

    Fluent draws it as a lid arc with a solid pupil under it, and leaves about
    1.2 units between them. Restoring the arc's weight at badge scale spends
    most of that, and the two run together into a blob - the thing that stopped
    this reading as an eye. Since the pupil is a disc, its own size is a free
    parameter the arc's is not: taking a little off it opens the gap back up
    without touching the shape that carries the reading.
    """
    art = weighted(use_fluent("eye_24_filled"), reach * 0.92)
    parts = ic.contours(art)
    pupil = min(parts, key=lambda c: c.area)
    lid = Art()
    for c in parts:
        if c is not pupil:
            lid = lid | c
    return (lid | pupil.shrink(0.20)).centred_on(0, 0)


def sym_alef():
    """The alef itself, as a badge mark.

    It goes on the link's disc, which is the larger of the two, and it is a
    letter rather than an object - so like the information "i" it is set to the
    full reach and given a letter's weight rather than an object's.
    """
    return alef_solid()


def sym_copy():
    """The copy mark this set already draws, reused rather than replaced.

    Fluent's own copy is two outlined sheets; at badge scale its 1.5-unit rings
    fall to 0.4 and vanish, so `alef_copy_24_filled` cuts the sheets out solid
    with badge ink between them instead. That adaptation is already the right
    drawing for a disc this size, so the link badge takes it rather than
    reducing Fluent's again and getting a different answer.
    """
    return part("alef_copy_24_filled", 2)


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


def sym_lock():
    """A padlock drawn at badge scale, not Fluent's padlock reduced to it.

    Reducing `lock_closed_24_filled` is the one adaptation that cannot work
    here. Its shackle is a 1.5-unit ring around a 3-unit opening; at the 0.29
    a badge mark is scaled to, the opening falls to under a unit and closes as
    soon as the stroke is put back, and what is left is a rounded blob with a
    dot in it. The blob is the body, so the mark loses the only feature that
    says lock.

    Fluent's own answer to this is to redraw, not to reduce - `lock_shield`
    carries a lock two units tall that shares no outline with the full-size
    one - and that is what this is: a body as wide as the disc will take, and
    above it a shackle whose opening is deliberately the largest thing in the
    mark rather than the smallest. There is no keyhole. At 16 px the badge is
    5.6 px across, so a keyhole would be a fifth of a pixel of black inside a
    three-pixel white mark, and all it would do is grey the mark down.
    """
    body = round_rect(-2.05, -0.30, 2.05, 2.85, 0.75)
    # The shackle: a thick arch, clipped to its upper half, with straight legs
    # carried down far enough to clear the body's own rounded top corners. The
    # body is kept narrow on purpose - its bottom corners are the farthest ink
    # from the mark's centre, so they are what `fit_radius` scales against, and
    # every tenth taken off them is a tenth the opening above can have.
    arch = (circle(0, -0.30, 1.75) - circle(0, -0.30, 0.95)) & ic.rect(
        -1.75, -2.25, 1.75, -0.30)
    legs = (ic.rect(-1.75, -0.30, -0.95, 0.50)
            | ic.rect(0.95, -0.30, 1.75, 0.50))
    return body | arch | legs


def sym_crown():
    """A plain three-point crown, drawn at badge scale.

    Built the way `sym_plus` and `sym_exclamation` are: a base band and three
    points solved as simple shapes rather than borrowed from Fluent, since
    Fluent has no crown small enough to read at badge size without redrawing.
    Kept to three points and no jewels - a badge this small can carry a
    silhouette, not ornament, and a crown with detail cut into it just goes
    grey at 16 px.
    """
    band = round_rect(-2.30, 0.95, 2.30, 1.95, 0.45)
    body = polygon([(-2.30, 0.95), (-2.30, -0.75), (-1.15, 0.55),
                    (0, -1.65), (1.15, 0.55), (2.30, -0.75), (2.30, 0.95)])
    balls = (circle(-2.30, -0.75, 0.42) | circle(0, -1.65, 0.48)
             | circle(2.30, -0.75, 0.42))
    return (band | body | balls).centred_on(0, 0)


def sym_book_empty():
    """The literal book `search_in_the_book_24_regular` already draws inside
    its own lens - not a redrawn approximation of it - read straight from
    that icon's own source the same way `sym_copy` reuses `alef_copy`'s
    sheets: `_search_split` returns exactly the region the font fills for
    that icon's content (its cover, its title bar cut as a hole, its base
    seam cut as a hole), and reusing that Art object directly means a later
    redraw of that book updates this badge too, instead of the two silently
    drifting apart the way a hand-copied approximation would.

    Two earlier versions redrew this by hand: one reused
    `book_empty_24_regular`'s own outline, which collapsed into a cusp once
    `weighted`'s regrowth pass tried to put stroke weight back onto its thin
    ribbon-tab detail; the other approximated the same "solid white cover,
    black seam line" construction with two round rects, which read fine but
    was still a second drawing of a book this set already has one of.
    """
    _, _, content = _search_split("search_in_the_book_24_regular")
    return content


# Marks already drawn at badge scale for the alef's disc, which is the only disc
# they go on: they take neither scaling nor re-weighting.
DRAWN_SYMBOLS = {
    "plus": sym_plus,
    "exclamation": sym_exclamation,
    "lock": sym_lock,
    "crown": sym_crown,
}


def symbol(kind, reach):
    """The mark for `kind`, centred on the origin, reaching `reach` units."""
    if kind in DRAWN_SYMBOLS:
        # Drawn at badge scale, so they need no re-weighting - but they are
        # still fitted, or they would stay at whatever size the disc used to be.
        return DRAWN_SYMBOLS[kind]().fit_radius(reach).centred_on(0, 0)
    if kind == "copy":
        # Already at badge weight; it only needs the disc it is going on.
        return sym_copy().fit_radius(reach).centred_on(0, 0)
    if kind == "lips":
        return sym_lips(reach)
    if kind == "cross":
        return weighted(sym_cross_mark(), reach)
    if kind == "eye":
        return sym_eye(reach)
    if kind == "information":
        return sym_information(reach)
    if kind == "alef":
        return weighted(sym_alef(), reach, weight=1.15)
    if kind == "book_empty":
        return weighted(sym_book_empty(), reach)
    return sym_fluent(kind, reach)


def badged(base, kind, badge_scale=1.0):
    """base + the alef family's disc, with `kind` knocked out of the disc.

    `badge_scale` enlarges the disc and its mark together, as one unit, about
    the canvas corner the disc sits nearest - so the badge reads better at
    small sizes without drifting off its corner or being stretched out of
    round.
    """
    disc = badge()
    # Centred on the disc's own actual centre, not the fixed BADGE_CX/BADGE_CY
    # `place` used: those constants recorded where the disc used to sit before
    # its own source (alef_copy_24_filled) was enlarged 20% in place, and the
    # corner-anchored scale that enlarged it also moved its centre - reading
    # the disc's current centre keeps the mark and the disc registered on each
    # other however the disc is drawn.
    mark = symbol(kind, disc.radius() * SYMBOL_REACH).centred_on(*disc.centre)
    if badge_scale != 1.0:
        corner = _anchor_corner(disc.bounds)
        disc = disc.scale(badge_scale, about=corner)
        mark = mark.scale(badge_scale, about=corner)
    return base | disc, [mark]


# --------------------------------------------------------------------------
# Recipes
# --------------------------------------------------------------------------
def alef_badge(kind):
    """The alef, badged.

    No `badge_scale` here: `alef_copy_24_filled` - the file `badge()` reads
    the canonical disc from - already carries it enlarged 20% in its own
    source (it is one of the icons the owner asked to have a bigger badge,
    same as every other alef badge). Applying `ALEF_BADGE_SCALE` again here
    on top of that would compound to 44%.
    """
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
# The filled twin of the same template: Fluent's own heavier chain, with the
# same disc in the same place. A link is a stroke icon, so its filled variant is
# the same drawing thickened - which is exactly what Fluent ships.
LINK_TEMPLATE_FILLED = "link_dismiss_24_filled"

def link_plate(template=LINK_TEMPLATE):
    """(cut-back link, disc, the mark in the disc) from Fluent's badged-link
    template.

    The template's contours are the disc, the link's three pieces, and the
    cross knocked out of the disc. They are told apart by containment rather
    than by index: the disc is the contour that holds another, the mark is what
    it holds, and the link is everything else - which stays true if Fluent
    renumbers its outline.
    """
    art = use_fluent(template)
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


def link_badge(kind, filled=False):
    """Fluent's link, cut back, with `kind` knocked out of Fluent's disc.

    The disc and its mark are enlarged 15% as one unit, anchored to the corner
    the disc already sits in, and the whole assembly - link and enlarged badge
    together - is then scaled to fill the canvas the way every other icon in
    the set that is drawn as large as it will go is: see `fill_canvas`.
    """
    def build():
        link, disc, _ = link_plate(LINK_TEMPLATE_FILLED if filled
                                   else LINK_TEMPLATE)
        x0, y0, x1, y1 = disc.bounds
        mark = symbol(kind, disc.radius() * SYMBOL_REACH).centred_on(
            (x0 + x1) / 2, (y0 + y1) / 2)
        corner = _anchor_corner(disc.bounds)
        disc = disc.scale(LINK_BADGE_SCALE, about=corner)
        mark = mark.scale(LINK_BADGE_SCALE, about=corner)
        solid, cuts = fill_canvas_pair(link | disc, [mark])
        return solid, cuts, True
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
# A filled icon from an outline one
# --------------------------------------------------------------------------
# Stated as a rule rather than derived by offsetting, which is what the earlier
# attempts got wrong:
#
#   every white area inside the icon, except the big one outside it, turns
#   black; every black line turns white; and a thin black line is added
#   around the outermost white lines.
#
# Read literally, that needs *no offset of the artwork at all*. The white lines
# of the filled icon are the black lines of the regular one, exactly where the
# designer drew them - same widths, same curves, same corners - so the pair
# cannot differ in the ways the offset versions did, least of all at the top of
# a cover where the outline turns most sharply. The only constructed part is the
# thin black line, and that is a *grow* of the silhouette, which unlike a shrink
# cannot collapse or fold.
FILLED_EDGE = 0.55

# Two families carry it at twice that, on the owner's ear: their covers are the
# heaviest drawings in the set, and against them a line this fine read as a
# hairline rather than as an edge. The extra goes outward only - the artwork
# inside is untouched, which is the whole point of the rule.
FILLED_EDGE_BY = {
    "book_open_medium": 1.10,
    "book_open_large": 1.10,
}


def filled_edge(base):
    for prefix, edge in FILLED_EDGE_BY.items():
        if base.startswith(prefix):
            return edge
    return FILLED_EDGE


def inverted(base, edge=None):
    """The regular icon turned inside out, by the rule above."""
    edge = filled_edge(base) if edge is None else edge
    art = glyph(base)
    body = ic.contours(art)[0]              # the silhouette, holes filled
    # The interior is cut with the exact silhouette, so the white lines land
    # exactly where the black ones were. Only the outer line is grown, and only
    # from a deburred copy: these covers are hand-drawn, and growing one raw
    # sheds slivers that end up welded to the artwork.
    ring = body.deburr().grow(edge) - body
    out = (body - art) | ring
    return out.despeckle(SPECK).fill_holes(SPECK).prune(0.002), []


# Anything below this is debris, not artwork: three orders of magnitude under
# the smallest real feature in these icons, which is one text rule at 5.5.
SPECK = 0.5


# --------------------------------------------------------------------------
# Text rules on an open book
# --------------------------------------------------------------------------
# Five of these icons showed their text as six or seven rules half a unit thick,
# 1.5 apart - bands of ink and paper almost equal in width. Below 24 px that
# closes into a grey slab, and it is worse in the filled variants, where the
# rules are white on black and go first. `book_open_medium_line` had it right
# already: three rules at 1.25 with 1.75 of paper between them, a gap 1.4 times
# the ink. Every family below is brought to four rules at that ratio.
#
# (rows, height, pitch, rule width - None keeps the width the rules already
# have). The width is absolute rather than an amount to trim, so that a second
# run draws the same rules instead of trimming them again.
RESTRIPE = {
    "book_open_large_lines_24_regular":   (4, 1.00, 2.30, None),
    "book_open_large_search_24_regular":  (4, 1.00, 2.30, None),
    # Already at the right weight; only shortened - from 5.75, and then again to
    # here. A rule this short is 3.5 times its own height, so the round ends are
    # a third of it and they read as ends; at 5.15 they were a quarter and the
    # bar read as a cut rectangle, which is what the owner saw in the filled
    # variant, where the rule is white on black and its ends go first.
    "book_open_medium_line_24_regular":   (3, 1.25, 3.00, 4.40),
    "book_open_medium_search_24_regular": (3, 1.25, 3.00, 4.40),
}


def find_rules(art):
    """The text rules in an icon, told apart from its structure by shape: wide,
    short, and much wider than they are tall."""
    out = []
    for c in ic.contours(art):
        x0, y0, x1, y1 = c.bounds
        w, h = x1 - x0, y1 - y0
        if w > 2.5 and 0.3 < h < 1.8 and w / h > 2.2:
            out.append(c)
    return out


def restripe(name, art):
    """Replace an icon's text rules with fewer, heavier, evenly spaced ones.

    The replacements are centred on the block the originals occupied, not on the
    page, so they stay where the designer put the text however the book around
    them is drawn. Columns are recovered from the originals' own left edges, and
    every rule is a stadium - round ends, radius exactly half the height.
    """
    rules = find_rules(art)
    rows, height, pitch, width = RESTRIPE[name]

    # Group the rules into columns by their left edge, rounded only for the
    # grouping - the extents kept are the real ones, because rounding is a
    # tenth of a unit and re-running on a rounded extent would walk the rules
    # sideways a little every time.
    columns = {}
    for c in rules:
        x0, _, x1, _ = c.bounds
        key = round(x0, 1)
        lo, hi = columns.get(key, (x0, x1))
        columns[key] = (min(lo, x0), max(hi, x1))
    tops = [c.bounds[1] for c in rules]
    bottoms = [c.bounds[3] for c in rules]
    middle = (min(tops) + max(bottoms)) / 2

    block = (rows - 1) * pitch + height
    top = middle - block / 2
    text = Art()
    for r in range(rows):
        y = top + r * pitch
        for x0, x1 in columns.values():
            mid = (x0 + x1) / 2
            half = (x1 - x0 if width is None else width) / 2
            text = text | round_rect(mid - half, y, mid + half, y + height,
                                     height / 2)

    old = Art()
    for c in rules:
        old = old | c
    # This rewrites its own source, so it stops when the rules it would draw are
    # the rules already there. Comparing the regions rather than counting them
    # is what makes that reliable: two of these icons already had the right
    # number of rules and still needed their ends pulling in.
    if (old - text).area + (text - old).area < 0.05:
        raise Restated("%s already carries these rules" % name)
    return (art - old) | text, []


# --------------------------------------------------------------------------
# Text spread over the page instead of set as a block
# --------------------------------------------------------------------------
# The two `otzaria_icon` line variants set their text in the top two thirds of
# the page and left the bottom third empty, which reads as a page that was cut
# short rather than as a page of text. Here the page itself is the block: five
# rules, with the same gap above the first, between each pair and below the
# last, measured from the frame lines the page is drawn between.
#
# (rows, gap as a multiple of the rule's own height). Stating the gap as a
# ratio rather than a pitch is what makes this survive the icon being scaled:
# the rule height is solved from the opening, so enlarging the drawing enlarges
# the text with it and a second run finds the layout it would have drawn.
# (rows, gap as a multiple of the rule's own height, rule width - None keeps
# the width the rules already have).
RESPREAD = {
    "otzaria_icon_line_24_regular":        (5, 1.55, None),
    "otzaria_icon_2_page_line_24_regular": (5, 1.55, None),
    # Its rules were 4.80 wide in a page 5.52 across, which left a quarter of a
    # unit of paper beside them - they read as running into the book's own
    # uprights - and four rows at a 2.25 pitch sat in the top half of a page
    # 13 units deep. Spread over the page and set to 4.00 they clear the
    # uprights by three quarters of a unit on each side.
    "book_open_small_line_24_regular":     (4, 1.75, 4.00),
}


def column_opening(art, mid, probe=0.3):
    """(top, bottom) of the white band a column of text sits in.

    Measured on the column's own centre line, through artwork the rules have
    already been taken out of, so what is found is the gap between the frame
    line above the text and the one below it - whatever shape the page is.
    """
    runs = sorted((c.bounds[1], c.bounds[3]) for c in
                  ic.contours(art & ic.rect(mid - probe, 0, mid + probe, 24)))
    gaps = [(runs[i][1], runs[i + 1][0]) for i in range(len(runs) - 1)]
    if not gaps:
        raise Restated("no opening found on the column at x=%.2f" % mid)
    return max(gaps, key=lambda g: g[1] - g[0])


def round_rule_ends(name, art):
    """Give an icon's text rules the round ends the rest of the set has.

    `otzaria_icon` is the one place that drew them as plain rectangles - two of
    its three, with the third eased and the other two not - which is what the
    owner saw as ends that are not round. Every other rule in the set is a
    stadium, and the design spec asks for Fluent's rounded terminals, so this
    replaces each square-ended rule with a stadium on its own bounding box:
    same length, same weight, same place.
    """
    out, done = art, 0
    for c in find_rules(art):
        x0, y0, x1, y1 = c.bounds
        if c.area < (x1 - x0) * (y1 - y0) - 0.05:
            continue                     # already eased
        out = (out - c) | round_rect(x0, y0, x1, y1, (y1 - y0) / 2)
        done += 1
    if not done:
        raise Restated("%s's rules already have round ends" % name)
    return out, []


def row_opening(art, y, x, probe=0.15):
    """(left, right) of the white band at height `y` that contains `x`.

    The horizontal counterpart of `column_opening`, and used for the same
    reason: a rule that is given a width has to be centred on the paper it sits
    on rather than on wherever the rules it replaces happened to start, or it
    keeps whatever lean the old ones had.
    """
    runs = sorted((c.bounds[0], c.bounds[2]) for c in
                  ic.contours(art & ic.rect(0, y - probe, 24, y + probe)))
    for i in range(len(runs) - 1):
        if runs[i][1] <= x <= runs[i + 1][0]:
            return runs[i][1], runs[i + 1][0]
    raise Restated("no paper found around x=%.2f at y=%.2f" % (x, y))


def respread(name, art):
    """Spread an icon's text rules evenly over the page they sit on."""
    rules = find_rules(art)
    rows, ratio, width = RESPREAD[name]

    columns = {}
    for c in rules:
        x0, _, x1, _ = c.bounds
        key = round(x0, 1)
        lo, hi = columns.get(key, (x0, x1))
        columns[key] = (min(lo, x0), max(hi, x1))

    old = Art()
    for c in rules:
        old = old | c
    bare = art - old

    text, drawn = Art(), []
    for x0, x1 in columns.values():
        mid = (x0 + x1) / 2
        top, bottom = column_opening(bare, mid)
        # rows*h + (rows+1)*ratio*h fills the opening exactly.
        height = (bottom - top) / (rows + (rows + 1) * ratio)
        gap = height * ratio
        if width is not None:
            lo, hi = row_opening(bare, (top + bottom) / 2, mid)
            x0 = (lo + hi) / 2 - width / 2
            x1 = x0 + width
        for r in range(rows):
            y = top + gap + r * (height + gap)
            text = text | round_rect(x0, y, x1, y + height, height / 2)
            drawn.append((x0, y, x1, y + height))

    # The guard compares the rules themselves rather than the two regions, as
    # `restripe` does. Region arithmetic is the more thorough test but it is not
    # a reliable one here: on `otzaria_icon_2_page_line` the difference of two
    # regions that draw the same ten rules comes back as eleven square units of
    # contour that encloses nothing, and a guard that cannot recognise its own
    # output is a guard that rewrites the file on every run. Ten boxes to a
    # fiftieth of a unit says the same thing and says it exactly.
    def boxes(bs):
        return sorted(tuple(round(v, 2) for v in b) for b in bs)

    if boxes(drawn) == boxes(c.bounds for c in rules):
        raise Restated("%s already carries these rules" % name)
    return (art - old) | text, []


# --------------------------------------------------------------------------
# Filling the canvas
# --------------------------------------------------------------------------
# What "as large as the icon will take" means here. Half a unit of air on each
# side: enough that a round terminal does not look cropped at 16 px, and close
# enough to the box that the drawing is the icon rather than a drawing inside
# it. The Torah scroll was already brought up to this, so the number is shared
# rather than restated.
CANVAS_BOX = 23.0


def fill_canvas(name, art):
    """Scale an icon about its own centre until it fills the canvas box, then
    centre it there."""
    x0, y0, x1, y1 = art.bounds
    if max(x1 - x0, y1 - y0) >= CANVAS_BOX - 0.05:
        raise Restated("%s already measures %.2f x %.2f"
                       % (name, x1 - x0, y1 - y0))
    s = min(CANVAS_BOX / (x1 - x0), CANVAS_BOX / (y1 - y0))
    return (art.scale(s, about=((x0 + x1) / 2, (y0 + y1) / 2))
               .centred_on(12, 12)), []


def sized(art):
    """`fill_canvas` for artwork that is derived rather than edited in place -
    no guard, because nothing here is read back from a file it just wrote."""
    x0, y0, x1, y1 = art.bounds
    s = min(CANVAS_BOX / (x1 - x0), CANVAS_BOX / (y1 - y0))
    return (art.scale(s, about=((x0 + x1) / 2, (y0 + y1) / 2))
               .centred_on(12, 12))


# How much is cut off each side of a sharp corner. `book_open_large` is drawn
# with a stepped frame whose corners are square, which beside the rest of the
# set - and beside Fluent, where nothing is square - reads as a spike. Cutting
# 0.85 gives a corner about two thirds of a unit across: visible at 24 px,
# and still well short of the 0.4 of an edge the fillet will ever take.
BOOK_CORNER = 0.85


def ease_corners(name, art):
    """Round off an icon's square corners, on the path rather than by erosion.

    The guard is the operation's own idempotence: filleting a corner leaves a
    curve, and a curve is not a corner, so a second run finds nothing to cut
    and returns the artwork unchanged to the last decimal.
    """
    out = art.fillet(BOOK_CORNER)
    if (art - out).area + (out - art).area < 0.02:
        raise Restated("%s has no square corners left" % name)
    return out, []


def in_place(name, *steps):
    """A recipe that applies a chain of edits to an icon's own source.

    Every step here rewrites the file it read, so every one of them has to be
    able to recognise its own output and refuse; this runs the ones that still
    have work to do and reports the icon unchanged only when none of them has.
    """
    def build():
        art, cuts, done, last = glyph(name), [], 0, None
        for step in steps:
            try:
                art, cuts = step(name, art)
                done += 1
            except Restated as e:
                last = e
        if not done:
            raise last
        return art, cuts, False
    return build


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
# Two letters side by side
# --------------------------------------------------------------------------
# `alef_alef_24_filled`'s layout exactly - two letters 10.80 units wide at
# x 0.95 and x 12.25 - so every pair in the set sits at the same size and
# rhythm. The Hebrew letter goes on the right, where a Hebrew reader starts.
PAIR_LEFT, PAIR_RIGHT, PAIR_WIDTH = 0.95, 12.25, 10.80


def pair(right, left):
    """Two letters laid out on that grid, each fitted to the same band so they
    share a baseline and a cap line rather than merely sitting side by side."""
    x0, y0, x1, y1 = right.bounds
    band = (0, y0, PAIR_WIDTH, y1)
    r = right.fit(band)
    l = left.fit(band)
    return (l.translate(PAIR_LEFT - l.bounds[0], 0)
            | r.translate(PAIR_RIGHT - r.bounds[0], 0))


def latin_a():
    """Fluent's capital A, lifted out of `local_language_24_filled`.

    That icon is an A beside a Korean syllable; the A is its largest contour
    with its counter inside, and the two are told apart by containment rather
    than by index.
    """
    art = use_fluent("local_language_24_filled")
    cs = ic.contours(art)
    body = max(cs, key=lambda c: c.area)
    out = body
    for c in cs:
        if c is not body and (c & body).area > 0.95 * c.area:
            out = out - c
    return out


class Restated(Exception):
    """A recipe that edits its own source refusing to run a second time."""


RECIPES = {}

# Which composed source a recipe reads, for the ones that read another icon's
# file rather than their own. A recipe that rewrites its own source has to have
# run before anything derived from it is built, or the derivation is one run
# behind - and that is not a theoretical worry: every icon that fills the canvas
# is resized in place, and its filled twin is built from the resized file.
DEPENDS = {}


def recipe(name):
    def deco(fn):
        RECIPES[name] = fn
        return fn
    return deco


# --------------------------------------------------------------------------
# book_fanned: traced from the reviewer's own reference vector art
# --------------------------------------------------------------------------
# Two earlier attempts built this from hand-picked or pixel-percentage
# parameters and both missed the reference. The reviewer then supplied the
# actual reference SVGs (dense M/L/Z polyline exports, fill-rule evenodd),
# which are transcribed directly rather than re-derived a third time: each
# subpath's point list is simplified (Ramer-Douglas-Peucker, since the
# exports are far denser than this canvas needs), rebuilt honouring evenodd,
# and scaled/centred into the 24-unit canvas - see the session's transcription
# script. book_fanned_24_filled and book_fanned_24_regular are therefore
# static sources, like most hand-drawn icons in this set, not recipes: the
# reference files live outside this repo, so nothing here could rebuild them
# from scratch, and a stale recipe left in place under these names would
# silently overwrite the traced result if compose_sources.py were ever run
# for them again.

@recipe("alef_rashi_24_filled")
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
    a = glyph("alef_rashi_24_filled")
    if a.size[0] > 11.5:
        raise Restated("alef_rashi_24_filled is already widened (%.2f units "
                       "across); rebuilding it would widen it again"
                       % a.size[0])
    return a.scale(1.22, 1.0, about=a.centre).grow(0.13), [], False


@recipe("alef_half_filled_24_regular")
def _alef_half():
    return alef_half(), [], False


# How much of the erosion is given back to the beit's back, over what span, and
# how far the giving-back is eased in at each end.
#
# `beit_24_filled` was made by scaling the small beit inside
# `beit_near_alef_24_filled` up to letter size and eroding it 0.45 units on
# every flank - 0.90 off every stroke. The back could not afford it: it measured
# 2.95 at the shoulder but 0.22 at y=16, a fifth of a pixel at 24 px. Restoring
# exactly the 0.90 the erosion took puts the back back on the letterform's own
# proportions - 1.40 at mid-height, 1.12 at its narrowest - rather than on a
# width picked by eye.
#
# The padding runs from the corner under the bar all the way into the base,
# with no easing at the foot: the foot is a junction, not a free end, and
# easing the padding off inside it turned the new edge back outward just as
# the letter's own flare turned inward - the hook that showed at the bottom of
# the back.
BEIT_RESTORE, BEIT_TOP, BEIT_FOOT, BEIT_EASE = 0.90, 8.0, 17.35, 1.6


def _ink_across(art, y, x0, x1):
    """How much ink a horizontal slice at `y` crosses between x0 and x1."""
    strip = art & ic.rect(x0, y, x1, y + 0.2)
    return sum(c.bounds[2] - c.bounds[0] for c in ic.contours(strip))


@recipe("alef_near_alef_24_filled")
def _alef_near_alef():
    """The small alef beside the big one, brought back inside the canvas.

    The drawing was placed 0.86 units past the left edge, so the small letter's
    tail was cut off by the glyph's own box - the one icon in the set whose
    artwork left the canvas. It is scaled (by half a percent) and moved into the
    same 0.95-unit margin every other two-letter icon here keeps. This edits its
    own source, so it stands down once the drawing is inside.
    """
    art = glyph("alef_near_alef_24_filled")
    x0, y0, x1, y1 = art.bounds
    if x0 >= PAIR_LEFT - 0.01:
        raise Restated("alef_near_alef_24_filled is already inside the canvas")
    right = 24 - PAIR_LEFT
    return art.fit((PAIR_LEFT, y0, right, y1)), [], False


@recipe("alef_near_alef_stam_24_filled")
def _alef_near_stam():
    """The square alef facing the STA"M one."""
    return pair(glyph("alef_24_filled"), glyph("alef_stam_24_filled")), [], False


@recipe("alef_near_alef_rashi_24_filled")
def _alef_near_rashi():
    """The square alef facing the Rashi one."""
    return pair(glyph("alef_24_filled"), glyph("alef_rashi_24_filled")), [], False


@recipe("alef_latin_a_24_filled")
def _alef_latin_a():
    """The alef facing a Latin A."""
    return pair(glyph("alef_24_filled"), latin_a()), [], False


@recipe("beit_24_filled")
def _beit():
    """Give the beit's back its weight back, and nothing else.

    The letter was made by eroding `beit_near_alef`'s letterform 0.45 units on
    every flank, which took 0.90 off every stroke. The back could not afford it:
    it measured 1.53 units at the shoulder but tapered to **0.397** at
    mid-height - under half a pixel at 24 px - so the letter read as a top and a
    base joined by a hair, which is nothing like the alef or the tet, neither of
    which has ink under 0.9 anywhere.

    Only the back's own left edge moves, and it moves to a *fitted* curve
    rather than to a smoothed copy of itself. The letterform is hand-drawn and
    carries small nicks along that edge; a traced or averaged edge carries them
    straight into the repair, which is what the owner saw as tremors in the
    lower back. A polynomial cannot carry them: it is smooth by construction,
    so what lands on the letter is one clean stroke edge from the corner under
    the bar down into the base.
    """
    art = glyph("beit_24_filled")
    # Guard on the defect itself - the ink across the back at mid-height -
    # rather than on "is there any thin ink left". There always is: the base's
    # terminals are cut on a slant, so they taper to a point and answer that
    # question yes however often this is run.
    waist = _ink_across(art, 15.0, 14.0, 20.0)
    if waist > 1.00:
        raise Restated("beit_24_filled's back already measures %.2f units at "
                       "mid-height" % waist)
    return art.pad_left_edge(BEIT_TOP, BEIT_FOOT, 14.0, 20.0,
                             BEIT_RESTORE, BEIT_EASE), [], False


# The line weight the outlined book stack is drawn at, and it is drawn *inside*
# the solid. The books are only 0.70 apart, so a line straddling their outlines
# spends half its width on each side of that gap and closes it: at 1.00 the
# stack came out as one black block, and at 0.75 the paper between two covers
# was still a hairline. Kept inside, the gaps survive whole and the weight is
# free to be what the drawing wants - half a unit, which also leaves the 1.20
# arms of the middle books a visible core.
BOOKS_LOW_LINE = 0.50

DEPENDS["books_stacked_low_24_regular"] = "books_stacked_low_24_filled"


@recipe("books_stacked_low_24_regular")
def _books_low():
    """The low stack as an outline drawing, from the solid one.

    The solid is three closed contours, one per book, each already cut where
    the book above it covers it - so outlining them one at a time draws exactly
    the lines a reader would see and none of the hidden ones. The line is kept
    inside each book, which is what leaves the paper between them; see
    `Art.outlined`. That also means the outline and the solid share a
    silhouette, so this needs no resizing of its own.
    """
    return glyph("books_stacked_low_24_filled").outlined(
        BOOKS_LOW_LINE, inside=True), [], False


@recipe("bookshelf_24_regular")
def _bookshelf():
    """Thinned 15%, and nothing else.

    A uniform inward offset is exactly that: every point of the outline travels
    along its own normal, so the drawing - the books' widths, their lean, the
    shelf - is untouched and only the weight changes. Half of 15% of the mean
    stroke is what takes 15% off the stroke, since an offset takes it off both
    sides.
    """
    art = glyph("bookshelf_24_regular")
    before = art.mean_stroke()
    if before < 0.95:
        raise Restated("bookshelf_24_regular is already at a %.3f mean stroke; "
                       "thinning again would take it under three quarters of a "
                       "pixel at 24 px" % before)
    return art.shrink(before * 0.15 / 2), [], False


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

    return sized((art - bars) | text).grow(SCROLL_GROW), [], False


@recipe("links_24_filled")
def _links_filled():
    """links_24_regular, every stroke 1.5x thicker.

    `inverted()` - the "invert every white area, add a thin outer line" rule
    the rest of the set's filled variants take - is built for a single closed
    silhouette (a book cover, a letter): it works from `contours(art)[0]`, the
    *largest* contour, on the assumption that it is the one silhouette the
    whole icon is drawn on. `links_24_regular` is two nearly-equal chain rings
    side by side (64.84 and 64.83 square units - neither "the" largest), so
    that rule keeps one ring and drops the other. A stroke icon like this one
    does not need inverting at all: its regular *is* the drawing, and Fluent's
    own filled/regular pairs for stroke icons are literally the same stroke
    thickened, which is exactly what the owner asked for here. `grow` offsets
    every edge outward by the same amount on both sides of each stroke, so it
    thickens without altering the drawing - not a re-render, the same path,
    heavier.
    """
    art = glyph("links_24_regular")
    before = art.mean_stroke()
    target = before * 1.5
    return art.grow((target - before) / 2), [], False


@recipe("link_24_regular")
def _link_plain():
    """Fluent's own plain link, sized to fill the canvas like every other icon
    in the set that is drawn as large as it will go.

    Taken from Fluent rather than drawn free-hand, for the same reason every
    badged link in this set is: it is the same chain the badge icons already
    carry (`link_dismiss_24_regular`'s own link is Fluent's chain with a
    corner cut for a disc), so the plain link and the badged ones read as the
    same drawing rather than as two different chains.
    """
    return sized(use_fluent("link_24_regular")), [], False


# --------------------------------------------------------------------------
# clock_add: canvas fill, a larger badge, and a plus that survives small sizes
# --------------------------------------------------------------------------
# How much larger the plus is set inside the enlarged disc, on top of the
# family's usual SYMBOL_REACH - the owner asked for it "noticeably larger",
# not merely along for the disc's own 15%.
CLOCK_ADD_PLUS_REACH = 1.12

# How much extra weight the plus is grown by after being fitted, so it reads
# at 16-20 px. `sym_plus`'s own stroke already carries the family's usual
# BADGE_MIN_STROKE; this is on top of that, same idea as `weighted`'s
# regrowth but pushed further because a plus is the one badge mark with
# nothing else to lose to a thicker stroke - no gap between two strokes to
# close, no counter to fill.
#
# First set to 0.30 (mean stroke 3.67), which the owner reviewed as too
# thick. A negative `grow` shrinks - see `Art.grow` - and -0.15 here lands the
# mean stroke at 2.4: comfortably more than 25% under 3.67, and still over
# twice the original icon's own 1.13, which was reviewed as too thin to read
# at small sizes.
CLOCK_ADD_PLUS_GROW = -0.15


@recipe("clock_add_24_regular")
def _clock_add():
    """Enlarge the badge disc 15% (this family's own rule, matching the link
    badges), and redraw the plus larger and heavier so it still reads at a
    small rendered size, then fill the canvas.

    Rebuilt from the file's own three raw paths rather than through `glyph`,
    because the two knockout paths (badge disc, then the plus knocked out of
    it) are told apart by position here, not by `fill="white"` - this source
    predates that convention (it is one of `LEGACY_INFERRED_KNOCKOUTS` in
    `repair_glyphs.py`) - and the plus is being replaced outright, not kept.
    `write` marks the new cut explicitly, so the source no longer needs the
    legacy inference to render correctly.
    """
    clock = part("clock_add_24_regular", 0)
    disc = part("clock_add_24_regular", 1)
    x0, y0, x1, y1 = (clock | disc).bounds
    if max(x1 - x0, y1 - y0) >= CANVAS_BOX - 0.05:
        raise Restated("clock_add_24_regular already measures %.2f x %.2f "
                       "units; rebuilding it would enlarge it again"
                       % (x1 - x0, y1 - y0))
    corner = _anchor_corner(disc.bounds)
    disc2 = disc.scale(1.15, about=corner)
    # An earlier version of this recipe clipped the clock's hand (both its
    # upright stroke and its horizontal arm, drawn as one bent shape - the
    # smallest of the clock's three contours) back from the enlarged disc's
    # edge, meaning to trim only the small spur where the hand's corner poked
    # a notch into the union's silhouette. The clip line fell to the left of
    # most of the arm instead and cut the whole arm away, leaving what looked
    # like a clock with one hand. The two are simply unioned here instead:
    # the arm's own length already falls almost entirely inside the enlarged
    # disc's own footprint, so it is covered by solid badge ink there rather
    # than sticking out past it, and nothing needs trimming.
    plus = sym_plus().fit_radius(disc2.radius() * SYMBOL_REACH
                                 * CLOCK_ADD_PLUS_REACH)
    plus = plus.grow(CLOCK_ADD_PLUS_GROW).centred_on(*disc2.centre)
    solid, cuts = fill_canvas_pair(clock | disc2, [plus])
    return solid, cuts, True


# --------------------------------------------------------------------------
# book_add / book_exclamation: the same closed-book cover the other book_*
# icons carry a centred mark on (book_download, book_star, book_search, ...),
# with a new mark centred the way `book_download`'s own arrow is.
#
# The reviewer asked for these brought in from Fluent's own `book_add`,
# `book_star` and `book_exclamation_mark`, mirrored to match this set's own
# orientation. Two things changed that plan on inspection rather than by
# guess, and both are worth recording for whoever reads this next:
#
#   - `book_star_24_regular/_filled` already exist in this set, and already
#     carry a star centred on the cover - not a Fluent corner badge, but
#     Fluent's own `book_star_24_regular` isn't a corner badge either: only
#     `book_add` puts its mark in a disc, and Fluent's own `book_star` and
#     `book_exclamation_mark` centre theirs on the cover exactly the way this
#     set's `book_download`/`book_search`/etc. already do. So the existing
#     `book_star` is left untouched rather than replaced or duplicated under
#     another name, and `book_add`/`book_exclamation` are drawn to match it
#     and the rest of the centred-mark family, not to match `book_add`'s own
#     one Fluent badge.
#   - The mirror itself did not hold up against the file it was to be
#     checked against: `books_stacked_low_24_regular` - rendered and read
#     directly rather than assumed - draws each book's spine on the *left*,
#     the same side Fluent draws it, not the right. `book_download`'s own
#     cover, the shape these two are built from, is left-right symmetric (no
#     spine drawn at all), so there is nothing in it to mirror one way or the
#     other. Between a symmetric shared cover and a spine side the one
#     asymmetric file in the set draws the same way Fluent does, no mirror is
#     applied here; this is flagged in the session report for the reviewer to
#     re-check against whatever reference image prompted the request.
def _book_cover():
    """(outer cover silhouette, its own interior cut) from
    `book_download_24_regular`'s single merged path: contour 0 is the cover's
    own outer ribbon shape, contour 1 the cut that hollows it to a stroke
    width, and contour 2 its own arrow mark, which is not wanted here."""
    full = part("book_download_24_regular", 0)
    cs = ic.contours(full)
    return cs[0], cs[1]


def _book_marked(mark, filled):
    """A closed-book cover with `mark` on it, matching how
    book_download/book_star/etc. already pair a cover with a mark.

    The two variants place the mark oppositely, not just the cover
    differently. A *regular* cover is hollowed to its own stroke width first
    (`outer - inner`), leaving a white interior, and the mark is drawn on top
    of that as solid ink - `book_download_24_regular`'s own arrow is a third
    solid contour, unioned in. A *filled* cover is solid all the way through,
    so adding the same mark as more solid ink would vanish into it - and
    `book_download_24_filled` does not do that: its arrow is *knocked out* of
    the solid cover instead, white on black. `write` always marks a cut with
    `fill="white"`, so a filled icon here needs the mark passed back as a
    `cuts` list, not unioned into the solid.
    """
    outer, inner = _book_cover()
    if filled:
        return outer, [mark]
    return (outer - inner) | mark, []


# The block book_download's own arrow occupies - x 7.5 to 16.5, y 6 to 16.5 -
# reused as the block a new centred mark sits in, so every centred-mark book
# in the set shares one placement rather than each guessing its own. Only
# `book_exclamation` uses this now - see the note above `_book_cover` for why
# `book_add` does not.
BOOK_MARK_BLOCK = (7.5, 6.0, 16.5, 16.5)


def _book_exclamation_mark():
    x0, y0, x1, y1 = BOOK_MARK_BLOCK
    cx, _, _, y1 = (x0 + x1) / 2, y0, x1, y1
    bar = round_rect(cx - 1.1, y0 + 0.5, cx + 1.1, y1 - 3.5, 1.1)
    dot = circle(cx, y1 - 1.5, 1.6)
    return bar | dot


# book_add: a corner badge, not a centred mark - checked against Fluent's own
# book_add_24_regular (its badge sits at roughly x 12-23, y 12-23 on a 24-unit
# canvas: bottom right, overlapping the cover's own corner) and against this
# set's own alef/link badges (a solid disc, a knocked-out mark, radius 4.5-5.5
# in the same corner), which the two turn out to agree on. Centre kept where
# it was against book_download's cover; radius enlarged 10% on review (5.06,
# from 4.6).
BOOK_ADD_BADGE = (17.3, 18.85, 4.6 * 1.10)


def _book_add_badge():
    cx, cy, r = BOOK_ADD_BADGE
    disc = circle(cx, cy, r)
    mark = sym_plus().fit_radius(r * SYMBOL_REACH).centred_on(cx, cy)
    return disc, mark


def _book_title_bar():
    """The title-bar rectangle `book_24_regular`/`_filled` carry on their
    cover, which `book_download`'s own cover (what `_book_cover` reads) does
    not have: its own mark sits where the title bar would, and book_add's
    badge sits at the corner instead, leaving that spot bare. Read the same
    way `_book_cover` reads book_download's: by contour, from book_24's own
    single merged path.

    The two are not the same kind of shape. `book_24_regular`'s bar is a
    hollow-bordered *solid* - `reg_cs[2] - reg_cs[3]`, ink drawn on the
    interior's own white - because the interior is already white there. But
    `book_24_filled`'s cover is solid black straight through, so its bar
    (`fil_cs[1]`) is a *hole* cut into it - `fil_cs[0].area - fil_cs[1].area`
    equals `full.area` exactly, confirming it - the same way `book_download`
    and `book_add`'s own marks are knocked out of a filled cover rather than
    drawn on top of one. A first version of this unioned the filled bar in as
    more solid ink instead, which put it on top of an already-solid cover and
    made it invisible - the same bug the very first version of book_add's own
    plus mark had, and the same fix: return it for the caller to knock out,
    not union in.
    """
    reg_cs = ic.contours(part("book_24_regular", 0))
    fil_cs = ic.contours(part("book_24_filled", 0))
    bar_regular = reg_cs[2] - reg_cs[3]
    bar_filled_cut = fil_cs[1]
    return bar_regular, bar_filled_cut


@recipe("book_add_24_regular")
def _book_add_r():
    outer, inner = _book_cover()
    disc, mark = _book_add_badge()
    bar_regular, _ = _book_title_bar()
    return (outer - inner) | disc | bar_regular, [mark], True


@recipe("book_add_24_filled")
def _book_add_f():
    outer, inner = _book_cover()
    disc, mark = _book_add_badge()
    _, bar_filled_cut = _book_title_bar()
    return outer | disc, [mark, bar_filled_cut], True


@recipe("book_exclamation_24_regular")
def _book_exclamation_r():
    solid, cuts = _book_marked(_book_exclamation_mark(), filled=False)
    return solid, cuts, False


@recipe("book_exclamation_24_filled")
def _book_exclamation_f():
    solid, cuts = _book_marked(_book_exclamation_mark(), filled=True)
    return solid, cuts, True


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


# Every filled variant in the set, by the one rule in `inverted`. They all get
# the same treatment because the rule is the same for all of them - which is
# what makes a filled icon look like its regular twin, and what the earlier
# per-family derivations, each offsetting its own cover, could not do.
#
# `otzaria_icon_24_filled` is back on this list. It was briefly a drawing of its
# own again, to get the wider paper gap the original had, and the cost of that
# was the thing the owner weighed it against: a drawing does not follow its
# regular. Every other icon in the set is redrawn by re-running this; that one
# would have had to be redrawn by hand every time.
for _name in ["book_open_medium_24_filled",
              "book_open_medium_line_24_filled",
              "book_open_medium_search_24_filled",
              # These three were drawn, not derived, and the drawing never
              # picked up the text change its regular twin had: six rules
              # against four. Deriving them keeps the two in step from here on.
              "book_open_large_24_filled",
              "book_open_large_lines_24_filled",
              "book_open_large_search_24_filled",
              "book_open_small_24_filled",
              "book_open_small_line_24_filled",
              "otzaria_icon_24_filled",
              "otzaria_icon_line_24_filled",
              "otzaria_icon_2_page_24_filled",
              "otzaria_icon_2_page_line_24_filled",
              "otzaria_icon_empty_24_filled",
              "books_stacked_high_24_filled"]:
    DEPENDS[_name] = _name.replace("_filled", "_regular")

    def _inv(base=_name.replace("_filled", "_regular"), name=_name):
        solid, cuts = inverted(base)
        # A derived filled icon inherits its regular's size, and then the rule
        # adds its outer line outside that - so in the two families that fill
        # the canvas the derivation would push the drawing off it. Bringing the
        # result back to the box is a uniform scale of the whole icon: the pair
        # still shares every line, and both of them fill the canvas.
        return (sized(solid) if fills_canvas(name) else solid), cuts, False
    RECIPES[_name] = _inv


# The families the owner asked to have as large as the canvas will take,
# regular and filled alike.
CANVAS_FAMILIES = ("book_open_large", "otzaria_icon", "books_stacked",
                   # The magnifiers. The two plain ones very nearly filled the
                   # box already, but every `search_in_*` was drawn inside a
                   # 19-unit square - a fifth smaller than the icons it sits
                   # beside in a toolbar, which is exactly what it looked like.
                   "search")

# The icons whose corners are cut square rather than eased. Only this family
# draws them that way; everything else in the set already turns its corners.
SQUARE_CORNERS = ("book_open_large",)


def fills_canvas(name):
    return name.startswith(CANVAS_FAMILIES)


def steps_for(name, *first):
    """The in-place chain for one icon: whatever redraws it, then the two
    treatments a whole family can carry."""
    steps = list(first)
    if name.startswith(SQUARE_CORNERS):
        steps.append(ease_corners)
    if fills_canvas(name):
        steps.append(fill_canvas)
    return in_place(name, *steps)


for _name in RESTRIPE:
    RECIPES[_name] = steps_for(_name, restripe)


for _name in RESPREAD:
    RECIPES[_name] = steps_for(_name, respread)


# The rest of those families: nothing to redraw, only the treatments. The
# filled ones that are derived are already covered above; `books_stacked_low`'s
# filled is here because it is the drawing its own regular is outlined from.
for _name in ["book_open_large_24_regular",
              "otzaria_icon_2_page_24_regular",
              "otzaria_icon_empty_24_regular",
              "books_stacked_high_24_regular",
              "books_stacked_low_24_filled"]:
    RECIPES[_name] = steps_for(_name)


# The search family, all of it. Nothing here is derived or redrawn - each one
# is its own drawing and the only treatment it takes is the canvas fill, so the
# list is just the names on disk.
for _name in sorted(os.path.basename(p)[:-4]
                    for p in glob.glob(os.path.join(ic.SVG_DIR, "search*.svg"))):
    RECIPES[_name] = steps_for(_name)


# --------------------------------------------------------------------------
# search_in_*: the magnifier redrawn from search_24_regular's own, thickened
# --------------------------------------------------------------------------
# Every `search_in_*_24_regular` source is one merged path - ring, handle and
# inner content already resolved into a single nonzero-wound outline, the
# same shape `search_24_regular` itself is stored as (see `write`, which
# marks a *knockout* icon with `data-preserve-overlap`; a plain union like
# these needs no such marker). Split by contour containment rather than by
# raw path index, so it does not matter how many sub-paths a given icon's own
# content happens to carry:
#   contours(icon)[0]  - the largest contour - is the ring+handle's own outer
#                        silhouette, since the ring necessarily encloses
#                        everything else the icon draws;
#   contours(icon)[1]  - the second largest - is the lens opening, since the
#                        content sits inside it and so can never be larger;
#   icon & lens         - the content itself, whatever shape it takes, found
#                        by intersecting the icon with its own lens opening
#                        rather than enumerated, so no per-icon content list
#                        has to be kept in step with what each one draws.
def _search_ring_template():
    """(outer silhouette, lens opening) of search_24_regular's own ring, the
    two contours every search_in_* icon's ring is replaced with."""
    full = part("search_24_regular", 0)
    cs = ic.contours(full)
    return cs[0], cs[1]


# The radius, from the lens's own centre, that separates the ring band from
# the handle in search_24_regular's outer contour. Sampled: the ring band's
# own points cluster tightly between 8.34 and 8.50 units from that centre,
# while the handle reaches out to 19.58 - so a circle at 9.0 keeps the whole
# ring band and excludes the whole handle. Needed because thickening only the
# ring (see `_search_redraw_split`) means growing the ring band and the
# handle separately: growing the two as one fused contour, which is what the
# first version of this recipe did, thickens the handle right along with the
# ring, and the reviewer's own measurement is that the handle should come out
# identical to search_24's - same angle, length and weight, only uniformly
# scaled - not thickened.
SEARCH_RING_BAND_RADIUS = 9.0


def _search_ring_and_handle(outer, lens, scale):
    """Split a placed (outer, lens) pair into (ring band alone, handle
    alone), by distance from the lens's own centre rather than by any
    property of the contour itself, since the two are one fused shape.
    `scale` is the same factor `place()` scaled the template by, so the
    band/handle boundary radius - measured on the unscaled template - grows
    or shrinks along with everything else instead of cutting the ring band
    off short (or eating into the handle) on an icon fitted to a larger or
    smaller lens.
    """
    disc = circle(*lens.centre, SEARCH_RING_BAND_RADIUS * scale)
    return outer & disc, outer - disc


def _search_split(name):
    """(outer silhouette, lens opening, content) of one search_in_* icon."""
    full = part(name, 0)
    cs = ic.contours(full)
    outer, lens = cs[0], cs[1]
    return outer, lens, full & lens


def _search_not_found_badge():
    """search_24_regular's own ring+handle, empty lens, with a small corner
    badge - a disc with the alef family's own X knocked out of it - added
    opposite the handle.

    Replaces the earlier design, which confined an X to the lens opening by
    dividing it into four petal-shaped gaps: it read as a target reticle
    more than a "not found" mark, and the petal-splitting it needed was
    fragile geometry unique to this one icon. A corner badge is what this
    set already uses for exactly this reading - `alef_deletion`,
    `link_deletion` - proven to read clearly at small sizes, and reusing
    `sym_cross` (the same X, not a redrawn one) keeps that reading
    consistent rather than adding a second "not found" mark to the set.
    """
    t_outer, t_lens = _search_ring_template()
    lcx, lcy = t_lens.centre
    lr = t_lens.radius()
    bx, by = lcx - lr * 0.72, lcy + lr * 0.72
    badge_r = lr * 0.44

    # The reviewer's actual ask was the badge *unit* - disc and X together -
    # scaled up as one group, anchored at a corner, the same operation the
    # alef/link badge families already take (there at 15-20%; here asked for
    # 3x). `_anchor_corner` - anchor at whichever canvas corner (0 or 24 on
    # each axis) the shape's own centre is nearest - is the wrong anchor for
    # this particular badge: it sits at roughly the ring's own 8-o'clock edge,
    # not near any actual canvas corner, so scaling about a canvas corner from
    # there swings the badge wildly off-canvas well before 3x (checked: past
    # y=0 by 2x). Anchored instead at the disc's own outer tangent point - on
    # the line from the lens centre through the badge centre, at the disc's
    # far edge, the point already sitting against the ring - growing the
    # badge stays docked there and grows inward, the way the alef/link badges
    # stay docked on their own canvas corner while growing inward. At the
    # full 3x this reviewer asked for, the badge (diameter ~18) swallows most
    # of the lens (diameter ~13.6) and clips half a unit past the canvas edge;
    # 2.2x is the largest factor that keeps the whole badge on-canvas and
    # leaves the ring/handle still legible as a ring - confirmed on review.
    dx, dy = bx - lcx, by - lcy
    dist = math.hypot(dx, dy)
    anchor = (bx + badge_r * dx / dist, by + badge_r * dy / dist)
    group_scale = 2.2
    # Nudged down a little on review, after the size itself was confirmed -
    # a plain translate of the already-scaled, already-docked group, so the
    # docking and the scale factor above are both untouched.
    shift_down = 0.6

    badge = (circle(bx, by, badge_r).scale(group_scale, about=anchor)
            .translate(0, shift_down))
    mark = (sym_cross().fit_radius(badge_r * 0.88).deburr(0.05)
            .centred_on(bx, by).scale(group_scale, about=anchor)
            .translate(0, shift_down))
    ring = (t_outer - t_lens) | badge
    return sized(ring), [mark]


# How much the ring's own band is thickened, outward only - the lens opening
# that is matched to the icon's own (see `_search_redraw`) is left exactly as
# it was, so the content inside it keeps the room it was drawn for.
SEARCH_RING_GROW_FRACTION = 0.20


def _search_redraw_split(name, split):
    """Replace the ring+handle `split` finds in `name`'s own source with
    search_24_regular's, fitted to the same icon's own lens opening so its
    content keeps its size and place, thickened 20% outward, then the whole
    icon scaled to fill the canvas.
    """
    t_outer, t_lens = _search_ring_template()
    i_outer, i_lens, content = split()

    tcx, tcy = t_lens.centre
    icx, icy = i_lens.centre
    scale = i_lens.radius() / t_lens.radius()

    def place(art):
        return art.scale(scale, about=(tcx, tcy)).translate(icx - tcx, icy - tcy)

    new_outer = place(t_outer)
    new_lens = place(t_lens)                 # coincides with i_lens
    ring_band, handle = _search_ring_and_handle(new_outer, new_lens, scale)
    band_width = (ring_band - new_lens).mean_stroke()
    grown_band = ring_band.grow(band_width * SEARCH_RING_GROW_FRACTION)

    # Idempotency guard: once this has run, the icon's own outer silhouette
    # already *is* the grown, placed template (ring band thickened, handle
    # not), so a second run would grow the ring band again on top of that.
    grown_outer = grown_band | handle
    diff = (grown_outer - i_outer).area + (i_outer - grown_outer).area
    if diff < max(1.0, i_outer.area * 0.03):
        raise Restated("%s's ring already looks redrawn from the template "
                       "and thickened" % name)

    ring = (grown_band - new_lens) | handle
    return sized(ring | content), [], False


def _search_redraw(name):
    return _search_redraw_split(name, lambda: _search_split(name))


SEARCH_IN_NAMES = [os.path.basename(p)[:-4] for p in
                  sorted(glob.glob(os.path.join(ic.SVG_DIR, "search_in_*.svg")))]

for _name in SEARCH_IN_NAMES:
    def _search_redraw_recipe(name=_name):
        return _search_redraw(name)
    RECIPES[_name] = _search_redraw_recipe


# `inverted`'s default FILLED_EDGE (0.55) is tuned for a cover silhouette, and
# on these rings it comes out at a 0.52 mean stroke - about half of
# `search_24_filled`'s own outer ring, measured at 0.91 (`outer - second`,
# the same two contours `inverted` itself builds from). 1.00 lands the
# derived ring at 0.91, matching it.
SEARCH_FILLED_EDGE = 1.00

for _name in SEARCH_IN_NAMES:
    _filled_name = _name.replace("_24_regular", "_24_filled")
    DEPENDS[_filled_name] = _name

    def _search_filled_recipe(base=_name, name=_filled_name):
        solid, cuts = inverted(base, edge=SEARCH_FILLED_EDGE)
        return sized(solid), cuts, False
    RECIPES[_filled_name] = _search_filled_recipe

# `search_not_found_24_regular/_filled` don't match the `search_in_*` glob
# the family loop above targets, so they were missed the first time.
def _search_not_found_r():
    solid, cuts = _search_not_found_badge()
    return solid, cuts, True


RECIPES["search_not_found_24_regular"] = _search_not_found_r
DEPENDS["search_not_found_24_filled"] = "search_not_found_24_regular"


def _search_not_found_filled_recipe():
    solid, cuts = inverted("search_not_found_24_regular", edge=SEARCH_FILLED_EDGE)
    return sized(solid), cuts, False


RECIPES["search_not_found_24_filled"] = _search_not_found_filled_recipe

RECIPES["otzaria_icon_24_regular"] = steps_for("otzaria_icon_24_regular",
                                               round_rule_ends)



for _kind, _name in [("scissors", "alef_scissors_24_filled"),
                     ("lips", "alef_lips_24_filled"),
                     ("marker", "alef_marker_24_filled"),
                     ("eye", "alef_eye_24_filled"),
                     ("eraser", "alef_with_eraser_24_filled"),
                     ("exclamation", "alef_with_exclamation_24_filled"),
                     ("plus", "alef_addition_24_filled"),
                     ("lock", "alef_lock_24_filled"),
                     ("crown", "alef_crown_24_filled")]:
    RECIPES[_name] = alef_badge(_kind)

for _kind, _name in [("copy", "link_copy_24_regular"),
                     ("eraser", "link_with_eraser_24_regular"),
                     ("marker", "link_marker_24_regular"),
                     ("information", "link_with_information_24_regular"),
                     ("quote", "link_quote_24_regular"),
                     ("document", "link_document_24_regular"),
                     ("scissors", "link_scissors_24_regular"),
                     ("cross", "link_deletion_24_regular"),
                     ("eye", "link_eye_24_regular"),
                     ("alef", "link_alef_24_regular"),
                     ("plus", "link_add_24_regular"),
                     ("book_empty", "link_book_empty_24_regular"),
                     ("exclamation", "link_book_exclamation_24_regular")]:
    RECIPES[_name] = link_badge(_kind)
    RECIPES[_name.replace("_regular", "_filled")] = link_badge(_kind, True)


@recipe("link_24_filled")
def _link_plain_filled():
    """`link_24_regular`'s drawing in Fluent's heavier weight, sized the same."""
    return sized(use_fluent("link_24_filled")), [], False


# --------------------------------------------------------------------------
# Filled twins that were simply missing
# --------------------------------------------------------------------------
# Icons that shipped with a regular and nothing to select with. Each filled one
# is the one rule in `inverted` applied to its regular, so it follows the
# regular from here on - the same as every other derived filled icon above.
# The rule adds a line outside the silhouette, and these drawings already reach
# the edge of the canvas box, so the result is brought back to the box as one
# uniform scale (as for the families that fill the canvas).
def _inverted_recipe(regular, fit=False):
    def build():
        solid, cuts = inverted(regular)
        x0, y0, x1, y1 = solid.bounds
        if fit and (min(x0, y0) < 0.5 or max(x1, y1) > 23.5):
            solid = sized(solid)
        return solid, cuts, False
    return build


for _base, _fit in [("booklet", False), ("booklet_empty", False),
                    ("clock_add", True), ("dependent_library", True),
                    ("torah_scroll", True)]:
    RECIPES[_base + "_24_filled"] = _inverted_recipe(_base + "_24_regular", _fit)
    DEPENDS[_base + "_24_filled"] = _base + "_24_regular"


# --------------------------------------------------------------------------
# yoma_deilula: a candle in front of a calendar
# --------------------------------------------------------------------------
# `inverted` takes the icon's largest contour as *the* silhouette, and this
# icon is two separate drawings - so it is applied to each of them in turn. The
# candle's own outline is closed and inverts as it is. The calendar's is not:
# the frame stops short where the candle stands in front of it, so there is no
# closed silhouette to invert, and one is built - the page's rectangle, with the
# candle's footprint cut out of it. The cut is deeper than the gap the regular
# draws, because the filled icon puts a line of its own outside each shape and
# the two lines have to leave the same air between them that the regular does.
#
# Two things are kept as the regular draws them rather than inverted: the
# binder rings (an inverted ring is a 0.6-unit sliver inside a 0.8-unit band,
# which is nothing at 24 px) and the slits through them. The nine date cells
# come out as plain white squares.
YOMA_PAGE = (7.6, 3.2, 23.8, 20.9)
YOMA_PAGE_CORNER = 1.6
YOMA_CUT = 1.9


@recipe("yoma_deilula_24_filled")
def _yoma_filled():
    art = glyph("yoma_deilula_24_regular")
    cl = ic.contours(art)
    frame, candle = cl[0], cl[1]
    slits = [c for c in cl if 1.3 < c.area < 1.5]
    cells = [c for c in cl if 6.0 < c.area < 8.0 and c.bounds[0] > 9]
    if len(slits) != 3 or len(cells) != 9:
        raise Restated("yoma_deilula_24_regular no longer has the three "
                       "binder slits and nine date cells this reads (%d, %d)"
                       % (len(slits), len(cells)))
    page = round_rect(*YOMA_PAGE, YOMA_PAGE_CORNER) - candle.grow(YOMA_CUT)
    out = Art()
    for body in (page, candle):
        out = out | (body - art) | (body.deburr().grow(FILLED_EDGE) - body)
    for cell in cells:
        out = out - cell
    out = out | (frame & ic.rect(0, 0, 24, 4.0))
    for slit in slits:
        out = out - slit
    out = out.despeckle(SPECK).fill_holes(SPECK).prune(0.002)
    return sized(out), [], False


DEPENDS["yoma_deilula_24_filled"] = "yoma_deilula_24_regular"


# A list whose rows are text rules and letters. The filled variants of the other
# lists (`text_bullet_list`, `text_number_list`) keep every rule's length and
# take it from 1.5 to 2.0 units tall, and the marks beside them get a little
# heavier; that is all the weight a list gains, and it is what this does.
LIST_RULE_HEIGHT = 2.0
LIST_MARK_GROW = 0.25


@recipe("text_alef_bet_list_24_filled")
def _alef_bet_list_filled():
    art = glyph("text_alef_bet_list_24_regular")
    out = Art()
    for c in ic.contours(art):
        x0, y0, x1, y1 = c.bounds
        if x1 - x0 > 8:                       # a text rule
            cy = (y0 + y1) / 2
            out = out | round_rect(x0, cy - LIST_RULE_HEIGHT / 2, x1,
                                   cy + LIST_RULE_HEIGHT / 2,
                                   LIST_RULE_HEIGHT / 2)
        else:                                 # a letter
            out = out | c.grow(LIST_MARK_GROW)
    return out, [], False


DEPENDS["text_alef_bet_list_24_filled"] = "text_alef_bet_list_24_regular"


# `icon_x` was drawn with a 3.3-unit stroke - twice Fluent's 1.5 and heavier
# than any other regular in the set - and filed as `_regular`. That is a filled
# weight, so it moves to `_filled` untouched, and the regular is Fluent's own
# `dismiss` at the same extent (it is the same mark), which is what a regular
# cross is everywhere else.
ICON_X_BOX = (2.0, 2.0, 22.0, 22.0)


@recipe("icon_x_24_regular")
def _icon_x_regular():
    return use_fluent("dismiss_24_regular").fit(ICON_X_BOX), [], False


# --------------------------------------------------------------------------
# The letters: a solid `_filled` and an outlined `_regular`
# --------------------------------------------------------------------------
# Every letter icon was drawn as a solid body and filed as `_regular`, so the
# whole alef/beit/tet family had a "regular" that was a filled icon - and no
# filled twin to select. The solid drawings now live under `_filled`, exactly as
# they were, and the `_regular` is derived from them here.
#
# A solid letter turns into an outline one the way `alef_24_regular` is already
# drawn: the letter's own boundary, kept inside the shape so the silhouette (and
# with it the icon's size) does not move. Strokes thinner than two lines come
# through solid, which is right - the hairlines of a letter, a dot, a numeral
# stay readable instead of dissolving into a pair of parallel threads.
LETTER_LINE = 0.50

# A badge on an outlined letter is a ring with its mark drawn as ink inside it -
# the same pairing the book family uses (`book_add_24_regular`'s plus sits in an
# outlined circle, `book_add_24_filled`'s is knocked out of a solid one). The
# ring is a little heavier than the letter's own line because it carries the
# badge, the gap is what keeps the letter's foot from running into it, and the
# air is what keeps the mark off the ring.
BADGE_RING = 0.90
BADGE_RING_GAP = 0.55
BADGE_RING_AIR = 0.50

# Which recipe supplied the Fluent artwork a derived icon inherits, so that its
# provenance follows the icon it was derived from rather than resetting to
# "custom".
PROVENANCE_OF = {}


def letter_outline(art):
    return art.deburr().outlined(LETTER_LINE, inside=True)


def ring_badge(letter, disc, mark):
    """An outlined `letter` carrying a ring badge: the letter is cut back from
    the disc by BADGE_RING_GAP, the disc becomes a ring, and `mark` - which the
    solid icon knocks out of its disc - is drawn as ink inside it, brought down
    to fit within the ring."""
    inner = disc.radius() - BADGE_RING
    ring = disc.outlined(BADGE_RING, inside=True)
    ink = mark.fit_radius(inner - BADGE_RING_AIR, about=disc.centre)
    return (letter_outline(letter) - disc.grow(BADGE_RING_GAP)) | ring | ink


def _split_badge(filled):
    """(letter, disc, mark) of a badged letter icon, from its solid source.

    The mark is whatever the source cuts out. The disc is the second solid when
    the source keeps it as its own path, and otherwise the canonical badge disc,
    which is what every composed alef badge is built on.
    """
    solids, cuts = ic.layers(filled)
    mark = Art()
    for c in cuts:
        mark = mark | c
    disc = min(solids, key=lambda s: s.area) if len(solids) == 2 else badge()
    return alef_solid(), disc, mark


def outline_recipe(filled, badged_letter=False):
    def build():
        if badged_letter:
            letter, disc, mark = _split_badge(filled)
            return ring_badge(letter, disc, mark), [], False
        return letter_outline(glyph(filled)), [], False
    return build


# The letter icons whose badge is a disc with a mark in it, and the ones that
# are only letters (a numeral, a second letter, a pen, a dot count as part of
# the letter and take the same outline).
LETTER_BADGED = (
    "alef_addition", "alef_copy", "alef_crown", "alef_deletion", "alef_eye",
    "alef_lips", "alef_lock", "alef_marker", "alef_scissors",
    "alef_with_eraser", "alef_with_exclamation", "alef_with_information",
)
LETTER_PLAIN = (
    "alef_1", "alef_2", "alef_3", "alef_alef", "alef_behind_alef",
    "alef_latin_a", "alef_near_alef", "alef_near_alef_rashi",
    "alef_near_alef_stam", "alef_rashi", "alef_stam", "alef_with_flavors",
    "alef_with_punctuation", "alef_with_score", "alef_writing", "beit",
    "beit_behind_alef", "beit_near_alef", "tet", "tet_behind_tet",
    "tet_near_tet", "tet_tet",
)

for _letter in LETTER_PLAIN + LETTER_BADGED:
    _filled, _regular = _letter + "_24_filled", _letter + "_24_regular"
    RECIPES[_regular] = outline_recipe(_filled, _letter in LETTER_BADGED)
    DEPENDS[_regular] = _filled
    PROVENANCE_OF[_regular] = _filled


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


def _in_dependency_order(names):
    """`names`, alphabetical, except that whatever a recipe reads comes first.

    One run then builds everything from what this run produced, rather than one
    icon per run catching up with the last.
    """
    wanted, seen, out = set(names), set(), []

    def visit(n, stack=()):
        if n in seen:
            return
        if n in stack:
            raise ValueError("recipes depend on each other: %s"
                             % " -> ".join(stack + (n,)))
        dep = DEPENDS.get(n)
        if dep and dep in wanted:
            visit(dep, stack + (n,))
        seen.add(n)
        out.append(n)

    for n in sorted(names):
        visit(n)
    return out


def main(argv):
    names = [a for a in argv if not a.startswith("-")]
    if "--list" in argv:
        for n in sorted(RECIPES):
            print(n)
        return 0
    if not names:
        names = sorted(RECIPES)
    names = _in_dependency_order(names)
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
        used[n] = list(_USED) + used.get(PROVENANCE_OF.get(n), [])
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
