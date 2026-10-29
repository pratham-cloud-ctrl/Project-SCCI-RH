"""Build the pin-audited BT40F/nRF5340 carrier and physical sideband chain.

The module's actual manufacturer pad names are retained. This is a digital
bench carrier, not an implant layout or a radio qualification.
"""
from pathlib import Path
import csv, hashlib, json, os, uuid
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
SHARE=Path(os.environ.get('KICAD_SHARE',r'E:\project workspace assests\EDA\KiCAD\share\kicad'))
PROJECT='controller_carrier'
def uid(key): return str(uuid.uuid5(uuid.NAMESPACE_URL,'project-scci-rh/stage4/controller-carrier/'+key))
ROOT_ID=uid('root'); parts=[]; SOURCES={}; PINS={}
FP={'R':'Resistor_SMD:R_0805_2012Metric','C':'Capacitor_SMD:C_1206_3216Metric'}
def add(ref,value,kind,nets,sheet,description):
 if kind=='J':
  fp=f'Connector_PinHeader_2.54mm:PinHeader_1x{len(nets):02d}_P2.54mm_Vertical'
  pins=[(str(i),str(i),'passive','L') for i in nets]
 elif kind in ('R','C'):
  fp=FP[kind]; pins=[('1','1','passive','L'),('2','2','passive','R')]
 else: fp=FP[kind]; pins=PINS[kind]
 assert {str(p[0]) for p in pins}=={str(n) for n in nets},ref
 parts.append(dict(ref=ref,value=value,kind=kind,footprint=fp,nets={str(k):v for k,v in nets.items()},pins=pins,xy=(0,0),sheet=sheet,description=description,source_url=SOURCES.get(kind,'')))
def R(ref,val,a,b,s,d): add(ref,val,'R',{1:a,2:b},s,d)
def C(ref,val,a,b,s,d): add(ref,val,'C',{1:a,2:b},s,d)
def J(ref,val,ns,s,d): add(ref,val,'J',dict(enumerate(ns,1)),s,d)
SOURCES['module']='https://www.fanstel.com/s/BT40F_BT40N-Product-Specifications.pdf'
SOURCES['sideband']='https://www.ti.com/lit/gpn/sn74lvc165a'
FP['module']='scci_rh_controller:BT40F_Manufacturer_66Pad'
FP['sideband']='Package_SO:TSSOP-16_4.4x5mm_P0.65mm'
pad_functions={
 '1':'P1.02','2':'P1.03','3':'NC_XL1_INTERNAL','4':'NC_XL2_INTERNAL',
 '5':'P0.04','6':'P0.05','7':'P0.02','8':'P0.03','9':'VDD','10':'GND',
 '11':'P0.09','12':'P0.11','13':'P0.30','14':'RESET_N','15':'SWCLK','16':'SWDIO',
 'Z0':'P1.09','Z1':'P1.10','Z2':'P1.11','Z3':'P1.12','Z4':'P1.13','Z5':'P1.14','Z6':'P1.15',
 'A0':'GND','A1':'P0.06','A2':'P0.07','A3':'P0.08','A4':'P0.16','A5':'P1.00','A6':'P1.08',
 'B0':'GND','B1':'P0.19','B2':'P0.17','B3':'P0.14','B4':'P0.15','B5':'P0.12','B6':'P0.13',
 'C0':'GND','C1':'P0.31','C2':'P0.21','C3':'P0.24','C4':'P0.23','C5':'P0.20','C6':'P0.25',
 'D0':'GND','D1':'P0.26','D2':'P0.27','D3':'P0.28','D4':'P0.29','D5':'P0.22','D6':'P1.01',
 'E0':'P1.04','E1':'P1.05','E2':'P1.06','E3':'P1.07','E4':'USB_DP','E5':'USB_DM','E6':'P0.10',
 'F3':'P0.18','F4':'VDDH','F5':'NC_DCCH_INTERNAL','F6':'VBUS_UNUSED',
 'H0':'GND','H1':'GND','H2':'GND','H3':'GND'}
rows=list(csv.DictReader((ROOT/'docs/stage4/nrf5340-pin-map.csv').open(encoding='utf-8-sig')))
signals={r['pin']:r['signal'] for r in rows}
assert len(signals)==46 and set(signals)=={f'P0.{n:02d}' for n in range(2,32)}|{f'P1.{n:02d}' for n in range(16)}
module_nets={}; PINS['module']=[]
for i,(pad,fn) in enumerate(pad_functions.items()):
 if fn in signals: net=signals[fn]; typ='bidirectional'
 elif fn in ('VDD','VDDH'): net='MCU_3V3'; typ='power_in'
 elif fn=='GND': net='GND'; typ='power_in'
 elif fn=='RESET_N': net='MCU_RESET_N'; typ='input'
 elif fn=='SWCLK': net='SWCLK'; typ='input'
 elif fn=='SWDIO': net='SWDIO'; typ='bidirectional'
 else: net=None; typ='no_connect' if fn.startswith('NC_') else 'passive'
 module_nets[pad]=net; PINS['module'].append((pad,fn,typ,'L' if i<33 else 'R'))
