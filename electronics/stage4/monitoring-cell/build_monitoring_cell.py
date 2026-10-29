"""Generate the NEW editable Stage 4 monitoring slice; no historical files changed.

This builds native hierarchical KiCad sources and local original symbols from
the pin-level connection manifest below. It does not generate a PCB or simulate
analog performance. Run with normal Python; KICAD_SHARE can relocate footprints.
"""
from pathlib import Path
import csv
import json
import os
import shutil
import uuid

OUT = Path(__file__).resolve().parent
SHARE = Path(os.environ.get("KICAD_SHARE", r"E:\project workspace assests\EDA\KiCAD\share\kicad"))
PROJECT = "monitoring_cell"
ROOT_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "project-scci-rh/stage4/monitoring-cell/root"))
def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "project-scci-rh/stage4/monitoring-cell/" + key))

SOURCES = {
    "ina": "https://www.ti.com/lit/ds/symlink/ina241a.pdf",
    "opa": "https://www.ti.com/lit/ds/symlink/opa391.pdf",
    "adc": "https://www.ti.com/lit/ds/symlink/ads8866.pdf",
    "mux": "https://www.ti.com/lit/ds/symlink/tmux1136.pdf",
    "ref": "https://www.ti.com/lit/ds/symlink/ref34.pdf",
    "cmp": "https://www.ti.com/lit/ds/symlink/tlv3202.pdf",
    "and": "https://www.ti.com/lit/ds/symlink/sn74lvc1g11.pdf",
    "ff": "https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf",
}
FP = {
    "R": "Resistor_SMD:R_0805_2012Metric", "C": "Capacitor_SMD:C_0805_2012Metric",
    "ina": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "opa": "Package_TO_SOT_SMD:SOT-353_SC-70-5",
    "adc": "Package_SO:MSOP-10_3x3mm_P0.5mm",
    "mux": "Package_SO:MSOP-10_3x3mm_P0.5mm",
    "ref": "Package_TO_SOT_SMD:SOT-23-6",
    "cmp": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "and": "Package_TO_SOT_SMD:SOT-23-6",
    "ff": "Package_SO:VSSOP-8_2.3x2mm_P0.5mm",
}
# number, function, KiCad electrical type, side; position is generated on 2.54mm grid.
PINS = {
    "ina": [(8,"IN+","input","L"),(1,"IN-","input","L"),(7,"REF1","input","L"),(3,"REF2","input","L"),(6,"VS","power_in","L"),(2,"GND","power_in","L"),(4,"NC=GND","passive","L"),(5,"OUT","output","R")],
    # TI SBOS925E Table4-1: production DCK pinout differs from preview DBV.
    "opa": [(1,"IN+","input","L"),(3,"IN-","input","L"),(5,"V+","power_in","L"),(2,"V-","power_in","L"),(4,"OUT","output","R")],
    "adc": [(3,"AINP","input","L"),(4,"AINN","input","L"),(1,"REF","input","L"),(2,"AVDD","power_in","L"),(10,"DVDD","power_in","L"),(5,"GND","power_in","L"),(6,"CONVST","input","R"),(9,"DIN/CS_N","input","R"),(8,"SCLK","input","R"),(7,"DOUT","tri_state","R")],
    "mux": [(1,"SEL1","input","L"),(5,"SEL2","input","L"),(8,"VDD","power_in","L"),(3,"GND","power_in","L"),(10,"D1","passive","R"),(9,"S1B_RESET","passive","R"),(2,"S1A_OPEN","passive","R"),(6,"D2","passive","R"),(7,"S2B_RESET","passive","R"),(4,"S2A_OPEN","passive","R")],
    "ref": [(4,"IN","power_in","L"),(3,"EN","input","L"),(1,"GND_F","power_in","L"),(2,"GND_S","input","L"),(6,"OUT_F","power_out","R"),(5,"OUT_S","input","R")],
    "cmp": [(3,"1IN+","input","L"),(2,"1IN-","input","L"),(5,"2IN+","input","L"),(6,"2IN-","input","L"),(8,"VCC","power_in","L"),(4,"GND","power_in","L"),(1,"HI_OK","output","R"),(7,"LO_OK","output","R")],
    "and": [(1,"A_HI_OK","input","L"),(3,"B_LO_OK","input","L"),(6,"C_EXT_SUP_OK","input","L"),(5,"VCC","power_in","L"),(2,"GND","power_in","L"),(4,"Y_CLR_N","output","R")],
    "ff": [(1,"CLK_REARM","input","L"),(2,"D","input","L"),(6,"CLR_N","input","L"),(7,"PRE_N","input","L"),(8,"VCC","power_in","L"),(4,"GND","power_in","L"),(5,"Q_PERMIT","output","R"),(3,"Q_N","output","R")],
}
parts=[]
def add(ref,value,kind,nets,xy,sheet,description):
    if kind == "J":
        fp=f"Connector_PinHeader_2.54mm:PinHeader_1x{len(nets):02d}_P2.54mm_Vertical"
        pins=[(i,str(i),"passive","L") for i in sorted(nets)]
    elif kind in "RC" and len(kind)==1:
        fp=FP[kind]; pins=[(1,"1","passive","L"),(2,"2","passive","R")]
    else:
        fp=FP[kind]; pins=PINS[kind]
    assert {str(p[0]) for p in pins} == {str(k) for k in nets}, (ref,nets,pins)
    parts.append(dict(ref=ref,value=value,kind=kind,footprint=fp,nets={str(k):v for k,v in nets.items()},pins=pins,xy=xy,sheet=sheet,description=description,source_url=SOURCES.get(kind,"")))
