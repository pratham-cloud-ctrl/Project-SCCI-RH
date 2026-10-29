"""Reimport actual populated STEP solids with FreeCAD's Python runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import FreeCAD
import Part

HERE=Path(__file__).resolve().parent


def verify(name):
    directory=HERE/'exports'/name
    path=directory/'populated.step'
    shape=Part.read(str(path))
    receipt=json.loads((directory/'export-receipt.json').read_text())
    assert shape.isValid() and shape.Volume>0,name
    assert len(shape.Solids)>=receipt['fitted_component_count']+1,(name,'expected board and fitted component solids')
    assert all(s.isValid() and s.Volume>0 for s in shape.Solids),name+' all solids'
    bounds=shape.BoundBox
    result=dict(schema='scci_rh.populated-step-geometry.v1',board=name,
                STEP_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                FreeCAD_version=FreeCAD.Version()[:3],valid=True,solids=len(shape.Solids),
                volume_mm3=shape.Volume,dimensions_mm=[bounds.XLength,bounds.YLength,bounds.ZLength],
                nominal_geometry_only=True,manufacturing_tolerance_or_physical_performance_qualified=False)
    (directory/'geometry-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(name,': valid reimported STEP,',len(shape.Solids),'solids',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--board',action='append',required=True)
    for name in parser.parse_args().board:verify(name)
