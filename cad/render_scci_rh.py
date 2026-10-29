"""Rebuild the editable Blender scene and engineering presentation images.
blender --background --factory-startup --python cad/render_scci_rh.py
"""
import bpy, math
from mathutils import Vector
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'media'
OUT.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def material(name,color,metal=0,rough=.35):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    n=m.node_tree.nodes.get('Principled BSDF'); n.inputs['Base Color'].default_value=(*color,1)
    n.inputs['Metallic'].default_value=metal; n.inputs['Roughness'].default_value=rough
    return m
navy=material('Graphite polymer',(.022,.038,.065),.15,.28)
teal=material('Teal anodized trim',(.035,.5,.52),.55,.25)
gold=material('Contact metal',(.83,.57,.24),.8,.2)
pcbmat=material('PCB solder mask',(.04,.18,.16),.15,.38)
black=material('Component packages',(.015,.02,.028),.05,.35)
white=material('Markings',(.85,.91,.92),.1,.4)
floor=material('Studio ground',(.024,.035,.058),.15,.45)

def mesh(name,mat):
    before=set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=str(ROOT/'exports'/f'{name}.stl'))
    obj=next(iter(set(bpy.data.objects)-before)); obj.name=name
    obj.data.materials.append(mat)
    bevel=obj.modifiers.new('Presentation micro bevel','BEVEL'); bevel.width=.15; bevel.segments=2
    obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return obj
base=mesh('base',navy); lid=mesh('lid',navy); board=mesh('pcb-envelope',pcbmat)

def box(name,location,size,mat,bevel=.15):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    obj=bpy.context.object; obj.name=name; obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod=obj.modifiers.new('Edge radius','BEVEL');mod.width=bevel;mod.segments=3
    return obj
def text(body,loc,size,mat,rotate=(0,0,0)):
    c=bpy.data.curves.new('Lettering','FONT');c.body=body;c.size=size;c.extrude=.012;c.align_x='CENTER'
    o=bpy.data.objects.new(body,c);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=rotate
    c.materials.append(mat);return o
label=text('SCCI RH',(0,2,32.12),10,white)
subtitle=text('SPINAL INTERFACE  /  DIGITAL STUDY',(0,-9,32.12),1.55,teal)
trim=box('Status lens',(0,-35.05,17),(20,.4,2),teal)
annotations=[label,subtitle]
component_objects=[]
# These visual blocks are envelopes only; actual circuit components are in KiCad.
for x,y,w,d,h in [(-21,8,8,6,2),(-7,8,8,6,2),(9,8,10,7,2),(25,8,8,6,2),(-20,-9,13,6,6),(1,-9,13,6,6),(25,-9,8,7,3)]:
    component_objects.append(box('Illustrative component envelope',(x,y,9.6+h/2),(w,d,h),black))
for x in (-30,30):
    for y in (-15,15):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=2.5,depth=.8,location=(x,y,10))
        bpy.context.object.data.materials.append(gold);component_objects.append(bpy.context.object)
for x in (-43,43):
    for y in (-28,28):
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=2.5,depth=.8,location=(x,y,31.5))
        o=bpy.context.object;o.name='Illustrative lid fastener';o.data.materials.append(black);annotations.append(o)
lead=mesh('lead-paddle',navy);contacts=mesh('lead-contacts',gold)
for o in [lead,contacts]:o.location=(70,5,.5);o.rotation_euler[2]=-.3
readlead=mesh('recording-cuff',teal);readcontacts=mesh('recording-contacts',gold)
for o in (readlead,readcontacts):o.location=(70,-26,9.5);o.rotation_euler[2]=-.4
box('Ground',(0,0,-2),(2000,2000,2),floor,0)

bpy.ops.object.camera_add(location=(145,-165,142))
camera=bpy.context.object;bpy.context.scene.camera=camera
def point(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
point(camera,(10,0,12));camera.data.type='ORTHO';camera.data.ortho_scale=185
def light(loc,power,size):
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;point(o,(0,0,15))
light((30,-70,160),650000,120);light((-90,20,90),400000,100);light((80,90,100),700000,80)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24
scene.world.color=(.18,.18,.18)
scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
def render(name):
    scene.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
render('scci_rh-hero.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'scci_rh-presentation.blend'))
# Exploded view: all shifts recorded as animation keys in the saved native scene.
for o in [lid,*annotations]:o.keyframe_insert(data_path='location',frame=1);o.location.z+=38;o.keyframe_insert(data_path='location',frame=60)
for o in [board,*component_objects]:o.keyframe_insert(data_path='location',frame=1);o.location.z+=13;o.keyframe_insert(data_path='location',frame=60)
point(camera,(10,0,38));camera.data.ortho_scale=205
scene.frame_set(60)
render('scci_rh-exploded.png')
scene.frame_start=1;scene.frame_end=60;scene.render.fps=24
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'scci_rh-exploded.blend'))
print('Presentation images and two editable Blender scenes saved.')
