"""Editable FreeCAD features for the conditional SCCI_RH interface concept.

All lengths are millimetres. The native file stores the generated BReps. Put this
directory on Python's module path (the supplied launcher does so) for recompute.
This module has no GUI or third-party dependencies beyond FreeCAD/Part.
"""
import json
import FreeCAD as App
import Part

V = App.Vector


def rounded_box(w, d, h, r, p=(0, 0, 0)):
    """Planar rounded rectangle extruded along Z; exact circular corners."""
    x, y, z = p
    if r == 0:
        return Part.makeBox(w, d, h, V(x, y, z))
    assert 0 < r <= min(w, d)/2
    pieces = [Part.makeBox(w-2*r, d, h, V(x+r, y, z)),
              Part.makeBox(w, d-2*r, h, V(x, y+r, z))]
    for a in (x+r, x+w-r):
        for b in (y+r, y+d-r):
            pieces.append(Part.makeCylinder(r, h, V(a, b, z)))
    return pieces[0].multiFuse(pieces[1:]).removeSplitter()


def cylinder_y(r, length, p):
    return Part.makeCylinder(r, length, V(*p), V(0, 1, 0))


def polywire(points, r):
    """A nominal round conductor with mitered sweep joins; not fatigue modelling."""
    pts = [V(*p) for p in points]
    clean = [pts[0]]
    for i in range(1, len(pts)-1):
        a, b = pts[i]-clean[-1], pts[i+1]-pts[i]
        if a.cross(b).Length < 1e-8*a.Length*b.Length and a.dot(b) > 0:
            continue
        clean.append(pts[i])
    pts = clean+[pts[-1]]
    path = Part.Wire(Part.makePolygon(pts).Edges)
    profile = Part.Wire([Part.makeCircle(r, pts[0], pts[1]-pts[0])])
    return path.makePipeShell([profile], True, False, 1).removeSplitter()


def rect_wire(cx, y, cz, width, height):
    pts = [V(cx-width/2, y, cz-height/2), V(cx+width/2, y, cz-height/2),
           V(cx+width/2, y, cz+height/2), V(cx-width/2, y, cz+height/2)]
    return Part.makePolygon(pts+[pts[0]])


def build(spec, dependencies):
    k = spec['kind']
    if k == 'rounded_box':
        shape = rounded_box(*spec['size'], spec.get('radius', 0), spec['position'])
    elif k == 'tube_y':
        shape = cylinder_y(spec['outer_radius'], spec['length'], spec['position'])
        if spec.get('inner_radius', 0):
            p = list(spec['position']); p[1] -= 0.01
            shape = shape.cut(cylinder_y(spec['inner_radius'], spec['length']+0.02, p))
    elif k == 'socket':
        shape = cylinder_y(spec['outer_radius'], spec['length'], spec['position'])
        shape = shape.cut(cylinder_y(spec['inner_radius'], spec['length']-spec['end_wall'], spec['position']))
    elif k == 'wire':
        shape = polywire(spec['points'], spec['radius'])
    elif k == 'loft':
        shape = Part.makeLoft([rect_wire(*s) for s in spec['sections']], True, False)
    elif k == 'compound':
        return Part.makeCompound([o.Shape for o in dependencies])
    else:
        raise ValueError(k)
    for box in spec.get('boxes_to_fuse', []):
        shape = shape.fuse(Part.makeBox(*box['size'], V(*box['position'])))
    for cut in spec.get('cuts', []):
        shape = shape.cut(build(cut, []))
    if dependencies:
        shape = shape.cut(Part.makeCompound([o.Shape for o in dependencies]))
    return shape.removeSplitter()


class ParametricPart:
    """Each feature exposes its complete dimension/point specification in CAD."""
    def __init__(self, obj, spec, dependencies=()):
        obj.addProperty('App::PropertyString', 'Specification', 'SCCI_RH dimensions',
                        'Editable JSON dimensions/points in mm; recompute after changing.')
        obj.addProperty('App::PropertyLinkList', 'CuttingParts', 'SCCI_RH construction',
                        'Exact conductor/socket solids subtracted from this dielectric part.')
        obj.Specification = json.dumps(spec, sort_keys=True)
        obj.CuttingParts = list(dependencies)
        obj.Proxy = self

    def execute(self, obj):
        obj.Shape = build(json.loads(obj.Specification), obj.CuttingParts)

    def dumps(self):
        return None

    def loads(self, state):
        return None


def feature(doc, name, label, spec, dependencies=(), category='physical',
            role='', port_id='', material='', color=(0.6, 0.6, 0.6)):
    obj = doc.addObject('Part::FeaturePython', name)
    obj.Label = label
    ParametricPart(obj, spec, dependencies)
    for prop, value in [('Category', category), ('Role', role), ('PortID', port_id),
                        ('MaterialProposal', material)]:
        obj.addProperty('App::PropertyString', prop, 'SCCI_RH identity')
        setattr(obj, prop, value)
    obj.addProperty('App::PropertyColor', 'DisplayColor', 'SCCI_RH identity')
    obj.DisplayColor = color
    obj.addProperty('App::PropertyVector', 'ExplodeOffset', 'SCCI_RH identity')
    obj.ExplodeOffset = V(0, 0, 0)
    try:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.LineColor = (0.10, 0.13, 0.17)
    except Exception:
        pass
    return obj
