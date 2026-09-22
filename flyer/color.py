"""Monochrome grounds.

Each flyer is set in one colour. The type is pure ink — black on a light
ground, white on a dark one — and the photo is desaturated and ramped between
the ground and that same ink. On a light ground that ramp runs black to the
ground, which is a multiply; on a dark ground it runs the ground to white,
which is a screen. One decision, made from the ground's luminance, drives both
the type colour and which way the photo goes.
"""

import re

_HEX = re.compile(r"^#?([0-9a-f]{3}|[0-9a-f]{6})$", re.I)

WHITE = "#FFFFFF"
BLACK = "#000000"


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
    return (value if value.startswith("#") else f"#{value}").upper()


def mix(a, b, ratio):
    """``ratio`` of colour ``a`` over colour ``b``."""
    channels = (x * ratio + y * (1 - ratio) for x, y in zip(parse(a), parse(b)))
    return "#" + "".join(f"{round(c * 255):02X}" for c in channels)


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
    """One ground colour, and everything derived from it."""

    def __init__(self, color, name=None, inks=None, tint=0.72, switch_at="auto"):
        inks = inks or {}
        self.name = name
        self.background = normalize(color)
        self.light_ink = normalize(inks.get("light", WHITE))
        self.dark_ink = normalize(inks.get("dark", BLACK))
        self.tint_ratio = float(tint)
        self.is_dark = self._too_dark(switch_at)
        self.ink = self.light_ink if self.is_dark else self.dark_ink
        self.blend = "screen" if self.is_dark else "multiply"

    def _too_dark(self, switch_at):
        """Whether the ground needs white type — and so a screen, not a multiply."""
        if switch_at in (None, "", "auto"):
            return (contrast(self.background, self.light_ink)
                    > contrast(self.background, self.dark_ink))
        return luminance(self.background) < float(switch_at)

    @property
    def tint(self):
        """Ink held back toward the ground, for a second level of hierarchy."""
        return mix(self.ink, self.background, self.tint_ratio)

    def resolve(self, role):
        """Resolve a role name or literal hex. The roles are the whole palette."""
        if role is None:
            return self.ink
        if is_color(role):
            return normalize(role)
        key = str(role).strip().lower()
        if key in ("ink", "text", "auto"):
            return self.ink
        if key in ("ground", "background", "bg", "paper"):
            return self.background
        if key in ("tint", "accent", "muted"):
            return self.tint
        raise ValueError(
            f"{role!r} is not a colour: a monochrome design has ink, ground "
            f"and tint (or give a hex)")

    def ramp(self, settings=None):
        """(shadow, highlight, blend) for the photo.

        A multiply runs the dark ink up to the ground; a screen runs the ground
        up to the light ink. Either end can be overridden, and ``blend`` can be
        forced rather than taken from the ground's luminance.
        """
        settings = settings or {}
        blend = settings.get("blend") or "auto"
        blend = self.blend if str(blend).lower() == "auto" else str(blend).lower()
        if blend == "multiply":
            shadow, highlight = self.dark_ink, self.background
        elif blend == "screen":
            shadow, highlight = self.background, self.light_ink
        else:
            raise ValueError(f"image.treatment.blend: expected multiply/screen/auto, "
                             f"got {blend!r}")
        if settings.get("shadow", "auto") != "auto":
            shadow = self.resolve(settings["shadow"])
        if settings.get("highlight", "auto") != "auto":
            highlight = self.resolve(settings["highlight"])
        return shadow, highlight, blend


def schemes_from(palette):
    """Normalise a palette into its list of monochrome grounds."""
    palette = palette or {}
    inks = palette.get("ink")
    if isinstance(inks, str):
        inks = {"dark": inks}
    common = {
        "inks": inks or {},
        "tint": palette.get("tint", 0.72),
        "switch_at": palette.get("switch_at", "auto"),
    }
    colors = palette.get("colors") or [WHITE]
    items = colors.items() if isinstance(colors, dict) else [(None, c) for c in colors]
    schemes = []
    for name, value in items:
        if isinstance(value, dict):
            name, value = value.get("name", name), value["color"]
        schemes.append(Scheme(value, name=name, **common))
    return schemes
