"""Independent filtered-history error witnesses and unchanged sample support."""
import unittest
import numpy as np
from scipy.signal import butter, sosfilt
from scci_rh.stage3.filter_residual import FilterResidualBound
from scci_rh.stage3.acquisition import AcquisitionConfig, ContactAcquisition


class ResidualBoundTests(unittest.TestCase):
    def setUp(self):
        self.sos = np.vstack((butter(1, .1, 'highpass', fs=4000, output='sos'),
                              butter(3, 300, 'lowpass', fs=4000, output='sos')))

    def test_actual_omission_error_is_enclosed_for_random_and_adversarial_signs(self):
        rng = np.random.default_rng(991)
        n = 12000
        clean = rng.uniform(-.005, .005, (n, 2))
        mask = np.zeros((n, 2), dtype=bool)
        mask[500:510, 0] = True; mask[300:900:17, 1] = True
        # A signed impulse-response witness targets the last filtered sample.
        impulse = np.zeros(n); impulse[0] = 1.
        h = sosfilt(self.sos, impulse)
        clean[mask[:, 1], 1] = .005*np.sign(h[::-1][mask[:, 1]])
        missing = np.where(mask, 0., clean)
        actual = np.abs(sosfilt(self.sos, clean, axis=0)-sosfilt(self.sos, missing, axis=0))
        bound = FilterResidualBound(self.sos, 2).advance(np.where(mask, .005, 0.))
        self.assertTrue(np.all(actual <= bound+1e-12))
        self.assertGreater(float(np.max(actual)), 1e-5)
        self.assertGreater(bound[-1, 1], 0.)

    def test_stationary_initial_bound_covers_unknown_past_not_a_reset_to_zero(self):
        rng = np.random.default_rng(8)
        past = rng.uniform(-.005, .005, 20000)
        _, state = sosfilt(self.sos, past, zi=np.zeros((len(self.sos), 2)))
        actual, _ = sosfilt(self.sos, np.zeros(1000), zi=state)
        tracker = FilterResidualBound(self.sos, 1)
        tracker.reset(prior_input_bound_v=.005)
        bound = tracker.advance(np.zeros((1000, 1)))[:, 0]
        self.assertTrue(np.all(np.abs(actual) <= bound+1e-12))
        self.assertGreater(bound[-1], 0.)

    def test_uninterrupted_input_has_zero_contamination(self):
        tracker = FilterResidualBound(self.sos, 2)
        np.testing.assert_array_equal(tracker.advance(np.zeros((100, 2))), 0.)
        for bad in ([[float('nan'), 0.]], [[-1., 0.]], [0., 0.]):
            with self.assertRaises(ValueError):
                tracker.advance(bad)


