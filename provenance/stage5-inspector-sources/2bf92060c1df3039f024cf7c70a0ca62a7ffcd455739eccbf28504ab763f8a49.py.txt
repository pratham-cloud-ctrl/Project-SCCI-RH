"""Independent, read-only Stage 5 BRep inspection using FreeCAD Python.

The assembly generators are deliberately not imported. Original KiCad STEP
files and PCB hole coordinates are reopened independently. A saved receipt is
evidence of this local native inspection, not physical qualification.
"""
from __future__ import annotations

import argparse
import hashlib
from itertools import combinations,product
import json
import math
from pathlib import Path
import sys
import tempfile
import zipfile

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]
COORDINATE_TOLERANCE_MM = .001  # 1 micrometre exchange tolerance; not a manufacturing tolerance.
RESUME_CHECKPOINTS = False
sys.path.insert(0, str(ROOT / 'electronics/stage4/integrated-pcb/integration'))
from sexp import loads, sub, subs


def digest(path, text=False):
    data = Path(path).read_bytes()
    if text:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def canonical(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def artifact_path(package_path, value):
    path = Path(value)
    return package_path.parent/path if path.parent==Path('.') else ROOT/path


def log(message):
    print(message,file=sys.stderr,flush=True)


def phase_checkpoint(package_name,phase,bindings,operation):
    """Resume only machine-written successful checks of identical frozen inputs.

    Local checkpoints are not producer CAD assertions and are not release
    receipts. They are written only after this independent operation returns;
    exact inspector, package, native, exchange and source bytes must still match.
    """
    path=ROOT/'tmp/stage5-native-checkpoints'/(package_name+'-'+phase+'.json')
    if RESUME_CHECKPOINTS and path.is_file():
        saved=json.loads(path.read_text(encoding='utf-8'))
        if saved.get('completed') is True and saved.get('bindings')==bindings:
            log(package_name+': resume verified phase '+phase)
            return saved['result']
    log(package_name+': executing independent phase '+phase)
    result=operation()
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(dict(completed=True,bindings=bindings,result=result),
                              indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


def read_step(path):
    if path.suffix.lower()!='.zip':
        return Part.read(str(path))
    with zipfile.ZipFile(path) as archive:
        members=[n for n in archive.namelist() if n.lower().endswith('.step')]
        assert len(members)==1 and archive.testzip() is None,'single intact STEP archive'
        with tempfile.TemporaryDirectory(prefix='scci_rh-stage5-inspect-') as temporary:
            extracted=Path(temporary)/Path(members[0]).name
            extracted.write_bytes(archive.read(members[0]))
            return Part.read(str(extracted))


def step_binding(path):
    binding={'sha256':digest(path)}
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as archive:
            member=next(n for n in archive.namelist() if n.lower().endswith('.step'))
            binding.update(member=member,uncompressed_sha256=hashlib.sha256(archive.read(member)).hexdigest())
    return binding


def bounds(shape):
    # Default OCC boxes can conservatively overshoot a trimmed B-spline by
    # several micrometres and vary after STEP parameterisation. Ask the kernel
    # for actual trimmed extrema without mesh or shape-tolerance inflation.
    b = shape.optimalBoundingBox(False,False)
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


def disjoint_bounds(a, b, epsilon=1e-8):
    # Conservative cached kernel boxes are appropriate for broad phase: an
    # overshoot creates extra exact checks, never a missed material collision.
    def broad(shape):
        q=shape.BoundBox
        return [q.XMin,q.YMin,q.ZMin,q.XMax,q.YMax,q.ZMax]
    aa,bb=broad(a),broad(b)
    return any(min(aa[i + 3], bb[i + 3]) - max(aa[i], bb[i]) <= epsilon for i in range(3))


def shape_metrics(shape):
    solids=shape.Solids
    volume=sum(s.Volume for s in solids)
    assert volume>0, 'positive material volume for shape metrics'
    c=sum((s.CenterOfMass*s.Volume for s in solids),App.Vector(0,0,0))/volume
    return dict(solids=len(shape.Solids), volume_mm3=shape.Volume,
                bounds_mm=bounds(shape), centre_mm=[c.x, c.y, c.z])


def assert_close(left, right, tolerance, reason):
    error=max((abs(a-b) for a,b in zip(left,right)),default=0)
    assert len(left)==len(right) and error<=tolerance,(reason,error,tolerance,left,right)


def placed(shape, row):
    result = shape.copy()
    rotation = row.get('rotation', {'axis': [0, 0, 1], 'degrees': 0})
    if rotation['degrees']:
        result.rotate(App.Vector(0, 0, 0), App.Vector(*rotation['axis']), rotation['degrees'])
    result.translate(App.Vector(*row['translation_mm']))
    return result


def native_mounts(path):
    """Derive all mechanical pad datums from the frozen native PCB itself."""
    board = loads(Path(path).read_text(encoding='utf-8'))
    rows = []
    for footprint in subs(board, 'footprint'):
        if not str(footprint[1]).startswith('MountingHole:'):
            continue
        at = sub(footprint, 'at')
        reference = next(p[2] for p in subs(footprint, 'property') if p[1] == 'Reference')
        pads = subs(footprint, 'pad')
        assert len(pads) == 1 and sub(pads[0], 'drill'), 'one drilled mounting pad'
        local = sub(pads[0], 'at')
        assert abs(float(local[1])) < 1e-9 and abs(float(local[2])) < 1e-9, 'central mounting pad'
        rows.append(dict(reference=reference, pcb_xy_mm=[float(at[1]), float(at[2])],
                         diameter_mm=float(sub(pads[0], 'drill')[1])))
    return sorted(rows, key=lambda row: row['reference'])


def physical_features(doc):
    return {o.Label: o for o in doc.Objects if hasattr(o, 'Shape') and not o.Shape.isNull()
            and not o.TypeId.startswith(('App::Part', 'PartDesign::Body'))}


def cylinder_surfaces(shape):
    values = []
    for face in shape.Faces:
        surface = face.Surface
        if isinstance(surface, Part.Cylinder):
            values.append(dict(radius_mm=surface.Radius,
                               centre_mm=list(surface.Center), axis=list(surface.Axis)))
    return values


def has_vertical_cylinder(shape, xy, radius):
    return any(abs(c['radius_mm']-radius) < 1e-5 and
               abs(c['centre_mm'][0]-xy[0]) < 1e-5 and
               abs(c['centre_mm'][1]-xy[1]) < 1e-5 and
               abs(abs(c['axis'][2])-1) < 1e-7 for c in cylinder_surfaces(shape))


def same_solids(expected, actual, reason):
    """Compare each actual solid to the independently transformed source solid.

    Volume, centre, bounds, every vertex, face area/centre/surface class and
    edge curve samples are compared. Source topology is not replaced by a
    manufacturer's body envelope or a generator's success flag. Interference
    uses exact Boolean material intersections separately; subtracting two
    coincident STEP solids adds no useful finite acceptance information here.
    """
    key = lambda s: tuple(round(x, 5) for x in [*bounds(s), s.Volume])
    aa, bb = sorted(expected.Solids, key=key), sorted(actual.Solids, key=key)
    assert len(aa) == len(bb), reason + ' solid cardinality'
    maximum_volume_error=maximum_coordinate_error=0.0
    def compare_points(aa,bb,why,curve_shapes=None):
        nonlocal maximum_coordinate_error
        assert len(aa)==len(bb),why+' cardinality'
        tolerance=COORDINATE_TOLERANCE_MM
        def one_direction(left,right,fallback=None):
            nonlocal maximum_coordinate_error
            cells={}
            def cell(p):return tuple(math.floor(v/tolerance) for v in p)
            for p in right:cells.setdefault(cell(p),[]).append(p)
            for a in left:
                centre=cell(a)
                candidates=[p for delta in product((-1,0,1),repeat=3)
                            for p in cells.get(tuple(c+d for c,d in zip(centre,delta)),[])]
                error=min((max(abs(x-y) for x,y in zip(a,b)) for b in candidates),default=math.inf)
                if error>tolerance and fallback is not None:
                    error=Part.Vertex(App.Vector(*a)).distToShape(fallback)[0]
                assert error<=tolerance,(why,error,tolerance,a)
                maximum_coordinate_error=max(maximum_coordinate_error,error)
        one_direction(aa,bb,curve_shapes[1] if curve_shapes else None)
        one_direction(bb,aa,curve_shapes[0] if curve_shapes else None)
    for index,(source, result) in enumerate(zip(aa, bb)):
        if index%100==0:
            log(reason+': solid '+str(index+1)+'/'+str(len(aa)))
        assert source.isValid() and result.isValid(), reason + ' valid constituent solid'
        assert abs(source.Volume-result.Volume) < max(1e-4, source.Volume*1e-6), reason + ' solid volume'
        assert_close(bounds(source), bounds(result), COORDINATE_TOLERANCE_MM, reason + ' solid bounds')
        assert_close(list(source.CenterOfMass), list(result.CenterOfMass), COORDINATE_TOLERANCE_MM, reason + ' solid centre')
        assert len(source.Faces)==len(result.Faces) and len(source.Edges)==len(result.Edges), reason+' exact face/edge topology counts'
        compare_points([list(v.Point) for v in source.Vertexes],
                       [list(v.Point) for v in result.Vertexes],reason+' full vertex geometry')
        face_signature=lambda s:[(str(type(f.Surface)),f.Area,*list(f.CenterOfMass),*bounds(f)) for f in s.Faces]
        af,bf=face_signature(source),face_signature(result)
        assert len(af)==len(bf)
        for a in af:
            candidates=[(i,b) for i,b in enumerate(bf) if a[0]==b[0]]
            assert candidates,reason+' face analytic surface class'
            index,b=min(candidates,key=lambda item:max(abs(x-y) for x,y in zip(a[2:],item[1][2:])))
            bf.pop(index)
            assert abs(a[1]-b[1])<max(.001,abs(a[1])*1e-5),(reason+' face area',a,b)
            assert_close(a[2:],b[2:],COORDINATE_TOLERANCE_MM,reason+' every face centre/bounds')
        def edge_samples(s):
            samples=[]
            for edge in s.Edges:
                for fraction in (0,.25,.5,.75,1):
                    samples.append(list(edge.valueAt(edge.FirstParameter+(edge.LastParameter-edge.FirstParameter)*fraction)))
            return samples
        compare_points(edge_samples(source),edge_samples(result),reason+' all edge curve quarter samples',
                       (Part.makeCompound(source.Edges),Part.makeCompound(result.Edges)))
        maximum_volume_error=max(maximum_volume_error,abs(source.Volume-result.Volume))
    return dict(compared_solids=len(aa),max_volume_error_mm3=maximum_volume_error,
                max_coordinate_error_mm=maximum_coordinate_error,
                coordinate_tolerance_mm=COORDINATE_TOLERANCE_MM,solid_volume_absolute_tolerance_mm3=1e-4,
                solid_volume_relative_tolerance=1e-6,face_area_absolute_tolerance_mm2=.001,
                face_area_relative_tolerance=1e-5,
                method='Per-solid volume, bounds, centre, full vertex geometry, face surface class/area/centre/bounds and all edge quarter samples')


def intersection_volume(a,b):
    # Testing full board compounds sends hundreds of irrelevant packages into
    # one Boolean operation. Prune only disjoint constituent bounding boxes;
    # every remaining material pair still receives an exact BRep Boolean.
    if len(a.Solids)==len(b.Solids)==1:
        return a.common(b).Volume
    return sum(sa.common(sb).Volume for sa in a.Solids for sb in b.Solids
               if not disjoint_bounds(sa,sb))


def check_interference(features, physical_labels, exceptions, required_labels=None):
    allowed = {}
    for row in exceptions:
        pair = frozenset((row['a'], row['b']))
        assert len(pair) == 2 and pair not in allowed and row['reason'], 'finite, reasoned interface exception'
        assert pair <= set(physical_labels), 'interface labels exist'
        allowed[pair] = row
    checked = exact = 0
    engagements = []
    for a, b in combinations(physical_labels, 2):
        if required_labels is not None and a not in required_labels and b not in required_labels:
            continue
        checked += 1
        sa, sb = features[a].Shape, features[b].Shape
        if disjoint_bounds(sa, sb):
            continue
        exact += 1
        if exact%50==1:
            log('Material pair '+str(exact)+': '+a+' / '+b)
        volume = intersection_volume(sa,sb)
        exception = allowed.get(frozenset((a, b)))
        maximum = exception['max_volume_mm3'] if exception else 1e-5
        assert volume <= maximum + 1e-6, ('unexplained material interference', a, b, volume, maximum)
        if volume > 1e-5:
            engagements.append(dict(a=a, b=b, volume_mm3=volume, reason=exception['reason']))
    return dict(physical_pairs_checked=checked, exact_BRep_pairs=exact,
                explained_engagements=engagements, unexplained_positive_volume_intersections=0)


def inspect_package(contract, name):
    package_path = ROOT / contract[name]['contract']
    package = json.loads(package_path.read_text(encoding='utf-8'))
    artifacts = package.get('artifacts', package)
    native_path = artifact_path(package_path,artifacts['native'])
    step_path = artifact_path(package_path,artifacts['step'])
    sys.path.insert(0,str(native_path.parent))
    native = App.openDocument(str(native_path))
    try:
        all_features = physical_features(native)
        inventory = package['parts']
        expected_labels = [p.get('label', p.get('name')) for p in inventory]
        assert len(expected_labels) == len(set(expected_labels)), 'unique final part labels'
        assert set(expected_labels) <= set(all_features), 'every contracted final part exists in native document'
        features = {label: all_features[label] for label in expected_labels}
        rows = []
        physical_labels = []
        for part in inventory:
            label = part.get('label', part.get('name'))
            obj = features[label]
            shape = obj.Shape
            category = part['category']
            assert shape.isValid() and shape.Volume > 0 and len(shape.Solids) > 0, ('valid solid', name, label)
            if category not in ('allocation', 'visual_guide', 'reservation'):
                physical_labels.append(label)
            rows.append(dict(label=label, category=category, **shape_metrics(shape)))
        source_paths=[ROOT/b[key] for b in package.get('boards',[]) for key in ('source_step','source_pcb')]
        extra_paths=[artifact_path(package_path,artifacts[key]) for key in ('mechanical_step','exploded_step') if key in artifacts]
        bindings=dict(inspector_sha256_lf=digest(Path(__file__),True),FreeCAD_version=list(App.Version()),
                      contract_canonical_sha256=canonical(package_path),native_sha256=digest(native_path),
                      files={p.relative_to(ROOT).as_posix():digest(p,p.suffix.lower() in ('.kicad_pcb',))
                             for p in [step_path,*extra_paths,*source_paths]})
        native_specific=phase_checkpoint(name,'native-specific',bindings,
            lambda:inspect_reference(package,features) if name=='reference' else inspect_future(package,features))
        # Exchange geometry is reopened from disk, not taken from the producer
        # receipt. Counts and aggregate topology are checked independently.
        export_categories=package.get('step_included_categories')
        export_labels=[p.get('label',p.get('name')) for p in inventory
                       if export_categories is None or p['category'] in export_categories]
        native_compound = Part.makeCompound([features[label].Shape for label in export_labels])
        def compare_nominal():
            exchange=read_step(step_path)
            assert exchange.isValid() and all(s.isValid() and s.Volume>0 for s in exchange.Solids),'valid reimported STEP solids'
            return same_solids(native_compound,exchange,name+' native/STEP')
        step_comparison=phase_checkpoint(name,'nominal-step',bindings,compare_nominal)
        step_evidence=step_binding(step_path)
        if 'step_sha256_uncompressed' in package:
            assert step_evidence['uncompressed_sha256']==package['step_sha256_uncompressed'],'declared exact lossless STEP archive'
            assert step_evidence['member']==package['step_member'],'declared exact STEP member'
        extra_exports={}
        if 'mechanical_step' in artifacts:
            mechanical_path=artifact_path(package_path,artifacts['mechanical_step'])
            mechanical=Part.makeCompound([features[p['label']].Shape for p in inventory if p['category']!='populated_board'])
            extra_exports['mechanical_step']={**step_binding(mechanical_path),
                **phase_checkpoint(name,'mechanical-step',bindings,
                    lambda:same_solids(mechanical,read_step(mechanical_path),name+' mechanical-only STEP'))}
        if 'exploded_step' in artifacts:
            exploded_path=artifact_path(package_path,artifacts['exploded_step'])
            offsets=package['exploded_transforms']
            included=package.get('exploded_included_categories')
            shapes=[]
            for p in inventory:
                if included is not None and p['category'] not in included:
                    continue
                label=p.get('label',p.get('name'));obj=features[label]
                key=label if label in offsets else obj.Name
                assert key in offsets,'every exploded part has an explicit rigid offset'
                shape=obj.Shape.copy();shape.translate(App.Vector(*offsets[key]));shapes.append(shape)
            log(name+': reading exploded STEP')
            extra_exports['exploded_step']={**step_binding(exploded_path),
                **phase_checkpoint(name,'exploded-step',bindings,
                    lambda:same_solids(Part.makeCompound(shapes),read_step(exploded_path),name+' exploded STEP'))}
            if 'exploded_step_sha256_uncompressed' in package:
                assert extra_exports['exploded_step']['uncompressed_sha256']==package['exploded_step_sha256_uncompressed']
        interference = check_interference(features, physical_labels, package.get('allowed_intersections', []))
        clearances = []
        for row in package.get('clearance_checks', []):
            measured = features[row['a']].Shape.distToShape(features[row['b']].Shape)[0]
            assert measured >= row['minimum_mm']-2e-5, ('clearance allocation', row, measured)
            clearances.append(dict(a=row['a'], b=row['b'], minimum_mm=row['minimum_mm'], measured_mm=measured))
        result = dict(contract=package_path.relative_to(ROOT).as_posix(),
                      contract_canonical_sha256=canonical(package_path),
                      native=native_path.relative_to(ROOT).as_posix(), native_sha256=digest(native_path),
                      step=step_path.relative_to(ROOT).as_posix(), step_sha256=digest(step_path),
                      parts=rows, final_objects=len(rows), physical_objects=len(physical_labels),
                      step_comparison=step_comparison,step_evidence=step_evidence,extra_exports=extra_exports,
                      interference=interference, clearances=clearances,
                      physical_qualification=False)
        result.update(native_specific)
        return result
    finally:
        App.closeDocument(native.Name)


def inspect_reference(package, features):
    boards, mounts = [], []
    assert len(package['boards']) == 8 and len(package['mounts']) == 32
    panels=[features[p['label']].Shape for p in package['parts'] if p['category']=='enclosure_panel']
    feet=[features[p['label']].Shape for p in package['parts'] if p['category']=='foot']
    assert len(panels)==6 and len(feet)==4,'six actual enclosure panels and four feet'
    case=Part.makeCompound(panels+feet)
    actual=[case.BoundBox.XLength,case.BoundBox.YLength,case.BoundBox.ZLength]
    assert_close(actual,package['case_dimensions_mm'],1e-5,'native overall chassis dimensions including feet')
    for row in package['boards']:
        label = row['label']
        source_path, pcb_path = ROOT/row['source_step'], ROOT/row['source_pcb']
        assert digest(source_path) == row['source_step_sha256'], 'actual frozen STEP source'
        assert digest(pcb_path, True) == row['source_pcb_sha256_lf'], 'actual frozen PCB source'
        assert row['rotation_axis_angle'] == [0, 0, 1, 0], 'approved translation-only board arrangement'
        source = read_step(source_path)
        transformed = placed(source, row)
        comparison = same_solids(transformed, features[label].Shape, 'actual populated '+row['board'])
        native_holes = native_mounts(pcb_path)
        assert len(native_holes) == 4, 'four actual drilled mounting holes'
        substrate = max(features[label].Shape.Solids, key=lambda s:s.Volume)
        for hole in native_holes:
            # Native STEP axes are X=PCB X, Y=-PCB Y; all eight transforms
            # remain translation-only and therefore cannot conceal a mirror.
            x = row['translation_mm'][0]+hole['pcb_xy_mm'][0]
            y = row['translation_mm'][1]-hole['pcb_xy_mm'][1]
            mount = next(m for m in package['mounts'] if m['board']==row['board'] and m['reference']==hole['reference'])
            assert_close(mount['axis_xy_mm'], [x,y], 1e-6, 'mount axis from original native PCB')
            assert abs(mount['board_hole_radius_mm']-hole['diameter_mm']/2) < 1e-7
            assert has_vertical_cylinder(substrate, [x,y], hole['diameter_mm']/2), ('actual substrate hole',row['board'],hole['reference'])
            standoff = features[mount['standoff_label']].Shape
            assert has_vertical_cylinder(standoff, [x,y], mount['standoff_outer_radius_mm']), 'actual standoff outside diameter'
            assert has_vertical_cylinder(standoff, [x,y], mount['standoff_bore_radius_mm']), 'actual standoff bore'
            assert abs(standoff.BoundBox.ZMin-mount['standoff_bottom_z_mm']) < 1e-6
            assert abs(standoff.BoundBox.ZMax-mount['standoff_top_z_mm']) < 1e-6
            assert abs(standoff.BoundBox.ZLength-package['standoff_length_mm']) < 1e-6
            assert abs(standoff.distToShape(substrate)[0]) < 1e-5, 'actual substrate/standoff seating'
            for screw_key in ('upper_screw_label','lower_screw_label'):
                screw = features[mount[screw_key]].Shape
                assert has_vertical_cylinder(screw, [x,y], mount['screw_shaft_radius_mm']), 'actual fastener shaft axis/radius'
                assert has_vertical_cylinder(screw, [x,y], mount['screw_head_radius_mm']), 'actual fastener head axis/radius'
            assert mount['screw_shaft_radius_mm'] < mount['board_hole_radius_mm'], 'positive screw-to-board radial allowance'
            assert mount['screw_shaft_radius_mm'] < mount['standoff_bore_radius_mm'], 'nominal thread-free model radial allowance'
            mounts.append(dict(board=row['board'], reference=hole['reference'], axis_xy_mm=[x,y],
                               drilled_diameter_mm=hole['diameter_mm'], standoff_seated=True,
                               shaft_to_board_radial_allowance_mm=hole['diameter_mm']/2-mount['screw_shaft_radius_mm']))
        boards.append(dict(board=row['board'], source_step=row['source_step'], source_sha256=digest(source_path),
                           source_pcb=row['source_pcb'], source_pcb_sha256_lf=digest(pcb_path, True),
                           translation_mm=row['translation_mm'], **comparison))
    return dict(boards=boards,mounts=mounts,case_envelope_including_feet_mm=actual)


def inspect_future(package, features):
    ports = package['ports']
    assert len(ports)==36 and len({p['port_id'] for p in ports})==36
    by_native_name = {obj.Name: obj for obj in features.values()}
    def object_for(name):
        return features.get(name, by_native_name.get(name))
    # Detailed interface distances are evaluated against actual saved shapes.
    inspected = []
    checks = package['checks']
    can = object_for('Can').Shape
    for port in ports:
        pin=object_for(port['pin_object']).Shape
        ferrule=object_for(port['ferrule_object']).Shape
        minimum_can=pin.distToShape(can)[0]
        minimum_ferrule=pin.distToShape(ferrule)[0]
        assert minimum_can >= checks['minimum_pin_to_can_mm']-1e-5, ('pin-to-can',port['port_id'],minimum_can)
        assert minimum_ferrule >= checks['minimum_pin_to_ferrule_mm']-1e-5, ('pin-to-ferrule',port['port_id'],minimum_ferrule)
        for field in ('pin_object','ceramic_object','ferrule_object','socket_object','conductor_object','contact_object'):
            assert object_for(port[field]) is not None, ('actual port part',port['port_id'],field)
        inspected.append(dict(port_id=port['port_id'], logical_function=port['logical_function'],
                              minimum_pin_to_can_mm=minimum_can,minimum_pin_to_ferrule_mm=minimum_ferrule))
    contacts=[object_for(p['contact_object']).Shape for p in ports]
    minimum_contact_gap=min(a.distToShape(b)[0] for a,b in combinations(contacts,2))
    assert minimum_contact_gap >= checks['minimum_distal_contact_edge_gap_mm']-1e-5, 'actual adjacent distal contact separation'
    return dict(ports=inspected,minimum_distal_contact_gap_mm=minimum_contact_gap)


def inspect_harness(contract):
    package_path=ROOT/contract['harness']['contract']
    package=json.loads(package_path.read_text(encoding='utf-8'))
    reference_path=ROOT/contract['reference']['contract']
    reference=json.loads(reference_path.read_text(encoding='utf-8'))
    native=App.openDocument(str(ROOT/package['native']))
    chassis=App.openDocument(str(ROOT/reference['native']))
    routes=App.openDocument(str(ROOT/package['routing_native']))
    try:
        all_features=physical_features(native)
        expected={m['label'] for m in package['mates']} | {
            'RearInsert_ArtificialLoad','RearInsert_CompanionPowerDebug',
            'Grommet_ArtificialLoad_58','Grommet_ArtificialLoad_96',
            'Grommet_CompanionPowerDebug_410','Grommet_CompanionPowerDebug_440',
            'Grommet_CompanionPowerDebug_470'}
        assert expected<=set(all_features),'all actual mating and rear interface parts exist'
        features={label:all_features[label] for label in expected}
        assert len(features)==90 and len(package['mates'])==83, '83 sockets and seven rear interface parts'
        assert all(o.Shape.isValid() and o.Shape.Volume>0 and len(o.Shape.Solids)==1 for o in features.values()), 'actual valid mating solids'
        log('harness: reading saved STEP')
        exchange=read_step(ROOT/package['step'])
        comparison=same_solids(Part.makeCompound([o.Shape for o in features.values()]),exchange,'mating native/STEP')
        chassis_features=physical_features(chassis)
        reference_features={p['label']:chassis_features[p['label']] for p in reference['parts']}
        combined={**reference_features,**features}
        assert len(combined)==len(features)+len(reference_features), 'global unique part labels'
        interference=check_interference(combined,list(combined),[],required_labels=set(features))
        sockets=[]
        for mate in package['mates']:
            shape=features[mate['label']].Shape
            pins=mate['pins']
            assert len(pins)==mate['pin_count'], 'actual mating pin cardinality'
            expected_volume=(mate['housing_length_mm']*mate['housing_width_mm']-
                             mate['pin_count']*mate['square_cavity_mm']**2)*mate['housing_height_mm']
            assert abs(shape.Volume-expected_volume)<1e-5, ('actual bored socket material volume',mate['label'])
            minimum_bore_gap=1e9
            for pin in pins:
                a,b=App.Vector(*pin['axis_mm']),App.Vector(*pin['wire_exit_mm'])
                line=Part.makeLine(a,b)
                assert shape.common(line).Length<1e-6, ('actual open socket passage',mate['label'],pin['pin'])
                gap=line.distToShape(shape)[0]
                assert abs(gap-mate['square_cavity_mm']/2)<1e-5, ('actual square cavity on exact native pad axis',mate['label'],pin['pin'],gap)
                minimum_bore_gap=min(minimum_bore_gap,gap)
            sockets.append(dict(label=mate['label'],board=mate['board'],reference=mate['pcb_reference'],
                                pin_count=len(pins),measured_axis_to_housing_mm=minimum_bore_gap))
        route_features=physical_features(routes)
        assert len(route_features)==258,'258 actual native planning routes'
        route_rows=[]
        for row in package['wires']:
            obj=route_features[row['id']]
            assert obj.Shape.isValid() and obj.Shape.Volume==0,'nonphysical planning route annotation'
            measured=obj.Shape.Length
            assert abs(measured-row['nominal_centerline_length_mm'])<=.00051,'native route length matches logical planning path'
            route_rows.append(dict(id=row['id'],native_length_mm=measured))
        return dict(contract=package_path.relative_to(ROOT).as_posix(),contract_canonical_sha256=canonical(package_path),
                    native=package['native'],native_sha256=digest(ROOT/package['native']),
                    step=package['step'],step_sha256=digest(ROOT/package['step']),
                    routing_native=package['routing_native'],routing_native_sha256=digest(ROOT/package['routing_native']),
                    reference_native_sha256=digest(ROOT/reference['native']),
                    final_objects=len(features),parts=[dict(label=k,category='mating_interface',**shape_metrics(v.Shape)) for k,v in features.items()],
                    step_comparison=comparison,interference=interference,clearances=[],sockets=sockets,routes=route_rows,
                    physical_qualification=False)
    finally:
        for doc in (routes,chassis,native):
            App.closeDocument(doc.Name)


def main():
    global RESUME_CHECKPOINTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', default='cad/stage5/assembly-contract.json')
    parser.add_argument('--package', choices=['reference', 'future', 'harness', 'all'], default='all')
    parser.add_argument('--write-receipt', action='store_true')
    parser.add_argument('--resume',action='store_true',help='Reuse only completed local phases with identical inspector and frozen input bindings')
    arguments = parser.parse_args()
    RESUME_CHECKPOINTS=arguments.resume
    contract_path = ROOT / arguments.contract
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    names = ['reference', 'future', 'harness'] if arguments.package == 'all' else [arguments.package]
    report = dict(schema='scci_rh.stage5.independent-native-inspection.v1',
                  scope='Nominal digital geometry; no fabrication, anatomy, hermetic or thermal qualification',
                  FreeCAD_version=list(App.Version()), inspector_sha256_lf=digest(Path(__file__), True),
                  packages={name: inspect_harness(contract) if name=='harness' else inspect_package(contract, name) for name in names}, passed=True)
    if arguments.write_receipt:
        destination = ROOT / ('provenance/stage5-native-' + arguments.package + '.json')
        destination.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
