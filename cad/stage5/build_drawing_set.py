"""Dimensioned digital mechanical review sheets, derived from Stage5 contracts.

Run using the bundled document Python (reportlab). These are review drawings,
not approved fabrication/implant drawings or toleranced manufacturing release.
"""
from pathlib import Path
from collections import Counter
import csv,json,math
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor,Color,white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'drawings';OUT.mkdir(exist_ok=True)
W,H=420*mm,297*mm
INK=HexColor('#142D3C');TEAL=HexColor('#007F80');GREY=HexColor('#647883');PALE=HexColor('#EEF4F6');GOLD=HexColor('#A96013')
pdfmetrics.registerFont(TTFont('Arial',r'C:\Windows\Fonts\arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold',r'C:\Windows\Fonts\arialbd.ttf'))
ref=json.loads((HERE/'reference/contract.json').read_text())
fut=json.loads((HERE/'future-interface/contract.json').read_text())
har=json.loads((HERE/'harness/contract.json').read_text())
prod=json.loads((HERE/'reference/producer-geometry.json').read_text())
ports=list(csv.DictReader((HERE/'harness/body-port-bridge.csv').open(newline='',encoding='utf-8')))
c=canvas.Canvas(str(OUT/'SCCI_RH_Stage5_Mechanical_Review.pdf'),pagesize=(W,H))
c.setTitle('Project SCCI RH - Stage5 mechanical assembly and packaging')
c.setAuthor('Project SCCI RH / Pratham with documented AI assistance')


def text(x,y,s,size=9,bold=False,color=INK):
    c.setFillColor(color);c.setFont('ArialBold' if bold else 'Arial',size);c.drawString(x*mm,y*mm,str(s))


def line(x1,y1,x2,y2,color=INK,width=.6,dash=None):
    c.setStrokeColor(color);c.setLineWidth(width);c.setDash(dash or [])
    c.line(x1*mm,y1*mm,x2*mm,y2*mm);c.setDash([])


def box(x,y,w,h,fill=None,stroke=INK,width=.6,radius=0):
    c.setStrokeColor(stroke);c.setLineWidth(width)
    if fill:c.setFillColor(fill)
    if radius:c.roundRect(x*mm,y*mm,w*mm,h*mm,radius*mm,stroke=1,fill=bool(fill))
    else:c.rect(x*mm,y*mm,w*mm,h*mm,stroke=1,fill=bool(fill))


def wrap(x,y,s,width=100,size=9,leading=4.5,color=INK):
    words=s.split();rows=[];row=''
    for word in words:
        candidate=(row+' '+word).strip()
        if pdfmetrics.stringWidth(candidate,'Arial',size)>width*mm and row:
            rows.append(row);row=word
        else:row=candidate
    if row:rows.append(row)
    for row in rows:text(x,y,row,size,color=color);y-=leading
    return y


def dimension(a,b,offset,label,vertical=False):
    if vertical:
        x1,y1=a;x2,y2=b;x=x1+offset
        line(x1,y1,x+2,y1,GREY,.35);line(x2,y2,x+2,y2,GREY,.35);line(x,y1,x,y2,GREY,.5)
        for y,sgn in [(y1,1),(y2,-1)]:line(x,y,x-1,y+sgn*2,GREY,.5);line(x,y,x+1,y+sgn*2,GREY,.5)
        c.saveState();c.translate((x-2)*mm,(y1+y2)/2*mm);c.rotate(90);c.setFont('Arial',8);c.setFillColor(GREY);c.drawCentredString(0,0,label);c.restoreState()
    else:
        x1,y1=a;x2,y2=b;y=y1+offset
        line(x1,y1,x1,y+2,GREY,.35);line(x2,y2,x2,y+2,GREY,.35);line(x1,y,x2,y,GREY,.5)
        for x,sgn in [(x1,1),(x2,-1)]:line(x,y,x+sgn*2,y+1,GREY,.5);line(x,y,x+sgn*2,y-1,GREY,.5)
        c.setFont('Arial',8);c.setFillColor(GREY);c.drawCentredString((x1+x2)/2*mm,(y+2)*mm,label)


