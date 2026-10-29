"""Saved confirmation audit only: never draws noise or regenerates a body."""
from pathlib import Path
import gzip
import hashlib
import json
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STARTED = time.perf_counter()
EXPECTED_FREEZE = '6e4725e801f3e7e9eb88d0c9e40520c6ea0b462f9776cf4adb5831d6d6dcbac0'
EXPECTED_PRODUCER = '7c7729caa49cac204c2edc8be81bc9ba11e3ae6b4ec2bd26ac129c18b087978d'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
freeze_path = ROOT/'tmp/observer-confirmation-freeze-12oct.json'
assert digest(freeze_path) == EXPECTED_FREEZE
freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
summary_path = ROOT/'tmp/observer-confirmation-summary-12oct.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
assert digest(ROOT/'tmp/observer-confirmation-12oct.py') == EXPECTED_PRODUCER == freeze['producer_evaluator_sha256']
assert digest(ROOT/'tmp/observer-confirmation-protocol-12oct.md') == freeze['protocol_sha256']
assert digest(ROOT/'tmp/observed_state_observer_12oct.py') == freeze['observer_source_sha256']
assert digest(ROOT/'tmp/observer-method-freeze-12oct.json') == freeze['method_receipt_sha256']
assert digest(ROOT/'tmp/phase_balanced_longcal_observations_12oct.json.gz') == freeze['calibration_input_sha256']
assert digest(ROOT/'tmp/drift_forecast_exploratory_observations_12oct.json.gz') == freeze['already_inspected_development_input_sha256']
actual_sources = {p.relative_to(ROOT).as_posix():digest(p) for p in sorted((ROOT/'src/scci_rh').rglob('*.py'))}
assert actual_sources == freeze['full_scci_rh_source_bytes_sha256']
for path,value in freeze['body_source_bytes_sha256'].items(): assert digest(ROOT/path) == value
expected_binding_keys = ('protocol_sha256','producer_evaluator_sha256','observer_source_sha256',
    'method_receipt_sha256','calibration_input_sha256','already_inspected_development_input_sha256',
    'body_source_bytes_sha256','full_scci_rh_source_bytes_sha256')
expected_bindings = {key:freeze[key] for key in expected_binding_keys}
assert summary['freeze_receipt_sha256'] == EXPECTED_FREEZE and summary['frozen_bindings'] == expected_bindings
assert summary['review_reference'] and 'observer-confirmation-root-review-12oct.md' in summary['review_reference']
assert len(freeze['cohort']) == len(summary['pair_files']) == len(summary['paired_grid_diagnostics']) == 16
noise_ids, noise_hashes, allocations, all_available, capture_passes = set(),set(),[],True,0
pair_audits, grid_diagnostics, capture_summaries = [],[],[]
indices, horizons = np.arange(20,570),np.arange(5,31)
count_residuals, injection_roundoff_max, maximum_file_size = 0,0.,0


def verify_peak(values, saved):
    location = np.unravel_index(np.argmax(abs(values)),values.shape)
    assert saved['array_index'] == list(location)
    assert saved['maximum_absolute_difference_m'] == float(np.max(abs(values)))
    if values.ndim == 3:
        i,h,foot = location
        assert abs(saved['current_support_s']-(20+i)*.005) < 1e-14
        assert abs(saved['horizon_s']-(5+h)*.005) < 1e-14
    else:
        i,foot = location
        assert abs(saved['support_s']-i*.005) < 1e-14
    assert saved['coordinate'] == foot


