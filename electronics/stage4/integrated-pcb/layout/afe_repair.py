"""Finite native AFE copper repair. Run with KiCad's bundled Python.

Routes saved DRC missing-connection pairs around native copper obstacles on four
layers. This geometric proposal MUST pass native DRC; no violation is suppressed.
No power plane crosses host/AFE isolation. Preserves the source schematics.

This is an authoring/repair helper, not a deterministic recreation of the complete
routing session. The saved, finalized native PCB and its separately bound full
DRC/parity checks are authoritative. The escape journal is partial because one
successful saved escape preceded a usage interruption before journal append.
A missing-connection report must match the board revision being repaired; never
replay an old report against a finalized board. The default final report contains
no missing connections, so an ordinary run proposes no extra copper.
"""
from __future__ import annotations
import argparse
import hashlib
import heapq
import json
from pathlib import Path
import time
import numpy as np
import pcbnew as pcb

HERE=Path(__file__).resolve().parent
PKG=HERE.parent
PATH=PKG/'boards/recording-front-end/recording_front_end.kicad_pcb'
GRID=.1
LAYERS=[pcb.F_Cu,pcb.In1_Cu,pcb.In2_Cu,pcb.B_Cu]
WIDTH=.15
VIA=.6
CLEAR=.15
MARGIN=.025
NX,NY=1551,1901


def mm(x):return pcb.FromMM(float(x))
def point(x,y):return pcb.VECTOR2I(mm(x),mm(y))
def xy(v):return pcb.ToMM(v.x),pcb.ToMM(v.y)
def digest(path):return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def cell(x,y):return int(round(x/GRID)),int(round(y/GRID))
def mark_rect(a,x0,y0,x1,y1,r=0):
    x0=max(0,int(np.ceil((x0-r)/GRID)));x1=min(NX-1,int(np.floor((x1+r)/GRID)))
    y0=max(0,int(np.ceil((y0-r)/GRID)));y1=min(NY-1,int(np.floor((y1+r)/GRID)))
    a[y0:y1+1,x0:x1+1]=True

def mark_line(a,start,end,r):
    sx,sy=start;ex,ey=end
    x0=max(0,int(np.floor((min(sx,ex)-r)/GRID)));x1=min(NX-1,int(np.ceil((max(sx,ex)+r)/GRID)))
    y0=max(0,int(np.floor((min(sy,ey)-r)/GRID)));y1=min(NY-1,int(np.ceil((max(sy,ey)+r)/GRID)))
    if x1<x0 or y1<y0:return
    yy,xx=np.ogrid[y0:y1+1,x0:x1+1];xx=xx*GRID;yy=yy*GRID
    dx,dy=ex-sx,ey-sy;den=dx*dx+dy*dy
    t=np.clip(((xx-sx)*dx+(yy-sy)*dy)/den,0,1) if den else 0
    distance=(xx-(sx+t*dx))**2+(yy-(sy+t*dy))**2
    a[y0:y1+1,x0:x1+1]|=distance<=r*r


