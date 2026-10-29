"""Reproduce the full-loop foundation studies; no human efficacy is inferred.

Results contain raw witnesses, paired-seed summaries and explicit assumption IDs.
--check compares numeric outputs with tight tolerances without rewriting files.
Optional ngspice library crosscheck is a separately scoped local verification.
--jobs 1..4 optionally parallelizes independent motor configuration/seed studies;
electrical, pressure and fallback studies remain serial. The default is 1 job.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict,replace
from concurrent.futures import ProcessPoolExecutor
import hashlib
import gzip
import io
import json
from multiprocessing import get_context
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from scci_rh.stage3.electrical import Load,simulate_pulse,observe_delivery,characterize,MotorDelivery,PressureDelivery

OUT=ROOT/'results/stage3'


def electrical_study():
    cases=[
        ('motor_reference',.003,.0002,24.,Load(),0.,{}),
        ('pressure_reference',.003,.0003,24.,Load(),0.,{}),
        ('high_load_compliance',.018,.0005,48.,Load(2000,5e-7),4.,{}),
        ('prepolarized_motor',.003,.0002,24.,Load(),4.,{}),
        ('interrupted_motor',.003,.0002,24.,Load(),0.,{'interrupted_after_phase1':True}),
        ('recharge_mismatch',.003,.0002,24.,Load(),0.,{'recharge_gain':1.02}),
        ('short_low_current',.0001,.00005,16.,Load(),0.,{}),
    ]
    outputs=[]
    for name,i,width,rail,load,initial,options in cases:
        pulse=simulate_pulse(i,width,rail,load,initial,**options)
        observation=observe_delivery(pulse)
        summary=characterize(i,width,rail,load,initial,**options)
        outputs.append({'id':name,'input':{'current_A':i,'phase_s':width,'boost_V':rail,
                        'load':asdict(load),'initial_polarization_V':initial,**options},
                        'summary':summary,'segments':[asdict(s) for s in pulse['segments']],
                        'trace':{k:observation[k].tolist() for k in
                                 ('times_s','current_A','terminal_truth_V','polarization_truth_V')},
                        'observed_delivery':{k:v for k,v in observation.items() if not isinstance(v,np.ndarray)}})
    return {'schema':'scci_rh.stage3.electrical-study.v1','scope':'exact reduced electrical loads; no chemistry or efficacy',
            'cases':outputs}


def close_nested(actual,expected,path='root'):
    if isinstance(actual,dict):
        assert isinstance(expected,dict) and actual.keys()==expected.keys(),f'Keys differ at {path}'
        for key,value in actual.items():close_nested(value,expected[key],f'{path}.{key}')
    elif isinstance(actual,(list,tuple)):
        # JSON arrays represent both dataclass tuples and runtime lists.
        assert isinstance(expected,(list,tuple)) and len(actual)==len(expected),f'Length differs at {path}'
        if actual and all(v is None or (isinstance(v,(float,int)) and not isinstance(v,bool)) for v in actual):
            assert all(v is None or (isinstance(v,(float,int)) and not isinstance(v,bool)) for v in expected),f'Types differ at {path}'
            assert [v is None for v in actual]==[v is None for v in expected],f'Missingness differs at {path}'
            assert np.allclose(np.asarray(actual,dtype=float),np.asarray(expected,dtype=float),
                               rtol=2e-8,atol=1e-11,equal_nan=True),f'Numeric series differs at {path}'
            return
        for index,(a,e) in enumerate(zip(actual,expected)):close_nested(a,e,f'{path}[{index}]')
    elif isinstance(actual,(float,int)) and not isinstance(actual,bool):
        assert isinstance(expected,(int,float)) and np.isclose(actual,expected,rtol=2e-8,atol=1e-11),f'Numeric difference at {path}'
    else:assert actual==expected,f'Value differs at {path}'


def record(name,value,check):
    target=OUT/name
    if check:
        contents=gzip.decompress(target.read_bytes()).decode('utf-8') if name.endswith('.gz') else target.read_text(encoding='utf-8')
        close_nested(value,json.loads(contents))
        print(f'{name}: reproduced within declared numeric tolerances')
    else:
        OUT.mkdir(parents=True,exist_ok=True)
        if name.endswith('.gz'):
            buffer=io.BytesIO()
            with gzip.GzipFile(filename='',mode='wb',fileobj=buffer,mtime=0) as file:
                file.write(json.dumps(value,separators=(',',':'),allow_nan=False).encode('utf-8'))
            target.write_bytes(buffer.getvalue())
        else:
            target.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(f'{name}: written')


def motor_study_worker(task):
    """Picklable independent study; electrical state is fresh in every task."""
    from scci_rh.stage3.motor import run_study
    label,seed,config=task
    print(f'Motor {label} seed{seed}: running',flush=True)
    study=run_study(seed=seed,config=config,
        delivery=None if label=='conditional_fast_response_assumed_delivery' else MotorDelivery(),
        faults=('shuffled_expert','incorrect_map','stale_external','artifact_recovery','saturation','source_drift') if seed==0 else ())
    return {'configuration_label':label,'study':study}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--module',choices=['electrical','pressure','fallbacks','motor','all'],default='all')
    parser.add_argument('--jobs',type=int,choices=range(1,5),default=1,
                        help='Independent motor configuration/seed workers (1..4, default 1); other modules remain serial')
    args=parser.parse_args()
    record('electrical.json',electrical_study(),args.check)
    if args.module=='electrical':return
    # Application APIs are deliberately independent of simulator hidden states.
    if args.module in ('pressure','all'):
        from scci_rh.stage3.pressure import run_batch
        pressure=run_batch(seeds=(0,1,2,3),delivery=PressureDelivery())
        record('pressure-raw.json.gz',{'schema':'scci_rh.stage3.pressure-batch.v1','runs':pressure},args.check)
        record('pressure-summary.json',{'schema':'scci_rh.stage3.pressure-summary.v1',
            'runs':[{k:r[k] for k in ('metadata','calibration','summary')} for r in pressure]},args.check)
        if args.module=='pressure':return
    if args.module in ('fallbacks','all'):
        from scci_rh.stage3.pressure import run_study as pressure_run,PressureConfig
        fallbacks=[pressure_run(seed,'sensor_loss','feedback',PressureDelivery(),
                               replace(PressureConfig(),fallback=policy))
                   for seed in (0,1,2,3) for policy in ('finite_hold','ramp')]
        record('pressure-fallbacks-raw.json.gz',{'schema':'scci_rh.stage3.pressure-fallbacks.v1','runs':fallbacks},args.check)
        record('pressure-fallbacks-summary.json',{'schema':'scci_rh.stage3.pressure-fallback-summary.v1',
               'runs':[{k:r[k] for k in ('metadata','calibration','summary')} for r in fallbacks]},args.check)
        if args.module=='fallbacks':return
    if args.module in ('motor','all'):
        from scci_rh.stage3.motor import MotorConfig
        configurations=[('nominal',MotorConfig()),
                        ('fast_response_sensitivity',replace(MotorConfig(),motor_onset_delay_s=.005)),
                        ('conditional_fast_response_assumed_delivery',replace(MotorConfig(),motor_onset_delay_s=.005))]
        tasks=[(label,seed,config) for label,config in configurations for seed in (0,1,2,3)]
        if args.jobs==1:
            motor=[motor_study_worker(task) for task in tasks]
        else:
            # map retains the exact branch/seed order irrespective of completion
            # order. Spawn also avoids inheriting mutable parent process state.
            with ProcessPoolExecutor(max_workers=args.jobs,mp_context=get_context('spawn')) as executor:
                motor=list(executor.map(motor_study_worker,tasks))
        record('motor-raw.json.gz',{'schema':'scci_rh.stage3.motor-batch.v1','runs':motor},args.check)
        record('motor-summary.json',{'schema':'scci_rh.stage3.motor-summary.v1',
               'runs':[{'configuration_label':r['configuration_label'],'study':
                        {k:v for k,v in r['study'].items() if k not in ('families','negative_controls')} |
                        {'families':{f:{'conditions':{c:{'summary':v['summary'],'practice_blocks':v['practice_blocks']}
                                                    for c,v in values['conditions'].items()},
                                        'contrasts':values['contrasts']}
                                     for f,values in r['study']['families'].items()},
                         'negative_controls':{f:v['metrics'] for f,v in r['study']['negative_controls'].items()}}}
                       for r in motor]},args.check)


if __name__=='__main__':main()
