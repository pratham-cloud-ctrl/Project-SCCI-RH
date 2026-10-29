"""Finish observed BT40F escapes with the shared exact-copper obstacle grid."""
import json
import os
from pathlib import Path
import subprocess
import pcbnew as pcb
import copper_grid as grid

PKG=Path(__file__).resolve().parent.parent
PATH=PKG/'boards/controller-carrier/controller_carrier.kicad_pcb'
CLI=Path(r'E:\project workspace assests\EDA\KiCAD\bin\kicad-cli.exe')

if __name__=='__main__':
    grid.NX=1551;grid.NY=1501;grid.GRID=.1;grid.VIA=.5
    report=PATH.parent/'drc.json';log=[]
    env=dict(os.environ,KICAD_CONFIG_HOME=r'E:\Project SCCI RH\tmp\pcb-cli-config')
    for iteration in range(8):
        d=json.loads(report.read_text());missing=d['unconnected_items']
        if not missing:break
        item=missing[0];board=pcb.LoadBoard(str(PATH));items=grid.native_items(board)
        a,b=[items[i['uuid']] for i in item['items']];net=a.GetNetCode();start=grid.endpoint(a,item['items'][0]['pos']);end=grid.endpoint(b,item['items'][1]['pos'])
        if isinstance(a,pcb.PAD) or isinstance(b,pcb.PAD):
            pad=a if isinstance(a,pcb.PAD) else b
            start=(grid.xy(pad.GetPosition()),[0])
            via_ends=[grid.xy(t.GetPosition()) for t in board.GetTracks() if isinstance(t,pcb.PCB_VIA) and t.GetNetCode()==net]
            if via_ends:end=(min(via_ends,key=lambda xy:(xy[0]-start[0][0])**2+(xy[1]-start[0][1])**2),[0,1,2,3])
        blocked,via=grid.obstacles(board,net)
        path,expanded=grid.route(blocked,via,start,end,max_nodes=300000)
        tracks,vias=grid.copper(board,net,path,start,end)
        for via_item in board.GetTracks():
            if isinstance(via_item,pcb.PCB_VIA) and via_item.GetWidth(pcb.F_Cu)==pcb.FromMM(.5):via_item.SetDrill(pcb.FromMM(.2))
        pcb.SaveBoard(str(PATH),board)
        project=PATH.with_suffix('.kicad_pro');settings=json.loads(project.read_text());rules=settings['board']['design_settings']['rules'];rules['min_via_diameter']=.5;rules['min_through_hole_diameter']=.2;rules['min_via_annular_width']=.15;project.write_text(json.dumps(settings,indent=2)+'\n')
        log.append({'iteration':iteration,'net':a.GetNetname(),'start':start,'end':end,'expanded':expanded,'tracks':tracks,'vias':vias})
        print(json.dumps(log[-1]),flush=True)
        subprocess.run([str(CLI),'pcb','drc','--format','json','--schematic-parity','--output',str(report),str(PATH)],env=env,check=True)
    (PATH.parent/'grid-escape-repair.json').write_text(json.dumps({'schema':'scci_rh.carrier-grid-escape.v1','scope':'Actual 0.15 mm traces / 0.6 mm diameter / 0.3 mm drill vias; digital native DRC required. Via filling/capping under LGA pads remains fabrication dependent.','steps':log},indent=2)+'\n')
