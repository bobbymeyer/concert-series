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
A concert flyer for a live music venue, designed to be printed on one press.

House style, which every flyer in the series shares:
- Portrait page, 8.5 by 11 inches, full bleed, no border and no white margin.
- One solid flat background colour over the whole page: {ground}.
- Exactly one ink on that ground: {ink}. No third colour anywhere.
- A single black and white documentary photograph, screened as a coarse
  newsprint halftone at about 45 lines per inch, the dots clearly visible.
  It is printed in the same one ink and bleeds off the page edges, filling
  either the top half, the bottom half, or one vertical half of the page.
  The photograph is a 1970s Italian street scene -- a city street, police
  cars, men in suits and sunglasses, a tram, a piazza.
- All the type sits in the half the photograph leaves empty, on a strict
  grid, flush left, aligned against the photograph, with generous margins.
- The type is a heavy geometric sans serif, tight and modern. The performer's
  name is set largest, in capitals, spanning the full width of the text area.
  Everything else steps down from it in a clear hierarchy.
- Swiss typographic poster, 1970s Italian crime film soundtrack, newsprint,
  one-colour offset. Flat vector shapes and halftone dots only: no gradients,
  no drop shadows, no glow, no paper texture, no photographic realism in the
  layout itself.

Set this text on the flyer, exactly as written, spelled exactly, and nothing
else. Do not invent any extra words, logos, sponsor names, barcodes, web
addresses, or decorative lettering.

{fields}"""

LABELS = [("performer", "Performer, the largest type on the page"),
          ("openers", "Opening acts, smaller, under the performer"),
          ("venue", "Venue"),
          ("address", "Address, small, under the venue"),
          ("date", "Date"),
          ("time", "Time"),
          ("cost", "Price"),
          ("details", "Note, the smallest type on the page")]


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
    return BRIEF.format(ground=ground, ink=ink, fields="\n".join(fields))


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
