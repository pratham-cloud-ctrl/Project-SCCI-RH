"""Generate the editable 16-stream recording research slice; no PCB is generated.

Native symbol rendering follows SCCI_RH's existing driver generator, with independent
package pin maps, exact custom RHD2216/RRP footprints, and no writes to old slices.
"""
from pathlib import Path
import csv
import json
import os
import uuid

OUT = Path(__file__).resolve().parent
SHARE = Path(os.environ.get("KICAD_SHARE", r"E:\project workspace assests\EDA\KiCAD\share\kicad"))
PROJECT = "recording_front_end"
SHEETS = ("root", "acquisition", "bank0", "bank1", "bank2", "bank3", "reference")
TITLES = {"root":"Isolated SPI, control and supplied power", "acquisition":"RHD2216 / sixteen sampled differential streams", "reference":"Shared reference / passive body bias"}
for bank in range(4): TITLES[f"bank{bank}"] = f"Inputs {4*bank:02d}-{4*bank+3:02d} / protected recording"
def uid(key): return str(uuid.uuid5(uuid.NAMESPACE_URL,"project-scci-rh/stage4/recording-front-end/"+key))
ROOT_ID = uid("root")
SOURCES = {
 "rhd":"https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf",
 "hv":"https://www.ti.com/lit/ds/symlink/tmux7412f.pdf",
 "mux":"https://www.ti.com/lit/ds/symlink/tmux6219.pdf",
 "iso":"https://www.ti.com/lit/ds/symlink/iso6741.pdf",
 "inv":"https://www.ti.com/lit/ds/symlink/sn74lvc1g04.pdf",
 "and":"https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf",
}
FP={"R":"Resistor_SMD:R_0805_2012Metric", "C":"Capacitor_SMD:C_0805_2012Metric",
 "rhd":"scci_rh_afe:RHD2216_QFN56_8x8_P0.5_EP6.1", "hv":"scci_rh_afe:Texas_RRP0016A_WQFN16_4x4_P0.65_EP2.6",
 "mux":"Package_SO:VSSOP-8_2.3x2mm_P0.5mm", "iso":"Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm",
 "inv":"Package_TO_SOT_SMD:SOT-23-5", "and":"Package_TO_SOT_SMD:SOT-23-5"}
PINS={
 "hv":[(15,"SEL1","input","L"),(14,"SEL2","input","L"),(7,"SEL3","input","L"),(6,"SEL4","input","L"),(11,"VDD","power_in","L"),(2,"VSS_NEG","power_in","L"),(3,"GND","power_in","L"),(17,"EP_SHIELD","passive","L"),(1,"S1_CONTACT","passive","R"),(16,"D1_INTERNAL","passive","R"),(12,"S2_CONTACT","passive","R"),(13,"D2_INTERNAL","passive","R"),(9,"S3_CONTACT","passive","R"),(8,"D3_INTERNAL","passive","R"),(4,"S4_CONTACT","passive","R"),(5,"D4_INTERNAL","passive","R"),(10,"FF_N","open_collector","R")],
 "mux":[(5,"EN","input","L"),(6,"SEL_ACQUIRE","input","L"),(4,"VDD","power_in","L"),(7,"VSS_NEG","power_in","L"),(3,"GND","power_in","L"),(1,"D_RHD","passive","R"),(2,"S1_CLAMP","passive","R"),(8,"S2_PROTECTED","passive","R")],
 "iso":[(1,"VCC1_HOST","power_in","L"),(2,"GND1_HOST","power_in","L"),(3,"INA","input","L"),(4,"INB","input","L"),(5,"INC","input","L"),(6,"OUTD","output","L"),(7,"EN1","input","L"),(8,"GND1_HOST","power_in","L"),(16,"VCC2_AFE","power_in","R"),(15,"GND2_AFE","power_in","R"),(14,"OUTA","output","R"),(13,"OUTB","output","R"),(12,"OUTC","output","R"),(11,"IND","input","R"),(10,"EN2","input","R"),(9,"GND2_AFE","power_in","R")],
 "inv":[(1,"NC","no_connect","L"),(2,"A","input","L"),(3,"GND","power_in","L"),(5,"VCC","power_in","L"),(4,"Y","output","R")],
 "and":[(1,"A","input","L"),(2,"B","input","L"),(3,"GND","power_in","L"),(5,"VCC","power_in","L"),(4,"Y","output","R")],
}
# Independent RHD2216 top-view package map, Intan datasheet p2. In CMOS
# mode the four negative SPI pins are NC (p13), not silently grounded.
RHD_NAMES={1:"in4+",2:"in3-",3:"in3+",4:"in2-",5:"in2+",6:"in1-",7:"in1+",8:"in0-",9:"in0+",10:"GND",11:"GND",12:"GND",13:"VDD",14:"auxin1",15:"auxin2",16:"auxin3",17:"GND",18:"CS-",19:"CS+",20:"SCLK-",21:"SCLK+",22:"MOSI-",23:"MOSI+",24:"MISO-",25:"MISO+",26:"VDD",27:"auxout",28:"ADC_ref",29:"GND",30:"LVDS_en",31:"VDD",32:"VESD",33:"elec_test",34:"in15-",35:"in15+",36:"in14-",37:"in14+",38:"in13-",39:"in13+",40:"in12-",41:"in12+",42:"in11-",43:"in11+",44:"in10-",45:"in10+",46:"in9-",47:"in9+",48:"in8-",49:"in8+",50:"in7-",51:"in7+",52:"in6-",53:"in6+",54:"in5-",55:"in5+",56:"in4-",57:"EP_SHIELD"}
PINS["rhd"]=[]
for ch in range(16):
 for suffix in ("+","-"):
  number=next(n for n,name in RHD_NAMES.items() if name==f"in{ch}{suffix}")
  PINS["rhd"].append((number,RHD_NAMES[number],"input","L"))
