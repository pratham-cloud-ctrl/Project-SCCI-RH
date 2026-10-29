"""Generate native dedicated monitoring conversion and companion interfaces.

Historical ADC endpoint circuits, hardware guards and recording remain unchanged.
"""
from pathlib import Path
import csv,json,os,uuid
OUT=Path(__file__).resolve().parent
SHARE=Path(os.environ.get('KICAD_SHARE',r'E:\project workspace assests\EDA\KiCAD\share\kicad'))
PROJECT='monitoring_transport'
def uid(key):return str(uuid.uuid5(uuid.NAMESPACE_URL,'project-scci-rh/stage4/monitoring-transport/'+key))
ROOT_ID=uid('root');parts=[];SOURCES={};PINS={}
FP={'R':'Resistor_SMD:R_0805_2012Metric','C':'Capacitor_SMD:C_1206_3216Metric'}
def add(ref,value,kind,nets,sheet,description):
 if kind=='J':fp=f'Connector_PinHeader_2.54mm:PinHeader_1x{len(nets):02d}_P2.54mm_Vertical';pins=[(i,str(i),'passive','L') for i in sorted(nets)]
 elif kind in ('R','C'):fp=FP[kind];pins=[(1,'1','passive','L'),(2,'2','passive','R')]
 else:fp=FP[kind];pins=PINS[kind]
 assert {str(p[0]) for p in pins}=={str(n) for n in nets},(ref,nets)
 assert ref not in {p['ref'] for p in parts},ref
 parts.append(dict(ref=ref,value=value,kind=kind,footprint=fp,nets={str(k):v for k,v in nets.items()},pins=pins,xy=(0,0),sheet=sheet,description=description,source_url=SOURCES.get(kind,'')))
