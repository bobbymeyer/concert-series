"""Line breaking: real metrics, hard breaks, and particles that stay put."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flyer.fontmetrics import bind_particles, load, wrap   # noqa: E402

FONT = load(ROOT / "design" / "fonts" / "RethinkSans-ExtraBold.ttf")


class TestBinding(unittest.TestCase):
    def test_a_short_particle_joins_the_word_after_it(self):
        self.assertEqual(bind_particles("GUIDO & MAURIZIO DE ANGELIS".split()),
                         ["GUIDO", "&", "MAURIZIO", "DE ANGELIS"])

    def test_it_works_for_other_names(self):
        self.assertEqual(bind_particles("Ludwig van Beethoven".split()),
                         ["Ludwig", "van Beethoven"])
        self.assertEqual(bind_particles("Vincent van der Berg".split()),
                         ["Vincent", "van der Berg"])

    def test_a_connective_is_left_where_it_is(self):
        """An ampersand reads fine at the end of a line; a particle does not."""
        self.assertIn("&", bind_particles("GUIDO & MAURIZIO".split()))

    def test_a_trailing_particle_has_nothing_to_join(self):
        self.assertEqual(bind_particles(["ANGELIS", "DE"]), ["ANGELIS", "DE"])

    def test_long_words_are_untouched(self):
        words = "Antonio Carlos Jobim".split()
        self.assertEqual(bind_particles(words), words)

    def test_binding_can_be_turned_off(self):
        self.assertEqual(bind_particles("GUIDO DE ANGELIS".split(), bind_max=0),
                         ["GUIDO", "DE", "ANGELIS"])


class TestWrap(unittest.TestCase):
    NAME = "GUIDO & MAURIZIO DE ANGELIS"

    def lines_at(self, width, **kwargs):
        return wrap(FONT, self.NAME, 58, width, **kwargs)

    def test_the_pair_stays_together_wherever_it_fits(self):
        """318pt at this size, so any measure that wide keeps it whole."""
        for width in (320, 400, 540):
            with self.subTest(width=width):
                lines = self.lines_at(width)
                self.assertTrue(any("DE ANGELIS" in line for line in lines), lines)
                self.assertNotIn("DE", lines)

    def test_a_pair_too_wide_to_fit_gives_way(self):
        """wrap cannot shrink, so the last resort is an ordinary break --
        never an overflowing line. Holding the pair together at a narrow
        measure is the layout's job, by shrinking the block."""
        for width in (120, 240, 280):
            for line in self.lines_at(width):
                self.assertLessEqual(FONT.width(line, 58), width + 1, line)

    def test_turning_binding_off_restores_the_old_break(self):
        """At 280 the unbound break is exactly the fault this fixes."""
        self.assertIn("DE", self.lines_at(280, bind_max=0))

    def test_wrapping_still_respects_the_measure(self):
        for width in (150, 240, 400):
            for line in self.lines_at(width):
                self.assertLessEqual(FONT.width(line, 58), width + 1)


class TestHeadlineShrinksToHoldAPair(unittest.TestCase):
    """The layout, unlike wrap, can shrink -- and does, rather than strand."""

    def test_the_de_angelis_headline_never_strands_its_particle(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from helpers import Fixture
        from flyer.layout import plan

        for size in ((60, 90), (90, 60)):
            with self.subTest(size=size):
                with Fixture({"performer": "Guido & Maurizio De Angelis"},
                             size=size) as flyer:
                    page = plan(flyer, "p.png")
                    head = [l.text for l in page.lines if l.field == "performer"]
                    self.assertNotIn("DE", head, head)
                    self.assertTrue(any("DE ANGELIS" in line for line in head),
                                    head)


if __name__ == "__main__":
    unittest.main()
