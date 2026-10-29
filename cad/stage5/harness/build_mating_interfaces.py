"""Generate native mating geometry and separate annotated route planning CAD.

Use the installed FreeCAD Python. Physical housing openings align with native
PCB pin axes. Route annotations deliberately have zero solid volume.
"""
from pathlib import Path
import hashlib
import json
import math
import FreeCAD as App
import Part
import Import

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
C=json.loads((HERE/'contract.json').read_text(encoding='utf-8'))


def style(obj, colour):
    obj.addProperty('App::PropertyColor','RenderColour','Presentation')
    obj.RenderColour=colour


def vector(p):
    return App.Vector(*p)


def main():
    doc=App.newDocument('SCCI_RH_Mating_Interfaces')
    physical=[]
    for mate in C['mates']:
        ux,uy,_=mate['direction_unit']
        theta=math.degrees(math.atan2(uy,ux))
        shape=Part.makeBox(mate['housing_length_mm'],mate['housing_width_mm'],mate['housing_height_mm'],App.Vector(-1.37,-1.25,0))
        holes=[]
        for i in range(mate['pin_count']):
            holes.append(Part.makeBox(.95,.95,14.4,App.Vector(2.54*i-.475,-.475,-.2)))
        shape=shape.cut(Part.makeCompound(holes))
        assert shape.isValid() and shape.Volume>0
        # Retain box and cutter dependencies instead of a single imported mesh.
        stock=doc.addObject('Part::Box',mate['label']+'_Stock')
        stock.Length=mate['housing_length_mm'];stock.Width=2.5;stock.Height=14
        stock.Placement.Base=App.Vector(-1.37,-1.25,0)
        cutter=doc.addObject('Part::Feature',mate['label']+'_Cavities')
        cutter.Shape=Part.makeCompound(holes)
        obj=doc.addObject('Part::Cut',mate['label'])
        obj.Base=stock;obj.Tool=cutter
        obj.Placement=App.Placement(vector(mate['pin1_mm']),App.Rotation(App.Vector(0,0,1),theta))
        obj.addProperty('App::PropertyString','Board','Interface');obj.Board=mate['board']
        obj.addProperty('App::PropertyString','PCBReference','Interface');obj.PCBReference=mate['pcb_reference']
        obj.addProperty('App::PropertyInteger','Positions','Interface');obj.Positions=mate['pin_count']
        obj.addProperty('App::PropertyString','Scope','Interface');obj.Scope=mate['candidate_family']
        style(obj,(.07,.085,.11));physical.append(obj)
    # Rear inserts are passive split plates and cable grommet allocations only.
    for name, xmin, width, centres in [('ArtificialLoad',32,90,[(58,4.5),(96,4.5)]),('CompanionPowerDebug',390,100,[(410,3.5),(440,3.5),(470,3.5)])]:
        panel=Part.makeBox(width,3,28,App.Vector(xmin,307,194))
        for x,bore in centres:
            outer=bore+2
            hole=Part.makeCylinder(outer,3.4,App.Vector(x,306.8,208),App.Vector(0,1,0))
            panel=panel.cut(hole)
            ring=Part.makeCylinder(outer,5,App.Vector(x,306,208),App.Vector(0,1,0)).cut(Part.makeCylinder(bore,5.4,App.Vector(x,305.8,208),App.Vector(0,1,0)))
            o=doc.addObject('Part::Feature',f'Grommet_{name}_{x}');o.Shape=ring;style(o,(.045,.05,.06));physical.append(o)
        o=doc.addObject('Part::Feature',f'RearInsert_{name}');o.Shape=panel;style(o,(.13,.19,.24));physical.append(o)
    scope=doc.addObject('App::FeaturePython','Scope')
    scope.addProperty('App::PropertyString','Status');scope.Status='Nominal mating and passive cable interfaces; crimp retention, wire rating and manufacturing loom unqualified'
    scope.addProperty('App::PropertyString','ElectricalSource');scope.ElectricalSource='Frozen Stage4 harness and system.json; no electrical changes'
    doc.recompute()
    parts=[]
    for o in physical:
        assert o.Shape.isValid() and o.Shape.Volume>0, o.Name
        b=o.Shape.BoundBox
        parts.append(dict(label=o.Name,volume_mm3=o.Shape.Volume,solid_count=len(o.Shape.Solids),
                          bbox_min_mm=[b.XMin,b.YMin,b.ZMin],bbox_max_mm=[b.XMax,b.YMax,b.ZMax],valid=o.Shape.isValid()))
    native=ROOT/C['native'];step=ROOT/C['step']
    doc.saveAs(str(native));Import.export(physical,str(step))
    App.closeDocument(doc.Name)
    # Separate route-planning document, never exported as physical solids.
    route_doc=App.newDocument('SCCI_RH_Harness_Route_Plans')
    route_count=0
    for w in C['wires']:
        points=[]
        for p in w['points_mm']:
            if not points or math.dist(p,points[-1])>1e-7:points.append(p)
        obj=route_doc.addObject('Part::Feature',w['id'])
        obj.Shape=Part.makePolygon([vector(p) for p in points])
        obj.addProperty('App::PropertyString','Net');obj.Net=w['net']
        obj.addProperty('App::PropertyString','Scope');obj.Scope='Nonphysical unsmoothed centerline; shared branches not independent wire cuts'
        obj.addProperty('App::PropertyLength','PlanningLength');obj.PlanningLength=w['planning_length_with_slack_mm']
        route_count+=1
    route_doc.recompute();route_doc.saveAs(str(ROOT/C['routing_native']))
    App.closeDocument(route_doc.Name)
    receipts=dict(schema='scci_rh.stage5.mating-geometry.v1',FreeCAD_version=App.Version(),
                  contract_sha256_lf=hashlib.sha256((HERE/'contract.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
                  parts=parts,physical_part_count=len(parts),mating_housings=83,route_annotation_count=route_count,
                  sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [C['native'],C['step'],C['routing_native']]})
    (HERE/'geometry-receipt.json').write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')
    print('Saved83socketenvelopes,7passivepanel/grommetpartsand258nonphysicalrouteannotations.')


if __name__=='__main__':main()
