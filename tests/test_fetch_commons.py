"""The licence gate on the Commons fetcher. No network is touched."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from fetch_commons import is_free, strip_markup   # noqa: E402


class TestLicenceGate(unittest.TestCase):
    FREE = ["CC0", "CC0 1.0", "CC BY 4.0", "CC-BY-SA-3.0", "CC BY-SA 4.0",
            "Public domain", "PD-old-70", "Attribution"]
    NOT_FREE = ["CC BY-NC 3.0", "CC BY-NC-SA 4.0", "CC BY-ND 2.0", "Fair use",
                "Non-free", "Copyrighted", "", None, "All rights reserved"]

    def test_free_licences_pass(self):
        for name in self.FREE:
            with self.subTest(name):
                self.assertTrue(is_free(name))

    def test_everything_else_is_refused(self):
        for name in self.NOT_FREE:
            with self.subTest(name):
                self.assertFalse(is_free(name))

    def test_a_restriction_beats_a_match(self):
        """A licence reading as both is refused: the gate errs toward not using."""
        self.assertFalse(is_free("CC BY-NC-ND 4.0"))

    def test_author_markup_is_stripped(self):
        self.assertEqual(
            strip_markup('<a href="/wiki/User:X" title="X">Some Photographer</a>'),
            "Some Photographer")
        self.assertEqual(strip_markup("Rossi &amp; Bianchi"), "Rossi & Bianchi")
        self.assertEqual(strip_markup(None), "")


if __name__ == "__main__":
    unittest.main()
