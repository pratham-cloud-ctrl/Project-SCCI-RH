"""ONE frozen observed-data observer; tmp-only, nonconfirmatory development."""
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
import argparse
import gzip
import hashlib
import json
import platform
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'tmp/observer-protocol-12oct.md'
CALIBRATION = ROOT / 'tmp/phase_balanced_longcal_observations_12oct.json.gz'
DEVELOPMENT = ROOT / 'tmp/drift_forecast_exploratory_observations_12oct.json.gz'
RECEIPT = ROOT / 'tmp/observer-method-freeze-12oct.json'
TAU, DT, SIGMA = .060, .005, .0015
PSD_ATOL, DIFFUSION_PSD_ATOL = 1e-12, 1e-14
R = np.eye(2) * SIGMA**2
H = np.eye(10)[:2]
HORIZONS = np.arange(5, 31)
POS = [0, 1]
THETA = list(range(2, 10))
BLOCK_STATE_INDICES = ([0, 2, 3, 4, 5], [1, 6, 7, 8, 9])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def checked_covariance(covariance, size, tolerance=PSD_ATOL):
    c = np.asarray(covariance, dtype=float)
    if (c.shape != (size, size) or not np.isfinite(c).all()
            or np.max(abs(c-c.T)) > tolerance):
        raise ValueError('nonfinite, asymmetric or malformed covariance')
    c = (c+c.T)/2
    values, vectors = np.linalg.eigh(c)
    if values.min() < -tolerance:
        raise ValueError('substantive negative covariance eigenvalue')
    if values.min() < 0:
        c = (vectors*np.maximum(values, 0))@vectors.T
    return c


