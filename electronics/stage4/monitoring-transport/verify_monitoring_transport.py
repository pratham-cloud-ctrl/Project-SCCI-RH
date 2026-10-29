"""Read-only checks of the native monitoring and companion package.

--write-receipt explicitly freezes a reviewed package. Routine use writes nothing.
The checks do not establish physical ADC performance or implanted qualification.
"""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,json,re,xml.etree.ElementTree as ET
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--write-receipt',action='store_true');args=ap.parse_args()
HERE=Path(__file__).resolve().parent
manifest=json.loads((HERE/'connectivity.json').read_text(encoding='utf-8-sig'))
parts={p['ref']:p for p in manifest['parts']}
assert len(parts)==len(manifest['parts'])==60
tree=ET.parse(HERE/'monitoring_transport.xml').getroot()
exported={c.attrib['ref']:c for c in tree.findall('./components/comp')}
assert set(exported)==set(parts)
nets={}
for net in tree.findall('./nets/net'):
 for node in net.findall('node'):
  key=(node.attrib['ref'],node.attrib['pin']);assert key not in nets
  nets[key]=net.attrib['name']
def pin(ref,n):return nets.get((ref,str(n)))
def contract(ref,expected):
 for n,net in expected.items():
  got=pin(ref,n)
  assert (got==net if net is not None else got is None or got.startswith('unconnected-')),(ref,n,got,net)
def value(ref,v):assert parts[ref]['value']==v,(ref,parts[ref]['value'],v)
checked=0
for ref,p in parts.items():
 assert exported[ref].findtext('value')==p['value']
 assert exported[ref].findtext('footprint')==p['footprint']
 assert p['footprint'].split(':')[0]=='scci_rh_transport'
 fp=HERE/'scci_rh_transport.pretty'/(p['footprint'].split(':')[1]+'.kicad_mod')
 pads=set(re.findall(r'\(pad "([^\"]+)"',fp.read_text(encoding='utf-8')))
 assert pads==set(p['nets']),(ref,pads,set(p['nets']))
 contract(ref,p['nets']);checked+=len(p['nets'])
assert checked==217
value('U1','ADS8688IDBTR');value('U20','ISO6721BDR')
assert parts['U1']['footprint'].endswith(':TSSOP-38_4.4x9.7mm_P0.5mm')
assert parts['U20']['footprint'].endswith(':SOIC-8_3.9x4.9mm_P1.27mm')
# Manufacturer pin polarity matters: ADC channels 2..5 alternate GND then P.
contract('U1',{1:'RAW_SDI_PAD',2:'RAW_RST_N',3:'GND',4:'GND',5:'RAW_REFIO',6:'GND',7:'RAW_REFCAP',8:'GND',9:'HOST_5',10:'GND',11:'GND',12:'ADC6',13:'GND',14:'ADC7',15:'GND',16:'ADC0',17:'GND',18:'ADC1',19:'GND',20:'GND',21:'ADC2',22:'GND',23:'ADC3',24:'GND',25:'ADC4',26:'GND',27:'ADC5',28:'GND',29:'GND',30:'HOST_5',31:'GND',32:'GND',33:'GND',34:'HOST_3V3',35:None,36:'RAW_SDO',37:'RAW_SCLK_PAD',38:'RAW_CS_N'})
for ref,v,a,b in [('C1','22u X7R 10V','RAW_REFIO','GND'),('C2','22u X7R 10V','RAW_REFCAP','GND'),('C3','1u X7R 10V','RAW_REFCAP','GND')]:
 value(ref,v);contract(ref,{1:a,2:b})
for k,node in enumerate(['CH0_I_MON','CH1_I_MON','CH0_VPAIR','CH1_VPAIR','MON_VREF','MON_VMID','PACK_SCALED','HOST5_SCALED']):
 r='R'+str(100+k);c='C'+str(100+k)
 value(r,'100R 0.1%');contract(r,{1:node,2:'ADC'+str(k)})
 value(c,'1n C0G 5%');contract(c,{1:'ADC'+str(k),2:'GND'})
