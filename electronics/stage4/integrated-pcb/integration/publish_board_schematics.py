"""Place exact per-board schematic sources beside the physical board files.

Do not modify board files, board project settings, routing rules or footprint
tables.  This makes KiCad's native schematic/PCB parity check concrete.
"""
import hashlib,json,shutil
from build_integration import HERE
def main():
    s=json.loads((HERE/'system.json').read_text(encoding='utf-8'));bindings=[]
    for pkg in s['boards']:
        source=HERE/'boards'/pkg;target=HERE.parent/'boards'/pkg;target.mkdir(parents=True,exist_ok=True)
        files=sorted(source.glob('*.kicad_sch'))+sorted(source.glob('*.kicad_sym'))+[source/'sym-lib-table']
        for path in files:
            dest=target/path.name;shutil.copyfile(path,dest)
            bindings.append({'source':str(path.relative_to(HERE.parent)).replace('\\','/'),'board_sibling':str(dest.relative_to(HERE.parent)).replace('\\','/'),'sha256_lf':hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()})
    (HERE/'board-schematic-bindings.json').write_text(json.dumps({'schema':'scci_rh.board-schematic-bindings.v1','files':bindings,'policy':'Exact schematic/symbol copies; board project/routing/footprint configuration never overwritten'},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'copied_files':len(bindings),'boards':len(s['boards'])}))
if __name__=='__main__':main()
