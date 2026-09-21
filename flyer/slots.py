"""Slot resolution: take the value from the yaml, or pick one deterministically.

Every unspecified slot is drawn from its own stream, seeded by the flyer's
identity and the slot's name. Pinning one slot in yaml therefore never shifts
what another slot picks, and the same content always renders the same flyer.
"""

import hashlib
import random

RANDOM = {"random", "any", "auto?"}

# start / middle / end are the canonical values; the rest are conveniences.
ALIGN_ALIASES = {
    "start": "start", "top": "start", "left": "start", "begin": "start",
    "middle": "middle", "center": "middle", "centre": "middle", "mid": "middle",
    "end": "end", "bottom": "end", "right": "end",
}

ALIGNMENTS = ("start", "middle", "end")


def normalize_align(value, slot="alignment"):
    """Map top/bottom/left/right/center onto start/middle/end."""
    if value is None:
        return None
    key = str(value).strip().lower()
    if key in RANDOM:
        return "random"
    if key not in ALIGN_ALIASES:
        raise ValueError(
            f"{slot}: {value!r} is not an alignment "
            f"(start/middle/end, or top/bottom/left/right/center)"
        )
    return ALIGN_ALIASES[key]


def is_random(value):
    return value is None or str(value).strip().lower() in RANDOM


class Chooser:
    """Per-slot deterministic picker."""

    def __init__(self, identity):
        self.identity = str(identity)

    def _rng(self, slot):
        digest = hashlib.sha256(f"{self.identity}\x00{slot}".encode()).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    def pick(self, slot, value, options):
        """Return ``value`` if it is set, else a stable pick from ``options``."""
        if not is_random(value):
            return value
        if not options:
            raise ValueError(f"{slot}: nothing to pick from")
        return self._rng(slot).choice(list(options))

    def pick_align(self, slot, value, options=ALIGNMENTS):
        return self.pick(slot, normalize_align(value, slot), options)