def heading(sheet,title,subtitle):
    c.setFillColor(white);c.rect(0,0,W,H,fill=1,stroke=0)
    text(15,280,'PROJECT SCCI RH',21,True);text(337,282,'MECHANICAL ENGINEERING',8,True,color=TEAL)
    text(337,276,'STAGE 05 / DIGITAL REVIEW',8,color=GREY)
    text(15,264,title,16,True);text(15,256,subtitle,9,color=GREY)
    line(15,250,405,250,TEAL,1)
    line(15,22,405,22,GREY,.5)
    text(15,15,'SCCI_RH-MECH-05  |  Rev A  |  16 OCT 2026  |  Dimensions in mm  |  Nominal review geometry',8,color=GREY)
    text(15,9,'Digital reference + conditional implant concept. No physical, hermetic, anatomical or biological qualification.',7,color=GREY)
    text(378,15,f'{sheet:02} / 06',10,True)


def image(path,x,y,w,h):
    if not path.exists():raise FileNotFoundError(path)
    c.drawImage(ImageReader(str(path)),x*mm,y*mm,w*mm,h*mm,preserveAspectRatio=True,anchor='c',mask='auto')


def finish():c.showPage()


# 1: actual full-size reference layout.
heading(1,'Reference chassis - general arrangement','Eight genuine populated boards; two bays; four removable tiers. Dimensioned review views; written dimensions govern.')
s=.31;x=22;y=139
text(x,241,'PLAN / LID REMOVED',10,True)
box(x,y,600*s,310*s,PALE)
box(x+336*s,y+20*s,38*s,270*s,HexColor('#D6ECE9'),TEAL)
for b in ref['boards']:
    if b['tier']!=3:continue
    tx,ty,tz=b['translation_mm'];bw,bd=b['board_outline_mm']
    box(x+tx*s,y+(ty-bd)*s,bw*s,bd*s,HexColor('#BFDACD'),TEAL)
    text(x+tx*s+2,y+(ty-bd)*s+bd*s/2,b['board'].replace('-',' '),7,True)
for m in [m for m in ref['mounts'] if m['board'] in ['contact-router','controller-carrier']]:
    ax,ay=m['axis_xy_mm'];c.setStrokeColor(INK);c.circle((x+ax*s)*mm,(y+ay*s)*mm,1.6*s*mm)
dimension((x,y),(x+600*s,y),-9,'600')
dimension((x+600*s,y),(x+600*s,y+310*s),9,'310',True)
text(x+104,y+6,'38 clear cable spine',7,color=TEAL)
fx=22;fy=45
text(fx,126,'FRONT SECTION / COVERS OMITTED',10,True)
box(fx,fy,600*s,240*s)
for b in ref['boards']:
    tx,ty,tz=b['translation_mm'];bw,bd=b['board_outline_mm']
    trayx=18 if b['bay']=='left' else 380;trayw=312 if b['bay']=='left' else 185
    box(fx+trayx*s,fy+(tz-12)*s,trayw*s,2*s,HexColor('#DFE7EB'))
    box(fx+tx*s,fy+tz*s,bw*s,1.53*s,TEAL)
    text(fx+tx*s+1,fy+tz*s+3,b['board'].replace('-',' '),6.5)
dimension((fx,fy),(fx,fy+240*s),-8,'240',True)
dimension((fx+600*s,fy+28*s),(fx+600*s,fy+78*s),9,'50 tier pitch',True)
rx=244;ry=235
for title,body in [
    ('Physical allocation','600 W x 310 D x 240 H overall, including feet. The base underside is Z8; feet occupy Z0 to Z8. Every board retains original populated geometry and its four native mounting holes.'),
    ('Mounting datum','PCB bottom Z = 28, 78, 128, 178. Two millimetre trays and 10 mm insulating standoffs. M3 hardware has simplified clearance geometry; threads are not modeled.'),
    ('Rear access','Two passive cable inserts route recording and guarded load lines separately from protected supply, companion and debug cables. No new active panel circuit is implied.'),
    ('Service access','Disconnect power and labelled plugs before removing a tray. Remove front cover and reserve at least 310 mm free space in front. Trays slide toward negative Y.'),
    ('Drawing interpretation','Only the upper tier is shown in plan. The front section identifies all eight boards. Detailed real packages and all source copper are available in native CAD/KiCad.')]:
    text(rx,ry,title.upper(),8.5,True,color=TEAL);ry=wrap(rx,ry-6,body,156,9,4.5)-10
finish()

