"""Finite zero-future baseline validation using actual completed dose records."""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from scci_rh.stage3.dynamic_response import (ResponsePosition, CompletedDose, FutureResponseFrame,
                                        response_model_from_record)
from scci_rh.stage3.sparse_baseline import (SparseBaselineSpec, fit_unassisted_baseline,
                                       validate_zero_future_recording)
from stage3_dynamic_response_study import capture, schedule
from run_stage3_studies import close_nested
from artifact_hashes import canonical_json_digest

INPUT = ROOT/'results/stage3/dynamic-response'
OUT = ROOT/'results/stage3/sparse-baseline'
SOURCES = ('src/scci_rh/stage3/sparse_baseline.py', 'src/scci_rh/stage3/dynamic_response.py',
    'src/scci_rh/stage3/cue_policy.py', 'src/scci_rh/stage3/motor.py', 'src/scci_rh/stage3/source_sensitivity.py',
    'src/scci_rh/stage3/electrical.py', 'scripts/stage3_dynamic_response_study.py',
    'scripts/stage3_sparse_baseline_study.py', 'scripts/artifact_hashes.py')


def source_hashes():
    return {p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for p in SOURCES}


def public_recording(saved):
    name = saved['recording_id']; generation = saved['generation']
    if name.startswith('moving_single') or name.startswith('moving_paired'):
        family = 'isolated_nominal'
    elif name == 'moving_sparse_paired': family = 'sparse_mixed_nominal'
    else: family = 'sparse_individual_nominal'
    if generation['subject_seed'] != 2:
        family = 'unvalidated_subject'
    return {'recording_id': name, 'measurement_noise_id': saved['recording_identity']['measurement_noise_id'],
        'measurements': [ResponsePosition(**p) for p in saved['measurements']],
        'observed_dose': [CompletedDose(**d) for d in saved['observed_dose']],
        'planned_frames': [FutureResponseFrame(**f) for f in saved['planned_frames']],
        'family': family, 'cadence_hz': generation['cadence_hz'], 'task_time_offset_s': 0.}


