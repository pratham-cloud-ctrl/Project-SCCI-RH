"""Read-only native/STEP inspection. Run with the installed FreeCAD Python.

Checks every nominal pair except the explicitly intentional header/interface
reservation. Writes a receipt only with --write-receipt; never edits the CAD.
"""
from pathlib import Path
from itertools import combinations
import argparse
import hashlib
import json
import FreeCAD as App
import Import
from artifact_hashes import canonical_json_digest

ROOT=Path(__file__).resolve().parents[1]
CAD=ROOT/'cad/stage2'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def features(doc):
    return [o for o in doc.Objects if o.TypeId=='Part::Feature' and not o.Shape.isNull()]


def inspect():
    native=App.openDocument(str(CAD/'SCCI_RH_stage2_allocation.FCStd'))
    step=App.newDocument('SCCI_RH_Stage2_Inspection')
    try:
        Import.insert(str(CAD/'SCCI_RH_stage2_allocation.step'),step.Name)
        native_parts=features(native);step_parts=features(step)
        by_name={o.Label:o for o in native_parts}
        expected=json.loads((CAD/'allocation-checks.json').read_text())
        assert len(by_name)==len(native_parts)==len(step_parts)==80
        assert set(by_name)=={r['name'] for r in expected['parts']}
        assert all(o.Shape.isValid() and len(o.Shape.Solids)==1 and o.Shape.Volume>0 for o in native_parts+step_parts)
        for row in expected['parts']:
            obj=by_name[row['name']]
            assert abs(obj.Shape.Volume-row['volume_mm3'])<1e-4
            bb=obj.Shape.BoundBox
            assert max(abs(x-y) for x,y in zip([bb.XMin,bb.YMin,bb.ZMin],row['bbox_min_mm']))<1e-6
            assert max(abs(x-y) for x,y in zip([bb.XMax,bb.YMax,bb.ZMax],row['bbox_max_mm']))<1e-6
        assert abs(sum(o.Shape.Volume for o in native_parts)-sum(o.Shape.Volume for o in step_parts))<1e-4
        checked=skipped=exact=0
        for a,b in combinations(native_parts,2):
            if (a.Label=='Dielectric_Header_Allocation' and b.Label.startswith(('Interface_Port_','Unqualified_Insulator_'))
                    or b.Label=='Dielectric_Header_Allocation' and a.Label.startswith(('Interface_Port_','Unqualified_Insulator_'))):
                skipped+=1
                continue
            checked+=1
            aa,bb=a.Shape.BoundBox,b.Shape.BoundBox
            if (min(aa.XMax,bb.XMax)-max(aa.XMin,bb.XMin)>1e-9
                    and min(aa.YMax,bb.YMax)-max(aa.YMin,bb.YMin)>1e-9
                    and min(aa.ZMax,bb.ZMax)-max(aa.ZMin,bb.ZMin)>1e-9):
                exact+=1
                assert a.Shape.common(b.Shape).Volume<1e-6,(a.Label,b.Label)
        assert checked==3088 and skipped==72
        return {'date':'2026-10-08','scope':'Read-only native/STEP validity, dimensions and all nominal pair inspections; no populated/anatomical/hermetic claim',
            'native_sha256':digest(CAD/'SCCI_RH_stage2_allocation.FCStd'),
            'step_sha256':digest(CAD/'SCCI_RH_stage2_allocation.step'),
            'allocation_receipt_canonical_json_sha256':canonical_json_digest(CAD/'allocation-checks.json'),
            'text_receipt_hash_convention':'Parsed JSON; sorted object keys; preserved array order; compact ASCII serialization; finite numbers. Git manifest separately binds exact committed bytes.',
            'FreeCAD_version':list(App.Version()),'native_parts':80,'STEP_parts':80,
            'all_valid_and_positive':True,'recorded_dimensions_and_volumes_match':True,
            'nominal_pairs_checked':checked,'bounding_box_rejections':checked-exact,
            'exact_BRep_intersections_checked':exact,'intentional_header_interface_reservation_pairs':skipped,
            'unexpected_positive_volume_intersections':0,
            'exception':'Header allocation intentionally contains interface extensions. Separate populated-zone reservation is not an occupied part.'}
    finally:
        App.closeDocument(step.Name)
        App.closeDocument(native.Name)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-receipt',action='store_true')
    args=parser.parse_args();receipt=inspect()
    if args.write_receipt:
        (CAD/'inspection-checks.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))
