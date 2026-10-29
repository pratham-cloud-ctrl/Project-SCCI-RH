"""Observable finite response-domain tests; no human efficacy is inferred."""
from copy import deepcopy
from itertools import product
import unittest

import numpy as np

from scci_rh.stage3.response_validation import (
    DomainSpec, PATTERNS, WholeFrameDensity, assess_applicability, capture_response,
    empirical_envelope, fit_route_map, monitored_input, propagate_correction_uncertainty, study_config,
)


class ResponseDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = study_config("conditional_fast_assumed_delivery", "nominal")
        cls.training = [capture_response(0, 710000 + index, cls.config, pattern, 1.,
                                          "conditional_fast_assumed_delivery")
                        for index, pattern in enumerate(tuple(PATTERNS)[:4])]
        cls.response = fit_route_map([c["observable"] for c in cls.training])
        cls.envelope_capture = capture_response(0, 720001, cls.config, "left_positive", 1.,
                                                "conditional_fast_assumed_delivery")
        cls.heldout_capture = capture_response(0, 720002, cls.config, "left_positive", 1.,
                                               "conditional_fast_assumed_delivery")

    def test_density_admits_complete_profiles_on_physical_frames(self):
        for density in (.25, .5, 1.):
            selector = WholeFrameDensity("mixed_opposed", density)
            commands = [selector(k * .025) for k in range(100)]
            self.assertEqual(selector.frame_count, 70)
            self.assertEqual(selector.admitted_count, int(70 * density))
            self.assertTrue(all(tuple(command) in {(0., 0.), (1., -1.)} for command in commands))
            with self.assertRaises(ValueError):
                selector(2.476)
        with self.assertRaises(ValueError):
            WholeFrameDensity("left_positive", .75)

    def test_response_fit_rejects_hidden_truth_and_does_not_read_threshold(self):
        self.assertTrue(self.response["qualified"])
        bad = [deepcopy(c["observable"]) for c in self.training]
        bad[0]["true_recruitment_threshold"] = .12
        with self.assertRaises(ValueError):
            fit_route_map(bad)
        bad = [deepcopy(c["observable"]) for c in self.training]
        bad[0]["monitors"][0]["true_phase_charge_C"] = 600e-9
        with self.assertRaises(ValueError):
            fit_route_map(bad)

    def test_input_replay_consumes_prior_monitor_charge_only(self):
        original = self.training[0]["observable"]
        dose, uncertainty, valid, _ = monitored_input(original, .70)
        changed = deepcopy(original)
        for monitor in changed["monitors"]:
            if monitor["time_s"] > .70:
                monitor["delivered_phase_charge_C"] *= 100
                monitor["charge_uncertainty_C"] *= 100
        same = monitored_input(changed, .70)
        np.testing.assert_array_equal(dose, same[0])
        np.testing.assert_array_equal(uncertainty, same[1])
        self.assertTrue(valid)
        self.assertGreater(uncertainty[0], 0)
        # Multiple coherent monitor uncertainties retain their full average;
        # they are not reduced as if independent random noise.
        self.assertAlmostEqual(uncertainty[0], .074, places=12)

    def test_future_support_or_wrong_frame_route_is_rejected(self):
        capture = deepcopy(self.training[0]["observable"])
        capture["positions"][0]["support_time_s"] = 5.
        with self.assertRaises(ValueError):
            monitored_input(capture, .7)
        capture = deepcopy(self.training[0]["observable"])
        index = next(i for i, frame in enumerate(capture["command_frames"]) if frame["admitted"])
        capture["command_frames"][index]["route_signs"] = [0, 1]
        with self.assertRaises(ValueError):
            monitored_input(capture, .7)

    def test_independent_envelope_never_refits_on_heldout_or_changed_context(self):
        envelope = empirical_envelope(self.envelope_capture["observable"], self.response)
        frozen = deepcopy(self.response)
        nominal = assess_applicability(self.heldout_capture["observable"], self.response, envelope)
        context_capture = capture_response(0, 720003, self.config, "left_positive", 1.,
                                            "conditional_fast_assumed_delivery", changed_context=True)
        changed = assess_applicability(context_capture["observable"], self.response, envelope)
        self.assertEqual(self.response, frozen)
        self.assertTrue(nominal["applicable_within_tested_domain"])
        self.assertLess(changed["empirical_joint_coverage"], nominal["empirical_joint_coverage"])
        self.assertFalse(changed["applicable_within_tested_domain"])
        with self.assertRaises(ValueError):
            assess_applicability(self.envelope_capture["observable"], self.response, envelope)

    def test_null_and_wrong_sign_routes_are_not_qualified_by_small_residuals(self):
        for variant in ("no_authority", "cross_route_adverse"):
            config = study_config("conditional_fast_assumed_delivery", variant)
            captures = [capture_response(0, 730000 + index, config, pattern, 1.,
                                         "conditional_fast_assumed_delivery")["observable"]
                        for index, pattern in enumerate(tuple(PATTERNS)[:4])]
            response = fit_route_map(captures)
            self.assertFalse(response["qualified"])
            if variant == "cross_route_adverse":
                self.assertFalse(response["routes"][1]["qualified"])
                self.assertFalse(response["routes"][3]["qualified"])
            else:
                self.assertFalse(any(route["qualified"] for route in response["routes"]))

    def test_actual_delivery_precision_keeps_authority_rejection(self):
        config = study_config("actual_nominal_delivery", "nominal")
        captures = [capture_response(0, 740000 + index, config, pattern, 1.,
                                     "actual_nominal_delivery")["observable"]
                    for index, pattern in enumerate(tuple(PATTERNS)[:4])]
        response = fit_route_map(captures)
        self.assertFalse(response["qualified"])
        self.assertLess(response["authority_singular_margin_m"], 0)

    def test_delivered_unqualified_monitor_is_never_command_as_dose(self):
        captures = [deepcopy(c["observable"]) for c in self.training]
        for monitor in captures[0]["monitors"]:
            monitor["quality"] = "DELIVERED_UNQUALIFIED"
        response = fit_route_map(captures)
        self.assertFalse(response["qualified"])
        self.assertEqual(response["routes"][0]["reason"], "MONITOR_UNQUALIFIED")
        self.assertEqual(response["routes"][0]["measured_reference_dose"], 0)
        self.assertGreater(response["routes"][0]["response_m"][0], .02)

    def test_correction_and_empirical_coverage_gates_are_frozen(self):
        with self.assertRaises(ValueError):
            DomainSpec(correction_budget_m=.05)
        with self.assertRaises(ValueError):
            DomainSpec(heldout_joint_coverage_floor=.50)

    def test_joint_map_and_input_interval_contains_independent_product_corners(self):
        gain = np.array([[.060, .020], [.010, .050]])
        gain_uncertainty = np.array([[.014, .005], [.005, .015]])
        dose = np.array([.50, .25])
        dose_uncertainty = np.array([.037, .0185])
        baseline = gain @ dose
        bound = propagate_correction_uncertainty(gain, gain_uncertainty, dose, dose_uncertainty)
        errors = []
        for matrix_signs in product((-1, 1), repeat=4):
            perturbed_gain = gain + np.reshape(matrix_signs, (2, 2)) * gain_uncertainty
            for input_signs in product((-1, 1), repeat=2):
                perturbed_dose = dose + np.asarray(input_signs) * dose_uncertainty
                errors.append(np.abs(perturbed_gain @ perturbed_dose - baseline))
        maximum = np.max(errors, axis=0)
        np.testing.assert_allclose(bound, maximum, rtol=1e-13, atol=1e-15)
        first_order_only = gain_uncertainty @ dose + gain @ dose_uncertainty
        self.assertTrue(np.all(maximum > first_order_only))


if __name__ == "__main__":
    unittest.main()
