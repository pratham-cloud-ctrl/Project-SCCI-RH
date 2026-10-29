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
PROJECT = "supervision"
def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "project-scci-rh/stage4/supervision/" + key))
ROOT_ID = uid("root")
SHEETS = ("root", "guards", "host_rails", "afe_rails", "watchdog", "quiescence", "voltage0", "voltage1", "duration", "admission0", "admission1")
TITLES = {"root":"Independent shutdown / integration interfaces", "guards":"Four source-side protected terminal paths", "host_rails":"Host and driver rail windows", "afe_rails":"Isolated recording rail windows", "watchdog":"Heartbeat and startup inhibition", "quiescence":"Observed current and reference windows", "voltage0":"Source 0 terminal / compliance observation", "voltage1":"Source 1 terminal / compliance observation", "duration":"Independent secondary phase timers", "admission0":"Source 0 sticky permission / explicit rearm", "admission1":"Source 1 sticky permission / explicit rearm"}
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


# Actual pinmaps are audited against manufacturer PDFs in the component review.
SOURCES.update({"hv":"https://www.ti.com/lit/ds/symlink/tmux7412f.pdf", "wd":"https://www.ti.com/lit/ds/symlink/tps3431.pdf", "rail":"https://www.ti.com/lit/ds/symlink/tps3700.pdf", "cmp":"https://www.ti.com/lit/ds/symlink/tlv3202.pdf", "timer":"https://www.analog.com/media/en/technical-documentation/data-sheets/ltc6993-6993-1-6993-2-6993-3-6993-4.pdf", "iso":"https://www.ti.com/lit/ds/symlink/iso6741.pdf", "opa":"https://www.ti.com/lit/ds/symlink/opa192.pdf"})
FP.update({"hv":"scci_rh_sup:Texas_RRP0016A_WQFN16_4x4_P0.65_EP2.6", "wd":"Package_DFN_QFN:DFN-8-1EP_3x3mm_P0.65mm_EP1.5x2.25mm", "rail":"Package_TO_SOT_SMD:SOT-23-6", "cmp":"Package_SO:VSSOP-8_2.3x2mm_P0.5mm", "timer":"Package_TO_SOT_SMD:TSOT-23-6", "iso":"Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm", "opa":"Package_TO_SOT_SMD:SOT-23-5"})
PINS.update({
"hv":[(15,"SEL1","input","L"),(14,"SEL2","input","L"),(7,"SEL3","input","L"),(6,"SEL4","input","L"),(11,"VDD","power_in","L"),(2,"VSS","power_in","L"),(3,"GND","power_in","L"),(17,"EP_GND","passive","L"),(1,"S1_EXTERNAL","passive","R"),(16,"D1_INTERNAL","passive","R"),(12,"S2_EXTERNAL","passive","R"),(13,"D2_INTERNAL","passive","R"),(9,"S3_EXTERNAL","passive","R"),(8,"D3_INTERNAL","passive","R"),(4,"S4_EXTERNAL","passive","R"),(5,"D4_INTERNAL","passive","R"),(10,"FF_N","open_collector","R")],
"wd":[(1,"VDD","power_in","L"),(2,"CWD","passive","L"),(3,"EN","input","L"),(4,"GND","power_in","L"),(5,"SET1","input","L"),(6,"WDI_FALLING","input","L"),(9,"EP_GND","passive","L"),(7,"WDO_N","open_collector","R"),(8,"ENOUT","open_collector","R")],
"rail":[(3,"INA+_UV","input","L"),(4,"INB-_OV","input","L"),(5,"VDD","power_in","L"),(2,"GND","power_in","L"),(1,"OUTA_UV_N","open_collector","R"),(6,"OUTB_OV_N","open_collector","R")],
"cmp":[(3,"IN1+","input","L"),(2,"IN1-","input","L"),(5,"IN2+","input","L"),(6,"IN2-","input","L"),(8,"VCC","power_in","L"),(4,"GND","power_in","L"),(1,"OUT1","output","R"),(7,"OUT2","output","R")],
"timer":[(1,"TRIG_RAW_REQUEST","input","L"),(3,"SET","passive","L"),(4,"DIV","input","L"),(5,"V+","power_in","L"),(2,"GND","power_in","L"),(6,"OUT","output","R")],
"iso":[(1,"VCC1_HOST","power_in","L"),(2,"GND1_HOST","power_in","L"),(3,"INA","input","L"),(4,"INB","input","L"),(5,"INC","input","L"),(6,"OUTD","output","L"),(7,"EN1","input","L"),(8,"GND1_HOST","power_in","L"),(16,"VCC2_AFE","power_in","R"),(15,"GND2_AFE","power_in","R"),(14,"OUTA","output","R"),(13,"OUTB","output","R"),(12,"OUTC","output","R"),(11,"IND","input","R"),(10,"EN2","input","R"),(9,"GND2_AFE","power_in","R")],
"opa":[(3,"IN+","input","L"),(4,"IN-","input","L"),(5,"V+","power_in","L"),(2,"V-","power_in","L"),(1,"OUT","output","R")]
})
# Final component realization, 14 October 2026. Kept in this new package only.
SOURCES['opa2']='https://www.ti.com/lit/ds/symlink/opa2192.pdf'
SOURCES['buf']='https://www.ti.com/lit/ds/symlink/opa391.pdf'
SOURCES['schmitt']='https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf'
SOURCES['diode']='https://www.diodes.com/datasheet/download/BAT54WS.pdf'
FP.update({'opa2':'Package_SO:VSSOP-8_2.3x2mm_P0.5mm','buf':'Package_TO_SOT_SMD:SOT-353_SC-70-5','schmitt':'Package_TO_SOT_SMD:SOT-23-5','diode':'Diode_SMD:D_SOD-323'})
PINS['opa2']=[(3,'INA+','input','L'),(2,'INA-','input','L'),(5,'INB+','input','L'),(6,'INB-','input','L'),(8,'V+','power_in','L'),(4,'V-','power_in','L'),(1,'OUTA','output','R'),(7,'OUTB','output','R')]
PINS['buf']=[(1,'IN+','input','L'),(3,'IN-','input','L'),(5,'V+','power_in','L'),(2,'V-','power_in','L'),(4,'OUT','output','R')]
PINS['schmitt']=[(2,'A','input','L'),(5,'VCC','power_in','L'),(3,'GND','power_in','L'),(1,'NC','no_connect','L'),(4,'Y','output','R')]
PINS['diode']=[(2,'A','passive','L'),(1,'K','passive','R')]
PINS['iso']=[(1,'VCC1','power_in','L'),(2,'GND1','power_in','L'),(3,'INA','input','L'),(4,'INB','input','L'),(5,'OUTC','output','L'),(6,'OUTD','output','L'),(7,'EN1','input','L'),(8,'GND1','power_in','L'),(16,'VCC2','power_in','R'),(15,'GND2','power_in','R'),(14,'OUTA','output','R'),(13,'OUTB','output','R'),(12,'INC','input','R'),(11,'IND','input','R'),(10,'EN2','input','R'),(9,'GND2','power_in','R')]
# Layout is assigned after pagination; all nets remain ordinary native global nets.
def A(ref,value,kind,nets,sheet,desc):
 if kind=='diode':nets={1:nets[3],2:nets[1]};value='BAT54WS-7-F'
 add(ref,value,kind,nets,(0,0),sheet,desc)
