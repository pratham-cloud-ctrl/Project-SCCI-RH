"""Export real saved SCCI_RH geometry to selectable browser glTF, without saving sources.

Run with the Python distributed with FreeCAD (FreeCAD, Part, MeshPart and Import).
Example on this checkout:
  & 'E:\\project workspace assests\\CAD\\FreeCAD\\bin\\python.exe' scripts/inspector/build_cad_assets.py

The source BReps/STEP files remain the engineering authority. Browser meshes are
display derivatives, not manufacturing or anatomical qualification. Coordinate
mapping is FreeCAD millimetres (x,y,z) -> glTF metres (x,z,-y), a proper rotation.
The glTF KHR_mesh_quantization extension bounds position rounding to one signed
16-bit step per primitive. Source colours are retained for named CAD objects;
STEP board bodies use a disclosed categorical palette because the headless STEP
reader does not expose the KiCad per-face render colours.
"""
from __future__ import annotations

import argparse
from array import array
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import zipfile

import FreeCAD as App
import Import
import MeshPart
import Part

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'inspector'
MODEL_DIR = OUT / 'assets/models'
MANIFEST = OUT / 'assets/cad-manifest.json'
LINEAR_MM = .22
ANGULAR_RAD = .5
BOARDS = ('recording-front-end', 'current-driver', 'contact-router', 'supervision',
          'power', 'monitoring-cell', 'monitoring-transport', 'controller-carrier')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def mm_to_m(v):
    return [round(float(v[0]) / 1000, 9), round(float(v[2]) / 1000, 9),
            round(-float(v[1]) / 1000, 9)]


def bbox(shape):
    b = shape.BoundBox
    return [round(x, 6) for x in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]


def combined_bounds(parts):
    bs = [p['bounds_mm'] for p in parts]
    return [min(b[i] for b in bs) for i in range(3)] + [max(b[i+3] for b in bs) for i in range(3)]


def gltf_bounds(mm):
    return [[mm[0]/1000, mm[2]/1000, -mm[4]/1000],
            [mm[3]/1000, mm[5]/1000, -mm[1]/1000]]


def smooth_mesh(shape):
    """Preserve sharp (>35 degree) edges while smoothing tessellated cylinders."""
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=LINEAR_MM,
                                 AngularDeflection=ANGULAR_RAD, Relative=False)
    points, triangles = mesh.Topology
    positions = [mm_to_m(p) for p in points]
    clusters = defaultdict(list)
    vertices, normals, indices = [], [], []
    cutoff = math.cos(math.radians(35))
    for face in triangles:
        a, b, c = [positions[k] for k in face]
        ab, ac = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
        n = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
        length = math.sqrt(sum(x*x for x in n))
        if length < 1e-20:
            continue
        unit = [x/length for x in n]
        for key in face:
            hit = next((v for v in clusters[key] if sum(v[0][i]*unit[i] for i in range(3)) > cutoff), None)
            if hit is None:
                index = len(vertices)
                vertices.append(positions[key]); normals.append(list(unit))
                hit = (unit, index)
                clusters[key].append(hit)
            else:
                index = hit[1]
                normals[index] = [normals[index][i]+unit[i] for i in range(3)]
            indices.append(index)
    assert vertices and indices and len(indices) % 3 == 0
    for n in normals:
        length = math.sqrt(sum(x*x for x in n))
        for i in range(3):
            n[i] /= length
    assert max(indices) < len(vertices)
    return vertices, normals, indices


