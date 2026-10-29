"""Read-only native power pin, footprint, circuit and export verification.

--write-receipt deliberately freezes this package after visual/MCP review.
Physical battery, converter-loop, thermal and implant qualification are excluded.
"""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,itertools,json,re,xml.etree.ElementTree as ET
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-receipt',action='store_true');args=ap.parse_args()
HERE=Path(__file__).resolve().parent
m=json.loads((HERE/'connectivity.json').read_text(encoding='utf-8-sig'));parts={p['ref']:p for p in m['parts']}
assert len(parts)==len(m['parts'])==156
root=ET.parse(HERE/'power.xml').getroot();exported={p.attrib['ref']:p for p in root.findall('./components/comp')}
assert set(exported)==set(parts)
nets={}
for net in root.findall('./nets/net'):
 for node in net.findall('node'):
  key=(node.attrib['ref'],node.attrib['pin']);assert key not in nets;nets[key]=net.attrib['name']
def pin(ref,n):return nets.get((ref,str(n)))
def contract(ref,expected):
 for n,net in expected.items():
  got=pin(ref,n);assert (got==net if net is not None else got is None or got.startswith('unconnected-')),(ref,n,got,net)
checked=0
for ref,p in parts.items():
 assert exported[ref].findtext('value')==p['value'];assert exported[ref].findtext('footprint')==p['footprint']
 path=HERE/'scci_rh_power.pretty'/(p['footprint'].split(':')[1]+'.kicad_mod')
 pads=set(re.findall(r'\(pad "([^\"]+)"',path.read_text(encoding='utf-8')))
 assert pads==set(p['nets']),(ref,pads,set(p['nets']))
 contract(ref,p['nets']);checked+=len(p['nets'])
assert checked==449
counts=Counter(p['value'] for p in parts.values())
for value,count in {'TPS62160DGKR':3,'TPS62130ARGTR':1,'LT8330ES6#TRPBF':2,'TMR3-0522':1,'TPS7A4901DGNR':2,'TPS7A3001DGNR':1,'TPS3700DDCR':5,'SN74LVC1G07DBVR':1,'PMEG6010CEJ':2,'SS34-E3/57T':1}.items():assert counts[value]==count,(value,counts[value])
# Physical input path, converter pins and source-referenced EN polarity.
contract('J1',{1:'PACK_POS',2:'GND'});contract('F1',{1:'PACK_POS',2:'PACK_FUSED'})
contract('D1',{1:'PACK_REVERSE_OK',2:'PACK_FUSED'});contract('SW1',{1:'PACK_REVERSE_OK',2:'PACK_BUS'})
assert parts['D1']['footprint'].endswith(':D_SMC')
for ref,node,en in [('U100','SUP_3V3','PACK_BUS'),('U101','SUP_5','PACK_BUS'),('U102','HOST_3V3','HOST_ENABLE')]:
 contract(ref,{1:'GND',2:'PACK_BUS',3:en,4:'GND',5:node+'_FB',6:node,7:node+'_SW',8:node+'_PG'})
 b=int(ref[1:]);contract('L'+str(b),{1:node+'_SW',2:node})
contract('U110',{1:'HOST_5_SW',2:'HOST_5_SW',3:'HOST_5_SW',4:'HOST_5_PG',5:'HOST_5_FB',6:'GND',7:'GND',8:'GND',9:'HOST_5_SS',10:'PACK_BUS',11:'PACK_BUS',12:'PACK_BUS',13:'HOST_ENABLE',14:'HOST_5',15:'GND',16:'GND',17:'GND'})
for b,node in [(300,'HOST_15'),(301,'VH_24')]:
 contract('U'+str(b),{1:node+'_SW',2:'GND',3:node+'_FB',4:'BOOST_ENABLE',5:node+'_INTVCC',6:'PACK_BUS'})
 contract('L'+str(b),{1:'PACK_BUS',2:node+'_SW'});contract('D'+str(b),{1:node,2:node+'_SW'})
 assert parts['D'+str(b)]['footprint'].endswith(':D_SOD-323F')
 assert parts['L'+str(b)]['value']=='4.7uH SRP5030T-4R7M'
contract('U400',{1:'GND',2:'HOST_5',3:None,5:None,6:'ISO_P12',7:'AFEAGND',8:'ISO_N12'})
for b,node,vin in [(410,'AFE_3V3','ISO_P12'),(411,'AFE_P5','ISO_P12'),(412,'AFE_N5','ISO_N12')]:
 contract('U'+str(b),{1:node,2:node+'_FB',3:None,4:'AFEAGND',5:vin,6:node+'_NR',7:None,8:vin,9:'AFEAGND'})
 contract('J'+str(b),{1:node,2:node+'_FB',3:'AFEAGND'})
 # Every LDO capacitor belongs wholly to the floating island.
 for k in range(4):assert 'GND' not in parts['C'+str(b*10+k)]['nets'].values()
# No schematic net directly shorts the two power-return domains.
assert 'GND'!='AFEAGND'
for p in parts.values():
 if p['ref'] not in ('U400','J5'):assert not ({'GND','AFEAGND'}<=set(p['nets'].values())),p['ref']
# Actual native gate pin maps and all combinations of independent observations.
gates={'U231':('and3',['S3_WINDOW_OK','S5_WINDOW_OK','PWR_START_OK'],'SUP_READY'),
       'U232':('and2',['BATT_WINDOW_OK','PWR_START_OK'],'BATT_OK'),
       'U233':('and3',['PWR_REQUEST','BATT_OK','SUP_READY'],'HOST_ENABLE'),
       'U234':('and2',['HOST_ENABLE','HOST_5_PG'],'BOOST_ENABLE'),
       'U236':('and2',['MREF_WINDOW_OK','MID_WINDOW_OK'],'REF_OK'),
       'U237':('and2',['BOOST_ENABLE','REF_OK'],'POWER_RUN_OK')}