for condition,file_info,saved_grid in zip(freeze['cohort'],summary['pair_files'],summary['paired_grid_diagnostics']):
    index = condition['pair_index']
    assert file_info['path'] == freeze['expected_raw_pair_files'][index]
    path = ROOT/file_info['path']
    assert digest(path) == file_info['sha256']
    assert path.stat().st_size == file_info['bytes'] < 50*1024*1024
    maximum_file_size = max(maximum_file_size,file_info['bytes'])
    pair = json.loads(gzip.decompress(path.read_bytes()))
    assert pair['freeze_receipt_sha256'] == EXPECTED_FREEZE and pair['frozen_bindings'] == expected_bindings
    assert pair['review_reference'] == summary['review_reference']
    assert pair['condition_provenance'] == pair['producer_only']['condition'] == condition
    assert condition['subject_seed'] == 2 and condition['seconds'] == 3 and condition['learning']
    assert condition['dose'] == 'zero' and condition['body_integration_steps_s'] == [.0025,.00125]
    noise_id = condition['measurement_noise_id']
    assert noise_id not in noise_ids and noise_id not in freeze['excluded_prior_noise_ids']
    noise_ids.add(noise_id)
    noise = np.array(pair['producer_only']['shared_noise_samples_m'])
    assert noise.shape == (600,2) and np.isfinite(noise).all()
    noise_hash = hashlib.sha256(noise.astype('<f8').tobytes()).hexdigest()
    assert noise_hash == pair['producer_only']['shared_noise_float64_little_endian_sha256']
    assert noise_hash not in noise_hashes
    noise_hashes.add(noise_hash)
    assert pair['producer_only']['shared_noise_passed_to_observer'] is False
    assert pair['producer_only']['private_state_passed_to_observer'] is False
    observed, predicted, errors, private_positions = [],[],[],[]
    assert len(pair['observed_records']) == len(pair['grid_forecasts']) == len(pair['grid_summaries']) == 2
    for grid_index,(record,raw,capture_summary) in enumerate(zip(pair['observed_records'],pair['grid_forecasts'],pair['grid_summaries'])):
        assert set(record) == {'id','noise_id','measurements'} and record['noise_id'] == noise_id
        rows = record['measurements']; assert len(rows) == 600
        assert all(set(row) == {'support_s','available_s','position_m','valid'} and row['valid'] for row in rows)
        support = np.array([r['support_s'] for r in rows]); availability = np.array([r['available_s'] for r in rows])
        assert np.allclose(support,np.arange(600)*.005,rtol=0,atol=1e-14)
        assert np.allclose(availability,support+.025,rtol=0,atol=1e-14)
        y = np.array([r['position_m'] for r in rows]); private = np.array(pair['producer_only']['private_positions_by_grid_m'][grid_index])
        assert y.shape == private.shape == (600,2) and np.isfinite(y).all() and np.isfinite(private).all()
        injection_error = float(np.max(abs(y-private-noise)))
        assert injection_error <= 1e-14
        injection_roundoff_max = max(injection_roundoff_max,injection_error)
        prediction = np.array(raw['predictions_m']); target = y[indices[:,None]+horizons[None,:]]
        assert prediction.shape == target.shape == (550,26,2)
        assert np.array_equal(target,raw['observed_targets_m'])
        residual = prediction-target
        assert np.array_equal(residual,raw['observed_residuals_m'])
        assert np.allclose(raw['current_supports_s'],support[indices],rtol=0,atol=1e-14)
        assert np.allclose(raw['horizons_s'],horizons*.005,rtol=0,atol=1e-14)
        assert raw['recording_id'] == record['id'] and raw['measurement_noise_id'] == noise_id
        assert len(raw['forecast_available']) == 550 and raw['current_support_count'] == 550 and raw['horizon_count'] == 26
        available = all(raw['forecast_available']); all_available &= available
        assert raw['available_supports'] == sum(raw['forecast_available'])
        allocation = np.max(abs(residual),axis=(0,2))+.003
        assert np.array_equal(allocation,raw['allocation_by_horizon_m'])
        assert raw['maximum_allocation_m'] == float(allocation.max())
        passes = bool(available and np.all(allocation<=.015))
        assert raw['all_horizons_within_budget_confirmation'] == passes
        capture_passes += passes; allocations.append(allocation)
        i,h,foot = np.unravel_index(np.argmax(abs(residual)),residual.shape)
        assert raw['maximum_error_foot'] == foot
        assert abs(raw['maximum_error_current_support_s']-indices[i]*.005) < 1e-14
        assert abs(raw['maximum_error_target_support_s']-(indices[i]+horizons[h])*.005) < 1e-14
        assert abs(raw['maximum_error_horizon_s']-horizons[h]*.005) < 1e-14
        variance, sensor = np.array(raw['conditional_forecast_variances_m2']),np.array(raw['causal_sensor_noise_variances_m2'])
        assert np.isfinite(variance).all() and np.isfinite(sensor).all() and variance.min() >= 0 and sensor.min() >= 0
        assert np.min(variance-sensor) > -1e-15
        for key,value in capture_summary.items(): assert raw[key] == value
        capture_summaries.append(capture_summary)
        observed.append(y); private_positions.append(private); predicted.append(prediction); errors.append(residual)
        count_residuals += residual.size
    grid = pair['paired_grid_diagnostics']
    for key,values in (('observed_positions',observed[0]-observed[1]),
        ('private_positions_evaluator_only',private_positions[0]-private_positions[1]),
        ('forecasts',predicted[0]-predicted[1]),('residuals',errors[0]-errors[1])):
        verify_peak(values,grid[key])
    roundoff = float(np.max(abs((observed[0]-observed[1])-(private_positions[0]-private_positions[1]))))
    assert roundoff == pair['producer_only']['observed_minus_private_paired_difference_roundoff_m'] and roundoff<=1e-14
    difference = allocations[-2]-allocations[-1]
    assert np.array_equal(difference,grid['allocation_difference_by_horizon_m'])
    changed = ((allocations[-2]<=.015)!=(allocations[-1]<=.015)).tolist()
    assert changed == grid['changed_horizon_budget_decisions']
    assert saved_grid == {'pair_index':index,**grid}
    grid_diagnostics.append(grid)
    pair_audits.append({'pair_index':index,'noise_id':noise_id,'raw_sha256':file_info['sha256'],
        'two_grid_capture_passes':sum(r['all_horizons_within_budget_confirmation'] for r in pair['grid_summaries']),
        'maximum_allocation_m':float(max(allocations[-2].max(),allocations[-1].max()))})

