# Cell measurements

Fill this in from the real cell. The driver PCB, its fuse and the firmware's pulse settings are all sized from these numbers, and nothing on the PCB side will be guessed in their place. Leave a line blank if it has not been measured.

Write the unit with every number, and say how it was measured.

## 1. Coil resistance

Multimeter on ohms across the two leads of one coil, with the coil disconnected from everything. Hand-wound coils vary, so measure all six if you can.

| Dot | Resistance (ohms) |
|---|---|
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |
| 6 | |

Meter used: 
Date: 

## 2. What already works on the breadboard

Record the settings that flip a dot reliably today. Do not change them to fill this in.

| Item | Value | Notes |
|---|---|---|
| Supply voltage at the coil (V) | | Measured at the driver, not the supply's label. |
| Pulse length (ms) | | The value the test code uses now. |
| Driver or transistor part | | e.g. a DRV8833 module, L298N, discrete MOSFETs. |
| Power supply used (model, rated current) | | |
| How many dots have been pulsed at the same moment | | |
| Does every dot flip both ways, every time? | | |

Current per coil can be calculated from voltage and resistance. **Do not hold a coil on to read a current meter.** If you have an oscilloscope and a small sense resistor, a trace of one pulse is welcome but optional.

## 3. Limits you have observed

Only what you have actually seen. Do not run a coil longer or harder to find out.

| Item | Value | Notes |
|---|---|---|
| Longest pulse you have used without the coil getting warm (ms) | | |
| Shortest pulse that still flipped the dot (ms) | | |
| Any dot that disturbed its neighbour? | | Which dots, at what settings. |

## 4. Mechanical

| Item | Answer |
|---|---|
| Scale factor against the Hackaday reference cell (e.g. 3x) | |
| Does every coil have both of its leads brought out separately (12 wires per cell)? Or are the coils joined to a common wire inside the cell (7 wires)? | |
| How do the coil leads leave the cell? (loose magnet wire, soldered pins, a small PCB) | |
| Core material and size (the reference uses a 1 x 10 mm ferrite rod; steel overheated) | |
| Coil wire diameter (mm) and approximate number of turns | |
| Magnet size and type | |
| Lead length available to reach a connector (mm) | |
| Wire gauge of the coil leads | |
| Dots per cell | |
| Cells planned | |

## 5. Endurance (checkpoint: Dec 18, 500 cycles)

One cycle = every dot up, then every dot down, or one pass through all 64 patterns. Say which.

| Date | Cycles run | Settings (V, ms) | Failures (which dot, what happened) |
|---|---|---|---|
| | | | |