for ref,(kind,ins,out) in gates.items():
 expected={1:ins[0],2:'GND',3:ins[1],4:out,5:'SUP_3V3',6:ins[2]} if kind=='and3' else {1:ins[0],2:ins[1],3:'GND',4:out,5:'SUP_3V3'}
 contract(ref,expected)
contract('U235',{1:None,2:'POWER_RUN_OK',3:'GND',4:'PWR_FAULT_N',5:'SUP_3V3'})
contract('J2',{1:'PWR_REQUEST',2:'SUP_READY',3:'BATT_OK',4:'HOST_ENABLE',5:'BOOST_ENABLE',6:'HOST_3V3_PG',7:'HOST_5_PG',8:'SUP_3V3_PG',9:'SUP_5_PG',10:'SUP_3V3',11:'PWR_FAULT_N',12:'GND'})
contract('J6',{1:'MON_VREF',2:'MON_VMID',3:'GND'})
inputs=['S3_WINDOW_OK','S5_WINDOW_OK','PWR_START_OK','BATT_WINDOW_OK','PWR_REQUEST','HOST_5_PG','MREF_WINDOW_OK','MID_WINDOW_OK']
truth=0
for values in itertools.product((False,True),repeat=len(inputs)):
 state=dict(zip(inputs,values))
 for ref,(kind,ins,out) in gates.items():state[out]=all(state[n] for n in ins)
 assert state['POWER_RUN_OK']==all(values)
 # Losing the request or references pulls the open-drain fault LOW even while rails stay charged.
 if not state['PWR_REQUEST'] or not state['MREF_WINDOW_OK'] or not state['MID_WINDOW_OK']:assert not state['POWER_RUN_OK']
 truth+=1
with (HERE/'bom.csv').open(encoding='utf-8',newline='') as f:bom=list(csv.DictReader(f))
assert len(bom)==156 and {p['reference'] for p in bom}==set(parts)
erc=json.loads((HERE/'erc.json').read_text());assert not erc['ignored_checks'] and len(erc['sheets'])==15
assert not [v for s in erc['sheets'] for v in s['violations']]
assert len(list(HERE.glob('*.kicad_sch')))==15
assert len(list((HERE/'svg').glob('*.svg')))==15
assert len(re.findall(rb'/Type\s*/Page(?!s)\b',(HERE/'power.pdf').read_bytes()))==15
for n in range(1,16):assert (HERE/'review'/f'page-{n:02d}.png').stat().st_size>1000
for p in (HERE/'svg').glob('*.svg'):assert all(l==l.rstrip() for l in p.read_text().splitlines())
def digest(p):
 data=p.read_bytes()
 if p.suffix not in ('.png','.pdf'):data=data.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
 return hashlib.sha256(data).hexdigest()
visual=json.loads((HERE/'visual-review.json').read_text());assert visual['pages_reviewed']==list(range(1,16));assert visual['pdf_sha256']==digest(HERE/'power.pdf')
assert all(digest(HERE/'review'/name)==sha for name,sha in visual['png_sha256'].items())
mcp=json.loads((HERE/'mcp-inspection.json').read_text(encoding='utf-8-sig'));assert mcp['erc']['total']==mcp['erc']['errors']==mcp['erc']['warnings']==0
assert mcp['interlock_pin']['net']=='PWR_FAULT_N'
assert len(mcp['buck_pins']['pins'])==8 and len(mcp['host5_pins']['pins'])==17 and len(mcp['boost_pins']['pins'])==6 and len(mcp['iso_pins']['pins'])==7 and len(mcp['ldo_pins']['pins'])==9
assert set(mcp['overlaps'])=={p.name for p in HERE.glob('*.kicad_sch')}
assert all(v['overlap_count']==0 and not v['bounds_unresolved'] for v in mcp['overlaps'].values())
assert all(digest(HERE/name)==sha for name,sha in mcp['schematic_sha256'].items())
files=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in ('verification.json','power.kicad_prl') and not p.name.endswith('.lck') and '__pycache__' not in p.parts)
receipt={'schema':'scci_rh.stage4.power.verification.v1','date':'2026-10-14','scope':'Nativepin/pad/gate/exportandMCPsaved-revisionchecks;notphysicalbattery/converter/implantqualification','components':156,'pin_contracts_compared':checked,'sheets':15,'pdf_pages':15,'native_gate_truth_combinations':truth,'erc_violations':0,'ignored_erc_checks':[],'checks':['all156exportedvalues/footprintsand449pinconnections','exactmanufacturerselectedbuck/boost/LDO/modulepins','seriesreverseprotectionSMCandboostSOD323Fidentities','physicallyseparategrounddomainsandLDOenablepolarity','moduleRemoteNCnotfabricatedTTL','rawpowerrequestplusnativewindowswithoutARMstartupfeedback','independentreferencehealthinopen-drainpowerinterlockonly','all256gateinputcombinations','zeroERC/noignoredchecks/15PDFandSVGpages','realMCPsavedproject/pins/overlaps/ERCboundtofinalschematics'],'unqualified':m['external_unimplemented'],'hash_policy':'ExactPNG/PDF;othertextnormalizesCRLF/CRtoLF;excludesreceipt/preferences/cache','sha256':{p.relative_to(HERE).as_posix():digest(p) for p in files}}
if args.write_receipt:(HERE/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
else:assert json.loads((HERE/'verification.json').read_text())==receipt,'Revieweditsbeforeintentionalreceiptrefresh'
print(json.dumps({k:receipt[k] for k in ('components','pin_contracts_compared','sheets','native_gate_truth_combinations','erc_violations')}))
