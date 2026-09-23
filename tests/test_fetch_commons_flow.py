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

# Shaped like a real commons query=generator=search response.
SEARCH = {"query": {"pages": [
    {"title": "File:Free photo.jpg",
     "imageinfo": [{"thumburl": PHOTO_URL,
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Free_photo.jpg",
                    "extmetadata": {
                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                        "Artist": {"value": '<a href="/wiki/User:P">Some Photographer</a>'}}}]},
    {"title": "File:Restricted photo.jpg",
     "imageinfo": [{"thumburl": "https://upload.wikimedia.org/thumb/No.jpg",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:No.jpg",
                    "extmetadata": {
                        "LicenseShortName": {"value": "CC BY-NC 3.0"},
                        "Artist": {"value": "Someone Else"}}}]},
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
        with mock.patch.object(fetch_commons.urllib.request, "urlopen", fake_urlopen):
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
        self.assertIn("File:Free_photo.jpg", credits)     # the free candidate
        self.assertNotIn("File:No.jpg", credits)          # the CC BY-NC one
        self.assertNotIn("Someone Else", credits)
        self.assertNotIn("NC", credits)

    def test_credits_carry_what_the_licence_requires(self):
        self.run_tool("--write")
        credits = (self.content / "PHOTO-CREDITS.md").read_text()
        for needed in ("Ennio Morricone", "Some Photographer", "CC BY-SA 4.0",
                       "creativecommons.org/licenses/by-sa/4.0",
                       "commons.wikimedia.org/wiki/File:Free_photo.jpg"):
            self.assertIn(needed, credits)
        self.assertNotIn("<a href", credits)          # markup stripped

    def test_the_downloaded_photo_is_a_photo_the_layout_can_read(self):
        from flyer.imageinfo import probe
        self.run_tool("--write")
        width, height, mime = probe(self.folder / "photo.jpg")
        self.assertEqual((width, height), (24, 32))
        self.assertEqual(mime, "image/png")           # stub bytes are a PNG


if __name__ == "__main__":
    unittest.main()