aggregate = np.max(allocations,axis=0)
assert summary['independent_noise_pairs'] == len(noise_ids) == len(noise_hashes) == 16
assert summary['grid_captures'] == len(capture_summaries) == 32
assert summary['coordinate_residuals'] == count_residuals == 915200
assert summary['capture_summaries'] == capture_summaries
assert summary['all_declared_coverage_available'] == all_available
assert summary['capture_all_horizon_passes'] == capture_passes
assert np.array_equal(summary['aggregate_allocation_by_horizon_m'],aggregate)
assert summary['maximum_aggregate_allocation_m'] == float(aggregate.max())
assert summary['all_conditions_both_grids_within_budget'] == bool(all_available and np.all(aggregate<=.015))
assert summary['capture_failures'] == [r['recording_id'] for r in capture_summaries if not r['all_horizons_within_budget_confirmation']]
for key,metric in (('maximum_observed_position_grid_difference_m','observed_positions'),
    ('maximum_forecast_grid_difference_m','forecasts'),('maximum_residual_grid_difference_m','residuals')):
    assert summary[key] == max(r[metric]['maximum_absolute_difference_m'] for r in grid_diagnostics)
assert summary['changed_grid_horizon_budget_decisions'] == sum(sum(g['changed_horizon_budget_decisions']) for g in grid_diagnostics)
result = {'schema':'scci_rh.tmp.observer-confirmation-saved-audit.v1','date':'2026-10-12',
    'audit_passed':True,'scientific_budget_arithmetic_pass':summary['all_conditions_both_grids_within_budget'],
    'audit_source_sha256':digest(Path(__file__)),'freeze_receipt_sha256':EXPECTED_FREEZE,
    'summary_sha256':digest(summary_path),'producer_sha256':EXPECTED_PRODUCER,
    'full_scci_rh_source_files_verified':len(actual_sources),'noise_pairs_verified':16,
    'capture_coverage_verified':32*550,'coordinate_residuals_recomputed':count_residuals,
    'maximum_noise_injection_roundoff_m':injection_roundoff_max,
    'maximum_segment_file_bytes':maximum_file_size,'pair_audits':pair_audits,
    'elapsed_wall_seconds':time.perf_counter()-STARTED,
    'no_capture_regeneration_or_noise_draws_performed':True,
    'limits':'Sensor-noise-only finite no-dose confirmation; no new subject/biology/pilot/stimulation/retained learning.'}
output = ROOT/'tmp/observer-confirmation-saved-audit-12oct.json'
output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
