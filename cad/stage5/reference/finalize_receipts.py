"""Package large lossless STEP exports and bind nongeometric release metadata."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,zipfile
HERE=Path(__file__).resolve().parent
C=json.loads((HERE/'contract.json').read_text());R=json.loads((HERE/'producer-geometry.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
C['exploded_transforms']={}
for r in R['objects']:
    dz=0
    if r['category'] in ('populated_board','tray','tray_pull','board_standoff','board_screw'):
        dz=max(0,round((r['bbox_mm'][2]-12)/50))*35+(15 if r['category']=='populated_board' else 0)
    elif r['label']=='Lid' or r['category']=='lid_screw':dz=165
    C['exploded_transforms'][r['label']]=[0,-50 if r['label']=='FrontPanel' else 0,dz]
C['compressed_step']='cad/stage5/reference/SCCI_RH_reference_assembly.step.zip'
C['compressed_exploded_step']='cad/stage5/reference/SCCI_RH_reference_exploded.step.zip'
C['step']=C['compressed_step'];C['step_archive']=C['step'];C['step_member']='SCCI_RH_reference_assembly.step'
C['exploded_step']=C['compressed_exploded_step'];C['exploded_step_archive']=C['exploded_step'];C['exploded_step_member']='SCCI_RH_reference_exploded.step'
C['step_sha256_uncompressed']=sha(HERE/C['step_member'])
C['exploded_step_sha256_uncompressed']=sha(HERE/C['exploded_step_member'])
(HERE/'contract.json').write_text(json.dumps(C,indent=2)+'\n')
R['builder_sha256_at_geometry_build']=R['builder_sha256'];R['builder_sha256_current']=sha(HERE/'build_reference.py')
R['nongeometric_metadata_update']='Added exact exploded transforms, deterministic lossless STEP zip exports and source/output hashes after the geometry build; no native shape or placement changed'
R['contract_sha256']=sha(HERE/'contract.json');R['metadata_finalizer_sha256']=sha(Path(__file__))
vol=defaultdict(float)
for r in R['objects']:vol[r['category']]+=r['volume_mm3']
R['solid_volume_allocation_mm3']=dict(vol);R['total_solid_volume_mm3']=sum(vol.values());R['mass_not_inferred']='Material grades and composite source board densities unqualified; solid volumes are reported without claiming measured mass'
R['outputs']={}
for filename in ['SCCI_RH_reference_assembly.step','SCCI_RH_reference_exploded.step']:
    source=HERE/filename;target=HERE/(filename+'.zip')
    info=zipfile.ZipInfo(filename,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
    archive_matches=False
    if target.exists():
        with zipfile.ZipFile(target) as z:
            archive_matches=z.namelist()==[filename] and hashlib.sha256(z.read(filename)).hexdigest()==sha(source)
    if not archive_matches:
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.writestr(info,source.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(target) as z:
        assert z.namelist()==[filename];assert hashlib.sha256(z.read(filename)).hexdigest()==sha(source)
    R['outputs'][filename]=dict(sha256=sha(source),bytes=source.stat().st_size,lossless_archive=target.name,archive_sha256=sha(target),archive_bytes=target.stat().st_size)
for filename in ['SCCI_RH_reference_assembly.FCStd','SCCI_RH_reference_mechanical.step','mechanical-bom.csv','board-datums.json','mcp-inspection.json']:
    p=HERE/filename
    if p.exists():R['outputs'][filename]=dict(sha256=sha(p),bytes=p.stat().st_size)
R['mechanical_stl']={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted((HERE/'stl').glob('*.stl'))}
(HERE/'producer-geometry.json').write_text(json.dumps(R,indent=2)+'\n')
print('Finalized exploded mapping for',len(C['exploded_transforms']),'parts; lossless large STEP archives verified')
