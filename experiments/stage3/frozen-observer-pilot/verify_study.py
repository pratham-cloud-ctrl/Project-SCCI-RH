"""Read-only saved-data/controller audit; optional same-cohort reproduction."""
from __future__ import annotations

import argparse
from dataclasses import FrozenInstanceError, asdict, replace
import gzip
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import tempfile

import numpy as np

PACKAGE=Path(__file__).resolve().parent
sys.path.insert(0,str(PACKAGE))
import study as s

PINS={'numpy':'2.3.5','scipy':'1.18.1'}


def compare(actual,expected,path='root'):
    if isinstance(actual,dict) and isinstance(expected,dict):
        if set(actual)!=set(expected): raise AssertionError(path+': keys differ')
        for key in actual:
            # Each saved/fresh freeze hash is separately checked against its own
            # exact floating payload; cross-platform floating hashes need not agree.
            if key=='frozen_forecast_sha256': continue
            compare(actual[key],expected[key],path+'.'+key)
    elif isinstance(actual,(list,tuple)) and isinstance(expected,(list,tuple)):
        if len(actual)!=len(expected): raise AssertionError(path+': length differs')
        if actual and all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in actual):
            if not all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in expected):
                raise AssertionError(path+': numeric types differ')
            if not np.isfinite(actual).all() or not np.isfinite(expected).all(): raise AssertionError(path+': nonfinite')
            if not np.allclose(actual,expected,rtol=2e-8,atol=1e-11): raise AssertionError(path+': numeric array differs')
        else:
            for i,(a,b) in enumerate(zip(actual,expected)): compare(a,b,f'{path}[{i}]')
    elif isinstance(actual,bool) or isinstance(expected,bool):
        if type(actual) is not type(expected) or actual!=expected: raise AssertionError(path+': decision differs')
    elif isinstance(actual,int) and isinstance(expected,int):
        if actual!=expected: raise AssertionError(path+': integer differs')
    elif isinstance(actual,(int,float)) and isinstance(expected,(int,float)):
        if not math.isfinite(actual) or not math.isfinite(expected) or not math.isclose(actual,expected,rel_tol=2e-8,abs_tol=1e-11):
            raise AssertionError(path+': number differs')
    elif actual!=expected: raise AssertionError(path+': value differs')


def must_raise(function,exception=ValueError):
    try: function()
    except exception: return
    raise AssertionError('Expected '+exception.__name__)


