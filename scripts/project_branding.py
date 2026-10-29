"""Explicit, bounded project-brand migration and historical identity helpers.

This module is a migration adapter, not a claim that historical Git objects
were renamed. Git commits remain immutable. Comparators may accept only exact
branding transformations, or a separately named and validated derivative rule.
"""
from __future__ import annotations

from functools import lru_cache
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
from typing import Callable
import zipfile

DISPLAY_NAME = "Project SCCI RH"
REPOSITORY_NAME = "Project-SCCI-RH"
NAMESPACE = "scci_rh"

_PHRASES = (
    ("PROJECT ATO", "PROJECT SCCI RH"),
    ("Project ATO", DISPLAY_NAME),
    ("project ATO", "project SCCI RH"),
    ("project ato", "project scci rh"),
    ("Project-ATO", REPOSITORY_NAME),
    ("PROJECT-ATO", "PROJECT-SCCI-RH"),
    ("project-ato", "project-scci-rh"),
    ("Project_ATO", "Project_SCCI_RH"),
    ("PROJECT_ATO", "PROJECT_SCCI_RH"),
    ("project_ato", "project_scci_rh"),
    ("libato_", "libscci_rh_"),
    ("-DATO_SHARED", "-DSCCI_RH_SHARED"),
    ("%~dp0ATO_", "%~dp0SCCI_RH_"),
    ("sameato_runtime.c", "samescci_rh_runtime.c"),
    ("ATOPART", "SCCIRHPART"),
    ("ATO2Bold", "SCCIRH2Bold"),
    ("ATO2", "SCCIRH2"),
    ("ATO3CBold", "SCCIRH3CBold"),
    ("ATO3Bold", "SCCIRH3Bold"),
    ("ATO3C", "SCCIRH3C"),
    ("ATO3", "SCCIRH3"),
)
_STYLE_IDENTIFIERS = (
    "BodyATO", "HeadingATO", "SubATO", "CaptionATO", "CellATO", "CodeATO",
    "ATOMono", "ATOBold",
)


def rename_text(value: str) -> str:
    """Rename complete brand tokens without altering operator/generator/etc.

    Underscores are intentionally separators: this updates C macros, modules,
    schema names, named CAD files and imported project library identifiers.
    Alphanumeric interiors of ordinary words are deliberately not matched.
    """
    result = value
    for previous, current in _PHRASES:
        result = result.replace(previous, current)
    for previous in _STYLE_IDENTIFIERS:
        result = result.replace(previous, previous.replace("ATO", "SCCI_RH"))
    for previous, current in (("ATO", "SCCI_RH"), ("ato", NAMESPACE), ("Ato", "ScciRh")):
        result = re.sub(r"(?<![A-Za-z0-9])" + previous + r"(?![A-Za-z0-9])", current, result)
    # Clearly namespaced camel-case identifiers retain their casing convention.
    for previous, current in (("ATO", "SCCIRH"), ("Ato", "ScciRh"), ("ato", "scciRh")):
        result = re.sub(r"(?<![A-Za-z0-9])" + previous + r"(?=[A-Z][a-z])", current, result)
    # Human title blocks use the display name; electrical/library IDs retain
    # their syntax-safe namespace.
    result = re.sub(r'(\(title ")SCCI_RH(?=[ /])', r'\1Project SCCI RH', result)
    return result


def rename_path(value: str | Path) -> str:
    """Map a path/reference while preserving its slash representation."""
    return rename_text(str(value))


def normalized_text_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def renamed_text_bytes(data: bytes) -> bytes:
    """Use only for decoded authored text, never for binary search/replace."""
    return rename_text(data.decode("utf-8-sig")).encode("utf-8")


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root)


@lru_cache(maxsize=24)
def historical_path_map(root: str, commit: str) -> dict[str, str]:
    """Map current paths back to actual immutable paths at one Git revision."""
    paths = _git(Path(root), "ls-tree", "-r", "--name-only", "-z", commit).decode("utf-8").split("\0")
    mapped: dict[str, str] = {}
    for previous in filter(None, paths):
        current = rename_path(previous)
        if current in mapped and mapped[current] != previous:
            raise AssertionError("Brand migration path collision: " + current)
        mapped[current] = previous
    return mapped


