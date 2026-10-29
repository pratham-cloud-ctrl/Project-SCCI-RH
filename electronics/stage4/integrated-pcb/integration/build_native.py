"""Author editable integrated master and per-board native schematic copies."""
import hashlib,json,re,shutil,uuid
from pathlib import Path
from sexp import loads,dumps,Quoted as Q,sub,subs,walk
from build_integration import ROOT,HERE,source_dir,refmap

SYSTEM=json.loads((HERE/'system.json').read_text(encoding='utf-8'))
NAMESPACE=uuid.UUID('133ed52e-806c-5896-8d8a-a6138defc719')
def uid(s): return str(uuid.uuid5(NAMESPACE,s))
MASTER=uid('master'); PROJECT='SCCI_RH_integrated'
SHARE=Path('E:/project workspace assests/EDA/KiCAD/share/kicad')
PAGE_MAP={};MODULE_PAGES={};BOARD_PAGE_COUNTS={};page_counter=2
for package,board in SYSTEM['boards'].items():
    source=source_dir(package); MODULE_PAGES[package]=page_counter;page_counter+=1
    def visit(path):
        global page_counter
        for child in subs(loads(path.read_text(encoding='utf-8')),'sheet'):
            PAGE_MAP[sub(child,'uuid')[1]]=page_counter;page_counter+=1
            filename=next(p[2] for p in subs(child,'property') if p[1]=='Sheetfile')
            visit(path.parent/filename)
    visit(source/(board['source_main']+'.kicad_sch'))
    if any(p['board']==package for p in SYSTEM['added_tap_headers']):
        PAGE_MAP[uid(package+'tap-sheet')]=page_counter;page_counter+=1
    BOARD_PAGE_COUNTS[package]=page_counter-MODULE_PAGES[package]
def label(net,x,y,k): return f'(global_label {json.dumps(net)} (shape bidirectional) (at {x} {y} 180) (effects (font (size .85 .85)) (justify right)) (uuid {uid(k)}))'
def tap_sheet(pkg,mode):
    src=source_dir(pkg); main=SYSTEM['sources'][pkg]['root']; original=loads((ROOT/main).read_text(encoding='utf-8')); original_uuid=sub(original,'uuid')[1]
    path='/'+original_uuid+'/'+uid(pkg+'tap-sheet') if mode=='boards' else '/'+MASTER+'/'+uid(pkg+'module')+'/'+uid(pkg+'tap-sheet')
    project=SYSTEM['boards'][pkg]['source_main'] if mode=='boards' else PROJECT
    parts=[p for p in SYSTEM['added_tap_headers'] if p['board']==pkg]
    symbols=[];elements=[]
    for i,p in enumerate(parts):
        ref=p['reference']; libid='SCCI_RH_INTEGRATION:'+ref; p['lib_id']=libid;p['source_sheet_uuid']=uid(pkg+'tap-document'); p['source_symbol_uuid']=uid(ref+'tap-instance')
        x=71.12+i*139.7;y=91.44;half=(len(p['pins'])-1)*1.27
        graphic=f'(rectangle (start -10.16 {half+2.54}) (end 10.16 {-half-2.54}) (stroke (width .2) (type default)) (fill (type background)))'
        pins=''.join(f'(pin passive line (at -12.7 {half-j*2.54} 0) (length 2.54) (name "{v["number"]}" (effects (font (size 1 1)))) (number "{v["number"]}" (effects (font (size 1 1)))))' for j,v in enumerate(p['pins']))
        symbols.append(f'(symbol "{libid}" (pin_names (offset .7)) (in_bom yes) (on_board yes) (property "Reference" "J" (at 0 0 0) (effects (font (size 1 1)))) (property "Value" "{p["value"]}" (at 0 0 0) (effects (font (size 1 1)))) (symbol "{ref}_0_1" {graphic}) (symbol "{ref}_1_1" {pins}))')
        inst=f'(symbol (lib_id "{libid}") (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {p["source_symbol_uuid"]}) (property "Reference" "{ref}" (at {x} {y-half-5} 0) (effects (font (size 1 1)))) (property "Value" "{p["value"]}" (at {x} {y+half+5} 0) (effects (font (size 1 1)))) (property "Footprint" "{p["footprint"]}" (at {x} {y} 0) (effects (font (size 1 1)) hide))'
        for j,v in enumerate(p['pins']):
            yy=y-half+j*2.54;xx=x-12.7;end=xx-5.08
            elements.append(f'(wire (pts (xy {xx} {yy}) (xy {end} {yy})) (stroke (width 0) (type default)) (uuid {uid(ref+"wire"+v["number"])}))'+label(v['net'],end,yy,ref+'label'+v['number']))
            inst+=f'(pin "{v["number"]}" (uuid {uid(ref+"pin"+v["number"])}))'
        elements.append(inst+f'(instances (project "{project}" (path "{path}" (reference "{ref}") (unit 1)))))')
    texts=[('INTEGRATED COMPONENT-TAP HARNESS / '+pkg,20,18,1.5),('Physical headers expose actual earlier component taps. Original connectors remain available.',20,26,1),('Only named electrical nets connect. AFE, HOST and companion grounds remain distinct.',20,34,1),('Artificial-load digital design. Added wiring capacitance and connector integrity require measurement.',20,150,1)]
    for i,(t,x,y,size) in enumerate(texts):elements.append(f'(text "{t}" (at {x} {y} 0) (effects (font (size {size} {size})) (justify left)) (uuid {uid(pkg+"taptext"+str(i))}))')
    return f'(kicad_sch (version 20250114) (generator "scci_rh_integrated") (uuid {uid(pkg+"tap-document")}) (paper "A3") (title_block (title "Project SCCI RH / {pkg} integration taps") (date "2026-10-14") (rev "0.1") (company "Project SCCI RH")) (lib_symbols {"".join(symbols)}) {"".join(elements)})\n'
