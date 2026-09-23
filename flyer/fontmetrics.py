"""Minimal TrueType reader: just enough to measure and wrap text exactly.

Only the tables needed for advance widths and the vertical box are parsed
(head, hhea, hmtx, cmap, OS/2), so the whole layout engine stays dependency
free. Kerning and shaping are not applied; the flyer type is set at sizes and
in a family where the difference is visually nil.
"""

import struct
from functools import lru_cache


class FontError(Exception):
    pass


class Font:
    def __init__(self, path):
        self.path = str(path)
        with open(path, "rb") as fh:
            self.data = fh.read()
        self._tables = self._read_directory()
        self.units_per_em = struct.unpack(">H", self._table("head")[18:20])[0]
        self._widths = self._read_hmtx()
        self._cmap = self._read_cmap()
        self.ascent, self.descent, self.line_gap = self._read_vertical()
        self.cap_height, self.x_height = self._read_heights()

    # -- table plumbing -------------------------------------------------
    def _read_directory(self):
        if self.data[:4] not in (b"\x00\x01\x00\x00", b"true", b"ttcf", b"OTTO"):
            raise FontError(f"not a TrueType/OpenType font: {self.path}")
        count = struct.unpack(">H", self.data[4:6])[0]
        tables = {}
        for i in range(count):
            off = 12 + 16 * i
            tag = self.data[off:off + 4].decode("latin1")
            start, length = struct.unpack(">II", self.data[off + 8:off + 16])
            tables[tag] = (start, length)
        return tables

    def _table(self, tag):
        if tag not in self._tables:
            raise FontError(f"{self.path}: missing {tag!r} table")
        start, length = self._tables[tag]
        return self.data[start:start + length]

    # -- metrics --------------------------------------------------------
    def _read_hmtx(self):
        num_h = struct.unpack(">H", self._table("hhea")[34:36])[0]
        hmtx = self._table("hmtx")
        widths = [struct.unpack(">H", hmtx[4 * i:4 * i + 2])[0] for i in range(num_h)]
        if not widths:
            raise FontError(f"{self.path}: empty hmtx")
        return widths

    def _read_vertical(self):
        """Ascent/descent/gap in font units, preferring the OS/2 typo metrics."""
        if "OS/2" in self._tables:
            os2 = self._table("OS/2")
            asc, desc, gap = struct.unpack(">hhh", os2[68:74])
            if asc:
                return asc, desc, gap
        asc, desc, gap = struct.unpack(">hhh", self._table("hhea")[4:10])
        return asc, desc, gap

    def _read_heights(self):
        """Cap and x height in font units, measured from the outlines if absent."""
        if "OS/2" in self._tables:
            os2 = self._table("OS/2")
            version = struct.unpack(">H", os2[0:2])[0]
            if version >= 2 and len(os2) >= 90:
                x_height, cap_height = struct.unpack(">hh", os2[86:90])
                if cap_height:
                    return cap_height, x_height or round(cap_height * 0.72)
        # Fall back to a typical proportion rather than parsing glyph outlines.
        return round(self.ascent * 0.72), round(self.ascent * 0.52)

    def _read_cmap(self):
        cmap = self._table("cmap")
        count = struct.unpack(">H", cmap[2:4])[0]
        best, best_score = None, -1
        for i in range(count):
            pid, eid, off = struct.unpack(">HHI", cmap[4 + 8 * i:12 + 8 * i])
            fmt = struct.unpack(">H", cmap[off:off + 2])[0]
            # Prefer a full-repertoire Unicode subtable over a BMP-only one.
            score = {(3, 10): 4, (0, 4): 4, (0, 6): 4, (3, 1): 3, (0, 3): 3}.get((pid, eid), 0)
            if fmt in (4, 12) and score > best_score:
                best, best_score = (fmt, off), score
        if not best:
            raise FontError(f"{self.path}: no usable cmap subtable")
        fmt, off = best
        return self._cmap4(cmap, off) if fmt == 4 else self._cmap12(cmap, off)

    @staticmethod
    def _cmap4(cmap, off):
        seg2 = struct.unpack(">H", cmap[off + 6:off + 8])[0]
        n = seg2 // 2
        base = off + 14
        ends = struct.unpack(f">{n}H", cmap[base:base + seg2])
        base += seg2 + 2
        starts = struct.unpack(f">{n}H", cmap[base:base + seg2])
        base += seg2
        deltas = struct.unpack(f">{n}h", cmap[base:base + seg2])
        range_off_at = base + seg2
        offsets = struct.unpack(f">{n}H", cmap[range_off_at:range_off_at + seg2])
        table = {}
        for i in range(n):
            for code in range(starts[i], min(ends[i], 0xFFFF) + 1):
                if offsets[i] == 0:
                    gid = (code + deltas[i]) & 0xFFFF
                else:
                    at = range_off_at + 2 * i + offsets[i] + 2 * (code - starts[i])
                    gid = struct.unpack(">H", cmap[at:at + 2])[0]
                    if gid:
                        gid = (gid + deltas[i]) & 0xFFFF
                if gid:
                    table[code] = gid
        return table

    @staticmethod
    def _cmap12(cmap, off):
        n = struct.unpack(">I", cmap[off + 12:off + 16])[0]
        table = {}
        for i in range(n):
            at = off + 16 + 12 * i
            start, end, gid = struct.unpack(">III", cmap[at:at + 12])
            for code in range(start, end + 1):
                table[code] = gid + (code - start)
        return table

    # -- public API -----------------------------------------------------
    def glyph_id(self, char):
        return self._cmap.get(ord(char), 0)

    def advance(self, char):
        """Advance width of a character, in em units (1.0 == font size)."""
        gid = self.glyph_id(char)
        width = self._widths[gid] if gid < len(self._widths) else self._widths[-1]
        return width / self.units_per_em

    @lru_cache(maxsize=8192)
    def measure(self, text, tracking=0.0):
        """Width of ``text`` in em units, with ``tracking`` em added per gap."""
        if not text:
            return 0.0
        total = sum(self.advance(c) for c in text)
        return total + tracking * (len(text) - 1)

    def width(self, text, size, tracking=0.0):
        """Width in points at a given font size."""
        return self.measure(text, tracking) * size

    def em(self, name):
        """A vertical metric as a fraction of the em."""
        return getattr(self, name) / self.units_per_em


