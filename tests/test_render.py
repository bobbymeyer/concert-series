import base64
import re
import unittest
import xml.etree.ElementTree as ET

from flyer.imageinfo import ImageError, probe
from flyer.render import render

from helpers import Fixture

SVG = "{http://www.w3.org/2000/svg}"


class TestImageProbe(unittest.TestCase):
    def test_reads_png_dimensions(self):
        with Fixture(size=(37, 91)) as flyer:
            self.assertEqual(probe(flyer.image_path), (37, 91, "image/png"))

    def test_rejects_other_files(self):
        with Fixture() as flyer:
            bogus = flyer.folder / "notes.png"
            bogus.write_bytes(b"this is not an image")
            with self.assertRaises(ImageError):
                probe(bogus)


class TestRender(unittest.TestCase):
    def svg(self, flyer, **kwargs):
        text, page = render(flyer, **kwargs)
        return ET.fromstring(text), text, page

    def test_output_is_well_formed_and_page_sized(self):
        with Fixture(size=(60, 90)) as flyer:
            root, _, _ = self.svg(flyer)
            self.assertEqual(root.get("width"), "8.5in")
            self.assertEqual(root.get("height"), "11in")
            self.assertEqual(root.get("viewBox"), "0 0 612 792")

    def test_photo_and_fonts_are_embedded(self):
        with Fixture(size=(60, 90)) as flyer:
            root, text, _ = self.svg(flyer)
            image = root.find(f".//{SVG}image")
            self.assertTrue(image.get("href").startswith("data:image/png;base64,"))
            self.assertIn("@font-face", text)
            self.assertIn("font-family:'Rethink Sans'", text)
            # Only the weights this flyer actually sets are carried.
            self.assertEqual(sorted(re.findall(r"font-weight:(\d+);", text)),
                             ["400", "500", "700", "800"])

    def test_nothing_external_is_referenced(self):
        with Fixture(size=(60, 90)) as flyer:
            _, text, _ = self.svg(flyer)
            self.assertNotIn("http://", text.replace("http://www.w3.org", ""))
            self.assertNotIn("https://", text)

    def test_no_embed_leaves_a_relative_reference(self):
        with Fixture(size=(60, 90)) as flyer:
            root, text, _ = self.svg(flyer, embed_images=False, embed_fonts=False)
            self.assertEqual(root.find(f".//{SVG}image").get("href"), "photo.png")
            self.assertNotIn("@font-face", text)

    def ends(self, root):
        """The (shadow, highlight) each channel of the tone filter ramps between."""
        low, high = [], []
        for channel in "RGB":
            func = root.find(f".//{SVG}feFunc{channel}")
            low.append(float(func.get("intercept")))
            high.append(low[-1] + float(func.get("slope")))
        return low, high

    def test_photo_is_desaturated_before_the_ramp(self):
        with Fixture({"scheme": "dusk"}, size=(60, 90)) as flyer:
            root, _, _ = self.svg(flyer)
            matrix = root.find(f".//{SVG}feColorMatrix")
            self.assertEqual(matrix.get("type"), "saturate")
            self.assertEqual(matrix.get("values"), "1")
            self.assertEqual(
                root.find(f".//{SVG}filter").get("color-interpolation-filters"), "sRGB")

    def test_dark_ground_screens_the_photo_up_to_white(self):
        with Fixture({"scheme": "dusk"}, size=(60, 90)) as flyer:
            low, high = self.ends(self.svg(flyer)[0])
            for value, channel in zip(low, (0x17, 0x29, 0x3B)):
                self.assertAlmostEqual(value, channel / 255, places=3)
            for value in high:
                self.assertAlmostEqual(value, 1.0, places=3)

    def test_light_ground_multiplies_the_photo_down_to_black(self):
        with Fixture({"scheme": "bone"}, size=(60, 90)) as flyer:
            low, high = self.ends(self.svg(flyer)[0])
            for value in low:
                self.assertAlmostEqual(value, 0.0, places=3)
            for value, channel in zip(high, (0xEF, 0xE7, 0xDA)):
                self.assertAlmostEqual(value, channel / 255, places=3)

    def test_image_is_clipped_to_its_cell(self):
        with Fixture(size=(60, 90)) as flyer:
            root, _, page = self.svg(flyer)
            image = root.find(f".//{SVG}image")
            self.assertEqual(image.get("clip-path"), "url(#photo)")
            self.assertTrue(image.get("preserveAspectRatio").endswith(" slice"))
            clip = root.find(f".//{SVG}clipPath/{SVG}rect")
            self.assertEqual(float(clip.get("width")), page.image.rect.w)

    def test_every_line_carries_its_measured_width(self):
        with Fixture(size=(60, 90)) as flyer:
            root, _, page = self.svg(flyer)
            texts = root.findall(f".//{SVG}text")
            self.assertEqual(len(texts), len(page.lines))
            for element, line in zip(texts, page.lines):
                self.assertEqual(element.text, line.text)
                self.assertEqual(element.get("lengthAdjust"), "spacing")
                self.assertAlmostEqual(float(element.get("textLength")),
                                       line.width, places=2)

    def test_markup_in_content_is_escaped(self):
        with Fixture({"venue": 'Bar & "Grill" <9>'}, size=(60, 90)) as flyer:
            root, text, _ = self.svg(flyer)
            self.assertIn("&amp;", text)
            venues = [e.text for e in root.findall(f".//{SVG}text")
                      if e.get("data-field") == "venue"]
            self.assertEqual(venues, ['BAR & "GRILL" <9>'])

    def test_rendering_is_byte_identical_across_runs(self):
        with Fixture(size=(60, 90)) as flyer:
            self.assertEqual(render(flyer)[0], render(flyer)[0])

    def test_embedded_photo_round_trips(self):
        with Fixture(size=(60, 90)) as flyer:
            root, _, _ = self.svg(flyer)
            blob = root.find(f".//{SVG}image").get("href").split(",", 1)[1]
            self.assertEqual(base64.b64decode(blob), flyer.image_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
