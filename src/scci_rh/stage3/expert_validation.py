"""Observed competence audit and separately privileged synthetic teacher benchmark.

Teacher generation may use the private reduced body's movement time constant.
That privilege is NOT available to decoders or competence qualification. Existing
expert libraries and historical study artifacts are not replaced by this module.
"""
from collections import deque
from dataclasses import asdict
import hashlib
from unittest.mock import patch
import numpy as np
from . import acquisition as acquisition_module
from .acquisition import AcquisitionConfig, ContactAcquisition
from .motor import MotorConfig, Observation, _World, _metrics, _fit_neural, task_goal

GENERATORS = ('legacy_voluntary', 'idealized_inverse')


def inverse_teacher_coefficients(config, *, heldout=False):
    """GENERATOR ONLY: inverse of dx/dt=(voluntary-x)/tau between task jumps.

    For x*=A sin(omega t), voluntary=x*+tau dx*/dt. Task direction changes
    remain finite-response discontinuities: this does not cancel their jumps.
    """
    omega = 2*np.pi*(1.15 if heldout else 1.)
    row = np.array([config.foot_amplitude_m,
                    config.foot_amplitude_m*config.movement_tau_s*omega, 0., 0.])
    return np.array([row, -row])


def qualify_observed_expert(external_records, config, *, heldout=False):
    """Only observed external coordinates/support plus declared task thresholds."""
    records = list(external_records)
    if len(records) < 80:
        return {'qualified': False, 'reason': 'INSUFFICIENT_EXTERNAL_RECORDS', 'metrics': None}
    times = np.array([row['support_time_s'] for row in records], dtype=float)
    positions = np.array([row['position_m'] for row in records], dtype=float)
    arrivals = np.array([row['available_time_s'] for row in records], dtype=float)
    valid = np.array([row['valid'] for row in records], dtype=bool)
    if (positions.shape != (len(records), 2) or not np.all(np.isfinite(times))
            or not np.all(np.isfinite(positions)) or not np.all(np.isfinite(arrivals))
            or not np.all(valid) or np.any(np.diff(times) <= 0)
            or np.any(times > arrivals) or np.any(arrivals-times > config.external_freshness_s)):
        return {'qualified': False, 'reason': 'EXTERNAL_RECORDS_INVALID_OR_STALE', 'metrics': None}
    metrics = _metrics(times, positions, config, heldout=heldout)
    spatial = metrics['contact_spatial_rmse_m']
    timing = metrics['contact_timing_rmse_s']
    qualified = (metrics['scored_contact_events'] > 0 and spatial is not None and timing is not None
                 and spatial <= config.retention_spatial_threshold_m
                 and timing <= config.retention_timing_threshold_s)
    failures = []
    if spatial is None or spatial > config.retention_spatial_threshold_m:
        failures.append('SPATIAL_THRESHOLD_FAILED')
    if timing is None or timing > config.retention_timing_threshold_s:
        failures.append('TIMING_THRESHOLD_FAILED')
    if not metrics['scored_contact_events']:
        failures.append('NO_SCORED_CONTACT_EVENTS')
    return {'qualified': bool(qualified),
            'reason': 'OBSERVED_TASK_COMPETENT' if qualified else '+'.join(failures),
            'metrics': metrics,
            'thresholds': {'contact_spatial_rmse_m': config.retention_spatial_threshold_m,
                           'contact_timing_rmse_s': config.retention_timing_threshold_s},
            'scope': 'measured external task performance; no private body truth supplied'}