def r(ref,value,a,b,xy,sheet,description): add(ref,value,"R",{1:a,2:b},xy,sheet,description)
def c(ref,value,a,b,xy,sheet,description): add(ref,value,"C",{1:a,2:b},xy,sheet,description)

# Root: regulated laboratory supplies and all external MCU/supervisor contracts.
add("J1","LAB RAILS ONLY","J",{1:"+5VA",2:"+3V3",3:"GND"},(38.1,45.72),"root","Regulated external power, not a populated battery/converter/charger")
add("J2","MCU ENDPOINT/CONTROL","J",{1:"CH0_CNV",2:"CH0_CS_N",3:"CH0_DOUT",4:"CH1_CNV",5:"CH1_CS_N",6:"CH1_DOUT",7:"MON_SCLK",8:"CH0_INT_RUN",9:"CH1_INT_RUN",10:"CH0_REARM",11:"CH1_REARM",12:"GND"},(360.68,45.72),"root","3.3V MCU interface; external clocks/CS/rearm are unimplemented")
add("J3","EXTERNAL SUPERVISION","J",{1:"CH0_EXT_SUP_OK",2:"CH1_EXT_SUP_OK",3:"CH0_PERMIT",4:"CH1_PERMIT",5:"GND"},(360.68,137.16),"root","EXT_SUP_OK must AND independent compliance, duration, watchdog, rails and reference health; not populated here")
add("J4","CURRENT ADC INTERFACE","J",{1:"CH0_I_MON",2:"CH1_I_MON",3:"V_MID",4:"GND"},(360.68,185.42),"root","Separate current/health ADC and compliance front-end remain external")
add("U1","REF3440DBVR","ref",{1:"GND",2:"GND",3:"+5VA",4:"+5VA",5:"V_REF",6:"V_REF"},(106.68,45.72),"root","4.096V reference; sense tied locally to force in slice")
add("U2","OPA391DCKR","opa",{1:"MID_DIV",2:"GND",3:"V_MID",4:"V_MID",5:"+5VA"},(200.66,45.72),"root","Buffered midpoint from reference; ADC reference remains separately bypassed")
add("U3","TMUX1136DGSR","mux",{1:"CH0_INT_RUN",2:None,3:"GND",4:None,5:"CH1_INT_RUN",6:"CH1_SUM",7:"CH1_Q_INT",8:"+5VA",9:"CH0_Q_INT",10:"CH0_SUM"},(294.64,45.72),"root","Low select closes B feedback reset; high select opens into unconnected A")
r("R1","10k 0.1%","V_REF","MID_DIV",(55.88,119.38),"root","Midpoint divider upper")
r("R2","10k 0.1%","MID_DIV","GND",(121.92,119.38),"root","Midpoint divider lower")
r("R3","10k 0.1%","V_REF","I_HI",(55.88,144.78),"root","Upper guard divider; no hard peak bound implied")
r("R4","19.1k 0.1%","I_HI","I_LO",(121.92,144.78),"root","Guard divider center")
r("R5","10k 0.1%","I_LO","GND",(187.96,144.78),"root","Lower guard divider")
c("C1","1u 10V","+5VA","GND",(55.88,175.26),"root","Reference input local bypass")
c("C2","1u 10V","V_REF","GND",(121.92,175.26),"root","Reference output bypass; ADC pins each have22uF")
c("C3","100n 10V","+5VA","GND",(187.96,175.26),"root","Midpoint buffer supply bypass")
c("C4","100n 10V","+5VA","GND",(254,175.26),"root","Reset mux supply bypass")
r("R6","100k","CH0_INT_RUN","GND",(55.88,208.28),"root","Default reset, not an output safety gate")
r("R7","100k","CH1_INT_RUN","GND",(121.92,208.28),"root","Default reset, not an output safety gate")

