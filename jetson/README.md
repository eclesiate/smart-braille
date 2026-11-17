# jetson

**Owner:** David (Jetson software)

Capture, preprocessing, OCR (Tesseract), liblouis translation, and the paging state machine.

## Status (Nov 17, 2026)

The whole software chain runs on a laptop from an image file, with the display printed in the terminal. Nothing has run on the Jetson yet (no SD card), and nothing has been tested with a real camera or a real Pico.

## Run it

From this folder, with the repo's `.venv` active:

```
python -m smartbraille --image page.jpg            # a photo instead of a camera
python -m smartbraille --image page.jpg --once     # scan, print every window, exit
python -m smartbraille --camera 0                  # USB camera
python -m smartbraille --camera 0 --serial /dev/ttyACM0
```

Keys, each followed by Enter: `s` scan, `n` next, `b` back, `p` play/pause, `q` quit.

Tests and accuracy, from the repo root:

```
pytest
python test/ocr_accuracy.py photos/                # real photos with matching .txt files
python test/ocr_accuracy.py --synthetic 116 220 285
```

## Modules (`smartbraille/`)

| File | Does |
|---|---|
| `capture.py` | Image sources: a file, or anything `cv2.VideoCapture` opens. |
| `preprocess.py` | Finds the page on the dark base, warps it to a letter rectangle, evens out the lighting. |
| `ocr.py` | Tesseract, then joins lines and hyphenated words into reading text. |
| `braille.py` | liblouis, uncontracted UEB. Text to 6-bit cells, with a map from each cell back to the source character. |
| `paging.py` | Splits cells into 8-cell windows at word boundaries. Scan / Next / Back / Play-Pause state machine. |
| `protocol.py` | The serial frame to the Pico and the bytes it sends back. |
| `display.py` | Terminal display, and the serial display with ack and retry. |
| `pipeline.py` | One scan end to end, with timings per stage. |
| `metrics.py` | Character error rate. |

## Assumptions

- **Serial protocol details are a proposal.** CLAUDE.md fixes the frame shape. These parts were chosen here and need agreeing with the Pico firmware: start byte 0x02, end byte 0x03, checksum = XOR of the 8 cell bytes, ack 0x06, nak 0x15, and the Pico reporting buttons as single bytes `S` `B` `N` `P`. Cell byte: bit 0 = dot 1 ... bit 5 = dot 6.
- **The buzzer has no command yet.** The reader decides when to beep (scan started, ready, end of text, no text found), but the frame has no way to tell the Pico. For now beeps are only printed. Either the Pico beeps on its own for button presses, or the protocol gains a beep byte.
- **Auto-advance interval** for Play is 3 s per window, a placeholder to tune with a real reader.
- **Page finding uses a brightness threshold**, not the edge map in the 498A design. It relies on the base being matte black and darker than the paper.
- **The page is assumed upright.** A page placed upside down or sideways is not detected or rotated yet.
- **Whitespace is flattened.** Paragraph breaks become single spaces in braille.
- **Low-resolution pages are enlarged** to 300 dpi before OCR when the camera gives under 200 dpi. The thresholds are untested on real photos.
- **Camera is not chosen.** `--camera` takes an index or an OpenCV pipeline string, so either the IMX219 or a USB camera can be used without code changes.

## Measurements

Synthetic pages only (11 pt Times, rendered and then warped, shaded and noised in software), on a MacBook, Nov 17, 2026, Tesseract 5.5.4:

| Page resolution | Character accuracy | OCR time |
|---|---|---|
| 100 dpi | 99.3% | 0.62 s |
| 116 dpi | 100.0% | 0.65 s |
| 150 dpi | 99.7% | 0.62 s |
| 220 dpi | 100.0% | 0.42 s |
| 285 dpi | 100.0% | 0.53 s |

These show the software works. They say nothing about the real camera: a synthetic page is in perfect focus with no lens distortion or glare. Times on the Jetson will differ.

## Setting up the Jetson (untested, to check when it boots)

```
sudo apt install tesseract-ocr liblouis-data python3-louis python3-opencv python3-serial
pip install pytesseract
```