def historical_path(root: Path, commit: str, current_path: str) -> str:
    """Resolve a historical Git query without inventing renamed Git objects."""
    relative = str(current_path).replace("\\", "/")
    return historical_path_map(str(root.resolve()), commit).get(relative, relative)


def historical_bytes(root: Path, commit: str, current_path: str) -> bytes:
    return _git(root, "show", commit + ":" + historical_path(root, commit, current_path))


def compare_renamed_bytes(previous: bytes, current: bytes, suffix: str = "") -> str | None:
    """Return an actual comparison rule, or None if equivalence is unproven.

    This deliberately refuses rendered PDFs/images, recompiled images and
    rebound hash receipts. Their regeneration requires separate evidence.
    """
    if previous == current:
        return "exact_bytes"
    suffix = suffix.lower()
    if suffix == ".gz":
        try:
            # Scientific captures can expand to hundreds of megabytes. Exact
            # uncompressed branding equality is stronger than reparsing and
            # canonicalizing that large numeric payload and avoids huge trees.
            before = normalized_text_bytes(renamed_text_bytes(gzip.decompress(previous)))
            after = normalized_text_bytes(gzip.decompress(current))
            if before == after:
                return "gzip_uncompressed_text_brand_equivalence"
        except (ValueError, UnicodeError, OSError, EOFError):
            pass
        return None
    if suffix in {".fcstd", ".zip"}:
        try:
            with zipfile.ZipFile(io.BytesIO(previous)) as old, zipfile.ZipFile(io.BytesIO(current)) as new:
                old_names, new_names = old.namelist(), new.namelist()
                if len(set(old_names)) != len(old_names) or len(set(new_names)) != len(new_names):
                    return None
                if {rename_path(name) for name in old_names} != set(new_names):
                    return None
                for name in old_names:
                    if name.endswith("/"):
                        continue
                    target = rename_path(name)
                    if compare_renamed_bytes(old.read(name), new.read(target), Path(name).suffix) is None:
                        return None
            return "archive_member_brand_equivalence"
        except (zipfile.BadZipFile, KeyError):
            return None
    if suffix == ".glb":
        try:
            def chunks(data: bytes):
                magic, version, length = struct.unpack_from("<4sII", data)
                if magic != b"glTF" or version != 2 or length != len(data):
                    raise ValueError("Invalid GLB")
                position, result = 12, []
                while position < len(data):
                    size, kind = struct.unpack_from("<II", data, position)
                    position += 8
                    payload = data[position:position+size]
                    if len(payload) != size:
                        raise ValueError("Truncated GLB")
                    result.append((kind, payload))
                    position += size
                return result
            old_chunks, new_chunks = chunks(previous), chunks(current)
            if len(old_chunks) != len(new_chunks):
                return None
            for (old_kind, old_data), (new_kind, new_data) in zip(old_chunks, new_chunks):
                if old_kind != new_kind:
                    return None
                if old_kind == 0x4E4F534A:
                    if json.loads(rename_text(old_data.decode("utf-8"))) != json.loads(new_data):
                        return None
                elif old_data != new_data:
                    return None
            return "glb_metadata_brand_equivalence_unchanged_geometry_buffers"
        except (ValueError, UnicodeError, struct.error):
            return None
    try:
        before = normalized_text_bytes(renamed_text_bytes(previous))
        after = normalized_text_bytes(current)
        if before == after:
            return "normalized_authored_text_brand_equivalence"
    except UnicodeError:
        pass
    return None


DerivativeValidator = Callable[[str, bytes, bytes], str | None]
RETIRED_BROWSER_CAPTURES = frozenset({
    "docs/explore/inspector-review/pcb-component.jpg",
    "docs/explore/inspector-review/reference-open.jpg",
})


