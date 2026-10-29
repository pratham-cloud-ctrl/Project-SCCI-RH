"""Compile an unmodified Nordic/Zephyr example for the proposed application core.

This is a local Windows installation smoke check, not SCCI_RH target firmware,
flashing, execution timing, peripheral integration or memory-budget closure.
Use the documented short physical SDK copy and project junction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v3.4.1"
BOARD = "nrf5340dk/nrf5340/cpuapp"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, default=Path("E:/SCCI_RH-Tools"))
    parser.add_argument("--project-alias", type=Path, default=Path("E:/SCCI_RH"))
    parser.add_argument("--sdk-install-root", type=Path, default=Path("E:/SCCI_RH-Nordic/ncs"))
    args = parser.parse_args()
    tools = args.tools.absolute()  # Original installer and manager metadata.
    project = args.project_alias.absolute()
    assert project.resolve() == ROOT, "Project alias must resolve to this repository"
    assert " " not in str(tools) and " " not in str(project), "SDK/build paths require no spaces"
    sdk_root = args.sdk_install_root.absolute()
    assert " " not in str(sdk_root.resolve()), "SDK physical path must contain no spaces"
    sdk = sdk_root / VERSION
    example = sdk / "zephyr/samples/hello_world"
    executable = tools / "nrfutil.exe"
    assert executable.is_file(), "Verified Nordic installer not found"
    assert (example / "src/main.c").is_file(), "Complete SDK installation is required"
    build = project / "build/stage4/nordic-toolchain-smoke"
    assert build.resolve().is_relative_to(ROOT / "build"), "Build must stay inside this repository"
    env = dict(os.environ, NRFUTIL_HOME=str(tools / "nrfutil-home"))
    logs = ROOT / "tmp/nordic-toolchain-check"
    logs.mkdir(parents=True, exist_ok=True)

    def execute(name, command):
        completed = subprocess.run(command, cwd=sdk, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        (logs / f"{name}.log").write_text(completed.stdout, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(f"{name} failed; inspect {logs / (name + '.log')}")
        return completed.stdout.strip()

    # The SDK canonicalizes module paths, so a junction cannot conceal the
    # asset directory's spaces. Use the complete short physical copy while
    # preserving the original installation. Rebase the supported environment
    # only in this child process; no SDK source or global environment changes.
    manager_environment = execute("manager-environment", [str(executable), "sdk-manager",
        "toolchain", "env", "--ncs-version", VERSION, "--install-dir", str(tools / "ncs"), "--json"])
    records = [json.loads(line) for line in manager_environment.splitlines() if line.strip()]
    variables = [v for record in records for v in record.get("data", {}).get("env_variables", [])]
    assert variables, "Manager returned no environment"
    physical = str((tools / "ncs").resolve())
    for variable in variables:
        value = variable["value"].replace(physical, str(sdk_root)).replace(
            physical.replace("\\", "/"), sdk_root.as_posix())
        env[variable["key"]] = value
    env["NRFUTIL_HOME"] = str(tools / "nrfutil-home")
    toolchain = sdk_root / "toolchains/4f5b6ad6dd"
    sdk_python = toolchain / "opt/bin/python.exe"
    compiler_bin = toolchain / "opt/zephyr-sdk/gnu/arm-zephyr-eabi/bin"
    env["ZEPHYR_BASE"] = (sdk / "zephyr").as_posix()
    prefix = [str(sdk_python), "-m", "west"]
    versions = {
        "nrfutil": execute("nrfutil-version", [str(executable), "--version"]),
        "compiler": execute("compiler-version", [str(compiler_bin / "arm-zephyr-eabi-gcc.exe"), "--version"]),
        "west": execute("west-version", prefix + ["--version"]),
        "cmake": execute("cmake-version", [str(toolchain / "opt/bin/cmake.exe"), "--version"]),
        "ninja": execute("ninja-version", [str(toolchain / "opt/bin/ninja.exe"), "--version"]),
    }
    command = prefix + ["build", "--no-sysbuild", "-b", BOARD, str(example),
                        "-d", str(build), "--pristine=always", "--",
                        "-DPYTHON_EXECUTABLE=" + sdk_python.as_posix(),
                        "-DPython3_EXECUTABLE=" + sdk_python.as_posix()]
    started = time.perf_counter()
    execute("hello-world-build", command)
    elapsed = time.perf_counter() - started
    elf = build / "zephyr/zephyr.elf"
    assert elf.is_file() and elf.stat().st_size > 0, "No linked application-core ELF"
    section_sizes = execute("elf-size", [str(compiler_bin / "arm-zephyr-eabi-size.exe"), str(elf)])
    example_text = (example / "src/main.c").read_text(encoding="utf-8").replace("\r\n", "\n")
    receipt = {
        "schema": "scci_rh.stage4.nordic-toolchain-smoke.v1", "date": "2026-10-12",
        "status": "unmodified_example_cross_compilation_passed",
        "scope": "Installed tools and linked Nordic/Zephyr hello_world application-core example only",
        "sdk_version": VERSION, "board": BOARD, "versions": versions,
        "nrfutil_sha256": sha(executable),
        "example_main_normalized_sha256": hashlib.sha256(example_text.encode()).hexdigest(),
        "build_command": command, "build_elapsed_s": round(elapsed, 3),
        "elf_sha256": sha(elf), "elf_bytes": elf.stat().st_size, "gnu_size_output": section_sizes,
        "physical_tool_directory": str(tools.resolve()), "tool_alias": str(tools),
        "toolchain_bundle_id": "4f5b6ad6dd",
        "physical_sdk_install_root": str(sdk_root.resolve()),
        "original_asset_installation_preserved": True,
        "child_environment_path_rebase": {"from": physical, "to": str(sdk_root)},
        "project_alias": str(project),
        "scci_rh_firmware_integrated": False, "flashed_or_executed": False,
        "target_timing_verified": False, "scci_rh_memory_budget_closed": False,
        "limitations": ["No output driver, ADC/DMA/timer backend, network image or SCCI_RH controller compiled here",
                        "Example section sizes are not full-system linked RAM/flash evidence",
                        "Compilation does not measure hardware behavior, deadlines or current consumption"],
    }
    target = ROOT / "provenance/stage4-nordic-toolchain-smoke.json"
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "board": BOARD,
                      "sdk_version": VERSION, "scci_rh_firmware_integrated": False}, indent=2))


if __name__ == "__main__":
    main()