add('U1','FANSTEL BT40F / nRF5340','module',module_nets,'processor','Actual66manufacturerpads;46GPIOallfree;32MHz/32.768kHzcrystalsandDC/DCnetworksinside;radioOFF;hostnormal3.3VtiesVDDandVDDH')
J('J1','HOST POWER',['HOST_3V3','GND'],'root','Onlyhost3.3Vandreturn; noAFEisolatedreturnjoin')
R('R1','0R','HOST_3V3','MCU_3V3','power','Modulecurrentsense/link; inputrailquietnessandstartupunqualified')
C('C1','47u X7R 10V','MCU_3V3','GND','power','Manufacturernoisyrailbulk; effectivecapacitanceandESRrequireselection')
C('C2','1u X7R 10V','MCU_3V3','GND','power','Localmodulebypass')
C('C3','100n X7R 10V','MCU_3V3','GND','power','LocalmoduleHFbypass')
R('R2','10k','MCU_3V3','MCU_RESET_N','power','ActiveLOWresetexternaldefault; SWDprobeorjumpercanassert')
J('J2','SWD / TARGET VREF',['MCU_3V3','SWDIO','GND','SWCLK','MCU_RESET_N','GND'],'power','TargetVREFsenseonly; externalSWDprobenotpowerfeed; noradioorUSB')
J('J3','RESET SHORTING HEADER',['MCU_RESET_N','GND'],'power','Momentaryshortassertsreset; normallyopen')
# Physical nearest-to-farthest H..A parallel load order matches frozen firmware.
sideband=['CH0_ADDR0','CH0_ADDR1','CH0_ADDR2','CH0_ADDR3','CH1_ADDR0','CH1_ADDR1','CH1_ADDR2','CH1_ADDR3',
 'RESET_READY','RAILS_QUALIFIED','WATCHDOG_OK','AFE_ISOLATED_READY','CH0_QUIESCENT_OK','CH1_QUIESCENT_OK','MON0_PERMIT','MON1_PERMIT',
 'PWR_FAULT_N','SUP_ARMED','GLOBAL_GUARD_EN','CH0_RUN','CH1_RUN','CH0_TIMER','CH1_TIMER','ROUTE_COMMAND_READY',
 'CH0_TIMEOUT','CH1_TIMEOUT','HOST_3V3','GND','GND','HOST_3V3','GND','HOST_3V3']
PINS['sideband']=[('1','SH_LD_N','input','L'),('2','CLK','input','L'),('3','E','input','L'),('4','F','input','L'),('5','G','input','L'),('6','H','input','L'),('7','QH_N','output','R'),('8','GND','power_in','L'),('9','QH','output','R'),('10','SER','input','L'),('11','A','input','L'),('12','B','input','L'),('13','C','input','L'),('14','D','input','L'),('15','CLK_INH','input','L'),('16','VCC','power_in','L')]
for k in range(4):
 nets={1:'SIDEBAND_LOAD_N',2:'CTRL_SCLK',7:None,8:'GND',9:'SIDEBAND_DATA' if k==0 else f'SB_Q{k}',10:'GND' if k==3 else f'SB_Q{k+1}',15:'GND',16:'HOST_3V3'}
 nets.update(dict(zip([6,5,4,3,14,13,12,11],sideband[k*8:k*8+8])))
 add('U'+str(10+k),'SN74LVC165APWR','sideband',nets,'sideband','EightphysicalH..Asamplebits'+str(k*8)+'..'+str(k*8+7)+'; nearestQHreadbeforeshift; QH_Nunused')
 C('C'+str(10+k),'100n X7R 10V','HOST_3V3','GND','sideband','Onebypassattheactual165supplypins')
# Carrier handoff names are the frozen firmware's names. Common CNV/rearm are
# explicit duplicate physical connector pins on one net, never alternate pins.
harnesses={
 'J10':('RAW MONITOR',['RAW_SCLK','RAW_SDI','RAW_SDO','RAW_CS_N','RAW_RST_N','GND'],'monitoring-transport:J3'),
 'J11':('ISOLATED RECORDING HOST',['HOST_3V3','GND','AFE_SCLK','AFE_MOSI','AFE_CS_ASSERT','AFE_MISO','AFE_CONNECT','AFE_RECORD','AFE_FAULT_N','GND'],'recording-front-end:J2'),
 'J12':('SHARED CHARGE ENDPOINT SPI',['MON_SCLK','MON_MISO','BOTH_CNV','CS0','BOTH_CNV','CS1','GND'],'monitoring-transport:J22'),
 'J13':('DOSE / MONITOR REARM',['INT_RUN0','INT_RUN1','MON_REARM0','MON_REARM1','GND'],'monitoring-transport:J20.8..11'),
 'J14':('DAC SERIAL',['CTRL_SCLK','DAC_SYNC_N','CTRL_MOSI','GND'],'current-driver:J2'),
 'J15':('DRIVER REQUEST / POLARITY',['REQ0','PLUS0','MINUS0','BOTH_DRV_REARM','REQ1','PLUS1','MINUS1','BOTH_DRV_REARM','GND'],'current-driver:J3'),
 'J16':('ROUTE CANDIDATE / COMMIT',['CTRL_MOSI','CTRL_SCLK','ROUTE_PRELOAD','ROUTE_COMMIT','ROUTE_REARM','ACTIVE_ACK','WANT0','WANT1','GND'],'contact-router:J2/J3/J4'),
 'J17':('ACTIVE ROUTE READBACK',sideband[:8]+['GND'],'contact-router:J6'),
 'J18':('SUPERVISION CONTROL',['SUP_REARM','FAULT_RESET','WDI','REQ0','REQ1','PHASE_REARM0','PHASE_REARM1','GND'],'supervision:J3'),
 'J19':('NATIVE HEALTH OBSERVATIONS',sideband[8:26]+['GND'],'native health/status only; noindependentguardauthorityreplacement'),
 'J20':('ISOLATED COMPANION HOST UART',['HOST_UART_TX','HOST_UART_RX','HOST_3V3','GND'],'monitoring-transport:J7')}
