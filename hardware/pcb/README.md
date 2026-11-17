# hardware/pcb

**Owner:** David (driver PCB)

KiCad project for the Pico driver board. The brief is [docs/PCB_DESIGN_BRIEF.md](../../docs/PCB_DESIGN_BRIEF.md). Schematic first, every BOM line gets an LCSC part number, ERC and DRC clean via `kicad-cli`. A human reviews the layout before any order.

## Status (Nov 16, 2026)

**Stopped at gate G1.** The datasheet checks, the architecture, the pin map and the bit-order mapping are done. Input 1 was answered on Nov 17 (bistable), which confirms H-bridges. No schematic exists yet. Inputs 2 to 5, 7 and 8 are still open; without 2 to 5 the fuse, supply, trace widths and bulk capacitor cannot be sized.

## Open inputs (gate G1)

Nothing in this table may be guessed. Sizing, the fuse, the connector and the schematic wait for it.

| # | Question | Why it matters | Answer |
|---|---|---|---|
| 1 | Are the cells bistable (a coil polarity reversal flips the cam, no holding current)? | If not, H-bridges are wrong and the driver section changes. | **Yes** (cells teammate, via David, Nov 17, 2026) |
| 2 | Coil resistance (ohms), per dot | Current and driver headroom. | |
| 3 | Coil supply voltage that flips a dot reliably | Sets VM. The DRV8833 accepts 2.7 V to 10.8 V. | |
| 4 | Current per coil while pulsing (A) | Driver margin, trace width, fuse, supply, bulk capacitance. Above about 1 A is a stop. | |
| 5 | Pulse length that flips a dot reliably (ms), and the safe maximum | Firmware pulse cap, hardware timeout, thermal sizing. | |
| 6 | Dots per cell, cell count | Assumed 6 and 8. | |
| 7 | How do the coil leads leave a cell? (loose wires, pins, a small cell PCB) | Connector type and pin order. | |
| 8 | Did the breadboard prototype use a particular driver that works? | A proven driver beats a new one. | |

## Architecture

```
Pico GP19 MOSI, GP18 SCK, GP17 RCLK, GP20 /OE, GP21 /SRCLR
        |
        v
   SR1 (74HC595) --QH'--> SR2 (74HC595) --QH'--> GP16 (loopback)
        |                      |
   bus bits 0..7          bus bits 8..11 (12..15 spare)
        +----------+-----------+
                   v
   12-bit bus, wired to the IN pins of all 24 DRV8833 (3 per cell)

Pico GP2..GP4 (A0..A2), GP5 (CELL_EN)
        |
        v
   74HC238 decoder --> Y0..Y7 = nSLEEP of cell 0..7 (one high at a time)

Each cell: 3 x DRV8833 --> 2x6 header --> 6 coils
Coil supply: jack --> fuse --> reverse-polarity FET --> VM (never joins the Pico's 5 V)
```

To move a cell, firmware puts the pattern on the bus, selects the cell on the decoder, raises CELL_EN, waits for the drivers to wake, drives the bus for the pulse length, then releases everything. Only the selected cell's drivers are awake, so only that cell acts on the bus.

## Deviations from the brief

1. **Two 74HC595s on a shared bus instead of twelve.** The firmware only ever pulses one cell at a time, and a sleeping DRV8833 ignores its inputs and leaves its outputs high-Z (DRV8833 p11). So every cell can share the same 12 data lines, and the cell enable alone decides which cell moves. This removes 10 chips, shortens the chain from 96 bits to 16, and makes the mapping identical for every cell. Costs: each bus line drives 8 inputs instead of 1 (at most 264 uA, well within a 74HC595 output), and a stuck bus line affects every cell instead of one.
2. **A 74HC238 decoder selects the cell, instead of 8 enable GPIOs.** With a shared bus, two awake cells would both move. The decoder can only raise one output, so "never drive two cells at once" becomes a hardware guarantee instead of a firmware rule. It also frees GP6..GP9.
3. **The section 5 mapping is replaced.** This is the contract with the firmware, so it is a change other people depend on. The new mapping is under "Bit order" below and in `firmware/pico/dotmap.py`. The protoboard fallback uses the same mapping with 2 x 74HC595 and 1 x 74HC238 in DIP.
4. **Pull resistor values.** /OE pull-up and CELL_EN pull-down are 4.7 kOhm, not 10 kOhm. An RP2040 pin in reset has a 50 to 80 kOhm internal pull-down, which drags a 10 kOhm pull-up to 2.75 V. That still reads high, but 4.7 kOhm gives 3.0 V. On a Pico 2, erratum RP2350-E9 needs an external pull-down of 8.2 kOhm or less to hold a pin low when its input buffer is on.
5. **Two capacitors the brief's parts list left out.** Each DRV8833 needs 10 nF from VCP to VM and 2.2 uF from VINT to GND, as well as the 10 uF on VM (DRV8833 p3, p15).
6. **Pico datasheets are not committed.** They total 21 MB. `datasheets/README.md` has their URLs and checksums.
7. **Planned: a hardware timeout on CELL_EN.** If MicroPython stops with a cell enabled, the coil stays driven until the watchdog fires. A capacitor-coupled enable would cut the cell off after a fixed time regardless of firmware. It needs the pulse length (input 5) before it can be sized, and it will have a bypass jumper. The brief assigns the pulse cap to firmware; this is a backstop, not a replacement.