def R(ref,val,a,b,sheet,desc):A(ref,val,'R',{1:a,2:b},sheet,desc)
def C(ref,val,a,b,sheet,desc):A(ref,val,'C',{1:a,2:b},sheet,desc)
def J(ref,val,nets,sheet,desc):A(ref,val,'J',dict(enumerate(nets,1)),sheet,desc)
def buffer(ref,node,out,sheet,v='SUP_5',g='GND'):
 A(ref,'OPA391DCKR','buf',{1:node,2:g,3:out,4:out,5:v},sheet,'Unity threshold buffer; actual DC errors and rail-valid startup are retained')
 C('C'+ref[1:],'100n X7R 16V',v,g,sheet,'Local OPA391 supply bypass')
gate_count=1000
logic_records=[]
def gate(kind,ins,out,sheet,desc,v='SUP_3V3',g='GND'):
 global gate_count
 ref='U'+str(gate_count);gate_count+=1
 if kind=='inv':nets={1:None,2:ins[0],3:g,4:out,5:v}
 elif kind=='and3':nets={1:ins[0],2:g,3:ins[1],4:out,5:v,6:ins[2]}
 else:nets={1:ins[0],2:ins[1],3:g,4:out,5:v}
 A(ref,LOGIC_VALUES[kind],kind,nets,sheet,desc)
 C('C'+ref[1:],'100n X7R 16V',v,g,sheet,'Local logic bypass for '+ref)
 logic_records.append({'ref':ref,'kind':kind,'inputs':ins,'output':out,'supply':v,'ground':g})
 return ref
def AND(ins,out,sheet,desc,v='SUP_3V3',g='GND'):
 ins=list(ins)
 if len(ins)==1:return gate('and2',[ins[0],v],out,sheet,desc,v,g)
 while len(ins)>3:
  tmp=out+'_G'+str(len(ins));gate('and3',ins[:3],tmp,sheet,desc,v,g);ins=[tmp]+ins[3:]
 return gate('and3' if len(ins)==3 else 'and2',ins,out,sheet,desc,v,g)
def INV(a,b,sheet,v='SUP_3V3',g='GND'):return gate('inv',[a],b,sheet,'Native logical inversion; no physical-state inference',v,g)
def FF(ref,clk,d,clr,out,sheet,pre='SUP_3V3',outn=None,v='SUP_3V3',g='GND'):
 A(ref,LOGIC_VALUES['ff'],'ff',{1:clk,2:d,3:outn,4:g,5:out,6:clr,7:pre,8:v},sheet,'Actual edge/async latch. Health return cannot supply a raw rearm clock')
 C('C'+ref[1:],'100n X7R 16V',v,g,sheet,'Local FF bypass')
# Root interfaces, separate host/supervisor and floating AFE domains.
J('J1','EXTERNAL SUPERVISOR AND HOST RAILS',['SUP_3V3','SUP_5','HOST_3V3','HOST_5','HOST_15','VH_24','GND'],'root','Always-on supervisor supplies remain external; generators are the next package')
J('J2','FLOATING AFE RAILS AND OBSERVED CONTROLS',['AFE_3V3','AFE_P5','AFE_N5','AFEAGND','AFE_CONNECT','AFE_ACQUIRE'],'root','Receive-side actual control nets, not host command copies; separate electrical island')
J('J3','RAW CONTROL / STATUS',['SUP_REARM','FAULT_RESET','WDI','CH0_REQUEST','CH1_REQUEST','CH0_RUN','CH1_RUN','CH0_ROUTE_LOCKED','CH1_ROUTE_LOCKED','CH0_PHASE_REARM','CH1_PHASE_REARM','GND'],'root','Distinct raw rearm and fault reset; no automatic retry or opposite phase')
J('J4','EXISTING MONITOR OBSERVATIONS',['CH0_I_MON','CH1_I_MON','MON_VMID','MON_VREF','MON0_PERMIT','MON1_PERMIT','CH0_MON_SUP_OK','CH1_MON_SUP_OK','GND'],'root','Map existing MID2.048V, REF4.096V, current scale40V/A; monitor supervisory health excludes ARM to avoid circular startup')
J('J5','EXPORTED NATIVE HEALTH / PERMISSION',['RESET_READY','RAILS_QUALIFIED','WATCHDOG_OK','AFE_ISOLATED_READY','CH0_QUIESCENT_OK','CH1_QUIESCENT_OK','CH0_EXT_SUP_OK','CH1_EXT_SUP_OK','SUP_ARMED','CH0_ALLOW','CH1_ALLOW','GLOBAL_GUARD_EN','GND'],'root','AFE_ISOLATED_READY means conditional blank-voltage/control qualification, never proof of open switches')
J('J6','DRIVER INTERNAL DIFFERENTIAL VOLTAGES',['CH0_A_BR','CH0_B_BR','CH1_A_BR','CH1_B_BR','GND'],'root','Internal driver-terminal compliance probe; not a body voltage/current or guard continuity sensor')
# All eighteen body conductors receive a protected source-side guard.
for bank in range(5):
 s='guards';b=100+bank; n={11:'VH_24',2:'GND',3:'GND',17:'GND',10:'GUARD_FAULT_N'}
 for leg,(sp,dp,sel) in enumerate(((1,16,15),(12,13,14),(9,8,7),(4,5,6))):
  k=bank*4+leg
  if k<18:
   name=f'STIM{k:02d}' if k<16 else f'RETURN{k-16}'
   n[sp]='BODY_'+name;n[dp]='ROUTED_'+name;n[sel]='GLOBAL_GUARD_EN'
  else:n[sp]=n[dp]=n[sel]='GND'
 A(f'U{b}','TMUX7412FRRPR','hv',n,s,'S pins face body; D pins face canonical router/monitor path. Off still has leakage/capacitance and welded-path limits')
 C(f'C{b}','100n X7R 50V','VH_24','GND',s,'Guard local high-voltage supply bypass')
 R(f'R{b}','22k','GLOBAL_GUARD_EN','GND',s,'Passive guard enable low when logic is absent; not rail-off isolation proof')
