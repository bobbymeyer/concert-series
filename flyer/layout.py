"""The layout engine: grid, image placement, and text flow.

Everything here is pure geometry — it produces a Plan of absolutely positioned
boxes and baselines that the renderer turns into SVG.
"""

import datetime as dt
from dataclasses import dataclass, field as dc_field
from typing import List, Optional

from . import fontmetrics
from .color import Scheme, schemes_from
from .config import Design, deep_merge
from .slots import Chooser, normalize_align

# Alignment -> the preserveAspectRatio tokens used to anchor a cover crop.
_PAR_X = {"start": "xMin", "middle": "xMid", "end": "xMax"}
_PAR_Y = {"start": "YMin", "middle": "YMid", "end": "YMax"}


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def inset(self, top=0.0, right=0.0, bottom=0.0, left=0.0):
        return Rect(self.x + left, self.y + top,
                    self.w - left - right, self.h - top - bottom)


@dataclass
class ImagePlacement:
    rect: Rect
    href: str
    mime: str
    preserve_aspect_ratio: str
    desaturate: float = 1.0
    shadow: str = "#000000"
    highlight: str = "#FFFFFF"
    blend: str = "multiply"


@dataclass
class Line:
    text: str
    x: float
    baseline: float
    anchor: str          # start | middle | end
    size: float
    weight: int
    color: str
    width: float         # measured advance width, used for textLength
    field: str


@dataclass
class Plan:
    width: float
    height: float
    background: str
    image: ImagePlacement
    lines: List[Line] = dc_field(default_factory=list)
    notes: dict = dc_field(default_factory=dict)


class LayoutError(Exception):
    pass


# --------------------------------------------------------------------------
# content preparation
# --------------------------------------------------------------------------

DEFAULT_FORMATS = {"date": "%A, %B %-d", "time": "%-I:%M %p"}


def _patterns(key, formats):
    """The strftime patterns for a kind of value, longest form first."""
    patterns = formats.get(key) or DEFAULT_FORMATS[key]
    return [patterns] if isinstance(patterns, str) else list(patterns)


def format_variants(name, value, formats):
    """Every acceptable rendering of a yaml value, longest first.

    A date given as a real date can be set several ways, so the layout can
    fall back to a shorter one when the column it lands in is too narrow for
    the long one. A date given as a string has only itself.
    """
    if isinstance(value, (list, tuple)):
        return ["\n".join(format_variants(name, v, formats)[0] for v in value)]
    if isinstance(value, dt.datetime):
        key = "time" if name == "time" else "date"
        return [value.strftime(p) for p in _patterns(key, formats)]
    if isinstance(value, dt.date):
        return [value.strftime(p) for p in _patterns("date", formats)]
    if isinstance(value, dt.time):
        return [value.strftime(p) for p in _patterns("time", formats)]
    if isinstance(value, bool):
        return ["Yes" if value else "No"]
    return [str(value)]


def format_value(name, value, formats):
    """The longest rendering of a yaml value."""
    return format_variants(name, value, formats)[0]


def apply_case(text, case):
    case = (case or "none").lower()
    if case in ("upper", "uppercase"):
        return text.upper()
    if case in ("lower", "lowercase"):
        return text.lower()
    if case in ("title", "titlecase"):
        return text.title()
    return text


@dataclass
class Block:
    name: str
    text: str
    size: float
    weight: int
    leading: float       # multiple of size
    tracking: float      # em
    color: str
    space_after: float
    span: object         # grid columns to occupy; "all" spans the measure
    fit: bool            # may shrink on its own to fit the measure
    font: object
    variants: List[str] = dc_field(default_factory=list)
    local: float = 1.0   # this block's own shrink, set by fit_width
    lines: List[str] = dc_field(default_factory=list)

    def px(self, scale=1.0):
        return self.size * self.local * scale

    def choose_variant(self, width, scale=1.0):
        """Take the longest form of the value that sets without wrapping.

        Shortening is a last resort before a wrap, not a habit: a field only
        drops to a briefer form when the column the grid gave it cannot hold
        the long one.
        """
        if len(self.variants) < 2:
            return self.text
        size = self.size * scale          # judged before any shrink of its own
        for text in self.variants:
            widest = max(self.font.width(line, size, self.tracking)
                         for line in text.split("\n"))
            if widest <= width + fontmetrics.TOLERANCE:
                self.text = text
                return text
        self.text = self.variants[-1]
        return self.text

    def fit_width(self, width, scale=1.0):
        """Shrink this block alone until its longest unbreakable word fits.

        A headline too wide for the measure should come down on its own rather
        than drag the body copy with it.
        """
        self.local = 1.0
        if not self.fit or width <= 0:
            return self.local
        widest = max(
            (self.font.width(word, self.size * scale, self.tracking)
             for word in self.text.split()),
            default=0.0,
        )
        if widest > width:
            self.local = max(MIN_SCALE, width / widest)
        return self.local

    def wrap(self, width, scale=1.0):
        self.lines = fontmetrics.wrap(
            self.font, self.text, self.px(scale), width, self.tracking)
        return self.lines

    def height(self, scale=1.0):
        """Cap height of the first line down to the baseline of the last.

        Blocks are boxed optically rather than by the font's line box, so a
        block flush to the top of the text area starts at its cap line and one
        flush to the bottom sits on its last baseline.
        """
        size = self.px(scale)
        n = max(len(self.lines), 1)
        return self.font.em("cap_height") * size + (n - 1) * self.leading * size

    def gap_after(self, scale=1.0):
        """Space to the next block: its own descender, then ``space_after``."""
        return -self.font.em("descent") * self.px(scale) + self.space_after * scale