# 2: exploded/reference assembly and finite tolerances.
heading(2,'Reference assembly - service and fit','Rendered from saved engineering BReps. Exploded positions illustrate assembly order; they are not operating positions.')
image(HERE/'renders/reference_exploded.png',16,47,237,195)
rx=266;ry=239
text(rx,ry,'ASSEMBLY ORDER',10,True,color=TEAL);ry-=8
for i,body in enumerate([
    'Install base, side/rear panels, posts and guide rails. Leave front cover and lid off.',
    'Fasten four insulating standoffs to each tray. Use all 32 original PCB hole axes; fit boards and upper M3 screws.',
    'Install labelled mating housings and branch harness according to electrical net identity. Keep HOST, AFE and companion returns separate.',
    'Slide each populated tray into its assigned bay/tier, then connect labelled harness branches. Add passive rear cable inserts.',
    'Inspect nominal clearances and cable/service space. Fit removable front cover and lid. Physical torque, retention and testing remain future work.'
],1):ry=wrap(rx,ry,f'{i}. {body}',132,8.8,4.3)-5
counts=Counter(r['category'] for r in ref['parts'])
text(rx,ry,'MECHANICAL CONTENT',10,True,color=TEAL);ry-=7
for label,value in [('Actual populated boards',8),('Fitted electronic positions',1296),('Reference mechanical pieces',prod['mechanical_part_count']),('PCB standoffs / mounting axes',32),('Board mounting screws',64),('Internal / external mating housings','78 / 5'),('Passive rear inserts / grommets','2 / 5')]:
    text(rx,ry,label,8);text(388,ry,value,8,True);ry-=5
ry-=7;text(rx,ry,'NOMINAL FIT LIMITS',10,True,color=TEAL);ry-=7
for body in ['PCB hole diameter 3.2 versus screw shaft 2.9 gives 0.15 nominal radial clearance. No thread or preload qualification.',
             'Standoff 10 and underside projection 1.385 leave 8.615 nominal tray clearance before tolerance stack-up.',
             'A 50 tier pitch leaves more than20 of selected populated-board-to-next-tray clearance. Actual per-pair checks bind the saved BReps.',
             'Suggested part-position review tolerance +/-0.25; do not convert these nominal drawings to a fabrication release without process-specific tolerances.']:
    ry=wrap(rx,ry,body,132,8,4)-4
finish()

# 3: future concept dimensions and lead render.
heading(3,'Future implanted interface - nominal package','A separate conditional architecture: 36 functional feedthroughs and two keyed 18-position lead interfaces.')
image(HERE/'renders/future_assembled.png',14,42,248,200)
x=287;y=139;s=1.65
text(x,239,'PACKAGE DATUM / PLAN',9,True)
box(x,y,60*s,48*s,HexColor('#E1E6EB'),INK)
box(x,y+48*s,60*s,10*s,HexColor('#E0EFED'),TEAL)
dimension((x,y),(x+60*s,y),-9,'60')
dimension((x+60*s,y),(x+60*s,y+58*s),8,'58 overall',True)
text(x+4,y+35*s,'Metal can 60 x 48',8,True)
text(x+4,y+51*s,'Header 60 x 10',8,color=TEAL)
text(279,112,'SECTION ENVELOPE',9,True)
box(287,82,60*s,14*s,HexColor('#E1E6EB'))
dimension((287+60*s,82),(287+60*s,82+14*s),8,'14',True)
text(279,70,'1.2 nominal metal wall allocation',8,color=GREY)
wrap(279,59,'Lead and paddle dimensions are geometric hypotheses. Their anatomical placement, recruitment selectivity, current density and chronic material behavior have not been established.',119,8.5,4.3)
text(20,35,'16 recording signals + reference + current-bounded bias  |  16 selectable stimulation contacts + 2 dedicated returns',9,True,color=TEAL)
finish()

# 4: future internal engineering and limitation bridge.
heading(4,'Future package - interfaces and architecture gap','Native cut/fuse dependencies and editable specifications; exported physical parts and internal reservations are identified separately.')
image(HERE/'renders/future_exploded.png',16,43,244,198)
rx=272;ry=238
for title,body in [
    ('Package and seal concept','A metal can/lid, seam allocation, dielectric header and individually isolated feedthroughs define a plausible geometry. Native bores preserve separation between conductive pins and surrounding metal.'),
    ('Lead functions','Recording and stimulation leads are separate keyed 18-contact concepts. Reference and body bias retain distinct identities; body bias is not a stimulation return. Each distal contact has its own mapped conductor.'),
    ('Communication allocation','A conditional dielectric RF window and antenna reservation give the future package an explicitly proposed path through the metal shell. Current firmware implements no radio or network-core image.'),
    ('Electronics redesign required','Eight reference boards cannot fit this can. A new multilayer/custom electronics implementation, integration, battery selection, heat removal, noise recovery and qualified feedthrough technology are prerequisites.'),
    ('Biological premise remains open','Spinal observations must contain useful task information, stimulation must selectively influence relevant circuits, and individualized feedback must remain stable. CAD does not establish expert-to-novice retained learning or physiological efficacy.')]:
    text(rx,ry,title.upper(),8.5,True,color=TEAL);ry=wrap(rx,ry-6,body,126,8.8,4.3)-9
