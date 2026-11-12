#!/usr/bin/env python3
"""Turn a letter traced from a bitmap into an icon source.

The input is what a bitmap tracer writes: one polygon of short straight steps, a
pixel across, on a canvas of a thousand-odd units, with a white background
rectangle. The output is a source for the letter icon family: the polygon
smoothed (its steps ironed out into a curve), scaled to the height the other
Stam letters have (`alef_stam`, `beit`, `tet` stand 2.9 to 21.1 on the canvas),
and centred.

Usage:
  python3 tool/import_traced_letter.py TRACED.svg NAME [--out-dir DIR]

writes NAME_24_filled.svg; the `_regular` is derived from it by compose_sources.py
(`vav_stam` is in `LETTER_PLAIN`).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import icon_compose as ic
from icon_compose import Art

# Where a Stam letter stands: the box of `alef_stam_24_filled`, whose height the
# letter is fitted to. The width follows from the letter's own proportions.
BOX = (4.65, 2.9, 19.35, 21.1)
# How much of a tracer's pixel steps is ironed out, in canvas units. The steps
# are about 0.016 units after scaling; this takes them out and leaves the
# calligraphic corners (a smoothing of 0.25 would round those off).
SIGMA = 0.07
STEP = 0.05


def trace(path):
    text = open(path, encoding="utf-8").read()
    art = Art()
    for tag in re.findall(r"<path\b[^>]*>", text):
        if re.search(r'fill="(white|#fff\w*)"', tag):
            continue
        d = re.search(r'\sd="([^"]+)"', tag)
        if d:
            art = art | Art.from_d(d.group(1))
    if art.is_empty:
        raise SystemExit("no ink found in %s" % path)
    return art


def letter(path):
    art = trace(path).fit(BOX)
    return art.smoothed(SIGMA, STEP)


def main(argv):
    out_dir = ic.SVG_DIR
    if "--out-dir" in argv:
        i = argv.index("--out-dir")
        out_dir, argv = argv[i + 1], argv[:i] + argv[i + 2:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    art = letter(argv[0])
    ic.SVG_DIR = out_dir
    ic.write("%s_24_filled" % argv[1], art)
    x0, y0, x1, y1 = art.bounds
    print("%s_24_filled: x %.2f-%.2f  y %.2f-%.2f  stroke %.2f"
          % (argv[1], x0, x1, y0, y1, art.mean_stroke()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