def build_block(design, data, scheme, name):
    """One field, or None when the flyer does not carry it."""
    value = data.get(name)
    if value is None or (isinstance(value, (str, list, tuple)) and len(value) == 0):
        return None
    style = design.field_style(name)
    variants = [apply_case(text, style.get("case"))
                for text in format_variants(name, value, design.formats)]
    weight = int(style.get("weight", 400))
    return Block(
        name=name,
        variants=variants,
        text=variants[0],
        size=float(style.get("size", 12)),
        weight=weight,
        leading=float(style.get("leading", 1.2)),
        tracking=float(style.get("tracking", 0.0)),
        color=scheme.resolve(style.get("color")),
        space_after=float(style.get("space_after", 12)),
        span=style.get("span", 1),
        fit=bool(style.get("fit", True)),
        font=fontmetrics.load(design.font_file(weight)),
    )


def build_cells(design, data, scheme):
    """The grid's cells, in order.

    An entry in ``typography.order`` is either a field name or a list of them.
    A list stacks those fields into one cell, which is how the address sits
    under the venue and the time under the date, in one column of the grid.
    """
    cells = []
    for entry in design.order:
        names = [entry] if isinstance(entry, str) else list(entry)
        blocks = [b for b in (build_block(design, data, scheme, n) for n in names) if b]
        if blocks:
            cells.append(blocks)
    if not cells:
        raise LayoutError("no content fields to set; expected performer/venue/date/...")
    return cells


def cell_height(blocks, scale):
    """A stacked cell, from its first cap line to its last baseline."""
    return (sum(b.height(scale) for b in blocks)
            + sum(b.gap_after(scale) for b in blocks[:-1]))


# --------------------------------------------------------------------------
# flows
# --------------------------------------------------------------------------

MIN_SCALE = 0.35


def _fit(measure, limit, tries=16):
    """Shrink until ``measure(scale)`` fits ``limit``. Returns the scale."""
    scale = 1.0
    for _ in range(tries):
        size = measure(scale)
        if size <= limit + 0.01:
            return scale
        scale = max(MIN_SCALE, scale * (limit / size) * 0.998)
        if scale <= MIN_SCALE:
            break
    return scale


def resolve_span(value, columns):
    """How many grid columns a field occupies. ``all`` spans the measure."""
    if value in (None, "", 1):
        return 1
    if isinstance(value, str):
        key = value.strip().lower()
        if key in ("all", "full", "span"):
            return columns
        value = int(key)
    return max(1, min(int(value), columns))