class AcquisitionResidualContracts(unittest.TestCase):
    def test_bound_qualifies_clean_capture_and_rejects_remaining_history(self):
        a = ContactAcquisition(7, AcquisitionConfig(qualification_mode='bounded_residual'))
        for k in range(60):
            packet = a.observe(k*.005, [0., 0.], [0., 0.])
        self.assertTrue(packet.valid)
        np.testing.assert_array_equal(a.last_feature_error_bound_uv, 0.)
        a.add_artifact(.300)
        for k in range(60, 86):
            packet = a.observe(k*.005, [0., 0.], [0., 0.])
        self.assertEqual(packet.usable_fraction, 1.)
        self.assertFalse(packet.valid)
        self.assertIn('FILTER_HISTORY_UNQUALIFIED', packet.reasons)
        self.assertGreater(float(np.max(a.last_feature_error_bound_uv)), 2.4)

    def test_gap_keeps_unknown_prior_state_and_pending_artifact(self):
        a = ContactAcquisition(8, AcquisitionConfig(qualification_mode='bounded_residual'))
        a.add_artifact(.255)
        for k in range(30): a.observe(k*.005, [0., 0.], [0., 0.])
        packet = a.observe(.250, [0., 0.], [0., 0.])
        self.assertIn('FILTER_HISTORY_UNQUALIFIED', packet.reasons)
        packet = a.observe(.255, [0., 0.], [0., 0.])
        self.assertLess(packet.usable_fraction, 1.)

    def test_contiguous_gap_and_clock_allocation_are_independent_gates(self):
        a = ContactAcquisition(9, AcquisitionConfig(maximum_contiguous_gap_s=.0005))
        for k in range(30): a.observe(k*.005, [0., 0.], [0., 0.])
        a.add_artifact(.15)
        packet = a.observe(.15, [0., 0.], [0., 0.])
        self.assertIn('CONTIGUOUS_GAP_UNQUALIFIED', packet.reasons)
        a = ContactAcquisition(9, AcquisitionConfig(clock_uncertainty_s=.001))
        packet = a.observe(0., [0., 0.], [0., 0.])
        self.assertIn('CLOCK_SUPPORT_UNQUALIFIED', packet.reasons)

    def test_aperture_source_changes_volts_without_changing_noise_or_sample_schedule(self):
        a, b = ContactAcquisition(10), ContactAcquisition(10)
        times = np.arange(20)[:, None]/4000 + np.arange(16)[None, :]*3e-6
        sources = np.zeros((20, 16, 4)); sources[:, :, 0] = times/.005
        pa = a.observe(0., [0., 0.], [0., 0.])
        pb = b.observe(0., [0., 0.], [0., 0.], simulator_aperture_sources=sources)
        self.assertEqual(a._rng.bit_generator.state, b._rng.bit_generator.state)
        self.assertEqual((pa.acquired_samples, pa.support_start_s, pa.support_end_s, pa.available_time_s),
                         (pb.acquired_samples, pb.support_start_s, pb.support_end_s, pb.available_time_s))
        self.assertGreater(np.linalg.norm(np.array(pa.values_uv)-pb.values_uv), 0.)
        with self.assertRaises(ValueError):
            b.observe(.005, [0., 0.], [0., 0.], simulator_aperture_sources=np.zeros((20, 4)))

    def test_rejected_gap_request_cannot_reset_state_or_consume_noise(self):
        a = ContactAcquisition(12, AcquisitionConfig(qualification_mode='bounded_residual'))
        for k in range(30): a.observe(k*.005, [0., 0.], [0., 0.])
        state = a._zi.copy(); noise = a._rng.bit_generator.state
        last = a._last_end; count = a.total_raw_samples
        for kwargs in ({'simulator_aperture_sources': np.zeros((20, 4))},
                       {'artifact_amplitude_v': float('nan')}):
            with self.assertRaises(ValueError): a.observe(.250, [0., 0.], [0., 0.], **kwargs)
            np.testing.assert_array_equal(a._zi, state)
            self.assertEqual(a._rng.bit_generator.state, noise)
            self.assertEqual(a._last_end, last); self.assertEqual(a.total_raw_samples, count)

    def test_redundant_source_and_artifact_support_must_be_finite(self):
        a = ContactAcquisition(13, AcquisitionConfig(source_mode='redundant'))
        for invalid in ([0., float('nan')], [0.], None):
            with self.assertRaises(ValueError):
                a.observe(0., [0., 0.], [0., 0.], external_redundant_state=invalid)
        self.assertEqual(a.total_raw_samples, 0)
        with self.assertRaises(ValueError): a.add_artifact(float('nan'))
        self.assertEqual(a._intervals, [])

    def test_one_missing_contact_cannot_hide_in_aggregate_coverage(self):
        a = ContactAcquisition(14, AcquisitionConfig(qualification_mode='bounded_residual', pregate_s=0.))
        for k in range(60): a.observe(k*.005, [0., 0.], [0., 0.])
        for k in range(60, 64):
            t = k*.005
            # Exclude only contact 15 at each aperture; all other 15 contacts
            # still qualify aggregate 93.75% raw coverage.
            a._intervals.extend((t+j/4000+45e-6-1e-8, t+j/4000+45e-6+1e-8) for j in range(20))
            packet = a.observe(t, [0., 0.], [0., 0.])
        self.assertAlmostEqual(packet.usable_fraction, .9375)
        self.assertEqual(packet.per_contact_usable_fraction[15], 0.)
        self.assertFalse(packet.valid)
        self.assertIn('LOW_CONTACT_USABLE_COVERAGE', packet.reasons)
        self.assertIn('STALE_CONTACT_FEATURE', packet.reasons)


if __name__ == '__main__': unittest.main()
