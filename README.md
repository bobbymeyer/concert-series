# concert-series

A deterministic flyer generator. Put a photo and a yaml file in a folder; get a
print-ready 8.5 × 11 SVG in a consistent house style. No design application, no
runtime dependencies beyond Python and PyYAML — the layout engine measures type
with the font's own metrics and writes plain SVG 1.1.

```
make            # build every flyer, then write a contact sheet
open out/index.html
```

## How a flyer is composed

Every flyer follows the same rules, so a run of them looks like a series.

**The grid.** The page is bisected across the photo's short axis: a portrait
photo splits it into two columns, a landscape photo into two rows. A square
photo splits vertically.

**The photo** fills one of the two cells edge to edge, cropped to cover, and
bleeds to the trim on that cell's outer sides. `h_align` and `v_align` choose
which part of the photo survives the crop.

**The text** takes the other cell, inset by the page margin on its outer sides
and by the gutter on the side it shares with the photo. It is aligned *against*
the photo: photo on the left, text is left aligned to it; photo on the right,
right aligned; photo on top, the text sits up against it, and so on.

**The flow** is a column grid inside the text box, and it follows the split. A
vertical split gives a tall, narrow measure, so the grid is one column and the
fields stack. A horizontal split gives a wide, short band, so the grid is four
columns and the fields run across it, breaking to a new row when one is full. A
field can span several columns, and the performer spans them all — which is why
the headline takes a row to itself and reads as a banner:

```
┌─────────────────────────────────────────────┐
│ MARTA REYES TRIO                            │  performer, span: all
├──────────────────────┬──────────────────────┤
│ GALLERY 9            │ Saturday, November 14│  venue 2, date 2
├──────────┬───────────┼──────────────────────┤
│ 9:30 PM  │ FREE      │ Late set, no opener. │  time 1, cost 1, details 2
└──────────┴───────────┴──────────────────────┘
```

Blocks sharing a grid row sit on a common baseline, so a venue set small reads
as part of the line the headline ends on rather than floating above it.

**The colour** is monochrome: one ground colour per flyer, drawn from the
palette. The type is pure ink — black on a light ground, white on a dark one,
whichever reads — and the photo is desaturated and ramped between the ground
and that same ink. On a light ground that ramp runs black up to the ground,
which is a multiply; on a dark ground it runs the ground up to white, which is
a screen. One decision, taken from the ground's luminance, sets both the type
colour and which way the photo goes, so a dark ground never swallows the photo.

## Slots, and why the output is stable

Anything you do not specify is a *slot*: the ground colour, which cell holds the photo,
the crop anchors, and where the text block sits along its free axis. An unset
slot is not random per run — it is derived from the flyer's folder name, so the
same content always produces the same flyer, and two flyers in the same series
get different ones. Each slot draws from its own stream, so pinning one never
shifts another.

```yaml
scheme: dusk        # a ground by name, from the palette
color: "#A63D26"    # or just give one
image:
  cell: left        # pin it
  v_align: random   # or say random explicitly; omitting it means the same
seed: 4             # or keep the slots and just reshuffle
```

Alignments accept `start` / `middle` / `end` or the friendlier `top`, `bottom`,
`left`, `right`, `center` — interchangeably.

## Laying out content

```
content/
  cardinal-wax/
    flyer.yaml
    photo.png
```

```yaml
performer: Cardinal Wax
venue: The Bell House
date: 2026-10-03            # a real date, formatted by design.yaml
time: "8:00 PM"             # quote times: bare 8:00 is a number in yaml
cost: $22 advance / $25 door
details: >-
  Doors at seven. All ages until ten, 21+ after.
```

Every field is optional; missing ones are skipped. `details` may be a list, and
each item becomes its own line. A folder with one image needs no `image:` key.

A flyer may also override any part of the design in place — `page:`,
`typography:`, `palette:`, `grid:`, `image:`, `formats:` — which is how you make
one flyer in the series break the rules without forking the design.

