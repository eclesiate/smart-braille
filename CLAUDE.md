# SmartBraille (ECE 498B)

## What it is
Letter-sized page on a matte-black base. USB camera on a ~350 mm mast. Jetson Orin Nano Super captures, dewarps, fixes illumination, runs Tesseract OCR, translates text to braille with liblouis (uncontracted UEB first), and sends 8-cell frames over USB serial. A Raspberry Pi Pico on a custom driver PCB reads 4 buttons (Scan, Back, Next, Play/Pause) and a buzzer, and drives 8 braille cells (6 coils each) through 74HC595 shift registers and DRV8833 H-bridges. The coils run from a separate 5 V supply with an inline fuse.

## Decisions (change only if I say so)
- Pico instead of CH32V003 + CH340C. No USB-C routing, no custom USB.
- Buttons on the Pico, not the Jetson 40-pin header.
- OCR first. The VLM (Qwen2.5-VL via ollama) is an optional mode, time-boxed to 2 days.
- 8 cells, not 40. Minimum acceptable demo is 4 working cells.
- Cells plug into the PCB through a 2x6 header each. The PCB does not depend on cell geometry.
- Display controller is MicroPython, with a hardware watchdog.
- Serial frame: start byte, 8 cell bytes, checksum, end byte. The Pico replies with an ack. Pulse one cell at a time and only dots that changed.

## Open questions. Never guess these, ask me
- Are the cells bistable (coil polarity reversal flips a magnet, no holding current)? Reference design: Hackaday project 191181.
- Measured per-coil resistance, voltage, current and pulse length. Needed to size the drivers, supply and fuse.
- Which camera is installed (the IMX219-120 on MIPI, or a USB autofocus module).
- Symposium date (assumed about March 10, 2027).

## Safety rules for anything that touches coils
- Outputs idle safe: 74HC595 output-enable pulled high and DRV8833 sleep pins pulled low in hardware, so nothing drives a coil before firmware has cleared the registers.
- Firmware hard-caps pulse length at the value measured on the breadboard, and never drives two cells at once.
- Never write or suggest a pulse length or current that isn't backed by a number I gave you.

## PCB workflow
1. Schematic first. Show me a summary of every net and part before layout.
2. Every BOM line gets a JLCPCB/LCSC part number. Check each pinout against the datasheet.
3. ERC must be clean, and DRC clean after layout. Run both with `kicad-cli`.
4. Never place an order. A human reviews the layout in the KiCad GUI first.

## Working style
- Small commits with clear messages.
- Put assumptions in the owning folder's README.md.
- Record real measurements in `docs/` or `hardware/cell/`, with units and the test conditions.
- Tests for OCR accuracy (character error rate) and timing go in `test/`.

## Checkpoints
- Dec 18: one cell survives 500 cycles, or simplify the mechanism. Don't order the PCB until one cell is reliable.
- Jan 8: PCB rev A ordered (before Chinese New Year, Feb 6, 2027). Rev B by Jan 22 if needed.
- Jan 15: fewer than 24 good dots means target 4 cells.
- Feb 5: PCB not working means protoboard fallback with 2-4 cells.
- Feb 19: feature freeze.
- OCR under 95% on the real rig: fix lighting and resolution before touching the model.
