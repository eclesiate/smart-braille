"""Settings for the display firmware. Edit this file, not the code.

COIL TIMING MUST COME FROM MEASUREMENTS. PULSE_MS and PULSE_CAP_MS are
None until someone has measured a real cell and written the numbers in
hardware/cell/MEASUREMENTS.md. While either is None the firmware accepts
frames and tracks state but never wakes a driver ("dry run").
"""

# Pulse length that flips a dot reliably, in ms. Measured, not guessed.
PULSE_MS = None
# Longest pulse the coil tolerates, in ms. Measured. PULSE_MS above this is refused.
PULSE_CAP_MS = None

# DRV8833 wake time after nSLEEP rises: datasheet says up to 1 ms (p11).
WAKE_MS = 2
# Rest between pulses, for the supply to recover.
GAP_MS = 2
# Most dots driven in one pulse. Lower it if the supply sags; the firmware
# then splits a cell's change into several pulses.
MAX_DOTS_PER_PULSE = 6

# Per-cell polarity masks (bit 0 = dot 1). Set a bit if that dot moves the
# wrong way.
INVERT = [0, 0, 0, 0, 0, 0, 0, 0]

# VM monitor on GP26. VM_DIVIDER is (top + bottom) / bottom of the resistor
# divider; both stay None until the divider is designed, which disables
# the check.
VM_DIVIDER = None
VM_MIN_V = None

SPI_BAUD = 1_000_000
WDT_TIMEOUT_MS = 1000
DEBOUNCE_MS = 20
BEEP_MS = 60
BUZZER_ACTIVE_HIGH = True

# Pins (see hardware/pcb/README.md, "Pico pin map").
PIN_ADDR = (2, 3, 4)
PIN_CELL_EN = 5
PIN_BUTTONS = {"S": 10, "B": 11, "N": 12, "P": 13}
PIN_BUZZER = 14
PIN_NFAULT = 15
PIN_SPI_RX = 16
PIN_RCLK = 17
PIN_SPI_SCK = 18
PIN_SPI_TX = 19
PIN_NOE = 20
PIN_NSRCLR = 21
PIN_VM_ADC = 26
