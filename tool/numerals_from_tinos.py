#!/usr/bin/env python3
"""Print the NUMERALS table of compose_sources.py: the digits 1-5 that sit beside
the alef in alef_1 ... alef_5, all five cut from one font.

They used to be two different drawings (1, 2 and 3 of unknown origin, 4 and 5
traced from Times New Roman Bold, which is not a font this repository may
redistribute). The font here is Tinos, Google's Apache-2.0 metric twin of Times
New Roman, regular weight, thickened to the weight the alef carries beside them.

Usage:
  python3 tool/numerals_from_tinos.py path/to/Tinos-Regular.ttf

The outcome is pasted into compose_sources.py as `NUMERALS`; the font itself is
not needed to build the set.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

import icon_compose as ic
from icon_compose import Art

# Where the numerals stand, in canvas units: the baseline they all share, the
# height of a flat-topped figure, the middle of the column they are centred in,
# and how far the font's thin strokes are thickened (per side) so that a figure
# is as heavy as the letter next to it.
BASELINE = 19.1
HEIGHT = 7.0
CENTRE_X = 21.3
GROW = 0.15
# The old numerals were narrow (3.7-4.3 wide at 7.4-8.3 high); Tinos' are wider,
# and at full width they run into the alef's foot, which ends at x=19.3.
XSCALE = 0.75


def figures(font_path):
    font = TTFont(font_path)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    one = glyphs[cmap[ord("1")]]
    probe = SVGPathPen(glyphs)
    one.draw(probe)
    top = Art.from_d(probe.getCommands()).bounds[3]      # font units, y up
    scale = HEIGHT / top
    out = {}
    for n in range(1, 6):
        pen = SVGPathPen(glyphs)
        # y is flipped: the font's baseline is y=0 with ink above it.
        glyphs[cmap[ord(str(n))]].draw(TransformPen(pen, (scale * XSCALE, 0, 0, -scale,
                                                           0, BASELINE)))
        art = Art.from_d(pen.getCommands())
        x0, _, x1, _ = art.bounds
        art = art.translate(CENTRE_X - (x0 + x1) / 2, 0).grow(GROW)
        out[n] = art
    return out


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    print("NUMERALS = {")
    for n, art in figures(argv[0]).items():
        x0, y0, x1, y1 = art.bounds
        print("    # %d: x %.2f-%.2f  y %.2f-%.2f  mean stroke %.2f"
              % (n, x0, x1, y0, y1, art.mean_stroke()))
        print('    %d: "%s",' % (n, art.d(3)))
    print("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