def negative_controls(inputs):
    module,method,context,dynamic,dose,domains,references,_=inputs
    passed=[]
    def done(name): passed.append(name)
    # Separate prerequisite failures; a policy can never replace one with the other.
    base=dict(baseline_qualified=True,reference_qualified=True,response_qualified=False,
        interaction_qualified=False,interval_qualified=True,policy_enabled=True,route_tested=True)
    actual=s.candidate_gates(**base)
    assert not actual['independent_actual_response_domain_qualified'] and not actual['learning_interaction_qualified']
    response_only=s.candidate_gates(**{**base,'response_qualified':True})
    interaction_only=s.candidate_gates(**{**base,'interaction_qualified':True})
    assert not all(response_only.values()) and not all(interaction_only.values())
    done('actual_response_and_learning_interaction_are_independent_blockers')
    must_raise(lambda:s.require_domain(context,.950,.150,((1.,0,1),)))
    done('nonempty_past_action_prefix_rejected')
    for support in (.095,2.850,.951): must_raise(lambda:s.require_domain(context,support,.150))
    for horizon in (.020,.155,.151): must_raise(lambda:s.require_domain(context,.950,horizon))
    done('outside_exact_support_and_horizon_domains_rejected')
    rows=[s.ResponsePosition(i*.005,i*.005+.025,(0.,0.)) for i in range(600)]
    def observer():
        o=s.SealedObserver(module,method,context,dynamic.model_id)
        for row in rows[:191]: assert o.update(row,row.available_s)['accepted']
        return o
    o=observer(); must_raise(lambda:o.freeze(.976)); done('incorrect_freeze_clock_rejected')
    o=observer(); frozen=o.freeze(.975)
    assert frozen.current_support_s==.9500000000000001 or abs(frozen.current_support_s-.950)<1e-12
    assert frozen.sealed_observer_updates==191 and len(frozen.targets_s)==26
    before=s.value_digest(frozen)
    assert not o.update(rows[191],rows[191].available_s)['accepted']
    must_raise(lambda:o.freeze(.975))
    def change(): frozen.created_s=0.
    must_raise(change,FrozenInstanceError)
    assert s.value_digest(frozen)==before
    done('sealed_observer_and_immutable_forecast_reject_reuse')
    permit=s.OneShotPermit((1,0)); assert permit.resolve(1.,guard_allowed=False)==(0,0)
    must_raise(lambda:permit.resolve(1.,guard_allowed=True))
    assert permit.resolution['state']=='IRREVOCABLY_WITHHELD'
    permit=s.OneShotPermit((1,0)); must_raise(lambda:permit.resolve(.995,guard_allowed=True))
    done('one_shot_permit_replay_and_wrong_launch_clock_rejected')
    # A zero-action tie cannot become a permitted nonzero choice through <= scoring.
    z=s.OneShotPermit((0,0)); assert z.resolve(1.,guard_allowed=True)==(0,0)
    assert z.resolution['authorized'] is False
    done('zero_choice_remains_zero_with_all_launch_checks_passed')
    # Synthetic contract fixture: six genuinely eligible zero-effect actions
    # tie a zero-error baseline. This checks the chooser's strict score rule.
    zero_dynamic=replace(dynamic,kernel_m_per_fraction=np.zeros_like(dynamic.kernel_m_per_fraction),
        gain_uncertainty_m_per_fraction=np.zeros_like(dynamic.gain_uncertainty_m_per_fraction))
    zero_domains=json.loads(s.canonical(domains))
    for domain in zero_domains.values():
        domain['qualified']=True
        domain['trace']['empirical_error_allocation_m']=[[.003,.003] for _ in domain['trace']['physical_support_s']]
        domain['trace']['joint_gain_dose_error_m']=[[0.,0.] for _ in domain['trace']['physical_support_s']]
    zero_frozen=replace(frozen,positions_m=tuple((0.,0.) for _ in range(26)),
        allowances_m=tuple((.001,.001) for _ in range(26)))
    zero_reference=replace(references['learner_goal'],coefficients_m=((0.,0.,0.,0.),(0.,0.,0.,0.)))
    tie=s.choose(zero_frozen,zero_reference,zero_dynamic,dose,zero_domains,policy_enabled=True,learning=False)
    assert sum(row['eligible'] for row in tie['candidates'])==6 and tie['selected_routes']==[0,0]
    done('six_eligible_exact_score_ties_preserve_zero_action')
    original=s.controller_replay(rows,inputs,'learner_goal')
    poisoned=list(rows)
    for i in range(191,600): poisoned[i]=replace(poisoned[i],position_m=(1000.,-1000.))
    changed=s.controller_replay(poisoned,inputs,'learner_goal')
    compare(original['frozen_forecast'],changed['frozen_forecast'])
    compare(original['decision'],changed['decision'])
    assert changed['frozen_current_target_diagnostic']['passed'] is False
    assert changed['frozen_current_target_diagnostic']['checked_at_s']==1.
    assert changed['launch_clock_check']['all_launch_checks_passed'] is False
    assert changed['permit']['state']=='IRREVOCABLY_WITHHELD'
    done('future_poison_cannot_revise_freeze_and_current_target_veto_precedes_launch')
    guard=s.DelayedResidualGuard()
    guard.observe(s.MeasuredPosition(.950,.975,(0.,0.)),now_s=.975)
    guard.commit(s.PredictionCommit(.975,1.100,(0.,0.),(.010,.010),'model','context'))
    for index in range(191,220):
        support=index*.005
        assert guard.observe(s.MeasuredPosition(support,support+.025,(0.,0.)),now_s=support+.025)['continuation_allowed']
    expiry=guard.check(now_s=1.151)
    assert not expiry['continuation_allowed'] and expiry['reason']=='COMMITTED_TARGET_ARRIVAL_EXPIRED'
    done('missing_last_target_expires_without_inventing_measurement')
    guard=s.DelayedResidualGuard()
    guard.observe(s.MeasuredPosition(.950,.975,(0.,0.)),now_s=.975)
    guard.commit(s.PredictionCommit(.975,1.100,(0.,0.),(.010,.010),'model','context'))
    for index in range(191,220):
        support=index*.005
        assert guard.observe(s.MeasuredPosition(support,support+.025,(0.,0.)),now_s=support+.025)['continuation_allowed']
    skip=guard.observe(s.MeasuredPosition(1.105,1.130,(0.,0.)),now_s=1.130)
    assert not skip['continuation_allowed'] and skip['reason']=='COMMITTED_TARGET_MEASUREMENT_MISSING'
    done('skipped_committed_support_latches_before_future_continuation')
    guard=s.DelayedResidualGuard()
    guard.observe(s.MeasuredPosition(.950,.975,(0.,0.)),now_s=.975)
    assert not guard.check(now_s=.970)['continuation_allowed']
    done('policy_clock_rollback_rejected')
    completed=s.CompletedDose(1.,1.0005,0,1,dose.measured_fraction,dose.uncertainty_fraction,'VALID')
    must_raise(lambda:s.predict_observed_past_response(dynamic,1.,[1.100],(completed,)))
    valid=s.predict_observed_past_response(dynamic,1.005,[1.100],(completed,))
    future=s.predict_future_effect(dynamic,.975,1.100,(s.FutureResponseFrame(1.,(1,0),.975),),dose)
    compare(valid['response_m'][0],future['effect_m'])
    compare(valid['joint_gain_dose_error_m'][0],future['joint_gain_dose_error_m'])
    done('completed_monitor_unavailable_until_its_real_clock_and_full_product_retained')
    must_raise(lambda:s.predict_observed_past_response(dynamic,1.605,[1.605],(completed,)))
    done('response_after600ms_has_no_qualified_zero_tail_release')
    must_raise(lambda:s.predict_observed_past_response(dynamic,1.005,[1.100],(replace(completed,quality='SATURATED'),)))
    done('invalid_actual_monitor_quality_rejected')
    return {'classification':'SOFTWARE_CONTRACT_PROBES_NOT_ACTIVE_DELIVERY_EVIDENCE',
            'passed':len(passed),'failed':0,'checks':passed}


