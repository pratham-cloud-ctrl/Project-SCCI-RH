"""Build SCCI_RH's conditional future interface in real native FreeCAD.

Run with the installed FreeCAD Python. No Stage2/Stage4 file is modified.
The compact electronics are allocations, not a repackaging of eight PCBs.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import sys
from itertools import combinations

import FreeCAD as App
import Part
import Mesh
import MeshPart

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from scci_rh_future_features import feature, rounded_box

V = App.Vector
COLORS = {'titanium': (0.53, 0.59, 0.65), 'ceramic': (0.91, 0.88, 0.77),
          'pin': (0.77, 0.72, 0.53), 'record': (0.10, 0.60, 0.66),
          'stim': (0.55, 0.34, 0.76), 'header': (0.27, 0.42, 0.50),
          'glass': (0.42, 0.73, 0.82), 'seam': (0.35, 0.42, 0.49)}


def sha(path):
    data = path.read_bytes()
    if path.suffix.lower() in ('.py', '.json', '.csv', '.md', '.cmd', '.fcmacro'):
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def rb(size, p, r=0):
    return {'kind': 'rounded_box', 'size': list(size), 'position': list(p), 'radius': r}


def tube(r, ri, length, p):
    return {'kind': 'tube_y', 'outer_radius': r, 'inner_radius': ri,
            'length': length, 'position': list(p)}


def bbox(shape):
    bb = shape.BoundBox
    return [bb.XMin, bb.YMin, bb.ZMin], [bb.XMax, bb.YMax, bb.ZMax]


def build():
    source = ROOT/'docs/stage2/system-design.json'
    port_source = ROOT/'docs/stage2/functional-port-map.csv'
    old = json.loads(source.read_text(encoding='utf-8'))['mechanical']
    assert old['can_outer_mm'] == [60, 48, 14]
    assert old['header_mm'] == [60, 10, 14] and old['body_feedthrough_ports'] == 36
    ports = list(csv.DictReader(port_source.open(encoding='utf-8', newline='')))
    assert len(ports) == 36
    doc = App.newDocument('SCCI_RH_Future_Interface')
    doc.Label = 'SCCI_RH | Conditional future spinal interface'
    groups = {}
    for name in ('Housing', 'Feedthroughs', 'Connectors', 'RecordingLead', 'StimulationLead', 'Allocations'):
        groups[name] = doc.addObject('App::DocumentObjectGroup', name)
    objects = []
    interfaces = []

    def add(name, label, spec, group, color, **kwargs):
        obj = feature(doc, name, label, spec, color=color, **kwargs)
        groups[group].addObject(obj); objects.append(obj)
        return obj

    params = doc.addObject('App::FeaturePython', 'DesignParameters')
    params.Label = 'DESIGN BASIS | nominal mm, conditional miniaturization'
    for name, value in [('CanWidth', 60), ('CanDepth', 48), ('CanHeight', 14),
                        ('Wall', 1.2), ('CornerRadius', 5), ('HeaderDepth', 10),
                        ('FeedthroughPitch', 3), ('FeedthroughPinRadius', .15),
                        ('FeedthroughFerruleRadius', .9), ('RecordingLeadWidth', 8),
                        ('StimulationLeadWidth', 10)]:
        params.addProperty('App::PropertyLength', name, 'Nominal interface dimensions')
        setattr(params, name, value)
    params.addProperty('App::PropertyString', 'EditInstructions', 'Design basis')
    params.EditInstructions = ('Summary dimensions. Each physical feature exposes its own complete '
        'Specification JSON and CuttingParts links for editable recompute; regenerate to propagate global changes.')
    params.addProperty('App::PropertyString', 'EvidenceBoundary', 'Design basis')
    params.EvidenceBoundary = ('Miniaturized future electronics and target-specific lead placement are assumptions. '
        'No physical implant, hermeticity, RF, thermal or biological qualification.')

    # Preserve Stage2 port centres. Each ceramic is a separate annulus, never a
    # common conductive block or a merger of recording reference with return.
    feed_bores = []
    pin_objects = []
    socket_objects = []
    conductor_objects = []
    contact_objects = []
    port_rows = []
    for idx, row in enumerate(ports):
        pid = row['port_id']; col = idx % 18; bank = idx//18
        x = 4.5+3*col; z = 5+4*bank
        # The inner rounded corner extends forward of the flat rear wall.
        # Extend the four end ferrules/sleeves through that complete shoulder;
        # a flat-wall-only bore leaves the pin just0.216 mm from uncut metal.
        sleeve_front = 46.0 if col in (0, 17) else 46.8
        sleeve_length = 48-sleeve_front
        feed_bores.append(tube(.9, 0, sleeve_length+.2, (x, sleeve_front-.1, z)))
        ferrule = add(pid+'_Ferrule', f'{pid} | Ti ferrule | {row["logical_function"]}',
                      tube(.9, .7, sleeve_length, (x, sleeve_front, z)), 'Feedthroughs', COLORS['titanium'],
                      role='Conditional welded ferrule', port_id=pid, material='Titanium proposal')
        ceramic = add(pid+'_Ceramic', f'{pid} | isolated ceramic sleeve',
                      tube(.7, .15, sleeve_length, (x, sleeve_front, z)), 'Feedthroughs', COLORS['ceramic'],
                      role='Nominal ceramic-to-pin and ceramic-to-ferrule interfaces', port_id=pid,
                      material='Alumina proposal; braze chemistry/CTE process unresolved')
        pin = add(pid+'_Pin', f'{pid} | {row["logical_function"]} feedthrough pin',
                  tube(.15, 0, 13.2, (x, 46.3, z)), 'Feedthroughs', COLORS['pin'],
                  role=row['electrical_role'], port_id=pid, material='Platinum/iridium proposal')
        socket = add(pid+'_Socket', f'{pid} | nominal mating socket',
                     {'kind': 'socket', 'position': [x, 58.2, z], 'outer_radius': .28,
                      'inner_radius': .15, 'length': 2.8, 'end_wall': .2},
                     'Connectors', COLORS['pin'], role='Nominal zero-gap electrical contact; spring/force design unresolved',
                     port_id=pid, material='Platinum/iridium proposal')
        pin_objects.append(pin); socket_objects.append(socket)
        interfaces += [{'a': pin.Name, 'b': ceramic.Name, 'kind': 'nominal ceramic/pin seal surface', 'nominal_gap_mm': 0},
                       {'a': ceramic.Name, 'b': ferrule.Name, 'kind': 'nominal ceramic/ferrule seal surface', 'nominal_gap_mm': 0},
                       {'a': pin.Name, 'b': socket.Name, 'kind': 'nominal mating contact surface; no interference fit', 'nominal_gap_mm': 0}]
        # Split the 18 conductors into monotone, non-crossing left/right fanouts.
        # Right-hand rows reverse order so conductors remain disjoint in one plane.
        cx = 12 if bank == 0 else 48
        cable_pitch = 6/17 if bank == 0 else .45
        wx = cx+(col-8.5)*cable_pitch
        contact_offset = 3 if bank == 0 else 4.5
        contact_x = cx-contact_offset if col < 9 else cx+contact_offset
        rr = col if col < 9 else 17-col
        contact_y = (162+3.5*rr) if bank == 0 else (163+4.6*rr)
        contact_z = 5.3 if bank == 0 else 9.5
        points = [[x, 61, z], [x, 68, z], [wx, 94, z], [wx, 158, z],
                  [contact_x, contact_y, z], [contact_x, contact_y, contact_z]]
        conductor = add(pid+'_Conductor', f'{pid} | continuous illustrative lead conductor',
                        {'kind': 'wire', 'points': points, 'radius': .035},
                        'RecordingLead' if bank == 0 else 'StimulationLead', COLORS['pin'],
                        role='75-ish micrometre nominal routed conductor; not fatigue/electrical qualification',
                        port_id=pid, material='Nominal 70 micrometre Pt/Ir wire allocation')
        contact_size = 2 if bank == 0 else 3
        contact = add(pid+'_Contact', f'{pid} | distal {row["logical_function"]}',
                      rb((contact_size, contact_size, .2),
                         (contact_x-contact_size/2, contact_y-contact_size/2, contact_z), .35),
                      'RecordingLead' if bank == 0 else 'StimulationLead',
                      COLORS['pin'] if idx in (16, 17, 34, 35) else COLORS['record' if bank == 0 else 'stim'],
                      role=row['electrical_role'], port_id=pid, material='Platinum/iridium contact proposal')
        conductor_objects.append(conductor); contact_objects.append(contact)
        interfaces += [{'a': socket.Name, 'b': conductor.Name, 'kind': 'nominal metal termination at y61', 'nominal_gap_mm': 0},
                       {'a': conductor.Name, 'b': contact.Name, 'kind': 'nominal conductor/contact termination', 'nominal_gap_mm': 0}]
        port_rows.append({'port_id': pid, 'logical_function': row['logical_function'],
                          'electrical_role': row['electrical_role'], 'pin_object': pin.Name,
                          'ceramic_object': ceramic.Name, 'ferrule_object': ferrule.Name,
                          'socket_object': socket.Name, 'conductor_object': conductor.Name,
                          'contact_object': contact.Name, 'feedthrough_center_mm': [x, 47.4, z],
                          'feedthrough_datum_note': 'Preserved Stage2 axis datum; not the extended ferrule centroid',
                          'sleeve_front_y_mm': sleeve_front, 'sleeve_length_mm': sleeve_length,
                          'contact_center_mm': [contact_x, contact_y, contact_z+.2],
                          'anatomical_assignment': 'Unassigned; separate target-specific recording/stimulation geometry'})

    can_spec = rb((60, 48, 12.6), (0, 0, 0), 5)
    can_spec['cuts'] = [rb((57.6, 45.6, 20), (1.2, 1.2, 1.2), 3.8), *feed_bores]
    can = add('Can', 'Titanium can | 60 x 48 x 14 envelope', can_spec,
              'Housing', COLORS['titanium'], material='Titanium proposal', role='1.2 mm nominal wall/floor')
    seam_spec = rb((60, 48, .2), (0, 0, 12.6), 5)
    seam_spec['cuts'] = [rb((57.6, 45.6, .4), (1.2, 1.2, 12.5), 3.8)]
    seam = add('Seam', 'Conditional weld seam | no qualified process', seam_spec,
               'Housing', COLORS['seam'], material='Titanium nominal weld allocation')
    window_outer = rb((20.3, 10.3, 1.4), (34.85, 5.85, 12.7), 2.15)
    lid_spec = rb((60, 48, 1.2), (0, 0, 12.8), 5); lid_spec['cuts'] = [window_outer]
    lid = add('Lid', 'Titanium lid | conditional RF window', lid_spec,
              'Housing', COLORS['titanium'], material='Titanium proposal')
    rf_seal_spec = rb((20.3, 10.3, 1.2), (34.85, 5.85, 12.8), 2.15)
    rf_seal_spec['cuts'] = [rb((20, 10, 1.4), (35, 6, 12.7), 2)]
    rf_seal = add('RF_Seal', 'RF window seal ring | nominal unqualified', rf_seal_spec,
                  'Housing', COLORS['seam'], material='Unspecified glass/metal sealing system',
                  role='Nominal 0.15 mm radial seal allocation, process unresolved')
    rf_glass = add('RF_Window', 'Conditional RF glass window | 20 x 10 mm',
                  rb((20, 10, 1.2), (35, 6, 12.8), 2),
                  'Housing', COLORS['glass'], material='RF-transmissive glass proposal',
                  role='Future radio window; current firmware radio remains off')
    interfaces += [{'a': 'Can', 'b': 'Seam', 'kind': 'nominal weld boundary', 'nominal_gap_mm': 0},
                   {'a': 'Seam', 'b': 'Lid', 'kind': 'nominal weld boundary', 'nominal_gap_mm': 0},
                   {'a': 'RF_Window', 'b': 'RF_Seal', 'kind': 'nominal RF seal boundary', 'nominal_gap_mm': 0},
                   {'a': 'RF_Seal', 'b': 'Lid', 'kind': 'nominal RF seal boundary', 'nominal_gap_mm': 0}]

    header_spec = rb((60, 10, 14), (0, 48, 0), 2)
    header_spec['cuts'] = [tube(.16, 0, 10.2, (4.5+3*c, 47.9, 5+4*b)) for b in range(2) for c in range(18)]
    for bank in range(2):
        z = 5+4*bank
        header_spec['cuts'].append(rb((56, 7.1, 3), (2, 51, z-1.5)))
        kx = 2.0 if bank == 0 else 56.4
        header_spec['cuts'].append(rb((1.6, 1.3, .9), (kx, 56.8, z+1.4)))
    header = add('Header', 'Dielectric header | separately keyed R/S ports', header_spec,
                 'Housing', COLORS['header'], material='Implant-grade dielectric header proposal')
    interfaces.append({'a': 'Can', 'b': 'Header', 'kind': 'nominal header/can boundary', 'nominal_gap_mm': 0})

    for bank, title in enumerate(('Record', 'Stim')):
        z = 5+4*bank; co = COLORS['record' if bank == 0 else 'stim']
        current_conductors = conductor_objects[18*bank:18*(bank+1)]
        current_sockets = socket_objects[18*bank:18*(bank+1)]
        insert_spec = rb((55.8, 7, 2.8), (2.1, 51, z-1.4), .2)
        insert_spec['cuts'] = [tube(.16, 0, 7.2, (4.5+3*c, 50.9, z)) for c in range(18)]
        ins = add(title+'_Insert', title+' | dielectric 18-way insert', insert_spec,
                  'Connectors', COLORS['ceramic'], material='Conditional dielectric insert', role='0.1 mm nominal pocket side clearance')
        plug_spec = rb((55.8, 9.8, 2.8), (2.1, 58.2, z-1.4), .2)
        # Clear the complete mating socket envelope, including its empty inner
        # lumen. Cutting only its annular metal would leave trapped plastic pins.
        plug_spec['cuts'] = [tube(.29, 0, 3.0, (4.5+3*c, 58.1, z)) for c in range(18)]
        kx = 2.2 if bank == 0 else 56.6
        plug_spec['boxes_to_fuse'] = [{'size': [1.2, 3.8, .7], 'position': [kx, 57.2, z+1.4]}]
        plug = add(title+'_Plug', title+' | removable keyed lead plug', plug_spec,
                   'Connectors', co, dependencies=[*current_sockets, *current_conductors],
                   material='Conditional dielectric plug', role='Distinct left/right mechanical key; spring retention/sealing unresolved')
        width = 8 if bank == 0 else 10; center = 12 if bank == 0 else 48
        boot_spec = {'kind': 'loft', 'sections': [[30, 68, z, 55.8, 2.8],
                                                               [center, 94, z, width, .6 if bank == 0 else 1.0]]}
        boot = add(title+'_Boot', title+' | tapered strain-relief boot', boot_spec,
                   'RecordingLead' if bank == 0 else 'StimulationLead', co,
                   dependencies=current_conductors, material='Silicone proposal',
                   role='26 mm nominal strain-relief taper; no fatigue/strain qualification')
        sub = rb((width, 66, .6 if bank == 0 else 1.0), (center-width/2, 94, z-(.3 if bank == 0 else .5)), .5)
        # A full-width junction maintains material continuity into the wider paddle.
        paddle = rb((12, 34, .6), (6, 160, 4.7), 2) if bank == 0 else rb((14, 44, 1), (41, 160, 8.5), 2)
        # Simple box union is deliberate: no unvalidated flexural lattice or tissue model.
        sub['boxes_to_fuse'] = [{'size': [width-1, 2, .6 if bank == 0 else 1],
                                'position': [center-(width-1)/2, 159, z-(.3 if bank == 0 else .5)]}]
        # Separate editable paddle is fused into the lead using a native linked shape.
        substrate_main = add(title+'_CableBase', title+' | cable construction', sub,
                             'RecordingLead' if bank == 0 else 'StimulationLead', co,
                             category='construction', material='Silicone proposal')
        paddle_base = add(title+'_PaddleBase', title+' | paddle construction', paddle,
                          'RecordingLead' if bank == 0 else 'StimulationLead', co,
                          category='construction', material='Silicone proposal')
        doc.recompute()
        # Generic rounded geometry with fused boxes is insufficient to preserve the
        # circular paddle corners; this feature uses a native fuse and native cut.
        fused = doc.addObject('Part::Fuse', title+'_SubstrateFuse')
        fused.Base = substrate_main; fused.Tool = paddle_base
        fused.Refine = True
        groups['RecordingLead' if bank == 0 else 'StimulationLead'].addObject(fused)
        cutters = doc.addObject('Part::Compound', title+'_WireCuts'); cutters.Links = current_conductors
        groups['RecordingLead' if bank == 0 else 'StimulationLead'].addObject(cutters)
        substrate = doc.addObject('Part::Cut', title+'_Substrate')
        substrate.Base = fused; substrate.Tool = cutters; substrate.Refine = True
        substrate.Label = title+' | insulated cable and surface paddle'
        for prop, value in [('Category', 'physical'), ('Role', 'Separate illustrative target-specific lead; anatomy unassigned'),
                            ('PortID', ''), ('MaterialProposal', 'Silicone proposal')]:
            substrate.addProperty('App::PropertyString', prop, 'SCCI_RH identity'); setattr(substrate, prop, value)
        substrate.addProperty('App::PropertyColor', 'DisplayColor', 'SCCI_RH identity'); substrate.DisplayColor = co
        substrate.addProperty('App::PropertyVector', 'ExplodeOffset', 'SCCI_RH identity'); substrate.ExplodeOffset = V(0, 0, 0)
        groups['RecordingLead' if bank == 0 else 'StimulationLead'].addObject(substrate)
        objects.append(substrate)
        try:
            substrate.ViewObject.ShapeColor = co
            for hidden in (substrate_main, paddle_base, fused, cutters): hidden.Visibility = False
        except Exception: pass
        for contact in contact_objects[18*bank:18*(bank+1)]:
            interfaces.append({'a': substrate.Name, 'b': contact.Name, 'kind': 'nominal flush distal contact support', 'nominal_gap_mm': 0})
        interfaces += [{'a': plug.Name, 'b': boot.Name, 'kind': 'nominal plug/boot boundary', 'nominal_gap_mm': 0},
                       {'a': boot.Name, 'b': substrate.Name, 'kind': 'nominal boot/cable boundary', 'nominal_gap_mm': 0}]

    allocations = [
        ('Board_Allocation', 'Future substrate | unpopulated 50 x 40 mm', rb((50, 40, 1), (5, 4, 1.8)), (.10, .36, .28)),
        ('Component_Allocation', 'Miniaturized components | conditional volume', rb((50, 40, 3), (5, 4, 2.8)), (.25, .55, .43)),
        ('HV_Bank_Allocation', 'HV bank | effective capacitance unresolved', rb((24, 14, 3), (7, 29, 2.8)), (.23, .43, .64)),
        ('Battery_Allocation', 'Contego 200 bounding box | isolated case-negative', rb((35.1, 17, 5.5), (12, 10, 6.3)), (.80, .59, .26)),
        ('Battery_Insulation_Allocation', '0.15 mm insulation | nominal bounding shell', rb((35.4, 17.3, 5.8), (11.85, 9.85, 6.15)), (.85, .77, .55)),
        ('Antenna_Allocation', 'Future antenna | RF unimplemented', rb((20, 10, .5), (35, 6, 12.1), 2), (.30, .66, .75))]
    for name, label, spec, color in allocations:
        if name == 'Battery_Insulation_Allocation':
            spec['cuts'] = [rb((35.1, 17, 5.5), (12, 10, 6.3))]
        obj = add(name, label, spec, 'Allocations', color, category='allocation', role='Reservation only; excluded from occupied-part collision claims')
        try: obj.ViewObject.Transparency = 72
        except Exception: pass

    # Native GUI preserves color/visibility through explicit properties even when
    # generated with headless FreeCAD Python.
    doc.recompute()
    physical = [o for o in objects if o.Category == 'physical']
    allocation_parts = [o for o in objects if o.Category == 'allocation']
    for obj in objects:
        assert not obj.Shape.isNull(), obj.Name
        assert obj.Shape.isValid() and obj.Shape.Volume > 0, obj.Name
        assert len(obj.Shape.Solids) == 1, (obj.Name, len(obj.Shape.Solids))
    # Exact BRep pair checks, never a visual-only collision declaration.
    collisions = []
    touching = []
    exact_checks = 0
    for a, b in combinations(physical, 2):
        if not a.Shape.BoundBox.intersect(b.Shape.BoundBox):
            continue
        exact_checks += 1
        common = a.Shape.common(b.Shape)
        volume = common.Volume
        if volume > 1e-6:
            collisions.append({'a': a.Name, 'b': b.Name, 'overlap_mm3': volume})
    if collisions:
        (HERE/'build-collisions.json').write_text(json.dumps(collisions, indent=2)+'\n')
        raise AssertionError(f'{len(collisions)} physical interferences; see build-collisions.json')
    clearance_checks = []
    for port in port_rows:
        pin = doc.getObject(port['pin_object'])
        ferrule = doc.getObject(port['ferrule_object'])
        can_distance, closest, _ = pin.Shape.distToShape(can.Shape)
        ferrule_distance = pin.Shape.distToShape(ferrule.Shape)[0]
        clearance_checks.append({'port_id': port['port_id'], 'pin_to_can_mm': can_distance,
                                 'pin_to_ferrule_mm': ferrule_distance,
                                 'pin_can_closest_points_mm': [[list(a), list(b)] for a, b in closest[:1]]})
        assert can_distance >= .75-1e-7, (port['port_id'], can_distance)
        assert ferrule_distance >= .55-1e-7, (port['port_id'], ferrule_distance)
    native = HERE/'SCCI_RH_future_interface.FCStd'
    doc.recompute(); doc.saveAs(str(native))
    step = HERE/'SCCI_RH_future_interface.step'
    Part.export(physical, str(step))
    # STL is physical material only, not overlapping allocation boxes.
    combined_mesh = Mesh.Mesh()
    mesh_rows = []
    for obj in physical:
        mesh = MeshPart.meshFromShape(Shape=obj.Shape, LinearDeflection=.12,
                                     AngularDeflection=.3, Relative=False)
        combined_mesh.addMesh(mesh)
        mesh_rows.append({'name': obj.Name, 'vertices': [list(v) for v in mesh.Topology[0]],
                          'faces': [list(f) for f in mesh.Topology[1]],
                          'color': list(obj.DisplayColor), 'port_id': obj.PortID})
    combined_mesh.write(str(HERE/'SCCI_RH_future_interface.stl'))
    (HERE/'render-meshes.json').write_text(json.dumps(mesh_rows, separators=(',', ':'))+'\n', encoding='utf-8')
    # Exploded native is a derived inspection view; fitted document is authoritative.
    exploded = App.newDocument('SCCI_RH_Future_Interface_Exploded')
    exploded.Label = 'SCCI_RH | Exploded future concept | assembly view only'
    exploded_transforms = {}
    for obj in physical+allocation_parts:
        out = exploded.addObject('Part::Feature', obj.Name)
        out.Label = obj.Label
        shape = obj.Shape.copy()
        off = V(0, 0, 0)
        if obj.Name in ('Lid', 'RF_Seal', 'RF_Window'): off = V(0, 0, 30)
        elif obj.Name == 'Seam': off = V(0, 0, 15)
        elif obj.Category == 'allocation': off = V(0, 0, 10)
        elif obj.Name == 'Header': off = V(0, 8, 0)
        elif obj.Name.endswith(('_Insert', '_Plug', '_Boot', '_Substrate', '_Conductor', '_Contact', '_Socket')):
            off = V(0, 22, 10 if obj.Name.startswith('Record') or (obj.PortID and int(obj.PortID[1:]) <= 18) else -10)
        shape.translate(off); out.Shape = shape
        exploded_transforms[obj.Name] = list(off)
        out.addProperty('App::PropertyString', 'SourceObject', 'SCCI_RH view'); out.SourceObject = obj.Name
        out.addProperty('App::PropertyVector', 'ExplodeOffset', 'SCCI_RH view'); out.ExplodeOffset = off
        out.addProperty('App::PropertyColor', 'DisplayColor', 'SCCI_RH view'); out.DisplayColor = obj.DisplayColor
        try: out.ViewObject.ShapeColor = tuple(obj.DisplayColor)[:3]
        except Exception: pass
    exploded.recompute(); exploded.saveAs(str(HERE/'SCCI_RH_future_interface_exploded.FCStd'))
    Part.export(exploded.Objects, str(HERE/'SCCI_RH_future_interface_exploded.step'))
    # Confirm exchange geometry survived export/reimport, not just native validity.
    imported = Part.read(str(step))
    expected_volume = sum(o.Shape.Volume for o in physical)
    assert imported.isValid() and len(imported.Solids) == len(physical)
    step_volume_tolerance = max(.01, expected_volume*1e-6)
    assert abs(imported.Volume-expected_volume) < step_volume_tolerance
    parts = []
    for obj in physical+allocation_parts:
        lo, hi = bbox(obj.Shape)
        parts.append({'name': obj.Name, 'label': obj.Label, 'category': obj.Category,
                      'role': obj.Role, 'port_id': obj.PortID, 'material_proposal': obj.MaterialProposal,
                      'color_rgb': list(obj.DisplayColor)[:3],
                      'volume_mm3': obj.Shape.Volume, 'bbox_min_mm': lo, 'bbox_max_mm': hi,
                      'valid': obj.Shape.isValid(), 'solid_count': len(obj.Shape.Solids)})
    artifacts = {'native': native.name, 'step': step.name, 'stl': 'SCCI_RH_future_interface.stl',
                 'exploded_native': 'SCCI_RH_future_interface_exploded.FCStd',
                 'exploded_step': 'SCCI_RH_future_interface_exploded.step'}
    contract = {
        'schema_version': 1, 'date': '2026-10-16',
        'scope': 'Conditional future SCCI package; nominal digital geometry only',
        'coordinate_system': 'mm, right-handed; can origin lower-left-bottom; header +Y; leads shown +Y for inspection, not anatomical routing',
        'parameters': {'can_outer_mm': [60, 48, 14], 'header_outer_mm': [60, 10, 14],
                       'core_envelope_mm': [60, 58, 14], 'wall_mm': 1.2, 'can_corner_radius_mm': 5,
                       'weld_seam_height_mm': .2, 'feedthrough_count': 36,
                       'corner_feedthrough_ports': ['P01', 'P18', 'P19', 'P36'],
                       'corner_sleeve_front_y_mm': 46.0, 'corner_sleeve_length_mm': 2.0,
                       'flat_wall_sleeve_front_y_mm': 46.8, 'flat_wall_sleeve_length_mm': 1.2,
                       'recording_streams': 16, 'shared_reference': 1, 'body_bias': 1,
                       'stimulation_contacts': 16, 'dedicated_returns': 2,
                       'lead_conductor_radius_mm': .035,
                       'recording_paddle_mm': [12, 34, .6], 'stim_paddle_mm': [14, 44, 1.0],
                       'recording_contact_size_mm': [2, 2, .2], 'stimulation_contact_size_mm': [3, 3, .2]},
        'source_hashes': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in (source, port_source, HERE/'build_future_interface.py', HERE/'scci_rh_future_features.py')},
        'hash_policy': 'Text py/json/csv/md/cmd/FCMacro sources use CRLF-to-LF normalization; native/STEP/STL byte-exact SHA256.',
        'artifacts': artifacts, 'artifact_sha256': {v: sha(HERE/v) for v in artifacts.values()},
        'step_included_categories': ['physical'], 'exploded_included_categories': ['physical', 'allocation'],
        'exploded_transforms': exploded_transforms,
        'parts': parts, 'ports': port_rows, 'allowed_intersections': [], 'interface_contacts': interfaces,
        'checks': {'all_native_shapes_valid': True, 'single_solid_physical_parts': len(physical),
                   'physical_pair_count': len(physical)*(len(physical)-1)//2,
                   'broad_phase_candidates_exact_checked': exact_checks,
                   'physical_interferences_over_1e_minus_6_mm3': collisions,
                   'step_reimport_solid_count': len(imported.Solids),
                   'step_reimport_volume_mm3': imported.Volume,
                   'native_physical_volume_mm3': expected_volume,
                   'step_volume_difference_mm3': imported.Volume-expected_volume,
                   'step_volume_tolerance_mm3': step_volume_tolerance,
                   'minimum_pin_to_can_mm': .75, 'minimum_pin_to_ferrule_mm': .55,
                   'actual_feedthrough_clearances': clearance_checks,
                   'same_row_feedthrough_pitch_mm': 3, 'row_spacing_mm': 4,
                   'minimum_distal_contact_edge_gap_mm': 1.5,
                   'lead_diameter_mm': .07, 'wire_join_geometry': 'mitered swept path; not a physical bend-radius model',
                   'minimum_parallel_cable_conductor_gap_mm': .28,
                   'recording_contact_nominal_area_mm2': 4-(4-math.pi)*.35**2,
                   'stimulation_contact_nominal_area_mm2': 9-(4-math.pi)*.35**2},
        'evidence_boundaries': [
            'Eight populated reference PCBs do not fit; compact electronics require independent redesign and miniaturization.',
            'Battery, components, HV bank, insulation and antenna are reservations, excluded from physical interference checks.',
            'No anatomical fit, implantation procedure, recruitment/selectivity or efficacy is established.',
            'Seal, lead, conductor, connector and strain-relief geometry is a nominal proposal, with no material/process/force/fatigue qualification.',
            'The RF window is an explicit future premise; no antenna tuning, wireless charging, radio link or RF enablement in current firmware.',
            'No thermal pass: Stage2 compact-package thermal concerns remain open; this CAD adds no heat-transfer measurement.',
            'Nominal zero-gap mating surfaces are interfaces; tolerance extremes and contact preload remain unresolved.'
        ]}
    for name in ('contract.json', 'geometry-receipt.json'):
        (HERE/name).write_text(json.dumps(contract, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    with (HERE/'parts.csv').open('w', encoding='utf-8', newline='') as f:
        fields = ['name', 'label', 'category', 'role', 'port_id', 'material_proposal', 'volume_mm3', 'valid', 'solid_count']
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(parts)
    with (HERE/'port-map.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(port_rows[0])); writer.writeheader(); writer.writerows(port_rows)
    print(json.dumps({'physical_parts': len(physical), 'allocations': len(allocation_parts),
                      'ports': len(ports), 'exact_pair_checks': exact_checks,
                      'step_solids': len(imported.Solids), 'volume_mm3': imported.Volume}))


if __name__ == '__main__':
    build()