for ch in (0,1):
    sheet=f"channel{ch}"; q=lambda s:f"CH{ch}_{s}"; b=100*(ch+1)
    add(f"J{b}",f"SOURCE {ch} RETURN SHUNT","J",{1:q("RETURN_LOAD"),2:q("RETURN_DRIVER")},(45.72,45.72),sheet,"Series dedicated return of an ARTIFICIAL load; no implicit body-ground isolation")
    r(f"R{b}","2R 0.1% KELVIN",q("RETURN_LOAD"),q("RETURN_DRIVER"),(53.34,76.2),sheet,"Separate monitor shunt, not driver-servo resistor; qualify TCR/power and Kelvin layout")
    add(f"U{b}","INA241A2IDR","ina",{1:q("RETURN_DRIVER"),2:"GND",3:"V_MID",4:"GND",5:q("I_MON"),6:"+5VA",7:"V_MID",8:q("RETURN_LOAD")},(111.76,45.72),sheet,"20V/V; A2 max15uV offset; NC pin4 explicitly ground; bias paths unqualified")
    add(f"U{b+1}","OPA391DCKR","opa",{1:"V_MID",2:"GND",3:q("SUM"),4:q("Q_INT"),5:"+5VA"},(200.66,45.72),sheet,"Continuous signed integrator around2.048V")
    r(f"R{b+1}","10k 0.1%",q("I_MON"),q("SUM"),(175.26,78.74),sheet,"Integrator input resistor; continuous current integral")
    c(f"C{b}","22n 0.5% C0G",q("SUM"),q("Q_INT"),(243.84,78.74),sheet,"Precision low-absorption feedback capacitor; tolerance/temperature require evidence")
    add(f"U{b+2}","OPA391DCKR","opa",{1:q("Q_INT"),2:"GND",3:q("ADC_BUF"),4:q("ADC_BUF"),5:"+5VA"},(289.56,45.72),sheet,"Endpoint buffer; capacitive drive/settling must be modeled")
    add(f"U{b+3}","ADS8866IDGSR","adc",{1:"V_REF",2:"+3V3",3:q("ADC_IN"),4:"GND",5:"GND",6:q("CNV"),7:q("DOUT"),8:"MON_SCLK",9:q("CS_N"),10:"+3V3"},(378.46,45.72),sheet,"Separate endpoint SAR; four-wire CS mode; AVDD/DVDD3.3V, reference4.096V")
    r(f"R{b+2}","33R",q("ADC_BUF"),q("ADC_IN"),(312.42,78.74),sheet,"ADC charge-kickback isolation; provisional settling network")
    c(f"C{b+1}","1n C0G",q("ADC_IN"),"GND",(378.46,78.74),sheet,"Provisional ADC local reservoir, not verified settling")
    add(f"U{b+4}","TLV3202IDR","cmp",{1:q("HI_OK"),2:q("I_MON"),3:"I_HI",4:"GND",5:q("I_MON"),6:"I_LO",7:q("LO_OK"),8:"+5VA"},(111.76,137.16),sheet,"Both outputs high only inside nominal current window; shared INA path is a common failure")
    add(f"U{b+5}","SN74LVC1G11DBVR","and",{1:q("HI_OK"),2:"GND",3:q("LO_OK"),4:q("CLEAR_N"),5:"+3V3",6:q("EXT_SUP_OK")},(200.66,137.16),sheet,"5V-tolerant inputs; output3.3V to asynchronous latch clear")
    add(f"U{b+6}","SN74LVC1G74DCUR","ff",{1:q("REARM"),2:"+3V3",3:None,4:"GND",5:q("PERMIT"),6:q("CLEAR_N"),7:"+3V3",8:"+3V3"},(289.56,137.16),sheet,"Q cleared by fault; manual qualifying rearm rising edge; external power-up supervision required")
    add(f"J{b+1}",f"SOURCE {ch} DRIVER PERMISSION","J",{1:q("PERMIT"),2:q("EXT_SUP_OK"),3:"GND"},(378.46,137.16),sheet,"Driver must inhibit independently and remain off with no permit; driver absent")
    r(f"R{b+3}","100k",q("EXT_SUP_OK"),"GND",(53.34,175.26),sheet,"Disconnected external supervisor means no permission")
    r(f"R{b+4}","100k",q("REARM"),"GND",(121.92,175.26),sheet,"Disconnected rearm clock low")
    r(f"R{b+5}","100k",q("PERMIT"),"GND",(190.5,175.26),sheet,"External driver permit default pulldown; not sufficient to certify all power sequences")
    for k,(net,val,xy,desc) in enumerate([
        ("+5VA","100n",(53.34,210.82),"INA supply bypass"),
        ("+5VA","100n",(121.92,210.82),"Integrator supply bypass"),
        ("+5VA","100n",(190.5,210.82),"Endpoint buffer supply bypass"),
        ("+3V3","1u",(259.08,210.82),"ADC analog supply bypass"),
        ("+3V3","1u",(327.66,210.82),"ADC digital supply bypass"),
        ("V_REF","22u",(53.34,238.76),"ADC reference local bypass >=10uF effective"),
        ("+5VA","100n",(121.92,238.76),"Comparator supply bypass"),
        ("+3V3","100n",(190.5,238.76),"AND logic supply bypass"),
        ("+3V3","100n",(259.08,238.76),"Latch supply bypass"),
    ],start=2):
        c(f"C{b+k}",val+" 10V",net,"GND",xy,sheet,desc)

