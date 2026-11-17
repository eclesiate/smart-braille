"""Braille displays: a text rendering for the monitor and the serial link."""

import time

from . import braille, protocol
from .paging import Button


def render(cells):
    """Draw cells as three rows of dots, for the monitor and for debugging."""
    rows = []
    for left, right in ((1, 4), (2, 5), (3, 6)):
        row = []
        for cell in cells:
            dots = braille.to_dots(cell)
            row.append(("o" if left in dots else ".") + ("o" if right in dots else "."))
        rows.append(" ".join(row))
    return "\n".join(rows)


class VirtualDisplay:
    """Prints each window. Stands in for the hardware."""

    def __init__(self, out=print):
        self.out = out
        self.shown = []

    def show(self, cells):
        self.shown = list(cells)
        self.out(braille.to_unicode(cells))
        self.out(render(cells))

    def poll_buttons(self):
        return []


class SerialDisplay:
    """Sends frames to the Pico and collects button presses from it.

    `port` is an open pyserial port (or anything with write, read and
    in_waiting). Not yet tested against real firmware.
    """

    def __init__(self, port, ack_timeout_s=1.5, retries=2):
        self.port = port
        self.ack_timeout_s = ack_timeout_s
        self.retries = retries
        self._buttons = []

    def show(self, cells):
        frame = protocol.encode_frame(cells)
        for _ in range(self.retries + 1):
            self.port.write(frame)
            if self._wait_ack():
                return
        raise TimeoutError("the display did not acknowledge the frame")

    def poll_buttons(self):
        """Return buttons pressed since the last call."""
        while self.port.in_waiting:
            self._handle(self.port.read(1))
        pressed, self._buttons = self._buttons, []
        return pressed

    def _wait_ack(self):
        deadline = time.monotonic() + self.ack_timeout_s
        while time.monotonic() < deadline:
            reply = self._handle(self.port.read(1))
            if reply == "ack":
                return True
            if reply == "nak":
                return False
        return False

    def _handle(self, data):
        """Process one byte. Buttons are queued; returns 'ack', 'nak' or None."""
        reply = protocol.parse_reply(data[0]) if data else None
        if isinstance(reply, Button):
            self._buttons.append(reply)
            return None
        return reply


def open_serial(device, baudrate=115200):
    """Open the Pico's USB serial port with a short read timeout."""
    import serial

    return serial.Serial(device, baudrate=baudrate, timeout=0.05)