for ref,v,a,b in [('R120','4.99k 0.1%','PACK_BUS','PACK_SCALED'),('R121','2.49k 0.1%','PACK_SCALED','GND'),('R122','2.4k 0.1%','HOST_5','HOST5_SCALED'),('R123','2k 0.1%','HOST5_SCALED','GND')]:
 value(ref,v);contract(ref,{1:a,2:b})
assert 4990*2490/(4990+2490)<2000 and 2400*2000/(2400+2000)<2000
contract('R1',{1:'RAW_SDI',2:'RAW_SDI_PAD'});value('R1','33R')
contract('R2',{1:'RAW_SCLK',2:'RAW_SCLK_PAD'});value('R2','33R')
contract('R3',{1:'HOST_3V3',2:'RAW_CS_N'});value('R3','100k')
contract('R4',{1:'RAW_RST_N',2:'GND'});value('R4','100k')
# Default-format raw bus is independent of the earlier endpoint bus.
assert not ({'RAW_SCLK','RAW_SCLK_PAD'}&{pin('J4',7),pin('J20',7)})
for n in range(1,8):assert pin('J4',n)==pin('J20',n)
for n in range(1,5):assert pin('J5',n)==pin('J20',n+7)
for n in range(1,11):assert pin('J6',n)==pin('J21',n)
contract('J4',{1:'CH0_CNV',2:'CH0_CS_N',3:'CH0_DOUT',4:'CH1_CNV',5:'CH1_CS_N',6:'CH1_DOUT',7:'MON_SCLK',8:'GND'})
contract('J5',{1:'CH0_INT_RUN',2:'CH1_INT_RUN',3:'CH0_MON_REARM',4:'CH1_MON_REARM',5:'GND'})
value('R30','330R');contract('R30',{1:'CH0_DOUT',2:'MON_MISO'})
value('R31','330R');contract('R31',{1:'CH1_DOUT',2:'MON_MISO'})
contract('J22',{1:'MON_SCLK',2:'MON_MISO',3:'CH0_CNV',4:'CH0_CS_N',5:'CH1_CNV',6:'CH1_CS_N',7:'GND'})
assert pin('J4',3)!=pin('J4',6) and pin('J22',2) not in (pin('J4',3),pin('J4',6))
assert Counter(p['kind'] for p in parts.values())['raw_adc']==1
assert not any('ADS8866' in p['value'] for p in parts.values())
# Standard ISO6721 mapping, default-high version and physically separate returns.
contract('U20',{1:'HOST_3V3',2:'UART_HOST_RX_PAD',3:'UART_HOST_TX_PAD',4:'GND',5:'COMP_GND',6:'UART_COMP_RX_PAD',7:'UART_COMP_TX_PAD',8:'COMP_3V3'})
for ref,v,a,b in [('R24','10k','HOST_3V3','UART_HOST_TX_PAD'),('R25','10k','COMP_3V3','UART_COMP_TX_PAD')]:
 value(ref,v);contract(ref,{1:a,2:b})
assert 3.3-10000*10e-6>3.3*.7
for p in parts.values():
 if p['ref']!='U20':assert not ({'GND','COMP_GND'}<=set(p['nets'].values())),p['ref']
 assert 'AFEAGND' not in p['nets'].values(),p['ref']
for ref,v,a,b in [('C20','100n X7R 10V','HOST_3V3','GND'),('C21','100n X7R 10V','COMP_3V3','COMP_GND')]:
 value(ref,v);contract(ref,{1:a,2:b})
