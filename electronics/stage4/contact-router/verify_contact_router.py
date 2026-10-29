"""Read-only saved native routing, package-pin and ideal-gate verification.

Use --write-receipt only after intentional edits, fresh native export and visual
review. This does not qualify analog switch state, propagation or an implant.
"""
from pathlib import Path
from collections import Counter
import argparse
import csv
import hashlib
import itertools
import json
import re
import xml.etree.ElementTree as ET

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument("--write-receipt",action="store_true")
args=ap.parse_args()
HERE=Path(__file__).resolve().parent
m=json.loads((HERE/"connectivity.json").read_text(encoding="utf-8"))
parts={p["ref"]:p for p in m["parts"]}
tree=ET.parse(HERE/"contact_router.xml").getroot()
exported={c.attrib["ref"]:c for c in tree.findall("./components/comp")}
assert set(exported)==set(parts) and len(parts)==155
nets={}
for net in tree.findall("./nets/net"):
    for node in net.findall("node"):
        key=node.attrib["ref"],node.attrib["pin"]
        assert key not in nets,key
        nets[key]=net.attrib["name"]
checked=0
for ref,p in parts.items():
    assert exported[ref].findtext("value")==p["value"],ref
    assert exported[ref].findtext("footprint")==p["footprint"],ref
    fp=HERE/"scci_rh_rte.pretty"/(p["footprint"].split(":")[1]+".kicad_mod")
    assert fp.is_file(),fp
    pads=set(re.findall(r'\(pad "([^\"]+)"',fp.read_text(encoding="utf-8")))
    assert pads==set(p["nets"]),(ref,pads,set(p["nets"]))
    for number,expected in p["nets"].items():
        got=nets.get((ref,number))
        assert got==expected if expected is not None else got is None or got.startswith("unconnected-"),(ref,number,got,expected)
        checked+=1
def pin(ref,number):return nets.get((ref,str(number)))
def contract(ref,expected):
    for number,expected_net in expected.items():
        actual=pin(ref,number)
        assert actual==expected_net if expected_net is not None else actual is None or actual.startswith("unconnected-"),(ref,number,actual,expected_net)
counts=Counter(p["value"] for p in parts.values() if p["kind"] not in ("R","C","J"))
assert counts["TMUX6208PWR"]==4 and "TMUX8108PWR" not in counts
assert counts["SN74LVC595APWR"]==1 and counts["SN74LVC157APWR"]==2
assert counts["SN74LVC1G74DCUR"]==11
for ch in (0,1):
    q=lambda n:f"CH{ch}_{n}";base=100*(ch+1)
    for bank in (0,1):
        expected={1:q("ADDR0"),16:q("ADDR1"),15:q("ADDR2"),2:q(f"BANK{bank}_EN"),13:"VH_24",3:"GND",14:"GND",8:q("A_ROUTER")}
        for offset,number in enumerate((4,5,6,7,12,11,10,9)):expected[number]=f"STIM{bank*8+offset:02d}_CONTACT"
        contract(f"U{base+bank}",expected)
        assert set(parts[f"U{base+bank}"]["nets"])=={str(i) for i in range(1,17)}
        contract(f"C{base+bank}",{1:"VH_24",2:"GND"})
        contract(f"C{base+bank+2}",{1:"VH_24",2:"GND"})
        contract(f"R{base+bank}",{1:q(f"BANK{bank}_EN"),2:"GND"})
        assert parts[f"R{base+bank}"]["value"]=="22k"
    contract(f"J{base}",{1:q("A_ROUTER"),2:q("RETURN_LOAD"),3:"GND"})
    # A dedicated return has ONLY two connector pins in this native slice.
    # The existing monitor's load-side return/shunt remains external and cannot
    # be silently replaced by a direct B_BR path in this package.
    assert {(ref,n) for (ref,n),net in nets.items() if net==q("RETURN_LOAD")}=={(f"J{base}","2"),("J7",str(17+ch))}
    assert not any(q("B_BR")==net for net in nets.values())
    assert not any("REF_CONTACT"==net or "BIAS_CONTACT"==net for net in nets.values())
    for bit in range(4):
        ref=f"U{30+ch*4+bit}"
        contract(ref,{1:"ROUTE_COMMIT",2:q(f"ADDR_D{bit}"),6:"RESET_READY",7:"VDD_3V3",8:"VDD_3V3",4:"GND",5:q(f"ADDR{bit}"),3:None})
        contract(f"C{30+ch*4+bit}",{1:"VDD_3V3",2:"GND"})
    mux={1:"QUIET_SAFE",15:"GND",16:"VDD_3V3",8:"GND"}
    for bit,(ain,bin,yout) in enumerate(((2,3,4),(5,6,7),(11,10,9),(14,13,12))):
        mux[ain]=q(f"ADDR{bit}");mux[bin]=q(f"PENDING{bit}");mux[yout]=q(f"ADDR_D{bit}")
    contract(f"U{20+ch}",mux)
    contract(f"C{20+ch}",{1:"VDD_3V3",2:"GND"})