J('J100','CANONICAL ROUTER J7 / BEFORE GUARDS',[f'ROUTED_STIM{k:02d}' for k in range(16)]+['ROUTED_RETURN0','ROUTED_RETURN1'],'guards','All18routerJ7outputs pass through this guard; existing monitor shunts remain upstream, never duplicated')
J('J101','BODY-FACING ARTIFICIAL LOAD CONTACTS',[f'BODY_STIM{k:02d}' for k in range(16)]+['BODY_RETURN0','BODY_RETURN1'],'guards','Digital research fixture connector, not an implant connector; no REF/BIAS stimulation return')
R('R110','1k','SUP_3V3','GUARD_FAULT_N','guards','Single pullup for five shared open-drain FF outputs; fault flag is not switch continuity')
# Rail windows. Two independent threshold dividers per rail, wired-AND fault outputs.
rail_specs=[('SUP3','SUP_3V3',3.10,3.50,'host_rails'),('SUP5','SUP_5',4.75,5.25,'host_rails'),('H3','HOST_3V3',3.10,3.50,'host_rails'),('H5','HOST_5',4.75,5.25,'host_rails'),('H15','HOST_15',13.5,16.5,'host_rails'),('H24','VH_24',22.8,25.2,'host_rails'),('A3','AFE_3V3',3.34,3.54,'afe_rails'),('AP','AFE_P5',5.20,5.42,'afe_rails'),('AN','AFE_NMAG',.475,.550,'afe_rails')]
for i,(name,node,lo,hi,s) in enumerate(rail_specs):
 afe=s=='afe_rails';v='AFE_3V3' if afe else 'SUP_3V3';g='AFEAGND' if afe else 'GND';b=200+i
 A(f'U{b}','TPS3700DDCR','rail',{1:name+'_RAIL_OK',2:g,3:name+'_UV',4:name+'_OV',5:v,6:name+'_RAIL_OK'},s,'Independent 400mV-reference UV/OV window; falling hysteresis/input-bias/reference tolerance are studied')
 for j,(th,suffix) in enumerate(((lo,'UV'),(hi,'OV'))):
  top=(th/.4-1)*10000
  R(f'R{b*10+j*2}',f'{top:.6g}R 0.1%',node,name+'_'+suffix,s,'Threshold upper resistor; exact provisional resistance, MPN/series realization follows in PCB package')
  R(f'R{b*10+j*2+1}','10k 0.1%',name+'_'+suffix,g,s,'Low impedance threshold lower resistor limits comparator bias error')
 R(f'R{b*10+4}','10k',v,name+'_RAIL_OK',s,'Wired-AND open-drain output pullup')
 C(f'C{b}','100n X7R 16V',v,g,s,'Supervisor local bypass')
# Negative rail sample = -0.1*AFE_N5; common mode stays close to island ground.
A('U220','OPA391DCKR','buf',{1:'AFEAGND',2:'AFEAGND',3:'AFE_NINV',4:'AFE_NMAG',5:'AFE_3V3'},'afe_rails','Inverting negative-rail magnitude observation, gain0.1; dependent on valid island opamp supply')
R('R2200','100k 0.1%','AFE_N5','AFE_NINV','afe_rails','Negative rail sense input')
R('R2201','10k 0.1%','AFE_NMAG','AFE_NINV','afe_rails','Magnitude feedback gain0.1')
C('C220','100n X7R 16V','AFE_3V3','AFEAGND','afe_rails','Magnitude opamp local bypass')
def startup(prefix,s,v,g,b):
 R(f'R{b}','100k 1%',v,prefix+'_RC',s,'Power-on hold resistor; 47nF tolerance and Schmitt threshold define a finite delay')
 C(f'C{b}','47n X7R 10%',prefix+'_RC',g,s,'Power-on hold capacitor; no universal brownout timing proof')
 A(f'D{b}','BAT54,215','diode',{1:prefix+'_RC',2:None,3:prefix+'_DIS'},s,'Fast rail-loss discharge, actual diode leakage/forward voltage remain bounded assumptions')
 R(f'R{b+1}','100R',prefix+'_DIS',v,s,'Discharge current limiting')
 A(f'U{b}','SN74LVC1G17DBVR','schmitt',{1:None,2:prefix+'_RC',3:g,4:prefix+'_STARTUP_OK',5:v},s,'Schmitt startup hold, no MCU-controlled qualification')
 C(f'C{b+1}','100n X7R 16V',v,g,s,'Schmitt local bypass')
