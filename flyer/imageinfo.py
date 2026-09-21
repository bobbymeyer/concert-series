"""Pixel dimensions and media type of an image, without any dependencies.

Supports the raster formats a flyer photo realistically arrives in (PNG, JPEG,
GIF, WEBP) plus SVG, which is read as XML.
"""

import re
import struct


class ImageError(Exception):
    pass


def probe(path):
    """Return (width, height, mime) for an image file."""
    with open(path, "rb") as fh:
        head = fh.read(32)
        for reader in (_png, _gif, _webp, _jpeg, _svg):
            got = reader(head, fh, path)
            if got:
                return got
    raise ImageError(f"unrecognized image format: {path}")


def _png(head, fh, path):
    if not head.startswith(b"\x89PNG\r\n\x1a\n") or head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h, "image/png"


def _gif(head, fh, path):
    if not head.startswith((b"GIF87a", b"GIF89a")):
        return None
    w, h = struct.unpack("<HH", head[6:10])
    return w, h, "image/gif"


def _webp(head, fh, path):
    if not (head.startswith(b"RIFF") and head[8:12] == b"WEBP"):
        return None
    chunk = head[12:16]
    if chunk == b"VP8X":
        w = int.from_bytes(head[24:27], "little") + 1
        h = int.from_bytes(head[27:30], "little") + 1
    elif chunk == b"VP8 ":
        w, h = struct.unpack("<HH", head[26:30])
        w, h = w & 0x3FFF, h & 0x3FFF
    elif chunk == b"VP8L":
        bits = int.from_bytes(head[21:25], "little")
        w = (bits & 0x3FFF) + 1
        h = ((bits >> 14) & 0x3FFF) + 1
    else:
        return None
    return w, h, "image/webp"


# Start-of-frame markers that carry the dimensions; SOF4/8/12 are not frames.
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _jpeg(head, fh, path):
    if not head.startswith(b"\xff\xd8"):
        return None
    fh.seek(2)
    while True:
        byte = fh.read(1)
        if not byte:
            raise ImageError(f"truncated JPEG: {path}")
        if byte != b"\xff":
            continue
        marker = fh.read(1)
        while marker == b"\xff":          # fill bytes before a marker
            marker = fh.read(1)
        if not marker:
            raise ImageError(f"truncated JPEG: {path}")
        code = marker[0]
        if code in (0xD8, 0x01) or 0xD0 <= code <= 0xD7:
            continue                       # standalone markers, no payload
        size = struct.unpack(">H", fh.read(2))[0]
        if code in _SOF:
            h, w = struct.unpack(">HH", fh.read(5)[1:])
            return w, h, "image/jpeg"
        fh.seek(size - 2, 1)


_SVG_ATTR = re.compile(rb"""\b(width|height|viewBox)\s*=\s*["']([^"']+)["']""", re.I)


def _svg(head, fh, path):
    if b"<svg" not in head and not head.lstrip().startswith(b"<?xml"):
        return None
    fh.seek(0)
    blob = fh.read(8192)
    start = blob.find(b"<svg")
    if start < 0:
        return None
    attrs = {k.decode().lower(): v.decode() for k, v in _SVG_ATTR.findall(blob[start:])}
    if "viewbox" in attrs:
        nums = [float(n) for n in re.split(r"[,\s]+", attrs["viewbox"].strip())]
        if len(nums) == 4:
            return nums[2], nums[3], "image/svg+xml"
    if "width" in attrs and "height" in attrs:
        from .units import to_pt
        return to_pt(attrs["width"]), to_pt(attrs["height"]), "image/svg+xml"
    raise ImageError(f"SVG has no intrinsic size: {path}")
