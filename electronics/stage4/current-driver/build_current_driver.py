"""Generate an editable dual-source KiCad driver slice from explicit pin nets.

Native rendering infrastructure follows the project's monitoring-cell generator;
no files in that historical package are modified. No PCB or implant is generated.
"""
from pathlib import Path
import csv
import json
import os
import re
import shutil
import uuid

OUT = Path(__file__).resolve().parent
SHARE = Path(os.environ.get("KICAD_SHARE", r"E:\project workspace assests\EDA\KiCAD\share\kicad"))
PROJECT = "current_driver"
def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "project-scci-rh/stage4/current-driver/" + key))
ROOT_ID = uid("root")
SHEETS = ("root", "source0", "permission0", "source1", "permission1")
TITLES = {"root": "Dual setpoint and external contracts"}
for ch in (0, 1):
    TITLES[f"source{ch}"] = f"Source {ch}: regulated sink and polarity bridge"
    TITLES[f"permission{ch}"] = f"Source {ch}: independent duration and sticky admission"
SOURCES = {
    "dac": "https://www.ti.com/lit/ds/symlink/dac80502.pdf",
    "opa": "https://www.ti.com/lit/ds/symlink/opa192.pdf",
    "sink": "https://www.infineon.com/assets/row/public/documents/24/49/infineon-bsp89-datasheet-en.pdf",
    "bridge": "https://www.ti.com/lit/ds/symlink/tmux7212.pdf",
    "mux": "https://www.ti.com/lit/ds/symlink/tmux6219.pdf",
    "timer": "https://www.analog.com/media/en/technical-documentation/data-sheets/ltc6993-6993-1-6993-2-6993-4.pdf",
    "and3": "https://www.ti.com/lit/ds/symlink/sn74lvc1g11.pdf",
    "and2": "https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf",
    "xor": "https://www.ti.com/lit/ds/symlink/sn74lvc1g86.pdf",
    "or": "https://www.ti.com/lit/ds/symlink/sn74lvc1g32.pdf",
    "inv": "https://www.ti.com/lit/ds/symlink/sn74lvc1g04.pdf",
    "ff": "https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf",
}
FP = {
    "R": "Resistor_SMD:R_0805_2012Metric", "C": "Capacitor_SMD:C_0805_2012Metric",
    "dac": "Package_SON:Texas_DRX_WSON-10_2.5x2.5mm_P0.5mm",
    "opa": "Package_TO_SOT_SMD:SOT-23-5", "sink": "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
    "bridge": "Package_SO:TSSOP-16_4.4x5mm_P0.65mm", "mux": "Package_SO:VSSOP-8_2.3x2mm_P0.5mm",
    "timer": "Package_TO_SOT_SMD:TSOT-23-6", "ff": "Package_SO:VSSOP-8_2.3x2mm_P0.5mm",
    "and3": "Package_TO_SOT_SMD:SOT-23-6",
}
for k in ("and2", "xor", "or", "inv"):
    FP[k] = "Package_TO_SOT_SMD:SOT-23-5"
# number, name, electrical type, side. These are package-specific contracts.
PINS = {
    "dac": [(1,"VDD","power_in","L"),(3,"RSTSEL","input","L"),(4,"AGND","power_in","L"),(5,"SPI2C","input","L"),(6,"SCLK","input","L"),(7,"SYNC_N","input","L"),(8,"SDIN","input","L"),(2,"VOUTA","output","R"),(9,"VOUTB","output","R"),(10,"VREFIO","passive","R")],
    "opa": [(3,"IN+","input","L"),(4,"IN-","input","L"),(5,"V+","power_in","L"),(2,"V-","power_in","L"),(1,"OUT","output","R")],
    "sink": [(1,"GATE","passive","L"),(2,"DRAIN","passive","R"),(4,"DRAIN_TAB","passive","R"),(3,"SOURCE","passive","R")],
    "bridge": [(1,"SEL1","input","L"),(16,"SEL2","input","L"),(9,"SEL3","input","L"),(8,"SEL4","input","L"),(13,"VDD","power_in","L"),(4,"VSS","power_in","L"),(5,"GND","power_in","L"),(2,"D1_A","passive","R"),(3,"S1_HV","passive","R"),(15,"D2_B","passive","R"),(14,"S2_HV","passive","R"),(10,"D3_A","passive","R"),(11,"S3_SINK","passive","R"),(7,"D4_B","passive","R"),(6,"S4_SINK","passive","R"),(12,"NC","no_connect","R")],
    "mux": [(5,"EN","input","L"),(6,"SEL_RUN","input","L"),(4,"VDD","power_in","L"),(7,"VSS","power_in","L"),(3,"GND","power_in","L"),(1,"D","passive","R"),(2,"S1_OFF","passive","R"),(8,"S2_RUN","passive","R")],
    "timer": [(1,"TRIG_RAW_REQ","input","L"),(3,"SET","passive","L"),(4,"DIV","input","L"),(5,"V+","power_in","L"),(2,"GND","power_in","L"),(6,"OUT","output","R")],
    "and3": [(1,"A","input","L"),(3,"B","input","L"),(6,"C","input","L"),(5,"VCC","power_in","L"),(2,"GND","power_in","L"),(4,"Y","output","R")],
    "ff": [(1,"CLK","input","L"),(2,"D","input","L"),(6,"CLR_N","input","L"),(7,"PRE_N","input","L"),(8,"VCC","power_in","L"),(4,"GND","power_in","L"),(5,"Q","output","R"),(3,"Q_N","output","R")],
    "inv": [(2,"A","input","L"),(5,"VCC","power_in","L"),(3,"GND","power_in","L"),(1,"NC","no_connect","L"),(4,"Y","output","R")],
}
for k in ("and2", "xor", "or"):
    PINS[k] = [(1,"A","input","L"),(2,"B","input","L"),(5,"VCC","power_in","L"),(3,"GND","power_in","L"),(4,"Y","output","R")]
