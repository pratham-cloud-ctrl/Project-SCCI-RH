"""Audit saved Stage 3 teacher/source/prediction/requirements evidence.

This checks artifact consistency and failure boundaries. Separate study runners
recompute numerical evidence; neither operation qualifies biological efficacy.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from artifact_hashes import canonical_json_digest
import stage3_source_sensitivity as source
import stage3_assisted_prediction_study as prediction
import stage3_resolved_teacher_study as resolved
import stage3_sparse_baseline_study as sparse
import stage3_isolated_pilot_study as pilot
from scci_rh.stage3.dynamic_response import (
    fit_response_kernel, response_model_from_record, validate_response_recording,
    ProspectiveDose,
)


def read(path):
    data = (ROOT/path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def sha(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def normalized_sha(path):
    return hashlib.sha256((ROOT/path).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()


def bind_sources(identity):
    for path, expected in identity.items():
        assert normalized_sha(path) == expected, f'Stale experiment source: {path}'


def independent_nominal_teacher_streams(library):
    qualification = library['qualification']
    nominal = [row['identity'] for row in qualification['observed_competence']
               if row['identity']['cadence_hz'] == 1.]
    training = qualification['training_identity']
    assert len(nominal) == 4
    for key in ('external_noise_seed', 'voltage_noise_seed'):
        assert len({identity[key] for identity in nominal}) == 4
        withheld = [row['identity'] for row in qualification['independent_validation']
                    if row['identity']['cadence_hz'] == 1.]
        assert len(withheld) == 3
        assert all(identity[key] != training[key] for identity in withheld)
    # Faster-cadence records intentionally pair the same noise streams. They
    # test cadence transfer and are not counted as new independent noise draws.


def verify():
    checks, counts = [], {}
    teacher = read('results/stage3/teacher-library/teacher-library-summary.json')
    bind_sources(teacher['source_sha256'])
    inputs = teacher['input_receipt']
    assert canonical_json_digest(ROOT/inputs['path']) == inputs['sha256']
    assert len(inputs['raw_files']) == 16
    for item in inputs['raw_files']:
        assert sha('results/stage3/expert-validation/'+item['path']) == item['sha256']
    assert not teacher['historical_information_studies_replaced']
    assert not teacher['new_teacher_recordings_generated']
    for generator, library in teacher['libraries'].items():
        independent_nominal_teacher_streams(library)
        assert library == read('results/stage3/teacher-library/'+generator+'.json')
        assert library['source_limits']['source_hold_fidelity_qualified'] is False
    counts['frozen_teacher_input_recordings'] = 16
    checks.append('Frozen teacher input bytes and new observed-library sources match; historical studies and held-source limits are preserved')

    path = 'results/stage3/resolved-teacher/raw.json.gz'
    raw = read(path)
    bind_sources(raw['source_identity'])
    assert resolved.summary(raw) == read('results/stage3/resolved-teacher/summary.json')
    assert raw['capture_count'] == len(raw['captures']) == 16
    assert len(raw['reference_refinements']) == 1
    assert all(r['qualified_for_tested_recording'] for r in raw['reference_refinements'])
    for generator, library in raw['libraries'].items():
        independent_nominal_teacher_streams(library)
        assert library['source_limits']['aperture_resolved_source']
        assert library['source_limits']['source_hold_s'] == 0.
        assert library['library_id'].startswith('SCCI_RH-S3-RESOLVED-TEACHER-1:')
        nominal, faster = library['qualification']['domains']['1'], library['qualification']['domains']['1.15']
        for gate in nominal['references'].values():
            assert gate['qualified'] == (generator == 'idealized_inverse')
        assert all(not gate['qualified'] for gate in faster['references'].values())
        for domain in library['qualification']['domains'].values():
            assert all(g['reference_id'].startswith(library['library_id']+':') for g in domain['references'].values())
    for capture in raw['captures']:
        meta, witness = capture['generation_metadata'], capture['source_observation_witness']
        assert meta['source_variant'] == 'aperture_resolved' and meta['source_hold_s'] == 0.
        assert witness['aperture_support']['all_apertures_before_packet_availability']
        assert len(capture['observations']) == 2400
    counts['new_aperture_resolved_teacher_recordings'] = 16
    counts['nominal_inverse_teacher_reference_admissions'] = 2
    checks.append('Fresh actual-aperture teacher captures bind to qualified nominal and rejected faster references; no learner result is inferred')
    del raw

    raw = read('results/stage3/source-sensitivity/raw.json.gz')
    bind_sources(raw['source_identity']); source.validate_receipt(raw)
    brief = source.readable_summary(raw)
    assert brief == read('results/stage3/source-sensitivity/summary.json')
    aggregate = brief['batch_summary']
    assert aggregate['capture_count_including_training_controls_and_witnesses'] == 75
    assert aggregate['all_pair_noise_and_observation_schedule_invariants_pass']
    assert not aggregate['source_hold_feature_allocation_qualified']
    assert not aggregate['source_hold_prediction_allocation_qualified']
    assert aggregate['dense_active_window_qualified_packets'] == 0
    assert aggregate['redundant_absent_control_feature_differences_all_zero']
    counts.update(moving_source_captures=75, moving_source_reference_grid_pairs=6,
                  acquired_contact_samples=aggregate['total_acquired_raw_contact_samples'])
    checks.append('75 moving-source captures preserve exact paired noise/support, failed source-hold allocations, dense residual failure and ambiguous-field abstention')
    del raw, brief

    path = 'results/stage3/assisted-prediction/raw.json.gz'
    raw = read(path); bind_sources(raw['source_identity'])
    assert prediction.summary(raw, 'raw.json.gz', sha(path)) == read('results/stage3/assisted-prediction/summary.json')
    assert len(raw['training_recordings']) == 4 and len(raw['withheld_recordings']) == 8
    assert len(raw['model']['models']) == 31 and len(raw['validation']) == 8
    for split in raw['model']['partitions']:
        assert split['latest_training_label_s'] < split['earliest_heldout_history_s']
    qualified = {v['context']['recording_id'] for v in raw['validation'] if v['context']['qualified']}
    assert qualified == {'withheld_quarter', 'withheld_half', 'withheld_unassisted', 'withheld_known_cue_shift'}
    assert not raw['scope']['retained_learning_measured'] and not raw['scope']['teacher_library_consumed']
    assert raw['scope']['coupled_feedback_pulses'] == 0
    for audit in raw['admission_audits']:
        for gate in audit['context_admissions'].values():
            assert not gate['admitted'] and gate['pulse_count'] == 0
            assert 'DYNAMIC_EXECUTION_RESPONSE_UNQUALIFIED' in gate['reasons']
            if audit['branch'] == 'actual_electrical':
                assert 'UNQUALIFIED_OBSERVED_AUTHORITY' in gate['reasons']
    counts.update(assisted_training_recordings=4, assisted_complete_withheld_recordings=8,
                  forecast_horizon_models=31, independent_recording_horizon_checks=248,
                  admitted_feedback_pulses=0)
    checks.append('Intervention-aware forecasts retain four passed/four failed complete contexts, purged fitting, actual authority rejection and dynamic-coupling abstention')
    del raw

    delivery = read('results/stage3/delivery-requirements/requirements.json')
    bind_sources(delivery['source_sha256'])
    assert delivery['counts'] == {'independent_observed_calibrations': 4,
        'counterfactual_requirement_rows': 144, 'full_direction_precision_thresholds': 24}
    assert len(delivery['records']) == 4
    assert all(not row['observed_actual_map']['qualified'] for row in delivery['records'])
    counts.update(observed_precision_calibrations=4, precision_requirement_rows=144,
                  precision_thresholds=24)
    checks.append('Requirements recover four observed maps while preserving actual monitor rejection; prospective precision is not circuit evidence')

    dynamic = read('results/stage3/dynamic-response/dynamic-response-summary.json')
    bind_sources(dynamic['source_sha256'])
    assert not dynamic['private_simulator_fit_inputs'] and not dynamic['historical_studies_replaced']
    assert dynamic['numerical_comparison']['qualification_decisions_match']
    assert dynamic['numerical_comparison']['maximum_kernel_difference_m_per_fraction'] < .000150
    assert len(dynamic['numerical_comparison']['records']) == 36
    inherited = dynamic['inherited_actual_steady_map_rejection']
    assert canonical_json_digest(ROOT/inherited['path']) == inherited['sha256']
    assert not inherited['response_map']['qualified']
    admitted_isolated = {'moving_single_0_1', 'moving_single_0_-1',
        'moving_single_1_1', 'moving_single_1_-1', 'moving_paired_same', 'moving_paired_opposite'}
    for grid, study in dynamic['grids'].items():
        raw_path = 'results/stage3/dynamic-response/'+study['raw_file']['path']
        assert sha(raw_path) == study['raw_file']['sha256']
        raw = read(raw_path); bind_sources(raw['source_sha256'])
        assert len(raw['training']) == 24 and len(raw['independent_validation']) == 12
        model = response_model_from_record(study['model'])
        refit = fit_response_kernel(raw['training'], protocol_id=model.model_id)
        assert np.allclose(refit.kernel_m_per_fraction, model.kernel_m_per_fraction, rtol=2e-8, atol=1e-11)
        assert np.allclose(refit.gain_uncertainty_m_per_fraction, model.gain_uncertainty_m_per_fraction, rtol=2e-8, atol=1e-11)
        stream_ids = [value for pair in model.training['observation_noise_ids'] for value in pair]
        assert len(stream_ids) == len(set(stream_ids)) == 48
        assert study['actual_generated_pulses'] == 207 and study['neural_records'] == 0
        assert not study['validation_fit_overlap']
        for branch, assumption in study['prospective_branches'].items():
            admitted = set()
            for recording in raw['independent_validation']:
                observed = validate_response_recording(model, recording, ProspectiveDose(**assumption))
                saved = study['independent_validation'][recording['recording_id']][branch]
                assert observed['qualified'] == saved['qualified']
                assert np.isclose(observed['maximum_empirical_error_allocation_m'],
                                  saved['maximum_empirical_error_allocation_m'], rtol=2e-8, atol=1e-11)
                assert not saved['prediction_used_future_monitor'] and not saved['prediction_used_future_measurements']
                if saved['qualified']: admitted.add(recording['recording_id'])
            assert admitted == (set() if branch == 'actual_electrical_trace_domain' else admitted_isolated)
        assert study['online_candidate_witness']['baseline_contract'] == 'ZERO_FUTURE_COMMAND_BASELINE'
        del raw
    counts.update(dynamic_integration_grids=2, dynamic_calibration_pulses=48,
        dynamic_withheld_trajectories=24, dynamic_recording_branch_checks=72,
        actual_adapter_pulses_in_dynamic_experiment=414)
    checks.append('Actual-adapter finite response is independently refitted from measured raw data; both grids preserve current-monitor rejection and only six isolated prospective domains')

    path = 'results/stage3/sparse-baseline/raw.json.gz'
    raw = read(path); bind_sources(raw['source_identity'])
    assert sparse.summary(raw, 'raw.json.gz', sha(path)) == read('results/stage3/sparse-baseline/summary.json')
    binding = raw['dynamic_receipt_binding']
    assert canonical_json_digest(ROOT/binding['path']) == binding['canonical_json_sha256']
    for item in binding['raw_files']: assert sha(item['path']) == item['sha256']
    assert all(value is False for value in raw['scope'].values())
    assert raw['new_calibration']['seconds_used'] == 12. and len(raw['new_calibration']['measurements']) == 2400
    for grid, study in raw['grids'].items():
        assert len(study['validation']) == 14
        assert study['dynamic_model_id'] == dynamic['grids'][grid]['model']['model_id']
        admitted = set()
        for validation in study['validation']:
            context = validation['context']
            assert len(context['horizons']) == 26
            assert not context['pre_action_candidate_controller_qualified'] and not context['zero_tail_after600ms_assumed']
            for i, h in enumerate(context['horizons'], start=5):
                assert h['excluded_rows'] == sum(h['exclusion_reasons'].values())
                assert h['eligible_rows']+h['excluded_rows'] == context['complete_recording_packets']-i-15
                coverage_rows = 0
                for domain in h['eligible_domains']:
                    start, end = domain['support_start_s'], domain['support_end_s']
                    assert 0. <= start <= end <= context['complete_recording_packets']*.005
                    assert np.isclose(start/.005, round(start/.005), atol=1e-8, rtol=0.)
                    assert np.isclose(end/.005, round(end/.005), atol=1e-8, rtol=0.)
                    coverage_rows += round((end-start)/.005)+1
                    actions = domain['observed_past_actions']
                    assert actions == sorted(actions) and len({tuple(a) for a in actions}) == len(actions)
                    assert all(a[1] in (0, 1) and a[2] in (-1, 1) for a in actions)
                assert coverage_rows == h['eligible_rows']
            assert len(validation['trace']) == sum(h['eligible_rows']+h['excluded_rows'] for h in context['horizons'])
            if context['qualified']: admitted.add(context['recording_id'])
        assert admitted == {'independent_unassisted_nominal'}
    assert all(row['qualification_matches'] and row['horizon_qualification_matches'] for row in raw['numerical_comparison'])
    counts.update(zero_future_calibration_seconds=12, zero_future_execution_horizons=26,
                  zero_future_recording_grid_horizon_checks=2*14*26)
    checks.append('Zero-future baseline retains every row/exclusion and all past-dose uncertainty; only independently observed unassisted motion passes, with no candidate or tail-release privilege')
    del raw

    path = 'results/stage3/isolated-pilot/raw.json.gz'
    raw = read(path); bind_sources(raw['source_sha256'])
    brief = pilot.compact_summary(raw, raw_name='raw.json.gz', raw_sha=sha(path))
    assert brief == read('results/stage3/isolated-pilot/summary.json')
    for name, expected in raw['inputs']['canonical_json_sha256'].items():
        assert canonical_json_digest(ROOT/name) == expected
    inherited = raw['inputs']['dynamic_raw']
    assert sha(inherited['path']) == inherited['sha256']
    assert raw['inputs']['dynamic_model_id'] == dynamic['grids']['2500us']['model']['model_id']
    assert len(raw['baseline']['independent_validation']) == 16 and len(raw['runs']) == 32
    assert not raw['baseline']['runtime_observed_context']['qualified']
    assert not any(h['qualified'] for h in raw['baseline']['runtime_observed_context']['horizons'])
    assert raw['no_live_learner_neural_increment_claim'] and raw['no_skill_transfer_or_multiplier_claim']
    assert brief['total_practice_launched_profiles'] == brief['total_practice_launched_frames'] == 0
    assert brief['total_off_launched_profiles'] == 0 and not brief['stage3_complete']
    run_keys = {(row['branch'], row['family'], row['arm']) for row in raw['runs']}
    assert len(run_keys) == 2*4*4
    practice_count = off_count = 0
    for run in raw['runs']:
        assert len(run['practice']) == 4 and set(run['assessments']) == {'retention_off', 'transfer_off'}
        reference = run['teacher_reference']
        assert reference['qualified']
        if run['arm'].startswith('expert_'):
            assert len(reference['independent_recording_ids']) == 3
            assert .003 < reference['position_error_allocation_m'] < .004
        else:
            assert reference['position_error_allocation_m'] == 0
        for trial in run['practice']:
            assert trial['launched_profiles'] == trial['launched_frames'] == 0
            assert trial['pending_forecasts_at_end'] == 0
            assert not trial['actual_monitor_records']
            assert trial['private_evaluator_only']['true_charge_used_only_by_body']
            for position in trial['measurements']:
                assert np.isclose(position['available_s']-position['support_s'], .025, rtol=0., atol=1e-12)
            practice_count += 1
        for assessment in run['assessments'].values():
            assert not assessment['learning_enabled']
            assert assessment['launched_profiles'] == assessment['launched_frames'] == 0
            assert not assessment['actual_monitor_records']
            off_count += 1
    for run in brief['runs']:
        assert run['retention_off_trajectory_rmse_difference_vs_observe_m'] == 0.
        assert run['transfer_off_trajectory_rmse_difference_vs_observe_m'] == 0.
    assert practice_count == 128 and off_count == 64
    counts.update(isolated_pilot_drift_recordings=16, isolated_pilot_matched_arm_family_branch_runs=32,
        isolated_pilot_practice_trials=practice_count, isolated_pilot_off_assessments=off_count,
        isolated_pilot_admitted_profiles=0)
    checks.append('Complete reset-trial pilot consumes independently bounded teacher references; all conservative drift horizons reject, all 128 practice trials abstain and all 64 OFF assessments remain pulse-free with no retained advantage')
    del raw, brief

    visual = read('provenance/stage3-revision-visual-review.json')
    assert len(visual['files']) == 2
    for name, record in visual['files'].items():
        assert (sha(name) if name.endswith('.png') else normalized_sha(name)) == record['sha256']
    checks.append('Rendered overview and companion scientific SVG match the inspected figure identities')

    document = read('provenance/stage3-revision-document-review.json')
    assert document['page_count'] == 8 and document['visual_review']['pages_inspected'] == list(range(1, 9))
    for name, record in document['files'].items():
        assert (sha(name) if name.endswith('.pdf') else normalized_sha(name)) == record['sha256']
    checks.append('Eight-page illustrated revision report and its editable builder match the recorded full visual review')

    result_paths = sorted(p.relative_to(ROOT).as_posix() for directory in (
        'teacher-library', 'resolved-teacher', 'source-sensitivity', 'assisted-prediction',
        'delivery-requirements', 'dynamic-response', 'sparse-baseline', 'isolated-pilot')
        for p in (ROOT/'results/stage3'/directory).glob('*') if p.is_file())
    source_paths = ['scripts/verify_stage3_revision.py', 'scripts/build_stage3_revision_figures.py',
                    'scripts/build_stage3_revision_brief.py', 'src/scci_rh/stage3/residual_guard.py']
    for record in (teacher, delivery, dynamic): source_paths.extend(record['source_sha256'])
    for directory in ('resolved-teacher', 'source-sensitivity', 'assisted-prediction', 'sparse-baseline'):
        source_paths.extend(read(f'results/stage3/{directory}/summary.json')['source_identity'])
    source_paths.extend(read('results/stage3/isolated-pilot/summary.json')['source_sha256'])
    return {'schema': 'scci_rh.stage3.mechanism-revision-verification.v2', 'date': '2026-10-12',
        'scope': 'Saved evidence audit for a partial Stage3 mechanism revision and negative coupled admission pilot; no admitted pilot intervention, retained learner benefit, biological or complete-implant qualification.',
        'checks': checks, 'counts': counts,
        'input_normalized_hashes': {p: normalized_sha(p) for p in sorted(set(source_paths))},
        'result_semantic_or_binary_hashes': {p: canonical_json_digest(ROOT/p) if p.endswith('.json') else sha(p) for p in result_paths}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-receipt', action='store_true')
    args = parser.parse_args()
    receipt = verify()
    target = ROOT/'provenance/stage3-revision-verification.json'
    if args.write_receipt: target.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    else: assert receipt == read(target), 'Revision receipt differs from current source/results'
    print(json.dumps({'checks_passed': len(receipt['checks']), 'counts': receipt['counts']}, indent=2))