def retired_artifact(root: Path, current_path: str, previous: bytes | None = None) -> str | None:
    """Recognize only two obsolete pre-rebrand browser evidence screenshots.

    This is deliberately not an arbitrary manifest-controlled deletion waiver.
    Each capture must be absent, explicitly retired and match its exact original
    immutable Git bytes. Its historical commit remains available for retrieval.
    """
    if current_path not in RETIRED_BROWSER_CAPTURES or (root/current_path).exists():
        return None
    manifest = root/"provenance/project-name-retirements.json"
    inventory_path = root/"provenance/project-name-migration.json"
    if not manifest.is_file() or not inventory_path.is_file():
        return None
    retirement, inventory = _read_json(manifest), _read_json(inventory_path)
    if retirement.get("schema") != "project-name-retirements.v1":
        raise AssertionError("Unknown retirement manifest schema")
    if retirement.get("original_commit") != inventory["original_commit"]:
        raise AssertionError("Retirement revision differs from original project inventory")
    rows = [row for row in retirement.get("files", []) if row.get("path") == current_path]
    originals = [row for row in inventory["files"] if row["new_path"] == current_path]
    if len(rows) != 1 or len(originals) != 1:
        raise AssertionError("Missing or duplicate original browser-capture retirement: " + current_path)
    row, original = rows[0], originals[0]
    if row.get("reason") != "historical_browser_capture_retired_after_rebrand":
        raise AssertionError("Retirement has no exact browser-capture reason: " + current_path)
    if row.get("original_sha256") != original["sha256"]:
        raise AssertionError("Retirement source differs from original inventory: " + current_path)
    commit = row.get("original_commit", retirement["original_commit"])
    if commit != inventory["original_commit"]:
        raise AssertionError("Retirement file uses an unapproved historical revision")
    data = previous if previous is not None else historical_bytes(root, commit, current_path)
    if hashlib.sha256(data).hexdigest() != row["original_sha256"]:
        raise AssertionError("Retirement differs from actual immutable Git bytes: " + current_path)
    return "historical_browser_capture_retired_after_rebrand"


