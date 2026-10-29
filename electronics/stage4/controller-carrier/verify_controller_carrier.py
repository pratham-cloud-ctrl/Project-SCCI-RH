"""Read-only physical-pad, firmware and sideband audit of the native carrier."""
from pathlib import Path
import argparse,csv,hashlib,json,re,xml.etree.ElementTree as ET
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-receipt',action='store_true');args=ap.parse_args()
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def digest(p):
 data=p.read_bytes()
 if p.suffix not in ('.png','.pdf'): data=data.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
 return hashlib.sha256(data).hexdigest()
m=json.loads((HERE/'connectivity.json').read_text());parts={p['ref']:p for p in m['parts']}
assert len(parts)==len(m['parts'])==68
xml=ET.parse(HERE/'controller_carrier.xml').getroot()
components={x.attrib['ref']:x for x in xml.findall('./components/comp')};assert set(components)==set(parts)
pins={}
for net in xml.findall('./nets/net'):
 for node in net.findall('node'):
  key=node.attrib['ref'],node.attrib['pin'];assert key not in pins;pins[key]=net.attrib['name']
def pin(ref,n):return pins.get((ref,str(n)))
def check(ref,n,expected):
 actual=pin(ref,n)
 assert (actual==expected if expected is not None else actual is None or actual.startswith('unconnected-')),(ref,n,actual,expected)
checked=0
for ref,p in parts.items():
 assert components[ref].findtext('value')==p['value']
 assert components[ref].findtext('footprint')==p['footprint']
 path=HERE/'scci_rh_controller.pretty'/(p['footprint'].split(':')[1]+'.kicad_mod')
 pads=re.findall(r'\(pad "([^"]+)"',path.read_text());assert set(pads)==set(p['nets']),(ref,pads,p['nets'])
 assert len(pads)==len(set(pads))
 for n,net in p['nets'].items():check(ref,n,net);checked+=1
assert checked==328
# Independent primary-manufacturer pad order, not generated symbol pin numbers.
gpio_pads=['7','8','5','6','A1','A2','A3','11','E6','12','B5','B6','B3','B4','A4','B2','F3','B1','C5','C2','D5','C4','C3','C6','D1','D2','D3','D4','13','C1','A5','D6','1','2','E0','E1','E2','E3','A6','Z0','Z1','Z2','Z3','Z4','Z5','Z6']
gpio_names=[f'P0.{i:02d}' for i in range(2,32)]+[f'P1.{i:02d}' for i in range(16)]
normative=dict(zip(gpio_names,gpio_pads));assert len(normative)==len(set(normative.values()))==46
rows=list(csv.DictReader((ROOT/'docs/stage4/nrf5340-pin-map.csv').open(encoding='utf-8-sig')))
assert len(rows)==46 and {r['pin'] for r in rows}==set(normative)
assert m['firmware_pin_map_sha256']==digest(ROOT/'docs/stage4/nrf5340-pin-map.csv')
for row in rows:check('U1',normative[row['pin']],row['signal'])
assert {p for p in m['physical_pad_functions'] if m['physical_pad_functions'][p].startswith('P')}==set(gpio_pads)
for p in ['10','A0','B0','C0','D0','H0','H1','H2','H3']:check('U1',p,'GND')
for p in ['9','F4']:check('U1',p,'MCU_3V3')
for p in ['3','4','F5','E4','E5','F6']:check('U1',p,None)
check('U1','14','MCU_RESET_N');check('U1','15','SWCLK');check('U1','16','SWDIO')
check('R1',1,'HOST_3V3');check('R1',2,'MCU_3V3');assert parts['R1']['value']=='0R'
for ref,value in [('C1','47u X7R 10V'),('C2','1u X7R 10V'),('C3','100n X7R 10V')]:
 assert parts[ref]['value']==value;check(ref,1,'MCU_3V3');check(ref,2,'GND')
