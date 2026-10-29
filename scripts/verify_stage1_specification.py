"""Check Stage 1 register coverage and artifact links, without efficacy claims."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
from urllib.parse import unquote
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / 'docs' / 'stage1'
REQUIRED = {
    'requirements.csv': ('requirement_id', 'requirement', 'owner', 'planned_stage', 'verification_id', 'status'),
    'assumptions.csv': ('assumption_id', 'type', 'premise', 'where_needed', 'failure_consequence', 'how_to_investigate', 'status'),
    'capability-map.csv': ('capability_id', 'family', 'consumer_or_medical_example', 'observable', 'proposed_influence', 'additional_premise', 'evidence_boundary', 'stage1_disposition'),
    'source-audit.csv': ('source_id', 'primary_url', 'title', 'publication_year', 'access_date', 'directly_supported', 'not_established', 'scope_notes'),
    'verification-matrix.csv': ('verification_id', 'objective', 'method', 'pass_criterion', 'evidence_type', 'stage', 'limitation'),
}


def verify(creating_receipt=False):
    records = {}
    checks = []
    for name, fields in REQUIRED.items():
        with (DOSSIER / name).open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            assert tuple(reader.fieldnames) == fields, (name, reader.fieldnames)
            rows = list(reader)
        assert rows, name
        ids = [row[fields[0]] for row in rows]
        assert len(ids) == len(set(ids)), f'Duplicate IDs: {name}'
        assert all(row.keys() == set(fields) and all(str(row[f]).strip() for f in fields)
                   for row in rows), f'Incomplete or malformed row: {name}'
        records[name] = rows
        checks.append(f'{name}: schema, nonempty fields and unique IDs')

    assert len(records['requirements.csv']) == 36
    assert len(records['assumptions.csv']) == 14
    assert len(records['capability-map.csv']) == 14
    assert len(records['verification-matrix.csv']) == 50
    verification_ids = {row['verification_id'] for row in records['verification-matrix.csv']}
    for row in records['requirements.csv']:
        assert set(row['verification_id'].split(';')) <= verification_ids, row['requirement_id']
        assert row['status'] in {'specified', 'pending'}, row['requirement_id']
    checks.append('All 36 requirements map to existing planned verification IDs')

    for row in records['source-audit.csv']:
        assert row['primary_url'].startswith('https://'), row['source_id']
        assert re.fullmatch(r'\d{4}', row['publication_year']), row['source_id']
        assert row['access_date'] == '2026-10-08', row['source_id']
    checks.append('Primary-source rows carry HTTPS URLs, years and Stage 1 audit date')

    link_count = 0
    source_ids = {row['source_id'] for row in records['source-audit.csv']}
    for doc in DOSSIER.glob('*.md'):
        content = doc.read_text(encoding='utf-8')
        assert set(re.findall(r'S1-REF-\d+', content)) <= source_ids, f'Unknown source ID: {doc.name}'
        assert content.count('```') % 2 == 0, f'Unbalanced fence: {doc.name}'
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', content):
            target = target.strip('<>')
            if target.startswith(('https://', 'http://', '#', 'mailto:')):
                continue
            path = unquote(target.split('#')[0])
            resolved = (doc.parent / path).resolve()
            receipt = (ROOT / 'provenance' / 'stage1-verification.json').resolve()
            assert resolved.exists() or (creating_receipt and resolved == receipt), f'Broken link: {doc.name}: {target}'
            link_count += 1
    checks.append(f'{link_count} local dossier links resolve; Markdown fences balance')
    checks.append('All primary-source IDs cited in dossier Markdown exist in the source audit')

    architecture = (DOSSIER / 'architecture-and-interfaces.md').read_text(encoding='utf-8')
    for prefix, count in [('ARCH', 4), ('MOD', 13), ('IF', 15)]:
        definitions = re.findall(r'\| \*\*(S1-' + prefix + r'-\d+)\*\* \|', architecture)
        assert len(definitions) == count and len(set(definitions)) == count, (prefix, definitions)
    checks.append('Four access alternatives, thirteen modules and fifteen interfaces are defined uniquely')

    pdf = ROOT / 'output' / 'pdf' / 'SCCI_RH_stage1_system_specification.pdf'
    pages = PdfReader(pdf).pages
    assert len(pages) == 9
    for index, page in enumerate(pages, 1):
        text = page.extract_text()
        assert len(text.strip()) > 350, f'Empty/short page {index}'
        assert f'{index} / 9' in text, f'Missing footer {index}'
        assert '\ufffd' not in text, f'Replacement glyph page {index}'
    for name in ['full-system', 'expert-learning', 'physiological-control']:
        assert (DOSSIER / 'figures' / f'{name}.png').stat().st_size > 10000
        assert '<svg' in (DOSSIER / 'figures' / f'{name}.svg').read_text(encoding='utf-8')
    checks.append('Nine PDF pages carry text and expected numbering; three SVG/PNG pairs exist')

    review = json.loads((ROOT / 'provenance' / 'stage1-review.json').read_text(encoding='utf-8'))
    assert review['pdf_visual_review']['sha256'] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert review['pdf_visual_review']['page_count'] == len(pages)
    assert review['source_reference']['page_count'] == 28
    assert len(review['source_reference']['sha256']) == 64
    checks.append('Manual visual-review record matches this PDF; original reference identity records 28 pages')

    return {
        'audit_date': '2026-10-08',
        'scope': 'Stage 1 specification consistency only; no efficacy, circuit or CAD validation',
        'counts': {name: len(rows) for name, rows in records.items()},
        'automated_checks': checks,
        'pdf_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
        'future_verification': 'Pending; the matrix defines later digital work and separate biological evidence requirements',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-receipt', action='store_true')
    args = parser.parse_args()
    result = verify(creating_receipt=args.write_receipt)
    if args.write_receipt:
        (ROOT / 'provenance' / 'stage1-verification.json').write_text(
            json.dumps(result, indent=2) + '\n', encoding='utf-8')
        assert verify() == result, 'The completed receipt must resolve like every other dossier link'
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
