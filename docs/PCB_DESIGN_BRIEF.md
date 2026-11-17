# SmartBraille driver PCB: design brief for Claude Code

Prepared Nov 16, 2026, for ECE 498B (University of Waterloo). Put this file in `docs/` and read it fully before touching anything. It is self-contained: the PCB-relevant parts of the team's build plan are included below, and nothing here needs the rest of the plan.

## 0. How to work

**You have full freedom to design this board the way you think is best.** This brief was drafted by a smaller model (Claude Sonnet 5.5) without opening any datasheets, and you are the stronger model doing the actual engineering. Treat it as a starting point and a record of what the team already assumes, not as a spec to obey. If you see a better topology, a better part, a simpler board, a cheaper or more reliable way to meet the goal, or a mistake in this brief, **change it**. Don't ask permission for design choices. Do the following instead:

- Write each deviation and the reason in `hardware/pcb/README.md` under "Deviations from the brief", so the team can follow what changed.
- Keep the system-level interface stable where other people depend on it: the USB serial link from the Jetson to the Pico, 8 cells x 6 dots, one pluggable connector per cell, the button and buzzer functions. If you change one of these, say so clearly at the next report.
- Hardware and safety rules in section 7 are the one thing that is not negotiable. You may reach them by a different design, but the guarantees must still hold.

What you may not do:

1. **Do not guess the open inputs in section 2.** They are measurements only my cells teammate can provide. If I haven't answered yet, draft everything that doesn't depend on them, and stop at the first part that does.
2. **Verify, don't trust.** Every claim tagged **[VERIFY]** must be checked against the manufacturer datasheet before you rely on it. Download the datasheets into `hardware/pcb/datasheets/`. If a datasheet contradicts this brief, the datasheet wins.
3. **Never place or suggest placing an order.** A human reviews the layout in the KiCad GUI first.
4. **Stop at the human gates in section 12** (G1 for the missing measurements, G4 for my layout review, G5 before anyone orders). Between those, keep going on your own; you don't need to check in after each step.
5. **Part numbers.** Every BOM line needs a JLCPCB/LCSC part number that you looked up yourself and confirmed is in stock. This brief deliberately contains no LCSC numbers.
6. Commit small and often. Keep the design in `hardware/pcb/`. Record assumptions in `hardware/pcb/README.md`.

## 1. What this board is

SmartBraille photographs a printed page, runs OCR on an NVIDIA Jetson Orin Nano Super, translates the text to braille, and shows it on an **8-cell refreshable braille display**. The cells are the team's own 3D-printed electromechanical cells, based on the open-source design at https://hackaday.io/project/191181-electromechanical-refreshable-braille-module: each dot is lifted or lowered by an eccentric cam holding a magnet, and a small electromagnet flips the cam to one of two stable positions when its polarity is reversed. The cam stays put with the power off, so no holding current is needed. (**Assumption, see section 2:** the team's large cells work the same way.)

This board is the **display driver board**. It takes frames over USB serial from the Jetson and pulses the right coils:

```
Jetson Orin Nano Super
   |  USB cable (data + power for the Pico only)
   v
Raspberry Pi Pico (plugged into sockets on this board; MicroPython)
   |-- 4 buttons (Scan, Back, Next, Play/Pause) and a buzzer
   |-- SPI (3.3 V) --> 12 x 74HC595 daisy chain (96 outputs)
   |-- 8 per-cell enable lines, 1 fault input
   v
96 outputs -> 24 x DRV8833 dual H-bridges (inputs) -> 48 coil outputs
   v
8 cell connectors (12 wires each = 6 dots x 2 coil leads)
         ^
         separate coil supply (nominally 5 V) through an inline fuse
```

Everything else (camera, OCR, enclosure) is out of scope for this board.

## 2. Open inputs: ask me, do not guess

My cells teammate is measuring these. Fill the right-hand column as answers arrive and keep this table in `hardware/pcb/README.md`.

