"""Generate the native two-source, sixteen-contact route command slice.

Editable pin-exact schematics and local footprint snapshots, not a PCB or
implant qualification. The generator uses no hidden global ERC exclusions.
"""
from pathlib import Path
import csv
import json
import os
import re
import uuid

OUT = Path(__file__).resolve().parent
SHARE = Path(os.environ.get("KICAD_SHARE", r"E:\project workspace assests\EDA\KiCAD\share\kicad"))
PROJECT = "contact_router"
def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "project-scci-rh/stage4/contact-router/" + key))
ROOT_ID = uid("root")
SHEETS = ("root", "source0", "source1", "address", "admission", "collision")
TITLES = {
    "root": "Route interfaces and monitored returns",
    "source0": "Source 0 / sixteen-contact output",
    "source1": "Source 1 / sixteen-contact output",
    "address": "Candidate preload and active addresses",
    "admission": "Commit, acknowledgement and rearm",
    "collision": "Conflict and bank enables",
}
SOURCES = {
    "mux": "https://www.ti.com/lit/ds/symlink/tmux6208.pdf",
    "shift": "https://www.ti.com/lit/ds/symlink/sn74lvc595a.pdf",
    "dmux": "https://www.ti.com/lit/ds/symlink/sn74lvc157a.pdf",
    "ff": "https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf",
    "and2": "https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf",
    "and3": "https://www.ti.com/lit/ds/symlink/sn74lvc1g11.pdf",
    "or": "https://www.ti.com/lit/ds/symlink/sn74lvc1g32.pdf",
    "xor": "https://www.ti.com/lit/ds/symlink/sn74lvc1g86.pdf",
    "inv": "https://www.ti.com/lit/ds/symlink/sn74lvc1g04.pdf",
}
FP = {
    "R": "Resistor_SMD:R_0805_2012Metric",
    "C": "Capacitor_SMD:C_0805_2012Metric",
    "mux": "Package_SO:TSSOP-16_4.4x5mm_P0.65mm",
    "shift": "Package_SO:TSSOP-16_4.4x5mm_P0.65mm",
    "dmux": "Package_SO:TSSOP-16_4.4x5mm_P0.65mm",
    "ff": "Package_SO:VSSOP-8_2.3x2mm_P0.5mm",
    "and3": "Package_TO_SOT_SMD:SOT-23-6",
}
for kind in ("and2", "or", "xor", "inv"):
    FP[kind] = "Package_TO_SOT_SMD:SOT-23-5"
PINS = {
    "mux": [(1,"A0","input","L"),(16,"A1","input","L"),(15,"A2","input","L"),(2,"EN_HIGH","input","L"),(13,"VDD","power_in","L"),(3,"VSS","power_in","L"),(14,"GND","power_in","L"),(8,"D_COMMON","passive","R"),(4,"S1","passive","R"),(5,"S2","passive","R"),(6,"S3","passive","R"),(7,"S4","passive","R"),(12,"S5","passive","R"),(11,"S6","passive","R"),(10,"S7","passive","R"),(9,"S8","passive","R")],
    "shift": [(14,"SER","input","L"),(11,"SRCLK","input","L"),(12,"RCLK_PRELOAD","input","L"),(10,"SRCLR_N","input","L"),(13,"OE_N","input","L"),(16,"VCC","power_in","L"),(8,"GND","power_in","L"),(15,"QA","output","R"),(1,"QB","output","R"),(2,"QC","output","R"),(3,"QD","output","R"),(4,"QE","output","R"),(5,"QF","output","R"),(6,"QG","output","R"),(7,"QH","output","R"),(9,"QH_SHIFT","output","R")],
    "dmux": [(1,"SELECT_SAFE","input","L"),(15,"ENABLE_N","input","L"),(2,"1A_HOLD","input","L"),(3,"1B_CANDIDATE","input","L"),(5,"2A_HOLD","input","L"),(6,"2B_CANDIDATE","input","L"),(11,"3A_HOLD","input","L"),(10,"3B_CANDIDATE","input","L"),(14,"4A_HOLD","input","L"),(13,"4B_CANDIDATE","input","L"),(16,"VCC","power_in","L"),(8,"GND","power_in","L"),(4,"1Y","output","R"),(7,"2Y","output","R"),(9,"3Y","output","R"),(12,"4Y","output","R")],
    "ff": [(1,"CLK","input","L"),(2,"D","input","L"),(6,"CLR_N","input","L"),(7,"PRE_N","input","L"),(8,"VCC","power_in","L"),(4,"GND","power_in","L"),(5,"Q","output","R"),(3,"Q_N","output","R")],
    "and3": [(1,"A","input","L"),(3,"B","input","L"),(6,"C","input","L"),(5,"VCC","power_in","L"),(2,"GND","power_in","L"),(4,"Y","output","R")],
    "inv": [(2,"A","input","L"),(5,"VCC","power_in","L"),(3,"GND","power_in","L"),(1,"NC","no_connect","L"),(4,"Y","output","R")],
}
for kind in ("and2", "or", "xor"):
    PINS[kind] = [(1,"A","input","L"),(2,"B","input","L"),(5,"VCC","power_in","L"),(3,"GND","power_in","L"),(4,"Y","output","R")]
