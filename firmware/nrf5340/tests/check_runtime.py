"""Compile and exercise the production C policy core; default is read-only.

No target peripherals or biological response are emulated by these tests.
Packet fixture encoding and CRC come from Python's standard library, independent
of the C parser. Binaries are created in a temporary directory and discarded.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib

BASE = Path(__file__).resolve().parents[1]
REPORT = BASE / "runtime-tests.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def compiler() -> list[str]:
    if os.environ.get("CC"):
        import shlex
        return shlex.split(os.environ["CC"])
    for name in ("cc", "gcc", "clang"):
        found = shutil.which(name)
        if found:
            return [found]
    zig = Path(r"E:\project workspace assests\tool readiness\zig\zig-x86_64-windows-0.15.2\zig.exe")
    if zig.exists():
        return [str(zig), "cc"]
    raise SystemExit("A native C11 compiler is required; set CC or install GCC/Clang/Zig.")


def run() -> dict:
    packet = struct.pack("<2sBBIIQQQHHffI", b"AT", 1, 2, 7, 1,
                         1500000, 1600000, 1700000, 12, 0, 120., 5., 1)
    crc = zlib.crc32(packet)
    packet += struct.pack("<I", crc)
    assert len(packet) == 56
    with tempfile.TemporaryDirectory(prefix="scci_rh-runtime-") as temporary:
        temp = Path(temporary)
        (temp / "packet_fixture.h").write_text(
            "static const unsigned char fixture_packet[56]={" +
            ",".join(str(x) for x in packet) + "};\n" +
            f"static const unsigned int fixture_crc={crc}u;\n", encoding="utf-8")
        binary = temp / ("runtime_test.exe" if os.name == "nt" else "runtime_test")
        cmd = compiler() + ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-Wpedantic", "-I", str(BASE / "core"), "-I", str(temp),
                            str(BASE / "core" / "scci_rh_runtime.c"),
                            str(BASE / "tests" / "runtime_test.c"), "-o", str(binary)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        complete = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        report = json.loads(complete.stdout)
    return {"schema": "scci_rh-nrf5340-runtime-tests-v1", "date": "2026-10-28", "original_design_date": "2026-10-14",
            "scope": "Compiled production C policy core; finite host fault scenarios, no physical or biological validation",
            "source_sha256_lf": {str(p.relative_to(BASE)).replace("\\", "/"): digest(p)
                                  for p in (BASE / "core" / "scci_rh_runtime.h",
                                            BASE / "core" / "scci_rh_runtime.c",
                                            BASE / "tests" / "runtime_test.c",
                                            BASE / "tests" / "check_runtime.py")},
            "packet_fixture_sha256": hashlib.sha256(packet).hexdigest(),
            "compiled_results": report}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-results", action="store_true")
    args = parser.parse_args()
    try:
        actual = run()
    except subprocess.CalledProcessError as exc:
        print(exc.stdout or "")
        print(exc.stderr or "")
        raise SystemExit(exc.returncode) from exc
    if args.write_results:
        REPORT.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    else:
        expected = json.loads(REPORT.read_text(encoding="utf-8"))
        if actual != expected:
            raise SystemExit("Runtime tests or source identity differ from saved results.")
    print(json.dumps(actual["compiled_results"], sort_keys=True))


if __name__ == "__main__":
    main()
