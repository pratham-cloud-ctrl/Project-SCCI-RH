"""Build actual FreeCAD solids and STEP models; run with FreeCAD's Python.

Missing-model replacement geometry is deliberately nominal. Native pads supply
pin count/order and datum, but land size is not a tolerance-qualified lead size.
"""
from pathlib import Path
import argparse
import hashlib
import json
import FreeCAD as App
import Part

HERE=Path(__file__).resolve().parent


def box(x,y,z,dx,dy,dz):return Part.makeBox(dx,dy,dz,App.Vector(x,y,z))


def make(row):
 w,d,h=[row[k] for k in ['body_width_mm','body_depth_mm','body_height_mm']]
 cx,cy=row['body_center_xy_mm'];cy=-cy
 kind=row['kind'];base=.4 if kind=='sip' else .05
 body=box(cx-w/2,cy-d/2,base,w,d,h)
 # Molded IC pin-1 dimple is geometry, not a claim of proprietary surface detail.
 if kind in ('qfn','gullwing'):
  radius=min(.23,w/10)
  body=body.cut(Part.makeCylinder(radius,.08,App.Vector(cx-w/2+.4,cy+d/2-.4,base+h-.08)))
 shapes=[body]
 if kind=='module':
  # PCB substrate plus nominal shield/component envelope; antenna portion bare.
  # Manufacturer Fab datum is asymmetric: upper 15 mm, lower 14 mm.
  # Convert the actual footprint polygon from y-down to the model's y-up.
  outline=[(-8,-10.5),(7,-10.5),(7,10.5),(-7,10.5),(-7,.5),(-8,.5)]
  points=[App.Vector(x,-y,.05) for x,y in outline]
  substrate=Part.Face(Part.makePolygon(points+[points[0]])).extrude(App.Vector(0,0,.6))
  shapes=[substrate,box(-6.7,-10,.65,13.4,11.2,1.4)]
 for p in row['pads']:
  x,y=p['x_mm'],-p['y_mm'];pw,ph=p['width_mm'],p['height_mm']
  if kind=='sip':
   lead=box(x-.25,y-.25,-3.,.5,.5,3.4)
  elif kind=='gullwing' and abs(x)>w/2:
   # Copper foot, vertical riser and shoulder are one connected lead solid.
   side=1 if x>0 else -1;outer=side*(w/2+.65);inner=side*(w/2-.15)
   foot=box(min(outer,x)-.18,y-min(ph,.4)/2,0,abs(outer-x)+.36,min(ph,.4),.15)
   riser=box(outer-.1,y-min(ph,.4)/2,.1,.2,min(ph,.4),.4)
   shoulder=box(min(inner,outer),y-min(ph,.4)/2,.4,abs(outer-inner)+.1,min(ph,.4),.15)
   lead=foot.fuse(riser).fuse(shoulder)
  else:
   # No-lead/package contact: preserve actual center/number, trim outer lands
   # to the nominal body edge. Solder fillets are outside this representation.
   if kind!='module':
    xmin=max(x-pw/2,cx-w/2-.05);xmax=min(x+pw/2,cx+w/2+.05)
    ymin=max(y-ph/2,cy-d/2-.05);ymax=min(y+ph/2,cy+d/2+.05)
   else:xmin,xmax,ymin,ymax=x-pw/2,x+pw/2,y-ph/2,y+ph/2
   if xmax<=xmin or ymax<=ymin:continue
   lead=box(xmin,ymin,0,xmax-xmin,ymax-ymin,.1)
  shapes.append(lead)
 return shapes


def main(selected=None):
 d=json.loads((HERE/'package-inputs.json').read_text());rows=[]
 for row in d['models']:
  if selected and row['name'] not in selected:continue
  doc=App.newDocument('SCCI_RH_'+row['name'][:28]);shapes=make(row)
  objects=[]
  for i,shape in enumerate(shapes):
   assert not shape.isNull() and shape.isValid() and shape.Volume>0,(row['name'],i)
   obj=doc.addObject('PartDesign::Feature','Body' if i==0 else f'Contact{i:02}')
   obj.Label=row['name']+('/body' if i==0 else f'/contact-{i:02}')
   obj.Shape=shape;objects.append(obj)
  doc.recompute()
  # Package names contain decimal dots; append the extension without replacing
  # the trailing dimensional suffix (e.g. EP6.1).
  native=HERE/(row['name']+'.FCStd');step=HERE/(row['name']+'.step')
  doc.saveAs(str(native))
  Part.export(objects,str(step))
  imported=Part.read(str(step))
  assert imported.isValid() and len(imported.Solids)>=len(shapes),(row['name'],'STEP topology')
  bounds=imported.BoundBox
  rows.append(dict(name=row['name'],STEP=step.name,native=native.name,
                   source_footprint=row['source_footprint'],source_sha256_lf=row['source_sha256_lf'],
                   actual_pad_count=len(row['pads']),exported_solids=len(imported.Solids),valid=True,
                   bound_dimensions_mm=[bounds.XLength,bounds.YLength,bounds.ZLength],
                   volume_mm3=imported.Volume,STEP_sha256=hashlib.sha256(step.read_bytes()).hexdigest()))
  App.closeDocument(doc.Name)
 if selected:
  prior=json.loads((HERE/'verification.json').read_text())
  rows=[r for r in prior['models'] if r['name'] not in selected]+rows
 result=dict(schema='scci_rh.nominal-package-models.v1',scope=d['scope'],height_policy=d['height_policy'],
             axes=d['local_model_axes'],FreeCAD_version=App.Version()[:3],models=rows)
 (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(f'{len(rows)} native FreeCAD/STEP packages exported and reimported; all solids valid')


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--model',action='append');main(parser.parse_args().model)
