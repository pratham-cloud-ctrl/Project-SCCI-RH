"""Finalize reference inspection from explicit completed independent evidence.

The original independent inspector completed source/neutral-export comparisons
and wrote four successful bound phase files. Its later whole-compound distance
run did not complete. This driver preserves those actual phases, binds a
separately completed exact solid-pair clearance inspection, and freshly reopens
the saved native assembly for validity, coverage and material checks. It never
reconstructs a pass from console logs or changes a completed phase's source hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SHA256_LF = '8705686a8a2efde080c1ad67868afe926c82e8c95bdec127a1ed659d4b06f75b'
PHASES = ('native-specific', 'nominal-step', 'mechanical-step', 'exploded-step')


def sha(path, text=False):
    data = Path(path).read_bytes()
    return hashlib.sha256(data.replace(b'\r\n', b'\n') if text else data).hexdigest()


assert sha(ROOT/'scripts/inspect_stage5_native.py', True) == BACKEND_SHA256_LF, 'exact independent geometry backend'
import inspect_stage5_native as backend
App, Part = backend.App, backend.Part


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load_phases(package_path, package):
    source_paths = [ROOT/b[key] for b in package['boards'] for key in ('source_step', 'source_pcb')]
    inputs = [ROOT/package[key] for key in ('step', 'mechanical_step', 'exploded_step')] + source_paths
    bindings = dict(inspector_sha256_lf=BACKEND_SHA256_LF, FreeCAD_version=list(App.Version()),
                    contract_canonical_sha256=backend.canonical(package_path),
                    native_sha256=sha(ROOT/package['native']),
                    files={p.relative_to(ROOT).as_posix(): sha(p, p.suffix.lower()=='.kicad_pcb') for p in inputs})
    results, receipts = {}, []
    for phase in PHASES:
        path = ROOT/'provenance/stage5-reference-phases'/('reference-'+phase+'.json')
        completed = read(path)
        assert completed['completed'] is True and completed['bindings'] == bindings, ('completed phase/current inputs', phase)
        results[phase] = completed['result']
        receipts.append(dict(phase=phase, receipt=path.relative_to(ROOT).as_posix(), sha256=sha(path)))
    archive = ROOT/'provenance/stage5-inspector-sources'/(BACKEND_SHA256_LF+'.py.txt')
    assert sha(archive, True)==BACKEND_SHA256_LF, 'preserved actual executed phase inspector'
    return results, receipts, bindings, archive


def load_clearance(package_path, package):
    manifest_path = ROOT/'provenance/stage5-reference-clearance/manifest.json'
    manifest = read(manifest_path)
    assert manifest['schema']=='scci_rh.stage5.actual-clearance-probe.v1'
    bindings = manifest['bindings']
    assert bindings['native_sha256']==sha(ROOT/package['native'])
    assert bindings['contract_canonical_sha256']==backend.canonical(package_path)
    for entry in manifest['files'].values():
        path = ROOT/entry['path']
        assert path.stat().st_size==entry['bytes'] and sha(path)==entry['sha256'], ('actual completed clearance evidence', path)
        if 'sha256_lf' in entry:
            assert sha(path, True)==entry['sha256_lf']
    result_path = ROOT/manifest['files']['raw_results']['path']
    result = read(result_path)
    assert result['all_passed'] is True
    assert result['native_sha256']==bindings['native_sha256']
    assert result['contract_canonical_sha256']==bindings['contract_canonical_sha256']
    assert len(result['rows'])==len(package['clearance_checks'])==14
    for actual, expected in zip(result['rows'], package['clearance_checks']):
        assert all(actual[k]==expected[k] for k in ('a', 'b', 'minimum_mm', 'reason')), 'exact declared clearance query'
        assert actual['passed'] and actual['measured_mm']>=expected['minimum_mm']-2e-5
        assert actual['exact_BRep_queries']+actual['AABB_pruned_pairs']==actual['solid_pair_count'], 'all constituent pairs covered'
    return manifest_path, manifest, result, result_path


def solid_coverage(shape):
    leaves = []
    def visit(item):
        if item.ShapeType=='Solid':
            leaves.append(item)
            return
        children = item.childShapes()
        assert children, ('non-solid native leaf excluded from distance query', item.ShapeType)
        for child in children:
            visit(child)
    visit(shape)
    assert len(leaves)==len(shape.Solids), 'complete constituent-solid coverage'
    return len(leaves)


def inspect():
    root_contract = read(ROOT/'cad/stage5/assembly-contract.json')
    package_path = ROOT/root_contract['reference']['contract']
    package = read(package_path)
    phases, phase_receipts, original_bindings, archive = load_phases(package_path, package)
    manifest_path, manifest, clearance, result_path = load_clearance(package_path, package)
    native_path, step_path = ROOT/package['native'], ROOT/package['step']
    native = App.openDocument(str(native_path))
    try:
        all_features = backend.physical_features(native)
        labels = [p['label'] for p in package['parts']]
        assert len(labels)==len(set(labels))==170 and set(labels)<=set(all_features)
        features = {label: all_features[label] for label in labels}
        parts = []
        for row in package['parts']:
            shape = features[row['label']].Shape
            assert shape.isValid() and shape.Volume>0 and all(s.isValid() and s.Volume>0 for s in shape.Solids)
            parts.append(dict(label=row['label'], category=row['category'], **backend.shape_metrics(shape)))
        coverage = []
        used = sorted({row[k] for row in package['clearance_checks'] for k in ('a', 'b')})
        for label in used:
            count = solid_coverage(features[label].Shape)
            coverage.append(dict(label=label, covered_solids=count, native_solids=count, non_solid_leaves=[]))
        old_coverage = read(ROOT/manifest['files']['raw_topology']['path'])
        assert sorted(coverage, key=lambda r:r['label'])==sorted(old_coverage, key=lambda r:r['label']), 'fresh native coverage agrees with actual completed query'
        # A fresh exact query on every recorded nearest solid pair witnesses the
        # reported value. The completed source/results retain proof of the full
        # pair search, including the remaining exact tests and AABB pruning.
        clearances = []
        for row in clearance['rows']:
            left, right = features[row['a']].Shape.Solids, features[row['b']].Shape.Solids
            assert len(left)*len(right)==row['solid_pair_count']
            i, j = row['minimum_solid_pair']
            measured = left[i].distToShape(right[j])[0]
            assert abs(measured-row['measured_mm'])<=2e-5 and measured>=row['minimum_mm']-2e-5
            clearances.append(dict(a=row['a'], b=row['b'], minimum_mm=row['minimum_mm'],
                                   measured_mm=row['measured_mm'], freshly_measured_minimum_pair_mm=measured,
                                   exact_BRep_queries=row['exact_BRep_queries'],
                                   AABB_pruned_pairs=row['AABB_pruned_pairs'], solid_pair_count=row['solid_pair_count']))
            backend.log('Exact clearance witness '+row['a']+' / '+row['b']+': '+str(measured)+' mm')
        backend.log('Fresh reference material-interference pass')
        interference = backend.check_interference(features, labels, package['allowed_intersections'])
        step_evidence = backend.step_binding(step_path)
        assert step_evidence['uncompressed_sha256']==package['step_sha256_uncompressed']
        assert step_evidence['member']==package['step_member']
        extra_exports = {
            'mechanical_step': dict(**backend.step_binding(ROOT/package['mechanical_step']), **phases['mechanical-step']),
            'exploded_step': dict(**backend.step_binding(ROOT/package['exploded_step']), **phases['exploded-step'])}
        assert extra_exports['exploded_step']['uncompressed_sha256']==package['exploded_step_sha256_uncompressed']
        geometry = dict(contract=package_path.relative_to(ROOT).as_posix(),
                        contract_canonical_sha256=backend.canonical(package_path),
                        native=package['native'], native_sha256=sha(native_path),
                        step=package['step'], step_sha256=sha(step_path),
                        parts=parts, final_objects=len(parts), physical_objects=len(parts),
                        step_comparison=phases['nominal-step'], step_evidence=step_evidence,
                        extra_exports=extra_exports, interference=interference,
                        clearances=clearances, fresh_solid_coverage=coverage, physical_qualification=False,
                        **phases['native-specific'])
        # Recheck all source/export/native bindings after the fresh operations.
        assert load_phases(package_path, package)[2]==original_bindings
        return dict(schema='scci_rh.stage5.independent-native-inspection.v1',
                    scope='Nominal digital geometry; no fabrication, anatomy, hermetic or thermal qualification',
                    inspector='scripts/inspect_stage5_reference.py', inspector_sha256_lf=sha(Path(__file__), True),
                    FreeCAD_version=list(App.Version()), packages={'reference':geometry}, passed=True,
                    evidence_reuse=dict(
                        method='Four actual successful independent source/export phases plus separately completed exact solid-pair clearance inspection; fresh native validity, full solid coverage, each nearest-pair witness and all material pairs',
                        backend=dict(path='scripts/inspect_stage5_native.py', sha256_lf=BACKEND_SHA256_LF,
                                     archived_source=archive.relative_to(ROOT).as_posix()),
                        completed_phases=phase_receipts,
                        clearance=dict(manifest=manifest_path.relative_to(ROOT).as_posix(), manifest_sha256=sha(manifest_path),
                                       result_path=result_path.relative_to(ROOT).as_posix(), result_sha256=sha(result_path))))
    finally:
        App.closeDocument(native.Name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-receipt', action='store_true')
    arguments = parser.parse_args()
    report = inspect()
    if arguments.write_receipt:
        destination = ROOT/'provenance/stage5-native-reference.json'
        destination.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__=='__main__':
    main()
