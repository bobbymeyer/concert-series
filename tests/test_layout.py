import unittest

from flyer.layout import LayoutError, Rect, apply_case, format_value, plan
from flyer.slots import Chooser, normalize_align

from helpers import BASE, Fixture, SeriesFixture

EPS = 0.75          # a fraction of a point of rounding slack


def text_box(page):
    """The text area the plan reports, as a Rect."""
    return Rect(*page.notes["box"])


def fields_in(row):
    """Every field name in a grid row, across its cells."""
    return [name for cell in row for name in cell]


def extents(line):
    """Left and right edge of a rendered line."""
    if line.anchor == "start":
        return line.x, line.x + line.width
    if line.anchor == "end":
        return line.x - line.width, line.x
    return line.x - line.width / 2, line.x + line.width / 2


class TestSlots(unittest.TestCase):
    def test_alignment_aliases(self):
        for word in ("top", "left", "start", "BEGIN"):
            self.assertEqual(normalize_align(word), "start")
        for word in ("center", "centre", "middle", "MID"):
            self.assertEqual(normalize_align(word), "middle")
        for word in ("bottom", "right", "end"):
            self.assertEqual(normalize_align(word), "end")
        with self.assertRaises(ValueError):
            normalize_align("sideways")

    def test_picks_are_stable_and_independent(self):
        a, b = Chooser("one"), Chooser("one")
        self.assertEqual(a.pick("image.cell", None, ("start", "end")),
                         b.pick("image.cell", None, ("start", "end")))
        # A slot's stream does not depend on what other slots drew.
        alone = Chooser("one").pick("image.v_align", None, ("start", "middle", "end"))
        after = Chooser("one")
        after.pick("image.cell", None, ("start", "end"))
        self.assertEqual(alone, after.pick("image.v_align", None,
                                           ("start", "middle", "end")))

    def test_explicit_values_win(self):
        self.assertEqual(Chooser("x").pick("slot", "end", ("start",)), "end")


class TestContent(unittest.TestCase):
    def test_case_transforms(self):
        self.assertEqual(apply_case("bell house", "upper"), "BELL HOUSE")
        self.assertEqual(apply_case("BELL", "lower"), "bell")
        self.assertEqual(apply_case("bell house", None), "bell house")

    def test_dates_use_the_design_format(self):
        import datetime as dt
        self.assertEqual(
            format_value("date", dt.date(2026, 10, 3), {"date": "%A, %B %-d"}),
            "Saturday, October 3")

    def test_lists_become_hard_lines(self):
        self.assertEqual(format_value("details", ["one", "two"], {}), "one\ntwo")


class TestGrid(unittest.TestCase):
    def test_portrait_splits_vertically(self):
        with Fixture(size=(60, 90)) as flyer:
            page = plan(flyer, "photo.png")
            self.assertEqual(page.notes["split"], "vertical")
            self.assertEqual(page.notes["flow"], "column")
            self.assertEqual(page.image.rect.h, page.height)
            self.assertAlmostEqual(page.image.rect.w, page.width / 2)

    def test_landscape_splits_horizontally(self):
        with Fixture(size=(90, 60)) as flyer:
            page = plan(flyer, "photo.png")
            self.assertEqual(page.notes["split"], "horizontal")
            self.assertEqual(page.notes["flow"], "row")
            self.assertEqual(page.image.rect.w, page.width)
            self.assertAlmostEqual(page.image.rect.h, page.height / 2)

    def test_photo_bleeds_to_the_page_edges(self):
        for size in ((60, 90), (90, 60)):
            with Fixture(size=size) as flyer:
                page = plan(flyer, "photo.png")
                rect = page.image.rect
                self.assertTrue(rect.x == 0 or rect.x + rect.w == page.width)
                self.assertTrue(rect.y == 0 or rect.y + rect.h == page.height)

    def test_crop_anchor_follows_the_alignment(self):
        cases = {("left", "top"): "xMinYMin slice",
                 ("center", "bottom"): "xMidYMax slice",
                 ("right", "middle"): "xMaxYMid slice"}
        for (h, v), expected in cases.items():
            with Fixture({"image": {"h_align": h, "v_align": v}}) as flyer:
                self.assertEqual(plan(flyer, "p.png").image.preserve_aspect_ratio,
                                 expected)

    def test_text_hugs_the_photo(self):
        with Fixture({"image": {"cell": "left"}}, size=(60, 90)) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.notes["text_anchor"], "start")
            self.assertGreaterEqual(text_box(page).x, page.width / 2)
        with Fixture({"image": {"cell": "right"}}, size=(60, 90)) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.notes["text_anchor"], "end")
            self.assertLessEqual(text_box(page).x + text_box(page).w, page.width / 2)
        with Fixture({"image": {"cell": "top"}}, size=(90, 60)) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.notes["text_anchor"], "start")
            self.assertGreaterEqual(text_box(page).y, page.height / 2)

    def test_middle_is_not_a_cell(self):
        with Fixture({"image": {"cell": "center"}}) as flyer:
            with self.assertRaises(LayoutError):
                plan(flyer, "p.png")


