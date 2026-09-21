"""Command line: build, list and inspect flyers."""

import argparse
import sys
from pathlib import Path

from .config import Design, Flyer, discover
from .render import render


def resolve(content_root, names):
    """Map slugs to content folders; with none given, take them all."""
    folders = discover(content_root)
    if not names:
        return folders
    by_slug = {f.name: f for f in folders}
    chosen = []
    for name in names:
        slug = Path(name).name
        if slug not in by_slug:
            raise SystemExit(
                f"no flyer named {slug!r} in {content_root} "
                f"(have: {', '.join(sorted(by_slug)) or 'none'})")
        chosen.append(by_slug[slug])
    return chosen


def cmd_build(args):
    design = Design.load(args.design)
    folders = resolve(args.content, args.slugs)
    if not folders:
        print(f"no flyers found in {args.content}/", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for folder in folders:
        flyer = Flyer(folder, design)
        svg, page = render(
            flyer,
            embed_images=None if args.embed else False,
            embed_fonts=None if args.embed else False,
        )
        target = out / f"{flyer.slug}.svg"
        target.write_text(svg, encoding="utf-8")
        n = page.notes
        print(f"{target}  {n['orientation']}/{n['split']} photo:{n['image_cell']} "
              f"{n['h_align']}/{n['v_align']}  {n['flow']} flow  "
              f"scheme:{n['scheme']}  type:{n['scale']:.0%}  {target.stat().st_size // 1024}kB")
    return 0


def cmd_list(args):
    design = Design.load(args.design)
    for folder in discover(args.content):
        flyer = Flyer(folder, design)
        print(f"{flyer.slug:28} {flyer.image_path.name:16} "
              f"{flyer.image_width}x{flyer.image_height} {flyer.orientation}")
    return 0


def cmd_inspect(args):
    design = Design.load(args.design)
    for folder in resolve(args.content, args.slugs):
        flyer = Flyer(folder, design)
        _, page = render(flyer, embed_images=False, embed_fonts=False)
        print(f"--- {flyer.slug}")
        for key, value in sorted(page.notes.items()):
            print(f"  {key:14} {value}")
        for line in page.lines:
            print(f"  · {line.field:10} {line.size:6.2f}pt/{line.weight} "
                  f"@({line.x:7.2f},{line.baseline:7.2f}) {line.anchor:6} {line.text!r}")
    return 0


SHEET = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Flyers</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; padding: 2rem; background: #8d8d8d;
         font: 13px/1.4 ui-sans-serif, system-ui, sans-serif; }}
  .sheet {{ display: grid; gap: 2rem;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }}
  figure {{ margin: 0; }}
  img {{ width: 100%; display: block; box-shadow: 0 2px 16px rgba(0,0,0,.35); }}
  figcaption {{ margin-top: .5rem; color: #fff; font-variant-numeric: tabular-nums; }}
</style></head>
<body><div class="sheet">
{tiles}
</div></body></html>
"""


def cmd_sheet(args):
    """Write a contact sheet so a run of flyers can be compared at a glance."""
    design = Design.load(args.design)
    out = Path(args.out)
    tiles = []
    for folder in resolve(args.content, args.slugs):
        flyer = Flyer(folder, design)
        svg = out / f"{flyer.slug}.svg"
        if not svg.exists():
            raise SystemExit(f"{svg} has not been built yet; run `flyer build` first")
        tiles.append(
            f'  <figure><img src="{svg.name}" alt="{flyer.slug}">'
            f'<figcaption>{flyer.slug}</figcaption></figure>')
    target = out / "index.html"
    target.write_text(SHEET.format(tiles="\n".join(tiles)), encoding="utf-8")
    print(f"{target}  {len(tiles)} flyers")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="flyer", description="Build concert flyers from yaml and a photo.")
    parser.add_argument("--design", default="design/design.yaml",
                        help="the shared design file (default: %(default)s)")
    parser.add_argument("--content", default="content",
                        help="folder of flyer folders (default: %(default)s)")
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="render flyers to SVG (the default)")
    build.add_argument("slugs", nargs="*", help="content folders; omit for all")
    build.add_argument("--out", default="out", help="output folder (default: %(default)s)")
    build.add_argument("--no-embed", dest="embed", action="store_false",
                       help="reference the photo and fonts instead of inlining them")
    build.set_defaults(func=cmd_build, embed=True)

    listing = sub.add_parser("list", help="show the content folders and their photos")
    listing.set_defaults(func=cmd_list)

    inspect = sub.add_parser("inspect", help="print the resolved layout, without writing")
    inspect.add_argument("slugs", nargs="*")
    inspect.set_defaults(func=cmd_inspect)

    sheet = sub.add_parser("sheet", help="write out/index.html, a contact sheet")
    sheet.add_argument("slugs", nargs="*")
    sheet.add_argument("--out", default="out")
    sheet.set_defaults(func=cmd_sheet)

    args = parser.parse_args(argv)
    if not args.command:                       # bare `flyer` builds everything
        args = parser.parse_args((argv or []) + ["build"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
