"""Verify release integrity and reported digital checks, never biological efficacy."""
from pathlib import Path
import json,csv,math
ROOT=Path(__file__).resolve().parents[1]
required=['README.md','docs/scci_rh-paper.md','docs/architecture.md','docs/model-methods.md',
 'docs/electronics.md','docs/learning-guide.md','docs/evidence-matrix.csv','docs/claim-register.csv',
 'electronics/scci_rh_reference.kicad_sch','electronics/scci_rh_reference.kicad_pcb',
 'electronics/bom.csv','electronics/exports/scci_rh_reference.step',
 'cad/build_scci_rh.py','cad/scci_rh-reference.FCStd','cad/scci_rh-presentation.blend',
 'cad/exports/scci_rh-desktop-assembly.step','cad/exports/geometry-checks.json',
 'media/scci_rh-hero.png','media/scci_rh-exploded.png','media/SCCI_RH_walkthrough.mp4',
 'site/index.html','output/pdf/SCCI_RH_engineering_paper.pdf',
 'results/summary.json','results/study_metadata.json','results/firmware_validation.json',
 'results/adapter_validation.json',
 'provenance/CONTRIBUTIONS.md']
for relative in required:
    p=ROOT/relative
    assert p.is_file() and p.stat().st_size>0, f'Missing or empty: {relative}'
summary=json.loads((ROOT/'results/summary.json').read_text())
assert summary['motor']['zero_beta_retention_difference_max']==0
assert summary['pressure']['stale_sensor_nonzero_commands']==0
geom=json.loads((ROOT/'cad/exports/geometry-checks.json').read_text())
assert geom['pcb_base_overlap_mm3']<.001 and geom['lid_base_overlap_mm3']<.001
assert all(part['valid'] and part['volume_mm3']>0 and part['step_volume_error_mm3']<.001 for part in geom['parts'].values())
assembly=json.loads((ROOT/'cad/exports/electronics-assembly-checks.json').read_text())
assert assembly['pcb_valid'] and assembly['base'] and assembly['lid']
assert assembly['pcb_base_overlap_mm3']<.001 and assembly['pcb_lid_overlap_mm3']<.001
assert json.loads((ROOT/'results/firmware_validation.json').read_text())['status']=='passed'
adapter=json.loads((ROOT/'results/adapter_validation.json').read_text())
assert adapter['status']=='passed' and all(adapter['checks'].values())
electrical=json.loads((ROOT/'electronics/simulation/metrics.json').read_text())
assert all(electrical['analytical_validation'].values())
for run in [electrical['spice'],*electrical['spice_sensitivity'].values()]:
    assert run['executed'] and all(run['validation'].values())
for report in ('erc','drc'):
    d=json.loads((ROOT/f'electronics/reports/{report}.json').read_text())
    if report=='erc':issues=[v for s in d['sheets'] for v in s.get('violations',[])]
    else:issues=d.get('violations',[])+d.get('unconnected_items',[])+d.get('schematic_parity',[])
    assert not issues, f'{report.upper()} has reported issues: {len(issues)}'
for p in (ROOT/'results').glob('*.csv'):
    with p.open(newline='',encoding='utf-8') as f:
        rows=list(csv.DictReader(f));assert rows,f'Empty CSV: {p.name}'
        for row in rows:
            for field,v in row.items():
                if v is None:raise AssertionError(f'Malformed row in {p.name}')
                try:n=float(v)
                except ValueError:continue
                missing_observation=(field=='measurement_mmhg' and
                    (row.get('sensor_available')=='0' or row.get('sensor_stale')=='1'))
                assert math.isfinite(n) or missing_observation,f'Unexpected nonfinite {field} in {p.name}'
assert '__SCCI_RH_DATA__' not in (ROOT/'site/index.html').read_text(encoding='utf-8')
print('Release files, model guards, geometry, ERC/DRC and source data verified; flagged unavailable measurements are preserved.')
