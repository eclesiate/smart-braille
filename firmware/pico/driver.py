"""Pulse sequencing for the braille cells.

All hardware access goes through a `hal` object, so this file runs under
pytest with a fake. The hal provides:

    write_bus(word)     shift a 16-bit word into the 74HC595s and latch it
    bus_drive(on)       on=True pulls /OE low (bus driven); False = high-Z
    select_cell(cell)   set the 74HC238 address lines
    cell_enable(on)     CELL_EN: on=True wakes the selected cell's drivers
    sleep_ms(ms)
    vm_ok()             False if the coil supply is known to be missing
    fault()             True if nFAULT is asserted
    feed()              feed the watchdog

Safety rules enforced here:
- One cell at a time. The address only changes while CELL_EN is low.
- The bus is high-Z except during a pulse.
- A pulse lasts PULSE_MS, which must be set and must not exceed
  PULSE_CAP_MS. With either unset, no driver is ever woken.
- Whatever happens inside a pulse, the outputs are returned to the safe
  state before the error propagates.
"""

import dotmap


class DriveError(Exception):
    pass


class CellDriver:
    def __init__(self, hal, config):
        self.hal = hal
        self.cfg = config
        # None = position unknown (after power-up the dots are wherever
        # they were left), so the first frame drives every dot.
        self.state = [None] * dotmap.CELLS
        self.safe()

    @property
    def dry_run(self):
        return self.cfg.PULSE_MS is None or self.cfg.PULSE_CAP_MS is None

    def safe(self):
        """Put every output in its idle state."""
        self.hal.cell_enable(False)
        self.hal.bus_drive(False)
        self.hal.write_bus(0)

    def show(self, cells):
        """Move the display to `cells` (8 patterns), one cell at a time."""
        if len(cells) != dotmap.CELLS:
            raise ValueError("need 8 cells")
        self._check_config()
        for cell in range(dotmap.CELLS):
            target = cells[cell] & dotmap.DOT_MASK
            old = self.state[cell]
            if old is None:
                up, down = target, dotmap.DOT_MASK & ~target
            else:
                up, down = dotmap.changed_dots(old, target)
            for part_up, part_down in self._split(up, down):
                self.pulse(cell, part_up, part_down)
                self.hal.sleep_ms(self.cfg.GAP_MS)
                self.hal.feed()
            self.state[cell] = target

    def pulse(self, cell, up, down):
        """Drive the given dots of one cell for one pulse."""
        self._check_config()
        if not up and not down:
            return
        word = dotmap.bus_word(up, down, self.cfg.INVERT[cell])
        if self.dry_run:
            return
        if not self.hal.vm_ok():
            raise DriveError("coil supply missing")
        hal = self.hal
        try:
            hal.cell_enable(False)
            hal.bus_drive(False)
            hal.select_cell(cell)
            hal.cell_enable(True)
            hal.sleep_ms(self.cfg.WAKE_MS)
            hal.write_bus(word)
            hal.bus_drive(True)
            hal.sleep_ms(self.cfg.PULSE_MS)
            fault = hal.fault()
        finally:
            self.safe()
        if fault:
            # Position is no longer known; force a full drive next time.
            self.state[cell] = None
            raise DriveError("driver fault on cell %d" % cell)

    def _check_config(self):
        cfg = self.cfg
        if self.dry_run:
            return
        if cfg.PULSE_MS <= 0 or cfg.PULSE_MS > cfg.PULSE_CAP_MS:
            raise DriveError("PULSE_MS must be above 0 and at most PULSE_CAP_MS")
        if not 1 <= cfg.MAX_DOTS_PER_PULSE <= dotmap.DOTS:
            raise DriveError("MAX_DOTS_PER_PULSE must be 1..6")
        # The watchdog is fed between pulses, so one pulse must fit well inside it.
        if 2 * (cfg.WAKE_MS + cfg.PULSE_MS + cfg.GAP_MS) > cfg.WDT_TIMEOUT_MS:
            raise DriveError("one pulse must take under half of WDT_TIMEOUT_MS")

    def _split(self, up, down):
        """Yield (up, down) groups of at most MAX_DOTS_PER_PULSE dots."""
        limit = self.cfg.MAX_DOTS_PER_PULSE
        part_up = part_down = count = 0
        for d in range(dotmap.DOTS):
            bit = 1 << d
            if not (up | down) & bit:
                continue
            if count == limit:
                yield part_up, part_down
                part_up = part_down = count = 0
            if up & bit:
                part_up |= bit
            else:
                part_down |= bit
            count += 1
        if count:
            yield part_up, part_down
