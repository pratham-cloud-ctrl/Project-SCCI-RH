"""Reproduce the bounded, reset-trial, actual-body-coupled motor pilot."""
from __future__ import annotations
import argparse
from dataclasses import asdict, is_dataclass
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3 import motor
from scci_rh.stage3.dynamic_response import ProspectiveDose, response_model_from_record
from scci_rh.stage3.isolated_pilot import (ARMS, ACTION_DOMAINS, PILOT_CONTEXT_ID, IsolatedPilotSpec, config,
    generate_unassisted, aggregate_context, run_trial, reference_from_library)
from scci_rh.stage3.sparse_baseline import fit_unassisted_baseline, validate_zero_future_recording
from artifact_hashes import canonical_json_digest
from run_stage3_studies import close_nested

OUT = ROOT/'results/stage3/isolated-pilot'
SPEC = IsolatedPilotSpec()
SOURCE_PATHS = ('src/scci_rh/stage3/isolated_pilot.py', 'scripts/stage3_isolated_pilot_study.py',
    'src/scci_rh/stage3/motor.py', 'src/scci_rh/stage3/electrical.py',
    'src/scci_rh/stage3/dynamic_response.py', 'src/scci_rh/stage3/sparse_baseline.py',
    'src/scci_rh/stage3/cue_policy.py', 'src/scci_rh/stage3/assisted_prediction.py',
    'src/scci_rh/stage3/residual_guard.py', 'src/scci_rh/stage3/teacher_library.py', 'scripts/artifact_hashes.py')
INPUTS = ('results/stage3/dynamic-response/dynamic-response-summary.json',
          'results/stage3/resolved-teacher/summary.json')


