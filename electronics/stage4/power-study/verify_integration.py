"""Read-only inter-package power/ground/open-drain wiring audit."""
from pathlib import Path
import argparse,csv,hashlib,json
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
S4=HERE.parent


def sha(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-receipt',action='store_true');args=ap.parse_args()
    parts={};xml={};hashes={};checks=0
    for pkg in ['power','supervision','monitoring-cell','current-driver','contact-router','recording-front-end']:
        path=S4/pkg/'connectivity.json';parts[pkg]={p['ref']:p for p in json.loads(path.read_text(encoding='utf-8'))['parts']}
        export=next((S4/pkg).glob('*.xml'));xml[pkg]={}
        for net in ET.parse(export).findall('.//nets/net'):
            for node in net.findall('node'):xml[pkg][node.attrib['ref'],node.attrib['pin']]=net.attrib['name'].lstrip('/')
        for p in (path,export):hashes[p.relative_to(ROOT).as_posix()]=sha(p)
    parents={}
    def find(key):
        if key not in parents:parents[key]=key
        if parents[key]!=key:parents[key]=find(parents[key])
        return parents[key]
    def join(a,b):parents[find(a)]=find(b)
    count=0
    for name in ['power-wiring.csv','supervision-wiring.csv']:
        path=ROOT/'docs/stage4'/name;rows=list(csv.DictReader(path.open(encoding='utf-8')))
        assert len(rows)==(32 if name=='power-wiring.csv' else 102),(name,len(rows))
        for row in rows:
            ends=[]
            for side in ('from','to'):
                pkg,ref,pin,net=[row[side+'_'+key] for key in ('package','ref','pin','net')]
                assert parts[pkg][ref]['nets'][pin]==xml[pkg][ref,pin]==net,(pkg,ref,pin,net)
                ends.append((pkg,net));checks+=2
            join(*ends)
        hashes[path.relative_to(ROOT).as_posix()]=sha(path);count+=len(rows)
    for pkg in parts:
        for net in set(n for p in parts[pkg].values() for n in p['nets'].values() if n is not None):
            assert not (net=='AFEAGND' and find((pkg,net))==find(('power','GND')))
    assert find(('power','PWR_FAULT_N'))==find(('supervision','GUARD_FAULT_N'))
    p=parts['power']['U235'];assert p['value']=='SN74LVC1G07DBVR'
    assert p['nets']['4']=='PWR_FAULT_N' and p['nets']['2']=='POWER_RUN_OK'
    assert any(str(pin[0])=='4' and pin[2]=='open_collector' for pin in p['pins'])
    for net in ('MON_VREF','MON_VMID'):
        assert find(('power',net))==find(('supervision',net))
    expected={'SUP_3V3','SUP_5','HOST_3V3','HOST_5','HOST_15','VH_24','AFE_3V3','AFE_P5','AFE_N5'}
    assert expected.issubset(set(parts['power']['J3']['nets'].values())|set(parts['power']['J4']['nets'].values()))
    assert find(('supervision','CH0_MON_SUP_OK'))!=find(('supervision','CH0_EXT_SUP_OK'))
    hashes[Path(__file__).relative_to(ROOT).as_posix()]=sha(Path(__file__))
    receipt={'schema':'scci_rh.stage4.power-integration.v1','date':'2026-10-14','new_power_wires':32,
             'combined_wire_plan_connections':count,'endpoint_manifest_XML_comparisons':checks,
             'generated_rails':9,'floating_ground_preserved':True,'fault_output_is_open_drain':True,
             'consolidated_native_hierarchy_or_PCB_created':False,'sha256_lf':hashes}
    path=HERE/'integration-verification.json'
    if args.write_receipt:path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    else:assert json.loads(path.read_text(encoding='utf-8'))==receipt
    print(f'Power integration:32 new wires; {count} combined wires; {checks} endpoint checks; nine rails and open-drain fault linked')


if __name__=='__main__':main()