LOGIC_VALUES = {"and2":"SN74LVC1G08DBVR","and3":"SN74LVC1G11DBVR","or":"SN74LVC1G32DBVR","xor":"SN74LVC1G86DBVR","inv":"SN74LVC1G04DBVR","ff":"SN74LVC1G74DCUR"}
parts = []
def add(ref, value, kind, nets, xy, sheet, description, dnp=False):
    if kind == "J":
        fp = f"Connector_PinHeader_2.54mm:PinHeader_1x{len(nets):02d}_P2.54mm_Vertical"
        pins = [(i, str(i), "passive", "L") for i in sorted(nets)]
    elif kind in ("R", "C"):
        fp = FP[kind]; pins = [(1,"1","passive","L"),(2,"2","passive","R")]
    else:
        fp = FP[kind]; pins = PINS[kind]
    assert {str(p[0]) for p in pins} == {str(k) for k in nets}, (ref, nets)
    assert ref not in {p["ref"] for p in parts}, ref
    parts.append(dict(ref=ref,value=value,kind=kind,footprint=fp,nets={str(k):v for k,v in nets.items()},pins=pins,xy=xy,sheet=sheet,description=description,source_url=SOURCES.get(kind,""),dnp=dnp))
def r(ref,val,a,b,xy,sheet,desc): add(ref,val,"R",{1:a,2:b},xy,sheet,desc)
def c(ref,val,a,b,xy,sheet,desc): add(ref,val,"C",{1:a,2:b},xy,sheet,desc)

add("J1","QUALIFIED EXTERNAL RAILS","J",{1:"VH_24",2:"VDD_3V3",3:"GND"},(55.88,60.96),"root","External qualified supplies; no converter, independent watchdog or rail supervisor is fabricated")
add("J2","CANDIDATE PRELOAD AND COMMIT","J",{1:"ROUTE_SER",2:"ROUTE_SRCLK",3:"ROUTE_PRELOAD_LATCH",4:"ROUTE_COMMIT",5:"ROUTE_REARM",6:"ROUTE_SHIFT_TAIL",7:"GND"},(55.88,121.92),"root","Shift candidate then latch preload; unconditional COMMIT captures only if quiet; separate deliberate REARM after active-bit verification")
add("J3","SOURCE ROUTE INTENT / PHASE STATUS","J",{1:"CH0_WANT_ROUTE",2:"CH1_WANT_ROUTE",3:"CH0_REQUEST",4:"CH1_REQUEST",5:"CH0_RUN",6:"CH1_RUN",7:"GND"},(55.88,205.74),"root","Keep WANT_ROUTE asserted across both phases, interphase gap and recovery; phase-low alone never authorizes reroute")
add("J4","EXTERNAL OBSERVED HEALTH CONTRACTS","J",{1:"RESET_READY",2:"RAILS_QUALIFIED",3:"WATCHDOG_OK",4:"AFE_ISOLATED_READY",5:"CH0_QUIESCENT_OK",6:"CH1_QUIESCENT_OK",7:"ROUTE_ACTIVE_BITS_VERIFIED",8:"CH0_MON_PERMIT",9:"CH1_MON_PERMIT",10:"GND"},(55.88,292.1),"root","All inputs default low; active-bit verification is a fresh acknowledgement rising edge after external readback, not a permanently high permission")
add("J5","COMMAND STATUS / NOT MUX READBACK","J",{1:"ROUTE_COMMAND_READY",2:"ROUTE_BLOCK",3:"ROUTE_ADDR_EQUAL",4:"ROUTE_CONFLICT",5:"CH0_ROUTE_EN",6:"CH1_ROUTE_EN",7:"CH0_ROUTE_LOCKED",8:"CH1_ROUTE_LOCKED",9:"QUIET_SAFE",10:"READBACK_SEEN",11:"COMMIT_SEEN",12:"GND"},(355.6,86.36),"root","Digital command status only; not observed continuity, isolation, current, selected switch or rail-off safety evidence")
add("J6","ACTIVE ADDRESS BIT READBACK","J",{i+1:f"CH{ch}_ADDR{bit}" for i,(ch,bit) in enumerate((ch,bit) for ch in (0,1) for bit in range(4))}|{9:"GND"},(355.6,226.06),"root","Actual active flip-flop Q outputs for host verification; not analog multiplexer-state or contact-continuity readback")
add("J7","SIXTEEN CONTACTS / TWO MONITORED RETURNS","J",{i+1:f"STIM{i:02d}_CONTACT" for i in range(16)}|{17:"CH0_RETURN_LOAD",18:"CH1_RETURN_LOAD"},(500.38,203.2),"root","One provisional18pin contact-side bench header: sixteen shared selectable contacts and two distinct monitored dedicated returns; not an implant lead connector")

