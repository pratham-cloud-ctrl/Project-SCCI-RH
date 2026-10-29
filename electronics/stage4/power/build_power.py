"""Generate the native battery/DC and nine-rail power package.

This new saved-file design does not alter historical circuit packages and does
not credit a module isolation rating as implant/body leakage qualification.
"""
from pathlib import Path
import csv, json, os, re, uuid
OUT=Path(__file__).resolve().parent
SHARE=Path(os.environ.get('KICAD_SHARE',r'E:\project workspace assests\EDA\KiCAD\share\kicad'))
PROJECT='power'
def uid(key):return str(uuid.uuid5(uuid.NAMESPACE_URL,'project-scci-rh/stage4/power/'+key))
ROOT_ID=uid('root')
parts=[]
SOURCES={}
FP={'R':'Resistor_SMD:R_0805_2012Metric','C':'Capacitor_SMD:C_1206_3216Metric','L':'Inductor_SMD:L_Bourns-SRP5030TA','D':'Diode_SMD:D_SMA'}
PINS={}
def add(ref,value,kind,nets,sheet,description):
 if kind=='J':fp=f'Connector_PinHeader_2.54mm:PinHeader_1x{len(nets):02d}_P2.54mm_Vertical';pins=[(i,str(i),'passive','L') for i in sorted(nets)]
 elif kind in ('R','C','L','F','SW'):fp=FP[kind];pins=[(1,'1','passive','L'),(2,'2','passive','R')]
 else:fp=FP[kind];pins=PINS[kind]
 assert {str(p[0]) for p in pins}=={str(n) for n in nets},(ref,nets)
 assert ref not in {p['ref'] for p in parts},ref
 parts.append(dict(ref=ref,value=value,kind=kind,footprint=fp,nets={str(k):v for k,v in nets.items()},pins=pins,xy=(0,0),sheet=sheet,description=description,source_url=SOURCES.get(kind,'')))
def R(ref,val,a,b,s,d):add(ref,val,'R',{1:a,2:b},s,d)
def C(ref,val,a,b,s,d):add(ref,val,'C',{1:a,2:b},s,d)
def J(ref,val,ns,s,d):add(ref,val,'J',dict(enumerate(ns,1)),s,d)
# Component construction below is intentionally explicit and primary-pin-audited.
SOURCES.update({'buck':'https://www.ti.com/lit/ds/symlink/tps62160.pdf','buck3':'https://www.ti.com/lit/ds/symlink/tps62130a.pdf','boost':'https://www.analog.com/media/en/technical-documentation/data-sheets/8330f.pdf','pos':'https://www.ti.com/lit/ds/symlink/tps7a49.pdf','neg':'https://www.ti.com/lit/ds/symlink/tps7a30.pdf','iso':'https://www.tracopower.com/products/tmr3.pdf','D':'https://www.diodes.com/assets/Datasheets/ds13003.pdf'})
FP.update({'buck':'Package_SO:VSSOP-8_3x3mm_P0.65mm','buck3':'Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm','boost':'Package_TO_SOT_SMD:TSOT-23-6','pos':'Package_SO:Texas_DGN0008D_VSSOP-8-1EP_3x3mm_P0.65mm_EP2x2.94mm_Mask1.57x1.89mm','neg':'Package_SO:Texas_DGN0008D_VSSOP-8-1EP_3x3mm_P0.65mm_EP2x2.94mm_Mask1.57x1.89mm','iso':'scci_rh_power:TRACO_TMR3_SIP8_21.8x9.1_P2.54','F':'Fuse:Fuse_1206_3216Metric','SW':'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical','L':'Inductor_SMD:L_Bourns_SRP5030T'})
PINS['buck']=[(1,'PGND','power_in','L'),(2,'VIN','power_in','L'),(3,'EN','input','L'),(4,'AGND','power_in','L'),(5,'FB','input','L'),(6,'VOS','input','R'),(7,'SW','output','R'),(8,'PG','open_collector','R')]
PINS['boost']=[(1,'SW','open_collector','R'),(2,'GND','power_in','L'),(3,'FBX','input','L'),(4,'EN_UVLO','input','L'),(5,'INTVCC','power_out','R'),(6,'VIN','power_in','L')]
PINS['iso']=[(1,'VIN_MINUS','power_in','L'),(2,'VIN_PLUS','power_in','L'),(3,'REMOTE_CURRENT','input','L'),(5,'NC','no_connect','R'),(6,'VOUT_PLUS','power_out','R'),(7,'AFE_RETURN','power_out','R'),(8,'VOUT_MINUS','power_out','R')]
for kind in ('pos','neg'):
 PINS[kind]=[(1,'OUT','power_out','R'),(2,'FB','input','L'),(3,'NC','no_connect','L'),(4,'GND','power_in','L'),(5,'EN','input','L'),(6,'NR_SS','passive','L'),(7,'DNC','no_connect','L'),(8,'IN','power_in','L'),(9,'EP_GND','passive','L')]
