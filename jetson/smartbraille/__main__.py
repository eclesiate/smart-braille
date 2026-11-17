"""Run the reader from a terminal.

    python -m smartbraille --image page.jpg          # file instead of a camera
    python -m smartbraille --camera 0                # USB camera
    python -m smartbraille --camera 0 --serial /dev/ttyACM0

Keys (then Enter): s scan, n next, b back, p play/pause, q quit.
With --serial, the buttons on the Pico work as well.
"""

import argparse
import select
import sys
import time

from . import capture, display, pipeline
from .paging import Button, Reader

KEYS = {"s": Button.SCAN, "n": Button.NEXT, "b": Button.BACK, "p": Button.PLAY_PAUSE}


class App:
    def __init__(self, camera, displays, reader=None, log=print):
        self.camera = camera
        self.displays = displays
        self.reader = reader or Reader()
        self.log = log
        self.result = None

    def press(self, button, now=None):
        now = time.monotonic() if now is None else now
        self._apply(self.reader.press(button, now))

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        self._apply(self.reader.tick(now))

    def _apply(self, output):
        if output.beep:
            for d in self.displays:
                d.beep(output.beep)
        if output.scan:
            self.result = pipeline.scan(self.camera.capture())
            times = ", ".join(f"{k} {v:.2f} s" for k, v in self.result.timings_s.items())
            self.log(f"[scan: {len(self.result.text)} characters, {times}]")
            self._apply(self.reader.load(self.result.translation.cells))
            return
        if output.window:
            self._show(output.window)

    def _show(self, window):
        if self.result and window.end > window.start:
            index = self.result.translation.source_index
            first, last = index[window.start], index[window.end - 1]
            self.log(f"[{self.reader.index + 1}/{len(self.reader.windows)}] "
                     f"{self.result.translation.text[first:last + 1]!r}")
        for d in self.displays:
            d.show(window.cells)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="smartbraille")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", help="read this image file instead of a camera")
    source.add_argument("--camera", help="camera index or OpenCV pipeline string")
    parser.add_argument("--serial", help="Pico serial device, e.g. /dev/ttyACM0")
    parser.add_argument("--once", action="store_true", help="scan once, print every window, exit")
    args = parser.parse_args(argv)

    if args.image:
        camera = capture.FileCamera(args.image)
    else:
        camera = capture.OpenCVCamera(int(args.camera) if args.camera.isdigit() else args.camera)
    displays = [display.VirtualDisplay()]
    if args.serial:
        displays.append(display.SerialDisplay(display.open_serial(args.serial)))
    app = App(camera, displays)

    if args.once:
        app.press(Button.SCAN)
        for _ in range(len(app.reader.windows) - 1):
            app.press(Button.NEXT)
        return 0

    print("s scan, n next, b back, p play/pause, q quit")
    while True:
        ready, _, _ = select.select([sys.stdin], [], [], 0.05)
        if ready:
            key = sys.stdin.readline().strip().lower()
            if key == "q":
                return 0
            if key in KEYS:
                app.press(KEYS[key])
        for d in displays:
            for button in d.poll_buttons():
                app.press(button)
        app.tick()


if __name__ == "__main__":
    sys.exit(main())