def audit_raw(raw_files,inputs):
    receipt,_=s.checked_preflight()
    noise_hashes={}; records={}; practice=[]; off=[]; arm_rows=[]
    gate_counts={}; tested_gate_counts={}; freeze_count=0; current_count=0; future_count=0; warmup_count=0
    guard_count=0; guard_failures=0; diagnostic_failures=0; all_causal=True; all_sealed=True
    for path in raw_files:
        data=json.loads(gzip.decompress(Path(path).read_bytes()))
        family=data['family']; step=data['body_integration_step_s']; key=(family,step)
        assert key not in records and family in s.motor.FAMILIES and step in s.GRIDS
        assert data['preflight_sha256']==s.digest(PACKAGE/'preflight.json')
        assert data['review_sha256']==s.digest(PACKAGE/'root-review.json')
        assert [r['arm'] for r in data['runs']]==list(s.ARMS)
        records[key]=data
        for run in data['runs']:
            arm=run['arm']; p=run['practice']; practice.append(p)
            for session,row in [('practice',p),*run['assessments'].items()]:
                assert row['session']==session and row['arm']==arm
                fi=s.motor.FAMILIES.index(family); sj=receipt['sessions'].index(session)
                expected_id=s.NOISE_IDS[fi*3+sj]
                assert row['measurement_noise_id']==expected_id
                measurements=row['measurements']; truth=row['private_evaluator_only']
                times=np.arange(600)*.005
                assert len(measurements)==600
                assert np.allclose([r['support_s'] for r in measurements],times,rtol=0,atol=1e-12)
                assert np.allclose([r['available_s'] for r in measurements],times+.025,rtol=0,atol=1e-12)
                assert all(r['valid'] for r in measurements)
                noise=np.asarray(truth['actual_sensor_noise_m'])
                assert noise.shape==(600,2) and np.isfinite(noise).all()
                expected_noise=np.random.default_rng(expected_id).normal(0.,.0015,(600,2))
                assert np.array_equal(noise,expected_noise)
                positions=np.asarray(truth['positions_m'])
                compare(np.asarray([r['position_m'] for r in measurements]).tolist(),(positions+noise).tolist())
                compare(truth['times_s'],times.tolist())
                signature=s.value_digest(truth['actual_sensor_noise_m'])
                if expected_id in noise_hashes: assert signature==noise_hashes[expected_id]
                noise_hashes[expected_id]=signature
                assert row['launched_profiles']==0 and not row['launches']
                assert not row['actual_monitor_records'] and not row['pending_monitor_records']
                assert not row['actual_dose_pending_response_trace']
                assert truth['active_delivery_path_implemented'] is False
                c=replace(s.config(),body_integration_step_s=step)
                metrics=s.motor._metrics(times,positions,c,heldout=session=='transfer_off')
                compare(metrics,row['metrics'])
                if session!='practice':
                    off.append(row)
                    assert row['learning_enabled'] is False
                    assert row['controller']['reason']=='OUTPUT_HARD_OFF_ASSESSMENT'
                    assert not row['controller']['delayed_command_queue']
                    compare(truth['theta_initial_m'],(np.asarray(p['private_evaluator_only']['theta_after_m'])*.98).tolist())
                    compare(truth['theta_after_m'],truth['theta_initial_m'])
            control=p['controller']; assert p['learning_enabled'] is True
            fresh=s.controller_replay(p['measurements'],inputs,arm)
            assert s.value_digest(control['frozen_forecast'])==control['frozen_forecast_sha256']
            assert s.value_digest(fresh['frozen_forecast'])==fresh['frozen_forecast_sha256']
            compare(fresh,control)
            assert control['observer_accepted_updates']==191
            assert len(control['observer_updates'])==191 and control['observer_updates_after_seal']==0
            for u in control['observer_updates']:
                assert u['accepted'] and 0<=u['support_s']<=u['available_s']<=u['processed_at_s']+1e-12
                assert u['processed_at_s']<=.975+1e-12
            all_causal &= all(u['available_s']<=u['processed_at_s']+1e-12 for u in control['observer_updates'])
            all_sealed &= control['observer_permanently_sealed']
            f=control['frozen_forecast']; compare(f['targets_s'],s.TARGETS.tolist())
            assert f['created_s']==.975 and abs(f['current_support_s']-.950)<1e-12
            assert not f['empty_action_prefix'] and len(f['positions_m'])==26
            assert control['permit']['state']=='IRREVOCABLY_WITHHELD' and not control['permit']['authorized']
            assert control['forecast_authority_expired'] and control['pending_forecasts_at_end']==0
            assert control['decision']['selected_routes']==[0,0]
            freeze_count+=1; current_count+=control['frozen_current_target_diagnostic'] is not None
            future_count+=len(control['future_commitments']); warmup_count+=len(control['warmup_commitments'])
            guard_count+=len(control['residual_checks']); guard_failures+=sum(not r['passed'] for r in control['residual_checks'])
            diagnostic_failures+=not control['frozen_current_target_diagnostic']['passed']
            for row in control['decision']['candidates']:
                assert row['eligible'] is False
                assert row['gates']['independent_actual_response_domain_qualified'] is False
                assert row['gates']['learning_interaction_qualified'] is False
                for reason in row['failed_gates']:
                    gate_counts[reason]=gate_counts.get(reason,0)+1
                    if row['domain_id'] is not None: tested_gate_counts[reason]=tested_gate_counts.get(reason,0)+1
            arm_rows.append({'family':family,'body_integration_step_s':step,'arm':arm,
                'practice_metrics':p['metrics'],'retention_off':run['assessments']['retention_off']['metrics'],
                'transfer_off':run['assessments']['transfer_off']['metrics'],
                'practice_launched_profiles':0,'off_launched_profiles':0,
                'decision_reason':control['decision']['reason'],
                'guard_latched_reason':control['residual_guard_latched_reason'],
                'separate_latched_reason':control['separate_latched_reason']})
    assert len(records)==8 and len(practice)==32 and len(off)==64
    assert set(noise_hashes)==set(s.NOISE_IDS) and len(set(noise_hashes.values()))==12
    matched=True; max_grid_position=0.; max_grid_forecast=0.; max_grid_metric=0.
    for family in s.motor.FAMILIES:
        for step in s.GRIDS:
            data=records[(family,step)]
            comparator=data['runs'][0]
            for run in data['runs'][1:]:
                for session in ('practice','retention_off','transfer_off'):
                    a=comparator['practice'] if session=='practice' else comparator['assessments'][session]
                    b=run['practice'] if session=='practice' else run['assessments'][session]
                    compare(a['measurements'],b['measurements'])
                    compare(a['private_evaluator_only'],b['private_evaluator_only'])
                    compare(a['metrics'],b['metrics'])
        a,b=(records[(family,step)]['runs'] for step in s.GRIDS)
        for ra,rb in zip(a,b):
            max_grid_forecast=max(max_grid_forecast,float(np.max(abs(np.asarray(ra['practice']['controller']['frozen_forecast']['positions_m'])-
                np.asarray(rb['practice']['controller']['frozen_forecast']['positions_m'])))))
            for session in ('practice','retention_off','transfer_off'):
                aa=ra['practice'] if session=='practice' else ra['assessments'][session]
                bb=rb['practice'] if session=='practice' else rb['assessments'][session]
                max_grid_position=max(max_grid_position,float(np.max(abs(np.asarray(aa['private_evaluator_only']['positions_m'])-
                    np.asarray(bb['private_evaluator_only']['positions_m'])))))
                max_grid_metric=max(max_grid_metric,abs(aa['metrics']['trajectory_rmse_m']-bb['metrics']['trajectory_rmse_m']))
    raw_manifest=[{'path':Path(p).name,'bytes':Path(p).stat().st_size,'sha256':s.digest(p)} for p in raw_files]
    summary={'schema':'scci_rh.stage3.frozen-observer-pilot.summary.v1','date':'2026-10-12',
        'classification':'FINITE_PRIMARY_ACTUAL_DOMAIN_ALL_WITHHELD_OBSERVER_FREEZE_REPLAY',
        'preflight_sha256':s.digest(PACKAGE/'preflight.json'),'review_sha256':s.digest(PACKAGE/'root-review.json'),
        'practice_trials':len(practice),'off_assessments':len(off),'total_launched_profiles':0,'total_off_launched_profiles':0,
        'frozen_vectors':freeze_count,'frozen_targets':freeze_count*26,'current_diagnostics':current_count,
        'future_guard_targets':future_count,'warmup_guard_targets':warmup_count,'guard_checks':guard_count,
        'guard_failures':guard_failures,'current_diagnostic_failures':diagnostic_failures,
        'candidate_failed_gate_counts':gate_counts,'tested_candidate_failed_gate_counts':tested_gate_counts,
        'baseline_context':inputs[2],'maximum_allocation_m':max(inputs[2]['allocation_m']),
        'all_observers_sealed':bool(all_sealed),'all_updates_causal':bool(all_causal),'matched_arms_identical':matched,
        'new_sensor_noise_ids':list(s.NOISE_IDS),'distinct_noise_arrays':len(noise_hashes),
        'grid_differences':{'maximum_position_difference_m':max_grid_position,
            'maximum_frozen_forecast_difference_m':max_grid_forecast,'maximum_trajectory_rmse_difference_m':max_grid_metric,
            'launch_decisions_changed':0},'arms':arm_rows,'raw_files':raw_manifest,
        'retained_advantage_established':False,'expert_transfer_established':False,'learner_spinal_neural_increment_established':False,
        'active_delivery_path_implemented':False,'actual_monitoring_exercised':False,'stage3_completion_decided_here':False,
        'scope':'one3s practice trial per arm/family/grid; primary actual-domain withholds all; no active delivery or human efficacy',
        'resource_accounting':{'shared_frozen_calibration_fit_s':64.,'shared_temporal_holdout_s':32.,
            'new_training_s':0.,'new_neural_acquisition_s':0.,'new_dynamic_calibration_s':0.,
            'practice_s_each_arm_family_grid':3.,'off_s_each_assessment':3.,'practice_exposure_equal_across_arms':True,
            'same_actual_noise_across_arms_and_grids':True,'teacher_available_equally':True,
            'unused_expert_resource_arms':['observe_only','learner_goal'],
            'capacity':s.read(s.FROZEN/'observer-method-freeze-12oct.json')['capacity']},
        'limitations':['Four named families reduce to two distinct no-dose equations.',
            'Overlapping targets and paired grids are not independent scientific trials.',
            'Earlier measured-dose trace reuse is no guarantee of future delivery.',
            'Learning-enabled intervention-response interaction remains unqualified.',
            'No launch means no active driver/monitor/pending-response validation.',
            'Full-prefix memory and synthetic plant prior differ from historical stateless baseline.',
            'Complete reset/washout between sessions is assumed.',
            'Onepractice trial is not equivalent to historical fourtrial exposure.']}
    audit={'schema':'scci_rh.stage3.frozen-observer-pilot.audit.v1','saved_records':8,'sessions':96,
        'sanitized_measurements_checked':96*600,'controller_replays':32,
        'frozen_target_predictions_checked':freeze_count*26*2,'actual_noise_arrays_checked':12,
        'all_predeclared_sessions_present':True,'all_outcomes_retained':True,
        'source_input_freeze_verified':True,'negative_controls':negative_controls(inputs),
        'classification':'SAVED_DATA_AND_MEASURED_INPUT_CONTROLLER_REPLAY; NOT_ACTIVE_ELECTRONICS_QUALIFICATION'}
    return summary,audit


