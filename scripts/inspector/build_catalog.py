"""Assemble the public inspector catalog, complete downloads and static fallback.

Run after native CAD/electronics exporters. Existing engineering sources are
read-only. --pilot allows a partial CAD catalog for local UI development.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'inspector'
DATE = (2026, 10, 28, 0, 0, 0)
REPO = 'https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/blob/main/'
TEXT_SOURCE_SUFFIXES = {'.py', '.fcmacro', '.cmd', '.ps1', '.csv', '.json', '.md',
                        '.txt', '.xml', '.html', '.css', '.js', '.mjs', '.svg',
                        '.yml', '.yaml', '.kicad_sch', '.kicad_pcb', '.kicad_pro',
                        '.kicad_sym', '.kicad_mod'}


def source_bytes(path):
    """Use Git's LF text representation; native geometry stays byte-exact."""
    path = Path(path)
    data = path.read_bytes()
    return data.replace(b'\r\n', b'\n') if path.suffix.lower() in TEXT_SOURCE_SUFFIXES else data


def sha(path):
    return hashlib.sha256(source_bytes(path)).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def tracked():
    return subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().strip('\0').split('\0')


def canonical(name):
    return source_bytes(ROOT/name)


def package_native():
    names = [name for name in tracked() if name.startswith('cad/') and
             (Path(name).suffix.lower() in {'.fcstd', '.fcmacro', '.py', '.cmd', '.ps1', '.csv', '.json', '.md'} or
              name == 'cad/stage5/drawings/SCCI_RH_Stage5_Mechanical_Review.pdf')]
    # Stage2 is an intentionally preserved historical allocation, not the current CAD.
    names = [name for name in names if not name.startswith('cad/stage2/')]
    readme = '''PROJECT SCCI RH / COMPLETE CURRENT FREECAD PACKAGE

Extract this ZIP, preserving its Project-SCCI-RH/cad/ folder structure.
Requires FreeCAD 1.1 or later. On Windows, run cad/OPEN_CURRENT_CAD.cmd.
For a different installation set SCCI_RH_FREECAD_EXE to FreeCAD.exe.

Current full reference: cad/stage5/SCCI_RH_stage5_reference_full.FCStd
Future concept: cad/stage5/future-interface/SCCI_RH_future_interface.FCStd
Before opening the future FCStd in FreeCAD's Python console:
  import sys
  sys.path.insert(0, r"<your extraction>/Project-SCCI-RH/cad/stage5/future-interface")
  import scci_rh_future_features
Then open the FCStd. The Windows launcher does this automatically.

The package contains editable native assemblies, feature definitions, opening
macros, current source scripts and mechanical review drawings. It does not
include the entire research repo or every prerequisite for rebuilding the
electronics-derived assemblies. Use the full repository for regeneration.
The saved FCStd geometry is embedded and does not require external STEP files
for inspection. Keep the supplied module alongside the future native model.

For view-only inspection, close without saving display changes. For intentional
edits use Save As to a separately named working copy.

Reference: 600 x 310 x 240 mm incl feet, 260 physical objects.
Separate future can/header: 60 x 58 x 14 mm before leads; 230 physical parts
plus 6 nonphysical allocation volumes. The reference boards do not fit it.
Digital engineering, no manufactured/implanted performance claimed.
All native members match the current rebranded repository bytes; original identities are recorded by the migration. Browser meshes are separate.
'''
    destination = OUT / 'downloads/SCCI_RH_CAD_Native.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    members = {}
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        info = zipfile.ZipInfo('README.txt', DATE); info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, readme)
        for name in sorted(names):
            data = canonical(name)
            info = zipfile.ZipInfo('Project-SCCI-RH/' + name, DATE); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
            members['Project-SCCI-RH/' + name] = {'source': name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return destination, members


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    cad = json.loads((OUT / 'assets/cad-manifest.json').read_text(encoding='utf-8-sig'))
    electrical = json.loads((OUT / 'assets/electronics-manifest.json').read_text(encoding='utf-8-sig'))
    if not args.pilot:
        assert len(cad['models']) == 10 and len(electrical['boards']) == 8
    native, members = package_native()
    downloads = []

    def add(path, title, fmt, description, designs=None, source=None, **extras):
        path = Path(path)
        assert path.is_file()
        downloads.append({'file': path.relative_to(OUT).as_posix(), 'title': title,
                          'format': fmt, 'description': description, 'designs': designs or [],
                          'bytes': path.stat().st_size, 'sha256': sha(path),
                          **({'source': source} if source else {}), **extras})

    def copy(source, name):
        target = OUT / 'downloads' / name
        shutil.copyfile(ROOT / source, target)
        return target

    add(native, 'Editable FreeCAD assemblies', 'NATIVE ZIP',
        'Complete current native CAD, feature module, opening launchers and drawings. Extract first; FreeCAD 1.1+. See the included instructions for the future feature module.', members=members)
    reference = OUT / 'downloads/SCCI_RH_Reference_Complete_STEP.zip'
    if reference.exists():
        add(reference, 'Complete reference assembly', 'STEP ZIP',
            'All 260 physical objects, including populated boards, mating interfaces and harness parts. Extract the STEP to inspect solid geometry in compatible CAD software.', ['reference'])
    future_source = 'cad/stage5/future-interface/SCCI_RH_future_interface.step'
    add(copy(future_source, 'SCCI_RH_Future_Interface.step'), 'Future interface solid geometry', 'STEP',
        'The fitted 230-part future interface in millimetres. Standard CAD interchange; parametric editing remains in the native package. Internal allocation boxes are not physical parts.', ['future'], future_source)
    mechanical_pdf = 'cad/stage5/drawings/SCCI_RH_Stage5_Mechanical_Review.pdf'
    add(copy(mechanical_pdf, 'SCCI_RH_Mechanical_Review.pdf'), 'Mechanical review drawings', 'PDF',
        'Six dimensioned assembly and interface review sheets, including the distinction between the full reference and future package.', ['future', 'reference'], mechanical_pdf)
    package = electrical['download']
    add(OUT / package['path'], 'All eight editable KiCad projects', 'KICAD ZIP',
        'Complete current schematics, PCBs, hierarchy, local libraries and custom package models. Requires KiCad 10 and its standard 3D-model libraries. Extract and preserve folders.', source_files=package['source_files'])
    schematic_source = 'electronics/stage4/integrated-pcb/integration/master/SCCI_RH_integrated.pdf'
    add(copy(schematic_source, 'SCCI_RH_Integrated_Schematics.pdf'), 'Complete integrated schematics', 'PDF',
        'All 80 current circuit sheets, with integrated global references. A dependable reader independent of the interactive viewers.', source=schematic_source)
    for item in electrical['boards']:
        source = f'electronics/stage4/integrated-pcb/exports/{item["id"]}/populated.step'
        add(copy(source, f'SCCI_RH_{item["id"]}.step'), item['title'] + ' populated solids', 'STEP',
            'Actual populated board exchange geometry, in millimetres. Open in CAD software without KiCad; the KiCad ZIP contains the editable circuit and layout.', [item['id']], source)
    write_json(OUT / 'assets/downloads-manifest.json', {'schema': 'scci_rh.inspector-downloads.v1', 'downloads': downloads})
    (OUT / 'downloads/SHA256SUMS.txt').write_text(''.join(f'{item["sha256"]}  {Path(item["file"]).name}\n' for item in downloads), encoding='utf-8', newline='\n')
    boards = [{**item, 'layers': [{'name': layer['id'], 'file': layer['svg']} for layer in item['copper']]} for item in electrical['boards']]
    board_map = {item['id']: item for item in boards}
    designs = []
    for item in cad['models']:
        description = {
            'future': ('60 × 58 × 14 mm can/header · 60 × 204 × 14 mm incl. leads', 'Proposed compact implant; allocation volumes are optional and nonphysical. Reference electronics do not fit this can.'),
            'reference': ('Chassis 600 × 310 × 240 mm · full envelope 600 × 311 × 240 mm', 'Complete 260-object full-scale reference, including the rear grommet projection. Board compounds contain fitted component geometry.'),
        }.get(item['id'])
        b = board_map.get(item['id'])
        dimensions, note = description if description else (
            f'{round(b["width_mm"])} × {round(b["height_mm"])} mm · {b["fitted"]} fitted components',
            'Actual STEP solids; categorical display colours. PCB substrate is a separate object; unfitted parts are omitted.')
        preview = (f'https://raw.githubusercontent.com/pratham-cloud-ctrl/Project-SCCI-RH/main/cad/stage5/renders/{item["id"]}_assembled.png' if not b else
                   f'https://raw.githubusercontent.com/pratham-cloud-ctrl/Project-SCCI-RH/main/electronics/stage4/integrated-pcb/exports/{item["id"]}/isometric.png')
        designs.append({**item, 'model': item['file'], 'modelBytes': item['bytes'], 'dimensions': dimensions, 'note': note, 'preview': preview})
    sheets = [{**{key: value for key, value in item.items() if key not in ('texts', 'text')}, 'file': item['svg'],
               'search': item['text'], 'boardTitle': board_map.get(item['board'], {}).get('title', 'Complete system')} for item in electrical['sheets']]
    catalog = {'schema': 'scci_rh.inspector-catalog.v1', 'date': '2026-10-28', 'designs': designs, 'boards': boards, 'sheets': sheets, 'downloads': downloads}
    # Download member/source records belong in provenance, not the initial UI payload.
    catalog['downloads'] = [{key: value for key, value in item.items() if key not in ('members', 'source_files')} for item in downloads]
    write_json(OUT / 'assets/catalog.json', catalog)
    release = json.loads((ROOT / 'docs/stage6/release-contract.json').read_text(encoding='utf-8'))
    manifest = {'schema': 'scci_rh.inspection-provenance.v1', 'engineering_release': release['tag'], 'viewer_date': release['date'],
                'sources': [{'file': 'assets/cad-manifest.json', 'sha256': sha(OUT / 'assets/cad-manifest.json')},
                            {'file': 'assets/electronics-manifest.json', 'sha256': sha(OUT / 'assets/electronics-manifest.json')},
                            {'file': 'assets/downloads-manifest.json', 'sha256': sha(OUT / 'assets/downloads-manifest.json')}],
                'catalog_sha256': sha(OUT / 'assets/catalog.json'), 'engineering_sources_changed': True, 'change_scope': 'Project name and metadata only; engineering geometry and behavior checked against the prior release',
                'reading': 'All meshes and drawings are visualization derivatives. Open linked manifests for native engine versions, input/output SHA-256, units, part identities and finite export checks.'}
    write_json(OUT / 'assets/inspection-manifest.json', manifest)
    static_index(catalog)
    print(json.dumps({'designs': len(designs), 'boards': len(boards), 'sheets': len(sheets), 'downloads': len(downloads), 'pilot': args.pilot}))


def static_index(catalog):
    e = html.escape
    def link(path, label): return f'<a href="{e(path, quote=True)}">{e(label)}</a>'
    output = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project SCCI RH · Static inspection index</title><link rel="stylesheet" href="app.css"><body><main class="static-content"><p>' + link('./', '← Interactive inspector') + '</p><h1>Inspect without an interactive viewer.</h1><p>Direct vector sheets, original previews, complete downloads and engineering source. No JavaScript or WebGL required.</p>']
    output.append('<section><h2>Mechanical assemblies</h2><div class="gallery">')
    for key, title in [('future', 'Future implanted-interface concept'), ('reference', 'Full reference assembly')]:
        source = f'https://raw.githubusercontent.com/pratham-cloud-ctrl/Project-SCCI-RH/main/cad/stage5/renders/{key}_assembled.png'
        output.append(f'<article><h3>{e(title)}</h3><a href="{source}"><img src="assets/previews/{key}.jpg" alt="{e(title)} from saved native geometry"></a></article>')
    output.append('</div></section><section><h2>Editable and standard downloads</h2><ul>')
    for item in catalog['downloads']:
        output.append('<li>' + link(item['file'], item['title'] + ' · ' + item['format']) + f' ({item["bytes"] / 1e6:.1f} MB) — {e(item["description"])}</li>')
    output.append('</ul><p>' + link('downloads/SHA256SUMS.txt', 'Full SHA-256 checksums') + '</p></section><section><h2>Eight circuit boards · all copper layers</h2>')
    for item in catalog['boards']:
        output.append(f'<details><summary>{e(item["title"])} · {item["fitted"]} fitted</summary><p>' + link(item['ibom'], 'Interactive component / outer-copper viewer') + ' · ' + link(REPO + item['source'], 'Native PCB source') + '</p><ul>')
        for layer in item['layers']: output.append('<li>' + link(layer['file'], layer['name'] + ' · native vector drawing') + '</li>')
        output.append('</ul></details>')
    output.append('</section><section><h2>All 80 current schematic sheets</h2><table><thead><tr><th>Page</th><th>Circuit</th><th>Board</th><th>Editable source</th></tr></thead><tbody>')
    for item in catalog['sheets']:
        output.append(f'<tr><td>{item["page"]}</td><td>{link(item["file"], item["title"])}</td><td>{e(item["boardTitle"])}</td><td>{link(REPO + item["source"], "KiCad source")}</td></tr>')
    output.append('</tbody></table></section><p>' + link('credits.html', 'Tools, licenses and design review') + '</p></main></body></html>')
    (OUT / 'fallback.html').write_text('\n'.join(output) + '\n', encoding='utf-8', newline='\n')
    previews = OUT / 'assets/previews'; previews.mkdir(parents=True, exist_ok=True)
    for key in ('future', 'reference'):
        shutil.copyfile(ROOT / f'docs/explore/assets/cad-{key}-assembled.jpg', previews / f'{key}.jpg')


if __name__ == '__main__':
    main()
