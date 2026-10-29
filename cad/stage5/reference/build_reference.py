"""Build the true-scale, editable Stage 5 modular reference chassis.

Run with FreeCAD's bundled Python. Source populated STEP compounds are loaded
unchanged and rigidly placed. Mechanical parts retain native primitive/boolean
dependencies; source board geometry is never reconstructed from envelopes.
"""
from __future__ import annotations
from pathlib import Path
import argparse,csv,hashlib,json,math
import FreeCAD as App
import Part,MeshPart
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
C=json.loads((HERE/'contract.json').read_text())
DOC=App.newDocument('SCCI_RH_Reference_Assembly')
FINAL=[];CONSTRUCTION=[];BOM=[]
GROUPS={}
for name in ['Electronics','Trays','MountingHardware','Chassis','Rails','Fasteners','Feet']:
    GROUPS[name]=DOC.addObject('App::DocumentObjectGroup',name)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def construction(obj):
    obj.addProperty('App::PropertyBool','Construction','Provenance');obj.Construction=True
    CONSTRUCTION.append(obj)
    return obj

def box(name,x,y,z,l,w,h):
    o=DOC.addObject('Part::Box',name);o.Length=l;o.Width=w;o.Height=h;o.Placement.Base=App.Vector(x,y,z)
    return construction(o)

def cylinder(name,x,y,z,r,h,direction=None):
    o=DOC.addObject('Part::Cylinder',name);o.Radius=r;o.Height=h
    o.Placement.Base=App.Vector(x,y,z)
    if direction:o.Placement.Rotation=App.Rotation(App.Vector(0,0,1),App.Vector(*direction))
    return construction(o)

def fuse(name,objects):
    if len(objects)==1:return objects[0]
    o=DOC.addObject('Part::MultiFuse',name);o.Shapes=objects
    return construction(o)

def cut(name,base,tools):
    o=DOC.addObject('Part::Cut',name);o.Base=base;o.Tool=fuse(name+'_Tools',tools)
    return construction(o)

def finish(o,label,role,group,material,quantity=1):
    o.Label=label
    if 'Construction' in o.PropertiesList:o.Construction=False
    else:o.addProperty('App::PropertyBool','Construction','Provenance');o.Construction=False
    o.addProperty('App::PropertyString','PartRole','Assembly');o.PartRole=role
    o.addProperty('App::PropertyString','MaterialAllocation','Assembly');o.MaterialAllocation=material
    o.addProperty('App::PropertyString','GeometryStatus','Assembly');o.GeometryStatus='Nominal digital geometry; no physical qualification'
    o.addProperty('App::PropertyColor','DisplayColor','Assembly')
    colors={'populated_board':(.08,.45,.24),'tray':(.14,.19,.24),'tray_pull':(.08,.48,.57),'board_standoff':(.86,.86,.82),'board_screw':(.67,.69,.71),'enclosure_panel':(.62,.65,.69),'rail':(.40,.44,.49),'frame_post':(.45,.48,.52),'lid_screw':(.67,.69,.71),'foot':(.05,.05,.055),'panel_bracket':(.46,.48,.51),'panel_screw':(.67,.69,.71)}
    o.DisplayColor=colors[role]
    GROUPS[group].addObject(o);FINAL.append(o)
    BOM.append(dict(label=label,category=role,quantity=quantity,material_allocation=material,native_feature_type=o.TypeId,physical_qualification='none'))
    return o

