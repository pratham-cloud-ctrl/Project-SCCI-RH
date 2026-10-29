"""Measured competence, inverse generator scope and causal source support."""
import unittest
from dataclasses import fields
import numpy as np
from scci_rh.stage3.motor import MotorConfig, Observation, _capture
from scci_rh.stage3.expert_validation import (capture_expert_performance,
                                         qualify_observed_expert,
                                         inverse_teacher_coefficients)


class ExpertValidationContracts(unittest.TestCase):
    def setUp(self):
        self.config = MotorConfig(body_integration_step_s=.0025,
                                  body_integration_method='midpoint_exact_cascade',
                                  acquisition_qualification_mode='bounded_residual',
                                  acquisition_clock_uncertainty_s=20e-6)

    def test_legacy_capture_preserves_existing_teacher_observations(self):
        new = capture_expert_performance(51000, self.config, duration_s=1.)
        old, records, _, _ = _capture(51000, self.config, 1., expert=True)
        self.assertEqual(new['observations'], old)
        for observed, previous in zip(new['external_records'], records):
            self.assertEqual(observed['position_m'], previous['observed_position_m'])
            self.assertEqual(observed['support_time_s'], previous['external_support_s'])

    def test_inverse_body_tracks_sinusoid_without_hidden_future_online_input(self):
        c = MotorConfig(external_noise_m=0., body_integration_step_s=.0025,
                        body_integration_method='midpoint_exact_cascade')
        capture = capture_expert_performance(51000, c, generator='idealized_inverse', duration_s=1.5)
        records = capture['private_evaluator']['records']
        error = np.array([np.array(r['position_m'])-r['task_goal_m'] for r in records])
        self.assertLess(np.max(np.abs(error)), 1e-5)
        self.assertTrue(capture['qualification']['qualified'])
        self.assertEqual(capture['generation_metadata']['privilege'], 'PRIVATE_EXPERT_MOVEMENT_TAU_IN_GENERATOR_ONLY')
        self.assertAlmostEqual(inverse_teacher_coefficients(c)[0, 1], .1*.06*2*np.pi)
        online_fields = {f.name for f in fields(Observation)}
        self.assertFalse({'theta', 'movement_tau_s', 'body_state'} & online_fields)

    def test_competence_is_observed_and_private_truth_cannot_override_failed_labels(self):
        c = MotorConfig(external_noise_m=0., body_integration_step_s=.0025,
                        body_integration_method='midpoint_exact_cascade')
        capture = capture_expert_performance(51000, c, generator='idealized_inverse', duration_s=1.5)
        records = [{**r, 'position_m': [p+.1 for p in r['position_m']]} for r in capture['external_records']]
        qualified = qualify_observed_expert(records, c)
        self.assertFalse(qualified['qualified'])
        self.assertIn('SPATIAL_THRESHOLD_FAILED', qualified['reason'])
        self.assertTrue(capture['qualification']['qualified'])

    def test_source_apertures_precede_future_world_and_noise_ids_are_independent(self):
        a = capture_expert_performance(51000, self.config, duration_s=.5)
        b = capture_expert_performance(61007, self.config, duration_s=.5)
        self.assertEqual(a['private_evaluator']['records'][0]['position_m'], [0., 0.])
        self.assertEqual(a['generation_metadata']['contact_geometry_seed'], b['generation_metadata']['contact_geometry_seed'])
        self.assertNotEqual(a['generation_metadata']['voltage_noise_seed'], b['generation_metadata']['voltage_noise_seed'])
        self.assertNotEqual(a['voltage_acquisition_witness']['filter_input_v_sha256'], b['voltage_acquisition_witness']['filter_input_v_sha256'])
        self.assertEqual(a['voltage_acquisition_witness']['aperture_samples'], 100*20*16)
        for o in a['observations']:
            self.assertLess(o.neural.support_end_s, o.available_time_s)
            self.assertAlmostEqual(o.available_time_s-o.external_measurement_time_s, .025)

    def test_replayed_external_records_cannot_qualify(self):
        capture = capture_expert_performance(51000, self.config, duration_s=.5)
        records = capture['external_records']
        records[20]['support_time_s'] = records[19]['support_time_s']
        self.assertFalse(qualify_observed_expert(records, self.config)['qualified'])


if __name__ == '__main__':
    unittest.main()
