"""Bind the Stage 3 continuation to saved evidence, sources and declared limits.

This checks saved artifacts. Separate CI commands recompute their model results.
Neither operation qualifies an implant or establishes biological efficacy.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'results/stage3'
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from artifact_hashes import canonical_json_digest
import stage3_motor_convergence as motor_check
import stage3_pressure_convergence as pressure_check
import stage3_information_comparison as information_check
import stage3_response_validation as response_check


def read(path):
    path = ROOT/path if isinstance(path, str) else path
    content = path.read_bytes()
    return json.loads(gzip.decompress(content) if path.suffix == '.gz' else content)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_sha(path):
    return hashlib.sha256(path.read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()


def source_identity(record, aliases=None):
    for name, expected in record.items():
        actual_name = aliases.get(name, name) if aliases else name
        assert normalized_sha(ROOT/actual_name) == expected, f'Stale source: {actual_name}'


def verify():
    checks = []
    counts = {}
    raw = read(DATA/'numerical/motor-convergence.json.gz')
    brief = read(DATA/'numerical/motor-convergence-summary.json')
    source_identity(raw['source_identity'], {
        'motor.py': 'src/scci_rh/stage3/motor.py', 'acquisition.py': 'src/scci_rh/stage3/acquisition.py',
        'external_history.py': 'src/scci_rh/stage3/external_history.py',
        'stage3_motor_convergence.py': 'scripts/stage3_motor_convergence.py'})
    assert brief == motor_check.summary(raw, 'motor-convergence.json.gz', sha(DATA/'numerical/motor-convergence.json.gz'))
    assert raw['coarse_baseline']['commit'] == '526b854ad90dda8320325635fb26fef2a9e120bf'
    assert raw['coarse_baseline']['status'] == 'EXACT_FROZEN_COARSE_REPRODUCTION'
    assert len(raw['coarse_baseline']['world_checks']) == 4 and len(raw['coarse_baseline']['capture_checks']) == 3
    assert all(all(row[k] for k in ('position_exact', 'velocity_exact', 'activation_exact', 'coefficient_exact'))
               for row in raw['coarse_baseline']['world_checks'])
    assert all(row['all_capture_outputs_exact'] for row in raw['coarse_baseline']['capture_checks'])
    assert len(raw['fixed_input_cases']) == 12 and len(raw['closed_loop_runs']) == 5
    assert sum(len(c['runs']) for c in raw['fixed_input_cases']) == 96
    recommendation = raw['production_recommendation']
    assert recommendation['body_integration_step_s'] == .0025
    assert recommendation['body_integration_method'] == 'midpoint_exact_cascade'
    assert recommendation['fixed_input_gate_pass'] and recommendation['bounded_closed_loop_gate_pass']
    assert any(not all(r['budget_pass'].values()) for c in raw['fixed_input_cases'] for r in c['runs'])
    counts.update(motor_fixed_runs=96, motor_bounded_closed_loop_grids=5)
    checks.append('Independent motor references, failed historical grids and scoped 2.5 ms recommendation retained; readable summary matches all saved raw witnesses')

    pressure = read(DATA/'numerical/pressure-convergence.json.gz')
    source_identity(pressure['source_identity'])
    pressure_check.validate_receipt(pressure)
    assert read(DATA/'numerical/pressure-convergence-summary.json') == pressure_check.summary_receipt(pressure)
    assert pressure['summary']['run_count'] == 408 and pressure['summary']['matched_group_count'] == 136
    assert pressure['summary']['comparison_count'] == 408 and pressure['summary']['budget_failure_count'] == 0
    assert pressure['summary']['discrete_sensitivity_count'] == 24
    assert pressure['summary']['identical_actual_sensor_noise_per_seed_across_all_runs']
    counts.update(pressure_refinement_runs=408, pressure_groups=136, pressure_frame_sensitive_comparisons=24)
    checks.append('408 pressure refinements preserve observed schedules and actual noise; all numeric budgets pass while 24 comparison-level frame sensitivities remain explicit')

    acquisition = read(DATA/'numerical/acquisition-qualification.json.gz')
    acquisition_summary = read(DATA/'numerical/acquisition-qualification-summary.json')
    source_identity(acquisition['sources'])
    expected = {k: acquisition[k] for k in ('schema', 'scope', 'reference_definition', 'numerical_scope', 'sources', 'comparisons')}
    expected['schema'] = 'scci_rh.stage3.acquisition-qualification-summary.v1'
    expected['runs'] = [{k: v for k, v in run.items() if k != 'rows'} for run in acquisition['runs']]
    expected['source_approximation'] = {k: v for k, v in acquisition['source_approximation'].items() if k not in ('held', 'aperture_resolved')}
    expected['raw_witness'] = {'file': 'acquisition-qualification.json.gz', 'sha256': sha(DATA/'numerical/acquisition-qualification.json.gz')}
    assert expected == acquisition_summary and len(acquisition['runs']) == 8
    assert len(acquisition['comparisons']) == 4
    assert all(c['identical_actual_noise'] and c['unchanged_raw_and_packet_schedule'] for c in acquisition['comparisons'])
    counts.update(acquisition_qualification_runs=8, acquisition_noise_matched_pairs=4)
    checks.append('Range-bounded digital missing-input filter qualification has eight matched recordings; analog recovery and full moving-body aperture convergence are not claimed')

    information = read(DATA/'information/comparison-summary.json')
    source_identity(information['source_sha256'])
    information_raw = []
    for item in information['raw_files']:
        path = DATA/'information'/item['path']
        assert sha(path) == item['sha256']
        saved = read(path)
        assert hashlib.sha256(information_check.canonical(saved)).hexdigest() == item['semantic_sha256']
        source_identity(saved['source_sha256'])
        information_raw.append(saved)
    assert information_check.summary_receipt(information_raw) == information
    assert information['study_count'] == 7 and information['family_condition_rows'] == 280
    assert information['negative_control_count'] == 6
    assert information['all_retention_transfer_output_off'] and information['calibration_cohorts_match']
    for run in information['runs']:
        for row in run['rows']:
            if run['task']['actual_electrical']:
                assert sum(b['pulse_count'] for b in row['practice_blocks']) == 0
            assert row['summary']['retention_off']['pulse_count'] == row['summary']['transfer_off']['pulse_count'] == 0
    counts.update(information_studies=7, information_family_condition_rows=280, information_negative_controls=6)
    checks.append('Seven fair-input studies bind 280 rows to matched calibration and saved raw bytes; actual motor abstention and all OFF assessments are preserved')

    response = read(DATA/'response-validation/response-domain-raw.json.gz')
    response_summary = read(DATA/'response-validation/response-domain-summary.json')
    source_identity(response['source_identity'])
    assert response_check.readable_summary(response) == response_summary
    assert response_summary['batch_summary']['study_count'] == 24
    assert response_summary['batch_summary']['heldout_nominal_case_count'] == 432
    assert response_summary['batch_summary']['heldout_changed_context_case_count'] == 432
    assert response_summary['batch_summary']['actual_delivery_qualified_map_count'] == 0
    assert response_summary['batch_summary']['null_or_adverse_qualified_map_count'] == 0
    counts.update(response_domain_studies=24, response_nominal_heldout_cases=432, response_changed_context_cases=432)
    checks.append('Observed-only route identification uses joint map/dose uncertainty including its cross term; empirical finite-domain results are not dynamic/context guarantees')

    cue = read(DATA/'cue-policy/raw.json.gz')
    cue_summary = read(DATA/'cue-policy/summary.json')
    source_identity(cue['source_identity'])
    expected = {k: v for k, v in cue.items() if k not in {'forecast', 'runs'}}
    expected['raw_witness'] = {'path': 'raw.json.gz', 'sha256': sha(DATA/'cue-policy/raw.json.gz')}
    expected['forecast'] = {k: v for k, v in cue['forecast'].items() if k != 'models'}
    expected['forecast']['models'] = [{k: v for k, v in m.items() if k not in {'mean', 'scale', 'weights'}} for m in cue['forecast']['models']]
    expected['runs'] = [{k: v for k, v in r.items() if k != 'replay'} | {'summary': r['replay']['summary']} for r in cue['runs']]
    assert expected == cue_summary and len(cue['runs']) == 8
    assert cue['status'] == 'component_witness_only' and cue['original_reactive_prediction_cap_s'] == .1
    assert cue['specification']['future_delivery_qualification'] == 'UNQUALIFIED_NOMINAL_ASSUMPTION'
    assert not cue['context_validation']['withheld_fixed_profile_assisted']['qualified']
    assert cue['task_reference']['kind'] == 'learner_only'
    for run in cue['runs']:
        summary = run['replay']['summary']
        assert summary['physical_pulses'] == 0 and not summary['retained_learning_measured']
        if run['branch'].startswith('actual_'): assert summary['launched_commands'] == 0
        if run['replay']['stop_after_first_command_for_unvalidated_coupling']:
            assert summary['launched_commands'] <= 1
        response_map = run.get('response', cue['runs'][1]['response'])
        gain, gain_u = np.asarray(response_map['gain_m']), np.asarray(response_map['gain_uncertainty_m'])
        for command in run['replay']['commands']:
            assert command['future_delivery_qualification'] == 'UNQUALIFIED_NOMINAL_ASSUMPTION'
            assert command['forecast_horizon_s'] <= .15+1e-12
            assert command['created_time_s']+.01185 <= command['launch_time_s']+1e-12
            assert command['launch_time_s'] <= command['expiry_time_s']
            dose = np.abs(command['prospective_measured_fraction'])
            dose_u = np.asarray(command['prospective_dose_uncertainty_fraction'])
            error = gain_u@dose+np.abs(gain)@dose_u+gain_u@dose_u+command['empirical_forecast_error_m']
            assert np.allclose(error, command['total_correction_error_allocation_m'], rtol=1e-12, atol=1e-14)
            assert np.max(error) <= cue['specification']['total_correction_uncertainty_limit_m']+1e-12
    counts['cue_component_replays'] = 8
    checks.append('Known-cue forecasting remains a separate component replay; actual delivery and assisted forecast gates are not promoted to a working motor controller')

    expert = read(DATA/'expert-validation/expert-summary.json')
    source_identity(expert['source_sha256'])
    assert expert['performance_count'] == len(expert['performances']) == 16
    assert not expert['historical_information_studies_replaced']
    for item in expert['raw_files']:
        path = DATA/'expert-validation'/item['path']
        assert sha(path) == item['sha256']
        performance = read(path)
        source_identity(performance['source_sha256'])
        row = next(r for r in expert['performances'] if r['name'] == performance['name'])
        assert performance['capture']['qualification'] == row['qualification']
        assert performance['frozen_decoder_validation'] == row['independent_decoder_validation']
    legacy = [r for r in expert['performances'] if r['generation']['generator'] == 'legacy_voluntary']
    revised = [r for r in expert['performances'] if r['generation']['generator'] == 'idealized_inverse']
    assert len(legacy) == len(revised) == 8
    assert all(not r['qualification']['qualified'] for r in legacy)
    assert all(r['qualification']['qualified'] for r in revised)
    counts.update(expert_recorded_performances=16, original_generator_competent_performances=0,
                  separately_labeled_inverse_generator_competent_performances=8)
    checks.append('Observed teacher timing exposes the original-generator failure; separate competence-qualified synthetic captures do not retroactively replace old learning results')
    tests = read('provenance/stage3-test-run.json')
    assert tests['observed_result']['status'] == 'OK'
    assert tests['observed_result']['failures'] == tests['observed_result']['errors'] == 0
    source_identity(tests['input_normalized_hashes'])
    source_identity(tests['test_normalized_hashes'])
    assert set(tests['input_normalized_hashes']) == {p.relative_to(ROOT).as_posix() for p in (ROOT/'src/scci_rh').rglob('*.py')}
    assert set(tests['test_normalized_hashes']) == {p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_*.py')}
    counts['observed_full_project_unit_tests'] = tests['observed_result']['tests_run']
    checks.append('Completed local full-suite result matches present source/test identities; CI independently repeats model studies and unit tests')

    visual = read('provenance/stage3-continuation-visual-review.json')
    assert len(visual['files']) == 6
    for name, item in visual['files'].items():
        path = ROOT/name
        assert (sha(path) if path.suffix == '.png' else normalized_sha(path)) == item['sha256']
    checks.append('Three new scientific figure pairs match the inspected PNGs and companion vector sources')

    matrix = {r['verification_id'] for r in csv.DictReader((ROOT/'docs/stage1/verification-matrix.csv').open(encoding='utf-8'))}
    progress = list(csv.DictReader((ROOT/'docs/stage3/verification-progress.csv').open(encoding='utf-8')))
    assert all(r['verification_id'] in matrix for r in progress)
    for doc in (ROOT/'docs/stage3').glob('*.md'):
        content = doc.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if target.startswith(('http:', 'https:', '#', 'mailto:')): continue
            resolved = (doc.parent/target.split('#')[0]).resolve()
            # The command creates/checks its own receipt after the audit succeeds.
            assert resolved == ROOT/'provenance/stage3-continuation-verification.json' or resolved.exists(), f'Broken local link in {doc.name}: {target}'
    status=(ROOT/'docs/stage3/README.md').read_text(encoding='utf-8').splitlines()[2]
    assert status.startswith(('**In progress,', '**Complete within selected digital scope,'))
    if status.startswith('**Complete within selected digital scope,'):
        assert '**COMPLETE WITHIN SELECTED DIGITAL SCOPE**' in (ROOT/'docs/stage3/exit-review.md').read_text(encoding='utf-8')
    checks.append('Dossier links and requirement IDs resolve; current stage status and separate closeout ledger are explicit')

    source_files = sorted((ROOT/'src/scci_rh/stage3').glob('*.py'))
    source_files += sorted((ROOT/'scripts').glob('stage3_*.py'))
    source_files += [Path(__file__), ROOT/'scripts/build_stage3_continuation_figures.py', ROOT/'scripts/record_stage3_tests.py']
    result_files = sorted(p for p in DATA.rglob('*') if p.is_file())
    return {'schema': 'scci_rh.stage3.continuation-verification.v1', 'date': '2026-10-12',
            'scope': 'Saved model evidence and artifact audit; no biological, implant, complete circuit or populated CAD qualification.',
            'checks': checks, 'counts': counts,
            'input_normalized_hashes': {p.relative_to(ROOT).as_posix(): normalized_sha(p) for p in source_files},
            'result_hash_policy': 'Canonical parsed JSON; exact compressed bytes. Git manifest binds all committed blobs separately.',
            'result_semantic_or_binary_hashes': {p.relative_to(ROOT).as_posix(): canonical_json_digest(p) if p.suffix == '.json' else sha(p) for p in result_files},
            'test_receipt_sha256': canonical_json_digest(ROOT/'provenance/stage3-test-run.json'),
            'visual_review_sha256': canonical_json_digest(ROOT/'provenance/stage3-continuation-visual-review.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-receipt', action='store_true')
    args = parser.parse_args()
    result = verify()
    path = ROOT/'provenance/stage3-continuation-verification.json'
    if args.write_receipt:
        path.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    else:
        assert read(path) == result, 'Stage 3 continuation receipt differs from current artifacts'
    print(json.dumps({'scope': result['scope'], 'counts': result['counts'], 'checks_passed': len(result['checks'])}, indent=2))


if __name__ == '__main__': main()
