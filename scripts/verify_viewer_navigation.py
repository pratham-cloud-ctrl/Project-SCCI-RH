"""Check the GitHub reader routes and preserve the released engineering files.

Read-only by default. --write-report records a reviewed documentation checkpoint;
this receipt excludes itself to avoid a hash cycle. No native app is launched.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from project_branding import assert_baseline_equivalence
REPORT = ROOT / 'provenance/viewer-navigation-verification.json'
BASELINE = '9f6cf0a4403a00549a858ae9f0cecdd9dce0c5bb'
MUTABLE = {
    'README.md', 'START_HERE.md', 'CURRENT_STATUS.md',
    'provenance/manifest.sha256', 'provenance/stage6-release-verification.json',
    'scripts/verify_stage6_release.py', '.github/workflows/verify-release.yml',
}
GUIDES = ['README.md', 'theory.md', 'cad.md', 'electronics.md', 'firmware.md',
          'reviewer-guide.md', 'repository-map.md']


def git(*args, data=None):
    return subprocess.check_output(['git', *args], input=data, cwd=ROOT)


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.images = []
        self.anchors = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for name in ('href', 'src'):
            if attrs.get(name):
                self.links.append(attrs[name])
        if tag == 'img':
            assert attrs.get('alt', '').strip(), 'HTML image needs meaningful alternative text'
            self.images.append(attrs['src'])
        for name in ('id', 'name'):
            if attrs.get(name):
                self.anchors.add(attrs[name])


def without_code(text):
    return re.sub(r'^(`{3,}|~{3,}).*?^\1\s*$', '', text, flags=re.M | re.S)


def anchors(path):
    text = without_code(path.read_text(encoding='utf-8-sig'))
    html = Links()
    html.feed(text)
    result = set(html.anchors)
    used = Counter()
    for match in re.finditer(r'^#{1,6}\s+(.+?)(?:\s+#+)?\s*$', text, re.M):
        heading = re.sub(r'<[^>]*>', '', match[1])
        heading = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', heading)
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        number = used[slug]
        used[slug] += 1
        result.add(slug + ('-' + str(number) if number else ''))
    return result


def inspect():
    documents = [ROOT / name for name in ('README.md', 'START_HERE.md',
                                         'CURRENT_STATUS.md', 'docs/README.md')]
    documents += [ROOT / 'docs/explore' / name for name in GUIDES]
    local_links = external_links = fragment_links = 0
    image_paths = set()
    file_bindings = {}
    for doc in documents:
        assert doc.is_file(), 'Missing reader guide: ' + str(doc)
        content = doc.read_text(encoding='utf-8-sig')
        text = without_code(content)
        html = Links()
        html.feed(text)
        targets = re.findall(r'\]\(([^)\n]+)\)', text) + html.links
        for alt, target in re.findall(r'!\[([^]]*)\]\(([^)\n]+)\)', text):
            assert alt.strip(), 'Markdown image needs meaningful alternative text'
            if not urlsplit(target).scheme:
                image_paths.add((doc.parent / unquote(target)).resolve())
        image_paths.update((doc.parent / unquote(name)).resolve()
                           for name in html.images if not urlsplit(name).scheme)
        for target in targets:
            target = target.strip().strip('<>')
            parts = urlsplit(target)
            if parts.scheme:
                assert parts.scheme in {'http', 'https', 'mailto'}, 'Unexpected URI: ' + target
                external_links += 1
                continue
            assert not parts.netloc, 'Unexpected protocol-relative link: ' + target
            path = (doc.parent / unquote(parts.path)).resolve() if parts.path else doc
            assert path.is_relative_to(ROOT), 'Link escapes repository: ' + target
            assert path.exists(), f'{doc.relative_to(ROOT)}: missing link {target}'
            local_links += 1
            if parts.fragment and path.suffix.lower() == '.md':
                assert unquote(parts.fragment) in anchors(path), (
                    f'{doc.relative_to(ROOT)}: missing section {target}')
                fragment_links += 1
        file_bindings[doc.relative_to(ROOT).as_posix()] = digest(doc)
    assert image_paths and all(p.is_file() for p in image_paths)
    for path in image_paths:
        with path.open('rb') as source:
            signature = source.read(8)
            assert (signature == b'\x89PNG\r\n\x1a\n' or
                    signature.startswith(b'\xff\xd8\xff')), 'Invalid preview image: ' + str(path)

    preview_path = ROOT / 'docs/explore/assets/manifest.json'
    previews = json.loads(preview_path.read_text(encoding='utf-8-sig'))
    assert previews['schema'] == 'scci_rh.reader-previews.v1'
    builder = ROOT / previews['generator']
    assert builder == ROOT / 'scripts/build_reader_previews.py'
    assert digest(builder) == previews['generator_sha256_lf']
    assert len(previews['images']) == 12
    outputs = set()
    source_bytes = output_bytes = 0
    for item in previews['images']:
        source = (ROOT / item['source']).resolve()
        output = (ROOT / item['output']).resolve()
        assert source.is_relative_to(ROOT) and output.is_relative_to(preview_path.parent)
        assert output in image_paths, 'Unused reader preview: ' + item['output']
        assert output not in outputs, 'Duplicate reader preview'
        outputs.add(output)
        for kind, path in (('source', source), ('output', output)):
            data = path.read_bytes()
            assert len(data) == item[kind + '_bytes']
            assert hashlib.sha256(data).hexdigest() == item[kind + '_sha256']
        width, height = item['source_dimensions']
        result_width, result_height = item['output_dimensions']
        assert 0 < result_width <= min(width, 1000) and result_height > 0
        assert abs(result_height - height * result_width / width) <= 0.5
        source_bytes += item['source_bytes']
        output_bytes += item['output_bytes']
    assert previews['totals'] == {
        'images': len(outputs), 'source_bytes': source_bytes,
        'output_bytes': output_bytes, 'saved_bytes': source_bytes - output_bytes,
    }
    file_bindings[previews['generator']] = digest(builder)
    file_bindings[preview_path.relative_to(ROOT).as_posix()] = digest(preview_path)

    electronics = ROOT / 'docs/explore/electronics.md'
    gallery = electronics.read_text(encoding='utf-8')
    board_paths = sorted((ROOT / 'electronics/stage4/integrated-pcb/boards').glob('*/*.kicad_pcb'))
    assert len(board_paths) == 8
    for board in board_paths:
        name = board.parent.name
        assert f'exports/{name}/isometric.png' in gallery, 'Board absent from gallery: ' + name
        assert board.name in gallery, 'Gallery lacks native layout: ' + name
        assert board.with_suffix('.kicad_sch').name in gallery, 'Gallery lacks native circuit: ' + name
    mesh = ROOT / 'cad/stage5/future-interface/SCCI_RH_future_interface.stl'
    assert mesh.stat().st_size < 10_000_000, 'Future mesh exceeds documented GitHub viewer limit'

    # Keep original Git identities and compare the current authorized rename;
    # rendered/recompiled/rebound derivatives require their own exact attestation.
    baseline = []
    for row in git('ls-tree', '-r', '-z', BASELINE).split(b'\0'):
        if not row:
            continue
        head, name = row.split(b'\t')
        mode, kind, blob = head.decode().split()
        name = name.decode('utf-8')
        assert kind == 'blob'
        if name not in MUTABLE:
            baseline.append((name, blob, mode))
    migration = assert_baseline_equivalence(ROOT, BASELINE, [(name, blob) for name, blob, _ in baseline])
    assert migration['files_compared'] == len(baseline), 'Every released identity compared after brand migration'
    inventory = ''.join(f'{mode} {blob} {name}\n' for name, blob, mode in baseline)
    file_bindings['scripts/verify_viewer_navigation.py'] = digest(Path(__file__))
    file_bindings['scripts/project_branding.py'] = digest(ROOT/'scripts/project_branding.py')
    file_bindings['.github/workflows/verify-release.yml'] = digest(ROOT / '.github/workflows/verify-release.yml')
    return {
        'schema': 'scci_rh.reader-navigation.v1', 'date': '2026-10-28', 'passed': True,
        'original_reader_review_date': '2026-10-21',
        'scope': 'GitHub documentation, local links, section anchors and existing preview assets; no redesigned engineering',
        'documents': len(documents), 'local_links': local_links,
        'local_markdown_fragments': fragment_links, 'external_links_recorded': external_links,
        'unique_image_previews': len(image_paths), 'board_gallery_entries': len(board_paths),
        'reader_preview_derivatives': len(outputs),
        'reader_preview_source_bytes': source_bytes, 'reader_preview_bytes': output_bytes,
        'git_blob_baseline': BASELINE, 'historical_released_files_compared': len(baseline),
        'authorized_brand_migration': migration,
        'baseline_allowed_reader_and_verification_updates': sorted(MUTABLE),
        'original_historical_inventory_sha256': hashlib.sha256(inventory.encode()).hexdigest(),
        'future_mesh_bytes': mesh.stat().st_size, 'source_sha256_lf': file_bindings,
        'external_urls_live_checked_by_this_script': False,
        'native_geometry_or_electrical_design_changed': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-report', action='store_true')
    args = parser.parse_args()
    result = inspect()
    if args.write_report:
        REPORT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    else:
        assert result == json.loads(REPORT.read_text(encoding='utf-8-sig')), (
            'Reader guides changed; inspect before updating the checkpoint')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
