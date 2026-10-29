"""Admission tests on complete frozen observed recordings, without new simulation."""
import copy
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from stage3_teacher_library_study import load_frozen_captures, consumer_witness
from scci_rh.stage3.motor import MotorConfig
from scci_rh.stage3.teacher_library import build_teacher_library, observed_capture_view


class ForbiddenPrivateMapping(dict):
    def __getitem__(self, key):
        if key in {'private_evaluator', 'movement_tau_s', 'theta'}:
            raise AssertionError('private generation input was read')
        return super().__getitem__(key)


class TeacherLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        summary, captures, _ = load_frozen_captures()
        cls.config = MotorConfig(**summary['config'])
        cls.inverse_captures = [c for c in captures if c['generation_metadata']['generator'] == 'idealized_inverse']
        cls.inverse = build_teacher_library(captures, cls.config, generator='idealized_inverse')
        cls.legacy = build_teacher_library(captures, cls.config, generator='legacy_voluntary')

    def build(self, captures):
        return build_teacher_library(captures, self.config, generator='idealized_inverse')

    @staticmethod
    def validation_capture(captures):
        return next(c for c in captures if c['generation_metadata']['cadence_hz'] == 1.
                    and c['generation_metadata']['performance_seed'] == 61007)

    def test_observed_competence_and_template_admission_are_separate(self):
        q = self.inverse.qualification
        self.assertTrue(all(r['qualification']['qualified'] for r in q['observed_competence']))
        self.assertTrue(self.inverse.references['expert_external'].qualified)
        self.assertTrue(self.inverse.references['expert_neural'].qualified)
        for kind in ('expert_external', 'expert_neural'):
            faster = self.inverse.reference_for(kind, cadence_hz=1.15)
            self.assertFalse(faster.qualified)
            self.assertIn('INDEPENDENT_REPRESENTATION_ALLOCATION_FAILED', faster.qualification_reason)
        self.assertEqual([r['identity']['cadence_hz'] for r in q['independent_validation']].count(1.), 3)
        self.assertEqual([r['identity']['cadence_hz'] for r in q['independent_validation']].count(1.15), 4)

    def test_legacy_failure_is_preserved_despite_a_fit(self):
        self.assertIsNotNone(self.legacy.decoder_model)
        for cadence in (1., 1.15):
            for kind in ('expert_external', 'expert_neural'):
                ref = self.legacy.reference_for(kind, cadence_hz=cadence)
                self.assertFalse(ref.qualified)
                self.assertIn('OBSERVED_TEACHER_COMPETENCE_FAILED', ref.qualification_reason)

    def test_complete_withheld_label_change_cannot_refit_model_or_coefficients(self):
        captures = copy.deepcopy(self.inverse_captures)
        capture = self.validation_capture(captures)
        for o, r in zip(capture['observations'], capture['external_records']):
            o['external_position_m'] = [x+.2 for x in o['external_position_m']]
            r['position_m'] = list(o['external_position_m'])
        changed = self.build(captures)
        np.testing.assert_array_equal(changed.decoder_model['weights'], self.inverse.decoder_model['weights'])
        for kind in ('expert_external', 'expert_neural'):
            self.assertEqual(changed.references[kind].coefficients_m, self.inverse.references[kind].coefficients_m)
            self.assertFalse(changed.references[kind].qualified)
        self.assertNotEqual(changed.library_id, self.inverse.library_id)

    def test_voltage_validation_corruption_rejects_neural_without_relabeling_external(self):
        captures = copy.deepcopy(self.inverse_captures)
        capture = self.validation_capture(captures)
        capture['observations'][500]['neural']['values_uv'][0] += 1000.
        changed = self.build(captures)
        self.assertFalse(changed.references['expert_neural'].qualified)
        self.assertTrue(changed.references['expert_external'].qualified)
        row = next(r for r in changed.qualification['independent_validation']
                   if r['identity']['cadence_hz'] == 1. and r['identity']['performance_seed'] == 61007)
        self.assertIn('NEURAL_FEATURE_RANGE_EXCEEDED', row['decoder']['reasons'])
        self.assertEqual(changed.references['expert_neural'].kind, 'expert_neural')

    def test_unavailable_training_neural_capture_preserves_external_reference_and_exposure(self):
        captures = copy.deepcopy(self.inverse_captures)
        for capture in captures:
            for observation in capture['observations']:
                observation['neural']['valid'] = False
        changed = self.build(captures)
        self.assertIsNone(changed.decoder_model)
        self.assertTrue(changed.references['expert_external'].qualified)
        self.assertFalse(changed.references['expert_neural'].qualified)
        self.assertEqual(changed.references['expert_external'].coefficients_m,
                         self.inverse.references['expert_external'].coefficients_m)
        self.assertEqual(changed.references['expert_neural'].kind, 'expert_neural')
        self.assertEqual(changed.resource_accounting['unique_teacher_recording_seconds'], 96.)
        self.assertEqual(changed.resource_accounting['independent_validation_seconds'], 84.)
        self.assertEqual(changed.resource_accounting['template_training_rows'], 1757)
        self.assertEqual(changed.resource_accounting['neural_template_training_rows'], 0)
        witness = consumer_witness(changed, self.config)
        nominal = {row['kind']: row for row in witness['rows'] if row['cadence_hz'] == 1.}
        self.assertTrue(nominal['expert_external']['reference_qualified'])
        self.assertEqual(nominal['expert_neural']['request_fraction'], [0., 0.])
        self.assertEqual(nominal['expert_neural']['policy_reason'], 'UNAVAILABLE_EXPERT_REPRESENTATION')

    def test_neural_support_or_dimension_permission_cannot_remove_external_labels(self):
        for fault in ('training_dimension', 'withheld_support'):
            with self.subTest(fault=fault):
                captures = copy.deepcopy(self.inverse_captures)
                if fault == 'training_dimension':
                    capture = next(c for c in captures if c['generation_metadata']['cadence_hz'] == 1.
                                   and c['generation_metadata']['performance_seed'] == 51000)
                    capture['observations'][500]['neural']['values_uv'].pop()
                else:
                    capture = self.validation_capture(captures)
                    capture['observations'][500]['neural']['available_time_s'] += 1.
                changed = self.build(captures)
                self.assertTrue(changed.references['expert_external'].qualified)
                self.assertFalse(changed.references['expert_neural'].qualified)
                self.assertEqual(changed.references['expert_external'].coefficients_m,
                                 self.inverse.references['expert_external'].coefficients_m)
                self.assertEqual(changed.resource_accounting['template_training_rows'], 1757)

    def test_repeat_or_future_physical_support_rejects_capture(self):
        for invalid_kind in ('repeat', 'future'):
            with self.subTest(invalid_kind=invalid_kind):
                captures = copy.deepcopy(self.inverse_captures)
                capture = self.validation_capture(captures)
                o = capture['observations'][500]
                support = (capture['observations'][499]['external_measurement_time_s'] if invalid_kind == 'repeat'
                           else o['available_time_s']+.01)
                o['external_measurement_time_s'] = support
                capture['external_records'][500]['support_time_s'] = support
                changed = self.build(captures)
                self.assertFalse(changed.references['expert_neural'].qualified)
                self.assertFalse(changed.references['expert_external'].qualified)

    def test_missing_or_duplicated_recording_identity_fails_all_expert_admissions(self):
        for fault in ('missing', 'duplicate_noise'):
            with self.subTest(fault=fault):
                captures = copy.deepcopy(self.inverse_captures)
                altered = self.validation_capture(captures)
                if fault == 'missing':
                    captures.remove(altered)
                else:
                    altered['generation_metadata']['external_noise_seed'] = 60200
                    altered['generation_metadata']['voltage_noise_seed'] = 68001
                changed = self.build(captures)
                self.assertTrue(changed.qualification['identity_errors'])
                self.assertFalse(changed.references['expert_neural'].qualified)
                self.assertFalse(changed.references['expert_external'].qualified)

    def test_private_generator_state_is_unread_and_not_in_consumer_model(self):
        capture = copy.deepcopy(self.inverse_captures[0])
        capture['generation_metadata']['config'] = ForbiddenPrivateMapping(capture['generation_metadata']['config'])
        capture = ForbiddenPrivateMapping(capture)
        view = observed_capture_view(capture)
        self.assertNotIn('private_evaluator', view)
        self.assertNotIn('config', view['generation_metadata'])
        captures = list(self.inverse_captures)
        captures[0] = capture
        guarded = self.build(captures)
        self.assertEqual(guarded.library_id, self.inverse.library_id)
        self.assertEqual(guarded.references, self.inverse.references)

    def test_unavailable_reference_is_zero_policy_with_no_fallback(self):
        witness = consumer_witness(self.inverse, self.config)
        for row in witness['rows']:
            if not row['reference_qualified']:
                self.assertEqual(row['request_fraction'], [0., 0.])
                self.assertEqual(row['policy_reason'], 'UNAVAILABLE_EXPERT_REPRESENTATION')
        outside = self.inverse.reference_for('expert_neural', cadence_hz=1.3)
        self.assertFalse(outside.qualified)
        self.assertEqual(outside.qualification_reason, 'TEACHER_REFERENCE_OUTSIDE_VALIDATED_CADENCE')
        self.assertTrue(self.legacy.references['learner_only'].qualified)
        self.assertEqual(self.legacy.references['learner_only'].training_seconds, 0.)

    def test_full_capture_resource_and_embodiment_limits_are_explicit(self):
        r = self.inverse.resource_accounting
        self.assertEqual(r['unique_teacher_recording_seconds'], 96.)
        self.assertEqual(r['independent_validation_seconds'], 84.)
        self.assertEqual(r['decoder_training_rows'], 1757)
        self.assertEqual(r['template_training_rows'], 1757)
        self.assertEqual(r['neural_template_training_rows'], 1757)
        self.assertEqual(r['decoder_withheld_rows_same_capture'], 568)
        self.assertEqual(r['distinct_observation_noise_realizations'], 4)
        self.assertTrue(r['paired_noise_ids_across_cadences'])
        self.assertFalse(self.inverse.source_limits['source_hold_fidelity_qualified'])
        self.assertEqual(self.inverse.source_limits['source_hold_s'], .005)
        for row in self.inverse.qualification['independent_validation']:
            self.assertTrue(row['decoder']['post_warmup_capture_complete'])
            self.assertGreater(row['decoder']['independent_residuals']['scored_rows'], 2300)

    def test_shortened_recording_cannot_inherit_complete_capture_resource_gate(self):
        captures = copy.deepcopy(self.inverse_captures)
        capture = self.validation_capture(captures)
        capture['observations'] = capture['observations'][:1000]
        capture['external_records'] = capture['external_records'][:1000]
        changed = self.build(captures)
        self.assertFalse(changed.references['expert_external'].qualified)
        self.assertFalse(changed.references['expert_neural'].qualified)
        row = next(r for r in changed.qualification['independent_validation']
                   if r['identity']['cadence_hz'] == 1. and r['identity']['performance_seed'] == 61007)
        self.assertIn('COMPLETE_RECORDING_CLOCK_OR_DURATION_FAILED', row['decoder']['reasons'])


if __name__ == '__main__':
    unittest.main()