PINS['D']=[(1,'K','passive','R'),(2,'A','passive','L')]

def buck(ref,node,vin,en,top,bottom,sheet):
 b=int(ref[1:]);fb=node+'_FB';sw=node+'_SW';pg=node+'_PG'
 add(ref,'TPS62160DGKR','buck',{1:'GND',2:vin,3:en,4:'GND',5:fb,6:node,7:sw,8:pg},sheet,'1A DCS-Control buck; PG is diagnostic and hi-Z while off, not independent rail qualification')
 add('L'+str(b),'2.2uH SRP5030T-2R2M','L',{1:sw,2:node},sheet,'Buck energy-storage inductor; current and effective capacitance bounds require PCB characterization')
 C('C'+str(b*10),'10u X7R 25V',vin,'GND',sheet,'Input ceramic; effective >=2.2uF under bias assumption')
 C('C'+str(b*10+1),'22u X7R 16V',node,'GND',sheet,'Output ceramic; effective >=10uF under bias assumption')
 R('R'+str(b*10),str(top)+'R 0.1%',node,fb,sheet,'0.8V feedback upper; assembly tolerance included in study')
 R('R'+str(b*10+1),str(bottom)+'R 0.1%',fb,'GND',sheet,'Feedback bottom resistor')
 R('R'+str(b*10+2),'100k','SUP_3V3',pg,sheet,'PG output pullup to independent supervisor rail')
 R('R'+str(b*10+3),'47k',node,'GND',sheet,'Finite discharge bleed; not a guaranteed shutdown time')
