"""Independent raw evidence recomputation, with no producer/controller execution."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import numpy as np

PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument('--write-receipt',action='store_true',
    help='Write the independently recomputed result to the named provenance receipt')
ARGS = PARSER.parse_args()

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'experiments/stage3/frozen-observer-pilot'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
freeze = read(P/'preflight.json')
review = read(P/'root-review.json')
assert sha(P/'preflight.json') == '939ee5a99e4cda623496c6efa4888442c7f463a90c6515f59baa490955c87933'
assert review['authorized'] and review['preflight_sha256'] == sha(P/'preflight.json')
for rel,h in freeze['code_bytes_sha256'].items(): assert sha(P/rel) == h
for rel,h in freeze['bindings']['inputs_bytes_sha256'].items(): assert sha(ROOT/rel) == h
for rel,h in freeze['bindings']['bound_scci_rh_source_bytes_sha256'].items(): assert sha(ROOT/rel) == h

files = sorted((P/'raw').glob('*.json.gz'))
assert len(files) == 8
records, noise, counts = {}, {}, dict(practice=0, off=0, measurements=0, updates=0, vectors=0,
    frozen_coordinate_residuals=0, guard_checks=0, current_diagnostics=0, candidate_rows=0,
    tested_candidate_rows=0, withheld_permits=0, guard_failures=0, diagnostic_failures=0)
maximum_frozen_residual = maximum_guard_residual = maximum_injection_roundoff = 0.
families, arms = freeze['generator_only_families'], freeze['arms']
dynamic = read(ROOT/'results/stage3/dynamic-response/dynamic-response-summary.json')['grids']['2500us']
kernel = np.array(dynamic['model']['kernel_m_per_fraction'])
gain_u = np.array(dynamic['model']['gain_uncertainty_m_per_fraction'])
knots = np.arange(len(kernel))*.005
dose = dynamic['prospective_branches']['actual_electrical_trace_domain']
d,ud = dose['measured_fraction'],dose['uncertainty_fraction']
maximum_candidate_allowance = 0.
for path in files:
    data = json.loads(gzip.decompress(path.read_bytes()))
    assert data['preflight_sha256'] == sha(P/'preflight.json')
    assert data['review_sha256'] == sha(P/'root-review.json')
    family, grid = data['family'], data['body_integration_step_s']
    assert family in families and grid in freeze['grids_s'] and (family,grid) not in records
    assert [r['arm'] for r in data['runs']] == arms
    records[family,grid] = data
    for run in data['runs']:
        practice = run['practice']
        for session,row in [('practice',practice),*run['assessments'].items()]:
            assert row['session'] == session and row['arm'] == run['arm']
            counts['practice' if session == 'practice' else 'off'] += 1
            obs = row['measurements']; truth = row['private_evaluator_only']
            assert len(obs) == 600 and all(r['valid'] for r in obs)
            times = np.arange(600)*.005
            assert np.allclose([r['support_s'] for r in obs],times,rtol=0,atol=1e-14)
            assert np.allclose([r['available_s'] for r in obs],times+.025,rtol=0,atol=1e-14)
            y = np.array([r['position_m'] for r in obs]); private = np.array(truth['positions_m'])
            n = np.array(truth['actual_sensor_noise_m'])
            assert y.shape == private.shape == n.shape == (600,2)
            injection = float(np.max(abs(y-private-n)))
            assert injection <= 1e-14
            maximum_injection_roundoff = max(maximum_injection_roundoff,injection)
            nid = row['measurement_noise_id']
            sj = freeze['sessions'].index(session); fi = families.index(family)
            assert nid == freeze['noise_ids'][fi*3+sj]
            assert nid not in freeze['bindings']['excluded_prior_noise_ids']
            nh = hashlib.sha256(n.astype('<f8').tobytes()).hexdigest()
            if nid in noise: assert noise[nid] == nh
            noise[nid] = nh
            assert row['launched_profiles'] == 0 and not row['launches']
            assert not row['actual_monitor_records'] and not row['pending_monitor_records']
            assert not row['actual_dose_pending_response_trace']
            assert not truth['active_delivery_path_implemented']
            counts['measurements'] += 600
            if session != 'practice':
                assert not row['learning_enabled']
                assert row['controller']['reason'] == 'OUTPUT_HARD_OFF_ASSESSMENT'
                assert row['controller']['permit']['state'] == 'HARD_OFF'
                assert not row['controller']['delayed_command_queue']
                expected = np.array(practice['private_evaluator_only']['theta_after_m'])*.98
                assert np.array_equal(np.array(truth['theta_initial_m']),expected)
                assert truth['theta_after_m'] == truth['theta_initial_m']
                continue
            c = row['controller']; f = c['frozen_forecast']
            assert c['observer_accepted_updates'] == len(c['observer_updates']) == 191
            assert c['observer_updates_after_seal'] == 0 and c['observer_permanently_sealed']
            for i,u in enumerate(c['observer_updates']):
                assert u['accepted'] and abs(u['support_s']-i*.005) < 1e-14
                assert 0 <= u['support_s'] <= u['available_s'] <= u['processed_at_s']+1e-12 <= .975+1e-12
            counts['updates'] += 191; counts['vectors'] += 1
            assert f['created_s'] == .975 and abs(f['current_support_s']-.950) < 1e-14
            assert not f['empty_action_prefix'] and f['sealed_observer_updates'] == 191
            assert np.allclose(f['targets_s'],np.arange(195,221)*.005,rtol=0,atol=1e-14)
            frozen_errors = abs(np.array(f['positions_m'])-y[195:221])
            assert np.array(f['allowances_m']).shape == (26,2)
            maximum_frozen_residual = max(maximum_frozen_residual,float(frozen_errors.max()))
            counts['frozen_coordinate_residuals'] += frozen_errors.size
            diagnostic = c['frozen_current_target_diagnostic']
            assert diagnostic['target_support_s'] == diagnostic['observed_support_s'] == .975
            assert diagnostic['observed_available_s'] == diagnostic['checked_at_s'] == 1.
            assert np.array_equal(np.array(diagnostic['absolute_residual_m']),frozen_errors[0])
            counts['current_diagnostics'] += 1; counts['diagnostic_failures'] += not diagnostic['passed']
            commits = c['warmup_commitments'] + c['future_commitments']
            assert len(c['warmup_commitments']) == len(c['future_commitments']) == 25
            for w in c['residual_checks']:
                matching = [a['forecast'] for a in commits if
                    abs(a['forecast']['created_s']-w['created_s']) < 1e-12 and
                    abs(a['forecast']['target_support_s']-w['target_support_s']) < 1e-12]
                assert len(matching) == 1
                commit = matching[0]; target = round(w['target_support_s']/.005)
                residual = abs(np.array(commit['position_m'])-y[target])
                assert np.array_equal(residual,np.array(w['absolute_residual_m']))
                assert w['created_s'] < w['target_support_s']
                assert w['observed_support_s'] == w['target_support_s']
                assert w['observed_available_s'] <= w['checked_at_s']+1e-12
                assert bool(np.all(residual<=np.array(w['allowance_m'])+1e-12)) == w['passed']
                maximum_guard_residual = max(maximum_guard_residual,float(residual.max()))
                counts['guard_checks'] += 1; counts['guard_failures'] += not w['passed']
            permit = c['permit']
            assert permit['resolved_at_s'] == 1. and permit['state'] == 'IRREVOCABLY_WITHHELD'
            assert permit['choice'] == permit['routes'] == [0,0]
            assert not permit['authorized'] and not permit['rearm_allowed']
            assert c['forecast_authority_expired'] and c['pending_forecasts_at_end'] == 0
            counts['withheld_permits'] += 1
            assert len(c['decision']['candidates']) == 8 and c['decision']['selected_routes'] == [0,0]
            for candidate in c['decision']['candidates']:
                assert not candidate['eligible']
                assert not candidate['gates']['independent_actual_response_domain_qualified']
                assert not candidate['gates']['learning_interaction_qualified']
                counts['candidate_rows'] += 1
                counts['tested_candidate_rows'] += candidate['domain_id'] is not None
                if candidate['domain_id'] is None: continue
                trace = dynamic['independent_validation'][candidate['domain_id']]['actual_electrical_trace_domain']['trace']
                trace_times = np.array(trace['physical_support_s'])
                trace_observed = np.array(trace['observed_response_m'])
                trace_prediction = np.array(trace['predicted_response_m'])
                effects, joint, residuals = [], [], []
                for target in f['targets_s']:
                    effect, uncertainty = np.zeros(2),np.zeros(2)
                    if target >= 1.-1e-12:
                        lag = target-1.
                        for source,sign in enumerate(candidate['routes']):
                            if not sign: continue
                            g = np.array([np.interp(lag,knots,kernel[:,foot,source]) for foot in range(2)])
                            u = np.array([np.interp(lag,knots,gain_u[:,foot,source]) for foot in range(2)])
                            effect += sign*g*d
                            uncertainty += u*d+abs(g)*ud+u*ud
                    index = np.flatnonzero(abs(trace_times-target)<1e-10)
                    assert len(index) == 1
                    residuals.append(abs(trace_prediction[index[0]]-trace_observed[index[0]])+.003)
                    effects.append(effect); joint.append(uncertainty)
                position = np.array(f['positions_m'])+np.array(effects)
                actual_u = np.array(f['allowances_m'])+np.array(joint)+np.array(residuals)
                correction_u = actual_u+candidate['independent_reference_allocation_m']
                assert np.allclose(position,candidate['predicted_positions_m'],rtol=2e-8,atol=1e-11)
                assert np.allclose(actual_u,candidate['total_position_allowance_m'],rtol=2e-8,atol=1e-11)
                assert np.allclose(correction_u,candidate['correction_against_reference_allowance_m'],rtol=2e-8,atol=1e-11)
                assert bool(np.max(correction_u)<=.025) == candidate['gates']['whole_vector_correction_interval_within25mm']
                maximum_candidate_allowance = max(maximum_candidate_allowance,float(correction_u.max()))

assert len(records) == 8 and len(noise) == len(set(noise.values())) == 12
for family in families:
    for grid in freeze['grids_s']:
        runs = records[family,grid]['runs']
        for run in runs[1:]:
            for session in freeze['sessions']:
                a = runs[0]['practice'] if session == 'practice' else runs[0]['assessments'][session]
                b = run['practice'] if session == 'practice' else run['assessments'][session]
                assert a['measurements'] == b['measurements']
                assert a['private_evaluator_only'] == b['private_evaluator_only']
                assert a['metrics'] == b['metrics']

result = {'schema':'scci_rh.stage3.frozen-observer-pilot-independent-audit.v1','date':'2026-10-12',
    'preflight_sha256':sha(P/'preflight.json'),'review_sha256':sha(P/'root-review.json'),
    'independent_raw_recomputation_passed':True,**counts,
    'distinct_new_noise_arrays':len(noise),'maximum_frozen_coordinate_residual_m':maximum_frozen_residual,
    'maximum_scored_guard_coordinate_residual_m':maximum_guard_residual,
    'maximum_noise_injection_roundoff_m':maximum_injection_roundoff,
    'independent_full_gain_dose_cross_term_and_response_residual_recomputed':True,
    'maximum_tested_candidate_correction_allowance_m':maximum_candidate_allowance,
    'code_input_and_21_source_hashes_unchanged':True,'matched_arms_exactly_equal':True,
    'producer_or_controller_executed':False,'active_delivery_or_monitor_validation':False,
    'auditor_source_sha256':sha(Path(__file__))}
if ARGS.write_receipt:
    out = ROOT/'provenance/stage3-frozen-pilot-independent-audit.json'
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result,indent=2))
