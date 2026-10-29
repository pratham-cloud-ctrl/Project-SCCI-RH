"""Read-only audit of exported KiCad connectivity, gates and saved artifacts.

--write-receipt intentionally updates hashes after native export/visual review.
The gate/event checks are ideal Boolean checks, not propagation/supply simulation.
"""
from pathlib import Path
from collections import Counter
import argparse
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
t=ET.parse(HERE/"current_driver.xml").getroot()
exported={c.attrib["ref"]:c for c in t.findall("./components/comp")}
assert set(exported)==set(parts) and len(parts)==156
nets={}
for net in t.findall("./nets/net"):
    for n in net.findall("node"):
        key=n.attrib["ref"],n.attrib["pin"]
        assert key not in nets,key
        nets[key]=net.attrib["name"]
checked=0
for ref,p in parts.items():
    assert exported[ref].findtext("value")==p["value"],ref
    assert exported[ref].findtext("footprint")==p["footprint"],ref
    fp=HERE/"scci_rh_drv.pretty"/(p["footprint"].split(":")[1]+".kicad_mod")
    assert fp.is_file(),fp
    pads=set(re.findall(r'\(pad "([^"]+)"',fp.read_text(encoding="utf-8")))
    assert pads==set(p["nets"]),(ref,pads,set(p["nets"]))
    for pin,expected in p["nets"].items():
        got=nets.get((ref,pin))
        assert got==expected if expected is not None else got is None or got.startswith("unconnected-"),(ref,pin,got,expected)
        checked+=1
def pin(ref,n): return nets[(ref,str(n))]
def contract(ref,expected):
    for n,net in expected.items(): assert pin(ref,n)==net,(ref,n,pin(ref,n),net)
contract("U1",{1:"VDD_5",2:"CH0_VSET",3:"GND",4:"GND",5:"GND",6:"DAC_SCLK",7:"DAC_SYNC_N",8:"DAC_SDIN",9:"CH1_VSET",10:"DAC_VREF"})
assert {p["value"]:sum(v["value"]==p["value"] for v in parts.values()) for p in parts.values() if p["kind"] in ("dac","opa","sink","bridge","mux","timer")}=={"DAC80502DRXR":1,"OPA192IDBVR":2,"BSP89H6327XTSA1":2,"TMUX7212PWR":2,"TMUX6219DGKR":4,"LTC6993HS6-1#TRPBF":2}
for ch in (0,1):
    q=lambda s:f"CH{ch}_{s}"
    b=100*(ch+1); bctl=300+100*ch
    contract(f"U{b}",{1:q("SERVO"),2:"GND",3:q("VSET"),4:q("FB"),5:"VA_15"})
    contract(f"Q{b}",{1:q("GATE"),2:q("SINK_D"),3:q("SENSE_K"),4:q("SINK_D")})
    contract(f"U{b+1}",{1:q("DIAG_P"),2:q("A_BR"),3:"VH_24",4:"GND",5:"GND",6:q("SINK_D"),7:q("B_BR"),8:q("DIAG_P"),9:q("DIAG_M"),10:q("A_BR"),11:q("SINK_D"),13:"VH_24",14:"VH_24",15:q("B_BR"),16:q("DIAG_M")})
    contract(f"U{b+2}",{1:q("GATE_SW"),2:"GND",3:"GND",4:"VA_15",5:"VA_15",6:q("RUN"),7:"GND",8:q("SERVO")})
    contract(f"U{b+3}",{1:q("FB"),2:q("SERVO"),3:"GND",4:"VA_15",5:"VA_15",6:q("RUN"),7:"GND",8:q("SENSE_K")})
    contract(f"R{b}",{1:q("SENSE_K"),2:"GND"})
    contract(f"R{b+1}",{1:q("GATE_SW"),2:q("GATE")})
    contract(f"R{b+2}",{1:q("GATE"),2:"GND"})
    contract(f"U{bctl}",{1:q("REQUEST"),2:"GND",3:q("T_SET"),4:q("T_DIV"),5:"VDD_3V3",6:q("TIMER")})
    contract(f"R{bctl}",{1:q("T_SET"),2:"GND"})
    contract(f"R{bctl+1}",{1:"VDD_3V3",2:q("T_DIV")})
    contract(f"R{bctl+2}",{1:q("T_DIV"),2:"GND"})
    assert parts[f"R{bctl}"]["value"]=="175.8k 0.1%"
    assert parts[f"R{bctl+1}"]["value"]=="976k 0.1%"
    assert parts[f"R{bctl+2}"]["value"]=="182k 0.1%"
    # Package-specific FF checks are independent of the generated symbol.
    for ref,clk,d,clrn,pren,out,outn in (
        (f"U{bctl+13}","GND","GND",q("LATCH_CLR_N"),q("BLOCK_PRE_N"),q("BLOCK"),q("BLOCK_N")),
        (f"U{bctl+15}",q("TIMER_N"),q("TIMEOUT_D"),q("LATCH_CLR_N"),"VDD_3V3",q("TIMEOUT"),q("TIMEOUT_N")),
        (f"U{bctl+16}",q("SAFE_REARM"),q("PLUS_RAW"),"RESET_READY","VDD_3V3",q("PLUS_LATCHED"),q("MINUS_LATCHED")),
    ):
        assert parts[ref]["value"]=="SN74LVC1G74DCUR"
        contract(ref,{1:clk,2:d,3:outn,4:"GND",5:out,6:clrn,7:pren,8:"VDD_3V3"})
    assert all(parts[f"R{b+k}"]["value"]=="22k" for k in (3,4,5))
    assert all(parts[f"R{bctl+k}"]["value"]=="10k" for k in range(3,11))
    # Check all ICs have a dedicated supply bypass, by explicit ref and net.
    for k in range(21):
        contract(f"C{bctl+k}",{1:"VDD_3V3",2:"GND"})
    assert not any(f"CH{1-ch}_" in net for p in parts.values() if p["sheet"] in (f"source{ch}",f"permission{ch}") for net in p["nets"].values() if net)