def fnum(x): return f"{x:.4f}".rstrip("0").rstrip(".")
FONT='(effects (font (size 1 1)))'
def pin_positions(p):
    out=[]
    for side in ("L","R"):
        pins=[v for v in p["pins"] if v[3]==side]
        start=(len(pins)-1)*1.27
        for i,(n,name,kind,_) in enumerate(pins):
            out.append((str(n),name,kind,-12.7 if side=="L" else 12.7,start-i*2.54,0 if side=="L" else 180))
    return out
def lib_symbol(p):
    name=p['ref']; pins=pin_positions(p); ymax=max(v[4] for v in pins)+2.54; ymin=min(v[4] for v in pins)-2.54
    graphic=f'(rectangle (start -10.16 {fnum(ymax)}) (end 10.16 {fnum(ymin)}) (stroke (width 0.2) (type default)) (fill (type background)))'
    s=f'(symbol "SCCI_RH_S4:{name}" (pin_names (offset 0.7)) (in_bom yes) (on_board yes) (property "Reference" "{name[0]}" (at 0 0 0) {FONT}) (property "Value" "{p["value"]}" (at 0 0 0) {FONT}) (property "Footprint" "{p["footprint"]}" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "{name}_0_1" {graphic}) (symbol "{name}_1_1" '
    for n,nm,kind,x,y,a in pins:
        s+=f'(pin {kind} line (at {fnum(x)} {fnum(y)} {a}) (length 2.54) (name "{nm}" (effects (font (size 0.85 0.85)))) (number "{n}" {FONT})) '
    return s+'))'
def glabel(net,x,y,key,left=False):
    angle=180 if left else 0
    justify="right" if left else "left"
    return f'(global_label "{net}" (shape bidirectional) (at {fnum(x)} {fnum(y)} {angle}) (effects (font (size 0.85 0.85)) (justify {justify})) (uuid {uid(key)}))'

# Copy native footprints only; CAD models and PCB will be a separate qualified step.
local=OUT/"scci_rh_s4.pretty"; local.mkdir(parents=True,exist_ok=True)
for p in parts:
    lib,name=p['footprint'].split(':')
    src=SHARE/"footprints"/(lib+".pretty")/(name+".kicad_mod")
    if not src.is_file(): raise FileNotFoundError(src)
    shutil.copyfile(src,local/(name+".kicad_mod"))
    p['footprint']='scci_rh_s4:'+name

