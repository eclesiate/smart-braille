"""Dot-to-bit mapping for the SmartBraille driver board (rev A draft).

DRAFT, pending gate G1: this assumes bistable cells driven by H-bridges
(open input #1) and 8 cells x 6 dots (open input #6). See
hardware/pcb/README.md, "Bit order", for the matching hardware table.

Runs unchanged on MicroPython and CPython. No imports.

Hardware model
--------------
Two 74HC595s in a chain (SR1 takes MOSI, SR2 takes SR1's QH') drive a
16-bit bus. Bus bits 0..11 go to the IN pins of every cell's three
DRV8833s in parallel. A 74HC238 decoder raises nSLEEP on exactly one
cell, so only that cell's drivers act on the bus.

    logical output n (0..15)   n = 0..7  -> SR1 QA..QH
                               n = 8..15 -> SR2 QA..QH
    dot index d (0..5) = dot number - 1
    IN1 of dot d = bus bit 2*d       IN2 of dot d = bus bit 2*d + 1
    bus bits 12..15 are spare

    (IN1, IN2) = (1, 0)  current flows lead A -> lead B   ("up" by default)
                 (0, 1)  current flows lead B -> lead A   ("down")
                 (0, 0)  coast, outputs high-Z            (idle)
                 (1, 1)  brake, never generated here

SPI: 16 bits, MSB first, mode 0. Bit n of the word is logical output n,
so the word is sent high byte first.
"""

CELLS = 8
DOTS = 6
BUS_BITS = 16
DOT_MASK = (1 << DOTS) - 1

_Q_NAMES = ("QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH")
# 74HC595 SOIC-16 pin numbers for QA..QH (TI SCLS041J, Table 5-1).
_Q_PINS = (15, 1, 2, 3, 4, 5, 6, 7)


def dot_bits(dot):
    """Return (in1_bit, in2_bit) on the bus for braille dot 1..6."""
    if not 1 <= dot <= DOTS:
        raise ValueError("dot must be 1..6")
    d = dot - 1
    return 2 * d, 2 * d + 1


def bus_word(up, down, invert=0):
    """Build the 16-bit bus word for one cell.

    up, down: 6-bit masks (bit 0 = dot 1 ... bit 5 = dot 6) of the dots to
    raise and to lower in this pulse. A dot may not be in both.
    invert: 6-bit mask of dots whose coil is wired the other way round, so
    "up" needs (IN1, IN2) = (0, 1) instead of (1, 0).
    """
    if (up | down | invert) & ~DOT_MASK:
        raise ValueError("masks must fit in 6 bits")
    if up & down:
        raise ValueError("a dot cannot be raised and lowered in one pulse")
    word = 0
    for d in range(DOTS):
        bit = 1 << d
        if not (up | down) & bit:
            continue
        forward = bool(up & bit) != bool(invert & bit)
        word |= 1 << (2 * d if forward else 2 * d + 1)
    return word


def changed_dots(old, new):
    """Return (up, down) masks for moving a cell from pattern old to new.

    old, new: 6-bit cell patterns (bit set = dot raised). Only dots that
    differ are pulsed.
    """
    if (old | new) & ~DOT_MASK:
        raise ValueError("patterns must fit in 6 bits")
    diff = old ^ new
    return diff & new, diff & old


def spi_bytes(word):
    """Return the two bytes to send on SPI (MSB first) for a bus word."""
    if not 0 <= word < (1 << BUS_BITS):
        raise ValueError("word must fit in 16 bits")
    return bytes((word >> 8, word & 0xFF))


def cell_address(cell):
    """Return (a0, a1, a2) for the 74HC238 so that output Y<cell> is selected."""
    if not 0 <= cell < CELLS:
        raise ValueError("cell must be 0..7")
    return cell & 1, (cell >> 1) & 1, (cell >> 2) & 1


def physical_output(n):
    """Return (chip, output_name, pin_number) carrying logical output n."""
    if not 0 <= n < BUS_BITS:
        raise ValueError("n must be 0..15")
    return ("SR1" if n < 8 else "SR2"), _Q_NAMES[n % 8], _Q_PINS[n % 8]


def drv_input(dot):
    """Return (chip_in_cell, in1_pin_name, in2_pin_name) for braille dot 1..6.

    chip_in_cell is 0..2. Even dot indexes use bridge A, odd use bridge B.
    """
    in1, _ = dot_bits(dot)
    d = dot - 1
    bridge = "A" if d % 2 == 0 else "B"
    return in1 // 4, bridge + "IN1", bridge + "IN2"
