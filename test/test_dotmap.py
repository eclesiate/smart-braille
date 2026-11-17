"""Tests for firmware/pico/dotmap.py.

The chain-order tests use an independent bit-level model of two chained
74HC595s, so a reversed bit order in dotmap.py fails here instead of on
the bench.
"""

import pytest

import dotmap


class HC595:
    """One 74HC595: SER shifts into QA, and data moves QA -> QH -> QH'."""

    def __init__(self):
        self.shift = [0] * 8  # index 0 = QA ... 7 = QH
        self.latch = [0] * 8

    def clock(self, ser):
        carry = self.shift[7]  # QH' before the clock edge
        self.shift = [ser] + self.shift[:7]
        return carry

    def rclk(self):
        self.latch = list(self.shift)


def shift_out(data):
    """Send bytes MSB first into SR1, with SR1.QH' feeding SR2.SER."""
    sr1, sr2 = HC595(), HC595()
    for byte in data:
        for i in range(7, -1, -1):
            bit = (byte >> i) & 1
            sr2.clock(sr1.clock(bit))
    sr1.rclk()
    sr2.rclk()
    return sr1.latch + sr2.latch  # logical outputs 0..15


def outputs_for(word):
    return shift_out(dotmap.spi_bytes(word))


def test_each_word_bit_lands_on_its_logical_output():
    for n in range(dotmap.BUS_BITS):
        outputs = outputs_for(1 << n)
        assert outputs == [1 if i == n else 0 for i in range(16)]


def test_physical_output_table():
    assert dotmap.physical_output(0) == ("SR1", "QA", 15)
    assert dotmap.physical_output(1) == ("SR1", "QB", 1)
    assert dotmap.physical_output(7) == ("SR1", "QH", 7)
    assert dotmap.physical_output(8) == ("SR2", "QA", 15)
    assert dotmap.physical_output(15) == ("SR2", "QH", 7)
    seen = {dotmap.physical_output(n)[:2] for n in range(16)}
    assert len(seen) == 16


def test_dot_bits_are_distinct_and_within_the_12_used_bits():
    bits = []
    for dot in range(1, 7):
        in1, in2 = dotmap.dot_bits(dot)
        assert in2 == in1 + 1
        bits += [in1, in2]
    assert sorted(bits) == list(range(12))


def test_drv_input_assignment():
    assert dotmap.drv_input(1) == (0, "AIN1", "AIN2")
    assert dotmap.drv_input(2) == (0, "BIN1", "BIN2")
    assert dotmap.drv_input(3) == (1, "AIN1", "AIN2")
    assert dotmap.drv_input(4) == (1, "BIN1", "BIN2")
    assert dotmap.drv_input(5) == (2, "AIN1", "AIN2")
    assert dotmap.drv_input(6) == (2, "BIN1", "BIN2")


def test_bus_word_up_and_down():
    # Dot 1 up: IN1 of dot 1 (bit 0). Dot 1 down: IN2 (bit 1).
    assert dotmap.bus_word(0b000001, 0) == 0b01
    assert dotmap.bus_word(0, 0b000001) == 0b10
    # Dot 6 up is bit 10, dot 6 down is bit 11.
    assert dotmap.bus_word(0b100000, 0) == 1 << 10
    assert dotmap.bus_word(0, 0b100000) == 1 << 11
    # Dots 1 and 4 up, dot 2 down.
    assert dotmap.bus_word(0b001001, 0b000010) == (1 << 0) | (1 << 6) | (1 << 3)


def test_bus_word_invert_swaps_polarity_for_that_dot_only():
    assert dotmap.bus_word(0b000011, 0, invert=0b000001) == (1 << 1) | (1 << 2)
    assert dotmap.bus_word(0, 0b000001, invert=0b000001) == 1 << 0


def test_no_word_ever_brakes_or_touches_spare_bits():
    for up in range(64):
        for down in range(64):
            if up & down:
                continue
            for invert in (0, 0b101010, 0b111111):
                word = dotmap.bus_word(up, down, invert)
                assert word < (1 << 12)
                for d in range(6):
                    pair = (word >> (2 * d)) & 0b11
                    assert pair != 0b11
                    moving = bool((up | down) & (1 << d))
                    assert (pair != 0) == moving


def test_bus_word_rejects_a_dot_in_both_masks():
    with pytest.raises(ValueError):
        dotmap.bus_word(0b000001, 0b000001)
    with pytest.raises(ValueError):
        dotmap.bus_word(0b1000000, 0)


def test_changed_dots_only_pulses_differences():
    assert dotmap.changed_dots(0b000000, 0b000000) == (0, 0)
    assert dotmap.changed_dots(0b000111, 0b000111) == (0, 0)
    assert dotmap.changed_dots(0b000000, 0b111111) == (0b111111, 0)
    assert dotmap.changed_dots(0b111111, 0b000000) == (0, 0b111111)
    assert dotmap.changed_dots(0b000101, 0b000110) == (0b000010, 0b000001)


def test_cell_address():
    assert dotmap.cell_address(0) == (0, 0, 0)
    assert dotmap.cell_address(1) == (1, 0, 0)
    assert dotmap.cell_address(6) == (0, 1, 1)
    assert dotmap.cell_address(7) == (1, 1, 1)
    with pytest.raises(ValueError):
        dotmap.cell_address(8)


def test_end_to_end_dot_reaches_the_right_595_pin():
    # Dot 5 up -> bus bit 8 -> SR2 QA (pin 15) -> chip 2 of the cell, AIN1.
    word = dotmap.bus_word(0b010000, 0)
    outputs = outputs_for(word)
    assert outputs.index(1) == 8 and sum(outputs) == 1
    assert dotmap.physical_output(8) == ("SR2", "QA", 15)
    assert dotmap.drv_input(5) == (2, "AIN1", "AIN2")
