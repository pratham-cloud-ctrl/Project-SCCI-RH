#!/usr/bin/env python3
"""Build source-bound browser inspections without saving the native engineering.

Use KiCad 10's Python, because the upstream iBOM exporter reads via pcbnew.
SVGs are rendered by native KiCad CLI; first publication also inspected the
exact hierarchy and exported schematics through the installed KiCad MCP.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "inspector"
NATIVE = ROOT / "electronics/stage4/integrated-pcb"
MASTER = NATIVE / "integration/master/SCCI_RH_integrated.kicad_sch"
VENDOR = OUT / "vendor/ibom"
PIN = "d1eb5b79a52a2ddc1ce270b63920346463c19b05"
BOARD_INFO = [
    ("recording-front-end", "Recording front end", 153, 0),
    ("controller-carrier", "Controller carrier", 68, 0),
    ("current-driver", "Current driver", 154, 2),
    ("contact-router", "Contact router", 155, 0),
    ("monitoring-cell", "Monitoring cell", 71, 0),
    ("supervision", "Independent supervision", 479, 0),
    ("monitoring-transport", "Monitoring and companion transport", 60, 0),
    ("power", "Power", 156, 0),
]
LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
NS = {"s": "http://www.w3.org/2000/svg"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def record(path):
    return {"path": relative(path), "bytes": Path(path).stat().st_size, "sha256": sha(path)}


def run(args, **kwargs):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True, encoding="utf-8", errors="replace", **kwargs)
    if result.returncode:
        raise RuntimeError(f"Command failed: {args}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def sexpr(path):
    """Minimal balanced reader, retaining KiCad strings exactly as strings."""
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', Path(path).read_text(encoding="utf-8"))
    stack, root = [], None
    for token in tokens:
        if token == "(":
            node = []
            if stack:
                stack[-1].append(node)
            else:
                root = node
            stack.append(node)
        elif token == ")":
            stack.pop()
        else:
            if token.startswith('"'):
                token = token[1:-1].replace('\\"', '"').replace('\\\\', '\\')
            stack[-1].append(token)
    if stack:
        raise ValueError(f"Unbalanced source {path}")
    return root


def children(node, name):
    return [x for x in node if isinstance(x, list) and x and x[0] == name]


def child(node, name, default=None):
    return next(iter(children(node, name)), default)


def normalise_svg(path):
    # Only metadata creation time is removed, never geometry or visible content.
    data = path.read_text(encoding="utf-8")
    data = re.sub(r'(<title>SVG Image created as .*?) date \d{4}-\d{2}-\d{2}T[^<]+(</title>)', r'\1\2', data)
    path.write_text(data, encoding="utf-8", newline="\n")


def sheet_index():
    result = []

    def walk(source, names, board, page, parent):
        node = sexpr(source)
        title_block = child(node, "title_block", [])
        title = child(title_block, "title", ["title", names[-1] if names else "Complete system"])[1]
        ident = f"sheet-{int(page):02d}"
        filename = "SCCI_RH_integrated" + ("-" + "-".join(names) if names else "") + ".svg"
        svg = OUT / "assets/schematics" / filename
        normalise_svg(svg)
        rendered = ET.parse(svg).getroot()
        texts = []
        for item in rendered.findall(".//s:text", NS):
            text = "".join(item.itertext()).strip()
            if not text:
                continue
            texts.append({"text": text, "x": float(item.attrib.get("x", 0)), "y": float(item.attrib.get("y", 0)),
                          "width": float(item.attrib.get("textLength", 0)),
                          "height": float(item.attrib.get("font-size", 1.27)),
                          "anchor": item.attrib.get("text-anchor", "start")})
        entry = {"id": ident, "title": title, "name": names[-1] if names else "Complete system", "page": int(page),
                 "board": board or "system", "parent": parent, "path": "/" + "/".join(names),
                 "svg": "assets/schematics/" + filename, "source": relative(source), "source_sha256": sha(source),
                 "svg_sha256": sha(svg), "viewBox": [float(v) for v in rendered.attrib["viewBox"].split()],
                 "text": "\n".join(dict.fromkeys(x["text"] for x in texts)), "texts": texts, "children": []}
        result.append(entry)
        for sheet in children(node, "sheet"):
            props = {x[1]: x[2] for x in children(sheet, "property")}
            name = props["Sheetname"]
            instance = child(sheet, "instances")
            project = next(x for x in children(instance, "project") if x[1] == "SCCI_RH_integrated")
            path = child(project, "path")
            childpage = child(path, "page")[1]
            entry["children"].append(f"sheet-{int(childpage):02d}")
            walk(source.parent / props["Sheetfile"], names + [name], board or name, childpage, ident)

    walk(MASTER, [], None, 1, None)
    assert len(result) == 80
    assert {x["page"] for x in result} == set(range(1, 81))
    assert len({x["source"] for x in result}) == 80
    return sorted(result, key=lambda x: x["page"])


def export_native(cli):
    destination = OUT / "assets/schematics"
    destination.mkdir(parents=True, exist_ok=True)
    run([cli, "sch", "export", "svg", "-o", str(destination) + os.sep, MASTER])
    for bid, _, _, _ in BOARD_INFO:
        board = NATIVE / "boards" / bid / (bid.replace("-", "_") + ".kicad_pcb")
        for layer in LAYERS:
            svg = OUT / "assets/copper" / bid / (layer.replace(".", "_") + ".svg")
            svg.parent.mkdir(parents=True, exist_ok=True)
            # The MCP wrapper has no page-size argument and defaults to A4.
            # Board-area native export avoids clipping boards larger than A4.
            run([cli, "pcb", "export", "svg", "--mode-single", "--page-size-mode", "2",
                 "--exclude-drawing-sheet", "--layers", layer + ",Edge.Cuts", "-o", svg, board])


def make_boards(sheets):
    import pcbnew
    script = VENDOR / "InteractiveHtmlBom/generate_interactive_bom.py"
    # Upstream version.py runs git describe. Do not accidentally describe SCCI_RH's
    # ancestor repository instead of the pinned vendored project.
    env = dict(os.environ, INTERACTIVE_HTML_BOM_NO_DISPLAY="1", PYTHONDONTWRITEBYTECODE="1",
               GIT_CEILING_DIRECTORIES=str(VENDOR.parent))
    boards = []
    all_dnp = []
    for bid, title, expected_fitted, expected_dnp in BOARD_INFO:
        source = NATIVE / "boards" / bid / (bid.replace("-", "_") + ".kicad_pcb")
        schematic = source.with_suffix(".kicad_sch")
        board = pcbnew.LoadBoard(str(source))
        footprints = list(board.GetFootprints())
        mechanical = [f for f in footprints if f.GetReference().startswith("H")]
        electrical = [f for f in footprints if f not in mechanical]
        dnp = sorted(f.GetReference() for f in electrical if f.IsDNP())
        fitted = sorted(f.GetReference() for f in electrical if not f.IsDNP())
        assert len(fitted) == expected_fitted, (bid, len(fitted))
        assert len(dnp) == expected_dnp
        assert len(mechanical) == 4
        all_dnp.extend(dnp)
        out = OUT / "pcb" / (bid + ".html")
        run([sys.executable, script, source, "--no-browser", "--dest-dir", out.parent,
             "--name-format", bid, "--include-tracks", "--include-nets", "--no-compression",
             "--layer-view", "F", "--bom-view", "left-right", "--checkboxes", "",
             "--blacklist", "H*", "--dnp-field", "kicad_dnp", "--extra-data-file", source,
             "--show-fields", "Value,Footprint", "--group-fields", "Value,Footprint"], env=env)
        html = out.read_text(encoding="utf-8")
        payload = re.search(r"^var pcbdata = (\{.*\})$", html, re.M)
        assert payload, bid
        data = json.loads(payload.group(1))
        assert data["ibom_version"] == "v2.12.0", data["ibom_version"]
        shown = sorted(ref for group in data["bom"]["both"] for ref, idx in group)
        assert shown == fitted, (bid, set(shown) ^ set(fitted))
        assert len(data["footprints"]) == len(footprints)
        assert "tracks" in data and "zones" in data and "nets" in data
        assert data["tracks"]["F"] and data["tracks"]["B"]
        assert len(data["nets"]) > 0
        bb = board.GetBoardEdgesBoundingBox()
        width, height = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
        layers = []
        for layer in LAYERS:
            svg = OUT / "assets/copper" / bid / (layer.replace(".", "_") + ".svg")
            normalise_svg(svg)
            root = ET.parse(svg).getroot()
            viewport = [float(v) for v in root.attrib["viewBox"].split()]
            assert abs(viewport[2] - width) < 2 and abs(viewport[3] - height) < 2, (bid, layer, viewport, width, height)
            layers.append({"id": layer, "title": layer, "svg": "assets/copper/" + bid + "/" + svg.name,
                           "sha256": sha(svg), "viewBox": viewport, "note": "Native vector copper and board outline; front-side coordinate view."})
        entries = [x["id"] for x in sheets if x["board"] == bid]
        boards.append({"id": bid, "title": title, "ibom": "pcb/" + bid + ".html", "ibom_sha256": sha(out),
                       "schematics": entries, "source": relative(source), "schematic_source": relative(schematic),
                       "project_source": relative(source.with_suffix(".kicad_pro")), "source_sha256": sha(source),
                       "width_mm": round(width, 3), "height_mm": round(height, 3),
                       "electrical_positions": len(electrical), "fitted": len(fitted), "dnp": dnp,
                       "mechanical_footprints": len(mechanical), "drawn_footprints": len(footprints),
                       "searchable_bom_components": len(shown), "nets": len(data["nets"]), "ibom_version": data["ibom_version"],
                       "copper": layers, "layers": layers,
                       "scope": "Components and net highlighting on F.Cu/B.Cu in the interactive layout; all four copper layers in native vector views."})
        print(f"{bid}: {len(fitted)} fitted, {len(dnp)} DNP, {len(mechanical)} mechanical; {len(entries)} sheets", flush=True)
    assert all_dnp == ["C20100", "C20200"]
    return boards


def make_package():
    """Exact native files, every local library and custom 3D model dependency."""
    allowed = {".kicad_pcb", ".kicad_sch", ".kicad_pro", ".kicad_sym", ".kicad_mod", ".kicad_dru", ".step", ".stp", ".wrl"}
    paths = []
    for folder in [NATIVE / "boards", NATIVE / "integration/master", NATIVE / "integration/shared", NATIVE / "package-models"]:
        for path in folder.rglob("*"):
            if path.is_file() and (path.suffix.lower() in allowed or path.name in {"fp-lib-table", "sym-lib-table"}):
                paths.append(path)
    paths = sorted(set(paths))
    target = OUT / "downloads/KiCad-SCCI_RH-native-projects.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    readme = """PROJECT SCCI RH / COMPLETE CURRENT KICAD SOURCE\n\nInstall KiCad 10 with its standard footprint and 3D-model libraries.\nExtract the entire archive, preserving its folders.\nOpen electronics/stage4/integrated-pcb/integration/master/SCCI_RH_integrated.kicad_pro for all 80 schematic sheets.\nOpen electronics/stage4/integrated-pcb/boards/<board>/<board>.kicad_pro for a PCB.\n\nThe native files are byte-identical copies of the reviewed source. All local symbol/footprint libraries and custom package models are included. Standard models reference the normal ${KICAD10_3DMODEL_DIR} installation; install the standard KiCad 10 3D-model package for those. Native KiCad files preserve pads/nets/layers; STEP exports preserve geometry only.\n\nThese are digital artificial-signal/load reference designs. Fabrication, analog performance, implantation and clinical use are not qualified by these files.\n\nProject: https://github.com/pratham-cloud-ctrl/Project-SCCI-RH\nEngineering baseline: v2.1.0\n"""
    source_manifest = {relative(p): sha(p) for p in paths}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            info = zipfile.ZipInfo(relative(path), date_time=(2026, 10, 21, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
        for name, value in {"OPEN_IN_KICAD.txt": readme, "SOURCE_SHA256.json": json.dumps(source_manifest, indent=2) + "\n"}.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 21, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, value)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for name, digest in source_manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    return {"path": "downloads/" + target.name, "sha256": sha(target), "bytes": target.stat().st_size,
            "native_files": len(paths), "standard_library_requirement": "KiCad 10 standard 3D-model libraries", "source_files": source_manifest}


def verify():
    manifest = json.loads((OUT / "assets/electronics-manifest.json").read_text(encoding="utf-8"))
    for rec in manifest["inputs"] + manifest["outputs"]:
        path = ROOT / rec["path"]
        assert path.is_file() and sha(path) == rec["sha256"], rec["path"]
    assert len(manifest["boards"]) == 8 and len(manifest["sheets"]) == 80
    assert manifest["counts"] == {"electrical_positions": 1298, "fitted_components": 1296, "dnp": 2, "mechanical_footprints": 32, "schematic_sheets": 80, "copper_views": 32}
    native_package = OUT / manifest["download"]["path"]
    with zipfile.ZipFile(native_package) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        listed = manifest["download"]["source_files"]
        assert names == set(listed) | {"OPEN_IN_KICAD.txt", "SOURCE_SHA256.json"}
        for name, digest in listed.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest, name
            assert sha(ROOT / name) == digest, name
            text = archive.read(name).decode("utf-8", errors="replace") if name.endswith((".kicad_sch", ".kicad_pcb", "-lib-table")) else ""
            dependencies = []
            if name.endswith(".kicad_sch"):
                dependencies.extend(re.findall(r'\(property "Sheetfile" "([^\"]+)"', text))
            if name.endswith("-lib-table"):
                dependencies.extend(re.findall(r'\(uri "([^\"]+)"', text))
            if name.endswith(".kicad_pcb"):
                dependencies.extend(re.findall(r'\(model "([^\"]+)"', text))
            for dependency in dependencies:
                if dependency.startswith("${KICAD10_3DMODEL_DIR}/"):
                    continue  # Explicit normal installed standard-library dependency.
                dependency = dependency.removeprefix("${KIPRJMOD}/")
                assert not re.match(r"^[A-Za-z]:|^/|^\$\{", dependency), (name, dependency)
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), dependency))
                assert resolved in names or any(p.startswith(resolved + "/") for p in names), (name, dependency, resolved)
    print("Browser electrical source/output hashes, eight boards, 80 sheets and four copper layers verified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", default=str(Path(sys.executable).parent / "kicad-cli.exe"))
    parser.add_argument("--reuse-native-exports", action="store_true", help="Use the already exported native MCP/CLI SVGs.")
    parser.add_argument("--package-only", action="store_true", help="Refresh the exact native package and its manifest entry, without rendering.")
    parser.add_argument("--verify", action="store_true", help="Read-only integrity verification; does not require pcbnew.")
    args = parser.parse_args()
    if args.verify:
        verify()
        return
    if args.package_only:
        path = OUT / "assets/electronics-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["download"] = make_package()
        target = OUT / manifest["download"]["path"]
        manifest["outputs"] = [r for r in manifest["outputs"] if r["path"] != relative(target)] + [record(target)]
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        verify()
        return
    if not args.reuse_native_exports:
        export_native(args.cli)
    sheets = sheet_index()
    boards = make_boards(sheets)
    package = make_package()
    inputs = sorted({ROOT / x["source"] for x in sheets} | {ROOT / b["source"] for b in boards})
    outputs = sorted(list((OUT / "assets/schematics").glob("*.svg")) + list((OUT / "assets/copper").rglob("*.svg")) + list((OUT / "pcb").glob("*.html")) + [OUT / package["path"]])
    manifest = {"schema": "scci_rh-browser-electronics-v1", "engineering_baseline": "v2.1.0", "generated_date": "2026-10-28",
                "renderer": {"kicad": run([args.cli, "version"]).strip(), "ibom_upstream": "https://github.com/openscopeproject/InteractiveHtmlBom", "ibom_commit": PIN, "ibom_license": "MIT"},
                "counts": {"electrical_positions": 1298, "fitted_components": 1296, "dnp": 2, "mechanical_footprints": 32, "schematic_sheets": 80, "copper_views": 32},
                "boards": boards, "sheets": sheets, "download": package,
                "inputs": [record(x) for x in inputs], "outputs": [record(x) for x in outputs],
                "limits": ["InteractiveHtmlBom exposes front/back tracks, zones, pads, components and net highlighting; it does not show inner copper.",
                           "All four copper layers have separate native KiCad vector exports.",
                           "Schematic search indexes actual invisible text records exported by KiCad; no connectivity is inferred from image pixels.",
                           "The exact native package includes local libraries/custom models; stock 3D models require KiCad 10's standard model library.",
                           "Exports improve inspection and do not establish electrical, manufacturing or biological performance."]}
    path = OUT / "assets/electronics-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    verify()


if __name__ == "__main__":
    main()