def experiment():
    identity = source_hashes()
    input_path = INPUT/'dynamic-response-summary.json'
    receipt = json.loads(input_path.read_text(encoding='utf-8'))
    input_binding = {'path': input_path.relative_to(ROOT).as_posix(),
                     'canonical_json_sha256': canonical_json_digest(input_path), 'raw_files': []}
    print('Capturing new12s unassisted measured baseline calibration', flush=True)
    calibration_raw = capture('zero_future_unassisted_calibration', 97000, .000625, seconds=12.,
                              plan=schedule(12., []))
    calibration = {'recording_id': calibration_raw['recording_id'], 'measurement_noise_id': 97000,
        'measurements': calibration_raw['measurements'], 'observed_dose': [],
        'planned_frames': calibration_raw['planned_frames'], 'cadence_hz': 1., 'task_time_offset_s': 0.}
    fitted = fit_unassisted_baseline(calibration)
    grids = {}
    for grid, study in receipt['grids'].items():
        path = INPUT/study['raw_file']['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != study['raw_file']['sha256']:
            raise AssertionError('Dynamic recording bytes differ')
        input_binding['raw_files'].append({'path': path.relative_to(ROOT).as_posix(), 'sha256': study['raw_file']['sha256']})
        raw = json.loads(gzip.decompress(path.read_bytes()))
        dynamic = response_model_from_record(study['model'])
        # The same frozen unassisted fit is independently combined with each
        # measured numerical-grid kernel; no fine body truth reaches inference.
        model = dict(fitted); model['context_validation'] = {}
        records = [public_recording(r) for r in raw['independent_validation']]
        first = raw['independent_validation'][0]
        records.insert(0, {'recording_id': 'independent_unassisted_nominal',
            'measurement_noise_id': first['recording_identity']['baseline_noise_id'],
            'measurements': [ResponsePosition(**p) for p in first['baseline_measurements']],
            'observed_dose': [], 'planned_frames': [FutureResponseFrame(f['frame_time_s'], (0, 0))
                                                   for f in first['planned_frames']],
            'family': 'unassisted_nominal', 'cadence_hz': 1., 'task_time_offset_s': 0.})
        # Paired derived fault: same independent measured-noise record, then an
        # unannounced sensor step. It is not another independent subject/draw.
        clean = records[0]
        records.append({**clean, 'recording_id': 'derived_unassisted_sensor_offset_control',
            'measurements': [replace(p, position_m=tuple(np.asarray(p.position_m)+[.04, -.04]))
                             if p.support_s >= 1.5 else p for p in clean['measurements']],
            'derived_negative_control': True})
        validations = []
        for recording in records:
            print(grid+': '+recording['recording_id'], flush=True)
            validations.append(validate_zero_future_recording(model, dynamic, recording))
        grids[grid] = {'dynamic_model_id': dynamic.model_id, 'model': model, 'validation': validations,
                      'input_recording_ids': [r['recording_id'] for r in records]}
    names = list(grids)
    comparison = []
    for a, b in zip(grids[names[0]]['validation'], grids[names[1]]['validation']):
        ca, cb = a['context'], b['context']
        comparison.append({'recording_id': ca['recording_id'], 'qualification_matches': ca['qualified'] == cb['qualified'],
            'horizon_qualification_matches': [h['qualified'] for h in ca['horizons']] == [h['qualified'] for h in cb['horizons']],
            'maximum_allocation_difference_m': max((abs(x['empirical_error_allocation_m']-y['empirical_error_allocation_m'])
                for x, y in zip(ca['horizons'], cb['horizons']) if x['empirical_error_allocation_m'] is not None
                and y['empirical_error_allocation_m'] is not None), default=0.)})
    if source_hashes() != identity: raise AssertionError('Source changed during zero-future study')
    return {'schema': 'scci_rh.stage3.sparse-baseline-study.v1', 'date': '2026-10-09', 'source_identity': identity,
        'qualification_scope_revision': {'date': '2026-10-12',
            'original_numerical_protocol_date': '2026-10-09',
            'change': 'bind qualified runtime calls to eligible5msphysical support and complete past action prefixes',
            'fit_prediction_error_thresholds_unchanged': True},
        'specification': asdict(SparseBaselineSpec()), 'dynamic_receipt_binding': input_binding,
        'new_calibration': {'recording_id': calibration['recording_id'], 'measurement_noise_id': 97000,
            'measurements': [asdict(p) for p in calibration['measurements']], 'seconds_used': 12.,
            'paired_generation_seconds_unused': 12., 'learning_enabled': False,
            'source': 'external-only dense moving-body reference; no neural source hold'},
        'grids': grids, 'numerical_comparison': comparison,
        'scope': {'coupled_practice': False, 'candidate_controller_qualified': False,
            'retained_learning_measured': False, 'actual_monitor_uncertainty_reduced': False,
            'future_candidate_in_baseline': False, 'past_tail_after600ms_qualified': False,
            'future_measurements_or_monitors_online': False, 'neural_used': False},
        'limitations': ['Only independently recorded, known-zero-future committed intervals are scored.',
            'Every unsupported old pulse remains an explicit rejection; no tail is truncated to earn a pass.',
            'Past dynamic uncertainty is propagated through both stripping and re-addition without cancellation.',
            'A restricted interval pass does not qualify a pre-action candidate, feedback controller or unseen family.',
            'Fresh one-action sessions need separate candidate/delivery/teacher/correction and delayed-residual gates.']}


def plain(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    raise TypeError(type(value).__name__)


def summary(result, path=None, sha=None):
    brief = {k: v for k, v in result.items() if k not in {'new_calibration', 'grids'}}
    brief['new_calibration'] = {k: v for k, v in result['new_calibration'].items() if k != 'measurements'}
    brief['grids'] = {}
    for name, grid in result['grids'].items():
        model = grid['model']; forecaster = model['forecaster']
        brief['grids'][name] = {'dynamic_model_id': grid['dynamic_model_id'],
            'model': {k: v for k, v in model.items() if k != 'forecaster'},
            'forecaster': {k: v for k, v in forecaster.items() if k != 'models'},
            'horizon_models': [{k: v for k, v in m.items() if k not in {'weights', 'mean', 'scale'}} for m in forecaster['models']],
            'validation': [v['context'] for v in grid['validation']]}
    if path: brief['raw_witness'] = {'path': path, 'sha256': sha}
    return brief


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path); parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.output and args.check: parser.error('Choose output or check')
    result = experiment()
    if args.check:
        close_nested(json.loads(json.dumps(result, default=plain)), json.loads(gzip.decompress(args.check.read_bytes())))
        close_nested(json.loads(json.dumps(summary(result, args.check.name, hashlib.sha256(args.check.read_bytes()).hexdigest()), default=plain)),
                     json.loads(args.check.with_name('summary.json').read_text(encoding='utf-8')))
        print('Zero-future restricted-interval raw and summary receipts reproduced')
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        with gzip.GzipFile(filename='', fileobj=buffer, mode='wb', mtime=0) as stream:
            stream.write((json.dumps(result, default=plain, separators=(',', ':'), allow_nan=False)+'\n').encode())
        args.output.write_bytes(buffer.getvalue())
        args.output.with_name('summary.json').write_text(json.dumps(summary(result, args.output.name,
            hashlib.sha256(args.output.read_bytes()).hexdigest()), default=plain, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print('Saved2grids of full-recording restricted zero-future interval validation')
    else: print(json.dumps({'grids': list(result['grids'])}))


if __name__ == '__main__': main()
