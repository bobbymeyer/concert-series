"""A deterministic flyer generator: yaml and an image in, print-ready SVG out."""

from .config import Design, Flyer, discover
from .render import render

__all__ = ["Design", "Flyer", "discover", "render"]
__version__ = "0.1.0"
