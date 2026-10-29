"""Native FreeCAD allocation document and STEP round-trip checks."""
from pathlib import Path
import json
import FreeCAD as App
import Import

HERE=Path(__file__).resolve().parent
doc=App.newDocument('SCCI_RH_Stage2_Allocation')
Import.insert(str(HERE/'SCCI_RH_stage2_allocation.step'),doc.Name)
parts=[obj for obj in doc.Objects if obj.TypeId=='Part::Feature' and hasattr(obj,'Shape') and not obj.Shape.isNull()]
shapes=[s for obj in parts for s in obj.Shape.Solids]
assert len(shapes)==80,(len(parts),len(shapes))
assert all(shape.isValid() and shape.Volume>0 for shape in shapes)
input_checks=json.loads((HERE/'allocation-checks.json').read_text(encoding='utf-8'))
expected=sum(row['volume_mm3'] for row in input_checks['parts'])
actual=sum(shape.Volume for shape in shapes)
assert abs(actual-expected)<1e-4,(actual,expected)
root=doc.addObject('App::FeaturePython','DesignScope')
root.addProperty('App::PropertyString','Status');root.Status='Stage2 allocation; not populated implant, anatomy or hermetic design'
root.addProperty('App::PropertyInteger','BodyPorts');root.BodyPorts=36
root.addProperty('App::PropertyString','ParameterSource');root.ParameterSource='docs/stage2/system-design.json'
root.addProperty('App::PropertyString','Regeneration');root.Regeneration='build_envelope.py (build123d0.13), then assemble_freecad.py (FreeCAD Python)'
doc.recompute();doc.saveAs(str(HERE/'SCCI_RH_stage2_allocation.FCStd'))
App.closeDocument(doc.Name)
reopened=App.openDocument(str(HERE/'SCCI_RH_stage2_allocation.FCStd'))
reopened_parts=[o for o in reopened.Objects if o.TypeId=='Part::Feature' and hasattr(o,'Shape')]
assert sum(len(o.Shape.Solids) for o in reopened_parts)==80
assert all(o.Shape.isValid() for o in reopened_parts)
assert reopened.getObject('DesignScope').BodyPorts==36
report={'date':'2026-10-08','native_document':'cad/stage2/SCCI_RH_stage2_allocation.FCStd',
    'FreeCAD_version':list(App.Version()),'reopened_native_solid_count':80,
    'step_import_solid_count':len(shapes),'all_BRep_valid':True,
    'input_volume_sum_mm3':expected,'roundtrip_volume_sum_mm3':actual,
    'volume_error_mm3':actual-expected,
    'scope':'STEP/native round-trip, not populated-board or anatomical verification'}
(HERE/'freecad-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(report)
App.closeDocument(reopened.Name)
