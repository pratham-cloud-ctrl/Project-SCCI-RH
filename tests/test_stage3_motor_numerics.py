"""Clock/event verification for the artificial motor body, not efficacy tests."""
from dataclasses import replace
import unittest
import numpy as np
from scipy.integrate import solve_ivp

from scci_rh.stage3.motor import MotorConfig, _World, _capture


class IndependentMotorClock(unittest.TestCase):
    def test_private_body_step_cannot_increase_observation_rate(self):
        for step in (.005, .0025, .00125, .000625):
            c = MotorConfig(body_integration_step_s=step, biological_variant="no_authority")
            observations, records, pulses, _ = _capture(4, c, .10, rest=True,
                                                       probe=lambda t: [1., 0.])
            self.assertEqual(len(observations), 20)
            self.assertEqual(sum(o.neural.acquired_samples for o in observations), 6400)
            self.assertEqual([p["time_s"] for p in pulses], [0., .025, .050, .075])
            for k, (o, record) in enumerate(zip(observations, records)):
                self.assertAlmostEqual(o.available_time_s, (k+1)*.005)
                self.assertAlmostEqual(o.external_measurement_time_s, k*.005-.020)
                self.assertAlmostEqual(o.available_time_s-o.external_measurement_time_s, .025)
                self.assertEqual(record["simulator_position_m"], [0., 0.])

    def test_zero_body_gives_identical_noise_and_features_across_grids(self):
        capture = []
        for step in (.005, .0025, .00125, .000625):
            c = MotorConfig(body_integration_step_s=step, biological_variant="no_authority")
            capture.append(_capture(9, c, .20, rest=True))
        for fine in capture[1:]:
            self.assertEqual(capture[0], fine)

    def test_exact_delayed_activation_at_identical_decision_support(self):
        for delay in (.005, .035, .150, .0037):
            for step in (.005, .0025, .00125, .000625):
                c = MotorConfig(body_integration_step_s=step, motor_onset_delay_s=delay)
                world = _World(3, c)
                for k in range(40):
                    now = (k+1)*c.dt_s
                    world.advance(now, [1., 0.], "zero", learning=False, rest=True)
                    expected = .88*(1-np.exp(-max(0., now-delay)/c.motor_activation_tau_s))
                    self.assertAlmostEqual(world.activation[0], expected, places=12)
                self.assertAlmostEqual(world.delay_transitions[0], delay)

    def test_source_velocity_is_whole_five_ms_displacement(self):
        c = MotorConfig(body_integration_step_s=.000625)
        world = _World(2, c)
        previous = world.x.copy()
        world.advance(.005, [0., 0.], "zero", learning=False)
        np.testing.assert_array_equal(world.v, (world.x-previous)/.005)
        self.assertEqual(world.integration_substeps, 8)

    def test_rate_correct_learning_keeps_zero_family_independent_of_stimulation(self):
        for method in ("legacy_endpoint", "midpoint_exact_cascade"):
            c = MotorConfig(body_integration_step_s=.000625, motor_onset_delay_s=.005,
                            body_integration_method=method)
            off, on = _World(5, c), _World(5, c)
            for k in range(100):
                off.advance((k+1)*.005, [0., 0.], "zero", learning=True)
                on.advance((k+1)*.005, [1., -1.], "zero", learning=True)
            np.testing.assert_array_equal(off.theta, on.theta)
            self.assertGreater(np.max(np.abs(off.x-on.x)), .01)

    def test_exact_cascade_matches_independent_constant_input_solution(self):
        for step in (.005, .0025, .00125, .000625):
            c = MotorConfig(body_integration_step_s=step,
                            body_integration_method="midpoint_exact_cascade", motor_onset_delay_s=0.)
            world = _World(3, c)
            target = world.recruitment@np.array([.88, 0.])
            for k in range(40):
                t = (k+1)*.005
                world.advance(t, [1., 0.], "zero", learning=False, rest=True)
                # Response of two cascaded first-order systems to a unit step.
                ta, tm = c.motor_activation_tau_s, c.movement_tau_s
                scale = 1-(ta*np.exp(-t/ta)-tm*np.exp(-t/tm))/(ta-tm)
                np.testing.assert_allclose(world.x, target*scale, rtol=1e-11, atol=1e-14)

    def test_equal_time_constants_do_not_divide_by_zero(self):
        c = MotorConfig(body_integration_method="midpoint_exact_cascade",
                        motor_onset_delay_s=0., motor_activation_tau_s=.060, movement_tau_s=.060)
        world = _World(3, c)
        for k in range(20): world.advance((k+1)*.005, [1., 0.], "zero", learning=False, rest=True)
        expected = (world.recruitment@np.array([.88, 0.]))*(1-(1+.1/.060)*np.exp(-.1/.060))
        np.testing.assert_allclose(world.x, expected, rtol=1e-11, atol=1e-14)

    def test_midpoint_coupled_plasticity_against_independent_ode_all_families(self):
        c = MotorConfig(body_integration_method="midpoint_exact_cascade",
                        body_integration_step_s=.0025, motor_onset_delay_s=0.)
        for family in ("favorable", "zero", "harmful", "dependent"):
            body = _World(3, c)
            recruitment = body.recruitment.copy()
            initial = np.r_[np.zeros(4), body.theta.ravel()]
            def rhs(t, state):
                activation, position, theta = state[:2], state[2:4], state[4:].reshape(2, 4)
                w = 2*np.pi*t
                basis = np.array([np.sin(w), np.cos(w), np.sin(3*w), np.cos(3*w)])
                target = .10*np.array([1., -1.])*basis[0]
                voluntary = theta@basis; stimulation = recruitment@activation
                if family == "zero": error = target-voluntary
                elif family == "favorable": error = target-voluntary+.30*stimulation
                elif family == "harmful": error = target-position-.15*stimulation
                else: error = target-position
                return np.r_[(np.array([.88, -.88])-activation)/.040,
                             (voluntary+stimulation-position)/.060,
                             (.050*np.outer(error, basis)).ravel()]
            times = np.arange(1, 201)*.005
            reference = solve_ivp(rhs, (0., 1.), initial, method="DOP853", t_eval=times,
                                  rtol=1e-12, atol=1e-14, max_step=.0025)
            self.assertTrue(reference.success)
            trajectory = []
            for t in times:
                body.advance(t, [1., -1.], family, learning=True)
                trajectory.append(body.x.copy())
            self.assertLess(np.max(np.abs(np.asarray(trajectory)-reference.y[2:4].T)), .00015)
            self.assertLess(np.max(np.abs(body.theta-reference.y[4:, -1].reshape(2, 4))), .00010)

    def test_invalid_body_grid_and_reversed_time_are_rejected(self):
        for value in (0., -.001, .006, .003, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                replace(MotorConfig(), body_integration_step_s=value)
        with self.assertRaises(ValueError):
            replace(MotorConfig(), external_delay_s=.0037)
        with self.assertRaises(ValueError):
            replace(MotorConfig(), motor_onset_delay_s=-.01)
        with self.assertRaises(ValueError):
            replace(MotorConfig(), body_integration_method="unqualified_solver")
        world = _World(2, MotorConfig())
        world.advance(.005, [0., 0.], "zero", learning=False)
        with self.assertRaises(ValueError):
            world.advance(.003, [0., 0.], "zero", learning=False)


if __name__ == "__main__":
    unittest.main()
