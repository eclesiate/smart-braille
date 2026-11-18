"""The generated schematic must be up to date, ERC clean, and match KiCad's netlist.

Skipped where kicad-cli is not installed.
"""

import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN = ROOT / "hardware" / "pcb" / "gen"
OUTPUTS = ["smartbraille_driver.kicad_sch", "cell.kicad_sch", "design.json", "SCHEMATIC_SUMMARY.md",
           "smartbraille.kicad_sym"]

pytestmark = pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")


def test_committed_schematic_matches_the_generator():
    pcb = ROOT / "hardware" / "pcb"
    before = {name: (pcb / name).read_bytes() for name in OUTPUTS}
    subprocess.run([sys.executable, str(GEN / "gen_schematic.py")], check=True, capture_output=True)
    stale = [name for name in OUTPUTS if (pcb / name).read_bytes() != before[name]]
    assert not stale, f"regenerate and commit: {stale}"


def test_erc_clean_and_netlist_matches():
    result = subprocess.run([sys.executable, str(GEN / "check_netlist.py")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
