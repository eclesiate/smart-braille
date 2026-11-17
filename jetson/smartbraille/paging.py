"""Split braille cells into display windows and step through them.

The reader is a pure state machine: it takes button events and the current
time and returns what to show and whether to beep. It does not touch the
camera, the display or the clock, so it can be tested without hardware.
"""

from dataclasses import dataclass
from enum import Enum

WIDTH = 8
BLANK = 0


@dataclass
class Window:
    cells: list[int]  # always exactly `width` cells, padded with blanks
    start: int  # index of the first cell in the full cell list
    end: int  # one past the last cell shown


def paginate(cells, width=WIDTH):
    """Split cells into windows, breaking at blanks when a word fits.

    A word longer than the display is split across windows. Blanks at the
    start of a window are dropped.
    """
    windows = []
    i, n = 0, len(cells)
    while i < n:
        while i < n and cells[i] == BLANK:
            i += 1
        if i >= n:
            break
        end = min(i + width, n)
        if end < n and cells[end] != BLANK:
            # The window would end mid-word: back up to the last blank.
            cut = end
            while cut > i and cells[cut - 1] != BLANK:
                cut -= 1
            if cut > i:
                end = cut
        shown_end = end
        while shown_end > i and cells[shown_end - 1] == BLANK:
            shown_end -= 1
        shown = list(cells[i:shown_end])
        windows.append(Window(shown + [BLANK] * (width - len(shown)), i, shown_end))
        i = end
    return windows


class Button(Enum):
    SCAN = "S"
    BACK = "B"
    NEXT = "N"
    PLAY_PAUSE = "P"


class Beep(Enum):
    OK = "ok"  # scan started
    READY = "ready"  # scan finished, first window shown
    LIMIT = "limit"  # no more text in that direction
    ERROR = "error"  # scan found no text


@dataclass
class Output:
    window: Window | None = None  # show this window, if not None
    beep: Beep | None = None
    scan: bool = False  # caller must run a scan and call load()


class Reader:
    """Paging state: which windows exist, which one is shown, auto-advance."""

    def __init__(self, width=WIDTH, auto_advance_s=3.0):
        self.width = width
        self.auto_advance_s = auto_advance_s
        self.windows = []
        self.index = 0
        self.playing = False
        self._next_advance = None

    @property
    def current(self):
        return self.windows[self.index] if self.windows else None

    def load(self, cells):
        """Install the result of a scan. Returns what to show."""
        self.windows = paginate(cells, self.width)
        self.index = 0
        self.playing = False
        self._next_advance = None
        if not self.windows:
            return Output(window=self._blank(), beep=Beep.ERROR)
        return Output(window=self.current, beep=Beep.READY)

    def press(self, button, now):
        if button is Button.SCAN:
            self.playing = False
            self._next_advance = None
            return Output(beep=Beep.OK, scan=True)
        if not self.windows:
            return Output(beep=Beep.LIMIT)
        if button is Button.NEXT:
            return self._step(+1, now)
        if button is Button.BACK:
            return self._step(-1, now)
        if button is Button.PLAY_PAUSE:
            self.playing = not self.playing
            self._next_advance = now + self.auto_advance_s if self.playing else None
            return Output()
        raise ValueError(button)

    def tick(self, now):
        """Call regularly. Advances one window when auto-advance is due."""
        if not self.playing or self._next_advance is None or now < self._next_advance:
            return Output()
        if self.index + 1 >= len(self.windows):
            self.playing = False
            self._next_advance = None
            return Output(beep=Beep.LIMIT)
        return self._step(+1, now)

    def _step(self, delta, now):
        target = self.index + delta
        if not 0 <= target < len(self.windows):
            return Output(beep=Beep.LIMIT)
        self.index = target
        if self.playing:
            self._next_advance = now + self.auto_advance_s
        return Output(window=self.current)

    def _blank(self):
        return Window([BLANK] * self.width, 0, 0)
