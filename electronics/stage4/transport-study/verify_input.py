"""Independent analytic input/power audit. Does not import input_study."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
checks=0


def check(ok,reason):
    global checks
    checks+=1
    if not ok:raise AssertionError(reason)


def close(a,b,reason,atol=1e-12):
    check(math.isclose(a,b,rel_tol=1e-10,abs_tol=atol),reason)


def sha(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n').replace(b'\r',b'\n')).hexdigest()


def verify():
    d=json.loads((HERE/'input-results.json').read_text())
    for p,h in d['source_sha256_lf'].items():check(sha(ROOT/p)==h,'source binding '+p)
    native=json.loads((ROOT/'electronics/stage4/monitoring-transport/connectivity.json').read_text())
    parts={p['ref']:p for p in native['parts']}
    for ref,value in [('R120','4.99k 0.1%'),('R121','2.49k 0.1%'),('R122','2.4k 0.1%'),('R123','2k 0.1%')]:
        check(parts[ref]['value']==value,'native divider '+ref)
    for row in d['divider_cases']:
        vs,va,vb,a,b,r,rin=[row[k] for k in ('source_V','scaled_V','ADC_V','top_ohm','bottom_ohm','series_ohm','Rin_ohm')]
        close((va-vs)/a+va/b+(va-vb)/r,0,'divider KCL',atol=1e-15)
        close((vb-va)/r+(vb-2.5)/rin,0,'ADC KCL',atol=1e-15)
        rt,rb=(4990,2490) if row['source']=='PACK_BUS' else (2400,2000)
        close(row['nominal_unloaded_V'],vs*rb/(rt+rb),'nominal ratio')
        close(row['reconstructed_source_V'],vb*(rt+rb)/rb,'loaded reconstruction')
        check(0<vb<5.12,'input range')
    for row in d['direct_cases']:
        close((row['ADC_V']-row['source_V'])/110+(row['ADC_V']-2.5)/row['Rin_ohm'],0,'direct KCL',atol=1e-15)
        close(row['error_V'],row['ADC_V']-row['source_V'],'direct error')
    with np.load(HERE/'input-traces.npz') as data:
        for row in d['filter_cases']:
            key=row['id'];t=data[key+'_time_s'];y=data[key+'_filtered_A'];src=data[key+'_source_A']
            tau=row['pole_time_constant_s'];fc=row['cutoff_3dB_Hz_assumed']
            close(1/(1+(2*math.pi*fc*tau)**2),1/math.sqrt(2),'combined cutoff')
            analytic=np.zeros_like(t);true=np.zeros_like(t)
            for when,delta in row['edges']:
                u=np.maximum(t-when,0);analytic+=delta*(1-(1+u/tau)*np.exp(-u/tau))
                true+=delta*(t>=when-1e-16)
            for i in range(len(t)):
                close(y[i],analytic[i],'analytic cascade point',atol=3e-15)
                close(src[i],true[i],'source edge point',atol=1e-15)
            st=data[key+'_sample_time_s'];codes=data[key+'_code'];est=data[key+'_estimated_A']
            sy=np.zeros_like(st)
            for when,delta in row['edges']:
                u=np.maximum(st-when,0);sy+=delta*(1-(1+u/tau)*np.exp(-u/tau))
            gain=1e6/(1e6+110)
            expected=np.clip(np.rint((2.5+(2.048+40*sy-2.5)*gain)/5.12*65536),0,65535).astype(np.uint16)
            check(np.array_equal(expected,codes),'independent quantization')
            for i in range(len(st)):
                close(est[i],((codes[i]*5.12/65536-2.5)/gain+2.5-2.048)/40,'decode')
            for stop,name in [(250e-6,'phase_window_charge_C'),(400e-6,'extended_tail_charge_C')]:
                # Independent intersected sample-hold intervals.
                charge=sum(float(est[i])*max(0,min(float(st[i+1]),stop)-max(float(st[i]),50e-6)) for i in range(len(st)-1))
                close(charge,row[name],'sample hold integral',atol=1e-18)
            check(not row['phase_charge_precision_certified'],'unearned precision retained')
            if key.endswith('spike'):check(row['observed_peak_A']<row['source_peak_A']/2,'narrow peak lost witness')
    p=d['power_overlay']
    old=json.loads((ROOT/'electronics/stage4/power-study/budget-results.json').read_text())
    base=next(x for x in old['operating_cases'] if x['mode']=='restricted-active')
    close(p['baseline_active_W'],base['battery_nominal_W'],'frozen baseline')
    close(p['added_bus_W'],(.010*3.3+.020*5)/.8+6.9**2/7480,'bus increment')
    close(p['added_battery_W'],p['added_bus_W']*7.4/6.9,'diode loss increment')
    close(p['active_W'],p['baseline_active_W']+p['added_battery_W'],'active sum')
    close(p['runtime_h'],15.392/p['active_W'],'runtime')
    check(p['HOST_3V3_new_parts_A']<=.010 and p['HOST_5_new_parts_A']<=.020,'new caps cover parts')
    close(p['HOST_3V3_new_parts_A'],.001+.0035+.00033+.000033+.000066+.0002,'host digital loads')
    close(p['HOST_5_new_parts_A'],.016+5/4400,'host analog loads')
    check(p['RAM_total_bytes']==404992 and p['monitor_used_bytes']<=p['monitor_cap_bytes']==8192,'RAM allocation retained')
    actual_caps={x['ref']:x for x in native['parts'] if x['ref'].startswith('C')}
    check(set(actual_caps)=={c['reference'] for c in p['capacitors']},'every new capacitor counted')
    for c in p['capacitors']:
        check(c['value']==actual_caps[c['reference']]['value'],'capacitor binding')
        close(c['energy_J'],.5*c['capacitance_F']*c['voltage_allocation_V']**2,'capacitor energy')
    close(p['host_added_capacitor_energy_J'],sum(c['energy_J'] for c in p['capacitors'] if not c['external_peer']),'host capacitor sum')
    close(p['host_added_capacitor_energy_plus20percent_J'],1.2*p['host_added_capacitor_energy_J'],'energy margin')
    check(not p['compact_thermal_2K_earned'],'thermal failure retained')
    return dict(schema='scci_rh.stage4.transport-input-verification.v1',passed=True,checks=checks,
                results_sha256_lf=sha(HERE/'input-results.json'),traces_sha256=hashlib.sha256((HERE/'input-traces.npz').read_bytes()).hexdigest(),
                verifier_sha256_lf=sha(Path(__file__)),scope='independent analytic/KCL/arithmetic finite audit, not physical qualification')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-report',action='store_true');args=parser.parse_args()
    report=verify()
    if args.write_report:(HERE/'input-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f"Independent transport input audit: {report['checks']} assertions passed")
