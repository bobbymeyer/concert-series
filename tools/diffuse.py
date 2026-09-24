#!/usr/bin/env python3
"""Make the same flyers by prompting an image model, for comparison.

The procedural side of this repo reads a folder of yaml and emits an SVG whose
every position it can account for. This is the other approach: hand the same
fields and the same house brief to a diffusion model in one prompt, and take
what comes back. Same content, same brief, no layout engine.

It is deliberately the naive method -- one prompt, one image, no retouching,
no second pass -- because that is the thing worth comparing against.

Needs an OpenAI key in OPENAI_API_KEY. Standard library only.

    python3 tools/diffuse.py --dry-run          # print the prompts, spend nothing
    python3 tools/diffuse.py ennio-morricone
    python3 tools/diffuse.py --quality medium
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flyer.cli import resolve                                  # noqa: E402
from flyer.config import Design, Flyer                         # noqa: E402
from flyer.render import render                                # noqa: E402

ENDPOINT = "https://api.openai.com/v1/images/generations"

BRIEF = """\
Design a concert flyer. Give me the finished artwork itself, flat and face on,
filling the whole frame: not a photograph of a printed poster, not a poster
hanging on a wall, not a mockup on a desk.

It belongs to a series, and every flyer in that series follows the same rules:

- Portrait page, 8.5 by 11 inches, printed full bleed. No border, no white
  margin, no frame around the artwork.
- The whole page is one flat solid colour: {ground_name}, {ground}.
- Exactly one ink prints on that ground: {ink_name}, {ink}. Nothing anywhere
  on the page is any other colour.
- One documentary photograph, reproduced as a coarse newsprint halftone --
  the dots plainly visible, around 45 lines to the inch -- printed in that
  same single ink. It fills one half of the page and bleeds off the edges:
  either the top half, the bottom half, or the left or the right half.
- The photograph is a 1970s Italian city street. Police cars, a tram, traffic,
  men in suits and dark glasses, a piazza. Unposed, ordinary, documentary.
- Every word sits in the other half, clear of the photograph, flush left on a
  strict grid, with a wide margin at the trim and a clear gutter against the
  photograph.
- The typeface is a heavy geometric sans serif, tight and contemporary. The
  performer's name is the largest thing on the page, in capitals, across the
  full width of the text area. Everything else steps down from it in a plain
  hierarchy, in the order the text is listed below.
- A 1970s Swiss typographic poster crossed with an Italian crime film sleeve:
  flat colour and halftone dots, nothing else. No gradients, no drop shadows,
  no glow, no grain overlay, no simulated paper texture, no 3D, no lighting
  effects on the layout.

Set exactly this text, spelled exactly as written, and nothing else. Do not add
words, logos, sponsor marks, barcodes, web addresses, social icons, extra dates
or decorative lettering of your own.

