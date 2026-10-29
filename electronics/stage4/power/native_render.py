def fnum(x):return f"{x:.4f}".rstrip("0").rstrip(".")
FONT='(effects (font (size 1 1)))'
def pin_positions(p):
    out=[]
    for side in ("L","R"):
        pins=[v for v in p["pins"] if v[3]==side];start=(len(pins)-1)*1.27
        for i,(n,name,kind,_) in enumerate(pins):
            out.append((str(n),name,kind,-12.7 if side=="L" else 12.7,start-i*2.54,0 if side=="L" else 180))
    return out
def lib_symbol(p):
    name=p["ref"];pins=pin_positions(p);ymax=max(v[4] for v in pins)+2.54;ymin=min(v[4] for v in pins)-2.54
    graphic=f'(rectangle (start -10.16 {fnum(ymax)}) (end 10.16 {fnum(ymin)}) (stroke (width 0.2) (type default)) (fill (type background)))'
    if p["kind"] in ("R","C"):
        wire=lambda a,b:f'(polyline (pts (xy {a} 0) (xy {b} 0)) (stroke (width 0.2) (type default)) (fill (type none)))'
        if p["kind"]=="R":graphic='(rectangle (start -5.08 1.27) (end 5.08 -1.27) (stroke (width 0.2) (type default)) (fill (type none)))'+wire(-10.16,-5.08)+wire(5.08,10.16)
        else:
            plate=lambda x:f'(polyline (pts (xy {x} -2.54) (xy {x} 2.54)) (stroke (width 0.3) (type default)) (fill (type none)))'
            graphic=plate(-1.27)+plate(1.27)+wire(-10.16,-1.27)+wire(1.27,10.16)
    text=f'(symbol "SCCI_RH_POWER:{name}" (pin_names (offset 0.7)) (in_bom yes) (on_board yes) (property "Reference" "{name[0]}" (at 0 0 0) {FONT}) (property "Value" "{p["value"]}" (at 0 0 0) {FONT}) (property "Footprint" "{p["footprint"]}" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "{name}_0_1" {graphic}) (symbol "{name}_1_1" '
    for n,nm,kind,x,y,a in pins:text+=f'(pin {kind} line (at {fnum(x)} {fnum(y)} {a}) (length 2.54) (name "{nm}" (effects (font (size 0.85 0.85)))) (number "{n}" {FONT})) '
    return text+'))'
def glabel(net,x,y,key,left=False):return f'(global_label "{net}" (shape bidirectional) (at {fnum(x)} {fnum(y)} {180 if left else 0}) (effects (font (size 0.85 0.85)) (justify {"right" if left else "left"})) (uuid {uid(key)}))'
local=OUT/"scci_rh_power.pretty";local.mkdir(exist_ok=True)
# Native footprint snapshots are package-local and independent of workstation associations.
for part in parts:
 lib,name=part['footprint'].split(':')
 if lib!='scci_rh_power':
  source=SHARE/'footprints'/(lib+'.pretty')/(name+'.kicad_mod');assert source.is_file(),source
  (local/(name+'.kicad_mod')).write_text(source.read_text(encoding='utf-8'),encoding='utf-8')
 part['footprint']='scci_rh_power:'+name
