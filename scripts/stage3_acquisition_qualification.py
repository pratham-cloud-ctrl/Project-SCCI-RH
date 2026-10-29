"""Reproduce digital filter residual and aperture-source diagnostic receipts."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3.acquisition import AcquisitionConfig, ContactAcquisition


class ObservedNoise:
    def __init__(self, rng):
        self.rng = rng; self.digest = hashlib.sha256(); self.calls = 0; self.values = 0
        self.initial = rng.bit_generator.state

    def normal(self, *args, **kwargs):
        result = self.rng.normal(*args, **kwargs)
        values = np.asarray(result, dtype='<f8')
        self.digest.update(values.tobytes()); self.calls += 1; self.values += values.size
        return result

    def receipt(self):
        return {'draw_calls': self.calls, 'draw_values': self.values,
                'actual_sample_sha256': self.digest.hexdigest(),
                'initial_state': self.initial, 'final_state': self.rng.bit_generator.state}


def source(times):
    return np.stack((.7*np.sin(2*np.pi*times), -.7*np.sin(2*np.pi*times),
                     .7*np.cos(2*np.pi*times), -.7*np.cos(2*np.pi*times)), axis=-1)


def capture(case, mode, *, aperture_resolved=False, seconds=5.):
    c = AcquisitionConfig(qualification_mode=mode, maximum_contiguous_gap_s=.002,
                          clock_uncertainty_s=20e-6)
    a = ContactAcquisition(23, c)
    noise = ObservedNoise(a._rng); a._rng = noise
    if case == 'single_artifact': a.add_artifact(.300)
    if case == 'train_40hz':
        for time in np.arange(.300, 1., .025): a.add_artifact(float(time))
    rows = []
    for k in range(round(seconds*c.controller_hz)):
        t = k/c.controller_hz
        if case == 'missing_block' and k == 60: continue
        start = source(np.array(t))
        kwargs = {}
        if aperture_resolved:
            times = t+np.arange(20)[:, None]/c.sample_hz+np.arange(16)[None, :]*c.aperture_step_s
            kwargs['simulator_aperture_sources'] = source(times)
        packet = a.observe(t, start[:2], start[2:], **kwargs)
        rows.append({'available_time_s': packet.available_time_s,
                     'support_start_s': packet.support_start_s, 'support_end_s': packet.support_end_s,
                     'valid': packet.valid, 'reasons': list(packet.reasons),
                     'raw_usable_fraction': packet.usable_fraction,
                     'feature_error_bound_uv': a.last_feature_error_bound_uv.tolist(),
                     'maximum_contiguous_gap_s': a.last_maximum_contiguous_gap_s,
                     'features_uv': list(packet.values_uv)})
    after = [r for r in rows if r['available_time_s'] >= .405]
    first = next((r['available_time_s'] for r in after if r['valid']), None)
    return {'case': case, 'qualification_mode': mode, 'aperture_resolved': aperture_resolved,
            'config': {'seconds': seconds, 'sample_hz': c.sample_hz, 'controller_hz': c.controller_hz,
                       'clock_uncertainty_s': c.clock_uncertainty_s, 'contiguous_gap_s': c.maximum_contiguous_gap_s,
                       'bounded_digital_input_v': c.range_v, 'feature_error_budget_uv': c.feature_error_budget_uv},
            'noise': noise.receipt(), 'filter_realization': a._residual.realization if a._residual else None,
            'summary': {'packet_count': len(rows), 'raw_sample_count': a.total_raw_samples,
                        'qualified_packets': sum(r['valid'] for r in rows),
                        'first_qualified_after_405ms_s': first,
                        'final_feature_error_bound_uv': max(rows[-1]['feature_error_bound_uv'])},
            'rows': rows}


def generate():
    runs = [capture(case, mode) for case in ('clean', 'single_artifact', 'train_40hz', 'missing_block')
            for mode in ('fixed_history', 'bounded_residual')]
    comparisons = []
    for old, bounded in zip(runs[::2], runs[1::2]):
        assert old['noise'] == bounded['noise']
        assert old['summary']['raw_sample_count'] == bounded['summary']['raw_sample_count']
        differences = [r['available_time_s'] for r, s in zip(old['rows'], bounded['rows']) if r['valid'] != s['valid']]
        comparisons.append({'case': old['case'], 'identical_actual_noise': True,
                            'unchanged_raw_and_packet_schedule': True,
                            'validity_difference_count': len(differences),
                            'first_validity_differences_s': differences[:10]})
    held = capture('clean', 'bounded_residual', seconds=1.)
    resolved = capture('clean', 'bounded_residual', aperture_resolved=True, seconds=1.)
    assert held['noise'] == resolved['noise']
    difference = np.array([r['features_uv'] for r in held['rows']])-np.array([r['features_uv'] for r in resolved['rows']])
    return {'schema': 'scci_rh.stage3.acquisition-qualification.v1',
            'scope': 'bounded digital missing-input contamination and independent analytic synthetic aperture-source diagnostic; not physical AFE recovery or full body-source convergence',
            'reference_definition': 'same initialized filter driven by unknown range-clipped artifact-free digital samples at masked apertures; input magnitudes <=5mV',
            'numerical_scope': 'engineering floating-point enclosure tested against independent SOS output, not formal interval proof',
            'sources': {name: hashlib.sha256((ROOT/name).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
                        for name in ('src/scci_rh/stage3/acquisition.py', 'src/scci_rh/stage3/filter_residual.py')},
            'runs': runs, 'comparisons': comparisons,
            'source_approximation': {'definition': '1Hz analytic private source evaluated at identical 4kHz per-contact skewed apertures versus block-start hold',
                                     'identical_noise': True, 'packet_count_each': len(held['rows']),
                                     'maximum_feature_difference_uv': float(np.max(np.abs(difference))),
                                     'feature_difference_rmse_uv': float(np.sqrt(np.mean(difference**2))),
                                     'held': held, 'aperture_resolved': resolved}}


def check_close(actual, saved):
    if isinstance(actual, dict):
        assert actual.keys() == saved.keys()
        for k in actual:
            if k == 'actual_sample_sha256': continue  # RNG states/counts bind cross-platform draws.
            check_close(actual[k], saved[k])
    elif isinstance(actual, list):
        assert len(actual) == len(saved)
        for a, b in zip(actual, saved): check_close(a, b)
    elif isinstance(actual, (float, int)) and not isinstance(actual, bool):
        assert np.isclose(actual, saved, rtol=2e-8, atol=1e-11), (actual, saved)
    else: assert actual == saved, (actual, saved)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--output', type=Path); group.add_argument('--check', type=Path)
    args = parser.parse_args(); result = generate()
    if args.check:
        contents = args.check.read_bytes()
        if args.check.suffix == '.gz': contents = gzip.decompress(contents)
        check_close(result, json.loads(contents))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        contents = (json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n').encode()
        if args.output.suffix == '.gz':
            buffer = io.BytesIO()
            with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as stream: stream.write(contents)
            contents = buffer.getvalue()
        args.output.write_bytes(contents)
        summary = {k: result[k] for k in ('schema', 'scope', 'reference_definition', 'numerical_scope', 'sources', 'comparisons')}
        summary['schema'] = 'scci_rh.stage3.acquisition-qualification-summary.v1'
        summary['runs'] = [{k: v for k, v in run.items() if k != 'rows'} for run in result['runs']]
        summary['source_approximation'] = {k: v for k, v in result['source_approximation'].items() if k not in ('held', 'aperture_resolved')}
        summary['raw_witness'] = {'file': args.output.name, 'sha256': hashlib.sha256(contents).hexdigest()}
        args.output.with_name('acquisition-qualification-summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'scope': result['scope'], 'runs': [{k: r[k] for k in ('case', 'qualification_mode', 'summary')} for r in result['runs']],
                      'comparisons': result['comparisons'],
                      'source_approximation_maximum_uv': result['source_approximation']['maximum_feature_difference_uv']}, indent=2))


if __name__ == '__main__': main()
