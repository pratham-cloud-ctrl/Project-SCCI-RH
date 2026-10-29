"""Zero-future mean/uncertainty accounting and restricted commitment contracts."""
from dataclasses import asdict, fields, replace
import unittest
import numpy as np
from scci_rh.stage3.dynamic_response import DynamicResponseModel, DynamicResponseSpec, ResponsePosition, CompletedDose, FutureResponseFrame
from scci_rh.stage3.sparse_baseline import (ZeroFutureInput, SparseBaselineSpec, predict_zero_future,
                                       validate_zero_future_recording, intersect_empty_action_domains)


def dynamic():
    kernel = np.zeros((121, 2, 2)); kernel[:, 0, 0] = .010
    error = np.zeros_like(kernel); error[:, 0, 0] = .001
    return DynamicResponseModel('TEST_OBSERVED_KERNEL', kernel, error, np.zeros_like(error), DynamicResponseSpec(), {})


def model():
    models = []
    for index in range(31):
        w = np.zeros((41, 2)); w[1, 0] = w[2, 1] = 1.
        models.append({'horizon_s': index*.005, 'mean': np.zeros(40), 'scale': np.ones(40), 'weights': w,
                       'qualified': True, 'empirical_error_allocation_m': .003})
    return {'training_recording_id': 'train', 'training_noise_identity': 1,
            'forecaster': {'models': models}, 'context_validation': {}}


def packet(past=True):
    rows = tuple(ResponsePosition(.425+i*.005, .450+i*.005, (.010 if past else 0., 0.)) for i in range(16))
    dose = (CompletedDose(.400, .4005, 0, 1, 1., .1, 'VALID'),) if past else ()
    return ZeroFutureInput(.525, rows, dose, .650, 'isolated_nominal' if past else 'unassisted_nominal')


def qualified_fixture(fitted, p, *, context_id='same'):
    actions = [[d.frame_time_s, d.source_id, d.route_sign] for d in p.completed_doses]
    horizons = [{'qualified': True, 'maximum_component_residual_m': 0.,
                 'empirical_error_allocation_m': .0072,
                 'eligible_domains': [{'support_start_s': .500, 'support_end_s': .500,
                                       'observed_past_actions': actions}]} for _ in range(26)]
    fitted['context_validation'][context_id] = {'qualified': True, 'family': p.family,
        'dynamic_model_id': dynamic().model_id, 'horizons': horizons}


def recording(*, pulse=False):
    return {'recording_id': 'independent', 'measurement_noise_id': 2,
        'measurements': [ResponsePosition(i*.005, i*.005+.025, (0., 0.)) for i in range(160)],
        'planned_frames': tuple(FutureResponseFrame(i*.025, (1, 0) if pulse and i == 20 else (0, 0))
                                for i in range(32)),
        'observed_dose': [CompletedDose(.5, .5005, 0, 1, 1., .1, 'VALID')] if pulse else [],
        'family': 'isolated_nominal' if pulse else 'unassisted_nominal'}


def recording_packet(r, index):
    current = r['measurements'][index]
    return ZeroFutureInput(current.available_s, tuple(r['measurements'][index-15:index+1]),
        tuple(d for d in r['observed_dose'] if d.available_s <= current.available_s),
        r['measurements'][-1].support_s, r['family'])