for n,name in RHD_NAMES.items():
 if name.startswith("in"): continue
 kind="power_in" if name in ("VDD","GND","VESD") else "no_connect" if n in (18,20,22,24,27) else "output" if n==25 else "passive" if n in (28,57) else "input"
 PINS["rhd"].append((n,name,kind,"R"))
parts=[]
def add(ref,value,kind,nets,xy,sheet,description):
 if kind=="J":
  fp=f"Connector_PinHeader_2.54mm:PinHeader_1x{len(nets):02d}_P2.54mm_Vertical"; pins=[(n,str(n),"passive","L") for n in sorted(nets)]
 elif kind in ("R","C"):
  fp=FP[kind];pins=[(1,"1","passive","L"),(2,"2","passive","R")]
 else:fp=FP[kind];pins=PINS[kind]
 assert {str(p[0]) for p in pins}=={str(n) for n in nets},ref
 parts.append(dict(ref=ref,value=value,kind=kind,nets={str(n):v for n,v in nets.items()},pins=pins,xy=xy,sheet=sheet,footprint=fp,description=description,source_url=SOURCES.get(kind,""),dnp=False))
def r(ref,value,a,b,xy,sheet,desc):add(ref,value,"R",{1:a,2:b},xy,sheet,desc)
def c(ref,value,a,b,xy,sheet,desc):add(ref,value,"C",{1:a,2:b},xy,sheet,desc)
rails=("HOST_3V3","HOSTGND","AFE_3V3","AFE_P5","AFE_N5","AFEAGND")
add("J1","EXTERNAL ISOLATED AFE RAILS","J",{1:"AFE_P5",2:"AFE_N5",3:"AFE_3V3",4:"AFEAGND"},(55.88,55.88),"root","Externally supplied regulated isolated rails; no isolated power converter or rail supervisor is implemented")
add("J2","HOST SPI / SUPERVISOR","J",dict(enumerate(("HOST_3V3","HOSTGND","HOST_SCLK","HOST_MOSI","HOST_CS_ASSERT","HOST_MISO","HOST_CONNECT_CMD","HOST_RECORD_CMD","HOST_FAULT_N","HOSTGND"),1)),(55.88,111.76),"root","Host/driver domain; active-high CS_ASSERT is inverted only on AFE island; voltage-qualified readiness is external")
contacts=[f"REC{ch:02d}_CONTACT" for ch in range(16)]+["REF_CONTACT","BIAS_CONTACT"]
add("J3","18 RECORDING FUNCTIONAL PORTS","J",dict(enumerate(contacts,1)),(365.76,91.44),"root","Research fixture header only: sixteen positive contacts, one reference and one separate body-bias contact; no stimulation return")
add("U1","ISO6741FDWR","iso",{1:"HOST_3V3",2:"HOSTGND",3:"HOST_SCLK",4:"HOST_MOSI",5:"HOST_CS_ASSERT",6:"HOST_MISO",7:"HOST_3V3",8:"HOSTGND",9:"AFEAGND",10:"AFE_3V3",11:"AFE_MISO",12:"AFE_CS_ASSERT",13:"AFE_MOSI",14:"AFE_SCLK",15:"AFEAGND",16:"AFE_3V3"},(200.66,63.5),"root","SPI galvanic barrier; F outputs default LOW when valid receive supply lacks valid input signal; no isolated power")
add("U2","ISO6741FDWR","iso",{1:"HOST_3V3",2:"HOSTGND",3:"HOST_CONNECT_CMD",4:"HOST_RECORD_CMD",5:"HOSTGND",6:"HOST_FAULT_N",7:"HOST_3V3",8:"HOSTGND",9:"AFEAGND",10:"AFE_3V3",11:"AFE_FAULT_N",12:None,13:"AFE_RECORD_CMD",14:"AFE_CONNECT",15:"AFEAGND",16:"AFE_3V3"},(200.66,127),"root","Separate active-high controls default disconnect/clamp; reverse wired fault flag is status, never evidence of RHD linear input voltage")
add("U3","SN74LVC1G04DBVR","inv",{1:None,2:"AFE_CS_ASSERT",3:"AFEAGND",4:"AFE_CS_N",5:"AFE_3V3"},(480.06,63.5),"root","Local inversion makes loss-of-link default CS inactive HIGH while island supply is valid")
add("U4","SN74LVC1G08DBVR","and",{1:"AFE_CONNECT",2:"AFE_RECORD_CMD",3:"AFEAGND",4:"AFE_ACQUIRE",5:"AFE_3V3"},(480.06,127),"root","ACQUIRE = CONNECT AND RECORD; invalid01 command remains physically clamped; no autonomous voltage qualification")
root_res=[("HOST_SCLK","HOSTGND","10k"),("HOST_MOSI","HOSTGND","10k"),("HOST_CS_ASSERT","HOSTGND","10k"),("HOST_CONNECT_CMD","HOSTGND","10k"),("HOST_RECORD_CMD","HOSTGND","10k"),("HOST_FAULT_N","HOSTGND","10k"),("AFE_CONNECT","AFEAGND","10k"),("AFE_RECORD_CMD","AFEAGND","10k"),("AFE_ACQUIRE","AFEAGND","10k"),("AFE_CS_ASSERT","AFEAGND","10k"),("AFE_CS_N","AFE_3V3","10k"),("AFE_SCLK","AFEAGND","10k"),("AFE_MOSI","AFEAGND","10k"),("AFE_FAULT_N","AFE_3V3","1k")]
for k,(net,gnd,val) in enumerate(root_res,1):
 r(f"R{k}",val,net,gnd,(50.8+(k-1)%5*76.2,172.72+(k-1)//5*25.4),"root","Explicit control/default or fault-flag pull; power ramps outside valid receiver supply remain unqualified")
for k,(net,gnd,desc) in enumerate((("HOST_3V3","HOSTGND","U1 host bypass"),("AFE_3V3","AFEAGND","U1 island bypass"),("HOST_3V3","HOSTGND","U2 host bypass"),("AFE_3V3","AFEAGND","U2 island bypass"),("AFE_3V3","AFEAGND","U3 inverter bypass"),("AFE_3V3","AFEAGND","U4 AND bypass")),1):
 c(f"C{k}","100n X7R 16V",net,gnd,(45.72+(k-1)*60.96,248.92),"root",desc)
rhdnets={}
for n,name in RHD_NAMES.items():
 if name.startswith("in"):
  ch=int(name[2:-1]);rhdnets[n]=f"AFE_IN{ch:02d}_P" if name.endswith("+") else "AFE_REF"
 elif name in ("GND","VESD","EP_SHIELD","LVDS_en","elec_test"):rhdnets[n]="AFEAGND"
 elif name=="VDD" or name.startswith("auxin"):rhdnets[n]="AFE_3V3"
 else:rhdnets[n]={18:None,19:"AFE_CS_N",20:None,21:"AFE_SCLK",22:None,23:"AFE_MOSI",24:None,25:"AFE_MISO",27:None,28:"AFE_ADC_REF"}[n]
add("U10","RHD2216","rhd",rhdnets,(200.66,101.6),"acquisition","Sixteen differential amplifier inputs and multiplexed 16-bit ADC; common-reference montage is an SCCI_RH choice, not sixteen bipolar electrode pairs")
c("C10","100n X7R 16V","AFE_3V3","AFEAGND",(71.12,193.04),"acquisition","Bottom-side CMOS supply bypass, place near VDD13/26")
c("C11","100n X7R 16V","AFE_3V3","AFEAGND",(190.5,193.04),"acquisition","Right-side supply bypass, place near VDD31")
c("C12","10n 16V","AFE_ADC_REF","AFEAGND",(309.88,193.04),"acquisition","ADC reference bypass within 1cm; no external loading or reference voltage source")
c("C13","1u X7R 16V","AFE_3V3","AFEAGND",(71.12,228.6),"acquisition","Provisional local supply reservoir; effective capacitance and rail ripple are external qualifications")
def input_path(ch,sheet,x):
 tag=f"{ch:02d}";b=100+ch
 contact=f"REC{tag}_CONTACT";after=f"REC{tag}_SERIES";protected=f"REC{tag}_PROT";afe=f"AFE_IN{tag}_P"
 r(f"R{b}","4.99k 0.1%",contact,after,(x,66.04),sheet,"Series impedance before source-side fault protection; resistor voltage/pulse limits require qualification")
 r(f"R{b+100}","10M",protected,"AFEAGND",(x,101.6),sheet,"Defines isolated internal node; maximum leakage can produce material DC voltage, so this is not a linear-range guarantee")
 add(f"U{b}","TMUX6219DGKR","mux",{1:afe,2:"AFEAGND",3:"AFEAGND",4:"AFE_P5",5:"AFE_3V3",6:"AFE_ACQUIRE",7:"AFE_N5",8:protected},(x,147.32),sheet,"Dual-supply bipolar SPDT: S1 grounds RHD during clamp; S2 connects protected node only after external qualification")
 c(f"C{b}","470p C0G 50V",afe,"AFEAGND",(x,193.04),sheet,"SCCI_RH charge-injection absorption choice; not a guaranteed switch injection bound")
 c(f"C{b+100}","100n X7R 16V","AFE_P5","AFEAGND",(x,233.68),sheet,"TMUX6219 local positive rail bypass")
 c(f"C{b+200}","100n X7R 16V","AFE_N5","AFEAGND",(x,266.7),sheet,"TMUX6219 local negative rail bypass")
for bank in range(4):
 sheet=f"bank{bank}";base=4*bank
 for k in range(4):input_path(base+k,sheet,60.96+96.52*k)
 n={1:f"REC{base:02d}_SERIES",16:f"REC{base:02d}_PROT",12:f"REC{base+1:02d}_SERIES",13:f"REC{base+1:02d}_PROT",9:f"REC{base+2:02d}_SERIES",8:f"REC{base+2:02d}_PROT",4:f"REC{base+3:02d}_SERIES",5:f"REC{base+3:02d}_PROT",15:"AFE_CONNECT",14:"AFE_CONNECT",7:"AFE_CONNECT",6:"AFE_CONNECT",11:"AFE_P5",2:"AFE_N5",3:"AFEAGND",17:"AFEAGND",10:"AFE_FAULT_N"}
 # Place the shared quad below its four per-contact paths on a dedicated A2
 # bank sheet, preserving readable parallel columns without overlapping nets.
 add(f"U{20+bank}","TMUX7412FRRPR","hv",n,(200.66,322.58),sheet,"Actual RRP WQFN part: external contact faces protected S; internal D floats on fault/disconnect; ±5V threshold does not protect RHD ±0.4V range")
 c(f"C{20+bank}","100n X7R 16V","AFE_P5","AFEAGND",(76.2,330.2),sheet,"Quad fault switch positive rail bypass")
 c(f"C{30+bank}","100n X7R 16V","AFE_N5","AFEAGND",(330.2,330.2),sheet,"Quad fault switch negative rail bypass")
refhv={1:"REF_SERIES",16:"REF_PROT",12:"AFEAGND",13:"AFEAGND",9:"AFEAGND",8:"AFEAGND",4:"AFEAGND",5:"AFEAGND",15:"AFE_CONNECT",14:"AFEAGND",7:"AFEAGND",6:"AFEAGND",11:"AFE_P5",2:"AFE_N5",3:"AFEAGND",17:"AFEAGND",10:"AFE_FAULT_N"}
add("U24","TMUX7412FRRPR","hv",refhv,(101.6,86.36),"reference","One reference channel used, three unused S/D and selectors grounded; source side only is fault protected")
r("R500","4.99k 0.1%","REF_CONTACT","REF_SERIES",(101.6,154.94),"reference","Single external reference input, not sixteen separate recording-reference contacts")
r("R501","10M","REF_PROT","AFEAGND",(101.6,193.04),"reference","Protected common-reference node DC bleed; source impedance and leakage affect all sixteen channels")
add("U500","TMUX6219DGKR","mux",{1:"AFE_REF",2:"AFEAGND",3:"AFEAGND",4:"AFE_P5",5:"AFE_3V3",6:"AFE_ACQUIRE",7:"AFE_N5",8:"REF_PROT"},(292.1,86.36),"reference","One clamped reference path fans out to all sixteen RHD negative pins; total intrinsic input capacitance is16×12pF typical")
c("C500","2.2n C0G 50V","AFE_REF","AFEAGND",(292.1,154.94),"reference","SCCI_RH reference compensation/injection absorption choice; common-mode conversion must be studied with the shared fanout")
r("R502","499k 0.1%","BIAS_CONTACT","BIAS_MID",(190.5,228.6),"reference","First passive body-bias current-limiting resistor; no stimulation return or active common-mode driver")
r("R503","499k 0.1%","BIAS_MID","AFEAGND",(307.34,228.6),"reference","Second passive body-bias resistor;24V/998k≈24.05uA arithmetic is conditional, not a clinical safe-current claim")
for k,(net,desc) in enumerate((("AFE_P5","U24 positive bypass"),("AFE_N5","U24 negative bypass"),("AFE_P5","U500 positive bypass"),("AFE_N5","U500 negative bypass"))):
 c(f"C{510+k}","100n X7R 16V",net,"AFEAGND",(60.96+(k%2)*129.54,243.84+(k//2)*25.4),"reference",desc)

def fnum(v):return f"{v:.4f}".rstrip("0").rstrip(".")
FONT='(effects (font (size 1 1)))'
def pin_positions(p):
 result=[]
 for side in ("L","R"):
  pins=[v for v in p["pins"] if v[3]==side];start=(len(pins)-1)*1.27
  for i,(n,name,kind,_) in enumerate(pins):result.append((str(n),name,kind,-15.24 if side=="L" else 15.24,start-i*2.54,0 if side=="L" else 180))
 return result
def lib_symbol(p):
 name=p["ref"];pins=pin_positions(p);ymax=max(v[4] for v in pins)+2.54;ymin=min(v[4] for v in pins)-2.54
 graphic=f'(rectangle (start -12.7 {fnum(ymax)}) (end 12.7 {fnum(ymin)}) (stroke (width 0.2) (type default)) (fill (type background)))'
 if p["kind"] in ("R","C"):
  wire=lambda a,b:f'(polyline (pts (xy {a} 0) (xy {b} 0)) (stroke (width 0.2) (type default)) (fill (type none)))'
  if p["kind"]=="R":graphic='(rectangle (start -5.08 1.27) (end 5.08 -1.27) (stroke (width 0.2) (type default)) (fill (type none)))'+wire(-12.7,-5.08)+wire(5.08,12.7)
  else:
   plate=lambda x:f'(polyline (pts (xy {x} -2.54) (xy {x} 2.54)) (stroke (width 0.3) (type default)) (fill (type none)))'
   graphic=plate(-1.27)+plate(1.27)+wire(-12.7,-1.27)+wire(1.27,12.7)
 result=f'(symbol "SCCI_RH_AFE:{name}" (pin_names (offset 0.7)) (in_bom yes) (on_board yes) (property "Reference" "{name[0]}" (at 0 0 0) {FONT}) (property "Value" "{p["value"]}" (at 0 0 0) {FONT}) (property "Footprint" "{p["footprint"]}" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "{name}_0_1" {graphic}) (symbol "{name}_1_1" '
 for n,nm,kind,x,y,a in pins:result+=f'(pin {kind} line (at {fnum(x)} {fnum(y)} {a}) (length 2.54) (name "{nm}" (effects (font (size 0.85 0.85)))) (number "{n}" {FONT})) '
 return result+'))'
def glabel(net,x,y,key,left=False):return f'(global_label "{net}" (shape bidirectional) (at {fnum(x)} {fnum(y)} {180 if left else 0}) (effects (font (size 0.85 0.85)) (justify {"right" if left else "left"})) (uuid {uid(key)}))'

local=OUT/"scci_rh_afe.pretty";local.mkdir(exist_ok=True)
def qfn(name,body,count,pitch,radius,padwidth,padlength,ep,source):
 text=f'(footprint "{name}" (version 20260206) (generator "scci_rh_afe_package") (layer "F.Cu") (descr "{source}") (attr smd) (property "Reference" "REF**" (at 0 {-body/2-1.2} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15)))) (property "Value" "{name}" (at 0 {body/2+1.2} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15)))) (fp_rect (start {-body/2} {-body/2}) (end {body/2} {body/2}) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab")) (fp_rect (start {-radius-padlength/2-.25} {-radius-padlength/2-.25}) (end {radius+padlength/2+.25} {radius+padlength/2+.25}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd")) (fp_circle (center {-body/2-.5} {-body/2+.5}) (end {-body/2-.3} {-body/2+.5}) (stroke (width 0.15) (type default)) (fill none) (layer "F.SilkS")) '
 per=count//4
 for n in range(1,count+1):
  side=(n-1)//per;i=(n-1)%per;t=(i-(per-1)/2)*pitch
  x,y=((-radius,t),(t,radius),(radius,-t),(-t,-radius))[side]
  sx,sy=(padlength,padwidth) if side in (0,2) else (padwidth,padlength)
  text+=f'(pad "{n}" smd rect (at {fnum(x)} {fnum(y)}) (size {sx} {sy}) (layers "F.Cu" "F.Paste" "F.Mask")) '
 text+=f'(pad "{count+1}" smd rect (at 0 0) (size {ep} {ep}) (layers "F.Cu" "F.Mask")) '
 # Nine reduced paste windows avoid a solid full-area center aperture.
 for x in (-ep*.32,0,ep*.32):
  for y in (-ep*.32,0,ep*.32):text+=f'(pad "" smd rect (at {fnum(x)} {fnum(y)}) (size {fnum(ep*.25)} {fnum(ep*.25)}) (layers "F.Paste")) '
 (local/(name+".kicad_mod")).write_text(text+')\n',encoding="utf-8")
qfn("RHD2216_QFN56_8x8_P0.5_EP6.1",8,56,.5,4.05,.25,.9,6.1,"Intan RHD2000 datasheet p38 recommended land pattern; EP57 ground shield; paste aperture choice remains assembly qualification")
qfn("Texas_RRP0016A_WQFN16_4x4_P0.65_EP2.6",4,16,.65,1.9,.3,.6,2.6,"TI TMUX7412F RRP0016A p46:3.8mm center-to-center land span; EP17 grounded; assembly qualification pending")
for p in parts:
 lib,name=p["footprint"].split(":")
 if lib!="scci_rh_afe":
  src=SHARE/"footprints"/(lib+".pretty")/(name+".kicad_mod");assert src.is_file(),src
  (local/(name+".kicad_mod")).write_text(src.read_text(encoding="utf-8"),encoding="utf-8")
  p["footprint"]="scci_rh_afe:"+name
flag_symbol='(symbol "SCCI_RH_AFE:SUPPLIED_RAIL" (pin_names (offset 0)) (in_bom no) (on_board no) (property "Reference" "#FLG" (at 0 0 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_QUALIFIED_RAIL" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "SUPPLIED_RAIL_0_1" (polyline (pts (xy -1 1) (xy 0 2) (xy 1 1)) (stroke (width 0.2) (type default)) (fill (type none)))) (symbol "SUPPLIED_RAIL_1_1" (pin power_out line (at 0 0 90) (length 0) (name "SUPPLIED" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))'
for sheet in SHEETS:
 bank=sheet.startswith("bank");sid=ROOT_ID if sheet=="root" else uid(sheet+"-document");path="/"+ROOT_ID if sheet=="root" else "/"+ROOT_ID+"/"+uid(sheet+"-sheet");elements=[]
 for p in [p for p in parts if p["sheet"]==sheet]:
  ref=p["ref"];x,y=p["xy"];pins=pin_positions(p);top=y-max(v[4] for v in pins)-5.08;bottom=y-min(v[4] for v in pins)+5.08
  inst=f'(symbol (lib_id "SCCI_RH_AFE:{ref}") (at {fnum(x)} {fnum(y)} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {fnum(x)} {fnum(top)} 0) {FONT}) (property "Value" "{p["value"]}" (at {fnum(x)} {fnum(bottom)} 0) (effects (font (size 0.95 0.95)))) (property "Footprint" "{p["footprint"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) (property "Datasheet" "{p["source_url"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) '
  for n,nm,kind,px,py,a in pins:
   xx,yy=x+px,y-py;net=p["nets"][n];inst+=f'(pin "{n}" (uuid {uid(ref+"-pin-"+n)})) '
   if net is None:elements.append(f'(no_connect (at {fnum(xx)} {fnum(yy)}) (uuid {uid(ref+"-nc-"+n)}))')
   else:
    ex=xx+(-5.08 if px<0 else 5.08);elements.append(f'(wire (pts (xy {fnum(xx)} {fnum(yy)}) (xy {fnum(ex)} {fnum(yy)})) (stroke (width 0) (type default)) (uuid {uid(ref+"-wire-"+n)}))');elements.append(glabel(net,ex,yy,ref+"-label-"+n,left=px<0))
  elements.append(inst+f'(instances (project "{PROJECT}" (path "{path}" (reference "{ref}") (unit 1)))))')
 texts=[("DIGITAL RESEARCH CIRCUIT / ARTIFICIAL SIGNALS / NO PCB OR IMPLANT QUALIFICATION",20.32,17.78,1.5),("Spinal concept: 16 positive contacts + 1 shared reference + separate passive bias; amplifier linearity and biological recording remain conditional.",20.32,25.4,1)]
 if sheet=="root":
  for i,net in enumerate(rails):
   x,y=45.72+i*60.96,280.67;ref=f"#FLG{i+1}"
   elements.append(f'(symbol (lib_id "SCCI_RH_AFE:SUPPLIED_RAIL") (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_QUALIFIED_RAIL" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (pin "1" (uuid {uid(ref+"-pin")})) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (reference "{ref}") (unit 1)))))');elements.append(glabel(net,x,y,ref+"-label"))
  for i,name in enumerate(SHEETS[1:]):
   x=20.32+(i%3)*127;y=312.42+(i//3)*43.18
   elements.append(f'(sheet (at {fnum(x)} {fnum(y)}) (size 111.76 15.24) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {uid(name+"-sheet")}) (property "Sheetname" "{name}" (at {fnum(x)} {fnum(y-2)} 0) (effects (font (size 1 1)) (justify left bottom))) (property "Sheetfile" "{name}.kicad_sch" (at {fnum(x)} {fnum(y+17.24)} 0) (effects (font (size 1 1)) (justify left top))) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (page "{i+2}")))))')
  texts +=[("HOSTGND and AFEAGND are separate domains. Both receive valid regulated supplies externally; the digital barrier does not generate power.",20.32,295.91,1),("CS_ASSERT low -> island CS_N high. CONNECT low disconnects HV paths; ACQUIRE = CONNECT & RECORD, so 01 remains clamped.",20.32,397.51,1),("Driver phase admission needs independently observed ISOLATED_READY; neither commands nor fault flags establish voltage or delivery evidence.",20.32,405.13,1)]
 elif bank:
  texts +=[("Per column: contact -> 4.99k -> quad protected S/D -> protected node -> S2; S1 grounds RHD until ACQUIRE is admitted.",20.32,285.75,1),("470pF is at the RHD pin; 10M bleeds the internal node. Switch capacitance/leakage/injection and shared reference mismatch remain modeled assumptions.",20.32,371.475,1),("Fault threshold follows +/-5V rails and is far outside RHD +/-0.4V linear DC range. External low-voltage qualification is mandatory before unclamping.",20.32,379.095,1)]
 elif sheet=="acquisition":
  texts +=[("Every minus input shares AFE_REF. This is 16 differential streams from 18 functional recording ports, not 32 independent recording electrodes.",20.32,162.56,1),("CMOS mode: LVDS_en=0; negative SPI pins NC; unused aux inputs at VDD; auxout NC; elec_test and VESD at AFEAGND.",20.32,259.08,1),("Configure, calibrate and verify readback via SPI before valid data. 4MHz / 5us command slots are the revised isolated-link study baseline.",20.32,266.7,1),("ADC response is pipelined; physical sample timestamps and invalid blanking/recovery intervals must be retained in software.",20.32,274.32,1)]
 else:
  texts +=[("REF_CONTACT passes through the same disconnect/clamp topology; one AFE_REF node feeds all sixteen minus pins (192pF intrinsic typical).",20.32,38.1,1),("BIAS_CONTACT is separate and never a stimulation return. Passive current arithmetic does not establish a medical current limit.",20.32,205.74,1)]
 for i,(txt,x,y,size) in enumerate(texts):elements.append(f'(text "{txt}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size {size} {size})) (justify left)) (uuid {uid(sheet+"-text-"+str(i))}))')
 embedded="".join(lib_symbol(p) for p in parts if p["sheet"]==sheet)+(flag_symbol if sheet=="root" else "")
 paper="A2" if sheet=="root" or bank else "A3"
 data=f'(kicad_sch (version 20250114) (generator "scci_rh_stage4_recording") (uuid {sid}) (paper "{paper}") (title_block (title "Project SCCI RH S4 / {TITLES[sheet]}") (date "2026-10-13") (rev "0.1") (company "Project SCCI RH") (comment 1 "Native digital circuit slice; artificial signals only; external supervisors/power/PCB remain")) (lib_symbols {embedded}) '+"".join(elements)+')\n'
 (OUT/(PROJECT if sheet=="root" else sheet)).with_suffix(".kicad_sch").write_text(data,encoding="utf-8")
(OUT/"SCCI_RH_AFE.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "scci_rh_stage4_recording") '+("".join(lib_symbol(p) for p in parts)+flag_symbol).replace('(symbol "SCCI_RH_AFE:', '(symbol "')+')\n',encoding="utf-8")
(OUT/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "SCCI_RH_AFE") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH_AFE.kicad_sym") (options "") (descr "Package-specific original pin symbols; source PDFs in connectivity.json")))\n',encoding="utf-8")
(OUT/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "scci_rh_afe") (type "KiCad") (uri "${KIPRJMOD}/scci_rh_afe.pretty") (options "") (descr "KiCad library snapshots plus custom manufacturer RHD2216 and RRP land patterns; assembly qualification pending")))\n',encoding="utf-8")
(OUT/(PROJECT+".kicad_pro")).write_text(json.dumps({"meta":{"filename":PROJECT+".kicad_pro","version":1},"erc":{"rule_severities":{"single_global_label":"warning","four_way_junction":"warning","simulation_model_issue":"warning","footprint_filter":"warning"}}},indent=2)+"\n",encoding="utf-8")
manifest={"schema":"scci_rh.stage4.recording-front-end.connectivity.v1","date":"2026-10-13","scope":"Native 16-stream shared-reference isolated recording research slice; artificial signals; not PCB or implant","parts":parts,"source_documents":SOURCES,"functional_contacts":contacts,"supply_domains":{"host":["HOST_3V3","HOSTGND"],"recording_island":["AFE_3V3","AFE_P5","AFE_N5","AFEAGND"]},"nominal":{"positive_streams":16,"shared_reference_paths":1,"recording_functional_ports":18,"RHD_input_C_each_typ_F":12e-12,"reference_input_C_typ_F":192e-12,"series_R_ohm":4990,"protected_bleed_R_ohm":1e7,"positive_added_C_F":470e-12,"reference_added_C_F":2.2e-9,"body_bias_R_total_ohm":998000,"body_bias_24V_arithmetic_A":24/998000,"SPI_clock_Hz":4000000,"SPI_command_slot_s":5e-6,"commands_per_frame":19,"frame_period_s":250e-6},"control_contract":{"connect_low":"All17 HV paths commanded disconnected; no observed isolation proof","acquire":"AFE_CONNECT & AFE_RECORD_CMD","00":"disconnected; all17 RHD pins clamped to AFEAGND","10":"connected; RHD pins clamped while protected nodes qualify","11":"acquisition only after external rail/voltage/quiet/settle evidence","01":"invalid request; AND keeps RHD pins clamped","CS":"F default-low CS_ASSERT is inverted on island to inactive-high CS_N","fault":"Five open-drain FF outputs wired together with1k pullup; healthy FF does not certify RHD linear input range","driver_admission":"External supervisor must establish observed ISOLATED_READY before driver phase; no readiness output is fabricated here"},"external_unimplemented":["isolated +5/-5/+3.3 power generation and valid rail sequencing","low voltage protected-node qualification before RHD unclamp","independent observed isolation before stimulation","SPI firmware initialization/calibration/readback/timestamping","artifact blanking/fast-settle/filter-validity management","electrode impedances, chronic interface and biological signal sufficiency","fault-current/passive component voltage/pulse and isolation qualification","PCB routing/assembly, EMC, thermal/CAD/implant qualification"]}
(OUT/"connectivity.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
with (OUT/"bom.csv").open("w",encoding="utf-8",newline="") as f:
 writer=csv.writer(f);writer.writerow(["reference","value","footprint","sheet","dnp","description","primary_source"])
 for p in parts:writer.writerow([p["ref"],p["value"],p["footprint"],p["sheet"],p["dnp"],p["description"],p["source_url"]])
print(json.dumps({"components":len(parts),"pins":sum(len(p["pins"]) for p in parts),"sheets":len(SHEETS),"root":str(OUT/(PROJECT+".kicad_sch"))}))
