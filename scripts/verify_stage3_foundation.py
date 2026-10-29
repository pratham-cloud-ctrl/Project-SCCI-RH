"""Audit artifact consistency and declared model boundaries, not biological efficacy."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
from importlib.metadata import version

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/stage3'
DOC=ROOT/'docs/stage3'
sys.path.insert(0,str(ROOT/'scripts'))
from artifact_hashes import canonical_json_digest


def read(name):
    path=DATA/name
    return json.loads(gzip.decompress(path.read_bytes()).decode() if name.endswith('.gz') else path.read_text(encoding='utf-8'))


def inputs():
    files=sorted((ROOT/'src/scci_rh/stage3').glob('*.py'))
    files += [ROOT/'scripts/run_stage3_studies.py',ROOT/'scripts/build_stage3_figures.py',
              ROOT/'scripts/stage3_ngspice_check.py',ROOT/'requirements-lock.txt']
    files.append(ROOT/'scripts/stage3_electrical_sweep.py')
    files.append(ROOT/'scripts/verify_stage3_foundation.py')
    files.append(ROOT/'scripts/stage3_pressure_convergence_probe.py')
    digest={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(
        p.read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest() for p in files}
    for name in ('system-design.json','control-contracts.json'):
        path=ROOT/'docs/stage2'/name
        digest[str(path.relative_to(ROOT)).replace('\\','/')]=canonical_json_digest(path)
    return digest


def verify():
    checks=[]
    electrical=read('electrical.json')['cases']
    assert len(electrical)==7
    cases={r['id']:r for r in electrical}
    for name in ('motor_reference','pressure_reference'):
        result=cases[name]['summary']
        assert result['qualified']
        assert result['measured_cathodic_charge_C'] != result['true_cathodic_charge_C']
        assert result['drive_net_uncertainty_C'] >= result['charge_uncertainty_C'] > 0
    for name in ('high_load_compliance','prepolarized_motor','interrupted_motor'):
        assert not cases[name]['summary']['qualified']
        assert cases[name]['summary']['true_cathodic_charge_C']>0
    independent=read('ngspice-crosscheck.json')
    assert independent['status']=='passed' and len(independent['runs'])==4
    assert all(r['passed'] for r in independent['runs']+independent['refinement_checks'])
    checks.append('Seven event-aligned electrical witnesses; observed charge is distinct, failed pulses retain dose; four actual local ngspice comparisons pass')
    sweep=read('electrical-sweep.json')
    assert sweep['status']=='passed_under_assumptions'
    assert sweep['ode_intervals']['case_count']==150 and sweep['ode_intervals']['passed']
    assert sweep['monitor_phases']['case_count']==500 and sweep['monitor_phases']['passed_under_assumptions']
    assert sweep['monitor_phases']['eligible_cases']==493 and sweep['monitor_phases']['excluded_cases']==7
    checks.append('Independent numerical sweeps record 150 ODE intervals and 500 ADC cases, with exclusions retained separately from eligible bound checks')

    motor=read('motor-raw.json.gz')['runs']
    motor_summary=read('motor-summary.json')['runs']
    assert len(motor)==len(motor_summary)==12
    labels={'nominal','fast_response_sensitivity','conditional_fast_response_assumed_delivery'}
    assert {r['configuration_label'] for r in motor}==labels
    for label in labels:
        assert {r['study']['seed'] for r in motor if r['configuration_label']==label}=={0,1,2,3}
    total_pulses={label:0 for label in labels}
    for row,summary_row in zip(motor,motor_summary):
        study=row['study'];conditional=row['configuration_label'].startswith('conditional')
        assert study['config']['pipeline_delay_s']==.01185
        assert study['config']['maximum_prediction_horizon_s']==.1
        assert study['calibration']['same_budget_all_conditions']
        assert study['delivery_model']==('UNQUALIFIED_NOMINAL_ASSUMPTION' if conditional else 'independent electrical callback')
        assert set(study['families'])=={'favorable','zero','harmful','dependent'}
        for family,values in study['families'].items():
            assert len(values['conditions'])==7
            for condition,result in values['conditions'].items():
                s=result['summary'];saved=summary_row['study']['families'][family]['conditions'][condition]
                assert s==saved['summary'] and result['practice_blocks']==saved['practice_blocks']
                assert s['assistance_off_verified']
                for name in ('retention_off','transfer_off'):
                    assert s[name]['pulse_count']==0 and s[name]['assistance']=='OFF'
                total_pulses[row['configuration_label']]+=sum(b['pulse_count'] for b in result['practice_blocks'])
                assert s['practice_seconds']==12.
                if 'trace' in result:
                    for phase in ('practice','retention','transfer'):
                        for sample in result['trace'][phase]['samples']:
                            assert sample['source_state_time_s'] <= sample['time_s']
                            assert sample['external_measurement_time_s'] <= sample['source_state_time_s']
        if study['seed']==0:assert len(study['negative_controls'])==6
    assert total_pulses['conditional_fast_response_assumed_delivery']>0
    checks.append('Twelve motor studies preserve three evidence branches, four plasticity families, seven fair arms, conditional intervention and output-OFF assessment')

    pressure=read('pressure-raw.json.gz')['runs']
    summaries=read('pressure-summary.json')['runs']
    assert len(pressure)==len(summaries)==156
    scenarios={r['metadata']['scenario']['name'] for r in pressure}
    assert len(scenarios)==13
    grouped={}
    for r,s in zip(pressure,summaries):
        assert {k:r[k] for k in ('metadata','calibration','summary')}==s
        m=r['metadata'];t=r['trace'];grouped[(m['scenario']['name'],m['seed'],m['mode'])]=r
        assert not m['neural_input_to_controller']
        assert m['oracle_excluded_from_claims']==(m['mode']=='oracle')
        assert m['config']['waveform_sample_hz']==200 and m['config']['policy_period_s']==.25
        for i,time in enumerate(t['time_s']):
            assert 0<=t['actual_delivered_fraction'][i]<=1
            assert 0<=t['admitted_reference_frames'][i]<=30
            if m['mode']=='off' and time>=m['config']['calibration_end_s']:assert t['requested_fraction'][i]==0
            if t['observation_fresh'][i]:
                assert t['observation_support_start_s'][i] <= t['observation_peak_s'][i] <= t['observation_support_end_s'][i]
                assert t['observation_support_end_s'][i] <= t['observation_arrival_s'][i] <= time
    for name in scenarios:
        for seed in range(4):
            off=grouped[(name,seed,'off')];feedback=grouped[(name,seed,'feedback')]
            assert off['calibration']==feedback['calibration']
            n=next(i for i,t in enumerate(off['trace']['time_s']) if t>=144)
            assert off['trace']['true_sbp_pa'][:n]==feedback['trace']['true_sbp_pa'][:n]
    checks.append('156 pressure runs cover thirteen families, paired equal calibration, observable support timing, whole frames and explicitly privileged oracle diagnostics')
    fallbacks=read('pressure-fallbacks-raw.json.gz')['runs']
    fallback_summaries=read('pressure-fallbacks-summary.json')['runs']
    assert len(fallbacks)==len(fallback_summaries)==8
    assert all({k:r[k] for k in ('metadata','calibration','summary')}==s
               for r,s in zip(fallbacks,fallback_summaries))
    assert {r['metadata']['config']['fallback'] for r in fallbacks}=={'finite_hold','ramp'}
    checks.append('Eight finite hold/ramp cases supplement stop; nadir, support loss and overshoot remain measured model outcomes')
    probe=read('pressure-convergence-probe.json')
    assert probe['status']=='bounded_diagnostic_only' and probe['experiment']['run_count']==6
    assert probe['experiment']['delivery']=='chosen_reference_surrogate'
    assert len(probe['runs'])==6 and {r['scenario'] for r in probe['runs']}=={'nominal','no_response'}
    assert {r['integration_step_s'] for r in probe['runs']}=={.005,.0025,.00125}
    assert len({r['noise_witness']['samples_sha256'] for r in probe['runs']})==1
    assert all(r['noise_witness']['scalar_call_count']==84001 for r in probe['runs'])
    assert probe['source_identity']['normalized_lf_sha256']==hashlib.sha256(
        (ROOT/'src/scci_rh/stage3/pressure.py').read_text(encoding='utf-8').replace('\r\n','\n').encode()).hexdigest()
    checks.append('Six separately scoped pressure refinement probes retain identical actual noise, fixed observation schedules and chosen surrogate delivery; no general convergence pass')

    matrix={r['verification_id'] for r in csv.DictReader((ROOT/'docs/stage1/verification-matrix.csv').open(encoding='utf-8'))}
    progress=list(csv.DictReader((DOC/'verification-progress.csv').open(encoding='utf-8')))
    assert all(r['verification_id'] in matrix for r in progress)
    # Foundation evidence keeps its original partial-study scope when later
    # packages close the selected digital investigation. Require an explicit
    # current status and, for closeout, the separate reviewed exit ledger.
    status=(DOC/'README.md').read_text(encoding='utf-8').splitlines()[2]
    assert status.startswith(('**In progress,', '**Complete within selected digital scope,'))
    if status.startswith('**Complete within selected digital scope,'):
        assert '**COMPLETE WITHIN SELECTED DIGITAL SCOPE**' in (DOC/'exit-review.md').read_text(encoding='utf-8')
    links=0
    for doc in DOC.glob('*.md'):
        text=doc.read_text(encoding='utf-8');assert text.count('```')%2==0
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if target.startswith(('https:','http:','#','mailto:')):continue
            assert (doc.parent/target.split('#')[0]).resolve().exists(),f'Broken {doc.name}: {target}'
            links+=1
    for stem in ('electrical-delivery','pressure-comparisons','conditional-motor-comparisons'):
        assert (DOC/'figures'/f'{stem}.png').stat().st_size>10000
        assert '<svg' in (DOC/'figures'/f'{stem}.svg').read_text(encoding='utf-8')
    visual=json.loads((ROOT/'provenance/stage3-visual-review.json').read_text(encoding='utf-8'))
    assert len(visual['files'])==6
    for name,entry in visual['files'].items():
        path=ROOT/name
        content=path.read_bytes() if path.suffix=='.png' else path.read_text(encoding='utf-8').replace('\r\n','\n').encode()
        assert hashlib.sha256(content).hexdigest()==entry['sha256'],f'Figure differs from visual review: {name}'
    checks.append(f'{links} local dossier links resolve; progress IDs match Stage1; three SVG/PNG figure pairs exist; current stage status and separate closeout ledger are explicit')
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):(canonical_json_digest(p) if p.suffix=='.json'
                                                    else hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(DATA.iterdir()) if p.is_file()}
    return {'schema':'scci_rh.stage3.foundation-verification.v1','date':'2026-10-12',
            'scope':'artifact and model-boundary audit; Stage3 partial; no biological or implant qualification',
            'checks':checks,'counts':{'electrical_cases':7,'motor_studies':12,'motor_condition_families':336,
                                    'pressure_runs':156,'additional_fallback_runs':8,'bounded_pressure_refinement_probes':6},
            'observed_motor_practice_pulses':total_pulses,'input_normalized_hashes':inputs(),
            'result_hash_policy':'Canonical parsed JSON for .json; exact binary bytes for .gz. Git manifest separately binds every committed blob.',
            'result_semantic_or_binary_hashes':hashes}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-receipt',action='store_true');args=parser.parse_args()
    result=verify();path=ROOT/'provenance/stage3-verification.json'
    if args.write_receipt:
        path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    else:
        receipt=json.loads(path.read_text(encoding='utf-8'))
        assert result==receipt,'Stage3 receipt does not match current artifacts'
    print(json.dumps(result,indent=2))
    if args.write_receipt:
        runtime={'date':'2026-10-12','scope':'Stage3 saved-model audit and local reproduction environment; underlying studies retain their own dates',
                 'python':platform.python_version(),'platform':platform.system(),
                 'packages':{p:version(p) for p in ('numpy','scipy','matplotlib','reportlab','Pillow','pypdf')}}
        (ROOT/'provenance/stage3-environment.json').write_text(json.dumps(runtime,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