parts = []
def add(ref, value, kind, nets, xy, sheet, description, dnp=False):
    if kind == "J":
        fp = f"Connector_PinHeader_2.54mm:PinHeader_1x{len(nets):02d}_P2.54mm_Vertical"
        pins = [(i,str(i),"passive","L") for i in sorted(nets)]
    elif kind in ("R", "C"):
        fp = FP[kind]; pins = [(1,"1","passive","L"),(2,"2","passive","R")]
    else:
        fp = FP[kind]; pins = PINS[kind]
    assert {str(p[0]) for p in pins} == {str(k) for k in nets}, (ref, nets)
    parts.append(dict(ref=ref,value=value,kind=kind,footprint=fp,nets={str(k):v for k,v in nets.items()},pins=pins,xy=xy,sheet=sheet,description=description,source_url=SOURCES.get(kind,""),dnp=dnp))
def r(ref,val,a,b,xy,sheet,desc): add(ref,val,"R",{1:a,2:b},xy,sheet,desc)
def c(ref,val,a,b,xy,sheet,desc,dnp=False): add(ref,val,"C",{1:a,2:b},xy,sheet,desc,dnp)

add("J1","QUALIFIED EXTERNAL RAILS","J",{1:"VH_24",2:"VA_15",3:"VDD_5",4:"VDD_3V3",5:"GND"},(50.8,55.88),"root","External regulated rails; no converters, battery, power-on supervisor or isolation")
add("J2","MCU SPI / PRELOAD INHIBITED","J",{1:"DAC_SCLK",2:"DAC_SYNC_N",3:"DAC_SDIN",4:"GND"},(50.8,129.54),"root","3.3V host SPI; configuration write and independent setpoint verification required before RESET_READY")
add("J3","MCU PHASE / EXPLICIT REARM","J",{1:"CH0_REQUEST",2:"CH0_PLUS_RAW",3:"CH0_MINUS_RAW",4:"CH0_REARM",5:"CH1_REQUEST",6:"CH1_PLUS_RAW",7:"CH1_MINUS_RAW",8:"CH1_REARM",9:"GND"},(355.6,60.96),"root","Separate controls; REARM pulse only after external observed quiescence, no automatic retry")
add("J4","EXTERNAL HEALTH CONTRACTS","J",{1:"RESET_READY",2:"RAILS_QUALIFIED",3:"CH0_MON_PERMIT",4:"CH0_EXT_SUP_OK",5:"CH0_ROUTE_LOCKED",6:"CH0_QUIESCENT_OK",7:"CH1_MON_PERMIT",8:"CH1_EXT_SUP_OK",9:"CH1_ROUTE_LOCKED",10:"CH1_QUIESCENT_OK",11:"GND"},(355.6,157.48),"root","Independent monitor, watchdog/compliance, power-startup, route and zero-current evidence are external; keep low until qualified")
add("J5","STATUS ONLY / NOT DELIVERY EVIDENCE","J",{1:"CH0_RUN",2:"CH0_BLOCK",3:"CH0_TIMEOUT",4:"CH0_TIMER",5:"CH1_RUN",6:"CH1_BLOCK",7:"CH1_TIMEOUT",8:"CH1_TIMER",9:"GND"},(254,162.56),"root","Internal command status does not certify actual current, dose or successful stimulation")
add("U1","DAC80502DRXR","dac",{1:"VDD_5",2:"CH0_VSET",3:"GND",4:"GND",5:"GND",6:"DAC_SCLK",7:"DAC_SYNC_N",8:"DAC_SDIN",9:"CH1_VSET",10:"DAC_VREF"},(160.02,60.96),"root","DRX10 has ten lands and no invented exposed-pad pin; internal reference; gain register0x0103")
for i,(net,val) in enumerate((("VDD_5","100n 10V"),("VDD_5","4.7u 10V"),("DAC_VREF","220n 10V")),1):
    c(f"C{i}",val,net,"GND",(76.2+i*60.96,111.76),"root","DAC local supply/reference bypass; effective reference capacitance >=150nF")