def verify_manifest():
    manifest=s.read(PACKAGE/'artifact-manifest.json'); listed={}
    for row in manifest['files']:
        path=PACKAGE/row['path']
        if row['path'] in listed or not path.resolve().is_relative_to(PACKAGE.resolve()) or not path.is_file():
            raise AssertionError('Invalid package inventory path')
        assert path.stat().st_size==row['bytes'] and s.digest(path)==row['sha256']
        listed[row['path']]=row['sha256']
    actual={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file()
        and p.name!='artifact-manifest.json' and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert actual==set(listed)
    return listed


def environment():
    if sys.version_info[:3]!=(3,12,14): raise RuntimeError('Python3.12.14 required')
    for package,pin in PINS.items():
        if importlib.metadata.version(package)!=pin: raise RuntimeError(package+' '+pin+' required')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-record',action='store_true',help='Initial saved-data audit after approved generation; refuses to replace records')
    parser.add_argument('--reproduce',action='store_true',help='Regenerate the same frozen cohort in scratch, never a new experiment')
    parser.add_argument('--controls-only',action='store_true',help='Run scoped contract probes before generation')
    args=parser.parse_args(); environment()
    inputs=s.load_inputs()
    if args.controls_only:
        print(json.dumps(negative_controls(inputs),indent=2)); return
    originals=None if args.build_record else verify_manifest()
    raw=sorted((PACKAGE/'raw').glob('*.json.gz'))
    summary,audit=audit_raw(raw,inputs)
    if args.build_record:
        if (PACKAGE/'summary.json').exists() or (PACKAGE/'audit.json').exists():
            raise ValueError('Saved summary/audit already exist; verification is read-only')
        s.save(PACKAGE/'summary.json',summary); s.save(PACKAGE/'audit.json',audit)
    else:
        compare(summary,s.read(PACKAGE/'summary.json'))
        compare(audit,s.read(PACKAGE/'audit.json'))
        if args.reproduce:
            with tempfile.TemporaryDirectory(prefix='scci_rh-frozen-observer-pilot-') as directory:
                fresh=s.generate(Path(directory)/'raw')
                for item in fresh:
                    path=Path(directory)/'raw'/item['path']; saved=PACKAGE/'raw'/item['path']
                    compare(json.loads(gzip.decompress(path.read_bytes())),json.loads(gzip.decompress(saved.read_bytes())))
        for relative,expected in originals.items(): assert s.digest(PACKAGE/relative)==expected
    print(f"Verified {summary['practice_trials']} practice + {summary['off_assessments']} OFF sessions; "
          f"{summary['total_launched_profiles']} launches; {audit['negative_controls']['passed']} contract probes.")
    print('Finite actual-domain all-withheld result; no active delivery or retained-learning benefit established.')


if __name__=='__main__': main()
