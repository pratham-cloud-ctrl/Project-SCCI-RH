"""Private moving-body sources versus observed contact features.

Only this evaluator evaluates latent trajectories and lead fields. Observer
fits receive voltage-derived packets and independently measured positions.
The encoding is a synthetic hypothesis, not a spinal observability claim.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from collections import Counter
import hashlib

import numpy as np
from scipy.integrate import solve_ivp

from . import motor
from .acquisition import AcquisitionConfig, ContactAcquisition

SOURCE_VARIANTS = ("legacy_block_hold", "instantaneous_block_hold", "aperture_resolved")
SCENARIOS = ("moving_clean", "moving_sparse_train", "moving_dense_train")
BUDGETS = {
    "reference_position_difference_m": .00015,
    "reference_velocity_difference_m_per_s": .010,
    "source_hold_feature_difference_uv": 2.4,
    "source_hold_position_prediction_difference_m": .0015,
    "observable_position_fit_rmse_m": .025,
    "observable_position_component_error_m": .025,
    "ambiguous_feature_equivalence_uv": 1e-10,
}
SECONDS = 3.
REFERENCE_GRIDS = (.0025, .000625)


def commands(scenario, seconds=SECONDS):
    """Known whole-profile events; no request uses a future body state."""
    if scenario not in SCENARIOS:
        raise ValueError("unknown moving-body scenario")
    frames = []
    for frame in range(round(seconds * 40)):
        time = frame / 40
        active = .3 <= time < 2.7
        admitted = active and (scenario == "moving_dense_train" or
                              (scenario == "moving_sparse_train" and frame % 4 == 0))
        signs = (1., -1.) if int(time // .5) % 2 == 0 else (-1., 1.)
        frames.append({"time_s": time, "signed_true_reference_dose": list(signs if admitted else (0., 0.)),
                       "whole_fixed_profile_admitted": admitted})
    return frames


class MovingBodyReference:
    """Event-split DOP853 integration of the declared full12-state body ODE."""
    def __init__(self, subject_seed, scenario, maximum_step_s=.0025, *, onset_s=.035,
                 seconds=SECONDS, tolerance=1e-11, theta_m=None, cadence_hz=1.,
                 learning=True, initial_position_m=None):
        self.seed, self.scenario, self.seconds = subject_seed, scenario, seconds
        self.cadence_hz, self.learning = float(cadence_hz), bool(learning)
        if not np.isfinite(cadence_hz) or cadence_hz <= 0:
            raise ValueError("cadence must be finite and positive")
        self.config = replace(motor.MotorConfig(), motor_onset_delay_s=onset_s)
        private = motor._World(subject_seed, self.config)
        self.recruitment = private.recruitment.copy()
        self.initial_theta = private.theta.copy() if theta_m is None else np.asarray(theta_m, dtype=float).copy()
        self.initial_position = np.zeros(2) if initial_position_m is None else np.asarray(initial_position_m, dtype=float).copy()
        if self.initial_theta.shape != (2, 4) or self.initial_position.shape != (2,) or not (
                np.all(np.isfinite(self.initial_theta)) and np.all(np.isfinite(self.initial_position))):
            raise ValueError("finite theta2x4 and position2 required")
        self.frames = commands(scenario, seconds)
        self.onset_s = onset_s
        self.maximum_step_s, self.tolerance = maximum_step_s, tolerance
        events = [(row["time_s"] + onset_s, np.asarray(row["signed_true_reference_dose"]))
                  for row in self.frames if row["time_s"] + onset_s < seconds]
        # Keep every frame transition explicit; repeated drive values do not
        # change the ODE but must never be rounded onto an integration grid.
        self.boundaries = sorted({0., seconds} | {time for time, _ in events}
                                 | {float(time) for time in np.arange(2., seconds, 2.)})
        state = np.r_[np.zeros(2), self.initial_position, self.initial_theta.ravel()]
        self.segments = []
        self.rhs_evaluations = 0
        for left, right in zip(self.boundaries[:-1], self.boundaries[1:]):
            raw = np.zeros(2)
            for time, value in events:
                if time <= (left + right) / 2:
                    raw = value
            drive = np.sign(raw) * np.maximum(0., np.abs(raw) - self.config.recruitment_threshold_fraction)
            direction = 1. if int(((left + right) / 2) // 2) % 2 == 0 else -1.
            rhs = self._rhs(drive, direction)
            result = solve_ivp(rhs, (left, right), state, method="DOP853",
                               rtol=tolerance, atol=tolerance * .01,
                               max_step=maximum_step_s, dense_output=True)
            if not result.success:
                raise AssertionError(result.message)
            self.segments.append((left, right, result.sol, drive, direction))
            self.rhs_evaluations += result.nfev
            state = result.y[:, -1]

    def _rhs(self, drive, direction):
        c = self.config
        recruitment = self.recruitment

        def rhs(time, state):
            a, x, theta = state[:2], state[2:4], state[4:].reshape(2, 4)
            phase = 2 * np.pi * self.cadence_hz * time
            phi = direction * np.array([np.sin(phase), np.cos(phase), np.sin(3 * phase), np.cos(3 * phase)])
            desired = c.foot_amplitude_m * np.array([1., -1.]) * phi[0]
            voluntary = theta @ phi
            stimulation = recruitment @ a
            theta_rate = (c.learning_step * np.outer(desired - voluntary + c.stimulation_teaching_fraction * stimulation, phi)
                          if self.learning else np.zeros((2, 4)))
            return np.r_[(drive - a) / c.motor_activation_tau_s,
                         (voluntary + stimulation - x) / c.movement_tau_s, theta_rate.ravel()]
        return rhs

    def evaluate(self, times):
        """Return private position, right-continuous physical derivative, theta."""
        query = np.asarray(times, dtype=float)
        if not np.all(np.isfinite(query)) or np.any(query < -1e-12) or np.any(query > self.seconds + 1e-12):
            raise ValueError("trajectory query outside its declared physical support")
        flat = np.maximum(query.ravel(), 0.)
        state = np.zeros((len(flat), 12))
        velocity = np.zeros((len(flat), 2))
        for index, (left, right, solution, drive, direction) in enumerate(self.segments):
            selected = (flat >= left) & ((flat < right) if index < len(self.segments) - 1 else (flat <= right))
            if not np.any(selected):
                continue
            values = solution(flat[selected]).T
            state[selected] = values
            phase = 2 * np.pi * self.cadence_hz * flat[selected]
            phi = direction * np.stack((np.sin(phase), np.cos(phase), np.sin(3 * phase), np.cos(3 * phase)), axis=1)
            voluntary = np.einsum("nij,nj->ni", values[:, 4:].reshape(-1, 2, 4), phi)
            velocity[selected] = (voluntary + values[:, :2] @ self.recruitment.T - values[:, 2:4]) / self.config.movement_tau_s
        return state[:, 2:4].reshape(query.shape + (2,)), velocity.reshape(query.shape + (2,)), state[:, 4:].reshape(query.shape + (2, 4))

    def sources(self, times, *, swap_feet=False):
        position, velocity, _ = self.evaluate(times)
        if swap_feet:
            position, velocity = position[..., ::-1], velocity[..., ::-1]
        return np.concatenate((position / self.config.foot_amplitude_m,
                               velocity / (2 * np.pi * self.config.foot_amplitude_m)), axis=-1)

    def receipt(self):
        grid = np.arange(round(self.seconds * 200) + 1) / 200
        position, velocity, theta = self.evaluate(grid)
        return {"subject_seed": self.seed, "scenario": self.scenario, "seconds": self.seconds,
                "maximum_internal_step_s": self.maximum_step_s, "rtol": self.tolerance,
                "atol": self.tolerance * .01, "onset_delay_s": self.onset_s,
                "exact_event_boundaries_s": self.boundaries, "rhs_evaluations": self.rhs_evaluations,
                "learning_family": "chosen_favorable" if self.learning else "learning_off",
                "cadence_hz": self.cadence_hz, "initial_theta_m": self.initial_theta.tolist(),
                "initial_position_m": self.initial_position.tolist(), "command_frames": self.frames,
                "private_reference": {"time_s": grid.tolist(), "position_m": position.tolist(),
                                      "physical_velocity_m_per_s": velocity.tolist(), "theta_m": theta.tolist()},
                "claim_boundary": "independent numerical solution of synthetic coupled movement/activation/plasticity; not measured biology"}


class NoiseAudit:
    def __init__(self, rng):
        self.rng = rng
        self.initial = rng.bit_generator.state
        self.digest = hashlib.sha256()
        self.calls = 0
        self.count = 0
        self.total = self.total_square = 0.

    def normal(self, *args, **kwargs):
        result = self.rng.normal(*args, **kwargs)
        array = np.asarray(result, dtype="<f8")
        self.digest.update(array.tobytes())
        self.calls += 1
        self.count += array.size
        self.total += float(array.sum())
        self.total_square += float(np.sum(array ** 2))
        return result

    def receipt(self):
        return {"calls": self.calls, "scalar_count": self.count,
                "actual_noise_sha256": self.digest.hexdigest(),
                "initial_generator_state": self.initial, "final_generator_state": self.rng.bit_generator.state,
                "mean": self.total / self.count, "second_moment": self.total_square / self.count}


def acquisition_config(source_mode="informative", *, clock_s=20e-6):
    return AcquisitionConfig(source_mode=source_mode, qualification_mode="bounded_residual",
                             clock_uncertainty_s=clock_s, maximum_contiguous_gap_s=.002)


def capture(reference, source_variant, *, source_mode="informative", recording_seed=103,
            clock_s=20e-6, missing_block=None, drift_time_s=None,
            ambiguous_field=False, swap_feet=False):
    if source_variant not in SOURCE_VARIANTS:
        raise ValueError("unknown source approximation")
    c = acquisition_config(source_mode, clock_s=clock_s)
    acquisition = ContactAcquisition(reference.seed + 8300, c, noise_seed=recording_seed)
    if ambiguous_field:
        # Private forward-model counterexample only; never passed to a fit.
        acquisition._lead[:, 1] = acquisition._lead[:, 0]
        acquisition._lead[:, 3] = acquisition._lead[:, 2]
    noise = NoiseAudit(acquisition._rng)
    acquisition._rng = noise
    for frame in reference.frames:
        if frame["whole_fixed_profile_admitted"]:
            acquisition.add_artifact(frame["time_s"])
    starts = np.arange(round(reference.seconds * 200)) / 200
    external_noise = np.random.default_rng(recording_seed + 800000).normal(0, .0015, (len(starts), 2))
    external_position, _, _ = reference.evaluate(np.maximum(0., starts - .020))
    if swap_feet:
        external_position = external_position[:, ::-1]
    measured_external = external_position + external_noise
    positions, velocities, _ = reference.evaluate(starts)
    if swap_feet:
        positions, velocities = positions[:, ::-1], velocities[:, ::-1]
    past, _, _ = reference.evaluate(np.maximum(0., starts - .005))
    if swap_feet:
        past = past[:, ::-1]
    legacy_velocity = (positions - past) / .005
    sample_times = starts[:, None, None] + np.arange(20)[None, :, None] / 4000 + np.arange(16)[None, None, :] * c.aperture_step_s
    aperture_sources = reference.sources(sample_times, swap_feet=swap_feet) if source_variant == "aperture_resolved" else None
    observations, rows = [], []
    for k, start in enumerate(starts):
        if drift_time_s is not None and start >= drift_time_s:
            acquisition.set_source_drift(np.diag([-1., 1., 1., 1.]))
        if k == missing_block:
            # The source/noise process still has a physical block. Its samples
            # are lost; consume the same draws without inventing a packet.
            noise.normal(0, c.reference_noise_rms_v / acquisition._noise_gain, (20, 1))
            noise.normal(0, c.noise_rms_v / acquisition._noise_gain, (20, 16))
            continue
        velocity = legacy_velocity[k] if source_variant == "legacy_block_hold" else velocities[k]
        kwargs = {"simulator_aperture_sources": aperture_sources[k]} if aperture_sources is not None else {}
        packet = acquisition.observe(float(start), positions[k] / .10, velocity / (2 * np.pi * .10),
                                     external_redundant_state=measured_external[k] / .10, **kwargs)
        observation = motor.Observation(float(start + .005), tuple(measured_external[k]), float(start - .020), True, packet)
        observations.append(observation)
        rows.append({"available_time_s": packet.available_time_s, "support_start_s": packet.support_start_s,
                     "support_end_s": packet.support_end_s, "representative_time_s": packet.representative_time_s,
                     "clock_uncertainty_s": packet.clock_uncertainty_s,
                     "external_support_s": observation.external_measurement_time_s,
                     "external_position_m": measured_external[k].tolist(),
                     "features_uv": list(packet.values_uv), "valid": packet.valid,
                     "reasons": list(packet.reasons), "usable_fraction": packet.usable_fraction,
                     "masked_samples": packet.masked_samples, "saturated_samples": packet.saturated_samples,
                     "feature_error_bound_uv": list(packet.feature_error_bound_uv)})
    active_rows = [row for row in rows if .5 <= row["available_time_s"] < 2.7]
    record = {"source_variant": source_variant, "source_mode": source_mode, "recording_seed": recording_seed,
              "config": asdict(c), "faults": {"missing_block": missing_block, "drift_time_s": drift_time_s,
                                               "ambiguous_field": ambiguous_field, "swapped_feet": swap_feet},
              "noise": noise.receipt(),
              "external_noise_sha256": hashlib.sha256(np.asarray(external_noise, dtype="<f8").tobytes()).hexdigest(),
              "aperture_support": {"samples_per_block_per_contact": 20, "contact_count": 16,
                                    "sample_hz_per_contact": 4000, "first_offset_s": 0.,
                                    "last_offset_s": float(sample_times[0, -1, -1] - starts[0]),
                                    "all_apertures_before_packet_availability": bool(np.all(sample_times < starts[:, None, None] + .005))},
              "summary": {"packet_count": len(rows), "raw_sample_count": acquisition.total_raw_samples,
                          "qualified_packet_count": sum(r["valid"] for r in rows),
                          "qualified_active_window_packets": sum(r["valid"] for r in active_rows),
                          "active_window_packet_count": len(active_rows),
                          "reason_counts": dict(Counter(reason for row in rows for reason in row["reasons"]))},
              "rows": rows}
    return record, observations


def fit_observer(observations):
    """Existing purged voltage/observed-label fit; latent states are unavailable."""
    return motor._fit_neural(observations)


def score_observer(model, record, reference, *, swap_feet=False):
    """Evaluator scores observed predictions at their original target support."""
    if model is None:
        return {"fit_available": False, "qualified": False, "valid_scored_packets": 0,
                "position_rmse_m": None, "predictions": [], "reason": "OBSERVED_FIT_UNAVAILABLE"}
    qualified = bool(model["rmse"] <= BUDGETS["observable_position_fit_rmse_m"])
    rows = [row for row in record["rows"] if row["valid"]]
    targets, _, _ = reference.evaluate(np.maximum(0., [row["external_support_s"] for row in rows]))
    if swap_feet:
        targets = targets[:, ::-1]
    errors, predictions, observed_residuals = [], [], []
    for row, target in zip(rows, targets):
        z = (np.asarray(row["features_uv"]) - model["mean"]) / model["scale"]
        prediction = (np.r_[1., z] @ model["weights"])[:2]
        errors.append(prediction - target)
        # Both inputs are observed and already available at this packet time.
        # This conflict flag never compares predictions with simulator truth.
        observed_residual = prediction - np.asarray(row["external_position_m"])
        conflict = bool(np.max(np.abs(observed_residual)) > BUDGETS["observable_position_component_error_m"])
        observed_residuals.append(observed_residual)
        predictions.append({"available_time_s": row["available_time_s"], "target_support_s": row["external_support_s"],
                            "position_prediction_m": prediction.tolist(),
                            "observed_component_residual_m": observed_residual.tolist(),
                            "observed_conflict_abstain": conflict})
    return {"fit_available": True, "qualified": qualified, "valid_scored_packets": len(errors),
            "qualification_scope": "observed position-fit RMSE only; not velocity, current-state, stimulation-policy or spinal observability qualification",
            "position_rmse_m": float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
            "observed_position_rmse_m": float(np.sqrt(np.mean(np.square(observed_residuals)))) if errors else None,
            "observed_conflict_abstention_count": sum(row["observed_conflict_abstain"] for row in predictions),
            "observed_conflict_abstention_active_window_count": sum(row["observed_conflict_abstain"]
                for row in predictions if .5 <= row["available_time_s"] < 2.7),
            "predictions": predictions,
            "reason": "CALIBRATED_OBSERVED_POSITION_BUDGET" if qualified else "OBSERVED_FIT_ERROR_EXCEEDS_25MM"}


def compare_sources(left, right, left_score=None, right_score=None, *, external_tolerance_m=0.):
    a, b = left["rows"], right["rows"]
    if len(a) != len(b):
        raise AssertionError("paired source approximation changed packet count")
    support_keys = ("available_time_s", "support_start_s", "support_end_s", "representative_time_s",
                    "clock_uncertainty_s", "external_support_s")
    if not np.isfinite(external_tolerance_m) or external_tolerance_m < 0:
        raise ValueError("Finite nonnegative external reference tolerance required")
    same_schedule = all(all(x[key] == y[key] for key in support_keys) for x, y in zip(a, b))
    external_difference = float(np.max(np.abs(np.asarray([x['external_position_m'] for x in a])
                                              -np.asarray([y['external_position_m'] for y in b]))))
    same_support = same_schedule and external_difference == 0.
    paired_support_pass = same_schedule and external_difference <= external_tolerance_m
    same_noise = left["noise"] == right["noise"] and left["external_noise_sha256"] == right["external_noise_sha256"]
    if not paired_support_pass or not same_noise:
        raise AssertionError("paired sources changed observations, support or actual noise")
    difference = np.asarray([x["features_uv"] for x in a]) - np.asarray([y["features_uv"] for y in b])
    common_valid = np.asarray([x["valid"] and y["valid"] for x, y in zip(a, b)])
    usable_difference = difference[common_valid]
    prediction_difference = None
    if left_score and right_score:
        lp, rp = left_score["predictions"], right_score["predictions"]
        if lp and rp and [r["target_support_s"] for r in lp] == [r["target_support_s"] for r in rp]:
            prediction_difference = float(np.max(np.abs(np.asarray([r["position_prediction_m"] for r in lp]) -
                                                        np.asarray([r["position_prediction_m"] for r in rp]))))
    return {"left": left["source_variant"], "right": right["source_variant"],
            "identical_actual_noise": same_noise, "identical_external_and_packet_support": same_support,
            "identical_observation_schedule": same_schedule,
            "maximum_external_reference_difference_m": external_difference,
            "external_reference_tolerance_m": external_tolerance_m,
            "paired_observation_support_pass": paired_support_pass,
            "maximum_feature_difference_uv": float(np.max(np.abs(difference))),
            "feature_difference_rmse_uv": float(np.sqrt(np.mean(difference ** 2))),
            "common_qualified_packet_count": int(np.count_nonzero(common_valid)),
            "maximum_qualified_feature_difference_uv": float(np.max(np.abs(usable_difference))) if usable_difference.size else None,
            "qualified_feature_difference_rmse_uv": float(np.sqrt(np.mean(usable_difference ** 2))) if usable_difference.size else None,
            "within_predeclared_feature_allocation": bool(np.max(np.abs(difference)) <= BUDGETS["source_hold_feature_difference_uv"]),
            "changed_quality_packets": sum(x["valid"] != y["valid"] or x["reasons"] != y["reasons"] for x, y in zip(a, b)),
            "maximum_position_prediction_difference_m": prediction_difference,
            "within_predeclared_prediction_allocation": None if prediction_difference is None else prediction_difference <= BUDGETS["source_hold_position_prediction_difference_m"]}


def ambiguous_witness(reference):
    first, _ = capture(reference, "aperture_resolved", recording_seed=991,
                       ambiguous_field=True, swap_feet=False)
    second, _ = capture(reference, "aperture_resolved", recording_seed=991,
                        ambiguous_field=True, swap_feet=True)
    feature_difference = np.max(np.abs(np.asarray([r["features_uv"] for r in first["rows"]]) -
                                       np.asarray([r["features_uv"] for r in second["rows"]])))
    witnesses = []
    for a, b in zip(first["rows"], second["rows"]):
        if not (a["valid"] and b["valid"]):
            continue
        unavoidable = float(np.max(np.abs(np.asarray(a["external_position_m"]) - b["external_position_m"])) / 2)
        if unavoidable > BUDGETS["observable_position_component_error_m"]:
            witnesses.append({"available_time_s": a["available_time_s"],
                              "external_support_s": a["external_support_s"],
                              "observed_labels_a_m": a["external_position_m"],
                              "observed_labels_b_m": b["external_position_m"],
                              "minimum_unavoidable_component_error_m": unavoidable})
    equivalent = bool(feature_difference <= BUDGETS["ambiguous_feature_equivalence_uv"])
    return {"definition": "private lead columns0=1 and2=3; two-foot state/velocity swap leaves contact voltages unchanged",
            "maximum_measured_feature_difference_uv": float(feature_difference),
            "paired_noise_exactly_equal": first["noise"] == second["noise"],
            "measured_features_indistinguishable": equivalent,
            "observed_contradiction_count": len(witnesses), "contradictions": witnesses,
            "observable_qualification": "AMBIGUOUS_FOR_25MM_TARGET_ABSTAIN" if equivalent and witnesses else "NO_CONTRADICTION_SHOWN",
            "scope": "constructed noninjective synthetic field; external labels expose contradiction. Not a biological impossibility proof or universal online ambiguity detector.",
            "captures": [first, second]}


def compare_reference_grids(coarse, fine):
    """Check the continuous reference at every actual contact aperture."""
    starts = np.arange(round(coarse.seconds * 200)) / 200
    times = starts[:, None, None] + np.arange(20)[None, :, None] / 4000 + np.arange(16)[None, None, :] * 3e-6
    left_x, left_v, _ = coarse.evaluate(times)
    right_x, right_v, _ = fine.evaluate(times)
    position_error = np.abs(left_x - right_x)
    velocity_error = np.abs(left_v - right_v)
    location = np.unravel_index(np.argmax(position_error), position_error.shape)
    return {"coarse_internal_step_s": coarse.maximum_step_s, "fine_internal_step_s": fine.maximum_step_s,
            "actual_contact_aperture_count": times.size,
            "identical_physical_event_boundaries": coarse.boundaries == fine.boundaries,
            "maximum_position_difference_m": float(position_error.max()),
            "maximum_physical_velocity_difference_m_per_s": float(velocity_error.max()),
            "position_budget_pass": bool(position_error.max() <= BUDGETS["reference_position_difference_m"]),
            "velocity_budget_pass": bool(velocity_error.max() <= BUDGETS["reference_velocity_difference_m_per_s"]),
            "largest_position_witness": {"block": int(location[0]), "sample": int(location[1]),
                "contact": int(location[2]), "component": int(location[3]),
                "time_s": float(times[location[:3]]), "coarse_position_m": float(left_x[location]),
                "fine_position_m": float(right_x[location])}}


def run_study(seed, *, extras=False):
    """Paired source study; calibration input is restricted to observed packets."""
    modes = ("informative", "redundant", "absent")
    refs = {scenario: MovingBodyReference(seed, scenario) for scenario in SCENARIOS}
    fine = {scenario: MovingBodyReference(seed, scenario, REFERENCE_GRIDS[1]) for scenario in SCENARIOS}
    study = {"subject_seed": seed, "references": {}, "training": [], "captures": [],
             "comparisons": [], "fine_grid_captures": [], "faults": [], "ambiguous_witness": None}
    models = {}
    for scenario in SCENARIOS:
        study["references"][scenario] = {"coarse": refs[scenario].receipt(), "fine": fine[scenario].receipt(),
                                         "refinement": compare_reference_grids(refs[scenario], fine[scenario])}
    for j, mode in enumerate(modes):
        training, observations = capture(refs["moving_clean"], "legacy_block_hold", source_mode=mode,
                                         recording_seed=10000 + seed + 100 * j)
        models[mode] = fit_observer(observations)
        training["fit"] = models[mode]
        study["training"].append(training)
        for scenario in SCENARIOS:
            records, scores = {}, {}
            for variant in SOURCE_VARIANTS:
                record, _ = capture(refs[scenario], variant, source_mode=mode, recording_seed=20000 + seed)
                record["scenario"] = scenario
                record["score"] = score_observer(models[mode], record, refs[scenario])
                records[variant], scores[variant] = record, record["score"]
                study["captures"].append(record)
            for left, right in ((SOURCE_VARIANTS[0], SOURCE_VARIANTS[1]),
                                (SOURCE_VARIANTS[1], SOURCE_VARIANTS[2]),
                                (SOURCE_VARIANTS[0], SOURCE_VARIANTS[2])):
                study["comparisons"].append({"scenario": scenario, "source_mode": mode,
                    **compare_sources(records[left], records[right], scores[left], scores[right])})
            if extras and mode == "informative":
                record, _ = capture(fine[scenario], "aperture_resolved", source_mode=mode, recording_seed=20000 + seed)
                record["scenario"] = scenario
                record["score"] = score_observer(models[mode], record, fine[scenario])
                study["fine_grid_captures"].append({"capture": record,
                    "comparison": compare_sources(records["aperture_resolved"], record,
                                                    scores["aperture_resolved"], record["score"],
                                                    external_tolerance_m=BUDGETS['reference_position_difference_m'])})
    if extras:
        nonaligned = MovingBodyReference(seed, "moving_sparse_train", onset_s=.03737)
        study["nonaligned_reference"] = nonaligned.receipt()
        cases = (("clock_100us", refs["moving_clean"], {"clock_s": 100e-6}),
                 ("clock_120us", refs["moving_clean"], {"clock_s": 120e-6}),
                 ("lost_5ms_block", refs["moving_clean"], {"missing_block": 200}),
                 ("changed_source_geometry", refs["moving_clean"], {"drift_time_s": 1.5}),
                 ("nonaligned_37_37ms_onset", nonaligned, {}))
        for name, ref, kwargs in cases:
            pair = []
            for variant in ("legacy_block_hold", "aperture_resolved"):
                record, _ = capture(ref, variant, recording_seed=20000 + seed, **kwargs)
                record["score"] = score_observer(models["informative"], record, ref)
                pair.append(record)
            study["faults"].append({"name": name, "captures": pair,
                "comparison": compare_sources(*pair, pair[0]["score"], pair[1]["score"])})
        study["ambiguous_witness"] = ambiguous_witness(refs["moving_clean"])
    return study
