"""Bind routed native boards to the final graph and portable model/library files.

This does not invent routing. Every old routed net must map to one and only one
final net. Splits are refused. Track width repairs widen only sub-minimum stubs;
the subsequent native DRC must establish their clearance.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import stat
import pcbnew as pcb
from build_boards import ROOT,PKG,LIB,fp_path,mm,project,digest

STACKUP='''
    (stackup
      (layer "F.SilkS" (type "Top Silk Screen") (color "White"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01))
      (layer "F.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
      (layer "In1.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 2" (type "core") (thickness 1.06) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
      (layer "In2.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
      (layer "B.Cu" (type "copper") (thickness 0.035))
      (layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.01))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
      (copper_finish "ENIG")
      (dielectric_constraints no)
    )'''

def quoted(s):return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'

def finalize(name,system,import_ses=False):
    directory=PKG/'boards'/name
    path=directory/(name.replace('-','_')+'.kicad_pcb')
    components={c['reference']:c for c in system['components'] if c['board']==name}
    board=pcb.LoadBoard(str(path))
    if import_ses:
        if not pcb.ImportSpecctraSES(board,str(path.with_suffix('.ses'))):raise RuntimeError('SES import failed')
        pcb.SaveBoard(str(path),board)
    renames={}
    for fp in board.GetFootprints():
        if fp.GetReference() not in components:continue
        pins={p['number']:p['net'] for p in components[fp.GetReference()]['pins']}
        for pad in fp.Pads():
            if pad.GetNumber() not in pins:continue
            old=pad.GetNetname();new=pins[pad.GetNumber()]
            if old in renames and renames[old]!=new:raise ValueError(('FINAL NET SPLIT',name,old,renames[old],new))
            renames[old]=new
    content=path.read_text(encoding='utf-8')
    for old,new in sorted(renames.items(),key=lambda x:-len(x[0])):
        if old!=new:content=content.replace(quoted(old),quoted(new))
    path.write_text(content,encoding='utf-8')
    board=pcb.LoadBoard(str(path))
    nominal=json.loads((PKG/'package-models/verification.json').read_text())
    nominalmap={Path(m['source_footprint']).stem:m['STEP'] for m in nominal['models']}
    libraries={};models=[];widened=[]
    for fp in board.GetFootprints():
        ref=fp.GetReference()
        if ref.startswith('H'):
            fp.SetFPIDAsString('MountingHole:MountingHole_3.2mm_M3')
            fp.SetAttributes(fp.GetAttributes()|pcb.FP_BOARD_ONLY|pcb.FP_EXCLUDE_FROM_BOM|pcb.FP_EXCLUDE_FROM_POS_FILES)
            source=LIB/'footprints/MountingHole.pretty/MountingHole_3.2mm_M3.kicad_mod'
            lib='MountingHole'
        else:
            c=components[ref];source=fp_path(c);lib=c['footprint'].split(':',1)[0]
            if c.get('dnp',False):fp.SetAttributes(fp.GetAttributes()|pcb.FP_DNP)
            else:fp.SetAttributes(fp.GetAttributes()&~pcb.FP_DNP)
            if c.get('datasheet'):
                field=fp.GetField('Datasheet')
                if field:field.SetText(c['datasheet']);field.SetVisible(False)
            if c.get('pcb_path'):
                keypath=pcb.KIID_PATH()
                for part in c['pcb_path'].strip('/').split('/'):keypath.push_back(pcb.KIID(part))
                fp.SetPath(keypath)
        libdest=PKG/'boards/libraries'/(lib+'.pretty');libdest.mkdir(parents=True,exist_ok=True)
        dest=libdest/source.name
        if dest.exists():dest.chmod(stat.S_IWRITE|stat.S_IREAD)
        shutil.copyfile(source,dest);libraries[lib]=libdest
        if source.stem=='Texas_DRB0008A_VSON8_3x3_P0.65_EP1.5x1.75':
            # TI DRB0008A package drawing: 2.8 mm is the pad-row centre span,
            # not the outside span. Source snapshot used +/-1.1 mm; corrected
            # board-owned land pattern uses +/-1.4 mm (0.6 mm long leads).
            footprint_text=dest.read_text(encoding='utf-8')
            footprint_text=footprint_text.replace('(at -1.1 ', '(at -1.4 ').replace('(at 1.1 ', '(at 1.4 ')
            dest.write_text(footprint_text,encoding='utf-8')
        # The old custom RHD pin-1 silk dot clips its pad. Move the mark to Fab
        # in this new layout-owned library variant; all copper pads stay exact.
        if source.stem.startswith('RHD2216_'):
            src=dest.read_text();src=src.replace('(layer "F.SilkS")','(layer "F.Fab")');dest.write_text(src)
            for item in fp.GraphicalItems():
                if item.GetLayer()==pcb.F_SilkS:item.SetLayer(pcb.F_Fab)
        if source.stem in nominalmap:
            fp.Models().clear()
            model=pcb.FP_3DMODEL();model.m_Filename='${KIPRJMOD}/../../package-models/'+nominalmap[source.stem]
            fp.Add3DModel(model);models.append({'reference':ref,'kind':'declared nominal package','path':model.m_Filename})
        else:
            for model in fp.Models():
                original=model.m_Filename
                resolved=Path(original.replace('${KICAD10_3DMODEL_DIR}',str(LIB/'3dmodels')).replace('${KIPRJMOD}',str(directory)))
                if not resolved.exists():raise FileNotFoundError((ref,original,resolved))
                rel=Path(resolved.parent.name)/resolved.name
                target=PKG/'boards/models'/rel;target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():shutil.copy2(resolved,target)
                model.m_Filename='${KIPRJMOD}/../models/'+rel.as_posix()
                models.append({'reference':ref,'kind':'KiCad library package model','path':model.m_Filename})
    for item in board.GetTracks():
        if not isinstance(item,pcb.PCB_VIA) and item.GetWidth()<mm(.15):
            widened.append({'uuid':item.m_Uuid.AsString(),'old_width_mm':pcb.ToMM(item.GetWidth())})
            item.SetWidth(mm(.15))
    title=board.GetTitleBlock()
    title.SetTitle('Project SCCI RH / '+name.replace('-',' ').title())
    title.SetRevision('A / Digital modular reference')
    title.SetDate('2026-10-15')
    title.SetCompany('Project SCCI RH / Pratham')
    title.SetComment(0,'Artificial electrical loads only; physical and biological qualification remain open')
    # Semantic silkscreen headings come from the actual saved board text; never
    # regenerate placements or routes merely to polish the review entry points.
    labels={'ADC.KICAD SCH':'RAW ADC','INPUTS.KICAD SCH':'ANALOG MONITOR TAPS','REFERENCE.KICAD SCH':'REFERENCE NETWORK','COMPANION.KICAD SCH':'ISOLATED COMPANION','HEALTH.KICAD SCH':'HEALTH OBSERVATIONS','HANDOFF.KICAD SCH':'CHARGE ENDPOINTS','ROOT 2.KICAD SCH':'HOST INTERFACES'}
    for item in board.GetDrawings():
        if isinstance(item,pcb.PCB_TEXT):
            label=item.GetText()
            if label in labels:item.SetText(labels[label])
            elif '.KICAD SCH' in label:item.SetText(label.replace('.KICAD SCH','').replace(' 2',' / CONTINUED').replace(' 3',' / CONTINUED'))
    for fp in board.GetFootprints():
        if fp.GetReference().startswith('J'):
            field=fp.Reference();field.SetLayer(pcb.F_SilkS);field.SetVisible(True);field.SetTextSize(pcb.VECTOR2I(mm(.8),mm(.8)));field.SetTextThickness(mm(.12))
            # Reference is placed just above its courtyard instead of over pads.
            layers=pcb.LSET();layers.AddLayer(pcb.F_CrtYd);box=fp.GetLayerBoundingBox(layers)
            field.SetPosition(pcb.VECTOR2I(box.GetCenter().x,box.GetTop()-mm(.65)))
            field.SetTextAngle(pcb.EDA_ANGLE(0,pcb.DEGREES_T))
    pcb.SaveBoard(str(path),board)
    txt=path.read_text(encoding='utf-8')
    if '(stackup' not in txt:txt=txt.replace('(setup','(setup'+STACKUP,1)
    path.write_text(txt,encoding='utf-8')
    pro=path.with_suffix('.kicad_pro');settings=project(path.stem)
    if name=='controller-carrier':
        rules=settings['board']['design_settings']['rules']
        rules['min_via_diameter']=.5;rules['min_through_hole_diameter']=.2;rules['min_via_annular_width']=.15
    pro.write_text(json.dumps(settings,indent=2)+'\n')
    entries=''.join('  (lib (name "'+lib+'") (type "KiCad") (uri "${KIPRJMOD}/../libraries/'+lib+'.pretty") (options "") (descr "Layout-owned exact source copper; nominal package models separately declared"))\n' for lib in sorted(libraries))
    (directory/'fp-lib-table').write_text('(fp_lib_table (version 7)\n'+entries+')\n')
    board=pcb.LoadBoard(str(path));board.BuildConnectivity();conn=board.GetConnectivity();conn.RecalculateRatsnest()
    tracks=list(board.GetTracks());vias=[t for t in tracks if isinstance(t,pcb.PCB_VIA)]
    result={'schema':'scci_rh.routed-board.v1','board':name,'pcb_sha256_lf':digest(path),'system_sha256_lf':digest(PKG/'integration/system.json'),'electrical_components':len(components),'mounting_holes':4,'pads':sum(len(list(f.Pads())) for f in board.GetFootprints()),'track_segments':len(tracks)-len(vias),'vias':len(vias),'unconnected':conn.GetUnconnectedCount(False),'net_renames':{k:v for k,v in renames.items() if k!=v},'widened_stubs':widened,'models':models,'stackup':'Four copper layers / 1.6 mm nominal FR4 / ENIG; impedance and fabrication tolerances unqualified'}
    (directory/'routing.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['board','electrical_components','track_segments','vias','unconnected']}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',action='append',required=True);p.add_argument('--import-ses',action='store_true');a=p.parse_args()
    system=json.loads((PKG/'integration/system.json').read_text())
    for name in a.board:finalize(name,system,a.import_ses)