def obstacles(board,net):
    blocked=np.zeros((4,NY,NX),dtype=np.bool_);via=np.zeros((NY,NX),dtype=np.bool_)
    for mask in list(blocked)+[via]:
        mask[:10,:]=True;mask[-10:,:]=True;mask[:,:10]=True;mask[:,-10:]=True
    for f in board.GetFootprints():
        for pad in f.Pads():
            if pad.GetNetCode()==net:continue
            box=pad.GetBoundingBox();x0,y0=xy(box.GetOrigin());x1,y1=xy(box.GetEnd())
            for index,layer in enumerate(LAYERS):
                if pad.IsOnLayer(layer):mark_rect(blocked[index],x0,y0,x1,y1,CLEAR+WIDTH/2+MARGIN)
            mark_rect(via,x0,y0,x1,y1,CLEAR+VIA/2+MARGIN)
    for track in board.GetTracks():
        start=xy(track.GetStart());end=xy(track.GetEnd())
        if isinstance(track,pcb.PCB_VIA):
            # Drilled vias require hole spacing even on the same electrical net.
            mark_line(via,start,start,.3+.25+MARGIN)
            if track.GetNetCode()!=net:
                for mask in blocked:mark_line(mask,start,start,pcb.ToMM(track.GetWidth(pcb.F_Cu))/2+CLEAR+WIDTH/2+MARGIN)
                mark_line(via,start,start,pcb.ToMM(track.GetWidth(pcb.F_Cu))/2+CLEAR+VIA/2+MARGIN)
        elif track.GetNetCode()!=net:
            layer=track.GetLayer()
            if layer in LAYERS:mark_line(blocked[LAYERS.index(layer)],start,end,pcb.ToMM(track.GetWidth())/2+CLEAR+WIDTH/2+MARGIN)
            mark_line(via,start,end,pcb.ToMM(track.GetWidth())/2+CLEAR+VIA/2+MARGIN)
    # Preserve a copper-free isolation corridor between each digital isolator's
    # host-facing and AFE-facing pins. This applies to the new AFE routes only.
    for mask in list(blocked)+[via]:
        mark_rect(mask,100.0,69,105.5,85.5)
        mark_rect(mask,100.0,89.5,105.5,106.5)
    # Existing same-net plated vias already provide a legal layer transition.
    # Reuse them rather than treating their drill-spacing mask as a new-via ban.
    for track in board.GetTracks():
        if isinstance(track,pcb.PCB_VIA) and track.GetNetCode()==net:
            x,y=cell(*xy(track.GetStart()))
            via[y,x]=False
            blocked[:,y,x]=False
    return blocked,via


def native_items(board):
    items={}
    for f in board.GetFootprints():
        for pad in f.Pads():items[pad.m_Uuid.AsString()]=pad
    for track in board.GetTracks():items[track.m_Uuid.AsString()]=track
    return items


def endpoint(item,reported):
    if isinstance(item,pcb.PAD):
        pos=xy(item.GetPosition());layers=[i for i,l in enumerate(LAYERS) if item.IsOnLayer(l)]
    elif isinstance(item,pcb.PCB_VIA):pos=xy(item.GetStart());layers=list(range(4))
    else:
        # DRC's item position is a real endpoint in these saved reports.
        options=[xy(item.GetStart()),xy(item.GetEnd())]
        pos=min(options,key=lambda p:(p[0]-reported['x'])**2+(p[1]-reported['y'])**2)
        layers=[LAYERS.index(item.GetLayer())]
    return pos,layers


def route(blocked,via,start,end,max_nodes=300000):
    (sx,sy),sl=start;(ex,ey),el=end
    ax,ay=cell(sx,sy);bx,by=cell(ex,ey)
    # Endpoints on their own copper are safe; a large obstacle margin may have
    # consumed one sampled cell. Never open a corridor through foreign copper.
    for l in sl:
        if blocked[l,ay,ax]:raise RuntimeError(('blocked start',sx,sy,l))
    for l in el:
        if blocked[l,by,bx]:raise RuntimeError(('blocked end',ex,ey,l))
    target={(l,bx,by) for l in el}
    def heuristic(x,y):
        dx=abs(x-bx);dy=abs(y-by)
        return 1.5*(max(dx,dy)+.41421356237*min(dx,dy))
    heap=[];cost={};prev={}
    for l in sl:
        key=(l,ax,ay);cost[key]=0.;heapq.heappush(heap,(heuristic(ax,ay),0.,key))
    n=0
    moves=[(1,0,1.),(-1,0,1.),(0,1,1.),(0,-1,1.),(1,1,1.41421356237),(1,-1,1.41421356237),(-1,1,1.41421356237),(-1,-1,1.41421356237)]
    while heap:
        _,g,key=heapq.heappop(heap)
        if g!=cost.get(key):continue
        if key in target:
            path=[key]
            while path[-1] in prev:path.append(prev[path[-1]])
            return path[::-1],n
        n+=1
        if n>max_nodes:raise RuntimeError(('route expansion bound',n))
        l,x,y=key
        for dx,dy,c in moves:
            nx=x+dx;ny=y+dy
            if nx<0 or nx>=NX or ny<0 or ny>=NY or blocked[l,ny,nx]:continue
            if dx and dy and (blocked[l,y,nx] or blocked[l,ny,x]):continue
            nk=(l,nx,ny);ng=g+c
            if ng<cost.get(nk,float('inf')):
                cost[nk]=ng;prev[nk]=key;heapq.heappush(heap,(ng+heuristic(nx,ny),ng,nk))
        if not via[y,x]:
            for nl in range(4):
                if nl==l or blocked[nl,y,x]:continue
                nk=(nl,x,y);ng=g+35
                if ng<cost.get(nk,float('inf')):
                    cost[nk]=ng;prev[nk]=key;heapq.heappush(heap,(ng+heuristic(x,y),ng,nk))
    raise RuntimeError(('no geometric route',start,end,n))


