#!/usr/bin/env python3
"""Screen each flyer's photo at the exact size of its photo cell.

An offset press prints one solid ink; a photograph becomes a field of dots
whose size carries the tone. Doing that here rather than leaving it to the
printer means the dots land 1:1 on the page, at the ruling they were screened
at, with no resampling in between — and the flyer's duotone ramp, which maps
black to the shadow and white to the highlight, tints the dots rather than
blurring them.

The cell is cropped to first, at the alignment the flyer resolved, so the
photo's own ``h_align``/``v_align`` have nothing left to move.

Needs Pillow and the ``halftoner`` command:
https://github.com/bobbymeyer/halftoner

    python3 tools/halftone.py                       # report, write nothing
    python3 tools/halftone.py --write
    python3 tools/halftone.py piero-piccioni --ruling 65 --write
"""

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from PIL import Image
except ImportError:                                            # pragma: no cover
    raise SystemExit("tools/halftone.py needs Pillow: python3 -m pip install pillow")

from flyer.cli import resolve                                  # noqa: E402
from flyer.config import Design, Flyer                         # noqa: E402
from flyer.render import render                                # noqa: E402

PT_PER_IN = 72.0
ANCHOR = {"start": 0.0, "middle": 0.5, "end": 1.0}
SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def cell_of(flyer):
    """The photo's rect and alignment, as the flyer itself resolved them."""
    _, page = render(flyer, embed_images=False, embed_fonts=False)
    rect, notes = page.image.rect, page.notes
    return (rect.w / PT_PER_IN, rect.h / PT_PER_IN,
            ANCHOR[notes["h_align"]], ANCHOR[notes["v_align"]])


def seed_for(slug):
    """One screen per flyer, the same one every time — as the flyer's own slots."""
    return int.from_bytes(hashlib.sha256(slug.encode()).digest()[:4], "big")


def crop_to(image, aspect, hx, vy):
    """Cover-crop to ``aspect``, holding the part the flyer would have shown."""
    w, h = image.size
    if w / h > aspect:
        nw, nh = round(h * aspect), h
    else:
        nw, nh = w, round(w / aspect)
    x, y = round((w - nw) * hx), round((h - nh) * vy)
    return image.crop((x, y, x + nw, y + nh))


def is_screened(image):
    """Don't screen a screen.

    Every dot in a halftone is the same ink at the same strength, so one grey
    level carries a quarter of the picture. A photograph spreads its tone: its
    commonest level holds a percent or two. Anything piling up past a tenth has
    been here before.
    """
    counts = image.convert("L").histogram()
    return max(counts) > sum(counts) * 0.10


def halftone(source, target, size, args, seed):
    """Run halftoner over one cropped image, in a recipe folder of its own."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        recipe = tmp / f"{target.stem}.json"
        run = lambda cmd: subprocess.run(cmd, check=True, capture_output=True, text=True)
        run(["halftoner", "new", str(recipe),
             "--profile", args.profile, "--image", str(source),
             "--size", "{:g}x{:g}".format(*size), "--unit", "in",
             "--dpi", str(args.dpi), "--ink", f"k={args.ink}",
             "--ruling", str(args.ruling), "--seed", str(seed)])
        run(["halftoner", "render", str(recipe), "--target", "screen", "--out", str(tmp)])
        rendered = next(tmp.glob("*.png"))
        # One channel: the screen is bilevel, so grey costs nothing and saves half.
        Image.open(rendered).convert("L").save(target, optimize=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slugs", nargs="*", help="content folders; omit for all")
    parser.add_argument("--design", default="design/design.yaml")
    parser.add_argument("--content", default="content")
    parser.add_argument("--write", action="store_true",
                        help="replace each photo; without it, only report")
    parser.add_argument("--profile", default="newsprint_nominal",
                        help="halftoner press profile (default: %(default)s)")
    parser.add_argument("--ruling", type=int, default=45,
                        help="screen, in lines per inch (default: %(default)s)")
    parser.add_argument("--dpi", type=int, default=300,
                        help="device resolution (default: %(default)s)")
    parser.add_argument("--ink", default="#141414",
                        help="the one ink, before the flyer's ramp "
                             "(default: %(default)s)")
    parser.add_argument("--force", action="store_true",
                        help="screen a photo that is already screened")
    args = parser.parse_args(argv)

    design = Design.load(args.design)
    for folder in resolve(args.content, args.slugs):
        flyer = Flyer(folder, design)
        source = flyer.image_path
        w, h, hx, vy = cell_of(flyer)
        with Image.open(source) as image:
            screened = is_screened(image)
            note = "already screened" if screened else f"{image.width}x{image.height}"
            if not args.write or (screened and not args.force):
                print(f"{flyer.slug:28} {w:.2f}x{h:.2f}in  {note}")
                continue
            cropped = crop_to(image.convert("RGB"), w / h, hx, vy)

        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "crop.png"
            cropped.save(staged)
            target = folder / "photo.png"
            halftone(staged, target, (w, h), args, seed_for(flyer.slug))
        for old in folder.glob("photo.*"):
            if old != target and old.suffix.lower() in SUFFIXES:
                old.unlink()
        print(f"{flyer.slug:28} {w:.2f}x{h:.2f}in  {args.ruling}lpi "
              f"{args.profile}  {target.stat().st_size // 1024}kB")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
