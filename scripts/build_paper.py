"""Typeset the source-grounded engineering paper and supporting appendix.
No generated biological claims are introduced by this renderer.
"""
from pathlib import Path
import re,html
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Image,Table,TableStyle,Preformatted,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'/'pdf';OUT.mkdir(parents=True,exist_ok=True)
fonts=Path(matplotlib.get_data_path())/'fonts'/'ttf'
for name,file in [('SCCI_RH','DejaVuSans.ttf'),('SCCI_RHBold','DejaVuSans-Bold.ttf'),('SCCI_RHMono','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
pdfmetrics.registerFontFamily('SCCI_RH',normal='SCCI_RH',bold='SCCI_RHBold',italic='SCCI_RH',boldItalic='SCCI_RHBold')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodySCCI_RH',fontName='SCCI_RH',fontSize=9.3,leading=14.7,spaceAfter=7,textColor=colors.HexColor('#24354a')))
styles.add(ParagraphStyle(name='HeadingSCCI_RH',fontName='SCCI_RHBold',fontSize=15,leading=20,spaceBefore=17,spaceAfter=9,textColor=colors.HexColor('#0b1424'),keepWithNext=True))
styles.add(ParagraphStyle(name='SubSCCI_RH',fontName='SCCI_RHBold',fontSize=11,leading=16,spaceBefore=11,spaceAfter=6,textColor=colors.HexColor('#147c82'),keepWithNext=True))
styles.add(ParagraphStyle(name='CaptionSCCI_RH',fontName='SCCI_RH',fontSize=8,leading=11,spaceAfter=12,textColor=colors.HexColor('#536275')))
styles.add(ParagraphStyle(name='CellSCCI_RH',fontName='SCCI_RH',fontSize=7.2,leading=10,textColor=colors.HexColor('#24354a')))
styles.add(ParagraphStyle(name='CodeSCCI_RH',fontName='SCCI_RHMono',fontSize=7.8,leading=11,spaceAfter=10))

def inline(text):
    text=html.escape(text)
    text=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',lambda m:f'<link href="{m.group(2)}" color="#147c82">{m.group(1)}</link>',text)
    text=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<i>\1</i>',text)
    text=re.sub(r'`([^`]+)`',r'<font name="SCCI_RHMono">\1</font>',text)
    return text
def picture(path,caption=None):
    from PIL import Image as PILImage
    p=(ROOT/'docs'/path) if str(path).replace('\\','/').startswith('../') else ROOT/path
    if not p.exists():raise FileNotFoundError(f'Missing paper figure: {p}')
    w,h=PILImage.open(p).size
    width=475; height=min(315,width*h/w)
    width=height*w/h
    items=[Image(str(p),width=width,height=height)]
    if caption:items.append(Paragraph(inline(caption),styles['CaptionSCCI_RH']))
    return [KeepTogether(items)] if caption else items
def parse(text):
    items=[];lines=text.splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('```'):
            block=[];i+=1
            while i<len(lines) and not lines[i].strip().startswith('```'):
                block.append(lines[i]);i+=1
            items.append(Preformatted('\n'.join(block),styles['CodeSCCI_RH'],maxLineLength=86));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+',c or '-') for c in cells):rows.append(cells)
                i+=1
            n=max(map(len,rows));rows=[[Paragraph(inline(c),styles['CellSCCI_RH']) for c in row+['']*(n-len(row))] for row in rows]
            t=Table(rows,colWidths=[475/n]*n,repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#d9eeee')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#24a0a7')),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('GRID',(0,1),(-1,-1),.25,colors.HexColor('#d5dce3'))]))
            items.extend([t,Spacer(1,10)]);continue
        if line.startswith('#'):
            level=len(line)-len(line.lstrip('#'));title=line.lstrip('#').strip()
            if level==1 and 'SCCI_RH' in title:i+=1;continue
            items.append(Paragraph(inline(title),styles['HeadingSCCI_RH'] if level<=2 else styles['SubSCCI_RH']));i+=1;continue
        if line.startswith('!['):
            m=re.match(r'!\[([^\]]*)\]\(([^)]+)\)',line)
            if m:items+=picture(m.group(2),m.group(1))
            i+=1;continue
        if line=='---':i+=1;continue
        if line.startswith(('- ','* ')) or re.match(r'^\d+\. ',line):
            items.append(Paragraph(inline(line),styles['BodySCCI_RH']));i+=1;continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].strip().startswith(('#','|','```','- ','![','* ')):
            para.append(lines[i].strip());i+=1
        items.append(Paragraph(inline(' '.join(para)),styles['BodySCCI_RH']))
    return items
def footer(c,doc):
    c.saveState();w,h=doc.pagesize
    c.setStrokeColor(colors.HexColor('#d5dce3'));c.line(48,40,w-48,40)
    c.setFont('SCCI_RH',7);c.setFillColor(colors.HexColor('#536275'))
    c.drawString(48,27,'PROJECT SCCI RH  /  DIGITAL ENGINEERING STUDY  /  07 OCT 2026')
    c.drawRightString(w-48,27,str(doc.page));c.restoreState()

story=[Spacer(1,32),Paragraph('PROJECT SCCI RH',ParagraphStyle(name='Cover',fontName='SCCI_RHBold',fontSize=36,leading=43,textColor=colors.HexColor('#0b1424'))),Spacer(1,14),
    Paragraph('A digital engineering study of invasive spinal interfaces',ParagraphStyle(name='Subtitle',fontName='SCCI_RH',fontSize=20,leading=27,textColor=colors.HexColor('#147c82'))),Spacer(1,15),
    Paragraph('Motor learning, physiological feedback, reference electronics and mechanical design',styles['BodySCCI_RH']),Spacer(1,8)]
story+=picture(Path('media/scci_rh-hero.png'))
story.extend([Spacer(1,12),Paragraph('<b>Pratham Varma</b> | AI-assisted research and engineering<br/>Release 1.0 | 7 October 2026',styles['BodySCCI_RH']),Paragraph('Digital proof of concept. All study data are synthetic. The design is not a clinically validated implant; the rendered enclosure is a desktop demonstrator.',styles['CaptionSCCI_RH']),PageBreak()])
story+=parse((ROOT/'docs'/'scci_rh-paper.md').read_text(encoding='utf-8'))
story.extend([PageBreak(),Paragraph('Engineering plates',styles['HeadingSCCI_RH'])])
for p,caption in [('figures/architecture.png','Figure E1. Proposed signal paths and digital abstractions. Recording and stimulation placements are distinct.'),('media/scci_rh-exploded.png','Figure E2. Desktop enclosure and illustrative component envelopes. Actual circuit connectivity is specified by KiCad.'),('figures/mechanical-drawing.png','Figure E3. Nominal enclosure and mounting dimensions, mm. No fabrication tolerances were validated.')]:story+=picture(Path(p),caption)
plate_number=4
for p in sorted((ROOT/'figures').glob('*.png')):
    if p.stem in ('architecture','mechanical-drawing','motor_study','pressure_study'):continue
    story+=picture(p.relative_to(ROOT),f'Figure E{plate_number}. '+p.stem.replace('_',' ').replace('-',' ')+'. Digital model or layout output; see methods and source data.')
    plate_number+=1
doc=SimpleDocTemplate(str(OUT/'SCCI_RH_engineering_paper.pdf'),pagesize=(595.28,841.89),leftMargin=55,rightMargin=55,topMargin=48,bottomMargin=55,title='Project SCCI RH: digital engineering study',author='Pratham Varma',pageCompression=1)
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT/'SCCI_RH_engineering_paper.pdf')
