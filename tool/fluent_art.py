#!/usr/bin/env python3
"""Read an icon's outline straight out of the Fluent icon font.

WHY THIS EXISTS
---------------
Several icons here put a small Fluent mark on Otzaria artwork - a highlighter,
an eraser, a pair of scissors. Drawing those marks by hand does not work: they
come out as *a* highlighter rather than *the* highlighter, and beside the rest
of a Fluent toolbar they read as a different hand. The only way to match the
line is to use the line.

Fluent ships no SVG in the Dart package, but a glyph outline is the same
artwork: `fluentui_system_icons` carries `FluentSystemIcons-Regular.ttf`, whose
24-size glyphs are drawn on the same 24-unit grid this set uses. This module
reads a glyph by name, maps it from font units back onto the 24x24 canvas, and
flips it the right way up, giving back the artwork Fluent actually draws.

Anything built on it is `modified_fluent` in the manifest and must carry its
provenance; `THIRD_PARTY_NOTICES.md` is generated from those records.

  python3 tool/fluent_art.py link_24_regular eraser_24_regular   # dump the paths

Requires: fonttools, skia-pathops.
"""
import os
import re
import sys

import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen

from icon_compose import Art

PACKAGE_VERSION = "1.1.273"
PACKAGE = "fluentui_system_icons"

# Fluent ships one font per style. A mark that has to survive being knocked out
# of a 8.4-unit badge is taken from the filled font: the regular one is drawn
# with 1.5-unit strokes, which fall under half a unit at badge scale and close
# up at 16 px.
FONTS = {"regular": "FluentSystemIcons-Regular",
         "filled": "FluentSystemIcons-Filled"}

# The Dart package is where this font is already resolved for the app, so it is
# also where its exact version is pinned. PUB_CACHE is not the default here.
_CACHES = [os.environ.get("PUB_CACHE"), r"C:\pubcache",
           os.path.expanduser(r"~\AppData\Local\Pub\Cache")]


def _package_root():
    for cache in _CACHES:
        if not cache:
            continue
        root = os.path.join(cache, "hosted", "pub.dev",
                            "%s-%s" % (PACKAGE, PACKAGE_VERSION))
        if os.path.isdir(root):
            return root
    raise SystemExit(
        "cannot find %s-%s in the pub cache; looked in %s"
        % (PACKAGE, PACKAGE_VERSION, ", ".join(c for c in _CACHES if c)))


_ROOT = None
_FONTS = {}
_NAMES = {}


def _style_of(name):
    return "filled" if name.endswith("_filled") else "regular"


def _font(style):
    global _ROOT
    if style not in _FONTS:
        if _ROOT is None:
            _ROOT = _package_root()
        _FONTS[style] = TTFont(
            os.path.join(_ROOT, "lib", "fonts", FONTS[style] + ".ttf"),
            fontNumber=0, lazy=True)
    return _FONTS[style]


def codepoints(style="regular"):
    """{icon name: codepoint} for one style, read from the package's own
    generated Dart so the mapping cannot drift from the font."""
    if style not in _NAMES:
        _font(style)
        src = os.path.join(_ROOT, "lib", "src", "fluent_icons.dart")
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        _NAMES[style] = {
            m.group(1): int(m.group(2))
            for m in re.finditer(
                r"IconData (\w+) = IconData\((\d+), "
                r"fontFamily: '%s'" % FONTS[style], text)}
    return _NAMES[style]


class _Pen(BasePen):
    """Collects a glyph into a pathops.Path."""

    def __init__(self, glyphSet, path):
        BasePen.__init__(self, glyphSet)
        self.path = path

    def _moveTo(self, p):
        self.path.moveTo(*p)

    def _lineTo(self, p):
        self.path.lineTo(*p)

    def _curveToOne(self, p1, p2, p3):
        self.path.cubicTo(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])

    def _closePath(self):
        self.path.close()


def art(name):
    """The Fluent icon `name` (e.g. "eraser_24_regular") as Art on the 24x24
    canvas, y down - the same frame every source in this set is drawn on."""
    style = _style_of(name)
    font = _font(style)
    cps = codepoints(style)
    if name not in cps:
        raise KeyError("no Fluent icon named %r in the %s font" % (name, style))
    glyph_name = font.getBestCmap()[cps[name]]
    glyphs = font.getGlyphSet()
    p = pathops.Path()
    glyphs[glyph_name].draw(_Pen(glyphs, p))
    # Font units to canvas units, and y up to y down. The 24-size glyphs are
    # drawn on a 24-unit grid scaled to the em, so one canvas unit is
    # unitsPerEm/24 font units.
    upem = font["head"].unitsPerEm
    s = 24.0 / upem
    return Art(pathops.simplify(p.transform(s, 0, 0, -s, 0, 24.0)))


def provenance(*names):
    """The manifest fields an icon derived from `names` must carry.

    The artwork is taken from a published package rather than a checkout, so
    `upstream_commit` records the released artifact it actually came from. That
    is the identifier a reader can resolve; inventing a repository SHA that was
    never consulted would not be.
    """
    return {
        "origin": "modified_fluent",
        "based_on": "microsoft/fluentui-system-icons: %s (%s %s)"
                    % (", ".join(names), PACKAGE, PACKAGE_VERSION),
        "license": "MIT AND GPL-3.0-only",
        "upstream_commit": "pub:%s@%s" % (PACKAGE, PACKAGE_VERSION),
    }


if __name__ == "__main__":
    for n in sys.argv[1:] or ["link_24_regular"]:
        a = art(n)
        print("%-28s bbox %s area %.2f" % (n, ["%.3f" % v for v in a.bounds],
                                           a.area))
        print(a.d(3))
