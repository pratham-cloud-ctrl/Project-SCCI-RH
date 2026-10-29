"""Reproduce a bounded six-run pressure refinement diagnostic.

The chosen reference delivery surrogate, seed 17 and three fixed grids are kept
explicit. This is not an integrated electrical check or an overall convergence
qualification. RNG instrumentation forwards every model draw without alteration.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scci_rh.stage3 import pressure  # noqa: E402

SEED = 17
STEPS = (0.005, 0.0025, 0.00125)
SCENARIOS = ("nominal", "no_response")
RTOL, ATOL = 2e-8, 1e-11
ORIGINAL_RNG = np.random.default_rng


class NoiseAudit:
    """Capture actual scalar sensor draws without supplying different values."""

    def __init__(self, seed, sigma):
        self.rng = ORIGINAL_RNG(seed)
        self.initial_state = self.rng.bit_generator.state
        self.sigma = sigma
        self.samples = []

    def normal(self, loc=0.0, scale=1.0, size=None):
        if loc != 0 or scale != self.sigma or size is not None:
            raise AssertionError("Pressure noise call schedule changed")
        value = self.rng.normal(loc, scale, size)
        self.samples.append(float(value))
        return value

    def receipt(self):
        values = np.asarray(self.samples, dtype="<f8")
        return {
            "instrumentation": "forwarded actual model scalar normal draws unchanged",
            "generator": "PCG64", "seed": SEED,
            "normal_location_pa": 0.0, "normal_scale_pa": self.sigma,
            "scalar_call_count": len(values),
            "samples_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            "hash_encoding": "chronological little-endian IEEE754 float64 sensor noise in Pa",
            "initial_generator_state": self.initial_state,
            "final_generator_state": self.rng.bit_generator.state,
            "sample_moments_pa": {
                "mean": float(np.mean(values)), "standard_deviation": float(np.std(values)),
                "minimum": float(np.min(values)), "maximum": float(np.max(values)),
            },
        }


def run_case(scenario, step):
    config = pressure.PressureConfig(integration_step_s=step)
    audit = NoiseAudit(SEED, config.sensor_noise_pa)
    calls = []

    def factory(seed):
        if seed != SEED or calls:
            raise AssertionError("Unexpected extra/different pressure RNG initialization")
        calls.append(seed)
        return audit

    # The frozen model still controls when and how its normal draws occur.
    # This patch exists only during this one serial evaluator call.
    with patch.object(pressure.np.random, "default_rng", factory):
        result = pressure.run_study(SEED, scenario, "feedback", config=config)
    if len(calls) != 1:
        raise AssertionError("Pressure model did not initialize exactly one sensor RNG")
    witness = audit.receipt()
    expected_samples = round(config.duration_s * config.waveform_sample_hz) + 1
    if witness["scalar_call_count"] != expected_samples:
        raise AssertionError("Refinement changed the sensor draw count")
    return result, witness


def different_values(a, b):
    if len(a) != len(b):
        raise AssertionError("Refinement changed the physical comparison schedule")
    return sum(x != y for x, y in zip(a, b))


def maximum_difference(a, b):
    if len(a) != len(b):
        raise AssertionError("Refinement changed array support")
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))


def compare_pair(coarse, fine):
    a, an = coarse
    b, bn = fine
    x, y = a["trace"], b["trace"]
    ar, br = a["external_observation_records"], b["external_observation_records"]
    ca, cb = a["calibration"], b["calibration"]
    sa, sb = a["summary"], b["summary"]
    metadata = lambda records: [{k: v for k, v in row.items() if k != "sbp_pa"}
                                for row in records]
    delta = {key: abs(sa[key] - sb[key]) / pressure.PA_PER_MMHG
             for key in ("disturbance_rmse_pa", "evaluation_rmse_pa",
                         "overshoot_above_target_pa", "disturbance_min_sbp_pa",
                         "recovery_peak_sbp_pa")}
    return {
        "coarse_step_s": a["metadata"]["config"]["integration_step_s"],
        "fine_step_s": b["metadata"]["config"]["integration_step_s"],
        "maximum_policy_sample_pressure_difference_mmHg": maximum_difference(
            x["true_sbp_pa"], y["true_sbp_pa"]) / pressure.PA_PER_MMHG,
        "absolute_summary_differences_mmHg": delta,
        "delivered_train_equivalent_difference_s": abs(
            sa["delivered_train_equivalent_s"] - sb["delivered_train_equivalent_s"]),
        "different_frame_decisions": different_values(
            x["admitted_reference_frames"], y["admitted_reference_frames"]),
        "different_controller_reasons": different_values(x["controller_reason"], y["controller_reason"]),
        "different_peak_times": different_values([r["peak_time_s"] for r in ar],
                                                  [r["peak_time_s"] for r in br]),
        "equivalence_flags": {
            "policy_timestamps_exactly_equal": x["time_s"] == y["time_s"],
            "frame_admissions_exactly_equal": x["admitted_reference_frames"] == y["admitted_reference_frames"],
            "controller_reasons_exactly_equal": x["controller_reason"] == y["controller_reason"],
            "external_record_count_equal": len(ar) == len(br),
            "external_record_metadata_exactly_equal": metadata(ar) == metadata(br),
            "external_records_exactly_equal": ar == br,
            "extracted_peak_times_exactly_equal": [r["peak_time_s"] for r in ar] == [r["peak_time_s"] for r in br],
            "actual_noise_samples_exactly_equal_within_host": an["samples_sha256"] == bn["samples_sha256"],
            "noise_draw_count_equal": an["scalar_call_count"] == bn["scalar_call_count"],
            "initial_rng_state_equal": an["initial_generator_state"] == bn["initial_generator_state"],
            "final_rng_state_equal": an["final_generator_state"] == bn["final_generator_state"],
            "calibration_qualification_equal": ca["qualified"] == cb["qualified"],
            "identified_lag_equal": ca["estimated_effect_lag_s"] == cb["estimated_effect_lag_s"],
        },
    }


def normalized_source_hash(path):
    contents = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(contents.encode("utf-8")).hexdigest()


def run_probe():
    runs, comparisons, all_hashes = [], {}, []
    for scenario in SCENARIOS:
        cases = [run_case(scenario, step) for step in STEPS]
        for result, noise in cases:
            all_hashes.append(noise["samples_sha256"])
            runs.append({
                "scenario": scenario, "integration_step_s": result["metadata"]["config"]["integration_step_s"],
                "config": result["metadata"]["config"],
                "scenario_parameters": result["metadata"]["scenario"],
                "delivery_boundary": result["metadata"]["delivery_boundary"],
                "calibration": result["calibration"], "summary": result["summary"],
                "policy_samples": len(result["trace"]["time_s"]),
                "external_records": len(result["external_observation_records"]),
                "noise_witness": noise,
            })
        comparisons[scenario] = [compare_pair(cases[a], cases[b]) for a, b in ((0, 1), (1, 2), (0, 2))]
    if len(set(all_hashes)) != 1:
        raise AssertionError("Paired six-run diagnostic changed the actual noise realization")
    return {
        "schema": "scci_rh.stage3.pressure-convergence-probe.v1",
        "status": "bounded_diagnostic_only",
        "scope": "Seed17, nominal/no-response feedback, chosen reference delivery surrogate; not integrated electrical verification or general convergence qualification.",
        "source_identity": {
            "path": "src/scci_rh/stage3/pressure.py", "normalized_lf_sha256": normalized_source_hash(ROOT / "src/scci_rh/stage3/pressure.py"),
            "source_model": "SBP = chosen baseline - prescribed disturbance + hidden two-state added pressure; synthetic1Hz cardiac waveform; independent200Hz sensor noise",
            "scenario_identity": "Same declared scenario parameters at all three grids; no-response changes gain to0 only, retaining the nominal baseline/disturbance/sensor parameters.",
        },
        "experiment": {
            "seed": SEED, "mode": "feedback", "delivery": "chosen_reference_surrogate",
            "steps_s": list(STEPS), "scenarios": list(SCENARIOS), "run_count": len(runs),
            "waveform_hz": 200, "extraction_hz": 1, "policy_hz": 4,
            "duration_s": 420, "same_actual_noise_hash_across_all_six_runs": True,
            "noise_audit_permission": "Evaluator captures existing generator draws; no noise samples, body states or future values supplied to the operational controller.",
        },
        "reproduction": {
            "rtol": RTOL, "atol": ATOL,
            "platform_local_hash_policy": "Each receipt must have identical actual-noise hashes across all six runs. Cross-platform reproduction compares RNG states, counts and numeric moments; it does not require identical noise floating-point bytes across operating systems.",
        },
        "runs": runs, "comparisons": comparisons,
        "remaining": ["Full integrated electrical-adapter pressure matrix, other seeds, joint parameters and all fallback variants remain unqualified.",
                      "Motor body-clock separation and independent body/source convergence experiments remain open."],
    }


def compare(actual, expected, path="root"):
    if isinstance(actual, dict):
        if not isinstance(expected, dict) or actual.keys() != expected.keys():
            raise AssertionError(f"Keys differ at {path}")
        for key in actual:
            if key == "samples_sha256":
                continue  # Platform-local bytes; within-receipt equality checked separately.
            compare(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, (list, tuple)):
        if not isinstance(expected, (list, tuple)) or len(actual) != len(expected):
            raise AssertionError(f"Sequence differs at {path}")
        for i, (a, b) in enumerate(zip(actual, expected)):
            compare(a, b, f"{path}[{i}]")
    elif isinstance(actual, float):
        if not isinstance(expected, (int, float)) or not np.isclose(actual, expected, rtol=RTOL, atol=ATOL):
            raise AssertionError(f"Numeric reproduction differs at {path}")
    elif actual != expected:
        raise AssertionError(f"Value differs at {path}")


def validate_hash_identity(receipt):
    hashes = [row["noise_witness"]["samples_sha256"] for row in receipt["runs"]]
    if len(hashes) != 6 or len(set(hashes)) != 1 or any(len(h) != 64 for h in hashes):
        raise AssertionError("Recorded actual-noise identity witness is inconsistent")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", type=Path, help="Write an explicit JSON receipt; otherwise print only a compact diagnostic summary")
    group.add_argument("--check", type=Path, help="Required receipt path when checking; reproduce without rewriting it")
    args = parser.parse_args()
    expected = json.loads(args.check.read_text(encoding="utf-8")) if args.check else None
    if expected is not None:
        validate_hash_identity(expected)
    result = run_probe()
    validate_hash_identity(result)
    if expected is not None:
        compare(result, expected)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    pair = result["comparisons"]["nominal"][-1]
    print("Pressure refinement probe: bounded diagnostic only; six runs with identical actual sensor-noise realizations.")
    print(f"Seed17 5ms versus1.25ms maximum policy-sample difference: {pair['maximum_policy_sample_pressure_difference_mmHg']:.9g} mmHg.")
    if args.check:
        print(f"Receipt reproduced at rtol={RTOL:g}, atol={ATOL:g}; no general convergence pass inferred.")


if __name__ == "__main__":
    main()
