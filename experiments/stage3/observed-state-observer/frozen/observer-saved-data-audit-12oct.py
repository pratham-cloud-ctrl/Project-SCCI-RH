"""Read-only saved result/target/coverage audit; no tuning or refitting."""
from pathlib import Path
import gzip
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
raw_path = ROOT/'tmp/observer-development-raw-12oct.json.gz'
summary_path = ROOT/'tmp/observer-development-summary-12oct.json'
raw = json.loads(gzip.decompress(raw_path.read_bytes()))
summary = json.loads(summary_path.read_text(encoding='utf-8'))
development_path = ROOT/'tmp/drift_forecast_exploratory_observations_12oct.json.gz'
calibration_path = ROOT/'tmp/phase_balanced_longcal_observations_12oct.json.gz'
development = json.loads(gzip.decompress(development_path.read_bytes()))['drifts']
calibration = json.loads(gzip.decompress(calibration_path.read_bytes()))['training']
receipt_path = ROOT/'tmp/observer-method-freeze-12oct.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert raw['method_receipt_sha256'] == summary['method_receipt_sha256'] == digest(receipt_path)
assert raw['implementation_sha256'] == summary['implementation_sha256'] == receipt['implementation_sha256'] == digest(ROOT/'tmp/observed_state_observer_12oct.py')
assert raw['protocol_sha256'] == summary['protocol_sha256'] == receipt['protocol_sha256'] == digest(ROOT/'tmp/observer-protocol-12oct.md')
assert raw['development_input_sha256'] == digest(development_path)
assert receipt['calibration_input_sha256'] == digest(calibration_path)
assert len(set(r['noise_id'] for r in development+calibration)) == 24
groups = {}
for group, records, raw_key, summary_key, first, count in (
    ('already_inspected_drift', development, 'development_forecasts','development',20,550),
    ('temporal_calibration_holdout', calibration,'temporal_calibration_holdout_forecasts','temporal_calibration_holdout',1620,750)):
    by_id = {r['id']:r for r in records}
    summary_by_id = {r['recording_id']:r for r in summary[summary_key]}
    categories = {c:[] for c in ('recent_75ms_spans_reversal','future_spans_reversal','neither_spans_reversal')}
    normalized, errors, variance_margin = [], [], []
    maximum_allocation, all_available = 0., True
    for saved in raw[raw_key]:
        record = by_id[saved['recording_id']]
        assert saved['measurement_noise_id'] == record['noise_id']
        indices = np.arange(first, first+count); horizons = np.arange(5,31)
        assert np.allclose(saved['current_supports_s'], indices*.005, rtol=0, atol=1e-14)
        assert np.allclose(saved['horizons_s'], horizons*.005, rtol=0, atol=1e-14)
        observed = np.array([r['position_m'] for r in record['measurements']])
        predicted = np.array(saved['predictions_m'])
        targets = observed[indices[:,None]+horizons[None,:]]
        assert predicted.shape == targets.shape == (count,26,2)
        assert np.array_equal(targets, np.array(saved['observed_targets_m']))
        residual = predicted-targets
        assert np.array_equal(residual, np.array(saved['observed_residuals_m']))
        allocation = np.max(abs(residual),axis=(0,2))+.003
        assert np.array_equal(allocation, saved['allocation_by_horizon_m'])
        maximum_allocation = max(maximum_allocation,float(allocation.max()))
        assert saved['maximum_allocation_m'] == float(allocation.max())
        i,h,foot = np.unravel_index(np.argmax(abs(residual)),residual.shape)
        assert saved['maximum_error_foot'] == foot
        assert abs(saved['maximum_error_current_support_s']-indices[i]*.005) < 1e-14
        assert abs(saved['maximum_error_target_support_s']-(indices[i]+horizons[h])*.005) < 1e-14
        assert abs(saved['maximum_error_horizon_s']-horizons[h]*.005) < 1e-14
        assert all(saved['forecast_available']) and len(saved['forecast_available']) == count
        all_available &= all(saved['forecast_available'])
        assert saved['current_support_count'] == saved['available_supports'] == count
        for key,value in summary_by_id[record['id']].items(): assert saved[key] == value
        p, n = np.array(saved['conditional_forecast_variances_m2']), np.array(saved['causal_sensor_noise_variances_m2'])
        assert np.isfinite(p).all() and np.isfinite(n).all() and p.min() >= 0 and n.min() >= 0
        assert np.min(p-n) > -1e-15
        variance_margin.append(float(np.min(p-n)))
        normalized.extend((abs(residual)/np.sqrt(p+.0015**2)).ravel().tolist())
        errors.extend(residual.ravel().tolist())
        for row,index in enumerate(indices):
            for column,horizon in enumerate(horizons):
                a,b,c = (index-15)*.005,index*.005,(index+horizon)*.005
                if any(a < 2*k <= b+1e-12 for k in range(int(a//2),int(c//2)+1)):
                    category = 'recent_75ms_spans_reversal'
                elif any(b < 2*k <= c+1e-12 for k in range(int(b//2),int(c//2)+1)):
                    category = 'future_spans_reversal'
                else: category = 'neither_spans_reversal'
                categories[category].extend(residual[row,column].tolist())
    normalized, errors = np.array(normalized),np.array(errors)
    groups[group] = {'records':len(records),'current_supports':len(records)*count,
        'support_horizon_coordinate_residuals':len(errors),'all_supports_available':bool(all_available),
        'maximum_allocation_m':maximum_allocation,'observed_rmse_m':float(np.sqrt(np.mean(errors**2))),
        'conditional_variance_minus_sensor_variance_minimum_m2':min(variance_margin),
        'conditional_standardized_residual_maximum':float(normalized.max()),
        'fraction_observed_components_exceeding_three_conditional_sigmas':float(np.mean(normalized>3)),
        'categories':{key:{'coordinate_residuals':len(e),
            'maximum_observed_component_error_m':float(np.max(abs(np.array(e)))),
            'maximum_error_plus_3mm_m':float(np.max(abs(np.array(e))))+.003,
            'observed_rmse_m':float(np.sqrt(np.mean(np.array(e)**2)))} for key,e in categories.items()}}
result = {'schema':'scci_rh.tmp.observer-saved-data-audit.v1','passed':True,
    'audit_source_sha256':digest(Path(__file__)), 'raw_sha256':digest(raw_path),
    'summary_sha256':digest(summary_path),'groups':groups,
    'covariance_note':'Conditional Gaussian covariance is not an empirical bound. These standardized residual diagnostics do not tune settings or replace maximum-error gates.'}
(ROOT/'tmp/observer-saved-data-audit-12oct.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