for ch in (0,1):
    sheet=f"source{ch}"; base=100*(ch+1); q=lambda name:f"CH{ch}_{name}"
    add(f"J{base}","DRIVER A / MONITORED RETURN","J",{1:q("A_ROUTER"),2:q("RETURN_LOAD"),3:"GND"},(55.88,63.5),sheet,"A_ROUTER joins driver A_BR only through required external terminal guard; RETURN_LOAD joins existing monitor load-side return, never B_BR directly")
    for bank in (0,1):
        nets={1:q("ADDR0"),16:q("ADDR1"),15:q("ADDR2"),2:q(f"BANK{bank}_EN"),13:"VH_24",3:"GND",14:"GND",8:q("A_ROUTER")}
        for offset,pin in enumerate((4,5,6,7,12,11,10,9)):nets[pin]=f"STIM{bank*8+offset:02d}_CONTACT"
        add(f"U{base+bank}","TMUX6208PWR","mux",nets,(152.4+bank*132.08,101.6),sheet,"24V single-supply 8:1 path; ENhigh selects one channel, ENlow commands all channels off; internal break-before-make is not terminal isolation")
        c(f"C{base+bank}","100n X7R 50V","VH_24","GND",(106.68+bank*132.08,177.8),sheet,"Local 24V switch bypass; effective capacitance, voltage transient and dielectric qualification remain")
        c(f"C{base+bank+2}","1u X7R 50V","VH_24","GND",(106.68+bank*132.08,210.82),sheet,"Local switch reservoir; exact capacitor MPN, bias derating and return coupling unqualified")
        r(f"R{base+bank}","22k",q(f"BANK{bank}_EN"),"GND",(106.68+bank*132.08,243.84),sheet,"Bank enable pull-down; supplies and stuck switches can defeat command-only inhibit")
    for bit in range(3):
        r(f"R{base+2+bit}","22k",q(f"ADDR{bit}"),"GND",(66.04+bit*121.92,276.86),sheet,"Active address default loading on loss of logic power; not an unpowered-contact safety guarantee")