liblist=[lib_symbol(p) for p in parts]
flag_symbol='(symbol "SCCI_RH_S4:SUPPLIED_RAIL" (pin_names (offset 0)) (in_bom no) (on_board no) (property "Reference" "#FLG" (at 0 0 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_REGULATED_RAIL" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "SUPPLIED_RAIL_0_1" (polyline (pts (xy -1 1) (xy 0 2) (xy 1 1)) (stroke (width 0.2) (type default)) (fill (type none)))) (symbol "SUPPLIED_RAIL_1_1" (pin power_out line (at 0 0 90) (length 0) (name "SUPPLIED" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))'
liblist.append(flag_symbol)
for sheet in ("root","channel0","channel1"):
    sid=ROOT_ID if sheet=="root" else uid(sheet+"-document")
    path='/'+ROOT_ID if sheet=="root" else '/'+ROOT_ID+'/'+uid(sheet+"-sheet")
    elements=[]
    for p in [p for p in parts if p['sheet']==sheet]:
        ref=p['ref']; x,y=p['xy']; pins=pin_positions(p)
        top=y-max(v[4] for v in pins)-5.08; bottom=y-min(v[4] for v in pins)+5.08
        inst=f'(symbol (lib_id "SCCI_RH_S4:{ref}") (at {fnum(x)} {fnum(y)} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {fnum(x)} {fnum(top)} 0) {FONT}) (property "Value" "{p["value"]}" (at {fnum(x)} {fnum(bottom)} 0) (effects (font (size 0.95 0.95)))) (property "Footprint" "{p["footprint"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) (property "Datasheet" "{p["source_url"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) '
        for n,nm,kind,px,py,a in pins:
            xx,yy=x+px,y-py; net=p['nets'][n]
            inst+=f'(pin "{n}" (uuid {uid(ref+"-pin-"+n)})) '
            if net is None:
                elements.append(f'(no_connect (at {fnum(xx)} {fnum(yy)}) (uuid {uid(ref+"-nc-"+n)}))')
            else:
                ex=xx+(-5.08 if px<0 else 5.08)
                elements.append(f'(wire (pts (xy {fnum(xx)} {fnum(yy)}) (xy {fnum(ex)} {fnum(yy)})) (stroke (width 0) (type default)) (uuid {uid(ref+"-wire-"+n)}))')
                # Global names deliberately cross the two child sheets; no hidden hierarchical pin.
                elements.append(glabel(net,ex,yy,ref+"-label-"+n,left=px<0))
        inst+=f'(instances (project "{PROJECT}" (path "{path}" (reference "{ref}") (unit 1)))))'
        elements.append(inst)
    texts=[("ARTIFICIAL ELECTRICAL LOADS ONLY / FIRST MONITORING SLICE",20.32,17.78,1.6),
           ("No current driver, HV router, differential compliance circuit, independent watchdog, MCU or PCB is completed here.",20.32,25.4,1.0)]
    if sheet=="root":
        # These markers declare only J1's explicitly supplied laboratory rails.
        # They do not assert that battery conversion or rail supervision is built.
        for i,net in enumerate(("+5VA","+3V3","GND")):
            x,y=38.1+i*45.72,91.44; ref=f"#FLG0{i+1}"
            elements.append(f'(symbol (lib_id "SCCI_RH_S4:SUPPLIED_RAIL") (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_REGULATED_RAIL" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (pin "1" (uuid {uid(ref+"-pin")})) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (reference "{ref}") (unit 1)))))')
            elements.append(glabel(net,x,y,ref+"-label"))
        for ch in (0,1):
            name=f"channel{ch}"; shid=uid(name+"-sheet"); x=38.1+ch*137.16
            elements.append(f'(sheet (at {fnum(x)} 259.08) (size 121.92 17.78) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {shid}) (property "Sheetname" "Source{ch}_monitor" (at {fnum(x)} 257.08 0) (effects (font (size 1 1)) (justify left bottom))) (property "Sheetfile" "{name}.kicad_sch" (at {fnum(x)} 278.86 0) (effects (font (size 1 1)) (justify left top))) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (page "{ch+2}")))))')
        texts += [("V_REF=4.096V; V_MID=2.048V. Low INT_RUN resets; high opens reset for continuous signed integration.",20.32,218.44,1),
                  ("I_LO=1.04757V / I_HI=3.04843V nominal (~+/-25.01mA). Threshold is NOT a proven complete-waveform cap.",20.32,226.06,1),
                  ("EXT_SUP_OK must stay LOW until external rails/reference/watchdog/compliance/duration checks pass.",20.32,233.68,1),
                  ("Two INA241 channels alone: up to32mW at5V. Input bias25..45uA/input is an unresolved leakage/bypass term.",20.32,241.3,1),
                  ("Named global nets connect sheets; connectors remain explicit external design contracts. Read README before interpretation.",20.32,248.92,1)]
    else:
        texts += [("Q=-10k*22n/40*(V_end-V_start); 600nC=109.091mV nominal. Take BASELINE, CATH, ANODE, NET/TAIL endpoints.",20.32,251.46,1),
                  ("Cathodic and anodic charges remain separate. Opposed phases can cancel: final net alone cannot qualify delivery.",20.32,259.08,1),
                  ("Actual current-tail/window evidence is required. Command edges, the comparator or an ideal16-bit LSB do not certify precision.",20.32,266.7,1),
                  ("CLRN = HI_OK AND LO_OK AND EXT_SUP_OK. Any low latches Q off; rising REARM admits only while CLRN is high.",20.32,274.32,1)]
    for i,(text,x,y,sz) in enumerate(texts):
        elements.append(f'(text "{text}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size {sz} {sz})) (justify left)) (uuid {uid(sheet+"-text-"+str(i))}))')
    title="Shared reference and interfaces" if sheet=="root" else f"Source {sheet[-1]}: current and phase charge"
    # All symbols are embedded, and only this sheet's symbols are embedded in each file.
    embedded=''.join(lib_symbol(p) for p in parts if p['sheet']==sheet)+(flag_symbol if sheet=="root" else "")
    data=f'(kicad_sch (version 20250114) (generator "scci_rh_stage4_monitor") (uuid {sid}) (paper "A3") (title_block (title "Project SCCI RH S4 / {title}") (date "2026-10-12") (rev "0.2 DCK") (company "Project SCCI RH") (comment 1 "ARTIFICIAL LOADS ONLY; native schematic slice, not a completed implant")) (lib_symbols {embedded}) '+''.join(elements)+')\n'
    (OUT/(PROJECT if sheet=="root" else sheet)).with_suffix('.kicad_sch').write_text(data,encoding='utf-8')