def flow_grid(cells, box, anchor, free_align, flow, options=None):
    """Lay the fields out on a column grid inside the text box.

    One grid serves both flows: a column flow is a single column, so the fields
    stack down the measure, and a row flow is several, so they run across the
    band. A field spanning every column takes a grid row to itself, which is
    how the performer reads as a banner rather than one item among many.
    """
    options = options or {}
    gutter = float(options.get("column_gap", 26))

    def per_flow(key, default):
        value = options.get(key, default)
        return value.get(flow, default[flow]) if isinstance(value, dict) else value

    columns = max(1, int(per_flow("columns", {"column": 1, "row": 4})))
    # Stacked fields keep their own optical spacing; a grid row of several
    # fields needs more air than the tightest field in it would ask for.
    row_gap = float(per_flow("row_gap", {"column": 0, "row": 12}))
    row_align = normalize_align(options.get("row_align", "end"), "grid.row_align")
    if row_align == "random":
        raise LayoutError("grid.row_align: expected start/middle/end")

    column_width = (box.w - gutter * (columns - 1)) / columns
    if column_width <= 0:
        raise LayoutError(
            f"grid.columns: {columns} columns with a {gutter}pt gutter do not "
            f"fit the {box.w:.0f}pt measure")

    def place(scale):
        """Fill the grid left to right, breaking to a new row when it is full."""
        rows, row, cursor = [], [], 0
        for blocks in cells:
            span = max(resolve_span(b.span, columns) for b in blocks)
            if row and cursor + span > columns:
                rows.append(row)
                row, cursor = [], 0
            width = span * column_width + (span - 1) * gutter
            for block in blocks:
                block.choose_variant(width, scale)
                block.fit_width(width, scale)
                block.wrap(width, scale)
            row.append((blocks, cursor * (column_width + gutter), width))
            cursor += span
            if cursor >= columns:
                rows.append(row)
                row, cursor = [], 0
        if row:
            rows.append(row)
        return rows

    def gap_below(row, scale):
        return max([bs[-1].gap_after(scale) for bs, _, _ in row] + [row_gap * scale])

    def height_of(rows, scale):
        """Row heights, with the spacing the cells in each row ask for."""
        total = sum(max(cell_height(bs, scale) for bs, _, _ in row) for row in rows)
        return total + sum(gap_below(row, scale) for row in rows[:-1])

    # Each cell fits its column on its own; the global scale only resolves a
    # grid that is too tall for the text box.
    scale = _fit(lambda s: height_of(place(s), s), box.h)
    rows = place(scale)
    height = height_of(rows, scale)

    # On a vertical split the free axis is vertical; on a horizontal one the
    # grid fills the width and the rows are pinned to the edge the photo is on.
    slot = free_align if flow == "column" else anchor
    y = box.y
    if slot == "middle":
        y += (box.h - height) / 2
    elif slot == "end":
        y += box.h - height

    # In a column flow the cells are aligned against the photo too.
    cell_anchor = anchor if flow == "column" else "start"
    lines = []
    for i, row in enumerate(rows):
        row_height = max(cell_height(bs, scale) for bs, _, _ in row)
        for blocks, offset, width in row:
            slack = row_height - cell_height(blocks, scale)
            top = y + (slack if row_align == "end"
                       else slack / 2 if row_align == "middle" else 0.0)
            x = box.x + offset + (width if cell_anchor == "end" else 0.0)
            for j, block in enumerate(blocks):
                size = block.px(scale)
                baseline = top + block.font.em("cap_height") * size
                for text in block.lines:
                    if text:
                        lines.append(Line(
                            text=text, x=x, baseline=baseline, anchor=cell_anchor,
                            size=size, weight=block.weight, color=block.color,
                            width=block.font.width(text, size, block.tracking),
                            field=block.name,
                        ))
                    baseline += block.leading * size
                top += block.height(scale)
                if j < len(blocks) - 1:
                    top += block.gap_after(scale)
        y += row_height
        if i < len(rows) - 1:
            y += gap_below(row, scale)

    return lines, {
        "scale": round(scale, 4),
        "columns": columns,
        "column_width": round(column_width, 2),
        "rows": [[[b.name for b in bs] for bs, _, _ in row] for row in rows],
        "text_height": round(height, 2),
    }


# --------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------

def series_scheme(flyer, schemes):
    """The ground a flyer takes from its place in the series.

    Hashing each flyer independently clumps -- six flyers routinely draw the
    same ground three times -- so an unpinned flyer instead takes the next
    ground in rotation, skipping any a sibling has pinned for itself. Adding a
    flyer to the middle of a series therefore re-colours the ones after it,
    which is the trade for an even spread; `palette.assign: independent` goes
    back to hashing.
    """
    rows = flyer.series
    taken = {name for _, name in rows if name}
    pool = [s for s in schemes if s.name not in taken] or list(schemes)
    unpinned = [slug for slug, name in rows if not name]
    index = unpinned.index(flyer.slug) if flyer.slug in unpinned else 0
    return pool[index % len(pool)], index


def _scheme_options(palette):
    """The palette-wide settings every ground is built with."""
    inks = palette.get("ink")
    if isinstance(inks, str):
        inks = {"dark": inks}
    return {"inks": inks or {}, "tint": palette.get("tint", 0.72),
            "switch_at": palette.get("switch_at", "auto")}


