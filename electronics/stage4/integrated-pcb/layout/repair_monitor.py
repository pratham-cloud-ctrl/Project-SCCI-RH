"""Join the two physically separate branches of the newly common CNV net.

The source monitor had two independent CNV inputs. The new carrier intentionally
drives them together; retained autoroutes need one explicit copper connection.
Run with KiCad's Python, then run actual native DRC. Does not repair by net label.
"""
import hashlib
import heapq
import json
import math
from pathlib import Path
import pcbnew as pcb

HERE=Path(__file__).resolve().parent
PKG=HERE.parent
PATH=PKG/'boards/monitoring-cell/monitoring_cell.kicad_pcb'


def main():
    board=pcb.LoadBoard(str(PATH))
    # Existing through vias provide a real layer change without adding tight
    # via pads beside the crowded CNV branch ends on In2.Cu.
    starts=[(21.0350,39.4735),(21.1142,59.7659)]
    def point(xy):return pcb.VECTOR2I(pcb.FromMM(xy[0]),pcb.FromMM(xy[1]))
    candidates=[t for t in board.GetTracks() if t.GetNetname().endswith('__BOTH_CNV')]
    assert candidates,'actual common CNV net'
    net=candidates[0].GetNetCode()
    assert all(t.GetNetCode()==net for t in candidates)
    before=hashlib.sha256(PATH.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    # Discard the first reviewed straight-line candidate: native DRC found
    # other nets crossing it. The final route below uses a clear inner layer.
    for trace in list(board.GetTracks()):
        if trace.m_Uuid.AsString()=='c08d603b-8fe9-4cc5-8b05-c2152c8021e0':board.Remove(trace)
    vias=[t for t in board.GetTracks() if isinstance(t,pcb.PCB_VIA) and t.GetNetCode()==net]
    assert all(any((v.GetPosition()-point(xy)).EuclideanNorm()<2 for v in vias) for xy in starts),'existing CNV through vias'
    layer=pcb.In1_Cu; obstacles=[]
    for trace in board.GetTracks():
        if trace.GetNetCode()==net:continue
        if not isinstance(trace,pcb.PCB_VIA) and trace.GetLayer()!=layer:continue
        a,b=trace.GetStart(),trace.GetEnd()
        width=trace.GetWidth(layer) if isinstance(trace,pcb.PCB_VIA) else trace.GetWidth()
        obstacles.append((pcb.ToMM(a.x),pcb.ToMM(a.y),pcb.ToMM(b.x),pcb.ToMM(b.y),pcb.ToMM(width)/2+.15+.1))
    boxes=[]
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode()==net or not pad.IsOnLayer(layer):continue
            bb=pad.GetBoundingBox();boxes.append((pcb.ToMM(bb.GetLeft())-.25,pcb.ToMM(bb.GetTop())-.25,pcb.ToMM(bb.GetRight())+.25,pcb.ToMM(bb.GetBottom())+.25))
    def free(x,y):
        if any(x0<=x<=x1 and y0<=y<=y1 for x0,y0,x1,y1 in boxes):return False
        for ax,ay,bx,by,radius in obstacles:
            dx,dy=bx-ax,by-ay;den=dx*dx+dy*dy
            t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/den)) if den else 0
            if math.hypot(x-ax-t*dx,y-ay-t*dy)<radius+.025:return False
        return True
    step=.2;ox,oy=starts[0];end=starts[1]
    goal=(round((end[0]-ox)/step),round((end[1]-oy)/step));origin=(0,0)
    def xy(node):return (ox+node[0]*step,oy+node[1]*step)
    queue=[(0.,origin)];cost={origin:0.};prev={};visited=set()
    moves=[(x,y) for x in (-1,0,1) for y in (-1,0,1) if x or y]
    while queue:
        _,node=heapq.heappop(queue)
        if node in visited:continue
        visited.add(node)
        if node==goal:break
        for dx,dy in moves:
            nxt=node[0]+dx,node[1]+dy
            x,y=xy(nxt)
            if not(8<x<35 and 28<y<70):continue
            x0,y0=xy(node)
            if not all(free(x0+(x-x0)*t,y0+(y-y0)*t) for t in (.25,.5,.75,1)):continue
            value=cost[node]+math.hypot(dx,dy)
            if value>=cost.get(nxt,float('inf')):continue
            cost[nxt]=value;prev[nxt]=node
            heapq.heappush(queue,(value+math.hypot(goal[0]-nxt[0],goal[1]-nxt[1]),nxt))
    assert goal in visited,'finite inner-layer route exists'
    route=[goal]
    while route[-1]!=origin:route.append(prev[route[-1]])
    route=list(reversed(route));vertices=[xy(n) for n in route]+[end]
    # Collapse exactly collinear runs, retaining finite corner geometry.
    simplified=[vertices[0]]
    for i in range(1,len(vertices)-1):
        a=vertices[i-1];b=vertices[i];c=vertices[i+1]
        if abs((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))>1e-9:simplified.append(b)
    simplified.append(vertices[-1])
    for a,b in zip(simplified,simplified[1:]):
        if math.dist(a,b)<1e-5:continue
        trace=pcb.PCB_TRACK(board);trace.SetStart(point(a));trace.SetEnd(point(b))
        trace.SetWidth(pcb.FromMM(.2));trace.SetLayer(layer);trace.SetNetCode(net);board.Add(trace)
    pcb.SaveBoard(str(PATH),board)
    board.BuildConnectivity();c=board.GetConnectivity();c.RecalculateRatsnest()
    result=dict(schema='scci_rh.monitor-cnv-join.v1',purpose='Actual copper join of common-CNV branches previously routed separately',
                source_before_sha256_lf=before,source_after_sha256_lf=hashlib.sha256(PATH.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
                added_trace_layer='In1.Cu',added_trace_width_mm=.2,endpoints_mm=starts,vertices_mm=simplified,
                native_unconnected_count=c.GetUnconnectedCount(False),native_DRC_required=True)
    (PATH.parent/'cnv-join.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
