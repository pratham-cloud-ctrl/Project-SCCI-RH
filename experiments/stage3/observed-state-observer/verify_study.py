"""Portable integrity, saved-data and independent-equation verification.

Runs the exact frozen scripts in a disposable original-layout scratch root.
It never changes or regenerates the packaged evidence. --reproduce is optional.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parent
REPOSITORY = PACKAGE.parents[2]
MANIFEST_NAME = 'artifact-manifest.json'
EXPECTED_FROZEN = {
    'observed_state_observer_12oct.py':'203a5bdd90ae20a67f1b6475b47c31a73880d96a5c4434957b51f28a2f767c44',
    'observer-method-freeze-12oct.json':'1157a4490d4455faba6773fe447560b22c218db852efe65fc95c180f373dce7f',
    'observer-confirmation-12oct.py':'7c7729caa49cac204c2edc8be81bc9ba11e3ae6b4ec2bd26ac129c18b087978d',
    'observer-confirmation-protocol-12oct.md':'32cbc703e850983dc0032a1b1000fac6d68e323b503917f03c2bddd6cac3f608',
    'observer-confirmation-freeze-12oct.json':'6e4725e801f3e7e9eb88d0c9e40520c6ea0b462f9776cf4adb5831d6d6dcbac0',
    'observer-confirmation-summary-12oct.json':'89d79c3d3eb3dafb62964ed4d15ae922c4a1b7e775ea612d8b9d7d1c0cb65a59',
}
PINS = {'numpy':'2.3.5','scipy':'1.18.1'}
PYTHON_PIN = (3,12,14)
AUDITS = (
    ('observer-independent-check-12oct.py','observer-independent-check-12oct.json'),
    ('observer-saved-data-audit-12oct.py','observer-saved-data-audit-12oct.json'),
    ('observer-confirmation-saved-audit-12oct.py','observer-confirmation-saved-audit-12oct.json'),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def semantic_compare(saved, fresh, path='root'):
    """All findings/counts/identities remain checked; only wall time is volatile."""
    if isinstance(saved,dict) and isinstance(fresh,dict):
        if set(saved) != set(fresh): raise AssertionError(f'{path}: key mismatch')
        for key in saved:
            if key == 'elapsed_wall_seconds': continue
            semantic_compare(saved[key],fresh[key],path+'.'+key)
    elif isinstance(saved,list) and isinstance(fresh,list):
        if len(saved) != len(fresh): raise AssertionError(f'{path}: length mismatch')
        for index,(a,b) in enumerate(zip(saved,fresh)):
            semantic_compare(a,b,f'{path}[{index}]')
    elif isinstance(saved,bool) or isinstance(fresh,bool):
        if type(saved) is not type(fresh) or saved != fresh:
            raise AssertionError(f'{path}: decision mismatch')
    elif isinstance(saved,int) and isinstance(fresh,int):
        if saved != fresh: raise AssertionError(f'{path}: integer mismatch')
    elif isinstance(saved,(int,float)) and isinstance(fresh,(int,float)):
        # Covariance fields have squared-meter units; do not use a meter floor.
        atol = 1e-18 if '_m2' in path else 1e-11
        if (not math.isfinite(saved) or not math.isfinite(fresh)
                or not math.isclose(saved,fresh,rel_tol=2e-8,abs_tol=atol)):
            raise AssertionError(f'{path}: numeric mismatch {saved!r} vs {fresh!r}')
    elif saved != fresh:
        raise AssertionError(f'{path}: value mismatch')


def verify_manifest(package=PACKAGE):
    manifest = read_json(package/MANIFEST_NAME)
    listed = {}
    for record in manifest['files']:
        relative = record['path']
        if relative in listed: raise AssertionError(f'duplicate manifest path {relative}')
        path = package/relative
        if not path.resolve().is_relative_to(package.resolve()) or not path.is_file():
            raise AssertionError(f'invalid manifest path {relative}')
        if path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
            raise AssertionError(f'package integrity mismatch: {relative}')
        listed[relative] = record
    actual = {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file()
              and p.name != MANIFEST_NAME and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    if actual != set(listed): raise AssertionError('package inventory mismatch')
    for name,expected in EXPECTED_FROZEN.items():
        if digest(package/'frozen'/name) != expected:
            raise AssertionError(f'approved freeze changed: {name}')
    return manifest


def verify_environment():
    if sys.version_info[:3] != PYTHON_PIN:
        raise RuntimeError(f'Python {".".join(map(str,PYTHON_PIN))} required; got {sys.version.split()[0]}')
    for name,expected in PINS.items():
        actual = importlib.metadata.version(name)
        if actual != expected: raise RuntimeError(f'{name} {expected} required; got {actual}')


def verified_sources(source_root: Path):
    freeze = read_json(PACKAGE/'frozen/observer-confirmation-freeze-12oct.json')
    expected = freeze['full_scci_rh_source_bytes_sha256']
    source_root = source_root.resolve()
    actual = {p:digest(source_root/p) for p in expected if (source_root/p).is_file()}
    if actual != expected:
        differences = sorted(set(actual)^set(expected) |
            {p for p in set(actual)&set(expected) if actual[p] != expected[p]})
        raise AssertionError('frozen src/scci_rh bytes differ: '+', '.join(differences))
    extras = {p.relative_to(source_root).as_posix()
              for p in (source_root/'src/scci_rh').rglob('*.py')} - set(expected)
    if extras:
        print(f'Excluded {len(extras)} later unbound source files from scratch.')
    return expected


def run_exact(scratch: Path, script: str, env: dict, arguments=(), *, stream=False):
    command = [sys.executable,'-X','utf8',str(scratch/'tmp'/script),*arguments]
    result = subprocess.run(command,cwd=scratch,env=env,text=True,encoding='utf-8',
                            stdout=None if stream else subprocess.PIPE,stderr=None if stream else subprocess.PIPE)
    if result.returncode:
        if not stream:
            print((result.stdout or '')[-12000:])
            print((result.stderr or '')[-12000:],file=sys.stderr)
        raise RuntimeError(f'{script} failed with exit code {result.returncode}')


def verify(source_root=REPOSITORY, *, reproduce=False):
    manifest = verify_manifest()
    verify_environment()
    sources = verified_sources(Path(source_root))
    originals = {record['path']:record['sha256'] for record in manifest['files']}
    with tempfile.TemporaryDirectory(prefix='scci_rh-observed-state-') as name:
        scratch = Path(name).resolve()
        (scratch/'tmp').mkdir()
        for path in sorted((PACKAGE/'frozen').iterdir()):
            if not path.is_file(): raise AssertionError('unexpected frozen subdirectory')
            shutil.copyfile(path,scratch/'tmp'/path.name)
        # Copy only bound source text, never caches or unbound bytecode.
        for relative,expected in sources.items():
            destination = scratch/relative
            if not destination.resolve().is_relative_to(scratch): raise AssertionError('source path escaped scratch root')
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(Path(source_root)/relative,destination)
            if digest(destination) != expected: raise AssertionError('source changed while copying')
        env = os.environ.copy()
        env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                   NUMEXPR_NUM_THREADS='1',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=os.pathsep.join((str(scratch/'src'),str(scratch/'tmp'))))
        for script,output in AUDITS:
            run_exact(scratch,script,env)
            semantic_compare(read_json(PACKAGE/'frozen'/output),read_json(scratch/'tmp'/output),output)
            print('Passed exact frozen audit: '+script)
        if reproduce:
            summary = read_json(PACKAGE/'frozen/observer-confirmation-summary-12oct.json')
            run_exact(scratch,'observer-confirmation-12oct.py',env,
                ('--check-after-root-review',summary['review_reference']),stream=True)
        # Scratch outputs may differ in newline/walltime; original frozen bytes never do.
        for relative,expected in originals.items():
            if digest(PACKAGE/relative) != expected: raise AssertionError('original package changed during verification')
    print(f'Verified {len(originals)} package files and {len(sources)} bound source files; originals unchanged.')
    print('Finite sensor-noise-only no-dose result: 11.353736 mm / 15 mm, all 32 grid captures; no pilot replacement.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=REPOSITORY,
        help='Checkout containing the exact src/scci_rh byte manifest; defaults to this repository')
    parser.add_argument('--reproduce',action='store_true',
        help='Additionally regenerate the same frozen confirmation pairs in scratch; no new independent-noise experiment')
    args = parser.parse_args()
    verify(args.source_root,reproduce=args.reproduce)


if __name__ == '__main__':
    main()
