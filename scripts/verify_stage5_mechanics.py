"""Portable independent audit of Stage 5 mechanical evidence.

This does not emulate FreeCAD or infer shape validity from a producer's JSON.
It binds independently reopened BRep receipts to the exact current native and
exchange files, and checks electronic source/port/harness identity itself.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from project_branding import assert_baseline_equivalence
BASELINE = '7a4371b7ff891248a5ab4f12e3149268485d828f'
STAGE5 = ROOT / 'cad/stage5'
REPORT = ROOT / 'provenance/stage5-mechanical-verification.json'
sys.path.insert(0, str(ROOT / 'electronics/stage4/integrated-pcb/integration'))
from sexp import loads, sub, subs


def sha(path, text=False):
    data = Path(path).read_bytes()
    if text:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def canonical(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def artifact_path(package_path,value):
    path=Path(value)
    return package_path.parent/path if path.parent==Path('.') else ROOT/path


def actual_inspector_source(receipt):
    expected=receipt['inspector_sha256_lf']
    current=ROOT/receipt.get('inspector','scripts/inspect_stage5_native.py')
    if sha(current,True)==expected:
        return current
    archived=ROOT/'provenance/stage5-inspector-sources'/(expected+'.py.txt')
    if archived.is_file() and sha(archived,True)==expected:
        return archived
    # Archive basenames retain immutable historical source identities. A
    # reviewed namespace migration can change source text without inventing a
    # newly executed historical inspection; locate the exact migrated content.
    matches=[path for path in (ROOT/'provenance/stage5-inspector-sources').glob('*.py.txt')
             if sha(path,True)==expected]
    assert len(matches)==1,'exact hash-bound independent inspector source must be present uniquely'
    return matches[0]


def audit_reused_reference_evidence(receipt, package_path, package, check):
    """Bind actual successful operations; never migrate their executed source."""
    reuse=receipt['evidence_reuse']
    geometry=receipt['packages']['reference']
    backend=reuse['backend']
    check(sha(ROOT/backend['path'],True)==backend['sha256_lf'],'current unchanged reference geometry backend')
    check(sha(ROOT/backend['archived_source'],True)==backend['sha256_lf'],'preserved actual completed-phase inspector')
    expected_inputs={package[k] for k in ('step','mechanical_step','exploded_step')}
    expected_inputs.update(b[k] for b in package['boards'] for k in ('source_step','source_pcb'))
    phases={}
    for row in reuse['completed_phases']:
        path=ROOT/row['receipt']
        check(sha(path)==row['sha256'],'exact actual completed phase bytes '+row['phase'])
        phase=json.loads(path.read_text(encoding='utf-8'))
        check(phase['completed'] is True,'actual machine operation completed '+row['phase'])
        bindings=phase['bindings']
        check(bindings['inspector_sha256_lf']==backend['sha256_lf'],'actual executed source retained '+row['phase'])
        check(bindings['FreeCAD_version']==receipt['FreeCAD_version'],'actual phase FreeCAD version '+row['phase'])
        check(bindings['contract_canonical_sha256']==canonical(package_path),'current phase contract '+row['phase'])
        check(bindings['native_sha256']==sha(ROOT/package['native']),'current phase native source '+row['phase'])
        check(set(bindings['files'])==expected_inputs,'all phase export and original board input bindings '+row['phase'])
        for source,digest in bindings['files'].items():
            check(sha(ROOT/source,Path(source).suffix.lower()=='.kicad_pcb')==digest,'current actual phase input '+source)
        phases[row['phase']]=phase['result']
    check(set(phases)=={'native-specific','nominal-step','mechanical-step','exploded-step'},'exact four actual successful independent phases')
    check(all(geometry[k]==value for k,value in phases['native-specific'].items()),'final receipt explicitly preserves actual native/source phase results')
    check(geometry['step_comparison']==phases['nominal-step'],'actual completed nominal neutral-export comparison retained')
    for name in ('mechanical','exploded'):
        check(all(geometry['extra_exports'][name+'_step'][k]==v for k,v in phases[name+'-step'].items()),'actual completed '+name+' neutral-export comparison retained')
    clearance=reuse['clearance']
    manifest_path=ROOT/clearance['manifest']
    check(sha(manifest_path)==clearance['manifest_sha256'],'exact completed-clearance evidence manifest')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    check(manifest['schema']=='scci_rh.stage5.actual-clearance-probe.v1','actual completed clearance schema')
    check(manifest['bindings']['native_sha256']==sha(ROOT/package['native']),'actual completed clearance native binding')
    check(manifest['bindings']['contract_canonical_sha256']==canonical(package_path),'actual completed clearance contract binding')
    for role,row in manifest['files'].items():
        path=ROOT/row['path']
        check(path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'unaltered completed clearance evidence '+role)
        if 'sha256_lf' in row:
            check(sha(path,True)==row['sha256_lf'],'exact actual executed clearance source '+role)
    result_path=ROOT/clearance['result_path']
    check(result_path==ROOT/manifest['files']['raw_results']['path'] and sha(result_path)==clearance['result_sha256'],'exact actual completed clearance results')
    results=json.loads(result_path.read_text(encoding='utf-8'))
    summary=json.loads((ROOT/manifest['files']['raw_summary']['path']).read_text(encoding='utf-8'))
    check(summary['probe_script_sha256']==manifest['files']['executed_source']['sha256'],'completed clearance summary binds actual executed source')
    check(results['all_passed'] and summary['all14_exact_gates_passed'],'all fourteen completed exact constituent-solid distance gates passed')
    check(results['native_sha256']==geometry['native_sha256'] and results['contract_canonical_sha256']==canonical(package_path),'raw clearance results bound to actual saved native/contract')
    check(len(results['rows'])==len(package['clearance_checks'])==len(geometry['clearances'])==14,'all fourteen declared reference clearances covered')
    topology=json.loads((ROOT/manifest['files']['raw_topology']['path']).read_text(encoding='utf-8'))
    check(sorted(topology,key=lambda r:r['label'])==sorted(geometry['fresh_solid_coverage'],key=lambda r:r['label']),'fresh native full-solid coverage matches completed inspection')
    check(all(r['native_solids']==r['covered_solids'] and not r['non_solid_leaves'] for r in topology),'no native non-solid topology omitted from clearance query')
    for row,expected,fresh in zip(results['rows'],package['clearance_checks'],geometry['clearances']):
        check(all(row[k]==expected[k]==fresh[k] for k in ('a','b','minimum_mm')),'exact actual declared clearance pair')
        check(row['passed'] and row['measured_mm']==fresh['measured_mm'] and abs(row['measured_mm']-fresh['freshly_measured_minimum_pair_mm'])<=2e-5,'fresh exact nearest-solid-pair witness of retained result')
        check(row['exact_BRep_queries']+row['AABB_pruned_pairs']==row['solid_pair_count'],'complete constituent-pair search accounting')
        check(row['measured_mm']>=row['minimum_mm']-2e-5,'unrelaxed exact clearance acceptance')
    check(sum(r['exact_BRep_queries'] for r in results['rows'])==summary['exact_queries']==1727,'actual exact constituent distance queries')
    check(sum(r['AABB_pruned_pairs'] for r in results['rows'])==summary['pruned_pairs']==1317,'actual remaining conservatively pruned constituent pairs')


def native_labels(path):
    """Portable structural check; actual validity comes from bound native audit."""
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, 'intact FreeCAD ZIP container'
        document = ET.fromstring(archive.read('Document.xml'))
    objects = {}
    for item in document.findall('./ObjectData/Object'):
        label = item.find('./Properties/Property[@name="Label"]/String')
        if label is not None:
            objects[item.get('name')] = label.get('value')
    return objects


def preserve_sources(check):
    """Retain original Git identities and explicitly compare renamed artifacts."""
    prefixes = ['cad/stage2', 'cad/exports', 'electronics', 'firmware',
                'docs/stage1', 'docs/stage2', 'docs/stage3', 'experiments','provenance']
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-z', BASELINE, '--', *prefixes], cwd=ROOT)
    expected = []
    for entry in tree.split(b'\0'):
        if not entry:
            continue
        header, path = entry.split(b'\t')
        mode, kind, blob = header.decode().split()
        relative=path.decode('utf-8')
        if relative.startswith('provenance/') and not Path(relative).name.startswith(('stage1-','stage2-','stage3-','stage4-')):
            continue
        check(kind == 'blob', 'source baseline contains ordinary file blobs')
        expected.append((relative, blob))
    check(len(expected) > 1500, 'substantial original Stage 1-4 source baseline')
    migration = assert_baseline_equivalence(ROOT, BASELINE, expected)
    check(migration['files_compared'] == len(expected), 'every original Stage 1-4 identity checked after branding migration')
    return dict(commit=BASELINE, historical_source_files=len(expected),
                path_blob_digest=hashlib.sha256(''.join(p+' '+b+'\n' for p, b in expected).encode()).hexdigest(),
                authorized_brand_migration=migration)


def pcb_geometry(path):
    board = loads(Path(path).read_text(encoding='utf-8'))
    connectors, mounts = {}, {}
    for footprint in subs(board, 'footprint'):
        props = {p[1]: p[2] for p in subs(footprint, 'property')}
        reference = props.get('Reference', '')
        at = sub(footprint, 'at')
        if reference.startswith('J'):
            angle=float(at[3]) if len(at)>3 else 0.0
            cosine,sine=math.cos(math.radians(angle)),math.sin(math.radians(angle))
            pads={}
            for pad in subs(footprint,'pad'):
                local=sub(pad,'at');x,y=float(local[1]),float(local[2])
                net=sub(pad,'net')
                pads[str(pad[1])]=dict(position_mm=[float(at[1])+cosine*x+sine*y,
                                                   float(at[2])-sine*x+cosine*y],
                                       net=str(net[-1]) if net else None)
            connectors[reference] = dict(position_mm=[float(at[1]), float(at[2])],
                                         rotation_deg=angle,pads=pads)
        if str(footprint[1]).startswith('MountingHole:'):
            pads = subs(footprint, 'pad')
            assert len(pads) == 1
            mounts[reference] = dict(position_mm=[float(at[1]), float(at[2])],
                                     diameter_mm=float(sub(pads[0], 'drill')[1]))
    return connectors, mounts


def audit_harness(root_contract, reference, original_ports, check):
    path=ROOT/root_contract['harness']['contract']
    harness=json.loads(path.read_text(encoding='utf-8'))
    electrical=json.loads((ROOT/'electronics/stage4/integrated-pcb/integration/harness.json').read_text(encoding='utf-8'))
    system=json.loads((ROOT/'electronics/stage4/integrated-pcb/integration/system.json').read_text(encoding='utf-8'))
    check(harness['baseline_commit']==BASELINE,'harness exact source revision')
    for source,digest in harness['sources'].items():
        check(sha(ROOT/source,True)==digest,'current harness planning source '+source)
    used={(row['board'],row['pcb_reference']) for row in electrical['connectors']}
    external={('recording-front-end','J30003'),('supervision','J50101'),('power','J60001'),
              ('monitoring-transport','J70008'),('controller-carrier','J80002')}
    mates={(row['board'],row['pcb_reference']):row for row in harness['mates']}
    check(len(used)==78 and len(mates)==83 and set(mates)==used|external,'exact78 internal and5 external connector mates')
    boards={b['board']:b for b in reference['boards']}
    native={name:pcb_geometry(ROOT/b['source_pcb'])[0] for name,b in boards.items()}
    parts={(c['board'],c['reference']):c for c in system['components']}
    endpoint_lookup={}
    for key,mate in mates.items():
        board=boards[key[0]]
        native_pads=native[key[0]][key[1]]['pads']
        original_pins={p['number']:p for p in parts[key]['pins']}
        check(len(mate['pins'])==mate['pin_count']==len(native_pads), 'actual native mating pin count '+str(key))
        check({p['pin'] for p in mate['pins']}==set(native_pads)==set(original_pins), 'all native mating pad identities '+str(key))
        for pin in mate['pins']:
            pad=native_pads[pin['pin']]
            x,y=pad['position_mm'];translation=board['translation_mm']
            expected=[translation[0]+x,translation[1]-y,translation[2]+4.2]
            check(max(abs(a-b) for a,b in zip(expected,pin['axis_mm']))<1e-5, 'mating axis from original native pad '+str(key)+':'+pin['pin'])
            check(pin['net']==pad['net']==original_pins[pin['pin']]['net'], 'actual native pad/electrical net '+str(key)+':'+pin['pin'])
            check(pin['source_net']==original_pins[pin['pin']]['source_net'],'original local pin role '+str(key)+':'+pin['pin'])
            check(abs(pin['wire_exit_mm'][2]-pin['axis_mm'][2]-14)<1e-7,'declared socket height to wire exit')
            endpoint_lookup[(key[0],key[1],pin['pin'])]=pin
        check(mate['housing_height_mm']==14 and mate['housing_width_mm']==2.5,'nominal selected housing envelope')
        check(abs(mate['housing_length_mm']-(2.54*(mate['pin_count']-1)+2.74))<1e-7,'nominal housing pitch/length allocation')
        check(mate['square_cavity_mm']==.95 and mate['nominal_pin_mm']==.64,'nominal socket radial allocation')
    terminal_routes=harness['terminal_routes']
    check(len(terminal_routes)==len(endpoint_lookup)==525,'one route fanout per actual socket terminal')
    terminal_ids={r['id'] for r in terminal_routes}
    check(len(terminal_ids)==len(terminal_routes),'unique terminal route identifiers')
    seen=set()
    for route in terminal_routes:
        endpoint=route['endpoint'];key=(endpoint['board'],endpoint['reference'],endpoint['pin'])
        check(key in endpoint_lookup and key not in seen,'one fanout per distinct terminal')
        seen.add(key)
        check(endpoint==endpoint_lookup[key],'route uses exact native connector endpoint')
        check(route['points_mm'][0]==endpoint['wire_exit_mm'],'fanout starts at socket exit')
        check(route['bend_radius_allocation_mm']==5,'stated unsmoothed future bend allocation')
    old={w['id']:w for w in electrical['wires']}
    proposed={w['id']:w for w in harness['wires']}
    check(len(old)==len(proposed)==258 and set(old)==set(proposed),'all258 frozen logical rows')
    for wire_id,wire in proposed.items():
        source=old[wire_id]
        check(wire['net']==source['net'],'unchanged logical net '+wire_id)
        ends=[{k:e[k] for k in ('board','reference','pin')} for e in wire['ends']]
        check(ends==source['ends'],'unchanged exact two logical endpoints '+wire_id)
        check(all(e['net']==wire['net'] for e in wire['ends']),'same net at both geometric wire endpoints '+wire_id)
        check(wire['points_mm'][0]==wire['ends'][0]['wire_exit_mm'] and wire['points_mm'][-1]==wire['ends'][-1]['wire_exit_mm'],'route endpoints at socket exits '+wire_id)
        check(set(wire['terminal_routes'])<=terminal_ids and len(wire['terminal_routes'])==2,'logical edge uses existing two terminal fanouts '+wire_id)
        length=sum(math.dist(a,b) for a,b in zip(wire['points_mm'],wire['points_mm'][1:]))
        check(abs(length-wire['nominal_centerline_length_mm'])<=.00051,'independent route length '+wire_id)
        planning=5*math.ceil((length*1.2+30)/5)
        check(wire['planning_length_with_slack_mm']==planning,'independent20percent slack and30mm termination allowance '+wire_id)
    check(harness['branch_nodes']==electrical['splices'] and len(harness['branch_nodes'])==47,'exact47 original electrical branch nodes')
    body=harness['body_ports']
    check({p['port_id']:p['logical_function'] for p in body}=={p['port_id']:p['logical_function'] for p in original_ports},'same36 future/reference logical functions')
    for i,row in enumerate(body):
        expected_board='recording-front-end' if i<18 else 'supervision'
        expected_reference='J30003' if i<18 else 'J50101'
        expected_pin=str(i+1 if i<18 else i-17)
        check((row['board'],row['pcb_reference'],row['pin'])==(expected_board,expected_reference,expected_pin),'body port uses protected or post-guard output '+row['port_id'])
        pin=endpoint_lookup[(expected_board,expected_reference,expected_pin)]
        check(row['source_net']==pin['source_net'] and row['integrated_net']==pin['net'],'body interface exact electrical net '+row['port_id'])
    bridge=list(csv.DictReader((path.parent/'body-port-bridge.csv').open(encoding='utf-8',newline='')))
    check(bridge==body,'delivered body-port CSV exactly matches protected logical map')
    lengths=list(csv.DictReader((path.parent/'wire-length-planning.csv').open(encoding='utf-8',newline='')))
    check(len(lengths)==258 and {r['wire_id'] for r in lengths}==set(proposed),'delivered route-length table has all258 logical rows')
    for row in lengths:
        wire=proposed[row['wire_id']]
        check(row['net']==wire['net'] and float(row['nominal_centerline_mm'])==wire['nominal_centerline_length_mm'], 'delivered planning table exact logical length '+row['wire_id'])
        check(float(row['planning_slack_mm'])==wire['planning_length_with_slack_mm'], 'delivered slack allocation '+row['wire_id'])
    receipt_path=ROOT/'provenance/stage5-native-harness.json'
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    inspector=actual_inspector_source(receipt)
    check(receipt['passed'] and sha(inspector,True)==receipt['inspector_sha256_lf'],'actual executed independent harness native inspector')
    geometry=receipt['packages']['harness']
    check(geometry['contract_canonical_sha256']==canonical(path),'current native harness contract')
    for field in ('native','step','routing_native'):
        check(geometry[field+'_sha256']==sha(ROOT/harness[field]),'current inspected harness '+field)
    check(geometry['reference_native_sha256']==sha(ROOT/reference['native']),'global mating interference uses current actual chassis')
    check(geometry['final_objects']==90 and len(geometry['sockets'])==83 and len(geometry['routes'])==258,'all physical sockets/rear parts and planning annotations independently inspected')
    check(geometry['interference']['unexplained_positive_volume_intersections']==0,'no global mating/chassis material interference')
    check(not geometry['physical_qualification'],'mating fit remains nominal digital geometry')
    return dict(contract_canonical_sha256=canonical(path),native_receipt_canonical_sha256=canonical(receipt_path),
                inspector_source=inspector.relative_to(ROOT).as_posix(),inspector_sha256_lf=receipt['inspector_sha256_lf'],
                sockets=83,internal_mates=78,external_mates=5,physical_rear_parts=7,
                terminal_fanouts=525,logical_rows=258,branch_nodes=47,body_ports=36,
                native_sha256=sha(ROOT/harness['native']),STEP_sha256=sha(ROOT/harness['step']),
                routing_native_sha256=sha(ROOT/harness['routing_native']),packed_loom_qualified=False)


def audit():
    checks = 0
    def check(value, reason):
        nonlocal checks
        checks += 1
        if not value:
            raise AssertionError(reason)
    contract_path = STAGE5/'assembly-contract.json'
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    check(contract['baseline_commit']==BASELINE,'root contract exact pre-mechanics source revision')
    reference_path = ROOT/contract['reference']['contract']
    future_path = ROOT/contract['future']['contract']
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    future = json.loads(future_path.read_text(encoding='utf-8'))
    preserved = preserve_sources(check)
    stage4_path = ROOT/'provenance/stage4-integrated-pcb-verification.json'
    stage4 = json.loads(stage4_path.read_text(encoding='utf-8'))
    check(stage4['passed'] and stage4['totals']['fitted_components']==1296, 'frozen complete eight-board digital source')
    check(len(reference['boards'])==len(stage4['boards'])==8, 'all eight populated boards packaged')
    check(len(reference['mounts'])==32, 'all thirty-two original PCB mounting axes')
    check(reference['case_dimensions_mm']==[600,310,240], 'declared full-size chassis dimensions')
    check(reference['allowed_intersections']==[], 'reference assembly has no hidden material-overlap exceptions')
    packages = {}
    for name, package_path, package in [('reference',reference_path,reference),('future',future_path,future)]:
        receipt_path = ROOT/('provenance/stage5-native-'+name+'.json')
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        check(receipt['passed'], name+' independent native inspection passed')
        inspector=actual_inspector_source(receipt)
        check(sha(inspector,True)==receipt['inspector_sha256_lf'], name+' actual executed independent inspector source')
        geometry = receipt['packages'][name]
        check(geometry['contract_canonical_sha256']==canonical(package_path), name+' native contract binding')
        artifacts = package.get('artifacts', package)
        native=artifact_path(package_path,artifacts['native'])
        step=artifact_path(package_path,artifacts['step'])
        check(geometry['native_sha256']==sha(native), name+' current inspected native geometry')
        check(geometry['step_sha256']==sha(step), name+' current inspected STEP geometry')
        objects = native_labels(native)
        by_label = set(objects.values())
        rows = package['parts']
        labels = [p.get('label',p.get('name')) for p in rows]
        physical=[p for p in rows if p['category'] not in ('allocation','visual_guide','reservation')]
        check(len(labels)==len(set(labels)),name+' unique contracted final part labels')
        check(set(labels)<=by_label,name+' exact native final object labels')
        check({p['label'] for p in geometry['parts']}==set(labels),name+' every final part independently inspected')
        check(geometry['step_comparison']['compared_solids']>=len(physical),name+' constituent STEP solids independently compared')
        check(geometry['interference']['unexplained_positive_volume_intersections']==0,name+' native physical interference result')
        check(geometry['interference']['physical_pairs_checked']==len(physical)*(len(physical)-1)//2,name+' every unordered physical pair checked')
        check(not geometry['physical_qualification'],name+' finite nominal geometry evidence boundary')
        for part in geometry['parts']:
            check(part['volume_mm3']>0 and part['solids']>=1,name+' inspected material volume '+part['label'])
        for clearance in geometry['clearances']:
            check(clearance['measured_mm']+2e-5>=clearance['minimum_mm'],name+' saved measured clearance')
        if name=='reference':
            if 'evidence_reuse' in receipt:
                audit_reused_reference_evidence(receipt,package_path,package,check)
            checked_boards={b['board']:b for b in geometry['boards']}
            check(set(checked_boards)==set(stage4['boards']),'all eight board source compounds independently compared')
            for board_id,b in checked_boards.items():
                check(b['source_sha256']==stage4['boards'][board_id]['STEP_sha256'],'inspected original populated source '+board_id)
                check(b['compared_solids']==stage4['boards'][board_id]['valid_reimported_solids'],'all original populated constituent solids '+board_id)
            check(len(geometry['mounts'])==len({(m['board'],m['reference']) for m in geometry['mounts']})==32,'all32 distinct mounts independently inspected')
            check(all(m['standoff_seated'] and m['shaft_to_board_radial_allowance_mm']>0 for m in geometry['mounts']),'all32 seated supports and positive nominal screw allowances')
            check(geometry['case_envelope_including_feet_mm']==[600,310,240],'actual full native chassis envelope including feet')
        else:
            check({p['port_id']:p['logical_function'] for p in geometry['ports']}==
                  {p['port_id']:p['logical_function'] for p in package['ports']},'all36 independently inspected future interface identities')
            check(all(p['minimum_pin_to_can_mm']>=package['checks']['minimum_pin_to_can_mm']-1e-5 and
                      p['minimum_pin_to_ferrule_mm']>=package['checks']['minimum_pin_to_ferrule_mm']-1e-5
                      for p in geometry['ports']),'all36 measured conductor-to-can/ferrule separations')
            check(geometry['minimum_distal_contact_gap_mm']>=package['checks']['minimum_distal_contact_edge_gap_mm']-1e-5,'measured future distal contact separation')
        output_hashes={}
        for key in ('native','step','exploded_step','mechanical_step','stl'):
            if key not in artifacts:
                continue
            path=artifact_path(package_path,artifacts[key])
            check(path.is_file() and path.stat().st_size>100,name+' actual '+key+' artifact')
            if key.endswith('step') or key=='step':
                if path.suffix.lower()=='.zip':
                    with zipfile.ZipFile(path) as archive:
                        check(archive.testzip() is None,name+' intact lossless STEP archive '+key)
                        members=[m for m in archive.namelist() if m.lower().endswith('.step')]
                        check(len(members)==1,name+' single named STEP archive member '+key)
                        raw=archive.read(members[0])
                    check(members[0]==package[key+'_member'],name+' exact archive member '+key)
                    check(hashlib.sha256(raw).hexdigest()==package[key+'_sha256_uncompressed'],name+' exact uncompressed STEP hash '+key)
                    evidence=geometry['step_evidence'] if key=='step' else geometry['extra_exports'][key]
                    check(evidence['uncompressed_sha256']==hashlib.sha256(raw).hexdigest(),name+' independently reimported archive contents '+key)
                    text=raw.decode('utf-8')
                else:
                    text=path.read_text(encoding='utf-8')
                check(text.startswith('ISO-10303-21;') and 'MANIFOLD_SOLID_BREP' in text,name+' actual BRep exchange '+key)
            output_hashes[key]=sha(path)
        packages[name]=dict(contract_canonical_sha256=canonical(package_path),native_receipt_canonical_sha256=canonical(receipt_path),
                            inspector_source=inspector.relative_to(ROOT).as_posix(),inspector_sha256_lf=receipt['inspector_sha256_lf'],
                            final_objects=len(rows),physical_objects=len(physical),outputs=output_hashes)

    board_rows=[]
    datums=json.loads((ROOT/reference['source_datums']).read_text(encoding='utf-8'))
    datum_by_id={b['board']:b for b in datums['boards']}
    check(set(datum_by_id)==set(stage4['boards']), 'producer datum inventory covers exact original board IDs')
    for board in reference['boards']:
        name=board['board']
        source_step, source_pcb = ROOT/board['source_step'],ROOT/board['source_pcb']
        check(sha(source_step)==board['source_step_sha256']==stage4['boards'][name]['STEP_sha256'],name+' exact Stage4 populated solid source')
        check(sha(source_pcb,True)==board['source_pcb_sha256_lf']==stage4['boards'][name]['pcb_sha256_lf'],name+' exact Stage4 native board source')
        check(board['fitted_components']==stage4['boards'][name]['fitted_components'],name+' original fitted population')
        connectors,mounts=pcb_geometry(source_pcb)
        datum=datum_by_id[name]
        check(len(datum['mounts'])==len(mounts)==4,name+' native four mounting holes')
        for mount in datum['mounts']:
            actual=mounts[mount['reference']]
            check(mount['position_mm']==actual['position_mm'],name+' directly derived mounting position')
            check(mount['pads'][0]['drill_mm']==[actual['diameter_mm']]*2,name+' directly derived drill diameter')
        check(len(datum['connectors'])==len(connectors),name+' all actual connector positions')
        for connector in datum['connectors']:
            actual=connectors[connector['reference']]
            check(connector['position_mm']==actual['position_mm'],name+' directly derived connector position')
            check(connector['rotation_deg']==actual['rotation_deg'],name+' directly derived connector rotation')
        board_rows.append(dict(board=name,source_step_sha256=sha(source_step),source_pcb_sha256_lf=sha(source_pcb,True),
                               fitted_components=board['fitted_components'],mounts=len(mounts),connectors=len(connectors)))
    port_source=ROOT/'docs/stage2/functional-port-map.csv'
    original_ports=list(csv.DictReader(port_source.open(encoding='utf-8',newline='')))
    proposed_ports=future['ports']
    original={p['port_id']:p['logical_function'] for p in original_ports}
    proposed={p['port_id']:p['logical_function'] for p in proposed_ports}
    check(len(proposed_ports)==len(proposed)==36 and proposed==original,'all36 exact Stage2 logical body ports retained')
    fields=('pin_object','ceramic_object','ferrule_object','socket_object','conductor_object','contact_object')
    for field in fields:
        check(len({p[field] for p in proposed_ports})==36,'one distinct actual '+field+' per body port')
    reference_bom=list(csv.DictReader((reference_path.parent/'mechanical-bom.csv').open(encoding='utf-8',newline='')))
    check(len(reference_bom)==len(reference['parts']),'complete reference mechanical BOM')
    reference_parts={p['label']:p for p in reference['parts']}
    check({p['label'] for p in reference_bom}==set(reference_parts),'exact native reference BOM label coverage')
    for row in reference_bom:
        check(row['category']==reference_parts[row['label']]['category'] and row['quantity']=='1','native mechanical BOM identity '+row['label'])
        check(row['physical_qualification']=='none','BOM evidence boundary '+row['label'])
    future_bom=list(csv.DictReader((future_path.parent/'parts.csv').open(encoding='utf-8',newline='')))
    future_parts={p['name']:p for p in future['parts']}
    check(len(future_bom)==len(future_parts) and {p['name'] for p in future_bom}==set(future_parts),'complete future physical/allocation inventory')
    for row in future_bom:
        check(all(row[k]==str(future_parts[row['name']][k]) for k in ('name','label','category','role','port_id')),'future part inventory identity '+row['name'])
    future_port_csv=list(csv.DictReader((future_path.parent/'port-map.csv').open(encoding='utf-8',newline='')))
    check(len(future_port_csv)==36,'delivered future interface table36rows')
    for row,port in zip(future_port_csv,proposed_ports):
        check(all(row[k]==str(port[k]) for k in ('port_id','logical_function',*fields)),'future CSV exact logical part mapping '+port['port_id'])
        check(json.loads(row['feedthrough_center_mm'])==port['feedthrough_center_mm'] and json.loads(row['contact_center_mm'])==port['contact_center_mm'],'future CSV exact geometric interface datums '+port['port_id'])
    for source,digest in future['source_hashes'].items():
        check(sha(ROOT/source,True)==digest,'future source binding '+source)
    for relative,digest in future['artifact_sha256'].items():
        path=artifact_path(future_path,relative)
        check(sha(path,path.suffix.lower() in ('.py','.json','.csv','.md'))==digest,'future current delivered artifact '+relative)
    check(len(proposed_ports)==len(json.loads((ROOT/'provenance/stage5-native-future.json').read_text())['packages']['future']['ports']),
          'every future body port independently inspected')
    harness=audit_harness(contract,reference,original_ports,check)
    combined={}
    if 'combined' in contract:
        combined_path=ROOT/contract['combined']['inspection']
        combined=json.loads(combined_path.read_text(encoding='utf-8'))
        check(combined['passed'] and combined['all_valid'],'independently reopened complete source-linked assembly')
        check(combined['physical_objects']==combined['source_parts_compared']==260,'all260 reference and mating pieces independently compared')
        check(combined['source_geometry_preserved'],'combined geometry preserves original source pieces')
        check(combined['native_sha256']==sha(ROOT/contract['combined']['native']),'current combined native entry assembly')
        check(combined['reference_native_sha256']==sha(ROOT/reference['native']),'combined assembly exact reference source')
        harness_contract=json.loads((ROOT/contract['harness']['contract']).read_text(encoding='utf-8'))
        check(combined['harness_native_sha256']==sha(ROOT/harness_contract['native']),'combined assembly exact mating source')
        check(combined['inspector_sha256_lf']==sha(ROOT/combined['inspector'],True),'current combined independent inspector source')
        check(not combined['physical_qualification'],'combined entry point nominal geometry evidence limit')
        combined={'receipt_canonical_sha256':canonical(combined_path),'native_sha256':combined['native_sha256'],'physical_objects':260}
    return dict(schema='scci_rh.stage5.mechanical-verification.v1',date='2026-10-28',passed=True,checks=checks,
                verifier='scripts/verify_stage5_mechanics.py',verifier_sha256_lf=sha(Path(__file__),True),
                branding_adapter_sha256_lf=sha(ROOT/'scripts/project_branding.py',True),
                scope='Full-size modular digital reference plus separate conditional future implant/interface geometry; no physical qualification',
                baseline=preserved,root_contract_canonical_sha256=canonical(contract_path),
                stage4_verification_canonical_sha256=canonical(stage4_path),
                port_source_sha256_lf=sha(port_source,True),packages=packages,boards=board_rows,
                harness=harness,combined=combined,body_ports=36,physical_qualification=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-report', action='store_true')
    arguments = parser.parse_args()
    report = audit()
    if arguments.write_report:
        REPORT.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    else:
        saved = json.loads(REPORT.read_text(encoding='utf-8'))
        assert report == saved, 'Stage 5 checkpoint drift: inspect and review changed evidence'
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
