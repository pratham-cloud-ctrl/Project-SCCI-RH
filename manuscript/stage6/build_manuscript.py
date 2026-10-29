"""Typeset the integrated manuscript; no data generation or biological fitting.

Requires the project's pinned reportlab, matplotlib, pillow and pypdf packages.
The Markdown, verified reference register and source-derived figures are inputs.
PDF bytes are deterministic with ReportLab invariant mode and a fixed source.
"""
from pathlib import Path
import hashlib, html, json, re, platform
from importlib.metadata import version
import matplotlib
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
    Spacer, PageBreak, Image, Table, TableStyle, KeepTogether, CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen.canvas import Canvas
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PDF=ROOT/'output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf'
SOURCE=HERE/'manuscript.md'
REFS=ROOT/'docs/stage6/references.json'
RELEASE=json.loads((ROOT/'docs/stage6/release-contract.json').read_text(encoding='utf-8'))
W,H=595.2756,841.8898
LEFT=50; RIGHT=50; TOP=53; BOTTOM=52; WIDTH=W-LEFT-RIGHT
NAVY=colors.HexColor('#172d45'); TEAL=colors.HexColor('#087f8c')
MUTED=colors.HexColor('#556779'); LIGHT=colors.HexColor('#edf4f6')
FONTS=Path(matplotlib.get_data_path())/'fonts/ttf'
for name,file in [('Serif','DejaVuSerif.ttf'),('SerifBold','DejaVuSerif-Bold.ttf'),
                  ('SerifItalic','DejaVuSerif-Italic.ttf'),('Sans','DejaVuSans.ttf'),
                  ('SansBold','DejaVuSans-Bold.ttf'),('Mono','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONTS/file)))
pdfmetrics.registerFontFamily('Serif',normal='Serif',bold='SerifBold',italic='SerifItalic',boldItalic='SerifBold')
pdfmetrics.registerFontFamily('Sans',normal='Sans',bold='SansBold',italic='Sans',boldItalic='SansBold')
styles={
 'body':ParagraphStyle('Body',fontName='Serif',fontSize=9.7,leading=14.5,spaceAfter=8,textColor=NAVY,allowWidows=0,allowOrphans=0),
 'h1':ParagraphStyle('Section',fontName='SansBold',fontSize=15,leading=20,spaceBefore=19,spaceAfter=10,textColor=NAVY,keepWithNext=True),
 'h2':ParagraphStyle('Subsection',fontName='SansBold',fontSize=10.7,leading=15,spaceBefore=12,spaceAfter=6,textColor=TEAL,keepWithNext=True),
 'caption':ParagraphStyle('Caption',fontName='Sans',fontSize=8,leading=11.4,spaceBefore=4,spaceAfter=13,textColor=MUTED),
 'cell':ParagraphStyle('Cell',fontName='Sans',fontSize=7.6,leading=10.7,textColor=NAVY,splitLongWords=True),
 'cellhead':ParagraphStyle('CellHead',fontName='SansBold',fontSize=7.6,leading=10.7,textColor=NAVY),
 'ref':ParagraphStyle('Reference',fontName='Serif',fontSize=8.2,leading=12,spaceAfter=10,textColor=NAVY),
 'equation':ParagraphStyle('Equation',fontName='Mono',fontSize=8.3,leading=12.8,leftIndent=9,rightIndent=9,
                            spaceBefore=3,spaceAfter=10,textColor=TEAL,borderColor=colors.HexColor('#c8dde2'),borderPadding=7,borderWidth=.5),
 'small':ParagraphStyle('Small',fontName='Sans',fontSize=8.3,leading=12,textColor=MUTED,spaceAfter=8),
}
FIGURES={}

def sha(p,text=False):
    b=Path(p).read_bytes()
    return hashlib.sha256(b.replace(b'\r\n',b'\n') if text else b).hexdigest()

def inline(text):
    text=text.translate(str.maketrans({'\u2010':'-','\u2011':'-','\u2012':'-','\u2013':'-','\u2014':'-','\u2212':'-'}))
    text=html.escape(text,quote=False)
    text=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',lambda m:f'<link href="{m.group(2)}" color="#087f8c">{m.group(1)}</link>',text)
    text=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'`([^`]+)`',r'<font name="Mono" size="8.1">\1</font>',text)
    text=re.sub(r'\[(R\d\d)\]',r'<link href="#ref-\1" color="#087f8c">[\1]</link>',text)
    return text

def picture(path,caption,maxheight=284):
    p=(HERE/path).resolve()
    assert p.is_file(),p
    FIGURES[p.relative_to(ROOT).as_posix()]=sha(p)
    w,h=PILImage.open(p).size
    height=min(maxheight,WIDTH*h/w);width=height*w/h
    return KeepTogether([Spacer(1,6),Image(str(p),width,height),Paragraph(inline(caption),styles['caption'])])

def table(rows):
    n=len(rows[0]);assert all(len(r)==n for r in rows),'rectangular manuscript table'
    # First columns carry concise identity; the remaining prose needs more width.
    fractions={3:[.23,.37,.40],4:[.25,.25,.25,.25],2:[.32,.68]}.get(n,[1/n]*n)
    if n==4 and all('mm' in c or 'events' in c.lower() or 'rho' in c.lower() for c in rows[0][1:]):fractions=[.34,.22,.22,.22]
    data=[[Paragraph(inline(c),styles['cellhead'] if i==0 else styles['cell']) for c in row] for i,row in enumerate(rows)]
    t=Table(data,colWidths=[WIDTH*f for f in fractions],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dfedf0')),
       ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
       ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
       ('LINEBELOW',(0,0),(-1,0),.7,TEAL),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#d2dce2')),
       ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7fafb')])]))
    # Compact comparisons should not strand one data row on the preceding page.
    if len(rows) <= 5:
        return [KeepTogether([t,Spacer(1,10)])]
    return [t,Spacer(1,10)]

def parse(text):
    lines=text.splitlines();out=[];i=0
    while i<len(lines):
        s=lines[i].strip()
        if not s or s.startswith('# '):i+=1;continue
        if s.startswith('## '):
            p=Paragraph(inline(s[3:]),styles['h1']);p._bookmark='section-'+str(i)
            out.extend([CondPageBreak(100),p]);i+=1;continue
        if s.startswith('### '):out.append(Paragraph(inline(s[4:]),styles['h2']));i+=1;continue
        if s.startswith('!['):
            m=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',s);assert m,s
            out.append(picture(m[2],m[1]));i+=1;continue
        if s.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+',c or '-') for c in cells):rows.append(cells)
                i+=1
            out+=table(rows);continue
        paragraph=[s];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('#','|','![')):
            paragraph.append(lines[i].strip());i+=1
        joined=' '.join(paragraph)
        if joined.startswith('`') and joined.endswith('`'):
            out.append(Paragraph(html.escape(joined[1:-1]),styles['equation']))
        else:
            paragraph=Paragraph(inline(joined),styles['body'])
            following=i
            while following<len(lines) and not lines[following].strip():following+=1
            if following<len(lines) and lines[following].strip().startswith('`'):
                paragraph.keepWithNext=True
            out.append(paragraph)
    return out

def footer(c,doc):
    c.saveState()
    c.setStrokeColor(colors.HexColor('#cbd8e0'));c.setLineWidth(.5);c.line(LEFT,39,W-RIGHT,39)
    c.setFillColor(MUTED);c.setFont('Sans',6.8)
    c.drawString(LEFT,26,'PROJECT SCCI RH  /  INTEGRATED DIGITAL RESEARCH AND ENGINEERING  /  '+RELEASE['tag'])
    c.drawRightString(W-RIGHT,26,str(doc.page));c.restoreState()

class Document(BaseDocTemplate):
    def afterFlowable(self,f):
        if isinstance(f,Paragraph) and f.style.name=='Section':
            key=f._bookmark;self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(f.getPlainText(),key,0,False)
            self.notify('TOCEntry',(0,f.getPlainText(),self.page,key))

def main():
    references=json.loads(REFS.read_text(encoding='utf-8'))['references']
    assert len(references)==18
    PDF.parent.mkdir(parents=True,exist_ok=True)
    story=[Spacer(1,24),Paragraph('PROJECT SCCI RH',ParagraphStyle('CoverMark',fontName='SansBold',fontSize=32,leading=38,textColor=NAVY)),Spacer(1,15),
      Paragraph('A conditional spinal cord-computer interface',ParagraphStyle('CoverTitle',fontName='SansBold',fontSize=24,leading=31,textColor=TEAL)),Spacer(1,11),
      Paragraph('Expert-informed practice and function-specific physiological feedback',ParagraphStyle('CoverSub',fontName='Serif',fontSize=14,leading=21,textColor=NAVY)),Spacer(1,15)]
    cover=ROOT/'cad/stage5/renders/future_assembled.png'
    FIGURES[cover.relative_to(ROOT).as_posix()]=sha(cover)
    w,h=PILImage.open(cover).size;story.append(Image(str(cover),400,400*h/w))
    story.extend([Spacer(1,10),Paragraph('<b>Pratham Varma</b><br/>AI-assisted student research and engineering<br/>Integrated digital release '+RELEASE['version']+' | '+RELEASE['date'],styles['small']),
      Paragraph('Theory, computational studies, native electronics, compiled control software and mechanical CAD. Future biological capabilities remain explicit hypotheses. No original human or animal experiment, physical hardware execution or implanted qualification is reported.',styles['small']),PageBreak()])
    story.append(Paragraph('Contents',ParagraphStyle('ContentsTitle',parent=styles['h1'])))
    toc=TableOfContents();toc.levelStyles=[ParagraphStyle('TOC0',fontName='Sans',fontSize=9.4,leading=14,spaceBefore=7,textColor=NAVY,leftIndent=0,firstLineIndent=0)]
    story.extend([toc,Spacer(1,18),Paragraph('Reading guide: Sections 1-4 define the future mechanism and premises; Sections 5-8 report model and software evidence; Sections 9-10 connect native engineering and verification; Sections 11-12 and the appendices explain reproduction, contribution and the next empirical decisions.',styles['small']),PageBreak()])
    story+=parse(SOURCE.read_text(encoding='utf-8'))
    for r in references:
        rid=r['id']
        authors=r.get('author_string') or ', '.join(r.get('authors',[]))
        if not authors:authors='AstroSam / sam-astro'
        journal=' '.join(str(r[k]) for k in ('journal','volume','pages_or_article') if r.get(k)).strip()
        title=r['title'].translate(str.maketrans({'\u2010':'-','\u2011':'-','\u2012':'-','\u2013':'-','\u2014':'-'}))
        text=f'<a name="ref-{rid}"/><b>[{rid}]</b> {html.escape(authors)} ({r.get("year",2026)}). {html.escape(title)}. '
        if journal:text+=html.escape(journal)+'. '
        text+=f'<link href="{html.escape(r["url"],quote=True)}" color="#087f8c">{html.escape(r["url"])}</link>.'
        story.append(Paragraph(text,styles['ref']))
    story.extend([Spacer(1,10),Paragraph('Primary-source verification: 16 October 2026. The original hypothesis paper states a 30 September 2026 evidence cutoff; this focused audit is not a claim of exhaustive coverage. Complete author metadata, access depth, populations, supported claims and inference limits are in docs/stage6/references.json and evidence-review.md.',styles['small'])])
    doc=Document(str(PDF),pagesize=(W,H),leftMargin=LEFT,rightMargin=RIGHT,topMargin=TOP,bottomMargin=BOTTOM,
       title='Project SCCI RH: integrated SCCI research and engineering',author='Pratham Varma',subject='Conditional spinal interface; digital design and finite evidence',pageCompression=1,
       invariant=1)  # BaseDocTemplate forwards its own value to every canvas.
    doc.addPageTemplates(PageTemplate(id='main',frames=[Frame(LEFT,BOTTOM,WIDTH,H-TOP-BOTTOM,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=footer))
    doc.multiBuild(story,canvasmaker=Canvas)
    reader=PdfReader(str(PDF))
    report={'schema':'scci_rh.stage6.manuscript-build.v1','version':RELEASE['version'],'date':RELEASE['date'],
      'release_contract_sha256_lf':sha(ROOT/'docs/stage6/release-contract.json',True),
      'source_path':SOURCE.relative_to(ROOT).as_posix(),'source_sha256_lf':sha(SOURCE,True),
      'builder_path':Path(__file__).relative_to(ROOT).as_posix(),'builder_sha256_lf':sha(Path(__file__),True),
      'pdf_path':PDF.relative_to(ROOT).as_posix(),'pdf_sha256':sha(PDF),'pages':len(reader.pages),
      'figures':dict(sorted(FIGURES.items())),'references_path':REFS.relative_to(ROOT).as_posix(),'references_sha256_lf':sha(REFS,True),
      'figure_generator_path':(HERE/'build_figures.py').relative_to(ROOT).as_posix(),'figure_generator_sha256_lf':sha(HERE/'build_figures.py',True),
      'source_words':len(SOURCE.read_text(encoding='utf-8').split()),'layout':'A4 portrait, embedded DejaVu fonts, linked contents/references, deterministic ReportLab PDF',
      'environment':{'python':platform.python_version(),
         'packages':{name:version(name) for name in ('reportlab','matplotlib','pillow','pypdf','numpy')},
         'font_sha256':{file:sha(FONTS/file) for file in ('DejaVuSerif.ttf','DejaVuSerif-Bold.ttf','DejaVuSerif-Italic.ttf','DejaVuSans.ttf','DejaVuSans-Bold.ttf','DejaVuSansMono.ttf')}},
      'visual_review_required':True,'physical_qualification':False}
    (HERE/'build-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'{len(reader.pages)} pages; {len(FIGURES)} image inputs; {report["source_words"]} source words; PDF {PDF.stat().st_size:,} bytes.')

if __name__=='__main__':main()
