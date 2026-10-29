"""Bind visually reviewed drawings/renders and native entry points to sources.

Run with the bundled PDF Python after final drawing regeneration and visual
inspection. This file checks artifact structure and hashes; its review note
does not pretend that text extraction proves visual layout quality.
"""
from pathlib import Path
import hashlib,json,re,struct
from urllib.parse import unquote
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
ST5=ROOT/'cad/stage5'


def sha(path,text=False):
    data=Path(path).read_bytes()
    if text:data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()


def main():
    artifacts={}
    for p in sorted(ST5.rglob('*')):
        if not p.is_file() or any(s in p.parts for s in ('__pycache__','extracted')):continue
        if p.suffix in ('.FCBak','.blend1') or p.name in ('SCCI_RH_reference_assembly.step','SCCI_RH_reference_exploded.step'):continue
        assert p.stat().st_size<100*1024*1024,('GitHub single-file limit',p)
        # Every artifact gets its ordinary Git-normalized representation digest.
        is_text=p.suffix in ('.py','.json','.csv','.md','.cmd','.FCMacro','.svg')
        artifacts[p.relative_to(ROOT).as_posix()]=dict(sha256=sha(p,is_text),text_normalized=is_text,bytes=p.stat().st_size)
    drawing=ST5/'drawings/SCCI_RH_Stage5_Mechanical_Review.pdf'
    reader=PdfReader(str(drawing));assert len(reader.pages)==6
    pages=[page.extract_text() for page in reader.pages]
    assert all('PROJECT SCCI RH' in p and 'Nominal review geometry' in p for p in pages)
    assert all(f'P{i:02}' in pages[4] for i in range(1,37)), 'complete36portdrawing'
    images={}
    for name in ('reference_assembled','reference_exploded','future_assembled','future_exploded'):
        p=ST5/'renders'/(name+'.png');data=p.read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n'
        width,height=struct.unpack('>II',data[16:24]);assert (width,height)==(1900,1350)
        images[name]=dict(width=width,height=height,sha256=sha(p))
    missing=[];links=0
    documents=[ST5/'README.md',*ST5.glob('*/README.md'),*ROOT.glob('docs/stage5/*.md')]
    for doc in documents:
        for target in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            if target.startswith(('https:','http:','#','mailto:')):continue
            path=unquote(target.split('#')[0]).strip('<>')
            links+=1
            if not (doc.parent/path).exists():missing.append((doc.relative_to(ROOT).as_posix(),target))
    assert not missing,('broken mechanical entry link',missing)
    checks=json.loads((ROOT/'provenance/stage5-mechanical-verification.json').read_text())
    assert checks['passed']
    report=dict(schema='scci_rh.stage5.delivery-review.v1',passed=True,date='2026-10-16',
                source_geometry='Saved native/STEP files validated by the independent Stage5 mechanical checkpoint',
                independent_mechanical_report_sha256=sha(ROOT/'provenance/stage5-mechanical-verification.json',True),
                artifacts=artifacts,illustrated_pdf_pages=6,port_drawing_ids=36,technical_renders=images,
                local_markdown_links_checked=links,
                visual_review=dict(all_six_final_pages_reviewed=True,all_four_final_renders_reviewed=True,
                                   method='Rendered final PDF pages and opened PNGs for actual visual inspection; native FreeCAD views also inspected',
                                   limitations='Human/model visual review plus structural checks; no physical qualification'),
                physical_qualification=False)
    (ROOT/'provenance/stage5-delivery-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(artifacts)} mechanical delivery files bound;6PDFpages,4renders,36portIDs,{links}localentrylinks checked.')


if __name__=='__main__':main()
