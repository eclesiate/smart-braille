"""Serial protocol between the Jetson and the Pico.

PROPOSAL, to be agreed with whoever writes the Pico firmware. CLAUDE.md
fixes the shape (start byte, 8 cell bytes, checksum, end byte, ack). The
byte values, the checksum rule and the button bytes below are choices made
here and are listed in jetson/README.md.

Jetson -> Pico, 11 bytes:
    STX (0x02), 8 cell bytes, checksum, ETX (0x03)
    cell byte: bit 0 = dot 1 ... bit 5 = dot 6, bits 6 and 7 zero
    checksum: XOR of the 8 cell bytes

Pico -> Jetson, single bytes:
    ACK (0x06)  frame accepted and shown
    NAK (0x15)  frame rejected (bad length, checksum or cell byte)
    'S' 'B' 'N' 'P'  button pressed: Scan, Back, Next, Play/Pause
"""

from .paging import Button

STX = 0x02
ETX = 0x03
ACK = 0x06
NAK = 0x15
CELLS = 8
FRAME_LEN = CELLS + 3

_BUTTONS = {ord(b.value): b for b in Button}


def checksum(cells):
    value = 0
    for c in cells:
        value ^= c
    return value


def encode_frame(cells):
    cells = list(cells)
    if len(cells) != CELLS:
        raise ValueError(f"a frame needs exactly {CELLS} cells")
    if any(not 0 <= c < 64 for c in cells):
        raise ValueError("cell bytes must be 0..63")
    return bytes([STX, *cells, checksum(cells), ETX])


def decode_frame(frame):
    """Return the 8 cells, or raise ValueError. The Pico does the same check."""
    if len(frame) != FRAME_LEN or frame[0] != STX or frame[-1] != ETX:
        raise ValueError("bad framing")
    cells = list(frame[1 : 1 + CELLS])
    if any(c >= 64 for c in cells):
        raise ValueError("bad cell byte")
    if checksum(cells) != frame[1 + CELLS]:
        raise ValueError("bad checksum")
    return cells


def parse_reply(byte):
    """Classify one byte from the Pico: 'ack', 'nak', a Button, or None."""
    if byte == ACK:
        return "ack"
    if byte == NAK:
        return "nak"
    return _BUTTONS.get(byte)