PINS['buck3']=[(1,'SW1','output','R'),(2,'SW2','passive','R'),(3,'SW3','passive','R'),(4,'PG','open_collector','R'),(5,'FB','input','L'),(6,'AGND','power_in','L'),(7,'FSW','input','L'),(8,'DEF','input','L'),(9,'SS_TR','passive','L'),(10,'AVIN','power_in','L'),(11,'PVIN1','power_in','L'),(12,'PVIN2','power_in','L'),(13,'EN','input','L'),(14,'VOS','input','R'),(15,'PGND1','power_in','L'),(16,'PGND2','power_in','L'),(17,'EP_GND','passive','L')]
PINS['rail']=[(1,'OUTA_UV_N','open_collector','R'),(2,'GND','power_in','L'),(3,'INA_UV','input','L'),(4,'INB_OV','input','L'),(5,'VDD','power_in','L'),(6,'OUTB_OV_N','open_collector','R')]
PINS['and2']=[(1,'A','input','L'),(2,'B','input','L'),(3,'GND','power_in','L'),(4,'Y','output','R'),(5,'VCC','power_in','L')]
PINS['and3']=[(1,'A','input','L'),(2,'GND','power_in','L'),(3,'B','input','L'),(4,'Y','output','R'),(5,'VCC','power_in','L'),(6,'C','input','L')]
PINS['schmitt']=[(1,'NC','no_connect','L'),(2,'A','input','L'),(3,'GND','power_in','L'),(4,'Y','output','R'),(5,'VCC','power_in','L')]
SOURCES.update({'rail':'https://www.ti.com/lit/ds/symlink/tps3700.pdf','and2':'https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf','and3':'https://www.ti.com/lit/ds/symlink/sn74lvc1g11.pdf','schmitt':'https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf','smallD':'https://www.diodes.com/assets/Datasheets/BAT54WS.pdf'})
FP.update({'rail':'Package_TO_SOT_SMD:SOT-23-6','and2':'Package_TO_SOT_SMD:SOT-23-5','and3':'Package_TO_SOT_SMD:SOT-23-6','schmitt':'Package_TO_SOT_SMD:SOT-23-5','smallD':'Diode_SMD:D_SOD-323'})
PINS['smallD']=PINS['D']
PINS['inputD']=PINS['D'];PINS['boostD']=PINS['D']
FP['inputD']='Diode_SMD:D_SMC';FP['boostD']='Diode_SMD:D_SOD-323F'
SOURCES['inputD']='https://www.vishay.com/docs/88751/ss32.pdf';SOURCES['boostD']='https://assets.nexperia.com/documents/data-sheet/PMEG6010CEJ.pdf'
PINS['odbuf']=[(1,'NC','no_connect','L'),(2,'A','input','L'),(3,'GND','power_in','L'),(4,'Y_OPEN_DRAIN','open_collector','R'),(5,'VCC','power_in','L')]
FP['odbuf']='Package_TO_SOT_SMD:SOT-23-5';SOURCES['odbuf']='https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf'
# External protected pack or current-limited DC source; no onboard charging.
J('J1','AT31004 PROTECTED 2S PACK / 6.4 TO 8.4V',['PACK_POS','GND'],'root','External Tenergy protected7.4V2.6Ahpack; offboardTLP2000charger; use keyed power wiring in finalPCB')
add('F1','2A FUSE 1206','F',{1:'PACK_POS',2:'PACK_FUSED'},'input','2A seriesinputfuse; exactfuseI2t/inrushcoordination remainsPCB/fixturequalification')
add('D1','SS34-E3/57T','inputD',{1:'PACK_REVERSE_OK',2:'PACK_FUSED'},'input','Series reverse polarity diode; forwarddropandheatinbudget, notidealreverseprotection')
add('SW1','MASTER SPST / OFFBOARD','SW',{1:'PACK_REVERSE_OK',2:'PACK_BUS'},'input','External master switch at2pinheader disconnects input; residualrailcapacitors remainenergized')
C('C1','100u 16V LOW ESR','PACK_BUS','GND','input','Inputbulk capacitor; effective80uFandESR0.1ohm are modelingassumptions, inrushnotunconditional')
C('C2','100n X7R 25V','PACK_BUS','GND','input','Localhighfrequencyinputbypass')
J('J2','POWER REQUEST / STATUS',['PWR_REQUEST','SUP_READY','BATT_OK','HOST_ENABLE','BOOST_ENABLE','HOST_3V3_PG','HOST_5_PG','SUP_3V3_PG','SUP_5_PG','SUP_3V3','PWR_FAULT_N','GND'],'root','PWR_REQUESTbenchjumpertoSUP3.3; activeenablehasnoARMfeedbackloop. PGdiagnosticsarenotninerailextsupervision')
J('J3','HOST AND SUPERVISOR RAILS',['SUP_3V3','SUP_5','HOST_3V3','HOST_5','HOST_15','VH_24','GND'],'root','SameorderedrailinterfaceassupervisionJ1; noinputpinpretendsgeneratedpower')
J('J4','FLOATING RECORDING RAILS',['AFE_3V3','AFE_P5','AFE_N5','AFEAGND'],'root','Separatefloatingdomain; noDCgroundtie, noUSBchargingconnectionorhumanconnection')
J('J6','EXISTING MONITOR REFERENCES',['MON_VREF','MON_VMID','GND'],'root','ActualexistingREF3440/OPA391voltagetaps; windowsaffectinterlock,neverconverterenable')
J('J5','CONVERTER TEST POINTS',['PACK_BUS','ISO_P12','ISO_N12','AFEAGND','GND'],'root','Testportsdonotbridgegrounds; useappropriateisolatedtestequipmentinanyfuturebenchwork')
# Supervisor converters remain on while the master is on, independent of host enable.
buck('U100','SUP_3V3','PACK_BUS','PACK_BUS',31250,10000,'sup3')
buck('U101','SUP_5','PACK_BUS','PACK_BUS',52500,10000,'sup5')
buck('U102','HOST_3V3','PACK_BUS','HOST_ENABLE',31250,10000,'host3')
# 3A host5 supplies the recording-island converter; each physical SW/VIN pin is explicit.
add('U110','TPS62130ARGTR','buck3',{1:'HOST_5_SW',2:'HOST_5_SW',3:'HOST_5_SW',4:'HOST_5_PG',5:'HOST_5_FB',6:'GND',7:'GND',8:'GND',9:'HOST_5_SS',10:'PACK_BUS',11:'PACK_BUS',12:'PACK_BUS',13:'HOST_ENABLE',14:'HOST_5',15:'GND',16:'GND',17:'GND'},'host5','3A DCS-Controlbuck; SS3.3nFnominal; physicalphase/enablesauditedagainstTI')
add('L110','2.2uH SRP5030T-2R2M','L',{1:'HOST_5_SW',2:'HOST_5'},'host5','Buckinductor saturation/DCRandtransientlimitsinprimaryreview')
for i,val,a,b in [(1100,'10u X7R 25V','PACK_BUS','GND'),(1101,'22u X7R 16V','HOST_5','GND'),(1102,'100n X7R 25V','PACK_BUS','GND'),(1103,'3.3n C0G 50V','HOST_5_SS','GND')]:C('C'+str(i),val,a,b,'host5','HOST5input/outputorsoftstartcapacitor')
R('R1100','52.5k 0.1%','HOST_5','HOST_5_FB','host5','0.8Vupperfeedbackresistor')
R('R1101','10k 0.1%','HOST_5_FB','GND','host5','Feedbackbottom')
R('R1102','100k','SUP_3V3','HOST_5_PG','host5','PGpullup; mustANDwithHOST_ENABLEbecauseoff-statePGishiZ')
R('R1103','47k','HOST_5','GND','host5','Finiteoutputbleed, moduleinputloadchangesactualdecay')
# Native battery and supervisor UV/OV qualification, separate from final nine rail supervision.
rail_specs=[('BATT','PACK_POS',6.6,8.6),('S3','SUP_3V3',3.10,3.50),('S5','SUP_5',4.75,5.25),('MREF','MON_VREF',3.98,4.22),('MID','MON_VMID',1.98,2.12)]
for i,(name,node,lo,hi) in enumerate(rail_specs):
 b=200+i
 add('U'+str(b),'TPS3700DDCR','rail',{1:name+'_WINDOW_OK',2:'GND',3:name+'_UV',4:name+'_OV',5:'SUP_3V3',6:name+'_WINDOW_OK'},'enable','Native400mVUV/OVwindow; startuphysteresis/bias/referencecornersarefinite')
 for j,(th,suf) in enumerate(((lo,'UV'),(hi,'OV'))):
  R('R'+str(b*10+2*j),f'{(th/.4-1)*10000:.6g}R 0.1%',node,name+'_'+suf,'enable','Windowupperdivider')
  R('R'+str(b*10+2*j+1),'10k 0.1%',name+'_'+suf,'GND','enable','Windowbottomdivider')
 R('R'+str(b*10+4),'10k','SUP_3V3',name+'_WINDOW_OK','enable','Wired-ANDUV/OVoutputpullup')
 C('C'+str(b),'100n X7R 16V','SUP_3V3','GND','enable','Railmonitorbypass')
