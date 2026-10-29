"""Refresh only hash-bound file-length metadata after the name migration."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]

def main():
    report=[]
    inventory=json.loads((ROOT/'provenance/project-name-migration.json').read_text(encoding='utf-8-sig'))
    for item in inventory['files']:
        p=ROOT/item['new_path']
        if p.suffix!='.json' or p.stat().st_size>8_000_000 or p.as_posix().startswith((ROOT/'inspector/vendor').as_posix()):continue
        obj=json.loads(p.read_text(encoding='utf-8-sig'));changes=[]
        def walk(v):
            if isinstance(v,list):
                for x in v:walk(x)
            elif isinstance(v,dict):
                if isinstance(v.get('bytes'),int) and isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):
                    candidates={q.resolve() for q in (p.parent/v['path'],ROOT/v['path']) if q.is_file()}
                    matches=[]
                    for q in candidates:
                        if not q.is_relative_to(ROOT):continue
                        raw=q.read_bytes()
                        if v['sha256'] in {hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()}:matches.append((q,len(raw)))
                    if len(matches)==1 and matches[0][1]!=v['bytes']:
                        q,size=matches[0];changes.append({'source':q.relative_to(ROOT).as_posix(),'prior_bytes':v['bytes'],'current_bytes':size});v['bytes']=size
                for x in v.values():walk(x)
        walk(obj)
        if changes:
            p.write_bytes((json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
            report.append({'path':p.relative_to(ROOT).as_posix(),'length_fields':changes})
    (ROOT/'provenance/rebrand-file-length-metadata.json').write_bytes((json.dumps({'scope':'Hash-bound file byte lengths only; no model parameters changed','files':report},indent=2)+'\n').encode())
    print(json.dumps({'files':len(report),'length_fields':sum(len(r['length_fields']) for r in report)}))

if __name__=='__main__':main()
