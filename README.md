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
fields stack. A horizontal split gives a wide, short band, so the grid is five
columns and the fields run across it, breaking to a new row when one is full. A
field can span several columns, and the performer spans them all — which is why
the headline takes a row to itself and reads as a banner:

```
┌──────────────────────────────────────────────────────┐
│ STELVIO CIPRIANI                                     │  [performer,
│ FRANCO MICALIZZI + RIZ ORTOLANI                      │   openers] all
├────────────────────┬─────────────────────┬───────────┤
│ LE POISSON ROUGE   │ Wed, September 23    │ $15      │  [venue, address] 2
│ 158 Bleecker Street│ 10:00 PM             │          │  [date, time] 2, cost 1
├────────────────────┴──────────────┬───────┴───────────┤
│ A night of chases and stakeouts.  │                   │  details 3
└───────────────────────────────────┴───────────────────┘
```

A field shortens rather than wraps when its cell is too narrow. `formats.date`
is a list of strftime patterns, longest first, and a date takes the longest one
that sets on a single line in the column the grid gave it — so "Wednesday,
September 23" becomes "Wed, September 23" in the row grid's narrower cell and
stays whole in the column flow's wider measure. Only a date written as a real
date can do this; one written as a string has only itself to offer.

A cell can hold a stack of fields rather than one: `typography.order` takes a
list where a single field would go, and those fields set one under another in
the same column. That is how the address sits under the venue and the time
under the date. Cells sharing a grid row sit on a common baseline — the last
line of each — so a venue set small reads as part of the line the headline ends
on rather than floating above it.

**The colour** is monochrome: one ground colour per flyer, drawn from the
palette. The type is pure ink — black on a light ground, white on a dark one,
whichever reads — and the photo is desaturated and ramped between the ground
and that same ink. On a light ground that ramp runs black up to the ground,
which is a multiply; on a dark ground it runs the ground up to white, which is
a screen. One decision, taken from the ground's luminance, sets both the type
colour and which way the photo goes, so a dark ground never swallows the photo.

## Slots, and why the output is stable

Anything you do not specify is a *slot*: which cell holds the photo, the crop
anchors, and where the text block sits along its free axis. An unset slot is not
random per run — it is derived from the flyer's folder name, so the same content
always produces the same flyer, and two flyers in the same series get different
ones. Each slot draws from its own stream, so pinning one never shifts another.

**The ground colour is the exception**, because it is the one choice that should
look deliberate across a run. Hashing each flyer independently clumps — six
flyers routinely draw the same ground three times — so an unpinned flyer takes
the next ground in rotation instead, by its position in the content folder,
skipping any a sibling has pinned for itself. Six flyers get six grounds. The
trade is that inserting a flyer re-colours the ones after it; set
`palette.assign: independent` to go back to hashing.

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
  ennio-morricone/
    flyer.yaml
    photo.png
```

```yaml
performer: Ennio Morricone
openers:                    # nought to four supporting acts
  - Bruno Nicolai
  - Alessandro Alessandroni
venue: Roulette
address: 509 Atlantic Avenue, Brooklyn
date: 2026-10-03            # a real date, formatted by design.yaml
time: "8:00 PM"             # quote times: bare 8:00 is a number in yaml
cost: $22 advance / $25 door
details: >-
  An evening of scores for Italian crime cinema, played live.
```

Every field is optional; missing ones are skipped, and a stack whose fields are
all missing takes no cell. `openers` takes up to four acts — a list, or a bare
string for one — and sets them as a single bill under the headline, joined by
the field's `join`. A fifth is refused rather than quietly crowding the page;
`max_items` on any field sets that limit. `details` may be a list, and
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
  A stacked cell takes the widest span of its fields.
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
make test                           # 94 tests, standard library only
```

`build` prints what each flyer resolved to:

```
out/ennio-morricone.svg  portrait/vertical photo:start end/start  column flow
                         ground:acid 2/6  type:100%  985kB
```

`1/6` is the flyer's place in the ground rotation, and `type:100%` means
nothing had to be shrunk to fit. A headline too wide for the
measure shrinks on its own, without dragging the body copy down with it; only a
text block too *tall* for its cell scales the whole thing.

## Fonts

[Rethink Sans](https://github.com/hans-thiessen/Rethink-Sans) by Hans Thiessen,
under the SIL Open Font License 1.1 (`design/fonts/OFL.txt`). The four static
weights in `design/fonts/` were instanced from the upstream variable font so
that advance widths are exact per weight.

## The example content

The examples are a season of Italian film-score nights — Morricone, Piccioni,
Cipriani, Trovajoli, Micalizzi, the De Angelis brothers — chosen because a run
of six shows off what the series rotation, the grid and the opening-act bill
each do. The events are invented; the composers are not.

**The photos are generated stand-ins, not the composers.**
`tools/make_placeholder.py` writes a deterministic PNG with the tonal range of
a portrait from a film still, which is all the duotone treatment reads.
Photographs of these men are still in copyright, so drop in images you have the
rights to and rebuild — the filename is the only thing the flyer yaml cares
about.

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