## Pico pin map

All rows checked against the Pico pinout (Pico datasheet Figure 2, PDF page 5). The Pico 2 pinout is the same.

| Function | GPIO | Pico pin | Notes |
|---|---|---|---|
| UART0 TX / RX | GP0 / GP1 | 1 / 2 | Optional 3-pin debug header. |
| Cell address A0, A1, A2 | GP2, GP3, GP4 | 4, 5, 6 | To the 74HC238. 10 kOhm pull-downs. |
| CELL_EN | GP5 | 7 | To the 74HC238 active-high strobe (pin 6). 4.7 kOhm pull-down: no cell is awake unless firmware raises it. |
| Spare | GP6..GP9 | 9..12 | Freed by the decoder. To a header. |
| Buttons SCAN, BACK, NEXT, PLAY | GP10..GP13 | 14..17 | Internal pull-ups, active low. DNP 100 nF each. |
| Buzzer | GP14 | 19 | Through a resistor to an NPN that switches the buzzer from VBUS. |
| nFAULT | GP15 | 20 | All DRV8833 nFAULT pins wire-OR'd, 10 kOhm pull-up to 3V3. |
| SPI0 RX | GP16 | 21 | From SR2 QH', for the loopback test. |
| RCLK | GP17 | 22 | Latch, plain GPIO. |
| SPI0 SCK | GP18 | 24 | 33 Ohm series resistor footprint. |
| SPI0 TX | GP19 | 25 | To SR1 SER. 33 Ohm series resistor footprint. |
| /OE | GP20 | 26 | 4.7 kOhm pull-up to 3V3: the bus is high-Z until firmware drives it low. |
| /SRCLR | GP21 | 27 | 10 kOhm pull-up to 3V3. |
| VM monitor | GP26 (ADC0) | 31 | Divider from VM, sized once VM is known. |
| Spare | GP22, GP27, GP28 | 29, 32, 34 | To a header. |

## Bit order

Draft, pending inputs 1 and 6. The table, `firmware/pico/dotmap.py` and `test/test_dotmap.py` change together or not at all.

SPI sends one 16-bit word, MSB first, mode 0. Bit n of the word is logical output n. The first bit sent ends up in SR2 QH, the last in SR1 QA.

| Word bit / logical output | Chip | Output | 74HC595 pin | Goes to (every cell) | Meaning |
|---|---|---|---|---|---|
| 0 | SR1 | QA | 15 | DRV chip 0, AIN1 | Dot 1, IN1 |
| 1 | SR1 | QB | 1 | DRV chip 0, AIN2 | Dot 1, IN2 |
| 2 | SR1 | QC | 2 | DRV chip 0, BIN1 | Dot 2, IN1 |
| 3 | SR1 | QD | 3 | DRV chip 0, BIN2 | Dot 2, IN2 |
| 4 | SR1 | QE | 4 | DRV chip 1, AIN1 | Dot 3, IN1 |
| 5 | SR1 | QF | 5 | DRV chip 1, AIN2 | Dot 3, IN2 |
| 6 | SR1 | QG | 6 | DRV chip 1, BIN1 | Dot 4, IN1 |
| 7 | SR1 | QH | 7 | DRV chip 1, BIN2 | Dot 4, IN2 |
| 8 | SR2 | QA | 15 | DRV chip 2, AIN1 | Dot 5, IN1 |
| 9 | SR2 | QB | 1 | DRV chip 2, AIN2 | Dot 5, IN2 |
| 10 | SR2 | QC | 2 | DRV chip 2, BIN1 | Dot 6, IN1 |
| 11 | SR2 | QD | 3 | DRV chip 2, BIN2 | Dot 6, IN2 |
| 12..15 | SR2 | QE..QH | 4..7 | Spare, to test pads | |