def copper(board,net,path,start,end):
    # Compress collinear grid steps, retaining a vertex at every layer change.
    simplified=[path[0]]
    for i in range(1,len(path)-1):
        a,b,c=path[i-1:i+2]
        if a[0]!=b[0] or b[0]!=c[0] or (b[1]-a[1],b[2]-a[2])!=(c[1]-b[1],c[2]-b[2]):simplified.append(b)
    simplified.append(path[-1])
    tracks=0;vias=0
    def segment(a,b,layer):
        nonlocal tracks
        if point(*a)==point(*b):return
        t=pcb.PCB_TRACK(board);t.SetStart(point(*a));t.SetEnd(point(*b));t.SetWidth(mm(WIDTH));t.SetLayer(LAYERS[layer]);t.SetNetCode(net);board.Add(t);tracks+=1
    segment(start[0],(path[0][1]*GRID,path[0][2]*GRID),path[0][0])
    for a,b in zip(simplified,simplified[1:]):
        if a[0]!=b[0]:
            location=(a[1]*GRID,a[2]*GRID)
            existing=[t for t in board.GetTracks() if isinstance(t,pcb.PCB_VIA) and t.GetNetCode()==net
                      and sum((u-v)**2 for u,v in zip(xy(t.GetStart()),location))<=(GRID*.72)**2]
            if not existing:
                v=pcb.PCB_VIA(board);v.SetPosition(point(*location));v.SetWidth(mm(VIA));v.SetDrill(mm(.3));v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNetCode(net);board.Add(v);vias+=1
        else:segment((a[1]*GRID,a[2]*GRID),(b[1]*GRID,b[2]*GRID),a[0])
    segment((path[-1][1]*GRID,path[-1][2]*GRID),end[0],path[-1][0])
    return tracks,vias


def distance_point_segment(p,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1];den=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
    return ((p[0]-a[0]-t*dx)**2+(p[1]-a[1]-t*dy)**2)**.5


def segment_distance(a,b,c,d):
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return 0.
    return min(distance_point_segment(a,c,d),distance_point_segment(b,c,d),
               distance_point_segment(c,a,b),distance_point_segment(d,a,b))


def box_distance(a,b,box):
    x0,y0=xy(box.GetOrigin());x1,y1=xy(box.GetEnd())
    if x0<=a[0]<=x1 and y0<=a[1]<=y1:return 0.
    if x0<=b[0]<=x1 and y0<=b[1]<=y1:return 0.
    corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    return min(segment_distance(a,b,c,d) for c,d in zip(corners,corners[1:]+corners[:1]))


