"""Ties the protocol, the cell driver and the buttons together.

Hardware-free: bytes come in through on_byte(), replies and button bytes
go out through the `send` callable, beeps through `beep`.
"""

import frames
from buttons import Debouncer
from driver import DriveError


class Controller:
    def __init__(self, driver, send, beep, button_names, debounce_ms):
        self.driver = driver
        self.send = send
        self.beep = beep
        self.parser = frames.Parser()
        self.buttons = {name: Debouncer(debounce_ms) for name in button_names}
        self.last_error = None

    def on_byte(self, byte):
        event = self.parser.feed(byte)
        if event is None:
            return
        if event[0] == "frame":
            try:
                self.driver.show(event[1])
            except DriveError as exc:
                self.last_error = str(exc)
                self.send(frames.NAK)
            else:
                self.send(frames.ACK)
        elif event[0] == "bad":
            self.send(frames.NAK)
        elif event[0] == "beep":
            self.beep(event[1])

    def on_buttons(self, levels, now_ms):
        """levels: {name: 0 or 1}. Sends the button's byte once per press."""
        for name, level in levels.items():
            if self.buttons[name].sample(level, now_ms):
                self.beep(0)
                self.send(ord(name))