# Base, removable front/rear panels, side walls and lid. All dimensions are native parameters.
finish(box('BaseBlank',0,0,8,600,310,3),'Base','enclosure_panel','Chassis','Nominal aluminium3mm')
finish(box('LeftWallBlank',0,3,11,3,304,226),'SideLeft','enclosure_panel','Chassis','Nominal aluminium3mm')
finish(box('RightWallBlank',597,3,11,3,304,226),'SideRight','enclosure_panel','Chassis','Nominal aluminium3mm')
front=box('FrontBlank',0,0,11,600,3,226)
front_tools=[]
for col,x in enumerate([10,590]):
    for row,z in enumerate([40,200]):
        tag=f'{col}_{row}'
        front_tools.extend([cylinder('FrontThrough_'+tag,x,0,z,1.6,3,(0,1,0)),cylinder('FrontCounterbore_'+tag,x,0,z,3.1,2,(0,1,0))])
        bracket=box('FrontBracketBlank_'+tag,3 if col==0 else 585,3,z-5,12,5,10)
        bracket=cut('FrontBracketCut_'+tag,bracket,[cylinder('FrontThreadClear_'+tag,x,3,z,1.5,5,(0,1,0))])
        finish(bracket,'FrontBracket_'+tag,'panel_bracket','Chassis','Nominal aluminium bracket; threads omitted')
        head=cylinder('FrontHead_'+tag,x,0,z,2.75,2,(0,1,0));shaft=cylinder('FrontShaft_'+tag,x,2,z,1.45,6,(0,1,0))
        finish(fuse('FrontScrew_'+tag,[head,shaft]),'FrontScrew_'+tag,'panel_screw','Fasteners','Nominal M3; threads omitted')
finish(cut('FrontPanelCut',front,front_tools),'FrontPanel','enclosure_panel','Chassis','Nominal removable aluminium3mm')
rear=box('RearBlank',0,307,11,600,3,226)
port_tools=[]
for p in C['external_ports']:
    x,y,z=p['cutout_min_mm'];xx,yy,zz=p['cutout_max_mm']
    port_tools.append(box('Port_'+p['name'],x,y-.1,z,xx-x,yy-y+.2,zz-z))
# Open ventilation allocations; no air-flow performance is claimed.
for index in range(12):port_tools.append(box('RearVent_'+str(index),180+index*9,306.9,205,4,3.2,17))
finish(cut('RearPanelCut',rear,port_tools),'RearPanel','enclosure_panel','Chassis','Nominal aluminium3mm; ventilation allocation')
lid=box('LidBlank',0,0,237,600,310,3);lidtools=[]
for col,x in enumerate([15,333,377,568]):
    for row,y in enumerate([17,293]):
        tag=f'{col}_{row}'
        post=box('FramePostBlank_'+tag,x-3,y-3,11,6,6,226)
        finish(cut('FramePostCut_'+tag,post,[cylinder('PostThreadClear_'+tag,x,y,229,1.5,8)]),'Post_'+tag,'frame_post','Chassis','Nominal aluminium6mm square bar; threads omitted')
        lidtools.extend([cylinder('LidThrough_'+tag,x,y,236.9,1.6,3.2),cylinder('LidCounterbore_'+tag,x,y,238,3.1,2.1)])
        head=cylinder('LidHead_'+tag,x,y,238,2.75,2);shaft=cylinder('LidShaft_'+tag,x,y,232,1.45,6)
        finish(fuse('LidFastener_'+tag,[head,shaft]),'LidScrew_'+tag,'lid_screw','Fasteners','Nominal M3; threads omitted')
finish(cut('LidCut',lid,lidtools),'Lid','enclosure_panel','Chassis','Nominal clear polycarbonate3mm')
for index,(x,y) in enumerate([(25,25),(575,25),(25,285),(575,285)]):
    finish(cylinder('RubberFoot_'+str(index),x,y,0,10,8),'Foot_'+str(index),'foot','Feet','Nominal adhesive elastomer foot')

# Tray rails and each editable 2mm insulating tray, with holes taken from native PCB.
for bay,x0,x1 in [('left',18,330),('right',380,565)]:
    for tier in range(4):
        bottom=16+50*tier
        for side in ['left','right']:
            tag=f'{bay}_{tier}_{side}'
            web=box('RailWeb_'+tag,x0-3 if side=='left' else x1,20,bottom-4,3,270,4)
            lip=box('RailLip_'+tag,x0 if side=='left' else x1-3,20,bottom-2,3,270,2)
            finish(fuse('RailFuse_'+tag,[web,lip]),'Rail_'+tag,'rail','Rails','Nominal aluminium angle rail')
