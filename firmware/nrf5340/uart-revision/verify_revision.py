"""Independently audit the additive UART revision and exact target load bytes.

Read-only by default. Uses the preserved independent ELF/HEX readers, never
imports the build producer, and requires the actual old-fails/new-passes host
regression. No hardware execution is implied.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import posixpath
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORT = HERE / "verification.json"


def sha(path: Path, text: bool = False) -> str:
    data = path.read_bytes()
    if text:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def audit() -> dict:
    checks = 0
    def check(value: bool, reason: str) -> None:
        nonlocal checks
        checks += 1
        if not value:
            raise AssertionError(reason)

    receipt = json.loads((HERE / "build-receipt.json").read_text(encoding="utf-8"))
    check(receipt["schema"] == "scci_rh.uart-revision.target-build.v1", "dedicated revision build")
    check(receipt["date"] == "2026-10-28" and receipt["original_design_date"] == "2026-10-17", "actual migration rebuild date and original implementation date")
    check(receipt["status"] == "scci_rh_application_cross_compiled_and_linked", "completed target build")
    check(receipt["hardware_carrier"] == "Fanstel BT40F" and receipt["sdk_version"] == "v3.4.1", "reviewed hardware/SDK")
    check(receipt["board"] == "nrf5340dk/nrf5340/cpuapp", "application-core startup/linker")
    for key in ("incremental", "flashed_or_executed", "hardware_timing_verified",
            "physical_peripheral_behavior_verified", "network_core_image_built", "full_450k_monitor_profile_implemented"):
        check(receipt[key] is False, "bounded target evidence: " + key)
    expected_sources = {"firmware/nrf5340/uart-revision/" + p for p in
        ("build_revision.py", "CMakeLists.txt", "src/scci_rh_backend.c")}
    expected_sources.update("firmware/nrf5340/" + p for p in ("app/src/main.c", "app/src/scci_rh_backend.h",
        "app/src/scci_rh_pins.h", "app/prj.conf", "app/app.overlay", "core/scci_rh_runtime.c", "core/scci_rh_runtime.h"))
    expected_sources.add("electronics/stage4/integrated-pcb/firmware-profile/bt40f.conf")
    check(set(receipt["source_sha256_lf"]) == expected_sources, "complete actual source set")
    for path, digest in receipt["source_sha256_lf"].items():
        check(sha(ROOT / path, True) == digest, "built source: " + path)
    expected_artifacts = {"scci_rh.elf", "scci_rh.hex", "scci_rh.bin", "scci_rh.map", "build.config", "zephyr.dts",
        "compile-records.json", "symbols.txt", "sections.txt"}
    artifacts = HERE / "artifacts"
    check({p.name for p in artifacts.iterdir() if p.is_file()} == expected_artifacts, "exact artifact set")
    check({Path(p).name for p in receipt["artifact_sha256"]} == expected_artifacts, "complete artifact bindings")
    for path, digest in receipt["artifact_sha256"].items():
        check(sha(ROOT / path, Path(path).suffix not in (".elf", ".bin")) == digest, "target artifact: " + path)
    # Preserve the original source/image record. These are historical checks,
    # not claims that its known UART defect disappeared retrospectively.
    old_audit = load("scci_rh_historical_independent", ROOT / "scripts/verify_nrf5340.py")
    carrier_path = ROOT / "electronics/stage4/integrated-pcb/firmware-profile/verify_bt40f.py"
    carrier_audit = load("scci_rh_carrier_independent", carrier_path)
    old = old_audit.audit()
    carrier = carrier_audit.audit()
    check(old["passed"] and carrier["passed"], "immutable historical source/artifact evidence preserved")
    original = (ROOT / "firmware/nrf5340/app/src/scci_rh_backend.c").read_text(encoding="utf-8")
    current = (HERE / "src/scci_rh_backend.c").read_text(encoding="utf-8")
    state = ("/* An interrupt/FIFO boundary is not a wire-frame boundary. Keep ownership\n"
        " * through the whole selected frame; only then may normal traffic preempt raw. */\n"
        "static uint16_t tx_frame_remaining;\nstatic bool tx_frame_raw;\n")
    check(current.count(state) == 1, "one explicit persistent frame owner")
    def regions(text: str) -> tuple[str, str]:
        start = text.index("static void uart_callback(")
        end = text.index("\nstatic void put16(", start)
        return text[:start], text[end:]
    check(regions(current.replace(state, "")) == regions(original), "only UART callback/state changed in target backend")
    cmake = (HERE / "CMakeLists.txt").read_text(encoding="utf-8")
    for expected in ("../app/src/main.c", "src/scci_rh_backend.c", "../core/scci_rh_runtime.c",
            "../app/prj.conf", "../app/app.overlay"):
        check(expected in cmake, "unchanged reviewed input reused: " + expected)
    compiled = json.loads((artifacts / "compile-records.json").read_text(encoding="utf-8"))
    compiled_by_name = {Path(r["file"].replace("\\", "/")).name: r for r in compiled}
    check(set(compiled_by_name) == {"main.c", "scci_rh_backend.c", "scci_rh_runtime.c", "system_nrf5340_application.c"}, "actual compile records")
    for name, record in compiled_by_name.items():
        check("-mcpu=cortex-m33" in record["command"] and "-mthumb" in record["command"], "M33/Thumb compile: " + name)
    # These are retained Windows build records, even when audited on Ubuntu.
    # Map the actual canonical short-path junction to a repository-relative
    # source identity instead of resolving an E: path on the current OS.
    def project_compile_path(raw: str) -> str:
        windows = PureWindowsPath(raw)
        relative = windows.relative_to(PureWindowsPath("E:/SCCI_RH"))
        normalized = posixpath.normpath(relative.as_posix())
        if normalized == ".." or normalized.startswith("../"):
            raise AssertionError("compiled application path escaped project prefix")
        return normalized
    for name, relative in {
            "scci_rh_backend.c": "firmware/nrf5340/uart-revision/src/scci_rh_backend.c",
            "main.c": "firmware/nrf5340/app/src/main.c",
            "scci_rh_runtime.c": "firmware/nrf5340/core/scci_rh_runtime.c"}.items():
        check(project_compile_path(compiled_by_name[name]["file"]) == relative,
            "actual compiled repository source: " + name)
        check(relative in receipt["source_sha256_lf"], "compiled input is source-bound: " + name)
    image = old_audit.elf_image(artifacts / "scci_rh.elf")
    loads, segments = carrier_audit.elf_load_bytes(artifacts / "scci_rh.elf")
    hexbytes, entry, records = carrier_audit.intel_hex((artifacts / "scci_rh.hex").read_text(encoding="utf-8"))
    check(loads == hexbytes, "exact ELF/HEX physical load bytes")
    check(entry == image["entry"], "ELF/HEX entry parity")
    first, last = min(loads), max(loads) + 1
    check(first == 0 and last == image["flash_LOAD_extent_bytes"], "flash address extent")
    binary = (artifacts / "scci_rh.bin").read_bytes()
    check(binary == bytes(loads.get(address, 255) for address in range(first, last)), "BIN exact load bytes with erased gap fill")
    stack, reset = struct.unpack_from("<II", binary)
    check(0x20000000 < stack <= 0x20080000 and stack % 8 == 0, "aligned application RAM stack")
    check(reset == image["entry"] and reset & 1, "Thumb reset vector")
    regions_map = {}
    for name in ("FLASH", "RAM"):
        match = re.search(r"^" + name + r"\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)",
            (artifacts / "scci_rh.map").read_text(encoding="utf-8"), re.MULTILINE)
        check(match is not None, "actual linker region: " + name)
        regions_map[name] = [int(v, 16) for v in match.groups()]
    check(regions_map["FLASH"] == [0, 1048576] and last <= 1048576, "1 MiB application flash")
    check(regions_map["RAM"] == [0x20000000, 458752], "448 KiB linker allocation")
    check(image["RAM_extent_bytes"] <= .8 * regions_map["RAM"][1], "20 percent RAM headroom")
    configuration = carrier_audit.config_values(artifacts / "build.config")
    prior_configuration = carrier_audit.config_values(carrier_path.parent / "artifacts/build.config")
    check(configuration == prior_configuration, "unchanged BT40F hardware/peripheral Kconfig")
    check(configuration["CONFIG_SOC_HFXO_CAP_INT_VALUE_X2"] == "22", "manufacturer 11 pF HFXO")
    check(configuration.get("CONFIG_BT", "n") == "n", "radio remains disabled")
    scci_rh_functions = {name for name in image["functions"] if name == "main" or name.startswith("scci_rh_")}
    check(scci_rh_functions == set(carrier["linked_scci_rh_functions"]), "all policy/backend SCCI_RH functions retained")
    subprocess.run([sys.executable, str(HERE / "tests/check_uart_framing.py")], check=True, capture_output=True, text=True)
    regression = json.loads((HERE / "uart-framing-tests.json").read_text(encoding="utf-8"))
    check(regression["passed"] and regression["historical"]["failed"] > 0, "historical defect reproduced by actual C callback")
    check(regression["current"]["failed"] == 0 and regression["current"]["scenarios"] == 1172, "current finite frame regression passed")
    return {"schema": "scci_rh.uart-revision.independent-verification.v1", "date": "2026-10-28", "original_design_date": "2026-10-17",
        "passed": True, "checks": checks, "hardware_carrier": "Fanstel BT40F",
        "flash_LOAD_extent_bytes": last, "RAM_extent_bytes": image["RAM_extent_bytes"],
        "RAM_linker_capacity_bytes": regions_map["RAM"][1], "flash_capacity_bytes": 1048576,
        "elf_sha256": sha(artifacts / "scci_rh.elf"), "intel_hex_records": records,
        "load_segments": segments, "linked_scci_rh_functions": sorted(scci_rh_functions),
        "hardware_configuration_unchanged": True, "historical_bindings_preserved": True,
        "historical_failing_host_scenarios": regression["historical"]["failed"],
        "current_passing_host_scenarios": regression["current"]["passed"],
        "flashed_or_executed": False, "hardware_timing_verified": False,
        "evidence": "Actual corrected target image/source binding; independent ELF/HEX/BIN audit; finite actual-callback FIFO-stub regression",
        "source_sha256_lf": {p.relative_to(ROOT).as_posix(): sha(p, True) for p in
            (Path(__file__), HERE / "README.md", HERE / "build-receipt.json", HERE / "uart-framing-tests.json",
             HERE / "tests/check_uart_framing.py", ROOT / "scripts/verify_nrf5340.py", carrier_path)}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    result = audit()
    if args.write_report:
        REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    elif result != json.loads(REPORT.read_text(encoding="utf-8")):
        raise AssertionError("revision evidence differs; explicit review required")
    print(json.dumps({key: result[key] for key in ("passed", "checks", "flash_LOAD_extent_bytes",
        "RAM_extent_bytes", "historical_failing_host_scenarios", "current_passing_host_scenarios")}, sort_keys=True))


if __name__ == "__main__":
    main()