class ZeroFutureContracts(unittest.TestCase):
    def test_strip_and_readd_observed_past_effect_exactly_once(self):
        prediction = predict_zero_future(model(), dynamic(), packet(), .150, require_qualified=False)
        np.testing.assert_allclose(prediction['stripped_unassisted_prediction_m'], (0., 0.))
        np.testing.assert_allclose(prediction['ongoing_observed_past_response_m'], (.010, 0.))
        np.testing.assert_allclose(prediction['position_m'], (.010, 0.))
        self.assertFalse(prediction['candidate_future_response_included'])

    def test_full_product_intervals_propagate_through_history_and_target_without_cancellation(self):
        prediction = predict_zero_future(model(), dynamic(), packet(), .150, require_qualified=False)
        # .001*1 + .010*.1 + .001*.1 = .0021 at each support.
        np.testing.assert_allclose(prediction['history_strip_interval_projection_m'], (.0021, 0.))
        np.testing.assert_allclose(prediction['target_past_response_interval_m'], (.0021, 0.))
        np.testing.assert_allclose(prediction['total_forecast_allocation_m'], (.0072, .003))

    def test_past_tail_future_monitor_and_short_commitment_reject(self):
        p = packet()
        cases = (replace(p, completed_doses=(replace(p.completed_doses[0], frame_time_s=0.),)),
                 replace(p, completed_doses=(replace(p.completed_doses[0], available_s=.526),)),
                 replace(p, committed_zero_until_s=.600), replace(p, cadence_hz=1.15))
        for value in cases:
            with self.assertRaises(ValueError): predict_zero_future(model(), dynamic(), value, .150, require_qualified=False)

    def test_unknown_context_and_wrong_family_cannot_be_called_qualified(self):
        with self.assertRaises(ValueError): predict_zero_future(model(), dynamic(), packet(False), .150, context_id='unknown')
        self.assertNotIn('future_candidate', {f.name for f in fields(ZeroFutureInput)})
        with self.assertRaises(TypeError): ZeroFutureInput(**{**packet().__dict__, 'future_measured_position': (0., 0.)})

    def test_live_large_past_dose_interval_rejects_even_with_saved_context_pass(self):
        fitted = model(); p = packet(); spec = SparseBaselineSpec()
        qualified_fixture(fitted, p)
        accepted = predict_zero_future(fitted, dynamic(), p, .150, context_id='same')
        self.assertTrue(accepted['qualified_for_context'])
        enlarged = replace(p, completed_doses=(replace(p.completed_doses[0], uncertainty_fraction=1.),))
        with self.assertRaisesRegex(ValueError, 'EXCEEDS15MM'):
            predict_zero_future(fitted, dynamic(), enlarged, .150, context_id='same')

    def test_all_eligible_independent_rows_scored_and_future_action_rows_explicitly_excluded(self):
        records = [ResponsePosition(i*.005, i*.005+.025, (0., 0.)) for i in range(160)]
        planned = tuple(FutureResponseFrame(i*.025, (1, 0) if i == 20 else (0, 0)) for i in range(32))
        recording = {'recording_id': 'independent', 'measurement_noise_id': 2,
            'measurements': records, 'observed_dose': [CompletedDose(.5, .5005, 0, 1, 1., .1, 'VALID')],
            'planned_frames': planned, 'family': 'isolated_nominal'}
        # A zero response kernel isolates timing/domain eligibility from accuracy.
        d = dynamic(); d.kernel_m_per_fraction.fill(0); d.gain_uncertainty_m_per_fraction.fill(0)
        checked = validate_zero_future_recording(model(), d, recording)
        self.assertEqual(len(checked['context']['horizons']), 26)
        self.assertTrue(checked['context']['qualified'])
        self.assertTrue(any('NONZERO_FUTURE_COMMAND_WITHIN_TARGET' in h['exclusion_reasons'] for h in checked['context']['horizons']))
        for horizon in checked['context']['horizons']:
            total = horizon['eligible_rows']+horizon['excluded_rows']
            self.assertEqual(total, len(records)-round(horizon['horizon_s']/.005)-15)
        changed = dict(recording); changed['recording_id'] = 'train'
        with self.assertRaises(ValueError): validate_zero_future_recording(model(), d, changed)

    def test_qualified_fresh_support_cannot_be_reused_at_a_later_period(self):
        fitted = model(); r = recording(); d = dynamic()
        d.kernel_m_per_fraction.fill(0); d.gain_uncertainty_m_per_fraction.fill(0)
        validate_zero_future_recording(fitted, d, r)
        p = recording_packet(r, 100)
        accepted = predict_zero_future(fitted, d, p, .150, context_id=r['recording_id'])
        self.assertTrue(accepted['qualified_for_context'])
        shifted = replace(p, now_s=p.now_s+4., committed_zero_until_s=p.committed_zero_until_s+4.,
            history=tuple(replace(row, support_s=row.support_s+4., available_s=row.available_s+4.) for row in p.history))
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_VALIDATED'):
            predict_zero_future(fitted, d, shifted, .150, context_id=r['recording_id'])

    def test_excluded_gap_and_off_grid_support_are_not_inside_a_qualified_envelope(self):
        fitted = model(); r = recording(pulse=True); d = dynamic()
        d.kernel_m_per_fraction.fill(0); d.gain_uncertainty_m_per_fraction.fill(0)
        checked = validate_zero_future_recording(fitted, d, r)
        self.assertTrue(checked['context']['qualified'])
        # At .400 s the declared .500 s command falls before the .550 s target.
        # This support is inside the recording span but outside eligible ranges.
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_VALIDATED'):
            predict_zero_future(fitted, d, recording_packet(r, 80), .150, context_id=r['recording_id'])
        p = recording_packet(r, 120)
        off_grid = replace(p, now_s=p.now_s+.001,
            history=tuple(replace(row, support_s=row.support_s+.001, available_s=row.available_s+.001) for row in p.history))
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_VALIDATED'):
            predict_zero_future(fitted, d, off_grid, .150, context_id=r['recording_id'])

    def test_changed_missing_or_extra_past_action_cannot_reuse_qualified_context(self):
        fitted = model(); p = packet(); qualified_fixture(fitted, p)
        dose = p.completed_doses[0]
        cases = (replace(p, completed_doses=()),
                 replace(p, completed_doses=(replace(dose, route_sign=-1),)),
                 replace(p, completed_doses=(replace(dose, source_id=1),)),
                 replace(p, completed_doses=(replace(dose, frame_time_s=.375, available_s=.3755),)),
                 replace(p, completed_doses=(dose, replace(dose, source_id=1))))
        for changed in cases:
            with self.assertRaisesRegex(ValueError, 'PAST_ACTION_PATTERN_DIFFERS'):
                predict_zero_future(fitted, dynamic(), changed, .150, context_id='same')

    def test_scope_domains_are_built_from_eligible_supports_not_prediction_errors(self):
        d = dynamic(); d.kernel_m_per_fraction.fill(0); d.gain_uncertainty_m_per_fraction.fill(0)
        good = recording(pulse=True)
        bad = {**good, 'recording_id': 'independent_bad_labels',
               'measurements': [replace(p, position_m=(.04, -.04)) if p.support_s >= .65 else p
                                for p in good['measurements']]}
        a = validate_zero_future_recording(model(), d, good)['context']
        b = validate_zero_future_recording(model(), d, bad)['context']
        self.assertTrue(a['qualified']); self.assertFalse(b['qualified'])
        self.assertEqual([h['eligible_domains'] for h in a['horizons']],
                         [h['eligible_domains'] for h in b['horizons']])
        for horizon in a['horizons']:
            count = sum(round((r['support_end_s']-r['support_start_s'])/.005)+1 for r in horizon['eligible_domains'])
            self.assertEqual(count, horizon['eligible_rows'])
            self.assertTrue(any(r['observed_past_actions'] for r in horizon['eligible_domains']))

    def test_fresh_aggregate_intersects_supports_and_preserves_coverage_holes(self):
        def domain(start, end):
            return {'support_start_s': start, 'support_end_s': end, 'observed_past_actions': []}
        common = intersect_empty_action_domains([
            [domain(.1, .4), domain(.5, .7)], [domain(.2, .6)]])
        self.assertEqual(common, [domain(.2, .4), domain(.5, .6)])
        self.assertEqual(intersect_empty_action_domains([[domain(.1, .2)], []]), [])
        with self.assertRaisesRegex(ValueError, 'empty past-action'):
            intersect_empty_action_domains([[{**domain(.1, .2), 'observed_past_actions': [[.0, 0, 1]]}]])
        with self.assertRaisesRegex(ValueError, '5msaggregate'):
            intersect_empty_action_domains([[domain(.101, .2)]])

    def test_missing_scope_receipt_cannot_grant_runtime_qualification(self):
        fitted = model(); p = packet(False); qualified_fixture(fitted, p)
        for horizon in fitted['context_validation']['same']['horizons']:
            del horizon['eligible_domains']
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_VALIDATED'):
            predict_zero_future(fitted, dynamic(), p, .150, context_id='same')


if __name__ == '__main__': unittest.main()