r("R1","10k","DAC_SCLK","GND",(111.76,149.86),"root","SPI clock default low")
r("R2","10k","DAC_SDIN","GND",(172.72,149.86),"root","SPI data default low")
r("R3","10k","DAC_SYNC_N","VDD_3V3",(111.76,180.34),"root","SPI inactive pull-up to host3.3V domain; no5V backdrive to MCU")
r("R4","10k","RESET_READY","GND",(172.72,180.34),"root","Startup must remain inhibited until externally qualified")
r("R5","10k","RAILS_QUALIFIED","GND",(50.8,180.34),"root","Disconnected rail supervisor cannot admit output")

LOGIC_VALUES = {"xor":"SN74LVC1G86DBVR","inv":"SN74LVC1G04DBVR","or":"SN74LVC1G32DBVR","and2":"SN74LVC1G08DBVR","and3":"SN74LVC1G11DBVR","ff":"SN74LVC1G74DCUR"}
for ch in (0,1):
    q=lambda s: f"CH{ch}_{s}"
    s=f"source{ch}"; b=100*(ch+1)
    add(f"U{b}","OPA192IDBVR","opa",{1:q("SERVO"),2:"GND",3:q("VSET"),4:q("FB"),5:"VA_15"},(101.6,60.96),s,"Current servo; compensation and startup/overload performance remain conditional")
    add(f"Q{b}","BSP89H6327XTSA1","sink",{1:q("GATE"),2:q("SINK_D"),3:q("SENSE_K"),4:q("SINK_D")},(205.74,60.96),s,"Linear sink; numbered drain tab4 and drain lead2 deliberately share drain net")
    add(f"U{b+1}","TMUX7212PWR","bridge",{1:q("DIAG_P"),2:q("A_BR"),3:"VH_24",4:"GND",5:"GND",6:q("SINK_D"),7:q("B_BR"),8:q("DIAG_P"),9:q("DIAG_M"),10:q("A_BR"),11:q("SINK_D"),12:None,13:"VH_24",14:"VH_24",15:q("B_BR"),16:q("DIAG_M")},(312.42,63.5),s,"Restricted24Vbridge: diagonal1/4positive,2/3negative; alloff is not fail-open rail isolation")
    add(f"U{b+2}","TMUX6219DGKR","mux",{1:q("GATE_SW"),2:"GND",3:"GND",4:"VA_15",5:"VA_15",6:q("RUN"),7:"GND",8:q("SERVO")},(101.6,132.08),s,"ENhigh15V; RUNlow selectsS1ground, RUNhigh selectsS2servo; passive gate pulldown remains")
    add(f"U{b+3}","TMUX6219DGKR","mux",{1:q("FB"),2:q("SERVO"),3:"GND",4:"VA_15",5:"VA_15",6:q("RUN"),7:"GND",8:q("SENSE_K")},(205.74,132.08),s,"RUNlow selects unity local feedback, RUNhigh Kelvin feedback; skew/stuck-path study required")
    add(f"J{b}","EXTERNAL ROUTER / MONITOR","J",{1:q("A_BR"),2:q("B_BR"),3:q("SENSE_K"),4:"GND"},(355.6,144.78),s,"Artificial loadA via future router; B_BR connects existingmonitorRETURN_DRIVER; external2ohmmonitor shunt thenloadB")
    r(f"R{b}","100R 0.1% LOW TCR",q("SENSE_K"),"GND",(66.04,195.58),s,"Feedback resistor; exact passiveMPN/thermalrating unselected; Kelvin sense/layout required")
    r(f"R{b+1}","330R",q("GATE_SW"),q("GATE"),(157.48,195.58),s,"Provisional gate resistor; mux clamp-current and repeated pulse stress unqualified")
    r(f"R{b+2}","100k",q("GATE"),"GND",(248.92,195.58),s,"Passive gate default on loss of auxrail; not terminal isolation")
    c(f"C{b}","DNP 10p C0G",q("SERVO"),q("FB"),(340.36,195.58),s,"Reserved compensation footprint, not populated/stablebandwidth claim",True)
    for k,(net,val,desc) in enumerate((("VA_15","100n 25V","Servo bypass"),("VA_15","100n 25V","Gate mux bypass"),("VA_15","100n 25V","Feedback mux bypass"),("VH_24","100n 50V","Bridge bypass"),("VH_24","1u 50V","Bridge local reservoir; effective capacitance/rail transient requiresreview")),1):
        c(f"C{b+k}",val,net,"GND",(45.72+(k-1)*76.2,233.68),s,desc)
    r(f"R{b+3}","22k",q("DIAG_P"),"GND",(55.88,264.16),s,"BothpositiveSELinputs pulldown on sharedsame-net diagonal")
    r(f"R{b+4}","22k",q("DIAG_M"),"GND",(152.4,264.16),s,"BothnegativeSELinputs pulldown on sharedsame-net diagonal")
    r(f"R{b+5}","22k",q("RUN"),"GND",(248.92,264.16),s,"Mux selectors defaultinhibited iflogicunpowered; startupsequence still external")

    s=f"permission{ch}"; b=300+100*ch
    cell=0
    def logic(kind,nets,desc):
        global cell
        xy=(55.88+(cell%6)*91.44,55.88+(cell//6)*55.88)
        ref=f"U{b+cell}"
        add(ref, "LTC6993HS6-1#TRPBF" if kind=="timer" else LOGIC_VALUES[kind],kind,nets,xy,s,desc)
        cell+=1
        return ref
    def g2(kind,a,bn,out,desc): return logic(kind,{1:a,2:bn,3:"GND",4:out,5:"VDD_3V3"},desc)
    def g3(a,bn,cn,out,desc): return logic("and3",{1:a,2:"GND",3:bn,4:out,5:"VDD_3V3",6:cn},desc)
    def inv(a,out,desc): return logic("inv",{1:None,2:a,3:"GND",4:out,5:"VDD_3V3"},desc)
    def ff(clk,d,clrn,pren,qn,qbn,desc): return logic("ff",{1:clk,2:d,3:qbn,4:"GND",5:qn,6:clrn,7:pren,8:"VDD_3V3"},desc)
    logic("timer",{1:q("REQUEST"),2:"GND",3:q("T_SET"),4:q("T_DIV"),5:"VDD_3V3",6:q("TIMER")},"Raw request edge; non-retriggerable -1; timer clocks never gated by readiness")
    g2("xor",q("PLUS_RAW"),q("MINUS_RAW"),q("VALID_DIR"),"Exactly one raw direction; invalid state immediately dropsBASE_GOOD")
    g3(q("MON_PERMIT"),q("EXT_SUP_OK"),q("ROUTE_LOCKED"),q("HEALTH_A"),"External current guard, independent supervision and route ownership")
    g3("RESET_READY","RAILS_QUALIFIED",q("VALID_DIR"),q("HEALTH_B"),"Qualified startup/rails and direction; these externalports are not populatedsupervisors")
    g2("and2",q("HEALTH_A"),q("HEALTH_B"),q("BASE_GOOD"),"BASE_GOOD excludesstickyBLOCK/TIMEOUT soexplicitrearmcan clear them")
    inv(q("REQUEST"),q("REQ_N"),"Normal request end contributes to consumed-admission latch")
    inv(q("TIMER"),q("TIMER_N"),"Risinginvertedtimerclocks stickytimeout atwindowend")
    g2("and2",q("TIMER"),q("REQ_N"),q("STOP_CONSUME"),"Request ending duringtimer consumesadmission; notclassifiedas timeout")
    inv(q("STOP_CONSUME"),q("STOP_N"),"Active-low consumedadmissioncondition")
    g2("and2",q("BASE_GOOD"),q("STOP_N"),q("BLOCK_PRE_N"),"Asyncblockset onfault ornormalend; recovery cannot clearblock")
    g3(q("REARM"),q("BASE_GOOD"),q("QUIESCENT_OK"),q("REARM_A"),"Externallydeliberaterearm mustbe stableandnonoverlap; monitorrearm independent")
    g3(q("REARM_A"),q("REQ_N"),q("TIMER_N"),q("SAFE_REARM"),"Rearm onlyrequestLOW,timerLOW,observedquiescent andallhealthgood")
    inv(q("SAFE_REARM"),q("LATCH_CLR_N"),"Onlyqualifiedexplicitrearm clearsdriverblock/timeout")
    ff("GND","GND",q("LATCH_CLR_N"),q("BLOCK_PRE_N"),q("BLOCK"),q("BLOCK_N"),"AsyncPRE setsstickyadmissionblock; asyncCLRqualifiedrearm; no simultaneousactivecontrolsadmitted")
    g2("or",q("TIMEOUT"),q("REQUEST"),q("TIMEOUT_D"),"StickyOR avoids a later normalphase clearingrecordedtimeout")
    ff(q("TIMER_N"),q("TIMEOUT_D"),q("LATCH_CLR_N"),"VDD_3V3",q("TIMEOUT"),q("TIMEOUT_N"),"At timerfall latchfaultifrequestheld; directtimergate inhibitsregardlessofsetup/holdclassification")
    ff(q("SAFE_REARM"),q("PLUS_RAW"),"RESET_READY","VDD_3V3",q("PLUS_LATCHED"),q("MINUS_LATCHED"),"Qualifiedrearmcapturesdirectionwhileoff; externalrearmmustreleaseandsettlebeforefreshrequest")
    g3(q("BASE_GOOD"),q("BLOCK_N"),q("TIMEOUT_N"),q("GOOD"),"Permission includesboth stickyblockandstickytimeout")
    g3(q("REQUEST"),q("TIMER"),q("GOOD"),q("RUN"),"TimerdirectlycutsRUN; nofirmwarecanextendactivewindow")
    g2("and2",q("RUN"),q("PLUS_LATCHED"),q("DIAG_P"),"Capturedpositivephase drives bridgeSEL1/SEL4")
    g2("and2",q("RUN"),q("MINUS_LATCHED"),q("DIAG_M"),"Capturednegativephase drives bridgeSEL2/SEL3")
    # Local bypass for EVERY one of the 21 logic/timer ICs.
    passive=[]
    for k in range(cell):
        passive.append(("C",f"C{b+k}","100n 10V","VDD_3V3","GND",f"Local bypass for U{b+k}"))
    passive += [("R",f"R{b}","175.8k 0.1%",q("T_SET"),"GND","FixedtimerRSET; temperaturedriftandstartuptimequalificationexternal"),("R",f"R{b+1}","976k 0.1%","VDD_3V3",q("T_DIV"),"DIVcode2 topresistor"),("R",f"R{b+2}","182k 0.1%",q("T_DIV"),"GND","DIVcode2 bottomresistor")]
    for k,net in enumerate(("REQUEST","PLUS_RAW","MINUS_RAW","REARM","MON_PERMIT","EXT_SUP_OK","ROUTE_LOCKED","QUIESCENT_OK"),3):
        passive.append(("R",f"R{b+k}","10k",q(net),"GND","Disconnectedexternalinput defaultsLOW; notpowersequencingproof"))
    for k,(kind,ref,val,a,bn,desc) in enumerate(passive):
        (r if kind=="R" else c)(ref,val,a,bn,(43.18+(k%7)*81.28,279.4+(k//7)*25.4),s,desc)

def fnum(x): return f"{x:.4f}".rstrip("0").rstrip(".")
FONT='(effects (font (size 1 1)))'
def pin_positions(p):
    out=[]
    for side in ("L","R"):
        ps=[v for v in p["pins"] if v[3]==side]
        start=(len(ps)-1)*1.27
        for i,(n,name,kind,_) in enumerate(ps):
            out.append((str(n),name,kind,-12.7 if side=="L" else 12.7,start-i*2.54,0 if side=="L" else 180))
    return out
def lib_symbol(p):
    name=p["ref"]; pins=pin_positions(p)
    ymax=max(v[4] for v in pins)+2.54; ymin=min(v[4] for v in pins)-2.54
    graphic=f'(rectangle (start -10.16 {fnum(ymax)}) (end 10.16 {fnum(ymin)}) (stroke (width 0.2) (type default)) (fill (type background)))'
    if p["kind"] in ("R", "C"):
        wire = lambda x1,x2: f'(polyline (pts (xy {x1} 0) (xy {x2} 0)) (stroke (width 0.2) (type default)) (fill (type none)))'
        if p["kind"] == "R":
            graphic='(rectangle (start -5.08 1.27) (end 5.08 -1.27) (stroke (width 0.2) (type default)) (fill (type none)))'+wire(-10.16,-5.08)+wire(5.08,10.16)
        else:
            plate = lambda x: f'(polyline (pts (xy {x} -2.54) (xy {x} 2.54)) (stroke (width 0.3) (type default)) (fill (type none)))'
            graphic=plate(-1.27)+plate(1.27)+wire(-10.16,-1.27)+wire(1.27,10.16)
    st=f'(symbol "SCCI_RH_DRV:{name}" (pin_names (offset 0.7)) (in_bom yes) (on_board yes) (property "Reference" "{name[0]}" (at 0 0 0) {FONT}) (property "Value" "{p["value"]}" (at 0 0 0) {FONT}) (property "Footprint" "{p["footprint"]}" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "{name}_0_1" {graphic}) (symbol "{name}_1_1" '
    for n,nm,kind,x,y,a in pins:
        st+=f'(pin {kind} line (at {fnum(x)} {fnum(y)} {a}) (length 2.54) (name "{nm}" (effects (font (size 0.85 0.85)))) (number "{n}" {FONT})) '
    return st+'))'
def glabel(net,x,y,key,left=False):
    return f'(global_label "{net}" (shape bidirectional) (at {fnum(x)} {fnum(y)} {180 if left else 0}) (effects (font (size 0.85 0.85)) (justify {"right" if left else "left"})) (uuid {uid(key)}))'

local=OUT/"scci_rh_drv.pretty"; local.mkdir(exist_ok=True)
for p in parts:
    lib,name=p["footprint"].split(":")
    src=SHARE/"footprints"/(lib+".pretty")/(name+".kicad_mod")
    assert src.is_file(),src
    text=src.read_text(encoding="utf-8")
    if p["kind"]=="sink":
        # KiCad's generic SOT223 footprint labels the large tab2; Infineon
        # calls it4. Retain geometry and assign the explicit fourth pin.
        assert text.count('(pad "2"')==2
        pos=text.rfind('(pad "2"')
        text=text[:pos]+text[pos:].replace('(pad "2"','(pad "4"',1)
        name="BSP89_PG-SOT223-4_DrainTab"
        text=text.replace('SOT-223-3_TabPin2',name)
    (local/(name+".kicad_mod")).write_text(text,encoding="utf-8")
    p["footprint"]="scci_rh_drv:"+name

flag_symbol='(symbol "SCCI_RH_DRV:SUPPLIED_RAIL" (pin_names (offset 0)) (in_bom no) (on_board no) (property "Reference" "#FLG" (at 0 0 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_QUALIFIED_RAIL" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "SUPPLIED_RAIL_0_1" (polyline (pts (xy -1 1) (xy 0 2) (xy 1 1)) (stroke (width 0.2) (type default)) (fill (type none)))) (symbol "SUPPLIED_RAIL_1_1" (pin power_out line (at 0 0 90) (length 0) (name "SUPPLIED" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))'
for sheet in SHEETS:
    permission=sheet.startswith("permission")
    sid=ROOT_ID if sheet=="root" else uid(sheet+"-document")
    path="/"+ROOT_ID if sheet=="root" else "/"+ROOT_ID+"/"+uid(sheet+"-sheet")
    elements=[]
    for p in [p for p in parts if p["sheet"]==sheet]:
        ref=p["ref"]; x,y=p["xy"]; pins=pin_positions(p)
        top=y-max(v[4] for v in pins)-5.08; bottom=y-min(v[4] for v in pins)+5.08
        inst=f'(symbol (lib_id "SCCI_RH_DRV:{ref}") (at {fnum(x)} {fnum(y)} 0) (unit 1) (in_bom yes) (on_board yes) (dnp {"yes" if p["dnp"] else "no"}) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {fnum(x)} {fnum(top)} 0) {FONT}) (property "Value" "{p["value"]}" (at {fnum(x)} {fnum(bottom)} 0) (effects (font (size 0.95 0.95)))) (property "Footprint" "{p["footprint"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) (property "Datasheet" "{p["source_url"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) '
        for n,nm,kind,px,py,a in pins:
            xx,yy=x+px,y-py; net=p["nets"][n]
            inst+=f'(pin "{n}" (uuid {uid(ref+"-pin-"+n)})) '
            if net is None:
                elements.append(f'(no_connect (at {fnum(xx)} {fnum(yy)}) (uuid {uid(ref+"-nc-"+n)}))')
            else:
                ex=xx+(-5.08 if px<0 else 5.08)
                elements.append(f'(wire (pts (xy {fnum(xx)} {fnum(yy)}) (xy {fnum(ex)} {fnum(yy)})) (stroke (width 0) (type default)) (uuid {uid(ref+"-wire-"+n)}))')
                elements.append(glabel(net,ex,yy,ref+"-label-"+n,left=px<0))
        inst+=f'(instances (project "{PROJECT}" (path "{path}" (reference "{ref}") (unit 1)))))'
        elements.append(inst)
    texts=[("ARTIFICIAL LOADS ONLY / RESTRICTED 24 V, 3 mA, 200 us DRIVER SLICE",20.32,17.78,1.6),
           ("External rails, recording AFE, 16-contact routing, compliance, charge guard, watchdog, PCB and implant qualification remain outside.",20.32,25.4,1.0)]
    if sheet=="root":
        for i,net in enumerate(("VH_24","VA_15","VDD_5","VDD_3V3","GND")):
            x,y=35.56+i*66.04,226.06; ref=f"#FLG{i+1}"
            elements.append(f'(symbol (lib_id "SCCI_RH_DRV:SUPPLIED_RAIL") (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_QUALIFIED_RAIL" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (pin "1" (uuid {uid(ref+"-pin")})) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (reference "{ref}") (unit 1)))))')
            elements.append(glabel(net,x,y,ref+"-label"))
        for i,name in enumerate(SHEETS[1:]):
            x=20.32+i*96.52; y=85.09
            shname=f"Source{name[-1]}_"+("permission" if name.startswith("permission") else "analog")
            elements.append(f'(sheet (at {fnum(x)} {fnum(y)}) (size 86.36 10.16) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {uid(name+"-sheet")}) (property "Sheetname" "{shname}" (at {fnum(x)} {fnum(y-2)} 0) (effects (font (size 1 1)) (justify left bottom))) (property "Sheetfile" "{name}.kicad_sch" (at {fnum(x)} {fnum(y+12.16)} 0) (effects (font (size 1 1)) (justify left top))) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (page "{i+2}")))))')
        texts += [("DAC initialization before READY: GAIN[0x04]=0x0103, reference divider 2 and both output buffer gains 2 => nominal 2.5 V FSR.",20.32,196.85,1),
                  ("Code 7864 -> 2.999878 mA nominal through 100 ohm. Zero code is not terminal disconnection. Read README and external contracts.",20.32,204.47,1),
                  ("RESET_READY held LOW through startup; REARM is an explicit pulse with REQUEST/TIMER LOW and independently observed quiescence.",20.32,212.09,1)]
    elif permission:
        texts += [("BASE_GOOD=MON & EXT & ROUTE & READY & RAILS & XOR(raw directions). Raw REQUEST clocks TIMER; SAFE_REARM preloads direction while off.",20.32,391.16,1),
                  ("Normal request end consumes BLOCK; TIMEOUT records held request at timer fall. REARM requires request/timer LOW + QUIESCENT_OK.",20.32,398.78,1),
                  ("Static/event checks do not qualify asynchronous hazards, supply ramps, propagation delay or real current tails. No automatic retry.",20.32,406.4,1)]
    else:
        texts += [("Current path: VH -> upper switch -> artificial pair load + external 2 ohm monitor -> lower switch -> BSP89 -> 100 ohm -> GND.",20.32,98.425,1),
                  ("RUN low grounds gate and closes local unity feedback. RUN high selects current loop. DNP compensation needs a transient study.",20.32,172.72,1),
                  ("Bridge uses captured direction; all four commanded off during inhibit. Analog rail clamps, input bias and stuck switches remain real paths.",20.32,281.94,1)]
    for i,(txt,x,y,sz) in enumerate(texts):
        elements.append(f'(text "{txt}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size {sz} {sz})) (justify left)) (uuid {uid(sheet+"-text-"+str(i))}))')
    embedded="".join(lib_symbol(p) for p in parts if p["sheet"]==sheet)+(flag_symbol if sheet=="root" else "")
    data=f'(kicad_sch (version 20250114) (generator "scci_rh_stage4_driver") (uuid {sid}) (paper "{"A2" if permission else "A3"}") (title_block (title "Project SCCI RH S4 / {TITLES[sheet]}") (date "2026-10-13") (rev "0.1") (company "Project SCCI RH") (comment 1 "Native circuit slice; artificial loads only; no PCB or implant qualification")) (lib_symbols {embedded}) '+"".join(elements)+')\n'
    (OUT/(PROJECT if sheet=="root" else sheet)).with_suffix(".kicad_sch").write_text(data,encoding="utf-8")
(OUT/"SCCI_RH_DRV.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "scci_rh_stage4_driver") '+("".join(lib_symbol(p) for p in parts)+flag_symbol).replace('(symbol "SCCI_RH_DRV:', '(symbol "')+')\n',encoding="utf-8")
(OUT/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "SCCI_RH_DRV") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH_DRV.kicad_sym") (options "") (descr "Original package-specific pin symbols; primary sources in connectivity.json")))\n',encoding="utf-8")
(OUT/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "scci_rh_drv") (type "KiCad") (uri "${KIPRJMOD}/scci_rh_drv.pretty") (options "") (descr "KiCad library snapshots; BSP89 tab explicitly renumbered4; landpattern assemblyreview pending")))\n',encoding="utf-8")
(OUT/(PROJECT+".kicad_pro")).write_text(json.dumps({"meta":{"filename":PROJECT+".kicad_pro","version":1},"erc":{"rule_severities":{"single_global_label":"warning","four_way_junction":"warning","simulation_model_issue":"warning","footprint_filter":"warning"}}},indent=2)+"\n",encoding="utf-8")
manifest={"schema":"scci_rh.stage4.current-driver.connectivity.v1","date":"2026-10-13","scope":"Native artificial-load24V3mA200us two-source driver/control slice; not PCB/analog qualification/implant","parts":parts,"source_documents":SOURCES,"external_unimplemented":["qualified24V15V5V3.3V rails and powersequencing","independent monitored current/charge observation","16-contact router and dedicatedreturnmonitor2ohmshunts","terminal disconnect and biasreturn containment","differential compliance and independent chargeguard","watchdog, rail/reference health and startup supervision","observed zero-current quiescence and external routeownership","MCUfirmware/duty/profilecounter","spinal recording AFE","PCB/populatedCAD/chronicimplantqualification"],"nominal":{"rail_V":24,"servo_rail_V":15,"feedback_R_ohm":100,"DAC_FSR_V":2.5,"DAC_GAIN_register":259,"DAC_code":7864,"DAC_current_A":7864*2.5/65536/100,"command_phase_s":200e-6,"command_charge_C":7864*2.5/65536/100*200e-6,"timer_NDIV":64,"timer_RSET_ohm":175800,"timer_DIVCODE":2,"timer_nominal_s":64*175800/50000*1e-6,"timer_min_s":64*175800/50000*1e-6*(1-.044)*(1-.001),"timer_max_s":64*175800/50000*1e-6*(1+.044)*(1+.001)},"control_contract":{"timer_trigger":"rawREQUEST risingedge; never gatedbyreadiness","base_good":"MON_PERMIT&EXT_SUP_OK&ROUTE_LOCKED&RESET_READY&RAILS_QUALIFIED&(PLUS_RAW xor MINUS_RAW)","safe_rearm":"REARM&BASE_GOOD&QUIESCENT_OK&!REQUEST&!TIMER","block_async_pre_n":"BASE_GOOD&!(TIMER&!REQUEST)","block_async_clear_n":"!SAFE_REARM","timeout_D":"TIMEOUT|REQUEST","timeout_clock":"!TIMER risingedge","timeout_async_clear_n":"!SAFE_REARM","direction_D":"PLUS_RAW","direction_clock":"SAFE_REARM risingedge whileREQUEST=TIMER=0; releaseandsettlebeforefreshrequest","run":"REQUEST&TIMER&BASE_GOOD&!BLOCK&!TIMEOUT","positive":"RUN&PLUS_LATCHED","negative":"RUN&MINUS_LATCHED","startup":"RESET_READY heldLOW untilvalidsuppliesandtimerready; thenexplicitquiescentrearm; nohardwareguaranteeoutsidelogicsupplyvalidrange","rearm_input":"explicitstablepulse returnedLOW beforephaseedge; externalnonoverlapandsetupholdrequired; doesnotrearmmonitor"}}
(OUT/"connectivity.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
with (OUT/"bom.csv").open("w",encoding="utf-8",newline="") as f:
    w=csv.writer(f);w.writerow(["reference","value","footprint","sheet","dnp","description","primary_source"])
    for p in parts:w.writerow([p["ref"],p["value"],p["footprint"],p["sheet"],p["dnp"],p["description"],p["source_url"]])
print(json.dumps({"parts":len(parts),"sheets":len(SHEETS),"root":str(OUT/(PROJECT+".kicad_sch"))}))