{fields}"""

LABELS = [("performer", "Performer, the largest type on the page"),
          ("openers", "Opening acts, under the performer"),
          ("venue", "Venue"),
          ("address", "Address, small, under the venue"),
          ("date", "Date"),
          ("time", "Time"),
          ("cost", "Price"),
          ("details", "Note, the smallest type on the page")]

HUES = [(15, "red"), (45, "orange"), (62, "yellow"), (90, "yellow-green"),
        (150, "green"), (190, "green-blue"), (250, "blue"), (290, "violet"),
        (345, "magenta"), (360, "red")]


def describe(hex_color):
    """Name a colour the way a person briefing a designer would name it.

    A hex triplet is the precise thing to hand a renderer and close to useless
    as a description, so the prompt carries both.
    """
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    high, low = max(r, g, b), min(r, g, b)
    light, spread = (high + low) / 2, high - low
    if spread < 0.04:
        if light < 0.03:
            return "black"
        return ("near-black" if light < 0.2 else "dark grey" if light < 0.45
                else "mid grey" if light < 0.7 else "off-white" if light < 0.93
                else "white")
    sat = spread / (2 - high - low) if light > 0.5 else spread / (high + low)
    if high == r:
        hue = 60 * (((g - b) / spread) % 6)
    elif high == g:
        hue = 60 * ((b - r) / spread + 2)
    else:
        hue = 60 * ((r - g) / spread + 4)
    name = next(n for edge, n in HUES if hue < edge)
    warm = name in ("red", "orange", "yellow")
    if light > 0.85:
        return f"a warm off-white" if warm and sat < 0.5 else f"a pale {name}"
    if light < 0.22:
        return f"a very dark {name}"
    if sat > 0.6:
        return f"a strong {name}" if light > 0.45 else f"a deep {name}"
    return f"a muted {name}" if sat < 0.35 else f"a {name}"


def text_of(flyer, key):
    """One field, formatted the way the procedural side would format it."""
    value = flyer.data.get(key)
    if value is None or value == "":
        return None
    if key == "date" and not isinstance(value, str):
        patterns = flyer.design.data.get("formats", {}).get("date")
        pattern = patterns[0] if isinstance(patterns, list) else patterns
        return value.strftime(pattern.replace("%-", "%")).replace(" 0", " ")
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return " ".join(str(value).split())


def ground_of(flyer):
    """The ground and ink the procedural side gave this flyer, so both match."""
    _, page = render(flyer, embed_images=False, embed_fonts=False)
    return page.notes["ground"], page.notes["ink"]


def prompt_for(flyer):
    """The one prompt: the house brief, then this flyer's own fields."""
    ground, ink = ground_of(flyer)
    fields = []
    for key, label in LABELS:
        text = text_of(flyer, key)
        if text:
            fields.append(f"{label}: {text}")
    return BRIEF.format(ground_name=describe(ground), ground=ground,
                        ink_name=describe(ink), ink=ink,
                        fields="\n".join(fields))


def generate(prompt, args, key):
    """One image, straight from the model. Retries only on a rate limit."""
    body = json.dumps({"model": args.model, "prompt": prompt,
                       "size": args.size, "quality": args.quality,
                       "n": 1}).encode()
    request = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    for attempt in range(args.attempts):
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                payload = json.load(response)
            return base64.b64decode(payload["data"][0]["b64_json"])
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:400]
            if err.code not in (429, 500, 502, 503) or attempt == args.attempts - 1:
                raise SystemExit(f"{err.code} from the image API: {detail}")
            time.sleep(2 ** attempt * 5)
    raise SystemExit("out of attempts")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slugs", nargs="*", help="content folders; omit for all")
    parser.add_argument("--design", default="design/design.yaml")
    parser.add_argument("--content", default="content")
    parser.add_argument("--out", default="out/diffusion")
    parser.add_argument("--model", default="gpt-image-1")
    parser.add_argument("--size", default="1024x1536",
                        help="the model's nearest portrait size; the page is "
                             "8.5x11, which it cannot be asked for "
                             "(default: %(default)s)")
    parser.add_argument("--quality", default="high",
                        choices=["low", "medium", "high"])
    parser.add_argument("--dry-run", action="store_true",
                        help="print the prompts and call nothing")
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)

    design = Design.load(args.design)
    folders = resolve(args.content, args.slugs)
    key = os.environ.get("OPENAI_API_KEY")
    if not key and not args.dry_run:
        raise SystemExit("set OPENAI_API_KEY, or pass --dry-run")

    out = Path(args.out)
    if not args.dry_run:
        out.mkdir(parents=True, exist_ok=True)
    for folder in folders:
        flyer = Flyer(folder, design)
        prompt = prompt_for(flyer)
        if args.dry_run:
            print(f"--- {flyer.slug}\n{prompt}\n")
            continue
        began = time.time()
        image = generate(prompt, args, key)
        target = out / f"{flyer.slug}.png"
        target.write_bytes(image)
        print(f"{target}  {args.model} {args.size} {args.quality}  "
              f"{len(image) // 1024}kB  {time.time() - began:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
