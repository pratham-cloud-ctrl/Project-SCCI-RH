"""Finite actual-domain observer freeze replay; no historical source mutation."""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass, replace
import gzip
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import platform
from pathlib import Path
import sys

import numpy as np

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3 import motor
from scci_rh.stage3.assisted_prediction import MeasuredPosition
from scci_rh.stage3.dynamic_response import (ResponsePosition, ProspectiveDose,
    FutureResponseFrame, CompletedDose, predict_future_effect,
    predict_observed_past_response, response_model_from_record)
from scci_rh.stage3.isolated_pilot import ARMS, ACTION_DOMAINS, reference_from_library, config
from scci_rh.stage3.residual_guard import DelayedResidualGuard, PredictionCommit

OBSERVER = ROOT/'experiments/stage3/observed-state-observer'
FROZEN = OBSERVER/'frozen'
BRANCH = 'actual_electrical_trace_domain'
CONTEXT_ID = 'SCCI_RH_S3_FROZEN_PREFIX_DEVELOPMENT_AND_CONFIRMATION_12OCT'
NOISE_IDS = tuple(range(1261012100,1261012112))
GRIDS = (.0025,.00125)
HORIZONS = np.arange(5,31)*.005
TARGETS = np.arange(195,221)*.005
INPUT_PATHS = (
    'experiments/stage3/observed-state-observer/artifact-manifest.json',
    'experiments/stage3/observed-state-observer/frozen/observed_state_observer_12oct.py',
    'experiments/stage3/observed-state-observer/frozen/observer-method-freeze-12oct.json',
    'experiments/stage3/observed-state-observer/frozen/observer-development-summary-12oct.json',
    'experiments/stage3/observed-state-observer/frozen/observer-confirmation-summary-12oct.json',
    'experiments/stage3/observed-state-observer/frozen/observer-confirmation-freeze-12oct.json',
    'results/stage3/dynamic-response/dynamic-response-summary.json',
    'results/stage3/resolved-teacher/summary.json',
)
CODE_PATHS = ('protocol.md','study.py','verify_study.py','requirements-lock.txt')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain(value):
    if isinstance(value,np.ndarray): return value.tolist()
    if isinstance(value,np.generic): return value.item()
    if hasattr(value,'__dataclass_fields__'): return asdict(value)
    raise TypeError(type(value).__name__)


def canonical(value):
    return json.dumps(value,default=plain,sort_keys=True,separators=(',',':'),allow_nan=False)


