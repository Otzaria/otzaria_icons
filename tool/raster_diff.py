#!/usr/bin/env python3
"""Independent visual check: render two sets of sources and compare the pixels.

WHY THIS EXISTS
---------------
tool/region_diff.py is the primary proof that a restructured source still draws
the same icon, and it is the stronger of the two: it compares exact vector
regions rather than one sampled resolution. But it reaches that answer through
the same skia-pathops boolean engine the font pipeline uses, so a fault in that
engine would be invisible to it.

This tool answers the same question along a completely separate path: it renders
both versions with Inkscape and compares the resulting bitmaps. Agreement
between two independent methods is what makes "no graphical change" a claim
rather than a hope.

It also renders at the sizes the package actually ships (16, 20, 24, 32, 48) plus
a large size for inspection, so a defect that only shows up at small sizes -
where a stray bump merges into a stroke - is caught by the same run.

USAGE
-----
  python3 tool/raster_diff.py --baseline DIR              # every source vs DIR
  python3 tool/raster_diff.py --baseline DIR a.svg b.svg  # specific sources
  python3 tool/raster_diff.py --sizes 24,512              # override sizes
  python3 tool/raster_diff.py --out DIR                   # keep the PNGs

Requires Inkscape. Set INKSCAPE to its executable when it is not on PATH.
"""
import sys, os, glob, subprocess, tempfile, shutil, struct, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "assets_src", "svg")

# The sizes the package documents for visual acceptance, plus 512 so a defect
# too small to resolve at icon sizes is still visible somewhere in the run.
DEFAULT_SIZES = (16, 20, 24, 32, 48, 512)

# A pixel must differ by more than this (0-255) to count. Renderers are not
# bit-exact run to run; anything a person could see is far above this.
CHANNEL_TOL = 2


def inkscape_binary():
    env = os.environ.get("INKSCAPE")
    if env:
        return env
    found = shutil.which("inkscape")
    if found:
        return found
    for guess in (r"C:\Program Files\Inkscape\bin\inkscape.exe",
                  r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe",
                  "/usr/bin/inkscape"):
        if os.path.exists(guess):
            return guess
    sys.exit("Inkscape not found. Set INKSCAPE to its executable.")


def render(binary, svg_path, png_path, size):
    subprocess.run([binary,
                    "--export-type=png",
                    "--export-filename=" + png_path,
                    "--export-width=%d" % size,
                    "--export-height=%d" % size,
                    "--export-background=white",
                    "--export-background-opacity=255",
                    svg_path],
                   check=True, capture_output=True)


def read_png_gray(path):
    """Decode a PNG into (width, height, [luma bytes]).

    Written out longhand rather than pulled from an image library: the pipeline
    already pins three Python dependencies for reproducibility and this needs to
    read exactly one kind of file that Inkscape just wrote."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: %s" % path)

    pos, idat, width = 8, b"", None
    while pos < len(data):
        length, = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            if depth != 8 or color not in (2, 6):
                raise ValueError("unexpected PNG format in %s" % path)
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
        pos += 12 + length

    raw = zlib.decompress(idat)
    stride = width * channels
    out = bytearray(width * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        filt = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if filt == 1:
                line[i] = (line[i] + a) & 0xFF
            elif filt == 2:
                line[i] = (line[i] + b) & 0xFF
            elif filt == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        for x in range(width):
            r, g, bl = line[x * channels:x * channels + 3]
            out[y * width + x] = (r * 299 + g * 587 + bl * 114) // 1000
        prev = line
    return width, height, out


def compare_images(a_path, b_path):
    """Return (differing_pixel_count, worst_channel_delta, total_pixels)."""
    wa, ha, a = read_png_gray(a_path)
    wb, hb, b = read_png_gray(b_path)
    if (wa, ha) != (wb, hb):
        return len(a), 255, len(a)
    count = worst = 0
    for i in range(len(a)):
        delta = abs(a[i] - b[i])
        if delta > worst:
            worst = delta
        if delta > CHANNEL_TOL:
            count += 1
    return count, worst, len(a)


def main(argv):
    sizes = DEFAULT_SIZES
    out_dir = None
    baseline = None
    if "--sizes" in argv:
        i = argv.index("--sizes")
        sizes = tuple(int(s) for s in argv[i + 1].split(","))
        del argv[i:i + 2]
    if "--out" in argv:
        i = argv.index("--out")
        out_dir = argv[i + 1]
        del argv[i:i + 2]
    if "--baseline" in argv:
        i = argv.index("--baseline")
        baseline = argv[i + 1]
        del argv[i:i + 2]
    if not baseline:
        sys.exit(__doc__)

    binary = inkscape_binary()
    targets = [a for a in argv if not a.startswith("--")] or \
        sorted(glob.glob(os.path.join(SVG_DIR, "*.svg")))

    work = out_dir or tempfile.mkdtemp(prefix="raster_diff_")
    os.makedirs(work, exist_ok=True)
    failures = 0
    try:
        for cur in targets:
            name = os.path.basename(cur)
            old = os.path.join(baseline, name)
            if not os.path.exists(old):
                print("NEW      %s (no baseline)" % name)
                continue
            reports = []
            for size in sizes:
                stem = os.path.join(work, "%s_%d" % (name[:-4], size))
                render(binary, old, stem + "_old.png", size)
                render(binary, cur, stem + "_new.png", size)
                count, worst, total = compare_images(stem + "_old.png",
                                                     stem + "_new.png")
                if count:
                    reports.append("%dpx %d/%d px worst %d"
                                   % (size, count, total, worst))
            if reports:
                failures += 1
                # Every size is reported, not just the worst. A difference that
                # appears only at 512 px is antialiasing on a subpixel edge
                # shift; one that appears at 16 or 24 px is a real change to
                # what ships.
                print("DIFFERS  %-40s %s" % (name, "; ".join(reports)))
            else:
                print("same     %s" % name)
        print("\n%d compared, %d differ (sizes: %s)"
              % (len(targets), failures, ",".join(str(s) for s in sizes)))
    finally:
        if not out_dir:
            shutil.rmtree(work, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
