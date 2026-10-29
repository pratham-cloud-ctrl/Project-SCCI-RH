"""Read-only independent BT40F image audit; Python standard library only.

--write-report intentionally refreshes the saved result after review. No SDK,
build-producer import, device, execution, flashing or hardware claim is involved.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = HERE / "artifacts"
REPORT = HERE / "verification.json"


def sha(path, text=False):
    raw = path.read_bytes()
    if text:
        raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def intel_hex(text):
    memory = {}
    base = 0
    entry = None
    ended = False
    records = 0
    for line in text.splitlines():
        if not line:
            continue
        if ended or not line.startswith(":"):
            raise ValueError("HEX record after EOF or missing record marker")
        try:
            record = bytes.fromhex(line[1:])
        except ValueError as exc:
            raise ValueError("HEX encoding") from exc
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) & 255:
            raise ValueError("HEX length/checksum")
        count, address, kind = record[0], int.from_bytes(record[1:3], "big"), record[3]
        data = record[4:-1]
        records += 1
        if kind == 0:
            for offset, value in enumerate(data):
                destination = base + address + offset
                if destination in memory:
                    raise ValueError("HEX overlapping byte")
                memory[destination] = value
        elif kind == 1:
            if count or address:
                raise ValueError("HEX EOF shape")
            ended = True
        elif kind in (2, 4):
            if count != 2 or address:
                raise ValueError("HEX extended address shape")
            base = int.from_bytes(data, "big") << (4 if kind == 2 else 16)
        elif kind in (3, 5):
            if count != 4 or address or entry is not None:
                raise ValueError("HEX entry shape")
            entry = (int.from_bytes(data[:2], "big") * 16 + int.from_bytes(data[2:], "big")
                     if kind == 3 else int.from_bytes(data, "big"))
        else:
            raise ValueError("HEX unsupported record type")
    if not ended or not memory:
        raise ValueError("HEX missing EOF/data")
    return memory, entry, records


def elf_load_bytes(path):
    raw = path.read_bytes()
    h = struct.unpack_from("<16sHHIIIIIHHHHHH", raw)
    if h[0][:7] != b"\x7fELF\x01\x01\x01" or h[9] != 32:
        raise ValueError("ELF32 little endian and native program-header size required")
    memory = {}
    segments = []
    for i in range(h[10]):
        kind, offset, virtual, physical, size, memsize, flags, align = struct.unpack_from(
            "<IIIIIIII", raw, h[5] + i * h[9])
        if kind != 1 or not size:
            continue
        if offset + size > len(raw) or not (0 <= physical < physical + size <= 1048576):
            raise ValueError("ELF load range outside application flash")
        for j, value in enumerate(raw[offset:offset + size]):
            if physical + j in memory:
                raise ValueError("ELF overlapping load byte")
            memory[physical + j] = value
        segments.append(dict(physical_address=physical, virtual_address=virtual, bytes=size))
    if not memory:
        raise ValueError("ELF no load image")
    return memory, segments


def config_values(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CONFIG_"):
            name, value = line.split("=", 1)
            if name in values:
                raise ValueError("duplicate Kconfig key")
            values[name] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            name = line[2:-11]
            if name in values:
                raise ValueError("duplicate Kconfig key")
            values[name] = "n"
    return values


def audit():
    checks = 0
    def check(value, message):
        nonlocal checks
        checks += 1
        if not value:
            raise AssertionError(message)
    receipt = json.loads((HERE / "build-receipt.json").read_text())
    check(receipt["status"] == "scci_rh_application_cross_compiled_and_linked", "successful saved build")
    check(receipt["hardware_carrier"] == "Fanstel BT40F", "carrier identity")
    check(receipt["internal_HFXO_capacitance_pF"] == 11, "declared HFXO capacitance")
    check(receipt["board"] == "nrf5340dk/nrf5340/cpuapp", "application-core target")
    check(receipt["sdk_version"] == "v3.4.1", "SDK identity")
    for key in ["flashed_or_executed", "hardware_timing_verified", "physical_peripheral_behavior_verified",
                "network_core_image_built", "full_450k_monitor_profile_implemented", "incremental"]:
        check(receipt[key] is False, "finite build evidence: " + key)
    bindings = {}
    for relative, expected in receipt["source_sha256_lf"].items():
        check(sha(ROOT / relative, True) == expected, "built source: " + relative)
        bindings[relative] = expected
    expected_sources = {p.relative_to(ROOT).as_posix()
                        for name in ("app", "core")
                        for p in (ROOT / "firmware/nrf5340" / name).rglob("*") if p.is_file()}
    expected_sources.update((HERE / name).relative_to(ROOT).as_posix()
                            for name in ("build_bt40f.py", "bt40f.conf"))
    check(set(bindings) == expected_sources, "complete application/core/variant source bindings")
    expected_artifacts = {"scci_rh.elf", "scci_rh.hex", "scci_rh.bin", "scci_rh.map", "build.config",
                          "zephyr.dts", "compile-records.json", "symbols.txt", "sections.txt"}
    check({p.name for p in ART.iterdir() if p.is_file()} == expected_artifacts, "exact exported artifact set")
    check({Path(p).name for p in receipt["artifact_sha256"]} == expected_artifacts, "complete artifact bindings")
    for relative, expected in receipt["artifact_sha256"].items():
        check(sha(ROOT / relative, Path(relative).suffix not in (".elf", ".bin")) == expected,
              "build artifact: " + relative)
    # Independently retain the previous package's own source and artifact bindings.
    previous = json.loads((ROOT / "provenance/stage4-nrf5340-build.json").read_text())
    for relative, expected in previous["source_sha256_lf"].items():
        check(sha(ROOT / relative, True) == expected, "preserved original source: " + relative)
    for relative, expected in previous["artifact_sha256"].items():
        check(expected in (sha(ROOT / relative), sha(ROOT / relative, True)),
              "preserved original artifact: " + relative)
    helper_path = ROOT / "scripts/verify_nrf5340.py"
    spec = importlib.util.spec_from_file_location("scci_rh_original_elf_auditor", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    image = helper.elf_image(ART / "scci_rh.elf")
    original = helper.elf_image(ROOT / "firmware/nrf5340/artifacts/scci_rh.elf")
    current_scci_rh = {k for k in image["functions"] if k.startswith("scci_rh_") or k == "main"}
    previous_scci_rh = {k for k in original["functions"] if k.startswith("scci_rh_") or k == "main"}
    check(current_scci_rh == previous_scci_rh and len(current_scci_rh) >= 11, "all previously linked SCCI_RH functions retained")
    loads, segments = elf_load_bytes(ART / "scci_rh.elf")
    hexbytes, entry, records = intel_hex((ART / "scci_rh.hex").read_text())
    check(loads == hexbytes, "ELF and Intel HEX exact physical load-byte parity")
    check(entry == image["entry"], "ELF and Intel HEX entry parity")
    first, last = min(loads), max(loads) + 1
    check(first == 0, "flash begins at zero")
    binary = (ART / "scci_rh.bin").read_bytes()
    check(binary == bytes(loads.get(address, 255) for address in range(first, last)),
          "BIN exact load image with erased-flash fill")
    check(last == image["flash_LOAD_extent_bytes"] == 54072, "independent rebranded-image flash extent agreement")
    initial_sp, reset = struct.unpack_from("<II", binary)
    check(0x20000000 < initial_sp <= 0x20080000 and initial_sp % 8 == 0, "aligned initial stack in application RAM")
    check(reset == image["entry"] and reset & 1, "Thumb reset vector equals ELF entry")
    map_text = (ART / "scci_rh.map").read_text()
    regions = {}
    for name in ("FLASH", "RAM"):
        match = re.search(r"^" + name + r"\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)", map_text, re.MULTILINE)
        check(match is not None, "actual linker region: " + name)
        regions[name] = [int(x, 16) for x in match.groups()]
    check(regions["FLASH"] == [0, 1048576], "1 MiB application flash allocation")
    check(regions["RAM"] == [0x20000000, 458752], "448 KiB linker RAM allocation")
    check(image["RAM_extent_bytes"] == 98000 <= .8 * regions["RAM"][1], "20 percent RAM headroom")
    current_config = config_values(ART / "build.config")
    previous_config = config_values(ROOT / "firmware/nrf5340/artifacts/build.config")
    required = {"CONFIG_SOC_HFXO_CAP_DEFAULT": "n", "CONFIG_SOC_HFXO_CAP_INTERNAL": "y",
                "CONFIG_SOC_HFXO_CAP_INT_VALUE_X2": "22", "CONFIG_DEPRECATED": "y"}
    delta = {k: {"previous": previous_config.get(k), "BT40F": current_config.get(k)}
             for k in set(previous_config) | set(current_config)
             if previous_config.get(k) != current_config.get(k)}
    check(set(delta) == set(required), "only reviewed HFXO and SDK deprecated-selection configuration delta")
    for key, value in required.items():
        check(current_config.get(key) == value, "carrier Kconfig: " + key)
    check(current_config.get("CONFIG_BT", "n") == "n", "radio remains disabled")
    fragment = config_values(HERE / "bt40f.conf")
    check(fragment == {"CONFIG_SOC_HFXO_CAP_INTERNAL": "y", "CONFIG_SOC_HFXO_CAP_INT_VALUE_X2": "22"},
          "exact carrier configuration fragment")
    records_compiled = json.loads((ART / "compile-records.json").read_text())
    compiled = {Path(r["file"].replace("\\", "/")).name: r["command"] for r in records_compiled}
    check(set(compiled) == {"main.c", "scci_rh_backend.c", "scci_rh_runtime.c", "system_nrf5340_application.c"},
          "actual application/core/startup compile records")
    for name, command in compiled.items():
        check("-mcpu=cortex-m33" in command and "-mthumb" in command, "M33/Thumb compile: " + name)
    # Finite rejection check ensures checksum corruption cannot pass the HEX parser.
    bad = (ART / "scci_rh.hex").read_text().splitlines()
    bad[0] = bad[0][:-2] + ("00" if bad[0][-2:] != "00" else "01")
    try:
        intel_hex("\n".join(bad))
    except ValueError:
        rejected = True
    else:
        rejected = False
    check(rejected, "corrupt HEX checksum rejected")
    review_paths = [HERE / "verify_bt40f.py", HERE / "README.md", HERE / "build-receipt.json",
                    ROOT / "provenance/stage4-nrf5340-build.json", helper_path]
    bindings.update({p.relative_to(ROOT).as_posix(): sha(p, True) for p in review_paths})
    return dict(schema="scci_rh.stage4.bt40f-independent-verification.v1", date="2026-10-28", original_design_date="2026-10-15",
                passed=True, checks=checks, hardware_carrier="Fanstel BT40F", internal_HFXO_capacitance_pF=11,
                evidence="read-only source/artifact bindings, independent ELF and HEX parsers, BIN parity; no target execution",
                elf_sha256=sha(ART / "scci_rh.elf"), entry_hex=hex(image["entry"]),
                flash_LOAD_extent_bytes=last, flash_LOAD_data_bytes=len(loads), flash_gap_fill_bytes=len(binary)-len(loads),
                flash_capacity_bytes=regions["FLASH"][1], RAM_extent_bytes=image["RAM_extent_bytes"],
                RAM_allocated_section_bytes=image["RAM_allocated_section_bytes"], RAM_linker_capacity_bytes=regions["RAM"][1],
                RAM_physical_capacity_bytes=524288, RAM_20percent_headroom_pass=True,
                load_segments=segments, intel_hex_records=records, linked_scci_rh_functions=sorted(current_scci_rh),
                configuration_delta={k: delta[k] for k in sorted(delta)}, original_package_bindings_preserved=True,
                flashed_or_executed=False, hardware_timing_verified=False, source_sha256_lf=dict(sorted(bindings.items())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    result = audit()
    if args.write_report:
        REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    elif result != json.loads(REPORT.read_text()):
        raise AssertionError("saved verification differs; review before explicit regeneration")
    print(json.dumps({k: result[k] for k in ("passed", "checks", "flash_LOAD_extent_bytes", "RAM_extent_bytes",
                                            "internal_HFXO_capacitance_pF", "original_package_bindings_preserved")}, sort_keys=True))


if __name__ == "__main__":
    main()
