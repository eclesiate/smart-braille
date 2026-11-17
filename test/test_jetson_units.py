"""Unit tests for the Jetson software that need no camera or display."""

import pytest

from smartbraille import braille, display, metrics, protocol
from smartbraille.paging import Beep, Button, Reader, paginate


# --- metrics -----------------------------------------------------------

def test_edit_distance_known_values():
    assert metrics.edit_distance("kitten", "sitting") == 3
    assert metrics.edit_distance("", "abc") == 3
    assert metrics.edit_distance("abc", "") == 3
    assert metrics.edit_distance("flaw", "lawn") == 2
    assert metrics.edit_distance("same", "same") == 0
    assert metrics.edit_distance("abc", "xabcx") == 2


def test_cer_ignores_line_breaks_and_scales_by_reference_length():
    assert metrics.cer("hello world", "hello\n  world") == 0.0
    assert metrics.cer("abcdefghij", "abcdefghiX") == pytest.approx(0.1)
    assert metrics.cer("", "") == 0.0


# --- braille -----------------------------------------------------------

def test_letters_translate_to_their_dot_patterns():
    t = braille.translate("abc")
    assert [braille.to_dots(c) for c in t.cells] == [(1,), (1, 2), (1, 4)]
    assert braille.to_unicode(t.cells) == "⠁⠃⠉"


def test_capital_and_number_take_an_extra_cell():
    capital = braille.translate("A")
    assert [braille.to_dots(c) for c in capital.cells] == [(6,), (1,)]
    number = braille.translate("1")
    assert [braille.to_dots(c) for c in number.cells] == [(3, 4, 5, 6), (1,)]


def test_whitespace_collapses_and_every_cell_maps_to_a_source_character():
    t = braille.translate("Hi\n\n  there\tyou")
    assert t.text == "Hi there you"
    assert len(t.source_index) == len(t.cells)
    assert all(0 <= i < len(t.text) for i in t.source_index)
    assert all(0 <= c < 64 for c in t.cells)
    assert t.cells.count(braille.BLANK) == 2


def test_empty_text_gives_no_cells():
    assert braille.translate("  \n ").cells == []


# --- paging ------------------------------------------------------------

def cells_for(text):
    return braille.translate(text).cells


def shown(windows):
    return [braille.to_unicode(w.cells) for w in windows]


def test_paginate_breaks_at_word_boundaries_and_pads():
    windows = paginate(cells_for("the cat sat on a mat"))
    assert shown(windows) == ["⠞⠓⠑⠀⠉⠁⠞⠀", "⠎⠁⠞⠀⠕⠝⠀⠁", "⠍⠁⠞⠀⠀⠀⠀⠀"]
    assert all(len(w.cells) == 8 for w in windows)


def test_paginate_splits_a_word_longer_than_the_display():
    windows = paginate(cells_for("extraordinary"))
    assert [len(w.cells) for w in windows] == [8, 8]
    assert windows[0].end - windows[0].start == 8
    assert windows[1].end - windows[1].start == 5


def test_paginate_covers_every_non_blank_cell_once_in_order():
    cells = cells_for("A refreshable display raises and lowers its pins, 8 cells at a time.")
    windows = paginate(cells)
    covered = [c for w in windows for c in cells[w.start:w.end] if c != 0]
    assert covered == [c for c in cells if c != 0]
    for w in windows:
        assert w.cells[0] != 0


def test_paginate_empty():
    assert paginate([]) == []
    assert paginate([0, 0, 0]) == []


def test_reader_scan_next_back_and_limits():
    reader = Reader()
    out = reader.press(Button.SCAN, now=0.0)
    assert out.scan and out.beep is Beep.OK
    out = reader.load(cells_for("the cat sat on a mat"))
    assert out.beep is Beep.READY and out.window is reader.windows[0]

    assert reader.press(Button.BACK, 1.0).beep is Beep.LIMIT
    assert reader.press(Button.NEXT, 2.0).window is reader.windows[1]
    assert reader.press(Button.NEXT, 3.0).window is reader.windows[2]
    assert reader.press(Button.NEXT, 4.0).beep is Beep.LIMIT
    assert reader.index == 2
    assert reader.press(Button.BACK, 5.0).window is reader.windows[1]


