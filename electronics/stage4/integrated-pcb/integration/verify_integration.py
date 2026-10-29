"""Independent source-net equivalence audit of the actual exported master.

The audit reconstructs source pin groups and the explicit harness joins from XML
and CSV. It does not accept the producer's DSU or named-net list as evidence of
electrical equivalence. All checks are read-only; --write saves the receipt.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from build_integration import HERE,ROOT,PACKAGES,MAINS,refmap

def sha(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def xml_netlist(path):
    x=ET.parse(path).getroot()
    components={c.get('ref'):c for c in x.findall('components/comp')}
    groups=[];lookup={}
    for n in x.findall('nets/net'):
        group=frozenset((p.get('ref'),p.get('pin')) for p in n.findall('node') if p.get('ref') in components)
        if not group:continue
        groups.append(group)
        for key in group:lookup[key]=n.get('name')
    return x,components,groups,lookup
def main(write=False):
    s=json.loads((HERE/'system.json').read_text(encoding='utf-8'))
    checks=0
    def check(condition,label):
        nonlocal checks
        if not condition:raise AssertionError(label)
        checks+=1
    parent={}
    def root(k):
        parent.setdefault(k,k)
        while parent[k]!=k:
            parent[k]=parent[parent[k]];k=parent[k]
        return k
    def join(a,b):
        a,b=root(a),root(b)
        if a!=b:parent[b]=a
    source_lookup={};source_net_members={};source_pins={};expected_parts={};source_hashes={}
    for pkg,info in s['sources'].items():
        path=ROOT/info['xml'];check(sha(path)==info['sha256_lf'],'source XML binding '+pkg)
        source_hashes[pkg]=sha(path)
        x,parts,groups,lookup=xml_netlist(path)
        for ref,c in parts.items():
            new=refmap(ref,info['offset']);expected_parts[new]=c
        for group in groups:
            members=[(refmap(ref,info['offset']),pin) for ref,pin in group]
            for item in members:join(members[0],item)
        for (ref,pin),net in lookup.items():
            source_lookup[pkg,ref,pin]=net
            source_pins[pkg,ref,pin]=(refmap(ref,info['offset']),pin)
            source_net_members.setdefault((pkg,net),[]).append((refmap(ref,info['offset']),pin))
    old_rows=[]
    for file in ['supervision-wiring.csv','power-wiring.csv','monitoring-transport-wiring.csv']:
        old_rows+=list(csv.DictReader((ROOT/'docs/stage4'/file).open(encoding='utf-8-sig',newline='')))
    check(len(old_rows)==168,'168 original integration rows')
    excluded=s['excluded_legacy_wires']
    expected_excluded={('current-driver','J3','4','supervision','J3','10'),('current-driver','J3','8','supervision','J3','11')}
    signature=lambda w:tuple(w[k] for k in ['from_package','from_ref','from_pin','to_package','to_ref','to_pin'])
    check({signature(w) for w in excluded}==expected_excluded,'exact two corrected rearm aliases')
    legacy=[r for r in old_rows if signature(r) not in expected_excluded]
    carrier=list(csv.DictReader((ROOT/'docs/stage4/integrated-pcb-controller-wiring.csv').open(encoding='utf-8-sig',newline='')))
    wires=list(csv.DictReader((ROOT/'docs/stage4/integrated-pcb-wiring.csv').open(encoding='utf-8-sig',newline='')))
    check(len(legacy)==166 and len(carrier)==92 and len(wires)==258,'166 legacy + 92 carrier harness rows')
    check([signature(w) for w in wires]==[signature(w) for w in legacy+carrier],'final table exact source wire union')
    for w in wires:
        endpoints=[]
        for side in ['from','to']:
            identity=(w[side+'_package'],w[side+'_ref'],w[side+'_pin'])
            check(source_lookup[identity]==w[side+'_net'],'wire source pin identity '+str(identity))
            endpoints.append(source_pins[identity])
        join(*endpoints)
    # Added headers expose every former bare-component tap, with a physical
    # domain return. Their actual XML pins must share the original source nets.
    for adapter in s['added_tap_headers']:
        check(adapter['domain'] in ['HOST','AFE'],'header explicit electrical domain')
        check(adapter['footprint'].startswith('Connector_PinHeader_2.54mm:'),'native physical tap header footprint')
        for p in adapter['pins']:
            original=source_net_members[adapter['board'],p['source_net']][0]
            join((adapter['reference'],p['number']),original)
    expected_groups=defaultdict(set)
    for p in parent:expected_groups[root(p)].add(p)
    expected=set(map(frozenset,expected_groups.values()))
    master=HERE/'master/SCCI_RH_integrated.xml'
    x,actual_parts,groups,actual_lookup=xml_netlist(master)
    check(len(actual_parts)==1298,'actual master 1298 component positions')
    dnp_refs={ref for ref,c in actual_parts.items() if any(p.get('name')=='dnp' for p in c.findall('property'))}
    check(dnp_refs=={'C20100','C20200'},'two original driver DNP positions retained')
    check(set(actual_parts)==set(expected_parts)|{a['reference'] for a in s['added_tap_headers']},'actual master reference coverage')
    check(set(groups)==expected,'actual master exhaustive pin-group equivalence to source circuits and harness')
    for ref,source in expected_parts.items():
        actual=actual_parts[ref]
        check(actual.findtext('value')==source.findtext('value'),'source value preserved '+ref)
        check(actual.findtext('footprint')==source.findtext('footprint'),'source footprint preserved '+ref)
    for w in wires:
        for side in ['from','to']:
            physical=(w[side+'_harness_ref'],w[side+'_harness_pin'])
            original=(w[side+'_integrated_ref'],w[side+'_pin'])
            check(physical[0].startswith('J'),'physical connector endpoint '+str(physical))
            check(actual_lookup[physical]==actual_lookup[original],'physical harness reaches original net '+str(original))
            check(actual_lookup[physical]==w['integrated_net'],'harness CSV actual exported net identity')
    # Exhaustive board subsets must agree with the actual master, rather than
    # trusting the intermediate generator's component list.
    board_results={}
    for pkg,out in s['native_outputs'].items():
        path=(ROOT/out['board_root']).with_suffix('.xml')
        _,parts,bgroups,blookup=xml_netlist(path)
        refs=set(s['boards'][pkg]['references'])
        check(set(parts)==refs,'board XML exact component coverage '+pkg)
        for pin,net in blookup.items():
            check(actual_lookup[pin]==net or net.startswith('unconnected-'),'board/master net-name parity '+pkg+str(pin))
        mgroups={frozenset(pin for pin in g if pin[0] in refs) for g in groups}
        mgroups.discard(frozenset())
        check(set(bgroups)==mgroups,'board/master exhaustive electrical parity '+pkg)
        erc=json.loads((path.parent/'erc.json').read_text(encoding='utf-8'))
        violations=[v for sheet in erc['sheets'] for v in sheet.get('violations',[])]
        check(not violations,'board all-severity ERC '+pkg)
        board_results[pkg]={'components':len(parts),'pins':len(blookup),'xml_sha256_lf':sha(path),'erc_violations':len(violations)}
    erc=json.loads((master.parent/'erc.json').read_text(encoding='utf-8'))
    violations=[v for sheet in erc['sheets'] for v in sheet.get('violations',[])]
    check(not violations,'master all-severity ERC')
    check(not erc.get('ignored'), 'master ERC no ignored violations')
    # Exact physical processor module pads must connect to all 50 firmware
    # endpoint entries. The two internal serial sideband GPIOs stay on carrier.
    manifest=json.loads((ROOT/'electronics/stage4/controller-carrier/connectivity.json').read_text(encoding='utf-8'))
    check(len(manifest['gpio_bindings'])==46,'46 actual processor GPIO bindings')
    gpio_endpoints=0
    for binding in manifest['gpio_bindings']:
        source=('U80001',str(binding['physical_pad']))
        for entry in binding['connection'].split(';'):
            m=re.fullmatch(r'([^:]+):(J[0-9]+)\.([0-9]+)',entry)
            if not m:continue
            pkg,ref,pin=m.groups();target=(refmap(ref,s['sources'][pkg]['offset']),pin)
            check(actual_lookup[source]==actual_lookup[target],'physical processor pad to firmware endpoint '+entry)
            gpio_endpoints+=1
    check(gpio_endpoints==50,'50 actual GPIO endpoint connections')
    # Derive driver rearm physical pad from binding instead of assuming a module
    # drawing pin for it (the two Z pads are manufacturer-defined P1.10/11).
    drv=next(b for b in manifest['gpio_bindings'] if b['signal']=='BOTH_DRV_REARM')['physical_pad']
    check(len({actual_lookup['U80001',str(drv)],actual_lookup['U80001','Z1'],actual_lookup['U80001','Z2']})==3,'three rearm outputs remain electrically distinct')
    ground_nodes=[source_pins['power','J3','7'],source_pins['power','J4','4'],source_pins['monitoring-transport','J8','4']]
    check(len({actual_lookup[n] for n in ground_nodes})==3,'HOST, AFE and companion returns are distinct')
    check(actual_lookup['J80016','9']==actual_lookup['J40002','7'],'router loom return uses actual GND pin 7')
    check(actual_lookup['J40002','6']!=actual_lookup['J40002','7'],'candidate shift tail is not grounded')
    check(len(x.findall('design/sheet'))==80,'80 actual native master sheets')
    result={'schema':'scci_rh.integrated-native-verification.v1','passed':True,'assertions':checks,'components':len(actual_parts),'fitted_components':len(actual_parts)-len(dnp_refs),'DNP_references':sorted(dnp_refs),'connected_and_NC_pins':len(actual_lookup),'sheets':len(x.findall('design/sheet')),'harness_rows':len(wires),'legacy_retained':166,'legacy_corrected':2,'carrier_wires':92,'firmware_GPIO':46,'firmware_endpoint_connections':gpio_endpoints,'added_physical_tap_headers':4,'master_erc_violations':0,'source_xml_sha256_lf':source_hashes,'master_xml_sha256_lf':sha(master),'boards':board_results,'limits':['Saved native electrical design and pin-group parity; no physical board measurements','Pin-header/loom fanouts require a fabricated harness and continuity testing','ERC does not establish analog accuracy, medical isolation, radio approval or stimulation efficacy']}
    if write:(HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');main(p.parse_args().write)