def append_tap(document,pkg,mode):
    project=SYSTEM['boards'][pkg]['source_main'] if mode=='boards' else PROJECT
    path='/'+sub(document,'uuid')[1] if mode=='boards' else '/'+MASTER+'/'+uid(pkg+'module')
    # New child is located beneath the original drawing, on a larger A1 sheet.
    sub(document,'paper')[1]=Q('A1')
    document.append(loads(f'(sheet (at 20.32 520.7) (size 180.34 12.7) (stroke (width .254) (type default)) (fill (color 0 0 0 0)) (uuid {uid(pkg+"tap-sheet")}) (property "Sheetname" "Integrated_component_taps" (at 20.32 519.43 0) (effects (font (size 1 1)) (justify left bottom))) (property "Sheetfile" "integration_taps.kicad_sch" (at 20.32 535.94 0) (effects (font (size 1 1)) (justify left top))) (instances (project "{project}" (path "{path}" (page "{BOARD_PAGE_COUNTS[pkg] if mode=="boards" else PAGE_MAP[uid(pkg+"tap-sheet")]}")))))'))
def diagram_margins(document):
    # Source-qualified net labels are longer than their standalone aliases.
    # Keep every glyph on paper without changing native electrical identities.
    sub(document,'paper')[1]=Q('A1')
    for element in document[1:]:
        if not isinstance(element,list) or element[0] in ['lib_symbols','title_block','instances']:continue
        if element[0] not in ['symbol','wire','label','global_label','hierarchical_label','junction','no_connect','text','sheet','polyline','rectangle']:continue
        for node in walk(element):
            if node and node[0] in ['at','xy','start','end'] and len(node)>2:
                node[1]=str(round(float(node[1])+81.28,6));node[2]=str(round(float(node[2])+25.4,6))