# Schmitt power-on hold clears default-low enable through finite rise/fall model.
R('R230','100k 1%','SUP_3V3','PWR_START_RC','enable','Hardwarestartuphold')
C('C230','47n X7R 10%','PWR_START_RC','GND','enable','Startupqualificationcapacitor')
add('D230','BAT54WS-7-F','smallD',{1:'PWR_START_DIS',2:'PWR_START_RC'},'enable','Faststartupnode discharge afterrailfall; diodeleakageretainedaslimitation')
R('R231','100R','PWR_START_DIS','SUP_3V3','enable','Dischargecurrentlimit')
add('U230','SN74LVC1G17DBVR','schmitt',{1:None,2:'PWR_START_RC',3:'GND',4:'PWR_START_OK',5:'SUP_3V3'},'enable','Hardwarepoweronhold; noMCUcreditedforqualification')
add('U231','SN74LVC1G11DBVR','and3',{1:'S3_WINDOW_OK',2:'GND',3:'S5_WINDOW_OK',4:'SUP_READY',5:'SUP_3V3',6:'PWR_START_OK'},'enable','NativeSUPrailwindowsANDstartuphold')
add('U232','SN74LVC1G08DBVR','and2',{1:'BATT_WINDOW_OK',2:'PWR_START_OK',3:'GND',4:'BATT_OK',5:'SUP_3V3'},'enable','Batteryhealthgatedbyhardwarestartup')
add('U233','SN74LVC1G11DBVR','and3',{1:'PWR_REQUEST',2:'GND',3:'BATT_OK',4:'HOST_ENABLE',5:'SUP_3V3',6:'SUP_READY'},'enable','ExplicitrequestANDbatteryANDsupervisorreadiness; nocircularsystemARMcondition')
add('U234','SN74LVC1G08DBVR','and2',{1:'HOST_ENABLE',2:'HOST_5_PG',3:'GND',4:'BOOST_ENABLE',5:'SUP_3V3'},'enable','BothHOST_ENABLEandactualHOST5PGrequired; PGhi-Zoffcannotenableboost')
for n in range(230,235):C('C'+str(n+10),'100n X7R 16V','SUP_3V3','GND','enable','Logiclocalbypass')
for i,node in enumerate(('PWR_REQUEST','HOST_ENABLE','BOOST_ENABLE')):R('R'+str(240+i),'10k',node,'GND','enable','Passiveabsent-controldefaultlow; power-offbackfeedstillrequiresPCBtest')
# Open-drain power interlock joins the frozen supervisor guard-fault wired net.
add('U235','SN74LVC1G07DBVR','odbuf',{1:None,2:'POWER_RUN_OK',3:'GND',4:'PWR_FAULT_N',5:'SUP_3V3'},'enable','Open-drain LOW on power-request/qualificationloss immediatelyconsumesexistingglobalARM; releaseisnotrearm')
C('C245','100n X7R 16V','SUP_3V3','GND','enable','Powerinterlocklocalbypass')
add('U236','SN74LVC1G08DBVR','and2',{1:'MREF_WINDOW_OK',2:'MID_WINDOW_OK',3:'GND',4:'REF_OK',5:'SUP_3V3'},'enable','Existing4.096Vreferenceand2.048Vmidpointbothqualified; noweakindependentaccuracyclaim')
add('U237','SN74LVC1G08DBVR','and2',{1:'BOOST_ENABLE',2:'REF_OK',3:'GND',4:'POWER_RUN_OK',5:'SUP_3V3'},'enable','Referencequalificationonlyinhibitsguardinterlock; neverblocksconverterstartup')
C('C246','100n X7R 16V','SUP_3V3','GND','enable','Referencestatuslogicbypass')
C('C247','100n X7R 16V','SUP_3V3','GND','enable','Power-runlogicbypass')
# Two independent positive boosts; ENlow does not block input-diode conduction to output.
for b,node,top in ((300,'HOST_15',418750),(301,'VH_24',700000)):
 s='boost15' if b==300 else 'boost24';sw=node+'_SW';fb=node+'_FB';vcc=node+'_INTVCC'
 add('U'+str(b),'LT8330ES6#TRPBF','boost',{1:sw,2:'GND',3:fb,4:'BOOST_ENABLE',5:vcc,6:'PACK_BUS'},s,'40Vinternal switch2MHzboost. ENlowstopsconversionbutdoesnotdisconnectdiodepathorresidualcharge')
 add('L'+str(b),'4.7uH SRP5030T-4R7M','L',{1:'PACK_BUS',2:sw},s,'Boostinductortopology; finiteCCM/DCMcurrentbudgetdoesnotreplacephysicalloopstability')
 add('D'+str(b),'PMEG6010CEJ','boostD',{1:node,2:sw},s,'60V1ArectifyingSchottky; surgeandlayoutqualificationremain')
 C('C'+str(b*10),'10u X7R 25V','PACK_BUS','GND',s,'Boostinputceramic')
 C('C'+str(b*10+1),'22u X7R 50V',node,'GND',s,'Reservoir1; combinedeffective30uFminimumassumed')
 C('C'+str(b*10+2),'22u X7R 50V',node,'GND',s,'Reservoir2; combinedESR0.1ohmassumed')
 C('C'+str(b*10+3),'1u X7R 10V',vcc,'GND',s,'Internal5Vregulatorbypassperdatasheet')
 R('R'+str(b*10),str(top)+'R 0.1%',node,fb,s,'1.6Vboostreferenceupperdivider; provisionalexactresistance')
 C('C'+str(b*10+4),'4.7p C0G 50V',node,fb,s,'FeedforwardupperresistorcapperLT8330boostexample; layoutdependent')
 R('R'+str(b*10+1),'50k 0.1%',fb,'GND',s,'Lowerfeedback; 25k..1Mohmdatasheetrange')
 R('R'+str(b*10+2),'100k',node,'GND',s,'Outputbleeddoesnotguaranteezerooutputwithbatteryconnected')