contract("U10",{14:"ROUTE_SER",11:"ROUTE_SRCLK",12:"ROUTE_PRELOAD_LATCH",10:"RESET_READY",13:"GND",16:"VDD_3V3",8:"GND",9:"ROUTE_SHIFT_TAIL"}|dict(zip((15,1,2,3,4,5,6,7),(f"CH{ch}_PENDING{bit}" for ch in (0,1) for bit in range(4)))))
contract("C10",{1:"VDD_3V3",2:"GND"})
contract("J6",{i+1:f"CH{ch}_ADDR{bit}" for i,(ch,bit) in enumerate((ch,bit) for ch in (0,1) for bit in range(4))}|{9:"GND"})
contract("J7",{i+1:f"STIM{i:02d}_CONTACT" for i in range(16)}|{17:"CH0_RETURN_LOAD",18:"CH1_RETURN_LOAD"})
for ref,clk,d,clear,out in (("U314","ROUTE_COMMIT","QUIET_SAFE","BASE_HEALTH","COMMIT_SEEN"),("U316","ROUTE_ACTIVE_BITS_VERIFIED","COMMIT_SEEN","ACK_CLR_N","READBACK_SEEN"),("U318","ROUTE_REARM","REARM_D","VALID_CLR_N","ROUTE_VALID")):
    contract(ref,{1:clk,2:d,3:None,4:"GND",5:out,6:clear,7:"VDD_3V3",8:"VDD_3V3"})
for sheet,base in (("admission",300),("collision",400)):
    refs=[ref for ref,p in parts.items() if p["sheet"]==sheet and p["kind"] not in ("R","C","J")]
    for ref in refs:contract("C"+ref[1:],{1:"VDD_3V3",2:"GND"})
assert all(p["value"]=="10k" for p in parts.values() if p["kind"]=="R" and p["sheet"] in ("address","admission"))

GATES={"SN74LVC1G08DBVR":"and2","SN74LVC1G11DBVR":"and3","SN74LVC1G32DBVR":"or","SN74LVC1G86DBVR":"xor","SN74LVC1G04DBVR":"inv"}
FFS=[ref for ref,p in parts.items() if p["value"]=="SN74LVC1G74DCUR"]
raw_clocks={"ROUTE_COMMIT","ROUTE_ACTIVE_BITS_VERIFIED","ROUTE_REARM"}
assert {pin(ref,1) for ref in FFS}==raw_clocks,"All FF clocks must be raw external inputs, never readiness-gated clocks"
# Build a topological execution plan directly from exported pin nets. Exact
# manufacturer MPNs select logic; descriptive manifest equations are not used.
external_names=["RESET_READY","RAILS_QUALIFIED","WATCHDOG_OK","AFE_ISOLATED_READY","CH0_MON_PERMIT","CH1_MON_PERMIT","CH0_QUIESCENT_OK","CH1_QUIESCENT_OK","CH0_WANT_ROUTE","CH1_WANT_ROUTE","CH0_REQUEST","CH1_REQUEST","CH0_RUN","CH1_RUN","ROUTE_COMMIT","ROUTE_ACTIVE_BITS_VERIFIED","ROUTE_REARM"]
state_names=[pin(ref,5) for ref in FFS]
known={"GND","VDD_3V3",*external_names,*state_names,*(f"CH{ch}_PENDING{bit}" for ch in (0,1) for bit in range(4))}
pending=[ref for ref,p in parts.items() if p["value"] in GATES]
plan=[]
while pending:
    progress=False
    for ref in pending[:]:
        kind=GATES[parts[ref]["value"]]
        numbers=(2,) if kind=="inv" else (1,3,6) if kind=="and3" else (1,2)
        inputs=tuple(pin(ref,n) for n in numbers)
        if not all(n in known for n in inputs):continue
        plan.append((kind,inputs,pin(ref,4)));known.add(pin(ref,4));pending.remove(ref);progress=True
    assert progress,"Combinational graph cycle or unresolved input"
