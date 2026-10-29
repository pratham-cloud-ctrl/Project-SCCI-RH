"""FreeCAD embedded Python: native reference assembly and PCB placement checks.
Run with FreeCAD's bin/python executable. STEP component envelopes remain subject
to library model availability; no fabrication tolerances are validated.
"""
from pathlib import Path
import json
import FreeCAD as App
import Part
ROOT=Path(__file__).resolve().parent
doc=App.newDocument('SCCI_RH_ReferenceAssembly')
checks={}
for name in ('base','lid'):
    obj=doc.addObject('PartDesign::Feature',name.title())
    shape=Part.Shape();shape.read(str(ROOT/'exports'/f'{name}.step'));obj.Shape=shape
    checks[name]=bool(obj.Shape.isValid())
pcb=Part.Shape();pcb.read(str(ROOT.parent/'electronics'/'exports'/'scci_rh_reference.step'))
bb=pcb.BoundBox
board_solids=[s for s in pcb.Solids if abs(s.BoundBox.XLength-80)<.02 and abs(s.BoundBox.YLength-50)<.02 and s.BoundBox.ZLength<2]
assert len(board_solids)==1,'Identify the PCB substrate rather than component/pin bounds.'
substrate=board_solids[0].BoundBox
translation=App.Vector(-(substrate.XMin+substrate.XMax)/2,-(substrate.YMin+substrate.YMax)/2,8-substrate.ZMin)
pcb.translate(translation)
obj=doc.addObject('PartDesign::Feature','PCB');obj.Shape=pcb
checks['pcb_valid']=bool(pcb.isValid())
checks['pcb_bounding_box_mm']=[pcb.BoundBox.XLength,pcb.BoundBox.YLength,pcb.BoundBox.ZLength]
checks['substrate_bottom_z_mm']=8
checks['substrate_thickness_mm']=substrate.ZLength
checks['pcb_base_overlap_mm3']=doc.getObject('Base').Shape.common(pcb).Volume
checks['pcb_lid_overlap_mm3']=doc.getObject('Lid').Shape.common(pcb).Volume
doc.recompute();doc.saveAs(str(ROOT/'scci_rh-reference.FCStd'))
Part.export([doc.getObject('Base'),doc.getObject('Lid'),obj],str(ROOT/'exports'/'scci_rh-electronics-assembly.step'))
(ROOT/'exports'/'electronics-assembly-checks.json').write_text(json.dumps(checks,indent=2))
print(checks)
