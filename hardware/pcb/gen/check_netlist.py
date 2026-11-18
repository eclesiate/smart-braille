"""Check the generated schematic with KiCad's own tools.

    python hardware/pcb/gen/check_netlist.py

1. Runs ERC through kicad-cli and fails on any violation.
2. Exports KiCad's netlist and compares it, pin by pin, with
   design.json written by gen_schematic.py. This catches a label
   that missed its pin, which ERC alone might not.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

import sexpr

PCB = pathlib.Path(__file__).resolve().parent.parent
ROOT = PCB / "smartbraille_driver.kicad_sch"


def run(args):
    return subprocess.run(["kicad-cli", *args], capture_output=True, text=True)


def erc(tmp):
    report = pathlib.Path(tmp) / "erc.json"
    result = run(["sch", "erc", "--severity-all", "--format", "json", "-o", str(report), str(ROOT)])
    if not report.exists():
        raise SystemExit("ERC did not run:\n" + result.stdout + result.stderr)
    data = json.loads(report.read_text())
    violations = [(s.get("path"), v["severity"], v["type"], v.get("description"))
                  for s in data.get("sheets", []) for v in s.get("violations", [])]
    return violations


def kicad_nets(tmp):
    out = pathlib.Path(tmp) / "netlist.net"
    result = run(["sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(ROOT)])
    if not out.exists():
        raise SystemExit("netlist export failed:\n" + result.stdout + result.stderr)
    tree = sexpr.parse(out.read_text())
    nets = {}
    for net in sexpr.find_all(sexpr.find(tree, "nets"), "net"):
        name = sexpr.find(net, "name")[1]
        nodes = {f"{sexpr.find(n, 'ref')[1]}.{sexpr.find(n, 'pin')[1]}" for n in sexpr.find_all(net, "node")}
        nets[name] = nodes
    components = {sexpr.find(c, "ref")[1] for c in sexpr.find_all(sexpr.find(tree, "components"), "comp")}
    return nets, components


def main():
    intended_pins = json.loads((PCB / "design.json").read_text())["pins"]
    intended = {}
    for pin, net in intended_pins.items():
        intended.setdefault(net, set()).add(pin)

    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        violations = erc(tmp)
        actual, components = kicad_nets(tmp)

    for v in violations:
        problems.append("ERC: %s %s %s %s" % v)

    pin_to_actual = {pin: name for name, pins in actual.items() for pin in pins}
    for net, pins in sorted(intended.items()):
        found = {pin_to_actual.get(pin) for pin in pins}
        if None in found:
            missing = sorted(p for p in pins if p not in pin_to_actual)
            problems.append(f"{net}: pins missing from KiCad's netlist: {missing}")
            continue
        if len(found) != 1:
            problems.append(f"{net}: split across KiCad nets {sorted(found)}")
            continue
        extra = actual[found.pop()] - pins
        if extra:
            problems.append(f"{net}: KiCad also connects {sorted(extra)}")
    connected = {pin for pins in actual.values() if len(pins) > 1 for pin in pins}
    for pin in sorted(connected - set(intended_pins)):
        problems.append(f"{pin}: connected in KiCad but not in the intended netlist")

    expected_parts = {pin.split(".")[0] for pin in intended_pins}
    if expected_parts - components:
        problems.append(f"parts missing from KiCad's netlist: {sorted(expected_parts - components)}")

    if problems:
        print(f"FAIL: {len(problems)} problems")
        for line in problems[:60]:
            print("  " + line)
        return 1
    print(f"OK: ERC clean, {len(intended)} nets and {len(intended_pins)} pins match KiCad's netlist, "
          f"{len(components)} components")
    return 0


if __name__ == "__main__":
    sys.exit(main())
