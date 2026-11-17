"""Serial protocol between the Jetson and the Pico.

CLAUDE.md fixes the frame's shape (start byte, 8 cell bytes, checksum, end
byte, ack). The byte values, the checksum rule, the button bytes and the
beep command are choices made here and are listed in jetson/README.md.

Jetson -> Pico, 11 bytes:
    STX (0x02), 8 cell bytes, checksum, ETX (0x03)
    cell byte: bit 0 = dot 1 ... bit 5 = dot 6, bits 6 and 7 zero
    checksum: XOR of the 8 cell bytes

Jetson -> Pico, 2 bytes:
    BEL (0x07), pattern (0..3): sound pattern + 1 short beeps

Pico -> Jetson, single bytes:
    ACK (0x06)  frame accepted and shown
    NAK (0x15)  frame rejected (bad checksum or cell byte) or not shown
    'S' 'B' 'N' 'P'  button pressed: Scan, Back, Next, Play/Pause

The Pico side is firmware/pico/frames.py. test/test_firmware.py runs the
two against each other.
"""

from .paging import Beep, Button

STX = 0x02
ETX = 0x03
ACK = 0x06
BEL = 0x07
NAK = 0x15

# The Pico beeps once by itself on every button press, so "scan started"
# needs no command. Counts are placeholders to tune with a real user.
BEEP_PATTERN = {Beep.READY: 1, Beep.LIMIT: 2, Beep.ERROR: 3}


def encode_beep(beep):
    """Return the bytes to send for a beep, or b'' if none is needed."""
    pattern = BEEP_PATTERN.get(beep)
    return b"" if pattern is None else bytes([BEL, pattern])
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