assert all(parts[f"R{k}"]["value"]=="10k" for k in (1,2,3,4,5))
assert parts["C3"]["value"]=="220n 10V"
assert all(parts[f"C{b}"]["dnp"] for b in (100,200))

# Evaluate the exported connections using logic functions selected by exact MPN.
GATES={"SN74LVC1G08DBVR":"and2","SN74LVC1G11DBVR":"and3","SN74LVC1G86DBVR":"xor","SN74LVC1G04DBVR":"inv","SN74LVC1G32DBVR":"or"}
def evaluate(ch,external,state):
    q=lambda s:f"CH{ch}_{s}"
    values={"GND":False,"VDD_3V3":True,**external}
    for name,value in state.items():
        values[q(name)]=bool(value)
    values[q("BLOCK_N")]=not values[q("BLOCK")]
    values[q("TIMEOUT_N")]=not values[q("TIMEOUT")]
    values[q("MINUS_LATCHED")]=not values[q("PLUS_LATCHED")]
    remaining=[ref for ref,p in parts.items() if p["sheet"]==f"permission{ch}" and p["value"] in GATES]
    while remaining:
        progress=False
        for ref in remaining[:]:
            kind=GATES[parts[ref]["value"]]
            ins=(2,) if kind=="inv" else (1,3,6) if kind=="and3" else (1,2)
            if not all(pin(ref,n) in values for n in ins): continue
            v=[values[pin(ref,n)] for n in ins]
            values[pin(ref,4)]=not v[0] if kind=="inv" else bool(v[0])!=bool(v[1]) if kind=="xor" else any(v) if kind=="or" else all(v)
            remaining.remove(ref); progress=True
        assert progress,"Unresolved or cyclic combinational graph"
    return values
truth_rows=0
for ch in (0,1):
    q=lambda s:f"CH{ch}_{s}"
    extnames=[q(v) for v in ("MON_PERMIT","EXT_SUP_OK","ROUTE_LOCKED","PLUS_RAW","MINUS_RAW","REQUEST","TIMER","QUIESCENT_OK","REARM")]+["RESET_READY","RAILS_QUALIFIED"]
    for bits in itertools.product((False,True),repeat=14):
        ext=dict(zip(extnames,bits[:11])); state=dict(zip(("BLOCK","TIMEOUT","PLUS_LATCHED"),bits[11:]))
        v=evaluate(ch,ext,state)
        base=all(ext[n] for n in (q("MON_PERMIT"),q("EXT_SUP_OK"),q("ROUTE_LOCKED"),"RESET_READY","RAILS_QUALIFIED")) and ext[q("PLUS_RAW")]!=ext[q("MINUS_RAW")]
        safe=ext[q("REARM")] and base and ext[q("QUIESCENT_OK")] and not ext[q("REQUEST")] and not ext[q("TIMER")]
        run=ext[q("REQUEST")] and ext[q("TIMER")] and base and not state["BLOCK"] and not state["TIMEOUT"]
        assert v[q("BASE_GOOD")]==base
        assert v[q("SAFE_REARM")]==safe
        assert v[q("RUN")]==run
        assert v[q("DIAG_P")]==(run and state["PLUS_LATCHED"])
        assert v[q("DIAG_M")]==(run and not state["PLUS_LATCHED"])
        assert not (v[q("DIAG_P")] and v[q("DIAG_M")])
        assert v[q("TIMEOUT_D")]==(state["TIMEOUT"] or ext[q("REQUEST")])
        assert v[q("BLOCK_PRE_N")]==(base and not(ext[q("TIMER")] and not ext[q("REQUEST")]))
        assert not(not v[q("BLOCK_PRE_N")] and not v[q("LATCH_CLR_N")])
        truth_rows+=1