- Dot d (1..6): `IN1 = 2*(d-1)`, `IN2 = IN1 + 1`.
- (IN1, IN2) = (1, 0) drives lead A high and lead B low. (0, 1) is the reverse. (0, 0) is idle, outputs high-Z. (1, 1) is never sent.
- Which direction is "up" depends on how each coil is wound. `bus_word()` takes a per-dot invert mask.
- Cell c (0..7): decoder address A0 = bit 0 of c, A1 = bit 1, A2 = bit 2. Output Yc drives that cell's three nSLEEP pins.
- Cell connector: pin pair for dot d is (xOUT1, xOUT2) of that dot's bridge, labelled "dA dB".

## Datasheet checks

Page numbers are PDF pages. Files are in `datasheets/`.

| Item from the brief | Result | Source |
|---|---|---|
| DRV8833 VM range | 2.7 V to 10.8 V recommended, 11.8 V absolute maximum. 5 V is fine. | DRV8833 p5 |
| DRV8833 current per bridge | 1.5 A RMS, 2 A peak in the PWP package at VM = 5 V, 25 C. Overcurrent trips between 2 A and 3.3 A, then retries after 1.35 ms. | p1, p6, p11 |
| DRV8833 input-high threshold | 2.0 V on the IN pins. **2.5 V on nSLEEP**, which the brief did not mention. Input-low is 0.7 V (0.5 V on nSLEEP). | p6 |
| 74HC595 output high at 3.3 V clears it | Yes. The datasheet gives VCC - 0.1 V at 20 uA for 2 V and 4.5 V supplies, so about 3.2 V at 3.3 V. With 8 inputs on a line (33 uA each, maximum) the drop is still well under 0.2 V. Margin over 2.0 V is more than 1 V. | 74HC595 p5, DRV8833 p6 |
| 74HC238 output high clears nSLEEP's 2.5 V | Yes, with about 0.5 V of margin at a 3.2 V rail and a 10 kOhm pull-down load. This is the tightest logic margin on the board. | 74HC238 p5, DRV8833 p6 |
| nSLEEP wake time | Up to 1 ms before the outputs respond. Firmware waits at least 2 ms after CELL_EN before driving the bus. | p11 |
| nFAULT exists, open-drain | Yes, pin 8, open-drain, low on overcurrent and overtemperature. The text says it also goes low on undervoltage, but Table 3 says it does not. Firmware must not trust nFAULT when VM is off, and uses the VM monitor instead. | p4, p6, p11 |
| Required capacitors | 10 uF minimum on VM. 2.2 uF, 6.3 V on VINT. 10 nF, 16 V X7R from VCP to VM (not to ground). | p3, p15 |
| ISEN pins | "If current control is not needed, the xISEN pins should be connected directly to ground." Overcurrent protection still works without sense resistors. Plan: tie to ground, confirmed once input 4 is known. | p10, p11 |
| Outputs with both inputs low | Coast: both outputs high-Z. | p9, Table 1 |
| Inputs left unconnected or high-Z | Safe. Every IN pin has a 150 kOhm internal pull-down and nSLEEP has 500 kOhm, so a floating input reads low. | p3, p6 |
| Logic signals present with VM off | Allowed: "The presence of digital input signals is acceptable before VM is applied." The inputs are rated to 5.75 V independent of VM. | p14, p5 |
| Thermal pad | The GND pin and the pad must both be connected to ground. | p3 |
| DRV8833 PWP pinout | 1 nSLEEP, 2 AOUT1, 3 AISEN, 4 AOUT2, 5 BOUT2, 6 BISEN, 7 BOUT1, 8 nFAULT, 9 BIN1, 10 BIN2, 11 VCP, 12 VM, 13 GND, 14 VINT, 15 AIN2, 16 AIN1, pad GND. | p3 |
| 74HC595 supply range | 2 V to 6 V. 3.3 V is fine. | 74HC595 p4 |
| 74HC595 input-high at 3.3 V | About 2.4 V (0.7 x VCC). The Pico guarantees 2.62 V. | 74HC595 p4, RP2040 datasheet p617 |
| 74HC595 maximum clock | 5 MHz guaranteed at 2 V, 25 MHz at 4.5 V. Run SPI at 1 MHz. | p6 |
| 74HC595 /OE, /SRCLR, QH' | /OE pin 13: high disables QA..QH only, so QH' still works for loopback. /SRCLR pin 10 clears the shift register but **not the outputs**; firmware must pulse RCLK after a clear. QH' pin 9. | p3, p12 |
| 74HC595 pinout | 1..7 QB..QH, 8 GND, 9 QH', 10 /SRCLR, 11 SRCLK, 12 RCLK, 13 /OE, 14 SER, 15 QA, 16 VCC. | p3 |
| 74HC238 pinout | 1..3 A0..A2, 4 and 5 active-low strobes, 6 active-high strobe, 7 Y7, 8 GND, 9 Y6, 10 Y5, 11 Y4, 12 Y3, 13 Y2, 14 Y1, 15 Y0, 16 VCC. **Go by pin number:** TI calls pin 6 "G2", other vendors call it "G1" or "E3". | 74HC238 p3 |
| Pico 3V3 pin load | Keep under 300 mA. The logic here draws a few mA. | Pico p9 |
| Pico pull-down in reset | 50 to 80 kOhm on RP2040. On RP2350, erratum E9 needs 8.2 kOhm or less externally. | RP2040 datasheet p617, RP2350 datasheet p1359 |