class TestTextFits(unittest.TestCase):
    """Across the whole matrix of slots, type stays inside the text box."""

    def matrix(self):
        for size in ((60, 90), (90, 60)):
            for cell in ("start", "end"):
                for align in ("start", "middle", "end"):
                    yield size, cell, align

    def test_type_stays_in_its_box(self):
        for size, cell, align in self.matrix():
            overrides = {"image": {"cell": cell},
                         "typography": {"align": align}}
            with self.subTest(size=size, cell=cell, align=align):
                with Fixture(overrides, size=size) as flyer:
                    page = plan(flyer, "p.png")
                    box = text_box(page)
                    for line in page.lines:
                        left, right = extents(line)
                        self.assertGreaterEqual(left, box.x - EPS, line.text)
                        self.assertLessEqual(right, box.x + box.w + EPS, line.text)
                        cap = line.baseline - line.size * 0.7
                        self.assertGreaterEqual(cap, box.y - EPS, line.text)
                        self.assertLessEqual(line.baseline, box.y + box.h + EPS,
                                             line.text)

    def test_long_unbreakable_words_shrink_rather_than_overflow(self):
        with Fixture({"performer": "Llanfairpwllgwyngyllgogerychwyrn"},
                     size=(60, 90)) as flyer:
            page = plan(flyer, "p.png")
            box = text_box(page)
            head = [line for line in page.lines if line.field == "performer"]
            self.assertTrue(head)
            for line in head:
                self.assertLessEqual(extents(line)[1], box.x + box.w + EPS)
            # Only the headline comes down; the body copy keeps its size.
            body = next(line for line in page.lines if line.field == "details")
            self.assertAlmostEqual(body.size, 10.5, places=2)

    def test_column_lines_never_collide(self):
        with Fixture(size=(60, 90)) as flyer:
            page = plan(flyer, "p.png")
            ordered = sorted(page.lines, key=lambda line: line.baseline)
            for above, below in zip(ordered, ordered[1:]):
                self.assertGreater(below.baseline - above.baseline,
                                   above.size * 0.75, f"{above.text} / {below.text}")

    def test_row_flow_shares_a_baseline_across_each_row(self):
        with Fixture(size=(90, 60)) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.notes["flow"], "row")
            last = {}
            for line in page.lines:
                last[line.field] = max(last.get(line.field, 0), line.baseline)
            # Every cell in a row ends on the row's baseline, whatever it holds.
            for row in page.notes["rows"]:
                bottoms = {round(last[cell[-1]], 3) for cell in row}
                self.assertEqual(len(bottoms), 1, f"{row} -> {bottoms}")
            # The rows themselves still differ.
            self.assertGreater(len({round(l.baseline, 3) for l in page.lines}), 1)

    def test_row_align_can_be_moved_to_the_top(self):
        """A one-line cost beside a two-field stack shows which edge lines up."""
        def measure(row_align):
            overrides = {"grid": {"row_align": row_align}} if row_align else {}
            with Fixture(overrides, size=(90, 60)) as flyer:
                page = plan(flyer, "p.png")
                row = next(r for r in page.notes["rows"] if "cost" in fields_in(r))
                self.assertIn("address", fields_in(row))
                first, last = {}, {}
                for line in page.lines:
                    if line.field in ("cost", "venue", "address"):
                        first.setdefault(line.field, (line.baseline, line.size))
                        last[line.field] = line.baseline
                caps = {f: b - 0.7 * size for f, (b, size) in first.items()}
                return caps, last

        _, last = measure(None)      # the default: the cells end together
        self.assertAlmostEqual(last["cost"], last["address"], places=3)
        caps, last = measure("top")  # the cells start together instead
        self.assertAlmostEqual(caps["cost"], caps["venue"], places=2)
        self.assertNotAlmostEqual(last["cost"], last["address"], places=1)

    def test_sparse_content_still_lays_out(self):
        with Fixture({"venue": None, "address": None, "cost": None,
                      "details": None}, size=(60, 90)) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual({line.field for line in page.lines},
                             {"performer", "date", "time"})

    def test_no_content_is_an_error(self):
        with Fixture({k: None for k in BASE}) as f:
            with self.assertRaises(LayoutError):
                plan(f, "p.png")