def main():
    seen_flags=set(); outputs={}
    actual_power_out={p['net'] for c in SYSTEM['components'] for p in c['pins'] if p['type']=='power_out'}
    for mode in ['master','boards']:
        for pkg,source in SYSTEM['sources'].items():
            src=source_dir(pkg); dst=HERE/mode/pkg;dst.mkdir(parents=True,exist_ok=True)
            mainname=SYSTEM['boards'][pkg]['source_main']; rootdoc=loads((src/(mainname+'.kicad_sch')).read_text(encoding='utf-8'));original_uuid=sub(rootdoc,'uuid')[1]
            for file in src.glob('*.kicad_sch'):
                doc=loads(file.read_text(encoding='utf-8'))
                for node in walk(doc):
                    if node and node[0] in ['global_label','label']:
                        old=str(node[1]); mapped=SYSTEM['net_mapping'].get(pkg+'::'+old)
                        if mapped:node[1]=Q(mapped)
                    if node and node[0]=='property' and node[1]=='Reference' and re.fullmatch(r'[^0-9]+[0-9]+',str(node[2])):
                        node[2]=Q(refmap(str(node[2]),source['offset']))
                    if node and node[0]=='reference' and re.fullmatch(r'[^0-9]+[0-9]+',str(node[1])):node[1]=Q(refmap(str(node[1]),source['offset']))
                    if mode=='master' and node and node[0]=='project':node[1]=Q(PROJECT)
                    if mode=='master' and node and node[0]=='path' and str(node[1]).startswith('/'+original_uuid):node[1]=Q('/'+MASTER+'/'+uid(pkg+'module')+str(node[1])[len(original_uuid)+1:])
                # Multiple source projects each supplied a power flag. Retain
                # exactly one native driver for each joined power-net flag.
                if mode=='master':
                    remove=[]
                    for sym in subs(doc,'symbol'):
                        prop=next((p for p in subs(sym,'property') if p[1]=='Reference'),None)
                        if prop is None or not str(prop[2]).startswith('#'):continue
                        at=sub(sym,'at'); xy=tuple(round(float(v),6) for v in at[1:3]); labs=[l for l in subs(doc,'global_label') if tuple(round(float(v),6) for v in sub(l,'at')[1:3])==xy]
                        if not labs:continue
                        net=str(labs[0][1])
                        if net in seen_flags or net in actual_power_out: remove.extend([sym,*labs])
                        else:seen_flags.add(net)
                    doc[:]=[d for d in doc if not any(d is r for r in remove)]
                if file.stem==mainname and any(p['board']==pkg for p in SYSTEM['added_tap_headers']):append_tap(doc,pkg,mode)
                if mode=='master':
                    for child in subs(doc,'sheet'):
                        project=sub(sub(child,'instances'),'project'); path=sub(project,'path')
                        sub(path,'page')[1]=Q(str(PAGE_MAP[sub(child,'uuid')[1]]))
                diagram_margins(doc)
                (dst/file.name).write_text(dumps(doc)+'\n',encoding='utf-8')
            for file in src.glob('*.kicad_sym'):shutil.copyfile(file,dst/file.name)
            for folder in src.glob('*.pretty'):shutil.copytree(folder,dst/folder.name,dirs_exist_ok=True)
            if pkg=='supervision':
                # Deliberate new-integration land-pattern correction. The frozen
                # source is never patched. TI DRB0008A dimension 2.8 mm spans
                # pad-row centres; +/-1.1 mm in the old snapshot was incorrect.
                name='Texas_DRB0008A_VSON8_3x3_P0.65_EP1.5x1.75.kicad_mod'
                fp=dst/'scci_rh_sup.pretty'/name;footprint=loads(fp.read_text(encoding='utf-8'))
                for pad in subs(footprint,'pad'):
                    if str(pad[1]) in list(map(str,range(1,9))):
                        at=sub(pad,'at');at[1]='-1.4' if float(at[1])<0 else '1.4'
                fp.write_text(dumps(footprint)+'\n',encoding='utf-8')
            for name in ['sym-lib-table','fp-lib-table']:
                if (src/name).exists():shutil.copyfile(src/name,dst/name)
            if any(p['board']==pkg for p in SYSTEM['added_tap_headers']):
                tap_doc=loads(tap_sheet(pkg,mode));diagram_margins(tap_doc);tap_native=dumps(tap_doc)+'\n'
                (dst/'integration_taps.kicad_sch').write_text(tap_native,encoding='utf-8')
                tap_symbols=sub(loads(tap_native),'lib_symbols')[1:]
                external=[]
                for symbol in tap_symbols:
                    symbol[1]=Q(str(symbol[1]).split(':',1)[1]);external.append(dumps(symbol))
                (dst/'SCCI_RH_INTEGRATION.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "scci_rh_integrated") '+' '.join(external)+')\n',encoding='utf-8')
                symt=dst/'sym-lib-table';symtext=symt.read_text(encoding='utf-8').rstrip()
                symentry=' (lib (name "SCCI_RH_INTEGRATION") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH_INTEGRATION.kicad_sym") (options "") (descr "Actual component-tap connector symbols"))'
                symt.write_text(symtext[:-1]+symentry+')\n',encoding='utf-8')
                fpt=dst/'fp-lib-table';text=fpt.read_text(encoding='utf-8').rstrip();entry=' (lib (name "Connector_PinHeader_2.54mm") (type "KiCad") (uri "${KIPRJMOD}/../../shared/Connector_PinHeader_2.54mm.pretty") (options "") (descr "Project-local native KiCad integration header snapshots"))'
                fpt.write_text(text[:-1]+entry+')\n',encoding='utf-8')
            (dst/(mainname+'.kicad_pro')).write_text(json.dumps({'meta':{'filename':mainname+'.kicad_pro','version':1}},indent=2)+'\n',encoding='utf-8')
            outputs[pkg]={'master_root':str((HERE/'master'/pkg/(mainname+'.kicad_sch')).relative_to(ROOT)).replace('\\','/'),'board_root':str((HERE/'boards'/pkg/(mainname+'.kicad_sch')).relative_to(ROOT)).replace('\\','/')}
    # Overview sheet is an actual hierarchy; it is not a picture of connectivity.
    sheets=[]
    for i,(pkg,board) in enumerate(SYSTEM['boards'].items()):
        x=30+(i%2)*260;y=65+(i//2)*65
        sheets.append(f'(sheet (at {x} {y}) (size 230 30) (stroke (width .254) (type default)) (fill (color 0 0 0 0)) (uuid {uid(pkg+"module")}) (property "Sheetname" "{pkg}" (at {x} {y-2} 0) (effects (font (size 1.4 1.4)) (justify left bottom))) (property "Sheetfile" "{pkg}/{board["source_main"]}.kicad_sch" (at {x} {y+32} 0) (effects (font (size 1 1)) (justify left top))) (instances (project "{PROJECT}" (path "/{MASTER}" (page "{MODULE_PAGES[pkg]}")))))')
    texts=['PROJECT SCCI RH / INTEGRATED MODULAR CIRCUIT SYSTEM','Eight functional boards; actual mapped electrical connections and physical tap headers.','Reference namespaces preserve frozen source identities. Read integrated-pcb-wiring.csv for the harness.','Common driver rearm and independent supervisor phase rearm are deliberately separated.','Digital artificial-load concept. Geometry and ERC do not establish implantation or measured performance.']
    for i,t in enumerate(texts):sheets.append(f'(text "{t}" (at 25 {18+i*8} 0) (effects (font (size {1.7 if i==0 else 1.05} {1.7 if i==0 else 1.05})) (justify left)) (uuid {uid("mastertext"+str(i))}))')
    master=HERE/'master'/f'{PROJECT}.kicad_sch'
    master.write_text(f'(kicad_sch (version 20250114) (generator "scci_rh_integrated") (uuid {MASTER}) (paper "A2") (title_block (title "Project SCCI RH / Integrated modular SCCI electrical system") (date "2026-10-14") (rev "0.1") (company "Project SCCI RH")) (lib_symbols) {"".join(sheets)})\n',encoding='utf-8')
    (master.with_suffix('.kicad_pro')).write_text(json.dumps({'meta':{'filename':PROJECT+'.kicad_pro','version':1}},indent=2)+'\n',encoding='utf-8')
    # KiCad resolves an entire hierarchy through the root project library tables.
    # Build explicit root tables for all native symbol and footprint snapshots.
    root_tables={'sym-lib-table':['sym_lib_table',['version','7']], 'fp-lib-table':['fp_lib_table',['version','7']]}
    seen_library_names={name:set() for name in root_tables}
    integration_symbols=[]
    for pkg in SYSTEM['sources']:
        folder=HERE/'master'/pkg
        for name in root_tables:
            table=loads((folder/name).read_text(encoding='utf-8'))
            for library in subs(table,'lib'):
                lname=str(sub(library,'name')[1])
                if lname=='SCCI_RH_INTEGRATION':
                    syms=loads((folder/'SCCI_RH_INTEGRATION.kicad_sym').read_text(encoding='utf-8'))
                    integration_symbols+=subs(syms,'symbol')
                    continue
                if lname in seen_library_names[name]:continue
                seen_library_names[name].add(lname)
                uri=sub(library,'uri'); old=str(uri[1])
                if old.startswith('${KIPRJMOD}/../../shared/'):uri[1]=Q(old.replace('${KIPRJMOD}/../../shared/','${KIPRJMOD}/../shared/'))
                elif old.startswith('${KIPRJMOD}/'):uri[1]=Q(old.replace('${KIPRJMOD}/','${KIPRJMOD}/'+pkg+'/'))
                root_tables[name].append(library)
    if integration_symbols:
        (master.parent/'SCCI_RH_INTEGRATION.kicad_sym').write_text(dumps(['kicad_symbol_lib',['version','20241209'],['generator',Q('scci_rh_integrated')],*integration_symbols])+'\n',encoding='utf-8')
        root_tables['sym-lib-table'].append(loads('(lib (name "SCCI_RH_INTEGRATION") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH_INTEGRATION.kicad_sym") (options "") (descr "Integrated component-tap headers"))'))
    for name,table in root_tables.items():(master.parent/name).write_text(dumps(table)+'\n',encoding='utf-8')
    local=HERE/'shared/Connector_PinHeader_2.54mm.pretty';local.mkdir(parents=True,exist_ok=True)
    for component in SYSTEM['added_tap_headers']:
        fp=component['footprint'].split(':',1)[1]+'.kicad_mod'
        shutil.copyfile(SHARE/'footprints/Connector_PinHeader_2.54mm.pretty'/fp,local/fp)
    SYSTEM['native_outputs']=outputs;SYSTEM['master_uuid']=MASTER;SYSTEM['master_module_pages']=MODULE_PAGES
    root_ids={p:sub(loads((source_dir(p)/(b['source_main']+'.kicad_sch')).read_text(encoding='utf-8')),'uuid')[1] for p,b in SYSTEM['boards'].items()}
    for component in SYSTEM['components']:
        pkg=component['board']; original_uuid=root_ids[pkg]
        if component.get('added'):
            match=next(p for p in SYSTEM['added_tap_headers'] if p['reference']==component['reference'])
            component.update({k:match[k] for k in ['lib_id','source_sheet_uuid','source_symbol_uuid']})
            component['source_instance_path']='/'+original_uuid+'/'+uid(pkg+'tap-sheet')
            component['pcb_path']=component['source_instance_path']+'/'+component['source_symbol_uuid']
        component['master_path']='/'+MASTER+'/'+uid(pkg+'module')+component['source_instance_path'][len(original_uuid)+1:]+'/'+component['source_symbol_uuid']
    (HERE/'system.json').write_text(json.dumps(SYSTEM,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'master':str(master),'boards':len(outputs),'retained_power_flags':len(seen_flags),'added_headers':len(SYSTEM['added_tap_headers'])}))
if __name__=='__main__':main()