def R(ref,val,a,b,s,d):add(ref,val,'R',{1:a,2:b},s,d)
def C(ref,val,a,b,s,d):add(ref,val,'C',{1:a,2:b},s,d)
def J(ref,val,ns,s,d):add(ref,val,'J',dict(enumerate(ns,1)),s,d)
SOURCES['raw_adc']='https://www.ti.com/lit/ds/symlink/ads8688.pdf'
FP['raw_adc']='Package_SO:TSSOP-38_4.4x9.7mm_P0.5mm'
PINS['raw_adc']=[(1,'SDI','input','L'),(2,'RST_PD_N','input','L'),(3,'DAISY','input','L'),(4,'REFSEL','input','L'),(5,'REFIO','bidirectional','R'),(6,'REFGND','power_in','L'),(7,'REFCAP','passive','R'),(8,'AGND','power_in','L'),(9,'AVDD','power_in','L'),(10,'AUX_IN','input','L'),(11,'AUX_GND','power_in','L'),(12,'AIN_6P','input','L'),(13,'AIN_6GND','input','L'),(14,'AIN_7P','input','L'),(15,'AIN_7GND','input','L'),(16,'AIN_0P','input','L'),(17,'AIN_0GND','input','L'),(18,'AIN_1P','input','L'),(19,'AIN_1GND','input','L'),(20,'AIN_2GND','input','L'),(21,'AIN_2P','input','L'),(22,'AIN_3GND','input','L'),(23,'AIN_3P','input','L'),(24,'AIN_4GND','input','L'),(25,'AIN_4P','input','L'),(26,'AIN_5GND','input','L'),(27,'AIN_5P','input','L'),(28,'AGND','power_in','L'),(29,'AGND','power_in','L'),(30,'AVDD','power_in','L'),(31,'AGND','power_in','L'),(32,'AGND','power_in','L'),(33,'DGND','power_in','L'),(34,'DVDD','power_in','L'),(35,'DNC','no_connect','R'),(36,'SDO','output','R'),(37,'SCLK','input','L'),(38,'CS_N','input','L')]
J('J1','HOST RAILS / RAW ADC',['HOST_5','HOST_3V3','GND'],'root','GeneratedpowerpackageHOST5/HOST3V3andhostreturn; noneconnectAFEAGND')
J('J2','EXISTING ANALOG TAPS',['CH0_I_MON','CH1_I_MON','CH0_VPAIR','CH1_VPAIR','MON_VREF','MON_VMID','PACK_BUS','GND'],'root','Currentfrommonitor,scaledpairfromsupervision,4.096/2.048Vreferenceandpackbus; nomodificationofsourcecircuits')
J('J3','DEDICATED RAW ADC BUS',['RAW_SCLK','RAW_SDI','RAW_SDO','RAW_CS_N','RAW_RST_N','GND'],'root','DedicatedhostSPIbusallocation,independentfromRHDandADS8866endpointbuses; SoCpinmap/firmwareisnextpackage')
J('J4','TWO EXISTING CHARGE ADCs',['CH0_CNV','CH0_CS_N','CH0_DOUT','CH1_CNV','CH1_CS_N','CH1_DOUT','MON_SCLK','GND'],'root','PassivehandofftoexistingADS8866monitorJ2; nocopies/newchargeADC; eachCNVaperture/resultidentityretained')
J('J5','CHARGE CONTROL HANDOFF',['CH0_INT_RUN','CH1_INT_RUN','CH0_MON_REARM','CH1_MON_REARM','GND'],'root','Separateintegrator/resetandmonitorrearmhandoff,neverderivedfromtransportvalidity')
J('J6','READ-ONLY NATIVE HEALTH',['RESET_READY','RAILS_QUALIFIED','WATCHDOG_OK','AFE_ISOLATED_READY','CH0_QUIESCENT_OK','CH1_QUIESCENT_OK','SUP_ARMED','GLOBAL_GUARD_EN','PWR_FAULT_N','GND'],'root','HostGPIOobservationofexistingnativehealth; ADCandcompaniondonotgrantstimulationauthority')
# Every ADS8688 physical pin is explicit; channel2..5 positive/ground ordering is reversed.
nets={1:'RAW_SDI_PAD',2:'RAW_RST_N',3:'GND',4:'GND',5:'RAW_REFIO',6:'GND',7:'RAW_REFCAP',8:'GND',9:'HOST_5',10:'GND',11:'GND',12:'ADC6',13:'GND',14:'ADC7',15:'GND',16:'ADC0',17:'GND',18:'ADC1',19:'GND',20:'GND',21:'ADC2',22:'GND',23:'ADC3',24:'GND',25:'ADC4',26:'GND',27:'ADC5',28:'GND',29:'GND',30:'HOST_5',31:'GND',32:'GND',33:'GND',34:'HOST_3V3',35:None,36:'RAW_SDO',37:'RAW_SCLK_PAD',38:'RAW_CS_N'}
add('U1','ADS8688IDBTR','raw_adc',nets,'adc','8channel16bit500kspsaggregateADC,internal4.096reference,programmableunipolar0..5.12V; internalPGA/filterisnotantialiasedproof')
R('R1','33R','RAW_SDI','RAW_SDI_PAD','adc','SeriesdampingatMCUout; finalplacementinPCB')
R('R2','33R','RAW_SCLK','RAW_SCLK_PAD','adc','Clockseriesdamping; physicalsignalqualityrequiresPCB')
R('R3','100k','HOST_3V3','RAW_CS_N','adc','InactiveCSdefault; logicvaliditystilldependsrails')
R('R4','100k','RAW_RST_N','GND','adc','Reset/powerdowndefaultLOWuntilhostexplicitconfiguration')
R('R5','100k','RAW_SCLK_PAD','GND','adc','Definedidleclockwhilehostunpowered')
R('R6','100k','RAW_SDI_PAD','GND','adc','Definedserialinputwhilehostunpowered')
for ref,val,node in [('C1','22u X7R 10V','RAW_REFIO'),('C2','22u X7R 10V','RAW_REFCAP'),('C3','1u X7R 10V','RAW_REFCAP'),('C4','10u X7R 10V','HOST_5'),('C5','1u X7R 10V','HOST_5'),('C6','10u X7R 10V','HOST_5'),('C7','1u X7R 10V','HOST_5'),('C8','10u X7R 10V','HOST_3V3'),('C9','100n X7R 10V','HOST_3V3')]:
 C(ref,val,node,'GND','reference','Manufacturerreferenceandlocalrailbypass; placement/effectivecapacitancequalificationremainsPCB')
# Source taps are voltageobservations; no body/HV terminal is directlyconnected to theADC.
channels=[('CH0_I_MON','raw current 0'),('CH1_I_MON','raw current 1'),('CH0_VPAIR','existing scaled differential voltage 0'),('CH1_VPAIR','existing scaled differential voltage 1'),('MON_VREF','monitor reference health'),('MON_VMID','monitor midpoint health'),('PACK_SCALED','divided pack-bus voltage'),('HOST5_SCALED','divided host5 voltage')]
for k,(node,desc) in enumerate(channels):
 R('R'+str(100+k),'100R 0.1%',node,'ADC'+str(k),'inputs',desc+'; finite1MohmADCinputtointernal2.5Vbiasloads100ohmsourcefilter')
 C('C'+str(100+k),'1n C0G 5%','ADC'+str(k),'GND','inputs','100ohm/1nFexternalpole1.59MHz; notNyquistantialiasfilterorfullmeasurementsettlingproof')
