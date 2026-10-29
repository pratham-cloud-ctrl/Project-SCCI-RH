"""Run the unmodified frozen pilot/auditor in an exact-byte disposable layout.

Two inherited JSON contexts were frozen with CRLF, while their existing Git
blobs use LF. Restore only newline representation in scratch, accepting it only
if the complete original approved SHA256 matches. No source/results are edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PILOT = Path("experiments/stage3/frozen-observer-pilot")
OBSERVER = Path("experiments/stage3/observed-state-observer")
AUDITOR = Path("scripts/audit_frozen_observer_pilot.py")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT,
                        help="Repository checkout to verify without modifying it")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--reproduce", action="store_true")
    args = parser.parse_args()
    ROOT = args.source_root.resolve()
    if args.audit_only and args.reproduce:
        parser.error("--audit-only and --reproduce are mutually exclusive")
    preflight = json.loads((ROOT / PILOT / "preflight.json").read_text(encoding="utf-8"))
    bindings = preflight["bindings"]
    copies = dict(bindings["inputs_bytes_sha256"])
    copies.update(bindings["bound_scci_rh_source_bytes_sha256"])
    copies[bindings["dynamic_raw"]["path"]] = bindings["dynamic_raw"]["sha256"]
    # Inherited summaries also bind their producer scripts by normalized text.
    for name, key in (("results/stage3/dynamic-response/dynamic-response-summary.json", "source_sha256"),
                      ("results/stage3/resolved-teacher/summary.json", "source_identity")):
        receipt = json.loads((ROOT / name).read_text(encoding="utf-8"))
        for rel, expected in receipt[key].items():
            content = (ROOT / rel).read_bytes()
            assert digest(content.replace(b"\r\n", b"\n")) == expected, "Inherited producer changed: " + rel
            copies.setdefault(rel, digest(content))
    # This optional historical summary participates in the frozen noise ledger.
    old = Path("results/stage3/isolated-pilot/summary.json")
    copies[old.as_posix()] = digest((ROOT / old).read_bytes())
    originals = {rel: digest((ROOT / rel).read_bytes()) for rel in copies}
    originals[AUDITOR.as_posix()] = digest((ROOT / AUDITOR).read_bytes())
    for package in (PILOT, OBSERVER):
        for path in (ROOT / package).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                originals[path.relative_to(ROOT).as_posix()] = digest(path.read_bytes())
    parent = ROOT / "tmp"
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scci_rh-pilot-portable-", dir=parent) as directory:
        scratch = Path(directory).resolve()
        assert scratch.is_relative_to(parent.resolve())
        for rel in originals:
            destination = scratch / rel
            assert destination.resolve().is_relative_to(scratch)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, destination)
        restored = []
        for rel, expected in copies.items():
            path = scratch / rel
            data = path.read_bytes()
            if digest(data) != expected:
                # Bound inputs are JSON; never rewrite frozen Python or raw data.
                if rel not in bindings["inputs_bytes_sha256"] or path.suffix != ".json":
                    raise AssertionError("Approved input bytes changed: " + rel)
                candidate = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                if digest(candidate) != expected or json.loads(candidate) != json.loads(data):
                    raise AssertionError("Cannot recover approved newline-only context: " + rel)
                path.write_bytes(candidate)
                restored.append(rel)
        environment = os.environ.copy()
        environment.update(PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1",
                           OMP_NUM_THREADS="1", PYTHONPATH=str(scratch / "src"))
        print("Exact original input hashes verified; scratch newline restorations:", restored, flush=True)
        if not args.audit_only:
            command = [sys.executable, "-X", "utf8", str(scratch / PILOT / "verify_study.py")]
            if args.reproduce:
                command.append("--reproduce")
            subprocess.run(command, cwd=scratch, env=environment, check=True)
        subprocess.run([sys.executable, "-X", "utf8", str(scratch / AUDITOR)],
                       cwd=scratch, env=environment, check=True)
        for rel, expected in originals.items():
            assert digest((ROOT / rel).read_bytes()) == expected, "Original changed: " + rel
        assert scratch.is_relative_to(parent.resolve())
    print("Portable frozen verification passed; repository originals unchanged.")


if __name__ == "__main__":
    main()
