"""Reproduce the independent Stage 3 electrical review sweeps.

The evaluator may inspect exact segment endpoints to check a chosen full-waveform
peak assumption. That check is never fed to the operational controller. Cases
outside the premise or with ADC saturation are explicitly excluded, not passed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scci_rh.stage3.electrical import (  # noqa: E402
    Load, integrate_interval, observe_delivery, simulate_pulse,
)


def ode_sweep():
    seed = 5
    rng = np.random.Generator(np.random.PCG64(seed))
    tolerance = {"polarization_V": 2e-7, "charge_C": 5e-11, "series_energy_J": 1e-8}
    cases = []
    for index in range(150):
        resistance = float(rng.uniform(500, 2000))
        capacitance = float(10 ** rng.uniform(-6.3, -4.9))
        leakage = float(10 ** rng.uniform(3, 6))
        command = float(rng.uniform(-.02, .02))
        initial = float(rng.uniform(-30, 30))
        usable = float(rng.choice([8., 16., 28., 40.]))
        duration = float(rng.uniform(50e-6, 1e-3))
        load = Load(resistance, capacitance, leakage)
        segments, polarization = integrate_interval(
            load, 0, duration, initial, command, usable, "review_interval")

        def derivative(_time, state):
            current = np.clip(command, (-usable - state[0]) / resistance,
                              (usable - state[0]) / resistance)
            return [(current - state[0] / leakage) / capacitance,
                    current, resistance * current * current]

        solution = solve_ivp(derivative, (0, duration), [initial, 0., 0.],
                             rtol=2e-10, atol=1e-13, max_step=duration / 100)
        if not solution.success or not np.all(np.isfinite(solution.y)):
            raise RuntimeError(f"Independent ODE solver failed for interval {index}")
        analytical = {"polarization_V": float(polarization),
                      "charge_C": float(sum(s.charge_C for s in segments)),
                      "series_energy_J": float(sum(s.bulk_energy_J(resistance) for s in segments))}
        numerical = dict(zip(analytical, map(float, solution.y[:, -1])))
        errors = {key: abs(analytical[key] - numerical[key]) for key in analytical}
        passed = all(errors[key] <= tolerance[key] for key in errors)
        cases.append({"case_id": f"ODE-{index:03d}",
                      "input": {"load": asdict(load), "command_A": command,
                                "initial_polarization_V": initial, "usable_compliance_V": usable,
                                "duration_s": duration},
                      "analytical": analytical, "independent_ode": numerical,
                      "absolute_error": errors, "segments": len(segments), "passed": passed})
    return {"seed": seed, "random_generator": "PCG64", "case_count": len(cases),
            "solver": {"method": "RK45", "rtol": 2e-10, "atol": 1e-13,
                       "max_step": "interval_duration/100"},
            "acceptance_absolute_error": tolerance,
            "maximum_absolute_error": {key: max(c["absolute_error"][key] for c in cases)
                                       for key in tolerance},
            "failed_cases": [c["case_id"] for c in cases if not c["passed"]],
            "passed": all(c["passed"] for c in cases), "cases": cases,
            "scope": "Numerical verification of the assumed equations, not validation of load values."}


def monitor_sweep():
    seed = 514
    rng = np.random.Generator(np.random.PCG64(seed))
    cases = []
    for index in range(500):
        load = Load(float(rng.uniform(500, 2000)),
                    float(10 ** rng.uniform(-6.3, -3.7)), float(10 ** rng.uniform(3, 6)))
        current = float(rng.uniform(.0001, .02))
        phase = float(rng.uniform(50e-6, 500e-6))
        boost = float(rng.choice([16., 24., 36., 48.]))
        initial = float(rng.uniform(-8, 8))
        gap = float(rng.uniform(0, 200e-6))
        recharge = float(rng.uniform(.5, 1.5))
        pulse = simulate_pulse(current, phase, boost, load, initial_V=initial,
                               gap_s=gap, recharge_gain=recharge)
        offset = float(rng.uniform(0, 5e-6))
        gain = float(rng.choice([-.02, .02]))
        bias = float(rng.choice([-5e-6, 5e-6]))
        observation = observe_delivery(pulse, offset, gain, bias)
        # Constant/exponential current is monotone in every exact segment, so
        # endpoints bound its entire segment. This is evaluator-only evidence.
        peak = max(abs(float(segment.at(time)[0])) for segment in pulse["segments"]
                   for time in (segment.start_s, segment.end_s))
        excluded = []
        if observation["monitor_saturated"]:
            excluded.append("ADC_SAMPLE_SATURATION")
        if peak > observation["complete_waveform_peak_assumption_A"]:
            excluded.append("EVALUATOR_FULL_WAVEFORM_PEAK_EXCEEDS_ASSUMPTION")
        eligible = not excluded
        phases = {}
        for name, measured, bound in (
            ("cathodic", -observation["measured_cathodic_charge_C"],
             observation["cathodic_uncertainty_C"]),
            ("anodic", observation["measured_anodic_charge_C"],
             observation["anodic_uncertainty_C"]),
        ):
            truth = pulse["phase_charge_C"][name]
            error = abs(measured - truth)
            phases[name] = {"true_signed_charge_C": float(truth),
                            "measured_signed_charge_C": float(measured),
                            "uncertainty_C": float(bound), "absolute_error_C": float(error),
                            "bound_utilization": float(error / bound),
                            "passed_under_assumptions": bool(error <= bound + 1e-15) if eligible else None}
        status = ("passed_under_assumptions" if all(p["passed_under_assumptions"] for p in phases.values())
                  else "failed_under_assumptions") if eligible else "excluded_outside_assumptions"
        cases.append({"case_id": f"ADC-{index:03d}",
                      "input": {"load": asdict(load), "current_A": current, "phase_s": phase,
                                "boost_V": boost, "initial_polarization_V": initial,
                                "gap_s": gap, "recharge_gain": recharge,
                                "adc_offset_s": offset, "adc_gain_error": gain, "adc_offset_A": bias},
                      "evaluator_full_waveform_peak_A": peak,
                      "chosen_full_waveform_peak_bound_A": observation["complete_waveform_peak_assumption_A"],
                      "monitor_saturated": observation["monitor_saturated"],
                      "status": status, "exclusion_reasons": excluded, "phases": phases})
    eligible = [c for c in cases if c["status"] != "excluded_outside_assumptions"]
    failures = [c["case_id"] for c in eligible if c["status"] == "failed_under_assumptions"]
    return {"seed": seed, "random_generator": "PCG64", "case_count": len(cases),
            "eligible_cases": len(eligible), "excluded_cases": len(cases) - len(eligible),
            "exclusion_ids": [c["case_id"] for c in cases if c["exclusion_reasons"]],
            "failed_eligible_cases": failures,
            "maximum_eligible_bound_utilization": max(p["bound_utilization"]
                for c in eligible for p in c["phases"].values()),
            "passed_under_assumptions": not failures, "cases": cases,
            "scope": "Excluded cases are not passes. Exact endpoint peak checks are evaluator-only; ADC samples cannot establish absence of unseen spikes. No hardware peak guard is validated."}


def run_sweep():
    ode, monitor = ode_sweep(), monitor_sweep()
    return {"schema": "scci_rh.stage3.electrical-review-sweep.v1", "review_date": "2026-10-08",
            "status": "passed_under_assumptions" if ode["passed"] and monitor["passed_under_assumptions"] else "failed",
            "model": "src/scci_rh/stage3/electrical.py", "ode_intervals": ode, "monitor_phases": monitor,
            "scope": "Independent reduced-model numerical evidence; no circuit servo, electrode chemistry, tissue field, biological efficacy or unrestricted current-monitor claim."}


def compare(actual, recorded, path="root"):
    """Portable numerical comparison; source/blob provenance is checked separately."""
    if isinstance(actual, dict):
        if not isinstance(recorded, dict) or actual.keys() != recorded.keys():
            raise AssertionError(f"Keys differ at {path}")
        for key in actual:
            compare(actual[key], recorded[key], f"{path}.{key}")
    elif isinstance(actual, list):
        if not isinstance(recorded, list) or len(actual) != len(recorded):
            raise AssertionError(f"List differs at {path}")
        for index, (a, b) in enumerate(zip(actual, recorded)):
            compare(a, b, f"{path}[{index}]")
    elif isinstance(actual, float):
        if not isinstance(recorded, (int, float)) or not np.isclose(actual, recorded, rtol=2e-6, atol=1e-11):
            raise AssertionError(f"Numerical reproduction differs at {path}")
    elif actual != recorded:
        raise AssertionError(f"Value differs at {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a fresh JSON receipt; default only prints the compact summary")
    parser.add_argument("--check", type=Path, help="Reproduce and compare an existing receipt without rewriting it")
    args = parser.parse_args()
    if args.output and args.check:
        parser.error("Choose either --output or --check")
    result = run_sweep()
    if args.check:
        compare(result, json.loads(args.check.read_text(encoding="utf-8")))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    ode, monitor = result["ode_intervals"], result["monitor_phases"]
    print(f"Electrical review: {result['status']}; ODE {ode['case_count']} intervals, "
          f"maximum polarization error {ode['maximum_absolute_error']['polarization_V']:.3g} V; "
          f"ADC {monitor['eligible_cases']}/{monitor['case_count']} eligible, "
          f"{monitor['excluded_cases']} excluded, maximum bound utilization "
          f"{monitor['maximum_eligible_bound_utilization']:.4f}")
    if args.check:
        print("Recorded sweep reproduced within declared numerical comparison tolerances.")
    return int(result["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