R('R120','4.99k 0.1%','PACK_BUS','PACK_SCALED','health','Nominalpackdivideby3; ADC1Mohmtointernal2.5Vbiasandfilterareincludedinfinitegaincalculation')
R('R121','2.49k 0.1%','PACK_SCALED','GND','health','Packdividertoreturn; noextrapolatedbatterySOCclaim')
R('R122','2.4k 0.1%','HOST_5','HOST5_SCALED','health','Nominalhost5divideby2.2; ADC1Mohmtointernal2.5Vbiasandfilterareincluded')
R('R123','2k 0.1%','HOST5_SCALED','GND','health','Host5dividertoreturn; independenthardwarewindowsremainseparate')
# Companion circuit appended after its primaryparts/line contract is frozen.
PINS['uart_iso']=[(1,'VCC1','power_in','L'),(2,'OUTA_HOST_RX','output','R'),(3,'INB_HOST_TX','input','L'),(4,'GND1','power_in','L'),(5,'GND2','power_in','L'),(6,'OUTB_COMP_RX','output','R'),(7,'INA_COMP_TX','input','L'),(8,'VCC2','power_in','L')]
FP['uart_iso']='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
SOURCES['uart_iso']='https://www.ti.com/lit/ds/symlink/iso6721.pdf'
add('U20','ISO6721BDR','uart_iso',{1:'HOST_3V3',2:'UART_HOST_RX_PAD',3:'UART_HOST_TX_PAD',4:'GND',5:'COMP_GND',6:'UART_COMP_RX_PAD',7:'UART_COMP_TX_PAD',8:'COMP_3V3'},'companion','50Mbpsstandardmappingbidirectionisolator; nonFdefaultHIGHmatchesUARTidle. Functionalgalvanicisolationisnotbody/RF/medicalqualification')
J('J7','HOST PROCESSED UART',['HOST_UART_TX','HOST_UART_RX','HOST_3V3','GND'],'companion','1Mbaud8N1hostcompanionbus; packetage/CRC/identityvalidityhandledbyseparatestudy,targetfirmwarenext')
J('J8','EXTERNAL COMPANION UART',['COMP_UART_TX','COMP_UART_RX','COMP_3V3','COMP_GND'],'companion','Externallypowered3.3VUARThost/companionfixture; pressureestimator/featureprocessoroutsidepackage,notspinalorbodyradiosignal')
for n,node,a,b in [(20,'TXH','HOST_UART_TX','UART_HOST_TX_PAD'),(21,'RXH','UART_HOST_RX_PAD','HOST_UART_RX'),(22,'TXC','COMP_UART_TX','UART_COMP_TX_PAD'),(23,'RXC','UART_COMP_RX_PAD','COMP_UART_RX')]:R('R'+str(n),'33R',a,b,'companion','FiniteUARTlinedamping; specifiedshortdigitalfixture,novalidatedcableEMI/ESDtest')
R('R24','10k','HOST_3V3','UART_HOST_TX_PAD','companion','UARTidleHIGHinputdefaultinhostdomain')
R('R25','10k','COMP_3V3','UART_COMP_TX_PAD','companion','UARTidleHIGHinputdefaultincompaniondomain')
C('C20','100n X7R 10V','HOST_3V3','GND','companion','Isolatorhostlocalbypass')
C('C21','100n X7R 10V','COMP_3V3','COMP_GND','companion','Isolatorcompanionlocalbypass; neverbridgesgrounddomains')
C('C22','1u X7R 10V','HOST_3V3','GND','companion','HostUARTrailbulk')
C('C23','1u X7R 10V','COMP_3V3','COMP_GND','companion','CompanionUARTrailbulk')
J('J20','HOST CHARGE ADC BUS',['CH0_CNV','CH0_CS_N','CH0_DOUT','CH1_CNV','CH1_CS_N','CH1_DOUT','MON_SCLK','CH0_INT_RUN','CH1_INT_RUN','CH0_MON_REARM','CH1_MON_REARM','GND'],'handoff','ActualpassivehandofftoJ4/J5; SoCportpinallocationwillbeimplementednext')
J('J21','HOST HEALTH INPUTS',['RESET_READY','RAILS_QUALIFIED','WATCHDOG_OK','AFE_ISOLATED_READY','CH0_QUIESCENT_OK','CH1_QUIESCENT_OK','SUP_ARMED','GLOBAL_GUARD_EN','PWR_FAULT_N','GND'],'handoff','SamehealthobservationsasJ6, passivewiresonly; noADC/firmwareauthoritybypass')
R('R30','330R','CH0_DOUT','MON_MISO','handoff','Source0tri-stateDOUTjoin; selectonlyoneADC; 8MHzsharedbusloadingrequiresPCBqualification')
R('R31','330R','CH1_DOUT','MON_MISO','handoff','Source1tri-stateDOUTjoin; resistorsdonotmakeconcurrentCSorunpoweredADCvalid')
J('J22','HOST SHARED ENDPOINT SPI',['MON_SCLK','MON_MISO','CH0_CNV','CH0_CS_N','CH1_CNV','CH1_CS_N','GND'],'handoff','Explicitshared8MHzendpointMISO; J20retainsseparateDOUTdiagnostictaps; chipselectsneveroverlapinhealthycontract')
base_order=['root','adc','reference','inputs','health','companion','handoff']
title_base={'root':'Existing package and host endpoints','adc':'Dedicated eight-channel raw conversion','reference':'Independent ADC reference and bypass','inputs':'Raw current and scaled voltage filtering','health':'Divided power observations','companion':'Isolated wired processed-feature companion','handoff':'Charge ADC and health host handoff'}
SHEETS=[];TITLES={}
for base in base_order:
 group=[p for p in parts if p['sheet']==base];limit=4 if base=='root' else 6 if base=='handoff' else 16
 pages=(len(group)+limit-1)//limit;chunk=(len(group)+pages-1)//pages
 for page in range(pages):
  sh=base if page==0 else base+'_'+str(page+1);SHEETS.append(sh);TITLES[sh]=title_base[base]+(' / '+str(page+1) if page else '')
  for i,p in enumerate(group[page*chunk:(page+1)*chunk]):
   p['sheet']=sh;p['xy']=(101.6+(i%2)*266.7,88.9+(i//2)*111.76) if base in ('root','handoff') else (76.2+(i%4)*137.16,96.52+(i//4)*73.66)
exec((OUT/'native_render.py').read_text(encoding='utf-8'),globals())
manifest={'schema':'scci_rh.stage4.monitoring-transport.connectivity.v1','date':'2026-10-14','scope':'DedicatedrawADC,existingcharge-ADC/healthhandoffandisolatedwiredcompanion; artificialsignals,notimplantedbodylinkqualification','parts':parts,'source_documents':SOURCES,'channels':[{'channel':i,'source':node,'description':desc,'range_code':6,'range_V':[0,5.12]} for i,(node,desc) in enumerate(channels)],'nominal':{'raw_ADC_max_aggregate_sps':500000,'raw_ADC_bits':16,'raw_ADC_VREF_V':4.096,'raw_ADC_range_V':5.12,'input_filter_R_ohm':100,'input_filter_C_F':1e-9,'input_ADC_R_ohm_typ':1e6,'input_ADC_R_ohm_25C_bounds':[850000,1150000],'input_ADC_bias_V':2.5,'raw_SPI_Hz':16000000,'raw_frame_allocation_s':2.125e-6,'UART_baud':1000000,'UART_frame':'8N1','isolator_rate_bps':50000000,'host_3V3_V':3.3,'host_5_V':5,'companion_external_3V3_V':3.3},'external_unimplemented':['PhysicalADCsettling/aliasing/ESDandSPIeyepatternqualification','ADCinput0.85..1.15Mohmat25Cplusmax25ppm/Cdrift; fullphysicalsettling/aliasingnotqualified','Effective22uFREFIO/REFCAPcapacitanceandlayoutrequiresPCBselection','SoCpinallocation/targetfirmware/DMAandrealinterrupttimingarethenextpackage','ExternalcompanionpressureestimatornotnativeSBPcufforuniversalbody-stateobserver','NoRF/through-body/antenna/clinicalisolationorimplantleakagequalification','ExistingchargeADCfaultinputprotectionandintegratorbiaslimitsremainhistorical,notfixedbyrawADC']}
(OUT/'connectivity.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
with (OUT/'bom.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['reference','value','footprint','sheet','description','primary_source'])
 for p in parts:w.writerow([p['ref'],p['value'],p['footprint'],p['sheet'],p['description'],p['source_url']])
print(json.dumps({'components':len(parts),'pins':sum(len(p['pins']) for p in parts),'sheets':len(SHEETS),'root':str(OUT/(PROJECT+'.kicad_sch'))}))
