"""Read-only audit of native exported recording paths and frozen artifacts.

--write-receipt intentionally refreshes reviewed exports; no KiCad installation
or analog simulator is required for the saved-package audit. This does not
qualify physical isolation, amplifier linearity, switch transients or biology.
"""
from pathlib import Path
import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument("--write-receipt",action="store_true")
args=ap.parse_args()
HERE=Path(__file__).resolve().parent
m=json.loads((HERE/"connectivity.json").read_text(encoding="utf-8"))
parts={p["ref"]:p for p in m["parts"]}
t=ET.parse(HERE/"recording_front_end.xml").getroot()
exported={c.attrib["ref"]:c for c in t.findall("./components/comp")}
assert set(parts)==set(exported) and len(parts)==151
nets={}
for net in t.findall("./nets/net"):
 for node in net.findall("node"):
  key=node.attrib["ref"],node.attrib["pin"]
  assert key not in nets,key
  nets[key]=net.attrib["name"]
def pin(ref,n):return nets[(ref,str(n))]
def contract(ref,expected):
 for n,want in expected.items():assert pin(ref,n)==want,(ref,n,pin(ref,n),want)
checked=0
for ref,p in parts.items():
 assert exported[ref].findtext("value")==p["value"],ref
 assert exported[ref].findtext("footprint")==p["footprint"],ref
 fp=HERE/"scci_rh_afe.pretty"/(p["footprint"].split(":")[1]+".kicad_mod")
 pads={s for s in re.findall(r'\(pad "([^\"]*)"',fp.read_text(encoding="utf-8")) if s}
 assert pads==set(p["nets"]),(ref,pads,set(p["nets"]))
 for n,want in p["nets"].items():
  got=nets.get((ref,n))
  assert got==want if want is not None else got is None or got.startswith("unconnected-"),(ref,n,got,want)
  checked+=1
counts=Counter(p["value"] for p in parts.values())
assert {v:counts[v] for v in ("RHD2216","TMUX7412FRRPR","TMUX6219DGKR","ISO6741FDWR","SN74LVC1G04DBVR","SN74LVC1G08DBVR")}=={"RHD2216":1,"TMUX7412FRRPR":5,"TMUX6219DGKR":17,"ISO6741FDWR":2,"SN74LVC1G04DBVR":1,"SN74LVC1G08DBVR":1}
# Manufacturer top-view pin contracts, independent of generated symbol order.
positive_pins=(9,7,5,3,1,55,53,51,49,47,45,43,41,39,37,35)
negative_pins=(8,6,4,2,56,54,52,50,48,46,44,42,40,38,36,34)
for ch,n in enumerate(positive_pins):contract("U10",{n:f"AFE_IN{ch:02d}_P"})
for n in negative_pins:contract("U10",{n:"AFE_REF"})
contract("U10",{10:"AFEAGND",11:"AFEAGND",12:"AFEAGND",13:"AFE_3V3",14:"AFE_3V3",15:"AFE_3V3",16:"AFE_3V3",17:"AFEAGND",19:"AFE_CS_N",21:"AFE_SCLK",23:"AFE_MOSI",25:"AFE_MISO",26:"AFE_3V3",28:"AFE_ADC_REF",29:"AFEAGND",30:"AFEAGND",31:"AFE_3V3",32:"AFEAGND",33:"AFEAGND",57:"AFEAGND"})
for n in (18,20,22,24,27):assert ("U10",str(n)) not in nets or nets[("U10",str(n))].startswith("unconnected-")
for ch in range(16):
 tag=f"{ch:02d}";b=100+ch;quad=f"U{20+ch//4}"
 source,drain,selector=((1,16,15),(12,13,14),(9,8,7),(4,5,6))[ch%4]
 contract(f"R{b}",{1:f"REC{tag}_CONTACT",2:f"REC{tag}_SERIES"})
 contract(quad,{source:f"REC{tag}_SERIES",drain:f"REC{tag}_PROT",selector:"AFE_CONNECT"})
 contract(f"R{b+100}",{1:f"REC{tag}_PROT",2:"AFEAGND"})
 contract(f"U{b}",{1:f"AFE_IN{tag}_P",2:"AFEAGND",3:"AFEAGND",4:"AFE_P5",5:"AFE_3V3",6:"AFE_ACQUIRE",7:"AFE_N5",8:f"REC{tag}_PROT"})
 contract(f"C{b}",{1:f"AFE_IN{tag}_P",2:"AFEAGND"})
 assert parts[f"R{b}"]["value"]=="4.99k 0.1%"
 assert parts[f"R{b+100}"]["value"]=="10M"
 assert parts[f"C{b}"]["value"]=="470p C0G 50V"
 for ref,rail in ((f"C{b+100}","AFE_P5"),(f"C{b+200}","AFE_N5")):contract(ref,{1:rail,2:"AFEAGND"})
