"""Generate the editable, artificial-signal SCCI_RH reference electronics.

Run with KiCad's Python (pcbnew is required). KICAD_SHARE selects a KiCad
installation's share/kicad directory; KICAD_CLI selects kicad-cli.
The hardware is a 5 V electrical test-load reference, never an implant.
"""
from pathlib import Path
import csv, json, os, re, shutil, subprocess, uuid, math, heapq, itertools
from collections import defaultdict
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "electronics"
OUT.mkdir(exist_ok=True)
SHARE = Path(os.environ["KICAD_SHARE"])
CLI = os.environ["KICAD_CLI"]
uid = lambda key: str(uuid.uuid5(uuid.NAMESPACE_URL, "project-scci-rh/electronics/" + key))
mm = pcb.FromMM

# This manifest is the single source of pin connectivity for schematic and PCB.
# OPA2333 SOIC pin numbering: 1 OUTA,2 INA-,3 INA+,4 V-,5 INB+,6 INB-,7 OUTB,8 V+.
parts = []
def add(ref, value, footprint, nets, xy, group, description, mpn=""):
    parts.append(dict(ref=ref, value=value, footprint=footprint, nets={str(k):v for k,v in nets.items()},
                      xy=xy, group=group, description=description, mpn=mpn))
RFP="Resistor_SMD:R_0805_2012Metric"
CFP="Capacitor_SMD:C_0805_2012Metric"
SO8="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
SO16="Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"
def r(ref,value,a,b,xy,group,desc): add(ref,value,RFP,{1:a,2:b},xy,group,desc,"0805 thin-film, 0.1%, >=0.125 W")
def c(ref,value,a,b,xy,group,desc): add(ref,value,CFP,{1:a,2:b},xy,group,desc,"0805 ceramic, X7R, >=10 V, 10%")
add("J1","5V INPUT","Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",{1:"+5V",2:"GND"},(5,24),"power","External regulated 5 V only; no isolation or regulator")
add("J2","ARTIFICIAL IN","Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",{1:"SIG_IN",2:"GND",3:"MID"},(3,13),"recording","Function-generator input and midpoint monitor")
add("J3","ANALOG OUT","Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",{1:"REC_OUT",2:"GND",3:"MID"},(3,32),"recording","High-impedance external ADC/scope, not populated")
add("U1","OPA2333AID",SO8,{1:"REC_AMP",2:"REC_FB",3:"REC_IN",4:"GND",5:"MID_RAW",6:"MID",7:"MID",8:"+5V"},(25,20),"recording","A: AC-coupled gain 21; B: midpoint follower","OPA2333AID")
r("R1","10k","SIG_IN","AC_IN",(16,13),"recording","Input series impedance; not patient protection")
c("C1","1u","AC_IN","REC_IN",(20,13),"recording","Input AC coupling, 0.158 Hz corner with R1+R2")
r("R2","1M","REC_IN","MID",(22,10),"recording","Amplifier input bias return")
r("R3","1k","REC_FB","MID",(22,28),"recording","Gain denominator")
r("R4","20k","REC_AMP","REC_FB",(27,28),"recording","Gain numerator")
r("R5","1k","REC_AMP","REC_OUT",(33,21),"recording","Output RC and capacitive-load isolation")
c("C2","47n","REC_OUT","GND",(38,21),"recording","Output low-pass capacitor")
r("R6","10k","+5V","MID_RAW",(14,28),"power","Midpoint divider upper")
r("R7","10k","MID_RAW","GND",(14,33),"power","Midpoint divider lower")
c("C3","10u","MID_RAW","GND",(19,35),"power","Midpoint bulk bypass")
c("C5","100n","+5V","GND",(30,14),"power","U1 local supply bypass")
c("C8","10u","+5V","GND",(8,21),"power","Input supply bulk bypass")
add("U2","OPA2333AID",SO8,{1:"I_REF",2:"I_REF",3:"I_REF_RAW",4:"GND",5:"I_REF",6:"I_SENSE",7:"GATE_DRV",8:"+5V"},(47,30),"stimulation","A: reference follower; B: current servo","OPA2333AID")
r("R8","49.9k","+5V","I_REF_RAW",(38,29),"stimulation","Current-reference divider upper")
r("R9","1.02k","I_REF_RAW","GND",(38,34),"stimulation","Current-reference divider lower")
c("C4","100n","I_REF_RAW","GND",(42,37),"stimulation","Reference low-pass")
r("R10","1k","I_SENSE","GND",(48,40),"stimulation","Current sense, I = Vref / R10")
r("R11","1k","GATE_DRV","GATE",(54,37),"stimulation","MOSFET gate isolation")
add("Q1","2N7002","Package_TO_SOT_SMD:SOT-23",{1:"GATE",2:"I_SENSE",3:"SINK"},(57,32),"stimulation","N-MOSFET current sink; stability not hardware-validated","2N7002")
add("Q2","2N7002","Package_TO_SOT_SMD:SOT-23",{1:"INHIBIT",2:"SINK",3:"+5V"},(57,41),"stimulation","Idle source-follower bypass keeps sink servo supplied while INHIBIT=1","2N7002")
c("C6","100n","+5V","GND",(46,24),"power","U2 local supply bypass")
add("U3","74HC4053D",SO16,{1:"+5V",2:"SINK",3:"GND",4:"GND",5:"GND",6:"INHIBIT",7:"GND",8:"GND",9:"GND",10:"PHASE",11:"PHASE",12:"+5V",13:"SINK",14:"SW_A",15:"SW_B",16:"+5V"},(60,18),"stimulation","A/B SPDT sections reverse one regulated sink; C grounded unused","74HC4053D")
r("R12","100k","INHIBIT","+5V",(63,10),"control","Default-off pull-up; externally driven low to enable")
r("R13","100k","PHASE","GND",(65,29),"control","Defined polarity while logic is disconnected")
c("C7","100n","+5V","GND",(55,10),"power","U3 local supply bypass")
r("R14","12k","SW_A","DUT_A",(68,27),"stimulation","Revision B series output resistance, leg A")
r("R15","12k","SW_B","DUT_B",(66,34),"stimulation","Revision B series output resistance, leg B")
add("J4","5V LOGIC","Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",{1:"PHASE",2:"INHIBIT",3:"+5V",4:"GND"},(74,16),"control","External phase/inhibit sequencer; 5 V CMOS logic required")
add("J5","DUMMY LOAD","Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",{1:"DUT_A",2:"DUT_B"},(74,32),"stimulation","External electrical test load only")

