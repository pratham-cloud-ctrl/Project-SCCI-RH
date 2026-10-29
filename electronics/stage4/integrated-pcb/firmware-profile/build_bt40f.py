"""Build the BT40F carrier variant without changing the frozen firmware package.

Uses the verified short Windows SDK copy. --incremental keeps the build tree;
the default pristine build is the reproducible publication operation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VERSION = "v3.4.1"
BOARD = "nrf5340dk/nrf5340/cpuapp"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incremental", action="store_true")
    args = parser.parse_args()
    tools = Path("E:/SCCI_RH-Tools")
    sdk_root = Path("E:/SCCI_RH-Nordic/ncs")
    project = Path("E:/SCCI_RH")
    assert project.resolve() == ROOT
    sdk = sdk_root / VERSION
    toolchain = sdk_root / "toolchains/4f5b6ad6dd"
    sdk_python = toolchain / "opt/bin/python.exe"
    compiler = toolchain / "opt/zephyr-sdk/gnu/arm-zephyr-eabi/bin"
    nrfutil = tools / "nrfutil.exe"
    env = dict(os.environ, NRFUTIL_HOME=str(tools / "nrfutil-home"))
    logs = ROOT / "tmp/nrf5340-bt40f-build"
    logs.mkdir(parents=True, exist_ok=True)

    def execute(name, command):
        result = subprocess.run(command, cwd=sdk, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        (logs / f"{name}.log").write_text(result.stdout, encoding="utf-8")
        if result.returncode:
            print(result.stdout[-14000:])
            raise RuntimeError(f"{name} failed; see {logs / (name + '.log')}")
        return result.stdout.strip()

    manager = execute("manager", [str(nrfutil), "sdk-manager", "toolchain", "env", "--ncs-version",
                                   VERSION, "--install-dir", str(tools / "ncs"), "--json"])
    records = [json.loads(line) for line in manager.splitlines() if line.strip()]
    variables = [v for r in records for v in r.get("data", {}).get("env_variables", [])]
    assert variables
    physical = str((tools / "ncs").resolve())
    for v in variables:
        env[v["key"]] = v["value"].replace(physical, str(sdk_root)).replace(
            physical.replace("\\", "/"), sdk_root.as_posix())
    env["ZEPHYR_BASE"] = (sdk / "zephyr").as_posix()
    build = project / "build/stage4/nrf5340-bt40f"
    assert build.resolve().is_relative_to(ROOT / "build")
    command = [str(sdk_python), "-m", "west", "build", "--no-sysbuild", "-b", BOARD,
               str(project / "firmware/nrf5340/app"), "-d", str(build)]
    command += ["--pristine=never" if args.incremental else "--pristine=always"]
    command += ["--", "-DPYTHON_EXECUTABLE=" + sdk_python.as_posix(),
                 "-DPython3_EXECUTABLE=" + sdk_python.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                 "-DEXTRA_CONF_FILE=" + (project / "electronics/stage4/integrated-pcb/firmware-profile/bt40f.conf").as_posix()]
    started = time.perf_counter()
    output = execute("build", command)
    elapsed = time.perf_counter() - started
    print(output[-2000:])
    artifacts = HERE / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    for source, target in {"zephyr.elf": "scci_rh.elf", "zephyr.hex": "scci_rh.hex",
                            "zephyr.bin": "scci_rh.bin", "zephyr.map": "scci_rh.map",
                            ".config": "build.config", "zephyr.dts": "zephyr.dts"}.items():
        shutil.copyfile(build / "zephyr" / source, artifacts / target)
    size_output = execute("size", [str(compiler / "arm-zephyr-eabi-size.exe"), "-A", str(artifacts / "scci_rh.elf")])
    symbols = execute("symbols", [str(compiler / "arm-zephyr-eabi-nm.exe"), "--print-size", "--size-sort",
                                   str(artifacts / "scci_rh.elf")])
    (artifacts / "symbols.txt").write_text(symbols + "\n", encoding="utf-8")
    (artifacts / "sections.txt").write_text(size_output + "\n", encoding="utf-8")
    commands = json.loads((build / "compile_commands.json").read_text(encoding="utf-8"))
    selected = [record for record in commands if Path(record["file"]).name in {
        "system_nrf5340_application.c", "scci_rh_backend.c", "scci_rh_runtime.c", "main.c"}]
    assert {Path(record["file"]).name for record in selected} == {
        "system_nrf5340_application.c", "scci_rh_backend.c", "scci_rh_runtime.c", "main.c"}
    (artifacts / "compile-records.json").write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
    versions = {
        "compiler": execute("compiler", [str(compiler / "arm-zephyr-eabi-gcc.exe"), "--version"]),
        "west": execute("west", [str(sdk_python), "-m", "west", "--version"]),
        "cmake": execute("cmake", [str(toolchain / "opt/bin/cmake.exe"), "--version"]),
        "ninja": execute("ninja", [str(toolchain / "opt/bin/ninja.exe"), "--version"]),
    }
    sources = [Path(__file__), HERE / "bt40f.conf"]
    for directory in ["app", "core"]:
        sources += [p for p in (ROOT / "firmware/nrf5340" / directory).rglob("*") if p.is_file()]
    receipt = {
        "schema": "scci_rh.stage4.bt40f-target-build.v1",
        "hardware_carrier": "Fanstel BT40F", "internal_HFXO_capacitance_pF": 11,
        "previous_firmware_artifacts_preserved": True, "date": "2026-10-28", "original_design_date": "2026-10-14",
        "status": "scci_rh_application_cross_compiled_and_linked", "sdk_version": VERSION,
        "board": BOARD, "toolchain_bundle_id": "4f5b6ad6dd", "versions": versions,
        "source_sha256_lf": {p.relative_to(ROOT).as_posix(): hashlib.sha256(
            p.read_text(encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest() for p in sorted(sources)},
        "artifact_hash_policy": "Exact ELF/BIN bytes; LF-normalized UTF-8 for all text artifacts",
        "artifact_sha256": {p.relative_to(ROOT).as_posix(): (sha(p) if p.suffix in {'.elf', '.bin'} else hashlib.sha256(
            p.read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest())
            for p in sorted(artifacts.iterdir()) if p.is_file()},
        "build_command": command, "build_elapsed_s": round(elapsed, 3),
        "gnu_size_output": size_output, "incremental": args.incremental,
        "flashed_or_executed": False, "hardware_timing_verified": False,
        "physical_peripheral_behavior_verified": False, "network_core_image_built": False,
        "full_450k_monitor_profile_implemented": False,
        "raw_target_profile": {"nominal_slot_us": 100, "aggregate_ceiling_sps": 10000,
                               "channels": 8, "frame_clocks": 40, "hardware_channel_tag": True,
                               "polling_actual_cadence_not_measured": True},
        "recording_target_profile": {"frame_period_us": 1000, "streams": 16,
                                     "commands_per_frame": 19, "nominal_per_stream_sps": 1000,
                                     "analog_recovery_qualified": False},
        "carrier_dependency": "Four SN74LVC165APWR input serializers, shared clocks/fanouts; consolidated PCB pending",
        "limitations": [
            "ELF proves ARM target compilation/linkage; no board, fabricated hardware or implant executed",
            "Polling schedules detect missed work but have no measured WCET, jitter, throughput or analog accuracy",
            "Hardware timer/DPPI phase cutoff is implemented configuration, not a measured terminal edge",
            "DAC native interface is write-only; SPI success does not verify setpoint or delivered charge",
            "Companion session/clock/calibration values remain trusted explicit inputs; CRC is not authentication",
            "Transport-valid recording samples and features are not qualified biological observations or learned skill",
            "Radio/network core, full-system algorithms, populated PCB and final CAD remain outside this package"
        ]
    }
    (HERE / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "elf_sha256": sha(artifacts / "scci_rh.elf"),
                      "flashed_or_executed": False}, indent=2))

if __name__ == "__main__":
    main()