assert manifest['nominal']['raw_SPI_Hz']==16000000<17000000
assert manifest['nominal']['raw_frame_allocation_s']>32/16000000+70e-9
assert manifest['nominal']['UART_baud']*8/10==800000
assert [c['channel'] for c in manifest['channels']]==list(range(8))
assert all(c['range_code']==6 and c['range_V']==[0,5.12] for c in manifest['channels'])
with (HERE/'bom.csv').open(encoding='utf-8',newline='') as f:bom=list(csv.DictReader(f))
assert len(bom)==60 and {p['reference'] for p in bom}==set(parts)
erc=json.loads((HERE/'erc.json').read_text());assert not erc['ignored_checks'] and len(erc['sheets'])==8
assert not [v for s in erc['sheets'] for v in s['violations']]
assert len(list(HERE.glob('*.kicad_sch')))==8
assert len(list((HERE/'svg').glob('*.svg')))==8
assert len(re.findall(rb'/Type\s*/Page(?!s)\b',(HERE/'monitoring_transport.pdf').read_bytes()))==8
def digest(p):
 data=p.read_bytes()
 if p.suffix not in ('.png','.pdf'):data=data.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
 return hashlib.sha256(data).hexdigest()
visual=json.loads((HERE/'visual-review.json').read_text())
assert visual['pages_reviewed']==list(range(1,9))
assert visual['pdf_sha256']==digest(HERE/'monitoring_transport.pdf')
assert all(digest(HERE/'review'/name)==sha for name,sha in visual['png_sha256'].items())
assert set(visual['png_sha256'])=={f'page-{n}.png' for n in range(1,9)}
for p in (HERE/'svg').glob('*.svg'):assert all(line==line.rstrip() for line in p.read_text().splitlines())
mcp=json.loads((HERE/'mcp-inspection.json').read_text(encoding='utf-8-sig'))
assert mcp['erc']['total']==mcp['erc']['errors']==mcp['erc']['warnings']==0
assert len(mcp['adc_pins']['pins'])==38 and len(mcp['uart_pins']['pins'])==8
assert mcp['adc_channel2_pin']['net']=='ADC2' and mcp['companion_ground_pin']['net']=='COMP_GND'
assert mcp['endpoint_miso_pin']['net']=='MON_MISO'
assert mcp['endpoint_r30_source']['net']=='CH0_DOUT' and mcp['endpoint_r30_bus']['net']=='MON_MISO'
assert mcp['endpoint_r31_source']['net']=='CH1_DOUT' and mcp['endpoint_r31_bus']['net']=='MON_MISO'
assert set(mcp['overlaps'])=={p.name for p in HERE.glob('*.kicad_sch')}
assert all(v['overlap_count']==0 and not v['bounds_unresolved'] for v in mcp['overlaps'].values())
assert all(digest(HERE/name)==sha for name,sha in mcp['schematic_sha256'].items())
files=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in ('verification.json','monitoring_transport.kicad_prl') and not p.name.endswith('.lck') and '__pycache__' not in p.parts)
receipt={'schema':'scci_rh.stage4.monitoring-transport.verification.v1','date':'2026-10-14','scope':'Native pin/pad/export/MCP and visual checks; physical bandwidth and target firmware excluded','components':60,'pin_contracts_compared':checked,'sheets':8,'pdf_pages':8,'erc_violations':0,'ignored_erc_checks':[],'checks':['60 exported values/footprints and 217 physical pins','38-pin ADS8688 channel polarity, reference and supply map','eight native input filters and two low-impedance health dividers','dedicated raw SPI separated from two earlier endpoint ADCs','two 330 ohm tri-state DOUT branches and explicit shared endpoint MISO header','actual passive endpoint, integrator and health host handoffs','ISO6721 standard pin map, idle input pullups and separate power returns','zero full-severity ERC without ignored checks','eight PDF/SVG sheets and final rendered visual review','actual Konnect MCP pin/geometry/ERC evidence bound to saved schematics'],'unqualified':manifest['external_unimplemented'],'hash_policy':'Exact PDF/PNG; text normalized CRLF/CR to LF; excludes receipt/preferences/cache','sha256':{p.relative_to(HERE).as_posix():digest(p) for p in files}}
if args.write_receipt:(HERE/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
else:assert json.loads((HERE/'verification.json').read_text())==receipt,'Review changes before deliberate receipt refresh'
print(json.dumps({k:receipt[k] for k in ('components','pin_contracts_compared','sheets','erc_violations')}))
