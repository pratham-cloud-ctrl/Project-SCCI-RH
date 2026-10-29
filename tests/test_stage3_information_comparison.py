"""Coupled observable-input comparison with OFF assessments and no body leakage."""
import unittest
from dataclasses import fields
import numpy as np
from scci_rh.stage3.motor import (MotorConfig, Observation, run_study,
                              CONDITIONS, EXTERNAL_HISTORY_CONDITIONS)


class CoupledInformationComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = MotorConfig(calibration_s=3., practice_blocks=1, practice_block_s=1.,
                                 assessment_s=1., motor_onset_delay_s=.005,
                                 body_integration_step_s=.0025,
                                 body_integration_method='midpoint_exact_cascade',
                                 acquisition_qualification_mode='bounded_residual',
                                 acquisition_clock_uncertainty_s=20e-6)
        cls.study = run_study(3, cls.config, families=('favorable',),
                              conditions=CONDITIONS+EXTERNAL_HISTORY_CONDITIONS)

    def test_every_added_arm_has_independent_off_scores(self):
        arms = self.study['families']['favorable']['conditions']
        self.assertEqual(tuple(arms), CONDITIONS+EXTERNAL_HISTORY_CONDITIONS)
        for result in arms.values():
            summary = result['summary']
            self.assertTrue(summary['assistance_off_verified'])
            for name in ('retention_off', 'transfer_off'):
                metrics = summary[name]
                self.assertEqual(metrics['pulse_count'], 0)
                self.assertEqual(metrics['assistance'], 'OFF')
                score = metrics['same_support_estimation']
                self.assertGreater(score['valid_scored_packets'], 0)
                self.assertLessEqual(score['valid_scored_packets'], score['total_packets'])
                self.assertTrue(np.isfinite(score['position_rmse_m']))

    def test_equal_fit_exposure_and_explicit_delivery_assumption(self):
        calibration = self.study['calibration']
        neural, external = calibration['decoder_fit'], calibration['external_history_fit']
        self.assertTrue(external['exact_neural_cohort_matched'])
        self.assertEqual(neural['training_rows'], external['training_rows'])
        self.assertEqual(neural['heldout_rows'], external['heldout_rows'])
        self.assertEqual(neural['labels'], external['labels'])
        self.assertEqual(external['coefficient_count'], 132)
        self.assertEqual(self.study['delivery_model'], 'UNQUALIFIED_NOMINAL_ASSUMPTION')
        self.assertEqual(self.study['config']['acquisition_clock_uncertainty_s'], 20e-6)

    def test_online_body_score_is_evaluator_only_and_support_age_retained(self):
        fields_in_observer = {field.name for field in fields(Observation)}
        self.assertFalse({'body_position', 'theta', 'true_phase_charge_C', 'recruitment'} & fields_in_observer)
        self.assertIn('body state', self.study['information_permissions']['simulator_only'])
        for result in self.study['families']['favorable']['conditions'].values():
            metric = result['practice_blocks'][0]
            self.assertAlmostEqual(metric['maximum_external_support_age_s'], .025)
            self.assertIn('evaluator-only', metric['same_support_estimation']['scope'])
        contrasts = self.study['families']['favorable']['contrasts']
        for rep in ('learner_only', 'expert_external', 'expert_neural'):
            self.assertIn('neural_minus_external_history_retention_m__'+rep, contrasts)


if __name__ == '__main__':
    unittest.main()
