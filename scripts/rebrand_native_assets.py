"""Migrate project names inside native containers without altering geometry.

The canonical text/path transformation is supplied by project_branding.py.
This script never performs raw search/replace on opaque CAD or firmware bytes.
Use --apply only after the ordinary tracked path/text migration has completed.
Use --validate-freecad with FreeCAD's Python for before/after geometry checks.
"""
from __future__ import annotations

import argparse
from copy import copy
import gzip
import hashlib
import importlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from project_branding import rename_path, rename_text

TEXT_EXTENSIONS = {'.xml', '.txt', '.json', '.md', '.py', '.ps1', '.cmd',
                   '.fcmacro', '.step', '.stp', '.kicad_sch', '.kicad_pcb',
                   '.kicad_pro', '.kicad_mod', '.kicad_sym', '.csv', '.svg',
                   '.html', '.js', '.css', '.cff', '.yml', '.yaml'}
GEOMETRY_EXTENSIONS = {'.brp', '.brep', '.bin', '.npy'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rewrite_text(data):
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return data
    return rename_text(text).encode('utf-8')


def safe_name(name):
    pure = PurePosixPath(name)
    if pure.is_absolute() or '..' in pure.parts or '\\' in name:
        raise ValueError('Unsafe container member: ' + name)
    return name


def rewrite_zip(data, *, native=False):
    """Preserve every BRep/opaque member byte; transform metadata containers."""
    output = io.BytesIO()
    changes, geometry = [], {}
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        original_names = source.namelist()
        if len(original_names) != len(set(original_names)) or source.testzip():
            raise ValueError('Invalid input ZIP')
        comment_changed = rewrite_text(source.comment) != source.comment
        with zipfile.ZipFile(output, 'w', allowZip64=True) as destination:
            destination.comment = rewrite_text(source.comment)
            new_names = set()
            for info in source.infolist():
                old_name = safe_name(info.filename)
                new_name = safe_name(rename_path(old_name))
                if new_name in new_names:
                    raise ValueError('Renamed member collision: ' + new_name)
                new_names.add(new_name)
                before = source.read(info)
                suffix = PurePosixPath(old_name).suffix.lower()
                after = before
                nested = None
                if suffix == '.fcstd':
                    after, nested = rewrite_zip(before, native=True)
                elif suffix == '.zip' and not native:
                    after, nested = rewrite_zip(before)
                elif native:
                    # StringHasher and BRep persistence records are left intact.
                    # Object identities and Python bindings live in XML metadata.
                    if suffix == '.xml':
                        after = rewrite_text(before)
                elif suffix in TEXT_EXTENSIONS or PurePosixPath(old_name).name in {
                        'fp-lib-table', 'sym-lib-table', 'SOURCE_SHA256.json'}:
                    after = rewrite_text(before)
                elif suffix == '.glb':
                    after, nested = rewrite_glb(before)
                if suffix in GEOMETRY_EXTENSIONS:
                    if after != before:
                        raise AssertionError('Geometry payload changed: ' + old_name)
                    geometry[new_name] = digest(before)
                if before != after or old_name != new_name:
                    changes.append({'before_name_sha256': digest(old_name.encode()), 'after': new_name,
                                    'before_sha256': digest(before),
                                    'after_sha256': digest(after),
                                    **({'nested': nested} if nested else {})})
                new_info = copy(info)
                new_info.filename = new_name
                new_info.comment = rewrite_text(info.comment)
                destination.writestr(new_info, after)
    result = output.getvalue()
    with zipfile.ZipFile(io.BytesIO(result)) as check:
        assert check.testzip() is None
        for name, expected in geometry.items():
            assert digest(check.read(name)) == expected
    return (result if changes or comment_changed else data), {
        'kind': 'FCStd metadata' if native else 'ZIP container',
        'changed_members': changes,
        'preserved_geometry_members_sha256': geometry,
    }


def rewrite_glb(data):
    if data[:4] != b'glTF' or struct.unpack_from('<I', data, 4)[0] != 2:
        raise ValueError('Expected glTF 2 GLB')
    if struct.unpack_from('<I', data, 8)[0] != len(data):
        raise ValueError('Invalid GLB length')
    cursor, chunks, hashes = 12, [], []
    while cursor < len(data):
        length, kind = struct.unpack_from('<II', data, cursor)
        payload = data[cursor + 8:cursor + 8 + length]
        if len(payload) != length:
            raise ValueError('Truncated GLB chunk')
        cursor += 8 + length
        if kind == 0x4E4F534A:
            # The shared transform only changes brand strings, never numbers.
            original = json.loads(payload.decode('utf-8').rstrip(' \x00'))
            mapped = rename_text(json.dumps(original, ensure_ascii=False))
            updated = json.loads(mapped)
            payload = json.dumps(updated, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
            payload += b' ' * (-len(payload) % 4)
        else:
            hashes.append({'kind': kind, 'sha256': digest(payload), 'bytes': length})
        chunks.append(struct.pack('<II', len(payload), kind) + payload)
    body = b''.join(chunks)
    result = b'glTF' + struct.pack('<II', 2, 12 + len(body)) + body
    # Non-JSON chunks contain the actual vertex/index buffers.
    cursor, actual = 12, []
    while cursor < len(result):
        length, kind = struct.unpack_from('<II', result, cursor)
        payload = result[cursor + 8:cursor + 8 + length]
        if kind != 0x4E4F534A:
            actual.append({'kind': kind, 'sha256': digest(payload), 'bytes': length})
        cursor += 8 + length
    assert actual == hashes
    return result, {'kind': 'GLB metadata', 'preserved_buffer_chunks': hashes}


def rewrite_stl(data):
    # Binary STL has an 80-byte comment and fixed 50-byte triangle records.
    if len(data) >= 84 and len(data) == 84 + 50 * struct.unpack_from('<I', data, 80)[0]:
        raw = data[:80].rstrip(b'\x00 ')
        try:
            header = rename_text(raw.decode('ascii')).encode('ascii')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return data, {'kind': 'binary STL', 'changed': False}
        if len(header) > 80:
            raise ValueError('Renamed STL comment exceeds 80-byte header')
        result = header.ljust(80, b'\x00') + data[80:]
        assert result[80:] == data[80:]
        return result, {'kind': 'binary STL', 'geometry_sha256': digest(data[80:])}
    result = rewrite_text(data)
    return result, {'kind': 'ASCII STL'}


def file_transform(path):
    before = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == '.fcstd':
        after, evidence = rewrite_zip(before, native=True)
    elif suffix == '.zip':
        after, evidence = rewrite_zip(before)
    elif suffix == '.glb':
        after, evidence = rewrite_glb(before)
    elif suffix == '.stl':
        after, evidence = rewrite_stl(before)
    elif suffix == '.gz':
        plain = gzip.decompress(before)
        changed = rewrite_text(plain)
        after = gzip.compress(changed, compresslevel=9, mtime=0) if changed != plain else before
        evidence = {'kind': 'gzip text', 'uncompressed_before_sha256': digest(plain),
                    'uncompressed_after_sha256': digest(changed)}
    else:
        raise ValueError('Unsupported native/container format: ' + str(path))
    return before, after, evidence


def native_summary(path):
    """Read actual saved BReps in native FreeCAD; do not save/recompute sources."""
    import FreeCAD as App
    import Part  # noqa: F401
    module_parent = ROOT / 'cad/stage5/future-interface'
    sys.path.insert(0, str(module_parent))
    # Resolve both the old saved module identity and its new filename while
    # opening the before/after copy. Only imports existing project modules.
    with zipfile.ZipFile(path) as z:
        xml = z.read('Document.xml').decode('utf-8')
    for name in set(re.findall(r'\bmodule="([A-Za-z_][A-Za-z0-9_.]*)"', xml)):
        new_name = rename_text(name)
        if (module_parent / (new_name + '.py')).is_file():
            sys.modules[name] = importlib.import_module(new_name)
    doc = App.openDocument(str(path))
    try:
        objects = []
        for obj in doc.Objects:
            if not hasattr(obj, 'Shape') or obj.Shape.isNull():
                continue
            shape = obj.Shape
            if not shape.isValid():
                raise AssertionError('Invalid native BRep: ' + obj.Name)
            box = shape.BoundBox
            proxy = getattr(obj, 'Proxy', None)
            proxy_module = getattr(getattr(proxy, '__class__', None), '__module__', None)
            objects.append({'name': rename_text(obj.Name),
                            'label': rename_text(obj.Label),
                            'proxy_module': rename_text(proxy_module) if proxy_module else None,
                            'solids': len(shape.Solids),
                            'volume': round(shape.Volume, 7),
                            'area': round(shape.Area, 7),
                            'bounds': [round(v, 7) for v in (box.XMin, box.YMin, box.ZMin,
                                                           box.XMax, box.YMax, box.ZMax)]})
        return {'objects': objects, 'all_saved_shapes_valid': True,
                'native_engine': '.'.join(App.Version()[:3]),
                'source_save_performed': False}
    finally:
        App.closeDocument(doc.Name)


def tracked_paths():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').strip('\0').split('\0')
    return sorted({ROOT / rename_path(name) for name in names if name})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--native-only', action='store_true', help='Only FCStd files; excludes download ZIPs.')
    parser.add_argument('--formats', nargs='+', choices=['fcstd', 'zip', 'glb', 'stl', 'gz'],
                        help='Restrict the file formats for a coordinated migration phase.')
    parser.add_argument('--prefix', action='append', default=[],
                        help='Restrict processing to these repository-relative path prefixes.')
    parser.add_argument('--freecad-python', type=Path,
                        help='Validate changed FCStd files through the installed native Python before accepting them.')
    parser.add_argument('--validate-freecad', nargs=2, type=Path, metavar=('BEFORE', 'AFTER'))
    parser.add_argument('--report', type=Path, default=ROOT / 'tmp/rebrand-native-assets.json')
    args = parser.parse_args()
    if args.validate_freecad:
        before, after = [native_summary(p) for p in args.validate_freecad]
        if before != after:
            raise AssertionError('Before/after native shape metrics differ')
        print('NATIVE_REBRAND_RESULT=' + json.dumps({'passed': True, 'geometry': after}))
        return
    rows = []
    supported = {'.fcstd'} if args.native_only else ({'.' + name for name in args.formats}
                if args.formats else {'.fcstd', '.zip', '.glb', '.stl', '.gz'})
    for path in tracked_paths():
        if not path.is_file() or path.suffix.lower() not in supported:
            continue
        if args.prefix and not any(path.relative_to(ROOT).as_posix().startswith(p) for p in args.prefix):
            continue
        before, after, evidence = file_transform(path)
        changed = before != after
        if changed and args.apply:
            path.write_bytes(after)
            if path.suffix.lower() == '.fcstd' and args.freecad_python:
                temporary_parent = ROOT / 'tmp'
                temporary_parent.mkdir(exist_ok=True)
                try:
                    with tempfile.TemporaryDirectory(prefix='native-branding-', dir=temporary_parent) as temporary:
                        original = Path(temporary) / path.name
                        original.write_bytes(before)
                        checked = subprocess.run([str(args.freecad_python), str(Path(__file__)),
                                                  '--validate-freecad', str(original), str(path)],
                                                 capture_output=True, text=True, encoding='utf-8',
                                                 errors='replace', check=True)
                        marker = next(line.partition('=')[2] for line in checked.stdout.splitlines()
                                      if line.startswith('NATIVE_REBRAND_RESULT='))
                        evidence['native_comparison'] = json.loads(marker)
                except Exception:
                    path.write_bytes(before)
                    raise
        rows.append({'path': path.relative_to(ROOT).as_posix(), 'changed': changed,
                     'before_sha256': digest(before), 'after_sha256': digest(after),
                     'evidence': evidence})
        print(('Updated ' if changed and args.apply else 'Review ') + path.relative_to(ROOT).as_posix(), flush=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'applied': args.apply, 'assets': rows,
                                      'opaque_firmware_changed': False}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'assets': len(rows), 'changed': sum(r['changed'] for r in rows),
                      'applied': args.apply, 'report': str(args.report)}))


if __name__ == '__main__':
    main()
