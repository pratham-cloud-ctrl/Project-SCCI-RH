"""Extract frozen board mount and connector datums using native KiCad 10 pcbnew."""
from pathlib import Path
import hashlib,json
import pcbnew as pcb
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PKG=ROOT/'electronics/stage4/integrated-pcb'
def sha(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n') if p.suffix in ('.kicad_pcb','.json') else p.read_bytes()).hexdigest()
boards=[]
for folder in sorted((PKG/'exports').iterdir()):
    if not folder.is_dir():continue
    name=folder.name
    path=PKG/'boards'/name/(name.replace('-','_')+'.kicad_pcb')
    board=pcb.LoadBoard(str(path)); bb=board.GetBoardEdgesBoundingBox()
    mounts=[];connectors=[]
    for fp in board.GetFootprints():
        ref=fp.GetReference();at=fp.GetPosition()
        pads=[dict(number=p.GetNumber(),position_mm=[pcb.ToMM(p.GetPosition().x),pcb.ToMM(p.GetPosition().y)],drill_mm=[pcb.ToMM(p.GetDrillSize().x),pcb.ToMM(p.GetDrillSize().y)]) for p in fp.Pads()]
        item=dict(reference=ref,value=fp.GetValue(),footprint=str(fp.GetFPID().GetLibItemName()),position_mm=[pcb.ToMM(at.x),pcb.ToMM(at.y)],rotation_deg=fp.GetOrientationDegrees(),pads=pads)
        if ref.startswith('H') and 'MountingHole' in str(fp.GetFPID().GetLibItemName()):mounts.append(item)
        elif ref.startswith('J'):connectors.append(item)
    receipt=json.loads((folder/'export-receipt.json').read_text())
    assert len(mounts)==4
    boards.append(dict(board=name,pcb=path.relative_to(ROOT).as_posix(),pcb_sha256_lf=sha(path),step=(folder/'populated.step').relative_to(ROOT).as_posix(),step_sha256=sha(folder/'populated.step'),outline_mm=[pcb.ToMM(bb.GetWidth())-.05,pcb.ToMM(bb.GetHeight())-.05],fitted_components=receipt['fitted_component_count'],mounts=sorted(mounts,key=lambda x:x['reference']),connectors=sorted(connectors,key=lambda x:x['reference'])))
(HERE/'board-datums.json').write_text(json.dumps(dict(schema='scci_rh.stage5.board-datums.v1',boards=boards),indent=2)+'\n')
print('Extracted',len(boards),'boards /',sum(len(b['mounts']) for b in boards),'native mounting axes /',sum(len(b['connectors']) for b in boards),'connector datums')