The pin tables above use TI datasheets. The parts JLCPCB stocks are from other manufacturers (see "Candidate parts"), so gate G3 repeats the pin check against each manufacturer's own datasheet.

## Safe state

How the four hard requirements in section 7 of the brief are met.

1. **Pico unpowered, in reset, or before firmware runs: no coil driven.** Two independent barriers. CELL_EN is pulled down, so the decoder holds all eight nSLEEP lines low and every DRV8833 is asleep with high-Z outputs. /OE is pulled up, so the bus is high-Z and the DRV8833 internal pull-downs hold every input low (coast). Each nSLEEP line also has its own 10 kOhm pull-down, so the drivers stay asleep even if the decoder is missing or unpowered.
2. **VM present, Pico unpowered.** The 3V3 rail is off, so the decoder and shift registers are unpowered and cannot drive anything high. The nSLEEP pull-downs keep the drivers asleep. One side effect: the VM monitor divider feeds a small current into GP26 through the pin's protection diode. The divider will be sized to keep that under 50 uA.
3. **Pico powered, VM off.** TI states logic signals may be present before VM (DRV8833 p14), and the inputs carry a rating that does not depend on VM (p5), so there is no back-powering path through an input diode to VM. In normal operation the bus is high-Z and the nSLEEP lines are low anyway. Firmware also reads the VM monitor and refuses to pulse when VM is absent.
4. **Only an enabled cell can move.** A sleeping DRV8833 has high-Z outputs whatever its inputs are (p11), and the decoder can wake only one cell. The supply-side limit (fuse and trace sizing) waits for input 4.

## Sizing (waits for G1)

No numbers until the measurements arrive. The arithmetic will be:

- Coil current: `I_coil = VM / (R_coil + R_bridge)`, with `R_bridge` = 0.36 Ohm typical and 0.6 Ohm hot (DRV8833 p6). Compared against the measured value in input 4.
- Worst-case pulse current: `I_cell = 6 x I_coil`, one cell at a time. Sets the supply rating, VM trace width (IPC-2221) and the fuse.
- Fuse: a slow-blow rating above `I_cell` at the pulse duty cycle, and below what the VM traces and jack can carry.
- Bulk capacitance: `C = I_cell x t_pulse / dV` for the allowed droop, less whatever the supply delivers during the pulse.
- Driver heating: `P = I_coil^2 x R_bridge` per bridge during a pulse, times the duty cycle.
- Each bridge must stay under the 2 A overcurrent floor with margin.

## Candidate parts

Looked up Nov 16, 2026. Stock must be confirmed again when the BOM is frozen.

| Part | LCSC | JLCPCB class | Stock |
|---|---|---|---|
| TI DRV8833PWPR, HTSSOP-16 with pad | C50506 | Extended | About 37,000 (third-party stock mirror, jlcsearch) |
| Nexperia 74HC595D,118, SOIC-16 | C5947 | Basic | Not confirmed: listed on jlcpcb.com, but no stock figure found |
| Toshiba 74HC238D(BJ), SOIC-16 | C5379113 | Extended | About 4,300 (same mirror) |

## Assumptions

- Cells are bistable and each coil has two leads brought out separately (inputs 1 and 7).
- 8 cells of 6 dots (input 6).
- The Pico is a Pico H or Pico 2 H in sockets, powered only from USB.
- Coil supply is nominally 5 V and never connects to the Pico's VBUS or VSYS. Grounds are common.

## Next steps after G1

1. Fill in the table, do the sizing arithmetic, pick the connector, fuse, FET, TVS and bulk capacitor.
2. Schematic in KiCad, ERC clean, net and part summary (G2).
3. Pin-by-pin check against each manufacturer's datasheet and a second pass over the netlist (G3).
4. Layout, DRC clean, then stop for review in the KiCad GUI (G4).