class TestGrid2(unittest.TestCase):
    """The text sits on a column grid, and the performer spans it."""

    def test_the_performer_spans_the_measure(self):
        for size in ((60, 90), (90, 60)):
            with self.subTest(size=size):
                with Fixture(size=size) as flyer:
                    page = plan(flyer, "p.png")
                    box = text_box(page)
                    self.assertEqual(page.notes["rows"][0], [["performer"]])
                    head = [l for l in page.lines if l.field == "performer"]
                    self.assertTrue(all(l.x == box.x for l in head))

    def test_cells_snap_to_the_column_grid(self):
        with Fixture(size=(90, 60)) as flyer:
            page = plan(flyer, "p.png")
            box = text_box(page)
            columns, width = page.notes["columns"], page.notes["column_width"]
            self.assertGreater(columns, 1)
            gutter = (box.w - columns * width) / (columns - 1)
            tracks = [round(box.x + i * (width + gutter), 2) for i in range(columns)]
            for line in page.lines:
                self.assertIn(round(line.x, 2), tracks, line.text)

    def test_column_flow_is_a_single_column(self):
        with Fixture(size=(60, 90)) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.notes["columns"], 1)
            self.assertEqual(page.notes["rows"],
                             [[["performer"]], [["venue", "address"]],
                              [["date", "time"]], [["cost"]], [["details"]]])

    def test_a_span_wider_than_the_grid_is_clamped(self):
        with Fixture({"typography": {"fields": {"venue": {"span": 9}}}},
                     size=(90, 60)) as flyer:
            page = plan(flyer, "p.png")
            row = next(r for r in page.notes["rows"] if "venue" in fields_in(r))
            self.assertEqual(fields_in(row), ["venue", "address"])

    def test_the_grid_can_be_widened(self):
        with Fixture({"grid": {"columns": {"row": 6}}}, size=(90, 60)) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.notes["columns"], 6)
            self.assertLess(page.notes["column_width"], 90)

    def test_stacked_fields_share_one_cell(self):
        with Fixture(size=(90, 60)) as flyer:
            page = plan(flyer, "p.png")
            row = next(r for r in page.notes["rows"] if "venue" in fields_in(r))
            self.assertEqual(row, [["venue", "address"], ["date", "time"], ["cost"]])
            at = {l.field: (l.x, l.baseline) for l in page.lines}
            # Stacked: same column, the second below the first.
            for top, below in (("venue", "address"), ("date", "time")):
                self.assertEqual(at[top][0], at[below][0])
                self.assertGreater(at[below][1], at[top][1])
            # Side by side: the cells start on different tracks.
            self.assertLess(at["venue"][0], at["date"][0])
            self.assertLess(at["date"][0], at["cost"][0])

    def test_a_missing_field_collapses_its_stack(self):
        with Fixture({"address": None}, size=(90, 60)) as flyer:
            page = plan(flyer, "p.png")
            row = next(r for r in page.notes["rows"] if "venue" in fields_in(r))
            self.assertEqual(row, [["venue"], ["date", "time"], ["cost"]])

    def test_too_many_columns_is_reported(self):
        with Fixture({"grid": {"columns": {"column": 40}}}, size=(60, 90)) as f:
            with self.assertRaisesRegex(LayoutError, "do not"):
                plan(f, "p.png")


class TestDeterminism(unittest.TestCase):
    def test_same_content_renders_the_same_flyer(self):
        with Fixture(size=(60, 90)) as flyer:
            first, second = plan(flyer, "p.png"), plan(flyer, "p.png")
            self.assertEqual(first.notes, second.notes)
            self.assertEqual([line.text for line in first.lines],
                             [line.text for line in second.lines])

    def test_a_seed_overrides_the_folder_name(self):
        picks = set()
        for seed in range(12):
            with Fixture({"seed": seed}, size=(60, 90)) as flyer:
                notes = plan(flyer, "p.png").notes
                picks.add((notes["image_cell"], notes["h_align"], notes["scheme"]))
        self.assertGreater(len(picks), 1, "seeds should reach different layouts")