for b in C['boards']:
    name=b['board'];slug=name.replace('-','_');tier=b['tier'];x0,x1=(18,330) if b['bay']=='left' else (380,565);bottom=16+50*tier
    plate=box('TrayBlank_'+slug,x0,20,bottom,x1-x0,270,2)
    rearstop=box('TrayStop_'+slug,x0,288,bottom+2,x1-x0,2,6)
    blank=fuse('TrayAndStop_'+slug,[plate,rearstop])
    holes=[]
    for m in [m for m in C['mounts'] if m['board']==name]:
        x,y=m['axis_xy_mm'];tag=slug+'_'+m['reference']
        holes.append(cylinder('TrayHole_'+tag,x,y,bottom-.1,1.65,2.2))
        standoff=cut('StandoffCut_'+tag,cylinder('StandoffOuter_'+tag,x,y,bottom+2,3,10),[cylinder('StandoffBore_'+tag,x,y,bottom+1.9,1.5,10.2)])
        finish(standoff,m['standoff_label'],'board_standoff','MountingHardware','Nominal insulating M3 female/female10mm; thread detail omitted')
        upperbase=m['board_top_z_mm']
        upper=fuse('UpperFastener_'+tag,[cylinder('UpperHead_'+tag,x,y,upperbase,2.75,2.2),cylinder('UpperShaft_'+tag,x,y,upperbase-6,1.45,6)])
        finish(upper,m['upper_screw_label'],'board_screw','MountingHardware','Nominal M3×6; thread detail omitted')
        lower=fuse('LowerFastener_'+tag,[cylinder('LowerHead_'+tag,x,y,bottom-2.2,2.75,2.2),cylinder('LowerShaft_'+tag,x,y,bottom,1.45,6)])
        finish(lower,m['lower_screw_label'],'board_screw','MountingHardware','Nominal M3×6; thread detail omitted')
    finish(cut('TrayPocket_'+slug,blank,holes),b['tray_label'],'tray','Trays','Nominal insulating sheet2mm with6mm rear stop')
    mid=(x0+x1)/2
    pull=box('PullBlank_'+slug,mid-25,11,bottom,50,9,12)
    pull=cut('PullCut_'+slug,pull,[box('FingerOpening_'+slug,mid-17,10.9,bottom+3,34,6.1,6)])
    finish(pull,'Pull_'+slug,'tray_pull','Trays','Nominal polymer grip')

# Actual populated boards: preserve source compound and all its detailed solids.
for b in C['boards']:
    source=ROOT/b['source_step'];assert sha(source)==b['source_step_sha256']
    print('Loading actual populated STEP:',b['board'],flush=True)
    shape=Part.read(str(source));assert shape.isValid()
    obj=DOC.addObject('Part::Feature',b['label']);obj.Shape=shape
    obj.Placement.Base=App.Vector(*b['translation_mm'])
    finish(obj,b['label'],'populated_board','Electronics','Source board compound with actual fitted packages')
    for prop,val in [('SourceSTEP',b['source_step']),('SourceSHA256',b['source_step_sha256']),('SourcePCB',b['source_pcb']),('SourcePCBSHA256',b['source_pcb_sha256_lf'])]:obj.addProperty('App::PropertyString',prop,'Provenance');setattr(obj,prop,val)
    obj.addProperty('App::PropertyVector','RigidTranslation','Provenance');obj.RigidTranslation=App.Vector(*b['translation_mm'])
    obj.addProperty('App::PropertyInteger','FittedComponents','Provenance');obj.FittedComponents=b['fitted_components']

DOC.recompute()
# Save categorical palette in document properties; GUI helper applies it visibly.
for obj in FINAL:
    assert not obj.Shape.isNull() and obj.Shape.isValid(),obj.Label
    if obj.ViewObject:
        obj.ViewObject.ShapeColor=tuple(obj.DisplayColor)
        if obj.Label=='Lid':obj.ViewObject.Transparency=65
for obj in CONSTRUCTION:
    if obj not in FINAL and obj.ViewObject:obj.ViewObject.Visibility=False
for obj in FINAL:
    if obj.ViewObject:obj.ViewObject.Visibility=True
DOC.recompute()
DOC.addObject('App::DocumentObjectGroup','DesignNotes').addProperty('App::PropertyString','Scope','Design').Scope=C['design_scope']
native=HERE/'SCCI_RH_reference_assembly.FCStd';DOC.saveAs(str(native))