class EventModel:
    """Ideal-event interpretation of actual exported FF and gate nets."""
    def __init__(self,ch):
        self.ch=ch;self.q=lambda s:f"CH{ch}_{s}";b=300+100*ch
        self.refs={"BLOCK":f"U{b+13}","TIMEOUT":f"U{b+15}","PLUS_LATCHED":f"U{b+16}"}
        self.ext={self.q(n):False for n in ("MON_PERMIT","EXT_SUP_OK","ROUTE_LOCKED","PLUS_RAW","MINUS_RAW","REQUEST","TIMER","QUIESCENT_OK","REARM")}
        self.ext.update(RESET_READY=False,RAILS_QUALIFIED=False)
        self.state={n:False for n in self.refs};self.clocks={ref:False for ref in self.refs.values()}
        self.step()
    def step(self,**changes):
        for name,val in changes.items(): self.ext[name if name in ("RESET_READY","RAILS_QUALIFIED") else self.q(name)]=bool(val)
        for _ in range(12):
            v=evaluate(self.ch,self.ext,self.state);new=self.state.copy()
            for name,ref in self.refs.items():
                clk=v[pin(ref,1)];clear=not v[pin(ref,6)];preset=not v[pin(ref,7)]
                assert not(clear and preset),"Unadmitted asynchronous overlap"
                if clear:new[name]=False
                elif preset:new[name]=True
                elif clk and not self.clocks[ref]:new[name]=v[pin(ref,2)]
                self.clocks[ref]=clk
            if new==self.state:
                self.v=v;return v
            self.state=new
        raise AssertionError("Event graph did not settle")
    def good(self):self.step(MON_PERMIT=1,EXT_SUP_OK=1,ROUTE_LOCKED=1,QUIESCENT_OK=1,PLUS_RAW=1,MINUS_RAW=0,RESET_READY=1,RAILS_QUALIFIED=1)
    def rearm(self):self.step(REQUEST=0,TIMER=0,REARM=0);self.step(REARM=1);self.step(REARM=0)
    def start(self):self.step(REQUEST=1);return self.step(TIMER=1)
    def out(self,n):return self.v[self.q(n)]
probes=[]
for ch in (0,1):
    x=EventModel(ch);assert x.out("BLOCK") and not x.out("RUN");x.good();assert x.out("BLOCK");probes.append(f"source{ch}: startup and health restoration remain blocked")
    x.rearm();assert not x.out("BLOCK") and x.out("PLUS_LATCHED");x.start();assert x.out("DIAG_P") and not x.out("DIAG_M")
    x.step(REQUEST=0);assert x.out("BLOCK") and not x.out("RUN");x.step(TIMER=0);assert not x.out("TIMEOUT");probes.append(f"source{ch}: normal end consumes admission without timeout")
    x.step(REQUEST=1,TIMER=1);assert not x.out("RUN");probes.append(f"source{ch}: repeated request cannot reopen consumed permission")
    x.rearm();x.start();x.step(TIMER=0);assert x.out("TIMEOUT") and not x.out("RUN");x.step(REQUEST=0);x.step(REQUEST=1,TIMER=1);assert x.out("TIMEOUT") and not x.out("RUN");probes.append(f"source{ch}: held request times out and remains latched")
    x.rearm();x.start();x.step(MON_PERMIT=0);assert x.out("BLOCK") and not x.out("RUN");x.step(MON_PERMIT=1);assert not x.out("RUN");probes.append(f"source{ch}: monitor interruption cannot restart on recovery")
    x.rearm();x.start();x.step(PLUS_RAW=0,MINUS_RAW=1);assert x.out("PLUS_LATCHED") and x.out("DIAG_P") and not x.out("DIAG_M");probes.append(f"source{ch}: valid raw direction swap cannot commutate bridge")
    x.step(PLUS_RAW=1,MINUS_RAW=1);assert x.out("BLOCK") and not x.out("RUN");x.step(PLUS_RAW=0,MINUS_RAW=1);assert not x.out("RUN");probes.append(f"source{ch}: invalid raw direction latches admission off")
    x.step(REQUEST=0,TIMER=0,QUIESCENT_OK=0,REARM=1);assert x.out("BLOCK");x.step(REARM=0);probes.append(f"source{ch}: unobserved quiescence cannot rearm")
    x.step(QUIESCENT_OK=1);x.rearm();assert not x.out("PLUS_LATCHED");x.start();assert x.out("DIAG_M") and not x.out("DIAG_P");probes.append(f"source{ch}: negative phase is captured while inhibited at rearm")
    x.step(REARM=1);assert not x.out("SAFE_REARM");probes.append(f"source{ch}: rearm asserted during phase has no authority")

