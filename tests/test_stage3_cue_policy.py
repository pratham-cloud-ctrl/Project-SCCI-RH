"""Observed forecast/scheduler contract tests, not human effectiveness tests."""
from dataclasses import fields, replace
import unittest
import numpy as np

from scci_rh.stage3.motor import MotorConfig, Observation, StateEstimate, LearnerMap, ExpertRepresentation, _capture, calibrate
from scci_rh.stage3.acquisition import NeuralFeatures
from scci_rh.stage3.electrical import MotorDelivery
from scci_rh.stage3.cue_policy import (CueConfig, CueCommand, CuePolicy, CueFrameScheduler,
                                  fit_known_cue_forecast, validate_forecast_context)


def observation(now=.5, support=None):
    support = now-.025 if support is None else support
    neural = NeuralFeatures((0.,)*32, now-.02, now-.000205, now-.01, 1., True, (), 320, 0, 0, now, 1.)
    return Observation(now, (0., 0.), support, True, neural)


def state(o):
    return StateEstimate((0., 0.), (0., 0.), o.external_measurement_time_s, .008, True, "EXTERNAL", "TEST")


def response():
    return LearnerMap(((.06, 0.), (0., .06)), ((.002, 0.), (0., .002)),
                      .0675, .005, True, (), 200, 1., .001, .001)


def representation():
    return ExpertRepresentation("expert_neural", ((.1, 0., 0., 0.), (-.1, 0., 0., 0.)),
                                .001, "offline observed expert", "independent_subject", 12.)


def constant_model():
    return {"models": [{"horizon_s": i*.005, "mean": np.zeros(40), "scale": np.ones(40),
        "weights": np.zeros((41, 2)), "qualified": True, "empirical_error_allocation_m": .004}
        for i in range(31)], "context_validation": {"nominal_unassisted": {"qualified": True, "error_allocation_m": .004}}}


def command():
    return CueCommand(1, .5, .475, .525, .526, .605, .130, .004, (.4, -.4),
                      "nominal_unassisted", "TEST")


class FrameContracts(unittest.TestCase):
    def ready(self):
        scheduler = CueFrameScheduler(); o = observation()
        self.assertIsNone(scheduler.observe_guard(o, state(o), .5, "nominal_unassisted"))
        self.assertTrue(scheduler.submit(command(), .5))
        return scheduler

    def test_launch_only_after_pipeline_on_exact_frame_with_fresh_later_guard(self):
        scheduler = self.ready()
        self.assertIsNone(scheduler.tick(.524))
        o = observation(.520)
        scheduler.observe_guard(o, state(o), .520, "nominal_unassisted")
        emitted = scheduler.tick(.525)
        self.assertEqual(emitted, command())
        self.assertIsNone(scheduler.tick(.525))
        self.assertGreaterEqual(emitted.launch_time_s-emitted.created_time_s, .01185)

    def test_missed_frame_and_expiry_cancel_without_late_replay(self):
        for now, reason in ((.5255, "MISSED_FRAME"), (.527, "COMMAND_EXPIRED")):
            scheduler = self.ready()
            self.assertIsNone(scheduler.tick(now)); self.assertIsNone(scheduler.pending)
            self.assertEqual(scheduler.events[-1]["reason"], reason)

    def test_invalid_stale_replayed_and_context_changed_packet_cancel(self):
        cases = ((replace(observation(.505), external_valid=False), "nominal_unassisted"),
                 (observation(.60, .475), "nominal_unassisted"),
                 (observation(.505, .475), "nominal_unassisted"),
                 (observation(.505), "unvalidated_context"))
        for o, context in cases:
            scheduler = self.ready()
            self.assertIsNotNone(scheduler.observe_guard(o, state(o), o.available_time_s, context))
            self.assertIsNone(scheduler.pending); self.assertIsNone(scheduler.tick(.525))

    def test_nonfinite_or_replayed_command_is_rejected(self):
        for bad in (replace(command(), signed_fraction=(float("nan"), 0.)),
                    replace(command(), expected_effect_time_s=float("nan")),
                    replace(command(), launch_time_s=.524),
                    replace(command(), forecast_horizon_s=-.01)):
            scheduler = self.ready()
            self.assertFalse(scheduler.submit(bad, .5))
        scheduler = self.ready()
        self.assertFalse(scheduler.submit(command(), .5))

    def test_later_frame_plan_does_not_starve_earlier_frame(self):
        scheduler = self.ready()
        o = observation(.515)
        scheduler.observe_guard(o, state(o), .515, "nominal_unassisted")
        later = replace(command(), command_id=2, created_time_s=.515, observation_support_s=.490,
                        launch_time_s=.550, expiry_time_s=.551, expected_effect_time_s=.620)
        self.assertTrue(scheduler.submit(later, .515))
        self.assertEqual(scheduler.tick(.525).command_id, 1)
        o = observation(.540)
        scheduler.observe_guard(o, state(o), .540, "nominal_unassisted")
        self.assertEqual(scheduler.tick(.550).command_id, 2)

    def test_future_arrival_and_reversed_clock_cannot_qualify_past_launch(self):
        scheduler = self.ready(); o = observation(.530)
        scheduler.observe_guard(o, state(o), .530, "nominal_unassisted")
        self.assertIsNone(scheduler.tick(.525))
        self.assertEqual(scheduler.events[-1]["reason"], "FUTURE_OBSERVER_AT_LAUNCH")
        scheduler = self.ready(); scheduler.tick(.520)
        self.assertIsNone(scheduler.tick(.515))
        self.assertEqual(scheduler.events[-1]["reason"], "NONMONOTONIC_CLOCK")


