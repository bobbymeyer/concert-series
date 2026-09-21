"""Length parsing. Everything in the layout engine is in points (1/72 in)."""

import re

_UNITS = {
    "pt": 1.0,
    "px": 1.0,        # SVG user unit == pt here, since the viewBox is in points
    "in": 72.0,
    "mm": 72.0 / 25.4,
    "cm": 72.0 / 2.54,
    "pc": 12.0,
}

_LENGTH = re.compile(r"^\s*(-?\d*\.?\d+)\s*([a-z%]*)\s*$", re.I)


def to_pt(value, em=None):
    """Parse a length into points.

    Accepts numbers (already points), "8.5in", "12pt", "24", "-0.02em" and
    percentages. ``em`` supplies the reference size for em/% values.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _LENGTH.match(str(value))
    if not m:
        raise ValueError(f"cannot parse length: {value!r}")
    n, unit = float(m.group(1)), m.group(2).lower()
    if unit in ("", "pt", "px"):
        return n * _UNITS.get(unit or "pt", 1.0)
    if unit in ("em", "%"):
        if em is None:
            raise ValueError(f"{value!r} needs a font size for reference")
        return n * em if unit == "em" else n / 100.0 * em
    if unit in _UNITS:
        return n * _UNITS[unit]
    raise ValueError(f"unknown unit {unit!r} in {value!r}")


def fmt(n, places=3):
    """Format a number for SVG output without trailing zero noise."""
    s = f"{float(n):.{places}f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"