finish()

# 5: complete cross-stage port bridge.
heading(5,'Body port bridge - all 36 functional identities','Maps the preserved Stage 2 names to exact Stage 4 electrical boundaries. Future CAD carries the same port IDs; no anatomy is inferred.')
xs=[17,33,72,124,153,168,241,401]
headers=['Port','Stage 2 function','Reference board','Header','Pin','Native source net','Protection / role']
for i,label in enumerate(headers):text(xs[i],239,label,8,True,color=TEAL)
line(17,235,402,235,TEAL,.8)
ry=230
for i,p in enumerate(ports):
    if i%2==0:box(16,ry-1.5,386,5.3,PALE,PALE)
    role='Recording input / reference / bias' if i<18 else 'After independent output guards'
    vals=[p['port_id'],p['logical_function'],p['board'],p['pcb_reference'],p['pin'],p['source_net'],role]
    for j,value in enumerate(vals):text(xs[j],ry,value,7.8,bold=(j==0))
    ry-=5.3
line(17,ry+2,402,ry+2,GREY,.5)
wrap(17,ry-7,'Zero-based electrical names are deliberate: Stage 2 REC_01 maps to REC00_CONTACT, and STIM_01 maps to BODY_STIM00. P35/P36 map to BODY_RETURN0/BODY_RETURN1 after the guards. Full integrated net names, geometric mate axes and source hashes are retained in body-port-bridge.csv and harness/contract.json.',385,8.5,4.5)
finish()

# 6: review evidence, finite scope and serviceable organization.
heading(6,'Mechanical review - evidence and remaining qualification','Finite digital verification closes this stage; physical and biological claims remain explicitly separate.')
left=20;right=221;ry=238
for title,body in [
    ('Native authority','FreeCAD assemblies preserve the actual eight populated STEP compounds by rigid translation. Separate editable mechanical construction features define the chassis, mounts, housing cavities, package, bores and lead interfaces.'),
    ('Independent verification','A separate inspector reopens saved native/STEP BReps, compares placed solids to original source boards, derives hole axes from native KiCad files and checks material intersections, declared clearances and port identities.'),
    ('Wiring traceability','83 mating housing envelopes correspond to 78 internal and 5 external interfaces. All 258 original wiring rows and 47 branched nodes are preserved. Shared rows do not imply several wires forced into one terminal.'),
    ('Cable planning boundary','The separate route document contains nonphysical unsmoothed centerlines, a 5 mm bend allocation and length estimates with 20 percent service slack plus 30 mm termination allowance. It is not a collision-free packed loom, bend verification or wire cut list.')]:
    text(left,ry,title.upper(),10,True,color=TEAL);ry=wrap(left,ry-7,body,178,10,5)-12
ry=238
for title,body in [
    ('Unqualified mechanical work','No load/preload, material fatigue, environmental ingress, drop, sterilization, hermetic leakage, biocompatibility, RF, thermal or manufacturing process test has been performed.'),
    ('Unqualified electronics work','No assembly, flashing or physical analog measurement is claimed. Native ERC/DRC and target-linked firmware establish digital design artifacts; they do not establish working implanted hardware.'),
    ('Consumer mechanism','The proposed consumer practices a task while a personalized controller estimates relevant spinal state and applies bounded timing assistance; retained learning is assessed with assistance off. Function-specific physiological feedback uses its own selected sensor/pathway/policy.'),
    ('Credit and next stage','AstroSam Mind-Link inspired the progression from a future interface idea to inspectable electronics and a physical design identity. Project SCCI RH contributes its own spinal architecture and mechanisms. Stage 6 integrates the illustrated paper and final private repository release; video and website remain parked.')]:
    text(right,ry,title.upper(),10,True,color=TEAL);ry=wrap(right,ry-7,body,177,10,5)-12
text(20,38,'SOURCE INDEX',8,True,color=TEAL)
text(20,32,'assembly-contract.json  /  reference/contract.json  /  future-interface/contract.json  /  harness/contract.json  /  provenance/stage5-*.json',8,color=GREY)
finish();c.save()
print('Sixdimensionedmechanicalreviewsheetswritten.')
