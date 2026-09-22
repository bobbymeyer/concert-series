import unittest

from flyer.color import Scheme, contrast, luminance, mix, parse, schemes_from

PALETTE = {
    "ink": {"dark": "#000000", "light": "#FFFFFF"},
    "tint": 0.72,
    "colors": {"bone": "#EFE7DA", "clay": "#A63D26", "night": "#1A1A1A"},
}


def scheme(name):
    return {s.name: s for s in schemes_from(PALETTE)}[name]


class TestColor(unittest.TestCase):
    def test_parse_forms(self):
        self.assertEqual(parse("#fff"), (1.0, 1.0, 1.0))
        self.assertEqual(parse("000000"), (0.0, 0.0, 0.0))

    def test_contrast_is_symmetric_and_bounded(self):
        self.assertAlmostEqual(contrast("#000", "#fff"), 21, places=1)
        self.assertAlmostEqual(contrast("#123456", "#abcdef"),
                               contrast("#abcdef", "#123456"))

    def test_mix_interpolates(self):
        self.assertEqual(mix("#FFFFFF", "#000000", 1.0), "#FFFFFF")
        self.assertEqual(mix("#FFFFFF", "#000000", 0.0), "#000000")
        self.assertEqual(mix("#FFFFFF", "#000000", 0.5), "#808080")


class TestMonochrome(unittest.TestCase):
    def test_light_ground_takes_dark_ink_and_multiplies(self):
        bone = scheme("bone")
        self.assertEqual(bone.ink, "#000000")
        self.assertEqual(bone.blend, "multiply")
        self.assertEqual(bone.ramp(), ("#000000", "#EFE7DA", "multiply"))

    def test_dark_ground_takes_white_ink_and_screens(self):
        for name in ("clay", "night"):
            with self.subTest(name):
                ground = scheme(name)
                self.assertEqual(ground.ink, "#FFFFFF")
                self.assertEqual(ground.blend, "screen")
                self.assertEqual(ground.ramp(),
                                 (ground.background, "#FFFFFF", "screen"))

    def test_the_photo_always_runs_between_the_ground_and_the_ink(self):
        for ground in schemes_from(PALETTE):
            shadow, highlight, _ = ground.ramp()
            self.assertEqual({shadow, highlight}, {ground.background, ground.ink})
            self.assertLess(luminance(shadow), luminance(highlight))

    def test_every_ground_is_legible(self):
        for ground in schemes_from(PALETTE):
            self.assertGreater(contrast(ground.ink, ground.background), 4.5,
                               ground.name)

    def test_switch_point_can_be_pinned_to_a_luminance(self):
        light = Scheme("#A63D26", switch_at=0.05)     # below the auto crossover
        self.assertEqual(light.ink, "#000000")
        self.assertEqual(light.blend, "multiply")

    def test_blend_can_be_forced(self):
        bone = scheme("bone")
        self.assertEqual(bone.ramp({"blend": "screen"}),
                         ("#EFE7DA", "#FFFFFF", "screen"))
        with self.assertRaises(ValueError):
            bone.ramp({"blend": "overlay"})

    def test_ramp_ends_can_be_overridden(self):
        bone = scheme("bone")
        self.assertEqual(bone.ramp({"shadow": "#333333"})[0], "#333333")
        self.assertEqual(bone.ramp({"highlight": "tint"})[1], bone.tint)

    def test_tint_sits_between_the_ink_and_the_ground(self):
        for ground in schemes_from(PALETTE):
            between = sorted(luminance(c) for c in
                             (ground.ink, ground.background))
            self.assertGreater(luminance(ground.tint), between[0])
            self.assertLess(luminance(ground.tint), between[1])

    def test_roles_are_only_the_monochrome_ones(self):
        bone = scheme("bone")
        self.assertEqual(bone.resolve("ink"), bone.ink)
        self.assertEqual(bone.resolve("ground"), bone.background)
        self.assertEqual(bone.resolve("tint"), bone.tint)
        self.assertEqual(bone.resolve("#ABCDEF"), "#ABCDEF")
        with self.assertRaisesRegex(ValueError, "monochrome"):
            bone.resolve("chartreuse")

    def test_plain_list_of_colours(self):
        schemes = schemes_from({"colors": ["#FFFFFF", "#000000"]})
        self.assertEqual([s.ink for s in schemes], ["#000000", "#FFFFFF"])
        self.assertEqual([s.blend for s in schemes], ["multiply", "screen"])