def plan(flyer, href_for_image):
    """Resolve every slot and lay the flyer out. ``href_for_image`` supplies the
    image reference (data URI or path) so this module stays I/O free."""
    design = Design(flyer.design.root, deep_merge(flyer.design.data, flyer.overrides))
    choose = Chooser(flyer.data.get("seed", flyer.slug))

    # 1. the monochrome ground ----------------------------------------------
    schemes = schemes_from(design.palette)
    assign = str(design.palette.get("assign", "series")).lower()
    wanted = flyer.data.get("scheme")
    position = None
    if wanted is None and assign == "series":
        scheme, position = series_scheme(flyer, schemes)
    elif wanted is None:
        scheme = choose.pick("scheme", None, schemes)
    elif isinstance(wanted, int):
        scheme = schemes[wanted % len(schemes)]
    elif isinstance(wanted, dict):
        scheme = Scheme(wanted["color"], **_scheme_options(design.palette))
    else:
        named = {s.name: s for s in schemes if s.name}
        if str(wanted) not in named:
            raise LayoutError(
                f"scheme {wanted!r} is not in the palette "
                f"(have: {', '.join(sorted(named)) or 'none named'})")
        scheme = named[str(wanted)]
    # A flyer can also just name its own colour.
    override = flyer.data.get("color") or flyer.data.get("background")
    if override:
        scheme = Scheme(override, **_scheme_options(design.palette))
    background = scheme.background

    # 2. the grid: bisect across the image's short axis ---------------------
    split = str(design.data.get("grid", {}).get("split", "auto")).lower()
    if split in ("auto", "", "none"):
        split = "horizontal" if flyer.orientation == "landscape" else "vertical"
    if split not in ("vertical", "horizontal"):
        raise LayoutError(f"grid.split: expected vertical/horizontal/auto, got {split!r}")

    page = Rect(0, 0, design.width, design.height)
    if split == "vertical":
        cells = [Rect(0, 0, page.w / 2, page.h), Rect(page.w / 2, 0, page.w / 2, page.h)]
    else:
        cells = [Rect(0, 0, page.w, page.h / 2), Rect(0, page.h / 2, page.w, page.h / 2)]

    # 3. which cell holds the image ----------------------------------------
    image_cfg = design.data.get("image", {})
    cell_slot = normalize_align(image_cfg.get("cell"), "image.cell")
    if cell_slot == "middle":
        raise LayoutError("image.cell: expected start/end (left/right, top/bottom)")
    cell_slot = choose.pick("image.cell", cell_slot, ("start", "end"))
    image_index = 0 if cell_slot == "start" else 1
    image_cell, text_cell = cells[image_index], cells[1 - image_index]

    # 4. the photo covers its cell, bleeding to the page edges --------------
    h_align = choose.pick_align("image.h_align", image_cfg.get("h_align"))
    v_align = choose.pick_align("image.v_align", image_cfg.get("v_align"))
    treatment = image_cfg.get("treatment", {}) or {}
    shadow, highlight, blend = scheme.ramp(treatment)
    image = ImagePlacement(
        rect=image_cell,
        href=href_for_image,
        mime=flyer.image_mime,
        preserve_aspect_ratio=f"{_PAR_X[h_align]}{_PAR_Y[v_align]} slice",
        desaturate=float(treatment.get("desaturate", 1.0)),
        shadow=shadow,
        highlight=highlight,
        blend=blend,
    )

    # 5. the text box: page margin outside, gutter against the photo --------
    margin, gutter = design.margin, design.gutter
    if split == "vertical":
        if image_index == 0:                     # photo left, text right
            box, anchor = text_cell.inset(margin, margin, margin, gutter), "start"
        else:                                    # photo right, text left
            box, anchor = text_cell.inset(margin, gutter, margin, margin), "end"
    else:
        if image_index == 0:                     # photo top, text below
            box, anchor = text_cell.inset(gutter, margin, margin, margin), "start"
        else:                                    # photo bottom, text above
            box, anchor = text_cell.inset(margin, margin, gutter, margin), "end"
    if box.w <= 0 or box.h <= 0:
        raise LayoutError("page.margin/page.gutter leave no room for text")

    # 6. flow: column on a vertical split, row on a horizontal one ----------
    flow = str(design.data.get("grid", {}).get("flow", "auto")).lower()
    if flow in ("auto", "", "none"):
        flow = "column" if split == "vertical" else "row"
    free_align = choose.pick_align(
        "text.align", design.data.get("typography", {}).get("align"))

    cells = build_cells(design, flyer.data, scheme)
    lines, notes = flow_grid(cells, box, anchor, free_align, flow,
                             design.data.get("grid", {}))

    notes.update({
        "split": split, "flow": flow, "orientation": flyer.orientation,
        "image_cell": cell_slot, "h_align": h_align, "v_align": v_align,
        "text_anchor": anchor, "free_align": free_align,
        "scheme": scheme.name or background, "ground": background, "ink": scheme.ink,
        "series": "-" if position is None else f"{position + 1}/{len(schemes)}",
        "blend": blend, "ramp": [shadow, highlight],
        "box": [round(v, 2) for v in (box.x, box.y, box.w, box.h)],
    })
    return Plan(width=page.w, height=page.h, background=background,
                image=image, lines=lines, notes=notes)