_CACHE = {}


def load(path):
    key = str(path)
    if key not in _CACHE:
        _CACHE[key] = Font(path)
    return _CACHE[key]


# Widths are compared with a hair of slack, so a word shrunk to exactly the
# measure is not then broken by a rounding error.
TOLERANCE = 0.01


# A short word carrying the one after it -- "de" in De Angelis, "van" in Van
# Dyke -- belongs to that word, and is wrong left alone at the end of a line.
BIND_MAX = 3


def bind_particles(words, bind_max=BIND_MAX):
    """Join a short leading particle to the word it belongs with.

    Only letters bind: an ampersand or a dash is a connective that reads fine
    at the end of a line, while "DE" alone on one does not.
    """
    if bind_max <= 0:
        return list(words)
    bound = []
    for word in reversed(words):
        if bound and len(word) <= bind_max and word.isalpha():
            bound[-1] = f"{word} {bound[-1]}"
        else:
            bound.append(word)
    bound.reverse()
    return bound


def split_word(font, word, size, max_width, tracking=0.0):
    """Break a word that cannot fit on any line, so it can never overflow."""
    pieces, piece = [], ""
    for char in word:
        if piece and font.width(piece + char, size, tracking) > max_width + TOLERANCE:
            pieces.append(piece)
            piece = char
        else:
            piece += char
    if piece:
        pieces.append(piece)
    return pieces or [word]


def wrap(font, text, size, max_width, tracking=0.0, bind_max=BIND_MAX):
    """Greedy word wrap using real advance widths. Returns a list of lines."""
    lines = []
    for paragraph in str(text).split("\n"):
        words = []
        for word in bind_particles(paragraph.split(), bind_max):
            if font.width(word, size, tracking) <= max_width + TOLERANCE:
                words.append(word)
            elif " " in word:
                # The pair will not fit even so; break it, and check the parts.
                for part in word.split():
                    if font.width(part, size, tracking) <= max_width + TOLERANCE:
                        words.append(part)
                    else:
                        words.extend(
                            split_word(font, part, size, max_width, tracking))
            else:
                # A word wider than the measure is broken rather than run out.
                words.extend(split_word(font, word, size, max_width, tracking))
        if not words:
            lines.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if font.width(candidate, size, tracking) <= max_width + TOLERANCE:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines
