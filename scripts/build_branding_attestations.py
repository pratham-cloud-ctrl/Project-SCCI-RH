"""Classify migrated artifacts and attest only explicitly proved derivatives.

Default is a read-only plan (optionally --report). --write-known writes separate
per-artifact proof records plus the derivative index. Unknown differences remain
unknown; this tool never grants an extension-wide waiver for source or results.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

from project_branding import compare_renamed_bytes, rename_text, retired_artifact

ROOT=Path(__file__).resolve().parents[1]
HEX=re.compile(r'(?<![0-9a-fA-F])([0-9a-f]{64}|[0-9a-f]{40})(?![0-9a-fA-F])')
MANUAL_SOURCE_REVIEWS={
 'scripts/verify_integrated_pcb.py':'Original 667-file selection/count and electrical/numeric assertions retained; exact immutable-blob branding/attestation adapter replaces byte-unchanged claim.',
 'scripts/verify_stage5_mechanics.py':'Original historical scope, topology/geometry/electrical checks retained; explicit branding adapter and unique exact-digest archive source resolution added.',
 'scripts/verify_stage6_release.py':'Original completed baseline identities retained; explicit branding migration, 2.1 release recognition and adapter binding added; no biological claims expanded.',
 'scripts/verify_viewer_navigation.py':'Original source inventory and link/anchor checks retained; explicit branding-equivalence comparison and current audit date added.',
 'scripts/inspector/verify_inspector.py':'Original model topology/identity, native circuit, package and link checks retained; explicit branding adapter/current audit date added.',
 'scripts/stage3_motor_convergence.py':'Frozen Git path resolves to actual immutable object, then namespace-only migration occurs in memory; actual frozen worlds/captures independently reproduced exactly.',
 'electronics/stage4/integrated-pcb/firmware-profile/verify_bt40f.py':'Actual recompiled ELF flash extent reviewed at54072; ELF/HEX/BIN parity, configurations and hardware limits retained; audit date updated.',
 'scripts/verify_nrf5340.py':'Existing independent ELF/source/GPIO/peripheral assertions retained; audit date updated and report regenerated from recompiled image.',
 'firmware/nrf5340/uart-revision/verify_revision.py':'Actual rebuild date and original implementation date distinguished; source/frame/ELF/HEX/BIN/configuration assertions retained.',
 'firmware/nrf5340/tests/check_runtime.py':'Only branding and actual rerun/original design date metadata changed; actual compiled75-scenario713-assertion production-core test reran successfully.',
 'firmware/nrf5340/uart-revision/tests/check_uart_framing.py':'Only branding and actual rerun/original design date metadata changed;1172 current scenarios passed and334 historical corruption failures reproduced.',
}
MANUAL_SOURCE_SHA256_LF={
 "scripts/verify_integrated_pcb.py": "84704f82b069e375ca7dbf9cb6fa2ad529ff26d6f0da0d9f3d074ca0c910153c",
 "scripts/verify_stage5_mechanics.py": "bf95a3821c5a8870abc083fa5b1888ecb84c82c97a4cc55c0c0aeaa943e1ea1b",
 "scripts/verify_stage6_release.py": "86d789b0c7864932f46c166b0c3754820ad62f5a94312f8b757e647afe0d8d22",
 "scripts/verify_viewer_navigation.py": "c31d9beaabf059eda43e840c9ea769d28ff5733b97201b6ba8f836fd58796e4c",
 "scripts/inspector/verify_inspector.py": "5240f26faf07ae25f9a0f0ad003e31983f29538b4b6c2a8b7b5471a39e75ad87",
 "scripts/stage3_motor_convergence.py": "3d343ac5294d9f696c678af24e70af3840b35da0dea8d66a2261eceeb5c2fb70",
 "electronics/stage4/integrated-pcb/firmware-profile/verify_bt40f.py": "9f761c415da4089e775b86858eac2be3b4d12f60afa9bb09afb2a82fef359689",
 "scripts/verify_nrf5340.py": "8ae7aab3b754597114735df9e671de0e4f1874f5fe17c8427dbb074972fe4003",
 "firmware/nrf5340/uart-revision/verify_revision.py": "8de48e1d5ace0799fc2306cfaba063c52eab7fa04248a431d35e8aadeff7ba8d",
 "firmware/nrf5340/tests/check_runtime.py": "1e63adac9a07ae1e68b92b9f98e9dde2de78dcfd95a64e76fc8cf99e65a6ced5",
 "firmware/nrf5340/uart-revision/tests/check_uart_framing.py": "e23d19d863a8084a301cd0a64ee28a806a88720f30a566d56cc265ae691a3265"
}


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def masked(data):
 text=data.decode('utf-8-sig').replace('\r\n','\n')
 return HEX.sub(lambda m:'H'*len(m[0]) if not text[m.end():].startswith('.py.txt') else m[0],text)

def structural_hash_metadata_only(before,after):
 """Ignore JSON ordering, while retaining every non-digest value and key."""
 try:
  return json.loads(masked(rename_text(before.decode('utf-8-sig')).encode())) == json.loads(masked(after))
 except (UnicodeError,ValueError):return False

def finite_receipt_metadata(name,before,after):
 """Validate bounded receipt fields against the files they actually describe."""
 try:
  a=json.loads(rename_text(before.decode('utf-8-sig')));b=json.loads(after)
 except (UnicodeError,ValueError):return None
 if name in {'firmware/nrf5340/runtime-tests.json',
             'firmware/nrf5340/uart-revision/uart-framing-tests.json'}:
  if b.get('original_design_date')!=a.get('date') or b.get('date')!='2026-10-28':return None
  b.pop('original_design_date');b['date']=a['date']
  if structural_hash_metadata_only(json.dumps(a).encode(),json.dumps(b).encode()):
   return 'original_test_findings_preserved_actual_rerun_date_and_digest_metadata'
 if name.startswith('electronics/stage4/integrated-pcb/boards/') and name.endswith('/drc-binding.json'):
  native=read(ROOT/'provenance/rebrand-native-electrical-checks.json')
  row=next((r for r in native['boards'] if r['board']==b.get('board')),None)
  if row is None or not row.get('passed') or b.pop('actual_rebrand_revision_native_execution',None) is not True:return None
  for field,target in (('pcb_sha256_lf',row['source']),('drc_sha256_lf',row['drc_output'])):
   if b.get(field)!=sha((ROOT/target).read_bytes().replace(b'\r\n',b'\n')):return None
  if structural_hash_metadata_only(json.dumps(a).encode(),json.dumps(b).encode()):
   return 'unchanged_drc_findings_with_actual_native_reexecution_and_source_bindings'
 if name not in {'experiments/stage3/frozen-observer-pilot/artifact-manifest.json',
                 'experiments/stage3/observed-state-observer/artifact-manifest.json',
                 'provenance/stage5-reference-clearance/manifest.json'}:return None
 def visit(old,new):
  if isinstance(old,dict) and isinstance(new,dict):
   if set(old)!=set(new):raise ValueError('Non-metadata keys changed')
   if 'bytes' in old and old['bytes']!=new['bytes']:
    path=new.get('path');assert isinstance(path,str) and 'sha256' in new
    candidates=[p for p in (ROOT/path,(ROOT/name).parent/path) if p.is_file()]
    candidates=list(dict.fromkeys(p.resolve() for p in candidates));assert len(candidates)==1
    data=candidates[0].read_bytes();assert len(data)==new['bytes'] and sha(data)==new['sha256']
    new['bytes']=old['bytes']
   for key in old:visit(old[key],new[key])
  elif isinstance(old,list) and isinstance(new,list):
   assert len(old)==len(new)
   for x,y in zip(old,new):visit(x,y)
 try:visit(a,b)
 except (ValueError,AssertionError,OSError):return None
 if structural_hash_metadata_only(json.dumps(a).encode(),json.dumps(b).encode()):
  return 'unchanged_package_content_records_with_exact_current_source_lengths_and_digests'
 return None

def evidence_index():
 result={}
 names=[p for p in (ROOT/'provenance').glob('rebrand-*.json') if p.name!='rebrand-receipt-bindings.json']
 def visit(value,proof):
  if isinstance(value,dict):
   name=value.get('path')
   if name:
    for key in ('after_sha256','sha256','current_sha256'):
     if isinstance(value.get(key),str):result.setdefault(name,[]).append((value[key],proof,key))
   if value.get('builder') and value.get('metadata_corrected_builder_sha256_lf'):
    result.setdefault(value['builder'],[]).append((value['metadata_corrected_builder_sha256_lf'],proof,'metadata_corrected_builder_sha256_lf'))
   for key in ('artifacts_sha256','artifact_sha256','files_sha256',
               'fabrication_output_sha256_lf','actual_artifacts_sha256'):
    if isinstance(value.get(key),dict):
     for name,digest in value[key].items():
      if isinstance(digest,str):result.setdefault(name,[]).append((digest,proof,key))
   # Native checks identify their report by output rather than generic path.
   # Keep the exact pair; never attach an unrelated digest to a file.
   for source_key,digest_key in (('drc_output','drc_sha256_lf'),
                                 ('output','output_sha256_lf'),
                                 ('pdf','pdf_sha256')):
    if isinstance(value.get(source_key),str) and isinstance(value.get(digest_key),str):
     result.setdefault(value[source_key],[]).append((value[digest_key],proof,digest_key))
   for child in value.values():visit(child,proof)
  elif isinstance(value,list):
   for child in value:visit(child,proof)
 for p in names:
  try:visit(read(p),p)
  except (ValueError,OSError):pass
 # Independently parsed target checks bind the actual new artifacts in their
 # actual source-build receipts; this does not treat the old image as unchanged.
 for name in ('provenance/stage4-nrf5340-build.json','electronics/stage4/integrated-pcb/firmware-profile/build-receipt.json','firmware/nrf5340/uart-revision/build-receipt.json'):
  p=ROOT/name
  if p.is_file():visit(read(p),p)
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-known',action='store_true');parser.add_argument('--report',type=Path)
 parser.add_argument('--only',action='append',help='Review only this exact repository path; merge current records into an existing index')
 args=parser.parse_args();inventory=read(ROOT/'provenance/project-name-migration.json');evidence=evidence_index();rows=[];unknown=[];counts=Counter()
 proofdir=ROOT/'provenance/project-name-derivative-proofs'
 if args.write_known:proofdir.mkdir(parents=True,exist_ok=True)
 with subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE) as git:
  try:
   for number,item in enumerate(inventory['files']):
    if args.only and item['new_path'] not in args.only:continue
    if number%250==0:print(json.dumps({'reviewing':number+1,'total':len(inventory['files']),'known_derivatives':len(rows),'unknown':len(unknown)}),flush=True)
    name=item['new_path'];path=ROOT/name
    git.stdin.write((inventory['original_commit']+':'+item['path']+'\n').encode());git.stdin.flush()
    head=git.stdout.readline().decode().strip().split();assert len(head)==3 and head[1]=='blob',item['path']
    old=git.stdout.read(int(head[2]));assert git.stdout.read(1)==b'\n'
    if not path.is_file():
     if retired_artifact(ROOT,name,old):counts['explicitly_retired']+=1;continue
     unknown.append({'path':name,'reason':'missing non-retired artifact'});continue
    current=path.read_bytes();rule=compare_renamed_bytes(old,current,path.suffix)
    if rule:counts[rule]+=1;continue
    validation=None;links=[]
    for expected,proof,key in evidence.get(name,[]):
     if expected in {sha(current),sha(current.replace(b'\r\n',b'\n'))}:
      validation='explicit_digest_bound_regeneration_or_review_evidence'
      links=[{'path':proof.relative_to(ROOT).as_posix(),'sha256_lf':sha(proof.read_bytes().replace(b'\r\n',b'\n'))}];break
    if validation is None:
     try:
      before=gzip.decompress(old) if path.suffix=='.gz' else old
      after=gzip.decompress(current) if path.suffix=='.gz' else current
      if masked(rename_text(before.decode('utf-8-sig')).encode())==masked(after):
       validation='branding_and_fixed_length_digest_metadata_only'
     except (UnicodeError,ValueError,OSError,EOFError):pass
    if validation is None and path.suffix=='.json' and structural_hash_metadata_only(old,current):
     validation='branding_digest_metadata_and_json_order_only'
    if validation is None and path.suffix=='.json':
     validation=finite_receipt_metadata(name,old,current)
    if validation is None and name in {
        'electronics/simulation/ngspice_log.txt',
        'electronics/simulation/ngspice_log_high_supply_small_C_min_resistors.txt',
        'electronics/simulation/ngspice_log_precharged_negative_2V.txt',
        'electronics/simulation/ngspice_log_precharged_positive_2V.txt',
        'electronics/simulation/ngspice_log_small_Cdl.txt'}:
     # These five original Windows solver logs contain CR-CR-LF endings.
     # Compare every complete nonblank line, including every numeric result.
     before=rename_text(old.decode('utf-8-sig')).replace('\r','')
     after=current.decode('utf-8-sig').replace('\r','')
     if [s for s in before.splitlines() if s] == [s for s in after.splitlines() if s]:
      validation='branding_and_solver_log_line_endings_only'
    if (validation is None and name in MANUAL_SOURCE_REVIEWS and
        sha(current.replace(b'\r\n',b'\n')) == MANUAL_SOURCE_SHA256_LF[name]):
     validation='reviewed_branding_verifier_adaptation'
    if validation is None:
     unknown.append({'path':name,'reason':'not exact branding/hash-only and no matching regenerated-artifact evidence','original_sha256':sha(old),'current_sha256':sha(current)});continue
    proof={'schema':'project-name-per-artifact-equivalence.v1','date':'2026-10-28','passed':True,'path':name,
           'original_commit':inventory['original_commit'],'original_sha256':sha(old),'current_sha256':sha(current),
           'method':validation,'scope':'Authorized name migration; no new physical or biological validation',
           'review':MANUAL_SOURCE_REVIEWS.get(name,''),'independent_evidence':links}
    proofpath=proofdir/(sha(name.encode())[:20]+'.json');proofdata=(json.dumps(proof,indent=2)+'\n').encode()
    if args.write_known:proofpath.write_bytes(proofdata)
    rows.append({'path':name,'original_sha256_lf':item['sha256_lf'],'current_sha256_lf':sha(current.replace(b'\r\n',b'\n')),
                 'validation':{'passed':True,'method':validation,'evidence':[{'path':proofpath.relative_to(ROOT).as_posix(),'sha256_lf':sha(proofdata)}]}})
    counts[validation]+=1
    if number%250==0:print(json.dumps({'reviewed':number+1,'attested_known':len(rows),'unknown':len(unknown)}),flush=True)
  finally:
   git.stdin.close();git.stdout.close();git.wait()
 report={'schema':'project-name-attestation-plan.v1','counts':dict(counts),'known_derivatives':len(rows),'unknown':unknown,'scope':'Unknown differences are not approved or skipped'}
 if args.write_known:
  if args.only and (ROOT/'provenance/project-name-derivatives.json').is_file():
   existing=read(ROOT/'provenance/project-name-derivatives.json')
   assert existing['original_commit']==inventory['original_commit']
   rows=[r for r in existing['files'] if r['path'] not in args.only]+rows
  (ROOT/'provenance/project-name-derivatives.json').write_text(json.dumps({'schema':'project-name-derivatives.v1','original_commit':inventory['original_commit'],'files':rows},indent=2)+'\n')
 if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))

if __name__=='__main__':main()
