# concert-series

Print-ready concert flyers from a photo and a yaml file, in one house style.

## quickstart

```sh
git clone https://github.com/bobbymeyer/concert-series
cd concert-series
python3 -m pip install pyyaml
```

```sh
make
open out/index.html
```

## commands

`python3 -m flyer [--design PATH] [--content DIR] COMMAND`

| Command | Does |
| --- | --- |
| `build [slug ...]` | Render to `out/`. The default command. Omit slugs for all. |
| `list` | Content folders, their photo, its pixel size and orientation. |
| `inspect [slug ...]` | Print the resolved slots, grid rows and every baseline. Writes nothing. |
| `sheet [slug ...]` | Write `out/index.html`, a contact sheet of the built SVGs. |

| Option | Applies to | Default |
| --- | --- | --- |
| `--design PATH` | all | `design/design.yaml` |
| `--content DIR` | all | `content` |
| `--out DIR` | `build`, `sheet` | `out` |
| `--no-embed` | `build` | off; references the photo and fonts instead of inlining them |

| Make target | Runs |
| --- | --- |
| `make` / `make all` | `build`, then `sheet` |
| `make build` | render every content folder |
| `make sheet` | build, then write `out/index.html` |
| `make list` | list content folders |
| `make test` | `python3 -m unittest discover -s tests` |
| `make clean` | `rm -rf out` |

## a flyer

One folder per flyer under `content/`, holding `flyer.yaml` and one image.

```yaml
performer: Ennio Morricone
openers:
  - Bruno Nicolai
  - Alessandro Alessandroni
venue: Roulette
address: 509 Atlantic Avenue, Brooklyn
date: 2026-10-03
time: "8:00 PM"
cost: $22 advance / $25 door
details: >-
  An evening of scores for Italian crime cinema, played live.
```

| Field | Takes |
| --- | --- |
| `performer` | string |
| `openers` | string, or a list of up to 4 |
| `venue` | string |
| `address` | string |
| `date` | a yaml date, formatted by `formats.date`; or a string, used as written |
| `time` | string. Quote it: bare `8:00` is a sexagesimal number in yaml |
| `cost` | string |
| `details` | string, or a list of lines |

Every field is optional. A missing one is skipped, and a stack whose fields are
all missing takes no grid cell.

| Key | Takes |
| --- | --- |
| `image` | filename, or a block with `file:`. Omit it when the folder holds one image |
| `scheme` | a name from `palette.colors` |
| `color`, `background` | hex, overriding the scheme's ground |
| `seed` | any value; changes which slots are drawn |
| `page`, `grid`, `image`, `typography`, `palette`, `fonts`, `formats` | override that part of `design/design.yaml` for this flyer |

## the design

`design/design.yaml`. Lengths take `in`, `mm`, `cm`, `pt`; a bare number is
points.

| `page` | Default |
| --- | --- |
| `width`, `height` | `8.5in`, `11in` |
| `margin` | `0.5in`, trim edge to text |
| `gutter` | `0.5in`, photo edge to text |

| `grid` | Takes | Default |
| --- | --- | --- |
| `split` | `auto`, `vertical`, `horizontal` | `auto`: vertical unless the photo is landscape |
| `flow` | `auto`, `column`, `row` | `auto`: column on a vertical split |
| `columns.column`, `columns.row` | integer | `1`, `5` |
| `column_gap` | length | `16` |
| `row_gap.column`, `row_gap.row` | length, a floor between grid rows | `0`, `12` |
| `row_align` | `top`, `center`, `bottom` | `bottom`: cells in a row share a last baseline |

| `image` | Takes | Default |
| --- | --- | --- |
| `cell` | `start`, `end`, `random` | `random` |
| `h_align`, `v_align` | `start`, `middle`, `end`, `random` | `random` |
| `embed` | bool, inline the photo as a data URI | `true` |
| `treatment.desaturate` | `0`–`1`, `1` being fully grey | `1.0` |
| `treatment.blend` | `auto`, `multiply`, `screen` | `auto`: multiply on a light ground, screen on a dark one |
| `treatment.shadow`, `treatment.highlight` | `auto`, a role, or hex | `auto`, following the blend |

