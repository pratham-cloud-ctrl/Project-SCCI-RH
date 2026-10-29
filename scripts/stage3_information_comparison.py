"""Paired observable-input comparison; conditional models are not human evidence.

Seven independent studies retain full motor outputs in deterministic gzip files.
--check reproduces numerical results without rewriting them. --resume reuses
finished, source-matched studies after an interrupted batch. At most two workers
run concurrently; each actual-electrical study owns a fresh delivery adapter.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import gzip
import hashlib
import io
import json
from multiprocessing import get_context
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3.motor import (MotorConfig, run_study, FAMILIES, CONDITIONS,
                              EXTERNAL_HISTORY_CONDITIONS)
from scci_rh.stage3.electrical import MotorDelivery
from run_stage3_studies import close_nested

OUT = ROOT/'results/stage3/information'
DOC = ROOT/'docs/stage3/information-comparison.md'
ALL_CONDITIONS = CONDITIONS + EXTERNAL_HISTORY_CONDITIONS
FAULTS = ('shuffled_expert', 'incorrect_map', 'stale_external',
          'artifact_recovery', 'saturation', 'source_drift')
SOURCE_PATHS = ('src/scci_rh/stage3/motor.py', 'src/scci_rh/stage3/acquisition.py',
                'src/scci_rh/stage3/filter_residual.py', 'src/scci_rh/stage3/external_history.py',
                'src/scci_rh/stage3/electrical.py', 'scripts/stage3_information_comparison.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def source_hashes():
    return {path: hashlib.sha256((ROOT/path).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for path in SOURCE_PATHS}


def tasks():
    common = {'body_integration_step_s': .0025,
              'body_integration_method': 'midpoint_exact_cascade',
              'acquisition_qualification_mode': 'bounded_residual',
              'acquisition_clock_uncertainty_s': 20e-6}
    result = []
    for source in ('informative', 'redundant', 'absent'):
        for seed in (0, 1):
            result.append({'id': f'conditional_fast_{source}_seed{seed}', 'seed': seed,
                           'source_mode': source, 'actual_electrical': False,
                           'config': common | {'motor_onset_delay_s': .005, 'source_mode': source},
                           'faults': FAULTS if source == 'informative' and seed == 0 else ()})
    result.append({'id': 'actual_nominal_informative_seed0', 'seed': 0,
                   'source_mode': 'informative', 'actual_electrical': True,
                   'config': common | {'motor_onset_delay_s': .035, 'source_mode': 'informative'},
                   'faults': ()})
    return result


def run_one(task):
    print(f"{task['id']}: running", flush=True)
    started = time.perf_counter()
    study = run_study(task['seed'], MotorConfig(**task['config']),
                      MotorDelivery() if task['actual_electrical'] else None,
                      families=FAMILIES, conditions=ALL_CONDITIONS, faults=task['faults'])
    print(f"{task['id']}: finished in {time.perf_counter()-started:.1f} s", flush=True)
    return {'schema': 'scci_rh.stage3.information-study.v1', 'task': task,
            'source_sha256': source_hashes(), 'study': study}


def write_gzip(path, value):
    buffer = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as stream:
        stream.write(json.dumps(value, separators=(',', ':'), allow_nan=False).encode('utf-8'))
    path.write_bytes(buffer.getvalue())


def read_gzip(path):
    return json.loads(gzip.decompress(path.read_bytes()).decode('utf-8'))


def summarize_run(raw):
    study = raw['study']
    neural = study['calibration']['decoder_fit']
    external = study['calibration']['external_history_fit']
    assert neural is not None and external is not None, 'Comparator calibration unavailable'
    assert external['exact_neural_cohort_matched'], 'Different offline target cohort'
    assert neural['training_rows'] == external['training_rows'], 'Different training exposure'
    assert neural['heldout_rows'] == external['heldout_rows'], 'Different withheld exposure'
    assert neural['labels'] == external['labels'], 'Different label definitions'
    assert external['feature_dimension'] == 32 and external['coefficient_count'] == 132
    assert study['comparison_design']['learned_input_dimension_each'] == 32
    assert study['calibration']['same_budget_all_conditions']
    rows = []
    for family, result in study['families'].items():
        assert tuple(result['conditions']) == ALL_CONDITIONS
        for condition, entry in result['conditions'].items():
            summary = entry['summary']
            assert summary['assistance_off_verified']
            assert summary['retention_off']['pulse_count'] == summary['transfer_off']['pulse_count'] == 0
            assert all(m['maximum_external_support_age_s'] <= .025+1e-12 for m in entry['practice_blocks'])
            for metric in (*entry['practice_blocks'], summary['retention_off'], summary['transfer_off']):
                score = metric['same_support_estimation']
                assert score['valid_scored_packets'] <= score['total_packets']
                assert all(score[key] is None or np.isfinite(score[key])
                           for key in ('position_rmse_m', 'velocity_rmse_m_per_s'))
            rows.append({'family': family, 'condition': condition,
                         'summary': summary, 'practice_blocks': entry['practice_blocks']})
    return {'id': raw['task']['id'], 'task': raw['task'], 'config': study['config'],
            'delivery_model': study['delivery_model'], 'calibration': study['calibration'],
            'expert_resource': study['expert_resource'], 'comparison_design': study['comparison_design'],
            'rows': rows,
            'contrasts': {family: result['contrasts'] for family, result in study['families'].items()},
            'negative_controls': {fault: entry['metrics'] for fault, entry in study['negative_controls'].items()},
            'information_permissions': study['information_permissions'], 'limitations': study['limitations']}


def summary_receipt(raw_runs, output_dir=OUT):
    runs = [summarize_run(raw) for raw in raw_runs]
    return {'schema': 'scci_rh.stage3.information-comparison.v1',
            'scope': 'chosen synthetic source hypotheses and plasticity; no clinical or consumer efficacy',
            'source_sha256': source_hashes(),
            'numerical_reproduction_tolerances': {'relative': 2e-8, 'absolute': 1e-11},
            'study_count': len(runs), 'family_condition_rows': sum(len(run['rows']) for run in runs),
            'conditional_study_count': sum(not run['task']['actual_electrical'] for run in runs),
            'actual_electrical_study_count': sum(run['task']['actual_electrical'] for run in runs),
            'negative_control_count': sum(len(run['negative_controls']) for run in runs),
            'all_retention_transfer_output_off': True,
            'calibration_cohorts_match': True,
            'raw_files': [{'path': f"{raw['task']['id']}.json.gz",
                           'sha256': hashlib.sha256((output_dir/f"{raw['task']['id']}.json.gz").read_bytes()).hexdigest(),
                           'semantic_sha256': hashlib.sha256(canonical(raw)).hexdigest()}
                          for raw in raw_runs],
            'runs': runs}


def generate_report(receipt):
    lines = ['# Observable-input comparison', '',
             'This batch compares the original linear external observer, the neural/external fusion observer,',
             'and a learned external-history observer with the same number and class of learned coefficients.',
             'It retains the full SCCI chain and expert-informed motor-learning question. A strong external',
             'comparator helps identify what the implanted observations contribute in these chosen models;',
             'it does not determine what real spinal recordings can contain.', '',
             '## Frozen experiment', '',
             f"There are {receipt['study_count']} studies and {receipt['family_condition_rows']} plasticity/arm rows.",
             'Six studies cross informative, externally redundant and absent synthetic source hypotheses with',
             'seeds 0 and 1. They assume fast 5 ms biological onset and nominal delivery with unqualified dose',
             'uncertainty. One informative seed-0 study retains nominal 35 ms onset and the actual electrical',
             'monitor/qualification model. Each study has four plasticity families and ten arms, 12 s movement',
             'calibration, equal route/withheld calibration, four 3 s practice blocks and 3 s OFF assessments.',
             'Both sensors retain their original schedules. Body integration is the midpoint exact cascade',
             'at 2.5 ms; acquisition uses bounded digital filter residuals and 20 microsecond clock allowance.',
             'The residual bounds concern a range-bounded digital counterfactual, not amplifier recovery.', '',
             'Both learned observers have 32 inputs and 132 coefficients, ridge penalty 0.5, the same offline',
             'calibration target cohort and partition-local measured labels. The external history spans 75 ms;',
             'the neural lock-in window is 20 ms with recursive earlier history. Parameter count matching',
             'does not establish identical information content or effective statistical capacity.', '',
             '## Fit residuals and independent online scoring', '',
             'Offline position fit uses measured external labels; a history model can copy some newest',
             'measurement noise. The online evaluator separately scores private body position and the',
             'declared 5 ms body velocity at exactly the estimator’s physical external support. That truth',
             'never enters identification, decoding or policy. Scores use each arm’s valid packets; differing',
             'warmup/fallback masks mean the evaluated packet populations are not identical. Counts are saved.', '',
             '| Study | Neural fit position mm | External-history fit position mm | Same train / withheld rows |',
             '|---|---:|---:|---:|']
    for run in receipt['runs']:
        n, e = run['calibration']['decoder_fit'], run['calibration']['external_history_fit']
        lines.append(f"| {run['id']} | {n['rmse']*1000:.4f} | {e['rmse']*1000:.4f} | {n['training_rows']} / {n['heldout_rows']} |")
    lines += ['', 'The next table uses first-practice-block same-support body scoring with the declared learner goal.',
              'All sources and delivery assumptions stay separate. Neural use and learned-history use are',
              'fractions of the complete 600-packet block; a fallback remains an external observation.', '',
              '| Study | Observer | Body position RMSE mm | Body velocity RMSE m/s | Valid packets | Neural / learned-history use | Practice pulses |',
              '|---|---|---:|---:|---:|---:|---:|']
    for run in receipt['runs']:
        for observer in ('external', 'neural_external', 'external_history'):
            row = next(r for r in run['rows'] if r['family']=='favorable' and r['condition']==observer+'__learner_only')
            m = row['practice_blocks'][0]; score = m['same_support_estimation']
            pos = 'unavailable' if score['position_rmse_m'] is None else f"{score['position_rmse_m']*1000:.3f}"
            vel = 'unavailable' if score['velocity_rmse_m_per_s'] is None else f"{score['velocity_rmse_m_per_s']:.5f}"
            lines.append(f"| {run['id']} | {observer} | {pos} | {vel} | {score['valid_scored_packets']}/{score['total_packets']} | {m['neural_used_fraction']:.3f} / {m['learned_external_history_used_fraction']:.3f} | {m['pulse_count']} |")
    lines += ['', '## Retained learning contrasts', '',
              'Each entry below is neural-fusion OFF contact-spatial RMSE minus learned-external-history OFF',
              'contact-spatial RMSE, in millimetres, with the same expert representation. Negative values',
              'favor neural fusion within this model. Better assisted motion alone is not retained learning.', '',
              '| Study | Plasticity | Declared goal | Expert external | Expert neural |',
              '|---|---|---:|---:|---:|']
    for run in receipt['runs']:
        for family in FAMILIES:
            values = [run['contrasts'][family]['neural_minus_external_history_retention_m__'+rep]*1000
                      for rep in ('learner_only', 'expert_external', 'expert_neural')]
            lines.append(f"| {run['id']} | {family} | {values[0]:+.4f} | {values[1]:+.4f} | {values[2]:+.4f} |")
    censored = sum(row['summary']['threshold_censored'] for run in receipt['runs'] for row in run['rows'])
    lines += ['', f"{censored}/{receipt['family_condition_rows']} acquisition-threshold rows are censored after 12 s practice.",
              'No acquisition-speed multiplier is estimated from censored rows. Every retained and transfer',
              'assessment had zero output pulses; the idealized washout/body reset and chosen 2% forgetting',
              'remain explicit model assumptions rather than timed withdrawal or long-term human retention.', '',
              'The actual-electrical branch must be interpreted using its observed authority margin and',
              'admission reasons. A failure to deliver qualified intervention cannot establish the absence',
              'of useful spinal information. Conditional branches assume delivery and unusually fast onset;',
              'their outcomes do not repair the measured monitor precision or nominal timing limitations.', '',
              f"{receipt['negative_control_count']} separate seed-0 informative negative-control witnesses are retained.",
              'Their shuffled expert, incorrect response map, stale external input, prolonged artifacts,',
              'saturation and source drift dispositions appear in the readable receipt and raw files.', '',
              '## Reproduction and boundaries', '',
              'The adjacent JSON receipt preserves every arm’s block metrics, calibration quantities, expert',
              'qualification, contrasts, OFF scores, censoring and faults. Separate raw gzip files preserve',
              'the full study objects and available practice/retention/transfer/fault traces. Input-source',
              'hashes and raw hashes make the mechanism revision traceable.', '',
              '`python scripts/stage3_information_comparison.py --check --jobs 2` reproduces the seven studies',
              'with relative tolerance 2e-8 and absolute tolerance 1e-11. `--resume` reuses source-matched',
              'finished studies after an interruption. This batch does not validate real intradural signal',
              'content, chronic implants, biomechanics, clinical efficacy or consumer accelerated learning.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--jobs', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    if args.check and args.resume:
        parser.error('--check and --resume are mutually exclusive')
    OUT.mkdir(parents=True, exist_ok=True)
    completed, pending = {}, []
    current_hashes = source_hashes()
    for task in tasks():
        target = OUT/f"{task['id']}.json.gz"
        if args.resume and target.exists():
            saved = read_gzip(target)
            close_nested(task, saved['task'])
            assert saved['source_sha256'] == current_hashes, 'Cannot resume results from changed mechanism sources'
            summarize_run(saved)
            completed[task['id']] = saved
            print(f"{task['id']}: source-matched result reused", flush=True)
        else:
            pending.append(task)
    def accept(value):
        target = OUT/f"{value['task']['id']}.json.gz"
        summarize_run(value)
        if args.check:
            close_nested(value, read_gzip(target))
            print(f"{value['task']['id']}: reproduced within declared tolerances", flush=True)
        else:
            write_gzip(target, value)
            print(f"{value['task']['id']}: raw evidence saved", flush=True)
        completed[value['task']['id']] = value
    if args.jobs == 1:
        for task in pending:
            accept(run_one(task))
    else:
        with ProcessPoolExecutor(max_workers=args.jobs, mp_context=get_context('spawn')) as pool:
            futures = [pool.submit(run_one, task) for task in pending]
            for future in as_completed(futures):
                accept(future.result())
    ordered = [completed[task['id']] for task in tasks()]
    # Receipt hashes refer to the saved artifacts. Reproduction may differ in
    # float text within tolerance, so compare summaries numerically and preserve
    # the saved raw hash identity instead of inventing a new release identity.
    saved_ordered = [read_gzip(OUT/f"{task['id']}.json.gz") for task in tasks()] if args.check else ordered
    receipt = summary_receipt(saved_ordered)
    target = OUT/'comparison-summary.json'
    if args.check:
        close_nested(receipt, json.loads(target.read_text(encoding='utf-8')))
        assert DOC.read_text(encoding='utf-8') == generate_report(receipt), 'Report differs from receipt'
        print('Information comparison receipt/report: verified', flush=True)
    else:
        target.write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        DOC.write_text(generate_report(receipt), encoding='utf-8')
        print('Information comparison receipt/report: written', flush=True)


if __name__ == '__main__':
    main()
