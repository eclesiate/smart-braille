"""Generate the SmartBraille driver board schematic (rev A draft).

    python hardware/pcb/gen/gen_schematic.py

Writes smartbraille_driver.kicad_sch (root), cell.kicad_sch (one sheet used
eight times), design.json and SCHEMATIC_SUMMARY.md into hardware/pcb/. The circuit is
described here as parts and "pin -> net" maps; check_netlist.py compares
KiCad's own netlist with design.json.

Values marked TBD wait for the cell measurements (hardware/pcb/README.md,
"Open inputs"). Nothing here sets a coil current or a pulse length.
"""

import json
import pathlib

import schgen
import sexpr
from schgen import NC, Sheet
from sexpr import Sym

OUT = pathlib.Path(__file__).resolve().parent.parent
PROJECT = "smartbraille_driver"

BUS = [f"BUS{i}" for i in range(12)]
GLOBAL = {"GND", "VM", "+3V3", "NFAULT", *BUS}
DRV = "smartbraille:DRV8833PWP"

# The stock DRV8833PWP symbol types three pins in a way ERC objects to.
# The project-local copy changes only the electrical type, per the datasheet:
#   VINT (14): output of the internal regulator, needs only a capacitor (p3)
#   AISEN (3), BISEN (6): bridge ground returns, tied to GND here (p4, p10)
DRV_PIN_TYPES = {"14": "power_out", "3": "passive", "6": "passive"}

# Footprints
R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
SOIC16 = "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"
HDR1x2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
HDR1x3 = "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"
HDR2x5 = "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical"
IDC2x6 = "Connector_IDC:IDC-Header_2x06_P2.54mm_Vertical"
TP = "TestPoint:TestPoint_Pad_D1.5mm"

# Pin tables from the datasheets (hardware/pcb/README.md, "Datasheet checks").
# The generator refuses to run if a KiCad library symbol disagrees.
DATASHEET_PINS = {
    DRV: {
        "1": "~{SLEEP}", "2": "AOUT1", "3": "AISEN", "4": "AOUT2", "5": "BOUT2", "6": "BISEN",
        "7": "BOUT1", "8": "~{FAULT}", "9": "BIN1", "10": "BIN2", "11": "VCP", "12": "VM",
        "13": "GND", "14": "VINT", "15": "AIN2", "16": "AIN1", "17": "GND",
    },
    "74xx:74HC595": {
        "1": "QB", "2": "QC", "3": "QD", "4": "QE", "5": "QF", "6": "QG", "7": "QH", "8": "GND",
        "9": "QH'", "10": "~{SRCLR}", "11": "SRCLK", "12": "RCLK", "13": "~{OE}", "14": "SER",
        "15": "QA", "16": "VCC",
    },
    "74xx:74HC238": {
        "1": "A0", "2": "A1", "3": "A2", "4": "~{E1}", "5": "~{E2}", "6": "E3", "7": "Y7",
        "8": "GND", "9": "Y6", "10": "Y5", "11": "Y4", "12": "Y3", "13": "Y2", "14": "Y1",
        "15": "Y0", "16": "VCC",
    },
    "74xGxx:74LVC1G123": {
        "1": "~{A}", "2": "B", "3": "~{CLR}", "4": "GND", "5": "Q", "6": "Cext", "7": "RCext",
        "8": "VCC",
    },
}
PICO_GPIO_PINS = {
    0: "1", 1: "2", 2: "4", 3: "5", 4: "6", 5: "7", 6: "9", 7: "10", 8: "11", 9: "12",
    10: "14", 11: "15", 12: "16", 13: "17", 14: "19", 15: "20", 16: "21", 17: "22", 18: "24",
    19: "25", 20: "26", 21: "27", 22: "29", 26: "31", 27: "32", 28: "34",
}