def plain(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if is_dataclass(value): return asdict(value)
    raise TypeError(type(value).__name__)


def source_hashes():
    return {path: hashlib.sha256((ROOT/path).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for path in SOURCE_PATHS}


def load_inputs():
    data = [json.loads((ROOT/path).read_text(encoding='utf-8')) for path in INPUTS]
    dynamic, teacher = data
    for receipt, key in ((dynamic, 'source_sha256'), (teacher, 'source_identity')):
        for path, expected in receipt[key].items():
            actual = hashlib.sha256((ROOT/path).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            if actual != expected: raise ValueError('Stale input source: '+path)
    grid = dynamic['grids']['2500us']
    raw_path = ROOT/'results/stage3/dynamic-response'/grid['raw_file']['path']
    raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if raw_sha != grid['raw_file']['sha256']: raise ValueError('Dynamic raw receipt mismatch')
    model = response_model_from_record(grid['model'])
    library = teacher['libraries']['idealized_inverse']
    references = {arm: reference_from_library(library, kind)
                  for arm, kind in (('observe_only', 'learner_only'), ('learner_goal', 'learner_only'),
                                    ('expert_external', 'expert_external'), ('expert_neural', 'expert_neural'))}
    if not all(reference.qualified for reference in references.values()):
        raise ValueError('Frozen nominal observed teacher reference is unqualified')
    branches, domains = {}, {}
    for branch in ('actual_electrical_trace_domain', 'nominal_future_assumption'):
        branches[branch] = ProspectiveDose(**grid['prospective_branches'][branch])
        domains[branch] = {}
        for name in ACTION_DOMAINS.values():
            if name is None: continue
            validation = grid['independent_validation'][name][branch]
            trace = validation['trace']
            target_index = next(i for i, t in enumerate(trace['physical_support_s']) if abs(t-SPEC.target_s) < 1e-10)
            # Empirical response residual + its existing 3 mm paired-label
            # allowance. The gain/dose term is added by the live policy once.
            residual = (np.asarray(trace['empirical_error_allocation_m'][target_index])
                        -np.asarray(trace['joint_gain_dose_error_m'][target_index]))
            domains[branch][name] = {'qualified': validation['qualified'],
                'dynamic_model_id': model.model_id,
                'target_support_s': SPEC.target_s, 'launch_s': SPEC.launch_s,
                'target_residual_allocation_m': residual.tolist(),
                'full_trajectory_maximum_allocation_m': validation['maximum_empirical_error_allocation_m'],
                'independent_recording_id': validation['recording_id'],
                'residual_scope': 'exact independently measured nominal-cue target phase; includes 3 mm label allowance'}
    inputs = {'canonical_json_sha256': {path: canonical_json_digest(ROOT/path) for path in INPUTS},
        'dynamic_raw': {'path': raw_path.relative_to(ROOT).as_posix(), 'sha256': raw_sha},
        'dynamic_model_id': model.model_id, 'teacher_library_id': library['library_id'],
        'teacher_generator': library['generator'], 'teacher_resource_accounting': library['resource_accounting'],
        'input_json_hash_scope': 'parsed JSON, sorted keys and finite values; independent of line endings'}
    return model, references, branches, domains, inputs


def pilot_experiment():
    identity = source_hashes()
    dynamic, references, branches, domains, bindings = load_inputs()
    training, training_raw = generate_unassisted('isolated_pilot_12s_unassisted_calibration', 87001,
                                                seconds=12., learning=False)
    baseline = fit_unassisted_baseline(training)
    validations, captures = [], []
    for family_index, family in enumerate(motor.FAMILIES):
        for scale_index, scale in enumerate(SPEC.coefficient_validation_scales):
            name = f'pilot_withheld_{family}_scale{scale:g}'
            print('Independent observed context: '+name, flush=True)
            observed, raw = generate_unassisted(name, 88000+family_index*100+scale_index,
                seconds=3., family=family, theta_scale=scale, learning=True)
            validation = validate_zero_future_recording(baseline, dynamic, observed)
            validations.append(validation); captures.append(raw)
    context_id = PILOT_CONTEXT_ID
    aggregate = aggregate_context(validations, context_id=context_id, dynamic_model_id=dynamic.model_id)
    baseline['context_validation'][context_id] = aggregate
    print('Whole observed context qualified: '+str(aggregate['qualified']), flush=True)
    # This initial coefficient exists only in the private simulator wrapper.
    initial = motor._World(SPEC.subject_seed, config()).theta.copy()
    runs = []
    for branch, dose in branches.items():
        for family_index, family in enumerate(motor.FAMILIES):
            for arm in ARMS:
                print('Coupled trials: '+branch+' / '+family+' / '+arm, flush=True)
                theta = initial.copy(); practice = []
                for trial in range(SPEC.practice_trials):
                    result, theta = run_trial(theta=theta, family=family, arm=arm,
                        noise_seed=90000+family_index*100+trial, baseline_model=baseline,
                        dynamic_model=dynamic, context_id=context_id, independent_domains=domains[branch],
                        reference=references[arm], prospective_dose=dose, learning=True)
                    result['trial_index'] = trial; practice.append(result)
                retained_theta = theta*(1-config().forgetting_fraction)
                assessments = {}
                for label, heldout in (('retention_off', False), ('transfer_off', True)):
                    result, _ = run_trial(theta=retained_theta, family=family, arm=arm,
                        noise_seed=95000+family_index*100+(1 if heldout else 0), baseline_model=baseline,
                        dynamic_model=dynamic, context_id=context_id, independent_domains=domains[branch],
                        reference=references[arm], prospective_dose=dose, learning=False, heldout=heldout)
                    assessments[label] = result
                runs.append({'id': branch+'__'+family+'__'+arm, 'branch': branch, 'family': family, 'arm': arm,
                    'prospective_dose': asdict(dose), 'practice': practice, 'assessments': assessments,
                    'private_evaluator_only': {'theta_after_practice_m': theta.tolist(),
                                               'theta_after_declared_forgetting_m': retained_theta.tolist()},
                    'qualification': 'UNQUALIFIED_CONDITIONAL_DIGITAL_PILOT',
                    'learner_sensing': 'external-only fallback', 'teacher_reference': asdict(references[arm])})
    if source_hashes() != identity: raise ValueError('Pilot source changed during generation')
    _, _, _, _, final_bindings = load_inputs()
    if final_bindings != bindings: raise ValueError('Frozen input changed during generation')
    return {'schema': 'scci_rh.stage3.isolated-pilot.v1', 'date': '2026-10-12',
        'source_sha256': identity, 'inputs': bindings, 'specification': asdict(SPEC), 'body_config': asdict(config()),
        'baseline': {'model': baseline, 'training_recording': training_raw, 'withheld_captures': captures,
            'independent_validation': validations, 'runtime_observed_context': aggregate},
        'dynamic_domains': domains, 'runs': runs,
        'scope': 'actual model delivery into a private digital body; conditional one-frame reset-session experiment, not human efficacy',
        'no_live_learner_neural_increment_claim': True, 'no_skill_transfer_or_multiplier_claim': True,
        'reset_premise': 'unbounded physical washout time is assumed between 3 s trials; positions/activation/delay reset, learned coefficients carry',
        'resource_accounting': {'new_unassisted_calibration_s': 12., 'new_withheld_unassisted_validation_s': 48.,
            'practice_s_per_arm_and_family_and_branch': 12., 'off_assessment_s_each': 3.,
            'validation_drift_scales': list(SPEC.coefficient_validation_scales),
            'equal_learner_noise_and_initial_coefficients_across_arms': True,
            'expert_library_equal_available_to_all_arms': True, 'unused_expert_resources_explicit': ['observe_only', 'learner_goal'],
            'new_neural_acquisition_seconds': 0., 'new_dynamic_calibration_seconds': 0.,
            'inherited_dynamic_calibration_and_validation': bindings['dynamic_raw']}}


def compact_summary(raw, *, raw_name, raw_sha):
    runs = []
    for run in raw['runs']:
        reference = next(r for r in raw['runs'] if r['branch'] == run['branch'] and r['family'] == run['family']
                         and r['arm'] == 'observe_only')
        practice = run['practice']
        rows = {'id': run['id'], 'branch': run['branch'], 'family': run['family'], 'arm': run['arm'],
            'qualification': run['qualification'], 'prospective_dose': run['prospective_dose'],
            'practice_launched_frames': sum(r['launched_frames'] for r in practice),
            'practice_launched_profiles': sum(r['launched_profiles'] for r in practice),
            'decision_reasons': [r['decision']['reason'] for r in practice],
            'continuation_stops': [r['continuation_stop_reason'] for r in practice],
            'actual_monitor_assumption_mismatches': sum(m['prospective_interval_not_confirmed'] for r in practice
                                                        for m in r['actual_monitor_records']),
            'observed_forecast_targets_scored': sum(len(r['residual_checks']) for r in practice),
            'observed_forecast_targets_failed': sum(not c['passed'] for r in practice for c in r['residual_checks'])}
        for label in ('retention_off', 'transfer_off'):
            assessment = run['assessments'][label]
            rows[label] = assessment['metrics']
            rows[label+'_profiles'] = assessment['launched_profiles']
            rows[label+'_trajectory_rmse_difference_vs_observe_m'] = (
                assessment['metrics']['trajectory_rmse_m']-reference['assessments'][label]['metrics']['trajectory_rmse_m'])
        runs.append(rows)
    return {'schema': 'scci_rh.stage3.isolated-pilot-summary.v1', 'date': raw['date'],
        'source_sha256': raw['source_sha256'],
        'inputs': raw['inputs'], 'specification': raw['specification'], 'scope': raw['scope'],
        'raw': {'path': raw_name, 'sha256': raw_sha, 'hash_scope': 'exact deterministic gzip bytes'},
        'runtime_context': raw['baseline']['runtime_observed_context'],
        'individual_observed_contexts': [v['context'] for v in raw['baseline']['independent_validation']],
        'dynamic_domains': raw['dynamic_domains'], 'runs': runs, 'resource_accounting': raw['resource_accounting'],
        'total_practice_launched_frames': sum(r['practice_launched_frames'] for r in runs),
        'total_practice_launched_profiles': sum(r['practice_launched_profiles'] for r in runs),
        'total_actual_monitor_assumption_mismatches': sum(r['actual_monitor_assumption_mismatches'] for r in runs),
        'total_off_launched_profiles': sum(r[label+'_profiles'] for r in runs for label in ('retention_off', 'transfer_off')),
        'reference_allocations': {run['arm']: run['teacher_reference'] for run in raw['runs']
                                 if run['branch'] == 'actual_electrical_trace_domain' and run['family'] == 'favorable'},
        'assisted_retained_advantage_established': False,
        'no_live_learner_neural_increment_claim': True, 'no_skill_transfer_or_multiplier_claim': True,
        'stage3_complete': False, 'reset_premise': raw['reset_premise']}


def encoded(raw):
    output = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as stream:
        stream.write(json.dumps(raw, default=plain, allow_nan=False, separators=(',', ':')).encode())
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', type=Path, help='Reproduce and compare this saved raw gzip')
    parser.add_argument('--output', type=Path, default=OUT/'raw.json.gz')
    args = parser.parse_args()
    result = pilot_experiment()
    if args.check:
        saved = json.loads(gzip.decompress(args.check.read_bytes()))
        close_nested(json.loads(json.dumps(result, default=plain)), saved)
        sha = hashlib.sha256(args.check.read_bytes()).hexdigest()
        close_nested(compact_summary(saved, raw_name=args.check.name, raw_sha=sha),
                     json.loads(args.check.with_name('summary.json').read_text(encoding='utf-8')))
        print('Isolated pilot raw and summary reproduced', flush=True)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        data = encoded(result); args.output.write_bytes(data)
        summary = compact_summary(json.loads(json.dumps(result, default=plain)), raw_name=args.output.name,
                                  raw_sha=hashlib.sha256(data).hexdigest())
        args.output.with_name('summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print('Saved '+str(args.output), flush=True)


if __name__ == '__main__': main()
