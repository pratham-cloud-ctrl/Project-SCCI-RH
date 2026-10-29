"""Preserve historical teacher failures and audit a separately labeled benchmark."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3.motor import MotorConfig
from scci_rh.stage3.expert_validation import (capture_expert_performance,
                                         fit_observed_teacher_decoder,
                                         validate_observed_teacher_decoder, GENERATORS)
from run_stage3_studies import close_nested

OUT = ROOT/'results/stage3/expert-validation'
DOC = ROOT/'docs/stage3/expert-validation.md'
PERFORMANCE_SEEDS = (51000, 61007, 71014, 81021)
SOURCE_PATHS = ('src/scci_rh/stage3/expert_validation.py', 'src/scci_rh/stage3/motor.py',
                'src/scci_rh/stage3/acquisition.py', 'src/scci_rh/stage3/filter_residual.py',
                'scripts/stage3_expert_validation.py')


def source_hashes():
    return {path: hashlib.sha256((ROOT/path).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for path in SOURCE_PATHS}


def serialize(capture):
    return {**capture, 'observations': [asdict(o) for o in capture['observations']]}


def without_local_voltage_hash(value):
    """Recorded full voltage digest is identity, not a floating portability test."""
    if isinstance(value, dict):
        return {key: without_local_voltage_hash(item) for key, item in value.items()
                if key != 'filter_input_v_sha256'}
    if isinstance(value, (list, tuple)):
        return [without_local_voltage_hash(item) for item in value]
    return value


def save_gzip(path, value, check):
    if check:
        saved = json.loads(gzip.decompress(path.read_bytes()).decode())
        close_nested(without_local_voltage_hash(value), without_local_voltage_hash(saved))
        value['capture']['voltage_acquisition_witness']['filter_input_v_sha256'] = saved['capture']['voltage_acquisition_witness']['filter_input_v_sha256']
        return
    buffer = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as file:
        file.write(json.dumps(value, separators=(',', ':'), allow_nan=False).encode())
    path.write_bytes(buffer.getvalue())


def experiment(check=False):
    config = MotorConfig(body_integration_step_s=.0025,
                         body_integration_method='midpoint_exact_cascade',
                         acquisition_qualification_mode='bounded_residual',
                         acquisition_clock_uncertainty_s=20e-6)
    rows, fit_records, files = [], {}, []
    for generator in GENERATORS:
        model = None
        for heldout in (False, True):
            for index, performance_seed in enumerate(PERFORMANCE_SEEDS):
                name = f"{generator}_{'faster' if heldout else 'nominal'}_performance{index}"
                print(name+': capturing', flush=True)
                capture = capture_expert_performance(performance_seed, config, generator=generator,
                                                       heldout=heldout, subject_seed=51000)
                if not heldout and index == 0:
                    model = fit_observed_teacher_decoder(capture)
                    fit_records[generator] = None if model is None else {
                        key: value.tolist() if hasattr(value, 'tolist') else value for key, value in model.items()}
                independent = heldout or index != 0
                validation = (validate_observed_teacher_decoder(model, capture) if independent else
                              {'available': False, 'reason': 'TRAINING_PERFORMANCE_NOT_INDEPENDENT_VALIDATION'})
                value = {'schema': 'scci_rh.stage3.expert-performance.v1', 'source_sha256': source_hashes(),
                         'name': name, 'capture': serialize(capture),
                         'frozen_decoder_validation': validation}
                path = OUT/(name+'.json.gz')
                save_gzip(path, value, check)
                files.append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
                rows.append({'name': name, 'generation': capture['generation_metadata'],
                             'qualification': capture['qualification'],
                             'private_generation_metrics': capture['private_evaluator']['metrics'],
                             'voltage_witness': {key: value for key, value in capture['voltage_acquisition_witness'].items()
                                                  if not key.endswith('_filter_input_v')},
                             'independent_decoder_validation': validation})
                q = capture['qualification']
                print(f"{name}: observed qualified={q['qualified']} reason={q['reason']}", flush=True)
    return {'schema': 'scci_rh.stage3.expert-validation.v1', 'source_sha256': source_hashes(),
            'scope': 'observed competence and decoder transfer in separately labeled synthetic teacher generators',
            'performance_count': len(rows), 'independent_noise_realizations_per_generator_cadence': 4,
            'subject_geometry_seed': 51000, 'config': asdict(config),
            'decoder_training': 'performance0 nominal cadence, chronological purged split; frozen for other captures',
            'decoder_fits': fit_records, 'raw_files': files, 'performances': rows,
            'historical_information_studies_replaced': False,
            'next_library_requirement': 'independently competent observed teacher plus qualified transferable decoder; not integrated yet'}


def report(receipt):
    lines = ['# Expert competence and independent performance audit', '',
             'The earlier expert generator set voluntary coefficients equal to the desired sinusoid’s',
             'amplitude. The reduced body still has a 60 ms movement time constant, so a desired voluntary',
             'waveform does not establish expert-level task execution. Teacher competence must be assessed',
             'from observed task performance before its recordings can support an expert-to-novice claim.', '',
             'The existing [280-row information comparison](information-comparison.md) is preserved. Its teacher references are',
             '**unqualified for the full timing criterion**; its results remain conditional controller/',
             'plasticity comparisons rather than validated expert-to-novice skill acquisition.', '',
             '## Separate synthetic benchmark', '',
             'A proposed replacement generator uses the inverse of the declared private expert body law:',
             '`voluntary = desired position + movement time constant × desired velocity`.',
             'For a sinusoid, its voluntary sin/cos coefficients are `[A, A τ ω]`. The generator uses the',
             'private movement time constant solely to construct an idealized synthetic skill. This is an',
             'explicit generator privilege, not a learned real expert, and no controller receives that',
             'time constant, voluntary coefficients or private body state. Direction-change transients',
             'remain; no impulse or instantaneous body jump is inserted to force competence.', '',
             'Both generators receive four independent voltage/external observation-noise realizations',
             'of one synthetic subject/geometry at 1 Hz and four at 1.15 Hz. Body integration is midpoint',
             'exact cascade at 2.5 ms while decisions remain 5 ms. Each capture is 12 s. Voltage acquisition',
             'has 16 contacts at 4 kHz; physical aperture times and 20 ms external delay are preserved.',
             'The acquisition source is the body state at block start, advanced only after its 5 ms block.', '',
             '## Qualification using measured external records', '',
             'The same task metric and fixed 18 mm spatial / 25 ms timing thresholds apply to both',
             'generators and both cadences. Noise, thresholds and outcomes are not adjusted to make the',
             'new benchmark pass. The body-truth diagnostics are kept separately and never qualify a teacher.', '',
             '| Generator | Cadence Hz | Performance | Observed spatial RMSE mm | Observed timing RMSE ms | Qualified |',
             '|---|---:|---:|---:|---:|---|']
    for row in receipt['performances']:
        g, q = row['generation'], row['qualification']; m = q['metrics']
        lines.append(f"| {g['generator']} | {g['cadence_hz']:.2f} | {g['performance_seed']} | {m['contact_spatial_rmse_m']*1000:.3f} | {m['contact_timing_rmse_s']*1000:.3f} | {q['qualified']} |")
    lines += ['', '## Frozen decoder transfer', '',
              'Each decoder is fitted only on its generator’s nominal performance0 capture with the',
              'existing purged chronological split and externally measured position/differentiated labels.',
              'Other nominal performances have distinct observation noise. Every faster-cadence capture',
              'is withheld from this fit. Contact geometry stays fixed: this tests performance/noise/cadence',
              'transfer within one artificial subject, not transfer between people or changed electrodes.', '',
              '| Generator | Cadence Hz | Performance | Independent position RMSE mm | Velocity RMSE m/s | Rows |',
              '|---|---:|---:|---:|---:|---:|']
    for row in receipt['performances']:
        g, v = row['generation'], row['independent_decoder_validation']
        if v['available']:
            lines.append(f"| {g['generator']} | {g['cadence_hz']:.2f} | {g['performance_seed']} | {v['position_rmse_m']*1000:.3f} | {v['velocity_rmse_m_per_s']:.5f} | {v['scored_rows']} |")
    lines += ['', 'Transfer residuals are observations, not automatic decoder qualification. The original',
              'same-task fit gate is an empirical residual allocation; a revised expert library must admit',
              'only task-competent observed references and qualify its decoded representation against',
              'independent performance/cadence evidence. An unavailable teacher remains unavailable.', '',
              '## Provenance and next revision', '',
              'Raw gzip files retain Observation packets, external records, separate private generation',
              'diagnostics and first/last voltage blocks. Every chronological synthetic prefilter voltage',
              'aperture is hashed by a forwarding-only witness that does not change filter arguments/results.',
              'Source hashes, subject/noise identities and acquisition counts are saved in the receipt.', '',
              'This audit does not modify `motor.py`, the historical expert library or the saved information',
              'comparison. Integrating a competence-gated teacher is a separate mechanism revision that',
              'must receive new results. It does not retrospectively turn older conditional differences',
              'into evidence for expert-to-novice learning, nor establish real spinal skill-transfer biology.', '',
              '`python scripts/stage3_expert_validation.py --check` reproduces the captures and comparisons',
              'with relative tolerance 2e-8 and absolute tolerance 1e-11. Raw voltage hashes are within-host',
              'witnesses; numerical recorded arrays are the cross-platform comparison authority.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    value = experiment(args.check)
    target = OUT/'expert-summary.json'
    if args.check:
        close_nested(without_local_voltage_hash(value), without_local_voltage_hash(json.loads(target.read_text(encoding='utf-8'))))
        assert DOC.read_text(encoding='utf-8') == report(value)
        print('Expert qualification and independent performance receipt: reproduced')
    else:
        target.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        DOC.write_text(report(value), encoding='utf-8')
        print('Expert qualification and independent performance receipt: written')


if __name__ == '__main__':
    main()