for quad in range(20,25):contract(f"U{quad}",{2:"AFE_N5",3:"AFEAGND",10:"AFE_FAULT_N",11:"AFE_P5",17:"AFEAGND"})
contract("R500",{1:"REF_CONTACT",2:"REF_SERIES"})
contract("U24",{1:"REF_SERIES",16:"REF_PROT",15:"AFE_CONNECT"})
for n in (12,13,9,8,4,5,14,7,6):contract("U24",{n:"AFEAGND"})
contract("R501",{1:"REF_PROT",2:"AFEAGND"})
contract("U500",{1:"AFE_REF",2:"AFEAGND",3:"AFEAGND",4:"AFE_P5",5:"AFE_3V3",6:"AFE_ACQUIRE",7:"AFE_N5",8:"REF_PROT"})
contract("C500",{1:"AFE_REF",2:"AFEAGND"})
assert parts["R500"]["value"]=="4.99k 0.1%" and parts["R501"]["value"]=="10M"
assert parts["C500"]["value"]=="2.2n C0G 50V"
contract("R502",{1:"BIAS_CONTACT",2:"BIAS_MID"});contract("R503",{1:"BIAS_MID",2:"AFEAGND"})
assert parts["R502"]["value"]==parts["R503"]["value"]=="499k 0.1%"
# No conductive host/AFE bridge is hidden in passive wiring. Only the two
# specified galvanic isolator symbols contain pins from both domains.
for ref,p in parts.items():
 named={n for n in p["nets"].values() if n}
 host={n for n in named if n.startswith("HOST")}
 if host and ref not in ("U1","U2","J2"):
  assert named<=host,(ref,named)
assert pin("J2",2)=="HOSTGND" and pin("J1",4)=="AFEAGND"
for ref in ("U1","U2"):
 contract(ref,{1:"HOST_3V3",2:"HOSTGND",7:"HOST_3V3",8:"HOSTGND",9:"AFEAGND",10:"AFE_3V3",15:"AFEAGND",16:"AFE_3V3"})
contract("U1",{3:"HOST_SCLK",4:"HOST_MOSI",5:"HOST_CS_ASSERT",6:"HOST_MISO",11:"AFE_MISO",12:"AFE_CS_ASSERT",13:"AFE_MOSI",14:"AFE_SCLK"})
contract("U2",{3:"HOST_CONNECT_CMD",4:"HOST_RECORD_CMD",5:"HOSTGND",6:"HOST_FAULT_N",11:"AFE_FAULT_N",13:"AFE_RECORD_CMD",14:"AFE_CONNECT"})
contract("U3",{2:"AFE_CS_ASSERT",3:"AFEAGND",4:"AFE_CS_N",5:"AFE_3V3"})
contract("U4",{1:"AFE_CONNECT",2:"AFE_RECORD_CMD",3:"AFEAGND",4:"AFE_ACQUIRE",5:"AFE_3V3"})
for ref,net in (("R7","AFE_CONNECT"),("R8","AFE_RECORD_CMD"),("R9","AFE_ACQUIRE"),("R10","AFE_CS_ASSERT"),("R12","AFE_SCLK"),("R13","AFE_MOSI")):
 contract(ref,{1:net,2:"AFEAGND"});assert parts[ref]["value"]=="10k"