(OUT/"SCCI_RH_S4.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "scci_rh_stage4_monitor") '+''.join(liblist).replace('(symbol "SCCI_RH_S4:', '(symbol "')+')\n',encoding='utf-8')
(OUT/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "SCCI_RH_S4") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH_S4.kicad_sym") (options "") (descr "Original explicit pin symbols; checked manufacturer references in manifest")))\n',encoding='utf-8')
(OUT/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "scci_rh_s4") (type "KiCad") (uri "${KIPRJMOD}/scci_rh_s4.pretty") (options "") (descr "KiCad footprint snapshots; no PCB or populated CAD claimed")))\n',encoding='utf-8')
(OUT/(PROJECT+'.kicad_pro')).write_text(json.dumps({"meta":{"filename":PROJECT+'.kicad_pro',"version":1},"erc":{"rule_severities":{"single_global_label":"warning","four_way_junction":"warning","simulation_model_issue":"warning","footprint_filter":"warning"}}},indent=2)+'\n',encoding='utf-8')
manifest={"schema":"scci_rh.stage4.monitoring-cell.connectivity.v1","date":"2026-10-12","scope":"Artificial-load monitoring slice only; no analog qualification","parts":parts,"external_unimplemented":["driver/current servo and polarity bridge","HV16-contact routing and actual route evidence","separate current/health ADC","differential compliance","independent duration/watchdog/rail/reference supervision","MCU and target peripheral schedule","PCB and populated CAD"],"nominal":{"shunt_ohm":2,"sense_gain":20,"integrator_R_ohm":10000,"integrator_C_F":22e-9,"Vref_V":4.096,"Vmid_V":2.048,"current_gain_V_per_A":40,"charge_scale_C_per_V":5.5e-6,"nominal_phase_charge_C":600e-9,"nominal_delta_V":600e-9/5.5e-6,"ideal_adc_charge_LSB_C":4.096/65536*5.5e-6},"source_documents":SOURCES}
(OUT/"connectivity.json").write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
with (OUT/"bom.csv").open('w',encoding='utf-8',newline='') as f:
    w=csv.writer(f);w.writerow(['reference','value','footprint','sheet','description','primary_source'])
    for p in parts:w.writerow([p['ref'],p['value'],p['footprint'],p['sheet'],p['description'],p['source_url']])
print(json.dumps({"parts":len(parts),"sheets":3,"root":str(OUT/(PROJECT+'.kicad_sch')),"claims":"Native connectivity only; circuit evidence pending"}))
