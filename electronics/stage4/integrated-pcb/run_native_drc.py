"""Run real KiCad DRC/parity with the exact local footprint libraries.

The temporary empty GLOBAL library table avoids unrelated installed libraries;
each board's preserved PROJECT table still loads every actual footprint. No DRC
test, clearance or violation is suppressed. Does not alter the user's config.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board',action='append')
    parser.add_argument('--write',action='store_true',help='refresh bound saved reports; otherwise fresh checks live only in a temporary directory')
    parser.add_argument('--kicad-cli',default=shutil.which('kicad-cli') or r'E:\project workspace assests\EDA\KiCAD\bin\kicad-cli.exe')
    args=parser.parse_args();system=json.loads((HERE/'integration/system.json').read_text())
    with tempfile.TemporaryDirectory(prefix='scci_rh-native-drc-') as temporary:
        config=Path(temporary)/'config';config.mkdir()
        (config/'fp-lib-table').write_text('(fp_lib_table (version 7))\n')
        env=os.environ.copy();env['KICAD_CONFIG_HOME']=str(config)
        for name in args.board or system['boards']:
            board=HERE/'boards'/name/(name.replace('-','_')+'.kicad_pcb')
            output=board.parent/'drc.json' if args.write else Path(temporary)/(name+'-drc.json')
            command=[args.kicad_cli,'pcb','drc','--format','json','--schematic-parity','--output',str(output),str(board)]
            completed=subprocess.run(command,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
            if completed.returncode:raise RuntimeError(completed.stdout+completed.stderr)
            report=json.loads(output.read_text())
            counts={k:len(report[k]) for k in ('violations','unconnected_items','schematic_parity','ignored_checks')}
            assert not any(counts.values()),(name,counts)
            if args.write:
                subprocess.run([sys.executable,str(HERE/'layout/bind_drc.py'),'--board',name],check=True)
            print(name,counts,flush=True)


if __name__=='__main__':main()
