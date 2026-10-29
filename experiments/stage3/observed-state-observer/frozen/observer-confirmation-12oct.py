"""TMP ONLY: predeclared fresh-noise no-dose confirmation, no implicit run."""
from pathlib import Path
from dataclasses import asdict, replace
import argparse
import gzip
import hashlib
import json
import platform
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3 import motor
from scci_rh.stage3.isolated_pilot import config as original_config
import observed_state_observer_12oct as observer

PROTOCOL = ROOT/'tmp/observer-confirmation-protocol-12oct.md'
FREEZE = ROOT/'tmp/observer-confirmation-freeze-12oct.json'
SUMMARY = ROOT/'tmp/observer-confirmation-summary-12oct.json'
EXPECTED_OBSERVER_SHA = '203a5bdd90ae20a67f1b6475b47c31a73880d96a5c4434957b51f28a2f767c44'
EXPECTED_METHOD_SHA = '1157a4490d4455faba6773fe447560b22c218db852efe65fc95c180f373dce7f'
FAMILIES = ('favorable','zero','harmful','dependent')
SCALES = (.9, 1., 1.15, 1.3)
GRIDS = (.0025, .00125)
BODY_SOURCE_PATHS = ('src/scci_rh/stage3/motor.py','src/scci_rh/stage3/isolated_pilot.py')
ATOL, RTOL = 1e-11, 2e-8


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def cohort_manifest():
    return [{'pair_index':4*fi+si,'producer_only_family':family,
             'producer_only_initial_theta_scale':scale,'measurement_noise_id':261012000+4*fi+si,
             'subject_seed':2,'seconds':3.,'learning':True,'dose':'zero',
             'body_integration_steps_s':list(GRIDS)}
            for fi,family in enumerate(FAMILIES) for si,scale in enumerate(SCALES)]


def pair_path(index):
    return ROOT/f'tmp/observer-confirmation-pair-{index:02d}-12oct.json.gz'


def bindings():
    return {'protocol_sha256':digest(PROTOCOL),'producer_evaluator_sha256':digest(Path(__file__)),
        'observer_source_sha256':digest(Path(observer.__file__)),
        'method_receipt_sha256':digest(observer.RECEIPT),
        'calibration_input_sha256':digest(observer.CALIBRATION),
        'already_inspected_development_input_sha256':digest(observer.DEVELOPMENT),
        'body_source_bytes_sha256':{p:digest(ROOT/p) for p in BODY_SOURCE_PATHS},
        'full_scci_rh_source_bytes_sha256':{p.relative_to(ROOT).as_posix():digest(p)
            for p in sorted((ROOT/'src/scci_rh').rglob('*.py'))}}


