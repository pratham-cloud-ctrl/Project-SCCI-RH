"""Repair visible brand lettering in source-derived figures without changing data.

Matplotlib commonly stores rendered lettering as glyph outlines and keeps the
plain text only in a comment. A text-only migration changes the comment while
leaving the old visible lettering. This tool replaces only affected label groups
with native SVG text, preserves every geometry path, and renders matching PNGs
using Qt's native SVG renderer with the original output dimensions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from project_branding import rename_path, rename_text, historical_bytes

SVG = 'http://www.w3.org/2000/svg'
XLINK = 'http://www.w3.org/1999/xlink'
ET.register_namespace('', SVG)
ET.register_namespace('xlink', XLINK)
for prefix, uri in [('dc', 'http://purl.org/dc/elements/1.1/'),
                    ('cc', 'http://creativecommons.org/ns#'),
                    ('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')]:
    ET.register_namespace(prefix, uri)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def geometry_paths(root):
    # Font outlines, plotted curves and axes must all remain exact. Native text
    # changes only the use of glyphs, not any existing shape definition.
    tags = {'path', 'rect', 'line', 'circle', 'ellipse', 'polygon', 'polyline', 'image'}
    return [(element.tag, sorted(element.attrib.items())) for element in root.iter()
            if isinstance(element.tag, str) and element.tag.rsplit('}', 1)[-1] in tags]


@lru_cache(maxsize=32)
def glyph_index_characters(font_name):
    # Older Matplotlib releases identify outlines by glyph index, rather than
    # Unicode code point. Resolve that through the exact bundled font table.
    sys.path.append(str(ROOT / '.venv/Lib/site-packages'))
    from fontTools.ttLib import TTFont
    font_path = ROOT / '.venv/Lib/site-packages/matplotlib/mpl-data/fonts/ttf' / (font_name + '.ttf')
    if not font_path.is_file():
        return {}
    with TTFont(font_path) as font:
        reverse = {}
        for code, name in sorted(font.getBestCmap().items()):
            reverse.setdefault(name, chr(code))
        return {i: reverse[name] for i, name in enumerate(font.getGlyphOrder()) if name in reverse}


def repair_svg(path):
    original = path.read_bytes()
    tree = ET.fromstring(original)
    geometry = geometry_paths(tree)
    changed = []
    for group in list(tree.iter('{' + SVG + '}g')):
        if not group.attrib.get('id', '').startswith('text_'):
            continue
        uses = list(group.iter('{' + SVG + '}use'))
        if not uses:
            continue
        glyphs = []
        indexes = []
        fonts = []
        for use in uses:
            href = use.attrib.get('{' + XLINK + '}href', use.attrib.get('href', ''))
            match = re.fullmatch(r'#(.+)-([0-9a-fA-F]{1,6})', href)
            if not match:
                glyphs = []
                break
            glyphs.append(chr(int(match[2], 16)))
            indexes.append(int(match[2], 16))
            fonts.append(match[1])
        if not glyphs:
            continue
        before = ''.join(glyphs)
        after = rename_text(before)
        if after == before:
            mapped = [glyph_index_characters(font).get(index) for font, index in zip(fonts, indexes)]
            if all(char is not None for char in mapped):
                before = ''.join(mapped)
                after = rename_text(before)
        if after == before:
            continue
        # Pure ASCII brand strings can be restored with the same native font;
        # mixed mathematical groups are deliberately left for their generator.
        inner_groups = [e for e in group if e.tag == '{' + SVG + '}g']
        if len(inner_groups) != 1:
            raise ValueError('Complex branded SVG label requires its generator: ' + str(path))
        inner = inner_groups[0]
        if any(e.tag not in {'{' + SVG + '}defs', '{' + SVG + '}use'} for e in inner):
            raise ValueError('Mixed branded SVG label requires its generator: ' + str(path))
        for element in list(inner):
            if element.tag == '{' + SVG + '}use':
                inner.remove(element)
        font = fonts[0]
        family = 'DejaVu Sans' if 'DejaVuSans' in font else 'DejaVu Serif' if 'DejaVuSerif' in font else 'Arial'
        attrs = {'x': '0', 'y': '0', 'transform': 'scale(1 -1)',
                 'font-family': family, 'font-size': '100',
                 '{http://www.w3.org/XML/1998/namespace}space': 'preserve'}
        if 'Bold' in font:
            attrs['font-weight'] = 'bold'
        if 'Oblique' in font or 'Italic' in font:
            attrs['font-style'] = 'italic'
        text = ET.SubElement(inner, '{' + SVG + '}text', attrs)
        text.text = after.replace('SCCI_RH', 'SCCI RH')
        changed.append({'group': group.attrib['id'], 'new_text': text.text,
                        'original_label_sha256': sha(before.encode()),
                        'original_font': font})
    if not changed:
        return None
    assert geometry_paths(tree) == geometry, 'Existing plotted/geometry/font paths changed'
    after = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
    path.write_bytes(after + b'\n')
    return {'path': path.relative_to(ROOT).as_posix(), 'before_sha256': sha(original),
            'after_sha256': sha(path.read_bytes()), 'labels': changed,
            'geometry_paths_sha256': sha(json.dumps(geometry, separators=(',', ':')).encode()),
            'all_original_geometry_paths_unchanged': True}


def png_dimensions(path):
    import struct
    data = path.read_bytes()[:24]
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Not a PNG: ' + str(path))
    return struct.unpack('>II', data[16:24])


def render_svg(path):
    from PySide6 import QtCore, QtGui, QtSvg
    destination = path.with_suffix('.png')
    if not destination.is_file():
        return None
    before = destination.read_bytes()
    width, height = png_dimensions(destination)
    renderer = QtSvg.QSvgRenderer(str(path))
    if not renderer.isValid():
        raise ValueError('Native Qt cannot render SVG: ' + str(path))
    image = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    assert image.save(str(destination))
    return {'path': destination.relative_to(ROOT).as_posix(), 'width': width, 'height': height,
            'before_sha256': sha(before), 'after_sha256': sha(destination.read_bytes()),
            'source_svg_sha256': sha(path.read_bytes()), 'renderer': 'Qt QSvgRenderer'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', action='append', default=[])
    parser.add_argument('--render-pairs', action='store_true')
    parser.add_argument('--only-record', type=Path,
                        help='Only rerender previously repaired SVGs named in this report.')
    parser.add_argument('--report', type=Path, default=ROOT / 'provenance/rebrand-visual-assets.json')
    args = parser.parse_args()
    if args.render_pairs:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6 import QtGui
        app = QtGui.QGuiApplication([])
        fonts = ROOT / '.venv/Lib/site-packages/matplotlib/mpl-data/fonts/ttf'
        for font in fonts.glob('*.ttf'):
            QtGui.QFontDatabase.addApplicationFont(str(font))
        for name in ['arial.ttf', 'arialbd.ttf']:
            QtGui.QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts') / name))
    old_report = json.loads(args.only_record.read_text(encoding='utf-8')) if args.only_record else None
    if old_report:
        paths = [ROOT / row['path'] for row in old_report['source_svgs']]
    else:
        names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().strip('\0').split('\0')
        paths = sorted({ROOT / rename_path(name) for name in names if name.lower().endswith('.svg')})
    repaired, rasters, deferred = [], [], []
    for path in paths:
        if not path.is_file() or (args.prefix and not any(path.relative_to(ROOT).as_posix().startswith(p) for p in args.prefix)):
            continue
        try:
            result = None if old_report else repair_svg(path)
        except ValueError as error:
            deferred.append({'path': path.relative_to(ROOT).as_posix(), 'reason': str(error)})
            print('Requires source generator: ' + path.relative_to(ROOT).as_posix(), flush=True)
            continue
        # Recover receipts for a prior interrupted label pass using the actual
        # immutable original Git blob, rather than overwriting it or assuming
        # that numerical figure geometry stayed unchanged.
        if not old_report and result is None:
            current = ET.fromstring(path.read_bytes())
            labels = [e.text for e in current.iter('{' + SVG + '}text')
                      if e.text and ('SCCI RH' in e.text or 'SCCI_RH' in e.text)]
            if labels:
                previous = historical_bytes(ROOT, 'HEAD', path.relative_to(ROOT).as_posix())
                prior = ET.fromstring(previous)
                original_geometry, new_geometry = geometry_paths(prior), geometry_paths(current)
                if original_geometry == new_geometry:
                    result = {'path': path.relative_to(ROOT).as_posix(),
                              'baseline': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                              'before_sha256': sha(previous), 'after_sha256': sha(path.read_bytes()),
                              'labels': [{'new_text': label} for label in labels],
                              'geometry_paths_sha256': sha(json.dumps(original_geometry, separators=(',', ':')).encode()),
                              'all_original_geometry_paths_unchanged': True,
                              'receipt_recovered_from_original_git_geometry': True}
        if result:
            repaired.append(result)
            print('Repaired visible labels: ' + path.relative_to(ROOT).as_posix(), flush=True)
        if args.render_pairs and (result or old_report):
            raster = render_svg(path)
            if raster:
                rasters.append(raster)
    report = {'scope': 'Visible branding only; source scientific values and geometry paths preserved',
              'source_svgs': old_report['source_svgs'] if old_report else repaired,
              'rendered_pngs': rasters, 'requires_source_generator': deferred}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'svg_sources': len(report['source_svgs']), 'png_renders': len(rasters)}))


if __name__ == '__main__':
    main()
