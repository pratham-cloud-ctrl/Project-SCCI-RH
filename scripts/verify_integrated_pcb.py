"""Portable final checkpoint for SCCI_RH's populated digital PCB assembly.

Runs existing independent audits and binds their current native/source/export
evidence. Does not regenerate CAD, execute target firmware or require KiCad or
FreeCAD on the verification host. --write-report intentionally freezes a reviewed
revision; the default reruns read-only audits and compares the saved checkpoint.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from project_branding import assert_baseline_equivalence
PACKAGE=ROOT/'electronics/stage4/integrated-pcb'
REPORT=ROOT/'provenance/stage4-integrated-pcb-verification.json'
BASELINE='bf0bdf8dbf138481a492a7a50c65034b43bbdf99'
sys.path.insert(0,str(PACKAGE/'integration'))
from sexp import loads,sub,subs

def sha(path,text=False):
    raw=path.read_bytes()
    if text:raw=raw.replace(b'\r\n',b'\n')
    return hashlib.sha256(raw).hexdigest()

def audit():
    checks=0
    def check(value,reason):
        nonlocal checks
        checks+=1
        if not value:raise AssertionError(reason)
    def run(relative,*arguments):
        result=subprocess.run([sys.executable,str(ROOT/relative),*arguments],cwd=ROOT,
                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,encoding='utf-8',errors='replace',timeout=180)
        if result.returncode:raise AssertionError(relative+' failed:\n'+result.stdout[-10000:])
        check(True,'independent audit '+relative)
        return result.stdout

    integration=json.loads(run('electronics/stage4/integrated-pcb/integration/verify_integration.py'))
    populated=json.loads(run('electronics/stage4/integrated-pcb/integration/verify_populated_boards.py'))
    firmware=json.loads(run('electronics/stage4/integrated-pcb/firmware-profile/verify_bt40f.py'))
    power_stdout=run('electronics/stage4/integrated-pcb/verify_power.py').strip()
    reproduction_stdout=run('electronics/stage4/integrated-pcb/power_overlay.py').strip()
    export_stdout=run('electronics/stage4/integrated-pcb/verify_exports.py').strip()
    check(integration['passed'] and integration['assertions']>=9540,'independent native integration assertions')
    check(integration==json.loads((PACKAGE/'integration/verification.json').read_text(encoding='utf-8')),'saved native integration receipt is current')
    check(populated['passed'] and len(populated['boards'])==8,'eight actual native populated boards')
    check(firmware['passed'] and firmware['checks']==83,'83 carrier-specific firmware checks')
    check(not populated['failures'],'no populated audit failures')
    check('23 checks passed' in power_stdout,'independent decimal power arithmetic')
    totals={
        'electrical_positions':sum(b['schematic_components'] for b in populated['boards'].values()),
        'fitted_components':sum(b['fitted_components'] for b in populated['boards'].values()),
        'mechanical_mounts':sum(len(b['mechanical_footprints']) for b in populated['boards'].values()),
        'trace_segments':sum(b['segments'] for b in populated['boards'].values()),
        'vias':sum(b['vias'] for b in populated['boards'].values()),
        'electrical_pin_identities':sum(b['electrical_pins'] for b in populated['boards'].values()),
    }
    expected={'electrical_positions':1298,'fitted_components':1296,'mechanical_mounts':32,
              'trace_segments':21039,'vias':2335,'electrical_pin_identities':4781}
    check(totals==expected,'exact frozen eight-board totals')
    check(integration['components']==totals['electrical_positions'] and integration['fitted_components']==totals['fitted_components'],'master and physical population totals')
    check(integration['harness_rows']==258 and integration['sheets']==80,'master and physical harness scope')
    check(integration['DNP_references']==['C20100','C20200'],'two original optional driver positions')
    saved_populated=json.loads((PACKAGE/'integration/populated-verification.json').read_text(encoding='utf-8'))
    check(saved_populated['assertions']==populated['assertions'] and saved_populated['passed'],'saved populated audit receipt is current')
    for name,current in populated['boards'].items():
        saved=dict(saved_populated['boards'][name]);current=dict(current)
        saved['mechanical_footprints']=sorted(saved['mechanical_footprints']);current['mechanical_footprints']=sorted(current['mechanical_footprints'])
        check(saved==current,'saved actual board receipt matches current native data '+name)

    # Historical Git objects remain immutable. Current renamed artifacts must
    # match their exact branding transform or a hash-bound validated derivative.
    native=['monitoring-cell','current-driver','recording-front-end','contact-router','supervision','power','monitoring-transport']
    studies=['monitoring-study','driver-study','recording-study','routing-study','supervision-study','power-study','transport-study']
    historical_paths=['electronics/stage4/'+p for p in native+studies]+['firmware/nrf5340',
        'scripts/build_nrf5340.py','scripts/verify_nrf5340.py',
        'provenance/stage4-nrf5340-build.json','provenance/stage4-nrf5340-verification.json']
    tree=subprocess.check_output(['git','ls-tree','-r','-z',BASELINE,'--',*historical_paths],cwd=ROOT)
    entries=[]
    for record in tree.split(b'\0'):
        if not record:continue
        header,path=record.split(b'\t');mode,kind,blob=header.decode().split()
        check(kind=='blob','historical object is a file')
        entries.append((path.decode('utf-8'),blob))
    check(len(entries)==667,'667 historical source and firmware identities retained')
    migration=assert_baseline_equivalence(ROOT,BASELINE,entries)
    check(migration['files_compared']==len(entries),'every historical identity checked after authorized branding migration')
    historic_digest=hashlib.sha256(''.join(path+' '+blob+'\n' for path,blob in entries).encode()).hexdigest()

    inputs=json.loads((PACKAGE/'package-models/package-inputs.json').read_text(encoding='utf-8'))
    topology=json.loads((PACKAGE/'package-models/verification.json').read_text(encoding='utf-8'))
    input_models={m['name']:m for m in inputs['models']}
    check(len(topology['models'])==len(input_models)==8,'eight declared nominal package models')
    models=[]
    for model in topology['models']:
        name=model['name'];source=ROOT/model['source_footprint'];item=input_models[name]
        check(sha(source,True)==model['source_sha256_lf']==item['source_sha256_lf'],'current package footprint source '+name)
        check(model['source_footprint']==item['source_footprint'],'package input/topology source identity '+name)
        footprint=loads(source.read_text(encoding='utf-8'))
        # Paste-only stencil windows are not additional metal contacts. The
        # nominal package producer likewise models only numbered copper lands.
        pads=[pad for pad in subs(footprint,'pad') if str(pad[1]) and any(str(layer).endswith('.Cu') for layer in sub(pad,'layers')[1:])]
        check(len(pads)==model['actual_pad_count']==len(item['pads']),'actual package copper pad count '+name)
        for pad,declared in zip(pads,item['pads']):
            at=sub(pad,'at');size=sub(pad,'size')
            check(str(pad[1])==declared['number'],'nominal model pad identity '+name)
            check(all(abs(float(a)-float(b))<1e-7 for a,b in zip(at[1:3],[declared['x_mm'],declared['y_mm']])),'nominal model exact pad centres '+name)
            check(all(abs(float(a)-float(b))<1e-7 for a,b in zip(size[1:3],[declared['width_mm'],declared['height_mm']])),'nominal model exact pad dimensions '+name)
        step=PACKAGE/'package-models'/model['STEP'];fcstd=PACKAGE/'package-models'/model['native']
        check(sha(step)==model['STEP_sha256'],'package STEP topology receipt binding '+name)
        check(model['valid'] and model['volume_mm3']>0 and model['exported_solids']>=model['actual_pad_count']+1,'saved nominal package topology '+name)
        check(len(model['bound_dimensions_mm'])==3 and all(v>0 for v in model['bound_dimensions_mm']),'nominal package positive dimensions '+name)
        check(step.read_text(encoding='utf-8').startswith('ISO-10303-21;'),'actual package STEP file '+name)
        with zipfile.ZipFile(fcstd) as archive:
            check(archive.testzip() is None and 'Document.xml' in archive.namelist(),'intact native FreeCAD document '+name)
        models.append({'name':name,'pads':model['actual_pad_count'],'solids':model['exported_solids'],
                       'source_footprint_sha256_lf':sha(source,True),'STEP_sha256':sha(step),'FCStd_sha256':sha(fcstd)})

    boards={}
    for name,board in populated['boards'].items():
        directory=PACKAGE/'exports'/name;geometry=json.loads((directory/'geometry-verification.json').read_text(encoding='utf-8'))
        step=directory/'populated.step'
        check(geometry['STEP_sha256']==sha(step),'current actual populated STEP geometry binding '+name)
        check(geometry['valid'] and geometry['volume_mm3']>0,'saved actual populated topology '+name)
        check(geometry['solids']>=board['fitted_components']+1,'every fitted component plus board has solids '+name)
        check(geometry['nominal_geometry_only'] and not geometry['manufacturing_tolerance_or_physical_performance_qualified'],'topology evidence limit '+name)
        check(all(v==0 for v in board['drc'].values()),'every native board DRC finding count zero '+name)
        boards[name]={key:board[key] for key in ['schematic_components','fitted_components','electrical_pins','segments','vias','pcb_sha256_lf','xml_sha256_lf','drc']}
        boards[name].update(STEP_sha256=geometry['STEP_sha256'],valid_reimported_solids=geometry['solids'],dimensions_mm=geometry['dimensions_mm'])

    # Bind authored inputs and saved native evidence, including all child
    # schematic files. Export receipts themselves bind every PNG/SVG/Gerber;
    # checking those separately above avoids a duplicate bulky artifact list.
    bound={Path(__file__),ROOT/'scripts/project_branding.py',ROOT/'.github/workflows/verify.yml',PACKAGE/'power-overlay.json',
           PACKAGE/'power_overlay.py',PACKAGE/'verify_power.py',PACKAGE/'verify_exports.py',
           PACKAGE/'export_boards.py',PACKAGE/'verify_step_geometry.py',
           PACKAGE/'integration/system.json',PACKAGE/'integration/harness.json',
           PACKAGE/'integration/integration-changes.json',PACKAGE/'integration/verification.json',
           PACKAGE/'integration/populated-verification.json',PACKAGE/'integration/visual-review.json',
           PACKAGE/'integration/verify_integration.py',PACKAGE/'integration/verify_populated_boards.py',
           PACKAGE/'integration/sexp.py',PACKAGE/'integration/build_integration.py',
           PACKAGE/'firmware-profile/verify_bt40f.py',PACKAGE/'firmware-profile/verification.json',
           PACKAGE/'firmware-profile/build-receipt.json',PACKAGE/'package-models/package-inputs.json',
           PACKAGE/'package-models/verification.json',PACKAGE/'package-models/build_packages.py',
           PACKAGE/'package-models/extract_packages.py',ROOT/'docs/stage4/integrated-pcb-wiring.csv',
           ROOT/'docs/stage4/integrated-pcb-controller-wiring.csv'}
    for base in [PACKAGE/'integration/master',PACKAGE/'integration/boards',PACKAGE/'boards']:
        for path in base.rglob('*'):
            if path.is_file() and (path.suffix in ['.kicad_sch','.kicad_sym','.kicad_pcb','.kicad_pro','.kicad_mod'] or path.name in ['drc.json','erc.json','drc-binding.json','sym-lib-table','fp-lib-table']):bound.add(path)
    for name in populated['boards']:
        bound.update(PACKAGE/'exports'/name/f for f in ['export-receipt.json','geometry-verification.json'])
    hashes={path.relative_to(ROOT).as_posix():sha(path,True) for path in sorted(bound)}
    power=json.loads((PACKAGE/'power-overlay.json').read_text(encoding='utf-8'))
    return {'schema':'scci_rh.stage4.integrated-pcb-final-verification.v1','review_date':'2026-10-28',
            'original_design_review_date':'2026-10-16',
            'passed':True,'scope':'Digital modular artificial-load reference; no fabrication, measured hardware or biological qualification',
            'checkpoint_assertions':checks,'native_integration_assertions':integration['assertions'],
            'populated_board_assertions':populated['assertions'],'BT40F_firmware_assertions':firmware['checks'],
            'power_audit':power_stdout,'power_reproduction':reproduction_stdout,'export_audit':export_stdout,
            'totals':totals,'master_sheets':80,'harness_rows':258,'boards':boards,'nominal_package_models':models,
            'historical_sources':{'baseline_commit':BASELINE,'files_compared':len(entries),
                                  'path_and_blob_manifest_sha256':historic_digest,
                                  'authorized_brand_migration':migration},
            'conditional_power':{'HOST_3V3_cap_mA':power['HOST_3V3_new_cap_A']*1000,
                                 'HOST_3V3_allocated_mA':power['allocated_A']*1000,
                                 'active_W':power['active_W'],'runtime_h':power['runtime_h'],
                                 'measured':False,'compact_implant_thermal_2K_earned':False},
            'source_and_native_evidence_sha256_lf':hashes,
            'limits':['Actual saved source, native circuit, PCB pad and current native DRC-bound digital evidence',
                      'Saved FreeCAD topology checks are hash-bound here; no native CAD runtime is required by portable CI',
                      'Target firmware compiled, not flashed or physically timed; implemented lower acquisition rates and gaps remain',
                      'No implant miniaturization, clinical isolation, analog precision, retained learning or physiological benefit is established']}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-report',action='store_true');args=parser.parse_args()
    result=audit()
    if args.write_report:REPORT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    elif result!=json.loads(REPORT.read_text(encoding='utf-8')):raise AssertionError('Checkpoint differs from the saved reviewed revision; inspect before --write-report')
    print(json.dumps({k:result[k] for k in ['passed','checkpoint_assertions','native_integration_assertions','populated_board_assertions','BT40F_firmware_assertions','totals']},sort_keys=True))

if __name__=='__main__':main()