# Local footprint snapshots make source editable without absolute library paths.
fpdir=OUT/"scci_rh.pretty"; fpdir.mkdir(exist_ok=True)
modeldir=OUT/"models3d"; modeldir.mkdir(exist_ok=True)
for p in parts:
    lib,name=p['footprint'].split(':')
    src=SHARE/"footprints"/(lib+".pretty")/(name+".kicad_mod")
    s=src.read_text(encoding="utf-8")
    def replace_model(m):
        rel=m.group(1); model=SHARE/"3dmodels"/rel
        if model.exists():
            dest=modeldir/model.name
            if not dest.exists(): shutil.copy2(model,dest)
            return '"${KIPRJMOD}/models3d/'+model.name+'"'
        return m.group(0)
    s=re.sub(r'"\$\{KICAD10_3DMODEL_DIR\}/([^"\n]+)"',replace_model,s)
    (fpdir/(name+".kicad_mod")).write_text(s,encoding="utf-8")
    p['footprint']='scci_rh:'+name
(OUT/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "scci_rh") (type "KiCad") (uri "${KIPRJMOD}/scci_rh.pretty") (options "") (descr "SCCI_RH local footprint snapshots")))\n')

# Native schematic: chips expose every functional pin, with named local wires.
# All symbols are local, embedded, and single-unit to prevent hidden power pins.
def pins_for(p):
    if p['ref'].startswith('R') or p['ref'].startswith('C'): return [("1","1","passive",-5.08,0,0),("2","2","passive",5.08,0,180)]
    if p['ref'].startswith('J'):
        return [(n,n,"passive",-7.62,(int(n)-1)*-2.54,0) for n in p['nets']]
    if p['ref'].startswith('Q'): return [("1","G","input",-7.62,0,0),("2","S","passive",7.62,-2.54,180),("3","D","passive",7.62,2.54,180)]
    if p['ref'] in ('U1','U2'):
        return [("1","OUT_A","output",12.7,7.62,180),("2","IN_A-","input",-12.7,5.08,0),("3","IN_A+","input",-12.7,7.62,0),("4","V-","power_in",-12.7,-10.16,0),("5","IN_B+","input",-12.7,-2.54,0),("6","IN_B-","input",-12.7,-5.08,0),("7","OUT_B","output",12.7,-2.54,180),("8","V+","power_in",-12.7,12.7,0)]
    names={1:'B1',2:'B0',3:'C1',4:'C',5:'C0',6:'INH',7:'VEE',8:'VSS',9:'S_C',10:'S_B',11:'S_A',12:'A0',13:'A1',14:'A',15:'B',16:'VDD'}
    result=[]
    for n in range(1,17):
        left=n in (6,7,8,9,10,11,16)
        seq=([16,6,11,10,9,7,8] if left else [12,13,14,2,1,15,5,3,4])
        y=12.7-seq.index(n)*2.54
        # Analog switch terminals do not drive a voltage: their ERC type is
        # passive, unlike digital bidirectional I/O. This permits rail routing.
        kind='power_in' if n in (7,8,16) else 'input' if n in (6,9,10,11) else 'passive'
        result.append((str(n),names[n],kind,-15.24 if left else 15.24,y,0 if left else 180))
    return result
