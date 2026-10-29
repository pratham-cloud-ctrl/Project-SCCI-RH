"""Measured-history causality and capacity checks, not biological efficacy."""
import unittest
from types import SimpleNamespace
import numpy as np

from scci_rh.stage3.external_history import (CausalExternalHistoryDecoder,
                                         fit_external_history)
from scci_rh.stage3.motor import MotorConfig, _fit_neural, _capture


def packet(support, position, *, available=None, neural_valid=True, external_valid=True):
    return SimpleNamespace(available_time_s=support+.025 if available is None else available,
                           external_measurement_time_s=support,
                           external_position_m=tuple(position), external_valid=external_valid,
                           neural=SimpleNamespace(valid=neural_valid,
                                                  values_uv=tuple(np.tile(position, 16)*1000)))


def measured_capture(count=1000, noise=1e-4):
    rng = np.random.default_rng(18)
    result = []
    for i in range(count):
        t = i*.005
        measured = np.array([.08*np.sin(2*np.pi*t), .07*np.cos(1.4*np.pi*t)])
        measured += rng.normal(0, noise, 2)
        result.append(packet(t, measured, neural_valid=i>=20))
    return result


class ExternalHistoryContracts(unittest.TestCase):
    def test_reference_acquisition_cohort_has_identical_training_exposure(self):
        c = MotorConfig(calibration_s=3.)
        observations, _, _, _ = _capture(7, c, c.calibration_s)
        neural = _fit_neural(observations)
        external = fit_external_history(observations,
                                        external_freshness_s=c.external_freshness_s)
        self.assertTrue(external["exact_neural_cohort_matched"])
        self.assertEqual(external["calibration_observation_rows"], 600)
        self.assertEqual(external["training_rows"], neural["training_rows"])
        self.assertEqual(external["heldout_rows"], neural["heldout_rows"])

    def test_comparable_parameter_and_calibration_capacity(self):
        observations = measured_capture()
        external = fit_external_history(observations)
        neural = _fit_neural(observations)
        self.assertEqual(external["weights"].shape, neural["weights"].shape)
        self.assertEqual(external["coefficient_count"], 132)
        self.assertEqual(external["feature_dimension"], 32)
        self.assertEqual(external["ridge_penalty"], .5)
        self.assertEqual(external["training_rows"], neural["training_rows"])
        self.assertEqual(external["heldout_rows"], neural["heldout_rows"])
        self.assertTrue(external["exact_neural_cohort_matched"])
        self.assertEqual(external["labels"], neural["labels"])
        self.assertGreater(external["heldout_rows"], 100)
        self.assertLess(external["rmse"], .001)
        self.assertLess(external["velocity_rmse"], .03)

    def test_validation_labels_do_not_change_training_weights(self):
        observations = measured_capture()
        before = fit_external_history(observations)
        cut = before["split_support_time_s"]
        changed = [packet(o.external_measurement_time_s,
                          np.asarray(o.external_position_m)+(np.array([.10, -.08])
                           if o.external_measurement_time_s >= cut-.100 else 0.),
                          neural_valid=o.neural.valid) for o in observations]
        after = fit_external_history(changed)
        np.testing.assert_array_equal(before["mean"], after["mean"])
        np.testing.assert_array_equal(before["scale"], after["scale"])
        np.testing.assert_array_equal(before["weights"], after["weights"])
        self.assertEqual(before["training_support_sha256"], after["training_support_sha256"])
        self.assertNotEqual(before["rmse"], after["rmse"])

    def test_neural_values_and_private_body_attributes_are_not_inputs(self):
        class FlagsOnly:
            valid = True
            @property
            def values_uv(self):
                raise AssertionError("External history cannot read neural values")
        observations = measured_capture()
        for i, o in enumerate(observations):
            o.neural = FlagsOnly() if i >= 20 else SimpleNamespace(valid=False)
        model = fit_external_history(observations)
        self.assertIsNotNone(model)
        decoder = CausalExternalHistoryDecoder(MotorConfig(), model)
        for observation in observations[:100]:
            estimate = decoder.estimate(observation)
        self.assertEqual(estimate.source, "LEARNED_EXTERNAL_HISTORY")
        self.assertEqual(estimate.support_time_s, observations[99].external_measurement_time_s)
        self.assertTrue(estimate.valid)

    def test_online_same_support_and_transport_delay_are_retained(self):
        observations = measured_capture()
        model = fit_external_history(observations)
        decoder = CausalExternalHistoryDecoder(MotorConfig(), model)
        for observation in observations[:40]:
            estimate = decoder.estimate(observation)
        self.assertAlmostEqual(observations[39].available_time_s-estimate.support_time_s, .025)
        self.assertEqual(len(decoder._external), 16)
        self.assertAlmostEqual(decoder._external[-1][0]-decoder._external[0][0], .075)
        stale = decoder.estimate(packet(.2, (0., 0.), available=.26))
        self.assertFalse(stale.valid)
        self.assertEqual(stale.reason, "EXTERNAL_STALE_OR_INVALID")

    def test_replayed_reversed_and_nonfinite_packets_are_invalid(self):
        observations = measured_capture()
        for malicious in (packet(.195, (0., 0.), available=.23),
                          packet(.190, (0., 0.), available=.23),
                          packet(float("nan"), (0., 0.), available=.23),
                          packet(.2, (float("inf"), 0.), available=.23),
                          packet(.24, (0., 0.), available=.23),
                          packet(.2, (0., 0.), available=.20)):
            decoder = CausalExternalHistoryDecoder(MotorConfig(), None)
            for o in observations[:40]:
                decoder.estimate(o)
            estimate = decoder.estimate(malicious)
            self.assertFalse(estimate.valid)
            self.assertEqual(len(decoder._external), 0)

    def test_history_gap_does_not_invent_missing_measurements(self):
        decoder = CausalExternalHistoryDecoder(MotorConfig(), None)
        for o in measured_capture(40):
            decoder.estimate(o)
        estimate = decoder.estimate(packet(.210, (0., 0.)))
        self.assertFalse(estimate.valid)
        self.assertEqual(estimate.reason, "DECODER_HISTORY_WARMUP")
        self.assertEqual(len(decoder._external), 1)
        for i in range(1, 16):
            estimate = decoder.estimate(packet(.210+i*.005, (0., 0.)))
        self.assertTrue(estimate.valid)
        self.assertEqual(estimate.source, "EXTERNAL_LINEAR_HISTORY")

    def test_gapped_calibration_reports_failure_of_exact_cohort_matching(self):
        observations = measured_capture()
        observations[300].external_valid = False
        model = fit_external_history(observations)
        self.assertIsNotNone(model)
        self.assertFalse(model["exact_neural_cohort_matched"])
        self.assertGreater(model["excluded_history_rows"], 0)
        self.assertLess(model["history_eligible_rows"], model["matched_eligible_rows"])

    def test_invalid_fitting_settings_are_rejected(self):
        for fraction in (0., 1., float("nan")):
            with self.assertRaises(ValueError):
                fit_external_history([], heldout_fraction=fraction)


if __name__ == "__main__":
    unittest.main()