def escape_pad(board,ref,pin):
    fp=next(f for f in board.GetFootprints() if f.GetReference()==ref)
    pad=next(p for p in fp.Pads() if p.GetNumber()==pin)
    origin=xy(pad.GetPosition());center=xy(fp.GetPosition());net=pad.GetNetCode()
    dx=origin[0]-center[0];dy=origin[1]-center[1]
    direction=((1 if dx>0 else -1),0) if abs(dx)>abs(dy) else (0,(1 if dy>0 else -1))
    candidates=[]
    for distance in np.arange(.8,3.61,.1):
        target=(origin[0]+direction[0]*distance,origin[1]+direction[1]*distance)
        removed=[];valid=True
        for f in board.GetFootprints():
            for other in f.Pads():
                if other.GetNetCode()==net:continue
                box=other.GetBoundingBox()
                if other.IsOnLayer(pcb.F_Cu) and box_distance(origin,target,box)<CLEAR+WIDTH/2+.005:valid=False;break
                if box_distance(target,target,box)<CLEAR+VIA/2+.005:valid=False;break
            if not valid:break
        if not valid:continue
        for track in board.GetTracks():
            a=xy(track.GetStart());b=xy(track.GetEnd())
            if isinstance(track,pcb.PCB_VIA):
                separation=distance_point_segment(a,target,target)
                required=.55+.005 if track.GetNetCode()==net else .75+.005
                if separation<required:valid=False;break
                if track.GetNetCode()!=net and distance_point_segment(a,origin,target)<.3+CLEAR+WIDTH/2+.005:valid=False;break
            elif track.GetNetCode()!=net:
                r=pcb.ToMM(track.GetWidth())/2
                if (track.GetLayer()==pcb.F_Cu and segment_distance(origin,target,a,b)<r+CLEAR+WIDTH/2+.005
                    or distance_point_segment(target,a,b)<r+CLEAR+VIA/2+.005):removed.append(track)
        if valid:candidates.append((len(removed),distance,target,removed))
    if not candidates:raise RuntimeError(('no bounded outward escape candidate',ref,pin))
    count,distance,target,removed=min(candidates,key=lambda x:(x[0],x[1]))
    if count>8:raise RuntimeError(('escape exceeds finite rip-up bound',ref,pin,count))
    removed_records=[dict(uuid=t.m_Uuid.AsString(),net=t.GetNetname(),layer=board.GetLayerName(t.GetLayer()),start_mm=xy(t.GetStart()),end_mm=xy(t.GetEnd())) for t in removed]
    for track in removed:board.Remove(track)
    t=pcb.PCB_TRACK(board);t.SetStart(point(*origin));t.SetEnd(point(*target));t.SetWidth(mm(WIDTH));t.SetLayer(pcb.F_Cu);t.SetNetCode(net);board.Add(t)
    v=pcb.PCB_VIA(board);v.SetPosition(point(*target));v.SetWidth(mm(VIA));v.SetDrill(mm(.3));v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNetCode(net);board.Add(v)
    return dict(reference=ref,pin=pin,net=pad.GetNetname(),outward_length_mm=round(float(distance),3),start_mm=origin,via_mm=target,removed_foreign_segments=removed_records)


def cleanup(board,report):
    items=native_items(board);removed={};widened=[];centered=[]
    for violation in report['violations']:
        kind=violation['type'];members=violation['items']
        if kind in ('track_dangling','via_dangling'):
            item=items[members[0]['uuid']]
            removed[item.m_Uuid.AsString()]=dict(kind=kind,net=item.GetNetname(),position_mm=xy(item.GetStart()))
        elif kind=='track_width':
            item=items[members[0]['uuid']];old=pcb.ToMM(item.GetWidth());item.SetWidth(mm(.15));widened.append(dict(uuid=item.m_Uuid.AsString(),old_width_mm=old,new_width_mm=.15))
        elif kind=='track_not_centered_on_via':
            track=next(items[m['uuid']] for m in members if not isinstance(items[m['uuid']],pcb.PCB_VIA))
            via=next(items[m['uuid']] for m in members if isinstance(items[m['uuid']],pcb.PCB_VIA))
            center=via.GetStart();a=track.GetStart();b=track.GetEnd()
            da=(a.x-center.x)**2+(a.y-center.y)**2;db=(b.x-center.x)**2+(b.y-center.y)**2
            old=xy(a if da<db else b)
            if min(da,db)>mm(.1)**2:raise RuntimeError('unexpected off-center distance')
            if da<db:track.SetStart(center)
            else:track.SetEnd(center)
            centered.append(dict(track=track.m_Uuid.AsString(),via=via.m_Uuid.AsString(),old_endpoint_mm=old,new_endpoint_mm=xy(center)))
    for uuid in removed:board.Remove(items[uuid])
    pcb.SaveBoard(str(PATH),board)
    return dict(removed_dangling=list(removed.values()),widened=widened,centered_on_vias=centered,native_DRC_required=True)