contract("R11",{1:"AFE_CS_N",2:"AFE_3V3"});assert parts["R11"]["value"]=="10k"
contract("R14",{1:"AFE_FAULT_N",2:"AFE_3V3"});assert parts["R14"]["value"]=="1k"
assert sum(p["kind"]=="R" and set(p["nets"].values())=={"AFE_FAULT_N","AFE_3V3"} for p in parts.values())==1
contacts=[pin("J3",n) for n in range(1,19)]
assert contacts==[f"REC{ch:02d}_CONTACT" for ch in range(16)]+["REF_CONTACT","BIAS_CONTACT"]
assert len(set(contacts))==18 and "STIM" not in " ".join(nets.values())
contract("C10",{1:"AFE_3V3",2:"AFEAGND"});contract("C11",{1:"AFE_3V3",2:"AFEAGND"});contract("C12",{1:"AFE_ADC_REF",2:"AFEAGND"})
assert parts["C12"]["value"]=="10n 16V"
# Check land geometry and numbering actually saved in local footprints.
def geometry(name):
 text=(HERE/"scci_rh_afe.pretty"/(name+".kicad_mod")).read_text(encoding="utf-8")
 return {int(n):tuple(map(float,(x,y,sx,sy))) for n,x,y,sx,sy in re.findall(r'\(pad "(\d+)" smd rect \(at (-?[\d.]+) (-?[\d.]+)\) \(size ([\d.]+) ([\d.]+)\)',text)}
rhd=geometry("RHD2216_QFN56_8x8_P0.5_EP6.1")
assert len(rhd)==57 and rhd[57]==(0,0,6.1,6.1)
for n,v in {1:(-4.05,-3.25,.9,.25),14:(-4.05,3.25,.9,.25),15:(-3.25,4.05,.25,.9),28:(3.25,4.05,.25,.9),29:(4.05,3.25,.9,.25),42:(4.05,-3.25,.9,.25),43:(3.25,-4.05,.25,.9),56:(-3.25,-4.05,.25,.9)}.items():assert rhd[n]==v,(n,rhd[n],v)
rrp=geometry("Texas_RRP0016A_WQFN16_4x4_P0.65_EP2.6")
assert len(rrp)==17 and rrp[17]==(0,0,2.6,2.6)
for n,v in {1:(-1.9,-.975,.6,.3),4:(-1.9,.975,.6,.3),5:(-.975,1.9,.3,.6),8:(.975,1.9,.3,.6),9:(1.9,.975,.6,.3),12:(1.9,-.975,.6,.3),13:(.975,-1.9,.3,.6),16:(-.975,-1.9,.3,.6)}.items():assert rrp[n]==v,(n,rrp[n],v)
for name in ("RHD2216_QFN56_8x8_P0.5_EP6.1","Texas_RRP0016A_WQFN16_4x4_P0.65_EP2.6"):
 text=(HERE/"scci_rh_afe.pretty"/(name+".kicad_mod")).read_text(encoding="utf-8")
 assert text.count('(pad "" smd rect')==9 and '(layers "F.Paste")' in text
truth=[]
for connect,record,cs_assert in itertools.product((0,1),repeat=3):
 acquire=bool(connect and record);cs_n=not cs_assert
 assert not acquire if not connect else True
 truth.append({"connect":connect,"record":record,"cs_assert":cs_assert,"acquire":acquire,"cs_n":cs_n})
