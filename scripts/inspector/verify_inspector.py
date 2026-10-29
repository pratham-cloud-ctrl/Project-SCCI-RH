"""Independently inspect browser geometry, circuits, downloads and source preservation.

Read-only unless --write-report is supplied. Does not launch CAD, alter native
files, execute vendor generators or claim physical/biological performance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from project_branding import assert_baseline_equivalence
SITE = ROOT / 'inspector'
REPORT = ROOT / 'provenance/browser-inspector-verification.json'
BASELINE = '9f6cf0a4403a00549a858ae9f0cecdd9dce0c5bb'
MUTABLE = {'README.md', 'START_HERE.md', 'CURRENT_STATUS.md',
           'provenance/manifest.sha256', 'provenance/stage6-release-verification.json',
           'scripts/verify_stage6_release.py', '.github/workflows/verify-release.yml'}
EXPECTED = {'recording-front-end': 153, 'controller-carrier': 68,
            'current-driver': 154, 'contact-router': 155, 'monitoring-cell': 71,
            'supervision': 479, 'monitoring-transport': 60, 'power': 156}
TEXT_SUFFIXES = {'.py', '.json', '.md', '.txt', '.html', '.css', '.js', '.mjs', '.svg',
                 '.kicad_pcb', '.kicad_sch', '.kicad_pro', '.kicad_mod', '.kicad_sym',
                 '.xml', '.csv', '.cmd', '.ps1', '.fcmacro', '.yml'}
NS = {'s': 'http://www.w3.org/2000/svg'}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_file(path, expected=None):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT) and path.is_file(), 'Missing/unsafe file: ' + str(path))
    data = path.read_bytes()
    if expected:
        candidates = {sha(data)}
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {'fp-lib-table', 'sym-lib-table'}:
            candidates.add(sha(data.replace(b'\r\n', b'\n')))
        require(expected in candidates, 'Changed source/output: ' + str(path.relative_to(ROOT)))
    return data


def expr(path):
    # Independently read the actual saved KiCad syntax, not producer objects.
    tokens = re.finditer(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()]+', Path(path).read_text(encoding='utf-8-sig'))
    stack, root = [], None
    for match in tokens:
        token = match[0]
        if token == '(':
            value = []
            if stack:
                stack[-1].append(value)
            else:
                require(root is None, 'Multiple source roots')
                root = value
            stack.append(value)
        elif token == ')':
            require(bool(stack), 'Unbalanced KiCad source')
            stack.pop()
        else:
            require(bool(stack), 'Token outside source root')
            if token.startswith('"'):
                token = re.sub(r'\\(.)', r'\1', token[1:-1])
            stack[-1].append(token)
    require(root is not None and not stack, 'Unbalanced KiCad source')
    return root


def children(tree, name):
    return [v for v in tree if isinstance(v, list) and v and v[0] == name]


def child(tree, name, default=None):
    values = children(tree, name)
    return values[0] if values else default


def props(tree):
    return {v[1]: v[2] for v in children(tree, 'property')}


def saved_board(path):
    tree = expr(path)
    fps = {}
    for footprint in children(tree, 'footprint'):
        values = props(footprint)
        ref = values['Reference']
        require(ref not in fps, 'Duplicate native reference: ' + ref)
        attr = child(footprint, 'attr', [])
        fps[ref] = {'value': values.get('Value', ''), 'dnp': 'dnp' in attr,
                    'mechanical': 'exclude_from_bom' in attr,
                    'at': [float(v) for v in child(footprint, 'at')[1:3]]}
    layers = child(tree, 'layers', [])
    require({v[1] for v in layers[1:] if isinstance(v, list) and len(v) > 2 and v[2] == 'signal'} ==
            {'F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'}, 'Expected native four-layer board')
    edges = [item for item in children(tree, 'gr_line') if child(item, 'layer', [None, ''])[1] == 'Edge.Cuts']
    points = [[float(x) for x in child(item, name)[1:3]] for item in edges for name in ('start', 'end')]
    require(len(points) >= 8, 'Native rectangular board outline missing')
    bounds = [min(v[i] for v in points) for i in range(2)] + [max(v[i] for v in points) for i in range(2)]
    return fps, bounds


IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]


def product(a, b):
    return [sum(a[row*4+k] * b[k*4+col] for k in range(4)) for row in range(4) for col in range(4)]


def transform(node):
    if 'matrix' in node:
        values = node['matrix']
        require(len(values) == 16, 'Invalid node matrix')
        return [values[col*4+row] for row in range(4) for col in range(4)]
    x, y, z, w = node.get('rotation', [0, 0, 0, 1])
    require(abs(x*x+y*y+z*z+w*w-1) < 1e-5, 'Invalid node quaternion')
    scale = node.get('scale', [1, 1, 1])
    offset = node.get('translation', [0, 0, 0])
    matrix = [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), offset[0],
              2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), offset[1],
              2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y), offset[2],
              0, 0, 0, 1]
    for row in range(3):
        for col in range(3):
            matrix[row*4+col] *= scale[col]
    require(all(math.isfinite(v) for v in matrix), 'Nonfinite node transform')
    return matrix


def accessor(doc, binary, index):
    spec = doc['accessors'][index]
    require('sparse' not in spec, 'Unexpected sparse accessor needs independent review')
    formats = {5120: ('b', 1, 127), 5121: ('B', 1, 255), 5122: ('h', 2, 32767),
               5123: ('H', 2, 65535), 5125: ('I', 4, 4294967295), 5126: ('f', 4, None)}
    fmt, size, maximum = formats[spec['componentType']]
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[spec['type']]
    view = doc['bufferViews'][spec['bufferView']]
    require(view.get('buffer', 0) == 0, 'External GLB buffer')
    stride = view.get('byteStride', size*width)
    start = view.get('byteOffset', 0) + spec.get('byteOffset', 0)
    end = start + stride*(spec['count']-1) + size*width
    require(spec['count'] > 0 and end <= len(binary) and stride >= size*width,
            'Invalid GLB accessor range')
    require(end <= view.get('byteOffset', 0)+view['byteLength'], 'Accessor exceeds buffer view')
    rows = [struct.unpack_from('<'+fmt*width, binary, start+i*stride) for i in range(spec['count'])]
    require(all(math.isfinite(v) for row in rows for v in row), 'Nonfinite geometry')
    if 'min' in spec:
        require(all(abs(min(row[i] for row in rows)-spec['min'][i]) < 1e-6 for i in range(width)),
                'Declared GLB accessor minimum differs from actual data')
    if 'max' in spec:
        require(all(abs(max(row[i] for row in rows)-spec['max'][i]) < 1e-6 for i in range(width)),
                'Declared GLB accessor maximum differs from actual data')
    if spec.get('normalized'):
        require(maximum is not None, 'Normalized float accessor')
        rows = [tuple(max(-1, v/maximum) for v in row) for row in rows]
    return rows


def read_glb(path, expected_parts):
    data = checked_file(path)
    require(len(data) >= 28, 'Short GLB')
    magic, version, length = struct.unpack_from('<4sII', data)
    require((magic, version, length) == (b'glTF', 2, len(data)), 'Invalid GLB header')
    chunks, cursor = {}, 12
    while cursor < len(data):
        size, kind = struct.unpack_from('<I4s', data, cursor)
        require(size % 4 == 0 and cursor+8+size <= len(data) and kind not in chunks, 'Invalid GLB chunk')
        chunks[kind] = data[cursor+8:cursor+8+size]
        cursor += 8+size
    require(cursor == len(data) and set(chunks) == {b'JSON', b'BIN\0'}, 'Invalid GLB chunks')
    doc, binary = json.loads(chunks[b'JSON']), chunks[b'BIN\0']
    require(doc['asset']['version'] == '2.0' and len(doc['buffers']) == 1 and
            len(binary)-3 <= doc['buffers'][0]['byteLength'] <= len(binary), 'Invalid GLB payload length')
    require('uri' not in doc['buffers'][0], 'GLB is not self-contained')
    expected = {v['id']: v for v in expected_parts}
    require(len(expected) == len(expected_parts), 'Duplicate manifest part IDs')
    ids, visited, bounds = set(), set(), {}
    triangles = vertices = 0

    def walk(index, parent, part_id=None):
        nonlocal triangles, vertices
        require(index not in visited and 0 <= index < len(doc['nodes']), 'Invalid/cyclic/shared GLB node')
        visited.add(index)
        node = doc['nodes'][index]
        matrix = product(parent, transform(node))
        extra = node.get('extras', {})
        if 'id' in extra:
            part_id = extra['id']
            require(part_id in expected and part_id not in ids, 'Unexpected/duplicate GLB part identity')
            require(extra == expected[part_id], 'GLB part metadata differs from manifest: ' + part_id)
            ids.add(part_id)
            bounds[part_id] = [float('inf')]*3 + [-float('inf')]*3
        if 'mesh' in node:
            require(part_id is not None, 'Unidentified GLB mesh')
            for primitive in doc['meshes'][node['mesh']]['primitives']:
                require(primitive.get('mode', 4) == 4, 'Unexpected primitive mode')
                positions = accessor(doc, binary, primitive['attributes']['POSITION'])
                normals = accessor(doc, binary, primitive['attributes']['NORMAL'])
                indices = accessor(doc, binary, primitive['indices'])
                require(len(normals) == len(positions) and len(indices) % 3 == 0, 'Invalid mesh topology arrays')
                require(all(0 <= row[0] < len(positions) for row in indices), 'Index outside mesh positions')
                require(all(.85 < sum(v*v for v in normal) < 1.15 for normal in normals), 'Invalid normals')
                vertices += len(positions)
                triangles += len(indices)//3
                for v in positions:
                    point = [sum(matrix[row*4+k]*v[k] for k in range(3))+matrix[row*4+3] for row in range(3)]
                    for axis in range(3):
                        bounds[part_id][axis] = min(bounds[part_id][axis], point[axis])
                        bounds[part_id][axis+3] = max(bounds[part_id][axis+3], point[axis])
        for child_index in node.get('children', []):
            walk(child_index, matrix, part_id)

    for index in doc['scenes'][doc.get('scene', 0)]['nodes']:
        walk(index, IDENTITY)
    require(ids == set(expected) and len(visited) == len(doc['nodes']), 'Missing/unreachable GLB source parts')
    max_error = 0
    for ident, value in bounds.items():
        b = expected[ident]['bounds_mm']
        wanted = [b[0]/1000, b[2]/1000, -b[4]/1000, b[3]/1000, b[5]/1000, -b[1]/1000]
        error = max(abs(x-y)*1000 for x, y in zip(value, wanted))
        max_error = max(max_error, error)
        require(error <= .50, f'{path.name}/{ident}: decoded geometry deviates {error:.4f} mm from native bounds')
    return {'part_nodes': len(ids), 'mesh_nodes': len(doc['meshes']), 'vertices': vertices,
            'triangles': triangles, 'max_decoded_native_bounds_error_mm': round(max_error, 7)}


def inspect_geometry(cad, board_sources):
    models = {m['id']: m for m in cad['models']}
    require(set(models) == {'future', 'reference', *EXPECTED}, 'Missing current GLB models')
    future = read(ROOT/'cad/stage5/future-interface/contract.json')
    reference = read(ROOT/'cad/stage5/combined-assembly-receipt.json')
    reviewed_future = read(ROOT/'provenance/stage5-native-future.json')['packages']['future']
    reviewed_reference = read(ROOT/'provenance/stage5-combined-native.json')
    require(sha(checked_file(ROOT/cad['exporter']).replace(b'\r\n', b'\n')) == cad['exporter_sha256_lf'],
            'CAD exporter differs from recorded source')
    details = {}
    for ident, model in models.items():
        prior_bounds_residual = None
        path = SITE/model['file']
        data = checked_file(path, model['sha256'])
        require(len(data) == model['bytes'] and len(data) < 100*1024*1024, 'Model size binding')
        for source, digest in model['inputs'].items():
            checked_file(ROOT/source, digest)
        parts = model['parts']
        ids = {p['id'] for p in parts}
        if ident == 'future':
            require(ids == {p['name'] for p in future['parts']}, 'Future source identities differ')
            allocations = {p['name'] for p in future['parts'] if p['category'] == 'allocation'}
            require({p['id'] for p in parts if p.get('allocation')} == allocations and len(allocations) == 6,
                    'Future allocation coverage differs')
            require(sum(bool(p['physical']) for p in parts) == 230 and
                    all(p['default_hidden'] for p in parts if p['allocation']), 'Future physical/allocation distinction')
            reviewed = {p['label']: p['bounds_mm'] for p in reviewed_future['parts']}
            checked_file(ROOT/model['source'], reviewed_future['native_sha256'])
            prior_bounds_residual = 0
            for part in parts:
                require(part['label'] in reviewed, 'Future part lacks preserved independent inspection')
                residual = max(abs(a-b) for a, b in zip(part['bounds_mm'], reviewed[part['label']]))
                prior_bounds_residual = max(prior_bounds_residual, residual)
                # OCC cached triangulation can expand a curved-shape bounding
                # box slightly. Source FCStd identity is checked byte-for-byte.
                require(residual <= .05, 'Future bounds differ from preserved native inspection: '+part['id'])
        elif ident == 'reference':
            require(ids == {p['native_name'] for p in reference['parts']} and len(ids) == 260,
                    'Complete reference source identities differ')
            require(all(p['physical'] and not p['allocation'] for p in parts), 'Reference nonphysical part included')
            reviewed = {p['label']: p['source_geometry']['bounds'] for p in reviewed_reference['parts']}
            checked_file(ROOT/model['source'], reviewed_reference['native_sha256'])
            prior_bounds_residual = 0
            for part in parts:
                require(part['label'] in reviewed, 'Reference part lacks preserved independent inspection')
                residual = max(abs(a-b) for a, b in zip(part['bounds_mm'], reviewed[part['label']]))
                prior_bounds_residual = max(prior_bounds_residual, residual)
                require(residual <= .05, 'Reference bounds differ from preserved native inspection: '+part['id'])
        else:
            fps, _ = board_sources[ident]
            fitted = {ref for ref, value in fps.items() if not value['dnp'] and not value['mechanical']}
            require(ids == fitted | {'PCB'} and len(fitted) == EXPECTED[ident], 'PCB physical population differs: '+ident)
            require(not ({p['id'] for p in parts} & {ref for ref, v in fps.items() if v['dnp']}), 'DNP shown fitted')
            require(model['fitted_components'] == len(fitted), 'PCB fitted count binding')
            require(all(p['physical'] and not p['allocation'] for p in parts), 'PCB nonphysical part included')
            reviewed = read(ROOT/f'electronics/stage4/integrated-pcb/exports/{ident}/geometry-verification.json')
            checked_file(ROOT/model['source'], reviewed['STEP_sha256'])
            native_dimensions = [model['bounds_mm'][i+3]-model['bounds_mm'][i] for i in range(3)]
            require(max(abs(a-b) for a, b in zip(native_dimensions, reviewed['dimensions_mm'])) < .001,
                    'Board dimensions differ from preserved independent STEP inspection: '+ident)
        require(model['physical_parts'] == sum(bool(p['physical']) for p in parts), 'Physical count binding')
        details[ident] = read_glb(path, parts)
        if prior_bounds_residual is not None:
            details[ident]['max_prior_native_bounds_residual_mm'] = round(prior_bounds_residual, 7)
        require(details[ident]['vertices'] == model['vertices'] and details[ident]['triangles'] == model['triangles'],
                'Actual mesh counts differ from producer: '+ident)
    require(cad['units'] == 'metres' and cad['native_units'] == 'millimetres', 'Coordinate units not explicit')
    return details


def inspect_schematics(sheets):
    by_source = {s['source']: s for s in sheets}
    require(len(sheets) == len(by_source) == 80 and {s['page'] for s in sheets} == set(range(1, 81)),
            'Incomplete/duplicate schematic pages')
    seen, visible_refs = set(), set()

    def walk(path, parent, names):
        source = path.relative_to(ROOT).as_posix()
        require(source in by_source and source not in seen, 'Native hierarchy coverage differs')
        seen.add(source)
        row = by_source[source]
        node = expr(path)
        require(row['parent'] == parent and row['path'] == '/'+ '/'.join(names), 'Schematic parent/path differs')
        checked_file(path, row['source_sha256'])
        svg_data = checked_file(SITE/row['svg'], row['svg_sha256'])
        svg = ET.fromstring(svg_data)
        require('Eeschema' in ''.join(svg.itertext()), 'Schematic was not native-rendered')
        actual_text = [''.join(item.itertext()).strip() for item in svg.findall('.//s:text', NS)]
        require(row['text'] == '\n'.join(dict.fromkeys(t for t in actual_text if t)), 'Schematic search text differs')
        title = child(child(node, 'title_block', []), 'title')
        if title:
            require(title[1] == row['title'], 'Wrong current sheet title')
        refs = {props(symbol).get('Reference') for symbol in children(node, 'symbol')}
        refs = {ref for ref in refs if ref and not ref.startswith('#')}
        current = set(row['text'].splitlines())
        require(refs <= current, 'Missing searchable native references: '+source+' '+str(refs-current))
        visible_refs.update(refs)
        links = []
        for sheet in children(node, 'sheet'):
            values = props(sheet)
            destination = path.parent/values['Sheetfile']
            relative = destination.relative_to(ROOT).as_posix()
            require(relative in by_source, 'Missing native child sheet')
            child_row = by_source[relative]
            links.append(child_row['id'])
            walk(destination, row['id'], names+[values['Sheetname']])
        require(set(links) == set(row['children']), 'Wrong indexed children')

    walk(ROOT/'electronics/stage4/integrated-pcb/integration/master/SCCI_RH_integrated.kicad_sch', None, [])
    require(seen == set(by_source), 'Unreachable circuit sheets')
    return {'native_hierarchy_pages': len(seen), 'source_references_in_vector_search': len(visible_refs)}


def inspect_electronics(manifest):
    records = {board['id']: board for board in manifest['boards']}
    require(set(records) == set(EXPECTED), 'Missing circuit board viewers')
    for row in manifest['inputs']+manifest['outputs']:
        data = checked_file(ROOT/row['path'], row['sha256'])
        require(len(data) == row['bytes'], 'Source/output size binding')
    sources, dnp, pads, copper = {}, set(), 0, 0
    for ident, row in records.items():
        source = ROOT/row['source']
        checked_file(source, row['source_sha256'])
        fps, bounds = saved_board(source)
        sources[ident] = fps, bounds
        fitted = {ref for ref, p in fps.items() if not p['dnp'] and not p['mechanical']}
        unpopulated = {ref for ref, p in fps.items() if p['dnp']}
        mechanical = {ref for ref, p in fps.items() if p['mechanical']}
        require(len(fitted) == EXPECTED[ident] and len(mechanical) == 4 and unpopulated == set(row['dnp']),
                'Actual PCB population/holes differ: '+ident)
        dnp.update(unpopulated)
        data = checked_file(SITE/row['ibom'], row['ibom_sha256']).decode('utf-8')
        payload = re.search(r'^var pcbdata = (\{[^\r\n]*\})\r?$', data, re.M)
        require(payload is not None, 'Missing inspectable iBOM data')
        pcb = json.loads(payload[1])
        drawn = {p['ref'] for p in pcb['footprints']}
        require(drawn == set(fps), 'iBOM lost native footprint geometry')
        shown = [ref for group in pcb['bom']['both'] for ref, _ in group]
        require(set(shown) == fitted and len(shown) == len(fitted), 'iBOM fitted BOM differs')
        require(set(pcb['tracks']) == {'F', 'B'} and pcb['tracks']['F'] and pcb['tracks']['B'] and pcb['nets'],
                'Outer copper/net inspection absent')
        require(all('net' in p for fp in pcb['footprints'] for p in fp['pads']), 'Pads lack interactive net IDs')
        pads += sum(len(fp['pads']) for fp in pcb['footprints'])
        require({layer['id'] for layer in row['copper']} == {'F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'},
                'Inner-layer fallback missing')
        for layer in row['copper']:
            svg = ET.fromstring(checked_file(SITE/layer['svg'], layer['sha256']))
            view = [float(v) for v in svg.attrib['viewBox'].split()]
            width, height = bounds[2]-bounds[0], bounds[3]-bounds[1]
            require(abs(view[2]-width) < .5 and abs(view[3]-height) < .5,
                    'Copper export is paper-clipped, not board-area: '+ident+'/'+layer['id'])
            require(svg.findall('.//s:path', NS), 'Empty copper vector')
            require('PCBNEW' in ''.join(svg.itertext()), 'Copper export lacks native renderer identity')
            copper += 1
    require(dnp == {'C20100', 'C20200'}, 'Original optional driver positions differ')
    require(copper == 32, 'Incomplete copper coverage')
    details = inspect_schematics(manifest['sheets'])
    details.update(boards=8, fitted_components=sum(EXPECTED.values()), dnp_references=sorted(dnp),
                   electrical_positions=sum(EXPECTED.values())+len(dnp), mechanical_holes=32,
                   interactive_native_pads=pads, four_layer_vector_views=copper)
    return sources, details


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if attrs.get('id'):
            require(attrs['id'] not in self.ids, 'Duplicate HTML ID')
            self.ids.add(attrs['id'])
        for name in ('href', 'src'):
            if attrs.get(name):
                self.links.append(attrs[name])


def local_link(path, url):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or url.startswith('data:'):
        return None
    require(not parsed.path.startswith('/'), 'Root-relative URL breaks GitHub project Pages: '+url)
    target = (path.parent/unquote(parsed.path)).resolve() if parsed.path else path
    require(target.is_relative_to(SITE) and (target.is_file() or target.is_dir()), 'Broken/unsafe inspector URL: '+url)
    return target


def inspect_catalog(cad, electrical):
    catalog = read(SITE/'assets/catalog.json')
    designs = {d['id']: d for d in catalog['designs']}
    require(set(designs) == {'future', 'reference', *EXPECTED}, 'Catalog misses actual designs')
    require(len(catalog['sheets']) == 80 and len(catalog['boards']) == 8, 'Catalog schematic/PCB count')
    for design in designs.values():
        require((SITE/design['model']).is_file() and design['parts'], 'Design lacks browser geometry')
        checked_file(ROOT/design['source'])
        source = next(model for model in cad['models'] if model['id'] == design['id'])
        require(design['parts'] == source['parts'] and design['model'] == source['file'] and
                design['modelBytes'] == source['bytes'], 'Catalog changed native-derived model identity')
    for row in catalog['boards']:
        original = next(board for board in electrical['boards'] if board['id'] == row['id'])
        require(row['ibom'] == original['ibom'] and row['schematics'] == original['schematics'],
                'Catalog circuit-view mapping differs')
        for layer in row['layers']:
            local_link(SITE/'index.html', layer['file'])
    for row in catalog['sheets']:
        original = next(sheet for sheet in electrical['sheets'] if sheet['id'] == row['id'])
        require(row['file'] == original['svg'] and row['search'] == original['text'] and
                row['parent'] == original['parent'], 'Catalog lost circuit search/hierarchy')
    checked = 0
    for path in SITE.glob('*.html'):
        parser = HTMLLinks()
        parser.feed(path.read_text(encoding='utf-8'))
        for url in parser.links:
            target = local_link(path, url)
            if target:
                checked += 1
    html = (SITE/'index.html').read_text(encoding='utf-8')
    require('<noscript>' in html and 'fallback.html' in html and 'aria-label=' in html,
            'Basic inspection accessibility fallback missing')
    app = (SITE/'app.js').read_text(encoding='utf-8')
    require("getJSON('assets/catalog.json')" in app and 'loadAsync(item.model)' in app,
            'Catalog/model runtime entry differs')
    require('model-fallback' in app and 'keydown' in app, 'Model error/keyboard handling absent')
    downloads = catalog['downloads']
    package_records = read(SITE/'assets/downloads-manifest.json')['downloads']
    require(downloads == [{key: value for key, value in row.items() if key not in ('members', 'source_files')}
                          for row in package_records], 'Catalog download records differ')
    for row in downloads:
        path = local_link(SITE/'index.html', row['file'])
        require(path is not None and path.is_file(), 'Download is not locally distributable')
        data = checked_file(path, row['sha256'])
        require(len(data) == row['bytes'], 'Download size differs')
        if path.suffix.lower() == '.step':
            require(data.startswith(b'ISO-10303-21;') and b'SI_UNIT(.MILLI.,.METRE.)' in data,
                    'Standard STEP lacks explicit millimetre geometry units')
        if row.get('source'):
            original = checked_file(ROOT/row['source'])
            require(data == original, 'Standard download differs from authoritative source: '+row['file'])
    checksums = (SITE/'downloads/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
    require(set(checksums) == {row['sha256']+'  '+Path(row['file']).name for row in downloads},
            'Download checksum index is incomplete')
    provenance = read(SITE/'assets/inspection-manifest.json')
    for source in provenance['sources']:
        checked_file(SITE/source['file'], source['sha256'])
    checked_file(SITE/'assets/catalog.json', provenance['catalog_sha256'])
    vendor = read(SITE/'vendor/three/version.json')
    require(vendor['license'] == 'MIT' and vendor['integrity'].startswith('sha512-'), 'Unpinned renderer')
    for filename, digest in vendor['files_sha256'].items():
        checked_file(SITE/'vendor/three'/filename, digest)
    require((SITE/'vendor/ibom/LICENSE').is_file(), 'iBOM license not included')
    return catalog, {'designs': len(designs), 'local_html_links': checked, 'download_entries': len(downloads)}


def inspect_archives():
    details = {}
    downloads = read(SITE/'assets/downloads-manifest.json')['downloads']
    for path in sorted((SITE/'downloads').glob('*.zip')):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            require(len(names) == len(set(names)) and z.testzip() is None, 'Invalid ZIP members/CRC')
            for name in names:
                pure = PurePosixPath(name)
                require(not pure.is_absolute() and '..' not in pure.parts and '\\' not in name and
                        not re.match(r'^[A-Za-z]:', name), 'Unsafe archive path: '+name)
                mode = z.getinfo(name).external_attr >> 16
                require(mode & 0o170000 != 0o120000, 'Archive contains symlink')
            readmes = [name for name in names if name.lower().startswith(('readme', 'open_', 'start_'))
                       and name.lower().endswith(('.txt', '.md'))]
            require(readmes, 'Archive lacks opening instructions: '+path.name)
            source_members = 0
            record = next(row for row in downloads if row['file'] == 'downloads/'+path.name)
            bindings = record.get('members', {})
            for name, binding in bindings.items():
                require(name in names, 'Native package inventory member missing')
                data = z.read(name)
                require(sha(data) == binding['sha256'] and len(data) == binding['bytes'],
                        'Native CAD archive member differs')
                original = checked_file(ROOT/binding['source'])
                if Path(name).suffix.lower() in TEXT_SUFFIXES:
                    original, data = original.replace(b'\r\n', b'\n'), data.replace(b'\r\n', b'\n')
                require(original == data, 'Native package is not current source: '+name)
                source_members += 1
            for name in names:
                if name in bindings:
                    continue
                original = ROOT/name
                if original.is_file():
                    member, source = z.read(name), original.read_bytes()
                    if original.suffix.lower() in TEXT_SUFFIXES or original.name in {'sym-lib-table', 'fp-lib-table'}:
                        member, source = member.replace(b'\r\n', b'\n'), source.replace(b'\r\n', b'\n')
                    require(member == source, 'Archive altered native source: '+name)
                    source_members += 1
            if 'SOURCE_SHA256.json' in names:
                hashes = json.loads(z.read('SOURCE_SHA256.json'))
                for name, value in hashes.items():
                    require(name in names and sha(z.read(name)) == value, 'Package member hash differs')
                require(len(hashes) == source_members, 'Package source inventory incomplete')
            if 'geometry-manifest.json' in names:
                geometry = json.loads(z.read('geometry-manifest.json'))
                require(geometry['physical_objects'] == 260 and geometry['solids'] > 260 and
                        geometry['step_native_reopen_valid'], 'Complete STEP native evidence absent')
                step = [name for name in names if name.lower().endswith('.step')]
                require(len(step) == 1 and sha(z.read(step[0])) == geometry['step_sha256'], 'Complete STEP member differs')
                step_data = z.read(step[0])
                require(b'ISO-10303-21;' in step_data[:50], 'Invalid STEP exchange header')
                require(b'SI_UNIT(.MILLI.,.METRE.)' in step_data, 'Complete STEP lacks explicit millimetre units')
                checked_file(ROOT/geometry['source'], geometry['source_sha256'])
                reference = next(model for model in read(SITE/'assets/cad-manifest.json')['models']
                                 if model['id'] == 'reference')
                require(geometry['parts'] == reference['parts'] and geometry['bounds_mm'] == reference['bounds_mm'],
                        'Complete STEP and browser reference inventories differ')
                # Independently inspect the neutral exchange entities as well
                # as its receipt; this does not substitute for native reopening.
                products = re.findall(rb"=\s*PRODUCT\s*\(\s*'((?:[^']|'')*)'", step_data)
                labels = Counter(p['label'] for p in reference['parts'])
                actual = Counter(label.decode('utf-8').replace("''", "'") for label in products)
                require(actual == labels + Counter({Path(geometry['source']).stem: 1}),
                        'Complete STEP has missing/extra named physical products')
                require(len(re.findall(rb'=\s*NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(', step_data)) == 260 and
                        len(re.findall(rb'=\s*MANIFOLD_SOLID_BREP\s*\(', step_data)) == geometry['solids'],
                        'Complete STEP entity inventory differs from native reopening receipt')
            details[path.name] = {'members': len(names), 'unchanged_source_members': source_members,
                                  'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size}
    require(len(details) >= 3 and 'KiCad-SCCI_RH-native-projects.zip' in details,
            'Complete CAD/standard/KiCad downloads missing')
    return details


def preserved():
    rows = subprocess.check_output(['git', 'ls-tree', '-r', '-z', BASELINE], cwd=ROOT).split(b'\0')
    files, expected = [], []
    for row in rows:
        if not row:
            continue
        metadata, raw_name = row.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        if name in MUTABLE:
            continue
        files.append(name)
        expected.append(metadata.split()[2].decode())
    migration = assert_baseline_equivalence(ROOT, BASELINE, list(zip(files, expected)))
    require(migration['files_compared'] == len(files), 'All historical released identities compared after brand migration')
    return {'baseline': BASELINE, 'historical_released_files_compared': len(files),
            'authorized_brand_migration': migration,
            'allowed_reader_metadata_updates': sorted(MUTABLE), 'inventory_sha256': sha('\n'.join(files).encode())}


def published_files():
    """Bind distributed files, not local ignored caches or editor backups."""
    candidates = [p for p in SITE.rglob('*') if p.is_file()]
    candidates += [p for p in (ROOT/'scripts/inspector').glob('*')
                   if p.is_file() and p.suffix.lower() in {'.py', '.mjs'}]
    workflow = ROOT/'.github/workflows/deploy-inspector.yml'
    candidates.append(ROOT/'scripts/project_branding.py')
    if workflow.exists():
        candidates.append(workflow)
    names = sorted({p.relative_to(ROOT).as_posix() for p in candidates})
    ignored = subprocess.run(['git', 'check-ignore', '--stdin', '-z'],
                             input=('\0'.join(names)+'\0').encode(), capture_output=True, cwd=ROOT)
    require(ignored.returncode in (0, 1), 'Could not inspect ignored output files')
    excluded = set(ignored.stdout.decode().strip('\0').split('\0')) if ignored.stdout else set()
    return [ROOT/name for name in names if name not in excluded]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-report', action='store_true')
    parser.add_argument('--skip-preserved', action='store_true', help='Development only; report writing is forbidden.')
    args = parser.parse_args()
    require(not (args.write_report and args.skip_preserved), 'Cannot record incomplete source preservation')
    electronics = read(SITE/'assets/electronics-manifest.json')
    cad = read(SITE/'assets/cad-manifest.json')
    sources, circuit = inspect_electronics(electronics)
    print('Native circuits, BOM population, 80 hierarchy sheets and 32 copper views verified.', flush=True)
    geometry = inspect_geometry(cad, sources)
    print('All ten GLBs decoded: source identities, topology indices, units and part bounds verified.', flush=True)
    _, navigation = inspect_catalog(cad, electronics)
    packages = inspect_archives()
    preservation = {'not_run': 'Development-only skip'} if args.skip_preserved else preserved()
    output_files = published_files()
    bindings = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes().replace(b'\r\n', b'\n'))
                if p.suffix.lower() in TEXT_SUFFIXES else sha(p.read_bytes()) for p in output_files}
    report = {'schema': 'scci_rh.browser-inspector-review.v1', 'date': '2026-10-28', 'passed': True,
              'original_inspector_review_date': '2026-10-21',
              'scope': 'Independent derivative inspection and source preservation; browser interaction is reviewed separately.',
              'geometry': geometry, 'electronics': circuit, 'navigation': navigation,
              'download_packages': packages, 'protected_engineering': preservation,
              'source_and_output_sha256_lf_for_text': bindings,
              'limits': ['Mesh checks verify source identities, decoded bounds and finite topology; exact BRep is supplied in STEP/native downloads.',
                         'iBOM shows outer copper; all four layers have native vector exports.',
                         'No browser, GUI CAD, physical measurement or biological experiment is executed by this checker.']}
    if args.write_report:
        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    elif not args.skip_preserved:
        require(REPORT.is_file(), 'Missing saved inspector review; run --write-report after reviewing the final assets')
        require(read(REPORT) == report,
                'Saved inspector review differs from the current sources/outputs; review changes before --write-report')
    print(json.dumps({'passed': True, 'models': len(geometry), **circuit,
                      'archives': len(packages), 'historical_files_compared': preservation.get('historical_released_files_compared')}, indent=2))


if __name__ == '__main__':
    main()
