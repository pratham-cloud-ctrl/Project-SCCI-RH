"""Run the full project unit suite and bind the observed result to source files."""
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def hashes(files):
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for p in sorted(files)}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite): yield from flatten(item)
        else: yield item


if __name__ == '__main__':
    models = list((ROOT/'src/scci_rh').rglob('*.py'))
    tests = list((ROOT/'tests').glob('test_*.py'))
    before_models, before_tests = hashes(models), hashes(tests)
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    counts = {}
    for test in flatten(suite):
        module = test.__class__.__module__
        counts[module] = counts.get(module, 0)+1
    start = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    if before_models != hashes((ROOT/'src/scci_rh').rglob('*.py')) or before_tests != hashes((ROOT/'tests').glob('test_*.py')):
        raise RuntimeError('Sources changed during verification; no test receipt written')
    receipt = {'schema': 'scci_rh.stage3.unit-test-run.v2', 'date': '2026-10-12',
               'scope': 'Full project unit suite, including earlier subsystem and architecture checks; no human or physical-device qualification.',
               'command': 'python scripts/record_stage3_tests.py',
               'observed_result': {'tests_run': result.testsRun, 'failures': len(result.failures),
                                   'errors': len(result.errors), 'status': 'OK' if result.wasSuccessful() else 'FAILED',
                                   'elapsed_s': round(elapsed, 3)},
               'runtime': {'python': platform.python_version(), 'platform': platform.system()},
               'test_counts_by_module': counts,
               'input_normalized_hashes': before_models, 'test_normalized_hashes': before_tests,
               'evidence': 'Observed completed local execution; CI independently reruns the suite.'}
    (ROOT/'provenance/stage3-test-run.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    if not result.wasSuccessful(): sys.exit(1)
