"""Serial protocol, Pico side. Mirrors jetson/smartbraille/protocol.py.

Jetson -> Pico:
    frame: STX (0x02), 8 cell bytes (0..63), XOR checksum, ETX (0x03)
    beep:  BEL (0x07), pattern byte (0..3)
Pico -> Jetson, single bytes:
    ACK (0x06), NAK (0x15), or a button: 'S' 'B' 'N' 'P'

Runs on MicroPython and CPython. No imports.
"""

STX = 0x02
ETX = 0x03
ACK = 0x06
BEL = 0x07
NAK = 0x15
CELLS = 8

_IDLE = 0
_FRAME = 1
_BEEP = 2


class Parser:
    """Feed bytes one at a time. Returns an event tuple or None.

    Events: ("frame", [8 cells]), ("bad",) for a frame that failed a check,
    ("beep", pattern).
    """

    def __init__(self):
        self._state = _IDLE
        self._buf = []

    def feed(self, byte):
        if self._state == _IDLE:
            if byte == STX:
                self._state = _FRAME
                self._buf = []
            elif byte == BEL:
                self._state = _BEEP
            return None
        if self._state == _BEEP:
            self._state = _IDLE
            return ("beep", byte & 0x03)
        # In a frame: 8 cells, checksum, ETX.
        self._buf.append(byte)
        if len(self._buf) < CELLS + 2:
            return None
        self._state = _IDLE
        cells = self._buf[:CELLS]
        check = 0
        for c in cells:
            check ^= c
        ok = (
            self._buf[CELLS + 1] == ETX
            and self._buf[CELLS] == check
            and max(cells) < 64
        )
        return ("frame", cells) if ok else ("bad",)
