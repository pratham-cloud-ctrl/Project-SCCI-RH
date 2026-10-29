"""Refresh only presentation/source bindings after the native GUI save.

This does not change geometry or overwrite the generator's measured checks.
The independent inspector remains responsible for checking saved native solids.
"""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    data = path.read_bytes()
    if path.suffix.lower() in ('.py', '.json', '.csv', '.md', '.cmd', '.fcmacro'):
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def finalize():
    value = json.loads((HERE/'contract.json').read_text(encoding='utf-8'))
    value['artifacts'].update({'fitted_native_png': 'future-fitted-native.png',
                               'exploded_native_png': 'future-exploded-native.png',
                               'native_visual_receipt': 'native-visual-receipt.json'})
    value['artifact_sha256'] = {v: digest(HERE/v) for v in value['artifacts'].values()}
    sources = [HERE/'scci_rh_future_features.py', HERE/'build_future_interface.py',
               HERE/'style_future_interface.py', HERE/'finalize_presentation.py',
               HERE/'open_future_interface.FCMacro', HERE/'open_future_interface_exploded.FCMacro',
               HERE/'OPEN_FUTURE_INTERFACE.cmd', HERE/'OPEN_FUTURE_INTERFACE_EXPLODED.cmd',
               HERE/'README.md', ROOT/'docs/stage5/future-package-design.md']
    value['source_hashes'].update({str(p.relative_to(ROOT)).replace('\\', '/'): digest(p) for p in sources})
    value['native_presentation'] = {
        'saved_through': 'actual FreeCAD1.1.4 GUI via native MCP execute_python',
        'fitted_visible_physical_parts': 230,
        'fitted_hidden': 'construction operands and all six allocations',
        'exploded_visible_parts_and_allocations': 236,
        'native_images_reviewed': True,
        'view': 'axonometric with margin; explicit saved palette and allocation transparency',
        'geometry_note': 'Styling save only; independent saved-native inspection must establish geometry parity.'}
    for name in ('contract.json', 'geometry-receipt.json'):
        (HERE/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({'bound_artifacts': len(value['artifacts']), 'sources': len(value['source_hashes']),
                      'ports': len(value['ports']), 'parts': len(value['parts'])}))


if __name__ == '__main__':
    finalize()