# Regulated module isolates the AFE power return; REMOTE is not a TTL input.
add('U400','TMR3-0522','iso',{1:'GND',2:'HOST_5',3:None,5:None,6:'ISO_P12',7:'AFEAGND',8:'ISO_N12'},'island','Regulated5Vto+/-12V125mAeachfunctional-isolationmodule. RemoteNCmeansON; removeHOST5toendinputpower')
C('C400','22u X7R 16V','HOST_5','GND','island','Moduleinputbypassandlocalenergy')
C('C401','10u X7R 50V','ISO_P12','AFEAGND','island','Positiveisolatedoutputceramic')
C('C402','10u X7R 50V','ISO_N12','AFEAGND','island','Negativeisolatedoutputceramic; noelectrolyticpolarityerror')
for b,kind,node,vin,top,s in [(410,'pos','AFE_3V3','ISO_P12',19113.92405063291,'afe3'),(411,'pos','AFE_P5','ISO_P12',34725.73839662447,'afep'),(412,'neg','AFE_N5','ISO_N12',33367.34693877551,'afen')]:
 fb=node+'_FB';nr=node+'_NR'
 add('U'+str(b),'TPS7A4901DGNR' if kind=='pos' else 'TPS7A3001DGNR',kind,{1:node,2:fb,3:None,4:'AFEAGND',5:vin,6:nr,7:None,8:vin,9:'AFEAGND'},s,'AdjustablelownoiseLDO; ENtiedowninput(negativepolarityforTPS7A30); full+/-2.5%cornercansafelyinhibituntilquiescenttrim')
 C('C'+str(b*10),'10u X7R 50V',vin,'AFEAGND',s,'LDOlocalinputcap')
 C('C'+str(b*10+1),'10u X7R 16V',node,'AFEAGND',s,'LDOpulseloadoutputcap; effective>=2.2uFminimumassumed')
 C('C'+str(b*10+2),'10n C0G 50V',nr,'AFEAGND',s,'Noise-reduction/softstart')
 C('C'+str(b*10+3),'10n C0G 50V',node,fb,s,'Feedforwardcapperlow-noiseapplication')
 R('R'+str(b*10),f'{top:.8g}R 0.1%',node,fb,s,'Replaceabletrimselectionupperresistor; nominalisnotfull-toleranceguarantee')
 R('R'+str(b*10+1),'10k 0.1%',fb,'AFEAGND',s,'Feedbackbottom>5uAminimumfornegativeLDO')
 R('R'+str(b*10+2),'47k',node,'AFEAGND',s,'Finiteislandrailbleed')
 J('J'+str(b),'QUIESCENT TRIM / TEST ONLY',[node,fb,'AFEAGND'],s,'MeasureandselectRtopwithbodydisconnectedtoachievetarget+/-0.5%qualificationcondition; nocalibrationwhilearmed')