@lru_cache(maxsize=8)
def _read_json_versioned(path: str, modified_ns: int, size: int) -> dict:
    """Cache only an exact local file revision during a read-only audit."""
    del modified_ns, size
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _read_json(path: Path) -> dict:
    stat = path.stat()
    return _read_json_versioned(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def attested_derivative(root: Path, current_path: str, previous: bytes, current: bytes) -> str | None:
    """Accept a specifically validated regenerated derivative, never a class exemption.

    Both original and current bytes must be recorded. Original identities are
    checked against the complete pre-migration inventory, while each named
    independent validation report is itself hash-bound. This records changed
    derivatives honestly rather than describing them as byte-unchanged files.
    """
    manifest = root/"provenance/project-name-derivatives.json"
    inventory = root/"provenance/project-name-migration.json"
    if not manifest.is_file() or not inventory.is_file():
        return None
    attestations, migration = _read_json(manifest), _read_json(inventory)
    if attestations.get("schema") != "project-name-derivatives.v1":
        raise AssertionError("Unknown name-migration derivative attestation schema")
    if attestations.get("original_commit") != migration["original_commit"]:
        raise AssertionError("Derivative attestation uses a different source migration")
    rows = attestations.get("files", [])
    matches = [row for row in rows if row.get("path", row.get("new_path")) == current_path]
    if len(matches) != 1:
        if matches:
            raise AssertionError("Duplicate derivative attestation: " + current_path)
        return None
    row = matches[0]
    originals = [item for item in migration["files"] if item["new_path"] == current_path]
    if len(originals) != 1:
        raise AssertionError("Derivative is not in the original source inventory: " + current_path)
    original = originals[0]
    old_lf = hashlib.sha256(normalized_text_bytes(previous)).hexdigest()
    old_raw = hashlib.sha256(previous).hexdigest()
    if old_lf != original["sha256_lf"] and old_raw != original["sha256"]:
        raise AssertionError("Attestation cannot replace a different historical file: " + current_path)
    if row.get("original_sha256_lf"):
        if row["original_sha256_lf"] != old_lf:
            raise AssertionError("Original LF identity differs: " + current_path)
    elif row.get("original_sha256") != old_raw:
        raise AssertionError("Missing or different original derivative identity: " + current_path)
    if row.get("current_sha256_lf"):
        actual = hashlib.sha256(normalized_text_bytes(current)).hexdigest()
        expected = row["current_sha256_lf"]
    else:
        actual = hashlib.sha256(current).hexdigest()
        expected = row.get("current_sha256", row.get("sha256"))
    if actual != expected:
        raise AssertionError("Current derivative differs from reviewed bytes: " + current_path)
    validation = row.get("validation", {})
    if validation.get("passed") is not True or not str(validation.get("method", "")).strip():
        raise AssertionError("Derivative lacks an actual named validation: " + current_path)
    evidence = validation.get("evidence", [])
    if not evidence:
        raise AssertionError("Derivative validation has no independent evidence: " + current_path)
    for item in evidence:
        proof = (root/item["path"]).resolve()
        if not proof.is_relative_to(root.resolve()) or not proof.is_file() or proof == (root/current_path).resolve():
            raise AssertionError("Invalid independent migration evidence path: " + item["path"])
        data = proof.read_bytes()
        if item.get("sha256_lf"):
            value = hashlib.sha256(normalized_text_bytes(data)).hexdigest()
            expected_proof = item["sha256_lf"]
        else:
            value = hashlib.sha256(data).hexdigest()
            expected_proof = item.get("sha256")
        if value != expected_proof:
            raise AssertionError("Migration evidence differs from its binding: " + item["path"])
    return "attested_regeneration:" + validation["method"]


def assert_baseline_equivalence(root: Path, commit: str,
                                entries: list[tuple[str, str]],
                                derivative_validator: DerivativeValidator | None = None) -> dict:
    """Check each old Git blob against its renamed current file.

    Callers retain their original baseline selection and counts. Optional
    derivative validators must return a meaningful named proof rule and should
    independently bind reviewed before/after hashes; this helper never silently
    exempts hashes, numbers, images, firmware or other metadata from comparison.
    """
    rows = []
    # One streaming Git process avoids thousands of process launches while
    # retaining the exact original object identity for every comparison.
    with subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        try:
            for previous_path, old_blob in entries:
                current_path = rename_path(previous_path)
                current_file = root/current_path
                process.stdin.write((old_blob + "\n").encode("ascii"))
                process.stdin.flush()
                header = process.stdout.readline().decode("ascii").strip().split()
                if len(header) != 3 or header[0] != old_blob or header[1] != "blob":
                    raise AssertionError("Original historical blob is unavailable: " + previous_path)
                previous = process.stdout.read(int(header[2]))
                if process.stdout.read(1) != b"\n":
                    raise AssertionError("Malformed historical Git blob framing")
                if not current_file.is_file():
                    retirement = retired_artifact(root, current_path, previous)
                    if retirement is None:
                        raise AssertionError("Missing renamed baseline file: " + current_path)
                    rows.append({"path": current_path, "original_git_blob": old_blob,
                                 "original_sha256": hashlib.sha256(previous).hexdigest(),
                                 "comparison": retirement})
                    continue
                current = current_file.read_bytes()
                # Reuse an independently established per-file proof only when
                # both exact historical/current identities and its evidence
                # still match. This avoids repeatedly inflating large frozen
                # captures in every aggregate audit; the proof writer performs
                # the actual semantic comparison before issuing this record.
                rule = (attested_derivative(root, current_path, previous, current)
                        if derivative_validator is None else None)
                if rule is None:
                    rule = compare_renamed_bytes(previous, current, current_file.suffix)
                if rule is None:
                    validator = derivative_validator or (lambda name, before, after: attested_derivative(root, name, before, after))
                    rule = validator(current_path, previous, current)
                if not rule:
                    raise AssertionError("Unproven change beyond branding: " + current_path)
                # Raw identity and LF-normalized authored-text identity are
                # equally strict accepted outcomes. Git may check out an
                # otherwise identical text file with LF or CRLF; use one
                # report label so that the evidence manifest is portable.
                # This changes reporting only, never the comparisons above.
                if rule in {"exact_bytes", "normalized_authored_text_brand_equivalence"}:
                    rule = "byte_or_LF_normalized_brand_equivalence"
                rows.append({"path": current_path, "original_git_blob": old_blob,
                             "current_sha256_lf": hashlib.sha256(normalized_text_bytes(current)).hexdigest(),
                             "comparison": rule})
        finally:
            process.stdin.close()
            process.stdout.close()
            if process.wait() != 0:
                raise AssertionError("Historical Git blob reader failed")
    serialized = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"baseline_commit": commit, "files_compared": len(rows),
            "comparison_manifest_sha256": hashlib.sha256(serialized).hexdigest(),
            "scope": "Explicit brand migration; original immutable Git identities remain available",
            "rules": sorted({row["comparison"] for row in rows})}