## The design

`design/design.yaml` holds everything shared: page size, margins, the palette of
grounds, the type scale, and the date formats. It is commented throughout.
Three things are worth knowing:

- **`space_after` is optical.** It is the gap left below a block's descenders,
  before the next block's cap line — not a line height. Blocks are boxed from
  cap line to last baseline, so text flush to the top of the text area starts at
  its cap line and text flush to the bottom sits on its baseline.
- **The ink is derived, not chosen.** `palette.ink.dark` and `palette.ink.light`
  are the only two type colours; a ground takes whichever contrasts more.
  `palette.switch_at` overrides that crossover with a luminance if you want the
  swap to happen sooner or later.
- **The blend follows the ink.** `image.treatment.blend` is `auto` by default —
  multiply on a light ground, screen on a dark one — and can be forced either
  way per flyer, as can each end of the ramp.
- **A field's `span:`** is how many grid columns it takes — a number, or `all`
  for the full measure. It is clamped to the grid, so the same design works at
  one column and at four; in a column flow every field spans the single column.
- **Hierarchy is weight, size and tint**, not a second hue. A field's `color:`
  can be `ink`, `ground`, `tint` (ink held back toward the ground by
  `palette.tint`) or a literal hex. Anything else is an error, which is what
  keeps the design monochrome.

## Output

One self-contained SVG per flyer in `out/`. The photo is inlined as a data URI
and only the font weights the flyer actually uses are embedded as `@font-face`,
so the file renders the same in a browser, in Inkscape, at a print shop, or in
ten years — nothing is fetched and nothing needs installing. Each line of type
carries its measured width as `textLength`, so a renderer that substitutes a
font still lays the page out correctly.

The tone is an SVG filter (`feColorMatrix` + `feComponentTransfer`) rather than
a CSS blend mode, for the same reason: filters are SVG 1.1 and render
everywhere. Multiplying a fully desaturated photo over a flat ground is exactly
a linear ramp from black to that ground, and screening it is exactly a ramp
from the ground to white — so the filter computes the blend rather than asking
the renderer to composite it.

Build with `--no-embed` to reference the photo and fonts instead, which keeps
the SVG small while you are iterating.

## Commands

```
python3 -m flyer build [slug ...]   # render to out/ (the default command)
python3 -m flyer list               # content folders and their photos
python3 -m flyer inspect [slug]     # the resolved slots and every baseline
python3 -m flyer sheet              # out/index.html, a contact sheet
make test                           # 76 tests, standard library only
```

`build` prints what each flyer resolved to:

```
out/cardinal-wax.svg  portrait/vertical photo:start middle/end  column flow
                      scheme:dusk  type:100%  905kB
```

`type:100%` means nothing had to be shrunk to fit. A headline too wide for the
measure shrinks on its own, without dragging the body copy down with it; only a
text block too *tall* for its cell scales the whole thing.

## Fonts

[Rethink Sans](https://github.com/hans-thiessen/Rethink-Sans) by Hans Thiessen,
under the SIL Open Font License 1.1 (`design/fonts/OFL.txt`). The four static
weights in `design/fonts/` were instanced from the upstream variable font so
that advance widths are exact per weight.

## Placeholder photos

The example flyers ship with generated stand-ins rather than a real band photo.
`tools/make_placeholder.py` writes them; replace them with real images and
rebuild.

## Layout

```
design/design.yaml     the shared design
design/fonts/          Rethink Sans, static instances
content/<slug>/        one folder per flyer: yaml + photo
flyer/                 the generator
  config.py            loading and merging yaml
  slots.py             deterministic slot resolution
  color.py             monochrome grounds, ink and contrast
  fontmetrics.py       a minimal TrueType reader, for exact measurement
  imageinfo.py         image dimensions without a library
  layout.py            grid, image placement, both flows
  render.py            SVG emission
tools/                 placeholder photo generator
tests/                 unittest suite
```