with (HERE/"bom.csv").open(encoding="utf-8",newline="") as f:bom=list(csv.DictReader(f))
assert len(bom)==156 and {r["reference"] for r in bom}==set(parts)
erc=json.loads((HERE/"erc.json").read_text(encoding="utf-8"))
assert erc["ignored_checks"]==[]
assert len(erc["sheets"])==len(t.findall("./design/sheet"))==5
assert not [v for s in erc["sheets"] for v in s["violations"]]
pdf=HERE/"current_driver.pdf"
pages=len(re.findall(rb"/Type\s*/Page(?!s)\b",pdf.read_bytes()))
assert pages==5
try:
    from pypdf import PdfReader
except ImportError:pass
else:assert len(PdfReader(pdf).pages)==5
for name in ("current_driver.svg","current_driver-Source0_analog.svg","current_driver-Source0_permission.svg","current_driver-Source1_analog.svg","current_driver-Source1_permission.svg"):
    assert (HERE/"svg"/name).stat().st_size>1000
for i in range(1,6):assert (HERE/"review"/f"page-{i}.png").stat().st_size>1000
n=m["nominal"]
assert n["DAC_GAIN_register"]==0x0103
assert math.isclose(n["DAC_current_A"],7864*2.5/65536/100,rel_tol=1e-13)
assert math.isclose(n["command_charge_C"],n["DAC_current_A"]*200e-6,rel_tol=1e-13)
assert math.isclose(n["timer_nominal_s"],225.024e-6,rel_tol=1e-13)
assert n["timer_min_s"]>200e-6 and n["timer_max_s"]<236e-6
assert len(m["external_unimplemented"])>=10
def digest(p):
    data=p.read_bytes()
    if p.suffix not in (".png",".pdf"):data=data.replace(b"\r\n",b"\n").replace(b"\r",b"\n")
    return hashlib.sha256(data).hexdigest()
files=sorted(p for p in HERE.rglob("*") if p.is_file() and p.name not in ("verification.json","current_driver.kicad_prl") and not p.name.endswith(".lck") and "__pycache__" not in p.parts)
receipt={"schema":"scci_rh.stage4.current-driver.verification.v1","date":"2026-10-13","scope":"Native connectivity, export integrity and ideal gate/event contracts only; no analog/hazard/biological qualification","kicad_version":erc["kicad_version"],"components":156,"pin_contracts_compared":checked,"sheets":5,"pdf_pages":5,"erc_violations":0,"ignored_erc_checks":[],"exhaustive_exported_gate_rows":truth_rows,"ideal_event_probes":probes,"checks":["all exported pin/net/value/footprint assignments","actual local footprint pad-number sets match symbols including BSP89 tab4 and DRX10/noEP","independent package-specific functional contracts","one local bypass per logic/timer IC","channel isolation in exported signal names","all32768 exported-gate truth rows","20 ideal-event probes from exported FF/gate connections","BOM/ERC/PDF/SVG/review-image integrity","DAC/configuration and healthytimer arithmetic"],"hash_policy":"SHA256 exactPNG/PDF; other includedtextnormalizesCRLF/CRtoLF; excludesreceipt/localpreferences/Pythoncache","unqualified":["analog currentaccuracy/settling/tails","propagation/setuphold/asynccontrolhazards","powersequencingoutsidevalidlogicrange","RSET-open/timerstuckfault","railoffterminalisolation","deliveredchargeguard","monitorbiasloadbypass","externalwatchdog/compliance/route/quiescencesupervision","MCUfirmware","PCB/CAD/implantqualification","biologicalefficacy"],"sha256":{p.relative_to(HERE).as_posix():digest(p) for p in files}}
if args.write_receipt:(HERE/"verification.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
else:assert json.loads((HERE/"verification.json").read_text(encoding="utf-8"))==receipt,"Frozen receipt differs; review intentional native/source changes before refresh"
print(json.dumps({k:receipt[k] for k in ("components","pin_contracts_compared","sheets","pdf_pages","erc_violations","exhaustive_exported_gate_rows")}))
