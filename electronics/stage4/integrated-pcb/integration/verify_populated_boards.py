"""Portable actual-XML/PCB pad audit and native DRC receipt binding.

No pcbnew, regeneration or KiCad executable is required. This verifier reads
native KiCad PCB S-expressions and independently exported schematic XML. Copper
clearance/connectivity authority remains the separately bound native DRC report;
the parser does not pretend that equal net labels prove connected copper.
"""
from __future__ import annotations
import argparse,hashlib,json,xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from sexp import loads,sub,subs
from build_integration import HERE,ROOT
def sha(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def property_value(fp,name):return next((str(x[2]) for x in subs(fp,'property') if x[1]==name),'')
def net_name(node,net_codes):
    n=sub(node,'net')
    if n is None:return None
    return str(n[-1]) if len(n)>2 else net_codes.get(str(n[1]),str(n[1]))
def audit(board_names=None,write=False,allow_in_progress=False):
    system=json.loads((HERE/'system.json').read_text(encoding='utf-8'))
    selected=board_names or list(system['boards']);results={};failures=[];checks=0
    def check(condition,label):
        nonlocal checks
        checks+=1
        if not condition:failures.append(label)
    for pkg in selected:
        main=system['boards'][pkg]['source_main'];folder=HERE.parent/'boards'/pkg;pcb=folder/(main+'.kicad_pcb');xml=HERE/'boards'/pkg/(main+'.xml')
        check(pcb.is_file(),'actual PCB exists '+pkg)
        if not pcb.is_file():continue
        x=ET.parse(xml).getroot();components={c.get('ref'):c for c in x.findall('components/comp')}
        expected={(n.get('ref'),n.get('pin')):net.get('name') for net in x.findall('nets/net') for n in net.findall('node') if n.get('ref') in components}
        d=loads(pcb.read_text(encoding='utf-8'));net_codes={str(n[1]):str(n[2]) for n in subs(d,'net') if len(n)>2}
        footprints={property_value(f,'Reference'):f for f in subs(d,'footprint')};fitted=0;mechanical=[]
        actual_refs=set(footprints)
        check(set(components)<=actual_refs,'all schematic component footprints '+pkg)
        for ref in actual_refs-set(components):
            fp=footprints[ref];attr=sub(fp,'attr') or []
            check('board_only' in attr,'extra footprint must be explicitly board-only '+pkg+' '+ref)
            check('exclude_from_bom' in attr,'mechanical extras excluded from electrical BOM '+pkg+' '+ref)
            check(not any(net_name(p,net_codes) for p in subs(fp,'pad')),'mechanical extra has no electrical net '+pkg+' '+ref)
            mechanical.append(ref)
        source_metadata={c['reference']:c for c in system['components'] if c['board']==pkg}
        pad_groups=defaultdict(set);observed_pins=set();pad_count=0;models=0
        for ref,c in components.items():
            if ref not in footprints:continue
            fp=footprints[ref];metadata=source_metadata[ref]
            check(str(fp[1])==c.findtext('footprint'),'actual footprint ID '+pkg+' '+ref)
            check(property_value(fp,'Value')==c.findtext('value'),'actual value '+pkg+' '+ref)
            datasheet=next((f.text or '' for f in c.findall('fields/field') if f.get('name')=='Datasheet'),'')
            check(property_value(fp,'Datasheet')==datasheet,'actual Datasheet field '+pkg+' '+ref)
            attr=sub(fp,'attr') or [];dnp='dnp' in attr
            intended_dnp=any(p.get('name')=='dnp' for p in c.findall('property'))
            check(dnp==intended_dnp,'actual DNP assembly intent '+pkg+' '+ref)
            if not dnp:fitted+=1
            path=sub(fp,'path');check(path is not None and str(path[1])==metadata['pcb_path'],'native schematic UUID path '+pkg+' '+ref)
            pin_numbers={p.get('num') for p in c.findall('units/unit/pins/pin')}
            pads=subs(fp,'pad');pnums={str(p[1]) for p in pads if str(p[1])}
            check(pin_numbers<=pnums,'physical pad for every symbol pin '+pkg+' '+ref)
            check(not (pnums-pin_numbers),'no unmodelled electrical package pad '+pkg+' '+ref)
            if ref=='U50300':
                # TI DRB0008A 2.8 mm is centre-row spacing, not outer span.
                # The frozen standalone source had +/-1.1 mm; the new board
                # must carry the primary-drawing correction +/-1.4 mm.
                for pad in pads:
                    number=str(pad[1]);at=sub(pad,'at');size=sub(pad,'size')
                    if number in list(map(str,range(1,9))):
                        check(abs(abs(float(at[1]))-1.4)<1e-6,'TPS3431 correct +/-1.4 mm lead-row centre '+number)
                        check(abs(float(size[1])-.6)<1e-6 and abs(float(size[2])-.31)<1e-6,'TPS3431 correct lead land size '+number)
                    if number=='9':check(abs(float(size[1])-1.5)<1e-6 and abs(float(size[2])-1.75)<1e-6,'TPS3431 exposed pad size')
            if subs(fp,'model'):models+=1
            for pad in pads:
                number=str(pad[1]);actual=net_name(pad,net_codes);pad_count+=1
                if not number:
                    check(actual is None,'unnumbered mechanical pad has no net '+pkg+' '+ref);continue
                identity=(ref,number);observed_pins.add(identity);expected_net=expected.get(identity)
                check(actual==expected_net,'actual pad net '+pkg+' '+str(identity)+': '+str(actual)+' != '+str(expected_net))
                if actual:pad_groups[actual].add(identity)
        check(observed_pins==set(expected),'exhaustive electrical pin identity '+pkg)
        segments=subs(d,'segment');vias=subs(d,'via');zones=subs(d,'zone')
        check(bool(segments),'actual routed copper exists '+pkg)
        layers=sub(d,'layers');cu=[str(v[1]) for v in layers[1:] if isinstance(v,list) and len(v)>2 and str(v[1]).endswith('.Cu')]
        check(len(cu)>=4,'at least four actual copper layers '+pkg)
        drc_path=folder/'drc.json';check(drc_path.exists(),'native DRC report exists '+pkg)
        project_path=pcb.with_suffix('.kicad_pro')
        if project_path.exists():
            project=json.loads(project_path.read_text(encoding='utf-8'))
            settings=project.get('board',{}).get('design_settings',{})
            check(not settings.get('drc_exclusions'),'no project DRC exclusions '+pkg)
            check(not any(v in ['ignore','ignored'] for v in settings.get('rule_severities',{}).values()),'no ignored project rule severity '+pkg)
        drc_summary={}
        if drc_path.exists():
            report=json.loads(drc_path.read_text(encoding='utf-8'))
            check(report.get('kicad_version','').startswith('10.'),'native DRC version '+pkg)
            check(not report.get('ignored_checks'),'no ignored DRC checks '+pkg)
            for key in ['violations','unconnected_items','schematic_parity']:
                check(key in report,'native DRC report contains '+key+' '+pkg)
                drc_summary[key]=len(report.get(key,[]))
                if not allow_in_progress:check(not report.get(key),'zero native DRC '+key+' '+pkg)
            if not allow_in_progress:
                binding_path=folder/'drc-binding.json';check(binding_path.exists(),'native DRC hash binding exists '+pkg)
                if binding_path.exists():
                    binding=json.loads(binding_path.read_text(encoding='utf-8'))
                    for label,path in [('pcb_sha256_lf',pcb),('drc_sha256_lf',drc_path),('project_sha256_lf',pcb.with_suffix('.kicad_pro')),('schematic_sha256_lf',pcb.with_suffix('.kicad_sch'))]:
                        check(binding.get(label)==sha(path),'current native DRC binding '+label+' '+pkg)
                    check(binding.get('schematic_parity_checked') is True,'native schematic parity actually enabled '+pkg)
                    check(binding.get('suppressed_checks',[])==[],'native DRC no suppressed checks binding '+pkg)
        results[pkg]={'schematic_components':len(components),'fitted_components':fitted,'mechanical_footprints':mechanical,'electrical_pins':len(observed_pins),'physical_pads':pad_count,'footprints_with_3D_model':models,'copper_layers':cu,'segments':len(segments),'vias':len(vias),'zones':len(zones),'pcb_sha256_lf':sha(pcb),'xml_sha256_lf':sha(xml),'drc':drc_summary}
    result={'schema':'scci_rh.populated-board-verification.v1','passed':not failures,'mode':'in-progress inspection; DRC completion not asserted' if allow_in_progress else 'final native DRC-bound audit','assertions':checks,'boards':results,'failures':failures,'limits':['Native saved XML versus PCB pad/value/footprint/DNP/path audit','Physical copper clearance/connectivity and schematic parity are established only by the current hash-bound KiCad DRC reports','No physical assembly, signal integrity, analog accuracy, clinical isolation or biological performance has been measured']}
    if write:(HERE/'populated-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    if failures:raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',action='append');p.add_argument('--write',action='store_true');p.add_argument('--allow-in-progress',action='store_true');args=p.parse_args();audit(args.board,args.write,args.allow_in_progress)
