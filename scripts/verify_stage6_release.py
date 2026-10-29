"""Audit the integrated digital release without asserting biological efficacy.

Default mode recomputes and compares the saved reviewed checkpoint. Use
--write-report only after final manuscript rendering and actual visual review.
--archive PATH additionally compares a source ZIP with the exact HEAD Git blobs;
it never builds an archive inside the tree or rewrites the tracked checkpoint.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import unquote
import zipfile

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from project_branding import assert_baseline_equivalence
CONTRACT = ROOT / 'docs/stage6/release-contract.json'
REPORT = ROOT / 'provenance/stage6-release-verification.json'
TEXT_SUFFIXES = {'.py', '.c', '.h', '.md', '.json', '.yml', '.yaml', '.txt', '.csv',
                 '.cff', '.bib', '.svg', '.ps1', '.cmd', '.css', '.html',
                 '.hex', '.map', '.config', '.dts', '.js', '.mjs'}


def sha(path: Path, normalized=False):
    data = path.read_bytes()
    if normalized:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def git(*args, input=None):
    return subprocess.check_output(['git', *args], input=input, cwd=ROOT)


def tree_entries(commit):
    result = []
    for item in git('ls-tree', '-r', '-z', commit).split(b'\0'):
        if not item:
            continue
        header, path = item.split(b'\t')
        mode, kind, blob = header.decode('ascii').split()
        assert kind == 'blob', 'Submodules need a separate release policy'
        result.append((path.decode('utf-8'), blob, mode))
    return result


def inspect_archive(path):
    """Verify every unmodified Git blob, not just a ZIP's CRC/filename list."""
    entries = tree_entries('HEAD')
    with zipfile.ZipFile(path) as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in files]
        expected = {name for name, _, _ in entries}
        assert len(names) == len(set(names)), 'Duplicate archive member'
        prefix = ''
        if set(names) != expected:
            roots = {PurePosixPath(name).parts[0] for name in names}
            assert len(roots) == 1, 'Unexpected source ZIP members'
            prefix = next(iter(roots)) + '/'
            assert {name[len(prefix):] for name in names} == expected
        assert all(not PurePosixPath(name).is_absolute() and
                   '..' not in PurePosixPath(name).parts for name in names)
        for name, blob, _ in entries:
            item = archive.getinfo(prefix + name)
            digest = hashlib.sha1(b'blob ' + str(item.file_size).encode() + b'\0')
            with archive.open(item) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            assert digest.hexdigest() == blob, 'Archive differs from commit: ' + name
    return {'archive': path.name, 'files': len(entries),
            'commit': git('rev-parse', 'HEAD').decode().strip(),
            'sha256': sha(path), 'bytes': path.stat().st_size,
            'exact_git_blob_comparison': True}


def inspect_bound_git_blobs(artifacts, staged=False):
    """Catch checkout/Git-filter disagreement before publication, including EOLs."""
    prefix = ':' if staged else 'HEAD:'
    names = sorted(artifacts)
    data = git('cat-file', '--batch',
               input=''.join(prefix + name + '\n' for name in names).encode('utf-8'))
    offset = 0
    for name in names:
        end = data.index(b'\n', offset)
        header = data[offset:end].decode('ascii')
        assert not header.endswith(' missing'), 'Missing bound Git blob: ' + name
        size = int(header.rsplit(' ', 1)[1])
        content = data[end + 1:end + 1 + size]
        offset = end + size + 2
        if artifacts[name]['text_normalized']:
            content = content.replace(b'\r\n', b'\n')
        assert hashlib.sha256(content).hexdigest() == artifacts[name]['sha256'], (
            'Bound artifact differs from canonical Git blob: ' + name)
    return len(names)