for ref,(name,nets,source) in harnesses.items(): J(ref,name,nets,'handoff',source)
# Reset bias is deliberately stronger than legacy 100k pulls. These are passive
# commissioning defaults; power ordering/edge/glitch performance is unmeasured.
for k,row in enumerate(r for r in rows if r['direction']=='out'):
 n=row['signal']; hi=row['reset_state']=='high'
 R('R'+str(100+k),'10k','HOST_3V3' if hi else n,n if hi else 'GND','defaults','Carrierresetbias'+row['reset_state']+'; unknownintegratorhistoryhelduntilqualifiedrecovery')
base_order=['root','processor','power','sideband','handoff','defaults']
titles={'root':'Controller carrier / interface index','processor':'BT40F / actual nRF5340 physical pads','power':'Module normal-voltage supply and SWD','sideband':'Four physical 165 devices / parallel observations','handoff':'Matched peripheral handoff connectors','defaults':'Passive reset defaults / explicit recovery'}
SHEETS=[];TITLES={}
for base in base_order:
 group=[p for p in parts if p['sheet']==base]
 limit=1 if base=='processor' else 4 if base=='handoff' else 8 if base=='sideband' else 16
 pages=max(1,(len(group)+limit-1)//limit); chunk=(len(group)+pages-1)//pages
 for page in range(pages):
  sh=base if page==0 else base+'_'+str(page+1); SHEETS.append(sh); TITLES[sh]=titles[base]+(' / '+str(page+1) if page else '')
  for i,p in enumerate(group[page*chunk:(page+1)*chunk]):
   p['sheet']=sh
   p['xy']=(254,177.8) if base=='processor' else (101.6+(i%2)*266.7,99.06+(i//2)*139.7) if base=='handoff' else (76.2+(i%4)*137.16,96.52+(i//4)*73.66)
exec((OUT/'native_render.py').read_text(encoding='utf-8'),globals())
manifest={'schema':'scci_rh.stage4.controller-carrier.connectivity.v1','date':'2026-10-14','scope':'PhysicalBT40FnRF5340modulecarrierwith46GPIOandfourSN74LVC165;digitalbenchonly,radioOFF','parts':parts,'source_documents':SOURCES,'physical_pad_functions':pad_functions,'firmware_pin_map_sha256':hashlib.sha256((ROOT/'docs/stage4/nrf5340-pin-map.csv').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'gpio_bindings':[dict(row,module_reference='U1',physical_pad=next(p for p,f in pad_functions.items() if f==row['pin'])) for row in rows],'sideband_bits':sideband,'harnesses':{ref:{'description':name,'nets':dict(enumerate(ns,1)),'target':target} for ref,(name,ns,target) in harnesses.items()},'nominal':{'host_supply_V':3.3,'GPIO_count':46,'sideband_bits':32,'carrier_reset_pull_ohm':10000,'module_HFXO_internal_load_pF':11,'module_LFXO_internal':True,'module_VDD_VDDH_join':True},'unqualified':['PhysicalSPI/UARTedges,cablelengths,fanoutandreturnintegrity','Moduleactualoscillatorloadingandfinalcarrierfirmwareclockconfiguration','Noexecutedtargetboard,noimplant,noRFqualification','Resetdefaultresistorbiasdoesnotprovealltransientpowerorderings','LGAassemblymask/paste/thermal/ripple/effectivecapacitancequalification','Serializedhealthsnapshotdoesnotreplaceindependentnativeanalogguards']}
(OUT/'connectivity.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
with (OUT/'bom.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['reference','value','footprint','sheet','description','primary_source'])
 for p in parts:w.writerow([p['ref'],p['value'],p['footprint'],p['sheet'],p['description'],p['source_url']])
print(json.dumps({'components':len(parts),'pins':sum(len(p['pins']) for p in parts),'sheets':len(SHEETS)}))