font='(effects (font (size 1.0 1.0)))'
def lib_symbol(name,p):
    pins=pins_for(p)
    maxy=max(v[4] for v in pins); miny=min(v[4] for v in pins)
    if p['ref'][0] in 'RC':
        graphic='(rectangle (start -2.54 1.0) (end 2.54 -1.0) (stroke (width 0.2) (type default)) (fill (type none)))' if p['ref'][0]=='R' else '(polyline (pts (xy -1 -2) (xy -1 2)) (stroke (width 0.2) (type default)) (fill (type none))) (polyline (pts (xy 1 -2) (xy 1 2)) (stroke (width 0.2) (type default)) (fill (type none))) (polyline (pts (xy -2.54 0) (xy -1 0)) (stroke (width 0.2) (type default)) (fill (type none))) (polyline (pts (xy 1 0) (xy 2.54 0)) (stroke (width 0.2) (type default)) (fill (type none)))'
    else:
        half=12.7 if p['ref']=='U3' else 10.16 if p['ref'][0]=='U' else 5.08
        graphic=f'(rectangle (start {-half} {maxy+1.27}) (end {half} {miny-1.27}) (stroke (width 0.2) (type default)) (fill (type background)))'
    sy=f'(symbol "SCCI_RH:{name}" (pin_names (offset 0.8)) (in_bom yes) (on_board yes) (property "Reference" "{p["ref"][0]}" (at 0 0 0) {font}) (property "Value" "{p["value"]}" (at 0 0 0) {font}) (property "Footprint" "{p["footprint"]}" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "{name}_0_1" {graphic}) (symbol "{name}_1_1" '
    for n,nm,k,x,y,a in pins:
        sy+=f'(pin {k} line (at {x} {y} {a}) (length 2.54) (name "{nm}" {font}) (number "{n}" {font})) '
    return sy+'))'