def evaluate(external,state,pending_addresses=(0,0)):
    values={"GND":False,"VDD_3V3":True,**external,**state}
    for ch,address in enumerate(pending_addresses):
        for bit in range(4):values[f"CH{ch}_PENDING{bit}"]=bool(address&(1<<bit))
    for kind,inputs,out in plan:
        a=values[inputs[0]]
        if kind=="inv":value=not a
        elif kind=="xor":value=a!=values[inputs[1]]
        elif kind=="or":value=a or values[inputs[1]]
        elif kind=="and2":value=a and values[inputs[1]]
        else:value=a and values[inputs[1]] and values[inputs[2]]
        values[out]=bool(value)
    for ch in (0,1):
        ref=f"U{20+ch}";select=values[pin(ref,1)];disabled=values[pin(ref,15)]
        for ain,bin,yout in ((2,3,4),(5,6,7),(11,10,9),(14,13,12)):
            values[pin(ref,yout)]=False if disabled else values[pin(ref,bin if select else ain)]
    return values
def state_for(addresses=(3,9),commit=True,ack=True,valid=True):
    state={"COMMIT_SEEN":commit,"READBACK_SEEN":ack,"ROUTE_VALID":valid}
    for ch,address in enumerate(addresses):
        for bit in range(4):state[f"CH{ch}_ADDR{bit}"]=bool(address&(1<<bit))
    return state
defaults={n:False for n in external_names}
health_names=external_names[:6]
activity_names=external_names[8:14]
truth_rows=0
for bits in itertools.product((False,True),repeat=18):
    ext=defaults|dict(zip(health_names,bits[:6]))|dict(zip(activity_names,bits[6:12]))|dict(zip(("CH0_QUIESCENT_OK","CH1_QUIESCENT_OK"),bits[12:14]))|{"ROUTE_COMMIT":bits[17]}
    state=state_for(commit=bits[14],ack=bits[15],valid=bits[16])
    values=evaluate(ext,state,pending_addresses=(6,12))
    base=all(ext[n] for n in health_names)
    quiet=base and ext["CH0_QUIESCENT_OK"] and ext["CH1_QUIESCENT_OK"] and not any(ext[n] for n in activity_names)
    ready=state["ROUTE_VALID"] and base and not ext["ROUTE_COMMIT"]
    assert values["BASE_HEALTH"]==base and values["QUIET_SAFE"]==quiet
    assert values["REARM_D"]==(state["COMMIT_SEEN"] and state["READBACK_SEEN"] and quiet)
    assert values["ACK_CLR_N"]==(base and not ext["ROUTE_COMMIT"])
    assert values["VALID_CLR_N"]==(base and not ext["ROUTE_COMMIT"])
    assert values["ROUTE_COMMAND_READY"]==ready
    for ch in (0,1):
        enable=ready and ext[f"CH{ch}_WANT_ROUTE"]
        assert values[f"CH{ch}_ROUTE_EN"]==enable and values[f"CH{ch}_ROUTE_LOCKED"]==enable
        assert not(values[f"CH{ch}_BANK0_EN"] and values[f"CH{ch}_BANK1_EN"])
        for bit in range(4):assert values[f"CH{ch}_ADDR_D{bit}"]==(bool((6,12)[ch]&(1<<bit)) if quiet else state[f"CH{ch}_ADDR{bit}"])
    truth_rows+=1