def test_reader_buttons_before_any_scan_only_beep():
    reader = Reader()
    for button in (Button.NEXT, Button.BACK, Button.PLAY_PAUSE):
        out = reader.press(button, 0.0)
        assert out.window is None and out.beep is Beep.LIMIT


def test_reader_scan_with_no_text_reports_an_error_and_blanks_the_display():
    reader = Reader()
    out = reader.load([])
    assert out.beep is Beep.ERROR
    assert out.window.cells == [0] * 8


def test_reader_play_advances_on_time_and_stops_at_the_end():
    reader = Reader(auto_advance_s=3.0)
    reader.load(cells_for("the cat sat on a mat"))
    reader.press(Button.PLAY_PAUSE, 10.0)
    assert reader.tick(12.9).window is None
    assert reader.tick(13.0).window is reader.windows[1]
    assert reader.tick(15.9).window is None
    assert reader.tick(16.0).window is reader.windows[2]
    out = reader.tick(19.0)
    assert out.beep is Beep.LIMIT and not reader.playing
    assert reader.tick(30.0).window is None


def test_reader_pause_stops_advancing_and_manual_next_restarts_the_timer():
    reader = Reader(auto_advance_s=3.0)
    reader.load(cells_for("the cat sat on a mat"))
    reader.press(Button.PLAY_PAUSE, 0.0)
    reader.press(Button.NEXT, 2.0)
    assert reader.tick(3.5).window is None  # timer restarted at 2.0
    reader.press(Button.PLAY_PAUSE, 4.0)
    assert reader.tick(100.0).window is None
    assert reader.index == 1


# --- protocol and serial display --------------------------------------

def test_frame_layout_and_round_trip():
    cells = [1, 3, 9, 0, 63, 32, 0, 0]
    frame = protocol.encode_frame(cells)
    assert len(frame) == 11
    assert frame[0] == 0x02 and frame[-1] == 0x03
    assert frame[9] == 1 ^ 3 ^ 9 ^ 63 ^ 32
    assert protocol.decode_frame(frame) == cells


def test_frame_rejects_bad_input():
    with pytest.raises(ValueError):
        protocol.encode_frame([0] * 7)
    with pytest.raises(ValueError):
        protocol.encode_frame([64] + [0] * 7)
    good = bytearray(protocol.encode_frame([1, 2, 3, 4, 5, 6, 7, 8]))
    corrupted = bytes(good[:3] + bytes([good[3] ^ 0x10]) + good[4:])
    with pytest.raises(ValueError):
        protocol.decode_frame(corrupted)
    with pytest.raises(ValueError):
        protocol.decode_frame(bytes(good[:-1]))


class FakePort:
    """Stands in for pyserial: replies are queued per write."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.written = []
        self.rx = bytearray()

    def write(self, data):
        self.written.append(bytes(data))
        if self.replies:
            self.rx += self.replies.pop(0)

    def read(self, n):
        data, self.rx = bytes(self.rx[:n]), self.rx[n:]
        return data

    @property
    def in_waiting(self):
        return len(self.rx)


def test_serial_display_sends_one_frame_when_acked():
    port = FakePort([b"\x06"])
    display.SerialDisplay(port, ack_timeout_s=0.05).show([1] * 8)
    assert port.written == [protocol.encode_frame([1] * 8)]


def test_serial_display_retries_after_nak_then_gives_up():
    port = FakePort([b"\x15", b"\x06"])
    display.SerialDisplay(port, ack_timeout_s=0.05).show([2] * 8)
    assert len(port.written) == 2

    silent = FakePort([])
    with pytest.raises(TimeoutError):
        display.SerialDisplay(silent, ack_timeout_s=0.02, retries=1).show([0] * 8)
    assert len(silent.written) == 2


def test_serial_display_keeps_button_presses_that_arrive_before_the_ack():
    port = FakePort([b"N\x06"])
    d = display.SerialDisplay(port, ack_timeout_s=0.05)
    d.show([0] * 8)
    port.rx += b"SB"
    assert d.poll_buttons() == [Button.NEXT, Button.SCAN, Button.BACK]
    assert d.poll_buttons() == []


def test_render_draws_three_rows_of_dots():
    assert display.render([0b000001, 0b111111]) == "o. oo\n.. oo\n.. oo"