def preflight():
    identity = bindings()
    assert identity['observer_source_sha256'] == EXPECTED_OBSERVER_SHA
    assert identity['method_receipt_sha256'] == EXPECTED_METHOD_SHA
    receipt, _ = observer.load_frozen()
    assert receipt['calibration_input_sha256'] == identity['calibration_input_sha256']
    old = json.loads(gzip.decompress(observer.DEVELOPMENT.read_bytes()))
    calibration = json.loads(gzip.decompress(observer.CALIBRATION.read_bytes()))['training']
    old_ids = {r['noise_id'] for r in [old['base'],*old['drifts'],*calibration]}
    new_ids = [r['measurement_noise_id'] for r in cohort_manifest()]
    assert len(new_ids) == len(set(new_ids)) == 16 and not (set(new_ids)&old_ids)
    base = original_config()
    assert base.dt_s == .005 and base.body_integration_step_s == .0025
    assert base.body_integration_method == 'midpoint_exact_cascade'
    assert base.external_noise_m == observer.SIGMA
    configs = []
    for grid in GRIDS:
        c = replace(base, body_integration_step_s=grid)
        expected = asdict(base); expected['body_integration_step_s'] = grid
        assert asdict(c) == expected
        configs.append(asdict(c))
    result = {'schema':'scci_rh.tmp.observer-confirmation-freeze.v1','date':'2026-10-12',
        'classification':'PREGENERATION_METHOD_COHORT_FREEZE_REQUIRES_ROOT_REVIEW',
        **identity,'cohort':cohort_manifest(),'excluded_prior_noise_ids':sorted(old_ids),
        'sensor_noise_independent_pairs':16,'grid_captures':32,
        'original_generator_config':asdict(base),'paired_generator_configs':configs,
        'new_noise_draws_before_freeze':0,'captures_generated_before_freeze':0,
        'settings':{'current_indices_inclusive':[20,569],'current_supports_per_capture':550,
            'horizons_s':(np.arange(5,31)*.005).tolist(),'subject_seed':2,
            'duration_s':3.,'learning':True,'no_dose':True,'availability_delay_s':.025,
            'label_allocation_m':.003,'forecast_budget_m':.015,'combined_gate_not_tested_m':.025,
            'paired_noise_roundoff_difference_limit_m':1e-14,
            'reproduction_rtol':RTOL,'reproduction_atol':ATOL,'maximum_gzip_file_bytes':50*1024*1024},
        'expected_raw_pair_files':[pair_path(i).relative_to(ROOT).as_posix() for i in range(16)],
        'expected_summary_file':SUMMARY.relative_to(ROOT).as_posix(),
        'runtime_private_parameters_used':False,'authoritative_sources_modified':False,
        'limits':['Noise independence only: same subjectseed2 and finite family/scale domain.',
            'Two distinct no-dose learning laws, not four independent laws.',
            'Paired grid agreement does not establish continuum/biological validity.',
            'Standalone no-dose observer confirmation; no pilot, stimulation or retained-learning result.']}
    if FREEZE.exists():
        assert json.loads(FREEZE.read_text(encoding='utf-8')) == result, 'Existing freeze receipt is immutable; preserve it before a pre-review revision'
    else:
        save_json(FREEZE,result)
    print(json.dumps({k:v for k,v in result.items() if k not in
        ('original_generator_config','paired_generator_configs')},indent=2))


def load_freeze():
    freeze = json.loads(FREEZE.read_text(encoding='utf-8'))
    for key,value in bindings().items(): assert freeze[key] == value, key
    assert freeze['observer_source_sha256'] == EXPECTED_OBSERVER_SHA
    assert freeze['method_receipt_sha256'] == EXPECTED_METHOD_SHA
    assert freeze['cohort'] == cohort_manifest()
    return freeze


def produce_pair(condition):
    """PRIVATE producer only. No private fields enter the observer record."""
    rng = np.random.default_rng(condition['measurement_noise_id'])
    shared_noise = rng.normal(0., observer.SIGMA, (600,2))
    observed_records, private_positions, integration_substeps = [], [], []
    base = original_config()
    for grid in GRIDS:
        c = replace(base, body_integration_step_s=grid)
        world = motor._World(2,c)
        world.theta *= condition['producer_only_initial_theta_scale']
        rows, positions = [], []
        for index in range(600):
            support = index*c.dt_s
            private_position = world.x.copy()
            measured = private_position+shared_noise[index]
            rows.append({'support_s':support,'available_s':support+.025,
                         'position_m':measured.tolist(),'valid':True})
            positions.append(private_position.tolist())
            world.advance(support+c.dt_s,np.zeros(2),condition['producer_only_family'],learning=True)
        # Only these three fields are passed to the fixed observer evaluator.
        observed_records.append({'id':f"observer_confirmation_{condition['pair_index']:02d}_grid_{grid:g}",
            'noise_id':condition['measurement_noise_id'],'measurements':rows})
        private_positions.append(positions)
        integration_substeps.append(world.integration_substeps)
    a,b = (np.array([r['position_m'] for r in record['measurements']]) for record in observed_records)
    p,q = np.array(private_positions)
    roundoff_difference = float(np.max(abs((a-b)-(p-q))))
    assert roundoff_difference <= 1e-14
    private = {'condition':condition,'shared_noise_samples_m':shared_noise.tolist(),
        'shared_noise_float64_little_endian_sha256':hashlib.sha256(shared_noise.astype('<f8').tobytes()).hexdigest(),
        'private_positions_by_grid_m':private_positions,'integration_substeps_by_grid':integration_substeps,
        'observed_minus_private_paired_difference_roundoff_m':roundoff_difference,
        'shared_noise_passed_to_observer':False,'private_state_passed_to_observer':False}
    return observed_records, private