def main():
    global GRID,NX,NY
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cleanup',action='store_true');parser.add_argument('--component-ends',action='store_true');parser.add_argument('--escape',action='append');parser.add_argument('--fine',action='store_true');parser.add_argument('--report',type=Path,default=PATH.parent/'drc.json');parser.add_argument('--limit',type=int,default=100);parser.add_argument('--net',action='append');args=parser.parse_args()
    if args.fine:GRID=.05;NX=3101;NY=3801
    board=pcb.LoadBoard(str(PATH));before=digest(PATH)
    backup=PKG.parents[2]/'tmp/afe-routing-before-repair.kicad_pcb'
    backup.parent.mkdir(exist_ok=True)
    if not backup.exists():backup.write_bytes(PATH.read_bytes())
    if args.cleanup:
        result=cleanup(board,json.loads(args.report.read_text()))
        result.update(schema='scci_rh.afe-native-copper-cleanup.v1',before_sha256_lf=before,after_sha256_lf=digest(PATH))
        cleanup_path=PATH.parent/'afe-cleanup.json'
        if cleanup_path.exists():
            previous=json.loads(cleanup_path.read_text())
            result['before_sha256_lf']=previous['before_sha256_lf']
            for name in ('removed_dangling','widened','centered_on_vias'):
                result[name]=previous[name]+result[name]
        cleanup_path.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        return
    if args.escape:
        if len(args.escape)!=1:raise ValueError('one native escape per process; avoids KiCad SWIG ownership reload issue')
        records=[]
        for terminal in args.escape:
            records.append(escape_pad(board,*terminal.split('.')))
            pcb.SaveBoard(str(PATH),board)

        pcb.SaveBoard(str(PATH),board)
        receipt_path=PATH.parent/'afe-escape.json'
        history=json.loads(receipt_path.read_text()).get('escapes',[]) if receipt_path.exists() else []
        receipt_path.write_text(json.dumps(dict(schema='scci_rh.afe-pad-escape.v1',before_sha256_lf=before,after_sha256_lf=digest(PATH),escapes=history+records,native_DRC_required=True),indent=2)+'\n')
        print(json.dumps(records),flush=True)
        return
    report=json.loads(args.report.read_text());items=native_items(board)
    results=[];failed=[]
    pairs=report['unconnected_items'][:args.limit]
    for number,pair in enumerate(pairs):
        a,b=pair['items'];ia,ib=items[a['uuid']],items[b['uuid']]
        net=ia.GetNetCode();name=ia.GetNetname()
        if args.net and not any(name.endswith(n) for n in args.net):continue
        if net!=ib.GetNetCode():raise ValueError('native DRC pair net mismatch')
        start=endpoint(ia,a['pos']);end=endpoint(ib,b['pos'])
        if args.component_ends:
            board.BuildConnectivity();native=board.GetConnectivity();native.RecalculateRatsnest()
            groups=[]
            for source in (ia,ib):
                group=list(native.GetConnectedItems(source))+[source]
                vias=[item for item in group if isinstance(item,pcb.PCB_VIA)]
                groups.append(vias)
            if groups[0] and groups[1]:
                va,vb=min(((va,vb) for va in groups[0] for vb in groups[1]),
                          key=lambda pair:sum((x-y)**2 for x,y in zip(xy(pair[0].GetStart()),xy(pair[1].GetStart()))))
                start=(xy(va.GetStart()),list(range(4)));end=(xy(vb.GetStart()),list(range(4)))
        t=time.perf_counter()
        try:
            blocked,via=obstacles(board,net)
            path,n=route(blocked,via,start,end)
            segments,vias=copper(board,net,path,start,end)
            result=dict(pair=number,net=name,start=start,end=end,segments=segments,vias=vias,expanded=n,elapsed_s=round(time.perf_counter()-t,3))
            results.append(result);print(json.dumps(result),flush=True)
            pcb.SaveBoard(str(PATH),board)
        except RuntimeError as exc:
            result=dict(pair=number,net=name,error=str(exc),elapsed_s=round(time.perf_counter()-t,3));failed.append(result);print(json.dumps(result),flush=True)
    board.BuildConnectivity();conn=board.GetConnectivity();conn.RecalculateRatsnest()
    receipt=dict(schema='scci_rh.afe-native-copper-repair.v1',source_before_sha256_lf=before,source_after_sha256_lf=digest(PATH),grid_mm=GRID,track_width_mm=WIDTH,via_diameter_mm=VIA,via_drill_mm=.3,configured_clearance_mm=CLEAR,geometric_margin_mm=MARGIN,connections=results,failed=failed,native_unconnected_count=conn.GetUnconnectedCount(False),native_DRC_required=True)
    (PATH.parent/'afe-repair.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['native_unconnected_count','source_after_sha256_lf']}),flush=True)


if __name__=='__main__':main()
