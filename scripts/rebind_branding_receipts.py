"""Plan or explicitly rebind hash references after the authorized brand migration.

Default mode is read-only. --apply updates project-owned text, gzip JSON and,
when --archives is also passed, text metadata members of ZIP packages. No native
geometry, compiled image, numeric study output or historical Git object is edited.
Every hash replacement derives from an original/current file pair in the saved
pre-migration inventory. This is metadata maintenance, not renewed validation;
independent checks and derivative attestations must run afterward.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

try:
    from project_branding import retired_artifact
except ModuleNotFoundError:
    from scripts.project_branding import retired_artifact

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT/"provenance/project-name-migration.json"
TEXT_SUFFIXES = {".py", ".txt", ".md", ".json", ".csv", ".yml", ".yaml", ".xml", ".svg",
                 ".html", ".css", ".js", ".mjs", ".cff", ".bib", ".kicad_sch", ".kicad_pcb",
                 ".kicad_sym", ".kicad_mod", ".kicad_pro", ".kicad_dru", ".c", ".h", ".config",
                 ".dts", ".map", ".ps1", ".cmd", ".fcmacro", ".cir", ".sch", ".net"}
EXCLUDED = {"scripts/project_branding.py", "scripts/rebind_branding_receipts.py",
            "provenance/project-name-migration.json", "provenance/project-name-derivatives.json",
            "provenance/project-name-retirements.json",
            "provenance/project-name-migration-validation.json", "provenance/manifest.sha256"}
HEX = re.compile(r"(?<![0-9a-fA-F])(?:[0-9a-f]{64}|[0-9a-f]{40})(?![0-9a-fA-F])")


def sha(data: bytes, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, data).hexdigest()


def canonical_json(data: bytes, compressed: bool = False) -> bytes | None:
    try:
        raw = gzip.decompress(data) if compressed else data
        if len(raw) >= 1_000_000:
            return None
        return json.dumps(json.loads(raw.decode("utf-8-sig")), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError, OSError, EOFError):
        return None


def variants(data: bytes, suffix: str) -> dict[str, str]:
    result = {"sha256": sha(data), "sha256_lf": sha(data.replace(b"\r\n", b"\n")),
              "sha1": sha(data, "sha1"), "sha1_lf": sha(data.replace(b"\r\n", b"\n"), "sha1")}
    if suffix in {".json", ".gz"} and len(data) < 1_000_000:
        canonical = canonical_json(data, suffix == ".gz")
        if canonical is not None:
            result["canonical_json_sha256"] = sha(canonical)
    return result


def owned(name: str) -> bool:
    return (name not in EXCLUDED and not name.startswith(("inspector/vendor/", "tmp/", ".git/")) and
            "__pycache__" not in Path(name).parts)


def original_variants(inventory: dict) -> dict[str, dict[str, str]]:
    names = [row["path"] for row in inventory["files"]]
    result = {}
    with subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        try:
            for name in names:
                process.stdin.write((inventory["original_commit"]+":"+name+"\n").encode("utf-8"))
                process.stdin.flush()
                header = process.stdout.readline().decode("ascii").strip().split()
                if len(header) != 3 or header[1] != "blob":
                    raise AssertionError("Missing original Git blob: " + name)
                data = process.stdout.read(int(header[2]))
                if process.stdout.read(1) != b"\n":
                    raise AssertionError("Malformed historical Git response")
                result[name] = variants(data, Path(name).suffix.lower())
        finally:
            process.stdin.close()
            process.stdout.close()
            if process.wait() != 0:
                raise AssertionError("Original Git reader failed")
    return result


def current_variants(inventory: dict, cache: dict) -> dict[str, dict[str, str]]:
    result = {}
    for row in inventory["files"]:
        name = row["new_path"]
        path = ROOT/name
        if not path.is_file():
            if retired_artifact(ROOT, name):
                continue
            raise AssertionError("Missing migrated artifact: " + name)
        stat = path.stat()
        identity = (stat.st_mtime_ns, stat.st_size)
        if tuple(cache.get(name, (None,))[0] or ()) != identity:
            previous = cache.get(name)
            actual = variants(path.read_bytes(), path.suffix.lower())
            cache[name] = identity, actual
            # External native generators and report writers can change a file
            # between rounds. Retain their prior hashes for downstream receipts.
            if previous is not None:
                cache.setdefault('__external_transitions__', {}).update({previous[1][key]: actual[key]
                    for key in previous[1].keys() & actual.keys() if previous[1][key] != actual[key]})
        result[row["path"]] = cache[name][1]
    return result


def digest_map(originals: dict, current: dict, inventory: dict) -> tuple[dict[str, str], list[dict]]:
    destinations = defaultdict(set)
    sources = defaultdict(list)
    for row in inventory["files"]:
        name = row["path"]
        if name not in current:
            continue  # Only explicitly verified retired captures may be absent.
        if row["new_path"] in EXCLUDED or row["new_path"].startswith("inspector/vendor/"):
            continue
        before = dict(originals[name])
        # Working-tree raw bytes can differ from canonical Git bytes. Include
        # each original inventory representation only with its matching rule.
        before["inventory_raw"] = row["sha256"]
        before["inventory_lf"] = row["sha256_lf"]
        after = dict(current[name])
        after["inventory_raw"] = after["sha256"]
        after["inventory_lf"] = after["sha256_lf"]
        for kind, old in before.items():
            if kind not in after:
                continue
            new = after[kind]
            destinations[old].add(new)
            sources[old].append({"path": row["new_path"], "representation": kind, "current": new})
    mapping, conflicts = {}, []
    for old, values in destinations.items():
        if len(values) == 1:
            new = next(iter(values))
            if old != new:
                mapping[old] = new
            continue
        # LF-sensitive reports and Git blobs use normalized text by default;
        # a raw CRLF digest cannot be disambiguated from an old LF digest by a
        # blind replacement. Such ambiguity is reported and never guessed.
        conflicts.append({"original_digest": old, "candidates": sources[old]})
    return mapping, conflicts


def update_text(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    count = 0
    def replace(match):
        nonlocal count
        # SHA-named archived inspector files retain their historical names.
        if text[match.end():].startswith(".py.txt"):
            return match[0]
        replacement = mapping.get(match[0], match[0])
        count += replacement != match[0]
        return replacement
    return HEX.sub(replace, text), count


def update_payload(data: bytes, suffix: str, mapping: dict[str, str]) -> tuple[bytes, int]:
    compressed = suffix == ".gz"
    if compressed:
        raw = gzip.decompress(data)
        if not raw.lstrip().startswith((b"{", b"[")):
            raise ValueError("Compressed input is not a JSON document")
    else:
        raw = data
    text = raw.decode("utf-8-sig")
    updated, count = update_text(text, mapping)
    if not count:
        return data, 0
    result = updated.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf") and not compressed:
        result = b"\xef\xbb\xbf" + result
    return (gzip.compress(result, compresslevel=9, mtime=0) if compressed else result), count


def update_archive(data: bytes, mapping: dict[str, str]) -> tuple[bytes, int]:
    output, count, changed = io.BytesIO(), 0, {}
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        for info in source.infolist():
            if not info.is_dir() and Path(info.filename).suffix.lower() in TEXT_SUFFIXES:
                try:
                    member, changes = update_payload(source.read(info.filename), Path(info.filename).suffix.lower(), mapping)
                    count += changes
                    if changes:
                        changed[info.filename] = member
                except UnicodeError:
                    pass
        if not count:
            return data, 0
        with zipfile.ZipFile(output, "w") as target:
            for info in source.infolist():
                target.writestr(info, changed.get(info.filename, source.read(info.filename)))
    return output.getvalue(), count


def reference_tokens(data: bytes, suffix: str) -> set[str]:
    """Read a target once to cache all possible replaceable hash references."""
    if suffix == '.zip':
        result=set()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for item in archive.infolist():
                if not item.is_dir() and Path(item.filename).suffix.lower() in TEXT_SUFFIXES:
                    try:result.update(reference_tokens(archive.read(item.filename), Path(item.filename).suffix.lower()))
                    except UnicodeError:pass
        return result
    raw=gzip.decompress(data) if suffix=='.gz' else data
    text=raw.decode('utf-8-sig')
    return {match[0] for match in HEX.finditer(text) if not text[match.end():].startswith('.py.txt')}


def write_checkpoint(path: Path, state: dict) -> None:
    """Atomic checkpoints survive interruption without claiming completion."""
    path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_suffix(path.suffix+'.pending')
    pending.write_text(json.dumps(state,separators=(',',':'))+'\n',encoding='utf-8')
    pending.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Explicitly write rebound receipt metadata")
    parser.add_argument("--archives", action="store_true", help="Also update text metadata members in ZIP packages")
    parser.add_argument("--iterations", type=int, default=24)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--checkpoint", type=Path, default=ROOT/'tmp/branding-rebind-checkpoint.json')
    parser.add_argument("--fresh", action='store_true', help='Ignore an existing cache/checkpoint')
    args = parser.parse_args()
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8-sig"))
    identity=sha(INVENTORY.read_bytes())
    checkpoint=args.checkpoint.resolve()
    if not checkpoint.is_relative_to(ROOT):raise AssertionError('Checkpoint must remain inside project')
    state={}
    if checkpoint.is_file() and not args.fresh:
        candidate=json.loads(checkpoint.read_text())
        if candidate.get('inventory_sha256')==identity and candidate.get('original_commit')==inventory['original_commit']:
            state=candidate
    originals=state.get('originals')
    if originals is None:
        print("Reading original file digests (bounded canonical metadata only).", flush=True)
        originals = original_variants(inventory)
        print("Original digest inventory complete.", flush=True)
    else:print('Resuming exact original/current digest checkpoint.',flush=True)
    cache, rounds, combined = state.get('current_cache',{}),state.get('rounds',[]),state.get('combined',{})
    references=state.get('references',{})
    def save_state():
        if args.apply:write_checkpoint(checkpoint,{'schema':'project-name-rebind-checkpoint.v1',
            'inventory_sha256':identity,'original_commit':inventory['original_commit'],
            'originals':originals,'current_cache':cache,'rounds':rounds,'combined':combined,'references':references})
    save_state()
    targets = [row["new_path"] for row in inventory["files"] if owned(row["new_path"])]
    conflicts = []
    for number in range(args.iterations if args.apply else 1):
        current = current_variants(inventory, cache)
        combined.update(cache.pop('__external_transitions__',{}))
        mapping, conflicts = digest_map(originals, current, inventory)
        combined.update(mapping)
        # Resolve chains caused by an earlier metadata round. Original keys
        # always resolve to the current bytes; this does not replace numbers.
        for key in list(combined):
            value, seen = combined[key], {key}
            while value in combined and combined[value] != value:
                if value in seen:
                    raise AssertionError("Cyclic digest replacement identity")
                seen.add(value)
                value = combined[value]
            combined[key] = value
        changes = []
        for name in targets:
            path = ROOT/name
            if not path.is_file() and retired_artifact(ROOT, name):
                continue
            suffix = path.suffix.lower()
            if suffix not in TEXT_SUFFIXES|{".gz"} and not (args.archives and suffix == ".zip"):
                continue
            stat=path.stat();file_identity=[stat.st_mtime_ns,stat.st_size]
            entry=references.get(name)
            if entry is not None and entry['identity']==file_identity:
                if not set(entry['tokens']).intersection(combined):continue
            data = path.read_bytes()
            try:
                if entry is None or entry['identity']!=file_identity:
                    entry={'identity':file_identity,'tokens':sorted(reference_tokens(data,suffix))}
                    references[name]=entry
                if not set(entry['tokens']).intersection(combined):continue
                updated, count = update_archive(data, combined) if suffix == ".zip" else update_payload(data, suffix, combined)
            except (UnicodeError, ValueError, OSError):
                continue
            if count:
                changes.append({"path": name, "digest_references": count, "before_sha256": sha(data), "after_sha256": sha(updated)})
                if args.apply:
                    # Save the prior current digest identity too: downstream
                    # receipts may already have been partially rebound.
                    prior = variants(data, suffix)
                    after = variants(updated, suffix)
                    for kind in prior.keys() & after.keys():
                        if prior[kind] != after[kind]:
                            combined[prior[kind]] = after[kind]
                    path.write_bytes(updated)
                    stat=path.stat()
                    references[name]={'identity':[stat.st_mtime_ns,stat.st_size],
                        'tokens':sorted({combined.get(token,token) for token in entry['tokens']})}
                    cache[name]=((stat.st_mtime_ns,stat.st_size),after)
        rounds.append({"round": number+1, "changed_files": changes})
        save_state()
        print(json.dumps({"mode": "apply" if args.apply else "plan", "round": number+1,
                          "unambiguous_digest_mappings": len(mapping), "ambiguous_digest_mappings": len(conflicts),
                          "files_with_references": len(changes), "references": sum(item["digest_references"] for item in changes)}), flush=True)
        if not changes or not args.apply:
            break
    else:
        raise AssertionError("Receipt hash graph did not stabilize; inspect cyclic or stale references")
    report = {"schema": "project-name-receipt-rebind.v1", "original_commit": inventory["original_commit"],
              "applied": args.apply, "scope": "Hash metadata only; does not claim validation or rerun experiments",
              "rounds": rounds, "ambiguous_mappings_not_replaced": conflicts,
              "excluded_historical_identity_paths": sorted(EXCLUDED)}
    if args.report:
        destination = args.report.resolve()
        if not destination.is_relative_to(ROOT):
            raise AssertionError("Report must remain inside the project")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