n=m["nominal"]
assert n["reference_input_C_typ_F"]==16*n["RHD_input_C_each_typ_F"]
assert math.isclose(n["body_bias_24V_arithmetic_A"],24/(499000*2),rel_tol=1e-12)
assert n["SPI_clock_Hz"]==4000000 and n["SPI_command_slot_s"]==5e-6
assert math.isclose(n["commands_per_frame"]*n["SPI_command_slot_s"],95e-6,rel_tol=1e-12)
with (HERE/"bom.csv").open(encoding="utf-8",newline="") as f:bom=list(csv.DictReader(f))
assert len(bom)==151 and {r["reference"] for r in bom}==set(parts)
erc=json.loads((HERE/"erc.json").read_text(encoding="utf-8"))
assert erc["ignored_checks"]==[] and len(erc["sheets"])==7
assert not [v for s in erc["sheets"] for v in s["violations"]]
pdf=HERE/"recording_front_end.pdf"
assert len(re.findall(rb"/Type\s*/Page(?!s)\b",pdf.read_bytes()))==7
try:from pypdf import PdfReader
except ImportError:pass
else:assert len(PdfReader(pdf).pages)==7
assert len(list((HERE/"svg").glob("*.svg")))==7
for i in range(1,8):assert (HERE/"review"/f"page-{i}.png").stat().st_size>1000
def digest(p):
 data=p.read_bytes()
 if p.suffix not in (".png",".pdf"):data=data.replace(b"\r\n",b"\n").replace(b"\r",b"\n")
 return hashlib.sha256(data).hexdigest()
files=sorted(p for p in HERE.rglob("*") if p.is_file() and p.name not in ("verification.json","recording_front_end.kicad_prl") and not p.name.endswith(".lck") and "__pycache__" not in p.parts)
receipt={"schema":"scci_rh.stage4.recording-front-end.verification.v1","date":"2026-10-13","scope":"Saved native connectivity, actual land identity and ideal control defaults only; no analog/physical/biological qualification","kicad_version":erc["kicad_version"],"components":151,"pin_contracts_compared":checked,"sheets":7,"pdf_pages":7,"erc_violations":0,"ignored_erc_checks":[],"protected_signal_paths":17,"functional_recording_ports":18,"ideal_control_rows":truth,"checks":["all exported component pin/net/value/footprint assignments","manufacturer top-view RHD2216 positive/negative/CMOS/power/reference/EP contracts","all17 series/source-fault/internal-bleed/clamp/RHD paths","sixteen470pF and one2.2nF RHD-side capacitors","single shared reference and separate two-resistor bias","no hardwired host/AFE ground bridge","ISO6741F directions, domains, enables and default-aware CS inverter","actual AND gate retains clamp for invalid01 command","five open-drain fault flags with exactly one1k pullup","manufacturer custom RHD56/RRP16+EP copper pad dimensions, orientation and reduced paste windows","BOM, zero ERC, seven PDF/SVG pages and render-image integrity"],"hash_policy":"SHA256 exactPNG/PDF; other includedtextnormalizesCRLF/CRtoLF; excludesreceipt/localpreferences/Pythoncache","unqualified":["actual isolation and voltage qualification","fault/injection/leakage/parasitic worst-case bounds","rail generation/sequencing and supply transient behavior","SPI firmware and timestamp correctness on hardware","electrode/recorded signal quality or decoding","blanking/fast-settle/digital filter recovery","passive exact MPN, voltage/pulse and assembly ratings","PCB/CAD/implant/medical efficacy"],"sha256":{p.relative_to(HERE).as_posix():digest(p) for p in files}}
if args.write_receipt:(HERE/"verification.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
else:assert json.loads((HERE/"verification.json").read_text(encoding="utf-8"))==receipt,"Frozen receipt differs; review intentional source/native/export changes before refresh"
print(json.dumps({k:receipt[k] for k in ("components","pin_contracts_compared","sheets","pdf_pages","erc_violations","protected_signal_paths","functional_recording_ports")}))
