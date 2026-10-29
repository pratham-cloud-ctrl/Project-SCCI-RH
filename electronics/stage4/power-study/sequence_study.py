"""Finite valid-supply power sequencing and native gate audit; read-only default."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parent/'power'


def sha(path):return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def audit_native():
    tree=ET.parse(NATIVE/'power.xml');nets={}
    for net in tree.findall('.//nets/net'):
        for node in net.findall('node'):nets[node.attrib['ref'],node.attrib['pin']]=net.attrib['name'].lstrip('/')
    parts={p.attrib['ref']:p.findtext('value') for p in tree.findall('.//components/comp')}
    gates={}
    for ref,value in parts.items():
        if value.startswith('SN74LVC1G08'):pins=('1','2')
        elif value.startswith('SN74LVC1G11'):pins=('1','3','6')
        else:continue
        gates[nets[ref,'4']]=(ref,tuple(nets[ref,p] for p in pins))
    def evaluate(net,values):
        if net in values:return values[net]
        return all(evaluate(n,values) for n in gates[net][1])
    inputs=('PWR_REQUEST','BATT_WINDOW_OK','S3_WINDOW_OK','S5_WINDOW_OK','PWR_START_OK','HOST_5_PG','MREF_WINDOW_OK','MID_WINDOW_OK')
    rows=[]
    for bits in itertools.product((False,True),repeat=8):
        v=dict(zip(inputs,bits));request,batt,s3,s5,start,pg,ref,mid=bits
        host=request and batt and s3 and s5 and start
        expected={'SUP_READY':s3 and s5 and start,'BATT_OK':batt and start,
                  'HOST_ENABLE':host,'BOOST_ENABLE':host and pg,'REF_OK':ref and mid,
                  'POWER_RUN_OK':host and pg and ref and mid}
        actual={name:evaluate(name,v) for name in expected}
        assert actual==expected,(v,actual,expected)
        rows.append([*map(int,bits),*map(int,actual.values())])
    assert nets['U235','2']=='POWER_RUN_OK' and nets['U235','4']=='PWR_FAULT_N'
    assert nets['U235','5']=='SUP_3V3' and nets['U235','3']=='GND'
    assert parts['U235']=='SN74LVC1G07DBVR'
    # Device enables use actual circuit status, not human-readable descriptions.
    for ref,pin in [('U102','3'),('U110','13')]:assert nets[ref,pin]=='HOST_ENABLE'
    for ref in ('U300','U301'):assert nets[ref,'4']=='BOOST_ENABLE'
    return {'native_XML_sha256_lf':sha(NATIVE/'power.xml'),
            'native_manifest_sha256_lf':sha(NATIVE/'connectivity.json'),
            'Boolean_input_rows':len(rows),'gate_output_comparisons':len(rows)*6,
            'gate_truth_sha256':hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest(),
            'open_drain_and_four_enable_pin_bindings':8,
            'physical_propagation_supply_ramp_or_converter_loop_verified':False}


def histories():
    records=[]
    def run(name,events):
        state={n:False for n in ('power_request','battery','supplies','startup','host_pg','reference','midpoint','other_rails','other_health','phase')}
        arm=False;previous_rearm=False;history=[]
        for event in events:
            rearm=event.get('rearm',False);state.update({k:v for k,v in event.items() if k in state})
            host=state['power_request'] and state['battery'] and state['supplies'] and state['startup']
            boost=host and state['host_pg']
            power_good=boost and state['reference'] and state['midpoint']
            raw_health=power_good and state['other_rails'] and state['other_health']
            if not raw_health:arm=False
            if rearm and not previous_rearm and raw_health and not state['phase']:arm=True
            guard=arm and raw_health and state['phase']
            actual={'host_enable':host,'boost_enable':boost,'PWR_FAULT_N_released':power_good,
                    'arm':arm,'guard_command':guard,'rails_may_retain_energy_when_guard_off':True}
            for key,value in event.get('expect',{}).items():assert actual[key]==value,(name,event,key,actual)
            history.append({'event':event['label'],'inputs':dict(state),'explicit_rearm':rearm,'outputs':actual})
            previous_rearm=rearm
        records.append({'case':name,'history':history,
                        'assertions':sum(len(e.get('expect',{})) for e in events)})
    cold=[{'label':'cold request high','power_request':True,'expect':{'host_enable':False,'guard_command':False}},
          {'label':'battery and SUP windows valid before hold','battery':True,'supplies':True,'expect':{'host_enable':False}},
          {'label':'startup hold releases','startup':True,'expect':{'host_enable':True,'boost_enable':False}},
          {'label':'host5 PG valid; reference absent','host_pg':True,'expect':{'boost_enable':True,'PWR_FAULT_N_released':False}},
          {'label':'reference valid; midpoint absent','reference':True,'expect':{'PWR_FAULT_N_released':False}},
          {'label':'midpoint and actual remaining rails valid','midpoint':True,'other_rails':True,'other_health':True,'expect':{'PWR_FAULT_N_released':True,'arm':False}},
          {'label':'deliberate idle rearm','rearm':True,'expect':{'arm':True}},
          {'label':'fresh admitted phase','phase':True,'expect':{'guard_command':True}}]
    run('ordered_cold_start',cold)
    for signal in ('power_request','battery','supplies','host_pg','reference','midpoint','other_rails','other_health'):
        fault={'label':signal+' falls while reservoirs remain charged',signal:False,'expect':{'guard_command':False,'arm':False}}
        restore={'label':signal+' restores; phase still requested',signal:True,'expect':{'guard_command':False,'arm':False}}
        idle={'label':'phase ends; elapsed wait alone cannot arm','phase':False,'expect':{'arm':False}}
        explicit={'label':'new deliberate idle rearm','rearm':True,'expect':{'arm':True}}
        run(signal+'_loss_and_restore',cold+[fault,restore,idle,explicit])
    run('stale_PG_when_disabled',[{'label':'PG high but request low','host_pg':True,'battery':True,'supplies':True,'startup':True,
                                 'reference':True,'midpoint':True,'other_rails':True,'other_health':True,'phase':True,
                                 'expect':{'host_enable':False,'boost_enable':False,'PWR_FAULT_N_released':False,'guard_command':False}}])
    run('untrimmed_AFE_never_qualifies',[*cold[:5],{'label':'reference valid but actual AFE rail outside window','midpoint':True,
        'other_health':True,'other_rails':False,'rearm':True,'phase':False,'expect':{'arm':False,'guard_command':False}}])
    run('request_high_is_not_rearm',[*cold[:6],{'label':'phase request without supervisory rearm','phase':True,
                                           'expect':{'arm':False,'guard_command':False}}])
    return records


def window_corners():
    m=json.loads((NATIVE/'connectivity.json').read_text(encoding='utf-8'))
    parts={p['ref']:p for p in m['parts']};rows=[];checks=0
    def ohms(ref):
        value=parts[ref]['value'];match=re.match(r'([\d.]+)([kMR]?)',value)
        assert '0.1%' in value
        return float(match[1])*{'k':1000,'M':1e6,'R':1.,'':1.}[match[2]]
    for i,spec in enumerate(m['rail_specs']):
        limits={}
        for offset,side,bias in ((0,'UV',25e-9),(2,'OV',15e-9)):
            rt=ohms('R'+str(2000+10*i+offset));rb=ohms('R'+str(2001+10*i+offset))
            for edge,thresholds in [('rising',(.396,.404)),('falling',(.387,.400))]:
                values=[]
                for top,bottom,vt,ib in itertools.product((rt*.999,rt*1.001),(rb*.999,rb*1.001),thresholds,(-bias,bias)):
                    vin=vt+top*(vt/bottom+ib)
                    # Independently substitute into divider KCL at the threshold.
                    assert math.isclose((vin-vt)/top-vt/bottom,ib,abs_tol=1e-18)
                    values.append(vin);checks+=1
                limits[side+'_'+edge+'_V']=[min(values),max(values)]
        nominal={'BATT':7.4,'S3':3.3,'S5':5.,'MREF':4.096,'MID':2.048}[spec['name']]
        rows.append({'name':spec['name'],'actual_node':spec['node'],'bounds':limits,
                     'nominal_V':nominal,'nominal_inside_all_cold_start_windows':
                     limits['UV_rising_V'][1]<nominal<limits['OV_rising_V'][0]})
    batt=rows[0]
    assert 6.4<batt['bounds']['UV_rising_V'][0]
    assert all(r['nominal_inside_all_cold_start_windows'] for r in rows)
    return {'rows':rows,'threshold_KCL_corner_checks':checks,'pack6p4V_cold_start_admitted':False,
            'reference_gross_window_is_precision_calibration':False,
            'input_bias_threshold_and_resistor_limits':'TPS3700 primary tables and native0.1percent dividers',
            'supply_UVLO_ramp_and_physical_latency_qualified':False}


def generate():
    hs=histories()
    return {'schema':'scci_rh.stage4.power-sequence.v1','date':'2026-10-14','source_sha256_lf':sha(Path(__file__)),
            'scope':'Actual native gate/enable pin audit and finite valid-supply ideal event adapter to prior sticky supervision',
            'native_audit':audit_native(),'qualification_windows':window_corners(),'histories':hs,'scenario_groups':len(hs),
            'assertions_passed':sum(h['assertions'] for h in hs),'snapshots':sum(len(h['history']) for h in hs),
            'limits':{'converter_enable_is_output_disconnect':False,'switch_weld_or_invalid_logic_supply_covered':False,
                      'reference_window_earns_precision_calibration':False,'physical_fault_to_guard_delay_earned':False,
                      'automatic_rail_restart_can_rearm_stimulation':False,
                      'AFE_ground_passively_joined_to_host':False}}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-results',action='store_true');ap.add_argument('--check',action='store_true');args=ap.parse_args()
    data=generate();path=HERE/'sequence-results.json'
    if args.write_results:path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    else:assert json.loads(path.read_text(encoding='utf-8'))==data
    print(json.dumps({k:data[k] for k in ('scenario_groups','assertions_passed','snapshots','native_audit')}))


if __name__=='__main__':main()
