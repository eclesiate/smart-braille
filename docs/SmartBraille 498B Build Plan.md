# SmartBraille – ECE 498B Build Plan

Written Nov 11, 2026, from the 498A detailed design (July 12, 2026) and the team's current state: Jetson Orin Nano Super and IMX219-120 in hand (no storage), one 3D-printed large braille cell proven on a breadboard, nothing else built.

Goal of this plan: a working demo at the symposium with the least risk, not the best grade.

## 1. The calls

| Question | Decision |
|---|---|
| Custom PCB? | Yes, one, but a much simpler one than the design doc: a driver board with a Raspberry Pi Pico plugged into headers. No CH32V003, no CH340C, no USB-C routing. It is not on the critical path: a hand-wired 2–4 cell version is the fallback. |
| How many cells? | 8 (build 10). The 40 in the enclosure section is dropped. No spec states a cell count; FS3 only needs all 63 patterns. Minimum acceptable demo is 4 working cells. |
| Text extraction | Classical OCR (Tesseract) is the main path. The VLM becomes an optional mode, time-boxed to two days of effort. |
| Camera | Test the IMX219-120 this week, but order a USB autofocus camera now as the expected replacement. |
| Buttons | Wire them to the Pico, not the Jetson 40-pin header. |
| Enclosure | Flat board base + aluminum-extrusion mast. 3D-print only small parts. Single letter page, not a double spread. |
| Biggest schedule risk | Hand-building 48+ actuators, not the PCB. Cell production starts now. |

## 2. Target system

```
Page on matte-black base, LED bars at the sides
        |
USB autofocus camera on a ~350 mm mast
        |  USB
Jetson Orin Nano Super (Ubuntu / JetPack)
  capture -> OpenCV dewarp + illumination fix (already designed in 498A)
  -> Tesseract OCR -> liblouis (text -> braille cells)
  -> 8-cell window + paging state machine
        |  USB serial (/dev/ttyACM0), one cable
Raspberry Pi Pico on the driver PCB
  buttons (Scan, Back, Next, Play/Pause), buzzer
  shift registers -> H-bridge drivers -> 8 cells x 6 coils
        ^
separate 5 V supply + fuse for the coils
```

A monitor on the Jetson mirrors the recognized text and the dots being shown. Judges can verify the braille without reading it, and the demo survives a dead cell.

## 3. What changes from the detailed design, and why

**Display controller: Pico instead of CH32V003 + CH340C.** The Pico has native USB, shows up as a serial port, and is programmed over the same USB cable. The CH32V003 needs a separate WCH programmer, a USB bridge chip, and a from-scratch board bring-up. The block diagram stays the same (Jetson → USB serial → display MCU → drivers), so the report barely changes.

**Buttons move to the Pico.** Jetson Orin Nano header GPIO on JetPack 6 has a long record of pinmux and pull-resistor trouble. The Pico reads the buttons, debounces them in firmware, and sends events up the serial link.

**OCR first, VLM optional.** The 498A benchmark put Qwen2.5-VL at 10–35 s per page, against a 5 s spec (FS2, NFS1), and that was not measured on the Jetson (it has never booted). Tesseract on a clean, dewarped, 250+ DPI page of printed text is fast, does not invent words, and installs with one `apt` command. Reword NFS2 from "VLM system" to "text extraction". If someone wants the VLM story for the Jetson, try `ollama run qwen2.5vl:3b` for at most two days and keep it as a "complex layout" mode only if it works.

**Camera.** The design doc's 386 PPI figure assumes the page fills the sensor. With the IMX219-120's real 1.79 mm lens (the doc says 2.2 mm) at 350 mm, the frame is roughly 720 mm wide, the page covers about 39% of it, and you get about 116 DPI: 10-pt lowercase letters are ~8 pixels tall. That is marginal for OCR. Two fixes:
- Free: drop the IMX219 to about 150 mm. You get ~270 DPI in the centre, but with wide-angle distortion, soft corners and awkward lighting.
- Recommended: a 16 MP USB autofocus camera with a ~61–65° horizontal view (Arducam IMX298 USB2 or IMX519 USB3 module). At 350 mm it covers ~410 mm × 325 mm at ~285 DPI, keeps the mast height from the design, and needs no driver (plain `cv2.VideoCapture`).

