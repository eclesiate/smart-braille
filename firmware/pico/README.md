# firmware/pico

**Owner:** David (Pico firmware)

MicroPython: serial protocol and coil driver, with hardware watchdog. Pulse length is hard-capped at the measured value. Never drive two cells at once.

## Status (Nov 17, 2026)

The logic is written and tested under pytest against a fake hardware layer, including the Jetson's serial code talking to it. Every file compiles with `mpy-cross` 1.29. **Nothing has run on a Pico.** `main.py`, the only file that touches pins, is untested.

The firmware matches the shared-bus board in `hardware/pcb/README.md`, which has no schematic yet.

## Files

| File | Does |
|---|---|
| `config.py` | Every setting, including the pulse length. Edit this, not the code. |
| `dotmap.py` | Dot-to-bit mapping for the 74HC595 bus. |
| `frames.py` | Parses bytes from the Jetson. |
| `driver.py` | The pulse sequence and the coil-safety rules. |
| `buttons.py` | Debouncing. |
| `controller.py` | Connects protocol, driver, buttons and buzzer. |
| `main.py` | Pins, SPI, watchdog and the main loop. |

## Coil safety

- `PULSE_MS` and `PULSE_CAP_MS` in `config.py` are `None`. Until both are set from `hardware/cell/MEASUREMENTS.md`, the firmware runs in dry-run: it acknowledges frames and tracks state but never wakes a driver.
- A pulse longer than the cap is refused.
- One cell at a time. The decoder address only changes while the cell enable is low.
- The bus is high-Z except during a pulse.
- Any error inside a pulse returns the outputs to idle before it is reported.
- If MicroPython hangs mid-pulse, the coil stays on until the watchdog resets the Pico (`WDT_TIMEOUT_MS`, 1000 ms). The hardware timeout planned for the PCB is what shortens that.

## Assumptions

- After power-up the dot positions are unknown, so the first frame drives all six dots of every cell. Later frames drive only dots that changed.
- Up to 6 dots of one cell are pulsed together. `MAX_DOTS_PER_PULSE` lowers that if the supply sags.
- A driver fault (nFAULT low at the end of a pulse) fails the frame with a NAK, and that cell is fully re-driven next time.
- The Pico beeps once on its own for every button press. The Jetson can ask for 2, 3 or 4 beeps (ready, end of text, no text found).
- The USB serial port carries only protocol bytes. Debug text goes to UART0 on GP0.
- `micropython.kbd_intr(-1)` is required: the frame's end byte, 0x03, is otherwise read as Ctrl-C.

## Install (when a Pico is available)

Flash MicroPython yourself, then from the repo root:

```
mpremote cp firmware/pico/*.py :
mpremote reset
```