# Export provenance and finite geometry checks, independent audit is a separate task.
records=[]
for obj in FINAL:
    shape=obj.Shape;bb=shape.BoundBox
    records.append(dict(label=obj.Label,native_name=obj.Name,category=obj.PartRole,type=obj.TypeId,valid=shape.isValid(),solid_count=len(shape.Solids),volume_mm3=shape.Volume,bbox_mm=[bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax]))
with (HERE/'mechanical-bom.csv').open('w',newline='',encoding='utf-8') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(BOM[0]));writer.writeheader();writer.writerows(BOM)
# Reflect exactly all final parts into contract, retain root approved layout fields.
C['parts']=[dict(label=r['label'],native_name=r['native_name'],category=r['category']) for r in records]
C['exploded_transforms']={}
for r in records:
    dz=0
    if r['category'] in ('populated_board','tray','tray_pull','board_standoff','board_screw'):
        dz=max(0,round((r['bbox_mm'][2]-12)/50))*35+(15 if r['category']=='populated_board' else 0)
    elif r['label']=='Lid' or r['category']=='lid_screw':dz=165
    C['exploded_transforms'][r['label']]=[0,-50 if r['label']=='FrontPanel' else 0,dz]
(HERE/'contract.json').write_text(json.dumps(C,indent=2)+'\n')
receipt=dict(schema='scci_rh.stage5.reference-producer-geometry.v1',native=native.relative_to(ROOT).as_posix(),FreeCAD_version=list(App.Version()[:3]),contract_sha256=sha(HERE/'contract.json'),board_datums_sha256=sha(HERE/'board-datums.json'),builder_sha256=sha(Path(__file__)),source_steps={b['source_step']:b['source_step_sha256'] for b in C['boards']},objects=records,part_count=len(FINAL),fitted_electronic_components=sum(b['fitted_components'] for b in C['boards']),mechanical_part_count=sum(o.PartRole!='populated_board' for o in FINAL),native_dependency_features=sum(o.TypeId.startswith('Part::') and o.TypeId!='Part::Feature' for o in DOC.Objects),scope_limits=C['assembly_assumptions'])
(HERE/'producer-geometry.json').write_text(json.dumps(receipt,indent=2)+'\n')
parser=argparse.ArgumentParser();parser.add_argument('--native-only',action='store_true');args=parser.parse_args()
if not args.native_only:
    print('Exporting actual populated reference STEP',flush=True)
    Part.export(FINAL,str(HERE/'SCCI_RH_reference_assembly.step'))
    mechanical=[o for o in FINAL if o.PartRole!='populated_board']
    Part.export(mechanical,str(HERE/'SCCI_RH_reference_mechanical.step'))
    # Exploded view is a separate derivative; document source placements stay assembled.
    exploded=[]
    for obj in FINAL:
        q=obj.Shape.copy()
        dz=0
        if obj.PartRole in ('populated_board','tray','tray_pull','board_standoff','board_screw'):
            bb=q.BoundBox;dz=max(0,round((bb.ZMin-12)/50))*35
            if obj.PartRole=='populated_board':dz+=15
        elif obj.Label=='Lid' or obj.PartRole=='lid_screw':dz=165
        elif obj.Label=='FrontPanel':q.translate(App.Vector(0,-50,0))
        q.translate(App.Vector(0,0,dz));exploded.append(q)
    Part.makeCompound(exploded).exportStep(str(HERE/'SCCI_RH_reference_exploded.step'))
    meshdir=HERE/'stl';meshdir.mkdir(exist_ok=True)
    # Individual native mechanical parts are useful for inspection; not print permission.
    for obj in mechanical:
        mesh=MeshPart.meshFromShape(Shape=obj.Shape,LinearDeflection=.15,AngularDeflection=.35,Relative=False)
        mesh.write(str(meshdir/(obj.Label+'.stl')))
    print('STEP assembly, mechanical STEP, exploded STEP and',len(mechanical),'STL mechanical parts exported',flush=True)
print('Saved',native,':',len(FINAL),'parts;',sum(b['fitted_components'] for b in C['boards']),'fitted source components',flush=True)
App.closeDocument(DOC.Name)