check('R2',1,'MCU_3V3');check('R2',2,'MCU_RESET_N');assert parts['R2']['value']=='10k'
# Explicit common fanouts and independent rearms must never become a GPIO short.
check('J12',3,'BOTH_CNV');check('J12',5,'BOTH_CNV');check('U1','D5','BOTH_CNV')
check('J15',4,'BOTH_DRV_REARM');check('J15',8,'BOTH_DRV_REARM');check('U1','E2','BOTH_DRV_REARM')
check('J18',6,'PHASE_REARM0');check('U1','Z1','PHASE_REARM0')
check('J18',7,'PHASE_REARM1');check('U1','Z2','PHASE_REARM1')
assert len({pin('U1',x) for x in ['E2','Z1','Z2']})==3
expected=['CH0_ADDR0','CH0_ADDR1','CH0_ADDR2','CH0_ADDR3','CH1_ADDR0','CH1_ADDR1','CH1_ADDR2','CH1_ADDR3',
 'RESET_READY','RAILS_QUALIFIED','WATCHDOG_OK','AFE_ISOLATED_READY','CH0_QUIESCENT_OK','CH1_QUIESCENT_OK','MON0_PERMIT','MON1_PERMIT',
 'PWR_FAULT_N','SUP_ARMED','GLOBAL_GUARD_EN','CH0_RUN','CH1_RUN','CH0_TIMER','CH1_TIMER','ROUTE_COMMAND_READY','CH0_TIMEOUT','CH1_TIMEOUT',
 'HOST_3V3','GND','GND','HOST_3V3','GND','HOST_3V3']
assert m['sideband_bits']==expected
parallel_pins=[6,5,4,3,14,13,12,11]
for k in range(4):
 ref='U'+str(10+k)
 assert parts[ref]['value']=='SN74LVC165APWR'
 for p,n in zip(parallel_pins,expected[8*k:8*k+8]):check(ref,p,n)
 for p,n in [(1,'SIDEBAND_LOAD_N'),(2,'CTRL_SCLK'),(7,None),(8,'GND'),(15,'GND'),(16,'HOST_3V3')]:check(ref,p,n)
 check(ref,9,'SIDEBAND_DATA' if k==0 else 'SB_Q'+str(k))
 check(ref,10,'GND' if k==3 else 'SB_Q'+str(k+1))
 assert parts['C'+str(10+k)]['value']=='100n X7R 10V'
check('U1','Z5','SIDEBAND_LOAD_N');check('U1','Z6','SIDEBAND_DATA');check('U1','D4','CTRL_SCLK')
# Independently execute the physical H-to-A, QH-before-clock chain for all
# walking observations, empty/full observations, and hardwired sentinel.
vectors=[0,(1<<26)-1]+[1<<n for n in range(26)]
for word in vectors:
 parallel={n:(word>>b)&1 for b,n in enumerate(expected[:26])};parallel.update(HOST_3V3=1,GND=0)
 states=[[parallel[pin('U'+str(10+k),p)] for p in parallel_pins] for k in range(4)]
 bits=[]
 for _ in range(32):
  bits.append(states[0][0]);old=[s[:] for s in states]
  states=[old[k][1:]+[old[k+1][0] if k<3 else 0] for k in range(4)]
 captured=sum(bit<<n for n,bit in enumerate(bits));assert captured==word|0xa4000000
for ref,h in m['harnesses'].items():
 for n,net in h['nets'].items():check(ref,n,net)
for n,net in enumerate(expected[8:26],1):check('J19',n,net)
# Forty stronger passive defaults follow frozen firmware initialization states.
outs=[r for r in rows if r['direction']=='out'];assert len(outs)==40
for k,row in enumerate(outs):
 ref='R'+str(100+k);assert parts[ref]['value']=='10k'
 if row['reset_state']=='high':check(ref,1,'HOST_3V3');check(ref,2,row['signal'])
 else:check(ref,1,row['signal']);check(ref,2,'GND')
