"""Duotone schemes: every flyer is set in two colours plus an optional accent.

A style names a role (``ink``, ``paper``, ``accent``) rather than a colour, so
the same typography works in any scheme. The photo is desaturated and ramped
between the scheme's shadow and highlight, which is exactly a multiply blend
over the flat background (see ``duotone`` below).
"""

import re

_HEX = re.compile(r"^#?([0-9a-f]{3}|[0-9a-f]{6})$", re.I)


def parse(value):
    """Return (r, g, b) floats in 0..1 for a hex colour."""
    m = _HEX.match(str(value).strip())
    if not m:
        raise ValueError(f"not a hex colour: {value!r}")
    digits = m.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return tuple(int(digits[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def is_color(value):
    return isinstance(value, str) and bool(_HEX.match(value.strip()))


def normalize(value):
    value = str(value).strip()
    return value if value.startswith("#") else f"#{value}"


def luminance(value):
    """WCAG relative luminance."""
    def channel(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in parse(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG contrast ratio between two colours (1..21)."""
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + 0.05) / (lo + 0.05)


class Scheme:
    """One duotone: a background, an ink, and what the photo ramps between."""

    def __init__(self, data, palette=None):
        palette = palette or {}
        self.data = dict(data or {})
        self.name = self.data.get("name")
        self.background = normalize(self.data["background"])
        ink = self.data.get("ink")
        if ink is None:
            # No ink given: use whichever of the palette's two neutrals reads.
            candidates = [palette.get("ink", "#111111"), palette.get("paper", "#FFFFFF")]
            ink = max(candidates, key=lambda c: contrast(c, self.background))
        self.ink = normalize(ink)
        self.accent = self.data.get("accent")
        self.extras = {k: v for k, v in palette.items()
                       if k not in ("schemes", "backgrounds") and is_color(str(v))}

    def resolve(self, role, minimum=2.5):
        """Resolve a role name or literal hex into a colour that stays readable."""
        if role is None:
            return self.ink
        if is_color(role):
            return normalize(role)
        key = str(role).strip().lower()
        if key in ("ink", "text", "auto"):
            return self.ink
        if key in ("background", "paper", "bg"):
            return self.background
        value = self.accent if key == "accent" else None
        value = self.extras.get(key) if value is None else value
        if value is None:
            if key == "accent":
                return self.ink          # a scheme without an accent just uses ink
            raise ValueError(f"no colour named {key!r} in the scheme or palette")
        value = normalize(value)
        # An accent that disappears into the background falls back to ink.
        return value if contrast(value, self.background) >= minimum else self.ink

    def duotone(self, settings=None):
        """Shadow/highlight ends of the photo ramp.

        By default the photo ramps between the scheme's own two colours, dark
        end first, so it stays legible on light and dark backgrounds alike. On
        a light scheme that is the multiply blend of the desaturated photo over
        the background, tinted into the ink; ``shadow: "#000000"`` makes it a
        literal multiply, and either end can be set to any role or hex.
        """
        settings = settings or {}
        dark, light = sorted((self.ink, self.background), key=luminance)
        shadow = settings.get("shadow")
        highlight = settings.get("highlight")
        shadow = dark if shadow in (None, "auto") else self.resolve(shadow, minimum=0)
        highlight = light if highlight in (None, "auto") else self.resolve(highlight, minimum=0)
        return shadow, highlight


def schemes_from(palette):
    """Normalise ``palette`` into a list of schemes.

    Accepts an explicit ``schemes:`` list, or the ``backgrounds:`` shorthand
    where the ink is chosen for contrast.
    """
    palette = palette or {}
    listed = palette.get("schemes")
    if listed:
        return [Scheme(s, palette) for s in listed]
    backgrounds = palette.get("backgrounds") or [palette.get("paper", "#FFFFFF")]
    return [Scheme({"background": bg, "accent": palette.get("accent")}, palette)
            for bg in backgrounds]
