"""Read-only native comparison of the delivered combined assembly to sources.

Does not import any generator or trust its measured volumes. The frozen source
subassemblies are independently audited in inspect_stage5_native.py.
"""
from pathlib import Path
import hashlib,json,math
import FreeCAD as App

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'cad/stage5'


def sha(path,text=False):
    data=Path(path).read_bytes()
    return hashlib.sha256(data.replace(b'\r\n',b'\n') if text else data).hexdigest()


def signature(shape):
    b=shape.BoundBox
    cm=sum((s.CenterOfMass*s.Volume for s in shape.Solids),App.Vector())/shape.Volume
    return dict(solids=len(shape.Solids),vertices=len(shape.Vertexes),edges=len(shape.Edges),faces=len(shape.Faces),
                volume=shape.Volume,area=shape.Area,bounds=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],
                centre=[cm.x,cm.y,cm.z])


def main():
    ref=json.loads((HERE/'reference/contract.json').read_text())
    hc=json.loads((HERE/'harness/contract.json').read_text())
    hr=json.loads((HERE/'harness/geometry-receipt.json').read_text())
    native=HERE/'SCCI_RH_stage5_reference_full.FCStd'
    master=App.openDocument(str(native))
    by_label={o.Label:o for o in master.Objects}
    rows=[];residuals=[];maximum_metric=0
    for path,parts in [(ref['native'],ref['parts']),(hc['native'],hr['parts'])]:
        source=App.openDocument(str(ROOT/path))
        for p in parts:
            label=p['label'];obj=by_label[label]
            original=source.getObject(p.get('native_name',label))
            if original is None:original=next(o for o in source.Objects if o.Label==label)
            assert obj.AssemblySourceDocument==path and obj.AssemblySourceObject==original.Name
            a,b=obj.Shape,original.Shape
            assert a.isValid() and a.Volume>0 and b.isValid()
            sa,sb=signature(a),signature(b)
            for key in ('solids','vertices','edges','faces'):assert sa[key]==sb[key],(label,key)
            errors=[abs(sa[k]-sb[k]) for k in ('volume','area')]
            errors += [abs(x-y) for k in ('bounds','centre') for x,y in zip(sa[k],sb[k])]
            assert max(errors)<1e-6,(label,max(errors))
            # Compare actual material vertex coordinates, beyond bounding boxes.
            va=sorted((v.Point.x,v.Point.y,v.Point.z) for v in a.Vertexes)
            vb=sorted((v.Point.x,v.Point.y,v.Point.z) for v in b.Vertexes)
            vertex_error=max((math.dist(x,y) for x,y in zip(va,vb)),default=0)
            assert vertex_error<1e-6,(label,vertex_error)
            maximum_metric=max(maximum_metric,max(errors),vertex_error)
            rows.append(dict(label=label,source_document=path,source_name=original.Name,source_geometry=sb,
                             maximum_metric_error=max(errors),maximum_vertex_error_mm=vertex_error))
        App.closeDocument(source.Name)
    assert len(rows)==260 and len({r['label'] for r in rows})==260
    report=dict(schema='scci_rh.stage5.combined-native-inspection.v1',passed=True,
                native='cad/stage5/SCCI_RH_stage5_reference_full.FCStd',native_sha256=sha(native),
                reference_native_sha256=sha(ROOT/ref['native']),harness_native_sha256=sha(ROOT/hc['native']),
                inspector='scripts/inspect_stage5_combined.py',inspector_sha256_lf=sha(Path(__file__),True),
                physical_objects=260,all_valid=True,source_parts_compared=260,source_geometry_preserved=True,
                maximum_metric_residual=maximum_metric,metric_tolerance=1e-6,parts=rows,
                physical_qualification=False)
    dest=ROOT/'provenance/stage5-combined-native.json'
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Reopenedsavedcombinednative:260sourceparts,allvalid;maximumgeometrymetricerror',maximum_metric)


if __name__=='__main__':main()
