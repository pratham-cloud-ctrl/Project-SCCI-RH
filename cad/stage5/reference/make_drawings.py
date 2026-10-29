"""Create dimensioned vector layout drawings directly from the frozen CAD contract."""
from pathlib import Path
import csv,html,json
HERE=Path(__file__).resolve().parent
C=json.loads((HERE/'contract.json').read_text())
OUT=HERE/'drawings';OUT.mkdir(exist_ok=True)
def t(x,y,s,size=13,color='#263648',weight='normal'):
    return f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" fill="{color}" font-weight="{weight}">{html.escape(str(s))}</text>'
def line(x,y,xx,yy,stroke='#62768a',width=1,dash=''):
    return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{stroke}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>'
def rect(x,y,w,h,fill='none',stroke='#53677b',width=1,dash=''):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>'
def header(title,sub):
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1191" height="842" viewBox="0 0 1191 842"><rect width="1191" height="842" fill="#fff"/><g font-family="Arial, sans-serif">'+t(44,39,'PROJECT SCCI RH / STAGE 5',16,'#087b86','bold')+t(44,69,title,24,'#182c43','bold')+t(44,91,sub,12)
def footer(sheet):
    return rect(35,776,1120,40,'#f2f5f8','#a4b0bc')+t(47,794,'DIGITAL REFERENCE / dimensions in mm / nominal geometry / no manufacturing or physical qualification',12)+t(47,809,'Source: cad/stage5/reference/contract.json and native KiCad mounting datums | '+sheet,11)+'</g></svg>'
def dimh(x1,x2,y,label):
    return line(x1,y,x2,y)+line(x1,y-5,x1,y+5)+line(x2,y-5,x2,y+5)+t((x1+x2)/2-20,y-7,label,12)
def dimv(x,y1,y2,label):
    return line(x,y1,x,y2)+line(x-5,y1,x+5,y1)+line(x-5,y2,x+5,y2)+t(x+7,(y1+y2)/2,label,12)
S=.85;ox=65;oy=125
s=header('Reference chassis / bay and tier layout','True-scale eight-board assembly; 600 × 310 × 240 enclosure, four 50 mm service tiers per bay')
s+=t(65,115,'PLAN / all four tiers overlaid; lid removed',13,'#182c43','bold')
s+=rect(ox,oy,600*S,310*S,'#f4f7fa','#162f47',1.5)
for bay,x0,x1 in [('left',18,330),('right',380,565)]:s+=rect(ox+x0*S,oy+20*S,(x1-x0)*S,270*S,'#e4eaf0','#6b8197')
s+=rect(ox+336*S,oy+20*S,38*S,270*S,'#c6edf0','#238d96',1)
colors=['#235d94','#0d8586','#94632b','#8c5598']
for b in C['boards']:
    x=b['translation_mm'][0];width,depth=b['board_outline_mm'];color=colors[b['tier']]
    s+=rect(ox+x*S,oy+30*S,width*S,depth*S,'none',color,1.5,'7 4' if b['tier'] else '')
s+=dimh(ox,ox+600*S,oy+310*S+18,'600')+dimv(ox+600*S+20,oy,oy+310*S,'310')
s+=t(655,130,'BOARD ORDER / bottom → top',15,'#182c43','bold')
for i,(a,b) in enumerate(zip(['Supervision','Power','Current driver','Contact router'],['Recording front end','Monitoring cell','Monitoring transport','Controller carrier'])):
    s+=t(655,158+i*25,f'T{i}: {a}  |  {b}',13,colors[i])
s+=t(655,280,'Central service spine: X336..374',13)+t(655,303,'Rear corridor: Y296..307',13)+t(655,326,'Right corridor: X571..597',13)
s+=t(655,365,'32 actual board-hole axes / 10 mm standoffs',13)+t(655,388,'3.2 mm board holes / 3.3 mm tray bores',13)+t(655,411,'64 board screws / 8 lid + 4 front screws',13)
fy=468
s+=t(65,fy-13,'FRONT SECTION / front cover removed',13,'#182c43','bold')
s+=rect(ox,fy,600*S,240*S,'#f8fafc','#162f47',1.5)
for x in [15,333,377,568]:s+=rect(ox+(x-3)*S,fy+3*S,6*S,226*S,'#98a7b5','#7e8d9b')
for tier in range(4):
    z=16+tier*50;y=fy+(240-z-2)*S
    for x0,x1 in [(18,330),(380,565)]:s+=rect(ox+x0*S,y,(x1-x0)*S,2*S,'#253b50','#253b50')