flag_symbol='(symbol "SCCI_RH_POWER:EXTERNAL_POWER" (pin_names (offset 0)) (in_bom no) (on_board no) (property "Reference" "#FLG" (at 0 0 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_OR_CONVERTER_SOURCE" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "EXTERNAL_POWER_0_1" (polyline (pts (xy -1 1) (xy 0 2) (xy 1 1)) (stroke (width 0.2) (type default)) (fill (type none)))) (symbol "EXTERNAL_POWER_1_1" (pin power_out line (at 0 0 90) (length 0) (name "SUPPLIED" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))'
for sheet in SHEETS:
    sid=ROOT_ID if sheet=="root" else uid(sheet+"-document")
    path="/"+ROOT_ID if sheet=="root" else "/"+ROOT_ID+"/"+uid(sheet+"-sheet")
    elements=[]
    for p in [p for p in parts if p["sheet"]==sheet]:
        ref=p["ref"];x,y=p["xy"];pins=pin_positions(p);top=y-max(v[4] for v in pins)-5.08;bottom=y-min(v[4] for v in pins)+5.08
        inst=f'(symbol (lib_id "SCCI_RH_POWER:{ref}") (at {fnum(x)} {fnum(y)} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {fnum(x)} {fnum(top)} 0) {FONT}) (property "Value" "{p["value"]}" (at {fnum(x)} {fnum(bottom)} 0) (effects (font (size 0.95 0.95)))) (property "Footprint" "{p["footprint"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) (property "Datasheet" "{p["source_url"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) '
        for n,nm,kind,px,py,a in pins:
            xx,yy=x+px,y-py;net=p["nets"][n];inst+=f'(pin "{n}" (uuid {uid(ref+"-pin-"+n)})) '
            if net is None:elements.append(f'(no_connect (at {fnum(xx)} {fnum(yy)}) (uuid {uid(ref+"-nc-"+n)}))')
            else:
                ex=xx+(-5.08 if px<0 else 5.08)
                elements.append(f'(wire (pts (xy {fnum(xx)} {fnum(yy)}) (xy {fnum(ex)} {fnum(yy)})) (stroke (width 0) (type default)) (uuid {uid(ref+"-wire-"+n)}))')
                elements.append(glabel(net,ex,yy,ref+"-label-"+n,left=px<0))
        elements.append(inst+f'(instances (project "{PROJECT}" (path "{path}" (reference "{ref}") (unit 1)))))')
    texts=[("DIGITAL SCCI ENGINEERING / ARTIFICIAL LOADS / BATTERY AND POWER",20.32,17.78,1.5),("2S protected pack, independent supervisor rails, host converters and floating AFE supplies. Digital circuit design, not implant qualification.",20.32,25.4,1)]
    if sheet=="root":
        for i,net in enumerate(("PACK_POS","PACK_BUS","GND","SUP_3V3","SUP_5","HOST_3V3","HOST_5","HOST_15","VH_24")):
            x,y=25.4+(i%6)*91.44,241.3+(i//6)*15.24;ref=f"#FLG{i+1}"
            elements.append(f'(symbol (lib_id "SCCI_RH_POWER:EXTERNAL_POWER") (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_OR_CONVERTER_SOURCE" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (pin "1" (uuid {uid(ref+"-pin")})) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (reference "{ref}") (unit 1)))))')
            elements.append(glabel(net,x,y,ref+"-label"))
        for i,name in enumerate(SHEETS[1:]):
            x=20.32+(i%3)*185.42;y=279.4+(i//3)*12.7
            elements.append(f'(sheet (at {fnum(x)} {fnum(y)}) (size 157.48 3.81) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {uid(name+"-sheet")}) (property "Sheetname" "{name}" (at {fnum(x)} {fnum(y-1.27)} 0) (effects (font (size .85 .85)) (justify left bottom))) (property "Sheetfile" "{name}.kicad_sch" (at {fnum(x)} {fnum(y+5.08)} 0) (effects (font (size .85 .85)) (justify left top))) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (page "{i+2}")))))')
    else:
        texts += [("All labels are native electrical connections. PG is diagnostic; full qualification remains the nine independent supervision windows.",20.32,391.16,1),("Converter shutdown does not discharge boost paths or remove stored energy. Body-facing shutdown remains the separate terminal guards.",20.32,398.78,1)]
    for i,(text,x,y,size) in enumerate(texts):elements.append(f'(text "{text}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size {size} {size})) (justify left)) (uuid {uid(sheet+"-text-"+str(i))}))')
    embedded="".join(lib_symbol(p) for p in parts if p["sheet"]==sheet)+(flag_symbol if sheet=="root" else "")
    data=f'(kicad_sch (version 20250114) (generator "scci_rh_stage4_power") (uuid {sid}) (paper "A2") (title_block (title "Project SCCI RH S4 / {TITLES[sheet]}") (date "2026-10-14") (rev "0.1") (company "Project SCCI RH") (comment 1 "Native power; firmware, PCB layout, EMI and physical battery/thermal qualification remain")) (lib_symbols {embedded}) '+"".join(elements)+')\n'
    (OUT/(PROJECT if sheet=="root" else sheet)).with_suffix(".kicad_sch").write_text(data,encoding="utf-8")
(OUT/"SCCI_RH_POWER.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "scci_rh_stage4_power") '+("".join(lib_symbol(p) for p in parts)+flag_symbol).replace('(symbol "SCCI_RH_POWER:', '(symbol "')+')\n',encoding="utf-8")
(OUT/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "SCCI_RH_POWER") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH_POWER.kicad_sym") (options "") (descr "Package-specific primary-pin-audited power symbols; sources in connectivity.json")))\n',encoding="utf-8")
(OUT/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "scci_rh_power") (type "KiCad") (uri "${KIPRJMOD}/scci_rh_power.pretty") (options "") (descr "KiCad library footprint snapshots; PCB assembly and mask/paste qualification remain")))\n',encoding="utf-8")
(OUT/(PROJECT+".kicad_pro")).write_text(json.dumps({"meta":{"filename":PROJECT+".kicad_pro","version":1},"erc":{"rule_severities":{"single_global_label":"warning","four_way_junction":"warning","simulation_model_issue":"warning","footprint_filter":"warning"}}},indent=2)+"\n",encoding="utf-8")
