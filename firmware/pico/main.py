"""SmartBraille display firmware for the Raspberry Pi Pico (MicroPython).

Copy every .py file in this folder to the Pico. This file is the only one
that touches hardware. NOT YET RUN ON A PICO: the logic in the other files
is tested under pytest with fakes, this glue is not.

The USB serial port carries the binary protocol, so nothing may print to
it. Debug text goes to UART0 (GP0, 115200 baud).
"""

import sys

import micropython
import select
import time
from machine import ADC, SPI, UART, WDT, Pin

import config
import dotmap
from controller import Controller
from driver import CellDriver

# Bring the safety-critical outputs to their idle levels before anything else.
cell_en = Pin(config.PIN_CELL_EN, Pin.OUT, value=0)
n_oe = Pin(config.PIN_NOE, Pin.OUT, value=1)
addr = [Pin(p, Pin.OUT, value=0) for p in config.PIN_ADDR]
n_srclr = Pin(config.PIN_NSRCLR, Pin.OUT, value=1)
rclk = Pin(config.PIN_RCLK, Pin.OUT, value=0)
n_fault = Pin(config.PIN_NFAULT, Pin.IN, Pin.PULL_UP)
buzzer = Pin(config.PIN_BUZZER, Pin.OUT, value=0 if config.BUZZER_ACTIVE_HIGH else 1)
button_pins = {name: Pin(p, Pin.IN, Pin.PULL_UP) for name, p in config.PIN_BUTTONS.items()}
spi = SPI(
    0,
    baudrate=config.SPI_BAUD,
    polarity=0,
    phase=0,
    bits=8,
    firstbit=SPI.MSB,
    sck=Pin(config.PIN_SPI_SCK),
    mosi=Pin(config.PIN_SPI_TX),
    miso=Pin(config.PIN_SPI_RX),
)
vm_adc = ADC(config.PIN_VM_ADC)
debug = UART(0, 115200)
wdt = WDT(timeout=config.WDT_TIMEOUT_MS)


def log(message):
    debug.write(message + "\r\n")


class Hal:
    def write_bus(self, word):
        spi.write(dotmap.spi_bytes(word))
        rclk.value(1)
        rclk.value(0)

    def bus_drive(self, on):
        n_oe.value(0 if on else 1)

    def select_cell(self, cell):
        for pin, bit in zip(addr, dotmap.cell_address(cell)):
            pin.value(bit)

    def cell_enable(self, on):
        cell_en.value(1 if on else 0)

    def sleep_ms(self, ms):
        time.sleep_ms(ms)

    def vm_ok(self):
        if config.VM_DIVIDER is None or config.VM_MIN_V is None:
            return True
        volts = vm_adc.read_u16() * 3.3 / 65535 * config.VM_DIVIDER
        return volts >= config.VM_MIN_V

    def fault(self):
        return n_fault.value() == 0

    def feed(self):
        wdt.feed()


def beep(pattern):
    """Pattern 0 = one short beep, n = n + 1 short beeps."""
    on = 1 if config.BUZZER_ACTIVE_HIGH else 0
    for i in range(pattern + 1):
        buzzer.value(on)
        time.sleep_ms(config.BEEP_MS)
        buzzer.value(1 - on)
        if i < pattern:
            time.sleep_ms(config.BEEP_MS)
        wdt.feed()


def send(byte):
    sys.stdout.buffer.write(bytes((byte,)))


def main():
    # Byte 0x03 is the frame's end byte; stop MicroPython treating it as Ctrl-C.
    micropython.kbd_intr(-1)
    driver = CellDriver(Hal(), config)
    controller = Controller(driver, send, beep, list(config.PIN_BUTTONS), config.DEBOUNCE_MS)
    log("SmartBraille display ready" + (" (DRY RUN: pulse length not set)" if driver.dry_run else ""))
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    reported = None
    while True:
        wdt.feed()
        while poll.poll(0):
            controller.on_byte(sys.stdin.buffer.read(1)[0])
        levels = {name: pin.value() for name, pin in button_pins.items()}
        controller.on_buttons(levels, time.ticks_ms())
        if controller.last_error != reported:
            reported = controller.last_error
            log("error: %s" % reported)
        time.sleep_ms(2)


main()