class TestSeries(unittest.TestCase):
    """Unpinned grounds rotate through the palette rather than being hashed."""

    SIX = {f"flyer-{i}": None for i in range(6)}

    def grounds(self, flyers):
        return [plan(f, "p.png").notes["scheme"] for f in flyers]

    def test_a_run_of_flyers_spreads_across_the_palette(self):
        with SeriesFixture(self.SIX) as flyers:
            grounds = self.grounds(flyers)
            self.assertEqual(len(set(grounds)), 6, grounds)
            self.assertEqual(grounds,
                             ["bone", "acid", "mint", "clay", "dusk", "night"])

    def test_more_flyers_than_grounds_wraps_around(self):
        with SeriesFixture({f"flyer-{i}": None for i in range(8)}) as flyers:
            grounds = self.grounds(flyers)
            self.assertEqual(grounds[6:], grounds[:2])

    def test_a_pinned_ground_is_left_out_of_the_rotation(self):
        flyers = dict(self.SIX)
        flyers["flyer-2"] = {"scheme": "bone"}
        with SeriesFixture(flyers) as built:
            grounds = self.grounds(built)
            self.assertEqual(grounds[2], "bone")
            # bone is spoken for, so nobody else takes it.
            self.assertEqual(grounds.count("bone"), 1)
            self.assertEqual(len(set(grounds)), 6, grounds)

    def test_position_is_reported(self):
        with SeriesFixture(self.SIX) as flyers:
            self.assertEqual([plan(f, "p.png").notes["series"] for f in flyers],
                             [f"{i + 1}/6" for i in range(6)])

    def test_building_one_flyer_gives_it_the_same_ground(self):
        with SeriesFixture(self.SIX) as flyers:
            alone = plan(flyers[3], "p.png").notes["scheme"]
        with SeriesFixture(self.SIX) as flyers:
            self.assertEqual(self.grounds(flyers)[3], alone)

    def test_independent_assignment_goes_back_to_hashing(self):
        flyers = {slug: {"palette": {"assign": "independent"}} for slug in self.SIX}
        with SeriesFixture(flyers) as built:
            grounds = self.grounds(built)
            self.assertEqual([plan(f, "p.png").notes["series"] for f in built],
                             ["-"] * 6)
            # Each flyer is drawn on its own, so the palette order is not used.
            self.assertNotEqual(
                grounds, ["bone", "acid", "mint", "clay", "dusk", "night"])


class TestSchemes(unittest.TestCase):
    def test_named_scheme_is_honoured(self):
        with Fixture({"scheme": "acid"}) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.notes["scheme"], "acid")
            self.assertEqual(page.background, "#DCE84B")

    def test_unknown_scheme_is_reported(self):
        with Fixture({"scheme": "chartreuse"}) as flyer:
            with self.assertRaisesRegex(LayoutError, "chartreuse"):
                plan(flyer, "p.png")

    def test_background_is_an_alias_for_colour(self):
        with Fixture({"background": "#EFE7DA"}) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.background, "#EFE7DA")
            self.assertEqual(page.notes["ink"], "#000000")

    def test_a_dark_ground_screens_up_to_white(self):
        with Fixture({"scheme": "dusk"}) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.image.blend, "screen")
            self.assertEqual([page.image.shadow, page.image.highlight],
                             ["#17293B", "#FFFFFF"])
            self.assertEqual(page.notes["ink"], "#FFFFFF")

    def test_a_light_ground_multiplies_down_to_black(self):
        with Fixture({"scheme": "bone"}) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.image.blend, "multiply")
            self.assertEqual([page.image.shadow, page.image.highlight],
                             ["#000000", "#EFE7DA"])
            self.assertEqual(page.notes["ink"], "#000000")

    def test_the_blend_can_be_forced(self):
        with Fixture({"scheme": "bone",
                      "image": {"treatment": {"blend": "screen"}}}) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.image.blend, "screen")
            self.assertEqual([page.image.shadow, page.image.highlight],
                             ["#EFE7DA", "#FFFFFF"])

    def test_a_flyer_can_name_its_own_colour(self):
        with Fixture({"color": "#123456"}) as flyer:
            page = plan(flyer, "p.png")
            self.assertEqual(page.background, "#123456")
            self.assertEqual(page.image.blend, "screen")


if __name__ == "__main__":
    unittest.main()