| # | Question | Why it matters | Answer |
|---|---|---|---|
| 1 | Are the cells bistable (a coil polarity reversal flips the cam, no holding current)? | If not, an H-bridge is wrong. A low-side switch such as a TPIC6B595 would replace the H-bridges and the whole driver section changes. Stop and ask. | |
| 2 | Coil resistance (ohms), per dot | Sets current and driver headroom. | |
| 3 | Coil supply voltage that flips a dot reliably | Sets VM. DRV8833 tolerates a limited range **[VERIFY]**. Nominal is 5 V. | |
| 4 | Current per coil while pulsing (A) | Driver margin, trace width, fuse, supply, bulk capacitance. | |
| 5 | Pulse length that flips a dot reliably (ms), and the safe maximum | Firmware pulse cap and thermal sizing. | |
| 6 | Number of dots per cell, cell count | Assumed 6 and 8. Changes driver counts if not. | |
| 7 | How do the coil leads leave a cell? (loose wires, pins, a small cell PCB) | Decides the connector type and pin order. The board is designed so cell geometry doesn't matter: one pluggable connector per cell. | |
| 8 | Did the breadboard prototype already use a particular driver that works? | If yes, tell me before choosing. Copying a proven driver 48 times beats a new design. | |

If #4 turns out above about 1 A per coil, or #1 is "no", stop and tell me before continuing.

## 3. Starting decisions (defaults the team has assumed; change them if you can do better, and log it)

- **Controller:** a Raspberry Pi Pico (RP2040) or Pico 2 (RP2350), socketed, running MicroPython. No CH32V003, no CH340C, no USB-C routing. The Pico's own USB port is the link to the Jetson.
- **Cell count:** 8 cells, 6 dots each, so 48 dots.
- **Driver topology:** one H-bridge per dot. 48 dots = 24 x DRV8833 (dual H-bridge, 2 dots per chip). Each H-bridge needs 2 logic inputs, so 96 logic bits = 12 x 74HC595 (8 bits each).
- **Logic voltage:** the 74HC595s run at **3.3 V**, taken from the Pico's 3V3 pin, so no level shifters are needed. A 74HC595 at 5 V would need 3.5 V logic highs, which the Pico can't provide on its own (a 74HCT595 at 5 V would be the alternative). [VERIFY that the 74HC595 3.3 V output high level clears the DRV8833 input-high threshold.]
- **Buttons live on the Pico**, not the Jetson (Jetson GPIO has a known history of pinmux trouble). Debouncing is in firmware; leave optional RC footprints.
- **Power:** the coil supply is separate from the Pico's USB power. The Pico gets its 5 V only from USB. Coil power never connects to the Pico's VSYS/VBUS, so there is no back-feed path. Grounds are common.
- **Cell wiring:** one 2x6, 2.54 mm pin header per cell (12 pins = 6 dots x 2 leads). The cells plug in with a cable, so they are swappable.
- **Board stays simple:** 2 layers, all SMD parts on the top side so JLCPCB can assemble it. Through-hole parts (Pico sockets, headers, barrel jack, fuse pads) are hand-soldered.

## 4. Pico pin map (adopt as given, or tell me why you changed it)

