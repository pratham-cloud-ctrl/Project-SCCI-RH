"""Read-only portable audit of populated exports and exact source bindings."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def sha(p):
    data=p.read_bytes()
    if p.suffix.lower() not in ('.png','.step','.fcstd','.elf','.bin'):
        data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()


def main(names=None):
    system=json.loads((HERE/'integration/system.json').read_text())
    checks=0
    def check(value,why):
        nonlocal checks
        checks+=1
        assert value,why
    for name in names or system['boards']:
        directory=HERE/'exports'/name
        r=json.loads((directory/'export-receipt.json').read_text())
        board=ROOT/r['source_board']
        # Earlier exports preserve the exact source that actually generated
        # their bytes. A reviewed guard-only revision need not recast unchanged
        # geometry; the current independent checks below still bind its DRC.
        exporter=HERE/'export_boards.py'
        if sha(exporter)!=r['exporter_sha256_lf']:
            exporter=HERE/'provenance/exporter-sources'/(r['exporter_sha256_lf']+'.py.txt')
            if not exporter.is_file():
                # Original hash-named snapshots retain their historical names
                # after the authorized branding migration. Resolve only one
                # exact current-content digest; never substitute a newer tool.
                matches=[p for p in exporter.parent.glob('*.py.txt') if sha(p)==r['exporter_sha256_lf']]
                check(len(matches)==1,name+' unique exact archived exporter content')
                exporter=matches[0]
        check(exporter.is_file() and sha(exporter)==r['exporter_sha256_lf'],name+' actual exporter source binding')
        check(sha(board)==r['source_sha256_lf'],name+' source board')
        check(sha(board.with_suffix('.kicad_pro'))==r['source_project_sha256_lf'],name+' project rules')
        xml=(ROOT/system['native_outputs'][name]['board_root']).with_suffix('.xml')
        check(sha(xml)==r['source_xml_sha256_lf'],name+' actual source XML')
        drc=board.parent/'drc.json'
        check(sha(drc)==r['DRC_sha256_lf'],name+' DRC binding')
        actual=json.loads(drc.read_text())
        binding=json.loads((board.parent/'drc-binding.json').read_text())
        for key,path in [('pcb_sha256_lf',board),('project_sha256_lf',board.with_suffix('.kicad_pro')),
                         ('schematic_sha256_lf',board.with_suffix('.kicad_sch')),('drc_sha256_lf',drc)]:
            check(binding[key]==sha(path),name+' current native DRC '+key)
        check(binding['schematic_parity_checked'] and not binding['suppressed_checks'],name+' full native parity/DRC')
        for key in ('ignored_checks','violations','unconnected_items','schematic_parity'):
            check(not actual[key],name+' '+key)
        check(not r['physical_qualification'],name+' evidence boundary')
        for relative,h in r['outputs'].items():
            p=directory/relative
            check(p.is_file() and p.stat().st_size>0,name+' output '+relative)
            check(sha(p)==h,name+' output hash '+relative)
        parts={p.get('ref'):p for p in ET.parse(xml).getroot().findall('components/comp')}
        dnp={ref for ref,p in parts.items() if any(x.get('name')=='dnp' for x in p.findall('property'))}
        fitted=set(parts)-dnp
        check(r['component_count']==len(parts),name+' component count')
        check(r['fitted_component_count']==len(fitted) and set(r['DNP_references'])==dnp,name+' exact source population intent')
        fab=directory/'fabrication-reference'
        bom=list(csv.DictReader((fab/'bom.csv').open(encoding='utf-8',newline='')))
        check({p['Reference'] for p in bom}==set(parts),name+' BOM references')
        for row in bom:
            p=parts[row['Reference']]
            check(row['Value']==p.findtext('value') and row['Footprint']==p.findtext('footprint'),name+' BOM identity')
            check(row['DNP']==str(int(row['Reference'] in dnp)),name+' BOM DNP')
        positions=list(csv.DictReader((fab/'positions.csv').open(encoding='utf-8',newline='')))
        check({p['Ref'] for p in positions}==fitted,name+' fitted position reference coverage')
        step=(directory/'populated.step').read_text()
        check(step.startswith('ISO-10303-21;') and 'MANIFOLD_SOLID_BREP' in step,name+' actual STEP BREP')
        check('KiCad electronic assembly' in step,name+' native KiCad STEP')
        geometry=json.loads((directory/'geometry-verification.json').read_text())
        check(geometry['STEP_sha256']==sha(directory/'populated.step'),name+' reimported STEP hash')
        check(geometry['valid'] and geometry['solids']>=len(fitted)+1 and geometry['volume_mm3']>0,name+' valid reimported fitted solids')
        check(not geometry['manufacturing_tolerance_or_physical_performance_qualified'],name+' nominal geometry evidence')
        for ref in fitted:
            # KiCad reuses a package PRODUCT for repeated parts; each actual
            # reference is retained in a distinct assembly usage occurrence.
            check(bool(re.search(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\('[^']*','"+re.escape(ref)+r"'",step)),name+' populated STEP '+ref)
        for ref in dnp:
            check(not re.search(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\('[^']*','"+re.escape(ref)+r"'",step),name+' DNP excluded from geometry '+ref)
        for side in ('top','bottom','isometric'):
            png=(directory/(side+'.png')).read_bytes()
            check(png[:8]==b'\x89PNG\r\n\x1a\n',name+' rendered PNG '+side)
            # KiCad's native render viewport subtracts its frame padding on
            # Windows (1768x1376 for the requested 1800x1400 viewport).
            w,h=struct.unpack('>II',png[16:24])
            check(1600<=w<=1800 and 1200<=h<=1400,name+' actual rendered dimensions '+side)
        check(all(list(fab.glob('*'+ext)) for ext in ('.gtl','.g1','.g2','.gbl')),name+' four actual copper layers')
    print(f'Populated export audit: {checks} checks passed across {len(names or system["boards"])} board(s)')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',action='append');a=p.parse_args();main(a.board)