def make_project_symbols():
    """Build the project-local symbol library and register it with schgen."""
    stock = schgen.load_symbol("Driver_Motor:DRV8833PWP")
    patched = [Sym("symbol"), DRV]
    for item in stock[2:]:
        if isinstance(item, list) and item[0] == "symbol":
            unit = []
            for sub in item:
                if isinstance(sub, list) and sub[0] == "pin":
                    number = sexpr.find(sub, "number")[1]
                    if number in DRV_PIN_TYPES:
                        sub = [sub[0], Sym(DRV_PIN_TYPES[number])] + sub[2:]
                unit.append(sub)
            item = unit
        patched.append(item)
    schgen.CUSTOM[DRV] = patched
    in_file = list(patched)
    in_file[1] = "DRV8833PWP"
    lib = [Sym("kicad_symbol_lib"), [Sym("version"), 20251024], [Sym("generator"), "smartbraille_gen"],
           [Sym("generator_version"), "10.0"], in_file]
    (OUT / "smartbraille.kicad_sym").write_text(sexpr.dump(lib) + "\n")


def write_library_tables(sheets):
    """Project library tables, so the project opens the same on any machine."""
    sym_libs, fp_libs = set(), set()
    for sheet in sheets:
        for lib_id in sheet.lib_symbols:
            sym_libs.add(lib_id.split(":")[0])
        for _refs, _unit, node in sheet.parts:
            for prop in sexpr.find_all(node, "property"):
                if prop[1] == "Footprint" and ":" in prop[2]:
                    fp_libs.add(prop[2].split(":")[0])
    lines = ["(sym_lib_table", "\t(version 7)"]
    for name in sorted(sym_libs):
        uri = "${KIPRJMOD}/smartbraille.kicad_sym" if name == "smartbraille" else "${KICAD10_SYMBOL_DIR}/%s.kicad_sym" % name
        lines.append('\t(lib (name "%s") (type "KiCad") (uri "%s") (options "") (descr ""))' % (name, uri))
    (OUT / "sym-lib-table").write_text("\n".join(lines) + "\n)\n")
    lines = ["(fp_lib_table", "\t(version 7)"]
    for name in sorted(fp_libs):
        lines.append('\t(lib (name "%s") (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/%s.pretty") (options "") (descr ""))' % (name, name))
    (OUT / "fp-lib-table").write_text("\n".join(lines) + "\n)\n")


def check_library_pins():
    for lib_id, expected in DATASHEET_PINS.items():
        actual = {p[0]: p[1] for p in schgen.symbol_pins(schgen.load_symbol(lib_id))}
        if actual != expected:
            raise SystemExit(f"{lib_id}: library symbol pins differ from the datasheet table: {actual}")
    pico = {p[0]: p[1] for p in schgen.symbol_pins(schgen.load_symbol("MCU_Module:RaspberryPi_Pico"))}
    for gpio, pin in PICO_GPIO_PINS.items():
        if not pico[pin].startswith(f"GPIO{gpio}"):
            raise SystemExit(f"Pico pin {pin} is {pico[pin]}, expected GPIO{gpio}")
    for pin, name in {"36": "3V3", "40": "VBUS", "39": "VSYS", "30": "RUN", "33": "AGND"}.items():
        if pico[pin] != name:
            raise SystemExit(f"Pico pin {pin} is {pico[pin]}, expected {name}")


class Refs:
    """Hands out reference designators."""

    def __init__(self, base=0):
        self.base = base
        self.counts = {}

    def __call__(self, prefix):
        self.counts[prefix] = self.counts.get(prefix, 0) + 1
        return f"{prefix}{self.base + self.counts[prefix]}"


def resistor(sheet, ref, value, x, y, a, b, **kw):
    sheet.place("Device:R", ref, value, x, y, {"1": a, "2": b}, rot=90, footprint=R0603, **kw)


def capacitor(sheet, ref, value, x, y, a, b, footprint=C0603, **kw):
    sheet.place("Device:C", ref, value, x, y, {"1": a, "2": b}, rot=90, footprint=footprint, **kw)


def testpoint(sheet, ref, net, x, y):
    sheet.place("Connector:TestPoint", ref, "TP", x, y, {"1": net}, footprint=TP, in_bom=False)


# ---------------------------------------------------------------------------
# Cell sheet: three DRV8833, their capacitors, the cell connector.
# ---------------------------------------------------------------------------