Alignments accept `start`/`middle`/`end`, or `top`, `bottom`, `left`, `right`,
`center` interchangeably.

| `palette` | Takes | Default |
| --- | --- | --- |
| `colors` | named grounds, one per flyer | six |
| `ink.dark`, `ink.light` | the only two type colours | `#000000`, `#FFFFFF` |
| `switch_at` | `auto`, or a luminance `0`–`1` | `auto`: whichever ink contrasts more |
| `tint` | `0`–`1`, ink held back toward the ground | `0.72` |
| `assign` | `series` rotates grounds by position, `independent` hashes each flyer | `series` |

| `typography` | Takes | Default |
| --- | --- | --- |
| `family`, `fallback` | font names | `Rethink Sans` |
| `align` | where the block sits on its free axis | `random` |
| `text_length` | bool, pin each line to its measured width | `true` |
| `order` | one entry per grid cell; a list stacks those fields in one cell | |
| `defaults` | merged under every field | |
| `fields` | per-field overrides | |

| Field style | Takes |
| --- | --- |
| `size` | points |
| `weight` | `400`, `500`, `700`, `800` |
| `leading` | multiple of the size |
| `tracking` | em |
| `case` | `upper`, `lower`, `title`, `none` |
| `color` | `ink`, `ground`, `tint`, or hex |
| `space_after` | points below the descenders, before the next cap line |
| `span` | grid columns, or `all` |
| `join` | joins a list into one run instead of a line per item |
| `max_items` | caps a list; more is an error |
| `bind_max` | a word this short binds to the next; `0` turns it off |
| `fit` | bool, may shrink alone to fit the measure |

`formats.date` and `formats.time` take one strftime pattern or a list of them,
longest first. A field takes the longest that sets on one line in its column.

## recipes

Add a flyer:

```sh
mkdir content/piero-piccioni
cp ~/photo.jpg content/piero-piccioni/
$EDITOR content/piero-piccioni/flyer.yaml
make
```

See what a flyer resolved to without writing:

```sh
python3 -m flyer inspect piero-piccioni
```

Keep the SVGs small while iterating, then inline everything for the printer:

```sh
python3 -m flyer build --no-embed
python3 -m flyer build
```

Generate a stand-in photo for a flyer that has none:

```sh
python3 tools/make_placeholder.py content/piero-piccioni/photo.png 900x1200
```

Take photos from Wikimedia Commons. `tools/fetch_commons.py` keeps only CC0,
CC BY, CC BY-SA and public domain, and writes `content/PHOTO-CREDITS.md`:

```sh
python3 tools/fetch_commons.py --search "Alfa Romeo Polizia di Stato"
python3 tools/fetch_commons.py piero-piccioni --file "File:Example.jpg" --write
```

| `fetch_commons.py` | Does |
| --- | --- |
| `[slug ...]` | report free candidates for each flyer's performer |
| `--write` | download; without it nothing is written |
| `--search TERMS` | list free files matching the terms and stop |
| `--file FILE` | fetch one named Commons file into the one named slug |
| `--index N` | take the Nth candidate, 1-based |
| `--query TERMS` | search for this instead of the performer |
| `--credits-only` | re-record attributions without downloading again |
| `--content DIR` | content folder |

## output

One SVG per flyer in `out/`, 8.5 × 11in, `viewBox` in points. The photo is
inlined as a data URI and the font weights in use are embedded as `@font-face`.
Each line of type carries its measured width as `textLength`. The photo's tone
is an SVG filter, not a CSS blend mode.

## tech

Python 3.11 and PyYAML. No other dependencies; the type is measured by reading
the font's own tables.

```sh
make test
```

118 tests, standard library only. Default branch is `main`.

Type is [Rethink Sans](https://github.com/hans-thiessen/Rethink-Sans) by Hans
Thiessen under the SIL Open Font License 1.1, vendored in `design/fonts/` as
four static instances.

The example photographs are archival, from Wikimedia Commons, credited in
`content/PHOTO-CREDITS.md`. None of them depicts the composer named on the
flyer.
