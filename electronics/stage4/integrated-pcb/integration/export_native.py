"""Refresh actual KiCad exports; never used by read-only CI verification."""
import json,subprocess
from pathlib import Path
from build_integration import HERE,ROOT
CLI=Path('E:/project workspace assests/EDA/KiCAD/bin/kicad-cli.exe')
def run(args):
    result=subprocess.run([str(CLI),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    print(result.stdout.strip(),flush=True)
def main():
    system=json.loads((HERE/'system.json').read_text(encoding='utf-8'))
    for pkg,out in system['native_outputs'].items():
        schematic=ROOT/out['board_root']
        run(['sch','export','netlist','--format','kicadxml','--output',schematic.with_suffix('.xml'),schematic])
        run(['sch','erc','--format','json','--severity-all','--output',schematic.parent/'erc.json',schematic])
        print('Exported '+pkg,flush=True)
    master=HERE/'master/SCCI_RH_integrated.kicad_sch'
    run(['sch','export','netlist','--format','kicadxml','--output',master.with_suffix('.xml'),master])
    run(['sch','erc','--format','json','--severity-all','--output',master.parent/'erc.json',master])
    run(['sch','export','pdf','--output',master.with_suffix('.pdf'),master])
if __name__=='__main__':main()
