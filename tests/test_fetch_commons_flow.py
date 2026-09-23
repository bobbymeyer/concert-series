"""The fetcher's whole path -- search, filter, download, credits -- on a stub.

The real Commons is not reachable from every environment, so the network is
replaced with a recorded-shaped response. This is what proves the first real
run will not be the first time the code has been executed.
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fetch_commons                                  # noqa: E402
from make_placeholder import png, scene                # noqa: E402

PHOTO_URL = "https://upload.wikimedia.org/thumb/Example.jpg"

def page(title, url, licence, artist, licence_url=""):
    return {"title": title, "imageinfo": [{
        "thumburl": url,
        "descriptionurl": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
        "extmetadata": {"LicenseShortName": {"value": licence},
                        "LicenseUrl": {"value": licence_url},
                        "Artist": {"value": artist}}}]}


# Shaped like a real commons query=generator=search response, and carrying the
# two kinds of result a real search returns alongside the one you want: a photo
# of the right person under the wrong licence, and a freely licensed photo of
# something else entirely that merely shares a word.
SEARCH = {"query": {"pages": [
    page("File:Ennio Morricone Cannes 2007.jpg", PHOTO_URL, "CC BY-SA 4.0",
         '<a href="/wiki/User:P">Some Photographer</a>',
         "https://creativecommons.org/licenses/by-sa/4.0"),
    page("File:Ennio Morricone portrait.jpg",
         "https://upload.wikimedia.org/thumb/NoLicence.jpg", "CC BY-NC 3.0",
         "Someone Else"),
    page("File:Moscow trolleybus MTRZ-5279.jpg",
         "https://upload.wikimedia.org/thumb/NotHim.jpg", "CC BY-SA 4.0",
         "Artyom Svetlov"),
]}}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def fake_urlopen(request, timeout=None):
    url = request.full_url if hasattr(request, "full_url") else str(request)
    if url.startswith(fetch_commons.API):
        return FakeResponse(json.dumps(SEARCH).encode())
    if url == PHOTO_URL:
        return FakeResponse(JPEG_BYTES)
    raise AssertionError(f"unexpected request: {url}")


JPEG_BYTES = b""


def setUpModule():
    global JPEG_BYTES
    tmp = Path(tempfile.mkdtemp()) / "x.png"
    png(tmp, 24, 32, scene(24, 32, "stub"))
    JPEG_BYTES = tmp.read_bytes()


class TestFetchFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.content = self.tmp / "content"
        folder = self.content / "ennio-morricone"
        folder.mkdir(parents=True)
        (folder / "flyer.yaml").write_text(
            "performer: Ennio Morricone\nvenue: Roulette\n", encoding="utf-8")
        png(folder / "photo.png", 24, 32, scene(24, 32, "placeholder"))
        self.folder = folder
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_tool(self, *args):
        with mock.patch.object(fetch_commons.urllib.request, "urlopen", fake_urlopen), \
                mock.patch.object(fetch_commons, "PAUSE", 0.0):
            return fetch_commons.main(["--content", str(self.content), *args])

    def test_a_dry_run_changes_nothing(self):
        self.assertEqual(self.run_tool(), 0)
        self.assertTrue((self.folder / "photo.png").exists())
        self.assertFalse((self.content / "PHOTO-CREDITS.md").exists())

    def test_write_downloads_and_replaces_the_placeholder(self):
        self.assertEqual(self.run_tool("--write"), 0)
        self.assertTrue((self.folder / "photo.jpg").exists())
        self.assertEqual((self.folder / "photo.jpg").read_bytes(), JPEG_BYTES)
        # One photo per folder, or the flyer cannot tell which to use.
        self.assertEqual(sorted(p.name for p in self.folder.glob("photo.*")),
                         ["photo.jpg"])

    def test_the_restricted_candidate_is_never_taken(self):
        self.run_tool("--write")
        credits = (self.content / "PHOTO-CREDITS.md").read_text()
        self.assertIn("Ennio_Morricone_Cannes_2007", credits)
        self.assertNotIn("Someone Else", credits)         # the CC BY-NC one
        self.assertNotIn("NC", credits)

    def test_a_free_photo_of_something_else_is_never_taken(self):
        """The search returns whatever shares a word; the name gate stops it."""
        self.run_tool("--write")
        credits = (self.content / "PHOTO-CREDITS.md").read_text()
        self.assertNotIn("trolleybus", credits.lower())
        self.assertNotIn("Artyom", credits)
        self.assertEqual((self.folder / "photo.jpg").read_bytes(), JPEG_BYTES)

    def test_credits_carry_what_the_licence_requires(self):
        self.run_tool("--write")
        credits = (self.content / "PHOTO-CREDITS.md").read_text()
        for needed in ("Ennio Morricone", "Some Photographer", "CC BY-SA 4.0",
                       "creativecommons.org/licenses/by-sa/4.0",
                       "commons.wikimedia.org/wiki/File:Ennio_Morricone"):
            self.assertIn(needed, credits)
        self.assertNotIn("<a href", credits)          # markup stripped

    def test_fetching_one_flyer_keeps_the_others_credits(self):
        """Per-slug runs are the normal way to work, and used to clobber."""
        other = self.content / "piero-piccioni"
        other.mkdir()
        (other / "flyer.yaml").write_text("performer: Piero Piccioni\n",
                                          encoding="utf-8")
        (other / "photo-credit.yaml").write_text(
            "performer: Piero Piccioni\nfile: photo.jpg\n"
            "author: Someone\nlicence: Public domain\n"
            "descriptionurl: https://commons.wikimedia.org/wiki/File:Piccioni.jpg\n",
            encoding="utf-8")

        self.run_tool("ennio-morricone", "--write")

        credits = (self.content / "PHOTO-CREDITS.md").read_text()
        self.assertIn("Ennio Morricone", credits)
        self.assertIn("Piero Piccioni", credits)      # not dropped by this run

    def test_each_photo_carries_its_own_credit(self):
        self.run_tool("--write")
        credit = self.folder / "photo-credit.yaml"
        self.assertTrue(credit.exists())
        import yaml as _yaml
        row = _yaml.safe_load(credit.read_text())
        self.assertEqual(row["author"], "Some Photographer")
        self.assertEqual(row["licence"], "CC BY-SA 4.0")
        self.assertEqual(row["file"], "photo.jpg")

    def test_the_downloaded_photo_is_a_photo_the_layout_can_read(self):
        from flyer.imageinfo import probe
        self.run_tool("--write")
        width, height, mime = probe(self.folder / "photo.jpg")
        self.assertEqual((width, height), (24, 32))
        self.assertEqual(mime, "image/png")           # stub bytes are a PNG


if __name__ == "__main__":
    unittest.main()
