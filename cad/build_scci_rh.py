"""Parametric SCCI_RH desktop demonstrator, millimetres. Requires build123d 0.13.

An enclosure for digital engineering inspection, never an implant housing.
Run from any working directory; output paths are derived from this source.
"""
from pathlib import Path
import json
from build123d import *

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'exports'
OUT.mkdir(exist_ok=True)
W, D, H = 100., 70., 32.
WALL, FLOOR = 2.5, 2.
PCB_W, PCB_D, PCB_T = 80., 50., 1.6
MOUNT_Z = 8.
mounts = [(x,y) for x in (-30.,30.) for y in (-15.,15.)]
fasteners = [(x,y) for x in (-43.,43.) for y in (-28.,28.)]

def rounded_box(w,d,h,r):
    with BuildPart() as p:
        Box(w,d,h,align=(Align.CENTER,Align.CENTER,Align.MIN))
        fillet(p.edges().filter_by(Axis.Z), r)
    return p.part

shell = rounded_box(W,D,30,4) - Pos(0,0,FLOOR)*rounded_box(W-2*WALL,D-2*WALL,29,1.5)
for x,y in mounts:
    shell += Pos(x,y,FLOOR)*Cylinder(3.5,MOUNT_Z-FLOOR,align=(Align.CENTER,Align.CENTER,Align.MIN))
    shell -= Pos(x,y,3)*Cylinder(1.4,6,align=(Align.CENTER,Align.CENTER,Align.MIN))
for x,y in fasteners:
    shell += Pos(x,y,FLOOR)*Cylinder(3,28,align=(Align.CENTER,Align.CENTER,Align.MIN))
    shell -= Pos(x,y,23)*Cylinder(1.25,8,align=(Align.CENTER,Align.CENTER,Align.MIN))
# Rear panel: USB and two instrument cable entries. No waterproof claims.
shell -= Pos(0,D/2,14)*Box(11,9,5)
for x in (-24,24):
    shell -= Pos(x,D/2,14)*Rot(90,0,0)*Cylinder(3,9)
# Front status window.
shell -= Pos(0,-D/2,17)*Box(22,9,3)

lid = Pos(0,0,30)*rounded_box(W,D,2,4)
rim = rounded_box(94,64,4,3) - rounded_box(89,59,4,1.5)
for x,y in fasteners:
    rim -= Pos(x,y,0)*Cylinder(3.5,4,align=(Align.CENTER,Align.CENTER,Align.MIN))
lid += Pos(0,0,26)*rim
for x,y in fasteners:
    lid -= Pos(x,y,25)*Cylinder(1.6,9,align=(Align.CENTER,Align.CENTER,Align.MIN))
    lid -= Pos(x,y,31)*Cylinder(2.8,2,align=(Align.CENTER,Align.CENTER,Align.MIN))

board = Pos(0,0,MOUNT_Z)*rounded_box(PCB_W,PCB_D,PCB_T,2)
for x,y in mounts:
    board -= Pos(x,y,7)*Cylinder(1.6,4,align=(Align.CENTER,Align.CENTER,Align.MIN))

# Separate illustrative read/write geometries: no tissue fit or material model.
lead = rounded_box(10,40,.8,3)
contacts=[]
for x in (-2.5,2.5):
    for y in (-12.,-4.,4.,12.):
        contacts.append(Pos(x,y,.8)*Box(2,3,.1,align=(Align.CENTER,Align.CENTER,Align.MIN)))
cuff = Cylinder(6.2,18,arc_size=270) - Cylinder(6,20)
cuff_contacts=[]
for angle in (15,75,135,195):
    for z in (-5.,5.):
        patch=Cylinder(6,2,arc_size=12,align=(Align.NONE,Align.NONE,Align.CENTER)) - Cylinder(5.95,3)
        cuff_contacts.append(Pos(0,0,z)*Rot(0,0,angle)*patch)
parts={'base':shell,'lid':lid,'pcb-envelope':board,'lead-paddle':lead,
       'lead-contacts':Compound(children=contacts),'recording-cuff':cuff,
       'recording-contacts':Compound(children=cuff_contacts)}
checks={}
for name,shape in parts.items():
    assert shape.is_valid and shape.volume>0, name
    export_step(shape,OUT/f'{name}.step')
    export_stl(shape,OUT/f'{name}.stl')
    roundtrip=import_step(OUT/f'{name}.step')
    assert roundtrip.is_valid
    checks[name]={'valid':True,'volume_mm3':round(shape.volume,5),
                 'step_volume_error_mm3':abs(roundtrip.volume-shape.volume)}
overlap=shell & board
assert overlap.volume < .001, f'PCB interference {overlap.volume}'
lid_overlap=shell & lid
assert lid_overlap.volume < .001, f'lid interference {lid_overlap.volume}'
assembly=Compound(children=[shell,lid,board])
export_step(assembly,OUT/'scci_rh-desktop-assembly.step')
export_stl(assembly,OUT/'scci_rh-desktop-assembly.stl')
(OUT/'geometry-checks.json').write_text(json.dumps({'units':'mm','enclosure':[W,D,H],
    'pcb':[PCB_W,PCB_D,PCB_T],'pcb_mounting_plane':MOUNT_Z,'parts':checks,
    'pcb_base_overlap_mm3':overlap.volume,'lid_base_overlap_mm3':lid_overlap.volume},indent=2))
print('CAD solids, STEP round trips and assembly interference checks passed.')