startup('SUP','watchdog','SUP_3V3','GND',250)
startup('AFE','afe_rails','AFE_3V3','AFEAGND',260)
AND([n+'_RAIL_OK' for n in ('SUP3','SUP5','H3','H5','H15','H24')]+['SUP_STARTUP_OK'],'HOST_RAILS_OK','watchdog','All host/supervisor supplies qualified with native windows and startup hold')
AND(['A3_RAIL_OK','AP_RAIL_OK','AN_RAIL_OK','AFE_STARTUP_OK'],'AFE_RAIL_LOCAL_OK','afe_logic','Native isolated-island rail status','AFE_3V3','AFEAGND')
# Watchdog: actual falling edges, startup-gated enable and a heartbeat-seen FF.
A('U300','TPS3431SDRBR','wd',{1:'SUP_3V3',2:'WD_CWD',3:'HOST_RAILS_OK',4:'GND',5:'SUP_3V3',6:'WDI',7:'WD_ENOUT_OK',8:'WD_ENOUT_OK',9:'GND'},'watchdog','WDO and ENOUT wired-AND; fixed200ms nominal watchdog, not a microsecond phase limiter')
R('R300','10k','SUP_3V3','WD_CWD','watchdog','SET1high and CWD10ktoVDD select170..230ms timeout')
R('R301','10k','SUP_3V3','WD_ENOUT_OK','watchdog','Shared open-drain watchdog/startup output pullup')
R('R302','10k','WDI','GND','watchdog','Absent heartbeat remains low; only actual falling edges reset watchdog')
C('C300','100n X7R 16V','SUP_3V3','GND','watchdog','Watchdog local bypass')
INV('WDI','WDI_N','watchdog')
AND(['WD_ENOUT_OK','HOST_RAILS_OK'],'WD_SEEN_CLR_N','watchdog','A heartbeat seen before valid startup is discarded')
FF('U301','WDI_N','WD_ENOUT_OK','WD_SEEN_CLR_N','WD_SEEN','watchdog')
AND(['WD_ENOUT_OK','WD_SEEN','HOST_RAILS_OK'],'WD_GOOD','watchdog','No startup high-Z state is accepted as heartbeat evidence')
AND(['WD_GOOD'],'WATCHDOG_OK','watchdog','Export actual watchdog qualification')
# Quiet windows referenced to existing4.096V reference. +/-10mV is not zero current.
R('R400','203.8k 0.1%','MON_VREF','QUIET_HI_DIV','quiescence','Shared current threshold ladder top')
R('R401','2k 0.1%','QUIET_HI_DIV','QUIET_LO_DIV','quiescence','20mV separation around2.048V nominal')
R('R402','203.8k 0.1%','QUIET_LO_DIV','GND','quiescence','Shared current threshold ladder bottom')
buffer('U400','QUIET_HI_DIV','QUIET_HI','quiescence');buffer('U401','QUIET_LO_DIV','QUIET_LO','quiescence')
for ch in (0,1):
 q=lambda n:f'CH{ch}_{n}';b=410+ch
 A(f'U{b}','TLV3202DGKR','cmp',{1:q('QUIET_HI_OK'),2:q('I_MON'),3:'QUIET_HI',4:'GND',5:q('I_MON'),6:'QUIET_LO',7:q('QUIET_LO_OK'),8:'SUP_5'},'quiescence','Observed INA currentwindow;5V outputs enter only5.5V-tolerant LVCinputs')
 C(f'C{b}','100n X7R 16V','SUP_5','GND','quiescence','Comparator local bypass')
 AND([q('QUIET_HI_OK'),q('QUIET_LO_OK'),f'MON{ch}_PERMIT'],q('QUIET_RAW'),'quiescence','Quiet additionally requires existing actual monitor permit')
 R(f'R{b}','3.3k 1%',q('QUIET_RAW'),q('QUIET_RC'),'quiescence','Provisional dwell resistor, not proof of tissue-charge relaxation')
 C(f'C{b+10}','10n C0G 5%',q('QUIET_RC'),'GND','quiescence','Finite quiet qualification hold')
 A(f'D{b}','BAT54,215','diode',{1:q('QUIET_RC'),2:None,3:q('QUIET_DIS')},'quiescence','Fast quiet-loss discharge; positive retained voltage belowSchmittlow required')
 R(f'R{b+10}','100R',q('QUIET_DIS'),q('QUIET_RAW'),'quiescence','Quiet-discharge limiter')
 A(f'U{b+10}','SN74LVC1G17DBVR','schmitt',{1:None,2:q('QUIET_RC'),3:'GND',4:q('QUIESCENT_OK'),5:'SUP_3V3'},'quiescence','Dwell qualified finite current band; comparator error forbids calling this exact zero')
 C(f'C{b+20}','100n X7R 16V','SUP_3V3','GND','quiescence','Quiet Schmitt bypass')
# Differential compliance observation; both channels are one real OPA2192.
R('R500','232k 0.1%','MON_VREF','PAIR_HI_DIV','voltage','Shared differential threshold top')
R('R501','536k 0.1%','PAIR_HI_DIV','PAIR_LO_DIV','voltage','Nominal±22V threshold separation aftergain.0499')
R('R502','232k 0.1%','PAIR_LO_DIV','GND','voltage','Shared differential threshold bottom')
buffer('U500','PAIR_HI_DIV','PAIR_HI','voltage');buffer('U501','PAIR_LO_DIV','PAIR_LO','voltage')
A('U502','OPA2192IDGKR','opa2',{1:'CH0_VPAIR',2:'CH0_DIFF_N',3:'CH0_DIFF_P',4:'GND',5:'CH1_DIFF_P',6:'CH1_DIFF_N',7:'CH1_VPAIR',8:'SUP_5'},'voltage','Two real difference amplifiers, VPAIR=MID+.0499*(A_BR-B_BR); input matching and rail validity explicit')
C('C502','100n X7R 16V','SUP_5','GND','voltage','OPA2192 local bypass')
for ch in (0,1):
 q=lambda n:f'CH{ch}_{n}';b=510+ch*10
 R(f'R{b}','1M 0.1%',q('A_BR'),q('DIFF_P'),'voltage','Positive-terminal differential input')
 R(f'R{b+1}','49.9k 0.1%','MON_VMID',q('DIFF_P'),'voltage','Offset leg; matching affects common-mode rejection')
 R(f'R{b+2}','1M 0.1%',q('B_BR'),q('DIFF_N'),'voltage','Negative-terminal differential input')
 R(f'R{b+3}','49.9k 0.1%',q('VPAIR'),q('DIFF_N'),'voltage','Feedback gain.0499')
 A(f'U{b}','TLV3202DGKR','cmp',{1:q('PAIR_HI_OK'),2:q('VPAIR'),3:'PAIR_HI',4:'GND',5:q('VPAIR'),6:'PAIR_LO',7:q('PAIR_LO_OK'),8:'SUP_5'},'voltage','Internal driver differential compliance window, never body-voltage proof')
 C(f'C{b}','100n X7R 16V','SUP_5','GND','voltage','Pair comparator local bypass')
 AND([q('PAIR_HI_OK'),q('PAIR_LO_OK')],q('PAIR_OK'),'voltage','Independent voltage window admitted only while supervisor rails are valid')
