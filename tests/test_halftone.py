"""Cropping, seeding and the rescreen guard. Needs Pillow; skipped without it."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

try:
    from PIL import Image
    import halftone
except (ImportError, SystemExit):                    # pragma: no cover
    halftone = None


@unittest.skipIf(halftone is None, "Pillow is not installed")
class TestCrop(unittest.TestCase):
    def crop(self, size, aspect, hx, vy):
        return halftone.crop_to(Image.new("RGB", size), aspect, hx, vy)

    def test_a_wide_source_loses_width(self):
        self.assertEqual(self.crop((400, 100), 1.0, 0.5, 0.5).size, (100, 100))

    def test_a_tall_source_loses_height(self):
        self.assertEqual(self.crop((100, 400), 1.0, 0.5, 0.5).size, (100, 100))

    def test_the_anchor_picks_which_part_is_kept(self):
        wide = Image.new("RGB", (400, 100))
        for x in range(400):
            for y in range(100):
                wide.putpixel((x, y), (x % 256, 0, 0))
        left = halftone.crop_to(wide, 1.0, 0.0, 0.5)
        right = halftone.crop_to(wide, 1.0, 1.0, 0.5)
        self.assertEqual(left.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(right.getpixel((0, 0)), (300 % 256, 0, 0))

    def test_a_source_already_at_the_aspect_is_untouched(self):
        self.assertEqual(self.crop((300, 200), 1.5, 0.5, 0.5).size, (300, 200))


@unittest.skipIf(halftone is None, "Pillow is not installed")
class TestSeed(unittest.TestCase):
    def test_a_slug_always_seeds_the_same_screen(self):
        self.assertEqual(halftone.seed_for("piero-piccioni"),
                         halftone.seed_for("piero-piccioni"))

    def test_two_flyers_get_two_screens(self):
        self.assertNotEqual(halftone.seed_for("piero-piccioni"),
                            halftone.seed_for("ennio-morricone"))


@unittest.skipIf(halftone is None, "Pillow is not installed")
class TestRescreenGuard(unittest.TestCase):
    def test_a_halftone_is_recognised(self):
        """One ink at one strength: half the picture sits on two levels."""
        dots = Image.new("L", (100, 100), 223)
        for x in range(0, 100, 2):
            for y in range(0, 100, 2):
                dots.putpixel((x, y), 20)
        self.assertTrue(halftone.is_screened(dots))

    def test_a_photograph_is_not(self):
        """Continuous tone spreads across the range, peaking nowhere."""
        ramp = Image.new("L", (256, 256))
        for x in range(256):
            for y in range(256):
                ramp.putpixel((x, y), x)
        self.assertFalse(halftone.is_screened(ramp))
