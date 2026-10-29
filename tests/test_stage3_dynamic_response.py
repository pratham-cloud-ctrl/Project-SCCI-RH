"""Finite response identification, causal composition and uncertainty contracts."""
import copy
from dataclasses import replace
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from scci_rh.stage3.dynamic_response import (ResponsePosition, CompletedDose, FutureResponseFrame,
    ProspectiveDose, DynamicResponseSpec, fit_response_kernel, predict_future_effect,
    validate_response_recording, observed_view, predict_observed_past_response, response_model_from_record)


def fixture_record(name, noise_id, route=0, sign=1, *, noise=1e-6, pulse_s=.25):
    times = np.arange(240)*.005
    lag = times-pulse_s
    shape = np.where(lag >= .035, np.maximum(0., 1.-abs(lag-.100)/.100), 0.)
    gain = np.array([[.015, .002], [.0015, .016]])
    mean = shape[:, None]*gain[:, route]*sign*1.013
    rng = np.random.default_rng(noise_id)
    position = mean+rng.normal(0., noise, mean.shape)
    baseline = rng.normal(0., noise, mean.shape)
    routes = [0, 0]; routes[route] = sign
    return {'recording_id': name,
        'recording_identity': {'measurement_noise_id': noise_id, 'baseline_noise_id': noise_id+1000},
        'measurements': [ResponsePosition(float(t), float(t+.025), tuple(p)) for t, p in zip(times, position)],
        'baseline_measurements': [ResponsePosition(float(t), float(t+.025), tuple(p)) for t, p in zip(times, baseline)],
        'observed_dose': [CompletedDose(pulse_s, pulse_s+.0005, route, sign, 1.013, .441, 'VALID')],
        'planned_frames': [FutureResponseFrame(pulse_s, tuple(routes))],
        'private_evaluator_only': {'theta': object(), 'recruitment': object()}}


class ForbiddenPrivateMapping(dict):
    def __getitem__(self, key):
        if key in {'private_evaluator_only', 'generation', 'recruitment', 'theta'}:
            raise AssertionError('Private generator field was read')
        return super().__getitem__(key)


class DynamicResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training = [fixture_record(f'cal_{route}_{sign}_{repeat}', 100+12*route+6*(sign==1)+repeat,
                                      route, sign)
                        for route in (0, 1) for sign in (-1, 1) for repeat in range(6)]
        cls.model = fit_response_kernel(cls.training)

    def test_recovers_transient_and_off_diagonal_response_from_both_signs(self):
        expected = np.array([[.015, .002], [.0015, .016]])
        np.testing.assert_allclose(self.model.kernel_m_per_fraction[20], expected, atol=1e-6, rtol=0.)
        self.assertEqual(self.model.training['pulse_count'], 24)
        self.assertEqual(self.model.training['measured_response_rows'], 24*121)
        self.assertTrue(all(r['positive_directional_authority'] for r in self.model.training['principal_directional_authority']))
        self.assertFalse(self.model.training['private_inputs_used'])
        self.assertFalse(self.model.training['neural_used'])

    def test_product_interval_contains_cross_term(self):
        dose = ProspectiveDose(1.012, .074)
        out = predict_future_effect(self.model, 1., 1.1, (FutureResponseFrame(1., (1, 0)),), dose)
        g = self.model.kernel_m_per_fraction[20, :, 0]
        u = self.model.gain_uncertainty_m_per_fraction[20, :, 0]
        expected = u*1.012+abs(g)*.074+u*.074
        np.testing.assert_allclose(out['joint_gain_dose_error_m'], expected, atol=1e-14)
        self.assertTrue(np.all(expected > u*1.012+abs(g)*.074))
        for gain_edge in (-1., 1.):
            for dose_edge in (-1., 1.):
                product_error = abs((g+gain_edge*u)*(1.012+dose_edge*.074)-g*1.012)
                self.assertTrue(np.all(product_error <= np.asarray(out['joint_gain_dose_error_m'])+1e-14))

    def test_receipt_load_and_generator_frames_preserve_prediction(self):
        model = response_model_from_record(self.model.to_record())
        frames = (FutureResponseFrame(1., (1, 0)),)
        a = predict_future_effect(model, 1., 1.1, frames)
        b = predict_future_effect(model, 1., 1.1, (f for f in frames))
        self.assertEqual(a, b)
        self.assertTrue(a['domain_qualification_must_be_checked_separately'])
        bad = self.model.to_record(); bad['gain_uncertainty_m_per_fraction'][0][0][0] = -1.
        with self.assertRaises(ValueError): response_model_from_record(bad)

    def test_past_monitor_helper_rejects_future_and_unqualified_release(self):
        dose = CompletedDose(1., 1.0005, 0, 1, 1.013, .441, 'VALID')
        result = predict_observed_past_response(self.model, 1.05, [1.025, 1.1], [dose])
        self.assertEqual(len(result['response_m']), 2)
        self.assertFalse(result['release_after_response_window_qualified'])
        with self.assertRaises(ValueError): predict_observed_past_response(self.model, 1., [1.1], [dose])
        with self.assertRaises(ValueError): predict_observed_past_response(self.model, 1.7, [1.8], [dose])

    def test_future_effect_cannot_double_count_past_commands_or_read_future_monitor(self):
        for frames in ((FutureResponseFrame(.975, (1, 0)),),
                       (FutureResponseFrame(1., (1, 0), known_since_s=1.001),),
                       (FutureResponseFrame(1.001, (1, 0)),),
                       (FutureResponseFrame(1., (.5, 0)),),
                       (FutureResponseFrame(1., (1, 0)), FutureResponseFrame(1., (1, 0)))):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                predict_future_effect(self.model, 1., 1.1, frames)
        with self.assertRaises(ValueError):
            predict_future_effect(self.model, 1., 1.151, ())
        with self.assertRaises(ValueError):
            predict_future_effect(self.model, 1., 1.1, (), self.training[0]['observed_dose'][0])
        zero = predict_future_effect(self.model, 1., 1.1, ())
        self.assertEqual(zero['effect_m'], [0., 0.])
        self.assertEqual(zero['baseline_contract'], 'ZERO_FUTURE_COMMAND_BASELINE')
        self.assertFalse(zero['future_monitor_used'])

    def test_uncertainty_retains_actual_calibration_bound_in_conditional_future(self):
        self.assertEqual(self.model.training['dose_uncertainty_fraction_by_route'], {'0': .441, '1': .441})
        record = fixture_record('heldout', 900)
        nominal = validate_response_recording(self.model, record)
        actual = validate_response_recording(self.model, record,
            ProspectiveDose(1.013, .441, 'ACTUAL_TRACE_REUSE_NOT_FUTURE_GUARANTEE'))
        self.assertLess(nominal['maximum_joint_gain_dose_error_m'], actual['maximum_joint_gain_dose_error_m'])
        self.assertTrue(nominal['qualified'])
        self.assertFalse(actual['qualified'])

    def test_all_withheld_measurements_score_and_never_refit(self):
        record = fixture_record('corrupted_heldout', 901)
        record['measurements'][120] = replace(record['measurements'][120], position_m=(.05, -.05))
        before = self.model.kernel_m_per_fraction.copy()
        result = validate_response_recording(self.model, record)
        self.assertEqual(result['scored_physical_supports'], 240)
        self.assertFalse(result['qualified'])
        np.testing.assert_array_equal(self.model.kernel_m_per_fraction, before)
        self.assertFalse(result['prediction_used_future_measurements'])

    def test_independent_recordings_and_noise_are_required(self):
        repeated = list(self.training)
        repeated[-1] = repeated[-2]
        with self.assertRaises(ValueError): fit_response_kernel(repeated)
        with self.assertRaises(ValueError): validate_response_recording(self.model, self.training[0])
        with self.assertRaises(ValueError): fit_response_kernel(self.training[:-1])

    def test_partial_noise_reuse_and_within_pair_reuse_are_rejected(self):
        for fault in ('reused_measurement', 'reused_baseline', 'within_pair'):
            repeated = copy.deepcopy(self.training)
            identity = repeated[-1]['recording_identity']
            if fault == 'reused_measurement':
                identity['measurement_noise_id'] = repeated[0]['recording_identity']['measurement_noise_id']
            elif fault == 'reused_baseline':
                identity['baseline_noise_id'] = repeated[0]['recording_identity']['baseline_noise_id']
            else:
                identity['baseline_noise_id'] = identity['measurement_noise_id']
            with self.subTest(fault=fault), self.assertRaises(ValueError): fit_response_kernel(repeated)
        record = fixture_record('new_name_reused_training_stream', 900)
        record['recording_identity']['measurement_noise_id'] = self.training[0]['recording_identity']['baseline_noise_id']
        with self.assertRaises(ValueError): validate_response_recording(self.model, record)

    def test_private_generator_fields_are_unread_and_arrays_frozen(self):
        guarded = [ForbiddenPrivateMapping(record) for record in self.training]
        model = fit_response_kernel(guarded)
        self.assertEqual(model.model_id, self.model.model_id)
        with self.assertRaises(ValueError): model.kernel_m_per_fraction[0, 0, 0] = 0.

    def test_invalid_support_and_premature_monitor_fail_closed(self):
        cases = []
        repeated = copy.deepcopy(self.training[0])
        repeated['measurements'][30] = repeated['measurements'][29]
        cases.append(repeated)
        future = copy.deepcopy(self.training[0])
        future['measurements'][30] = replace(future['measurements'][30], available_s=.14)
        cases.append(future)
        monitor = copy.deepcopy(self.training[0])
        monitor['observed_dose'][0] = replace(monitor['observed_dose'][0], available_s=.2501)
        cases.append(monitor)
        uncertain = copy.deepcopy(self.training[0])
        uncertain['observed_dose'][0] = replace(uncertain['observed_dose'][0], uncertainty_fraction=1.014)
        cases.append(uncertain)
        for case in cases:
            with self.subTest(case=case['recording_id']), self.assertRaises(ValueError): observed_view(case)


if __name__ == '__main__':
    unittest.main()
