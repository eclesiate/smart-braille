"""Tests for the Pico firmware logic, run on a fake hardware layer.

The fake records every hardware call and checks the coil-safety rules on
each one, so any sequence the driver produces is checked, not only the
ones a test happens to look at.
"""

import types

import pytest

import dotmap
import frames
from controller import Controller
from driver import CellDriver, DriveError
from smartbraille import display, protocol
from smartbraille.paging import Beep, Button


def make_config(**overrides):
    cfg = types.SimpleNamespace(
        PULSE_MS=7, PULSE_CAP_MS=9, WAKE_MS=2, GAP_MS=2, MAX_DOTS_PER_PULSE=6,
        INVERT=[0] * 8, WDT_TIMEOUT_MS=1000,
    )
    # 7 and 9 ms are arbitrary test values, not coil recommendations.
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


class FakeHal:
    def __init__(self, vm=True, fault_on_cell=None):
        self.word = 0
        self.driven = False
        self.enabled = False
        self.cell = 0
        self.vm = vm
        self.fault_on_cell = fault_on_cell
        self.pulses = []  # (cell, word, duration_ms)
        self.feeds = 0
        self._pulse_ms = 0
        self._awake_ms = 0

    # --- hal interface ---
    def write_bus(self, word):
        assert 0 <= word < 1 << 16
        if self.driven:
            assert not self.enabled or word == self.word, "bus changed mid-pulse"
        self.word = word

    def bus_drive(self, on):
        if on:
            assert self.enabled, "bus driven with no cell awake"
            assert self._awake_ms >= 1, "bus driven before the driver woke"
            self._pulse_ms = 0
        elif self.driven and self.enabled:
            self.pulses.append((self.cell, self.word, self._pulse_ms))
        self.driven = on

    def select_cell(self, cell):
        assert not self.enabled, "address changed while a cell was awake"
        assert 0 <= cell < 8
        self.cell = cell

    def cell_enable(self, on):
        if on:
            assert not self.driven, "cell woken with the bus already driven"
            self._awake_ms = 0
        elif self.driven and self.enabled:
            # Putting the cell to sleep ends the pulse.
            self.pulses.append((self.cell, self.word, self._pulse_ms))
        self.enabled = on

    def sleep_ms(self, ms):
        if self.enabled:
            self._awake_ms += ms
            if self.driven:
                self._pulse_ms += ms

    def vm_ok(self):
        return self.vm

    def fault(self):
        return self.fault_on_cell == self.cell

    def feed(self):
        self.feeds += 1

    # --- helpers ---
    @property
    def idle(self):
        return not self.enabled and not self.driven and self.word == 0


def moved(hal):
    """Reconstruct what each pulse did: {cell: (up_mask, down_mask)}."""
    result = {}
    for cell, word, _ in hal.pulses:
        up, down = result.get(cell, (0, 0))
        for d in range(6):
            if word & (1 << (2 * d)):
                up |= 1 << d
            if word & (1 << (2 * d + 1)):
                down |= 1 << d
        result[cell] = (up, down)
    return result


def test_starts_in_the_safe_state():
    hal = FakeHal()
    CellDriver(hal, make_config())
    assert hal.idle and hal.pulses == []


def test_first_frame_drives_every_dot_of_every_cell():
    hal = FakeHal()
    driver = CellDriver(hal, make_config())
    driver.show([0b000101] + [0] * 7)
    result = moved(hal)
    assert result[0] == (0b000101, 0b111010)
    assert all(result[c] == (0, 0b111111) for c in range(1, 8))
    assert hal.idle


def test_later_frames_pulse_only_changed_dots():
    hal = FakeHal()
    driver = CellDriver(hal, make_config())
    driver.show([0b000101] + [0] * 7)
    hal.pulses.clear()
    driver.show([0b000110] + [0] * 7)
    assert moved(hal) == {0: (0b000010, 0b000001)}
    hal.pulses.clear()
    driver.show([0b000110] + [0] * 7)
    assert hal.pulses == []


def test_every_pulse_lasts_exactly_pulse_ms_and_never_brakes():
    hal = FakeHal()
    driver = CellDriver(hal, make_config())
    for pattern in range(64):
        driver.show([pattern, 63 - pattern] * 4)
    assert hal.pulses
    for _, word, duration in hal.pulses:
        assert duration == 7
        assert word < 1 << 12
        for d in range(6):
            assert (word >> (2 * d)) & 0b11 != 0b11
    assert hal.idle


def test_dry_run_when_pulse_length_is_not_set():
    for cfg in (make_config(PULSE_MS=None), make_config(PULSE_CAP_MS=None)):
        hal = FakeHal()
        driver = CellDriver(hal, cfg)
        assert driver.dry_run
        driver.show([63] * 8)
        assert hal.pulses == [] and hal.idle
        assert driver.state == [63] * 8


def test_refuses_a_pulse_longer_than_the_cap():
    hal = FakeHal()
    driver = CellDriver(hal, make_config(PULSE_MS=10, PULSE_CAP_MS=9))
    with pytest.raises(DriveError):
        driver.show([1] * 8)
    assert hal.pulses == [] and hal.idle


def test_refuses_to_pulse_without_coil_supply():
    hal = FakeHal(vm=False)
    driver = CellDriver(hal, make_config())
    with pytest.raises(DriveError):
        driver.show([1] * 8)
    assert hal.pulses == [] and hal.idle


def test_fault_returns_to_safe_and_forgets_that_cells_position():
    hal = FakeHal(fault_on_cell=2)
    driver = CellDriver(hal, make_config())
    with pytest.raises(DriveError):
        driver.show([1] * 8)
    assert hal.idle
    assert driver.state[:3] == [1, 1, None]


