import unittest

from flyer.units import fmt, to_pt


class TestUnits(unittest.TestCase):
    def test_absolute_lengths(self):
        self.assertEqual(to_pt("8.5in"), 612)
        self.assertEqual(to_pt("11in"), 792)
        self.assertEqual(to_pt("12pt"), 12)
        self.assertEqual(to_pt(24), 24)
        self.assertAlmostEqual(to_pt("25.4mm"), 72)
        self.assertAlmostEqual(to_pt("2.54cm"), 72)

    def test_relative_lengths(self):
        self.assertAlmostEqual(to_pt("-0.02em", em=50), -1.0)
        self.assertAlmostEqual(to_pt("50%", em=24), 12)
        with self.assertRaises(ValueError):
            to_pt("2em")

    def test_rejects_nonsense(self):
        with self.assertRaises(ValueError):
            to_pt("wide")
        with self.assertRaises(ValueError):
            to_pt("10furlongs")

    def test_fmt_trims(self):
        self.assertEqual(fmt(306.0), "306")
        self.assertEqual(fmt(1.23456), "1.235")
        self.assertEqual(fmt(-0.0001), "0")
