"""Repair explicit path/hash receipt bindings after an interrupted name migration.

Default is a read-only plan. --apply changes only hash strings and adjacent file
byte counts in recognized metadata records. Measurements, budgets, geometry and
algorithm values are not rewritten. Ambiguous paths or representations remain
reported and unchanged. Text formatting is retained; gzip is deterministic.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'provenance/project-name-migration.json','provenance/project-name-derivatives.json',
          'provenance/project-name-retirements.json','provenance/manifest.sha256'}
HASH=re.compile(r'^[0-9a-f]{64}$')
FIELDS={'source_sha256_lf','source_sha256','source_identity','source_hashes','source_hashes_lf',
        'artifact_sha256','artifact_hashes','inputs_bytes_sha256','bound_scci_rh_source_bytes_sha256',
        'input_normalized_hashes','source_and_native_evidence_sha256_lf','source_and_output_sha256_lf_for_text',
        'result_semantic_or_binary_hashes','input_hashes','artifact_sha256_lf','source_bindings','files'}
RECORD_KEYS={'sha256':'','sha256_lf':'','source_sha256':'source','source_sha256_lf':'source',
             'native_sha256':'native','step_sha256':'step','STEP_sha256':'STEP','svg_sha256':'svg',
             'exporter_sha256_lf':'exporter','inspector_sha256_lf':'inspector',
             'contract_canonical_sha256':'contract','xml_sha256_lf':'xml',
             'source_footprint_sha256_lf':'source_footprint'}

def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(data):return json.dumps(json.loads(data.decode('utf-8-sig')),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()

def resolve(name,document,inventory):
 if not isinstance(name,str) or name.startswith(('https:','http:','data:')):return None,'not a local path'
 if '\\' in name:name=name.replace('\\','/')
 if name.startswith(('E:/','C:/','${')):return None,'absolute or environment-dependent path'
 candidates=[]
 direct=(ROOT/name).resolve()
 if direct.is_relative_to(ROOT) and direct.is_file():return direct,None
 for base in [document.parent,*document.parents]:
  if not base.is_relative_to(ROOT):break
  candidate=(base/name).resolve()
  if candidate.is_relative_to(ROOT) and candidate.is_file():candidates.append(candidate)
 if len(set(candidates))==1:return candidates[0],None
 if len(set(candidates))>1:return None,'multiple document-relative files'
 if '/' not in name:
  matches=[ROOT/row['new_path'] for row in inventory['files'] if Path(row['new_path']).name==name and (ROOT/row['new_path']).is_file()]
  if len(set(matches))==1:return matches[0],None
  if len(set(matches))>1:return None,'multiple exact basename matches'
 return None,'local file not found'

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');parser.add_argument('--report',type=Path)
 parser.add_argument('--file',action='append',help='Review only these repository-relative JSON/gzip receipts')
 args=parser.parse_args();inventory=json.loads((ROOT/'provenance/project-name-migration.json').read_text());cache={};changes=[];unresolved=[]
 names=args.file or [r['new_path'] for r in inventory['files'] if Path(r['new_path']).suffix.lower() in {'.json','.gz'}]
 for number,name in enumerate(names):
  if name in EXCLUDED or name.startswith('inspector/vendor/'):continue
  path=ROOT/name
  if not path.is_file():continue
  data=path.read_bytes();raw=gzip.decompress(data) if path.suffix=='.gz' else data
  try:text=raw.decode('utf-8-sig')
  except UnicodeError:continue
  proposals=defaultdict(set);binding_sources=defaultdict(set)
  def propose(key,old,new,source):
   if old!=new:
    proposals[(key,str(old))].add(str(new));binding_sources[(key,str(old))].add(source)
  def file_hash(target,field,parent):
   mode='canonical' if 'canonical' in field or (field=='result_semantic_or_binary_hashes' and target.suffix=='.json') else 'lf' if '_lf' in field or 'normalized' in field or field in {'source_identity','source_hashes','source_sha256','source_bindings'} else 'raw'
   # These build receipts explicitly declare LF-normalized text artifacts.
   if field=='artifact_sha256' and target.suffix not in {'.elf','.bin','.zip','.glb','.pdf','.png','.jpg','.blend','.FCStd'} and 'LF-normalized' in str(parent.get('artifact_hash_policy','')):mode='lf'
   identity=(str(target),target.stat().st_mtime_ns,target.stat().st_size,mode)
   if identity not in cache:
    content=target.read_bytes()
    if mode=='lf':content=content.replace(b'\r\n',b'\n')
    if mode=='canonical':
     if len(content)>=16_000_000:raise ValueError('canonical JSON exceeds metadata bound')
     content=canonical(content)
    cache[identity]=digest(content)
   return cache[identity]
  def binding(key,value,field,parent):
   target,error=resolve(key,path,inventory)
   if target is None:
    if '/' in key or '.' in key:unresolved.append({'document':name,'field':field,'path':key,'reason':error})
    return
   try:expected=file_hash(target,field,parent)
   except (ValueError,UnicodeError):return
   propose(key,value,expected,target.relative_to(ROOT).as_posix())
  def walk(value,context=''):
   if isinstance(value,dict):
    for key,child in value.items():
     if key in FIELDS and isinstance(child,dict):
      for reference,old in child.items():
       if isinstance(old,str) and HASH.fullmatch(old):binding(reference,old,key,value)
     if key in RECORD_KEYS and isinstance(child,str) and HASH.fullmatch(child):
      associated=RECORD_KEYS[key]
      references=[value.get(associated)] if associated else [value.get(k) for k in ('path','file','svg','source')]
      references=[r for r in references if isinstance(r,str)]
      if references:
       target,error=resolve(references[0],path,inventory)
       if target:
        try:propose(key,child,file_hash(target,key,value),target.relative_to(ROOT).as_posix())
        except (ValueError,UnicodeError):pass
     walk(child,key)
    # File byte lengths are metadata only when the same record carries a
    # resolvable actual file path and its hash. No other numeric field changes.
    if 'bytes' in value and isinstance(value['bytes'],int) and any(k in value for k in ('sha256','sha256_lf')):
     reference=next((value.get(k) for k in ('path','file','svg') if isinstance(value.get(k),str)),None)
     if reference:
      target,_=resolve(reference,path,inventory)
      if target:propose('bytes',value['bytes'],target.stat().st_size,target.relative_to(ROOT).as_posix())
   elif isinstance(value,list):
    for child in value:walk(child,context)
  if len(raw)<=16_000_000:
   try:walk(json.loads(text))
   except ValueError:continue
  else:
   # Giant scientific gzip records retain exact formatting and numeric data;
   # decode only explicitly named small hash dictionaries, never whole arrays.
   expression=re.compile(r'"('+ '|'.join(re.escape(field) for field in sorted(FIELDS))+r')"\s*:\s*')
   decoder=json.JSONDecoder()
   for match in expression.finditer(text):
    try:value,end=decoder.raw_decode(text,match.end())
    except ValueError:continue
    if isinstance(value,dict):walk({match[1]:value})
  updated=text;applied=[]
  for (key,old),values in proposals.items():
   if len(values)!=1:
    unresolved.append({'document':name,'field':key,'old':old,'candidates':sorted(values),'reason':'same key/value pair resolves ambiguously; not replaced'});continue
   new=next(iter(values));quoted=HASH.fullmatch(old) is not None
   prefix=json.dumps(key,ensure_ascii=False)
   expression=re.compile('('+re.escape(prefix)+r'\s*:\s*'+('"' if quoted else '')+')'+re.escape(old)+(('"') if quoted else r'(?=\s*[,}])'))
   updated,count=expression.subn(lambda m:m[1]+new+('"' if quoted else ''),updated)
   if count:applied.append({'field':key,'previous':old,'current':new,'occurrences':count,'actual_source_paths':sorted(binding_sources[(key,old)])})
  if applied:
   output=updated.encode('utf-8');output=gzip.compress(output,compresslevel=9,mtime=0) if path.suffix=='.gz' else output
   if args.apply:path.write_bytes(output)
   changes.append({'path':name,'before_sha256':digest(data),'after_sha256':digest(output),'bindings':applied})
  if number%100==0:print(json.dumps({'reviewed':number+1,'documents_with_updates':len(changes),'unresolved':len(unresolved)}),flush=True)
 report={'schema':'project-name-path-binding-repair.v1','applied':args.apply,'scope':'Explicit local path/hash and associated file byte-count metadata only; numeric model values untouched','changed_documents':changes,'unresolved_not_modified':unresolved}
 if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'documents_with_updates':len(changes),'unresolved':len(unresolved),'applied':args.apply}))

if __name__=='__main__':main()