def test_exception_inside_a_pulse_still_ends_safe():
    class Exploding(FakeHal):
        def sleep_ms(self, ms):
            super().sleep_ms(ms)
            if self.driven:
                raise RuntimeError("boom")

    hal = Exploding()
    driver = CellDriver(hal, make_config())
    with pytest.raises(RuntimeError):
        driver.show([1] * 8)
    assert hal.idle


def test_max_dots_per_pulse_splits_a_cell_into_several_pulses():
    hal = FakeHal()
    driver = CellDriver(hal, make_config(MAX_DOTS_PER_PULSE=2))
    driver.show([0b111111] + [0] * 7)
    cell0 = [word for cell, word, _ in hal.pulses if cell == 0]
    assert len(cell0) == 3
    assert all(bin(word).count("1") == 2 for word in cell0)
    assert moved(hal)[0] == (0b111111, 0)


def test_invert_mask_swaps_polarity():
    hal = FakeHal()
    cfg = make_config(INVERT=[0b000001] + [0] * 7)
    CellDriver(hal, cfg).show([0b000001] + [0] * 7)
    cell0_word = next(word for cell, word, _ in hal.pulses if cell == 0)
    assert cell0_word & 0b11 == 0b10  # dot 1 "up" now uses IN2


def test_watchdog_is_fed_after_every_pulse():
    hal = FakeHal()
    CellDriver(hal, make_config()).show([63] * 8)
    assert hal.feeds == len(hal.pulses) == 8


# --- protocol: Jetson encoder against the Pico parser ---

def feed_all(parser, data):
    return [e for e in (parser.feed(b) for b in data) if e is not None]


def test_parser_accepts_what_the_jetson_sends():
    cells = [1, 3, 9, 0, 63, 32, 2, 3]  # includes bytes equal to STX and ETX
    assert feed_all(frames.Parser(), protocol.encode_frame(cells)) == [("frame", cells)]


def test_parser_rejects_corruption_and_recovers():
    good = protocol.encode_frame([1, 2, 3, 4, 5, 6, 7, 8])
    bad = bytes(good[:4]) + bytes([good[4] ^ 1]) + bytes(good[5:])
    parser = frames.Parser()
    assert feed_all(parser, bad) == [("bad",)]
    assert feed_all(parser, b"\xff\x00" + good) == [("frame", [1, 2, 3, 4, 5, 6, 7, 8])]


def test_parser_rejects_a_cell_byte_above_63():
    raw = bytes([frames.STX, 64, 0, 0, 0, 0, 0, 0, 0, 64, frames.ETX])
    assert feed_all(frames.Parser(), raw) == [("bad",)]


def test_parser_beep_command():
    for beep, pattern in protocol.BEEP_PATTERN.items():
        assert feed_all(frames.Parser(), protocol.encode_beep(beep)) == [("beep", pattern)]
    assert protocol.encode_beep(Beep.OK) == b""


def test_constants_match_on_both_sides():
    for name in ("STX", "ETX", "ACK", "NAK", "BEL", "CELLS"):
        assert getattr(frames, name) == getattr(protocol, name)


# --- whole link: Jetson SerialDisplay <-> Pico Controller ---

class Link:
    """A fake serial port whose far end is the firmware's Controller."""

    def __init__(self, cfg=None, hal=None):
        self.hal = hal or FakeHal()
        self.rx = bytearray()
        self.beeps = []
        driver = CellDriver(self.hal, cfg or make_config())
        self.controller = Controller(driver, self.rx.append, self.beeps.append, "SBNP", 20)

    def write(self, data):
        for byte in data:
            self.controller.on_byte(byte)

    def read(self, n):
        data = bytes(self.rx[:n])
        del self.rx[:n]
        return data

    @property
    def in_waiting(self):
        return len(self.rx)


def test_frame_from_the_jetson_moves_the_cells_and_is_acked():
    link = Link()
    serial = display.SerialDisplay(link, ack_timeout_s=0.05)
    serial.show([0b000001, 0b000011] + [0] * 6)
    assert link.controller.driver.state == [1, 3, 0, 0, 0, 0, 0, 0]
    assert moved(link.hal)[1] == (0b000011, 0b111100)


def test_drive_failure_is_reported_as_nak_and_the_jetson_gives_up():
    link = Link(hal=FakeHal(vm=False))
    serial = display.SerialDisplay(link, ack_timeout_s=0.05, retries=1)
    with pytest.raises(TimeoutError):
        serial.show([1] * 8)
    assert link.controller.last_error == "coil supply missing"


def test_button_press_is_debounced_beeps_and_reaches_the_jetson():
    link = Link()
    serial = display.SerialDisplay(link, ack_timeout_s=0.05)
    released = {"S": 1, "B": 1, "N": 1, "P": 1}
    pressed = dict(released, N=0)
    link.controller.on_buttons(pressed, 0)
    link.controller.on_buttons(released, 5)  # a bounce
    link.controller.on_buttons(pressed, 8)
    link.controller.on_buttons(pressed, 20)
    assert serial.poll_buttons() == []
    link.controller.on_buttons(pressed, 28)
    link.controller.on_buttons(pressed, 500)  # held: still one press
    assert serial.poll_buttons() == [Button.NEXT]
    assert link.beeps == [0]


def test_jetson_beep_reaches_the_buzzer():
    link = Link()
    serial = display.SerialDisplay(link, ack_timeout_s=0.05)
    serial.beep(Beep.READY)
    serial.beep(Beep.OK)  # no command: the Pico already beeped on the press
    assert link.beeps == [1]