def build_cell():
    sheet = Sheet(PROJECT, "cell", "A3", "Braille cell driver (one of eight)",
                  global_nets=GLOBAL, hier_nets={"NSLEEP": "input"})

    def refs(prefix, n):
        # Cell c (0..7) uses references (c+1)01, (c+1)02, ...
        return [f"{prefix}{(c + 1) * 100 + n}" for c in range(8)]

    sheet.text("Three dual H-bridges drive the six coils of one cell. The IN pins are the shared bus;", 25, 20)
    sheet.text("only the cell whose NSLEEP is high acts on it. ISEN pins grounded: no current chopping.", 25, 25)

    cap = 0
    for k in range(3):
        x, y = 80 + 125 * k, 80
        dot_a, dot_b = 2 * k + 1, 2 * k + 2
        vcp, vint = f"VCP{k}", f"VINT{k}"
        sheet.text(f"Dots {dot_a} and {dot_b}", x - 12, y - 28)
        sheet.place(
            DRV, refs("U", k + 1), "DRV8833PWP", x, y,
            {
                "1": "NSLEEP",
                "16": BUS[4 * k], "15": BUS[4 * k + 1], "9": BUS[4 * k + 2], "10": BUS[4 * k + 3],
                "3": "GND", "6": "GND",
                "11": vcp, "12": "VM", "14": vint, "13": "GND", "17": "GND",
                "8": "NFAULT",
                "2": f"D{dot_a}A", "4": f"D{dot_a}B", "7": f"D{dot_b}A", "5": f"D{dot_b}B",
            },
            fields={"LCSC": "C50506"},
        )
        cy = y + 40
        for value, a, b, fp in (
            ("10u 25V", "VM", "GND", C0805),
            ("100n", "VM", "GND", C0603),
            ("10n 50V X7R", vcp, "VM", C0603),
            ("2u2 10V", vint, "GND", C0603),
        ):
            cap += 1
            capacitor(sheet, refs("C", cap), value, x, cy, a, b, footprint=fp)
            cy += 10

    sheet.text("Cell connector: pin pairs are dot 1 A/B ... dot 6 A/B", 150, 195)
    sheet.place(
        "Connector_Generic:Conn_02x06_Odd_Even", refs("J", 1), "Cell 2x6", 205, 215,
        {str(2 * d + 1): f"D{d + 1}A" for d in range(6)} | {str(2 * d + 2): f"D{d + 1}B" for d in range(6)},
        footprint=IDC2x6,
    )
    sheet.text("Keeps the drivers asleep with the decoder unpowered", 40, 195)
    resistor(sheet, refs("R", 1), "10k", 70, 205, "NSLEEP", "GND")
    testpoint(sheet, refs("TP", 1), "NSLEEP", 70, 225)
    return sheet


# ---------------------------------------------------------------------------
# Root sheet: Pico, shift registers, decoder, timeout, power, connectors.
# ---------------------------------------------------------------------------

