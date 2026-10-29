"""New conditional assisted-observer recordings; no hidden truth online."""
from __future__ import annotations

import argparse
from collections import deque
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
from scci_rh.stage3 import motor
from scci_rh.stage3.acquisition import AcquisitionConfig, ContactAcquisition
from scci_rh.stage3.electrical import MotorDelivery
from scci_rh.stage3.assisted_prediction import (
    PredictionSpec, KnownInstruction, ObservedDose, PlannedFrame, measured_record,
    fit_assisted_predictor, validate_assisted_recording, coupling_admission)
from run_stage3_studies import close_nested

SOURCE_PATHS = ('src/scci_rh/stage3/assisted_prediction.py', 'src/scci_rh/stage3/motor.py',
                'src/scci_rh/stage3/acquisition.py', 'src/scci_rh/stage3/filter_residual.py',
                'src/scci_rh/stage3/electrical.py', 'scripts/stage3_assisted_prediction_study.py')
SPEC = PredictionSpec()


def source_hashes():
    return {p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for p in SOURCE_PATHS}


def schedule(duration_s, density, phase, *, unassisted=False):
    """Known whole-frame catalogue; no fractional-amplitude or catch-up pulse."""
    patterns = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (0, 0))
    frames = []
    accumulator = 0.
    for frame in range(int(np.ceil((duration_s+.2)/SPEC.frame_s))):
        time = frame*SPEC.frame_s
        block = int(np.floor((time+1e-10)/.250))
        chosen_density = (.25, .5, 1.)[(block+phase)%3] if density == 'mixed' else float(density)
        accumulator += chosen_density
        admitted = accumulator >= 1.-1e-12
        if admitted: accumulator -= 1.
        routes = patterns[(3*block+phase)%len(patterns)] if admitted else (0, 0)
        if unassisted or not .500 <= time < duration_s-.500: routes = (0, 0)
        frames.append(PlannedFrame(time, routes))
    return tuple(frames)