def capture_expert_performance(performance_seed, config=MotorConfig(), *,
                               generator='legacy_voluntary', heldout=False,
                               subject_seed=51000, duration_s=12.):
    """Capture a fresh performance, same geometry, independent observed noise.

    Full observations and external records are public inputs. Separate private
    evaluator records identify acquisition START states and ideal-body errors.
    A forwarding-only filter call witness hashes every chronological synthetic
    input voltage aperture and retains first/last blocks; no voltage is replaced.
    """
    if generator not in GENERATORS:
        raise ValueError('unknown teacher generator')
    if not np.isfinite(duration_s) or duration_s < .4:
        raise ValueError('finite duration with contact-assessment support required')
    c = config
    world = _World(subject_seed, c, heldout=heldout)
    world.theta = (inverse_teacher_coefficients(c, heldout=heldout)
                   if generator == 'idealized_inverse' else
                   np.array([[c.foot_amplitude_m, 0., 0., 0.],
                             [-c.foot_amplitude_m, 0., 0., 0.]]))
    acq = ContactAcquisition(subject_seed+8300,
                             AcquisitionConfig(source_mode=c.source_mode,
                                               qualification_mode=c.acquisition_qualification_mode,
                                               clock_uncertainty_s=c.acquisition_clock_uncertainty_s),
                             noise_seed=performance_seed+17001)
    rng = np.random.default_rng(performance_seed+9200)
    delay = int(round(c.external_delay_s/c.dt_s))
    history = deque([np.zeros(2) for _ in range(delay+1)], maxlen=delay+1)
    observations, records, evaluator = [], [], []
    input_hash = hashlib.sha256()
    first_block, last_block, aperture_count = None, None, 0
    original_filter = acquisition_module.sosfilt
    def witnessed_filter(sos, values, *args, **kwargs):
        nonlocal first_block, last_block, aperture_count
        value = np.asarray(values, dtype=float)
        if value.shape != (20, 16):
            raise AssertionError('unexpected acquisition filter input support')
        input_hash.update(np.asarray(value, dtype='<f8').tobytes())
        aperture_count += value.size
        if first_block is None:
            first_block = value.copy().tolist()
        last_block = value.copy().tolist()
        return original_filter(sos, values, *args, **kwargs)
    with patch.object(acquisition_module, 'sosfilt', witnessed_filter):
        for k in range(int(round(duration_s/c.dt_s))):
            t = k*c.dt_s
            history.append(world.x.copy())
            measured = history[0]+rng.normal(0, c.external_noise_m, 2)
            # Both voltage-source coordinates are the state at this block's
            # start. The future endpoint cannot populate earlier apertures.
            neural = acq.observe(t, world.x/c.foot_amplitude_m,
                                  world.v/(2*np.pi*c.foot_amplitude_m),
                                  external_redundant_state=measured/c.foot_amplitude_m)
            observation = Observation(t+c.dt_s, tuple(measured), t-c.external_delay_s,
                                      True, neural)
            observations.append(observation)
            records.append({'support_time_s': observation.external_measurement_time_s,
                            'available_time_s': observation.available_time_s,
                            'position_m': measured.tolist(), 'valid': True})
            evaluator.append({'source_state_time_s': t, 'position_m': world.x.tolist(),
                              'velocity_m_per_s': world.v.tolist(),
                              'task_goal_m': task_goal(t, c, heldout).tolist()})
            world.advance(t+c.dt_s, np.zeros(2), 'zero', learning=False, heldout=heldout)
    private_metrics = _metrics([r['source_state_time_s'] for r in evaluator],
                               [r['position_m'] for r in evaluator], c, heldout=heldout)
    return {'observations': observations, 'external_records': records,
            'qualification': qualify_observed_expert(records, c, heldout=heldout),
            'private_evaluator': {'records': evaluator, 'metrics': private_metrics,
                                  'scope': 'generation audit only; never controller or competence input'},
            'generation_metadata': {'generator': generator, 'performance_seed': int(performance_seed),
                                    'subject_seed': int(subject_seed), 'cadence_hz': 1.15 if heldout else 1.,
                                    'external_noise_seed': int(performance_seed+9200),
                                    'voltage_noise_seed': int(performance_seed+17001),
                                    'contact_geometry_seed': int(subject_seed+8300),
                                    'duration_s': duration_s, 'config': asdict(c),
                                    'privilege': 'PRIVATE_EXPERT_MOVEMENT_TAU_IN_GENERATOR_ONLY' if generator=='idealized_inverse' else 'declared amplitude voluntary template',
                                    'controller_receives': 'measured voltage-derived features, external labels and declared task',
                                    'controller_excludes': ['expert movement tau', 'expert theta', 'private body state'],
                                    'direction_change_scope': 'finite-response jumps retained; inverse valid between task discontinuities'},
            'voltage_acquisition_witness': {'filter_input_v_sha256': input_hash.hexdigest(),
                                           'aperture_samples': aperture_count,
                                           'streams': 16, 'sample_hz_per_stream': 4000.,
                                           'aperture_offset_s': 3e-6, 'source_hold_s': c.dt_s,
                                           'first_filter_input_v': first_block,
                                           'last_filter_input_v': last_block,
                                           'scope': 'every prefilter synthetic voltage hashed; first/last blocks retained; no raw neural measurements'}}


def fit_observed_teacher_decoder(capture):
    """Fit only Observation packets with partition-local measured labels."""
    return _fit_neural(capture['observations'])


def validate_observed_teacher_decoder(model, capture):
    """Independent performance labels; model/thresholds stay frozen."""
    selected = [o for o in capture['observations'] if o.neural.valid and o.external_valid]
    if model is None or len(selected) < 20:
        return {'available': False, 'reason': 'DECODER_OR_CAPTURE_UNAVAILABLE'}
    x = np.array([o.neural.values_uv for o in selected])
    y = np.array([o.external_position_m for o in selected])
    times = np.array([o.external_measurement_time_s for o in selected])
    velocity = np.gradient(y, times, axis=0)
    smoothed = np.column_stack([np.convolve(velocity[:, j], np.ones(9)/9, mode='same') for j in range(2)])
    z = (x-model['mean'])/model['scale']
    predicted = np.column_stack((np.ones(len(x)), z))@model['weights']
    keep = np.arange(4, len(x)-4)
    residual = predicted[keep]-np.column_stack((y, smoothed))[keep]
    return {'available': True, 'position_rmse_m': float(np.sqrt(np.mean(residual[:, :2]**2))),
            'velocity_rmse_m_per_s': float(np.sqrt(np.mean(residual[:, 2:]**2))),
            'scored_rows': len(keep), 'maximum_standardized_feature': float(np.max(np.abs(z[keep]))),
            'label_scope': 'independent measured external position and within-capture offline differentiated labels',
            'physical_support': 'same external physical support; no lower-latency neural state claimed',
            'performance_seed': capture['generation_metadata']['performance_seed'],
            'cadence_hz': capture['generation_metadata']['cadence_hz']}
