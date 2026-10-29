"""Numerical scheduling witnesses; no physiological tolerance is inferred."""
from dataclasses import replace
import gzip
import importlib.util
import json
import math
from pathlib import Path
import unittest

import numpy as np

from scci_rh.stage3.electrical import PressureDelivery
from scci_rh.stage3.pressure import (
    PA_PER_MMHG, PressureScenario, TimestampedPressureBody, run_study,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pressure_convergence_runner",
                                           ROOT / "scripts/stage3_pressure_convergence.py")
NUMERICS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NUMERICS)


class PressureNumericalTests(unittest.TestCase):
    def test_default_execution_preserves_saved_baseline(self):
        saved = json.loads(gzip.decompress((ROOT / "results/stage3/pressure-raw.json.gz").read_bytes()))["runs"][0]
        actual = json.loads(json.dumps(run_study(0, "nominal", "off", PressureDelivery())))
        # Saved Windows floats are not bitwise Linux/libm reference values.
        # The full structure/discrete fields remain exact; numeric fields use
        # the same tight tolerance as the independent reproduction command.
        NUMERICS.compare(actual, saved)

    def test_nonaligned_onset_occurs_exactly_without_early_response(self):
        scenario = replace(PressureScenario(), onset_delay_s=.1037)
        body = TimestampedPressureBody(scenario)
        body.schedule_dose(0, .65)
        body.advance(.1036)
        self.assertEqual(body.activation, 0)
        body.advance(.1037)
        self.assertEqual(body.activation, 0)
        self.assertEqual(body.applied_events, [(.1037, .65)])
        body.advance(.105)
        self.assertAlmostEqual(body.activation, .65 * (1 - math.exp(-.0013 / scenario.activation_tau_s)), places=14)

    def test_release_hold_expiry_splits_exact_physical_event(self):
        scenario = replace(PressureScenario(), onset_delay_s=.1037, release_delay_s=.1091)
        body = TimestampedPressureBody(scenario)
        body.schedule_dose(0, .65)
        body.advance(1)
        body.schedule_dose(1, 0)
        body.advance(1.1037)
        initial = body.activation
        body.advance(1.2128)
        self.assertAlmostEqual(body.activation, initial, places=14)
        body.advance(1.3)
        self.assertAlmostEqual(body.activation, initial * math.exp(-.0872 / scenario.activation_tau_s), places=14)
        self.assertAlmostEqual(body.release_until_s, 1.2128)

    def test_analytic_cascade_matches_independent_dense_ode(self):
        from scipy.integrate import solve_ivp
        a0, p0, q, g, ta, tp, duration = .2, 100, .65, 4000, .503, 1.007, .37
        answer = solve_ivp(lambda _, state: ((q - state[0]) / ta, (g * state[0] - state[1]) / tp),
                           (0, duration), (a0, p0), method="DOP853", rtol=1e-12, atol=1e-12)
        analytic = NUMERICS.analytic_cascade(a0, p0, q, g, ta, tp, duration)
        np.testing.assert_allclose(analytic, answer.y[:, -1], rtol=1e-11, atol=1e-9)
        same_tau = NUMERICS.analytic_cascade(a0, p0, q, g, 1.0, 1.0, duration)
        answer = solve_ivp(lambda _, state: (q - state[0], g * state[0] - state[1]),
                           (0, duration), (a0, p0), method="DOP853", rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(same_tau, answer.y[:, -1], rtol=1e-11, atol=1e-9)

    def test_event_gain_transition_and_body_refinement_against_analytic(self):
        witness = NUMERICS.fixed_input_reference()
        errors = [run["maximum_error_against_independent_analytic_mmHg"] for run in witness["runs"]]
        self.assertGreater(errors[0], errors[1])
        self.assertGreater(errors[1], errors[2])
        self.assertTrue(all(run["within_frozen_0p2mmHg_budget"] for run in witness["runs"]))
        self.assertTrue(all(run["applied_delayed_dose_events"] == [(.1037, .65)] for run in witness["runs"]))

    def test_no_extra_sensor_oracle_or_shared_adapter_in_matrix(self):
        tasks = NUMERICS.tasks_for_scope()
        self.assertEqual(len(tasks), 136)
        self.assertEqual(sum(task[0] == "baseline_integrated" for task in tasks), 104)
        self.assertEqual(sum(task[0] == "sensor_loss_fallback_integrated" for task in tasks), 8)
        self.assertEqual(sum(task[0] == "nonaligned_stress_integrated" for task in tasks), 24)
        self.assertFalse(any(task[3] == "oracle" for task in tasks))
        self.assertTrue(all(task[5] for task in tasks if task[0] == "nonaligned_stress_integrated"))
        self.assertEqual(NUMERICS.GATES["maximum_policy_pressure_difference_mmHg"], .2)

    def test_timestamp_queue_rejects_noncausal_or_nonfinite_commands(self):
        body = TimestampedPressureBody(PressureScenario())
        body.advance(.5)
        for time, dose in ((.4, .5), (.5, math.nan), (math.inf, .5), (.5, 1.1)):
            with self.assertRaises(ValueError):
                body.schedule_dose(time, dose)
        with self.assertRaises(ValueError):
            body.advance(.4)


if __name__ == "__main__":
    unittest.main()
