"""Read-only native/XML cross-package wiring and interface boundary audit.

The CSV is an electrical integration plan, including explicit component taps;
it is not a manufactured harness or consolidated PCB. No host/peer is invented.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
S4 = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def verify():
    parts, xml, hashes, parents = {}, {}, {}, {}
    checks = 0

    def require(ok, message):
        nonlocal checks
        checks += 1
        if not ok:
            raise AssertionError(message)

    def find(key):
        if key not in parents:
            parents[key] = key
        if parents[key] != key:
            parents[key] = find(parents[key])
        return parents[key]

    def join(a, b):
        parents[find(a)] = find(b)

    packages = ("power", "supervision", "monitoring-cell", "current-driver",
                "contact-router", "recording-front-end", "monitoring-transport")
    for pkg in packages:
        path = S4/pkg/"connectivity.json"
        parts[pkg] = {p["ref"]: p for p in json.loads(path.read_text(encoding="utf-8"))["parts"]}
        export = next((S4/pkg).glob("*.xml"))
        xml[pkg] = {}
        for net in ET.parse(export).findall(".//nets/net"):
            for node in net.findall("node"):
                xml[pkg][node.attrib["ref"], node.attrib["pin"]] = net.attrib["name"].split("/")[-1]
        for path in (path, export):
            hashes[path.relative_to(ROOT).as_posix()] = sha(path)

    wire_count, endpoint_checks = 0, 0
    for filename, expected in (("supervision-wiring.csv", 102), ("power-wiring.csv", 32),
                               ("monitoring-transport-wiring.csv", 34)):
        path = ROOT/"docs/stage4"/filename
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        require(len(rows) == expected, f"wire count {filename}")
        for row in rows:
            ends = []
            for side in ("from", "to"):
                pkg, ref, pin, net = [row[side+"_"+key] for key in ("package", "ref", "pin", "net")]
                require(parts[pkg][ref]["nets"][pin] == xml[pkg][ref, pin] == net,
                        f"actual manifest/XML wire endpoint {pkg}/{ref}/{pin}")
                endpoint_checks += 1
                ends.append((pkg, net))
            join(*ends)
        wire_count += len(rows)
        hashes[path.relative_to(ROOT).as_posix()] = sha(path)

    native = parts["monitoring-transport"]
    # Check real saved host-facing boundaries, not a fictional implemented MCU.
    headers = {
        "J3": {"1": "RAW_SCLK", "2": "RAW_SDI", "3": "RAW_SDO", "4": "RAW_CS_N", "5": "RAW_RST_N", "6": "GND"},
        "J7": {"1": "HOST_UART_TX", "2": "HOST_UART_RX", "3": "HOST_3V3", "4": "GND"},
        "J8": {"1": "COMP_UART_TX", "2": "COMP_UART_RX", "3": "COMP_3V3", "4": "COMP_GND"},
        "J22": {"1": "MON_SCLK", "2": "MON_MISO", "3": "CH0_CNV", "4": "CH0_CS_N", "5": "CH1_CNV", "6": "CH1_CS_N", "7": "GND"},
    }
    boundary_pins = 0
    for ref, mapping in headers.items():
        require(native[ref]["nets"] == mapping, f"actual interface header {ref}")
        for pin, net in mapping.items():
            require(xml["monitoring-transport"][ref, pin] == net, f"native XML header {ref}/{pin}")
            boundary_pins += 1
    for ref, source in (("R30", 0), ("R31", 1)):
        require(native[ref]["value"] == "330R", f"MISO resistor value {ref}")
        expected = {"1": f"CH{source}_DOUT", "2": "MON_MISO"}
        require(native[ref]["nets"] == expected, f"explicit resistive MISO join {ref}")
        for pin, net in expected.items():
            require(xml["monitoring-transport"][ref, pin] == net, f"MISO XML {ref}/{pin}")
    iso = native["U20"]
    require(iso["value"] == "ISO6721BDR", "selected UART isolator identity")
    require(iso["nets"] == {"1": "HOST_3V3", "2": "UART_HOST_RX_PAD", "3": "UART_HOST_TX_PAD",
                            "4": "GND", "5": "COMP_GND", "6": "UART_COMP_RX_PAD",
                            "7": "UART_COMP_TX_PAD", "8": "COMP_3V3"}, "UART isolator directions and domains")
    series = {"R20": ("HOST_UART_TX", "UART_HOST_TX_PAD"), "R21": ("UART_HOST_RX_PAD", "HOST_UART_RX"),
              "R22": ("COMP_UART_TX", "UART_COMP_TX_PAD"), "R23": ("UART_COMP_RX_PAD", "COMP_UART_RX")}
    for ref, nets in series.items():
        require(native[ref]["value"] == "33R" and native[ref]["nets"] == dict(zip(("1", "2"), nets)),
                f"native UART series handoff {ref}")
    for ref in ("R24", "R25"):
        require(native[ref]["value"] == "10k", f"leakage-compatible UART idle resistor {ref}")

    host = find(("power", "GND"))
    for pkg in packages:
        nets = {net for p in parts[pkg].values() for net in p["nets"].values() if net is not None}
        if "GND" in nets:
            require(find((pkg, "GND")) == host, f"host ground plan {pkg}")
        if "AFEAGND" in nets:
            require(find((pkg, "AFEAGND")) != host, f"floating recording ground {pkg}")
    require(find(("monitoring-transport", "COMP_GND")) != host, "companion ground excluded from wire plan")
    require(find(("monitoring-transport", "COMP_3V3")) != find(("power", "HOST_3V3")), "companion supply is external")

    # Include the new resistors in a second DC-conduction graph. The isolator
    # remains a domain-crossing component and is not a passive connection.
    for p in native.values():
        if p["ref"].startswith("R") and len(p["nets"]) == 2:
            nets = list(p["nets"].values())
            join(("monitoring-transport", nets[0]), ("monitoring-transport", nets[1]))
    require(find(("monitoring-transport", "COMP_GND")) != find(("monitoring-transport", "GND")), "no new passive ground bridge")
    require(find(("monitoring-transport", "COMP_3V3")) != find(("monitoring-transport", "HOST_3V3")), "no new passive supply bridge")
    require(find(("power", "PWR_FAULT_N")) == find(("supervision", "GUARD_FAULT_N")) == find(("monitoring-transport", "PWR_FAULT_N")), "existing fault is observed without replacing guard authority")
    require(find(("supervision", "CH0_MON_SUP_OK")) != find(("supervision", "CH0_EXT_SUP_OK")), "prearm health remains separate from arm-qualified enable")
    hashes[Path(__file__).relative_to(ROOT).as_posix()] = sha(Path(__file__))
    return {"schema": "scci_rh.stage4.monitoring-transport-integration.v1", "date": "2026-10-14", "status": "pass",
            "new_monitoring_transport_wires": 34, "combined_wire_plan_connections": wire_count,
            "endpoint_manifest_XML_comparisons": endpoint_checks, "actual_interface_header_pins": boundary_pins,
            "assertions": checks, "native_packages": len(packages), "floating_recording_ground_preserved": True,
            "external_companion_ground_and_power_preserved": True, "shared_MISO_join_is_explicit": True,
            "consolidated_native_hierarchy_or_PCB_created": False, "target_host_or_peer_implemented": False,
            "sha256_lf": hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args()
    receipt = verify()
    path = HERE/"integration-verification.json"
    if args.write_receipt:
        path.write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    else:
        assert json.loads(path.read_text(encoding="utf-8")) == receipt, "saved integration receipt differs"
    print(json.dumps({k: v for k, v in receipt.items() if k != "sha256_lf"}))


if __name__ == "__main__":
    main()
