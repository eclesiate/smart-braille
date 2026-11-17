"""Text to braille cells with liblouis.

A cell is an int 0..63: bit 0 is dot 1 ... bit 5 is dot 6. This matches
the Unicode braille block (U+2800 + cell) and the driver board's cell byte.
"""

from dataclasses import dataclass

import louis

UNCONTRACTED_UEB = "en-ueb-g1.ctb"
BRAILLE_BASE = 0x2800
BLANK = 0


@dataclass
class Translation:
    text: str  # the normalised source text that was translated
    cells: list[int]
    source_index: list[int]  # for each cell, index into `text`


def normalize(text):
    """Collapse all whitespace runs (including line breaks) to single spaces."""
    return " ".join(text.split())


def translate(text, table=UNCONTRACTED_UEB):
    """Translate text to cells. One character can become several cells."""
    source = normalize(text)
    if not source:
        return Translation("", [], [])
    braille, cell_to_source, _, _ = louis.translate(["unicode.dis", table], source)
    cells = []
    for ch in braille:
        code = ord(ch) - BRAILLE_BASE
        # Anything liblouis could not put in a 6-dot cell is shown as a blank.
        cells.append(code if 0 <= code < 64 else BLANK)
    return Translation(source, cells, list(cell_to_source))


def to_unicode(cells):
    return "".join(chr(BRAILLE_BASE + c) for c in cells)


def to_dots(cell):
    """Return the raised dot numbers of a cell, e.g. 0b000101 -> (1, 3)."""
    return tuple(d + 1 for d in range(6) if cell & (1 << d))
