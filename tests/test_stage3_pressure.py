"""Mechanism and information-boundary checks, not human efficacy tests."""
import json
import unittest
from dataclasses import replace, fields

import numpy as np

from scci_rh.stage3.pressure import (
    PA_PER_MMHG, CalibrationEvidence, DeliveryEvidence, DeliveryMonitorObservation,
    PressureConfig, PressureController, PressureObservation, default_scenarios,
    identify_response, run_study,
)


class PressureMechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nominal = run_study(17)
        cls.off = run_study(17, mode="off")
        cls.adverse = run_study(17, "adverse_response")
        cls.absent = run_study(17, "no_response")
        cls.replay = run_study(17, "stale_replay")

    def test_freshness_uses_physical_peak_instead_of_new_packet_arrival(self):
        old = PressureObservation(120 * PA_PER_MMHG, 0, 1, .75, 9.9, 10)
        self.assertFalse(old.fresh(10))
        fresh = replace(old, support_start_s=9, support_end_s=10,
                        peak_time_s=9.75, arrival_s=10)
        self.assertTrue(fresh.fresh(10))
        self.assertFalse(replace(fresh, support_start_s=10).fresh(10))
        self.assertFalse(replace(fresh, valid=False).fresh(10))

    def test_monitor_view_does_not_expose_delivered_truth(self):
        evidence = DeliveryEvidence(.7, .65, .03)
        view = evidence.controller_view()
        self.assertEqual({f.name for f in fields(view)},
                         {"measured_fraction", "uncertainty_fraction", "qualified", "reason"})
        self.assertNotEqual(evidence.effective_fraction, view.measured_fraction)
        noisy = DeliveryEvidence.from_value({"effective_fraction": 1, "measured_fraction": 1.02,
                                             "uncertainty_fraction": .06, "qualified": True,
                                             "reason": "monitor_gain_error"})
        self.assertEqual(noisy.measured_fraction, 1.02)

    def test_paired_comparison_has_identical_calibration_exposure_and_noise(self):
        n = next(i for i, t in enumerate(self.nominal["trace"]["time_s"]) if t >= 144)
        for key in ("requested_fraction", "actual_delivered_fraction", "observed_sbp_pa",
                    "true_sbp_pa", "observation_peak_s"):
            self.assertEqual(self.nominal["trace"][key][:n], self.off["trace"][key][:n])
        self.assertEqual(self.nominal["calibration"], self.off["calibration"])
        self.assertTrue(all(u == 0 for u in self.off["trace"]["requested_fraction"][n:]))

    def test_null_and_adverse_response_inhibit_feedback_after_calibration(self):
        for result in (self.absent, self.adverse):
            self.assertFalse(result["calibration"]["qualified"])
            trace = result["trace"]
            self.assertTrue(all(u == 0 for t, u in zip(trace["time_s"], trace["requested_fraction"]) if t >= 144))
        self.assertLess(self.adverse["calibration"]["gain_pa_per_fraction"], 0)

    def test_delivery_failure_changes_body_despite_nonzero_requested_command(self):
        def undelivered(request, now):
            return {"effective_fraction": 0, "measured_fraction": 0,
                    "uncertainty_fraction": 0, "qualified": True, "reason": "test_no_delivery"}
        result = run_study(17, delivery=undelivered)
        self.assertGreater(max(result["trace"]["requested_fraction"]), 0)
        self.assertEqual(max(result["trace"]["actual_delivered_fraction"]), 0)
        self.assertEqual(max(result["trace"]["added_pressure_truth_pa"]), 0)
        self.assertFalse(result["calibration"]["qualified"])

    def test_unknown_monitor_measurement_is_not_zero_delivery_evidence(self):
        def unknown(request, now):
            return DeliveryEvidence(.5 if request > 0 else 0, None, 1, False, "MONITOR_STALE")
        result = run_study(17, delivery=unknown)
        self.assertFalse(result["calibration"]["qualified"])
        self.assertTrue(all(u is None for u in result["trace"]["measured_delivered_fraction"]))

    def test_stale_replay_causes_fallback_despite_recent_arrival_and_sequence(self):
        trace = self.replay["trace"]
        indices = [i for i, t in enumerate(trace["time_s"]) if 255 <= t < 275]
        self.assertTrue(all(not trace["observation_fresh"][i] for i in indices))
        self.assertTrue(all(trace["requested_fraction"][i] == 0 for i in indices))
        self.assertTrue(any(trace["observation_arrival_s"][i] > 260 for i in indices))
        self.assertGreater(self.replay["summary"]["fallback_time_s"], 25)

    def test_fallbacks_are_finite_and_have_distinct_support_consequences(self):
        calibration = CalibrationEvidence(40 * PA_PER_MMHG,
            (30 * PA_PER_MMHG, 50 * PA_PER_MMHG), 1, 1, 1, True, "test", 100, 100, 120 * PA_PER_MMHG)
        monitor = DeliveryMonitorObservation(.8, .02, True, "test")
        outputs = {}
        for fallback in ("stop", "finite_hold", "ramp"):
            controller = PressureController(PressureConfig(fallback=fallback), calibration)
            controller.previous_fraction = .8
            outputs[fallback] = [controller.update(t, None, monitor) for t in (10, 11, 12, 15)]
        self.assertEqual(outputs["stop"], [0, 0, 0, 0])
        self.assertEqual(outputs["finite_hold"], [.8, .8, 0, 0])
        np.testing.assert_allclose(outputs["ramp"], [.8, .6, .4, 0])
        self.assertTrue(self.nominal["summary"]["support_remaining_after_command_zero"])

    def test_pressure_is_pressor_only_and_recovery_overshoot_is_preserved(self):
        trace = self.nominal["trace"]
        self.assertTrue(all(0 <= u <= 1 for u in trace["requested_fraction"]))
        self.assertGreater(self.nominal["summary"]["overshoot_above_target_pa"], 5 * PA_PER_MMHG)
        high = run_study(17, "unreachable_high")
        self.assertGreater(high["summary"]["high_pressure_no_lowering_time_s"], 100)
        self.assertGreater(high["summary"]["evaluation_rmse_pa"], 15 * PA_PER_MMHG)

    def test_sensor_rates_neural_invalidation_and_json_receipt(self):
        result = self.nominal
        self.assertEqual(len(result["trace"]["time_s"]), 1681)
        self.assertEqual(len(result["external_observation_records"]), 420)
        self.assertEqual(result["metadata"]["electrical_reference"]["offsets_s"], [0, .002, .004])
        self.assertFalse(result["metadata"]["neural_input_to_controller"])
        for request, admitted, frames in zip(result["trace"]["requested_fraction"],
                result["trace"]["admitted_fraction"], result["trace"]["admitted_reference_frames"]):
            self.assertTrue(0 <= frames <= 30)
            self.assertAlmostEqual(admitted, frames / 30)
            self.assertLessEqual(admitted, request + 1e-12)
        for actual, status in zip(result["trace"]["actual_delivered_fraction"], result["trace"]["neural_recording_quality"]):
            if actual > 0:
                self.assertEqual(status, "DENSE_TRAIN_UNQUALIFIED")
        json.dumps(result, allow_nan=False)

    def test_recursive_body_integration_converges_when_step_halves(self):
        fine = run_study(17, config=PressureConfig(integration_step_s=.0025))
        self.assertLess(abs(fine["summary"]["disturbance_rmse_pa"]
                            - self.nominal["summary"]["disturbance_rmse_pa"]), .2 * PA_PER_MMHG)

    def test_calibration_failure_has_no_secret_gain_or_future_pressure_fallback(self):
        result = identify_response([], [], PressureConfig())
        self.assertFalse(result.qualified)
        self.assertIsNone(result.gain_pa_per_fraction)
        self.assertIsNone(result.baseline_observed_pa)
        delayed = run_study(17, "sensor_delayed")
        self.assertFalse(delayed["calibration"]["qualified"])
        self.assertEqual(max(delayed["trace"]["requested_fraction"]), 0)
        oracle = run_study(17, mode="oracle")
        self.assertTrue(oracle["metadata"]["oracle_excluded_from_claims"])

    def test_monitored_dose_uncertainty_can_inhibit_calibration(self):
        def ambiguous(request, now):
            return DeliveryEvidence(request, request, request + .01, True, "unknown_dose_interval")
        result = run_study(17, delivery=ambiguous)
        self.assertFalse(result["calibration"]["qualified"])
        self.assertEqual(result["calibration"]["reason"], "calibration_dose_interval_includes_zero")


if __name__ == "__main__":
    unittest.main()
