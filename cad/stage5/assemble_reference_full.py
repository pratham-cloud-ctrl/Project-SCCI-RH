"""Create one inspectable native assembly from the verified native subassemblies.

Copies final objects and their construction dependencies. The detailed native
source documents remain separately editable and source-bound; this combined
document adds no electrically active parts or physical wires.
"""
from pathlib import Path
import hashlib,json
import FreeCAD as App
import Part
import MeshPart

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    ref=json.loads((HERE/'reference/contract.json').read_text())
    hr=json.loads((HERE/'harness/geometry-receipt.json').read_text())
    hc=json.loads((HERE/'harness/contract.json').read_text())
    master=App.newDocument('SCCI_RH_Stage5_Reference_Full')
    sources=[];final=[];copied=[]
    for name,path,rows in [('Reference',ref['native'],ref['parts']),('Mating',hc['native'],hr['parts'])]:
        source=App.openDocument(str(ROOT/path));sources.append(source)
        group=master.addObject('App::DocumentObjectGroup',name)
        for row in rows:
            src=source.getObject(row.get('native_name',row['label']))
            if src is None:src=next(o for o in source.Objects if o.Label==row['label'])
            obj=master.copyObject(src,True)
            assert obj is not None
            group.addObject(obj);final.append(obj)
            obj.addProperty('App::PropertyString','AssemblySourceDocument','AssemblyProvenance');obj.AssemblySourceDocument=path
            obj.addProperty('App::PropertyString','AssemblySourceObject','AssemblyProvenance');obj.AssemblySourceObject=src.Name
            copied.append(dict(label=obj.Label,native_name=obj.Name,source_document=path,source_name=src.Name))
    master.recompute()
    for obj in final:
        assert obj.Shape.isValid() and obj.Shape.Volume>0,obj.Name
    scope=master.addObject('App::FeaturePython','Stage5Scope')
    scope.addProperty('App::PropertyString','Status');scope.Status='True-scale eight-board reference chassis and nominal mating housings; separate route-planning file contains no physical wiring'
    scope.addProperty('App::PropertyString','Miniaturization');scope.Miniaturization='No implant scale transformation. Conditional future interface is a separate native assembly.'
    path=HERE/'SCCI_RH_stage5_reference_full.FCStd';master.saveAs(str(path))
    meshes=[]
    for obj in final:
        if obj.Label not in ('Lid','FrontPanel'):
            meshes.append(MeshPart.meshFromShape(Shape=obj.Shape,LinearDeflection=.25,AngularDeflection=.3,Relative=False))
    import Mesh
    combined=Mesh.Mesh()
    for mesh in meshes:combined.addMesh(mesh)
    combined.write(str(HERE/'SCCI_RH_reference_inspection.stl'))
    # A material-complete STLis a visualization derivative. Touching individual
    # assembly parts are not a unioned, printable single body.
    native_checks=[]
    for row,obj in zip(copied,final):
        source=next(d for d in sources if d.FileName.replace('\\','/').endswith(row['source_document']))
        original=source.getObject(row['source_name']).Shape
        native_checks.append(dict(**row,volume_error_mm3=abs(original.Volume-obj.Shape.Volume),
                                  source_solids=len(original.Solids),combined_solids=len(obj.Shape.Solids),
                                  valid=obj.Shape.isValid()))
        assert native_checks[-1]['volume_error_mm3']<1e-5
        assert len(original.Solids)==len(obj.Shape.Solids)
    receipt=dict(schema='scci_rh.stage5.combined-native.v1',native='cad/stage5/SCCI_RH_stage5_reference_full.FCStd',
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(),part_count=len(final),
                 construction_feature_count=len(master.Objects)-len(final)-3,
                 sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [ref['native'],hc['native']]},
                 parts=native_checks,inspection_stl_scope='Visualization derivative with cover/lid omitted; not a unioned manufacturing solid')
    (HERE/'combined-assembly-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Combinednativeassembly:',len(final),'physicalobjectsandretainedconstructiondependencies.')


if __name__=='__main__':main()