collision_rows=0
for a0,a1,w0,w1,valid,healthy,commit in itertools.product(range(16),range(16),(False,True),(False,True),(False,True),(False,True),(False,True)):
    ext=defaults|{n:healthy for n in health_names}|{"CH0_WANT_ROUTE":w0,"CH1_WANT_ROUTE":w1,"ROUTE_COMMIT":commit}
    values=evaluate(ext,state_for((a0,a1),valid=valid))
    conflict=w0 and w1 and a0==a1
    ready=valid and healthy and not commit and not conflict
    assert values["ROUTE_ADDR_EQUAL"]==(a0==a1) and values["ROUTE_CONFLICT"]==conflict
    assert values["VALID_CLR_N"]==(healthy and not commit and not conflict)
    assert values["ROUTE_COMMAND_READY"]==ready
    for ch,address,want in ((0,a0,w0),(1,a1,w1)):
        enable=ready and want
        assert values[f"CH{ch}_BANK0_EN"]==(enable and address<8)
        assert values[f"CH{ch}_BANK1_EN"]==(enable and address>=8)
    collision_rows+=1

class EventModel:
    """Ideal external-edge/asynchronous-clear model of the exported FF pins."""
    def __init__(self):
        self.external=defaults.copy();self.state={n:False for n in state_names};self.pending=(0,0)
        self.clocks={ref:False for ref in FFS};self.events=0;self.step()
    def settle(self):
        for _ in range(12):
            values=evaluate(self.external,self.state,self.pending);new=self.state.copy()
            for ref in FFS:
                assert values[pin(ref,7)],"No asynchronous preset is admitted"
                if not values[pin(ref,6)]:new[pin(ref,5)]=False
            if new==self.state:return values
            self.state=new
        raise AssertionError("Asynchronous state did not settle")
    def step(self,pending=None,**changes):
        self.external.update({key:bool(value) for key,value in changes.items()})
        if pending is not None:self.pending=tuple(pending)
        values=self.settle();new=self.state.copy()
        for ref in FFS:
            clk=values[pin(ref,1)]
            if not values[pin(ref,6)]:new[pin(ref,5)]=False
            elif clk and not self.clocks[ref]:new[pin(ref,5)]=bool(values[pin(ref,2)])
            self.clocks[ref]=bool(clk)
        self.state=new;self.values=self.settle();self.events+=1
        return self.values
    def pulse(self,name):
        self.step(**{name:False});self.step(**{name:True});return self.step(**{name:False})
    def arm(self,addresses=(3,9)):
        self.step(**{name:True for name in health_names},CH0_QUIESCENT_OK=True,CH1_QUIESCENT_OK=True,pending=addresses)
        self.pulse("ROUTE_COMMIT");self.pulse("ROUTE_ACTIVE_BITS_VERIFIED");self.pulse("ROUTE_REARM")
        assert self.values["ROUTE_COMMAND_READY"]
    def address(self,ch):return sum(int(self.state[f"CH{ch}_ADDR{bit}"])<<bit for bit in range(4))
probes=[];event_steps=0
def record(name,model):
    global event_steps
    probes.append(name);event_steps+=model.events
p=EventModel();p.step(RESET_READY=True);p.pulse("ROUTE_REARM");assert not p.values["ROUTE_COMMAND_READY"];record("startup cannot arm without a legal commit and fresh verification",p)
p=EventModel();p.arm();p.step(CH0_WANT_ROUTE=True,CH1_WANT_ROUTE=True);assert p.values["CH0_BANK0_EN"] and p.values["CH1_BANK1_EN"];record("different contacts permit both independent sources",p)
p=EventModel();p.arm();p.step(CH0_WANT_ROUTE=True,CH0_REQUEST=True,CH0_RUN=True,pending=(4,10));assert p.address(0)==3;record("candidate preload does not move active route during a phase",p)
for condition in activity_names:
    p=EventModel();p.arm();p.step(**{condition:True},pending=(4,10));p.pulse("ROUTE_COMMIT")
    assert (p.address(0),p.address(1))==(3,9) and not p.state["COMMIT_SEEN"] and not p.values["ROUTE_COMMAND_READY"]
    p.step(**{condition:False});p.pulse("ROUTE_ACTIVE_BITS_VERIFIED");p.pulse("ROUTE_REARM");assert not p.values["ROUTE_COMMAND_READY"]
    record(f"illegal commit with {condition} holds active route and consumes admission",p)
