# hardware/cell

**Owner:** David (cell mechanism)

Cell CAD and measured coil data. Record resistance, voltage, current and pulse length with units and test conditions.

- [MEASUREMENTS.md](MEASUREMENTS.md): the sheet to fill in from the real cell. The driver PCB and the firmware wait on it.

## Known so far

- The cells are bistable: reversing coil polarity flips the cam, and no holding current is needed (cells teammate, via David, Nov 17, 2026).
- The cell is a scaled-up copy of the Hackaday reference design below (David, Nov 18, 2026). **The scale factor is not recorded anywhere we can find.** The 498A detailed design's text does not state it; it may only appear in the cell figures (Figures 2 to 4).

## Reference design: Hackaday project 191181

https://hackaday.io/project/191181-electromechanical-refreshable-braille-module, read Nov 18, 2026.

What it states, and what it does not. **None of these numbers describe our cell.** Scaling changes the coil, core and magnet, and our coils are wound by hand. They are here as context only and must not be used for the pulse length, the current, the fuse or the supply.

| Item | Reference design | Source |
|---|---|---|
| Mechanism | Eccentric cam with a magnet, flipped between two stable positions by reversing the coil polarity. Cannot be back-driven by a finger. | Project page |
| Magnet | NdFeB disc, 1 mm diameter x 0.5 mm | Project page |
| Coil wire | 0.05 mm enamelled self-bonding copper | Project page |
| Core | Fair-Rite 67 ferrite rod, 1 mm x 10 mm. Steel cores (from paperclips) were tried first and overheated. | Project page, log "Updated Winding Jig for Ferrite Cores vs Steel Cores" |
| Coil size | About 6 mm long, at most 2.5 mm diameter (set by the winding jig's spacers) | Log "Coil Winding Tool for Micro-Electromagnets" |
| Turns, coil resistance, voltage, current, pulse length | **Not published.** Voltage was set with an adjustable LM317. A commenter asked for these specs and got no answer. | Logs "Testing Electronics", "Coil Winding Tool" |
| Timing | "At least 100 ms" per pin with the first electronics. Ferrite cores cut the maximum refresh from 200 ms to 50 ms. | Project page |
| Power | "Only 1 W" at any moment, because one pin is driven at a time | Project page |
| Cell wiring | **Both leads of every coil come out separately: 12 pads.** All six A leads at one end of the cell, all six B leads at the other, on two 3x2, 1.27 mm headers. | Eagle files (`Braille Cell Eagle Source Files.zip`, `Braille Cell Eagle Library.lbr`) |
| Driver | Half-H-bridges from source and sink transistor arrays (TBD62783APG, TBD62083APG; later UDN2981 and ULN2803), with the six coils of a cell joined to one common line on the evaluation board, selected by 74HC238 decoders. One pin driven at a time. | Logs "Braille Cell Array Drive Circuit", "Updated Drive Electronics" |
| Cell size | Module board 7.62 x 29.72 mm | Eagle board file |

## What this means for our design

- **The 12-lead cell matches our driver board.** Each coil gets its own H-bridge, and the cell connector carries 6 A/B pairs. This is only true if our scaled cell also brings out both leads of every coil, which is question 7 on the measurement sheet.
- **Our board does not use the reference's common line.** Joining one end of all six coils means a coil can only be driven while the common line is set for it, and a fault on one coil affects the whole cell. Separate H-bridges avoid both.
- **If our cell does join the coils inside it** (7 wires instead of 12), the board as drawn must not be used with it: the shared lead would connect outputs of different H-bridges together. Tell the PCB owner before wiring one.
- The reference's decoder (74HC238) is the same part our board uses to choose a cell.
