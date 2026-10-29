"""Independent differential-equation and causal/noise checks; no drift targets."""
from pathlib import Path
import copy
import gzip
import json
import time
import numpy as np
from scipy.integrate import solve_ivp
import scipy
import observed_state_observer_12oct as candidate

STARTED = time.perf_counter()
ROOT = Path(__file__).resolve().parents[1]
receipt, model = candidate.load_frozen()
checks = {}


def oracle(a, b, diffusion):
    """Integrate Fdot=A(t)F and Qdot=AQ+QA' + GSG', independently."""
    f, q = np.eye(10), np.zeros((10, 10))
    d = np.zeros((10, 10)); d[2:, 2:] = diffusion
    cuts = [a, *[2*k for k in range(int(a//2)+1, int(np.ceil(b/2))) if a < 2*k < b], b]
    for left, right in zip(cuts[:-1], cuts[1:]):
        sign = (-1.)**int(((left+right)/2)//2)
        def derivative(t, values):
            basis = sign*np.array([np.sin(2*np.pi*t), np.cos(2*np.pi*t),
                                   np.sin(6*np.pi*t), np.cos(6*np.pi*t)])
            a_matrix = np.zeros((10, 10))
            a_matrix[0, 0] = a_matrix[1, 1] = -1/.060
            a_matrix[0, 2:6] = basis/.060
            a_matrix[1, 6:10] = basis/.060
            phi, covariance = values[:100].reshape(10, 10), values[100:].reshape(10, 10)
            return np.r_[(a_matrix@phi).ravel(),
                         (a_matrix@covariance+covariance@a_matrix.T+d).ravel()]
        solution = solve_ivp(derivative, (left, right), np.r_[f.ravel(), q.ravel()],
            method='DOP853', rtol=2e-12, atol=1e-15, max_step=.0005)
        assert solution.success
        f, q = solution.y[:100, -1].reshape(10, 10), solution.y[100:, -1].reshape(10, 10)
    return f, q


intervals = ((0, .005), (1.975, 2.), (1.995, 2.015), (1.93, 2.08),
             (2., 2.15), (3.995, 4.025), (8.1, 8.25))
propagation = []
for a, b in intervals:
    f = candidate.transition(a, b)
    q = candidate.process_covariance(a, b, model.diffusion, 16)
    of, oq = oracle(a, b, model.diffusion)
    q8 = candidate.process_covariance(a, b, model.diffusion, 8)
    m = (a+b)/2
    f1, f2 = candidate.transition(a, m), candidate.transition(m, b)
    q1 = candidate.process_covariance(a, m, model.diffusion, 16)
    q2 = candidate.process_covariance(m, b, model.diffusion, 16)
    row = {'start_s':a, 'stop_s':b,
        'independent_ode_F_maximum_absolute_difference':float(np.max(abs(f-of))),
        'independent_ode_Q_maximum_absolute_difference_m2':float(np.max(abs(q-oq))),
        'quadrature_8_16_Q_maximum_absolute_difference_m2':float(np.max(abs(q-q8))),
        'semigroup_F_maximum_absolute_difference':float(np.max(abs(f-f2@f1))),
        'semigroup_Q_maximum_absolute_difference_m2':float(np.max(abs(q-(f2@q1@f2.T+q2)))),
        'minimum_Q_eigenvalue_m2':float(np.linalg.eigvalsh(q).min())}
    assert row['independent_ode_F_maximum_absolute_difference'] < 1e-10
    assert row['independent_ode_Q_maximum_absolute_difference_m2'] < 1e-14
    assert row['quadrature_8_16_Q_maximum_absolute_difference_m2'] < 1e-14
    assert row['semigroup_F_maximum_absolute_difference'] < 1e-12
    assert row['semigroup_Q_maximum_absolute_difference_m2'] < 1e-14
    assert row['minimum_Q_eigenvalue_m2'] > -1e-14
    propagation.append(row)
checks['independent_propagation'] = propagation

# Arbitrary declared test state, not a private studied learner or evaluator truth.
test_state = np.array([.012, -.01, .065, -.021, .002, -.001, -.062, .019, -.002, .001])
of, _ = oracle(1.93, 2.08, np.zeros((8, 8)))
zero_noise_error = float(np.max(abs(candidate.transition(1.93, 2.08)@test_state-of@test_state)))
assert zero_noise_error < 1e-11
epsilon = 1e-9
reversal_difference = candidate.transition(2-epsilon, 2+epsilon)@test_state-test_state
assert np.max(abs(reversal_difference[:2])) < 1e-7
assert np.array_equal(reversal_difference[2:], np.zeros(8))
checks['zero_noise_and_reversal'] = {'independent_state_error_m':zero_noise_error,
    'position_change_across_2ns_reversal_interval_m':reversal_difference[:2].tolist(),
    'coefficient_change_m':reversal_difference[2:].tolist()}

cal = json.loads(gzip.decompress(candidate.CALIBRATION.read_bytes()))['training']
rows = cal[0]['measurements']


def snapshot(observer):
    return (observer.mean.copy(), observer.covariance.copy(), observer.support_index,
            observer.last_accepted, observer.last_available, observer.consecutive, observer.last_decision)


def unchanged(before, after):
    return np.array_equal(before[0], after[0], equal_nan=True) and np.array_equal(before[1], after[1], equal_nan=True) and before[2:] == after[2:]


observer = candidate.Observer(model)
for row in rows[:25]: assert observer.update(row, row['available_s'])['accepted']
rejections = []
invalids = [(copy.deepcopy(rows[25]), rows[25]['available_s']-.001, 'future_availability'),
            (copy.deepcopy(rows[24]), rows[24]['available_s'], 'out_of_order'),
            (dict(rows[25], valid=False), rows[25]['available_s'], 'invalid'),
            (dict(rows[25], support_s=-.005), rows[25]['available_s'], 'negative_support'),
            (dict(rows[25], available_s=rows[25]['support_s']-.001), rows[25]['available_s'], 'availability_before_support'),
            (dict(rows[25], support_s=rows[25]['support_s']+.0001), rows[25]['available_s'], 'off_clock'),
            (dict(rows[25], position_m=[float('nan'), 0]), rows[25]['available_s'], 'nonfinite_measurement'),
            (copy.deepcopy(rows[25]), float('nan'), 'nonfinite_decision')]
for row, now, label in invalids:
    before = snapshot(observer); result = observer.update(row, now)
    assert not result['accepted'] and unchanged(before, snapshot(observer))
    rejections.append(label)
for kind in ('negative_covariance', 'nonfinite_covariance', 'nonfinite_mean'):
    broken = candidate.Observer(model)
    if kind == 'negative_covariance': broken.covariance[0, 0] = -1.
    elif kind == 'nonfinite_covariance': broken.covariance[0, 0] = np.nan
    else: broken.mean[0] = np.nan
    before = snapshot(broken); result = broken.update(rows[0], rows[0]['available_s'])
    assert not result['accepted'] and unchanged(before, snapshot(broken))
    rejections.append(kind)
for kind in ('negative_prior', 'nonfinite_prior', 'negative_diffusion'):
    bad = copy.deepcopy(receipt)
    if kind == 'negative_prior': bad['prior_covariance_m2'][0][0] = -1.
    elif kind == 'nonfinite_prior': bad['prior_covariance_m2'][0][0] = float('nan')
    else: bad['coefficient_diffusion_m2_per_s'][0][0] = -1.
    try: candidate.Model(bad)
    except ValueError: rejections.append(kind)
    else: raise AssertionError('malformed prior accepted')
checks['rejected_without_state_mutation'] = rejections

gap = candidate.Observer(model)
for row in rows[:25]: gap.update(row, row['available_s'])
info = gap.update(rows[40], rows[40]['available_s'])
assert info['reason'] == 'GAP_RESET' and gap.consecutive == 1
assert np.array_equal(gap.mean[:2], rows[40]['position_m'])
assert np.array_equal(gap.covariance[:2, :2], candidate.R)
assert np.array_equal(gap.covariance[:2, 2:], np.zeros((2, 8)))
assert not gap.forecast(rows[40]['available_s'])['available']
for row in rows[41:55]: gap.update(row, row['available_s'])
assert gap.consecutive == 15 and not gap.forecast(rows[54]['available_s'])['available']
gap.update(rows[55], rows[55]['available_s'])
assert gap.consecutive == 16 and gap.forecast(rows[55]['available_s'])['available']
assert not gap.forecast(rows[55]['available_s']+.051)['available']
checks['gap_reset_startup_and_freshness'] = 'passed: reset sample counted once; sixteen consecutive samples required'

clock_observer = candidate.Observer(model)
for row in rows[:25]: clock_observer.update(row, row['available_s'])
latest = rows[24]['available_s']
future_decision = latest+.010
late_forecast = clock_observer.forecast(future_decision)
assert not late_forecast['available']
assert not late_forecast['target_not_before_decision'][0]
assert late_forecast['target_not_before_decision'][-1]
assert late_forecast['predictions_m'].shape == (26, 2)
before = snapshot(clock_observer)
short_delay = dict(rows[25], available_s=rows[25]['support_s'])
assert not clock_observer.update(short_delay, short_delay['available_s'])['accepted']
assert unchanged(before, snapshot(clock_observer))
assert not clock_observer.forecast(latest)['available']
assert clock_observer.last_decision == future_decision
checks['monotone_decision_and_future_physical_target_contract'] = 'passed: no past target eligible and no clock rollback'

# Names and forbidden fields do not enter update; unarrived poisoned samples rejected.
plain, poison = candidate.Observer(model), candidate.Observer(model)
for row in rows[:50]:
    plain.update(row, row['available_s'])
    altered = dict(row, family='bogus', theta=np.full((2,4), 1000).tolist(),
                   gain=1000, recording_id='different', future_position_m=[1e9, -1e9])
    poison.update(altered, row['available_s'])
before = snapshot(poison)
for row in rows[50:80]:
    altered = dict(row, position_m=[1e9, -1e9])
    assert not poison.update(altered, rows[49]['available_s'])['accepted']
assert unchanged(before, snapshot(poison))
assert unchanged(snapshot(plain), snapshot(poison))
assert np.array_equal(plain.forecast(rows[49]['available_s'])['predictions_m'],
                      poison.forecast(rows[49]['available_s'])['predictions_m'])
checks['future_poisoning_and_identifier_invariance'] = 'passed'

# Independent explicit past-measurement derivative weights versus recursive noise covariance.
noise_observer = candidate.Observer(model)
noise_covariance = np.zeros((10, 10)); weights = np.zeros((10, 1200))
noise_checks = []
for index, row in enumerate(rows[:600]):
    info = noise_observer.update(row, row['available_s'])
    assert not info['reset']
    if index:
        f, _ = model.step(index-1)
        weights = f@weights
        noise_covariance = f@noise_covariance@f.T
    gain = info['gain']; residual = np.eye(10)-gain@candidate.H
    weights = residual@weights
    weights[:, 2*index:2*index+2] += gain
    noise_covariance = residual@noise_covariance@residual.T+gain@candidate.R@gain.T
    if index in (20, 399, 400, 415, 569):
        covariance_from_weights = candidate.SIGMA**2*(weights@weights.T)
        error = float(np.max(abs(covariance_from_weights-noise_covariance)))
        assert error < 1e-16
        f_future = candidate.transition(index*candidate.DT, (index+30)*candidate.DT)
        future_weights = f_future[:2]@weights
        assert not np.any(future_weights[:, 2*(index+1):])
        noise_checks.append({'current_support_s':index*candidate.DT,
            'recursive_vs_explicit_weight_covariance_maximum_error_m2':error,
            '150ms_sensor_noise_sigma_m':(candidate.SIGMA*np.linalg.norm(future_weights, axis=1)).tolist(),
            'future_measurement_weights_exactly_zero':True})
        if index == 400:
            saved_weights = future_weights.copy()
            saved_prediction = noise_observer.forecast(row['available_s'])['predictions_m'][-1]
            saved_index = index

# Finite perturbation independently verifies weights are actual estimator derivatives.
perturbed = candidate.Observer(model)
delta = np.zeros(1200); delta[2*375+1] = .001
for index, row in enumerate(rows[:saved_index+1]):
    altered = dict(row, position_m=(np.array(row['position_m'])+delta[2*index:2*index+2]).tolist())
    perturbed.update(altered, row['available_s'])
actual_change = perturbed.forecast(rows[saved_index]['available_s'])['predictions_m'][-1]-saved_prediction
linear_change = saved_weights@delta
derivative_error = float(np.max(abs(actual_change-linear_change)))
assert derivative_error < 1e-12
checks['causal_measurement_noise'] = {'supports':noise_checks,
    'finite_perturbation_vs_explicit_derivative_error_m':derivative_error}

assert receipt['implementation_sha256'] == candidate.digest(Path(candidate.__file__))
assert receipt['protocol_sha256'] == candidate.digest(candidate.PROTOCOL)
assert receipt['calibration_input_sha256'] == candidate.digest(candidate.CALIBRATION)
summary = {'schema':'scci_rh.tmp.observer-independent-check.v1', 'date':'2026-10-12',
    'classification':'NONCONFIRMATORY_CHECKS_NO_DRIFT_TARGETS_LOADED',
    'method_receipt_sha256':candidate.digest(candidate.RECEIPT),
    'independent_check_source_sha256':candidate.digest(Path(__file__)),
    'scipy_version':scipy.__version__, 'checks':checks, 'passed':True,
    'elapsed_wall_seconds':time.perf_counter()-STARTED}
candidate.save_json(ROOT/'tmp/observer-independent-check-12oct.json', summary)
print(json.dumps(summary, indent=2))