def value_digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path,value):
    Path(path).write_text(json.dumps(value,default=plain,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def encoded(value):
    buffer=io.BytesIO()
    with gzip.GzipFile(filename='',mode='wb',fileobj=buffer,mtime=0) as stream:
        stream.write(canonical(value).encode())
    return buffer.getvalue()


def load_observer():
    path=FROZEN/'observed_state_observer_12oct.py'
    spec=importlib.util.spec_from_file_location('scci_rh_frozen_observer_method',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    # Use only pure classes/functions; the original tmp-path I/O is never invoked.
    return module


def collect_noise_ids(value, *, noise_context=False):
    found=set()
    if isinstance(value,dict):
        for key,item in value.items():
            found |= collect_noise_ids(item,noise_context=noise_context or 'noise' in key.lower())
    elif isinstance(value,list):
        for item in value: found |= collect_noise_ids(item,noise_context=noise_context)
    elif noise_context and isinstance(value,int) and not isinstance(value,bool): found.add(value)
    return found


def load_inputs():
    development=read(FROZEN/'observer-development-summary-12oct.json')
    confirmation=read(FROZEN/'observer-confirmation-summary-12oct.json')
    method=read(FROZEN/'observer-method-freeze-12oct.json')
    freeze=read(FROZEN/'observer-confirmation-freeze-12oct.json')
    assert development['development_record_count']==16
    assert development['development_all_horizon_passes']==16
    assert confirmation['grid_captures']==32 and confirmation['all_declared_coverage_available']
    assert confirmation['all_conditions_both_grids_within_budget']
    rows=development['development']
    assert len(rows)==16 and all(r['current_support_count']==550 and r['available_supports']==550 for r in rows)
    allocation=np.maximum(np.max([r['allocation_by_horizon_m'] for r in rows],axis=0),
                          confirmation['aggregate_allocation_by_horizon_m'])
    if allocation.shape!=(26,) or not np.isfinite(allocation).all() or np.any(allocation>.015):
        raise ValueError('Complete empirical baseline context unavailable')
    context={'context_id':CONTEXT_ID,'qualified':True,'support_start_s':.100,'support_end_s':2.845,
        'sample_s':.005,'horizons_s':HORIZONS.tolist(),'allocation_m':allocation.tolist(),
        'action_prefix':[],'instruction_hz':1.,'task_time_offset_s':0.,
        'source_groups':['16 development drift captures','32 fresh confirmation grid captures'],
        'temporal_holdout_used_for_admission':False,'private_family_selector':False,
        'scope':'finite observed exact-prefix no-dose domain; empirical, not population coverage'}
    dynamic=read(ROOT/'results/stage3/dynamic-response/dynamic-response-summary.json')
    teacher=read(ROOT/'results/stage3/resolved-teacher/summary.json')
    for receipt,key in ((dynamic,'source_sha256'),(teacher,'source_identity')):
        for path,expected in receipt[key].items():
            actual=hashlib.sha256((ROOT/path).read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest()
            if actual!=expected: raise ValueError('Stale inherited source: '+path)
    grid=dynamic['grids']['2500us']
    raw=ROOT/'results/stage3/dynamic-response'/grid['raw_file']['path']
    if digest(raw)!=grid['raw_file']['sha256']: raise ValueError('Inherited dynamic raw hash mismatch')
    model=response_model_from_record(grid['model'])
    dose=ProspectiveDose(**grid['prospective_branches'][BRANCH])
    library=teacher['libraries']['idealized_inverse']
    references={arm:reference_from_library(library,kind) for arm,kind in
        (('observe_only','learner_only'),('learner_goal','learner_only'),
         ('expert_external','expert_external'),('expert_neural','expert_neural'))}
    if not all(r.qualified for r in references.values()): raise ValueError('Unqualified inherited teacher')
    domains={key:grid['independent_validation'][key][BRANCH]
             for key in ACTION_DOMAINS.values() if key is not None}
    if any(d['qualified'] for d in domains.values()): raise ValueError('Primary actual-domain premise changed')
    excluded=set()
    # All frozen observer compact receipts bind its calibration/development/confirmation IDs.
    for path in FROZEN.glob('*.json'): excluded |= collect_noise_ids(read(path))
    excluded |= collect_noise_ids(dynamic) | collect_noise_ids(teacher)
    old_pilot=ROOT/'results/stage3/isolated-pilot/summary.json'
    if old_pilot.exists(): excluded |= collect_noise_ids(read(old_pilot))
    # Historical pilot's fixed complete practice/OFF identity schedule.
    excluded |= {90000+f*100+t for f in range(4) for t in range(4)}
    excluded |= {95000+f*100+t for f in range(4) for t in range(2)}
    if set(NOISE_IDS)&excluded: raise ValueError('Fresh noise identity overlaps inherited evidence')
    binding={'inputs_bytes_sha256':{p:digest(ROOT/p) for p in INPUT_PATHS},
        'bound_scci_rh_source_bytes_sha256':freeze['full_scci_rh_source_bytes_sha256'],
        'dynamic_raw':{'path':raw.relative_to(ROOT).as_posix(),'sha256':digest(raw)},
        'dynamic_model_id':model.model_id,'teacher_library_id':library['library_id'],
        'teacher_generator':library['generator'],'teacher_resource_accounting':library['resource_accounting'],
        'excluded_prior_noise_ids':sorted(excluded),'noise_exclusion_scope':
        'all compact frozen observer receipts, inherited dynamic/teacher summaries, historical pilot fixed schedules'}
    for p,expected in binding['bound_scci_rh_source_bytes_sha256'].items():
        if digest(ROOT/p)!=expected: raise ValueError('Immutable historical source changed: '+p)
    return load_observer(),method,context,model,dose,domains,references,binding


def require_domain(context,support_s,horizon_s,action_prefix=()):
    values=np.asarray([support_s,horizon_s],float)
    if (not np.isfinite(values).all() or not context['qualified'] or action_prefix
            or context['action_prefix'] or context['instruction_hz']!=1.
            or context['task_time_offset_s']!=0.):
        raise ValueError('UNQUALIFIED_EMPTY_ACTION_BASELINE_DOMAIN')
    if (support_s<context['support_start_s']-1e-12 or support_s>context['support_end_s']+1e-12
            or abs(support_s/.005-round(support_s/.005))>1e-8):
        raise ValueError('OUTSIDE_COMMON_EXACT_PREFIX_SUPPORT_DOMAIN')
    index=round(horizon_s/.005)-5
    if not 0<=index<26 or abs(HORIZONS[index]-horizon_s)>1e-10:
        raise ValueError('UNQUALIFIED_FORECAST_HORIZON')
    allowance=float(context['allocation_m'][index])
    if not np.isfinite(allowance) or not 0<=allowance<=.015:
        raise ValueError('BASELINE_INTERVAL_EXCEEDS15MM')
    return allowance


@dataclass(frozen=True)
class FrozenForecast:
    created_s: float
    current_support_s: float
    targets_s: tuple[float,...]
    positions_m: tuple[tuple[float,float],...]
    allowances_m: tuple[tuple[float,float],...]
    context_id: str
    model_id: str
    empty_action_prefix: tuple
    sealed_observer_updates: int


class SealedObserver:
    def __init__(self,module,method,context,model_id):
        self.observer=module.Observer(module.Model(method))
        self.context,self.model_id=context,model_id
        self.sealed=False; self.accepted=0; self.freeze_record=None

    def update(self,measurement,now_s):
        if self.sealed: return {'accepted':False,'reason':'OBSERVER_PERMANENTLY_SEALED'}
        info=self.observer.update(asdict(measurement),now_s)
        if info['accepted']: self.accepted+=1
        return {'accepted':bool(info['accepted']),'reason':info['reason'],'reset':bool(info.get('reset',False))}

    def warmup(self,now_s):
        if self.sealed: raise ValueError('OBSERVER_PERMANENTLY_SEALED')
        result=self.observer.forecast(now_s)
        if not result['available']: raise ValueError('CAUSAL_OBSERVER_UNAVAILABLE')
        support=float(result['current_support_s'])
        allowance=require_domain(self.context,support,.150)
        return PredictionCommit(now_s,float(result['target_supports_s'][-1]),
            tuple(result['predictions_m'][-1]),(allowance,allowance),self.model_id,CONTEXT_ID)

    def freeze(self,now_s,action_prefix=()):
        if self.sealed: raise ValueError('OBSERVER_PERMANENTLY_SEALED')
        if abs(now_s-.975)>1e-10: raise ValueError('UNSUPPORTED_FREEZE_DECISION_CLOCK')
        for h in HORIZONS: require_domain(self.context,.950,float(h),action_prefix)
        result=self.observer.forecast(now_s)
        if (not result['available'] or abs(result['current_support_s']-.950)>1e-10
                or not np.allclose(result['target_supports_s'],TARGETS,rtol=0,atol=1e-10)):
            raise ValueError('EXACT_CAUSAL_FREEZE_SUPPORT_UNAVAILABLE')
        allowances=[require_domain(self.context,.950,float(h),action_prefix) for h in HORIZONS]
        self.freeze_record=FrozenForecast(now_s,.950,tuple(float(x) for x in TARGETS),
            tuple(tuple(float(x) for x in row) for row in result['predictions_m']),
            tuple((a,a) for a in allowances),CONTEXT_ID,self.model_id,tuple(action_prefix),self.accepted)
        self.sealed=True
        return self.freeze_record


class OneShotPermit:
    """One immutable choice, one resolution; no rearm within this trial."""
    def __init__(self,routes):
        if len(routes)!=2 or any(x not in (-1,0,1) for x in routes): raise ValueError('Invalid route choice')
        self._choice=tuple(routes); self._choice_hash=value_digest(self._choice)
        self.resolved=False; self.resolution=None

    @property
    def choice(self): return self._choice

    def resolve(self,now_s,*,guard_allowed,hard_off=False):
        if self.resolved: raise ValueError('ONE_SHOT_PERMIT_ALREADY_RESOLVED')
        if not np.isfinite(now_s) or abs(now_s-1.)>1e-10: raise ValueError('UNSUPPORTED_LAUNCH_CLOCK')
        if value_digest(self._choice)!=self._choice_hash: raise ValueError('IMMUTABLE_CHOICE_CHANGED')
        self.resolved=True
        authorized=bool(guard_allowed and not hard_off and any(self._choice))
        self.resolution={'resolved_at_s':now_s,'choice':list(self._choice),
            'choice_sha256':self._choice_hash,'authorized':authorized,
            'routes':list(self._choice if authorized else (0,0)),
            'state':'SPENT' if authorized else 'IRREVOCABLY_WITHHELD','rearm_allowed':False}
        return tuple(self.resolution['routes'])


def candidate_gates(*,baseline_qualified,reference_qualified,response_qualified,
                    interaction_qualified,interval_qualified,policy_enabled,route_tested):
    return {'baseline_domain_qualified':bool(baseline_qualified),
        'reference_qualified':bool(reference_qualified),'independent_actual_response_domain_qualified':bool(response_qualified),
        'learning_interaction_qualified':bool(interaction_qualified),
        'whole_vector_correction_interval_within25mm':bool(interval_qualified),
        'policy_enabled':bool(policy_enabled),'signed_route_independently_tested':bool(route_tested)}


def choose(frozen,reference,dynamic,dose,domains,*,policy_enabled,learning):
    baseline=np.asarray(frozen.positions_m); base_u=np.asarray(frozen.allowances_m)
    goal=np.asarray(reference.coefficients_m)@motor.task_basis(1.100)
    zero_score=float(np.sum((goal-baseline[-1])**2)); best=zero_score; routes=(0,0); candidates=[]
    for signs,name in ACTION_DOMAINS.items():
        row={'routes':list(signs),'domain_id':name}
        if name is None:
            gates=candidate_gates(baseline_qualified=True,reference_qualified=reference.qualified,
                response_qualified=False,interaction_qualified=not learning,interval_qualified=False,
                policy_enabled=policy_enabled,route_tested=False)
            candidates.append({**row,'gates':gates,'eligible':False,'failed_gates':[k for k,v in gates.items() if not v]})
            continue
        domain=domains[name]; trace=domain['trace']; effects=[]; joint=[]; residual=[]
        for target in frozen.targets_s:
            frames=() if target<1.-1e-12 else (FutureResponseFrame(1.,signs,.975),)
            response=predict_future_effect(dynamic,.975,target,frames,dose)
            indices=[i for i,t in enumerate(trace['physical_support_s']) if abs(t-target)<1e-10]
            if len(indices)!=1: raise ValueError('Independent response phase missing')
            index=indices[0]
            r=np.asarray(trace['empirical_error_allocation_m'][index])-np.asarray(trace['joint_gain_dose_error_m'][index])
            if not np.isfinite(r).all() or np.any(r<0): raise ValueError('Invalid independent response residual allocation')
            effects.append(response['effect_m']); joint.append(response['joint_gain_dose_error_m']); residual.append(r)
        prediction=baseline+np.asarray(effects)
        actual_u=base_u+np.asarray(joint)+np.asarray(residual)
        correction_u=actual_u+reference.position_error_allocation_m
        score=float(np.sum((goal-prediction[-1])**2))
        gates=candidate_gates(baseline_qualified=True,reference_qualified=reference.qualified,
            response_qualified=domain['qualified'],interaction_qualified=not learning,
            interval_qualified=np.isfinite(correction_u).all() and np.max(correction_u)<=.025,
            policy_enabled=policy_enabled,route_tested=True)
        eligible=all(gates.values())
        row.update(gates=gates,failed_gates=[k for k,v in gates.items() if not v],eligible=eligible,
            predicted_positions_m=prediction.tolist(),total_position_allowance_m=actual_u.tolist(),
            correction_against_reference_allowance_m=correction_u.tolist(),
            joint_gain_dose_error_m=joint,independent_response_residual_allowance_m=np.asarray(residual).tolist(),
            independent_reference_allocation_m=reference.position_error_allocation_m,score_m2=score,
            response_validation_learning_enabled=False,independent_recording_id=domain['recording_id'])
        candidates.append(row)
        if eligible and score<best-1e-15: best,routes=score,signs
    return {'selected_routes':list(routes),'zero_action_score_m2':zero_score,'selected_score_m2':best,
        'reference_position_m':goal.tolist(),'reference':asdict(reference),'candidates':candidates,
        'reason':'MATCHED_OBSERVE_ONLY' if not policy_enabled else
                 ('ZERO_ACTION_BEST_OR_CANDIDATES_UNAVAILABLE' if not any(routes) else 'ONE_SHOT_SELECTED'),
        'learner_sensing':'external-only fallback; no qualified live learner neural increment',
        'candidate_future_response_counted':1 if any(routes) else 0,
        'future_measurement_used':False,'future_monitor_used':False,'private_parameters_used':False}


class Controller:
    def __init__(self,module,method,context,dynamic,dose,domains,reference,*,policy_enabled):
        self.observer=SealedObserver(module,method,context,dynamic.model_id)
        self.guard=DelayedResidualGuard(); self.queue=deque(); self.dynamic=dynamic
        self.dose,self.domains,self.reference=dose,domains,reference
        self.policy_enabled=policy_enabled; self.extra_latch=None
        self.update_log=[]; self.warmup=[]; self.freeze_record=None; self.decision=None
        self.permit=None; self.diagnostic=None; self.future_commits=[]; self.launch_check=None
        self.freeze_hash=None; self.forecast_authority_expired=False

    def step(self,measurement,now_s):
        if measurement is not None: self.queue.append(measurement)
        while self.queue and self.queue[0].available_s<=now_s+1e-12:
            arrived=self.queue.popleft()
            if not self.observer.sealed:
                info=self.observer.update(arrived,now_s)
                self.update_log.append({'support_s':arrived.support_s,'available_s':arrived.available_s,
                                        'processed_at_s':now_s,**info})
                if not info['accepted']: self.extra_latch=self.extra_latch or 'OBSERVER_UPDATE_REJECTED'
            self.guard.observe(MeasuredPosition(arrived.support_s,arrived.available_s,arrived.position_m,arrived.valid),now_s=now_s)
            if self.freeze_record is not None and self.diagnostic is None and abs(arrived.support_s-.975)<1e-10:
                residual=abs(np.asarray(self.freeze_record.positions_m[0])-arrived.position_m)
                allowance=np.asarray(self.freeze_record.allowances_m[0]); passed=bool(np.all(residual<=allowance+1e-12))
                self.diagnostic={'created_s':.975,'target_support_s':.975,'observed_support_s':arrived.support_s,
                    'observed_available_s':arrived.available_s,'checked_at_s':now_s,
                    'position_m':list(self.freeze_record.positions_m[0]),'absolute_residual_m':residual.tolist(),
                    'allowance_m':allowance.tolist(),'passed':passed,'prelaunch_available':now_s<=1.+1e-12}
                if not passed: self.extra_latch=self.extra_latch or 'FROZEN_CURRENT_TARGET_RESIDUAL_EXCEEDED'
        timed=self.guard.check(now_s=now_s)
        index=round(now_s/.005)
        if .200-1e-12<=now_s<=.800+1e-12 and index%5==0:
            try:
                commit=self.observer.warmup(now_s)
                accepted=self.guard.commit(commit)
                self.warmup.append({'forecast':asdict(commit),'guard_commit':accepted})
            except ValueError as exc:
                self.extra_latch=self.extra_latch or str(exc)
                self.warmup.append({'created_s':now_s,'rejection':str(exc)})
        if abs(now_s-.975)<1e-10:
            self.freeze_record=self.observer.freeze(now_s)
            self.freeze_hash=value_digest(self.freeze_record)
            self.decision=choose(self.freeze_record,self.reference,self.dynamic,self.dose,self.domains,
                                 policy_enabled=self.policy_enabled,learning=True)
            for i in range(1,26):
                commit=PredictionCommit(.975,self.freeze_record.targets_s[i],self.freeze_record.positions_m[i],
                    self.freeze_record.allowances_m[i],self.dynamic.model_id,CONTEXT_ID)
                accepted=self.guard.commit(commit)
                self.future_commits.append({'forecast':asdict(commit),'guard_commit':accepted})
            self.permit=OneShotPermit(self.decision['selected_routes'])
        routes=(0,0)
        if abs(now_s-1.)<1e-10:
            fresh=self.guard.check(now_s=now_s)
            allowed=bool(fresh['continuation_allowed'] and self.extra_latch is None
                         and self.diagnostic is not None and self.diagnostic['passed'])
            self.launch_check={**fresh,'independent_diagnostic_latch':self.extra_latch,
                'current_diagnostic_available':self.diagnostic is not None,'all_launch_checks_passed':allowed}
            routes=self.permit.resolve(now_s,guard_allowed=allowed)
        if now_s>1.100+1e-12: self.forecast_authority_expired=True
        if self.freeze_record is not None and value_digest(self.freeze_record)!=self.freeze_hash:
            raise AssertionError('Sealed forecast changed')
        return routes

    def record(self):
        return {'observer_updates':self.update_log,'observer_accepted_updates':self.observer.accepted,
            'observer_updates_after_seal':0,'observer_permanently_sealed':self.observer.sealed,
            'warmup_commitments':self.warmup,'frozen_forecast':asdict(self.freeze_record),
            'frozen_forecast_sha256':self.freeze_hash,'decision':self.decision,
            'frozen_current_target_diagnostic':self.diagnostic,'future_commitments':self.future_commits,
            'residual_checks':self.guard.scored,'residual_guard_latched_reason':self.guard.latched_reason,
            'separate_latched_reason':self.extra_latch,'pending_forecasts_at_end':len(self.guard.pending),
            'launch_clock_check':self.launch_check,'permit':self.permit.resolution,
            'forecast_authority_expired':self.forecast_authority_expired,
            'authority_support_end_s':1.100,'last_target_normal_arrival_s':1.125,'last_target_expiry_s':1.150}


def controller_replay(measurements,inputs,arm):
    module,method,context,dynamic,dose,domains,references,_=inputs
    controller=Controller(module,method,context,dynamic,dose,domains,references[arm],policy_enabled=arm!='observe_only')
    rows=[p if isinstance(p,ResponsePosition) else ResponsePosition(**p) for p in measurements]
    if len(rows)!=600: raise ValueError('Complete three-second observed record required')
    for i,row in enumerate(rows):
        routes=controller.step(row,i*.005)
        if any(routes): raise AssertionError('Primary actual replay unexpectedly authorized intervention')
    while controller.queue: controller.step(None,controller.queue[0].available_s)
    return controller.record()


class PrimaryAuthorizationFailure(RuntimeError):
    def __init__(self,evidence):
        self.evidence=evidence
        super().__init__('Primary actual-domain replay unexpectedly authorized a nonzero frame; stopped before delivery')


def run_trial(*,theta,family,arm,noise,noise_id,body_step,inputs,session):
    module,method,context,dynamic,dose,domains,references,_=inputs
    heldout=session=='transfer_off'; learning=session=='practice'
    c=replace(config(),body_integration_step_s=body_step)
    world=motor._World(2,c,heldout=heldout); world.theta=np.asarray(theta).copy()
    controller=Controller(module,method,context,dynamic,dose,domains,references[arm],policy_enabled=arm!='observe_only') if learning else None
    measurements=[]; times=[]; positions=[]
    for i in range(600):
        t=i*.005
        measured=ResponsePosition(t,t+.025,tuple(world.x+noise[i]))
        measurements.append(asdict(measured)); times.append(t); positions.append(world.x.copy())
        routes=controller.step(measured,t) if learning else (0,0)
        if any(routes):
            raise PrimaryAuthorizationFailure({'processed_at_s':t,'arm':arm,'family':family,
                'session':session,'measurement_noise_id':noise_id,'measurements':measurements,
                'controller':controller.record(),'delivery_executed':False})
        world.advance(t+.005,np.zeros(2),family,learning=learning,heldout=heldout)
    if learning:
        while controller.queue: controller.step(None,controller.queue[0].available_s)
        control=controller.record()
    else:
        control={'reason':'OUTPUT_HARD_OFF_ASSESSMENT','learning_enabled':False,
                 'observer_updates':[],'launched_profiles':0,'delayed_command_queue':[],
                 'permit':{'state':'HARD_OFF','rearm_allowed':False}}
    return {'session':session,'arm':arm,'measurement_noise_id':noise_id,'learning_enabled':learning,
        'heldout_faster_cadence':heldout,'measurements':measurements,'controller':control,
        'metrics':motor._metrics(times,positions,c,heldout=heldout),'launched_profiles':0,
        'launches':[],'actual_monitor_records':[],'pending_monitor_records':[],
        'actual_dose_pending_response_trace':[],
        'pending_response_status':'NO_DELIVERED_PROFILE; active monitoring and tail release not exercised',
        'private_evaluator_only':{'times_s':times,'positions_m':np.asarray(positions).tolist(),
            'theta_initial_m':np.asarray(theta).tolist(),'theta_after_m':world.theta.tolist(),
            'actual_sensor_noise_m':noise.tolist(),'true_charge_used_only_by_body':True,
            'active_delivery_path_implemented':False}},world.theta.copy()


def preflight():
    inputs=load_inputs(); binding=inputs[-1]
    for name in CODE_PATHS:
        if not (PACKAGE/name).is_file(): raise ValueError('Missing frozen study code: '+name)
    receipt={'schema':'scci_rh.stage3.frozen-observer-pilot.preflight.v1','date':'2026-10-12',
        'classification':'PREGENERATION_PROTOCOL_SOURCE_INPUT_NOISE_FREEZE',
        'code_bytes_sha256':{p:digest(PACKAGE/p) for p in CODE_PATHS},'bindings':binding,
        'baseline_context':inputs[2],'noise_ids':list(NOISE_IDS),'grids_s':list(GRIDS),
        'arms':list(ARMS),'generator_only_families':list(motor.FAMILIES),
        'practice_trials_per_arm_family_grid':1,'practice_seconds':3.,'assessment_seconds_each':3.,
        'sessions':['practice','retention_off','transfer_off'],'subject_seed':2,'initial_scale':1.,
        'future_dose_assumption':asdict(inputs[4]),'learning_interaction_qualified':False,
        'python':platform.python_version(),'numpy':np.__version__,'scipy':importlib.metadata.version('scipy'),
        'independence':'12 new sensor-noise arrays; same subject and finite synthetic models',
        'root_review_required_before_generation':True}
    path=PACKAGE/'preflight.json'
    if path.exists():
        if canonical(read(path))!=canonical(receipt):
            raise ValueError('Existing preflight is immutable; use a separately versioned study for changes')
    else: save(path,receipt)
    return receipt


def checked_preflight():
    receipt=read(PACKAGE/'preflight.json')
    for p,expected in receipt['code_bytes_sha256'].items():
        if digest(PACKAGE/p)!=expected: raise ValueError('Frozen study code changed: '+p)
    inputs=load_inputs()
    if canonical(inputs[-1])!=canonical(receipt['bindings']) or canonical(inputs[2])!=canonical(receipt['baseline_context']):
        raise ValueError('Frozen inherited input/context changed')
    if (platform.python_version()!=receipt['python'] or np.__version__!=receipt['numpy']
            or importlib.metadata.version('scipy')!=receipt['scipy']):
        raise ValueError('Frozen Python/NumPy/SciPy environment mismatch')
    return receipt,inputs


def generate(output):
    receipt,inputs=checked_preflight()
    review=read(PACKAGE/'root-review.json')
    if review['preflight_sha256']!=digest(PACKAGE/'preflight.json') or review['authorized'] is not True:
        raise ValueError('Root pre-generation review missing or stale')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()): raise ValueError('Output directory must be empty; preserve any prior/partial generation')
    files=[]
    for family_index,family in enumerate(motor.FAMILIES):
        noises={session:np.random.default_rng(NOISE_IDS[family_index*3+j]).normal(0.,.0015,(600,2))
                for j,session in enumerate(receipt['sessions'])}
        for body_step in GRIDS:
            runs=[]
            for arm in ARMS:
                initial=motor._World(2,replace(config(),body_integration_step_s=body_step)).theta.copy()
                try:
                    practice,theta=run_trial(theta=initial,family=family,arm=arm,noise=noises['practice'],
                        noise_id=NOISE_IDS[family_index*3],body_step=body_step,inputs=inputs,session='practice')
                except PrimaryAuthorizationFailure as exc:
                    save(output/'unexpected-authorization-failure.json',exc.evidence)
                    raise
                assessments={}
                for j,session in enumerate(('retention_off','transfer_off'),1):
                    row,_=run_trial(theta=theta*(1-config().forgetting_fraction),family=family,arm=arm,
                        noise=noises[session],noise_id=NOISE_IDS[family_index*3+j],body_step=body_step,inputs=inputs,session=session)
                    assessments[session]=row
                runs.append({'arm':arm,'practice':practice,'assessments':assessments})
            record={'schema':'scci_rh.stage3.frozen-observer-pilot.raw.v1','family':family,
                'body_integration_step_s':body_step,'preflight_sha256':digest(PACKAGE/'preflight.json'),
                'review_sha256':digest(PACKAGE/'root-review.json'),'runs':runs}
            name=f'{family}-{round(body_step*1e6)}us.json.gz'; data=encoded(record)
            (output/name).write_bytes(data); files.append({'path':name,'bytes':len(data),
                'sha256':hashlib.sha256(data).hexdigest()})
            print('Generated '+name,flush=True)
    # Verify code/input freeze again after every outcome has been produced.
    checked_preflight()
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true',help='Bind protocol/code/inputs before root review; generate no outcomes')
    parser.add_argument('--generate',type=Path,help='Generate the predeclared study only after root-review.json approval')
    args=parser.parse_args()
    if args.freeze:
        result=preflight(); print('Pre-generation freeze: '+digest(PACKAGE/'preflight.json'))
    elif args.generate: generate(args.generate)
    else: parser.print_help()


if __name__=='__main__': main()