def build_root(cell_sheet):
    sheet = Sheet(PROJECT, "root", "A2", "SmartBraille driver board", global_nets=GLOBAL)
    ref = Refs()
    cell_enables = [f"CELL{c}_NSLEEP" for c in range(8)]

    # --- Pico ---
    sheet.text("Raspberry Pi Pico H or Pico 2 H in two 1x20 sockets. Powered from USB only.", 40, 30)
    gp = {
        0: "UART_TX", 1: "UART_RX", 2: "CELL_A0", 3: "CELL_A1", 4: "CELL_A2", 5: "CELL_EN",
        6: "SPARE_GP6", 7: "SPARE_GP7", 8: "SPARE_GP8", 9: "SPARE_GP9",
        10: "BTN_SCAN", 11: "BTN_BACK", 12: "BTN_NEXT", 13: "BTN_PLAY",
        14: "BUZZER", 15: "NFAULT", 16: "SR_MISO", 17: "SR_RCLK", 18: "SR_SCK_P", 19: "SR_MOSI_P",
        20: "SR_NOE", 21: "SR_NSRCLR", 22: "SPARE_GP22", 26: "VM_SENSE", 27: "SPARE_GP27",
        28: "SPARE_GP28",
    }
    pico = {PICO_GPIO_PINS[g]: net for g, net in gp.items()}
    pico |= {p: "GND" for p in ("3", "8", "13", "18", "23", "28", "38")}
    # AGND joins GND inside the Pico. Here it is only the return for the VM divider.
    pico |= {"33": "AGND", "30": "RUN", "35": NC, "36": "+3V3", "37": NC, "39": NC, "40": "VBUS"}
    sheet.place("MCU_Module:RaspberryPi_Pico", "A1", "Pico H / Pico 2 H", 90, 90, pico,
                footprint="Module:RaspberryPi_Pico_Common_THT")

    # --- shift registers ---
    sheet.text("16-bit bus register. /OE pulled high:", 170, 25)
    sheet.text("bus is high-Z until firmware drives it.", 170, 30)
    resistor(sheet, ref("R"), "33", 185, 40, "SR_SCK_P", "SR_SCK")
    resistor(sheet, ref("R"), "33", 185, 50, "SR_MOSI_P", "SR_MOSI")
    q_pins = ["15", "1", "2", "3", "4", "5", "6", "7"]  # QA..QH
    sr1 = {"14": "SR_MOSI", "11": "SR_SCK", "12": "SR_RCLK", "10": "SR_NSRCLR", "13": "SR_NOE",
           "9": "SR_CHAIN", "16": "+3V3", "8": "GND"}
    sr1 |= {q_pins[i]: BUS[i] for i in range(8)}
    sheet.place("74xx:74HC595", "U1", "74HC595", 200, 85, sr1, footprint=SOIC16, fields={"LCSC": "C5947"})
    spare = [f"SR_SPARE{i}" for i in range(12, 16)]
    sr2 = {"14": "SR_CHAIN", "11": "SR_SCK", "12": "SR_RCLK", "10": "SR_NSRCLR", "13": "SR_NOE",
           "9": "SR_MISO", "16": "+3V3", "8": "GND"}
    sr2 |= {q_pins[i]: BUS[8 + i] for i in range(4)}
    sr2 |= {q_pins[4 + i]: spare[i] for i in range(4)}
    sheet.place("74xx:74HC595", "U2", "74HC595", 200, 140, sr2, footprint=SOIC16, fields={"LCSC": "C5947"})
    capacitor(sheet, ref("C"), "100n", 185, 175, "+3V3", "GND")
    capacitor(sheet, ref("C"), "100n", 185, 185, "+3V3", "GND")
    resistor(sheet, ref("R"), "4k7", 185, 195, "+3V3", "SR_NOE")
    resistor(sheet, ref("R"), "10k", 185, 205, "+3V3", "SR_NSRCLR")
    for i, net in enumerate(spare):
        testpoint(sheet, ref("TP"), net, 235 + 8 * i, 195)

    # --- cell decoder and enable timeout ---
    sheet.text("Cell select. One output high at a time,", 290, 25)
    sheet.text("none unless CELL_EN_G is high.", 290, 30)
    y_pins = ["15", "14", "13", "12", "11", "10", "9", "7"]  # Y0..Y7
    dec = {"1": "CELL_A0", "2": "CELL_A1", "3": "CELL_A2", "4": "GND", "5": "GND", "6": "CELL_EN_G",
           "16": "+3V3", "8": "GND"}
    dec |= {y_pins[c]: cell_enables[c] for c in range(8)}
    sheet.place("74xx:74HC238", "U3", "74HC238", 320, 70, dec, footprint=SOIC16, fields={"LCSC": "C5379113"})
    capacitor(sheet, ref("C"), "100n", 305, 100, "+3V3", "GND")
    resistor(sheet, ref("R"), "10k", 305, 110, "CELL_A0", "GND")
    resistor(sheet, ref("R"), "10k", 305, 120, "CELL_A1", "GND")
    resistor(sheet, ref("R"), "10k", 305, 130, "CELL_A2", "GND")
    resistor(sheet, ref("R"), "4k7", 305, 140, "CELL_EN", "GND")
    resistor(sheet, ref("R"), "10k", 305, 150, "CELL_EN_G", "GND")

    sheet.text("Hardware timeout: CELL_EN rising starts one pulse on Q; CELL_EN low ends it.", 290, 170)
    sheet.text("R and C set the longest time a cell can stay awake. TBD from cell input 5.", 290, 175)
    sheet.text("JP1 as built (1-2) bypasses the timeout. Cut 1-2 and bridge 2-3 to use it.", 290, 180)
    mono_fp = "Package_SO:VSSOP-8_2.3x2mm_P0.5mm"
    sheet.place("74xGxx:74LVC1G123", "U4", "74LVC1G123", 320, 205,
                {"1": "GND", "2": "+3V3", "5": "CELL_EN_TMO", "6": "TMO_CEXT", "7": "TMO_RC", "3": "CELL_EN"},
                footprint=mono_fp, unit=1)
    sheet.place("74xGxx:74LVC1G123", "U4", "74LVC1G123", 370, 205, {"8": "+3V3", "4": "GND"},
                footprint=mono_fp, unit=2)
    resistor(sheet, ref("R"), "TBD (input 5)", 305, 235, "+3V3", "TMO_RC", dnp=True)
    capacitor(sheet, ref("C"), "TBD (input 5)", 305, 245, "TMO_RC", "TMO_CEXT", dnp=True)
    capacitor(sheet, ref("C"), "100n", 305, 255, "+3V3", "GND")
    sheet.place("Jumper:SolderJumper_3_Bridged12", "JP1", "Timeout bypass", 370, 240,
                {"1": "CELL_EN", "2": "CELL_EN_G", "3": "CELL_EN_TMO"},
                footprint="Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm", in_bom=False)
    testpoint(sheet, ref("TP"), "CELL_EN_G", 395, 240)

    # --- fault and VM monitor ---
    sheet.text("Fault line and coil-supply monitor", 40, 185)
    resistor(sheet, ref("R"), "10k", 60, 195, "+3V3", "NFAULT")
    sheet.text("220k / 68k keeps GP26 under 3.3 V up to the DRV8833's 11.8 V limit", 40, 207)
    resistor(sheet, ref("R"), "220k", 60, 215, "VM", "VM_SENSE")
    resistor(sheet, ref("R"), "68k", 60, 225, "VM_SENSE", "AGND")
    capacitor(sheet, ref("C"), "100n", 60, 235, "VM_SENSE", "AGND")

    # --- buttons, buzzer, headers ---
    sheet.text("Buttons: active low, Pico internal pull-ups. Capacitors not fitted.", 40, 255)
    for i, name in enumerate(("SCAN", "BACK", "NEXT", "PLAY")):
        x = 55 + 45 * i
        sheet.place("Connector_Generic:Conn_01x02", ref("J"), name, x, 270,
                    {"1": f"BTN_{name}", "2": "GND"}, footprint=HDR1x2)
        capacitor(sheet, ref("C"), "100n", x, 290, f"BTN_{name}", "GND", dnp=True)

    sheet.text("Buzzer: active 5 V type, switched from USB 5 V", 40, 310)
    resistor(sheet, ref("R"), "1k", 60, 320, "BUZZER", "BUZ_B")
    resistor(sheet, ref("R"), "10k", 60, 330, "BUZ_B", "GND")
    sheet.place("Transistor_BJT:MMBT3904", "Q1", "MMBT3904", 110, 325, {"1": "BUZ_B", "2": "GND", "3": "BUZ_N"})
    sheet.place("Diode:1N4148W", "D1", "1N4148W", 150, 320, {"1": "VBUS", "2": "BUZ_N"})
    sheet.place("Connector_Generic:Conn_01x02", ref("J"), "BUZZER", 190, 325,
                {"1": "VBUS", "2": "BUZ_N"}, footprint=HDR1x2)

    sheet.text("Debug UART, reset, spare GPIO", 40, 350)
    sheet.place("Connector_Generic:Conn_01x03", ref("J"), "UART0", 55, 365,
                {"1": "UART_TX", "2": "UART_RX", "3": "GND"}, footprint=HDR1x3)
    sheet.place("Connector_Generic:Conn_01x02", ref("J"), "RESET", 100, 365,
                {"1": "RUN", "2": "GND"}, footprint=HDR1x2)
    sheet.place("Connector_Generic:Conn_02x05_Odd_Even", ref("J"), "SPARE", 160, 365,
                {"1": "+3V3", "2": "GND", "3": "SPARE_GP6", "4": "SPARE_GP7", "5": "SPARE_GP8",
                 "6": "SPARE_GP9", "7": "SPARE_GP22", "8": "SPARE_GP27", "9": "SPARE_GP28", "10": "GND"},
                footprint=HDR2x5)

    # --- coil supply ---
    sheet.text("Coil supply. Never joins the Pico's VBUS or VSYS.", 420, 25)
    sheet.text("Parts marked TBD wait for cell inputs 2-5.", 420, 30)
    sheet.place("Connector:Barrel_Jack_Switch", "J20", "5.5x2.1 centre positive", 440, 55,
                {"1": "VIN_RAW", "2": "GND", "3": "GND"}, footprint="Connector_BarrelJack:BarrelJack_Horizontal")
    sheet.place("Device:Fuse", "F1", "TBD slow-blow (inputs 4, 5)", 490, 50,
                {"1": "VIN_RAW", "2": "VIN_FUSED"}, rot=90,
                footprint="Fuse:Fuseholder_Clip-5x20mm_Littelfuse_100_Inline_P20.50x4.60mm_D1.30mm_Horizontal")
    sheet.text("Reverse-polarity FET: part to confirm against input 4", 420, 75)
    sheet.place("Transistor_FET:AO3401A", "Q2", "AO3401A (confirm, input 4)", 470, 95,
                {"1": "RP_GATE", "2": "VM", "3": "VIN_FUSED"})
    resistor(sheet, ref("R"), "10k", 440, 120, "RP_GATE", "GND")
    sheet.place("Device:D_Zener", "D2", "TBD (input 3)", 490, 120, {"1": "VM", "2": "RP_GATE"},
                footprint="Diode_SMD:D_SOD-123", dnp=True)
    sheet.place("Device:D_TVS", "D3", "TBD (input 3)", 440, 140, {"1": "VM", "2": "GND"},
                footprint="Diode_SMD:D_SMA", dnp=True)
    sheet.place("Device:C_Polarized", "C20", "TBD bulk (inputs 4, 5)", 490, 140, {"1": "VM", "2": "GND"},
                rot=90, footprint="", dnp=True)
    capacitor(sheet, ref("C"), "100n", 440, 155, "VM", "GND")
    resistor(sheet, ref("R"), "2k2", 440, 170, "VM", "LED_A")
    sheet.place("Device:LED", "D4", "VM on", 490, 170, {"1": "GND", "2": "LED_A"},
                footprint="LED_SMD:LED_0603_1608Metric")
    sheet.flag("VM", 530, 60)

    # --- test points and mounting ---
    sheet.text("Test points", 420, 195)
    for i, net in enumerate(("VM", "GND", "GND", "GND", "+3V3", "VBUS", "SR_SCK", "SR_MOSI",
                             "SR_RCLK", "SR_NOE", "SR_MISO", "NFAULT")):
        testpoint(sheet, ref("TP"), net, 430 + 10 * (i % 12), 215)
    for i in range(4):
        sheet.place("Mechanical:MountingHole", f"H{i + 1}", "M3", 430 + 15 * i, 255, {},
                    footprint="MountingHole:MountingHole_3.2mm_M3", in_bom=False)

    # --- the eight cell sheets ---
    sheet.text("Cells 0..7: each is one copy of cell.kicad_sch", 420, 275)
    boxes = []
    for c in range(8):
        x, y = 430 + 38 * (c % 4), 290 + 40 * (c // 4)
        box_uuid = schgen.uid(PROJECT, "cell-instance", c)
        boxes.append(schgen.sheet_symbol(PROJECT, sheet.uuid, box_uuid, f"Cell{c}", "cell.kicad_sch",
                                         x, y, 20, 12, [("NSLEEP", "input", "left", 5.08)], page=c + 2))
        sheet.connect(x, y + 5.08, 0, cell_enables[c])
    return sheet, boxes


def intended_nets(root, cell):
    """Map 'REF.pin' -> net name, with cell-local nets prefixed by the cell."""
    nets = {}
    for (refs, pin), net in root.netlist.items():
        nets[f"{refs[0]}.{pin}"] = net
    for (refs, pin), net in cell.netlist.items():
        for c in range(8):
            if net in GLOBAL:
                name = net
            elif net == "NSLEEP":
                name = f"CELL{c}_NSLEEP"
            else:
                name = f"Cell{c}/{net}"
            nets[f"{refs[c]}.{pin}"] = name
    return nets


NET_NOTES = {
    "+3V3": "3.3 V from the Pico's regulator. Powers the shift registers, decoder, timeout chip and pull-ups.",
    "GND": "Common ground for logic and coil supply.",
    "AGND": "Pico analog ground. Return for the VM divider only; joined to GND inside the Pico.",
    "VBUS": "USB 5 V from the Pico. Feeds the buzzer only.",
    "VM": "Coil supply after the fuse and reverse-polarity FET. Feeds every DRV8833.",
    "VIN_RAW": "Coil supply straight from the barrel jack.",
    "VIN_FUSED": "Coil supply after the fuse, before the reverse-polarity FET.",
    "RP_GATE": "Gate of the reverse-polarity FET, pulled to GND.",
    "LED_A": "Anode of the 'VM on' LED.",
    "VM_SENSE": "VM divided by 4.24 for the Pico ADC (GP26).",
    "NFAULT": "All 24 DRV8833 fault outputs, wire-OR, pulled up to 3.3 V. To GP15.",
    "SR_SCK_P": "SPI clock at the Pico (GP18), before its series resistor.",
    "SR_MOSI_P": "SPI data at the Pico (GP19), before its series resistor.",
    "SR_SCK": "SPI clock to both shift registers.",
    "SR_MOSI": "SPI data into the first shift register.",
    "SR_CHAIN": "First shift register's serial output into the second.",
    "SR_MISO": "Second shift register's serial output back to the Pico (GP16) for the loopback test.",
    "SR_RCLK": "Latch for both shift registers (GP17).",
    "SR_NOE": "Bus output enable, active low, pulled up (GP20). High = bus high-Z.",
    "SR_NSRCLR": "Shift register clear, active low, pulled up (GP21).",
    "CELL_A0": "Decoder address bit 0 (GP2).", "CELL_A1": "Decoder address bit 1 (GP3).",
    "CELL_A2": "Decoder address bit 2 (GP4).",
    "CELL_EN": "Cell enable from the Pico (GP5), pulled down. Also the timeout chip's clear input.",
    "CELL_EN_TMO": "Timeout chip output: follows CELL_EN but drops after the set time.",
    "CELL_EN_G": "Enable actually seen by the decoder, chosen by JP1. Pulled down.",
    "TMO_RC": "Timing node of the timeout chip (resistor to 3.3 V, capacitor to TMO_CEXT).",
    "TMO_CEXT": "Other side of the timing capacitor.",
    "BUZZER": "Buzzer control from the Pico (GP14).", "BUZ_B": "Base of the buzzer transistor.",
    "BUZ_N": "Low side of the buzzer, switched by the transistor.",
    "UART_TX": "Debug UART transmit (GP0).", "UART_RX": "Debug UART receive (GP1).",
    "RUN": "Pico reset pin, on a 2-pin header.",
}
for _i in range(12):
    NET_NOTES[f"BUS{_i}"] = f"Shared bus bit {_i}: dot {_i // 2 + 1} IN{_i % 2 + 1} on every cell."
for _i in range(12, 16):
    NET_NOTES[f"SR_SPARE{_i}"] = f"Unused shift register output {_i}, on a test pad."
for _c in range(8):
    NET_NOTES[f"CELL{_c}_NSLEEP"] = f"Wakes cell {_c}'s three drivers. Decoder output Y{_c}, pulled down."
for _n in ("SCAN", "BACK", "NEXT", "PLAY"):
    NET_NOTES[f"BTN_{_n}"] = f"{_n.title()} button, active low."
for _g in (6, 7, 8, 9, 22, 27, 28):
    NET_NOTES[f"SPARE_GP{_g}"] = f"Spare GPIO GP{_g} on the spare header."
CELL_NET_NOTES = {"VCP": "Charge-pump capacitor node of one DRV8833.",
                  "VINT": "Internal regulator bypass node of one DRV8833.",
                  "D": "One lead of one coil, at the cell connector."}


def collect_parts(root, cell):
    """Return {ref: {value, footprint, lcsc, dnp, lib}} for every placed part."""
    parts = {}
    for sheet, count in ((root, 1), (cell, 8)):
        for refs, _unit, node in sheet.parts:
            props = {p[1]: p[2] for p in sexpr.find_all(node, "property")}
            info = {
                "value": props["Value"], "footprint": props["Footprint"], "lcsc": props.get("LCSC", ""),
                "dnp": str(sexpr.find(node, "dnp")[1]) == "yes", "lib": sexpr.find(node, "lib_id")[1],
                "sheet": sheet.name,
            }
            for i in range(count):
                ref = refs[i] if len(refs) > 1 else refs[0]
                if not ref.startswith("#"):
                    parts[ref] = info
    return parts


def write_summary(parts, nets):
    by_net = {}
    for pin, net in nets.items():
        by_net.setdefault(net, []).append(pin)

    def natural(ref):
        head = ref.rstrip("0123456789")
        return head, int(ref[len(head):] or 0)

    lines = ["# Schematic summary (rev A draft)", "",
             "Generated by `gen/gen_schematic.py`. Do not edit by hand.", "",
             "Parts marked TBD wait for the cell measurements. DNP = not fitted.", "",
             "## Parts on the main sheet", "", "| Ref | Value | Footprint | LCSC | Fitted |", "|---|---|---|---|---|"]
    for ref in sorted((r for r, p in parts.items() if p["sheet"] == "root"), key=natural):
        p = parts[ref]
        lines.append(f"| {ref} | {p['value']} | {p['footprint'].split(':')[-1] or 'TBD'} | {p['lcsc'] or ''} | {'no' if p['dnp'] else 'yes'} |")
    lines += ["", "## Parts in each cell (x8)", "",
              "References are (cell + 1) x 100 + n: cell 0 has U101..U103, cell 7 has U801..U803.", "",
              "| Ref in cell 0 | Value | Footprint | LCSC |", "|---|---|---|---|"]
    for ref in sorted((r for r, p in parts.items() if p["sheet"] == "cell" and natural(r)[1] // 100 == 1), key=natural):
        p = parts[ref]
        lines.append(f"| {ref} | {p['value']} | {p['footprint'].split(':')[-1]} | {p['lcsc']} |")
    lines += ["", "## Nets on the main sheet", "", "| Net | What it is | Pins |", "|---|---|---|"]
    for net in sorted(n for n in by_net if "/" not in n):
        pins = sorted(by_net[net], key=lambda s: natural(s.split(".")[0]))
        root_pins = [p for p in pins if parts.get(p.split(".")[0], {}).get("sheet") == "root"]
        cell_count = len(pins) - len(root_pins)
        shown = ", ".join(root_pins) + (f" + {cell_count} cell pins" if cell_count else "")
        lines.append(f"| {net} | {NET_NOTES[net]} | {shown} |")
    lines += ["", "## Nets inside each cell", "", "Shown for cell 0; the other seven are identical.", "",
              "| Net | What it is | Pins |", "|---|---|---|"]
    for net in sorted(n for n in by_net if n.startswith("Cell0/")):
        short = net.split("/")[1]
        note = CELL_NET_NOTES[short.rstrip("0123456789AB") if short[0] == "D" else short[:-1]]
        if short[0] == "D":
            note = f"Dot {short[1]} coil lead {short[2]}."
        lines.append(f"| {short} | {note} | {', '.join(sorted(by_net[net]))} |")
    lines += ["", f"Totals: {len(parts)} parts, {len(by_net)} nets, {len(nets)} connected pins.", ""]
    (OUT / "SCHEMATIC_SUMMARY.md").write_text("\n".join(lines))


def main():
    make_project_symbols()
    check_library_pins()
    cell = build_cell()
    root, boxes = build_root(cell)
    root_path = "/" + root.uuid
    cell_paths = [f"{root_path}/{schgen.uid(PROJECT, 'cell-instance', c)}" for c in range(8)]
    (OUT / f"{PROJECT}.kicad_sch").write_text(root.render([root_path], extra_items=boxes, root=True))
    (OUT / "cell.kicad_sch").write_text(cell.render(cell_paths))
    pro = OUT / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        pro.write_text(json.dumps({"meta": {"filename": pro.name, "version": 3}}, indent=2) + "\n")
    write_library_tables([root, cell])
    nets = intended_nets(root, cell)
    parts = collect_parts(root, cell)
    design = {"pins": nets, "parts": parts}
    (OUT / "design.json").write_text(json.dumps(design, indent=1, sort_keys=True) + "\n")
    write_summary(parts, nets)
    print(f"wrote {PROJECT}.kicad_sch and cell.kicad_sch: {len(parts)} parts, "
          f"{len(set(nets.values()))} nets, {len(nets)} pins")


if __name__ == "__main__":
    main()