class GLB:
    def __init__(self):
        self.binary = bytearray()
        self.doc = dict(asset=dict(version='2.0', generator='SCCI_RH native FreeCAD inspection exporter'),
                        scene=0, scenes=[dict(nodes=[])], nodes=[], meshes=[], materials=[],
                        buffers=[dict(byteLength=0)], bufferViews=[], accessors=[],
                        extensionsUsed=['KHR_mesh_quantization'], extensionsRequired=['KHR_mesh_quantization'])
        self.materials = {}
        self.triangles = self.vertices = 0
        self.max_rounding_mm = 0

    def accessor(self, data, component, count, kind, target, **extra):
        while len(self.binary) % 4:
            self.binary.append(0)
        view = len(self.doc['bufferViews'])
        self.doc['bufferViews'].append(dict(buffer=0, byteOffset=len(self.binary), byteLength=len(data), target=target,
                                           **extra.pop('view', {})))
        self.binary.extend(data)
        index = len(self.doc['accessors'])
        self.doc['accessors'].append(dict(bufferView=view, componentType=component, count=count, type=kind, **extra))
        return index

    def material(self, colour, allocation=False):
        colour = tuple(round(float(x), 4) for x in colour[:3])
        key = colour + (allocation,)
        if key not in self.materials:
            self.materials[key] = len(self.doc['materials'])
            self.doc['materials'].append(dict(name='Nominal display palette '+str(colour),
                pbrMetallicRoughness=dict(baseColorFactor=list(colour)+[.35 if allocation else 1],
                    metallicFactor=.25 if sum(colour) > 1.65 else .08, roughnessFactor=.62),
                alphaMode='BLEND' if allocation else 'OPAQUE', doubleSided=False))
        return self.materials[key]

    def geometry_node(self, shape, colour, name, allocation=False):
        vertices, normals, indices = smooth_mesh(shape)
        low = [min(v[i] for v in vertices) for i in range(3)]
        high = [max(v[i] for v in vertices) for i in range(3)]
        centre = [(low[i]+high[i])/2 for i in range(3)]
        # Uniform decode scale keeps 8-bit normals isotropic; a thin PCB must
        # not magnify normal quantization error through inverse-transpose scale.
        span = max(max((high[i]-low[i])/2 for i in range(3)), 1e-9)
        half = [span]*3
        raw_pos, raw_norm = bytearray(), bytearray()
        decoded_low, decoded_high = [32767]*3, [-32767]*3
        for v, n in zip(vertices, normals):
            q = [max(-32767, min(32767, round((v[i]-centre[i])/half[i]*32767))) for i in range(3)]
            raw_pos.extend(struct.pack('<hhhh', *q, 0))
            # Inverse transpose of child scale must produce the original normal.
            scaled_normal = [n[i]*half[i] for i in range(3)]
            length = math.sqrt(sum(x*x for x in scaled_normal))
            qn = [max(-127, min(127, round(x/length*127))) for x in scaled_normal]
            raw_norm.extend(struct.pack('<bbbb', *qn, 0))
            for i in range(3):
                decoded_low[i] = min(decoded_low[i], q[i]); decoded_high[i] = max(decoded_high[i], q[i])
        self.max_rounding_mm = max(self.max_rounding_mm, max(half)/32767*1000/2)
        pos = self.accessor(raw_pos, 5122, len(vertices), 'VEC3', 34962, normalized=True,
                            min=decoded_low, max=decoded_high, view=dict(byteStride=8))
        norm = self.accessor(raw_norm, 5120, len(vertices), 'VEC3', 34962, normalized=True,
                             view=dict(byteStride=4))
        use_short = len(vertices) < 65536
        raw_indices = array('H' if use_short else 'I', indices)
        if sys.byteorder != 'little': raw_indices.byteswap()
        ind = self.accessor(raw_indices.tobytes(), 5123 if use_short else 5125, len(indices), 'SCALAR', 34963)
        mesh = len(self.doc['meshes'])
        self.doc['meshes'].append(dict(name=name, primitives=[dict(attributes=dict(POSITION=pos, NORMAL=norm),
            indices=ind, material=self.material(colour, allocation), mode=4)]))
        node = len(self.doc['nodes'])
        self.doc['nodes'].append(dict(name=name, mesh=mesh, translation=centre, scale=half))
        self.vertices += len(vertices); self.triangles += len(indices)//3
        return node

    def part(self, row, segments):
        parent = len(self.doc['nodes'])
        self.doc['nodes'].append(dict(name=row['id'], extras=row, children=[]))
        self.doc['scenes'][0]['nodes'].append(parent)
        for i, (shape, colour) in enumerate(segments):
            self.doc['nodes'][parent]['children'].append(self.geometry_node(shape, colour, row['id']+'__mesh_'+str(i), row.get('allocation', False)))

    def write(self, path):
        while len(self.binary) % 4: self.binary.append(0)
        self.doc['buffers'][0]['byteLength'] = len(self.binary)
        js = json.dumps(self.doc, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
        js += b' '*((-len(js)) % 4)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(struct.pack('<4sII', b'glTF', 2, 12+8+len(js)+8+len(self.binary))+
                         struct.pack('<I4s', len(js), b'JSON')+js+
                         struct.pack('<I4s', len(self.binary), b'BIN\0')+self.binary)


def board_palette(shape, pcb=False, reference_z=0):
    if pcb: return [.035, .31, .19]
    b = shape.BoundBox
    if b.ZLength < .65 or min(b.XLength, b.YLength) < .65: return [.67, .64, .50]
    if b.ZMin < reference_z+1.2: return [.67, .68, .70]
    return [.10, .12, .15]


def output_model(model_id, title, kind, source, parts, glb, bindings):
    path = MODEL_DIR / (model_id+'.glb')
    glb.write(path)
    bounds = combined_bounds(parts)
    result = dict(id=model_id, title=title, kind=kind, file=path.relative_to(OUT).as_posix(),
                  source=source, parts=parts, bounds_mm=bounds, bounds=gltf_bounds(bounds),
                  bytes=path.stat().st_size, sha256=sha(path), triangles=glb.triangles,
                  vertices=glb.vertices, physical_parts=sum(p['physical'] for p in parts),
                  allocation_parts=sum(p.get('allocation', False) for p in parts), inputs=bindings,
                  native_geometry_valid=True, max_position_quantization_error_mm=glb.max_rounding_mm)
    print(json.dumps({k:v for k,v in result.items() if k not in ('parts','inputs')}, ensure_ascii=True), flush=True)
    return result


def future_model():
    contract_path = 'cad/stage5/future-interface/contract.json'
    contract = read(contract_path)
    source = 'cad/stage5/future-interface/'+contract['artifacts']['native']
    module = ROOT/'cad/stage5/future-interface/scci_rh_future_features.py'
    inputs = {p:sha(ROOT/p) for p in (contract_path, source, module.relative_to(ROOT).as_posix())}
    sys.path.insert(0, str(module.parent))
    import scci_rh_future_features  # noqa: F401 -- binds saved editable features before loading.
    doc = App.openDocument(str(ROOT/source))
    parts, glb = [], GLB()
    try:
        for row in contract['parts']:
            obj = doc.getObject(row['name'])
            assert obj and obj.Shape.isValid() and obj.Shape.Volume > 0, row['name']
            if obj.TypeId == 'Part::FeaturePython':
                assert obj.Proxy.__class__.__module__ == 'scci_rh_future_features', row['name']
            allocation = row['category'] == 'allocation'
            name = obj.Name
            group = ('Internal allocations' if allocation else 'Recording interface' if name.startswith('Rec_') or row.get('port_id','') in {'P%02d'%i for i in range(1,19)}
                     else 'Stimulation interface' if name.startswith('Stim_') or row.get('port_id') else 'Enclosure')
            entry = dict(id=name, name=name, label=row['label'], group=group, physical=not allocation,
                         allocation=allocation, default_hidden=allocation, source=source, source_object=name,
                         bounds_mm=bbox(obj.Shape), role=row['role'], material_proposal=row.get('material_proposal',''),
                         explode=mm_to_m(contract['exploded_transforms'].get(name,[0,0,0])),
                         cover=name.lower() in ('canlid','can_lid','lid'))
            parts.append(entry)
            glb.part(entry, [(obj.Shape, row['color_rgb'])])
    finally:
        App.closeDocument(doc.Name)
    assert len(parts)==236 and sum(p['physical'] for p in parts)==230
    assert all(sha(ROOT/p)==h for p,h in inputs.items()), 'No source changes'
    return output_model('future', 'Future implanted interface concept', 'assembly', source, parts, glb, inputs)


def reference_model(export_step=False):
    receipt_path = 'cad/stage5/combined-assembly-receipt.json'
    receipt = read(receipt_path)
    contract_path = 'cad/stage5/reference/contract.json'
    ref = read(contract_path)
    harness_path = 'cad/stage5/harness/contract.json'
    harness = read(harness_path)
    source = receipt['native']
    inputs = {p:sha(ROOT/p) for p in (receipt_path, contract_path, harness_path, source)}
    categories = {r['label']:r['category'] for r in ref['parts']}
    mates = {r['label']:r for r in harness['mates']}
    doc = App.openDocument(str(ROOT/source))
    parts, features, glb = [], [], GLB()
    try:
        for row in receipt['parts']:
            obj = doc.getObject(row['native_name'])
            assert obj and obj.Shape.isValid() and obj.Shape.Volume>0, row['label']
            features.append(obj)
            category = categories.get(row['label'], 'connector_mate')
            explode = ref['exploded_transforms'].get(row['label'], [0,0,0])
            mate = mates.get(row['source_name'])
            if mate:
                explode = ref['exploded_transforms'].get('PCB_'+mate['board'].replace('-','_'), [0,0,0])
            entry = dict(id=obj.Name, name=obj.Name, label=obj.Label, group=category.replace('_',' ').title(),
                         physical=True, allocation=False, source=source, source_object=obj.Name,
                         original_source=row['source_document'], original_source_object=row['source_name'],
                         bounds_mm=bbox(obj.Shape), explode=mm_to_m(explode), cover=obj.Label in ('Lid','FrontPanel'))
            colour = list(obj.DisplayColor)[:3] if 'DisplayColor' in obj.PropertiesList else list(obj.RenderColour)[:3] if 'RenderColour' in obj.PropertiesList else [.15,.20,.25]
            segments = [(obj.Shape, colour)]
            if category == 'populated_board':
                solids = list(obj.Shape.Solids)
                board_base = min(s.BoundBox.ZMin for s in solids)
                # Selection in this assembly is by whole PCB. Batch its exact
                # source solids by display colour so reference inspection does
                # not issue thousands of GPU draw calls. The individual board
                # viewers separately retain every fitted component reference.
                batches = defaultdict(list)
                for solid in solids:
                    b = solid.BoundBox
                    colour_key = tuple(board_palette(solid, b.XLength>70 and b.YLength>70 and b.ZLength<2, board_base))
                    batches[colour_key].append(solid)
                segments = [(Part.makeCompound(group), list(colour_key)) for colour_key, group in batches.items()]
            parts.append(entry); glb.part(entry, segments)
        if export_step:
            export_complete_reference_step(doc, features, parts, inputs)
    finally:
        App.closeDocument(doc.Name)
    assert len(parts)==260 and len({p['id'] for p in parts})==260
    assert all(sha(ROOT/p)==h for p,h in inputs.items()), 'No source changes'
    return output_model('reference', 'Full-scale reference assembly', 'assembly', source, parts, glb, inputs)


def export_complete_reference_step(doc, features, parts, inputs):
    destination = OUT/'downloads/SCCI_RH_Reference_Complete_STEP.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='scci_rh-inspector-step-') as td:
        step = Path(td)/'SCCI_RH_Reference_Complete.step'
        Import.export(features, str(step))
        # An independent native reopen proves the neutral file contains the exact
        # material count, volume and bounds of the selected 260 final features.
        actual = Part.read(str(step))
        expected = Part.makeCompound([o.Shape for o in features])
        assert actual.isValid() and len(actual.Solids)==len(expected.Solids)
        assert abs(actual.Volume-expected.Volume) < .05
        assert max(abs(a-b) for a,b in zip(bbox(actual),bbox(expected))) < .01
        proof = dict(schema='scci_rh.complete-reference-step.v1', source='cad/stage5/SCCI_RH_stage5_reference_full.FCStd',
                     source_sha256=inputs['cad/stage5/SCCI_RH_stage5_reference_full.FCStd'],
                     physical_objects=len(features), solids=len(actual.Solids), volume_mm3=actual.Volume,
                     bounds_mm=bbox(actual), step_sha256=sha(step), step_bytes=step.stat().st_size,
                     step_native_reopen_valid=True, parts=parts)
        text = ('PROJECT SCCI RH - COMPLETE REFERENCE ASSEMBLY\n\n'
                'Open SCCI_RH_Reference_Complete.step in FreeCAD, Fusion or another STEP-capable CAD application.\n'
                'This neutral CAD exchange contains the same 260 final physical objects as the browser reference viewer: 170 enclosure/board objects and 90 mating-interface objects.\n'
                'Dimensions are millimetres. It is a mechanical digital reference; not an implant or tested fabricated assembly.\n'
                'The existing historical 170-object reference STEP remains unchanged in the repository.\n'
                'Parts and exact source/neutral hashes are supplied in geometry-manifest.json.\n')
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name,data in [(step.name,step.read_bytes()),('README.txt',text.encode()),('geometry-manifest.json',(json.dumps(proof,indent=2)+'\n').encode())]:
                info=zipfile.ZipInfo(name,date_time=(2026,10,21,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        assert destination.stat().st_size<100*1024*1024
        print('Complete 260-object reference STEP ZIP:', destination.stat().st_size, 'bytes', flush=True)


def footprint_rows(board_path, dnp):
    sys.path.insert(0,str(ROOT/'electronics/stage4/integrated-pcb/integration'))
    from sexp import loads, sub, subs
    board = loads(board_path.read_text(encoding='utf-8'))
    rows=[]
    for fp in subs(board,'footprint'):
        props={p[1]:p[2] for p in subs(fp,'property')}
        if not subs(fp,'model') or props['Reference'] in dnp: continue
        at=sub(fp,'at'); model=sub(fp,'model')
        offset=sub(sub(model,'offset'),'xyz')
        ox,oy=(float(offset[1]),float(offset[2])) if offset else (0,0)
        angle=math.radians(float(at[3]) if len(at)>3 else 0)
        # KiCad footprint Y goes down; STEP Y goes up. KiCad model offsets are
        # local right-handed millimetres, rotated with the placed footprint.
        x=float(at[1])+ox*math.cos(angle)-oy*math.sin(angle)
        y=-float(at[2])+ox*math.sin(angle)+oy*math.cos(angle)
        rows.append(dict(reference=props['Reference'], value=props.get('Value',''),
                         xy=[x,y], model=Path(model[1]).stem, footprint=str(fp[1])))
    return rows


def board_model(board):
    source='electronics/stage4/integrated-pcb/exports/'+board+'/populated.step'
    receipt_path='electronics/stage4/integrated-pcb/exports/'+board+'/export-receipt.json'
    receipt=read(receipt_path)
    pcb=receipt['source_board']
    inputs={p:sha(ROOT/p) for p in (source,receipt_path,pcb)}
    fps=footprint_rows(ROOT/pcb,set(receipt['DNP_references']))
    doc=App.newDocument('SCCI_RH_Inspect_'+board.replace('-','_'))
    parts,glb=[],GLB()
    try:
        Import.insert(str(ROOT/source),doc.Name)
        roots=doc.RootObjects
        assert len(roots)==1 and roots[0].TypeId=='App::Part'
        source_parts=[o for o in roots[0].Group if hasattr(o,'Shape') and not o.Shape.isNull()]
        assert len(source_parts)==receipt['fitted_component_count']+1, (board,len(source_parts))
        seen=set()
        for number,obj in enumerate(source_parts):
            shape=obj.Shape
            assert shape.isValid() and shape.Volume>0
            pcb_body=obj.TypeId=='Part::Feature' and obj.Label.endswith('_PCB')
            match=None
            if not pcb_body:
                xy=[obj.Placement.Base.x,obj.Placement.Base.y]
                candidates=[(math.dist(xy,r['xy']),r) for r in fps if r['reference'] not in seen]
                error,match=min(candidates,key=lambda v:v[0])
                assert error < .02, (board,obj.Label,xy,error,match)
                seen.add(match['reference'])
            reference=match['reference'] if match else 'PCB'
            entry=dict(id=reference,name=reference,label=(reference+' | '+match['value']) if match else 'PCB substrate',
                       group='PCB substrate' if pcb_body else 'Populated components',physical=True,allocation=False,
                       source=source,source_object=obj.Name,source_label=obj.Label,pcb_source=pcb,
                       bounds_mm=bbox(shape),explode=[0,0,0] if pcb_body else [0,.012,0])
            if match: entry.update(reference=reference,value=match['value'],footprint=match['footprint'],model=match['model'])
            parts.append(entry)
            solids=list(shape.Solids)
            glb.part(entry,[(s,board_palette(s,pcb_body)) for s in solids])
        assert seen=={r['reference'] for r in fps} and len(seen)==receipt['fitted_component_count']
        assert not (seen & set(receipt['DNP_references']))
    finally:
        App.closeDocument(doc.Name)
    assert all(sha(ROOT/p)==h for p,h in inputs.items()),'No source changes'
    result=output_model(board,board.replace('-',' ').title()+' PCB','board',source,parts,glb,inputs)
    result.update(pcb_source=pcb,fitted_components=len(seen),DNP_references=receipt['DNP_references'],
                  colour_scope='Categorical display palette; STEP solids preserved, not KiCad per-face rendering colours.')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',nargs='+',choices=['future','reference',*BOARDS],default=['future',*BOARDS,'reference'])
    parser.add_argument('--complete-reference-step',action='store_true')
    args=parser.parse_args()
    existing=read(MANIFEST.relative_to(ROOT).as_posix()) if MANIFEST.is_file() else {}
    models={m['id']:m for m in existing.get('models',[])}
    for model_id in args.models:
        model=future_model() if model_id=='future' else reference_model(args.complete_reference_step) if model_id=='reference' else board_model(model_id)
        models[model_id]=model
        manifest=dict(schema='scci_rh.browser-cad-inspection.v1',units='metres',native_units='millimetres',
            coordinate_mapping='[x_mm,y_mm,z_mm] -> [x_mm/1000,z_mm/1000,-y_mm/1000]',
            source_files_unchanged=True,native_engine='FreeCAD '+'.'.join(App.Version()[:3]),
            derivation='Native saved BReps tessellated through FreeCAD MeshPart; no invented or reconstructed geometry.',
            mesh_settings=dict(linear_deflection_mm=LINEAR_MM,angular_deflection_radians=ANGULAR_RAD,
                position_quantization='signed 16 bit per primitive bounds',sharp_edge_threshold_degrees=35),
            scope='Visualization derivatives only. No physical, manufacturing, anatomical or biological qualification.',
            exporter='scripts/inspector/build_cad_assets.py',exporter_sha256_lf=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            reproduce="& '<FreeCAD installation>/bin/python.exe' scripts/inspector/build_cad_assets.py --complete-reference-step",
            models=[models[k] for k in ['future','reference',*BOARDS] if k in models])
        MANIFEST.parent.mkdir(parents=True,exist_ok=True)
        MANIFEST.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__': main()