def peak(values):
    location = np.unravel_index(np.argmax(abs(values)),values.shape)
    return {'maximum_absolute_difference_m':float(np.max(abs(values))),
            'array_index':list(map(int,location))}


def evaluate_pair(model, condition, freeze, review_reference):
    records, private = produce_pair(condition)
    summaries, raws = [], []
    for record in records:
        summary, raw = observer.evaluate_record(model,record,20,569)
        # Only the legacy helper's output label changes, never its calculation.
        for report in (summary, raw):
            report['all_horizons_within_budget_confirmation'] = report.pop('all_horizons_within_budget_development')
        summaries.append(summary); raws.append(raw)
    positions = [np.array([r['position_m'] for r in record['measurements']]) for record in records]
    predicted = [np.array(raw['predictions_m']) for raw in raws]
    residuals = [np.array(raw['observed_residuals_m']) for raw in raws]
    # Model covariance depends on clocks/prior and noise model, not achieved y.
    assert raws[0]['conditional_forecast_variances_m2'] == raws[1]['conditional_forecast_variances_m2']
    assert raws[0]['causal_sensor_noise_variances_m2'] == raws[1]['causal_sensor_noise_variances_m2']
    grid = {'observed_positions':peak(positions[0]-positions[1]),
        'private_positions_evaluator_only':peak(np.array(private['private_positions_by_grid_m'][0])-np.array(private['private_positions_by_grid_m'][1])),
        'forecasts':peak(predicted[0]-predicted[1]), 'residuals':peak(residuals[0]-residuals[1]),
        'allocation_difference_by_horizon_m':(np.array(summaries[0]['allocation_by_horizon_m'])-np.array(summaries[1]['allocation_by_horizon_m'])).tolist(),
        'changed_horizon_budget_decisions':[bool((a<=.015)!=(b<=.015)) for a,b in zip(
            summaries[0]['allocation_by_horizon_m'],summaries[1]['allocation_by_horizon_m'])]}
    for key in ('forecasts','residuals'):
        i,h,foot = grid[key]['array_index']
        grid[key].update(current_support_s=(20+i)*.005,horizon_s=(5+h)*.005,coordinate=foot)
    for key in ('observed_positions','private_positions_evaluator_only'):
        i,foot = grid[key]['array_index']
        grid[key].update(support_s=i*.005,coordinate=foot)
    result = {'schema':'scci_rh.tmp.observer-confirmation-pair.v1','date':'2026-10-12',
        'classification':'FRESH_SENSOR_NOISE_ONLY_NO_DOSE_FINITE_CONFIRMATION',
        'freeze_receipt_sha256':digest(FREEZE),'review_reference':review_reference,
        'frozen_bindings':{key:freeze[key] for key in bindings()},'condition_provenance':condition,
        'grid_summaries':summaries,'paired_grid_diagnostics':grid,
        'observed_records':records,'producer_only':private,'grid_forecasts':raws}
    return result


def compare(saved, fresh, path='root'):
    if isinstance(saved,dict) and isinstance(fresh,dict):
        assert set(saved) == set(fresh), path+' keys'
        for key in saved:
            if key == 'elapsed_wall_seconds': continue
            compare(saved[key],fresh[key],path+'.'+key)
    elif isinstance(saved,list) and isinstance(fresh,list):
        assert len(saved) == len(fresh), path+' length'
        for index,(a,b) in enumerate(zip(saved,fresh)): compare(a,b,f'{path}[{index}]')
    elif isinstance(saved,bool) or isinstance(fresh,bool):
        assert type(saved) == type(fresh) and saved == fresh,path
    elif isinstance(saved,int) and isinstance(fresh,int):
        assert saved == fresh,path
    elif isinstance(saved,(int,float)) and isinstance(fresh,(int,float)):
        assert np.isfinite(saved) and np.isfinite(fresh) and np.isclose(saved,fresh,rtol=RTOL,atol=ATOL),path
    else: assert saved == fresh,path


