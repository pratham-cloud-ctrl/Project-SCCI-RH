"""One isolated, actual-delivery-coupled intervention per reset digital trial.

The policy accepts observed baselines, fixed references and independent measured
response domains. Private learner parameters and electrical truth belong only
to the simulator. This is a finite conditional pilot, not implant qualification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import deque
import numpy as np

from . import motor
from .assisted_prediction import MeasuredPosition
from .dynamic_response import ResponsePosition, FutureResponseFrame, predict_future_effect
from .electrical import MotorDelivery
from .residual_guard import DelayedResidualGuard, PredictionCommit
from .sparse_baseline import ZeroFutureInput, predict_zero_future, intersect_empty_action_domains


ARMS = ('observe_only', 'learner_goal', 'expert_external', 'expert_neural')
PILOT_CONTEXT_ID = 'isolated_pilot_all_observed_drift_alternatives'
ACTION_DOMAINS = {(1, 0): 'moving_single_0_1', (-1, 0): 'moving_single_0_-1',
                  (0, 1): 'moving_single_1_1', (0, -1): 'moving_single_1_-1',
                  (1, 1): 'moving_paired_same', (1, -1): 'moving_paired_opposite',
                  (-1, -1): None, (-1, 1): None}


@dataclass(frozen=True)
class PilotReference:
    kind: str
    coefficients_m: tuple[tuple[float, ...], tuple[float, ...]]
    position_error_allocation_m: float
    qualified: bool
    reference_id: str
    independent_recording_ids: tuple[str, ...]


def reference_from_library(library, kind):
    """Sanitize the frozen nominal reference using independent template error.

    The retained neural template is compared directly with independent measured
    external movement. Its 2*RMSE already covers the template's fitted decoder;
    adding the decoder residual separately would count that error twice.
    """
    if kind not in ('learner_only', 'expert_external', 'expert_neural'):
        raise ValueError('Unknown reference kind')
    reference = library['references_by_cadence']['1'][kind]
    coefficients = tuple(tuple(row) for row in reference['coefficients_m'])
    if kind == 'learner_only':
        if reference['training_seconds'] != 0. or reference['reference_fit_rmse_m'] is not None:
            raise ValueError('Known learner goal must not borrow expert evidence')
        return PilotReference(kind, coefficients, 0., bool(reference['qualified']),
                              'DECLARED_KNOWN_LEARNER_GOAL', ())
    domain = library['qualification']['domains']['1']['references'][kind]
    records = [row for row in library['qualification']['independent_validation']
               if row['identity']['cadence_hz'] == 1.]
    training = library['qualification']['training_identity']
    if (not reference['qualified'] or not domain['qualified'] or len(records) != 3
            or any(row['identity']['performance_seed'] == training['performance_seed'] for row in records)
            or any(not row['representations'][kind]['qualified'] for row in records)):
        raise ValueError('Qualified independent nominal teacher representations required')
    values = [row['representations'][kind]['position_error_allocation_m'] for row in records]
    if not np.all(np.isfinite(values)) or min(values) < 0. or max(values) > .025:
        raise ValueError('Invalid independent reference position allocation')
    ids = tuple(f"{row['identity']['generator']}:{row['identity']['performance_seed']}:1Hz" for row in records)
    if len(set(ids)) != len(ids): raise ValueError('Duplicate independent teacher identity')
    return PilotReference(kind, coefficients, float(max(values)), True, domain['reference_id'], ids)


@dataclass(frozen=True)
class IsolatedPilotSpec:
    subject_seed: int = 2
    trial_seconds: float = 3.
    practice_trials: int = 4
    decision_s: float = .975
    launch_s: float = 1.
    target_s: float = 1.100
    observation_availability_delay_s: float = .025
    complete_monitor_s: float = .000500
    forecast_limit_m: float = .015
    correction_limit_m: float = .025
    coefficient_validation_scales: tuple[float, ...] = (.9, 1., 1.15, 1.3)

    def __post_init__(self):
        if asdict(self) != asdict(IsolatedPilotSpec.__new_defaults()):
            raise ValueError('This bounded pilot freezes its phase, gates and resources')

    @classmethod
    def __new_defaults(cls):
        value = object.__new__(cls)
        for name, field in cls.__dataclass_fields__.items():
            object.__setattr__(value, name, field.default)
        return value


def config():
    return motor.MotorConfig(body_integration_step_s=.0025,
        body_integration_method='midpoint_exact_cascade',
        acquisition_qualification_mode='bounded_residual', acquisition_clock_uncertainty_s=20e-6)


def choose_action(*, baseline, packet, dynamic_model, independent_domains, reference,
                  prospective_dose, now_s, launch_s, target_s):
    """Pure observable policy: zero wins ties; unavailable actions never score.

    Dynamic residual allowances were measured at this exact 1 s launch/1.1 s
    target phase, before practice. They are finite empirical allocations, not
    statistical or universal bounds. The future candidate is added exactly once.
    """
    if (baseline.get('baseline_contract') != 'ZERO_FUTURE_COMMAND_BASELINE'
            or baseline.get('candidate_future_response_included') is not False
            or baseline.get('qualified_for_context') is not True):
        raise ValueError('Qualified zero-future-command baseline required')
    if (not np.all(np.isfinite([now_s, launch_s, target_s])) or abs(now_s-.975) > 1e-10
            or abs(launch_s-1.) > 1e-10 or abs(target_s-1.1) > 1e-10
            or now_s > launch_s-.01185+1e-12):
        raise ValueError('Outside independently measured phase or processing window')
    if (not isinstance(packet, ZeroFutureInput) or packet.completed_doses
            or packet.family != 'isolated_nominal' or packet.cadence_hz != 1.
            or packet.task_time_offset_s != 0. or packet.now_s != now_s
            or not np.isfinite(packet.committed_zero_until_s) or packet.committed_zero_until_s < target_s
            or len(packet.history) != 16):
        raise ValueError('Fresh isolated nominal admission packet with no past dose required')
    for index, measurement in enumerate(packet.history):
        support = .875+index*.005
        if (not isinstance(measurement, ResponsePosition) or not measurement.valid
                or np.asarray(measurement.position_m).shape != (2,)
                or not np.all(np.isfinite([measurement.support_s, measurement.available_s, *measurement.position_m]))
                or abs(measurement.support_s-support) > 1e-10
                or abs(measurement.available_s-support-.025) > 1e-10
                or measurement.available_s > now_s+1e-12):
            raise ValueError('Exact causal 16-row 5 ms history and 25 ms arrival clock required')
    if (baseline.get('context_id') != PILOT_CONTEXT_ID
            or baseline.get('dynamic_model_id') != dynamic_model.model_id
            or not np.all(np.isfinite([baseline.get('support_s', np.nan),
                baseline.get('target_support_s', np.nan), baseline.get('horizon_s', np.nan)]))
            or abs(baseline['support_s']-.950) > 1e-10
            or abs(baseline['target_support_s']-target_s) > 1e-10
            or abs(baseline['horizon_s']-.150) > 1e-10):
        raise ValueError('Exact independent pilot context, model and physical forecast support required')
    position = np.asarray(baseline['position_m'], dtype=float)
    base_interval = np.broadcast_to(np.asarray(baseline['total_forecast_allocation_m'], dtype=float), (2,))
    if (position.shape != (2,) or not np.all(np.isfinite(position))
            or not np.all(np.isfinite(base_interval)) or np.any(base_interval < 0)
            or np.max(base_interval) > .015):
        raise ValueError('Invalid or excessive baseline interval')
    if not isinstance(reference, PilotReference) or not reference.qualified:
        raise ValueError('UNQUALIFIED_TEACHER_REFERENCE')
    reference_position = np.asarray(reference.coefficients_m)@motor.task_basis(target_s)
    reference_interval = float(reference.position_error_allocation_m)
    if (reference_position.shape != (2,) or not np.all(np.isfinite(reference_position))
            or not np.isfinite(reference_interval) or reference_interval < 0):
        raise ValueError('Invalid observed reference')
    score = float(np.sum((reference_position-position)**2))
    selected = (0, 0)
    candidate_position, candidate_interval = position, base_interval
    rows = []
    for routes, domain_id in ACTION_DOMAINS.items():
        if domain_id is None:
            rows.append({'routes': list(routes), 'domain_id': None, 'domain_qualified': False,
                         'eligible': False, 'reason': 'MIXED_ROUTE_NOT_INDEPENDENTLY_TESTED'})
            continue
        domain = independent_domains[domain_id]
        if (domain.get('dynamic_model_id') != dynamic_model.model_id
                or abs(domain.get('target_support_s', np.nan)-target_s) > 1e-10
                or abs(domain.get('launch_s', np.nan)-launch_s) > 1e-10
                or not np.all(np.isfinite([domain.get('target_support_s', np.nan), domain.get('launch_s', np.nan)]))):
            raise ValueError('Independent dynamic domain must match exact launch and target support')
        row = {'routes': list(routes), 'domain_id': domain_id, 'domain_qualified': bool(domain['qualified'])}
        if not domain['qualified']:
            rows.append({**row, 'eligible': False, 'reason': 'INDEPENDENT_DYNAMIC_DOMAIN_UNQUALIFIED'})
            continue
        effect = predict_future_effect(dynamic_model, now_s, target_s,
            (FutureResponseFrame(launch_s, routes, now_s),), prospective_dose)
        residual = np.asarray(domain['target_residual_allocation_m'], dtype=float)
        if (residual.shape != (2,) or not np.all(np.isfinite(residual)) or np.any(residual < 0)):
            raise ValueError('Invalid independent dynamic residual allocation')
        # The full joint gain/dose product is supplied by predict_future_effect.
        interval = base_interval+effect['joint_gain_dose_error_m']+residual+reference_interval
        predicted = position+effect['effect_m']
        candidate_score = float(np.sum((reference_position-predicted)**2))
        eligible = bool(np.all(np.isfinite(interval)) and np.max(interval) <= .025)
        row.update(eligible=eligible, reason='ADMITTED_FINITE_CONDITIONAL_CANDIDATE' if eligible
                   else 'COMBINED_CORRECTION_INTERVAL_EXCEEDS25MM',
                   position_m=predicted.tolist(), combined_allowance_m=interval.tolist(),
                   dynamic_joint_gain_dose_error_m=np.asarray(effect['joint_gain_dose_error_m']).tolist(),
                   independent_dynamic_residual_allocation_m=residual.tolist(),
                   independent_reference_position_allocation_m=reference_interval, score_m2=candidate_score)
        rows.append(row)
        if eligible and candidate_score < score-1e-15:
            score, selected = candidate_score, routes
            candidate_position, candidate_interval = predicted, interval
    return {'selected_routes': list(selected), 'selected_position_m': candidate_position.tolist(),
        'selected_allowance_m': candidate_interval.tolist(), 'reference_position_m': reference_position.tolist(),
        'zero_action_score_m2': float(np.sum((reference_position-position)**2)), 'selected_score_m2': score,
        'reason': 'ISOLATED_WHOLE_FRAME_SELECTED' if any(selected) else 'ZERO_ACTION_BEST_OR_ALL_CANDIDATES_UNAVAILABLE',
        'candidate_future_response_counted': 1 if any(selected) else 0,
        'future_monitor_used': False, 'future_measurement_used': False,
        'private_learner_parameters_used': False, 'learner_neural_used': False,
        'reference_id': reference.reference_id,
        'independent_reference_position_allocation_m': reference_interval,
        'reference_allocation_scope': 'maximum independent nominal complete-trajectory 2*RMSE; zero for known learner goal',
        'candidates': rows}


def generate_unassisted(recording_id, noise_seed, *, seconds, family='zero', theta_scale=1.,
                        learning=False, spec=IsolatedPilotSpec()):
    """Private generator; only the separate measured view may fit the baseline."""
    c = config(); world = motor._World(spec.subject_seed, c)
    world.theta *= theta_scale
    rng = np.random.default_rng(noise_seed)
    measured, positions, times = [], [], []
    for index in range(round(seconds/c.dt_s)):
        t = index*c.dt_s
        position = world.x.copy()
        observed = position+rng.normal(0., c.external_noise_m, 2)
        measured.append(ResponsePosition(t, t+spec.observation_availability_delay_s, tuple(observed)))
        positions.append(position.tolist()); times.append(t)
        world.advance(t+c.dt_s, np.zeros(2), family, learning=learning)
    observed_view = {'recording_id': recording_id, 'measurement_noise_id': noise_seed,
        'measurements': measured, 'observed_dose': [], 'planned_frames': [],
        'family': 'isolated_nominal', 'cadence_hz': 1., 'task_time_offset_s': 0.}
    return observed_view, {'generator_only': {'family': family, 'initial_theta_scale': theta_scale,
        'learning': learning, 'private_positions_m': positions, 'times_s': times},
        'observed': {**observed_view, 'measurements': [asdict(p) for p in measured]}}


def aggregate_context(validations, *, context_id, dynamic_model_id):
    """One conservative context for every arm/family; never select by private theta."""
    contexts = [v['context'] for v in validations]
    if not contexts or any(c['dynamic_model_id'] != dynamic_model_id or c['family'] != 'isolated_nominal'
                           for c in contexts):
        raise ValueError('Matched independent measured contexts required')
    horizons = []
    for index in range(26):
        rows = [c['horizons'][index] for c in contexts]
        values = [r['maximum_component_residual_m'] for r in rows]
        allocations = [r['empirical_error_allocation_m'] for r in rows]
        # Warmup exclusions are declared. Excluding a drift/domain failure does
        # not count as qualification of that complete observed context.
        exclusion_ok = all(not (set(r['exclusion_reasons'])-{'INITIAL_WARMUP'}) for r in rows)
        domains = intersect_empty_action_domains([r['eligible_domains'] for r in rows])
        qualified = all(r['qualified'] for r in rows) and exclusion_ok and bool(domains)
        horizons.append({'horizon_s': rows[0]['horizon_s'],
            'maximum_component_residual_m': max(values) if all(v is not None for v in values) else None,
            'empirical_error_allocation_m': max(allocations) if all(v is not None for v in allocations) else None,
            'qualified': qualified, 'all_capture_exclusions_supported': exclusion_ok,
            'eligible_domains': domains})
    return {'recording_id': context_id, 'family': 'isolated_nominal', 'dynamic_model_id': dynamic_model_id,
        'qualified': all(h['qualified'] for h in horizons), 'horizons': horizons,
        'independent_recording_ids': [c['recording_id'] for c in contexts],
        'empty_past_action_coverage': 'intersection across every independent capture per horizon; no union or dropped action prefix',
        'private_family_or_theta_used_to_select_context': False,
        'scope': 'maximum over all independent observed nominal-cue drift alternatives; finite empirical scope only'}


def run_trial(*, theta, family, arm, noise_seed, baseline_model, dynamic_model, context_id,
              independent_domains, reference, prospective_dose, learning, heldout=False,
              spec=IsolatedPilotSpec(), delivery=None):
    """Actual body coupling with one future action and delayed external evidence.

    Theta and true delivered charge stay inside this simulator wrapper. The
    observable chooser never receives either. Every trial resets state, delayed
    drive, acquisition history, monitor session and policy guard; only theta is
    carried by the experiment. This explicit washout is a modeling premise.
    """
    if arm not in ARMS or family not in motor.FAMILIES:
        raise ValueError('Unknown matched arm or plasticity family')
    if context_id != PILOT_CONTEXT_ID:
        raise ValueError('Fixed independent aggregate pilot context required')
    c = config(); world = motor._World(spec.subject_seed, c, heldout=heldout)
    world.theta = np.asarray(theta, dtype=float).copy()
    adapter = delivery if delivery is not None else MotorDelivery()
    if hasattr(adapter, 'begin_session'): adapter.begin_session()
    rng = np.random.default_rng(noise_seed)
    guard = DelayedResidualGuard(); queue = deque(); history = deque(maxlen=16)
    positions, times, measurements, launches, monitor_pending, monitors = [], [], [], [], [], []
    decision = None; selected = (0, 0); held_true = np.zeros(2)
    continuation_stop = None; launch_check = None
    baseline_commits = 0
    for index in range(round(spec.trial_seconds/c.dt_s)):
        t = index*c.dt_s
        # Current physical measurement is unavailable until t+25 ms. It cannot
        # influence today's policy, launch or candidate score.
        measured = ResponsePosition(t, t+spec.observation_availability_delay_s,
                                    tuple(world.x+rng.normal(0., c.external_noise_m, 2)))
        queue.append(measured); measurements.append(asdict(measured))
        while queue and queue[0].available_s <= t+1e-12:
            arrived = queue.popleft(); history.append(arrived)
            guard.observe(MeasuredPosition(arrived.support_s, arrived.available_s, arrived.position_m), now_s=t)
        while monitor_pending and monitor_pending[0]['available_s'] <= t+1e-12:
            monitor = monitor_pending.pop(0)
            monitor['processed_at_s'] = t
            nominal = c.nominal_current_A*c.phase_s
            measured_fraction = monitor['delivered_phase_charge_C']/nominal
            uncertainty_fraction = monitor['charge_uncertainty_C']/nominal
            outside = (abs(measured_fraction-prospective_dose.measured_fraction)+uncertainty_fraction
                       > prospective_dose.uncertainty_fraction+1e-12)
            monitor['prospective_interval_not_confirmed'] = outside
            monitor['measured_fraction'] = measured_fraction
            monitor['uncertainty_fraction'] = uncertainty_fraction
            if outside or monitor['quality'] != 'VALID' or monitor['inhibit_next']:
                continuation_stop = continuation_stop or ('ACTUAL_MONITOR_INTERVAL_EXCEEDS_PROSPECTIVE_ASSUMPTION'
                    if outside else 'ACTUAL_MONITOR_REJECTED_CONTINUATION')
            monitors.append(monitor)
        timed = guard.check(now_s=t)
        if not timed['continuation_allowed']:
            continuation_stop = continuation_stop or timed['reason']
        # Warmup independent of hidden drift. These baseline-only targets arrive
        # before the launch and can cancel it using measured residuals.
        if (learning and arm != 'observe_only' and len(history) == 16
                and .200-1e-12 <= t <= .800+1e-12 and index % 5 == 0
                and continuation_stop is None):
            packet = ZeroFutureInput(t, tuple(history), (), spec.launch_s, 'isolated_nominal')
            try:
                forecast = predict_zero_future(baseline_model, dynamic_model, packet, .150, context_id=context_id)
                allowance = np.broadcast_to(forecast['total_forecast_allocation_m'], (2,))
                guard.commit(PredictionCommit(t, forecast['target_support_s'], tuple(forecast['position_m']),
                    tuple(allowance), dynamic_model.model_id, context_id))
                baseline_commits += 1
            except ValueError as exc:
                continuation_stop = 'PRELAUNCH_BASELINE_REJECTED: '+str(exc)
        if abs(t-spec.decision_s) < 1e-10:
            if not learning or heldout or arm == 'observe_only':
                decision = {'selected_routes': [0, 0], 'reason': 'OUTPUT_OFF_ASSESSMENT' if not learning
                            else 'MATCHED_OBSERVE_ONLY', 'candidates': []}
            elif continuation_stop is not None or len(history) != 16:
                decision = {'selected_routes': [0, 0], 'reason': continuation_stop or 'INCOMPLETE_EXTERNAL_HISTORY', 'candidates': []}
            else:
                try:
                    packet = ZeroFutureInput(t, tuple(history), (), spec.trial_seconds, 'isolated_nominal')
                    horizon = spec.target_s-history[-1].support_s
                    forecast = predict_zero_future(baseline_model, dynamic_model, packet, horizon, context_id=context_id)
                    decision = choose_action(baseline=forecast, packet=packet, dynamic_model=dynamic_model,
                        independent_domains=independent_domains, reference=reference, prospective_dose=prospective_dose,
                        now_s=t, launch_s=spec.launch_s, target_s=spec.target_s)
                    decision['baseline'] = forecast
                    selected = tuple(decision['selected_routes'])
                    if any(selected):
                        guard.commit(PredictionCommit(t, spec.target_s, tuple(decision['selected_position_m']),
                            tuple(decision['selected_allowance_m']), dynamic_model.model_id, context_id))
                except ValueError as exc:
                    decision = {'selected_routes': [0, 0], 'reason': str(exc), 'candidates': []}
        if abs(t-spec.launch_s) < 1e-10:
            launch_check = guard.check(now_s=t)
            if continuation_stop is None and launch_check['continuation_allowed'] and any(selected):
                for route, sign in enumerate(selected):
                    if not sign: continue
                    truth, _, monitor, witness = motor._pulse(t, route, sign, adapter, c)
                    held_true[route] = truth  # Simulator only; never put in the policy packet.
                    launches.append(witness)
                    monitor_pending.append({**monitor, 'available_s': t+spec.complete_monitor_s})
            elif any(selected):
                decision['launch_cancelled_reason'] = continuation_stop or launch_check['reason']
        if t >= spec.launch_s+1/c.pulse_hz-1e-12:
            held_true.fill(0.)
        times.append(t); positions.append(world.x.copy())
        world.advance(t+c.dt_s, held_true, family, learning=learning, heldout=heldout)
    # Drain only already generated measurements on their actual availability
    # clock, so final targets are neither invented nor silently skipped.
    while queue:
        row = queue.popleft()
        guard.observe(MeasuredPosition(row.support_s, row.available_s, row.position_m), now_s=row.available_s)
        guard.check(now_s=row.available_s)
    unique_frames = sorted({round(p['time_s']*40) for p in launches})
    return {'arm': arm, 'learning_enabled': learning, 'heldout_faster_cadence': heldout,
        'noise_seed': noise_seed, 'decision': decision, 'launch_clock_check': launch_check,
        'launched_frames': len(unique_frames), 'launched_profiles': len(launches), 'launches': launches,
        'actual_monitor_records': monitors, 'continuation_stop_reason': continuation_stop,
        'residual_guard_latched_reason': guard.latched_reason, 'residual_checks': guard.scored,
        'baseline_only_forecasts_committed': baseline_commits, 'pending_forecasts_at_end': len(guard.pending),
        'metrics': motor._metrics(times, positions, c, heldout=heldout),
        'measurements': measurements, 'private_evaluator_only': {'times_s': times,
            'positions_m': np.asarray(positions).tolist(), 'theta_after_m': world.theta.tolist(),
            'true_charge_used_only_by_body': True},
        'learner_sensing': 'causal external-only fallback; live learner neural recording not qualified in this pilot',
        'output_protocol': 'one isolated whole 25 ms frame at 1 s; no further command, including OFF assessments',
        'state_reset_premise': 'complete position/activation/delay washout between trials; learned coefficients alone carry'}, world.theta.copy()
