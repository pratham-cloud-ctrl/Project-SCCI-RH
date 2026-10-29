"""Apply the saved palette and an inspection view in the genuine FreeCAD GUI."""
import FreeCAD as App
import FreeCADGui as Gui
from pathlib import Path
import json
path=Path(r'E:\Project SCCI RH\cad\stage5\reference\SCCI_RH_reference_assembly.FCStd')
doc=next((d for d in App.listDocuments().values() if Path(d.FileName)==path),None)
if doc is None:doc=App.openDocument(str(path))
App.setActiveDocument(doc.Name)
for obj in doc.Objects:
    if 'Construction' in obj.PropertiesList and obj.Construction:
        obj.ViewObject.Visibility=False
    elif 'PartRole' in obj.PropertiesList:
        obj.ViewObject.Visibility=True
        obj.ViewObject.ShapeColor=tuple(obj.DisplayColor)[:3]
        obj.ViewObject.LineColor=(.09,.11,.13)
        obj.ViewObject.DisplayMode='Flat Lines' if obj.PartRole!='populated_board' else 'Flat Lines'
        obj.ViewObject.LineWidth=1.0
        if obj.Label=='Lid':obj.ViewObject.Transparency=72
        if obj.PartRole=='populated_board':
            colors=[]
            for s in obj.Shape.Solids:
                bb=s.BoundBox
                if bb.XLength>70 and bb.YLength>70 and bb.ZLength<2:color=(.04,.36,.18)
                elif bb.ZMin<obj.Placement.Base.z+1.45:color=(.68,.70,.72)
                elif min(bb.XLength,bb.YLength)>1 and bb.ZLength>1.0:color=(.10,.12,.14)
                else:color=(.65,.50,.32)
                colors.extend([color]*len(s.Faces))
            if len(colors)==len(obj.Shape.Faces):obj.ViewObject.DiffuseColor=colors
            if 'PaletteRule' not in obj.PropertiesList:obj.addProperty('App::PropertyString','PaletteRule','Assembly')
            obj.PaletteRule='Derived nominal display palette by solid dimensions; source geometry unchanged'
Gui.activeDocument().activeView().viewAxonometric()
Gui.activeDocument().activeView().fitAll()
Gui.Selection.clearSelection()
doc.recompute()
doc.save()
_result_={'document':doc.Name,'saved':str(path),'final_parts':len([o for o in doc.Objects if 'PartRole' in o.PropertiesList]),'construction_hidden':sum('Construction' in o.PropertiesList and o.Construction and not o.ViewObject.Visibility for o in doc.Objects)}
