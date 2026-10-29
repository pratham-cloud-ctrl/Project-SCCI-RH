"""Blender technical plate renders from saved native geometry derivatives.

blender --background --python cad/stage5/render_assemblies.py
"""
from pathlib import Path
import gzip,json,math,sys
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'renders';OUT.mkdir(exist_ok=True)
with gzip.open(ROOT/'tmp/stage5-render-meshes.json.gz','rt',encoding='utf-8') as f:DATA=json.load(f)


def material(name,c,metal=False):
    m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
    b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*c,1)
    b.inputs['Roughness'].default_value=.32 if metal else .48
    b.inputs['Metallic'].default_value=.65 if metal else 0
    return m


def scene_for(kind,exploded=False):
    name=kind+('_exploded' if exploded else '_assembled')
    scene=bpy.data.scenes.new(name)
    bpy.context.window.scene=scene
    scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.resolution_x=1900;scene.render.resolution_y=1350;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new(name+'_World');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.82,.87,.92,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
    scene.view_settings.view_transform='AgX'
    materials={};points=[]
    for row in DATA[kind]:
        n=row['name'];cat=row['category'];allocation=('allocation' in cat.lower() or 'reservation' in cat.lower())
        if allocation:continue
        if kind=='reference':
            if row['parent'] in ('FrontPanel','Lid','LeftPanel') or cat=='lid_screw':
                if not exploded:continue
            # Hide ordinary opaque left wall so all four populated tiers can be inspected.
            if row['parent']=='LeftPanel' and exploded:continue
        mesh=bpy.data.meshes.new(n);mesh.from_pydata(row['mesh']['vertices'],[],row['mesh']['faces']);mesh.update()
        obj=bpy.data.objects.new(n,mesh);scene.collection.objects.link(obj)
        obj.scale=(.001,.001,.001)
        if exploded:
            if kind=='reference':
                obj.location.z=row.get('explode_z',0)*.001
                if row['parent']=='FrontPanel':obj.location.y=-.065
                if row['parent']=='Lid':obj.location.x=-.025
            else:
                # Use the package's explicit rigid exploded placement map.
                delta=row.get('explode_translation_mm',[0,0,0])
                obj.location=Vector(delta)*.001
        c=row['color'][:3];key=tuple(round(x,3) for x in c)
        if key not in materials:materials[key]=material(str(key),[v**2.2 for v in c] if kind=='future' else c,metal=max(c)-min(c)<.18 and max(c)>.45)
        obj.data.materials.append(materials[key])
        points.extend([obj.matrix_world @ Vector(v) for v in []])
    bpy.context.view_layer.update()
    # Object matrices of a non-active scene need explicit scale+translation.
    for obj in scene.objects:
        if obj.type=='MESH':
            points.extend([obj.matrix_world @ Vector(v) for v in obj.bound_box])
    low=Vector([min(p[i] for p in points) for i in range(3)]);high=Vector([max(p[i] for p in points) for i in range(3)])
    centre=(low+high)/2;span=high-low
    ground_mesh=bpy.data.meshes.new(name+'_ground')
    extent=max(span)*4
    ground_mesh.from_pydata([(-extent,-extent,low.z-.001),(extent,-extent,low.z-.001),(extent,extent,low.z-.001),(-extent,extent,low.z-.001)],[],[(0,1,2,3)])
    ground=bpy.data.objects.new(name+'_ground',ground_mesh);scene.collection.objects.link(ground);ground.data.materials.append(material(name+'_white',(.87,.90,.92)))
    camera_data=bpy.data.cameras.new(name+'_camera');camera=bpy.data.objects.new(name+'_camera',camera_data);scene.collection.objects.link(camera)
    direction=Vector((1,-1.65,1.15) if kind=='reference' else (1,-1.8,1.55)).normalized()
    camera.location=centre+direction*max(span)*2.5;camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler();camera_data.type='ORTHO'
    # Project extents onto camera axes for a guaranteed unclipped composition.
    right=camera.rotation_euler.to_matrix() @ Vector((1,0,0));up=camera.rotation_euler.to_matrix() @ Vector((0,1,0))
    projected_w=max(p.dot(right) for p in points)-min(p.dot(right) for p in points)
    projected_h=max(p.dot(up) for p in points)-min(p.dot(up) for p in points)
    centre += right*((max(p.dot(right) for p in points)+min(p.dot(right) for p in points))/2-centre.dot(right))
    centre += up*((max(p.dot(up) for p in points)+min(p.dot(up) for p in points))/2-centre.dot(up))
    camera.location=centre+direction*max(span)*2.5
    camera_data.ortho_scale=max(projected_w,projected_h*1900/1350)*1.18
    camera_data.lens=50;camera_data.clip_start=.0001;camera_data.clip_end=100
    scene.camera=camera
    bpy.context.view_layer.update()
    from bpy_extras.object_utils import world_to_camera_view
    frame=[world_to_camera_view(scene,camera,p) for p in points]
    assert all(.01<p.x<.99 and .01<p.y<.99 for p in frame),(name,'model clips frame',min(p.y for p in frame),max(p.y for p in frame))
    for idx,(side,power,size) in enumerate([((-1,-1,2.5),450,2),((2,.5,1.5),250,1.5),((0,2,2),300,1.5)]):
        l=bpy.data.lights.new(name+str(idx),'AREA');l.energy=power*(max(span)**2)*(.5 if kind=='future' else 1);l.shape='DISK';l.size=max(span)*size
        o=bpy.data.objects.new(name+str(idx),l);scene.collection.objects.link(o);o.location=centre+Vector(side)*max(span);o.rotation_euler=(centre-o.location).to_track_quat('-Z','Y').to_euler()
    if kind=='future':scene.world.node_tree.nodes['Background'].inputs[1].default_value=.25
    scene.render.filepath=str(OUT/(name+'.png'))
    bpy.context.window.scene=scene
    bpy.ops.render.render(write_still=True)
    return scene


future_only='--future-only' in sys.argv
if future_only:
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'SCCI_RH_engineering_assemblies.blend'))
    for old in [s for s in bpy.data.scenes if s.name.startswith('future_')]:bpy.data.scenes.remove(old)
else:bpy.ops.wm.read_factory_settings(use_empty=True)
for kind in (('future',) if future_only else ('reference','future')):
    for exploded in (False,True):scene_for(kind,exploded)
for empty in [s for s in bpy.data.scenes if not s.objects]:bpy.data.scenes.remove(empty)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SCCI_RH_engineering_assemblies.blend'),compress=True)
print('Savedfourtechnicalrendersandfour-sceneBlenderderivative.')