def execute(review_reference, check=False):
    started = time.perf_counter()
    freeze = load_freeze()
    assert review_reference.strip()
    if not check:
        assert not SUMMARY.exists() and not any(pair_path(i).exists() for i in range(16)), 'Existing confirmation outputs are preserved'
    receipt, model = observer.load_frozen()
    summaries, grids, files = [], [], []
    for condition in cohort_manifest():
        print(('Reproduce' if check else 'Fresh sensor-noise pair')+f" {condition['pair_index']:02d}",flush=True)
        pair = evaluate_pair(model,condition,freeze,review_reference)
        path = pair_path(condition['pair_index'])
        if check:
            saved = json.loads(gzip.decompress(path.read_bytes()))
            compare(saved,pair,path.name)
        else:
            payload = gzip.compress(json.dumps(pair,separators=(',',':'),allow_nan=False).encode(),mtime=0)
            assert len(payload) < 50*1024*1024
            path.write_bytes(payload)
        files.append({'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path),'bytes':path.stat().st_size})
        summaries.extend(pair['grid_summaries'])
        grids.append({'pair_index':condition['pair_index'],**pair['paired_grid_diagnostics']})
    allocations = np.max(np.array([s['allocation_by_horizon_m'] for s in summaries]),axis=0)
    all_coverage = all(s['current_support_count'] == s['available_supports'] == 550 and s['horizon_count'] == 26 for s in summaries)
    summary = {'schema':'scci_rh.tmp.observer-confirmation-summary.v1','date':'2026-10-12',
        'classification':'FRESH_SENSOR_NOISE_ONLY_NO_DOSE_FINITE_CONFIRMATION',
        'freeze_receipt_sha256':digest(FREEZE),'frozen_bindings':{key:freeze[key] for key in bindings()},
        'review_reference':review_reference,'independence':'sensor_noise_only_same_subjectseed2_and_finite_domain',
        'independent_noise_pairs':16,'grid_captures':32,'current_supports_per_capture':550,
        'horizons_per_support':26,'coordinate_residuals':32*550*26*2,
        'all_declared_coverage_available':all_coverage,
        'aggregate_allocation_by_horizon_m':allocations.tolist(),
        'maximum_aggregate_allocation_m':float(allocations.max()),
        'all_conditions_both_grids_within_budget':bool(all_coverage and np.all(allocations<=.015)),
        'capture_all_horizon_passes':sum(s['all_horizons_within_budget_confirmation'] for s in summaries),
        'capture_failures':[s['recording_id'] for s in summaries if not s['all_horizons_within_budget_confirmation']],
        'maximum_observed_position_grid_difference_m':max(g['observed_positions']['maximum_absolute_difference_m'] for g in grids),
        'maximum_forecast_grid_difference_m':max(g['forecasts']['maximum_absolute_difference_m'] for g in grids),
        'maximum_residual_grid_difference_m':max(g['residuals']['maximum_absolute_difference_m'] for g in grids),
        'changed_grid_horizon_budget_decisions':sum(sum(g['changed_horizon_budget_decisions']) for g in grids),
        'capture_summaries':summaries,'paired_grid_diagnostics':grids,'pair_files':files,
        'no_refit_or_settings_changes':True,'observer_private_inputs_used':False,
        'no_dose':True,'authoritative_predictor_or_pilot_changed':False,
        'neural_increment_assistance_or_retained_learning_tested':False,
        'elapsed_wall_seconds':time.perf_counter()-started,
        'python_version':platform.python_version(),'numpy_version':np.__version__,
        'capacity':receipt['capacity'],'limits':freeze['limits']}
    load_freeze()  # Frozen sources and inputs must remain unchanged throughout.
    if check:
        compare(json.loads(SUMMARY.read_text(encoding='utf-8')),summary,'summary')
        print('Fresh deterministic reproduction passed all16pairs and cohort summary; no output overwritten.')
    else:
        save_json(SUMMARY,summary)
        print(json.dumps({k:v for k,v in summary.items() if k not in ('capture_summaries','paired_grid_diagnostics','pair_files')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--run-after-root-review')
    parser.add_argument('--check-after-root-review')
    args = parser.parse_args()
    if args.preflight: preflight()
    elif args.run_after_root_review: execute(args.run_after_root_review)
    elif args.check_after_root_review: execute(args.check_after_root_review,check=True)
    else: parser.error('Preflight does not generate; actual run requires explicit pre-generation root review')