# Seventeen actual RHD-side window taps with acknowledged resistive loading.
for k in range(17):
 name=f'REC{k:02d}' if k<16 else 'REF';s='afe_bank'+str(k//4);b=600+k
 node=f'AFE_IN{k:02d}_P' if k<16 else 'AFE_REF';sense=f'{name}_SENSE';hi=f'{name}_HI_OK';lo=f'{name}_LO_OK'
 J(f'J{b}',name+' ACTUAL RHD-SIDE TAP',[node,'AFEAGND'],s,'Physical same node as RHD input, after clamp selector, not pre-clamp protected node or command copy')
 R(f'R{b*10}','10M 0.1%',node,sense,s,'Added window-probe load;3.45V bias through11Mohm gives~.314uA at zero input')
 R(f'R{b*10+1}','1M 0.1%','AFE_3V3',sense,s,'Sense=(10*AFE3V3+VIN)/11, threshold loading and comparator bias explicitly modelled')
 A(f'U{b}','TLV3202DGKR','cmp',{1:hi,2:sense,3:'AFE_WIN_HI',4:'AFEAGND',5:sense,6:'AFE_WIN_LO',7:lo,8:'AFE_P5'},s,'Both outputs high only in measured RHD-side DC band; not open-switch or chronic safety proof')
 C(f'C{b}','100n X7R 16V','AFE_P5','AFEAGND',s,'Window comparator bypass at5.30V nominal, absolute5.5V supply bound')
 AND([hi,lo],name+'_DC_OK',s,'Physical node window under stated offset/bias/loading bounds','AFE_3V3','AFEAGND')
R('R700','9.50k 0.1%','AFE_3V3','AFE_WIN_HI_DIV','afe_logic','Upper threshold from actual3.45V nominal island logic rail')
R('R701','100k 0.1%','AFE_WIN_HI_DIV','AFEAGND','afe_logic','Upper threshold divider bottom')
R('R702','10.5k 0.1%','AFE_3V3','AFE_WIN_LO_DIV','afe_logic','Lower threshold from actual3.45V nominal island logic rail')
R('R703','100k 0.1%','AFE_WIN_LO_DIV','AFEAGND','afe_logic','Lower threshold divider bottom')
buffer('U700','AFE_WIN_HI_DIV','AFE_WIN_HI','afe_logic','AFE_P5','AFEAGND');buffer('U701','AFE_WIN_LO_DIV','AFE_WIN_LO','afe_logic','AFE_P5','AFEAGND')
INV('AFE_CONNECT','AFE_CONNECT_LOW','afe_logic','AFE_3V3','AFEAGND');INV('AFE_ACQUIRE','AFE_ACQUIRE_LOW','afe_logic','AFE_3V3','AFEAGND')
AND([f'REC{k:02d}_DC_OK' for k in range(16)]+['REF_DC_OK'],'AFE_ALL_DC_OK','afe_logic','All17 actual RHD input/reference DC windows','AFE_3V3','AFEAGND')
AND(['AFE_ALL_DC_OK','AFE_CONNECT_LOW','AFE_ACQUIRE_LOW','AFE_RAIL_LOCAL_OK'],'AFE_BLANK_LOCAL_OK','afe_logic','Observed low receive-side controls plus observed DC windows, conditional healthy-switch blanking only','AFE_3V3','AFEAGND')
A('U710','ISO6742FDWR','iso',{1:'SUP_3V3',2:'GND',3:'GND',4:'GND',5:'AFE_RAIL_OBS_OK',6:'AFE_BLANK_OBS_OK',7:'SUP_3V3',8:'GND',9:'AFEAGND',10:'AFE_3V3',11:'AFE_BLANK_LOCAL_OK',12:'AFE_RAIL_LOCAL_OK',13:None,14:None,15:'AFEAGND',16:'AFE_3V3'},'afe_logic','Two independent reverse status channels; F default-low on valid receiving supply with absent input side; no isolated power')
C('C710','100n X7R 16V','SUP_3V3','GND','afe_logic','Host isolator bypass');C('C711','100n X7R 16V','AFE_3V3','AFEAGND','afe_logic','Island isolator bypass')
# Actual secondary timers independent of each driver's original timer resistor.
for ch in (0,1):
 q=lambda n:f'CH{ch}_{n}';b=800+ch
 A(f'U{b}','LTC6993HS6-1#TRPBF','timer',{1:q('REQUEST'),2:'GND',3:q('SEC_SET'),4:q('SEC_DIV'),5:'SUP_3V3',6:q('SEC_TIMER')},'duration','Independent nonretriggerable timer triggered by rawREQUEST, never health-gated trigger')
 R(f'R{b*10}','195.4k 0.1%',q('SEC_SET'),'GND','duration','Secondary durationnom250.112us, worstfinitefullmodelbound264us')
 R(f'R{b*10+1}','976k 0.1%','SUP_3V3',q('SEC_DIV'),'duration','DIVcode2 top')
 R(f'R{b*10+2}','182k 0.1%',q('SEC_DIV'),'GND','duration','DIVcode2 bottom,NDIV64')
 C(f'C{b}','100n X7R 16V','SUP_3V3','GND','duration','Secondary timer local bypass')
 INV(q('SEC_TIMER'),q('SEC_N'),'duration')
 gate('or',[q('TIMEOUT'),q('REQUEST')],q('TIMEOUT_D'),'duration','Held request at secondary expiration latches timeout')
 FF(f'U{810+ch}',q('SEC_N'),q('TIMEOUT_D'),'TIMEOUT_CLR_N',q('TIMEOUT'),'duration')
# Global admission and quiet reset. Separate sensing-health avoids monitor deadlock.
AND(['HOST_RAILS_OK','AFE_RAIL_OBS_OK'],'RAILS_QUALIFIED','admission','Both power domains actually observed')
AND(['HOST_RAILS_OK','AFE_RAIL_OBS_OK','WD_GOOD'],'RESET_READY','admission','Native startup/rails/heartbeat qualification, not ARM or raw phase command')
AND(['AFE_BLANK_OBS_OK'],'AFE_ISOLATED_READY','admission','Conditional healthy-switch blanking alias; welded-at-zero counterexample retained')
AND(['HOST_RAILS_OK','AFE_BLANK_OBS_OK','WD_GOOD','GUARD_FAULT_N','CH0_PAIR_OK','CH1_PAIR_OK'],'SENSE_HEALTH','admission','Sense health can recover without ARM or MON_PERMIT, enabling independent monitor rearm')
AND(['SENSE_HEALTH'],'CH0_MON_SUP_OK','admission','Map to monitoring-cell J3pin1 ONLY, never driver EXT_SUP_OK')
AND(['SENSE_HEALTH'],'CH1_MON_SUP_OK','admission','Map to monitoring-cell J3pin2 ONLY, never driver EXT_SUP_OK')
AND(['SENSE_HEALTH','MON0_PERMIT','MON1_PERMIT'],'RAW_HEALTH','admission','Final health includes both actual existing monitor latch outputs')
for ch in (0,1):
 for n in ('REQUEST','RUN','SEC_TIMER'):INV(f'CH{ch}_{n}',f'CH{ch}_{n}_N','admission')
AND([f'CH{ch}_{n}_N' for ch in (0,1) for n in ('REQUEST','RUN','SEC_TIMER')],'NO_ACTIVITY','admission','Both phases and secondary timers must actually be low before quiet reset')
AND(['RAW_HEALTH','CH0_QUIESCENT_OK','CH1_QUIESCENT_OK','NO_ACTIVITY'],'SAFE_IDLE','admission','Independent observed quiet band, no raw requests, RUN or secondary timer')
AND(['FAULT_RESET','SAFE_IDLE'],'TIMEOUT_RESET','admission','Timeout clear only by deliberate quiet fault reset')
INV('TIMEOUT_RESET','TIMEOUT_CLR_N','admission')
INV('CH0_TIMEOUT','CH0_NO_TIMEOUT','admission');INV('CH1_TIMEOUT','CH1_NO_TIMEOUT','admission')
AND(['RAW_HEALTH','CH0_NO_TIMEOUT','CH1_NO_TIMEOUT'],'ARM_CLR_N','admission','Health loss or secondary timeout consumes global arm')
FF('U900','SUP_REARM','SAFE_IDLE','ARM_CLR_N','SUP_ARMED','admission')
for ch in (0,1):
 s=f'phase{ch}';q=lambda n:f'CH{ch}_{n}'
 AND(['RAW_HEALTH','SUP_ARMED',q('ROUTE_LOCKED')],q('PHASE_HEALTH'),s,'Admission includes held route ownership, not physical mux continuity')
 AND([q('SEC_TIMER'),q('REQUEST_N')],q('ENDED'),s,'Normal request fall while secondary timer remains high consumes phase block')
 INV(q('ENDED'),q('STOP_N'),s)
 AND([q('PHASE_HEALTH'),q('STOP_N')],q('BLOCK_PRE_N'),s,'Asynchronous block set on fault or phase end')
 AND([q('PHASE_REARM'),q('PHASE_HEALTH'),q('QUIESCENT_OK'),q('REQUEST_N'),q('RUN_N'),q('SEC_TIMER_N')],q('PHASE_REARM_SAFE'),s,'Explicit rearm while source quiet; no raw phase activity')
 INV(q('PHASE_REARM_SAFE'),q('BLOCK_CLR_N'),s)
 FF(f'U{910+ch}','GND','GND',q('BLOCK_CLR_N'),q('BLOCK'),s,pre=q('BLOCK_PRE_N'))
 INV(q('BLOCK'),q('NO_BLOCK'),s)
 AND([q('PHASE_HEALTH'),q('NO_BLOCK'),q('NO_TIMEOUT'),q('REQUEST'),q('SEC_TIMER'),q('RUN')],q('ALLOW'),s,'One actual driver phase admitted through an independent secondary duration gate')
 AND(['RAW_HEALTH','SUP_ARMED',q('NO_TIMEOUT')],q('EXT_SUP_OK'),s,'Driver supervisory output remains phase independent so original driver can rearm')
gate('or',['CH0_ALLOW','CH1_ALLOW'],'GLOBAL_GUARD_EN','admission','Any allowed phase connects all18body conductors; any commonhealthfault clears globalarm and allguards')
# Explicit low defaults on external controls and observations where valid supply exists.
for i,node in enumerate(['SUP_REARM','FAULT_RESET','CH0_PHASE_REARM','CH1_PHASE_REARM','CH0_REQUEST','CH1_REQUEST','CH0_RUN','CH1_RUN','CH0_ROUTE_LOCKED','CH1_ROUTE_LOCKED','MON0_PERMIT','MON1_PERMIT']):R(f'R{950+i}','10k',node,'GND','defaults','Absent external control/permission is low; no universal power-off or stuck-pin proof')
# Paginate native parts: 30 cells per A2 sheet, spacing preserves visible pin labels.
base_order=['root','guards','host_rails','afe_rails','watchdog','quiescence','voltage','duration','admission','phase0','phase1',*[f'afe_bank{k}' for k in range(5)],'afe_logic','defaults']
title_base={'root':'System interfaces and conditional handoff','guards':'All18 body-facing terminal guards','host_rails':'Native host and supervisor rail windows','afe_rails':'Native floating AFE supply windows','watchdog':'Heartbeat, startup hold and observed seen latch','quiescence':'Observed finite current band and dwell','voltage':'Internal differential compliance observation','duration':'Independent secondary phase duration','admission':'Global sticky health and deliberate rearm','phase0':'Source0 phase consumption and independent permission','phase1':'Source1 phase consumption and independent permission','afe_logic':'Physical DC windows and isolated status','defaults':'External control safe defaults'}
SHEETS=[];TITLES={}
for base in base_order:
 group=[p for p in parts if p['sheet']==base]
 chunk=6 if base=='root' else (len(group)+((len(group)+29)//30)-1)//((len(group)+29)//30)
 for page in range((len(group)+chunk-1)//chunk):
  sh=base if page==0 else base+'_'+str(page+1);SHEETS.append(sh)
  TITLES[sh]=title_base.get(base,'RHD-side measured input windows '+base[-1])+(' / '+str(page+1) if page else '')
  for i,p in enumerate(group[page*chunk:(page+1)*chunk]):
   p['sheet']=sh
   p['xy']=(76.2+(i%3)*177.8,78.74+(i//3)*121.92) if base=='root' else (60.96+(i%5)*109.22,68.58+(i//5)*55.88)

short_titles={'root':'Interfaces and handoff','guards':'18 body-side terminal guards','host_rails':'Host supply windows','afe_rails':'AFE supply windows','watchdog':'Heartbeat and startup','quiescence':'Current quiet window','voltage':'Differential compliance','duration':'Secondary phase duration','admission':'Sticky permission and rearm','phase0':'Source 0 phase permission','phase1':'Source 1 phase permission','afe_logic':'AFE blank and isolated status','defaults':'External defaults'}
for sh in SHEETS:
 base=sh[:-2] if sh.endswith('_2') else sh
 TITLES[sh]=short_titles.get(base,'RHD input windows '+base[-1])+(' / 2' if sh.endswith('_2') else '')
for stale in OUT.glob('*.kicad_sch'):
 if stale.stem not in set(SHEETS)-{'root'}|{PROJECT} and 'scci_rh_stage4_supervision' in stale.read_text(encoding='utf-8'):
  assert stale.resolve().parent==OUT.resolve();stale.unlink()
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
    text=f'(symbol "SCCI_RH_SUP:{name}" (pin_names (offset 0.7)) (in_bom yes) (on_board yes) (property "Reference" "{name[0]}" (at 0 0 0) {FONT}) (property "Value" "{p["value"]}" (at 0 0 0) {FONT}) (property "Footprint" "{p["footprint"]}" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "{name}_0_1" {graphic}) (symbol "{name}_1_1" '
    for n,nm,kind,x,y,a in pins:text+=f'(pin {kind} line (at {fnum(x)} {fnum(y)} {a}) (length 2.54) (name "{nm}" (effects (font (size 0.85 0.85)))) (number "{n}" {FONT})) '
    return text+'))'
def glabel(net,x,y,key,left=False):return f'(global_label "{net}" (shape bidirectional) (at {fnum(x)} {fnum(y)} {180 if left else 0}) (effects (font (size 0.85 0.85)) (justify {"right" if left else "left"})) (uuid {uid(key)}))'
local=OUT/"scci_rh_sup.pretty";local.mkdir(exist_ok=True)
# Manufacturer-derived guard package snapshot copied from the closed recording slice.
custom="Texas_RRP0016A_WQFN16_4x4_P0.65_EP2.6"
(local/(custom+".kicad_mod")).write_text((OUT.parent/"recording-front-end"/"scci_rh_afe.pretty"/(custom+".kicad_mod")).read_text(encoding="utf-8"),encoding="utf-8")
# TI DRB0008A recommended land pattern, not a generic longer exposed pad.
wdname="Texas_DRB0008A_VSON8_3x3_P0.65_EP1.5x1.75"
wd='(footprint "'+wdname+'" (version 20260206) (generator "scci_rh_supervision") (layer "F.Cu") (descr "TI TPS3431 DRB0008A example board layout: 3x3 body,0.65pitch,EP1.5x1.75;mask/paste/assembly unqualified") (attr smd) (property "Reference" "REF**" (at 0 -2.3 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15)))) (property "Value" "'+wdname+'" (at 0 2.3 0) (layer "F.Fab") (effects (font (size 1 1) (thickness .15)))) (fp_rect (start -1.5 -1.5) (end 1.5 1.5) (stroke (width .1) (type default)) (fill none) (layer "F.Fab")) (fp_rect (start -1.7 -1.7) (end 1.7 1.7) (stroke (width .05) (type default)) (fill none) (layer "F.CrtYd")) '
for n in range(1,9):
 x=-1.1 if n<=4 else 1.1;y=(n-2.5)*.65 if n<=4 else (6.5-n)*.65
 wd+=f'(pad "{n}" smd roundrect (at {x} {y}) (size .6 .31) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio .2)) '
wd+='(pad "9" smd rect (at 0 0) (size 1.5 1.75) (layers "F.Cu" "F.Paste" "F.Mask")))'
(local/(wdname+".kicad_mod")).write_text(wd+"\n",encoding="utf-8")
for part in parts:
 if part["kind"]=="wd":part["footprint"]="scci_rh_sup:"+wdname
 lib,name=part["footprint"].split(":")
 if lib!="scci_rh_sup":
  source=SHARE/"footprints"/(lib+".pretty")/(name+".kicad_mod");assert source.is_file(),source
  (local/(name+".kicad_mod")).write_text(source.read_text(encoding="utf-8"),encoding="utf-8")
 part["footprint"]="scci_rh_sup:"+name
flag_symbol='(symbol "SCCI_RH_SUP:SUPPLIED_RAIL" (pin_names (offset 0)) (in_bom no) (on_board no) (property "Reference" "#FLG" (at 0 0 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNAL_QUALIFIED_RAIL" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol "SUPPLIED_RAIL_0_1" (polyline (pts (xy -1 1) (xy 0 2) (xy 1 1)) (stroke (width 0.2) (type default)) (fill (type none)))) (symbol "SUPPLIED_RAIL_1_1" (pin power_out line (at 0 0 90) (length 0) (name "SUPPLIED" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))'
for sheet in SHEETS:
    sid=ROOT_ID if sheet=="root" else uid(sheet+"-document")
    path="/"+ROOT_ID if sheet=="root" else "/"+ROOT_ID+"/"+uid(sheet+"-sheet")
    elements=[]
    for p in [p for p in parts if p["sheet"]==sheet]:
        ref=p["ref"];x,y=p["xy"];pins=pin_positions(p);top=y-max(v[4] for v in pins)-5.08;bottom=y-min(v[4] for v in pins)+5.08
        inst=f'(symbol (lib_id "SCCI_RH_SUP:{ref}") (at {fnum(x)} {fnum(y)} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {fnum(x)} {fnum(top)} 0) {FONT}) (property "Value" "{p["value"]}" (at {fnum(x)} {fnum(bottom)} 0) (effects (font (size 0.95 0.95)))) (property "Footprint" "{p["footprint"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) (property "Datasheet" "{p["source_url"]}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size 1 1)) hide)) '
        for n,nm,kind,px,py,a in pins:
            xx,yy=x+px,y-py;net=p["nets"][n];inst+=f'(pin "{n}" (uuid {uid(ref+"-pin-"+n)})) '
            if net is None:elements.append(f'(no_connect (at {fnum(xx)} {fnum(yy)}) (uuid {uid(ref+"-nc-"+n)}))')
            else:
                ex=xx+(-5.08 if px<0 else 5.08)
                elements.append(f'(wire (pts (xy {fnum(xx)} {fnum(yy)}) (xy {fnum(ex)} {fnum(yy)})) (stroke (width 0) (type default)) (uuid {uid(ref+"-wire-"+n)}))')
                elements.append(glabel(net,ex,yy,ref+"-label-"+n,left=px<0))
        elements.append(inst+f'(instances (project "{PROJECT}" (path "{path}" (reference "{ref}") (unit 1)))))')
    texts=[("DIGITAL SCCI ENGINEERING / ARTIFICIAL LOADS / NATIVE INDEPENDENT SUPERVISION",20.32,17.78,1.5),("18 guarded stimulation conductors, 17 measured RHD-side windows; conditional healthy-switch blanking is not proven isolation.",20.32,25.4,1)]
    if sheet=="root":
        for i,net in enumerate(("SUP_3V3","SUP_5","HOST_3V3","HOST_5","HOST_15","VH_24","GND","AFE_3V3","AFE_P5","AFE_N5","AFEAGND")):
            x,y=25.4+(i%6)*91.44,241.3+(i//6)*15.24;ref=f"#FLG{i+1}"
            elements.append(f'(symbol (lib_id "SCCI_RH_SUP:SUPPLIED_RAIL") (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {uid(ref)}) (property "Reference" "{ref}" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (property "Value" "EXTERNALLY_SUPPLIED" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (pin "1" (uuid {uid(ref+"-pin")})) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (reference "{ref}") (unit 1)))))')
            elements.append(glabel(net,x,y,ref+"-label"))
        for i,name in enumerate(SHEETS[1:]):
            x=20.32+(i%3)*185.42;y=279.4+(i//3)*12.7
            elements.append(f'(sheet (at {fnum(x)} {fnum(y)}) (size 157.48 3.81) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {uid(name+"-sheet")}) (property "Sheetname" "{name}" (at {fnum(x)} {fnum(y-1.27)} 0) (effects (font (size .85 .85)) (justify left bottom))) (property "Sheetfile" "{name}.kicad_sch" (at {fnum(x)} {fnum(y+5.08)} 0) (effects (font (size .85 .85)) (justify left top))) (instances (project "{PROJECT}" (path "/{ROOT_ID}" (page "{i+2}")))))')
    else:
        texts += [("All net labels are native electrical connections. Actual physical delay, leakage, failed switches and shared supplies remain bounded limitations.",20.32,391.16,1),("Independent phase cap, heartbeat watchdog, rail windows and deliberate rearm have different functions. No automatic retry or reverse pulse.",20.32,398.78,1)]
    for i,(text,x,y,size) in enumerate(texts):elements.append(f'(text "{text}" (at {fnum(x)} {fnum(y)} 0) (effects (font (size {size} {size})) (justify left)) (uuid {uid(sheet+"-text-"+str(i))}))')
    embedded="".join(lib_symbol(p) for p in parts if p["sheet"]==sheet)+(flag_symbol if sheet=="root" else "")
    data=f'(kicad_sch (version 20250114) (generator "scci_rh_stage4_supervision") (uuid {sid}) (paper "A2") (title_block (title "Project SCCI RH S4 / {TITLES[sheet]}") (date "2026-10-14") (rev "0.1") (company "Project SCCI RH") (comment 1 "Native supervision; converters, firmware, PCB and implant qualification remain")) (lib_symbols {embedded}) '+"".join(elements)+')\n'
    (OUT/(PROJECT if sheet=="root" else sheet)).with_suffix(".kicad_sch").write_text(data,encoding="utf-8")
(OUT/"SCCI_RH_SUP.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "scci_rh_stage4_supervision") '+("".join(lib_symbol(p) for p in parts)+flag_symbol).replace('(symbol "SCCI_RH_SUP:', '(symbol "')+')\n',encoding="utf-8")
(OUT/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "SCCI_RH_SUP") (type "KiCad") (uri "${KIPRJMOD}/SCCI_RH_SUP.kicad_sym") (options "") (descr "Package-specific original route circuit pin symbols; primary PDFs in connectivity.json")))\n',encoding="utf-8")
(OUT/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "scci_rh_sup") (type "KiCad") (uri "${KIPRJMOD}/scci_rh_sup.pretty") (options "") (descr "KiCad library footprint snapshots; PCB assembly and mask/paste qualification remain")))\n',encoding="utf-8")
(OUT/(PROJECT+".kicad_pro")).write_text(json.dumps({"meta":{"filename":PROJECT+".kicad_pro","version":1},"erc":{"rule_severities":{"single_global_label":"warning","four_way_junction":"warning","simulation_model_issue":"warning","footprint_filter":"warning"}}},indent=2)+"\n",encoding="utf-8")
manifest={'schema':'scci_rh.stage4.supervision.connectivity.v1','date':'2026-10-14','scope':'Native18conductorguard/17RHDwindow independent supervision; artificial signals and loads; conditionalhealthy-switch blanking, not implant qualification','parts':parts,'source_documents':SOURCES,'logic_records':logic_records,'rail_specs':[dict(name=n,node=x,low_V=l,high_V=h,domain='AFE' if s=='afe_rails' else 'host') for n,x,l,h,s in rail_specs],'nominal':{'guard_paths':18,'RHD_window_taps':17,'SUP_3V3_V':3.3,'SUP_5_V':5.0,'AFE_3V3_V':3.45,'AFE_P5_V':5.30,'AFE_N5_V':-5.10,'secondary_RSET_ohm':195400,'secondary_NDIV':64,'secondary_nominal_s':250.112e-6,'quiet_I_nominal_A':.000250,'quiet_dwell_R_ohm':3300,'quiet_dwell_C_F':10e-9,'startup_R_ohm':100000,'startup_C_F':47e-9,'pair_gain':.0499,'pair_nominal_limit_V':22,'RHD_probe_to_input_ohm':1e7,'RHD_probe_to_bias_ohm':1e6,'quiet_allocation_s':200e-6},'control_contract':{'sense_health':'HOST_RAILS_OK&AFE_BLANK_OBS_OK&WD_GOOD&GUARD_FAULT_N&CH0_PAIR_OK&CH1_PAIR_OK','raw_health':'SENSE_HEALTH&MON0_PERMIT&MON1_PERMIT','safe_idle':'RAW_HEALTH&CH0_QUIESCENT_OK&CH1_QUIESCENT_OK&!REQ0&!REQ1&!RUN0&!RUN1&!SEC0&!SEC1','arm':'rawSUP_REARM rising capturesSAFE_IDLE; asyncCLR RAW_HEALTH&!TIMEOUT0&!TIMEOUT1','monitor_health':'SENSE_HEALTH beforeARM/MON_PERMIT, avoiding circular startup','driver_EXT_SUP_OK':'RAW_HEALTH&SUP_ARMED&!TIMEOUTx; distinct frommonitorEXT_SUP_OK','guard_enable':'CH0_ALLOW|CH1_ALLOW','allow':'RAW_HEALTH&SUP_ARMED&ROUTE_LOCKEDx&!BLOCKx&!TIMEOUTx&REQx&SECx&RUNx','afe_blank':'actualreceiveCONNECTlow &ACQUIRElow &all17measuredDCwindows &localnativeRAIL_OK; healthy-switchassumption','isolation_limit':'welded-at-zero and unsensed alternate tissue paths remain possible; observedDC is not proof of open analog switch'},'external_unimplemented':['supervisor/host/isolatedAFE converters and physical sequencing outside declared valid rails','healthyanalogswitch assumption: no welded/stuck switch proof','body/DCleakage/parasitic coupling and physical charge bound','finite comparator propagation nearthreshold/metastability/setuphold/rail ramp behavior','exact passive MPN, matchedresistor arrays, thermal EMC and PCB assembly','complete monitoringADCtransport and nRFfirmware','electrode biological signal sufficiency or retainedlearning/physiological efficacy']}
(OUT/'connectivity.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
with (OUT/'bom.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['reference','value','footprint','sheet','description','primary_source'])
 for p in parts:w.writerow([p['ref'],p['value'],p['footprint'],p['sheet'],p['description'],p['source_url']])
print(json.dumps({'components':len(parts),'pins':sum(len(p['pins']) for p in parts),'sheets':len(SHEETS),'root':str(OUT/(PROJECT+'.kicad_sch'))}))
