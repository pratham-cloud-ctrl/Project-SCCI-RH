"""Check exported native connectivity, critical pin contracts and review artifacts.

This is an independent KiCad-export/manifest comparison, not an analog test.
Default mode is cross-platform and read-only against frozen exports/receipt.
Use --write-receipt only after intentional live KiCad exports and visual QA.
"""
from pathlib import Path
import csv
import argparse
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--write-receipt", action="store_true", help="Explicitly refresh the receipt after native export/visual review")
args = parser.parse_args()

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / "connectivity.json").read_text(encoding="utf-8"))
tree = ET.parse(HERE / "monitoring_cell.xml").getroot()
parts = {p["ref"]: p for p in manifest["parts"]}
actual_parts = {c.attrib["ref"]: c for c in tree.findall("./components/comp")}
assert set(actual_parts) == set(parts), (set(actual_parts) - set(parts), set(parts) - set(actual_parts))
assert len(parts) == 70
for ref, p in parts.items():
    assert actual_parts[ref].findtext("value") == p["value"], ref
    assert actual_parts[ref].findtext("footprint") == p["footprint"], ref
    fp = HERE / "scci_rh_s4.pretty" / (p["footprint"].split(":")[1] + ".kicad_mod")
    assert fp.is_file() and fp.stat().st_size > 0, ref

actual_nets = {}
for net in tree.findall("./nets/net"):
    for node in net.findall("node"):
        key = (node.attrib["ref"], node.attrib["pin"])
        assert key not in actual_nets, key
        actual_nets[key] = net.attrib["name"]
checked_pins = 0
for ref, p in parts.items():
    for pin, expected in p["nets"].items():
        key = (ref, pin)
        if expected is None:
            # KiCad emits intentionally unconnected pins as unique unconnected-* nets.
            assert key not in actual_nets or actual_nets[key].startswith("unconnected-"), key
        else:
            assert actual_nets.get(key) == expected, (key, actual_nets.get(key), expected)
        checked_pins += 1

def connected(ref, pin, net):
    assert actual_nets[(ref, str(pin))] == net, (ref, pin, net)

# Critical functional contracts are checked against the actual KiCad export.
# Production OPA391DCK pinout, independently written from TI SBOS925E Table4-1.
# Verify every amplifier role, not just the generated manifest's internal agreement.
opamp_contracts = {"U2": {1: "MID_DIV", 2: "GND", 3: "V_MID", 4: "V_MID", 5: "+5VA"}}
for ch in (0, 1):
    b = 100 * (ch + 1)
    opamp_contracts[f"U{b+1}"] = {1: "V_MID", 2: "GND", 3: f"CH{ch}_SUM", 4: f"CH{ch}_Q_INT", 5: "+5VA"}
    opamp_contracts[f"U{b+2}"] = {1: f"CH{ch}_Q_INT", 2: "GND", 3: f"CH{ch}_ADC_BUF", 4: f"CH{ch}_ADC_BUF", 5: "+5VA"}
assert {ref for ref, p in parts.items() if p["kind"] == "opa"} == set(opamp_contracts)
for ref, nets in opamp_contracts.items():
    assert parts[ref]["value"] == "OPA391DCKR", ref
    assert parts[ref]["footprint"] == "scci_rh_s4:SOT-353_SC-70-5", ref
    assert {str(p[0]): p[1] for p in parts[ref]["pins"]} == {
        "1": "IN+", "2": "V-", "3": "IN-", "4": "OUT", "5": "V+"}, ref
    for pin, net in nets.items():
        connected(ref, pin, net)
for ch in (0, 1):
    b = 100 * (ch + 1)
    q = lambda suffix: f"CH{ch}_{suffix}"
    connected(f"R{b}", 1, q("RETURN_LOAD"))
    connected(f"R{b}", 2, q("RETURN_DRIVER"))
    connected(f"U{b}", 8, q("RETURN_LOAD"))
    connected(f"U{b}", 1, q("RETURN_DRIVER"))
    connected(f"U{b}", 4, "GND")  # Manufacturer NC pin must be grounded.
    connected(f"U{b}", 3, "V_MID")
    connected(f"U{b}", 7, "V_MID")
    connected(f"U{b+1}", 1, "V_MID")
    connected(f"U{b+1}", 3, q("SUM"))
    connected(f"U{b+1}", 4, q("Q_INT"))
    connected(f"C{b}", 1, q("SUM"))
    connected(f"C{b}", 2, q("Q_INT"))
    connected(f"U{b+3}", 2, "+3V3")  # AVDD must NOT use the 5V reference supply.
    connected(f"U{b+3}", 10, "+3V3")
    connected(f"U{b+3}", 1, "V_REF")
    connected(f"U{b+3}", 3, q("ADC_IN"))
    connected(f"U{b+3}", 4, "GND")
    connected(f"U{b+4}", 3, "I_HI")
    connected(f"U{b+4}", 2, q("I_MON"))
    connected(f"U{b+4}", 5, q("I_MON"))
    connected(f"U{b+4}", 6, "I_LO")
    connected(f"U{b+5}", 6, q("EXT_SUP_OK"))
    connected(f"U{b+6}", 6, q("CLEAR_N"))
    connected(f"U{b+6}", 7, "+3V3")
    connected(f"U{b+6}", 1, q("REARM"))
    connected(f"U{b+6}", 5, q("PERMIT"))
    assert parts[f"U{b+6}"]["value"] == "SN74LVC1G74DCUR"
    assert "VSSOP-8_2.3x2mm_P0.5mm" in parts[f"U{b+6}"]["footprint"]