for b in C['boards']:
    x=b['translation_mm'][0];z=b['board_bottom_z_mm'];w=b['board_outline_mm'][0]
    s+=rect(ox+x*S,fy+(240-z-1.53)*S,w*S,1.53*S,'#1c7a48','#1c7a48')
    s+=t(ox+x*S+6,fy+(240-z-8)*S,'T'+str(b['tier']),10)
s+=dimv(ox-26,fy,fy+240*S,'240')+dimv(ox+600*S+20,fy+(240-178)*S,fy+(240-128)*S,'50')
s+=t(655,488,'SERVICE',15,'#182c43','bold')
for i,text in enumerate(['Isolate external power before opening.','Remove lid and front cover.','Disconnect + label harness plugs.','Withdraw selected tray toward the front.','Reserve ≥310 mm clear front access.','Do not lift trays with harness attached.']):s+=t(655,516+23*i,text,13)
s+=t(655,681,'Native mechanical features remain editable.',13)+t(655,704,'Source populated board solids remain frozen.',13)
s+=footer('S5-R01 / bay + tier layout')
(OUT/'reference-layout.svg').write_text(s,encoding='utf-8')
rows=[]
for b in C['boards']:
    slug=b['board'].replace('-','_');x0,x1=(18,330) if b['bay']=='left' else (380,565);w=x1-x0;D=270;ss=1.65;xx=70;yy=145
    s=header(b['board'].replace('-',' ').title()+' / dedicated tray mounting','Hole locations are measured from tray front-left; tray 2 mm nominal insulating sheet, board 10 mm above tray')
    s+=rect(xx,yy,w*ss,D*ss,'#edf2f5','#233e55',1.5)+rect(xx,yy+268*ss,w*ss,2*ss,'#d0dbe4','#60798d')
    bx=b['translation_mm'][0]-x0;by=10;bw,bd=b['board_outline_mm'];s+=rect(xx+bx*ss,yy+by*ss,bw*ss,bd*ss,'#d5ece1','#177c4e',1.5)
    s+=dimh(xx,xx+w*ss,yy+D*ss+28,f'{w:g}')+dimv(xx+w*ss+25,yy,yy+D*ss,f'{D:g}')
    for m in [m for m in C['mounts'] if m['board']==b['board']]:
        mx=m['axis_xy_mm'][0]-x0;my=m['axis_xy_mm'][1]-20
        s+=f'<circle cx="{xx+mx*ss}" cy="{yy+my*ss}" r="{1.65*ss}" fill="#fff" stroke="#173c56" stroke-width="1.2"/>'
        s+=line(xx+mx*ss-7,yy+my*ss,xx+mx*ss+7,yy+my*ss,'#136d8a',.7)+line(xx+mx*ss,yy+my*ss-7,xx+mx*ss,yy+my*ss+7,'#136d8a',.7)
        s+=t(xx+mx*ss+7,yy+my*ss-6,m['reference'],11)
        rows.append(dict(board=b['board'],hole=m['reference'],tray_x_mm=mx,tray_y_mm=my,tray_hole_diameter_mm=3.3,board_hole_diameter_mm=3.2,assembly_x_mm=m['axis_xy_mm'][0],assembly_y_mm=m['axis_xy_mm'][1],board_bottom_z_mm=b['board_bottom_z_mm']))
    tx=710;s+=t(tx,148,'MOUNT TABLE / tray datum',15,'#182c43','bold')
    s+=t(tx,180,'Axis',13,'#182c43','bold')+t(tx+80,180,'X',13,'#182c43','bold')+t(tx+160,180,'Y',13,'#182c43','bold')
    for i,r in enumerate(rows[-4:]):s+=t(tx,207+24*i,r['hole'],13)+t(tx+80,207+24*i,f"{r['tray_x_mm']:.2f}",13)+t(tx+160,207+24*i,f"{r['tray_y_mm']:.2f}",13)
    s+=t(tx,332,f'PCB: {bw:g} × {bd:g}',13)+t(tx,357,f"Tier: {b['tier']} / bay: {b['bay']}",13)+t(tx,382,f"PCB bottom datum Z={b['board_bottom_z_mm']:g}",13)
    for i,text in enumerate(['M3 screw nominal shaft Ø2.9','Standoff outer Ø6 / bore Ø3','Board hole extracted from KiCad','No thread or torque qualification','Rear 6 mm stop not a structural test','Origin (0,0): tray front-left corner']):s+=t(tx,425+24*i,text,12)
    s+=footer('S5-R02 / '+b['board']+' mounting')
    (OUT/(b['board']+'-tray.svg')).write_text(s,encoding='utf-8')
with (OUT/'mounting-hole-table.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print('Wrote1assembly layout,8tray mount drawings and32-axis mounting table')
