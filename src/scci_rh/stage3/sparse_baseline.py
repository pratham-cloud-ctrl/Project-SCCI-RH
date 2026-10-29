"""External-only zero-future-command baseline with observed past-response removal.

The online contract contains no paired baseline, future achieved movement or
future dose. Finite response ages and zero-command commitments are explicit.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from types import SimpleNamespace
import numpy as np

from .cue_policy import CueConfig, fit_known_cue_forecast
from .dynamic_response import ResponsePosition, CompletedDose, predict_observed_past_response
from .motor import task_basis


@dataclass(frozen=True)
class SparseBaselineSpec:
    sample_s: float = .005
    history_rows: int = 16
    maximum_horizon_s: float = .150
    minimum_execution_horizon_s: float = .025
    forecast_limit_m: float = .015
    label_allowance_m: float = .003
    minimum_support_s: float = .100
    feature_limit: float = 5.

    def __post_init__(self):
        if tuple(asdict(self).values()) != (.005, 16, .150, .025, .015, .003, .100, 5.):
            raise ValueError('Sparse baseline clocks, domain and allocations are frozen')


@dataclass(frozen=True)
class ZeroFutureInput:
    now_s: float
    history: tuple[ResponsePosition, ...]
    completed_doses: tuple[CompletedDose, ...]
    committed_zero_until_s: float
    family: str
    cadence_hz: float = 1.
    task_time_offset_s: float = 0.


FAMILIES = ('unassisted_nominal', 'isolated_nominal', 'sparse_individual_nominal', 'sparse_mixed_nominal')


def _past_action_pattern(doses):
    """Only known completed action identity; measured dose intervals stay live."""
    return [list(action) for action in sorted(
        (round(d.frame_time_s/.025)*.025, d.source_id, d.route_sign) for d in doses)]


def _append_eligible_domain(domains, support_s, actions, spec):
    support = round(support_s/spec.sample_s)*spec.sample_s
    if abs(support-support_s) > 1e-9:
        raise ValueError('Validated physical support must use the frozen5msgrid')
    if (domains and domains[-1]['observed_past_actions'] == actions
            and abs(support-domains[-1]['support_end_s']-spec.sample_s) <= 1e-9):
        domains[-1]['support_end_s'] = support
    else:
        domains.append({'support_start_s': support, 'support_end_s': support,
                        'observed_past_actions': actions})


def intersect_empty_action_domains(domain_sets, spec=SparseBaselineSpec()):
    """Common finite support of independent fresh no-dose qualifications.

    Empty action prefixes are required in every input. Taking a union or
    dropping a nonempty prefix would silently widen fresh-session authority.
    """
    sets = []
    for domains in domain_sets:
        support_indices = set()
        for domain in domains:
            if domain['observed_past_actions']:
                raise ValueError('Fresh aggregate requires empty past-action domains')
            start, end = domain['support_start_s'], domain['support_end_s']
            if (not np.all(np.isfinite([start, end])) or end < start
                    or abs(start/spec.sample_s-round(start/spec.sample_s)) > 1e-8
                    or abs(end/spec.sample_s-round(end/spec.sample_s)) > 1e-8):
                raise ValueError('Finite ordered5msaggregate support required')
            support_indices.update(range(round(start/spec.sample_s), round(end/spec.sample_s)+1))
        sets.append(support_indices)
    common = set.intersection(*sets) if sets else set()
    output = []
    for index in sorted(common):
        _append_eligible_domain(output, index*spec.sample_s, [], spec)
    return output


def _require_eligible_domain(checked, packet, spec):
    support = packet.history[-1].support_s
    matched = [domain for domain in checked.get('eligible_domains', ())
               if domain['support_start_s']-1e-9 <= support <= domain['support_end_s']+1e-9
               and abs((support-domain['support_start_s'])/spec.sample_s
                       -round((support-domain['support_start_s'])/spec.sample_s)) <= 1e-8]
    if not matched:
        raise ValueError('OUTSIDE_VALIDATED_ZERO_FUTURE_SUPPORT_DOMAIN')
    actions = _past_action_pattern(packet.completed_doses)
    if not any(domain['observed_past_actions'] == actions for domain in matched):
        raise ValueError('ZERO_FUTURE_PAST_ACTION_PATTERN_DIFFERS_FROM_VALIDATED_DOMAIN')


def fit_unassisted_baseline(recording, spec=SparseBaselineSpec()):
    if recording.get('observed_dose') or any(any(f.signed_routes) for f in recording.get('planned_frames', ())):
        raise ValueError('Unassisted measured calibration only')
    if recording.get('cadence_hz', 1.) != 1. or recording.get('task_time_offset_s', 0.) != 0.:
        raise ValueError('This baseline fits the declared nominal instruction only')
    positions = recording['measurements']
    if len(positions) != 2400:
        raise ValueError('Declared twelve-second measured calibration required')
    observations = [SimpleNamespace(available_time_s=p.available_s, external_measurement_time_s=p.support_s,
        external_position_m=p.position_m, external_valid=p.valid) for p in positions]
    model = fit_known_cue_forecast(observations, CueConfig())
    return {'schema': 'scci_rh.stage3.zero-future-baseline.v1', 'training_recording_id': recording['recording_id'],
        'training_noise_identity': recording['measurement_noise_id'], 'specification': asdict(spec),
        'forecaster': model, 'context_validation': {},
        'source': 'external measured positions and known nominal instructions only',
        'candidate_future_command_included': False,
        'permissions': 'completed past monitored dose may strip/re-add observed response; no future measured body/dose, private gain/tau/state or paired baseline'}


def _validate(packet, target, spec):
    if not isinstance(packet, ZeroFutureInput) or len(packet.history) != spec.history_rows:
        raise ValueError('Complete sanitized external history required')
    if not np.all(np.isfinite([packet.now_s, target, packet.committed_zero_until_s,
                              packet.cadence_hz, packet.task_time_offset_s])):
        raise ValueError('Nonfinite baseline clocks/instruction')
    if packet.cadence_hz != 1. or packet.task_time_offset_s != 0. or packet.family not in FAMILIES:
        raise ValueError('UNSUPPORTED_INSTRUCTION_OR_ACTION_FAMILY')
    if target < packet.now_s-1e-12 or target > packet.committed_zero_until_s+1e-12:
        raise ValueError('NO_VALID_ZERO_FUTURE_COMMAND_COMMITMENT')
    previous_support = previous_available = -np.inf
    for row in packet.history:
        if (not isinstance(row, ResponsePosition) or np.asarray(row.position_m).shape != (2,)
                or not row.valid or not np.all(np.isfinite([row.support_s, row.available_s, *row.position_m]))
                or row.support_s > row.available_s or row.available_s > packet.now_s+1e-12
                or row.support_s <= previous_support or row.available_s <= previous_available):
            raise ValueError('Invalid, future or replayed external history')
        if np.isfinite(previous_support) and abs(row.support_s-previous_support-spec.sample_s) > 1e-9:
            raise ValueError('External support gap')
        previous_support, previous_available = row.support_s, row.available_s
    if packet.now_s-packet.history[-1].support_s > .050+1e-12:
        raise ValueError('Stale external history')
    if packet.family == 'unassisted_nominal' and packet.completed_doses:
        raise ValueError('Unassisted family cannot contain a delivered pulse')
    frames = sorted({round(d.frame_time_s/.025) for d in packet.completed_doses})
    if packet.family == 'isolated_nominal' and len(frames) > 1:
        raise ValueError('Isolated action family has multiple delivered frames')
    if packet.family.startswith('sparse_') and any(b-a < 8 for a, b in zip(frames, frames[1:])):
        raise ValueError('Sparse family requires at least eight40Hzframes between actions')
    if packet.family == 'sparse_individual_nominal' and len(frames) != len(packet.completed_doses):
        raise ValueError('Individual sparse family cannot contain simultaneous routes')


def predict_zero_future(model, dynamic_model, packet, horizon_s, *, context_id=None,
                        require_qualified=True, spec=SparseBaselineSpec()):
    if not isinstance(packet, ZeroFutureInput) or len(packet.history) != spec.history_rows:
        raise ValueError('Complete sanitized external history required')
    index = round(horizon_s/spec.sample_s)
    if (not np.isfinite(horizon_s) or abs(index*spec.sample_s-horizon_s) > 1e-9
            or not 5 <= index <= 30):
        raise ValueError('Execution horizon must be25..150ms on the5ms support grid')
    support = packet.history[-1].support_s
    target = support+horizon_s
    _validate(packet, target, spec)
    supports = [row.support_s for row in packet.history]+[target]
    past = predict_observed_past_response(dynamic_model, packet.now_s, supports, packet.completed_doses)
    mean = np.asarray(past['response_m']); uncertainty = np.asarray(past['joint_gain_dose_error_m'])
    stripped = np.asarray([p.position_m for p in packet.history])-mean[:-1]
    features = np.r_[stripped[::-1].ravel(), task_basis(support), task_basis(target)]
    fitted = model['forecaster']['models'][index]
    scale, weights = np.asarray(fitted['scale']), np.asarray(fitted['weights'])
    standardized = (features-np.asarray(fitted['mean']))/scale
    if not np.all(np.isfinite(standardized)) or np.max(abs(standardized)) > spec.feature_limit:
        raise ValueError('STRIPPED_HISTORY_OUTSIDE_FITTED_FEATURE_DOMAIN')
    free_prediction = np.r_[1., standardized]@weights
    history_error = uncertainty[:-1][::-1].ravel()@np.abs(weights[1:33]/scale[:32, None])
    propagated = history_error+uncertainty[-1]
    training_base = fitted['empirical_error_allocation_m']
    total = training_base+propagated
    if require_qualified:
        context = model['context_validation'].get(context_id)
        if (context is None or not context['qualified'] or context['family'] != packet.family
                or context['dynamic_model_id'] != dynamic_model.model_id):
            raise ValueError('INDEPENDENT_ZERO_FUTURE_CONTEXT_UNQUALIFIED')
        checked = context['horizons'][index-5]
        _require_eligible_domain(checked, packet, spec)
        residual_base = max(training_base, checked['maximum_component_residual_m']+spec.label_allowance_m)
        total = np.maximum(checked['empirical_error_allocation_m'], residual_base+propagated)
        if not fitted['qualified'] or not checked['qualified']:
            raise ValueError('ZERO_FUTURE_FORECAST_HORIZON_UNQUALIFIED')
        if not np.all(np.isfinite(total)) or np.max(total) > spec.forecast_limit_m:
            raise ValueError('ZERO_FUTURE_FORECAST_INTERVAL_EXCEEDS15MM')
    return {'baseline_contract': 'ZERO_FUTURE_COMMAND_BASELINE', 'support_s': support,
        'target_support_s': target, 'horizon_s': horizon_s,
        'position_m': free_prediction+mean[-1], 'stripped_unassisted_prediction_m': free_prediction,
        'ongoing_observed_past_response_m': mean[-1], 'history_strip_interval_projection_m': history_error,
        'target_past_response_interval_m': uncertainty[-1], 'total_forecast_allocation_m': total,
        'qualified_for_context': bool(require_qualified), 'context_id': context_id,
        'candidate_future_response_included': False, 'neural_used': False,
        'future_measured_position_used': False, 'future_measured_dose_used': False,
        'dynamic_model_id': dynamic_model.model_id}


def validate_zero_future_recording(model, dynamic_model, recording, spec=SparseBaselineSpec()):
    if (recording['recording_id'] == model['training_recording_id']
            or recording['measurement_noise_id'] == model['training_noise_identity']):
        raise ValueError('Independent complete recording/noise identity required')
    positions, doses, frames = recording['measurements'], recording['observed_dose'], recording['planned_frames']
    traces, horizons = [], []
    for hindex in range(5, 31):
        errors, intervals, reasons, eligible_domains = [], [], {}, []
        for index in range(15, len(positions)-hindex):
            current = positions[index]; target = current.support_s+hindex*spec.sample_s
            reason = None
            if current.support_s < spec.minimum_support_s:
                reason = 'INITIAL_WARMUP'
            elif any(d.frame_time_s <= current.available_s+1e-12 < d.available_s for d in doses):
                reason = 'PROFILE_MONITOR_NOT_YET_COMPLETE'
            future = [f.frame_time_s for f in frames if any(f.signed_routes)
                      and f.frame_time_s > current.available_s+1e-12]
            commitment = min(future, default=positions[-1].support_s)
            if target >= commitment-1e-12 and future:
                reason = reason or 'NONZERO_FUTURE_COMMAND_WITHIN_TARGET'
            past = tuple(d for d in doses if d.available_s <= current.available_s+1e-12)
            packet = ZeroFutureInput(current.available_s, tuple(positions[index-15:index+1]), past,
                commitment, recording['family'], recording.get('cadence_hz', 1.), recording.get('task_time_offset_s', 0.))
            predicted = None
            if reason is None:
                try:
                    predicted = predict_zero_future(model, dynamic_model, packet, hindex*spec.sample_s,
                                                    require_qualified=False)
                except ValueError as exc: reason = str(exc)
            if reason:
                reasons[reason] = reasons.get(reason, 0)+1
                traces.append({'index': index, 'horizon_index': hindex, 'eligible': False, 'reason': reason})
                continue
            # Scope records depend only on already-admitted physical supports
            # and completed action identities, before looking at target errors.
            _append_eligible_domain(eligible_domains, current.support_s,
                                    _past_action_pattern(past), spec)
            residual = np.asarray(predicted['position_m'])-np.asarray(positions[index+hindex].position_m)
            propagated = np.asarray(predicted['history_strip_interval_projection_m'])+predicted['target_past_response_interval_m']
            errors.append(residual); intervals.append(propagated)
            traces.append({'index': index, 'horizon_index': hindex, 'eligible': True,
                'prediction': predicted, 'measured_target_m': positions[index+hindex].position_m,
                'residual_m': residual})
        maximum = float(np.max(abs(np.asarray(errors)))) if errors else None
        maximum_interval = float(np.max(intervals)) if intervals else None
        training_base = model['forecaster']['models'][hindex]['empirical_error_allocation_m']
        allocation = max(training_base, maximum+spec.label_allowance_m)+maximum_interval if errors else None
        horizons.append({'horizon_s': hindex*spec.sample_s, 'eligible_rows': len(errors),
            'eligible_domains': eligible_domains,
            'excluded_rows': sum(reasons.values()), 'exclusion_reasons': reasons,
            'maximum_component_residual_m': maximum, 'maximum_propagated_past_interval_m': maximum_interval,
            'empirical_error_allocation_m': allocation,
            'qualified': bool(errors) and model['forecaster']['models'][hindex]['qualified']
                         and allocation <= spec.forecast_limit_m})
    context = {'recording_id': recording['recording_id'], 'family': recording['family'],
        'dynamic_model_id': dynamic_model.model_id, 'horizons': horizons,
        'qualified': all(h['qualified'] for h in horizons),
        'complete_recording_packets': len(positions), 'restricted_committed_intervals_only': True,
        'pre_action_candidate_controller_qualified': False,
        'zero_tail_after600ms_assumed': False, 'neural_used': False,
        'qualification_scope_contract': 'exact eligible5msphysical support and complete past frame/source/sign prefix; live measured dose and uncertainty remain inputs',
        'empirical_scope': 'all eligible known-zero-future intervals of this complete independent measured recording; no feedback or population guarantee'}
    model['context_validation'][recording['recording_id']] = context
    return {'context': context, 'trace': traces}
