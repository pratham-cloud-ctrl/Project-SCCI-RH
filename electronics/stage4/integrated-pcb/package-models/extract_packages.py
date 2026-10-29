"""Extract actual land-pattern datums with KiCad's bundled Python/pcbnew.

Produces input geometry for nominal package models where no installed STEP
exists. These are visual/mechanical reference models, not vendor CAD/tolerances.
"""
import hashlib
import json
from pathlib import Path
import pcbnew

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
INVENTORY=HERE.parent/'layout/footprint-inventory.json'
PARAMETERS={
 'Texas_DRX_WSON-10_2.5x2.5mm_P0.5mm':(2.5,2.5,.8,'qfn'),
 'RHD2216_QFN56_8x8_P0.5_EP6.1':(8.,8.,1.,'qfn'),
 'Texas_RRP0016A_WQFN16_4x4_P0.65_EP2.6':(4.,4.,1.,'qfn'),
 'Texas_DRB0008A_VSON8_3x3_P0.65_EP1.5x1.75':(3.,3.,1.,'qfn'),
 'VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm':(3.,3.,1.,'qfn'),
 'TRACO_TMR3_SIP8_21.8x9.1_P2.54':(21.8,9.1,11.2,'sip'),
 'Texas_DGN0008D_VSSOP-8-1EP_3x3mm_P0.65mm_EP2x2.94mm_Mask1.57x1.89mm':(3.,3.,1.1,'gullwing'),
 'BT40F_Manufacturer_66Pad':(15.,21.,2.,'module')}


def main():
 inventory=json.loads(INVENTORY.read_text());sources={}
 for value in inventory['items'].values():
  p=Path(value['source'])
  if p.stem in PARAMETERS:sources.setdefault(p.stem,p)
 sources['BT40F_Manufacturer_66Pad']=ROOT/'electronics/stage4/controller-carrier/scci_rh_controller.pretty/BT40F_Manufacturer_66Pad.kicad_mod'
 # New integrated package corrects the preserved TPS3431 row-center error.
 corrected=HERE.parent/'integration/boards/supervision/scci_rh_sup.pretty/Texas_DRB0008A_VSON8_3x3_P0.65_EP1.5x1.75.kicad_mod'
 assert corrected.exists(),'reviewed integrated TPS3431 land pattern'
 sources['Texas_DRB0008A_VSON8_3x3_P0.65_EP1.5x1.75']=corrected
 rows=[]
 for name,path in sources.items():
  footprint=pcbnew.FootprintLoad(str(path.parent),path.stem)
  assert footprint is not None,name
  pads=[]
  for pad in footprint.Pads():
   if not pad.GetNumber():continue
   xy=pad.GetPosition();size=pad.GetSize()
   pads.append(dict(number=pad.GetNumber(),x_mm=pcbnew.ToMM(xy.x),y_mm=pcbnew.ToMM(xy.y),
                    width_mm=pcbnew.ToMM(size.x),height_mm=pcbnew.ToMM(size.y),
                    through_hole=pad.GetAttribute()==pcbnew.PAD_ATTRIB_PTH))
  width,depth,height,kind=PARAMETERS[name]
  rows.append(dict(name=name,kind=kind,body_width_mm=width,body_depth_mm=depth,body_height_mm=height,
                   body_center_xy_mm=[8.89,2.25] if kind=='sip' else [0,0],
                   source_footprint=path.relative_to(ROOT).as_posix(),
                   source_sha256_lf=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),pads=pads))
 assert len(rows)==8,'all eight missing nominal package patterns'
 result=dict(schema='scci_rh.nominal-package-input.v1',scope='Nominal package geometry; actual land-pattern pin coordinates; no vendor STEP or tolerance claim',
             height_policy='Declared nominal visualization allocations for small ICs; TRACO and BT40F body dimensions from package descriptions. Not height/tolerance qualification.',
             local_model_axes='X=footprintX,Y=-footprintY,Z=aboveboard; origin remains exact footprint datum',models=rows)
 (HERE/'package-inputs.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(f'{len(rows)} nominal package definitions; {sum(len(r["pads"]) for r in rows)} physical pad datums')


if __name__=='__main__':main()