**Braille translation: use liblouis**, not a hand-written table. Start with uncontracted UEB (`en-ueb-g1.ctb`). It handles capital and number indicators, which is why one cell is not always one character.

**Enclosure.** A 50 cm × 31 cm printed PETG base is days of printing and warps. Use a plywood/MDF/acrylic base painted or covered matte black (this also makes page-edge detection trivial), corner stops for the page, a 20×20 aluminum extrusion mast, and printed brackets for the camera, button panel, cell tray and Jetson.

## 4. The PCB

Assumption to confirm with the teammate who built the cell: the actuators are bistable, like the Hackaday reference design (magnet flipped by reversing coil polarity, no holding current). If they are instead "power on = dot up", tell me; the board gets simpler (TPIC6B595 low-side drivers, no H-bridges).

**Contents (2-layer, repeated block per cell):**
- 2×20 socket headers for a Pico
- one full H-bridge per dot: 24 × DRV8833 (dual bridge) for 48 dots. If the breadboard prototype already uses a different driver that works, copy that one 48 times instead.
- 12 × 74HC595 on one SPI chain (96 driver inputs)
- one 2×6 header per cell for the 12 coil leads, so cells plug in and can be swapped (NFS5), and the board does not depend on cell geometry. That lets it be designed now.
- 5 V barrel jack, fuse, bulk capacitor near the drivers, 100 nF per chip
- headers for 4 buttons and a buzzer

**Three things that prevent burnt coils:**
1. Pull the 74HC595 output-enable high and the DRV8833 sleep pins low with resistors, so nothing drives a coil until the Pico has booted and cleared the registers.
2. Firmware hard-caps pulse length (start at the value proven on the breadboard) and wakes the drivers only during a pulse.
3. Pulse one cell at a time (8 × ~100 ms fits the 1 s refresh spec, NFS3) and only dots that changed. Size the 5 V supply and fuse from the measured current of six coils, not the 5 A in the design doc.

**Schedule for the board.** Fabrication is not a month: 5 two-layer boards are typically built in a day or two and DHL takes under a week; assembly adds about a week. The real constraint is Chinese New Year on Feb 6, 2027: factories slow from late January and anything ordered then sits until mid/late February.
- Rev A ordered by Jan 8 at the latest (before Christmas is better). Have JLCPCB assemble the SMD parts.
- Rev B, only if needed, ordered by Jan 22.
- Fallback if both fail: DRV8833 breakout modules + 74HC595s on protoboard driving 2–4 cells. Same firmware.

## 5. Order this week

- 2 × microSD, 128 GB, U3/A2 (the Jetson ships with no storage; second card is a clone for demo day). An NVMe SSD is optional and only worth it if the VLM stays.
- DisplayPort cable or DP→HDMI adapter (the dev kit has DisplayPort only), USB keyboard and mouse if nobody has spares
- USB autofocus camera (above)
- 3 × Raspberry Pi Pico with headers
- 10 × DRV8833 breakout modules and 10 × 74HC595 (DIP) for breadboarding: half to the cells teammate, half to whoever does firmware
- 5 V / 4 A supply with barrel jack, inline fuse holder
- 4 large push buttons, 1 piezo buzzer
- 2 × USB LED light bars
- Magnets, magnet wire, ferrite cores and filament for 60 dots (cells teammate knows the exact parts)

## 6. Who does what

Five work packages, one owner each. David takes A since he has the Jetson and camera.

