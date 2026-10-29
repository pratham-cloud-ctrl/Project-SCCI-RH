"""Measured finite-frame response identification, separate from body simulation.

Only externally measured positions, completed independent monitor records and
known whole-frame instructions enter this module. It does not import an ODE,
recruitment map, threshold, private body state or neural source generator.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import numpy as np


@dataclass(frozen=True)
class DynamicResponseSpec:
    sample_s: float = .005
    frame_s: float = .025
    complete_profile_s: float = .0005
    response_window_s: float = .600
    online_horizon_s: float = .150
    correction_limit_m: float = .025
    label_allowance_m: float = .003
    minimum_repeats_per_signed_route: int = 6

    def __post_init__(self):
        fixed = (.005, .025, .0005, .600, .150, .025, .003, 6)
        if tuple(asdict(self).values()) != fixed:
            raise ValueError('The finite-frame experiment freezes its clocks, exposure and allocations')


@dataclass(frozen=True)
class ResponsePosition:
    support_s: float
    available_s: float
    position_m: tuple[float, float]
    valid: bool = True


@dataclass(frozen=True)
class CompletedDose:
    frame_time_s: float
    available_s: float
    source_id: int
    route_sign: int
    measured_fraction: float
    uncertainty_fraction: float
    quality: str


@dataclass(frozen=True)
class FutureResponseFrame:
    frame_time_s: float
    signed_routes: tuple[int, int]
    known_since_s: float = 0.


@dataclass(frozen=True)
class ProspectiveDose:
    measured_fraction: float = 1.012
    uncertainty_fraction: float = .074
    qualification: str = 'UNQUALIFIED_NOMINAL_ASSUMPTION'

    def __post_init__(self):
        if (not np.all(np.isfinite([self.measured_fraction, self.uncertainty_fraction]))
                or self.measured_fraction <= 0 or self.uncertainty_fraction < 0
                or self.qualification not in {'UNQUALIFIED_NOMINAL_ASSUMPTION',
                    'UNQUALIFIED_FUTURE_MONITOR_ALLOCATION', 'ACTUAL_TRACE_REUSE_NOT_FUTURE_GUARANTEE'}):
            raise ValueError('Explicit finite prospective dose assumption required')


def _grid_index(time, step):
    if not np.isfinite(time) or abs(time/step-round(time/step)) > 1e-8:
        raise ValueError('Whole frame/sample grid required')
    return int(round(time/step))


def observed_view(recording, spec=DynamicResponseSpec()):
    """Exclude private evaluator data and preserve both physical/arrival clocks."""
    records = recording['measurements']
    baseline = recording['baseline_measurements']
    values = []
    for collection in (records, baseline):
        converted = [p if isinstance(p, ResponsePosition) else ResponsePosition(**p) for p in collection]
        if len(converted) < 80:
            raise ValueError('Complete observed response recording required')
        previous_support = previous_arrival = -np.inf
        for p in converted:
            if (np.asarray(p.position_m).shape != (2,) or not p.valid
                    or not np.all(np.isfinite([p.support_s, p.available_s, *p.position_m]))
                    or p.support_s > p.available_s or p.support_s <= previous_support
                    or p.available_s <= previous_arrival
                    or p.available_s-p.support_s > .050+1e-12):
                raise ValueError('Nonfinite, future, stale, invalid or replayed position')
            if np.isfinite(previous_support) and abs(p.support_s-previous_support-spec.sample_s) > 1e-9:
                raise ValueError('Response support gap')
            previous_support, previous_arrival = p.support_s, p.available_s
        values.append(converted)
    if len(values[0]) != len(values[1]) or any(a.support_s != b.support_s for a, b in zip(*values)):
        raise ValueError('Matched physical support required for baseline subtraction')
    doses = [d if isinstance(d, CompletedDose) else CompletedDose(**d) for d in recording['observed_dose']]
    seen = set()
    fit_available = max(p.available_s for collection in values for p in collection)
    for d in doses:
        key = (_grid_index(d.frame_time_s, spec.frame_s), d.source_id)
        if (key in seen or d.source_id not in (0, 1) or d.route_sign not in (-1, 1)
                or not np.all(np.isfinite([d.available_s, d.measured_fraction, d.uncertainty_fraction]))
                or d.measured_fraction <= d.uncertainty_fraction or d.uncertainty_fraction < 0
                or d.available_s < d.frame_time_s+spec.complete_profile_s-1e-12
                or d.available_s > fit_available or d.quality != 'VALID'):
            raise ValueError('Incomplete, future, duplicated or unqualified independent monitor record')
        seen.add(key)
    identity = recording['recording_identity']
    if set(identity) != {'measurement_noise_id', 'baseline_noise_id'}:
        raise ValueError('Explicit independent observation identities required')
    if identity['measurement_noise_id'] == identity['baseline_noise_id']:
        raise ValueError('Stimulated and baseline noise streams must be independent')
    return {'recording_id': recording['recording_id'], 'recording_identity': dict(identity), 'measurements': values[0],
            'baseline_measurements': values[1], 'observed_dose': doses}


@dataclass(frozen=True)
class DynamicResponseModel:
    model_id: str
    kernel_m_per_fraction: np.ndarray
    gain_uncertainty_m_per_fraction: np.ndarray
    repeat_sem_m_per_fraction: np.ndarray
    specification: DynamicResponseSpec
    training: dict

    def to_record(self):
        return {'schema': 'scci_rh.stage3.dynamic-response-model.v1', 'model_id': self.model_id,
                'kernel_m_per_fraction': self.kernel_m_per_fraction.tolist(),
                'gain_uncertainty_m_per_fraction': self.gain_uncertainty_m_per_fraction.tolist(),
                'repeat_sem_m_per_fraction': self.repeat_sem_m_per_fraction.tolist(),
                'specification': asdict(self.specification), 'training': self.training}


def response_model_from_record(record):
    """Load a separately provenance-verified receipt without adding privileges."""
    if record.get('schema') != 'scci_rh.stage3.dynamic-response-model.v1':
        raise ValueError('Unexpected finite response model schema')
    spec = DynamicResponseSpec(**record['specification'])
    arrays = [np.asarray(record[key], dtype=float) for key in (
        'kernel_m_per_fraction', 'gain_uncertainty_m_per_fraction', 'repeat_sem_m_per_fraction')]
    expected = (round(spec.response_window_s/spec.sample_s)+1, 2, 2)
    if (any(a.shape != expected or not np.all(np.isfinite(a)) for a in arrays)
            or np.any(arrays[1] < 0) or np.any(arrays[2] < 0)
            or not record['model_id'].startswith('SCCI_RH-S3-DYNAMIC-1:')):
        raise ValueError('Invalid finite response table or identity')
    for array in arrays: array.setflags(write=False)
    return DynamicResponseModel(record['model_id'], *arrays, spec, record['training'])


def fit_response_kernel(recordings, spec=DynamicResponseSpec(), *, protocol_id=None):
    """Offline fit from isolated signed-route pulses and measured subtraction.

    Each pair is a separately recorded stimulated/rest baseline trajectory. No
    future target is an online input. Repetition error is an empirical 2*SEM
    allocation, not a confidence interval or deterministic sensor bound.
    """
    views = [observed_view(r, spec) for r in recordings]
    noise_ids = [(v['recording_identity']['measurement_noise_id'], v['recording_identity']['baseline_noise_id']) for v in views]
    every_noise_id = [value for pair in noise_ids for value in pair]
    if (len({v['recording_id'] for v in views}) != len(views)
            or len(set(every_noise_id)) != len(every_noise_id)):
        raise ValueError('Independent recording and observation-noise identities required')
    n_lags = round(spec.response_window_s/spec.sample_s)+1
    grouped = {route: [] for route in (0, 1)}
    counts = {(route, sign): 0 for route in (0, 1) for sign in (-1, 1)}
    dose_means = {0: [], 1: []}; dose_unc = {0: [], 1: []}
    digest = hashlib.sha256(b'scci_rh.stage3.dynamic-response-model.v1')
    rows = 0
    for view in views:
        if len(view['observed_dose']) != 1:
            raise ValueError('Isolated one-pulse calibration required')
        d = view['observed_dose'][0]
        times = np.array([p.support_s for p in view['measurements']])
        indices = np.array([np.argmin(abs(times-(d.frame_time_s+k*spec.sample_s))) for k in range(n_lags)])
        if not np.allclose(times[indices], d.frame_time_s+np.arange(n_lags)*spec.sample_s, rtol=0., atol=1e-10):
            raise ValueError('Complete observed 600 ms pulse response required')
        measured = np.array([p.position_m for p in view['measurements']])
        baseline = np.array([p.position_m for p in view['baseline_measurements']])
        response = d.route_sign*(measured[indices]-baseline[indices])/d.measured_fraction
        grouped[d.source_id].append(response)
        counts[(d.source_id, d.route_sign)] += 1
        dose_means[d.source_id].append(d.measured_fraction)
        dose_unc[d.source_id].append(d.uncertainty_fraction)
        public = {key: [asdict(item) for item in value] if isinstance(value, list) else value
                  for key, value in view.items()}
        digest.update(json.dumps(public, sort_keys=True, separators=(',', ':')).encode())
        rows += len(times)
    if any(n < spec.minimum_repeats_per_signed_route for n in counts.values()):
        raise ValueError('Six independent repeats per positive/negative route required')
    kernel = np.zeros((n_lags, 2, 2)); sem = np.zeros_like(kernel); uncertainty = np.zeros_like(kernel)
    for route, trials in grouped.items():
        trials = np.asarray(trials)
        kernel[:, :, route] = np.mean(trials, axis=0)
        sem[:, :, route] = np.std(trials, axis=0, ddof=1)/np.sqrt(len(trials))
        # |true_gain - observed_gain| <= (response allocation + |G|*u_d)/(d-u_d).
        # Both measured denominator error and repeated-label residual are retained.
        minimum_dose, maximum_u = min(dose_means[route]), max(dose_unc[route])
        uncertainty[:, :, route] = (2*sem[:, :, route]*minimum_dose
                                    +abs(kernel[:, :, route])*maximum_u)/(minimum_dose-maximum_u)
    principal = []
    for route in (0, 1):
        window = kernel[:round(spec.online_horizon_s/spec.sample_s)+1, route, route]
        peak = int(np.argmax(window))
        principal.append({'route': route, 'peak_lag_s': peak*spec.sample_s,
                          'observed_peak_gain_m_per_fraction': float(window[peak]),
                          'gain_uncertainty_m_per_fraction': float(uncertainty[peak, route, route]),
                          'positive_directional_authority': bool(window[peak]-uncertainty[peak, route, route] > 0)})
    training = {'recording_ids': [v['recording_id'] for v in views],
                'observation_noise_ids': [list(ids) for ids in noise_ids],
                'signed_route_repeats': {f'{route}:{sign}': n for (route, sign), n in counts.items()},
                'measured_response_rows': n_lags*len(views), 'unique_external_rows_each_arm': rows,
                'pulse_count': len(views), 'physical_recording_seconds_each_arm': rows*spec.sample_s,
                'baseline_recording_seconds_additional': rows*spec.sample_s,
                'dose_mean_fraction_by_route': {str(k): float(np.mean(v)) for k, v in dose_means.items()},
                'dose_uncertainty_fraction_by_route': {str(k): max(v) for k, v in dose_unc.items()},
                'principal_directional_authority': principal,
                'repeat_allocation': '2*SEM over independent signed pulse/baseline recordings; empirical, not probability coverage',
                'calibration_uncertainty': '(2*SEM*d + abs(G)*dose_uncertainty)/(d-dose_uncertainty)',
                'fit_inputs': 'observed external positions, matched measured baseline, completed independent monitor records only',
                'identity_scope': 'source/spec/declared-recording protocol' if protocol_id is not None else 'within-host measured-input digest',
                'private_inputs_used': False, 'neural_used': False,
                'response_scope': 'finite whole-frame response, not a steady plateau gain or instantaneous pulse displacement'}
    for array in (kernel, sem, uncertainty): array.setflags(write=False)
    model_id = protocol_id if protocol_id is not None else 'SCCI_RH-S3-DYNAMIC-1:'+digest.hexdigest()[:20]
    if not isinstance(model_id, str) or not model_id.startswith('SCCI_RH-S3-DYNAMIC-1:'):
        raise ValueError('Explicit source-bound dynamic protocol identity required')
    return DynamicResponseModel(model_id, kernel, uncertainty, sem, spec, training)


def _convolve(model, support_times, frames, dose):
    times = np.asarray(support_times, dtype=float)
    if times.ndim != 1 or not np.all(np.isfinite(times)):
        raise ValueError('Finite physical response supports required')
    output = np.zeros((len(times), 2)); uncertainty = np.zeros_like(output)
    knots = np.arange(len(model.kernel_m_per_fraction))*model.specification.sample_s
    for frame in frames:
        lag = times-frame.frame_time_s
        active = (lag >= -1e-12)&(lag <= model.specification.response_window_s+1e-12)
        if not np.any(active): continue
        for route, sign in enumerate(frame.signed_routes):
            if not sign: continue
            g = np.column_stack([np.interp(lag[active], knots, model.kernel_m_per_fraction[:, foot, route]) for foot in (0, 1)])
            u = np.column_stack([np.interp(lag[active], knots, model.gain_uncertainty_m_per_fraction[:, foot, route]) for foot in (0, 1)])
            output[active] += sign*g*dose.measured_fraction
            # Joint product interval includes the gain*dose uncertainty cross term.
            uncertainty[active] += (u*dose.measured_fraction+abs(g)*dose.uncertainty_fraction
                                    +u*dose.uncertainty_fraction)
    return output, uncertainty


def predict_future_effect(model, now_s, target_support_s, frames, dose=ProspectiveDose()):
    """Add ONLY newly planned future commands to a zero-future-command baseline.

    Past response is already part of that baseline and cannot be added again.
    This API accepts no future monitored dose, future measurement or body state.
    """
    spec = model.specification
    frames = tuple(frames)
    if not isinstance(dose, ProspectiveDose):
        raise ValueError('Only an explicitly qualified prospective assumption is accepted; no future monitor input')
    if (not np.all(np.isfinite([now_s, target_support_s])) or target_support_s < now_s
            or target_support_s-now_s > spec.online_horizon_s+1e-12):
        raise ValueError('Finite 0..150 ms prospective physical horizon required')
    seen = set()
    for frame in frames:
        if not isinstance(frame, FutureResponseFrame):
            raise ValueError('Sanitized prospective whole-frame command required')
        key = _grid_index(frame.frame_time_s, spec.frame_s)
        if (key in seen
                or not np.isfinite(frame.known_since_s) or frame.known_since_s > now_s
                or frame.frame_time_s < now_s-1e-12 or frame.frame_time_s > target_support_s+1e-12
                or len(frame.signed_routes) != 2 or any(x not in (-1, 0, 1) for x in frame.signed_routes)):
            raise ValueError('Past/double-counted, unknown, duplicate or fractional future command')
        seen.add(key)
    effect, uncertainty = _convolve(model, [target_support_s], frames, dose)
    return {'effect_m': effect[0].tolist(), 'joint_gain_dose_error_m': uncertainty[0].tolist(),
            'model_id': model.model_id, 'target_support_s': target_support_s,
            'dose_assumption': asdict(dose), 'baseline_contract': 'ZERO_FUTURE_COMMAND_BASELINE',
            'future_monitor_used': False, 'future_measurement_used': False,
            'domain_qualification_must_be_checked_separately': True,
            'scope': 'conditional finite response; downstream baseline error and reference gates still apply'}


def predict_observed_past_response(model, now_s, physical_supports_s, completed_doses):
    """Mean/interval from ALL completed past doses for baseline strip/re-add.

    The caller must supply complete past monitor history. There is no qualified
    release rule after600ms: an older contribution is rejected, not dropped.
    No future or incomplete monitor evidence is accepted. Physical targets may
    be measured history supports or at most150ms after the current decision.
    """
    times = np.asarray(physical_supports_s, dtype=float)
    if (times.ndim != 1 or not len(times) or not np.isfinite(now_s) or not np.all(np.isfinite(times))
            or np.any(times < 0) or np.any(times > now_s+model.specification.online_horizon_s+1e-12)):
        raise ValueError('Finite past/0..150ms future physical supports required')
    total = np.zeros((len(times), 2)); error = np.zeros_like(total); seen = set()
    for dose in completed_doses:
        if not isinstance(dose, CompletedDose):
            raise ValueError('Sanitized completed dose required')
        key = (_grid_index(dose.frame_time_s, model.specification.frame_s), dose.source_id)
        if (key in seen or dose.source_id not in (0, 1) or dose.route_sign not in (-1, 1)
                or not np.all(np.isfinite([dose.available_s, dose.measured_fraction, dose.uncertainty_fraction]))
                or dose.measured_fraction <= 0 or dose.uncertainty_fraction < 0 or dose.quality != 'VALID'
                or dose.available_s < dose.frame_time_s+model.specification.complete_profile_s-1e-12
                or dose.available_s > now_s+1e-12):
            raise ValueError('Future, incomplete, duplicated or invalid past monitor')
        if np.any(times-dose.frame_time_s > model.specification.response_window_s+1e-12):
            raise ValueError('PAST_RESPONSE_OUTSIDE_MEASURED_WINDOW_NO_QUALIFIED_RELEASE')
        seen.add(key)
        routes = [0, 0]; routes[dose.source_id] = dose.route_sign
        assumption = ProspectiveDose(dose.measured_fraction, dose.uncertainty_fraction,
                                     'ACTUAL_TRACE_REUSE_NOT_FUTURE_GUARANTEE')
        mean, bound = _convolve(model, times, (FutureResponseFrame(dose.frame_time_s, tuple(routes)),), assumption)
        total += mean; error += bound
    return {'physical_support_s': times.tolist(), 'response_m': total.tolist(),
            'joint_gain_dose_error_m': error.tolist(), 'model_id': model.model_id,
            'future_monitor_used': False, 'complete_past_monitor_history_required': True,
            'domain_qualification_must_be_checked_separately': True,
            'release_after_response_window_qualified': False}


def validate_response_recording(model, recording, dose=ProspectiveDose()):
    view = observed_view(recording, model.specification)
    noise_ids = [view['recording_identity']['measurement_noise_id'], view['recording_identity']['baseline_noise_id']]
    training_noise_ids = {value for pair in model.training['observation_noise_ids'] for value in pair}
    if (view['recording_id'] in model.training['recording_ids']
            or any(value in training_noise_ids for value in noise_ids)):
        raise ValueError('Complete withheld recording/noise identity required')
    frames = [f if isinstance(f, FutureResponseFrame) else FutureResponseFrame(**f)
              for f in recording['planned_frames']]
    seen = set()
    for frame in frames:
        index = _grid_index(frame.frame_time_s, model.specification.frame_s)
        if (index in seen or frame.known_since_s != 0. or len(frame.signed_routes) != 2
                or any(x not in (-1, 0, 1) for x in frame.signed_routes)):
            raise ValueError('Validation must use its predeclared complete fixed-profile schedule')
        seen.add(index)
    times = np.array([p.support_s for p in view['measurements']])
    measured = np.array([p.position_m for p in view['measurements']])
    baseline = np.array([p.position_m for p in view['baseline_measurements']])
    predicted, uncertainty = _convolve(model, times, frames, dose)
    observed = measured-baseline
    residual = predicted-observed
    allocation = abs(residual)+model.specification.label_allowance_m+uncertainty
    authority = all(r['positive_directional_authority'] for r in model.training['principal_directional_authority'])
    qualified = bool(authority and np.max(allocation) < model.specification.correction_limit_m)
    return {'recording_id': view['recording_id'], 'qualified': qualified,
            'reason': 'FINITE_OBSERVED_RESPONSE_DOMAIN_QUALIFIED' if qualified else 'FINITE_RESPONSE_ERROR_OR_AUTHORITY_ALLOCATION_FAILED',
            'scored_physical_supports': len(times), 'measured_response_rmse_m': float(np.sqrt(np.mean(residual**2))),
            'maximum_measured_response_error_m': float(np.max(abs(residual))),
            'maximum_joint_gain_dose_error_m': float(np.max(uncertainty)),
            'maximum_empirical_error_allocation_m': float(np.max(allocation)),
            'correction_limit_m': model.specification.correction_limit_m,
            'label_allowance_m': model.specification.label_allowance_m,
            'dose_assumption': asdict(dose), 'prediction_used_future_monitor': False,
            'prediction_used_future_measurements': False,
            'scope': 'full independent measured trajectory; empirical error allocation, not worst-case biological coverage',
            'trace': {'physical_support_s': times.tolist(), 'observed_response_m': observed.tolist(),
                      'predicted_response_m': predicted.tolist(), 'joint_gain_dose_error_m': uncertainty.tolist(),
                      'empirical_error_allocation_m': allocation.tolist()}}
