"""Reproduce integrated pressure-body refinement without adding observations.

The frozen baseline and explicitly timestamped nonaligned stress experiments
are distinct. Acceptance allocations are engineering numerical budgets, never
physiological tolerances. A receipt may report failures or discrete sensitivity.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import gzip
import hashlib
import io
import json
import math
from multiprocessing import get_context
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scci_rh.stage3 import pressure  # noqa: E402
from scci_rh.stage3.electrical import PressureDelivery  # noqa: E402

STEPS = (0.005, 0.0025, 0.00125)
SEEDS = (0, 1, 2, 3)
RTOL, ATOL = 2e-8, 1e-11
GATES = {
    "summary_pressure_difference_mmHg": 0.2,
    "maximum_policy_pressure_difference_mmHg": 0.2,
    "fallback_duration_difference_s": 0.25,
    "delivered_train_equivalent_difference_s": 0.5,
}
ORIGINAL_RNG = np.random.default_rng


class NoiseAudit:
    """Forward real draws unchanged, auditing their physical sensor schedule."""
    def __init__(self, seed, sigma):
        self.rng = ORIGINAL_RNG(seed)
        self.seed, self.sigma = seed, sigma
        self.initial_state = self.rng.bit_generator.state
        self.samples = []

    def normal(self, loc=0.0, scale=1.0, size=None):
        if loc != 0 or scale != self.sigma or size is not None:
            raise AssertionError("Pressure sensor draw signature changed")
        value = self.rng.normal(loc, scale, size)
        self.samples.append(float(value))
        return value

    def receipt(self):
        values = np.asarray(self.samples, dtype="<f8")
        return {
            "seed": self.seed, "generator": "PCG64", "normal_scale_pa": self.sigma,
            "scalar_call_count": len(values),
            "samples_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            "initial_generator_state": self.initial_state,
            "final_generator_state": self.rng.bit_generator.state,
            "sample_moments_pa": {"mean": float(np.mean(values)),
                                  "standard_deviation": float(np.std(values)),
                                  "minimum": float(np.min(values)), "maximum": float(np.max(values))},
        }


def source_hash(path):
    return hashlib.sha256((ROOT / path).read_text(encoding="utf-8").replace(
        "\r\n", "\n").encode("utf-8")).hexdigest()


def stresses():
    """Fixed synthetic stress choices, frozen before evaluating the matrix."""
    base = pressure.PressureScenario()
    return (
        replace(base, name="nonaligned_fast_near_limit", activation_tau_s=.503,
                response_tau_s=1.007, onset_delay_s=.1037, release_delay_s=.1091,
                sensor_delay_s=.1537, gain_pa=59.9 * pressure.PA_PER_MMHG),
        replace(base, name="nonaligned_slow_near_limit", activation_tau_s=9.999,
                response_tau_s=29.999, onset_delay_s=9.9987, release_delay_s=59.9973,
                sensor_delay_s=.1537),
        replace(base, name="nonaligned_context_reversal", onset_delay_s=.8037,
                release_delay_s=2.0091, sensor_delay_s=.1537,
                activation_tau_s=1.497, response_tau_s=6.003,
                changed_gain_pa=-15 * pressure.PA_PER_MMHG, change_time_s=260.0037),
    )


def run_case(seed, scenario, mode, step, fallback, exact_events):
    config = pressure.PressureConfig(integration_step_s=step, fallback=fallback)
    audit = NoiseAudit(seed, config.sensor_noise_pa)
    initializations = []

    def factory(requested_seed):
        if requested_seed != seed or initializations:
            raise AssertionError("Sensor RNG initialization changed")
        initializations.append(requested_seed)
        return audit

    # No persistent adapter/source state is shared between numerical grids.
    delivery = PressureDelivery()
    with patch.object(pressure.np.random, "default_rng", factory):
        result = pressure.run_study(seed, scenario, mode, delivery, config,
                                    exact_events=exact_events)
    witness = audit.receipt()
    if len(initializations) != 1 or witness["scalar_call_count"] != round(
            config.duration_s * config.waveform_sample_hz) + 1:
        raise AssertionError("Refinement changed sensor noise schedule")
    return result, witness


def changed_rows(a, b, keys):
    return [{"time_s": a["time_s"][i],
             "coarse": {key: a[key][i] for key in keys},
             "fine": {key: b[key][i] for key in keys}}
            for i in range(len(a["time_s"]))
            if any(a[key][i] != b[key][i] for key in keys)]


def compare_pair(coarse, fine):
    a, an = coarse
    b, bn = fine
    x, y = a["trace"], b["trace"]
    sa, sb = a["summary"], b["summary"]
    if x["time_s"] != y["time_s"]:
        raise AssertionError("Policy support schedule changed")
    ar, br = a["external_observation_records"], b["external_observation_records"]
    support_keys = ("support_start_s", "support_end_s", "arrival_s", "sequence",
                    "valid", "transported", "stale_replay")
    support_equal = len(ar) == len(br) and all(
        all(r[k] == s[k] for k in support_keys) for r, s in zip(ar, br))
    noise_equal = an["samples_sha256"] == bn["samples_sha256"]
    if not support_equal or not noise_equal:
        raise AssertionError("Refinement changed physical support or actual sensor noise")
    deltas = np.abs(np.asarray(x["true_sbp_pa"]) - y["true_sbp_pa"]) / pressure.PA_PER_MMHG
    largest = int(np.argmax(deltas))
    pressure_keys = [key for key in sa if key.endswith("_pa") and sa[key] is not None and sb[key] is not None]
    summary_delta = {key: abs(sa[key] - sb[key]) / pressure.PA_PER_MMHG for key in pressure_keys}
    fallback_delta = abs(sa["fallback_time_s"] - sb["fallback_time_s"])
    dose_delta = abs(sa["delivered_train_equivalent_s"] - sb["delivered_train_equivalent_s"])
    gates = {
        "summary_pressure": max(summary_delta.values()) <= GATES["summary_pressure_difference_mmHg"],
        "policy_pressure": float(deltas[largest]) <= GATES["maximum_policy_pressure_difference_mmHg"],
        "fallback_duration": fallback_delta <= GATES["fallback_duration_difference_s"],
        "delivered_dose": dose_delta <= GATES["delivered_train_equivalent_difference_s"],
    }
    frames = changed_rows(x, y, ("admitted_reference_frames",))
    reasons = changed_rows(x, y, ("controller_reason",))
    peaks = [{"sequence": r["sequence"], "coarse_peak_s": r["peak_time_s"],
              "fine_peak_s": s["peak_time_s"]} for r, s in zip(ar, br)
             if r["peak_time_s"] != s["peak_time_s"]]
    qualification_equal = a["calibration"]["qualified"] == b["calibration"]["qualified"]
    cal_sign = lambda r: None if r["calibration"]["gain_pa_per_fraction"] is None else int(
        np.sign(r["calibration"]["gain_pa_per_fraction"]))
    gain_sign_equal = cal_sign(a) == cal_sign(b)
    status = "within_frozen_budgets"
    if not all(gates.values()):
        status = "frozen_budget_exceeded"
    elif not qualification_equal or not gain_sign_equal or frames or reasons:
        status = "discrete_policy_or_qualification_sensitive"
    return {
        "coarse_step_s": a["metadata"]["config"]["integration_step_s"],
        "fine_step_s": b["metadata"]["config"]["integration_step_s"],
        "status": status, "gates": gates,
        "maximum_policy_pressure_difference_mmHg": float(deltas[largest]),
        "largest_difference_witness": {"time_s": x["time_s"][largest],
                                       "coarse_sbp_pa": x["true_sbp_pa"][largest],
                                       "fine_sbp_pa": y["true_sbp_pa"][largest]},
        "absolute_summary_differences_mmHg": summary_delta,
        "fallback_duration_difference_s": fallback_delta,
        "delivered_train_equivalent_difference_s": dose_delta,
        "changed_frame_decisions": frames, "changed_controller_reasons": reasons,
        "changed_peak_times": peaks,
        "equivalence_flags": {
            "policy_timestamps_exactly_equal": True,
            "observation_support_transport_schedule_exactly_equal": support_equal,
            "actual_sensor_noise_exactly_equal_within_host": noise_equal,
            "initial_rng_state_equal": an["initial_generator_state"] == bn["initial_generator_state"],
            "final_rng_state_equal": an["final_generator_state"] == bn["final_generator_state"],
            "noise_draw_count_equal": an["scalar_call_count"] == bn["scalar_call_count"],
            "calibration_qualification_equal": qualification_equal,
            "calibration_gain_sign_equal": gain_sign_equal,
            "calibration_reason_equal": a["calibration"]["reason"] == b["calibration"]["reason"],
            "identified_lag_equal": a["calibration"]["estimated_effect_lag_s"] == b["calibration"]["estimated_effect_lag_s"],
        },
    }


def compress_runs(values):
    return [{"start_policy_index": i, "value": value}
            for i, value in enumerate(values) if i == 0 or value != values[i - 1]]


def pack_run(result, noise):
    trace = result["trace"]
    record_keys = ("support_start_s", "support_end_s", "peak_time_s", "arrival_s",
                   "sequence", "valid", "transported", "stale_replay")
    return {
        "metadata": result["metadata"], "calibration": result["calibration"],
        "summary": result["summary"], "noise_witness": noise,
        "policy_witness": {
            "physical_support": {"first_s": trace["time_s"][0], "period_s": .25,
                                 "last_s": trace["time_s"][-1], "count": len(trace["time_s"])},
            "true_sbp_pa": trace["true_sbp_pa"],
            "admitted_reference_frames_runs": compress_runs(trace["admitted_reference_frames"]),
            "controller_reason_runs": compress_runs(trace["controller_reason"]),
            "observation_fresh_runs": compress_runs(trace["observation_fresh"]),
        },
        "external_support_witness": [{key: r[key] for key in record_keys}
                                     for r in result["external_observation_records"]],
        "body_event_witness": result.get("body_event_witness"),
    }


def run_group(task):
    section, seed, scenario, mode, fallback, exact_events = task
    cases = [run_case(seed, scenario, mode, step, fallback, exact_events) for step in STEPS]
    return {"section": section, "seed": seed, "scenario": scenario.name,
            "mode": mode, "fallback": fallback, "exact_timestamped_events": exact_events,
            "runs": [pack_run(*case) for case in cases],
            "comparisons": [compare_pair(cases[a], cases[b]) for a, b in ((0, 1), (1, 2), (0, 2))]}


def analytic_cascade(a, p, dose, gain, ta, tp, duration):
    """Independent closed-form constant-forcing two-state cascade."""
    ea, ep = math.exp(-duration / ta), math.exp(-duration / tp)
    cross = duration / tp * ep if ta == tp else ta / (ta - tp) * (ea - ep)
    return dose + (a - dose) * ea, p * ep + gain * dose * (1 - ep) + gain * (a - dose) * cross


def fixed_input_reference():
    """No controller or observation: nonaligned onset and gain-change witness."""
    scenario = replace(pressure.PressureScenario(), name="analytic_fixed_input",
                       onset_delay_s=.1037, activation_tau_s=.503, response_tau_s=1.007,
                       changed_gain_pa=-15 * pressure.PA_PER_MMHG, change_time_s=1.7037)
    samples = np.arange(0, 3.001, .25)
    analytic = []
    a = p = t = 0.0
    for target in samples:
        boundaries = sorted({float(target)} | {v for v in (.1037, 1.7037) if t < v < target})
        for end in boundaries:
            dose = .65 if t >= .1037 - 1e-12 else 0.0
            gain = scenario.gain_pa if t < 1.7037 - 1e-12 else scenario.changed_gain_pa
            a, p = analytic_cascade(a, p, dose, gain, scenario.activation_tau_s,
                                    scenario.response_tau_s, end - t)
            t = end
        analytic.append(p)
    runs = []
    for step in STEPS:
        body = pressure.TimestampedPressureBody(scenario)
        body.schedule_dose(0, .65)
        values = []
        for target in samples:
            while body.time_s < target - 1e-12:
                body.advance(min(float(target), body.time_s + step))
            values.append(body.added_pressure)
        difference = np.abs(np.asarray(values) - analytic) / pressure.PA_PER_MMHG
        runs.append({"integration_step_s": step, "pressure_pa": values,
                     "maximum_error_against_independent_analytic_mmHg": float(max(difference)),
                     "within_frozen_0p2mmHg_budget": bool(max(difference) <= .2),
                     "applied_delayed_dose_events": body.applied_events})
    return {"scope": "fixed .65 dose; nonaligned .1037s onset and1.7037s gain reversal; no learning/controller/sensor",
            "sample_times_s": samples.tolist(), "independent_analytic_pressure_pa": analytic,
            "scenario": asdict(scenario), "runs": runs}


def tasks_for_scope(scope="full"):
    families = pressure.default_scenarios()
    tasks = [("baseline_integrated", seed, scenario, mode, "stop", False)
             for scenario in families.values() for seed in SEEDS for mode in ("off", "feedback")]
    tasks += [("sensor_loss_fallback_integrated", seed, families["sensor_loss"], "feedback", fallback, False)
              for seed in SEEDS for fallback in ("finite_hold", "ramp")]
    tasks += [("nonaligned_stress_integrated", seed, scenario, mode, "stop", True)
              for scenario in stresses() for seed in SEEDS for mode in ("off", "feedback")]
    if scope == "smoke":
        return [tasks[0], tasks[1], tasks[-1]]
    return tasks


def run_matrix(jobs=1, scope="full"):
    tasks = tasks_for_scope(scope)
    groups = []
    if jobs == 1:
        iterator = map(run_group, tasks)
        for i, group in enumerate(iterator, 1):
            groups.append(group)
            if i % 8 == 0:
                print(f"Pressure refinement: {i}/{len(tasks)} matched groups", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context("spawn")) as pool:
            for i, group in enumerate(pool.map(run_group, tasks), 1):
                groups.append(group)
                if i % 8 == 0:
                    print(f"Pressure refinement: {i}/{len(tasks)} matched groups", flush=True)
    comparisons = [pair for group in groups for pair in group["comparisons"]]
    noise_by_seed = {}
    for group in groups:
        for run in group["runs"]:
            noise_by_seed.setdefault(group["seed"], set()).add(run["noise_witness"]["samples_sha256"])
    if any(len(hashes) != 1 for hashes in noise_by_seed.values()):
        raise AssertionError("Scenario or mode changed the matched physical sensor noise")
    return {
        "schema": "scci_rh.stage3.pressure-convergence.v1", "scope": scope,
        "claim_boundary": "Numerical accuracy of declared artificial pressure plant and averaged electrical adapter; no physiological efficacy, neural pressure decoder or continuous circuit integration is established.",
        "frozen_gates": GATES,
        "experiment": {"steps_s": STEPS, "seeds": SEEDS, "modes": ("off", "feedback"),
                       "oracle_excluded": True, "fresh_pressure_delivery_per_run": True,
                       "waveform_hz": 200, "extraction_hz": 1, "policy_hz": 4,
                       "duration_s": 420, "sensor_draws_per_run": 84001,
                       "baseline_event_mode": "frozen_rounded_aligned_grid",
                       "stress_event_mode": "exact_timestamped_onset_release_gain_events",
                       "stress_parameters_frozen_before_results": [asdict(x) for x in stresses()]},
        "source_identity": {path: source_hash(path) for path in (
            "src/scci_rh/stage3/pressure.py", "src/scci_rh/stage3/electrical.py",
            "scripts/stage3_pressure_convergence.py")},
        "reproduction": {"rtol": RTOL, "atol": ATOL,
                         "noise_hash_policy": "Exact within-host identity; cross-platform compare RNG states/counts and numeric moments, not noise byte hashes."},
        "summary": {"matched_group_count": len(groups), "run_count": len(groups) * 3,
                    "comparison_count": len(comparisons),
                    "budget_failure_count": sum(x["status"] == "frozen_budget_exceeded" for x in comparisons),
                    "discrete_sensitivity_count": sum(x["status"] == "discrete_policy_or_qualification_sensitive" for x in comparisons),
                    "maximum_policy_pressure_difference_mmHg": max(x["maximum_policy_pressure_difference_mmHg"] for x in comparisons),
                    "identical_actual_sensor_noise_per_seed_across_all_runs": True},
        "fixed_input_independent_reference": fixed_input_reference(), "groups": groups,
        "remaining": ["Averaged pressure dose is not a continuously simulated three-route source/routing/power timeline.",
                      "Frozen baseline uses its declared rounded onset queue; exact nonaligned stress is a separately selected path.",
                      "Threshold-sensitive frame/qualification changes are reported even when continuous metrics meet budgets."]}


def compare(actual, expected, path="root"):
    if isinstance(actual, dict):
        if not isinstance(expected, dict) or actual.keys() != expected.keys():
            raise AssertionError(f"Keys differ at {path}")
        for key in actual:
            if key != "samples_sha256":
                compare(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, (list, tuple)):
        if not isinstance(expected, (list, tuple)) or len(actual) != len(expected):
            raise AssertionError(f"Sequence differs at {path}")
        if actual and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in actual):
            if not np.allclose(actual, expected, rtol=RTOL, atol=ATOL):
                raise AssertionError(f"Numeric series differs at {path}")
        else:
            for i, (a, b) in enumerate(zip(actual, expected)):
                compare(a, b, f"{path}[{i}]")
    elif isinstance(actual, float):
        if not isinstance(expected, (int, float)) or not np.isclose(actual, expected, rtol=RTOL, atol=ATOL):
            raise AssertionError(f"Numeric value differs at {path}")
    elif actual != expected:
        raise AssertionError(f"Value differs at {path}")


def validate_receipt(receipt):
    hashes = {}
    for group in receipt["groups"]:
        for run in group["runs"]:
            witness = run["noise_witness"]
            if witness["scalar_call_count"] != 84001:
                raise AssertionError("Saved sensor draw count changed")
            hashes.setdefault(group["seed"], set()).add(witness["samples_sha256"])
    if any(len(values) != 1 for values in hashes.values()):
        raise AssertionError("Saved noise identity inconsistent")


def read_receipt(path):
    contents = path.read_bytes()
    if path.suffix == ".gz":
        contents = gzip.decompress(contents)
    return json.loads(contents.decode("utf-8"))


def write_receipt(path, receipt):
    contents = (json.dumps(receipt, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    if path.suffix == ".gz":
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
            stream.write(contents)
        contents = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def summary_receipt(receipt):
    """Readable findings with all comparisons; raw arrays stay in full receipt."""
    groups = []
    for group in receipt["groups"]:
        findings = []
        for pair in group["comparisons"]:
            findings.append({
                "steps_s": [pair["coarse_step_s"], pair["fine_step_s"]],
                "status": pair["status"], "gates": pair["gates"],
                "maximum_policy_pressure_difference_mmHg": pair["maximum_policy_pressure_difference_mmHg"],
                "absolute_summary_differences_mmHg": pair["absolute_summary_differences_mmHg"],
                "fallback_duration_difference_s": pair["fallback_duration_difference_s"],
                "delivered_train_equivalent_difference_s": pair["delivered_train_equivalent_difference_s"],
                "changed_frame_decision_count": len(pair["changed_frame_decisions"]),
                "changed_controller_reason_count": len(pair["changed_controller_reasons"]),
                "changed_peak_time_count": len(pair["changed_peak_times"]),
                "all_equivalence_flags_true": all(pair["equivalence_flags"].values()),
                "non_equivalent_flags": [key for key, value in pair["equivalence_flags"].items() if not value],
            })
        groups.append({key: group[key] for key in (
            "section", "seed", "scenario", "mode", "fallback", "exact_timestamped_events")} | {
                "calibration_by_grid": [{"integration_step_s": run["metadata"]["config"]["integration_step_s"],
                                         "qualified": run["calibration"]["qualified"],
                                         "reason": run["calibration"]["reason"],
                                         "gain_pa_per_fraction": run["calibration"]["gain_pa_per_fraction"],
                                         "gain_interval_pa": run["calibration"]["gain_interval_pa"],
                                         "estimated_effect_lag_s": run["calibration"]["estimated_effect_lag_s"]}
                                        for run in group["runs"]],
                "comparisons": findings,
            })
    return {"schema": "scci_rh.stage3.pressure-convergence-summary.v1",
            **{key: receipt[key] for key in (
                "scope", "claim_boundary", "frozen_gates", "experiment", "source_identity",
                "reproduction", "summary", "fixed_input_independent_reference", "remaining")},
            "raw_witness_policy": "Full compressed receipt retains every pressure sample, support/noise witness and changed-decision row. This summary reports every group's gate and comparison findings.",
            "groups": groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", type=Path)
    group.add_argument("--check", type=Path)
    parser.add_argument("--summary-output", type=Path,
                        help="Write a readable summary alongside an explicit --output receipt")
    parser.add_argument("--summary-check", type=Path,
                        help="Check readable summary consistency alongside --check")
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--scope", choices=("full", "smoke"), default="full")
    args = parser.parse_args()
    if args.summary_output and not args.output:
        parser.error("--summary-output requires --output")
    if args.summary_check and not args.check:
        parser.error("--summary-check requires --check")
    expected = read_receipt(args.check) if args.check else None
    if expected is not None:
        validate_receipt(expected)
        if expected["scope"] != args.scope:
            parser.error("--scope must match the saved receipt")
    result = run_matrix(args.jobs, args.scope)
    validate_receipt(result)
    if expected is not None:
        compare(result, expected)
        if args.summary_check:
            compare(summary_receipt(result), read_receipt(args.summary_check))
    if args.output:
        write_receipt(args.output, result)
        if args.summary_output:
            args.summary_output.parent.mkdir(parents=True, exist_ok=True)
            args.summary_output.write_text(json.dumps(summary_receipt(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    if args.check:
        print(f"Pressure numerical receipt reproduced at rtol={RTOL:g}, atol={ATOL:g}; scope and negative findings retained.")


if __name__ == "__main__":
    main()