def cue(t):
    omega = 2*np.pi
    direction = 1 if int((t + 1e-13)//2) % 2 == 0 else -1
    return direction*np.array([np.sin(omega*t), np.cos(omega*t),
                               np.sin(3*omega*t), np.cos(3*omega*t)])


def split_points(a, b):
    events = [2*k for k in range(int(np.floor(a/2))+1, int(np.ceil(b/2)))
              if a < 2*k < b]
    return [a, *events, b]


def convolution(a, b):
    """Exact constant-coefficient cue integral into position at b."""
    if b < a: raise ValueError('backwards propagation')
    out = np.zeros(4)
    cuts = split_points(a, b)
    for left, right in zip(cuts[:-1], cuts[1:]):
        direction = 1 if int(((left+right)/2)//2) % 2 == 0 else -1
        for j, frequency in enumerate((1., 3.)):
            omega = 2*np.pi*frequency
            integral = (np.exp(1j*omega*right)
                        - np.exp(-(right-left)/TAU + 1j*omega*left))/(1+1j*omega*TAU)
            integral *= direction*np.exp(-(b-right)/TAU)
            out[2*j:2*j+2] += (integral.imag, integral.real)
    return out


def transition(a, b):
    f = np.eye(10)
    f[0, 0] = f[1, 1] = np.exp(-(b-a)/TAU)
    j = convolution(a, b)
    f[0, 2:6] = j
    f[1, 6:10] = j
    return f


def process_covariance(a, b, diffusion, order=16):
    nodes, weights = np.polynomial.legendre.leggauss(order)
    q = np.zeros((10, 10))
    cuts = split_points(a, b)
    for left, right in zip(cuts[:-1], cuts[1:]):
        for n, w in zip(nodes, weights):
            u = left + (n+1)*(right-left)/2
            e = np.zeros((10, 8))
            e[2:] = np.eye(8)
            j = convolution(float(u), b)
            e[0, :4], e[1, 4:] = j, j
            q += w*(right-left)/2*(e@diffusion@e.T)
    return (q+q.T)/2


def measurements(record):
    rows = record['measurements']
    t = np.array([p['support_s'] for p in rows])
    y = np.array([p['position_m'] for p in rows])
    assert all(p['valid'] for p in rows)
    assert y.shape == (len(rows), 2) and np.isfinite(y).all()
    assert np.allclose(t, np.arange(len(rows))*DT, rtol=0, atol=1e-10)
    assert all(abs(p['available_s']-p['support_s']-.025) < 1e-10 for p in rows)
    return rows, t, y


def calibrate():
    # This input contains calibration observations only, no development targets.
    records = json.loads(gzip.decompress(CALIBRATION.read_bytes()))['training']
    assert len(records) == 8
    initial, initial_covariances, differences, blocks = [], [], [], []
    for record in records:
        rows, t, y = measurements(record)
        assert len(rows) == 2400
        estimates = []
        for block in range(4):
            first, stop = block*400, (block+1)*400
            a = float(t[first])
            design = np.array([np.r_[np.exp(-(u-a)/TAU), convolution(a, float(u))]
                               for u in t[first:stop]])
            beta, _, rank, singular = np.linalg.lstsq(design, y[first:stop], rcond=None)
            assert rank == 5
            state = np.r_[beta[0], beta[1:, 0], beta[1:, 1]]
            covariance = np.zeros((10, 10))
            hp = np.linalg.pinv(design, rcond=1e-12)
            covariance_per_foot = SIGMA**2*(hp@hp.T)
            for indices in BLOCK_STATE_INDICES:
                covariance[np.ix_(indices, indices)] = covariance_per_foot
            residual = design@beta-y[first:stop]
            blocks.append({'recording_id': record['id'], 'noise_id': record['noise_id'],
                'block_start_s': a, 'block_right_endpoint_excluded_s': a+2,
                'samples': 400, 'rank': int(rank), 'condition_number': float(singular[0]/singular[-1]),
                'observed_fit_rmse_m': float(np.sqrt(np.mean(residual**2))),
                'maximum_observed_fit_error_m': float(np.max(abs(residual))),
                'fitted_state_m': state.tolist(), 'sensor_only_ols_covariance_m2': covariance.tolist(),
                'observed_fit_residuals_m': residual.tolist()})
            estimates.append(state[2:])
            if block == 0:
                initial.append(state)
                initial_covariances.append(covariance)
        differences.extend(np.diff(estimates, axis=0))
    initial = np.array(initial)
    prior_mean = initial.mean(axis=0)
    prior_covariance = np.cov(initial, rowvar=False, ddof=1)+np.mean(initial_covariances, axis=0)
    differences = np.array(differences)
    assert differences.shape == (24, 8)
    diffusion = differences.T@differences/(24*2.)
    eigenvalues, eigenvectors = np.linalg.eigh((diffusion+diffusion.T)/2)
    assert eigenvalues.min() >= -1e-14
    diffusion = checked_covariance(diffusion, 8, DIFFUSION_PSD_ATOL)
    prior_covariance = checked_covariance(prior_covariance, 10)
    result = {'schema': 'scci_rh.tmp.observed-state-method-freeze.v1', 'date': '2026-10-12',
        'classification': 'FROZEN_NONCONFIRMATORY_DEVELOPMENT_METHOD',
        'protocol_sha256': digest(PROTOCOL), 'implementation_sha256': digest(Path(__file__)),
        'calibration_input_sha256': digest(CALIBRATION),
        'calibration_records': [{'id':r['id'], 'noise_id':r['noise_id']} for r in records],
        'total_declared_calibration_exposure_s':96., 'fit_exposure_s':64., 'temporal_holdout_exposure_s':32.,
        'new_training_seconds':0., 'new_independent_confirmation_seconds':0.,
        'settings':{'movement_tau_s':TAU, 'sample_interval_s':DT, 'sensor_noise_sigma_m':SIGMA,
            'quadrature_order':16, 'coefficient_drift_law':'zero_mean_brownian_observed_second_moment',
            'initialization':'one_common_measured_calibration_prior_each_trial',
            'gap_reset_if_gt_s':.050, 'required_consecutive_samples':16,
            'covariance_roundoff_psd_tolerance_m2':PSD_ATOL,
            'diffusion_roundoff_psd_tolerance_m2_per_s':DIFFUSION_PSD_ATOL,
            'forecast_budget_m':.015, 'label_allocation_m':.003, 'unchanged_combined_gate_m':.025},
        'capacity':{'persistent_state_means':10,'persistent_covariance_unique_entries':55,
            'persistent_covariance_stored_entries_python':100,'monotone_decision_clock_scalars':1,
            'common_prior_mean_entries':10,'common_prior_covariance_unique_entries':55,
            'diffusion_covariance_unique_entries':36,'learned_scalar_entries_total':101,
            'common_prior_covariance_stored_entries_python':100,
            'diffusion_covariance_stored_entries_python':64,
            'raw_history_rows_stored':0,'diagnostic_sensor_covariance_unique_entries':55,
            'deterministic_transition_cache_maximum_entries':1024,
            'deterministic_cache_float64_payload_maximum_bytes':1024*2*10*10*8},
        'prior_mean_m':prior_mean.tolist(), 'prior_covariance_m2':prior_covariance.tolist(),
        'coefficient_diffusion_m2_per_s':diffusion.tolist(),
        'diffusion_eigenvalues_m2_per_s':np.linalg.eigvalsh(diffusion).tolist(),
        'prior_covariance_eigenvalues_m2':np.linalg.eigvalsh(prior_covariance).tolist(),
        'calibration_block_fits':blocks,
        'forbidden_private_parameter_inputs_used':False,
        'runtime_record_identifier_selector':False,
        'limits':['Measured block drift is a heuristic prior with estimation/model error.',
            'All later sixteen targets are already inspected development data.',
            'Persistent prefix memory and exact synthetic dynamics differ from the old forty-input model.',
            'Desktop deterministic cache payload alone exceeds the 512 KB target RAM; no target-ready runtime claim.']}
    save_json(RECEIPT, result)
    return result


class Model:
    def __init__(self, receipt):
        self.mean = np.array(receipt['prior_mean_m'])
        if self.mean.shape != (10,) or not np.isfinite(self.mean).all():
            raise ValueError('invalid prior mean')
        self.covariance = checked_covariance(receipt['prior_covariance_m2'], 10)
        self.diffusion = checked_covariance(receipt['coefficient_diffusion_m2_per_s'], 8, DIFFUSION_PSD_ATOL)

    @lru_cache(maxsize=1024)
    def step(self, first):
        a, b = first*DT, (first+1)*DT
        return transition(a, b), process_covariance(a, b, self.diffusion)

    def propagate(self, mean, covariance, first, stop, *, process=True):
        mean, covariance = mean.copy(), covariance.copy()
        for index in range(first, stop):
            f, q = self.step(index)
            mean = f@mean
            covariance = f@covariance@f.T+(q if process else 0)
        return mean, checked_covariance((covariance+covariance.T)/2, 10)


class Observer:
    """No record/family/gain identifiers or future observation API exists here."""
    def __init__(self, model):
        self.model = model
        self.mean, self.covariance = model.mean.copy(), model.covariance.copy()
        self.support_index = 0
        self.last_accepted = None
        self.last_available = None
        self.last_decision = None
        self.consecutive = 0

    def update(self, measurement, decision_time_s):
        y = np.asarray(measurement['position_m'], dtype=float)
        support, available = float(measurement['support_s']), float(measurement['available_s'])
        if (not measurement['valid'] or y.shape != (2,) or not np.isfinite(y).all()
                or not np.isfinite([support, available, decision_time_s]).all()
                or support < 0 or available < support or available > decision_time_s+1e-12
                or (self.last_decision is not None and decision_time_s < self.last_decision-1e-12)):
            return {'accepted':False, 'reason':'INVALID_OR_NOT_AVAILABLE'}
        index = round(support/DT)
        if abs(index*DT-support) > 1e-10 or (self.last_accepted is not None and index <= self.last_accepted):
            return {'accepted':False, 'reason':'OFF_CLOCK_OR_OUT_OF_ORDER'}
        try:
            checked_covariance(self.covariance, 10)
            if not np.isfinite(self.mean).all(): raise ValueError('invalid mean')
        except ValueError:
            return {'accepted':False, 'reason':'INVALID_FILTER_STATE'}
        distance = index-(self.last_accepted if self.last_accepted is not None else 0)
        reset = distance > 10
        if reset:
            candidate_mean = np.r_[y, self.model.mean[2:]]
            candidate_covariance = np.zeros((10, 10))
            candidate_covariance[:2, :2] = R
            candidate_covariance[2:, 2:] = self.model.covariance[2:, 2:]
            candidate_consecutive = 1
            info = {'accepted':True, 'reason':'GAP_RESET', 'reset':True}
        else:
            prior_index = self.support_index
            candidate_mean, candidate_covariance = self.model.propagate(self.mean, self.covariance, prior_index, index)
            innovation_covariance = H@candidate_covariance@H.T+R
            gain = np.linalg.solve(innovation_covariance, H@candidate_covariance).T
            candidate_mean += gain@(y-H@candidate_mean)
            residual = np.eye(10)-gain@H
            candidate_covariance = residual@candidate_covariance@residual.T+gain@R@gain.T
            candidate_covariance = (candidate_covariance+candidate_covariance.T)/2
            candidate_consecutive = self.consecutive+1 if distance == 1 else 1
            info = {'accepted':True, 'reason':'UPDATED', 'reset':False, 'gain':gain,
                    'from_index':prior_index, 'to_index':index}
        candidate_covariance = checked_covariance(candidate_covariance, 10)
        if not np.isfinite(candidate_mean).all():
            return {'accepted':False, 'reason':'INVALID_CANDIDATE_STATE'}
        self.mean, self.covariance = candidate_mean, candidate_covariance
        self.consecutive = candidate_consecutive
        self.support_index = self.last_accepted = index
        self.last_available = available
        self.last_decision = float(decision_time_s)
        return info

    def forecast(self, decision_time_s):
        if not np.isfinite(decision_time_s): raise ValueError('invalid decision time')
        checked_covariance(self.covariance, 10)
        if not np.isfinite(self.mean).all(): raise ValueError('invalid filter mean')
        monotone = self.last_decision is None or decision_time_s >= self.last_decision-1e-12
        targets = (self.support_index+HORIZONS)*DT
        target_not_before_decision = targets >= decision_time_s-1e-12
        available = (self.consecutive >= 16 and self.last_available is not None
                     and decision_time_s >= self.last_available-1e-12
                     and decision_time_s-self.last_available <= .050+1e-12
                     and monotone and bool(target_not_before_decision.all()))
        mean, covariance = self.mean.copy(), self.covariance.copy()
        means, variances = [], []
        for offset in range(1, 31):
            f, q = self.model.step(self.support_index+offset-1)
            mean = f@mean
            covariance = f@covariance@f.T+q
            covariance = checked_covariance((covariance+covariance.T)/2, 10)
            if offset >= 5:
                means.append(mean[:2].copy())
                variances.append(np.diag(covariance)[:2].copy())
        if monotone: self.last_decision = float(decision_time_s)
        return {'available':available, 'predictions_m':np.array(means),
                'conditional_variances_m2':np.array(variances),
                'target_supports_s':targets, 'target_not_before_decision':target_not_before_decision,
                'current_support_s':self.support_index*DT}


def load_frozen():
    receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
    assert receipt['protocol_sha256'] == digest(PROTOCOL)
    assert receipt['implementation_sha256'] == digest(Path(__file__))
    assert receipt['calibration_input_sha256'] == digest(CALIBRATION)
    return receipt, Model(receipt)


def reversal_category(index, target):
    a, b, t = (index-15)*DT, index*DT, target*DT
    if any(a < 2*k <= b+1e-12 for k in range(int(a//2), int(t//2)+1)):
        return 'recent_75ms_spans_reversal'
    if any(b < 2*k <= t+1e-12 for k in range(int(b//2), int(t//2)+1)):
        return 'future_spans_reversal'
    return 'neither_spans_reversal'


def evaluate_record(model, record, first_index, last_index):
    rows, times, observed = measurements(record)
    observer, sensor_covariance = Observer(model), np.zeros((10, 10))
    forecasts, variances, noise_variances, indices, available, min_eigenvalues = [], [], [], [], [], []
    for index, row in enumerate(rows[:last_index+1]):
        info = observer.update(row, row['available_s'])
        assert info['accepted']
        if info['reset']:
            sensor_covariance = np.zeros((10, 10)); sensor_covariance[:2, :2] = R
        else:
            _, sensor_covariance = model.propagate(np.zeros(10), sensor_covariance,
                info['from_index'], info['to_index'], process=False)
            gain = info['gain']; residual = np.eye(10)-gain@H
            sensor_covariance = residual@sensor_covariance@residual.T+gain@R@gain.T
        min_eigenvalues.append(float(np.linalg.eigvalsh(observer.covariance).min()))
        if index < first_index: continue
        prediction = observer.forecast(row['available_s'])
        forecasts.append(prediction['predictions_m'])
        variances.append(prediction['conditional_variances_m2'])
        indices.append(index); available.append(prediction['available'])
        n = sensor_covariance.copy(); forecast_noise = []
        for offset in range(1, 31):
            f, _ = model.step(index+offset-1); n = f@n@f.T
            if offset >= 5: forecast_noise.append(np.diag(n)[:2].copy())
        noise_variances.append(forecast_noise)
    indices = np.array(indices); forecasts = np.array(forecasts)
    targets = observed[indices[:, None]+HORIZONS[None, :]]
    error = forecasts-targets
    peak_i, peak_h, peak_foot = np.unravel_index(np.argmax(abs(error)), error.shape)
    allocations = np.max(abs(error), axis=(0, 2))+.003
    categories = {}
    for category in ('recent_75ms_spans_reversal','future_spans_reversal','neither_spans_reversal'):
        selected = np.array([[reversal_category(i, i+h) == category for h in HORIZONS] for i in indices])
        e = error[selected]
        categories[category] = {'support_horizon_count':int(selected.sum()),
            'maximum_observed_component_error_m':float(np.max(abs(e))) if e.size else None,
            'observed_rmse_m':float(np.sqrt(np.mean(e**2))) if e.size else None}
    summary = {'recording_id':record['id'], 'measurement_noise_id':record['noise_id'],
        'current_support_count':len(indices), 'horizon_count':26, 'available_supports':sum(available),
        'maximum_allocation_m':float(allocations.max()),
        'all_horizons_within_budget_development':bool(all(available) and np.all(allocations <= .015)),
        'allocation_by_horizon_m':allocations.tolist(), 'observed_rmse_m':float(np.sqrt(np.mean(error**2))),
        'maximum_error_current_support_s':float(times[indices[peak_i]]),
        'maximum_error_target_support_s':float(times[indices[peak_i]+HORIZONS[peak_h]]),
        'maximum_error_horizon_s':float(HORIZONS[peak_h]*DT), 'maximum_error_foot':int(peak_foot),
        'conditional_forecast_sigma_maximum_m':float(np.sqrt(np.maximum(variances, 0)).max()),
        'causal_sensor_noise_sigma_maximum_m':float(np.sqrt(np.maximum(noise_variances, 0)).max()),
        'minimum_filter_covariance_eigenvalue_m2':min(min_eigenvalues), 'categories':categories}
    raw = {**summary, 'current_supports_s':times[indices].tolist(),
        'horizons_s':(HORIZONS*DT).tolist(), 'forecast_available':available,
        'predictions_m':forecasts.tolist(), 'observed_targets_m':targets.tolist(),
        'observed_residuals_m':error.tolist(), 'conditional_forecast_variances_m2':np.array(variances).tolist(),
        'causal_sensor_noise_variances_m2':np.array(noise_variances).tolist()}
    return summary, raw


def score(review_reference):
    started = time.perf_counter()
    receipt, model = load_frozen()
    assert review_reference.strip()
    data = json.loads(gzip.decompress(DEVELOPMENT.read_bytes()))
    records = data['drifts']
    assert len(records) == 16
    cal = json.loads(gzip.decompress(CALIBRATION.read_bytes()))['training']
    assert not ({r['noise_id'] for r in records}&{r['noise_id'] for r in cal})
    summaries, raw = [], []
    for record in records:
        print('Development only: '+record['id'], flush=True)
        s, r = evaluate_record(model, record, 20, 569); summaries.append(s); raw.append(r)
    temporal, temporal_raw = [], []
    for record in cal:
        s, r = evaluate_record(model, record, 1620, 2369); temporal.append(s); temporal_raw.append(r)
    summary = {'schema':'scci_rh.tmp.observed-state-development.v1','date':'2026-10-12',
        'classification':'NONCONFIRMATORY_OBSERVED_STATE_DEVELOPMENT',
        'method_receipt_sha256':digest(RECEIPT), 'protocol_sha256':digest(PROTOCOL),
        'implementation_sha256':digest(Path(__file__)), 'development_input_sha256':digest(DEVELOPMENT),
        'review_reference':review_reference,'independent_confirmation_performed':False,
        'forbidden_private_inputs_used':False,'new_observed_training_seconds':0.,
        'new_independent_confirmation_seconds':0., 'runtime_or_gate_changes':False,
        'declared_calibration_exposure_s':96.,'capacity':receipt['capacity'],
        'development_record_count':16,'development_all_horizon_passes':sum(s['all_horizons_within_budget_development'] for s in summaries),
        'maximum_development_allocation_m':max(s['maximum_allocation_m'] for s in summaries),
        'maximum_temporal_calibration_holdout_allocation_m':max(s['maximum_allocation_m'] for s in temporal),
        'temporal_calibration_holdout_all_horizon_passes':sum(s['all_horizons_within_budget_development'] for s in temporal),
        'development':summaries,'temporal_calibration_holdout':temporal,
        'elapsed_wall_seconds':time.perf_counter()-started,
        'python_version':platform.python_version(),'numpy_version':np.__version__,
        'transition_cache':model.step.cache_info()._asdict(),
        'limits':['Already inspected targets: development, not fresh qualification.',
            'No combined-correction, stimulation, neural-increment or retained-learning test performed.',
            'Exact 60 ms dynamics and noise are conditional synthetic structural assumptions.',
            'Persistent prefix state differs from the old stateless 75 ms predictor.']}
    save_json(ROOT/'tmp/observer-development-summary-12oct.json', summary)
    (ROOT/'tmp/observer-development-raw-12oct.json.gz').write_bytes(gzip.compress(json.dumps(
        {**summary,'development_forecasts':raw,'temporal_calibration_holdout_forecasts':temporal_raw},
        separators=(',',':'),allow_nan=False).encode(),mtime=0))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('development','temporal_calibration_holdout')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--calibrate', action='store_true')
    parser.add_argument('--score-after-review')
    args = parser.parse_args()
    if args.calibrate:
        started = time.perf_counter(); r = calibrate()
        print(json.dumps({k:v for k,v in r.items() if k not in ('calibration_block_fits',
            'prior_covariance_m2','coefficient_diffusion_m2_per_s')}, indent=2))
        print('Calibration elapsed seconds:',time.perf_counter()-started)
    elif args.score_after_review:
        score(args.score_after_review)
    else:
        parser.error('Choose calibration or an explicitly reviewed development score')
