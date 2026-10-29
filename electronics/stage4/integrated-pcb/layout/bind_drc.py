"""Write an exact local native DRC + schematic parity revision binding."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
PKG=ROOT/'electronics/stage4/integrated-pcb'
def sha(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def bind(name):
    directory=PKG/'boards'/name;pcb=directory/(name.replace('-','_')+'.kicad_pcb');drc=directory/'drc.json'
    report=json.loads(drc.read_text())
    counts={k:len(report.get(k,[])) for k in ['violations','unconnected_items','schematic_parity','ignored_checks']}
    if any(counts.values()):raise AssertionError((name,counts))
    result={'schema':'scci_rh.native-board-drc-binding.v1','board':name,'pcb_sha256_lf':sha(pcb),'drc_sha256_lf':sha(drc),'project_sha256_lf':sha(pcb.with_suffix('.kicad_pro')),'schematic_sha256_lf':sha(pcb.with_suffix('.kicad_sch')),'schematic_parity_checked':True,'suppressed_checks':[],'counts':counts,'command':'kicad-cli pcb drc --format json --schematic-parity','scope':'Saved native board digital geometry and electrical graph; no fabrication, impedance, thermal, EMI, isolation or biological qualification.'}
    (directory/'drc-binding.json').write_text(json.dumps(result,indent=2)+'\n')
    routing=directory/'routing.json'
    if routing.exists():
        r=json.loads(routing.read_text());r.update({'pcb_sha256_lf':result['pcb_sha256_lf'],'project_sha256_lf':result['project_sha256_lf'],'drc_sha256_lf':result['drc_sha256_lf'],'schematic_sha256_lf':result['schematic_sha256_lf'],'unconnected':0,'native_drc_counts':counts});routing.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({'board':name,**counts}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',action='append',required=True);a=p.parse_args()
    for name in a.board:bind(name)