assert abs(3.3*100000/110000-3.0)<1e-12 and abs(3.3*10000/110000-.3)<1e-12
assert 40*3.3/10000==.0132
for p in parts.values():assert not {'AFEAGND','COMP_GND','HOSTGND'}&set(p['nets'].values())
geometry=list(csv.DictReader((HERE/'module-pad-geometry.csv').open(encoding='utf-8')));assert len(geometry)==66
source=json.loads((HERE/'module-footprint-source.json').read_text());assert source['actual_pad_count']==66
assert source['manufacturer_specification']['sha256']=='63e7cfabad1f13149c4b090cf02a79f46cf927af5549cb1614f3ecbc56101a22'
assert source['body_geometry']['upper_x_bounds_mm']==[-8,7] and source['body_geometry']['lower_x_bounds_mm']==[-7,7]
assert source['body_geometry']['y_bounds_mm']==[-10.5,10.5] and source['body_geometry']['notch_y_mm']==.5
assert {r['pad'] for r in geometry}==set(m['physical_pad_functions'])
assert source['numeric_to_physical_names']['52']=='F3' and source['numeric_to_physical_names']['59']=='H3'
fp=(HERE/'scci_rh_controller.pretty/BT40F_Manufacturer_66Pad.kicad_mod').read_text()
assert '(start -8.5 -11) (end 7.5 11)' in fp and '(start -7 10.5) (end -7 0.5)' in fp
for row in geometry:
 match=re.search(r'\(pad "'+re.escape(row['pad'])+r'" smd (\w+) \(at ([\d.-]+) ([\d.-]+)\) \(size ([\d.-]+) ([\d.-]+)\)',fp);assert match,row
 assert match[1]==row['shape']
 for a,b in zip(map(float,match.groups()[1:]),[float(row[x]) for x in ['x_mm','y_mm','width_mm','height_mm']]):assert abs(a-b)<1e-6
erc=json.loads((HERE/'erc.json').read_text());assert not erc['ignored_checks'] and len(erc['sheets'])==10
assert not [v for s in erc['sheets'] for v in s['violations']]
mcp=json.loads((HERE/'mcp-inspection.json').read_text());assert mcp['erc']['total']==0
assert len(mcp['module_pins']['pins'])==66 and len(mcp['nearest_pins']['pins'])==16
assert mcp['h_bit0']['net']=='CH0_ADDR0' and mcp['data_pin']['net']=='SIDEBAND_DATA'
assert mcp['common_drv']['net']=='BOTH_DRV_REARM' and mcp['phase0']['net']=='PHASE_REARM0'
assert len(mcp['overlaps'])==10 and all(x['overlap_count']==0 and not x['bounds_unresolved'] for x in mcp['overlaps'].values())
assert all(digest(HERE/name)==sha for name,sha in mcp['schematic_sha256'].items())
assert len(list(HERE.glob('*.kicad_sch')))==10 and len(list((HERE/'svg').glob('*.svg')))==10
visual=json.loads((HERE/'visual-review.json').read_text());assert visual['pages_reviewed']==list(range(1,11))
assert visual['pdf_sha256']==digest(HERE/'controller_carrier.pdf')
assert all(digest(HERE/'review'/n)==sha for n,sha in visual['png_sha256'].items())
for p in (HERE/'svg').glob('*.svg'):assert all(l==l.rstrip() for l in p.read_text().splitlines())
with (HERE/'bom.csv').open(encoding='utf-8',newline='') as f:bom=list(csv.DictReader(f))
assert len(bom)==68 and {x['reference'] for x in bom}==set(parts)
files=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in ('verification.json','controller_carrier.kicad_prl') and '__pycache__' not in p.parts and not p.name.endswith('.lck'))
receipt={'schema':'scci_rh.stage4.controller-carrier.verification.v1','date':'2026-10-14','scope':'SavednativeGPIO,pad,sideband,ERC,MCPandvisualverification;physicalexecutionexcluded','components':68,'physical_pin_contracts':328,'module_physical_pads':66,'firmware_GPIO':46,'sideband_serial_vectors':len(vectors),'sheets':10,'ERC_violations':0,'ignored_ERC_checks':[],'checks':['all66actualmodulepadsand46frozenfirmwareGPIO','fourphysicalHtoA/QH/SERchainsand26observationsplus6sentinelbits','separatecommon-driverandtwo-phase-supervisorrearms','explicitcommonendpointCNV','forty10kresetbiasesandstatic13.2mAopposedceiling','primaryEaglegeometrytoactualnativepadnames','nativeXML/BOM/footprintpinsets','savedfileKonnectMCPgeometry/pins/ERC','tenPDF/SVGpageswithfinalvisualreview'],'unqualified':m['unqualified'],'hash_policy':'TextLFnormalized;PDF/PNGexact;selfreceipt/caches/preferencesexcluded','sha256':{p.relative_to(HERE).as_posix():digest(p) for p in files}}
if args.write_receipt:(HERE/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
else:assert json.loads((HERE/'verification.json').read_text())==receipt,'Review before deliberate receipt refresh'
print(json.dumps({k:receipt[k] for k in ['components','physical_pin_contracts','module_physical_pads','firmware_GPIO','sideband_serial_vectors','sheets','ERC_violations']}))