connected("U3", 1, "CH0_INT_RUN")
connected("U3", 5, "CH1_INT_RUN")
connected("U3", 10, "CH0_SUM")
connected("U3", 9, "CH0_Q_INT")
connected("U3", 6, "CH1_SUM")
connected("U3", 7, "CH1_Q_INT")
assert parts["U3"]["nets"]["2"] is None and parts["U3"]["nets"]["4"] is None

with (HERE / "bom.csv").open(encoding="utf-8", newline="") as f:
    bom = list(csv.DictReader(f))
assert {r["reference"] for r in bom} == set(parts) and len(bom) == len(parts)
erc = json.loads((HERE / "erc.json").read_text(encoding="utf-8"))
assert erc["ignored_checks"] == []
violations = [v for s in erc["sheets"] for v in s["violations"]]
assert violations == [], violations
assert len(erc["sheets"]) == len(tree.findall("./design/sheet")) == 3
# KiCad's exported page dictionary objects are plain text. This bounded check is
# not a generic arbitrary-PDF parser. pypdf is an optional independent cross-check.
pages = len(re.findall(rb"/Type\s*/Page(?!s)\b", (HERE / "monitoring_cell.pdf").read_bytes()))
try:
    from pypdf import PdfReader
except ImportError:
    pass
else:
    assert len(PdfReader(HERE / "monitoring_cell.pdf").pages) == pages
assert pages == 3
for name in ("monitoring_cell.svg", "monitoring_cell-Source0_monitor.svg", "monitoring_cell-Source1_monitor.svg"):
    svg = HERE / "svg" / name
    assert svg.is_file() and svg.stat().st_size > 1000

n = manifest["nominal"]
gain = n["shunt_ohm"] * n["sense_gain"]
scale = n["integrator_R_ohm"] * n["integrator_C_F"] / gain
assert math.isclose(gain, n["current_gain_V_per_A"], rel_tol=1e-12)
assert math.isclose(scale, n["charge_scale_C_per_V"], rel_tol=1e-12)
assert math.isclose(n["nominal_phase_charge_C"] / scale, n["nominal_delta_V"], rel_tol=1e-12)
assert math.isclose(n["Vref_V"] / 65536 * scale, n["ideal_adc_charge_LSB_C"], rel_tol=1e-12)
assert len(manifest["external_unimplemented"]) >= 7

files = sorted(p for p in HERE.rglob("*") if p.is_file() and p.name not in {"verification.json", "monitoring_cell.kicad_prl"} and "__pycache__" not in p.parts and not any(s.startswith("failed-export-") for s in p.parts))
def artifact_hash(path):
    data = path.read_bytes()
    if path.suffix.lower() not in {".png", ".pdf"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()
receipt = {
    "schema": "scci_rh.stage4.monitoring-cell.verification.v1",
    "date": "2026-10-12",
    "scope": "Native schematic connectivity and export integrity only; not analog or biological validation",
    "kicad_version": erc["kicad_version"],
    "components": len(parts), "pin_contracts_compared": checked_pins,
    "sheets": 3, "pdf_pages": pages, "erc_violations": 0, "ignored_erc_checks": [],
    "checks": ["exported component/value/footprint identity", "all pin-to-net assignments", "critical supply and functional pin contracts", "BOM identity", "local footprint availability", "three-sheet ERC with no ignored checks", "PDF and SVG exports", "nominal transfer arithmetic"],
    "hash_policy": "SHA256 of exact PNG/PDF bytes; all other included source/export text normalizes CRLF and CR to LF; receipt, local KiCad preferences, Python cache and ignored failed-export preservation are excluded",
    "unqualified": ["analog stability and settling", "24nC/4% precision target", "sensor input-bias/load bypass", "waveform window and tail bounds", "hardware fault response latency", "power-sequence behavior", "complete independent supervision", "HV current driver/routing", "PCB/physical assembly", "chronic implant suitability", "biological efficacy"],
    "sha256": {p.relative_to(HERE).as_posix(): artifact_hash(p) for p in files},
}
if args.write_receipt:
    (HERE / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
else:
    frozen = json.loads((HERE / "verification.json").read_text(encoding="utf-8"))
    assert frozen == receipt, "Frozen verification receipt or artifact hashes differ; review intentional changes before refreshing"
print(json.dumps({k: receipt[k] for k in ("components", "pin_contracts_compared", "sheets", "pdf_pages", "erc_violations", "ignored_erc_checks")}))
