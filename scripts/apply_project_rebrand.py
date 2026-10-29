"""Apply the authorized source/path rebrand; immutable history is untouched."""
from pathlib import Path
import json, subprocess
from project_branding import rename_text, rename_path

ROOT=Path(__file__).resolve().parents[1]
BINARY={'.fcstd','.blend','.glb','.stl','.pdf','.png','.jpg','.mp4','.zip','.gz','.npz','.bin','.elf'}

def main():
    inventory=json.loads(Path('E:/Project-history/before-name-change-20261028/inventory.json').read_text())
    rows=[]
    for record in inventory['files']:
        old=record['path'];new=rename_path(old)
        source=ROOT/old;target=ROOT/new
        if new!=old:
            assert not target.exists(), 'Rename collision: '+new
            target.parent.mkdir(parents=True,exist_ok=True)
            source.rename(target)
        changed=False
        if not new.startswith('inspector/vendor/') and target.suffix.lower() not in BINARY:
            data=target.read_bytes()
            try:
                if b'\0' not in data[:4096]:
                    decoded=data.decode('utf-8');updated=rename_text(decoded)
                    if updated!=decoded:target.write_bytes(updated.encode('utf-8'));changed=True
            except UnicodeDecodeError:pass
        rows.append({**record,'new_path':new,'text_rebranded':changed})
    report={'schema':'project-branding-migration.v1','date':'2026-10-28','original_commit':inventory['commit'],
            'display_name':'Project SCCI RH','repository_name':'Project-SCCI-RH','namespace':'scci_rh',
            'scope':'Authorized active-project name migration; original immutable Git objects are retained.',
            'files':rows}
    (ROOT/'provenance/project-name-migration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'files':len(rows),'paths_renamed':sum(r['path']!=r['new_path'] for r in rows),
                      'text_files_rebranded':sum(r['text_rebranded'] for r in rows)}))

if __name__=='__main__':main()
