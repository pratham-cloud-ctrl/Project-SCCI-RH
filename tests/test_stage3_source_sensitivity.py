"""Independent moving-body/source and observational boundary checks."""
import unittest
from copy import deepcopy
import numpy as np
from scci_rh.stage3.source_sensitivity import (MovingBodyReference, capture, compare_sources,
                                           compare_reference_grids, ambiguous_witness)


class SourceSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = MovingBodyReference(0, 'moving_clean')
        cls.held, _ = capture(cls.reference, 'legacy_block_hold', recording_seed=20000)
        cls.resolved, _ = capture(cls.reference, 'aperture_resolved', recording_seed=20000)

    def test_reference_matches_independent_unforced_exponential(self):
        r = MovingBodyReference(0, 'moving_clean', seconds=.2, theta_m=np.zeros((2, 4)),
                                initial_position_m=(.01, -.02), learning=False)
        times = np.linspace(0, .2, 57)
        x, v, theta = r.evaluate(times)
        expected = np.exp(-times[:, None]/.060)*np.array([.01, -.02])
        np.testing.assert_allclose(x, expected, rtol=1e-9, atol=1e-12)
        np.testing.assert_allclose(v, -expected/.060, rtol=1e-9, atol=1e-12)
        np.testing.assert_array_equal(theta, np.zeros_like(theta))

    def test_source_comparison_preserves_actual_noise_and_physical_support(self):
        comparison = compare_sources(self.held, self.resolved)
        self.assertTrue(comparison['identical_actual_noise'])
        self.assertTrue(comparison['identical_external_and_packet_support'])
        self.assertGreater(comparison['maximum_feature_difference_uv'], 2.4)
        self.assertFalse(comparison['within_predeclared_feature_allocation'])
        self.assertTrue(self.resolved['aperture_support']['all_apertures_before_packet_availability'])

    def test_absent_source_cannot_acquire_movement_information_from_resolution(self):
        left, _ = capture(self.reference, 'legacy_block_hold', source_mode='absent')
        right, _ = capture(self.reference, 'aperture_resolved', source_mode='absent')
        self.assertEqual(compare_sources(left, right)['maximum_feature_difference_uv'], 0.)

    def test_only_declared_reference_refinement_can_tolerate_label_difference(self):
        changed = deepcopy(self.resolved)
        changed['rows'][100]['external_position_m'][0] += 1e-6
        with self.assertRaises(AssertionError): compare_sources(self.resolved, changed)
        result = compare_sources(self.resolved, changed, external_tolerance_m=.00015)
        self.assertFalse(result['identical_external_and_packet_support'])
        self.assertTrue(result['paired_observation_support_pass'])
        changed['rows'][100]['external_position_m'][0] += .001
        with self.assertRaises(AssertionError):
            compare_sources(self.resolved, changed, external_tolerance_m=.00015)

    def test_lost_block_does_not_rewrite_the_physical_noise_stream(self):
        lost, _ = capture(self.reference, 'aperture_resolved', recording_seed=20000, missing_block=200)
        self.assertEqual(lost['noise'], self.resolved['noise'])
        self.assertEqual(lost['summary']['packet_count'], 599)
        # A lost block resets recursive history with a nonzero prior-input
        # bound. It is not an in-packet mask gap, so inspect the actual bound
        # and rejection rather than expecting a mask-gap reason.
        resumed = next(row for row in lost['rows'] if row['available_time_s'] > 1.005+1e-12)
        baseline = next(row for row in self.resolved['rows']
                        if row['available_time_s'] == resumed['available_time_s'])
        self.assertFalse(resumed['valid'])
        self.assertGreater(max(resumed['feature_error_bound_uv']), max(baseline['feature_error_bound_uv']))

    def test_wide_clock_allowance_rejects_every_packet(self):
        result, _ = capture(self.reference, 'aperture_resolved', clock_s=120e-6)
        self.assertEqual(result['summary']['qualified_packet_count'], 0)

    def test_dense_artifact_train_keeps_neural_information_unavailable(self):
        reference = MovingBodyReference(0, 'moving_dense_train')
        result, _ = capture(reference, 'aperture_resolved')
        self.assertEqual(result['summary']['qualified_active_window_packets'], 0)

    def test_noninjective_field_retains_indistinguishable_inputs_and_conflicting_labels(self):
        result = ambiguous_witness(self.reference)
        self.assertTrue(result['measured_features_indistinguishable'])
        self.assertTrue(result['paired_noise_exactly_equal'])
        self.assertGreater(result['observed_contradiction_count'], 0)
        self.assertEqual(result['observable_qualification'], 'AMBIGUOUS_FOR_25MM_TARGET_ABSTAIN')

    def test_refinement_compares_at_actual_apertures(self):
        fine = MovingBodyReference(0, 'moving_clean', maximum_step_s=.000625)
        result = compare_reference_grids(self.reference, fine)
        self.assertEqual(result['actual_contact_aperture_count'], 192000)
        self.assertTrue(result['identical_physical_event_boundaries'])
        self.assertTrue(result['position_budget_pass'] and result['velocity_budget_pass'])
        with self.assertRaises(ValueError): self.reference.sources([3.01])


if __name__ == '__main__': unittest.main()