p=EventModel();p.arm();p.step(CH0_WANT_ROUTE=True);p.step(CH0_REQUEST=True,CH0_RUN=True);p.step(CH0_REQUEST=False,CH0_RUN=False,pending=(7,11));p.pulse("ROUTE_COMMIT");assert p.address(0)==3;record("phase gap remains frozen while route intent is held",p)
p=EventModel();p.arm((5,5));p.step(CH0_WANT_ROUTE=True,CH1_WANT_ROUTE=True);assert not p.state["ROUTE_VALID"] and not p.values["CH0_ROUTE_EN"] and not p.values["CH1_ROUTE_EN"];p.step(CH1_WANT_ROUTE=False);assert not p.values["CH0_ROUTE_EN"];record("collision disables both sources and removal cannot restart",p)
p=EventModel();p.arm();p.step(ROUTE_ACTIVE_BITS_VERIFIED=True,pending=(4,10));p.pulse("ROUTE_COMMIT");p.pulse("ROUTE_REARM");assert not p.values["ROUTE_COMMAND_READY"];p.pulse("ROUTE_ACTIVE_BITS_VERIFIED");p.pulse("ROUTE_REARM");assert p.values["ROUTE_COMMAND_READY"];record("stale high verification is rejected until a fresh acknowledgement edge",p)
for health in health_names:
    p=EventModel();p.arm();p.step(CH0_WANT_ROUTE=True);p.step(**{health:False});assert not p.values["CH0_ROUTE_EN"];p.step(**{health:True});assert not p.values["CH0_ROUTE_EN"];p.step(CH0_WANT_ROUTE=False);p.pulse("ROUTE_REARM");assert not p.values["ROUTE_COMMAND_READY"]
    record(f"{health} loss consumes prior commit acknowledgement and validation",p)
p=EventModel();p.arm();p.step(pending=(4,10));p.pulse("ROUTE_COMMIT");assert (p.address(0),p.address(1))==(4,10) and not p.values["ROUTE_COMMAND_READY"];record("legal fresh commit updates bits but does not automatically rearm",p)
p=EventModel();p.arm();p.step(CH0_WANT_ROUTE=True,ROUTE_REARM=True);assert not p.values["ROUTE_COMMAND_READY"];p.step(CH0_WANT_ROUTE=False);assert not p.values["ROUTE_COMMAND_READY"];record("illegal rearm captures zero and later quiet cannot create a rearm edge",p)
p=EventModel();p.arm();p.step(RESET_READY=False);assert p.address(0)==p.address(1)==0 and not p.values["ROUTE_COMMAND_READY"];record("reset-to-address-zero never asserts any bank",p)

with (HERE/"bom.csv").open(encoding="utf-8",newline="") as f:bom=list(csv.DictReader(f))
assert len(bom)==155 and {row["reference"] for row in bom}==set(parts)
erc=json.loads((HERE/"erc.json").read_text(encoding="utf-8"))
assert erc["ignored_checks"]==[] and len(erc["sheets"])==6
assert not [v for sheet in erc["sheets"] for v in sheet["violations"]]
assert len(re.findall(rb"/Type\s*/Page(?!s)\b",(HERE/"contact_router.pdf").read_bytes()))==6
try:from pypdf import PdfReader
except ImportError:pass
else:assert len(PdfReader(HERE/"contact_router.pdf").pages)==6
assert len(list((HERE/"svg").glob("*.svg")))==6
for i in range(1,7):assert (HERE/"review"/f"page-{i}.png").stat().st_size>1000
for path in (HERE/"svg").glob("*.svg"):
    assert all(line==line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()),"Trim exported SVG trailing whitespace before freezing"
