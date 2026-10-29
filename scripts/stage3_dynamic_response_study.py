"""Identify actual monitored whole-frame transient responses without neural fitting."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3 import source_sensitivity, motor
from scci_rh.stage3.electrical import MotorDelivery
from scci_rh.stage3.dynamic_response import (DynamicResponseSpec, ResponsePosition, CompletedDose,
    FutureResponseFrame, ProspectiveDose, fit_response_kernel, validate_response_recording,
    predict_future_effect)
from run_stage3_studies import close_nested
from artifact_hashes import canonical_json_digest

SPEC = DynamicResponseSpec()
OUT = ROOT/'results/stage3/dynamic-response'
DOC = ROOT/'docs/stage3/dynamic-response.md'
SOURCE_PATHS = ('src/scci_rh/stage3/dynamic_response.py', 'scripts/stage3_dynamic_response_study.py',
                'src/scci_rh/stage3/source_sensitivity.py', 'src/scci_rh/stage3/motor.py',
                'src/scci_rh/stage3/electrical.py')
GRIDS = (.0025, .000625)
SUBJECT = 2


def source_hashes():
    return {path: hashlib.sha256((ROOT/path).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for path in SOURCE_PATHS}


def schedule(seconds, events):
    table = {round(time/SPEC.frame_s): tuple(routes) for time, routes in events}
    if len(table) != len(events): raise ValueError('Duplicate scheduled frame')
    for time, routes in events:
        if abs(time/SPEC.frame_s-round(time/SPEC.frame_s)) > 1e-8 or any(r not in (-1, 0, 1) for r in routes):
            raise ValueError('Complete fixed frame required')
    return tuple(FutureResponseFrame(frame*SPEC.frame_s, table.get(frame, (0, 0)))
                 for frame in range(round(seconds/SPEC.frame_s)))


def capture(recording_id, noise_seed, maximum_step_s, *, seconds, plan, rest=False,
            subject_seed=SUBJECT, cadence_hz=1., unmatched_baseline=False, sensor_offset=False):
    """Private generator only; observed_view excludes all evaluator fields."""
    config = motor.MotorConfig()
    adapter = MotorDelivery()
    adapter.begin_session()
    observed, witnesses, private_frames = [], [], []
    for frame in plan:
        truth = np.zeros(2)
        for route, sign in enumerate(frame.signed_routes):
            if not sign: continue
            true, _, monitor, witness = motor._pulse(frame.frame_time_s, route, sign, adapter, config)
            truth[route] = true
            observed.append(CompletedDose(frame.frame_time_s,
                frame.frame_time_s+SPEC.complete_profile_s, route, sign,
                monitor['delivered_phase_charge_C']/(config.nominal_current_A*config.phase_s),
                monitor['charge_uncertainty_C']/(config.nominal_current_A*config.phase_s), monitor['quality']))
            witnesses.append(witness)
        private_frames.append({'time_s': frame.frame_time_s, 'signed_true_reference_dose': truth.tolist(),
                               'whole_fixed_profile_admitted': bool(any(frame.signed_routes))})
    zero_frames = [{'time_s': frame.frame_time_s, 'signed_true_reference_dose': [0., 0.],
                    'whole_fixed_profile_admitted': False} for frame in plan]
    kwargs = {'maximum_step_s': maximum_step_s, 'seconds': seconds, 'onset_s': .035,
              'cadence_hz': cadence_hz, 'learning': False, 'theta_m': np.zeros((2, 4)) if rest else None}
    with patch.object(source_sensitivity, 'commands', return_value=private_frames):
        stimulated = source_sensitivity.MovingBodyReference(subject_seed, 'moving_clean', **kwargs)
    with patch.object(source_sensitivity, 'commands', return_value=zero_frames):
        baseline = source_sensitivity.MovingBodyReference(subject_seed, 'moving_clean',
            **{**kwargs, 'cadence_hz': 1.15 if unmatched_baseline else cadence_hz})
    times = np.arange(round(seconds/SPEC.sample_s))*SPEC.sample_s
    position, _, _ = stimulated.evaluate(times)
    base_position, _, _ = baseline.evaluate(times)
    observed_position = position+np.random.default_rng(noise_seed).normal(0., .0015, position.shape)
    observed_baseline = base_position+np.random.default_rng(noise_seed+800000).normal(0., .0015, base_position.shape)
    if sensor_offset: observed_position[times >= 1.5] += [.04, -.04]
    records = [ResponsePosition(float(t), float(t+.025), tuple(p)) for t, p in zip(times, observed_position)]
    baseline_records = [ResponsePosition(float(t), float(t+.025), tuple(p)) for t, p in zip(times, observed_baseline)]
    return {'recording_id': recording_id,
            'recording_identity': {'measurement_noise_id': noise_seed, 'baseline_noise_id': noise_seed+800000},
            'measurements': records,
            'baseline_measurements': baseline_records, 'observed_dose': observed,
            'planned_frames': plan,
            'generation': {'subject_seed': subject_seed, 'observation_noise_seed': noise_seed,
                'baseline_observation_noise_seed': noise_seed+800000,
                'seconds_each_arm': seconds, 'maximum_internal_step_s': maximum_step_s,
                'onset_s': .035, 'original_body_constants': True, 'learning': False,
                'cadence_hz': cadence_hz, 'rest': rest, 'unmatched_baseline': unmatched_baseline,
                'unannounced_sensor_offset': sensor_offset, 'neural_capture': False,
                'source_scope': 'external-only exact dense moving-body physical support; no held neural sources'},
            'private_evaluator_only': {'position_m': position.tolist(), 'baseline_position_m': base_position.tolist(),
                'pulse_witnesses': witnesses, 'rhs_evaluations': stimulated.rhs_evaluations+baseline.rhs_evaluations,
                'scope': 'true electrical dose drives private body; no private fields enter fit or prospective predictor'}}


def serialize(recording):
    return {**recording, **{key: [asdict(value) for value in recording[key]]
                           for key in ('measurements', 'baseline_measurements', 'observed_dose', 'planned_frames')}}


def write_gzip(path, value, check):
    if check:
        close_nested(without_local_diagnostics(value), without_local_diagnostics(
            json.loads(gzip.decompress(path.read_bytes()).decode('utf-8'))))
        return
    output = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as file:
        file.write(json.dumps(value, separators=(',', ':'), allow_nan=False).encode())
    path.write_bytes(output.getvalue())


def without_local_diagnostics(value):
    if isinstance(value, dict):
        return {key: without_local_diagnostics(item) for key, item in value.items() if key != 'rhs_evaluations'}
    if isinstance(value, (tuple, list)):
        return [without_local_diagnostics(item) for item in value]
    return value


def protocol_id(source_identity, grid, training):
    protocol = {'source_sha256': source_identity, 'specification': asdict(SPEC), 'grid_s': grid,
                'recordings': [{'recording_id': r['recording_id'], 'recording_identity': r['recording_identity'],
                    'planned_frames': [asdict(f) for f in r['planned_frames']]} for r in training]}
    digest = hashlib.sha256(json.dumps(protocol, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return 'SCCI_RH-S3-DYNAMIC-1:'+digest[:20]


def validation_cases():
    cases = []
    for route, sign in ((0, 1), (0, -1), (1, 1), (1, -1)):
        routes = [0, 0]; routes[route] = sign
        cases.append((f'moving_single_{route}_{sign}', 3., [(1., tuple(routes))], {}))
    cases += [('moving_paired_same', 3., [(1., (1, 1))], {}),
              ('moving_paired_opposite', 3., [(1., (1, -1))], {})]
    sparse = [(float(time), ((1, 0), (0, 1), (-1, 0), (0, -1))[i%4])
              for i, time in enumerate(np.arange(.6, 5.401, .2))]
    paired = [(float(time), ((1, 1), (1, -1), (-1, 1), (-1, -1))[i%4])
              for i, time in enumerate(np.arange(.6, 5.401, .2))]
    cases += [('moving_sparse', 6., sparse, {}), ('moving_sparse_paired', 6., paired, {}),
              ('moving_faster_sparse', 6., sparse, {'cadence_hz': 1.15}),
              ('changed_subject_sparse', 6., sparse, {'subject_seed': 193}),
              ('unmatched_baseline_sparse', 6., sparse, {'unmatched_baseline': True}),
              ('unannounced_sensor_offset', 6., sparse, {'sensor_offset': True})]
    return cases


def inherited_steady_rejection():
    path = ROOT/'results/stage3/information/comparison-summary.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    run = next(row for row in data['runs'] if row['id'] == 'actual_nominal_informative_seed0')
    c = run['calibration']
    return {'path': 'results/stage3/information/comparison-summary.json',
            'sha256': canonical_json_digest(path), 'sha256_scope': 'canonical JSON; independent of text line endings', 'run_id': run['id'],
            'response_map': c['response_map'], 'authority_singular_margin_m': c['authority_singular_margin_m'],
            'measured_dose_uncertainty_fraction': c['measured_dose_uncertainty_fraction'],
            'unchanged': True, 'new_dynamic_result_does_not_requalify_old_steady_map': True}


def experiment(check=False):
    identity = source_hashes()
    studies, models = {}, {}
    grid_records = {}
    for grid in GRIDS:
        grid_id = f'{grid*1e6:g}us'
        training = []
        for route in (0, 1):
            for sign in (-1, 1):
                for repeat in range(SPEC.minimum_repeats_per_signed_route):
                    index = len(training); routes = [0, 0]; routes[route] = sign
                    name = f'isolated_route{route}_sign{sign}_repeat{repeat}'
                    print(grid_id+': '+name, flush=True)
                    training.append(capture(name, 53000+index, grid, seconds=1.2,
                        plan=schedule(1.2, [(.25, tuple(routes))]), rest=True))
        model = fit_response_kernel(training, protocol_id=protocol_id(identity, grid, training))
        models[grid_id] = model
        actual_mean = float(np.mean(list(model.training['dose_mean_fraction_by_route'].values())))
        actual_u = max(model.training['dose_uncertainty_fraction_by_route'].values())
        doses = {'actual_electrical_trace_domain': ProspectiveDose(actual_mean, actual_u, 'ACTUAL_TRACE_REUSE_NOT_FUTURE_GUARANTEE'),
                 'nominal_future_assumption': ProspectiveDose(),
                 'four_percent_future_monitor_assumption': ProspectiveDose(1.012, .04, 'UNQUALIFIED_FUTURE_MONITOR_ALLOCATION')}
        validation, captures = {}, []
        for index, (name, seconds, events, extra) in enumerate(validation_cases()):
            print(grid_id+': '+name, flush=True)
            recording = capture(name, 64000+index, grid, seconds=seconds,
                                plan=schedule(seconds, events), **extra)
            captures.append(recording)
            validation[name] = {key: validate_response_recording(model, recording, dose) for key, dose in doses.items()}
        raw = {'schema': 'scci_rh.stage3.dynamic-response-recordings.v1', 'source_sha256': identity,
               'grid_s': grid, 'training': [serialize(r) for r in training],
               'independent_validation': [serialize(r) for r in captures]}
        raw_path = OUT/(grid_id+'.json.gz')
        write_gzip(raw_path, raw, check)
        studies[grid_id] = {'model': model.to_record(), 'prospective_branches': {key: asdict(dose) for key, dose in doses.items()},
                           'independent_validation': validation,
                           'raw_file': {'path': raw_path.name, 'sha256': hashlib.sha256(raw_path.read_bytes()).hexdigest()},
                           'online_candidate_witness': predict_future_effect(model, 1., 1.15,
                               (FutureResponseFrame(1., (1, 0)),), ProspectiveDose()),
                           'new_recording_seconds': 2*(len(training)*1.2+sum(case[1] for case in validation_cases())),
                           'actual_generated_pulses': sum(len(r['observed_dose']) for r in training+captures),
                           'validation_fit_overlap': False, 'neural_records': 0}
        grid_records[grid_id] = training+captures
    coarse, fine = (f'{grid*1e6:g}us' for grid in GRIDS)
    comparisons = []
    for a, b in zip(grid_records[coarse], grid_records[fine]):
        delta = np.asarray(a['private_evaluator_only']['position_m'])-b['private_evaluator_only']['position_m']
        base_delta = np.asarray(a['private_evaluator_only']['baseline_position_m'])-b['private_evaluator_only']['baseline_position_m']
        comparisons.append({'recording_id': a['recording_id'],
                            'maximum_position_difference_m': float(np.max(abs(delta))),
                            'maximum_baseline_difference_m': float(np.max(abs(base_delta)))})
    decision_match = all(studies[coarse]['independent_validation'][name][branch]['qualified'] ==
                         studies[fine]['independent_validation'][name][branch]['qualified']
                         for name in studies[coarse]['independent_validation']
                         for branch in studies[coarse]['prospective_branches'])
    if identity != source_hashes(): raise AssertionError('Source changed during dynamic response experiment')
    return {'schema': 'scci_rh.stage3.dynamic-response-study.v1', 'result_id': 'SCCI_RH-S3-DYNAMIC-RESPONSE-1',
            'source_sha256': identity, 'specification': asdict(SPEC), 'grids': studies,
            'numerical_comparison': {'records': comparisons, 'qualification_decisions_match': decision_match,
                'maximum_kernel_difference_m_per_fraction': float(np.max(abs(models[coarse].kernel_m_per_fraction-models[fine].kernel_m_per_fraction)))},
            'inherited_actual_steady_map_rejection': inherited_steady_rejection(),
            'scope': 'externally measured finite whole-frame response under fixed synthetic subject/task/load; no closed-loop or learning claim',
            'private_simulator_fit_inputs': False, 'historical_studies_replaced': False}


def report(value):
    lines = ['# Measured finite-frame dynamic response', '',
             'A steady pulse-train plateau gain does not predict the displacement caused by one sparse',
             'whole-profile command. This separate experiment identifies its measured time course.',
             'It changes no historical model, reference library, predictor or learning result.', '',
             '## Declared experiment', '',
             'The unchanged electrical adapter generates every nonzero calibration and validation',
             'pulse: **3 mA, 200 microseconds per phase, 40 Hz whole-profile frames**. The private body',
             'receives the adapter’s returned true signed charge fraction. Identification receives only',
             'independently monitored completed dose and external position measurements. Nominal onset',
             'stays **35 ms**, original movement/activation/plasticity constants stay fixed, and learning',
             'is disabled. Event-split integration at 2.5 ms and 0.625 ms is compared. This is an',
             '**external-only** experiment; there are no neural recordings or held-source claims.', '',
             'The original reduced biological law still holds a charge-normalized command for its',
             '25 ms frame after onset. The identified kernel qualifies that declared activation/body',
             'surrogate. It does not establish the real spinal response to a 500-microsecond biphasic',
             'electrode waveform; actual electrical delivery and assumed biological transduction remain',
             'distinct parts of the digital experiment.', '',
             'Calibration uses six isolated positive and six isolated negative pulses on each route,',
             'each paired with a separately measured rest baseline. A fixed 0..600 ms table at 5 ms',
             'physical supports estimates the two-foot response per monitored dose. Other noise',
             'realizations, movement, route combinations and schedules remain excluded from fitting.',
             'The body’s recruitment matrix, threshold, time constants, ODE state and future state are',
             'never fit or prospective prediction inputs. Measured baseline subtraction is an explicit',
             'paired-recording assumption; a subject/context change can invalidate it.', '',
             '## Error accounting', '',
             'The original actual monitor uncertainty (about 44.1% of nominal phase charge) is retained',
             'in **all fitted gain intervals**. The calibration allocation is',
             '`U_G = (2 SEM × d + |G| × U_d) / (d - U_d)`, with a positive denominator required.',
             '`2 SEM` is an empirical repeated-recording allocation, not probability coverage or a',
             'deterministic label bound. Prospective product error includes the cross term:',
             '`U_G × d_future + |G| × U_future + U_G × U_future`.',
             'The measured withheld residual, a separately declared **3 mm baseline-subtracted label',
             'allowance**, and joint product allocation must together remain below **25 mm** at every',
             'scored physical support. Positive principal-route directional authority is checked within',
             '150 ms. These finite empirical gates do not establish a worst-case biological bound.', '',
             'Directional single-command evidence does not qualify a full two-route inverse map.',
             'A later controller must select only independently admitted response domains and include',
             'its baseline/reference errors; the response table alone is not permission to stimulate.', '',
             'The actual branch generates its own per-frame electrical/monitor records. For prospective',
             'prediction it reuses the calibration trace mean/bound under the fixed modeled load; future',
             'validation monitors are withheld. The nominal branch instead chooses **1.012 ± 0.074**.',
             'A third branch chooses a **4% future-monitor allocation**. Both are unqualified prospective',
             'assumptions and neither reduces the actual past calibration uncertainty.', '',
             '## Independent observed domains', '',
             '| Grid us | Recording | Actual electrical trace domain | Nominal future assumption | 4% future assumption |',
             '|---:|---|---|---|---|']
    for grid, study in value['grids'].items():
        for name, branches in study['independent_validation'].items():
            decisions = [str(branches[key]['qualified']) for key in study['prospective_branches']]
            lines.append(f"| {grid.removesuffix('us')} | {name} | {' | '.join(decisions)} |")
    lines += ['', '| Grid us | Recording | Branch | Measured RMSE mm | Largest empirical allocation mm |',
              '|---:|---|---|---:|---:|']
    for grid, study in value['grids'].items():
        for name, branches in study['independent_validation'].items():
            for branch, row in branches.items():
                lines.append(f"| {grid.removesuffix('us')} | {name} | {branch} | {row['measured_response_rmse_m']*1000:.3f} | {row['maximum_empirical_error_allocation_m']*1000:.3f} |")
    comparisons = value['numerical_comparison']
    lines += ['', '## Numerical and composition limits', '',
              f"Both grids make identical domain decisions: **{comparisons['qualification_decisions_match']}**.",
              f"Largest fitted kernel difference: **{comparisons['maximum_kernel_difference_m_per_fraction']:.3g} m per dose fraction**.",
              'Raw independent trajectories, measured labels, monitor records, private generator-only',
              'pulse witnesses and every scored error trace are retained in the deterministic gzip files.', '',
              '`response_model_from_record(...)` loads a separately provenance-verified model receipt.',
              '`predict_future_effect(...)` accepts only known whole frames from the current decision',
              'to a physical target within 150 ms. It accepts no future monitor or measurement. Its',
              'output may be added only to a **zero-future-command baseline forecast**. The baseline',
              'already contains the effects of past commands; adding them again or adding this table',
              'to an assisted forecast would double-count intervention. Baseline prediction error,',
              'reference availability, acquisition, scheduling and residual guards remain separate',
              'prerequisites for any later coupled experiment.', '',
              '`predict_observed_past_response(...)` separately provides past-dose means and the same',
              'joint intervals for stripping measured history and adding ongoing past response at a',
              'target. It accepts only completed monitors already available at the decision and requires',
              'the complete past monitor history. **Release after 600 ms is unqualified**: older effects',
              'raise an explicit error instead of being silently treated as zero. A release rule or',
              'longer kernel domain needs separate qualification before long-running use.', '',
              'The existing actual steady-map rejection is linked with its saved source identity in',
              'the receipt and remains unchanged. New dynamic outcomes cannot retrospectively qualify',
              'that map or the historical 280-row learning comparison. No closed-loop policy, new',
              'retained-learning result, real neural recording or real consumer efficacy is established.', '',
              '## Reproduction', '',
              '`python -X utf8 scripts/stage3_dynamic_response_study.py --check` reruns the actual',
              'per-frame electrical delivery, both integration grids, measured fits and all heldout',
              'domains, and compares saved receipts/report at relative tolerance 2e-8, absolute 1e-11.',
              'Schemas: `scci_rh.stage3.dynamic-response-study.v1`, `scci_rh.stage3.dynamic-response-model.v1`,',
              'and `scci_rh.stage3.dynamic-response-recordings.v1`. All new files are separate from frozen',
              'Stage 3 studies. Model identities bind normalized sources, specification and declared',
              'recording/noise/schedule identities; numeric observations are compared separately with',
              'tolerance. ODE right-hand-side evaluation counts are platform-local diagnostics. The',
              'inherited JSON receipt uses a canonical digest independent of text line endings.',
              'Any failure remains a declared unavailable dynamic domain.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    value = experiment(args.check)
    path = OUT/'dynamic-response-summary.json'
    if args.check:
        saved = json.loads(path.read_text(encoding='utf-8'))
        close_nested(value, saved)
        assert DOC.read_text(encoding='utf-8') == report(saved), 'dynamic response report drift'
        print('Measured dynamic response and complete error accounting: reproduced')
    else:
        path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        DOC.write_text(report(value), encoding='utf-8')
        print('Measured dynamic response and complete error accounting: written')


if __name__ == '__main__':
    main()