def audit():
    contract = json.loads(CONTRACT.read_text(encoding='utf-8-sig'))
    checks = 0

    def check(condition, description):
        nonlocal checks
        assert condition, description
        checks += 1

    check(contract['schema'] == 'scci_rh.stage6.release-contract.v1', 'release schema')
    check(re.fullmatch(r'2\.(?:0|1)\.\d+', contract['version']) and
          contract['tag'] == 'v' + contract['version'],
          'new release leaves historical v1 tag distinct')
    check(contract['limitations']['assumptions_permitted_when_explicit_and_defensible'],
          'conditional future interface is permitted')
    for name, value in contract['limitations'].items():
        expected = name in {'assumptions_permitted_when_explicit_and_defensible',
                            'original_negative_results_preserved'}
        check(value is expected, 'truthful finite digital limitation: ' + name)

    baseline = contract['baseline_commit']
    check(git('rev-parse', baseline).decode().strip() == baseline,
          'full immutable Stage 5 baseline available')
    mutable = set(contract['baseline_mutable_entries'])
    allowed_mutable = {'.gitattributes', '.gitignore', 'README.md', 'CURRENT_STATUS.md',
                       'CITATION.cff', 'docs/engineering-roadmap.md',
                       'provenance/manifest.sha256'}
    check(mutable == allowed_mutable, 'only declared current entry/manifest files mutable')
    baseline_entries = tree_entries(baseline)
    check(len(baseline_entries) == contract['baseline_tracked_files'],
          'exact completed baseline inventory')
    preserved = [(name, blob) for name, blob, _ in baseline_entries
                 if name not in mutable]
    check(len(preserved) == contract['baseline_tracked_files'] - len(mutable),
          'complete previous digital release retained')
    migration = assert_baseline_equivalence(ROOT, baseline, preserved)
    check(migration['files_compared'] == len(preserved), 'every Stage 1-5 historical identity checked after authorized branding migration')
    preserved_digest = hashlib.sha256(''.join(name + ' ' + blob + '\n'
                                             for name, blob in preserved).encode()).hexdigest()

    manuscript = contract['manuscript']
    required = set(contract['required_files']) | set(manuscript.values())
    required.update({'docs/stage6/release-contract.json'})
    for name in sorted(required):
        path = ROOT / name
        check(path.is_file() and path.stat().st_size > 0, 'required release artifact: ' + name)
        check(path.stat().st_size < 100 * 1024 * 1024, 'GitHub per-file size: ' + name)

    # Validate current navigation, including image inputs; historical documents
    # are preserved snapshots and are not rewritten by this finite entry audit.
    docs = [ROOT / 'README.md', ROOT / 'START_HERE.md', ROOT / 'CURRENT_STATUS.md',
            ROOT / 'docs/README.md',
            *sorted((ROOT / 'docs/explore').rglob('*.md')),
            *sorted((ROOT / 'docs/stage6').rglob('*.md')),
            *sorted((ROOT / 'docs/review-v2.0.1').rglob('*.md')),
            ROOT / 'cad/CURRENT_CAD.md',
            ROOT / 'firmware/nrf5340/uart-revision/README.md',
            ROOT / manuscript['source']]
    links = 0
    external_links = set()
    for doc in docs:
        content = doc.read_text(encoding='utf-8-sig')
        for target in re.findall(r'\]\(([^)]+)\)', content):
            target = target.strip()
            if target.startswith('<'):
                target = target[1:target.index('>')]
            else:
                target = re.split(r'\s+["\']', target, maxsplit=1)[0]
            if target.startswith(('https:', 'http:', 'mailto:')):
                external_links.add(target)
                continue
            if target.startswith('#'):
                continue
            target = unquote(target.split('#')[0])
            check(bool(target), 'nonempty local link: ' + str(doc.relative_to(ROOT)))
            path = (doc.parent / target).resolve()
            check(path.is_relative_to(ROOT), 'portable in-repository local link: ' + target)
            check(path.exists(), 'local release entry link: ' + target)
            links += 1

    citation = (ROOT / 'CITATION.cff').read_text(encoding='utf-8-sig')
    check(re.search(r'^version:\s*["\']?' + re.escape(contract['version']) +
                    r'["\']?\s*$', citation, re.M),
          'citation metadata uses integrated release version')
    check('date-released: ' + contract['date'] in citation,
          'citation metadata uses actual release date')

    pdf = ROOT / manuscript['pdf']
    reader = PdfReader(str(pdf))
    check(not reader.is_encrypted, 'readable manuscript PDF')
    check(len(reader.pages) > 0, 'nonempty manuscript PDF')
    texts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ''
        check(bool(text.strip()), 'extractable manuscript page ' + str(i + 1))
        check(float(page.mediabox.width) > 100 and float(page.mediabox.height) > 100,
              'valid manuscript page dimensions ' + str(i + 1))
        texts.append(text)
    build = json.loads((ROOT / manuscript['build_manifest']).read_text(encoding='utf-8-sig'))
    check(build['schema'] == 'scci_rh.stage6.manuscript-build.v1' and
          build['version'] == contract['version'] and build['date'] == contract['date'],
          'current manuscript build identity')
    check(build['release_contract_sha256_lf'] == sha(CONTRACT, True),
          'manuscript binds the release metadata used by its cover and footer')
    check(build['physical_qualification'] is False, 'manuscript is a digital artifact')
    check(build['source_path'] == manuscript['source'] and
          build['source_sha256_lf'] == sha(ROOT / manuscript['source'], True),
          'build binds exact editable manuscript source')
    check(build['builder_path'] == manuscript['builder'] and
          build['builder_sha256_lf'] == sha(ROOT / manuscript['builder'], True),
          'build binds actual PDF generator source')
    check(build['pdf_path'] == manuscript['pdf'] and
          build['pdf_sha256'] == sha(pdf) and build['pages'] == len(reader.pages),
          'build binds exact final PDF and page inventory')
    check(build['references_path'] == 'docs/stage6/references.json' and
          build['references_sha256_lf'] == sha(ROOT / build['references_path'], True),
          'build binds exact current primary-reference register')
    check(build['figure_generator_path'] == 'manuscript/stage6/build_figures.py' and
          build['figure_generator_sha256_lf'] == sha(ROOT / build['figure_generator_path'], True),
          'build binds actual source-derived figure generator')
    check(bool(build['figures']), 'build records actual figure inputs')
    for name, expected in build['figures'].items():
        check((ROOT / name).is_file() and sha(ROOT / name) == expected,
              'exact figure bytes used by PDF build: ' + name)
    review_path = ROOT / manuscript['document_review']
    review = json.loads(review_path.read_text(encoding='utf-8-sig'))
    check(review.get('passed') is True, 'final actual document review passed')
    check(review.get('pdf_sha256') == sha(pdf), 'review binds exact final PDF')
    check(review.get('pages_reviewed') == len(reader.pages), 'every final PDF page reviewed')
    check(review.get('visual_review_performed') is True, 'actual visual review distinguished from extraction')
    references = json.loads((ROOT / 'docs/stage6/references.json').read_text(encoding='utf-8-sig'))
    rows = references['references']
    expected_ids = {f'R{i:02}' for i in range(1, 19)}
    check(len(rows) == 18 and {row['id'] for row in rows} == expected_ids,
          'all 18 unique primary/inspiration reference identities')
    pdf_text = '\n'.join(texts)
    for row in rows:
        check(all(row.get(field) for field in ('title', 'url', 'cohort', 'access_and_signal',
                                               'supported_claim', 'not_established',
                                               'scci_rh_inference', 'verification_depth')),
              'evidence/inference/limitation fields: ' + row['id'])
        check(re.search(r'\b' + row['id'] + r'\b', pdf_text) is not None,
              'reference appears in final PDF: ' + row['id'])
    check(references['original_paper']['page_count'] == 28,
          'original starting paper remains distinct')
    original_pdf = ROOT / 'docs/stage6/original-hypothesis/SCCI_research_hypothesis_paper.pdf'
    check(sha(original_pdf) == references['original_paper']['sha256'],
          'archival original paper copy preserves exact read-only source bytes')
    check(len(PdfReader(str(original_pdf)).pages) == references['original_paper']['page_count'],
          'archival source contains the original 28 pages')
    with (ROOT / 'docs/stage6/evidence-claims.csv').open(newline='', encoding='utf-8-sig') as source:
        claims = list(csv.DictReader(source))
    check(bool(claims) and len({row['claim_id'] for row in claims}) == len(claims),
          'nonempty uniquely identified evidence/claim register')
    for row in claims:
        check(bool(row['claim'] and row['scope'] and row['limitation']),
              'each current evidence claim retains scope and limitation: ' + row['claim_id'])
        check(set(filter(None, row['source_ids'].split(';'))) <= expected_ids,
              'claim source identities: ' + row['claim_id'])
    with (ROOT / 'docs/stage1/requirements.csv').open(newline='', encoding='utf-8-sig') as source:
        original_requirements = {row['requirement_id'] for row in csv.DictReader(source)}
    with (ROOT / 'docs/stage6/requirements-claims-trace.csv').open(newline='', encoding='utf-8-sig') as source:
        trace = list(csv.DictReader(source))
    check(len(trace) == len(original_requirements) == 36 and
          {row['requirement_id'] for row in trace} == original_requirements,
          'all original 36 requirements receive an explicit final scoped disposition')
    for row in trace:
        check(bool(row['stage6_status'] and row['claim_and_limit']),
              'scoped requirement disposition: ' + row['requirement_id'])
        for name in row['evidence_paths'].split(';'):
            check((ROOT / name).is_file(), 'requirement evidence exists: ' + name)
    source_text = (ROOT / manuscript['source']).read_text(encoding='utf-8-sig')
    check(not re.search(r'\bTBD\b|__PLACEHOLDER__|\[INSERT ', source_text),
          'no unfinished manuscript placeholders')
    figures = {path.stem for path in (ROOT / 'manuscript/stage6/figures').glob('*')
               if path.suffix.lower() in ('.png', '.svg', '.pdf')}
    check(len(figures) >= 8, 'illustrated manuscript contains the declared engineering figures')

    s3 = json.loads((ROOT / 'provenance/stage3-conditional-concept-review.json').read_text())
    s4 = json.loads((ROOT / 'provenance/stage4-integrated-pcb-verification.json').read_text())
    s5 = json.loads((ROOT / 'provenance/stage5-mechanical-verification.json').read_text())
    check(s3['run_count'] == 128 and s3['practice_blocks'] == 3072,
          'conditional mechanism study scope preserved')
    check(s3['raw_human_data'] is False, 'synthetic mechanism evidence identified')
    check(s4['passed'] and s5['passed'], 'completed electrical and mechanical receipts')
    check(s4['totals']['electrical_positions'] == 1298 and
          s4['totals']['fitted_components'] == 1296, 'current populated reference identity')
    check(s4['master_sheets'] == 80 and s4['harness_rows'] == 258,
          'integrated hierarchy and harness preserved')
    check(s5['packages']['future']['physical_objects'] == 230,
          'conditional future package remains distinct')
    digital_path = ROOT / 'results/stage6/digital-path-verification.json'
    path_result = json.loads(digital_path.read_text(encoding='utf-8-sig'))
    integration = json.loads((ROOT / 'results/stage6/integration-summary.json').read_text(encoding='utf-8-sig'))
    check(path_result['passed'] and integration['passed'], 'integrated conditional software paths pass')
    check(path_result['baseline_commit'] == baseline, 'integration uses the preserved completed system')
    check(integration['source_report_sha256_lf'] == sha(digital_path, True),
          'summary binds exact detailed integration result')
    check(integration['assertions'] == path_result['assertions'], 'integration assertion identity')
    check(integration['protected_body_ports'] == 36, 'integration preserves body-port identity')
    for field in ('live_rhd_feedback_while_motor_implemented',
                  'target_peripheral_execution', 'physical_integrated_execution',
                  'biological_efficacy_demonstrated'):
        check(integration[field] is False, 'conditional integrated limitation: ' + field)
    for name, expected in path_result['source_sha256_lf'].items():
        check(sha(ROOT / name, True) == expected, 'current integrated source: ' + name)

    # The report excludes itself and the manifest. The eventual commit and
    # external release asset checksums are verified after publication, avoiding
    # a commit/hash cycle. All source files used to build the final PDF are bound.
    bound = {ROOT / name for name in required}
    bound.update(path for path in (ROOT / 'manuscript/stage6').rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts)
    bound.update(path for path in (ROOT / 'docs/stage6').rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts)
    bound.update(path for path in (ROOT / 'docs/explore').rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts)
    for directory in ('inspector', 'scripts/inspector'):
        bound.update(path for path in (ROOT / directory).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts)
    bound.update({ROOT / 'docs/README.md', ROOT / 'scripts/verify_viewer_navigation.py',
                  ROOT / 'scripts/build_reader_previews.py',
                  ROOT / '.github/workflows/deploy-inspector.yml',
                  ROOT / 'provenance/browser-inspector-verification.json',
                  ROOT / 'provenance/viewer-navigation-verification.json'})
    bound.update(path for path in (ROOT / 'docs/review-v2.0.1').rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts)
    bound.update(path for path in (ROOT / 'firmware/nrf5340/uart-revision').rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts)
    for directory in ('results/stage6', 'experiments/stage6', 'scripts/stage6'):
        bound.update(path for path in (ROOT / directory).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts)
    bound.add(Path(__file__))
    bound.add(ROOT/'scripts/project_branding.py')
    bound.discard(REPORT)
    bound.discard(ROOT / 'provenance/manifest.sha256')
    artifacts = {}
    for path in sorted(bound):
        name = path.relative_to(ROOT).as_posix()
        check(path.stat().st_size < 100 * 1024 * 1024, 'bound source size: ' + name)
        normalized = path.suffix.lower() in TEXT_SUFFIXES or path.name == 'LICENSE'
        artifacts[name] = {'sha256': sha(path, normalized),
                           'text_normalized': normalized}
    return {
        'schema': 'scci_rh.stage6.release-verification.v1', 'passed': True,
        'version': contract['version'], 'date': contract['date'],
        'scope': contract['scope'], 'checks': checks,
        'baseline': {'commit': baseline, 'historical_source_files': len(preserved),
                     'path_and_blob_sha256': preserved_digest,
                     'mutable_entries': sorted(mutable), 'authorized_brand_migration': migration},
        'manuscript': {'pages': len(reader.pages), 'pdf_sha256': sha(pdf),
                       'all_pages_visually_reviewed': True,
                       'primary_and_inspiration_references': len(rows),
                       'figure_stems': sorted(figures)},
        'local_entry_links': links,
        'external_links_recorded_not_live_revalidated_here': sorted(external_links),
        'preserved_scope': {'conditional_scenarios': s3['run_count'],
                            'fitted_components': s4['totals']['fitted_components'],
                            'master_sheets': s4['master_sheets'],
                            'mechanical_checks': s5['checks']},
        'new_conditional_software_integration': {
            'assertions': integration['assertions'],
            'motor_completed_events': integration['motor_completed_events'],
            'physiology_completed_events': integration['physiology']['completed_events'],
            'live_rhd_feedback_while_motor_implemented': False,
            'physical_or_biological_execution': False},
        'artifacts': artifacts, 'limitations': contract['limitations'],
        'post_commit_release_checks': [
            'Git blob manifest, remote branch and tag commit identities',
            'Clean independent checkout and actual GitHub workflow conclusions',
            'Full source archive member blobs and remote release asset digests'
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-report', action='store_true')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--index', action='store_true',
                        help='verify staged rather than committed artifact blobs before committing')
    args = parser.parse_args()
    result = audit()
    if args.write_report:
        REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n',
                          encoding='utf-8')
    else:
        previous = json.loads(REPORT.read_text(encoding='utf-8-sig'))
        if result != previous:
            fields = sorted(key for key in set(result) | set(previous)
                            if result.get(key) != previous.get(key))
            artifacts = sorted(key for key in set(result['artifacts']) | set(previous['artifacts'])
                               if result['artifacts'].get(key) != previous['artifacts'].get(key))
            raise AssertionError('Stage 6 changed after review; inspect before --write-report. '
                                 'Fields: ' + ', '.join(fields) +
                                 '; differing artifacts: ' + ', '.join(artifacts))
    summary = {key: result[key] for key in ('passed', 'version', 'checks', 'baseline', 'manuscript')}
    if not args.write_report:
        summary['bound_git_blobs_verified'] = inspect_bound_git_blobs(result['artifacts'], args.index)
    if args.archive:
        summary['archive'] = inspect_archive(args.archive.resolve())
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