schemuid=uid('schematic')
liblist=[]; instances=[]; wires=[]
# Component cards fit A3; chips grouped above passive rows.
positions={
'J1':(30.48,35.56),'J2':(30.48,68.58),'J3':(30.48,96.52),
'U1':(96.52,55.88),'U2':(205.74,55.88),'Q1':(256.54,50.8),'Q2':(256.54,86.36),'U3':(327.66,58.42),
'J4':(393.7,35.56),'J5':(393.7,83.82)}
passives=[p for p in parts if p['ref'][0] in 'RC']
for i,p in enumerate(passives): positions[p['ref']]=(35.56+(i%7)*53.34,147.32+(i//7)*25.4)
for p in parts:
    name=p['ref']; liblist.append(lib_symbol(name,p)); x,y=positions[name]
    inst=f'(symbol (lib_id "SCCI_RH:{name}") (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(name)}) '
    inst+=f'(property "Reference" "{name}" (at {x} {y-18 if name.startswith("U") else y-5.08} 0) {font}) '
    value_y=y+19 if name.startswith('U') else y+(len(p['nets'])-1)*2.54+4.0 if name.startswith('J') else y+5.08
    inst+=f'(property "Value" "{p["value"]}" (at {x} {value_y} 0) {font}) '
    inst+=f'(property "Footprint" "{p["footprint"]}" (at {x} {y} 0) (effects (font (size 1 1)) hide)) '
    for n,nm,k,px,py,a in pins_for(p):
        xx,yy=x+px,y-py; net=p['nets'][n]
        inst+=f'(pin "{n}" (uuid {uid(name+"-pin-"+n)})) '
        if net is None:
            wires.append(f'(no_connect (at {xx} {yy}) (uuid {uid(name+"-nc-"+n)}))'); continue
        end=xx+(-7.62 if px<0 else 7.62)
        wires.append(f'(wire (pts (xy {xx} {yy}) (xy {end} {yy})) (stroke (width 0) (type default)) (uuid {uid(name+"-wire-"+n)}))')
        # label faces toward the wire, outside the component.
        ang=0 if px<0 else 180
        just='left' if px<0 else 'right'
        wires.append(f'(label "{net}" (at {end} {yy} {ang}) (effects (font (size 0.85 0.85)) (justify {just} bottom)) (uuid {uid(name+"-label-"+n)}))')
    inst+=f'(instances (project "scci_rh_reference" (path "/{schemuid}" (reference "{name}") (unit 1)))))'
    instances.append(inst)
# Genuine externally-powered power markers, not rule suppressions.
flagname='POWER_FLAG'
liblist.append(f'(symbol "SCCI_RH:{flagname}" (pin_names (offset 0)) (in_bom no) (on_board no) (property "Reference" "#FLG" (at 0 0 0) {font}) (property "Value" "PWR_FLAG" (at 0 0 0) {font}) (symbol "{flagname}_0_1" (polyline (pts (xy -1 1) (xy 0 2) (xy 1 1)) (stroke (width 0.2) (type default)) (fill (type none)))) (symbol "{flagname}_1_1" (pin power_out line (at 0 0 90) (length 0) (name "pwr" {font}) (number "1" {font}))))')
for i,net in enumerate(['+5V','GND']):
    x,y=30.48+i*25.4,119.38; ref=f'#FLG0{i+1}'
    instances.append(f'(symbol (lib_id "SCCI_RH:POWER_FLAG") (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (property "Value" "PWR_FLAG" (at {x} {y-3} 0) {font}) (pin "1" (uuid {uid(ref+"pin")})) (instances (project "scci_rh_reference" (path "/{schemuid}" (reference "{ref}") (unit 1)))))')
    wires.append(f'(label "{net}" (at {x} {y} 0) (effects (font (size 1 1)) (justify left bottom)) (uuid {uid(ref+"label")}))')
texts=[('SCCI_RH / ANALOG REFERENCE',25.4,15.24,2),('5 V / ARTIFICIAL SIGNALS / ELECTRICAL TEST LOADS ONLY',25.4,21.59,1.3),('RECORDING + BUFFERED MIDPOINT',76.2,28,1.25),('PRECISION SINK + POLARITY SWITCH',180,28,1.25),('PASSIVES / net labels define connectivity',25.4,135,1.2),('OPA2333: OUTA=1, INA-=2, INA+=3, V-=4, INB+=5, INB-=6, OUTB=7, V+=8',25.4,238,1.0),('PHASE 0: A=+5V, B=sink. PHASE 1: A=sink, B=+5V. INHIBIT 1: isolated.',25.4,245,1.0),('External 5 V sequencer: 200 us enabled phase 0, inhibit for 50 us, 200 us phase 1, inhibit.',25.4,252,1.0),('No MCU, ADC, current monitor, patient isolation, implant package or validated safety interlock populated.',25.4,259,1.0),('R8/R9/R10: 5*(1.02k)/(49.9k+1.02k)/1k = 100.157 uA nominal; calibrate if ever fabricated.',25.4,266,1.0)]
textitems=[f'(text "{t}" (at {x} {y} 0) (effects (font (size {sz} {sz})) (justify left)) (uuid {uid("text"+str(i))}))' for i,(t,x,y,sz) in enumerate(texts)]
sch='(kicad_sch (version 20250114) (generator "scci_rh_build") (uuid '+schemuid+') (paper "A3") (title_block (title "Project SCCI RH | Artificial-signal analog reference") (rev "1.0") (company "Project SCCI RH") (comment 1 "Digital reference only; no body connection")) (lib_symbols '+''.join(liblist)+') '+''.join(wires+instances+textitems)+')\n'
(OUT/'scci_rh_reference.kicad_sch').write_text(sch,encoding='utf-8')
library=''.join(liblist).replace('(symbol "SCCI_RH:', '(symbol "')
(OUT/'SCCI_RH.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "scci_rh_build") '+library+')\n',encoding='utf-8')
(OUT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "SCCI_RH") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH.kicad_sym") (options "") (descr "SCCI_RH embedded pin-accurate reference symbols")))\n')

# Board generation. Routing is deterministic, on a 0.25 mm two-layer grid.
board=pcb.BOARD(); board.GetDesignSettings().SetCopperLayerCount(2)
board.GetDesignSettings().SetBoardThickness(mm(1.6))
netnames=sorted({v for p in parts for v in p['nets'].values() if v is not None})
nets={}
for name in netnames:
    n=pcb.NETINFO_ITEM(board,'/'+name);board.Add(n);nets[name]=n
footprints=[]
for p in parts:
    name=p['footprint'].split(':')[1]
    fp=pcb.FootprintLoad(str(fpdir),name); fp.SetReference(p['ref']);fp.SetValue(p['value'])
    fp.SetFPID(pcb.LIB_ID('scci_rh',name));fp.SetPosition(pcb.VECTOR2I(mm(p['xy'][0]),mm(p['xy'][1])))
    fp.SetPath(pcb.KIID_PATH('/'+schemuid+'/'+uid(p['ref'])))
    fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
    for pad in fp.Pads():
        n=p['nets'].get(pad.GetNumber())
        if n: pad.SetNet(nets[n])
    board.Add(fp);footprints.append(fp)
for i,(x,y) in enumerate([(10,10),(70,10),(10,40),(70,40)]):
    fp=pcb.FootprintLoad(str(SHARE/'footprints'/'MountingHole.pretty'),'MountingHole_3.2mm_M3')
    name='MountingHole_3.2mm_M3'
    if not (fpdir/(name+'.kicad_mod')).exists(): shutil.copy2(SHARE/'footprints'/'MountingHole.pretty'/(name+'.kicad_mod'),fpdir/(name+'.kicad_mod'))
    fp.SetFPID(pcb.LIB_ID('scci_rh',name));fp.SetReference('H'+str(i+1));fp.SetPosition(pcb.VECTOR2I(mm(x),mm(y)));fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
    fp.SetAttributes(fp.GetAttributes() | pcb.FP_BOARD_ONLY)
    board.Add(fp);footprints.append(fp)
for a,b in [((0,0),(80,0)),((80,0),(80,50)),((80,50),(0,50)),((0,50),(0,0))]:
    sh=pcb.PCB_SHAPE();sh.SetShape(pcb.SHAPE_T_SEGMENT);sh.SetStart(pcb.VECTOR2I(mm(a[0]),mm(a[1])));sh.SetEnd(pcb.VECTOR2I(mm(b[0]),mm(b[1])));sh.SetLayer(pcb.Edge_Cuts);sh.SetWidth(mm(.05));board.Add(sh)

STEP=.25; NX=321; NY=201
owners=[[0]*(NX*NY),[0]*(NX*NY)]
drilled=[]; vias={}
def idx(x,y):return y*NX+x
def mark(layer,x,y,owner):
    old=owners[layer][idx(x,y)]
    owners[layer][idx(x,y)]=owner if old in (0,owner) else -1
def markrect(layer,x0,y0,x1,y1,owner):
    for y in range(max(0,int(math.floor(y0/STEP))),min(NY-1,int(math.ceil(y1/STEP)))+1):
        for x in range(max(0,int(math.floor(x0/STEP))),min(NX-1,int(math.ceil(x1/STEP)))+1):
            mark(layer,x,y,owner)
for z in (0,1):
    markrect(z,0,0,.75,50,-1);markrect(z,79.25,0,80,50,-1);markrect(z,0,0,80,.75,-1);markrect(z,0,49.25,80,50,-1)
def markdisc(layer,x,y,r,owner):
    gx=int(round(x/STEP));gy=int(round(y/STEP));rr=int(math.ceil(r/STEP))
    for yy in range(max(0,gy-rr),min(NY,gy+rr+1)):
        for xx in range(max(0,gx-rr),min(NX,gx+rr+1)):
            if math.hypot(xx*STEP-x,yy*STEP-y)<=r+.18: mark(layer,xx,yy,owner)
padnodes=defaultdict(list)
for fp in footprints:
    for pad in fp.Pads():
        pt=pad.GetPosition();x,y=pcb.ToMM(pt.x),pcb.ToMM(pt.y);size=pad.GetSize();w,h=pcb.ToMM(size.x),pcb.ToMM(size.y)
        n=pad.GetNetCode();n=n if n>0 else -1
        thru=pad.GetAttribute()!=pcb.PAD_ATTRIB_SMD
        if thru:
            d=pad.GetDrillSize();drilled.append((x,y,max(pcb.ToMM(d.x),pcb.ToMM(d.y))/2))
        layers=(0,1) if thru else (0,)
        for z in layers:markrect(z,x-w/2-.38,y-h/2-.38,x+w/2+.38,y+h/2+.38,n)
        if n>0:padnodes[n].append((round(x/STEP),round(y/STEP),0,x,y))
directions=[(1,0),(0,1),(-1,0),(0,-1)]
def clear(x,y,z,n):
    if x<1 or y<1 or x>=NX-1 or y>=NY-1:return False
    return owners[z][idx(x,y)] in (0,n)
def viaok(x,y,n):
    for xx,yy,r in drilled:
        if math.hypot(x*STEP-xx,y*STEP-yy)<r+.15+.35:return False
    for (vx,vy),vn in vias.items():
        if (vx,vy)==(x,y):
            if vn!=n:return False
        elif math.hypot(x-vx,y-vy)*STEP<1.0:return False
    for z in (0,1):
        for dy in range(-2,3):
            for dx in range(-2,3):
                if dx*dx+dy*dy<=5 and not clear(x+dx,y+dy,z,n): return False
    return True
def astar(start,goal,n):
    sx,sy,sz=start;gx,gy,gz=goal
    # Direction in state discourages unnecessary turns, preserving Manhattan segments.
    ss=(sx,sy,sz,4);heap=[(abs(sx-gx)+abs(sy-gy),0,ss)];dist={ss:0};prev={}
    visited=0
    while heap:
        _,g,s=heapq.heappop(heap)
        if g!=dist.get(s):continue
        x,y,z,d=s;visited+=1
        if (x,y,z)==(gx,gy,gz):
            path=[]
            while s in prev:path.append(s[:3]);s=prev[s]
            path.append(s[:3]);return path[::-1]
        if visited>900000:return None
        for nd,(dx,dy) in enumerate(directions):
            xx,yy=x+dx,y+dy
            if not clear(xx,yy,z,n):continue
            cost=1+(.25 if d not in (nd,4) else 0);t=(xx,yy,z,nd);ng=g+cost
            if ng<dist.get(t,1e100):
                dist[t]=ng;prev[t]=s;heapq.heappush(heap,(ng+abs(xx-gx)+abs(yy-gy)+(8 if z!=gz else 0),ng,t))
        if viaok(x,y,n):
            t=(x,y,1-z,4);ng=g+8
            if ng<dist.get(t,1e100):dist[t]=ng;prev[t]=s;heapq.heappush(heap,(ng+abs(x-gx)+abs(y-gy)+(8 if 1-z!=gz else 0),ng,t))
    return None
def track(a,b,z,n):
    if a==b:return
    t=pcb.PCB_TRACK(board);t.SetStart(pcb.VECTOR2I(mm(a[0]),mm(a[1])));t.SetEnd(pcb.VECTOR2I(mm(b[0]),mm(b[1])));t.SetWidth(mm(.25));t.SetLayer(pcb.F_Cu if z==0 else pcb.B_Cu);t.SetNetCode(n);board.Add(t)
def emit(path,n,start_exact,end_exact):
    first=path[0];last=path[-1]
    track(start_exact,(first[0]*STEP,first[1]*STEP),first[2],n)
    anchor=first;prev=first;direc=None
    for p in path[1:]:
        if p[2]!=prev[2]:
            track((anchor[0]*STEP,anchor[1]*STEP),(prev[0]*STEP,prev[1]*STEP),prev[2],n)
            if (p[0],p[1]) not in vias:
                v=pcb.PCB_VIA(board);v.SetPosition(pcb.VECTOR2I(mm(p[0]*STEP),mm(p[1]*STEP)));v.SetWidth(mm(.65));v.SetDrill(mm(.3));v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNetCode(n);board.Add(v);vias[(p[0],p[1])]=n
            for z in (0,1):markdisc(z,p[0]*STEP,p[1]*STEP,.58,n)
            anchor=p;direc=None
        else:
            d=(p[0]-prev[0],p[1]-prev[1])
            if direc is not None and d!=direc:
                track((anchor[0]*STEP,anchor[1]*STEP),(prev[0]*STEP,prev[1]*STEP),prev[2],n);anchor=prev
            direc=d
        markdisc(p[2],p[0]*STEP,p[1]*STEP,.39,n);prev=p
    track((anchor[0]*STEP,anchor[1]*STEP),(last[0]*STEP,last[1]*STEP),last[2],n)
    track((last[0]*STEP,last[1]*STEP),end_exact,last[2],n)

routed=[]
# Local nets first; rails later. Every connection is explicit copper, no hidden zones.
def priority(n):
    name=board.FindNet(n).GetNetname().lstrip('/')
    return (0 if name=='PHASE' else 1 if name=='INHIBIT' else 3 if name in ('GND','+5V','MID') else 2,len(padnodes[n]),n)
order=sorted(padnodes,key=priority)
for n in order:
    nodes=padnodes[n];connected=[nodes[0]];remaining=nodes[1:]
    while remaining:
        pairs=sorted((abs(a[0]-b[0])+abs(a[1]-b[1]),i,j) for i,a in enumerate(connected) for j,b in enumerate(remaining))
        done=False
        for _,i,j in pairs:
            a,b=connected[i],remaining[j];path=astar(a[:3],b[:3],n)
            if path is None:continue
            emit(path,n,a[3:],b[3:]);connected.append(remaining.pop(j));routed.append(dict(net=board.FindNet(n).GetNetname(),points=len(path)));done=True;break
        if not done:
            details=[(a[:3],owners[a[2]][idx(a[0],a[1])]) for a in nodes]
            raise RuntimeError('Cannot route '+board.FindNet(n).GetNetname()+' endpoints='+str(details))
    print('Routed',board.FindNet(n).GetNetname(),len(nodes),'pads',flush=True)

def silk(text,x,y,size=1):
    t=pcb.PCB_TEXT(board);t.SetText(text);t.SetPosition(pcb.VECTOR2I(mm(x),mm(y)));t.SetLayer(pcb.F_SilkS);t.SetTextSize(pcb.VECTOR2I(mm(size),mm(size)));t.SetTextThickness(mm(.15));board.Add(t)
silk('SCCI_RH / ANALOG REFERENCE',40,3,1.25);silk('DIGITAL DESIGN - DUMMY LOAD ONLY',40,47,1)
# Reference text on fabrication layer stays readable without silk/pad conflicts.
for fp in footprints:
    fp.Reference().SetLayer(pcb.F_Fab);fp.Reference().SetVisible(True)
pcb.SaveBoard(str(OUT/'scci_rh_reference.kicad_pcb'),board)
# Minimal project with ordinary (unwaived) constraints.
project={"meta":{"filename":"scci_rh_reference.kicad_pro","version":1},"board":{"design_settings":{"rules":{"min_clearance":0.18,"min_track_width":0.20,"min_via_diameter":0.60,"min_through_hole_diameter":0.30,"min_hole_clearance":0.25,"min_copper_edge_clearance":0.30}}}}
(OUT/'scci_rh_reference.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
(OUT/'connectivity.json').write_text(json.dumps({'board_mm':[80,50,1.6],'mounting_holes_mm':[[10,10],[70,10],[10,40],[70,40]],'parts':parts,'routes':routed},indent=2)+'\n')
with (OUT/'bom.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['Reference','Value','Footprint','MPN or specification','Function'])
    for p in parts:w.writerow([p['ref'],p['value'],p['footprint'],p['mpn'],p['description']])
exports=OUT/'exports';exports.mkdir(exist_ok=True)
reports=OUT/'reports';reports.mkdir(exist_ok=True)
gerbers=exports/'gerbers';gerbers.mkdir(exist_ok=True)
# Remove only this generator's obsolete non-fabrication Gerber layers.
for obsolete in ['F_Adhesive.gta','B_Adhesive.gba','User_Drawings.gbr','User_Comments.gbr','User_Eco1.gbr','User_Eco2.gbr','Margin.gbr','F_Courtyard.gbr','B_Courtyard.gbr','F_Fab.gbr','B_Fab.gbr','User_1.gbr','User_2.gbr','User_3.gbr','User_4.gbr']:
    old=gerbers/('scci_rh_reference-'+obsolete)
    if old.is_file() and old.resolve().parent==gerbers.resolve():old.unlink()
def run(*args):
    print('Export/check:',' '.join(args),flush=True)
    r=subprocess.run([CLI,*args],capture_output=True,text=True);print(r.stdout,r.stderr)
    if r.returncode: raise RuntimeError('KiCad command failed: '+' '.join(args)+'\n'+r.stdout+r.stderr)
    return r.returncode
schematic=str(OUT/'scci_rh_reference.kicad_sch');pcbfile=str(OUT/'scci_rh_reference.kicad_pcb')
run('sch','erc','--format','json','--severity-all','--exit-code-violations','-o',str(reports/'erc.json'),schematic)
run('sch','export','pdf','-o',str(exports/'scci_rh_reference_schematic.pdf'),schematic)
run('sch','export','svg','-o',str(exports),schematic)
run('sch','export','netlist','-o',str(exports/'scci_rh_reference.net'),schematic)
netlistfile=exports/'scci_rh_reference.net'
# Only normalize export metadata; all native net/pin connectivity is retained.
netlistfile.write_text(re.sub(r'\(source "[^"\n]*"\)', '(source "scci_rh_reference.kicad_sch")',netlistfile.read_text(encoding='utf-8')),encoding='utf-8')
run('pcb','drc','--format','json','--severity-all','--schematic-parity','--exit-code-violations','-o',str(reports/'drc.json'),pcbfile)
run('pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts','-o',str(gerbers),pcbfile)
run('pcb','export','drill','-o',str(gerbers),pcbfile)
run('pcb','export','step','--force','--subst-models','-o',str(exports/'scci_rh_reference.step'),pcbfile)
run('pcb','export','svg','--layers','F.Cu,B.Cu,F.SilkS,Edge.Cuts','-o',str(exports/'scci_rh_reference_board.svg'),pcbfile)
print('Electronics artifacts generated; inspect ERC/DRC reports before calling them clean.')
