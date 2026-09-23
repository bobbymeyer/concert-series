#!/usr/bin/env python3
"""Generate a stand-in photo for an example flyer.

The examples need an image, and shipping someone's band photo in a template
repo is a licensing problem. This writes a deterministic PNG with the tonal
range of a real photo — soft light, a subject mass, grain — which is all the
duotone treatment actually reads. Replace it with a real photo when you have
one.

    python3 tools/make_placeholder.py content/the-mountain-goats/photo.png 1200x1600
"""

import math
import random
import struct
import sys
import zlib


def png(path, width, height, pixel):
    """Write an 8-bit RGB PNG; ``pixel(x, y)`` returns an (r, g, b) triple."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)                                  # filter type: none
        for x in range(width):
            rows.extend(max(0, min(255, int(c))) for c in pixel(x, y))

    def chunk(tag, payload):
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        fh.write(chunk(b"IDAT", zlib.compress(bytes(rows), 9)))
        fh.write(chunk(b"IEND", b""))


def scene(width, height, seed):
    """A lit subject against a falling-off background, plus grain.

    Shaped like a portrait from a 1970s film still -- one key light, a rim, a
    vignette and coarse grain -- because that tonal range is all the duotone
    treatment reads. It is a stand-in, not a likeness of anyone.
    """
    rng = random.Random(seed)
    cx, cy = width * rng.uniform(0.38, 0.62), height * rng.uniform(0.34, 0.48)
    radius = min(width, height) * rng.uniform(0.30, 0.38)
    key_x, key_y = width * rng.uniform(-0.1, 0.4), height * rng.uniform(-0.2, 0.1)
    blobs = [(width * rng.uniform(0.1, 0.9), height * rng.uniform(0.5, 1.1),
              min(width, height) * rng.uniform(0.12, 0.30), rng.uniform(-40, 30))
             for _ in range(5)]
    # Quantised so the grain stays photographic without defeating PNG's filter.
    # Coarse and quantised, so it reads as film grain without ballooning the PNG.
    grain = [round(rng.gauss(0, 6) / 4) * 4 for _ in range(4096)]

    def pixel(x, y):
        # Background: a soft falloff from the key light.
        d_key = math.hypot(x - key_x, y - key_y) / max(width, height)
        value = 188 - 120 * min(1.0, d_key ** 1.25)

        # Subject: a rounded mass with its own shading and a rim highlight.
        d = math.hypot((x - cx) / radius, (y - cy) / (radius * 1.22))
        if d < 1.0:
            shade = 1.0 - 0.55 * ((x - cx) / radius + 1.0) / 2.0
            value = 60 + 150 * shade * (1.0 - 0.35 * d * d)
        elif d < 1.06:
            value += 55                                  # rim light

        for bx, by, br, tone in blobs:                   # foreground shapes
            if math.hypot((x - bx) / br, (y - by) / (br * 0.8)) < 1.0:
                value += tone

        # A vignette and a contrast curve, so the duotone has somewhere to go.
        dx, dy = (x / width - 0.5) * 2, (y / height - 0.5) * 2
        value *= 1.0 - 0.38 * min(1.0, (dx * dx + dy * dy) ** 1.1)
        value = 128 + (value - 128) * 1.28

        value += grain[((x >> 1) * 31 + (y >> 1) * 17) % len(grain)]
        # A faint cast, so `desaturate` has something to remove.
        return value * 1.02, value, value * 0.94

    return pixel


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip())
        return 1
    path = argv[1]
    size = argv[2] if len(argv) > 2 else "900x1200"
    width, height = (int(n) for n in size.lower().split("x"))
    seed = argv[3] if len(argv) > 3 else path
    png(path, width, height, scene(width, height, seed))
    print(f"wrote {path} ({width}x{height})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