def capture(recording_id, seed, config, *, density, phase, instruction=KnownInstruction(),
            changed_response=False, sensor_offset=False, unassisted=False):
    """Simulator/evaluator boundary only; all fitting views are sanitized below."""
    duration = 6.
    plan = schedule(duration, density, phase, unassisted=unassisted)
    world = motor._World(2, config, heldout=changed_response)
    acquisition = ContactAcquisition(8302, AcquisitionConfig(qualification_mode='bounded_residual',
                                      clock_uncertainty_s=20e-6), noise_seed=seed+17001)
    external_rng = np.random.default_rng(seed+9200)
    history = deque([np.zeros(2) for _ in range(5)], maxlen=5)
    measurements, monitor, evaluator_pulses = [], [], []
    neural_status, errors = [], []
    held_true = np.zeros(2)
    # Only the generation law receives private state. Known task instructions
    # are identical public inputs for the observer; no physical time constant
    # or body coefficient enters the model fit.
    with patch.object(motor, 'task_basis', side_effect=lambda t, heldout=False: instruction.basis(t)):
        for tick in range(int(duration/config.dt_s)):
            time = tick*config.dt_s
            if motor._pulse_frame(time, config):
                held_true.fill(0)
                frame = plan[int(round(time/config.dt_s))//5]
                for source, route in enumerate(frame.signed_routes):
                    if not route: continue
                    truth, _, observed, witness = motor._pulse(time, source, route, motor._assumed_delivery, config)
                    held_true[source] = truth
                    monitor.append(ObservedDose(time, time+SPEC.complete_profile_s, source, route,
                        observed['delivered_phase_charge_C']/(config.nominal_current_A*config.phase_s),
                        observed['charge_uncertainty_C']/(config.nominal_current_A*config.phase_s), observed['quality']))
                    evaluator_pulses.append(witness)
                    if truth != 0: acquisition.add_artifact(time, config.phase_s)
            history.append(world.x.copy())
            measured = history[0]+external_rng.normal(0, config.external_noise_m, 2)
            if sensor_offset and time >= 3.: measured += np.array([.040, -.040])
            neural = acquisition.observe(time, world.x/config.foot_amplitude_m,
                world.v/(2*np.pi*config.foot_amplitude_m),
                external_redundant_state=measured/config.foot_amplitude_m)
            observation = motor.Observation(time+config.dt_s, tuple(measured), time-config.external_delay_s, True, neural)
            measurements.append(measured_record(observation))
            neural_status.append({'available_s': observation.available_time_s,
                'valid': neural.valid, 'reasons': neural.reasons,
                'feature_error_maximum_uv': max(neural.feature_error_bound_uv, default=0.)})
            errors.append(np.asarray(neural.feature_error_bound_uv))
            world.advance(time+config.dt_s, held_true, 'zero', learning=False)
    schedule_digest = hashlib.sha256(json.dumps([asdict(f) for f in plan], sort_keys=True,
                                               separators=(',', ':')).encode()).hexdigest()
    return {'recording_id': recording_id, 'measurements': measurements, 'observed_dose': monitor,
        'planned_frames': plan, 'instruction': instruction, 'schedule_identity': schedule_digest,
        'generation': {'subject_seed': 2, 'observation_noise_seed': seed, 'duration_s': duration,
            'density': density, 'pattern_phase': phase, 'changed_response_context': changed_response,
            'sensor_offset_step': sensor_offset, 'unassisted': unassisted,
            'learning_enabled': False, 'source_approximation': 'block-start5msheld; full moving-body apertures pending',
            'private_body_parameters_excluded_from_prediction': True},
        'acquisition': {'mode': 'bounded_residual', 'raw_sample_count': acquisition.total_raw_samples,
            'masked_sample_count': acquisition.total_masked_samples,
            'valid_packet_count': sum(p.neural_valid for p in measurements),
            'neural_packet_count': len(measurements), 'status': neural_status,
            'maximum_feature_error_bound_uv': float(max((np.max(e) for e in errors if len(e)), default=0.)),
            'voltage_noise_final_generator_state': acquisition._rng.bit_generator.state,
            'external_noise_final_generator_state': external_rng.bit_generator.state},
        'private_evaluator_only': {'pulse_witnesses': evaluator_pulses,
            'pulse_count': len(evaluator_pulses), 'body_integration_steps': world.integration_substeps}}


def serialize_recording(recording):
    return {**recording, 'measurements': [asdict(p) for p in recording['measurements']],
        'observed_dose': [asdict(p) for p in recording['observed_dose']],
        'planned_frames': [asdict(p) for p in recording['planned_frames']],
        'instruction': asdict(recording['instruction'])}


def run_study():
    identity = source_hashes()
    config = motor.MotorConfig(body_integration_step_s=.0025, body_integration_method='midpoint_exact_cascade',
        acquisition_qualification_mode='bounded_residual', acquisition_clock_uncertainty_s=20e-6)
    training = []
    for number, density in enumerate((1., .5, .25, 'mixed')):
        name = f'assisted_calibration_{number}'
        print(name+': capturing', flush=True)
        training.append(capture(name, 33000+number, config, density=density, phase=number))
    print('Fitting31causal assisted horizon models', flush=True)
    model = fit_assisted_predictor(training)
    contexts = [
        ('withheld_quarter', .25, 5, {}), ('withheld_half', .5, 6, {}),
        ('withheld_full', 1., 7, {}), ('withheld_unassisted', 1., 0, {'unassisted': True}),
        ('withheld_faster_known_cadence', 'mixed', 2, {'instruction': KnownInstruction(1.15)}),
        ('withheld_known_cue_shift', 'mixed', 3, {'instruction': KnownInstruction(1., .125)}),
        ('withheld_changed_response', 'mixed', 4, {'changed_response': True}),
        ('withheld_unannounced_sensor_offset', 'mixed', 5, {'sensor_offset': True})]
    recordings, validation = [], []
    for number, (name, density, phase, extra) in enumerate(contexts):
        print(name+': capturing and checking every horizon', flush=True)
        recording = capture(name, 44000+number, config, density=density, phase=phase, **extra)
        recordings.append(recording)
        validation.append(validate_assisted_recording(model, recording))
    print('Preserving actual electrical map rejection', flush=True)
    # These calibrations are diagnostic resources, not free additions to a
    # learning comparison. No learner-plasticity experiment is run here.
    actual_map, _, actual_meta = motor.calibrate(2, config, MotorDelivery())
    conditional_map, _, conditional_meta = motor.calibrate(2, config)
    reference = motor.ExpertRepresentation('learner_only', ((.1, 0., 0., 0.), (-.1, 0., 0., 0.)),
        None, 'known instructed goal; teacher library integration separate', 'known_task_no_subject', 0.)
    admissions = []
    for name, response, metadata in (('actual_electrical', actual_map, actual_meta),
                                     ('conditional_prospective_delivery', conditional_map, conditional_meta)):
        admissions.append({'branch': name, 'response': asdict(response),
            'calibration_authority_margin_m': metadata['authority_singular_margin_m'],
            'context_admissions': {r['recording_id']: coupling_admission(model, r['recording_id'], response,
                reference, dynamic_response_qualified=False) for r in recordings}})
    if source_hashes() != identity: raise AssertionError('Source changed during prediction experiment')
    return {'schema': 'scci_rh.stage3.assisted-prediction-study.v1', 'date': '2026-10-09',
        'source_identity': identity, 'status': 'independent_assisted_forecast_and_admission_audit',
        'specification': asdict(SPEC), 'motor_config': asdict(config), 'model': model,
        'training_recordings': [serialize_recording(r) for r in training],
        'withheld_recordings': [serialize_recording(r) for r in recordings],
        'validation': validation, 'admission_audits': admissions,
        'teacher_reference': asdict(reference),
        'scope': {'coupled_feedback_pulses': 0, 'retained_learning_measured': False,
            'teacher_library_consumed': False, 'future_monitored_charge_as_online_input': False,
            'future_achieved_motion_as_online_input': False,
            'dynamic_execution_response_qualified': False,
            'full_moving_body_aperture_qualification': False,
            'actual_monitor_rejection_preserved': True},
        'limitations': ['Predetermined intervention recordings are not feedback-policy validation.',
            'Future dose intervals are explicitly unqualified assumptions; actual electrical authority remains rejected.',
            'Linear-weight dose-interval propagation is conditional on the fitted empirical model.',
            'A finite context pass does not establish population coverage, unknown posture or biological skill transfer.',
            'Bounded-residual spinal packets are never replaced or relabeled valid by this external-history forecaster.',
            'Static route-map qualification does not qualify dynamic execution-time correction.']}


def plain(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    raise TypeError(type(value).__name__)


def summary(result, raw_path=None, raw_sha=None):
    brief = {k: v for k, v in result.items() if k not in {'model', 'training_recordings', 'withheld_recordings', 'validation'}}
    brief['model'] = {k: v for k, v in result['model'].items() if k != 'models'}
    brief['model']['models'] = [{k: v for k, v in m.items() if k not in {'weights', 'mean', 'scale'}}
                                for m in result['model']['models']]
    brief['recordings'] = [{k: v for k, v in r.items() if k not in {'measurements', 'observed_dose', 'planned_frames', 'private_evaluator_only'}}
        | {'acquisition': {k: v for k, v in r['acquisition'].items() if k != 'status'},
           'pulse_count': r['private_evaluator_only']['pulse_count']}
        for r in result['training_recordings']+result['withheld_recordings']]
    brief['validation'] = [v['context'] for v in result['validation']]
    brief['counts'] = {'training_recordings': len(result['training_recordings']),
        'complete_withheld_recordings': len(result['withheld_recordings']),
        'horizon_models': len(result['model']['models']),
        'qualified_chronological_horizons': sum(m['qualified'] for m in result['model']['models']),
        'qualified_complete_withheld_recordings': sum(v['context']['qualified'] for v in result['validation']),
        'independent_recording_horizon_checks': sum(len(v['context']['horizons']) for v in result['validation']),
        'coupled_feedback_pulses': 0}
    if raw_path: brief['raw_witness'] = {'path': raw_path, 'sha256': raw_sha}
    return brief


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path); parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.output and args.check: parser.error('Choose output or check')
    result = run_study()
    if args.check:
        expected = json.loads(gzip.decompress(args.check.read_bytes()))
        close_nested(json.loads(json.dumps(result, default=plain)), expected)
        saved_summary = json.loads(args.check.with_name('summary.json').read_text(encoding='utf-8'))
        close_nested(json.loads(json.dumps(summary(result, args.check.name, hashlib.sha256(args.check.read_bytes()).hexdigest()), default=plain)), saved_summary)
        print('Assisted prediction raw and readable receipts reproduced; failed domains and actual rejection retained')
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        with gzip.GzipFile(filename='', fileobj=buffer, mode='wb', mtime=0) as stream:
            stream.write((json.dumps(result, default=plain, separators=(',', ':'), allow_nan=False)+'\n').encode())
        args.output.write_bytes(buffer.getvalue())
        brief = summary(result, args.output.name, hashlib.sha256(args.output.read_bytes()).hexdigest())
        args.output.with_name('summary.json').write_text(json.dumps(brief, default=plain, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(json.dumps(brief['counts']))
    else: print(json.dumps(summary(result)['counts']))


if __name__ == '__main__': main()
