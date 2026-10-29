"""Consolidate frozen source circuits by documented electrical wiring only.

The source projects are inputs, never modified.  Every joined net retains its
source identities; source-only equal names do not silently join across boards.
"""
from __future__ import annotations
import csv, hashlib, json, re, xml.etree.ElementTree as ET
from pathlib import Path
from sexp import loads, sub, subs, walk

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
STAGE=ROOT/'electronics/stage4'
PACKAGES=['monitoring-cell','current-driver','recording-front-end','contact-router','supervision','power','monitoring-transport','controller-carrier']
MAINS=['monitoring_cell','current_driver','recording_front_end','contact_router','supervision','power','monitoring_transport','controller_carrier']
def digest(p): return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def source_dir(pkg): return STAGE/pkg
def refmap(ref,offset):
    m=re.fullmatch(r'([^0-9]+)([0-9]+)',ref)
    assert m,ref
    return m[1]+str(int(m[2])+offset)
def key(p,n): return p+'::'+n
def main():
    HERE.mkdir(parents=True,exist_ok=True)
    components=[]; boards={}; sources={}; pin_lookup={}; net_lookup={}; parent={}; symbol_info={}
    def find(x):
        parent.setdefault(x,x)
        if parent[x]!=x: parent[x]=find(parent[x])
        return parent[x]
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[max(a,b)]=min(a,b)
    for ix,(pkg,mainname) in enumerate(zip(PACKAGES,MAINS),1):
        src=source_dir(pkg); xml=src/(mainname+'.xml')
        if not xml.exists(): continue
        x=ET.parse(xml).getroot(); offset=ix*10000
        sources[pkg]={'xml':str(xml.relative_to(ROOT)).replace('\\','/'),'sha256_lf':digest(xml),'root':str((src/(mainname+'.kicad_sch')).relative_to(ROOT)).replace('\\','/'),'offset':offset}
        libparts={(l.get('lib'),l.get('part')):l for l in x.findall('libparts/libpart')}
        for sch in src.glob('*.kicad_sch'):
            document=loads(sch.read_text(encoding='utf-8'))
            for inst in subs(document,'symbol'):
                prop=next((p for p in subs(inst,'property') if p[1]=='Reference'),None)
                if prop is not None:
                    proj=sub(sub(inst,'instances'),'project');instance_path=sub(proj,'path')[1]
                    symbol_info[pkg,str(prop[2])]={'source_sheet':sch.name,'source_sheet_uuid':sub(document,'uuid')[1],'source_symbol_uuid':sub(inst,'uuid')[1],'source_instance_path':instance_path,'pcb_path':instance_path+'/'+sub(inst,'uuid')[1]}
        pins={}
        for n in x.findall('nets/net'):
            net=n.get('name'); find(key(pkg,net))
            for node in n.findall('node'):
                pins[node.get('ref'),node.get('pin')]=net
        refs=[]
        for c in x.findall('components/comp'):
            ref=c.get('ref'); new=refmap(ref,offset); ls=c.find('libsource'); lp=libparts[ls.get('lib'),ls.get('part')]
            cp=[]
            for p in lp.findall('pins/pin'):
                net=pins.get((ref,p.get('num')))
                cp.append({'number':p.get('num'),'name':p.get('name'),'type':p.get('type'),'source_net':net,'net':key(pkg,net) if net else None})
                pin_lookup[pkg,ref,p.get('num')]=net
            datasheet=next((f.text or '' for f in c.findall('fields/field') if f.get('name')=='Datasheet'),'')
            dnp=any(p.get('name')=='dnp' for p in c.findall('property'))
            components.append({'board':pkg,'source_package':pkg,'source_ref':ref,'reference':new,'lib_id':ls.get('lib')+':'+ls.get('part'),'value':c.findtext('value'),'footprint':c.findtext('footprint'),'datasheet':datasheet,'dnp':dnp,'pins':cp,**symbol_info[pkg,ref]})
            refs.append(new)
        boards[pkg]={'references':refs,'source_main':mainname,'offset':offset}
    rows=[]; excluded=[]
    for name in ['supervision-wiring.csv','power-wiring.csv','monitoring-transport-wiring.csv','integrated-pcb-controller-wiring.csv']:
        path=ROOT/'docs/stage4'/name
        if not path.exists(): continue
        for row in csv.DictReader(path.open(encoding='utf-8-sig',newline='')):
            if row['from_package'] not in sources or row['to_package'] not in sources: continue
            for side in ['from','to']:
                ep=(row[side+'_package'],row[side+'_ref'],row[side+'_pin'])
                assert pin_lookup.get(ep)==row[side+'_net'],(ep,pin_lookup.get(ep),row[side+'_net'])
            if name=='supervision-wiring.csv' and row['from_package']=='current-driver' and row['from_ref']=='J3' and row['from_pin'] in ['4','8'] and row['to_package']=='supervision' and row['to_ref']=='J3' and row['to_pin'] in ['10','11']:
                excluded.append({**row,'reason':'Superseded in integrated system: common driver rearm and two independent supervisor phase-rearm GPIO must remain separate, avoiding three push-pull outputs on one wire.'})
                continue
            union(key(row['from_package'],row['from_net']),key(row['to_package'],row['to_net']))
            rows.append(row)
    groups={}
    for n in sorted(parent): groups.setdefault(find(n),[]).append(n)
    mappings={}; nets=[]
    for ix,group in enumerate(sorted(groups.values()),1):
        labels=[a.split('::',1)[1] for a in group]
        preferred=next((s for s in ['GND','AFEAGND','COMP_GND','HOST_3V3','HOST_5','SUP_3V3','SUP_5','VH_24','MON_VREF','MON_VMID'] if s in labels),labels[0])
        canonical=min(group,key=lambda s:(PACKAGES.index(s.split('::',1)[0]),s))
        identifier=hashlib.sha256(canonical.encode()).hexdigest()[:8]
        name=f'SYS_{identifier}__'+re.sub(r'[^A-Za-z0-9_+.-]','_',preferred) if len(group)>1 else group[0].replace('::','__')
        if len(group)==1 and labels[0].startswith('unconnected-'):
            source_package=group[0].split('::',1)[0]
            name=re.sub(r'^(unconnected-\()([^\-]+)(-)',lambda m:m[1]+refmap(m[2],sources[source_package]['offset'])+m[3],labels[0])
        for item in group: mappings[item]=name
        nets.append({'name':name,'sources':group,'cross_board':len(group)>1})
    for c in components:
        for p in c['pins']:
            if p['net']: p['net']=mappings[p['net']]
    for row in rows:
        row['integrated_net']=mappings[key(row['from_package'],row['from_net'])]
        for side in ['from','to']:
            row[side+'_integrated_ref']=refmap(row[side+'_ref'],sources[row[side+'_package']]['offset'])
    # Component output taps in the earlier contract now have actual board headers.
    # Existing J headers remain the actual interface everywhere else. A loom may
    # splice one named net to several mates; a splice is never an additional net.
    taps={}
    for row in rows:
        for side in ['from','to']:
            if not row[side+'_ref'].startswith('J'):
                pkg=row[side+'_package']; net=row[side+'_net']
                domain='AFE' if net.startswith('AFE_') or net=='AFEAGND' else 'HOST'
                taps.setdefault((pkg,domain),set()).add(net)
    tap_pins={}; adapters=[]
    for (pkg,domain),labels in sorted(taps.items()):
        offset=sources[pkg]['offset']; labels=sorted(labels)
        for chunkidx,start in enumerate(range(0,len(labels),11)):
            chunk=labels[start:start+11]; ground='AFEAGND' if domain=='AFE' else ('HOSTGND' if pkg=='recording-front-end' else 'GND')
            if ground not in chunk: chunk.append(ground)
            src_ref='J'+str(9901+len([a for a in adapters if a['board']==pkg])); reference=refmap(src_ref,offset)
            pins=[]
            for pi,net in enumerate(chunk,1):
                pins.append({'number':str(pi),'name':str(pi),'type':'passive','source_net':net,'net':mappings[key(pkg,net)]})
                tap_pins[pkg,net]=(reference,str(pi))
            cp={'board':pkg,'source_package':pkg,'source_ref':src_ref,'reference':reference,'lib_id':'SCCI_RH_INTEGRATION:'+src_ref,'value':domain+' TAP HARNESS','footprint':'Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical'%len(pins),'pins':pins,'source_sheet':'integration_taps.kicad_sch','source_sheet_uuid':'','source_symbol_uuid':'','added':True,'domain':domain}
            adapters.append(cp); components.append(cp); boards[pkg]['references'].append(reference)
    for row in rows:
        for side in ['from','to']:
            pkg=row[side+'_package']; net=row[side+'_net']
            if not row[side+'_ref'].startswith('J'):
                row[side+'_harness_ref'],row[side+'_harness_pin']=tap_pins[pkg,net]
            else:
                row[side+'_harness_ref']=row[side+'_integrated_ref']; row[side+'_harness_pin']=row[side+'_pin']
    result={'schema':'scci_rh.integrated-system.v1','scope':'Digital modular artificial-load engineering; no physical qualification','sources':sources,'boards':boards,'components':components,'nets':nets,'net_mapping':mappings,'wires':rows,'added_tap_headers':adapters,'excluded_legacy_wires':excluded}
    (HERE/'system.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (HERE/'integration-changes.json').write_text(json.dumps({'schema':'scci_rh.integration-changes.v1','excluded_legacy_wires':excluded,'added_tap_headers':adapters,'source_edit_policy':'Seven source circuit packages and previous CSV files remain unchanged.'},indent=2)+'\n',encoding='utf-8')
    columns=['from_package','from_ref','from_pin','from_net','to_package','to_ref','to_pin','to_net','purpose','integrated_net','from_integrated_ref','to_integrated_ref','from_harness_ref','from_harness_pin','to_harness_ref','to_harness_pin']
    with (ROOT/'docs/stage4/integrated-pcb-wiring.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'boards':len(boards),'parts':len(components),'wires':len(rows),'nets':len(nets)}))
if __name__=='__main__': main()
