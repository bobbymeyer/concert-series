"""Shared fixtures: a throwaway content folder with a real (tiny) image."""

import shutil
import tempfile
from pathlib import Path

import yaml

from flyer.config import Design, Flyer

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design" / "design.yaml"

BASE = {
    "performer": "Cardinal Wax",
    "venue": "The Bell House",
    "date": "Saturday, October 3",
    "time": "8:00 PM",
    "cost": "$22 advance / $25 door",
    "details": "Doors at seven. All ages until ten, 21+ after.",
}


def tiny_png(path, width, height):
    """A small valid PNG, so tests exercise the real image probe."""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from make_placeholder import png, scene
    png(path, width, height, scene(width, height, path.name))


class Fixture:
    """A temporary content folder, used as a context manager."""

    def __init__(self, data=None, size=(60, 80), slug="test-flyer"):
        self.data = dict(BASE, **(data or {}))
        self.size = size
        self.slug = slug

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp())
        folder = self.tmp / self.slug
        folder.mkdir()
        tiny_png(folder / "photo.png", *self.size)
        (folder / "flyer.yaml").write_text(yaml.safe_dump(self.data), encoding="utf-8")
        return Flyer(folder, Design.load(DESIGN))

    def __exit__(self, *exc):
        shutil.rmtree(self.tmp, ignore_errors=True)
