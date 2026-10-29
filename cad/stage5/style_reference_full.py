"""Apply native visibility/palette after headless generation, through FreeCAD GUI.

Run using the FreeCAD MCP execute_python tool or supplied FCMacro.
"""
from pathlib import Path
import hashlib,json
import FreeCAD as App
import FreeCADGui as Gui

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def display(doc,physical):
    final=set(physical)
    for obj in doc.Objects:
        if not obj.ViewObject:continue
        if obj.TypeId=='App::DocumentObjectGroup':
            obj.ViewObject.Visibility=True
            continue
        obj.ViewObject.Visibility=obj.Name in final
        if obj.Name not in final:continue
        if 'DisplayColor' in obj.PropertiesList:obj.ViewObject.ShapeColor=tuple(obj.DisplayColor)
        elif 'RenderColour' in obj.PropertiesList:obj.ViewObject.ShapeColor=tuple(obj.RenderColour)
        obj.ViewObject.LineColor=(.12,.17,.2)
        obj.ViewObject.DisplayMode='Flat Lines'
        if obj.Label=='Lid':obj.ViewObject.Transparency=76
        if 'PartRole' in obj.PropertiesList and obj.PartRole=='populated_board':
            colors=[]
            for solid in obj.Shape.Solids:
                bb=solid.BoundBox
                if bb.XLength>70 and bb.YLength>70 and bb.ZLength<2:color=(.04,.36,.18)
                elif bb.ZMin<obj.Placement.Base.z+1.45:color=(.68,.70,.72)
                elif min(bb.XLength,bb.YLength)>1 and bb.ZLength>1:color=(.10,.12,.14)
                else:color=(.65,.50,.32)
                colors.extend([color]*len(solid.Faces))
            if len(colors)==len(obj.Shape.Faces):obj.ViewObject.DiffuseColor=colors
    Gui.activeDocument().activeView().viewAxonometric();Gui.activeDocument().activeView().fitAll()
    doc.recompute();doc.saveAs(doc.FileName)


def main():
    hc=json.loads((HERE/'harness/contract.json').read_text())
    receipt=json.loads((HERE/'harness/geometry-receipt.json').read_text())
    path=ROOT/hc['native']
    doc=next((d for d in App.listDocuments().values() if d.FileName.replace('\\','/')==path.as_posix()),None)
    if doc is None:doc=App.openDocument(str(path))
    App.setActiveDocument(doc.Name)
    display(doc,[r['label'] for r in receipt['parts']])
    App.closeDocument(doc.Name)
    receipt['contract_sha256_lf']=hashlib.sha256((HERE/'harness/contract.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    receipt['sources']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in receipt['sources']}
    (HERE/'harness/geometry-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    # The combined document copied source shapes before this presentation-only
    # operation; shape fidelity is independently rechecked after this save.
    combined=HERE/'SCCI_RH_stage5_reference_full.FCStd'
    doc=App.openDocument(str(combined));App.setActiveDocument(doc.Name)
    labels=[r['native_name'] for r in json.loads((HERE/'combined-assembly-receipt.json').read_text())['parts']]
    display(doc,labels)
    summary=dict(document=doc.Name,path=str(combined),physical_objects=len(labels),
                 visible_physical_objects=sum(bool(doc.getObject(n).ViewObject.Visibility) for n in labels),
                 hidden_construction=sum(1 for o in doc.Objects if o.Name not in labels and o.ViewObject and not o.ViewObject.Visibility))
    (HERE/'combined-display-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    _result_=summary
    return summary


if __name__=='__main__':main()
