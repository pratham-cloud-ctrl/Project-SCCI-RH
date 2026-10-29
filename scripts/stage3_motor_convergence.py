"""Bounded motor refinement with unchanged observations and independent references.

The budgets are frozen here before running the experiment. Failed budgets are
saved findings; they do not turn into larger tolerances or a biological claim.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import patch

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scci_rh.stage3 import motor  # noqa: E402

STEPS = (.005, .0025, .00125, .000625)
BUDGETS = {"maximum_position_difference_m": .00015,
           "trajectory_rmse_difference_m": .00010,
           "contact_spatial_rmse_difference_m": .00010,
           "final_coefficient_difference_m": .00010,
           "same_support_velocity_difference_m_per_s": .010,
           "contact_timing_rmse_difference_s": .001}
SCHEDULE = ((0., (0., 0.)), (.150, (1., 0.)), (.400, (-1., 0.)),
            (.650, (0., 1.)), (.850, (1., -1.)), (1.200, (.5, .5)),
            (1.700, (0., 0.)), (2.200, (-.8, .8)), (2.600, (0., 0.)))
CASES = (("nominal_35ms", .035, "nominal"),
         ("fast_5ms", .005, "nominal"),
         ("slow_150ms", .150, "nominal"),
         ("no_authority", .035, "no_authority"),
         ("adverse_route", .035, "cross_route_adverse"),
         ("nonaligned_37ms", .037, "nominal"))
ORIGINAL_RNG = np.random.default_rng
FROZEN_COMMIT = "526b854ad90dda8320325635fb26fef2a9e120bf"


def digest_array(value):
    return hashlib.sha256(np.asarray(value, dtype="<f8").tobytes()).hexdigest()


def source_hash(path):
    return hashlib.sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest()


def dose_at(t):
    selected = np.zeros(2)
    for when, dose in SCHEDULE:
        if when <= t+1e-12:
            selected = np.asarray(dose)
    return selected


def drive_at(t, c):
    if t < c.motor_onset_delay_s-1e-12:
        return np.zeros(2)
    raw = dose_at(t-c.motor_onset_delay_s)
    active = np.sign(raw)*np.maximum(0., np.abs(raw)-c.recruitment_threshold_fraction)
    # Declared negative-route convention, independently expressed here.
    if c.biological_variant != "nominal" and c.biological_variant != "no_authority":
        active = np.abs(active)
    return active


def replay(c, *, rest, learning):
    world = motor._World(3, c)
    times, positions, velocities, coefficients = [], [], [], []
    for index in range(600):
        start = index*c.dt_s
        now = (index+1)*c.dt_s
        world.advance(now, dose_at(start), "favorable", learning=learning, rest=rest)
        times.append(now); positions.append(world.x.copy()); velocities.append(world.v.copy())
        coefficients.append(world.theta.copy())
    return {"time_s": times, "position_m": np.asarray(positions),
            "source_velocity_m_per_s": np.asarray(velocities),
            "coefficients_m": np.asarray(coefficients), "substeps": world.integration_substeps,
            "delay_transition_times_s": world.delay_transitions}


def independent_reference(c, *, rest, learning, tolerance=1e-12):
    """Integrate declared coupled ODEs with exact input/direction event splits.

    The known task forcing is reimplemented independently of task_basis. Model
    parameter draws belong to the same private subject, not to the controller.
    """
    world = motor._World(3, c)
    initial = np.r_[np.zeros(4), world.theta.ravel()]
    recruitment = world.recruitment.copy()
    boundaries = sorted(set([0., 2., 3.] + [when+c.motor_onset_delay_s
                         for when, _ in SCHEDULE if 0 < when+c.motor_onset_delay_s < 3.]))
    times = np.arange(1, 601)*.005
    values = np.empty((600, 12)); evaluations = 0
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        constant_drive = drive_at((left+right)/2, c)
        direction = 1. if int(((left+right)/2)//2)%2 == 0 else -1.
        def rhs(t, state):
            a, x, theta = state[:2], state[2:4], state[4:].reshape(2, 4)
            w = 2*np.pi*t
            phi = direction*np.array([np.sin(w), np.cos(w), np.sin(3*w), np.cos(3*w)])
            desired = c.foot_amplitude_m*np.array([1., -1.])*phi[0]
            voluntary = np.zeros(2) if rest else theta@phi
            stimulation = recruitment@a
            theta_rate = (c.learning_step*np.outer(desired-voluntary
                          +c.stimulation_teaching_fraction*stimulation, phi)
                          if learning and not rest else np.zeros((2, 4)))
            return np.r_[(constant_drive-a)/c.motor_activation_tau_s,
                         (voluntary+stimulation-x)/c.movement_tau_s, theta_rate.ravel()]
        solution = solve_ivp(rhs, (left, right), initial, method="DOP853",
                             rtol=tolerance, atol=tolerance*.01, max_step=.0025,
                             dense_output=True)
        if not solution.success:
            raise AssertionError(solution.message)
        selected = (times > left+1e-12)&(times <= right+1e-12)
        values[selected] = solution.sol(times[selected]).T
        initial = solution.y[:, -1]
        evaluations += solution.nfev
    position = values[:, 2:4]
    return {"position_m": position, "source_velocity_m_per_s": np.diff(
                np.vstack((np.zeros((1, 2)), position)), axis=0)/.005,
            "coefficients_m": values[:, 4:].reshape(-1, 2, 4),
            "rhs_evaluations": evaluations,
            "maximum_internal_step_s": .0025, "rtol": tolerance,
            "atol": tolerance*.01, "exact_event_boundaries_s": boundaries}


def analytic_rest_reference(c):
    """Exact constant-input cascade across every declared physical event."""
    world = motor._World(3, c)
    a, x = np.zeros(2), np.zeros(2)
    output, cursor = [], 0.
    transitions = [when+c.motor_onset_delay_s for when, _ in SCHEDULE]
    for endpoint in np.arange(1, 601)*.005:
        stops = sorted([t for t in transitions if cursor+1e-12 < t < endpoint-1e-12]+[endpoint])
        for stop in stops:
            drive = drive_at((cursor+stop)/2, c)
            h = stop-cursor
            ea, ex = np.exp(-h/c.motor_activation_tau_s), np.exp(-h/c.movement_tau_s)
            cascade = c.motor_activation_tau_s/(c.motor_activation_tau_s-c.movement_tau_s)*(ea-ex)
            x = x*ex + (world.recruitment@drive)*(1-ex)+(world.recruitment@(a-drive))*cascade
            a = drive+(a-drive)*ea
            cursor = stop
        output.append(x.copy())
    return np.asarray(output)


class GeneratorAudit:
    def __init__(self, seed):
        self.seed = int(seed); self.rng = ORIGINAL_RNG(seed)
        self.initial_state = self.rng.bit_generator.state
        self.samples = []; self.calls = []

    def _draw(self, method, args, kwargs):
        value = getattr(self.rng, method)(*args, **kwargs)
        array = np.asarray(value, dtype="<f8")
        self.samples.append(array.ravel()); self.calls.append({"method": method, "shape": list(array.shape)})
        return value

    def normal(self, *args, **kwargs):
        return self._draw("normal", args, kwargs)

    def uniform(self, *args, **kwargs):
        return self._draw("uniform", args, kwargs)

    def receipt(self):
        values = np.concatenate(self.samples) if self.samples else np.zeros(0)
        schedule = json.dumps(self.calls, sort_keys=True, separators=(",", ":"))
        signatures = {}
        for call in self.calls:
            key = call["method"]+":"+str(call["shape"])
            signatures[key] = signatures.get(key, 0)+1
        return {"seed": self.seed, "draw_schedule_sha256": hashlib.sha256(schedule.encode()).hexdigest(),
                "call_count": len(self.calls), "call_signature_counts": signatures,
                "scalar_count": len(values), "samples_sha256": digest_array(values),
                "initial_generator_state": self.initial_state,
                "final_generator_state": self.rng.bit_generator.state,
                "sample_mean": float(np.mean(values)) if len(values) else None,
                "sample_std": float(np.std(values)) if len(values) else None}


def bounded_protocol(step, method="midpoint_exact_cascade"):
    c = motor.MotorConfig(body_integration_step_s=step, body_integration_method=method, motor_onset_delay_s=.005,
                          calibration_s=3., practice_blocks=1, practice_block_s=3., assessment_s=3.)
    audits = []
    def factory(seed):
        audit = GeneratorAudit(seed); audits.append(audit); return audit
    with patch.object(motor.np.random, "default_rng", factory):
        response, decoder, calibration = motor.calibrate(2, c)
        library = motor._expert_library(2, c)
        initial = motor._World(2, c).theta.copy()
        outcomes = {}
        for family in ("favorable", "zero"):
            outcomes[family] = {}
            for condition in ("observe_only", "neural_external__expert_neural"):
                theta, active, raw = motor._run_trial(1002, c, family, condition, response,
                    decoder, library, initial, 3., motor._assumed_delivery, learning=True,
                    save_trace=True, subject_seed=2)
                final = theta*(1-c.forgetting_fraction)
                _, off, retention = motor._run_trial(60002, c, family, condition, response,
                    decoder, library, final, 3., motor._assumed_delivery, learning=False,
                    save_trace=True, subject_seed=2)
                _, transfer, transfer_raw = motor._run_trial(61002, c, family, condition, response,
                    decoder, library, final, 3., motor._assumed_delivery, learning=False,
                    heldout=True, save_trace=True, subject_seed=2)
                def compact(records):
                    return {key: [row[key] for row in records["samples"]] for key in (
                        "time_s", "source_state_time_s", "simulator_position_m", "neural_valid",
                        "estimate_source", "policy_reason")} | {
                        "pulse_events": [{key: row[key] for key in ("time_s", "source_id", "route_sign")}
                                         for row in records["pulses"]]}
                outcomes[family][condition] = {"active": active, "retention_off": off,
                    "transfer_off": transfer, "final_coefficients_m": theta.tolist(),
                    "acquisition_threshold_reached_in_single_off_probe": bool(
                        off["contact_spatial_rmse_m"] <= c.retention_spatial_threshold_m
                        and off["contact_timing_rmse_s"] <= c.retention_timing_threshold_s),
                    "trace": {"active": compact(raw), "retention_off": compact(retention),
                              "transfer_off": compact(transfer_raw)}}
    receipts = [audit.receipt() for audit in audits]
    contrasts = {family: rows["observe_only"]["retention_off"]["contact_spatial_rmse_m"]
                          -rows["neural_external__expert_neural"]["retention_off"]["contact_spatial_rmse_m"]
                 for family, rows in outcomes.items()}
    return {"config": asdict(c), "delivery": "UNQUALIFIED_NOMINAL_ASSUMPTION",
            "calibrated_response": asdict(response),
            "calibration_scope": "3 s movement + 8 s routes + 4 s withheld mixed routes; 12 s independent expert; equal at every grid",
            "authority_singular_margin_m": calibration["authority_singular_margin_m"],
            "outcomes": outcomes, "retained_contact_gain_vs_observe_m": contrasts, "randomness": receipts,
            "randomness_hash": hashlib.sha256(json.dumps(
                [{k: row[k] for k in ("seed", "draw_schedule_sha256", "call_count", "scalar_count", "samples_sha256")}
                 for row in receipts], sort_keys=True).encode()).hexdigest()}


def numeric_delta(a, b):
    return float(np.max(np.abs(np.asarray(a)-np.asarray(b))))


def compare_closed(a, b):
    rows = []
    for family, conditions in a["outcomes"].items():
        for condition, left in conditions.items():
            right = b["outcomes"][family][condition]
            for phase in ("active", "retention_off", "transfer_off"):
                x, y = left["trace"][phase], right["trace"][phase]
                deltas = {"maximum_position_difference_m": numeric_delta(
                        x["simulator_position_m"], y["simulator_position_m"]),
                    "trajectory_rmse_difference_m": abs(left[phase]["trajectory_rmse_m"]-right[phase]["trajectory_rmse_m"]),
                    "contact_spatial_rmse_difference_m": abs(left[phase]["contact_spatial_rmse_m"]-right[phase]["contact_spatial_rmse_m"]),
                    "final_coefficient_difference_m": numeric_delta(
                        left["final_coefficients_m"], right["final_coefficients_m"]),
                    "same_support_velocity_difference_m_per_s": numeric_delta(
                        np.diff(x["simulator_position_m"], axis=0)/.005,
                        np.diff(y["simulator_position_m"], axis=0)/.005),
                    "contact_timing_rmse_difference_s": abs(
                        left[phase]["contact_timing_rmse_s"]-right[phase]["contact_timing_rmse_s"])}
                rows.append({"family": family, "condition": condition, "phase": phase,
                    "differences": deltas, "budget_pass": {key: value <= BUDGETS[key] for key, value in deltas.items()},
                    "same_physical_sample_schedule": x["time_s"] == y["time_s"] and x["source_state_time_s"] == y["source_state_time_s"],
                    "changed_policy_reasons": sum(u != v for u, v in zip(x["policy_reason"], y["policy_reason"])),
                    "changed_policy_reason_witnesses": [{"time_s": time, "coarse_reason": u, "fine_reason": v}
                        for time, u, v in zip(x["time_s"], x["policy_reason"], y["policy_reason"]) if u != v],
                    "changed_neural_validity": sum(u != v for u, v in zip(x["neural_valid"], y["neural_valid"])),
                    "changed_estimate_source": sum(u != v for u, v in zip(x["estimate_source"], y["estimate_source"])),
                    "pulse_events_equal": x["pulse_events"] == y["pulse_events"]})
    return {"coarse_step_s": a["config"]["body_integration_step_s"],
            "fine_step_s": b["config"]["body_integration_step_s"],
            "coarse_method": a["config"]["body_integration_method"],
            "fine_method": b["config"]["body_integration_method"],
            "actual_random_draws_identical": a["randomness_hash"] == b["randomness_hash"],
            "response_qualification_equal": a["calibrated_response"]["qualified"] == b["calibrated_response"]["qualified"],
            "onset_estimate_difference_s": abs(a["calibrated_response"]["onset_delay_s"]-b["calibrated_response"]["onset_delay_s"]),
            "retained_gain_sign_equal": all(np.sign(a["retained_contact_gain_vs_observe_m"][f])
                                            ==np.sign(b["retained_contact_gain_vs_observe_m"][f]) for f in a["outcomes"]),
            "zero_family_null_preserved": abs(a["retained_contact_gain_vs_observe_m"]["zero"]) < 1e-12
                                          and abs(b["retained_contact_gain_vs_observe_m"]["zero"]) < 1e-12,
            "acquisition_threshold_dispositions_equal": all(
                a["outcomes"][f][c]["acquisition_threshold_reached_in_single_off_probe"]
                ==b["outcomes"][f][c]["acquisition_threshold_reached_in_single_off_probe"]
                for f in a["outcomes"] for c in a["outcomes"][f]),
            "rows": rows}


def coarse_baseline_witness():
    if str(ROOT/'scripts') not in sys.path:
        sys.path.insert(0,str(ROOT/'scripts'))
    from project_branding import historical_bytes, rename_text
    try:
        source = historical_bytes(ROOT, FROZEN_COMMIT, "src/scci_rh/stage3/motor.py").decode('utf-8')
    except subprocess.CalledProcessError:
        return {"status": "SKIP_FROZEN_GIT_OBJECT_UNAVAILABLE", "commit": FROZEN_COMMIT}
    module = types.ModuleType("scci_rh.stage3._frozen_convergence_baseline")
    module.__package__ = "scci_rh.stage3"; sys.modules[module.__name__] = module
    # Resolve the actual immutable Git path, then migrate namespace references
    # in memory. Equations, constants and frozen numeric observations stay exact.
    exec(compile(rename_text(source), "frozen_526b854_motor.py", "exec"), module.__dict__)
    rows = []
    for family in motor.FAMILIES:
        old = module._World(3, module.MotorConfig()); new = motor._World(3, motor.MotorConfig())
        for k in range(600):
            now = (k+1)*.005
            old.advance(now, dose_at(k*.005), family, learning=True)
            new.advance(now, dose_at(k*.005), family, learning=True)
        flags = {"position_exact": np.array_equal(old.x, new.x),
                 "velocity_exact": np.array_equal(old.v, new.v),
                 "activation_exact": np.array_equal(old.activation, new.activation),
                 "coefficient_exact": np.array_equal(old.theta, new.theta)}
        if not all(flags.values()):
            raise AssertionError("Default coarse refactor changed frozen world")
        rows.append({"family": family, **flags})
    captures = []
    for delay in (.005, .035, .150):
        a = module._capture(1, module.MotorConfig(motor_onset_delay_s=delay), 1., rest=True, probe=lambda t: [1., -1.])
        b = motor._capture(1, motor.MotorConfig(motor_onset_delay_s=delay), 1., rest=True, probe=lambda t: [1., -1.])
        encode = lambda x: json.dumps(x, default=lambda y: y.__dict__, sort_keys=True)
        exact = encode(a) == encode(b)
        if not exact:
            raise AssertionError("Default coarse refactor changed capture")
        captures.append({"onset_delay_s": delay, "all_capture_outputs_exact": exact})
    return {"status": "EXACT_FROZEN_COARSE_REPRODUCTION", "commit": FROZEN_COMMIT,
            "normalized_lf_source_sha256": hashlib.sha256(source.replace("\r\n", "\n").encode()).hexdigest(),
            "world_checks": rows, "capture_checks": captures}


def run_probe(include_closed=True):
    cases = []
    for label, delay, variant in CASES:
        c = motor.MotorConfig(motor_onset_delay_s=delay, biological_variant=variant)
        for rest, learning in ((True, False), (False, True)):
            reference = independent_reference(c, rest=rest, learning=learning)
            tighter = independent_reference(c, rest=rest, learning=learning, tolerance=2e-13)
            ref_delta = numeric_delta(reference["position_m"], tighter["position_m"])
            if ref_delta > 1e-10:
                raise AssertionError("Independent reference tolerance refinement is unresolved")
            analytic_delta = numeric_delta(reference["position_m"], analytic_rest_reference(c)) if rest else None
            if rest and analytic_delta > 1e-10:
                raise AssertionError("Independent ODE and analytic cascade disagree")
            runs = []
            for method in ("legacy_endpoint", "midpoint_exact_cascade"):
                for step in STEPS:
                    replayed = replay(replace(c, body_integration_step_s=step,
                                             body_integration_method=method), rest=rest, learning=learning)
                    delta = {"maximum_position_difference_m": numeric_delta(replayed["position_m"], reference["position_m"]),
                        "final_coefficient_difference_m": numeric_delta(replayed["coefficients_m"][-1], reference["coefficients_m"][-1]),
                        "same_support_velocity_difference_m_per_s": numeric_delta(replayed["source_velocity_m_per_s"], reference["source_velocity_m_per_s"])}
                    replayed["final_coefficients_m"] = replayed.pop("coefficients_m")[-1]
                    runs.append({"body_step_s": step, "method": method, **replayed,
                                 "differences_from_independent_reference": delta,
                                 "budget_pass": {key: value <= BUDGETS[key] for key, value in delta.items()}})
            reference["final_coefficients_m"] = reference.pop("coefficients_m")[-1]
            cases.append({"case": label, "rest": rest, "learning": learning,
                "config": asdict(c), "reference": reference,
                "reference_tolerance_refinement_maximum_position_difference_m": ref_delta,
                "reference_vs_analytic_cascade_maximum_position_difference_m": analytic_delta,
                "runs": runs})
    closed = ([bounded_protocol(.005, "legacy_endpoint")]+[bounded_protocol(step) for step in STEPS]) if include_closed else []
    if closed and len({row["randomness_hash"] for row in closed}) != 1:
        raise AssertionError("Refinement changed actual random draws or initialization")
    comparisons = [compare_closed(closed[a], closed[b]) for a, b in ((0, 4), (1, 2), (2, 3), (3, 4), (1, 4), (2, 4))] if closed else []
    selected_fixed = [run for case in cases for run in case["runs"]
                      if run["method"] == "midpoint_exact_cascade" and run["body_step_s"] == .0025]
    fixed_pass = all(all(run["budget_pass"].values()) for run in selected_fixed)
    selected_pair = comparisons[-1] if comparisons else None
    closed_pass = selected_pair is not None and all((
        selected_pair["actual_random_draws_identical"], selected_pair["response_qualification_equal"],
        selected_pair["retained_gain_sign_equal"], selected_pair["zero_family_null_preserved"],
        selected_pair["acquisition_threshold_dispositions_equal"])) and all(
            all(row["budget_pass"].values()) and row["same_physical_sample_schedule"]
            and row["changed_policy_reasons"] == 0 and row["changed_neural_validity"] == 0
            and row["changed_estimate_source"] == 0 and row["pulse_events_equal"]
            for row in selected_pair["rows"])
    return {"schema": "scci_rh.stage3.motor-convergence.v1", "status": "bounded_numerical_diagnostic",
        "source_identity": {"motor.py": source_hash(ROOT/"src/scci_rh/stage3/motor.py"),
                            "acquisition.py": source_hash(ROOT/"src/scci_rh/stage3/acquisition.py"),
                            "external_history.py": source_hash(ROOT/"src/scci_rh/stage3/external_history.py"),
                            "stage3_motor_convergence.py": source_hash(Path(__file__))},
        "experiment": {"seed": 3, "closed_loop_seed": 2, "steps_s": list(STEPS),
            "fixed_input_duration_s": 3., "fixed_input_schedule": SCHEDULE,
            "budget_freeze": "Allocations fixed before first result generation, inherited from numerical-convergence-plan.md",
            "budgets": BUDGETS, "decision_hz": 200, "contact_sample_hz": 4000,
            "contact_samples_per_decision": 320, "source_hold_s": .005,
            "reference_scope": "Independent event-split DOP853 coupled ODE; exact analytic rest cascade; right-end body forcing quadrature retained in replay",
            "closed_loop_scope": "One seed; 3 s calibration movement; one3s practice block; favorable and zero; observe-only and neural-expert conditional delivery; 3sOFF retention and transfer; not full original matrix"},
        "coarse_baseline": coarse_baseline_witness(), "fixed_input_cases": cases,
        "closed_loop_runs": closed, "closed_loop_comparisons": comparisons,
        "production_recommendation": {
            "body_integration_method": "midpoint_exact_cascade", "body_integration_step_s": .0025,
            "status": "candidate_qualified_only_in_this_bounded_numerical_scope" if fixed_pass and closed_pass
                      else "FAILED_OR_SENSITIVE_OR_CLOSED_LOOP_NOT_RUN",
            "fixed_input_gate_pass": fixed_pass, "bounded_closed_loop_gate_pass": closed_pass,
            "basis": "Independent fixed-input budgets pass at all midpoint grids; 2.5ms vs0.625ms selected closed-loop metrics, frame events, reasons and qualifications stable.5ms midpoint retains one reason sensitivity.",
            "historical_default": "legacy_endpoint at5ms retained exactly; frozen results are not silently replaced",
            "application_boundary": "Re-run expanded scenarios/subjects and changed decoder/controller mechanisms before broader numerical qualification."},
        "remaining": ["Aperture-resolved source discretization is a separate study, not part of body refinement.",
                      "Other seeds, learning families and actual electrical-adapter calibration matrix remain outside this bounded closed-loop diagnostic.",
                      "No step is silently promoted to production; failures and discrete frame changes are retained.",
                      "No human information, efficacy or retained learning is established."]}


def plain(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    raise TypeError(type(value).__name__)


def summary(receipt, raw_name, raw_hash):
    keys = ("schema", "status", "source_identity", "experiment", "coarse_baseline",
            "closed_loop_comparisons", "production_recommendation", "remaining")
    selected = {key: receipt[key] for key in keys}
    selected["schema"] = "scci_rh.stage3.motor-convergence-summary.v1"
    selected["raw_witness"] = {"path": raw_name, "sha256": raw_hash,
                               "format": "deterministic gzip UTF8JSON; all fixed5ms trajectories and RNG receipts retained"}
    selected["fixed_input_cases"] = [{key: case[key] for key in (
        "case", "rest", "learning", "config", "reference_tolerance_refinement_maximum_position_difference_m",
        "reference_vs_analytic_cascade_maximum_position_difference_m")} | {
        "runs": [{key: run[key] for key in ("body_step_s", "method", "substeps",
                  "differences_from_independent_reference", "budget_pass")} for run in case["runs"]]}
        for case in receipt["fixed_input_cases"]]
    selected["closed_loop_runs"] = [{key: run[key] for key in (
        "config", "delivery", "calibrated_response", "calibration_scope", "authority_singular_margin_m",
        "retained_contact_gain_vs_observe_m", "randomness_hash")} | {
        "outcomes": {family: {condition: {key: value for key, value in values.items() if key != "trace"}
                               for condition, values in rows.items()} for family, rows in run["outcomes"].items()},
        "rng_generator_count": len(run["randomness"]),
        "rng_scalar_count": sum(row["scalar_count"] for row in run["randomness"])}
        for run in receipt["closed_loop_runs"]]
    return selected


def compare(actual, expected, path="root"):
    if isinstance(actual, dict):
        if not isinstance(expected, dict) or actual.keys() != expected.keys():
            raise AssertionError("Keys differ at "+path)
        for key in actual:
            if key in {"samples_sha256", "randomness_hash"}: continue
            compare(actual[key], expected[key], path+"."+key)
    elif isinstance(actual, (tuple, list, np.ndarray)):
        if len(actual) != len(expected): raise AssertionError("Lengths differ at "+path)
        # Retain booleans/strings and mixed witnesses while accelerating arrays.
        try:
            a, b = np.asarray(actual), np.asarray(expected)
            if a.dtype.kind in "fiu" and b.dtype.kind in "fiu":
                if not np.allclose(a, b, rtol=2e-8, atol=1e-11):
                    raise AssertionError("Numerics differ at "+path)
                return
        except (ValueError, TypeError): pass
        for i, (a, b) in enumerate(zip(actual, expected)): compare(a, b, f"{path}[{i}]")
    elif isinstance(actual, (float, np.floating)):
        if not np.isclose(actual, expected, rtol=2e-8, atol=1e-11): raise AssertionError("Numeric differs at "+path)
    elif actual != expected: raise AssertionError("Value differs at "+path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--fixed-input-only", action="store_true")
    args = parser.parse_args()
    if args.output and args.check: parser.error("Choose --output or --check")
    receipt = run_probe(not args.fixed_input_only)
    if args.check:
        if args.check.suffix == ".gz":
            with gzip.open(args.check, "rt", encoding="utf-8") as stream: expected = json.load(stream)
        else: expected = json.loads(args.check.read_text(encoding="utf-8"))
        compare(receipt, expected)
        print("Bounded motor numerical receipt reproduced; scope and failed budgets retained")
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.suffix == ".gz":
            encoded = (json.dumps(receipt, default=plain, separators=(",", ":"), allow_nan=False)+"\n").encode("utf-8")
            with args.output.open("wb") as stream:
                with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed: compressed.write(encoded)
            brief = summary(receipt, args.output.name, hashlib.sha256(args.output.read_bytes()).hexdigest())
            args.output.with_name("motor-convergence-summary.json").write_text(
                json.dumps(brief, default=plain, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        else: args.output.write_text(json.dumps(receipt, default=plain, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        print(f"Saved {len(receipt['fixed_input_cases'])} fixed-input cases and {len(receipt['closed_loop_runs'])} bounded closed-loop grids")
    else:
        print(json.dumps({"status": receipt["status"], "budgets": BUDGETS,
                         "fixed_input_cases": len(receipt["fixed_input_cases"]),
                         "closed_loop_grids": len(receipt["closed_loop_runs"])}))


if __name__ == "__main__": main()