| Function | GPIO | Notes |
|---|---|---|
| UART0 TX / RX | GP0 / GP1 | Optional 3-pin debug header (TX, RX, GND). |
| Cell enable 0..7 (to DRV8833 nSLEEP of that cell's 3 chips) | GP2..GP9 | 10 kOhm pull-down to GND on every line, so a cell is asleep unless firmware enables it. |
| Button SCAN, BACK, NEXT, PLAY/PAUSE | GP10..GP13 | Internal pull-ups, active low, to 2-pin headers. Optional DNP 100 nF to GND per button. |
| Buzzer | GP14 | GPIO through about 1 kOhm to an NPN transistor that switches an active 3-5 V piezo buzzer from the Pico's VBUS (USB 5 V). 2-pin header for the buzzer. |
| nFAULT in | GP15 | Open-drain DRV8833 nFAULT outputs wire-OR'd, 10 kOhm pull-up to 3V3. [VERIFY nFAULT exists and is open-drain.] |
| SPI0 RX (chain end QH' back to Pico) | GP16 | For chain loopback tests. |
| 74HC595 RCLK (latch) | GP17 | Plain GPIO. |
| SPI0 SCK | GP18 | Common to all 12 chips. Optional 33 Ohm series resistor near the Pico. |
| SPI0 TX (MOSI to first chip SER) | GP19 | Optional 33 Ohm series resistor. |
| 74HC595 /OE (output enable, active low) | GP20 | **10 kOhm pull-up to 3V3**, so outputs are high-Z until firmware enables them. |
| 74HC595 /SRCLR (active low) | GP21 | 10 kOhm pull-up to 3V3 so it idles high. |
| VM monitor (optional ADC) | GP26 | Resistor divider from VM sized so the maximum VM stays below 3.3 V. |
| Spare | GP22, GP27, GP28 | Break out to a header. |

Check every row against the Pico datasheet (https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf). Use the official KiCad Pico footprint if available. Leave the Pico's USB connector reachable at the board edge.

## 5. Dot-to-bit mapping (the contract with the firmware)

Cells 0..7, dots 1..6 in standard braille order (dots 1,2,3 down the left column, 4,5,6 down the right). Within a cell, dot index d = 0..5.

- DRV chip index: `drv = 3*cell + d//2` (0..23). Each chip has bridge A (`d%2 == 0`) and bridge B (`d%2 == 1`).
- Logic bits for that dot: `IN1 = 4*drv + 2*(d%2)`, `IN2 = IN1 + 1`, as logical output index 0..95.
- Drive states: dot up = (IN1, IN2) = (1, 0), dot down = (0, 1), idle = (0, 0). Which polarity is "up" depends on how the coil is wound, so keep it configurable in firmware.
- Each cell's three DRV chips share that cell's nSLEEP enable line.

**You must write down the exact chain order:** which physical 595 pin carries each logical output index, and which bit of the 96-bit SPI stream is that. When 12 chips are chained, the first bit sent ends up in the last chip. Put the table in `hardware/pcb/README.md`, add a tested Python function for it in `firmware/pico/`, and verify it at bring-up (section 10).

## 6. Parts and datasheet checks

Choose actual orderable parts and confirm stock. Suggested parts below.

| Block | Suggested part | Notes / [VERIFY] |
|---|---|---|
| Dual H-bridge, 24x | TI DRV8833 (HTSSOP-16 with thermal pad, "PWP") | Pinout, VM range, per-bridge current, VIH threshold, nSLEEP wake time, nFAULT behaviour, required capacitors (VM bulk and bypass, the internal-regulator pin capacitor), ISENx pin handling, and how the outputs behave with both inputs low. The thermal pad must be soldered to a ground pour. If it is out of stock or end-of-life, propose a pin-compatible alternative and stop for my approval. |
| Shift register, 12x | 74HC595 in SOIC-16 | Confirm VCC range includes 3.3 V, output-high level at 3.3 V, max clock at 3.3 V, and the /OE, /SRCLR and QH' pins. |
| Pico | Raspberry Pi Pico H or Pico 2 H, in two 1x20 female 2.54 mm socket rows | Either works with MicroPython. I'll flash the matching firmware. |
| Buzzer driver | small SOT-23 NPN | Check base resistor and that the transistor suits the buzzer's current. |
| Coil supply input | 5.5 mm x 2.1 mm barrel jack (or screw terminal), center-positive | Silkscreen polarity clearly. |
| Fuse | Provide pads or a holder footprint for a 5x20 mm fuse in series with the coil supply | The team spec (NFS9) requires an inline fuse. The rating is **not** 5 A by default: size it from the measured current in section 2, see section 7. |
| Reverse polarity and surge | P-channel MOSFET reverse-polarity protection, plus a TVS diode | Size to the final VM and current. Check the MOSFET's drop and dissipation at peak current. |
| Bulk capacitors | Electrolytic or polymer at the supply input, plus 10 uF + 100 nF at each DRV8833 per the datasheet | Compute the bulk value from pulse current and allowed droop. |
| Test points | 5 V (VM), GND (several), 3V3, SCK, MOSI, RCLK, /OE, nFAULT, the 8 cell enables | For bring-up. |
| Mounting | 4 x M3 holes | Keep clear of the Pico's USB connector. |

Estimated parts: 36 chips, about 110 capacitors, a few dozen resistors. Budget is not tight; JLCPCB "extended" parts are fine, but prefer "basic" passives to keep assembly simple.

## 7. Power, protection and the safe state

**Safe state. These are hard requirements, not suggestions:**

1. With the Pico unpowered, in reset, or running before the firmware starts, **no coil may be driven**. 74HC595 /OE is pulled up, so its outputs are high-Z; every cell's nSLEEP line is pulled down, so the DRV8833s are asleep. Check on the DRV8833 datasheet that input pins are safe when left unconnected or high-Z [VERIFY], and make the nSLEEP pull-down alone sufficient.
2. With VM present but the Pico unpowered, the DRV8833s stay asleep (same reasoning).
3. With the Pico powered but VM off, check that the 74HC595 outputs can't back-power the DRV8833s through their input protection diodes. Explain what you found.
4. Firmware, not hardware, handles the pulse length cap and one-cell-at-a-time rule. The hardware guarantee is that only an enabled cell can move, and that the supply can't deliver more than the fuse and sizing allow.

**Sizing (do this once section 2 is answered, and show the arithmetic):**
- Worst-case simultaneous current = (dots flipped at once, up to 6 in one cell) x (current per coil). This sets the supply rating, the VM trace width and the fuse.
- The fuse must tolerate the pulse inrush without nuisance blowing (a slow-blow type, as in the team's design) and still protect the board. If the arithmetic gives a fuse far from 5 A, say so.
- DRV8833 current limiting: decide whether to tie the ISEN pins straight to ground or fit sense resistors, and justify it. Coil resistance already limits the current, so direct grounding is probably fine **[VERIFY]**.
- Pulse everything on or off through the enable and data lines, not by switching VM.

## 8. Connectors

- **Cell connectors J_CELL0..7:** 2x6 pin header, 2.54 mm, keyed or with a clear pin-1 mark. Pairs are (dot1+, dot1-), (dot2+, dot2-), ... Label the silkscreen "C0".."C7" and "1A 1B 2A 2B ...". Polarity is arbitrary because firmware reverses it; label them anyway so everyone wires the same way.
- **Buttons:** four 2-pin 2.54 mm headers (JST-XH is a fine alternative), labelled SCAN, BACK, NEXT, PLAY.
- **Buzzer:** 2-pin header.
- **Debug UART:** 3-pin header.
- **Coil supply:** barrel jack plus fuse pads.
- **Optional:** the Pico's SWD pads exposed, and an unpopulated 2x3 header for chain loopback.

## 9. Layout guidance

- 2 layers, 1.6 mm FR4. Bottom layer is mostly ground. Top layer holds parts, logic routing and the wide VM traces.
- Target at most 100 x 100 mm if you can (cheapest JLCPCB tier). Larger is acceptable. Don't contort the layout for size.
- Put the Pico at an edge with its USB connector overhanging the edge. Put the barrel jack and fuse at the opposite edge. Put the 8 cell headers in a row along one edge so cables don't cross.
- Place each cell's three DRV8833 chips and their two supporting 595 chips close to its header, so coil traces stay short. Run VM high-current paths with trace widths computed from section 2, and say how you computed them.
- Decoupling: 100 nF within a few mm of every IC supply pin; each DRV8833's bulk and bypass caps per the datasheet.
- Keep SCK and RCLK short with a continuous ground under them. The 12-chip daisy chain is not fast, so there is no need for exotic termination beyond the optional series resistors.
- Solder the DRV8833 thermal pad to ground with vias, and check JLCPCB's via-in-pad and minimum-spacing rules before routing.
- Silkscreen: pin 1 marks, connector names, polarity, test-point names, board name and revision ("SmartBraille driver Rev A").
- Include fiducials if JLCPCB assembly needs them, and check the 3D view for footprint orientation.

## 10. Bring-up test plan (design the board so this is possible)

1. **Unpowered:** continuity and shorts checks on VM-GND, 3V3-GND.
2. **Pico only (VM off):** the Pico boots over USB; the 3V3 rail loads normally.
3. **Chain loopback:** with /OE high and nothing connected to the cells, shift a known 96-bit pattern in and read it back on GP16. Proves the whole 595 chain with no coil risk.
4. **One-hot test:** enable /OE and walk a single logic output through all 96 positions, measuring the corresponding DRV8833 input pin. Verifies the mapping table.
5. **VM on, no cells:** confirm the DRV8833s stay asleep until a cell enable goes high.
6. **Dummy load:** a resistor of the measured coil resistance across one output pair. Pulse it at the measured pulse length and check current and temperature.
7. **One cell:** connect one cell. Cycle all 64 patterns.
8. **Then:** all 8 cells, then the full system.

## 11. Manufacturing deliverables (JLCPCB, 2 layers, top-side SMT)

- Run ERC and DRC with `kicad-cli`. Both must be clean, or every remaining item explained in writing.
- Export Gerbers and drill files, a BOM in JLCPCB's format with LCSC part numbers, and a pick-and-place (CPL) file. Check the CPL rotations for polarised and IC parts against JLCPCB's 3D preview, since rotation offsets are a common error.
- Put the fab package in `hardware/pcb/release/revA/` with a short checklist of what you verified.
- JLCPCB production time for simple two-layer boards is typically 1-2 days build plus shipping, and SMT assembly adds a few days. See https://jlcpcb.com/help/article/PCB-Fabrication-Services-and-Production-Time. Don't treat these as promises.

## 12. Gates (stop and report at each)

Only G1, G4 and G5 are hard stops that need a human. G2 and G3 are artifacts to produce and report as you go; continue straight through them without waiting for my approval unless you hit something you can't resolve.

| Gate | What I expect to see |
|---|---|
| G1 Inputs (**stop**) | Section 2 table filled in by me. If it isn't, finish everything that doesn't depend on it, then stop and list what you need. |
| G2 Schematic | A complete KiCad schematic, plus a plain-language summary of every net and every part, the bit-order table from section 5, and the sizing arithmetic from section 7. |
| G3 Checks | ERC clean, and a table checking each IC pin against its datasheet with the page cited. Every [VERIFY] item from this brief resolved. A second pass over the netlist, as if reviewing someone else's work. |
| G4 Layout (**stop**) | Placement and routing done, DRC clean, screenshots of the board. I review it in the KiCad GUI. |
| G5 Fab package (**stop**) | Release files, BOM/CPL, and the checklist. I order the boards myself. |

## 13. Schedule

- Rev A should be ordered by **Jan 8, 2027** at the latest. Earlier is better, before Christmas if the cell numbers allow.
- Chinese New Year is Feb 6, 2027. Factories slow in late January, so a respin (Rev B) should be ordered by Jan 22.
- Fallback if neither revision works: breakout DRV8833 modules and 74HC595 chips on protoboard driving 2 to 4 cells with the same firmware. Design the pin map and mapping function so the fallback uses them unchanged.

## 14. Things most likely to go wrong

- Wrong or unverified pinout on a hand-checked schematic. This costs a respin, so the pin table in G3 is not optional.
- 74HC595 outputs and DRV8833 inputs disagreeing on logic levels at 3.3 V.
- Coil outputs driven at boot because a pull-up or pull-down is missing.
- Thermal pad not connected, or too little copper on the VM rail.
- Fuse rating copied from the earlier design doc instead of derived from measurements.
- Chain bit order reversed, so every dot is the wrong one.
- A footprint rotated 90 or 180 degrees in the JLCPCB assembly file.

## References

- Reference cell design (Hackaday): https://hackaday.io/project/191181-electromechanical-refreshable-braille-module
- TI DRV8833 product page: https://www.ti.com/product/DRV8833
- TI SN74HC595 product page: https://www.ti.com/product/SN74HC595
- Raspberry Pi Pico datasheet: https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf
- JLCPCB production times: https://jlcpcb.com/help/article/PCB-Fabrication-Services-and-Production-Time
