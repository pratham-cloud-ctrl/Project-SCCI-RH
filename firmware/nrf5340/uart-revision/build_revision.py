"""Build the additive UART-corrected BT40F image; never flash a device.

The v2.0.0 application, images and receipts remain immutable. This command uses
the existing locally verified SDK/toolchain and writes only this revision's
artifacts/receipt plus its own build/log directories.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VERSION = "v3.4.1"
BOARD = "nrf5340dk/nrf5340/cpuapp"


def sha(path: Path, text: bool = False) -> str:
    data = path.read_bytes()
    if text:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def sources() -> list[Path]:
    return [HERE / "build_revision.py", HERE / "CMakeLists.txt", HERE / "src/scci_rh_backend.c",
        ROOT / "firmware/nrf5340/app/src/main.c", ROOT / "firmware/nrf5340/app/src/scci_rh_backend.h",
        ROOT / "firmware/nrf5340/app/src/scci_rh_pins.h", ROOT / "firmware/nrf5340/app/prj.conf",
        ROOT / "firmware/nrf5340/app/app.overlay", ROOT / "firmware/nrf5340/core/scci_rh_runtime.c",
        ROOT / "firmware/nrf5340/core/scci_rh_runtime.h",
        ROOT / "electronics/stage4/integrated-pcb/firmware-profile/bt40f.conf"]


def main() -> None:
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
    env = dict(os.environ, NRFUTIL_HOME=str(tools / "nrfutil-home"))
    logs = ROOT / "tmp/nrf5340-uart-revision-build"
    logs.mkdir(parents=True, exist_ok=True)

    def execute(name: str, command: list[str]) -> str:
        result = subprocess.run(command, cwd=sdk, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        (logs / f"{name}.log").write_text(result.stdout, encoding="utf-8")
        if result.returncode:
            print(result.stdout[-14000:])
            raise RuntimeError(f"{name} failed; see {logs / (name + '.log')}")
        return result.stdout.strip()

    manager = execute("manager", [str(tools / "nrfutil.exe"), "sdk-manager", "toolchain", "env",
        "--ncs-version", VERSION, "--install-dir", str(tools / "ncs"), "--json"])
    records = [json.loads(line) for line in manager.splitlines() if line.strip()]
    variables = [v for r in records for v in r.get("data", {}).get("env_variables", [])]
    assert variables
    physical = str((tools / "ncs").resolve())
    for variable in variables:
        env[variable["key"]] = variable["value"].replace(physical, str(sdk_root)).replace(
            physical.replace("\\", "/"), sdk_root.as_posix())
    env["ZEPHYR_BASE"] = (sdk / "zephyr").as_posix()
    build = project / "build/stage4/nrf5340-uart-revision"
    assert build.resolve().is_relative_to(ROOT / "build")
    fragment = project / "electronics/stage4/integrated-pcb/firmware-profile/bt40f.conf"
    command = [str(sdk_python), "-m", "west", "build", "--no-sysbuild", "-b", BOARD,
        str(project / "firmware/nrf5340/uart-revision"), "-d", str(build),
        "--pristine=never" if args.incremental else "--pristine=always", "--",
        "-DPYTHON_EXECUTABLE=" + sdk_python.as_posix(),
        "-DPython3_EXECUTABLE=" + sdk_python.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        "-DEXTRA_CONF_FILE=" + fragment.as_posix()]
    started = time.perf_counter()
    output = execute("build", command)
    elapsed = time.perf_counter() - started
    print(output[-2000:])
    artifacts = HERE / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    for source, target in {"zephyr.elf": "scci_rh.elf", "zephyr.hex": "scci_rh.hex", "zephyr.bin": "scci_rh.bin",
            "zephyr.map": "scci_rh.map", ".config": "build.config", "zephyr.dts": "zephyr.dts"}.items():
        shutil.copyfile(build / "zephyr" / source, artifacts / target)
    size = execute("size", [str(compiler / "arm-zephyr-eabi-size.exe"), "-A", str(artifacts / "scci_rh.elf")])
    symbols = execute("symbols", [str(compiler / "arm-zephyr-eabi-nm.exe"), "--print-size", "--size-sort",
        str(artifacts / "scci_rh.elf")])
    (artifacts / "symbols.txt").write_text(symbols + "\n", encoding="utf-8")
    (artifacts / "sections.txt").write_text(size + "\n", encoding="utf-8")
    compiled = json.loads((build / "compile_commands.json").read_text(encoding="utf-8"))
    selected = [record for record in compiled if Path(record["file"]).name in
        {"system_nrf5340_application.c", "scci_rh_backend.c", "scci_rh_runtime.c", "main.c"}]
    assert {Path(record["file"]).name for record in selected} == {
        "system_nrf5340_application.c", "scci_rh_backend.c", "scci_rh_runtime.c", "main.c"}
    (artifacts / "compile-records.json").write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
    versions = {
        "compiler": execute("compiler", [str(compiler / "arm-zephyr-eabi-gcc.exe"), "--version"]),
        "west": execute("west", [str(sdk_python), "-m", "west", "--version"]),
        "cmake": execute("cmake", [str(toolchain / "opt/bin/cmake.exe"), "--version"]),
        "ninja": execute("ninja", [str(toolchain / "opt/bin/ninja.exe"), "--version"])}
    receipt = {"schema": "scci_rh.uart-revision.target-build.v1", "date": "2026-10-28", "original_design_date": "2026-10-17",
        "status": "scci_rh_application_cross_compiled_and_linked", "hardware_carrier": "Fanstel BT40F",
        "internal_HFXO_capacitance_pF": 11, "sdk_version": VERSION, "board": BOARD,
        "toolchain_bundle_id": "4f5b6ad6dd", "versions": versions,
        "source_sha256_lf": {p.relative_to(ROOT).as_posix(): sha(p, True) for p in sorted(sources())},
        "artifact_hash_policy": "Exact ELF/BIN bytes; LF-normalized UTF-8 for text exports",
        "artifact_sha256": {p.relative_to(ROOT).as_posix(): sha(p, p.suffix not in {".elf", ".bin"})
            for p in sorted(artifacts.iterdir()) if p.is_file()},
        "build_command": command, "build_elapsed_s": round(elapsed, 3), "incremental": args.incremental,
        "gnu_size_output": size, "historical_firmware_preserved": True,
        "flashed_or_executed": False, "hardware_timing_verified": False,
        "physical_peripheral_behavior_verified": False, "network_core_image_built": False,
        "full_450k_monitor_profile_implemented": False,
        "change": "UART queue ownership is retained through a complete envelope; priority switches only between frames",
        "limitations": ["Compiled and linked only; no hardware, implant or biological execution",
            "FIFO-stub regression does not measure physical UART behavior or WCET",
            "Existing polling gaps, write-only DAC, observation-only RHD and trusted companion assumptions remain",
            "No radio/network-core image, autonomous spinal policy or retained biological learning demonstrated"]}
    (HERE / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "elf_sha256": sha(artifacts / "scci_rh.elf"),
        "flashed_or_executed": False}, indent=2))


if __name__ == "__main__":
    main()
