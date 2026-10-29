"""Audit saved inter-package wiring and analog/native identities; read-only default.

This checks an explicit wiring plan against separate native packages. It does
not pretend that the later consolidated PCB/hierarchy already exists.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
S4=HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def number(value):
    m=re.match(r'([\d.]+)([MknuRp]?)',value)
    assert m,value
    return float(m[1])*{'M':1e6,'k':1e3,'n':1e-9,'u':1e-6,'p':1e-12,'R':1.,'':1.}[m[2]]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-receipt',action='store_true');args=ap.parse_args()
    packages=['supervision','current-driver','monitoring-cell','contact-router','recording-front-end']
    manifests={};parts={};xml={};hashes={};checks=0
    for package in packages:
        path=S4/package/'connectivity.json'
        manifests[package]=json.loads(path.read_text(encoding='utf-8-sig'))
        parts[package]={p['ref']:p for p in manifests[package]['parts']}
        netfile=next((S4/package).glob('*.xml'))
        tree=ET.parse(netfile);xml[package]={}
        for net in tree.findall('.//nets/net'):
            for node in net.findall('node'):xml[package][node.attrib['ref'],node.attrib['pin']]=net.attrib['name'].lstrip('/')
        for f in (path,netfile):hashes[f.relative_to(ROOT).as_posix()]=sha(f)
    path=ROOT/'docs/stage4/supervision-wiring.csv'
    rows=list(csv.DictReader(path.open(encoding='utf-8')));assert len(rows)==102
    hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    parents={}
    def find(key):
        if key not in parents:parents[key]=key
        if parents[key]!=key:parents[key]=find(parents[key])
        return parents[key]
    def join(a,b):parents[find(a)]=find(b)
    def identity(package,ref,pin):return package,parts[package][ref]['nets'][str(pin)]
    seen=set()
    for row in rows:
        ends=[]
        for side in ('from','to'):
            pkg,ref,pin,net=[row[side+'_'+key] for key in ('package','ref','pin','net')]
            assert parts[pkg][ref]['nets'][pin]==net,(pkg,ref,pin,net)
            assert xml[pkg][ref,pin]==net,(pkg,ref,pin,xml[pkg].get((ref,pin)),net)
            ends.append((pkg,net));checks+=2
        assert tuple(ends) not in seen;seen.add(tuple(ends));join(*ends)
    for pin in range(1,19):
        assert find(identity('contact-router','J7',pin))==find(identity('supervision','J100',pin));checks+=1
    rhd=[9,7,5,3,1,55,53,51,49,47,45,43,41,39,37,35,2]
    for ch,pin in enumerate(rhd):
        assert find(identity('recording-front-end','U10',pin))==find(identity('supervision','J'+str(600+ch),1));checks+=1
    assert find(('supervision','AFEAGND'))!=find(('supervision','GND'))
    for ch in range(2):
        assert find(identity('monitoring-cell','J3',1+ch))==find(identity('supervision','J4',7+ch))
        assert find(identity('current-driver','J4',4+4*ch))==find(identity('supervision','J5',7+ch))
        assert find(identity('monitoring-cell','J3',1+ch))!=find(identity('current-driver','J4',4+4*ch))
        checks+=3
    # Independent manufacturer-derived guard S/D/SEL pin roles, not drawing order.
    roles=[(1,16,15),(12,13,14),(9,8,7),(4,5,6)]
    guards=sorted([p for p in parts['supervision'].values() if p['value']=='TMUX7412FRRPR'],key=lambda p:int(p['ref'][1:]))
    assert len(guards)==5
    for index in range(20):
        p=guards[index//4];s,d,sel=map(str,roles[index%4]);nets=p['nets']
        if index<18:
            pin=str(index+1)
            assert nets[s]==parts['supervision']['J101']['nets'][pin]
            assert nets[d]==parts['supervision']['J100']['nets'][pin]
            assert nets[sel]=='GLOBAL_GUARD_EN'
        else:assert nets[s]==nets[d]==nets[sel]=='GND'
        checks+=3
    native=parts['supervision'];data=json.loads((HERE/'analog-results.json').read_text(encoding='utf-8'))
    def value(ref,expected):
        nonlocal checks
        assert math.isclose(number(native[ref]['value']),expected,rel_tol=1e-12),(ref,expected,native[ref]['value']);checks+=1
    for ref,v in {'R400':203800,'R401':2000,'R402':203800,'R500':232000,'R501':536000,'R502':232000,
                  'R510':1e6,'R511':49900,'R512':1e6,'R513':49900,'R520':1e6,'R521':49900,'R522':1e6,'R523':49900,
                  'R8000':195400,'R8010':195400,'R2200':100000,'R2201':10000,
                  'R250':100000,'C250':47e-9,'R260':100000,'C260':47e-9,
                  'R410':3300,'C420':10e-9,'R411':3300,'C421':10e-9}.items():value(ref,v)
    # Actual rail divider identities and model thresholds, including negative scaling.
    analog={r['rail']:r for r in data['rail_windows']}
    aliases=['SUP_3V3','SUP_5','HOST_3V3','HOST_5','HOST_15','HOST_24','AFE_3V3','AFE_P5','AFE_N5_MAG']
    for i,(spec,name) in enumerate(zip(manifests['supervision']['rail_specs'],aliases)):
        row=analog[name];gain=row['declared_scaling_gain']
        assert math.isclose(spec['low_V'],row['nominal_UV_rising_V']*gain)
        assert math.isclose(spec['high_V'],row['nominal_OV_rising_V']*gain)
        for offset,side in ((0,'UV'),(2,'OV')):
            value('R'+str(2000+i*10+offset),row['dividers'][side]['top_R_ohm'])
            value('R'+str(2001+i*10+offset),10000)
    for ref in ('U700','U701'):
        assert native[ref]['nets']['5']=='AFE_P5';checks+=1
    for f in (HERE/'analog-results.json',Path(__file__)):
        hashes[f.relative_to(ROOT).as_posix()]=sha(f)
    receipt={'schema':'scci_rh.stage4.supervision-integration.v1','date':'2026-10-14',
             'wires_checked':len(rows),'pin_net_value_checks':checks,'guarded_body_terminals':18,'RHD_pin_taps':17,
             'monitor_and_driver_supervision_aliases_distinct':True,'host_to_AFE_passive_ground_bridge':False,
             'consolidated_hierarchy_or_PCB_implemented':False,'normalized_lf_sha256':hashes}
    target=HERE/'integration-verification.json'
    if args.write_receipt:target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    else:assert json.loads(target.read_text(encoding='utf-8'))==receipt
    print(f'Integrated wiring plan: {len(rows)} wires, {checks} pin/net/value checks;18 guarded ports,17 actual RHD taps')


if __name__=='__main__':main()