| | Package | First deliverable |
|---|---|---|
| A | Jetson + camera + OCR | Jetson booted; photo of a page → text file, with accuracy and time measured |
| B | Braille cells (teammate with the prototype) | One complete 6-dot cell cycling through all 64 patterns 500 times; coil resistance, voltage, current and pulse length written down |
| C | Driver PCB + Pico firmware | Pico on a breadboard driving LEDs (then B's cell) from serial frames; schematic done |
| D | Mechanical: base, mast, lighting, cell tray, button panel | Camera rigidly held at 350 mm over a letter page with even light |
| E | Application software + testing + documents | Paging state machine, liblouis, on-screen "virtual display", test scripts; tracks spec changes for the final report |

## 7. Timeline

Symposium date assumed to be around March 10, 2027 (it was March 11 in 2026 and March 12 in 2025). Confirm when the 498B outline is posted.

**Nov 11 – Nov 22**
- Place the order in section 5.
- A: flash the JetPack 6.2.x SD-card image and boot. If it will not boot, the kit has old firmware and needs the firmware-update step in NVIDIA's guide first.
- A: shoot the same printed page with the IMX219 at 15 cm and 35 cm, run Tesseract on both.
- B: answer the actuator questions in section 4.

**Nov 23 – Dec 18 (co-op, evenings)**
- A + E: full software chain on the Jetson with the virtual display: Scan → text → braille → Next/Back on screen. This needs no hardware from anyone else.
- B: finish the one-cell endurance test, check that neighbouring dots do not disturb each other, then start producing dots. Target 20 by Dec 18.
- C: serial protocol (start byte, 8 cell bytes, checksum, end byte, ack) and firmware on a bare Pico; PCB schematic and layout.
- D: base and mast design, buy materials.

**Dec 19 – Jan 3**
- C: order PCB rev A. B: keep producing dots.

**Jan 4 – Jan 15 (back on campus)**
- Day one: one real cell working end to end from a scanned page.
- Email Prof. Basir a short list of the changes in section 3 so they are agreed early.
- Mast, lighting and camera assembled; OCR tuned on the real rig.

**Jan 18 – Feb 5**
- PCB bring-up, one cell at a time. Rev B by Jan 22 if needed.
- All 8 cells assembled and mounted. Buttons, buzzer, Jetson auto-start on power-up (systemd service).

**Feb 8 – Feb 19**
- Full system working. Feature freeze Feb 19.

**Feb 22 – symposium**
- Verification against the spec table: 20 printed pages for accuracy (character error rate), scan-to-first-braille time, refresh time, 30-minute soak (NFS4), all 63 patterns on every cell.
- Poster, final report, demo rehearsals, two spare cells, cloned SD card.

## 8. Checkpoints that trigger the fallback

- Dec 18: one cell has not survived 500 cycles → meet over the break and simplify the mechanism or enlarge it further; do not order the PCB until one cell is reliable.
- Jan 15: fewer than 24 good dots → target 4 cells.
- Feb 5: PCB not working → protoboard fallback with 2–4 cells.
- Any time: OCR under 95% on the real rig → fix lighting and resolution before touching the model.

## 9. Minimum demo that still passes

Place a printed page, press Scan, hear a beep, and within about 10 seconds the first characters appear on at least 4 cells; Next and Back page through the text; the monitor shows the text and dot patterns. Everything beyond that is a bonus.

## Sources

- Reference actuator design: https://hackaday.io/project/191181-electromechanical-refreshable-braille-module
- Jetson Orin Nano quick start (storage, JetPack): https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/quick_start.html
- JetPack 6 SD-card setup and firmware check: https://www.jetson-ai-lab.com/tutorials/initial-setup-jetson-orin-nano
- Jetson GPIO issues on JetPack 6: https://forums.developer.nvidia.com/t/problems-with-jetpack-6-and-gpio/326340
- IMX219-120 lens specs: https://www.waveshare.com/product/raspberry-pi/cameras/pi5-imx219.htm
- Arducam 16 MP USB autofocus cameras: https://www.arducam.com/16mp-autofocus-usb-camera-with-microphone-1-2-8-imx298-mini-uvc-usb2-0-4k-video-webcam-standard-module.html and https://arducam.com/?p=98638
- JLCPCB production time: https://jlcpcb.com/help/article/PCB-Fabrication-Services-and-Production-Time
- ECE symposium dates: https://uwaterloo.ca/electrical-computer-engineering/events/electrical-and-computer-engineering-capstone-design-0