def digest(path):
    data=path.read_bytes()
    if path.suffix not in (".png",".pdf"):data=data.replace(b"\r\n",b"\n").replace(b"\r",b"\n")
    return hashlib.sha256(data).hexdigest()
mcp=json.loads((HERE/"mcp-inspection.json").read_text(encoding="utf-8"))
assert mcp["mux_component"]["value"]=="TMUX6208PWR" and mcp["mux_component"]["reference"]=="U100"
assert len(mcp["mux_pin_locations"]["pins"])==16 and len(mcp["contact_header_pin_locations"]["pins"])==18
assert {pin["number"]:pin["name"] for pin in mcp["mux_pin_locations"]["pins"]}=={"1":"A0","16":"A1","15":"A2","2":"EN_HIGH","13":"VDD","3":"VSS","14":"GND","8":"D_COMMON","4":"S1","5":"S2","6":"S3","7":"S4","12":"S5","11":"S6","10":"S7","9":"S8"}
assert mcp["erc"]["total"]==mcp["erc"]["errors"]==mcp["erc"]["warnings"]==0 and mcp["erc"]["violations"]==[]
assert set(mcp["overlaps"])=={"contact_router","source0","source1","address","admission","collision"}
assert all(result["overlap_count"]==0 and result["bounds_unresolved"]==[] for result in mcp["overlaps"].values())
assert set(mcp["schematic_sha256"])=={path.name for path in HERE.glob("*.kicad_sch")}
assert all(digest(HERE/name)==sha for name,sha in mcp["schematic_sha256"].items()),"MCP receipt must be bound to the actual saved native revision"
files=sorted(path for path in HERE.rglob("*") if path.is_file() and path.name not in ("verification.json","contact_router.kicad_prl") and not path.name.endswith(".lck") and "__pycache__" not in path.parts)
receipt={"schema":"scci_rh.stage4.contact-router.verification.v1","date":"2026-10-13","scope":"Saved native pin/connectivity and ideal stable Boolean/event checks; not analog switch/physical timing or biological qualification","kicad_version":erc["kicad_version"],"components":155,"pin_contracts_compared":checked,"sheets":6,"pdf_pages":6,"erc_violations":0,"ignored_erc_checks":[],"selectable_stim_contacts":16,"dedicated_monitored_returns":2,"control_truth_rows":truth_rows,"collision_bank_truth_rows":collision_rows,"event_probes":probes,"event_steps":event_steps,"checks":["all155 exported values/footprints and650 pin nets compared","exact6208PW16 pinmap, commonD and16contact source mapping","single18pincontactside header with two distinct monitored returns","separate monitoredloadside returns with no shunt duplication or B_BR shortcut","candidate595storage is separate from8activeaddress FFQ bits","actual157D-input selection and hold feedback, no clock gate","unconditional external COMMIT/ACK/REARM clocks on all11FFs","native collision equality over allfour activebits denies both sources","fresh ACK latch rejects heldHIGH verification aftercommit","actual per-IC bypasses and safe-default input resistors","zero ERC/no ignoredchecks, six PDF/SVG pages and review image hashes"],"hash_policy":"SHA256 exactPNG/PDF; otherincludedtext normalizesCRLF/CRtoLF; excludesreceipt/localpreferences/Pythoncache","unqualified":["actual route continuity/isolation/stuck switch detection","fresh ACK correctness beyond its edge being new","asynchronous hazards/metastability/propagation/clock/setuphold/supply transitions","24V mux timing/leakage/injection/parasitic worstcase","terminal guard and independent watchdog/compliance/rail supervision","actual current/charge observation and recordingisland isolation","PCB/assembly/exactpassiveMPN/CAD/chronicimplant or biological efficacy"],"sha256":{path.relative_to(HERE).as_posix():digest(path) for path in files}}
if args.write_receipt:(HERE/"verification.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
else:assert json.loads((HERE/"verification.json").read_text(encoding="utf-8"))==receipt,"Saved receipt differs; review intentional native/export changes before refreshing"
print(json.dumps({key:receipt[key] for key in ("components","pin_contracts_compared","sheets","erc_violations","control_truth_rows","collision_bank_truth_rows","event_steps")}|{"event_probes":len(probes)}))
