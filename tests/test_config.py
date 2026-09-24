import unittest

from flyer.config import ConfigError, Design, Flyer, deep_merge

from helpers import DESIGN, Fixture


class TestMerge(unittest.TestCase):
    def test_deep_merge_does_not_mutate(self):
        base = {"page": {"margin": 36, "gutter": 36}, "grid": {"split": "auto"}}
        merged = deep_merge(base, {"page": {"margin": 18}})
        self.assertEqual(merged["page"], {"margin": 18, "gutter": 36})
        self.assertEqual(base["page"]["margin"], 36)


class TestDesign(unittest.TestCase):
    def setUp(self):
        self.design = Design.load(DESIGN)

    def test_page_geometry(self):
        self.assertEqual((self.design.width, self.design.height), (612, 792))

    def test_font_weight_lookup_snaps_to_the_nearest(self):
        self.assertTrue(self.design.font_file(800).name.endswith("ExtraBold.ttf"))
        self.assertTrue(self.design.font_file(450).name.endswith("Regular.ttf"))

    def test_shipped_fonts_all_exist(self):
        for weight in self.design.data["fonts"]["weights"]:
            self.assertTrue(self.design.font_file(weight).exists())

    def test_field_style_inherits_the_defaults(self):
        style = self.design.field_style("details")
        self.assertEqual(style["weight"], 400)
        self.assertIn("leading", style)


class TestFlyer(unittest.TestCase):
    def test_orientation_from_the_photo(self):
        for size, expected in (((60, 90), "portrait"), ((90, 60), "landscape"),
                               ((60, 60), "square")):
            with Fixture(size=size) as flyer:
                self.assertEqual(flyer.orientation, expected)

    def test_a_square_photo_splits_vertically(self):
        from flyer.layout import plan
        with Fixture(size=(60, 60)) as flyer:
            self.assertEqual(plan(flyer, "p.png").notes["split"], "vertical")

    def test_missing_yaml_is_reported(self):
        with Fixture() as flyer:
            (flyer.folder / "flyer.yaml").unlink()
            with self.assertRaisesRegex(ConfigError, "no flyer.yaml"):
                Flyer(flyer.folder, flyer.design)

    def test_two_photos_need_naming(self):
        with Fixture() as flyer:
            (flyer.folder / "other.png").write_bytes(flyer.image_path.read_bytes())
            with self.assertRaisesRegex(ConfigError, "name one with"):
                Flyer(flyer.folder, flyer.design)

    def test_a_source_is_not_a_second_photo(self):
        """`source.*` is what halftone.py screens from, so it never counts."""
        with Fixture() as flyer:
            (flyer.folder / "source.jpg").write_bytes(flyer.image_path.read_bytes())
            self.assertEqual(Flyer(flyer.folder, flyer.design).image_path.name,
                             "photo.png")

    def test_a_source_can_still_be_named(self):
        with Fixture() as flyer:
            (flyer.folder / "source.png").write_bytes(flyer.image_path.read_bytes())
            text = (flyer.folder / "flyer.yaml").read_text()
            (flyer.folder / "flyer.yaml").write_text(text + "\nimage: source.png\n")
            self.assertEqual(Flyer(flyer.folder, flyer.design).image_path.name,
                             "source.png")

    def test_a_named_photo_resolves_the_ambiguity(self):
        with Fixture() as flyer:
            (flyer.folder / "chosen.png").write_bytes(flyer.image_path.read_bytes())
            text = (flyer.folder / "flyer.yaml").read_text()
            (flyer.folder / "flyer.yaml").write_text(text + "\nimage: chosen.png\n")
            self.assertEqual(Flyer(flyer.folder, flyer.design).image_path.name,
                             "chosen.png")

    def test_a_flyer_can_override_the_design(self):
        from flyer.layout import plan
        with Fixture({"page": {"margin": "1in"}}, size=(60, 90)) as flyer:
            self.assertEqual(plan(flyer, "p.png").notes["box"][1], 72.0)


if __name__ == "__main__":
    unittest.main()