# Original circuit pages remain immutable; final inter-package wiring is root-owned.
base_order=['root','input','sup3','sup5','host3','host5','enable','boost15','boost24','island','afe3','afep','afen']
title_base={'root':'Interfaces and rail handoff','input':'Protected pack and input disconnect','sup3':'Always-on supervisor 3.3 V','sup5':'Always-on supervisor 5 V','host3':'Host logic 3.3 V','host5':'Host and module input 5 V','enable':'Native battery and startup qualification','boost15':'Host 15 V boost','boost24':'Stimulation 24 V boost','island':'Floating recording power module','afe3':'Floating AFE 3.45 V regulator','afep':'Floating AFE +5.30 V regulator','afen':'Floating AFE -5.10 V regulator'}
SHEETS=[];TITLES={}
for base in base_order:
 group=[p for p in parts if p['sheet']==base];limit=6 if base=='root' else 24
 pages=(len(group)+limit-1)//limit;chunk=(len(group)+pages-1)//pages
 for page in range(pages):
  sh=base if page==0 else base+'_'+str(page+1);SHEETS.append(sh);TITLES[sh]=title_base[base]+(' / '+str(page+1) if page else '')
  for i,p in enumerate(group[page*chunk:(page+1)*chunk]):
   p['sheet']=sh;p['xy']=(76.2+(i%3)*177.8,78.74+(i//3)*121.92) if base=='root' else (63.5+(i%4)*137.16,68.58+(i//4)*55.88)
# A manufacturer-derived SIP module land pattern is explicit rather than an invented generic package.
local=OUT/'scci_rh_power.pretty';local.mkdir(exist_ok=True)
mod='(footprint "TRACO_TMR3_SIP8_21.8x9.1_P2.54" (version 20260206) (generator "scci_rh_stage4_power") (layer "F.Cu") (descr "TRACO TMR3 standardSIP pinlocations,2.54mmgrid,body21.8x9.1mm;height11.2mm;noisolationclearancequalification") (attr through_hole) (property "Reference" "REF**" (at 8.89 -3.5 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15)))) (property "Value" "TMR3-0522" (at 8.89 8 0) (layer "F.Fab") (effects (font (size 1 1) (thickness .15)))) (fp_rect (start -2.01 -2.3) (end 19.79 6.8) (stroke (width .1) (type default)) (fill none) (layer "F.Fab")) (fp_rect (start -2.26 -2.55) (end 20.04 7.05) (stroke (width .05) (type default)) (fill none) (layer "F.CrtYd")) '
for n in (1,2,3,5,6,7,8):mod+=f'(pad "{n}" thru_hole {"rect" if n==1 else "circle"} (at {(n-1)*2.54} 0) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask")) '
(local/'TRACO_TMR3_SIP8_21.8x9.1_P2.54.kicad_mod').write_text(mod+')\n',encoding='utf-8')
exec((OUT/'native_render.py').read_text(encoding='utf-8'),globals())
manifest={'schema':'scci_rh.stage4.power.connectivity.v1','date':'2026-10-14','scope':'Nativeprotectedbattery/DC,independentSUP,hostandfloatingAFEpower;artificialsignalsandloads;notimplantqualification','parts':parts,'source_documents':SOURCES,'rail_specs':[{'name':n,'node':x,'low_V':l,'high_V':h} for n,x,l,h in rail_specs],'nominal':{'PACK_nominal_V':7.4,'PACK_min_V':6.4,'PACK_max_V':8.4,'PACK_capacity_Ah':2.6,'PACK_energy_Wh':19.24,'SUP_3V3_V':3.3,'SUP_5_V':5,'HOST_3V3_V':3.3,'HOST_5_V':5,'HOST_15_V':15,'VH_24_V':24,'ISO_P12_V':12,'ISO_N12_V':-12,'AFE_3V3_V':3.45,'AFE_P5_V':5.30,'AFE_N5_V':-5.10,'boost_reservoir_effective_F':30e-6,'boost_reservoir_ESR_ohm':.1,'input_bulk_effective_F':80e-6,'AFE_trim_target_fraction':.005},'control_contract':{'SUP_READY':'S3_WINDOW_OK&S5_WINDOW_OK&PWR_START_OK','BATT_OK':'BATT_WINDOW_OK&PWR_START_OK','HOST_ENABLE':'PWR_REQUEST&BATT_OK&SUP_READY','BOOST_ENABLE':'HOST_ENABLE&HOST_5_PG','REF_OK':'MREF_WINDOW_OK&MID_WINDOW_OK','POWER_RUN_OK':'BOOST_ENABLE&REF_OK','PWR_FAULT_N':'SN74LVC1G07open-drainoutputLOWif!POWER_RUN_OK;wiretosupervisionGUARD_FAULT_N','TMR_remote':'NC/open=ON;HOST5buckinputremovalendsinputpower;notTTL','LDO_enable':'tiedownrawinput;negativepolarityTPS7A30','supervision':'allninefinalrailsstillqualifiedbyhistoricalsupervisionpackage;noARMfeedbackloop'},'external_unimplemented':['ActualbatteryprotectionI2t/fuse/charge/inrushbenchqualification','Converterloopstabilityandtransient/ripple/EMIphysicalmeasurements','FullLDO+/-2.5%cornerscanfailAFEwindows;quiescentresistorselection+/-0.5%operatingrailisanexplicitcondition','BoostENdoesnotdisconnectinputdiodepath;storedenergyandmoduledecayremain','Functionalmoduleisolationratingdoesnotproveclinicalleakageorbodyisolation','ExactpassiveMPNs/resistorseriesselectionandPCBthermalassemblyqualification','Transportfirmware,integratedPCB,populatedCADandbiologicalefficacy']}
(OUT/'connectivity.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
with (OUT/'bom.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['reference','value','footprint','sheet','description','primary_source'])
 for p in parts:w.writerow([p['ref'],p['value'],p['footprint'],p['sheet'],p['description'],p['source_url']])
print(json.dumps({'components':len(parts),'pins':sum(len(p['pins']) for p in parts),'sheets':len(SHEETS),'root':str(OUT/(PROJECT+'.kicad_sch'))}))