class ForecastContracts(unittest.TestCase):
    def ready_policy(self):
        policy = CuePolicy(constant_model())
        for index in range(16):
            o = observation(.425+index*.005)
            result = policy.propose(o, state(o), response(), representation(), o.available_time_s)
        return policy, o, result

    def test_known_cue_family_keeps_original_reactive_cap_and_includes_frame_wait(self):
        _, o, (plan, reason) = self.ready_policy()
        self.assertIsNotNone(plan)
        self.assertEqual(reason, "PLANNED_KNOWN_CUE_COMMAND")
        self.assertAlmostEqual(plan.launch_time_s, .525)
        self.assertAlmostEqual(plan.forecast_horizon_s, .130)
        self.assertGreater(plan.forecast_horizon_s, MotorConfig().maximum_prediction_horizon_s)
        self.assertEqual(MotorConfig().maximum_prediction_horizon_s, .100)
        self.assertEqual(CueConfig().maximum_forecast_horizon_s, .150)
        forbidden = {"theta", "recruitment", "true_phase", "future_position_m"}
        self.assertFalse(forbidden & {f.name for f in fields(CueCommand)})

    def test_unvalidated_context_and_excessive_horizon_abstain(self):
        policy, o, _ = self.ready_policy()
        fresh = observation(o.available_time_s+.005)
        _, reason = policy.propose(fresh, state(fresh), response(), representation(), fresh.available_time_s,
                                  context_id="cue_closed_loop_unvalidated")
        self.assertEqual(reason, "UNVALIDATED_FORECAST_CONTEXT")
        fresh = observation(fresh.available_time_s+.005)
        _, reason = policy.propose(fresh, state(fresh), replace(response(), onset_delay_s=.150),
                                  representation(), fresh.available_time_s)
        self.assertEqual(reason, "CUE_FORECAST_HORIZON_EXCEEDS_VALIDATED_DOMAIN")

    def test_bad_observed_authority_cannot_be_relabelled_qualified(self):
        policy, o, _ = self.ready_policy(); fresh = observation(o.available_time_s+.005)
        bad = replace(response(), gain_uncertainty_m=((.09, 0.), (0., .09)), qualified=True)
        _, reason = policy.propose(fresh, state(fresh), bad, representation(), fresh.available_time_s)
        self.assertEqual(reason, "UNQUALIFIED_OBSERVED_AUTHORITY")

    def test_prospective_dose_budget_includes_gain_dose_joint_term(self):
        _, _, (plan, _) = self.ready_policy()
        g, ug = np.asarray(response().gain_m), np.asarray(response().gain_uncertainty_m)
        u, uu = np.asarray(plan.prospective_measured_fraction), np.asarray(plan.prospective_dose_uncertainty_fraction)
        expected = np.abs(ug)@np.abs(u)+np.abs(g)@uu+np.abs(ug)@uu+plan.empirical_forecast_error_m
        np.testing.assert_allclose(plan.total_correction_error_allocation_m, expected, rtol=0, atol=1e-15)
        self.assertEqual(plan.future_delivery_qualification, "UNQUALIFIED_NOMINAL_ASSUMPTION")
        np.testing.assert_allclose(u, np.asarray(plan.signed_fraction)*1.012)

    def test_forecast_residual_uses_later_arrived_measurement_and_latches(self):
        policy, old, (plan, _) = self.ready_policy()
        self.assertFalse(policy.residual_latched)
        # Advance measured support chronologically until the earlier forecast
        # target is actually observed; no test-time future value is injected.
        target = plan.expected_effect_time_s
        next_support = old.external_measurement_time_s+.005
        while next_support < target-1e-9:
            o = observation(next_support+.025, next_support)
            policy.propose(o, state(o), response(), representation(), o.available_time_s)
            next_support += .005
        o = replace(observation(target+.025, target), external_position_m=(.040, -.040))
        _, reason = policy.propose(o, state(o), response(), representation(), o.available_time_s)
        self.assertEqual(reason, "RECENT_MEASURED_FORECAST_RESIDUAL_EXCEEDS_ALLOCATION")
        self.assertAlmostEqual(policy.first_residual_failure_arrival_s, target+.025)
        later = observation(target+.030, target+.005)
        _, reason = policy.propose(later, state(later), response(), representation(), later.available_time_s)
        self.assertEqual(reason, "RECENT_MEASURED_FORECAST_RESIDUAL_EXCEEDS_ALLOCATION")

    def test_finite_external_fit_has_purged_future_label_support(self):
        c = MotorConfig(body_integration_step_s=.0025, body_integration_method="midpoint_exact_cascade")
        measured, _, _, _ = _capture(4, c, 12.)
        fitted = fit_known_cue_forecast(measured)
        self.assertLess(fitted["training_latest_label_support_s"], fitted["split_support_time_s"]-.100)
        self.assertGreater(fitted["heldout_earliest_history_support_s"], fitted["split_support_time_s"]+.100)
        self.assertEqual(fitted["feature_dimension"], 40)
        self.assertEqual(len(fitted["models"]), 31)
        drifted = [replace(o, external_position_m=(p+.4, q-.4)) for o in measured
                   for p, q in [o.external_position_m]]
        drift = validate_forecast_context(fitted, drifted, "large_geometry_drift")
        self.assertFalse(drift["qualified"])

    def test_actual_independent_dose_precision_remains_negative(self):
        actual, _, _ = calibrate(0, MotorConfig(calibration_s=3.), MotorDelivery())
        policy, o, _ = self.ready_policy(); fresh = observation(o.available_time_s+.005)
        _, reason = policy.propose(fresh, state(fresh), actual, representation(), fresh.available_time_s)
        self.assertEqual(reason, "UNQUALIFIED_OBSERVED_AUTHORITY")


if __name__=="__main__": unittest.main()