# Candidate storage, protected active address and command admission are added
# below as explicit native gates, never as descriptive placeholder blocks.
candidate = {14:"ROUTE_SER",11:"ROUTE_SRCLK",12:"ROUTE_PRELOAD_LATCH",10:"RESET_READY",13:"GND",16:"VDD_3V3",8:"GND",9:"ROUTE_SHIFT_TAIL"}
for pin,net in zip((15,1,2,3,4,5,6,7),(f"CH{ch}_PENDING{bit}" for ch in (0,1) for bit in range(4))):candidate[pin]=net
add("U10","SN74LVC595APWR","shift",candidate,(60.96,73.66),"address","Candidate storage only; SRCLR clears shift stage, not output-storage latch; candidate values never directly drive contact addresses")
c("C10","100n X7R 10V","VDD_3V3","GND",(60.96,132.08),"address","Local candidate-shift register bypass")
for ch in (0,1):
    q=lambda s:f"CH{ch}_{s}"
    mux={1:"QUIET_SAFE",15:"GND",16:"VDD_3V3",8:"GND"}
    for bit,(ain,bin,yout) in enumerate(((2,3,4),(5,6,7),(11,10,9),(14,13,12))):
        mux[ain]=q(f"ADDR{bit}");mux[bin]=q(f"PENDING{bit}");mux[yout]=q(f"ADDR_D{bit}")
    add(f"U{20+ch}","SN74LVC157APWR","dmux",mux,(243.84+ch*213.36,78.74),"address","QUIET_SAFE selects pending data; otherwise feedback holds current active Q. COMMIT clock is unconditional and cannot be manufactured by health recovery")
    c(f"C{20+ch}","100n X7R 10V","VDD_3V3","GND",(243.84+ch*213.36,137.16),"address","Local data-mux supply bypass")
    for bit in range(4):
        ref=f"U{30+ch*4+bit}"
        add(ref,"SN74LVC1G74DCUR","ff",{1:"ROUTE_COMMIT",2:q(f"ADDR_D{bit}"),6:"RESET_READY",7:"VDD_3V3",8:"VDD_3V3",4:"GND",5:q(f"ADDR{bit}"),3:None},(76.2+(bit%2)*132.08+ch*264.16,203.2+(bit//2)*81.28),"address","Active address captures only via protected D mux; asynchronous reset forces address zero but cannot admit output")
        c(f"C{30+ch*4+bit}","100n X7R 10V","VDD_3V3","GND",(76.2+(bit%2)*132.08+ch*264.16,241.3+(bit//2)*81.28),"address",f"Local active-address flip-flop {ref} bypass")
for i,net in enumerate(("ROUTE_SER","ROUTE_SRCLK","ROUTE_PRELOAD_LATCH","ROUTE_COMMIT","ROUTE_REARM")):
    r(f"R{10+i}","10k",net,"GND",(50.8+i*106.68,363.22),"address","External clock/control default low; required setup, hold, quiet and release sequencing remains explicit")

cells={"admission":0,"collision":0}
def logic(sheet,kind,nets,desc):
    index=cells[sheet];base=300 if sheet=="admission" else 400
    xy=(55.88+(index%6)*93.98,55.88+(index//6)*63.5)
    ref=f"U{base+index}"
    add(ref,LOGIC_VALUES[kind],kind,nets,xy,sheet,desc)
    cells[sheet]+=1
    return ref
def g2(sheet,kind,a,b,out,desc):return logic(sheet,kind,{1:a,2:b,3:"GND",4:out,5:"VDD_3V3"},desc)
def g3(sheet,a,b,cx,out,desc):return logic(sheet,"and3",{1:a,2:"GND",3:b,4:out,5:"VDD_3V3",6:cx},desc)
def inv(sheet,a,out,desc):return logic(sheet,"inv",{1:None,2:a,3:"GND",4:out,5:"VDD_3V3"},desc)
def ff(sheet,clk,d,clr,out,outn,desc):return logic(sheet,"ff",{1:clk,2:d,3:outn,4:"GND",5:out,6:clr,7:"VDD_3V3",8:"VDD_3V3"},desc)
s="admission"
g3(s,"RESET_READY","RAILS_QUALIFIED","WATCHDOG_OK","HEALTH_A","Qualified startup, rails and externally independent watchdog")
g3(s,"AFE_ISOLATED_READY","CH0_MON_PERMIT","CH1_MON_PERMIT","HEALTH_B","Observed recording isolation and both independent signed-current monitor permits")
g2(s,"and2","HEALTH_A","HEALTH_B","BASE_HEALTH","All health flags must be independently qualified; commands are not observations")
g2(s,"or","CH0_WANT_ROUTE","CH1_WANT_ROUTE","ANY_WANT","Route intent stays high across phases, gap and recovery")
inv(s,"ANY_WANT","NO_WANT","A low phase request alone cannot admit address capture")
g2(s,"or","CH0_REQUEST","CH1_REQUEST","ANY_REQUEST","Both raw phase requests must be low before route change")
g2(s,"or","CH0_RUN","CH1_RUN","ANY_RUN","Both native driver run statuses must be low before route change")
g2(s,"or","ANY_REQUEST","ANY_RUN","ANY_PHASE","Request or actual digital RUN excludes route update")
inv(s,"ANY_PHASE","NO_PHASE","No clock gating; this affects only D-input selection")
g3(s,"CH0_QUIESCENT_OK","CH1_QUIESCENT_OK","BASE_HEALTH","QUIET_HEALTH","External observed quiescence, valid supply/monitor/isolation/watchdog evidence")
g3(s,"NO_WANT","NO_PHASE","QUIET_HEALTH","QUIET_SAFE","Must be stable before COMMIT; COMMIT itself never manufactures quiet")
inv(s,"ROUTE_COMMIT","COMMIT_N","Raw COMMIT inhibits route output and resets route validation")
inv(s,"ROUTE_CONFLICT","NO_CONFLICT","A same-contact dual intent clears validation and inhibits both sources")
g3(s,"BASE_HEALTH","COMMIT_N","NO_CONFLICT","VALID_CLR_N","Asynchronous loss of health, any commit or collision consumes route validation")
ff(s,"ROUTE_COMMIT","QUIET_SAFE","BASE_HEALTH","COMMIT_SEEN",None,"Unconditional raw clock captures whether commit was legal; health loss clears prior acceptance")
g2(s,"and2","BASE_HEALTH","COMMIT_N","ACK_CLR_N","Every COMMIT and health loss consumes the prior readback acknowledgement")
ff(s,"ROUTE_ACTIVE_BITS_VERIFIED","COMMIT_SEEN","ACK_CLR_N","READBACK_SEEN",None,"Unconditional raw acknowledgement clock records fresh post-commit verification event; stale high flag cannot acknowledge new address")
g3(s,"COMMIT_SEEN","QUIET_SAFE","READBACK_SEEN","REARM_D","Separate rearm requires accepted commit, observed quiet and a fresh external active-Q readback acknowledgement")
ff(s,"ROUTE_REARM","REARM_D","VALID_CLR_N","ROUTE_VALID",None,"Unconditional external rearm clock; illegal rearm captures zero; no readiness-generated edge")
g3(s,"ROUTE_VALID","BASE_HEALTH","COMMIT_N","READY_A","Validated digital route command; not observed physical switch state")
g2(s,"and2","READY_A","NO_CONFLICT","ROUTE_COMMAND_READY","Collision removal cannot restore validation without deliberate rearm")
inv(s,"ROUTE_VALID","ROUTE_BLOCK","Inverse route-validation state only; command-level sticky consumed permission")

s="collision"
for bit in range(4):g2(s,"xor",f"CH0_ADDR{bit}",f"CH1_ADDR{bit}",f"ADDR_DIFF{bit}","Actual active Q bits feed contact equality, not pending shift payload")
g2(s,"or","ADDR_DIFF0","ADDR_DIFF1","ADDR_DIFF_LO","Low two active address differences")
g2(s,"or","ADDR_DIFF2","ADDR_DIFF3","ADDR_DIFF_HI","High two active address differences, including bank bit")
g2(s,"or","ADDR_DIFF_LO","ADDR_DIFF_HI","ADDR_ANY_DIFF","Any of four bits differing means different selected contact")
inv(s,"ADDR_ANY_DIFF","ROUTE_ADDR_EQUAL","Full sixteen-contact equality")
g3(s,"CH0_WANT_ROUTE","CH1_WANT_ROUTE","ROUTE_ADDR_EQUAL","ROUTE_CONFLICT","Same active contact with both source intents inhibits BOTH sources; no priority arbitration")
for ch in (0,1):
    q=lambda n:f"CH{ch}_{n}"
    g2(s,"and2","ROUTE_COMMAND_READY",q("WANT_ROUTE"),q("ROUTE_EN"),"Per-source digital route enable; actual isolation/continuity remains external")
    inv(s,q("ADDR3"),q("BANK0_SELECT"),"Active bank bit zero selects contacts 0 through 7")
    g2(s,"and2",q("ROUTE_EN"),q("BANK0_SELECT"),q("BANK0_EN"),"Low bank cannot be commanded on with high bank")
    g2(s,"and2",q("ROUTE_EN"),q("ADDR3"),q("BANK1_EN"),"High bank cannot be commanded on with low bank")
    g2(s,"and2","ROUTE_COMMAND_READY",q("WANT_ROUTE"),q("ROUTE_LOCKED"),"Command permission connection to driver ROUTE_LOCKED; name does not certify switch position")
for sheet,base in (("admission",300),("collision",400)):
    for i in range(cells[sheet]):
        cols=9 if sheet=="admission" else 7;pitch=60.96 if sheet=="admission" else 81.28
        c(f"C{base+i}","100n X7R 10V","VDD_3V3","GND",(43.18+(i%cols)*pitch,279.4+(i//cols)*25.4),sheet,f"Local bypass for U{base+i}")
for i,net in enumerate(("RESET_READY","RAILS_QUALIFIED","WATCHDOG_OK","AFE_ISOLATED_READY","CH0_QUIESCENT_OK","CH1_QUIESCENT_OK","ROUTE_ACTIVE_BITS_VERIFIED","CH0_MON_PERMIT","CH1_MON_PERMIT","CH0_WANT_ROUTE","CH1_WANT_ROUTE","CH0_REQUEST","CH1_REQUEST","CH0_RUN","CH1_RUN")):
    r(f"R{300+i}","10k",net,"GND",(43.18+(i%9)*60.96,353.06+(i//9)*25.4),"admission","Disconnected health, observation or intent input defaults low; not an analog supply-sequencing proof")

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
    text=f'(symbol "SCCI_RH_RTE:{name}" (pin_names (offset 0.7)) (in_bom yes) (on_board yes) (property "Reference" "{name[0]}" (at 0 0 0) {FONT}) (property "Value" "{p["value"]}" (at 0 0 0) {FONT}) (property "Footprint" "{p["footprint"]}" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "{name}_0_1" {graphic}) (symbol "{name}_1_1" '
    for n,nm,kind,x,y,a in pins:text+=f'(pin {kind} line (at {fnum(x)} {fnum(y)} {a}) (length 2.54) (name "{nm}" (effects (font (size 0.85 0.85)))) (number "{n}" {FONT})) '
    return text+'))'
def glabel(net,x,y,key,left=False):return f'(global_label "{net}" (shape bidirectional) (at {fnum(x)} {fnum(y)} {180 if left else 0}) (effects (font (size 0.85 0.85)) (justify {"right" if left else "left"})) (uuid {uid(key)}))'
local=OUT/"scci_rh_rte.pretty";local.mkdir(exist_ok=True)
for p in parts:
    lib,name=p["footprint"].split(":");src=SHARE/"footprints"/(lib+".pretty")/(name+".kicad_mod")
    assert src.is_file(),src
    (local/(name+".kicad_mod")).write_text(src.read_text(encoding="utf-8"),encoding="utf-8")
    p["footprint"]="scci_rh_rte:"+name
flag_symbol='(symbol "SCCI_RH_RTE:SUPPLIED_RAIL" (pin_names (offset 0)) (in_bom no) (on_board no) (property "Reference" "#FLG" (at 0 0 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_QUALIFIED_RAIL" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "SUPPLIED_RAIL_0_1" (polyline (pts (xy -1 1) (xy 0 2) (xy 1 1)) (stroke (width 0.2) (type default)) (fill (type none)))) (symbol "SUPPLIED_RAIL_1_1" (pin power_out line (at 0 0 90) (length 0) (name "SUPPLIED" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))'
for sheet in SHEETS:
    sid=ROOT_ID if sheet=="root" else uid(sheet+"-document")
    path="/"+ROOT_ID if sheet=="root" else "/"+ROOT_ID+"/"+uid(sheet+"-sheet")
    elements=[]
    for p in [p for p in parts if p["sheet"]==sheet]:
        ref=p["ref"];x,y=p["xy"];pins=pin_positions(p);top=y-max(v[4] for v in pins)-5.08;bottom=y-min(v[4] for v in pins)+5.08
        inst=f'(symbol (lib_id "SCCI_RH_RTE:{ref}") (at {fnum(x)} {fnum(y)} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {fnum(x)} {fnum(top)} 0) {FONT}) (property "Value" "{p["value"]}" (at {fnum(x)} {fnum(bottom)} 0) (effects (font (size 0.95 0.95)))) (property "Footprint" "{p["footprint"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) (property "Datasheet" "{p["source_url"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) '
        for n,nm,kind,px,py,a in pins:
            xx,yy=x+px,y-py;net=p["nets"][n];inst+=f'(pin "{n}" (uuid {uid(ref+"-pin-"+n)})) '
            if net is None:elements.append(f'(no_connect (at {fnum(xx)} {fnum(yy)}) (uuid {uid(ref+"-nc-"+n)}))')
            else:
                ex=xx+(-5.08 if px<0 else 5.08)
                elements.append(f'(wire (pts (xy {fnum(xx)} {fnum(yy)}) (xy {fnum(ex)} {fnum(yy)})) (stroke (width 0) (type default)) (uuid {uid(ref+"-wire-"+n)}))')
                elements.append(glabel(net,ex,yy,ref+"-label-"+n,left=px<0))
        elements.append(inst+f'(instances (project "{PROJECT}" (path "{path}" (reference "{ref}") (unit 1)))))')
    texts=[("DIGITAL RESEARCH CIRCUIT / RESTRICTED 24 V, 3 mA SOURCES / ARTIFICIAL LOADS ONLY",20.32,17.78,1.5),("Sixteen selectable stimulation contacts, two dedicated monitored returns; command-level routing is not measured continuity or isolation.",20.32,25.4,1)]
    if sheet=="root":
        for i,net in enumerate(("VH_24","VDD_3V3","GND")):
            x,y=177.8+i*81.28,292.1;ref=f"#FLG{i+1}"
            elements.append(f'(symbol (lib_id "SCCI_RH_RTE:SUPPLIED_RAIL") (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_QUALIFIED_RAIL" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (pin "1" (uuid {uid(ref+"-pin")})) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (reference "{ref}") (unit 1)))))')
            elements.append(glabel(net,x,y,ref+"-label"))
        for i,name in enumerate(SHEETS[1:]):
            x=20.32+(i%3)*182.88;y=337.82+(i//3)*30.48
            elements.append(f'(sheet (at {fnum(x)} {fnum(y)}) (size 157.48 10.16) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {uid(name+"-sheet")}) (property "Sheetname" "{name}" (at {fnum(x)} {fnum(y-2)} 0) (effects (font (size 1 1)) (justify left bottom))) (property "Sheetfile" "{name}.kicad_sch" (at {fnum(x)} {fnum(y+12.16)} 0) (effects (font (size 1 1)) (justify left top))) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (page "{i+2}")))))')
        texts +=[("Required before COMMIT: both WANT/REQUEST/RUN low, independently observed quiescence, monitor permits, rails, recording isolation and watchdog valid.",20.32,317.5,1),("Then: COMMIT -> read all eight active Q bits -> fresh verification ACK edge -> separate REARM -> assert route WANT -> allow settling before phase.",20.32,325.12,1),("No mux state sensor, independent terminal cut-off, compliance detector, independent watchdog, rail generator, PCB or implanted device is completed here.",20.32,398.78,1)]
    elif sheet.startswith("source"):
        texts +=[("Both bank D commons share A_ROUTER. EN0 = ROUTE_EN & !ADDR3; EN1 = ROUTE_EN & ADDR3. Addresses 000..111 select S1..S8.",20.32,38.1,1),("Dedicated return: external contact -> RETURN_LOAD -> existing monitor 2 ohm shunt -> RETURN_DRIVER -> current-driver B_BR.",20.32,307.34,1),("Do not bypass the monitor, add a second shunt, tie the two returns, or use recording REF/BIAS as a stimulation return.",20.32,314.96,1),("TMUX6208 is rail-to-rail at valid 24 V supply; powered-off, stuck-on, parasitic coupling and two-source shared tissue paths remain unqualified.",20.32,322.58,1),("A_ROUTER needs external terminal guard qualification before connection to A_BR. Internal enable-low is only a commanded off state.",20.32,330.2,1)]
    elif sheet=="address":
        texts +=[("Candidate bits may change without changing active addresses. Eight active flip-flops always see raw COMMIT clock; safe D selection loads or holds.",20.32,158.75,1),("RESET_READY low asynchronously clears active bits to zero; outputs remain inhibited until legal COMMIT, fresh readback ACK and deliberate REARM.",20.32,166.37,1),("SRCLR affects only the candidate shift stage. QH_SHIFT is payload cascade, not active-address or analog switch readback. Actual Q bits appear at J6.",20.32,393.7,1),("QUIET_SAFE and candidate data must meet physical setup/hold. Gate delay, asynchronous clear, metastability and clock-integrity qualification remain.",20.32,401.32,1)]
    elif sheet=="admission":
        texts +=[("BASE_HEALTH = RESET & RAILS & WATCHDOG & AFE_ISOLATED_READY & MON0 & MON1; QUIET_SAFE additionally requires both WANT/REQUEST/RUN low and quiescence.",20.32,36.83,0.9),("Any COMMIT invalidates prior validation and ACK. Illegal COMMIT holds active bits and captures COMMIT_SEEN=0.",20.32,391.16,1),("Rearm needs a fresh post-commit ACK edge. Health recovery or collision removal cannot create a clock edge or restart output.",20.32,398.78,1),("Ideal logic only: setup/hold, all-off settling, voltage, independent watchdog and actual current observation remain mandatory.",20.32,406.4,1)]
    else:
        texts +=[("Conflict = WANT0 & WANT1 & equal(all four active address bits). It disables BOTH bank families and asynchronously clears route validation.",20.32,36.83,1),("Removing a conflict only removes its fault condition; it does not restore VALID. Release both WANTs, verify quiet, then explicitly rearm.",20.32,381,1),("The two source enables may coexist only at different contacts. Common tissue impedance and volume conduction are outside this digital collision test.",20.32,388.62,1),("ROUTE_LOCKED means admitted digital command ownership only. No selected-contact continuity or power-off isolation is inferred.",20.32,396.24,1)]
    for i,(text,x,y,size) in enumerate(texts):elements.append(f'(text "{text}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size {size} {size})) (justify left)) (uuid {uid(sheet+"-text-"+str(i))}))')
    embedded="".join(lib_symbol(p) for p in parts if p["sheet"]==sheet)+(flag_symbol if sheet=="root" else "")
    data=f'(kicad_sch (version 20250114) (generator "scci_rh_stage4_router") (uuid {sid}) (paper "A2") (title_block (title "Project SCCI RH S4 / {TITLES[sheet]}") (date "2026-10-13") (rev "0.1") (company "Project SCCI RH") (comment 1 "Native digital route slice; artificial loads; external protection/power/PCB remain")) (lib_symbols {embedded}) '+"".join(elements)+')\n'
    (OUT/(PROJECT if sheet=="root" else sheet)).with_suffix(".kicad_sch").write_text(data,encoding="utf-8")
(OUT/"SCCI_RH_RTE.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "scci_rh_stage4_router") '+("".join(lib_symbol(p) for p in parts)+flag_symbol).replace('(symbol "SCCI_RH_RTE:', '(symbol "')+')\n',encoding="utf-8")
(OUT/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "SCCI_RH_RTE") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH_RTE.kicad_sym") (options "") (descr "Package-specific original route circuit pin symbols; primary PDFs in connectivity.json")))\n',encoding="utf-8")
(OUT/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "scci_rh_rte") (type "KiCad") (uri "${KIPRJMOD}/scci_rh_rte.pretty") (options "") (descr "KiCad library footprint snapshots; PCB assembly and mask/paste qualification remain")))\n',encoding="utf-8")
(OUT/(PROJECT+".kicad_pro")).write_text(json.dumps({"meta":{"filename":PROJECT+".kicad_pro","version":1},"erc":{"rule_severities":{"single_global_label":"warning","four_way_junction":"warning","simulation_model_issue":"warning","footprint_filter":"warning"}}},indent=2)+"\n",encoding="utf-8")
manifest={"schema":"scci_rh.stage4.contact-router.connectivity.v1","date":"2026-10-13","scope":"Native two-source sixteen-contact digital route command slice; restricted24V3mA artificial loads; not observed mux state/PCB/implant qualification","parts":parts,"source_documents":SOURCES,"nominal":{"sources":2,"selectable_contacts":16,"dedicated_returns":2,"muxes":4,"mux_supply_V":24,"logic_supply_V":3.3,"command_current_A":.003,"command_phase_s":200e-6,"routing_off_guard_allocation_s":25e-6,"route_settle_allocation_s":25e-6},"control_contract":{"base_health":"RESET_READY&RAILS_QUALIFIED&WATCHDOG_OK&AFE_ISOLATED_READY&CH0_MON_PERMIT&CH1_MON_PERMIT","quiet_safe":"BASE_HEALTH&CH0_QUIESCENT_OK&CH1_QUIESCENT_OK&!CH0_WANT_ROUTE&!CH1_WANT_ROUTE&!CH0_REQUEST&!CH1_REQUEST&!CH0_RUN&!CH1_RUN","active_D":"QUIET_SAFE?PENDING:ACTIVE_Q; rawCOMMIT clock unconditional","active_clear_n":"RESET_READY","commit_seen_D":"QUIET_SAFE","commit_seen_clock":"ROUTE_COMMIT rising","commit_seen_clear_n":"BASE_HEALTH","readback_seen_D":"COMMIT_SEEN","readback_seen_clock":"ROUTE_ACTIVE_BITS_VERIFIED rising; external fresh ACK after checking all8activeQ bits","readback_seen_clear_n":"BASE_HEALTH&!ROUTE_COMMIT","valid_D":"COMMIT_SEEN&QUIET_SAFE&READBACK_SEEN","valid_clock":"ROUTE_REARM rising","valid_clear_n":"BASE_HEALTH&!ROUTE_COMMIT&!ROUTE_CONFLICT","collision":"CH0_WANT_ROUTE&CH1_WANT_ROUTE&(CH0_ADDR==CH1_ADDR)","command_ready":"ROUTE_VALID&BASE_HEALTH&!ROUTE_COMMIT&!ROUTE_CONFLICT","source_enable":"ROUTE_COMMAND_READY&CHx_WANT_ROUTE","low_bank_enable":"CHx_ROUTE_EN&!CHx_ADDR3","high_bank_enable":"CHx_ROUTE_EN&CHx_ADDR3","route_locked":"same admitted command as CHx_ROUTE_EN; not observed analog route state","clock_rule":"all address/commit/verification/rearm FF clocks are raw external signals; readiness affects D or asynchronous clear only","want_rule":"held across both phases, interphase gap and recovery; only explicit route release permits a new address","readback_limit":"J6 actualactiveQ readback exists; fresh ACK can still be wrong and analog mux state is not sensed"},"external_unimplemented":["terminal guard/disconnect between driver A_BR and A_ROUTER","existing2ohm monitor shunts remaininmonitoring-cell, notduplicated here","independent external watchdog and rail/startup qualification","observed current/charge, compliance and zero-current quiescence","observed recording-island isolation and node voltages","correct externalactiveQreadback and fresh acknowledgement protocol","actual multiplexer state/contactcontinuity and welded/stuck switch detection","physical setuphold/propagation/alloff/settle and supply sequencing","PCB/assembly, passives exactMPN, thermal/EMC/CAD and biological interface"]}
(OUT/"connectivity.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
with (OUT/"bom.csv").open("w",encoding="utf-8",newline="") as f:
    writer=csv.writer(f);writer.writerow(["reference","value","footprint","sheet","dnp","description","primary_source"])
    for p in parts:writer.writerow([p["ref"],p["value"],p["footprint"],p["sheet"],p["dnp"],p["description"],p["source_url"]])
print(json.dumps({"components":len(parts),"pins":sum(len(p["pins"]) for p in parts),"sheets":len(SHEETS),"root":str(OUT/(PROJECT+".kicad_sch"))}))
