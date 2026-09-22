"""Loading and merging of design.yaml and a flyer's content yaml."""

import copy
from pathlib import Path

import yaml

from .imageinfo import probe
from .units import to_pt

FIELDS = ("performer", ("venue", "address"), ("date", "time"), "cost", "details")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")


class ConfigError(Exception):
    pass


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return data


def deep_merge(base, override):
    """Recursively merge ``override`` onto a copy of ``base``."""
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


class Design:
    """The shared design: page geometry, palette, typography, font files."""

    def __init__(self, root, data):
        self.root = Path(root)
        self.data = data
        page = data.get("page", {})
        self.width = to_pt(page.get("width", "8.5in"))
        self.height = to_pt(page.get("height", "11in"))
        self.margin = to_pt(page.get("margin", "0.5in"))
        self.gutter = to_pt(page.get("gutter", self.margin))
        self.typography = data.get("typography", {})
        self.palette = data.get("palette", {})
        self.formats = data.get("formats", {})
        self.fonts_dir = self.root / data.get("fonts", {}).get("dir", "fonts")

    @classmethod
    def load(cls, path):
        path = Path(path)
        return cls(path.parent, load_yaml(path))

    def field_style(self, field):
        fields = self.typography.get("fields", {})
        base = self.typography.get("defaults", {})
        return deep_merge(base, fields.get(field, {}))

    @property
    def order(self):
        return list(self.typography.get("order", FIELDS))

    def font_file(self, weight):
        """Path to the static instance closest to ``weight``."""
        named = self.data.get("fonts", {}).get("weights", {})
        if str(weight) in {str(k) for k in named}:
            key = next(k for k in named if str(k) == str(weight))
            return self.fonts_dir / named[key]
        if not named:
            raise ConfigError("design.yaml: fonts.weights is empty")
        nearest = min(named, key=lambda w: abs(int(w) - int(weight)))
        return self.fonts_dir / named[nearest]


class Flyer:
    """One content folder: its yaml, its image, and the design it inherits."""

    def __init__(self, folder, design):
        self.folder = Path(folder)
        self.slug = self.folder.name
        self.design = design
        self.data = load_yaml(self._content_file())
        self.image_path = self._find_image()
        self.image_width, self.image_height, self.image_mime = probe(self.image_path)
        # A flyer may override any part of the design in place.
        # A flyer may override any part of the design in place. `image:` is
        # skipped when it is just a filename rather than a block of settings.
        self.overrides = {
            key: self.data[key]
            for key in ("page", "typography", "palette", "formats", "grid", "image", "fonts")
            if isinstance(self.data.get(key), dict)
        }

    @staticmethod
    def _content_file_in(folder):
        for name in ("flyer.yaml", "flyer.yml", "content.yaml", "content.yml"):
            candidate = Path(folder) / name
            if candidate.exists():
                return candidate
        raise ConfigError(f"{folder}: no flyer.yaml")

    def _content_file(self):
        return self._content_file_in(self.folder)

    @property
    def series(self):
        """The flyers this one is published alongside."""
        return series(self.folder.parent)

    def _find_image(self):
        declared = self.data.get("image")
        if isinstance(declared, dict):
            declared = declared.get("file")
        if declared:
            path = self.folder / declared
            if not path.exists():
                raise ConfigError(f"{self.folder}: image {declared!r} not found")
            return path
        found = sorted(
            p for p in self.folder.iterdir()
            if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file()
        )
        if not found:
            raise ConfigError(f"{self.folder}: no image file")
        if len(found) > 1:
            raise ConfigError(
                f"{self.folder}: {len(found)} images found "
                f"({', '.join(p.name for p in found)}); name one with `image:`"
            )
        return found[0]

    @property
    def orientation(self):
        if self.image_width > self.image_height:
            return "landscape"
        if self.image_width < self.image_height:
            return "portrait"
        return "square"

    def setting(self, section, key, default=None):
        """Look a key up in the flyer's yaml, then the design's."""
        local = self.data.get(section)
        if isinstance(local, dict) and key in local:
            return local[key]
        shared = self.design.data.get(section)
        if isinstance(shared, dict) and key in shared:
            return shared[key]
        return default


def discover(content_root):
    """Every content folder that holds a flyer yaml, in stable order."""
    root = Path(content_root)
    if not root.exists():
        return []
    return sorted(
        p for p in root.iterdir()
        if p.is_dir() and any((p / n).exists() for n in ("flyer.yaml", "flyer.yml"))
    )


_SERIES = {}


def series(content_root):
    """The run of flyers in a content folder, as (slug, pinned scheme) pairs.

    A flyer's ground colour can depend on where it falls in the series, so the
    siblings are read once per run. The cache is keyed on the folder's contents
    and their timestamps, so an edit mid-run is still picked up.
    """
    folders = discover(content_root)
    key = (str(Path(content_root).resolve()),
           tuple((f.name, f.stat().st_mtime_ns) for f in folders))
    if key not in _SERIES:
        rows = []
        for folder in folders:
            try:
                data = load_yaml(Flyer._content_file_in(folder))
            except (ConfigError, OSError, yaml.YAMLError):
                data = {}
            pinned = data.get("scheme")
            rows.append((folder.name, pinned if isinstance(pinned, str) else None))
        _SERIES[key] = rows
    return _SERIES[key]
