import unittest

from flyer.color import Scheme, contrast, luminance, parse, schemes_from

PALETTE = {
    "ink": "#141414",
    "paper": "#FBF9F5",
    "schemes": [
        {"name": "dusk", "background": "#17293B", "ink": "#F0E6D6", "accent": "#E9A13B"},
        {"name": "bone", "background": "#EFE7DA"},
    ],
}


class TestColor(unittest.TestCase):
    def test_parse_forms(self):
        self.assertEqual(parse("#fff"), (1.0, 1.0, 1.0))
        self.assertEqual(parse("000000"), (0.0, 0.0, 0.0))

    def test_contrast_is_symmetric_and_bounded(self):
        self.assertAlmostEqual(contrast("#000", "#fff"), 21, places=1)
        self.assertAlmostEqual(contrast("#123456", "#abcdef"),
                               contrast("#abcdef", "#123456"))

    def test_scheme_without_ink_picks_a_readable_neutral(self):
        bone = schemes_from(PALETTE)[1]
        self.assertEqual(bone.ink, "#141414")
        self.assertGreater(contrast(bone.ink, bone.background), 4.5)

    def test_accent_falls_back_when_it_would_vanish(self):
        washed = Scheme({"background": "#E9A13B", "ink": "#17293B",
                         "accent": "#E9A13B"}, PALETTE)
        self.assertEqual(washed.resolve("accent"), washed.ink)

    def test_scheme_without_accent_uses_ink(self):
        self.assertEqual(schemes_from(PALETTE)[1].resolve("accent"), "#141414")

    def test_duotone_runs_dark_to_light(self):
        for scheme in schemes_from(PALETTE):
            shadow, highlight = scheme.duotone()
            self.assertLess(luminance(shadow), luminance(highlight))
            self.assertIn(shadow, (scheme.ink, scheme.background))
            self.assertIn(highlight, (scheme.ink, scheme.background))
            self.assertNotEqual(shadow, highlight)

    def test_literal_multiply_is_available(self):
        dusk = schemes_from(PALETTE)[0]
        self.assertEqual(dusk.duotone({"shadow": "#000000", "highlight": "background"}),
                         ("#000000", "#17293B"))

    def test_backgrounds_shorthand(self):
        schemes = schemes_from({"ink": "#111111", "paper": "#FFFFFF",
                                "backgrounds": ["#FFFFFF", "#000000"]})
        self.assertEqual([s.ink for s in schemes], ["#111111", "#FFFFFF"])
