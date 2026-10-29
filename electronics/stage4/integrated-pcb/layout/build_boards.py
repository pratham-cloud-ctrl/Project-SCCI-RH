"""Create genuine modular KiCad boards from the audited integrated electrical graph.

Run with KiCad's bundled Python (pcbnew), not the research virtual environment.
Placement groups follow the original functional sheets. ICs are anchors; adjacent
signal and decoupling parts are placed around them using their real courtyards.
No source schematic, footprint snapshot, or existing PCB is modified.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import uuid
import xml.etree.ElementTree as ET
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT/'electronics/stage4/integrated-pcb'
LIB = Path(r'E:\project workspace assests\EDA\KiCAD\share\kicad')
NS = uuid.UUID('6258a9c7-3b1e-4ced-a10a-dd7ee4e49a9e')

def mm(n): return pcb.FromMM(float(n))
def v(x,y): return pcb.VECTOR2I(mm(x),mm(y))
def digest(p): return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def natural(s): return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)',s)]
def nref(s):
    m=re.search(r'(\d+)$',s)
    return int(m.group(1)) if m else 0

def source_metadata(system):
    meta={}
    for name, source in system['sources'].items():
        path=ROOT/source['xml']
        if not path.exists(): continue
        for comp in ET.parse(path).getroot().findall('components/comp'):
            sp=comp.find('sheetpath')
            meta[(name,comp.get('ref'))]={'sheet':sp.get('names','/') if sp is not None else '/', 'source_uuid':comp.findtext('tstamps',''), 'source_path':sp.get('tstamps','/') if sp is not None else '/'}
    return meta

def fp_path(comp):
    lib,name=comp['footprint'].split(':',1)
    candidates=[ROOT/'electronics/stage4'/comp['source_package']/(lib+'.pretty')/(name+'.kicad_mod'),PKG/'controller-carrier'/(lib+'.pretty')/(name+'.kicad_mod'),PKG/'integration/scci_rh_integrated.pretty'/(name+'.kicad_mod')]
    for path in candidates:
        if path.exists(): return path
    if (LIB/'footprints'/(lib+'.pretty')/(name+'.kicad_mod')).exists(): return LIB/'footprints'/(lib+'.pretty')/(name+'.kicad_mod')
    raise FileNotFoundError(candidates)

def local_models(fp, boarddir):
    missing=[]
    for model in fp.Models():
        ref=model.m_Filename
        resolved=Path(ref.replace('${KICAD10_3DMODEL_DIR}',str(LIB/'3dmodels')))
        if not resolved.exists():
            missing.append(ref)
            continue
        rel=Path(resolved.parent.name)/resolved.name
        dest=PKG/'boards/models'/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists(): shutil.copy2(resolved,dest)
        model.m_Filename='${KIPRJMOD}/../models/'+rel.as_posix()
    return missing

def courtyard(fp):
    layers=pcb.LSET();layers.AddLayer(pcb.F_CrtYd)
    bb=fp.GetLayerBoundingBox(layers)
    if bb.GetWidth()<mm(.1) or bb.GetHeight()<mm(.1):
        points=[p.GetPosition() for p in fp.Pads()]
        x=[pcb.ToMM(p.x) for p in points];y=[pcb.ToMM(p.y) for p in points]
        return max(x)-min(x)+2,max(y)-min(y)+2
    return pcb.ToMM(bb.GetWidth()),pcb.ToMM(bb.GetHeight())

def text(board,string,x,y,size=1.0,layer=pcb.F_SilkS):
    t=pcb.PCB_TEXT(board);t.SetText(string);t.SetPosition(v(x,y));t.SetLayer(layer)
    t.SetTextSize(v(size,size));t.SetTextThickness(mm(size*.15));t.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_LEFT);board.Add(t)
    return t

def rect(board,x0,y0,x1,y1,layer,width=.1):
    for a,b in [((x0,y0),(x1,y0)),((x1,y0),(x1,y1)),((x1,y1),(x0,y1)),((x0,y1),(x0,y0))]:
        s=pcb.PCB_SHAPE(board);s.SetShape(pcb.SHAPE_T_SEGMENT);s.SetStart(v(*a));s.SetEnd(v(*b));s.SetLayer(layer);s.SetWidth(mm(width));board.Add(s)

def overlaps(a,b,gap=.45):
    return not(a[2]+gap<=b[0] or b[2]+gap<=a[0] or a[3]+gap<=b[1] or b[3]+gap<=a[1])

def cluster(anchor, followers, objects, comps, netdegree):
    """Allocate real-courtyard rectangles near their electrical anchor."""
    fp=objects[anchor];w,h=courtyard(fp)
    placed={anchor:(0.,0.,0.)};boxes=[(-w/2,-h/2,w/2,h/2)]
    anchorpins={p.GetNetname():p.GetPosition() for p in fp.Pads() if p.GetNetname()}
    for ref in sorted(followers,key=lambda r:(not r.startswith('C'), natural(r))):
        part=objects[ref];pw,ph=courtyard(part)
        connected=[anchorpins[n] for n in {p['net'] for p in comps[ref]['pins']} if n in anchorpins and netdegree[n]<12]
        tx=sum(pcb.ToMM(p.x) for p in connected)/len(connected) if connected else 0
        ty=sum(pcb.ToMM(p.y) for p in connected)/len(connected) if connected else 0
        candidates=[]
        # A half-millimetre grid makes independent rectangles deterministic while
        # retaining short connections to the observed matching anchor pins.
        for angle in (0,90):
            cw,ch=(pw,ph) if angle==0 else (ph,pw)
            for radius in range(1,40):
                d=radius*.75
                for x,y in ((-w/2-cw/2-.8, d),(-w/2-cw/2-.8,-d),(w/2+cw/2+.8,d),(w/2+cw/2+.8,-d),(d,-h/2-ch/2-.8),(-d,-h/2-ch/2-.8),(d,h/2+ch/2+.8),(-d,h/2+ch/2+.8)):
                    box=(x-cw/2,y-ch/2,x+cw/2,y+ch/2)
                    if any(overlaps(box,b) for b in boxes):continue
                    cost=(x-tx)**2+(y-ty)**2+.015*abs(x*y)
                    candidates.append((cost,x,y,angle,box))
        if not candidates:raise RuntimeError('Cannot place '+ref)
        _,x,y,angle,box=min(candidates)
        placed[ref]=(x,y,angle);boxes.append(box)
    xmin=min(b[0] for b in boxes);ymin=min(b[1] for b in boxes)
    xmax=max(b[2] for b in boxes);ymax=max(b[3] for b in boxes)
    return {'placements':{r:(x-xmin+1,y-ymin+1,a) for r,(x,y,a) in placed.items()},'width':xmax-xmin+2,'height':ymax-ymin+2}

def pack_rects(items,target_width,gap=2.0):
    x=y=height=0.;out=[];maxx=0.
    for name,w,h in items:
        if x+w>target_width and x>0:y+=height+gap;x=0.;height=0.
        out.append((name,x,y));maxx=max(maxx,x+w);x+=w+gap;height=max(height,h)
    return out,maxx,y+height

def place_sheet(refs,objects,comps,netdegree):
    anchors=[r for r in refs if r.startswith(('U','Q','L','K','Y','BT','F'))]
    headers=[r for r in refs if r.startswith(('J','P','TP'))]
    passive=[r for r in refs if r not in anchors and r not in headers]
    if not anchors:
        anchors=passive[:1];passive=passive[1:]
    groups={r:[] for r in anchors}
    nets={r:{p['net'] for p in comps[r]['pins']} for r in refs}
    for ref in passive:
        # Shared low-degree signal nets outweigh reference-number proximity.
        # Broad power nets have small weight; numerical proximity breaks ties
        # within repeated circuit cells from the original functional sheets.
        def score(a):
            shared=nets[ref]&nets[a]
            return sum(10/(netdegree[n]**1.5) for n in shared)-.0001*abs(nref(comps[ref]['source_ref'])-nref(comps[a]['source_ref']))
        a=max(anchors,key=score);groups[a].append(ref)
    cells={a:cluster(a,groups[a],objects,comps,netdegree) for a in anchors}
    area=sum(c['width']*c['height'] for c in cells.values())
    target=max(35.,math.sqrt(area)*1.35,max((c['width'] for c in cells.values()),default=0))
    packed,w,h=pack_rects([(a,cells[a]['width'],cells[a]['height']) for a in sorted(anchors,key=natural)],target)
    positions={}
    for a,x,y in packed:
        for ref,(px,py,angle) in cells[a]['placements'].items():positions[ref]=(x+px+2,y+py+5,angle)
    headeritems=[]
    for ref in sorted(headers,key=natural):
        fw,fh=courtyard(objects[ref]);angle=90 if fh>fw else 0
        if angle:fw,fh=fh,fw
        headeritems.append((ref,fw+2,fh+2,angle))
    headerpacked,hw,hh=pack_rects([(r,fw,fh) for r,fw,fh,a in headeritems],max(w,target))
    for ref,x,y in headerpacked:
        fw,fh,angle=next((fw,fh,a) for r,fw,fh,a in headeritems if r==ref)
        positions[ref]=(x+fw/2+2,y+h+fh/2+7,angle)
    return {'positions':positions,'width':max(w,hw)+4,'height':h+hh+9}

def project(boardname):
    return {'meta':{'filename':boardname+'.kicad_pro','version':1},'board':{'design_settings':{'rules':{'min_clearance':.15,'min_copper_edge_clearance':.5,'min_hole_clearance':.25,'min_track_width':.15,'min_via_annular_width':.15,'min_via_diameter':.6,'min_through_hole_diameter':.3,'min_silk_clearance':.15,'min_silk_text_height':.7,'min_silk_text_thickness':.1},'rule_severities':{k:'warning' for k in ['missing_courtyard','track_not_centered_on_via','tuning_profile_track_geometries','footprint_filters_mismatch','footprint_type_mismatch']},'drc_exclusions':[]}},'net_settings':{'classes':[{'name':'Default','clearance':.15,'track_width':.2,'via_diameter':.6,'via_drill':.3,'microvia_diameter':.3,'microvia_drill':.1,'diff_pair_width':.2,'diff_pair_gap':.2,'diff_pair_via_gap':.25,'pcb_color':'rgba(0, 0, 0, 0.000)','schematic_color':'rgba(0, 0, 0, 0.000)','wire_width':6,'bus_width':12,'line_style':0}],'netclass_assignments':{},'netclass_patterns':[]}}

def build(name,system,replace_generated=False):
    boarddir=PKG/'boards'/name;boarddir.mkdir(parents=True,exist_ok=True)
    path=boarddir/(name.replace('-','_')+'.kicad_pcb')
    if path.exists() and not replace_generated:
        raise FileExistsError('Refusing to overwrite a reviewed PCB. Use --replace-generated only when deliberately regenerating the initial unrouted placement: '+str(path))
    components=[c for c in system['components'] if c['board']==name]
    comps={c['reference']:c for c in components};meta=source_metadata(system)
    board=pcb.BOARD();board.SetCopperLayerCount(4)
    ds=board.GetDesignSettings();ds.m_MinClearance=mm(.15);ds.m_TrackMinWidth=mm(.15);ds.m_ViasMinSize=mm(.6);ds.m_ViasMinAnnularWidth=mm(.15);ds.m_CopperEdgeClearance=mm(.5);ds.m_HoleClearance=mm(.25)
    nets={}
    for n in sorted({p['net'] for c in components for p in c['pins']}):
        net=pcb.NETINFO_ITEM(board,n,len(nets)+1);board.Add(net);nets[n]=net
    objects={};missingmodels=[];groups=defaultdict(list);netdegree=Counter()
    for c in components:
        ref=c['reference'];source=fp_path(c)
        fp=pcb.FootprintLoad(str(source.parent),source.stem)
        if fp is None:raise RuntimeError('Cannot load '+str(source))
        fp.SetReference(ref);fp.SetValue(c['value']);fp.SetUuid(pcb.KIID(str(uuid.uuid5(NS,name+'/'+ref))))
        fp.SetFPIDAsString(c['footprint']);fp.Reference().SetLayer(pcb.F_Fab);fp.Reference().SetTextSize(v(.65,.65));fp.Reference().SetTextThickness(mm(.1));fp.Value().SetVisible(False)
        if c.get('pcb_path'):
            kiidpath=pcb.KIID_PATH()
            for part in c['pcb_path'].strip('/').split('/'):kiidpath.push_back(pcb.KIID(part))
            fp.SetPath(kiidpath)
        missingmodels.extend((ref,m) for m in local_models(fp,boarddir))
        pinmap={p['number']:p['net'] for p in c['pins']}
        actual={p.GetNumber() for p in fp.Pads()}
        if not set(pinmap)<=actual:raise ValueError((ref,'missing pads',set(pinmap)-actual))
        for pad in fp.Pads():
            if pad.GetNumber() in pinmap:pad.SetNet(nets[pinmap[pad.GetNumber()]])
        board.Add(fp);objects[ref]=fp
        md=meta.get((c['source_package'],c['source_ref']),{})
        sheet=c.get('source_sheet',c.get('sheet_name',md.get('sheet','/interfaces/')))
        groups[sheet].append(ref)
        netdegree.update({p['net'] for p in c['pins']})
    sheets={s:place_sheet(refs,objects,comps,netdegree) for s,refs in groups.items()}
    area=sum(s['width']*s['height'] for s in sheets.values())
    target=max(80,math.sqrt(area)*1.5,max(s['width'] for s in sheets.values()))
    shelf,w,h=pack_rects([(s,sheets[s]['width'],sheets[s]['height']) for s in sorted(sheets)],target,gap=6)
    for sheet,x,y in shelf:
        s=sheets[sheet];ox=x+10;oy=y+15
        title=sheet.strip('/') or 'REFERENCE / CORE INTERFACES'
        text(board,title.upper().replace('_',' '),ox+1,oy+1,.8)
        rect(board,ox,oy-1,ox+s['width'],oy+s['height'],pcb.Dwgs_User,.1)
        for ref,(px,py,angle) in s['positions'].items():
            fp=objects[ref];fp.SetOrientationDegrees(angle)
            ls=pcb.LSET();ls.AddLayer(pcb.F_CrtYd)
            center=fp.GetLayerBoundingBox(ls).GetCenter()
            fp.Move(v(ox+px,oy+py)-center)
    width=math.ceil((w+20)/5)*5;height=math.ceil((h+28)/5)*5
    rect(board,0,0,width,height,pcb.Edge_Cuts,.05)
    for index,(x,y) in enumerate(((4,4),(width-4,4),(4,height-4),(width-4,height-4))):
        fp=pcb.FootprintLoad(str(LIB/'footprints/MountingHole.pretty'),'MountingHole_3.2mm_M3');fp.SetReference('H'+str(index+1));fp.SetPosition(v(x,y));fp.Reference().SetVisible(False);fp.Value().SetVisible(False);fp.SetUuid(pcb.KIID(str(uuid.uuid5(NS,name+'/mount/'+str(index)))));board.Add(fp)
    text(board,'SCCI_RH / '+name.upper().replace('-',' '),9,5,1.2)
    text(board,'DIGITAL REFERENCE  |  ARTIFICIAL LOADS ONLY  |  REV A',9,height-5,.8)
    board.SetFileName(str(path));pcb.SaveBoard(str(path),board)
    pro=path.with_suffix('.kicad_pro');pro.write_text(json.dumps(project(path.stem),indent=2)+'\n')
    libs={}
    for c in components:
        library=c['footprint'].split(':',1)[0]
        directory=fp_path(c).parent
        libs[library]=directory
    (boarddir/'fp-lib-table').write_text('(fp_lib_table (version 7)\n'+''.join('  (lib (name "'+lib+'") (type "KiCad") (uri "'+str(directory).replace('\\','/')+'") (options "") (descr "Exact preserved native source snapshots"))\n' for lib,directory in sorted(libs.items()))+')\n')
    board=pcb.LoadBoard(str(path));dsn=path.with_suffix('.dsn')
    result=pcb.ExportSpecctraDSN(board,str(dsn))
    if not result:raise RuntimeError('DSN export failed '+name)
    info={'schema':'scci_rh.layout.v1','board':name,'pcb':path.relative_to(ROOT).as_posix(),'system_sha256_lf':digest(PKG/'integration/system.json'),'source_components':len(components),'mounting_holes':4,'copper_layers':4,'outline_mm':[width,height],'nets':len(nets),'pads':sum(len(list(fp.Pads())) for fp in board.GetFootprints()),'tracks':len(list(board.GetTracks())),'functional_groups':{s:len(groups[s]) for s in groups},'missing_models':missingmodels,'dsn_export':result,'placements':{r:{'x_mm':pcb.ToMM(fp.GetPosition().x),'y_mm':pcb.ToMM(fp.GetPosition().y),'angle_deg':fp.GetOrientationDegrees()} for r,fp in objects.items()}}
    (boarddir/'placement.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps({k:info[k] for k in ['board','source_components','outline_mm','nets','pads','copper_layers','dsn_export']}),flush=True)
    return info

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--board',action='append');parser.add_argument('--replace-generated',action='store_true',help='Deliberately replace reviewed PCB with initial unrouted placement; all final routing is lost.');args=parser.parse_args()
    system=json.loads((PKG/'integration/system.json').read_text())
    for name in args.board or system['boards']:
        build(name,system,args.replace_generated)
