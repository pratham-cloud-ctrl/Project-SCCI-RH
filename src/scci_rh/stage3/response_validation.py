"""Finite observed route/density applicability for the fixed motor profile.

Identification functions accept positions and independent monitor records only.
The capture/evaluator boundary alone creates hidden response-context changes.
This is a digital hypothesis study, never a population coverage guarantee.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from collections import Counter
from unittest.mock import patch
import math

import numpy as np

from . import motor
from .electrical import MotorDelivery

QUALIFIED_MONITOR_NAMES = ("VALID", "ASSUMED_NOMINAL")
PATTERNS = {
    "left_positive": (1, 0), "left_negative": (-1, 0),
    "right_positive": (0, 1), "right_negative": (0, -1),
    "mixed_same": (1, 1), "mixed_opposed": (1, -1),
}
DENSITIES = (.25, .5, 1.)
ORIGINAL_WORLD = motor._World


@dataclass(frozen=True)
class DomainSpec:
    capture_s: float = 2.5
    active_start_s: float = .25
    active_stop_s: float = 2.0
    plateau_start_s: float = 1.5
    plateau_stop_s: float = 1.9
    dose_history_s: float = .25
    nominal_phase_charge_c: float = 600e-9
    calibration_position_allowance_m: float = .0095
    correction_budget_m: float = .025
    heldout_joint_coverage_floor: float = .95

    def __post_init__(self):
        if not all(math.isfinite(value) and value > 0 for value in asdict(self).values()):
            raise ValueError("finite positive frozen-domain allocations required")
        if not (self.active_start_s < self.plateau_start_s < self.plateau_stop_s <
                self.active_stop_s < self.capture_s):
            raise ValueError("plateau must lie inside the declared active capture")
        if self.correction_budget_m != .025 or self.heldout_joint_coverage_floor != .95:
            raise ValueError("this experiment freezes25mm correction and95percent empirical gates")


class WholeFrameDensity:
    """Preregistered sigma-delta selection of complete40Hz profile frames."""
    def __init__(self, pattern, density, spec=DomainSpec()):
        if pattern not in PATTERNS or density not in DENSITIES:
            raise ValueError("only explicitly tested pattern/density combinations allowed")
        self.pattern = pattern
        self.density = density
        self.spec = spec
        self.accumulator = 0.
        self.frame_count = self.admitted_count = 0
        self.last_time_s = -math.inf
        self.events = []

    def __call__(self, time_s):
        if not math.isfinite(time_s) or time_s <= self.last_time_s:
            raise ValueError("density selector needs chronological unique frame times")
        if abs(time_s * 40 - round(time_s * 40)) > 1e-9:
            raise ValueError("dose decisions belong to whole40Hz frames")
        self.last_time_s = time_s
        active = self.spec.active_start_s <= time_s < self.spec.active_stop_s
        admitted = False
        if active:
            self.frame_count += 1
            self.accumulator += self.density
            if self.accumulator >= 1 - 1e-12:
                self.accumulator -= 1
                self.admitted_count += 1
                admitted = True
        signs = PATTERNS[self.pattern] if admitted else (0, 0)
        self.events.append({"time_s": float(time_s), "active": active,
                            "admitted": admitted, "route_signs": list(signs)})
        return np.asarray(signs, dtype=float)


def capture_response(subject_seed, recording_id, config, pattern, density, branch,
                     *, changed_context=False, spec=DomainSpec()):
    """Private evaluator: truth is retained separately from observable records."""
    selector = WholeFrameDensity(pattern, density, spec)
    delivery = MotorDelivery() if branch == "actual_nominal_delivery" else None
    if branch not in {"actual_nominal_delivery", "conditional_fast_assumed_delivery"}:
        raise ValueError("unknown delivery branch")
    if changed_context:
        def world_factory(seed, c):
            return ORIGINAL_WORLD(seed, c, heldout=True)
        with patch.object(motor, "_World", world_factory):
            observations, data, witnesses, _ = motor._capture(
                recording_id, config, spec.capture_s, rest=True, probe=selector,
                delivery=delivery, subject_seed=subject_seed)
    else:
        observations, data, witnesses, _ = motor._capture(
            recording_id, config, spec.capture_s, rest=True, probe=selector,
            delivery=delivery, subject_seed=subject_seed)
    observable = {
        "schema": "scci_rh.stage3.observable-response-capture.v1",
        "recording_id": recording_id, "pattern": pattern, "density": density,
        "command_frames": selector.events,
        "positions": [{"available_time_s": o.available_time_s,
                       "support_time_s": o.external_measurement_time_s,
                       "position_m": list(o.external_position_m), "valid": o.external_valid}
                      for o in observations],
        "monitors": [{key: w[key] for key in (
            "time_s", "source_id", "route_sign", "delivered_phase_charge_C",
            "charge_uncertainty_C", "quality", "inhibit_next")} for w in witnesses],
    }
    return {
        "observable": observable,
        "evaluator_only": {"subject_seed": subject_seed, "changed_response_context": changed_context,
                           "simulator_position_m": [row["simulator_position_m"] for row in data],
                           "pulse_witnesses": witnesses},
        "delivery_status": "ACTUAL_REDUCED_ELECTRICAL_MODEL" if delivery else "UNQUALIFIED_NOMINAL_ASSUMPTION",
        "commanded_active_frames": selector.frame_count,
        "admitted_complete_frames": selector.admitted_count,
    }


def _validate_observable(capture):
    if set(capture) != {"schema", "recording_id", "pattern", "density", "command_frames", "positions", "monitors"}:
        raise ValueError("response identification accepts the sanitized observable schema only")
    previous = -math.inf
    for row in capture["positions"]:
        if set(row) != {"available_time_s", "support_time_s", "position_m", "valid"}:
            raise ValueError("position record must contain measurements only")
        support, available = row["support_time_s"], row["available_time_s"]
        if not (math.isfinite(support) and math.isfinite(available) and support > previous
                and support <= available and np.shape(row["position_m"]) == (2,)
                and np.all(np.isfinite(row["position_m"]))):
            raise ValueError("finite chronological physical position support required")
        previous = support
    previous = -math.inf
    for frame in capture["command_frames"]:
        if set(frame) != {"time_s", "active", "admitted", "route_signs"}:
            raise ValueError("command frame schema changed")
        time_s = frame["time_s"]
        if not (math.isfinite(time_s) and time_s > previous
                and abs(time_s * 40 - round(time_s * 40)) < 1e-9):
            raise ValueError("chronological whole40Hz command frames required")
        expected = PATTERNS[capture["pattern"]] if frame["admitted"] else (0, 0)
        if tuple(frame["route_signs"]) != expected:
            raise ValueError("admitted route identity does not match declared pattern")
        previous = time_s
    for monitor in capture["monitors"]:
        if set(monitor) != {"time_s", "source_id", "route_sign", "delivered_phase_charge_C",
                            "charge_uncertainty_C", "quality", "inhibit_next"}:
            raise ValueError("monitor must not expose actual dose or electrical/body truth")
        if not (math.isfinite(monitor["time_s"]) and monitor["source_id"] in (0, 1)
                and monitor["route_sign"] in (-1, 1)
                and math.isfinite(monitor["delivered_phase_charge_C"])
                and monitor["delivered_phase_charge_C"] >= 0
                and math.isfinite(monitor["charge_uncertainty_C"])
                and monitor["charge_uncertainty_C"] >= 0):
            raise ValueError("invalid monitored dose")


def monitored_input(capture, support_s, spec=DomainSpec()):
    """Past-window held-frame dose; no pulse after physical support is consumed."""
    _validate_observable(capture)
    return _monitored_input(capture, support_s, spec)


def _monitored_input(capture, support_s, spec):
    """Internal replay after one complete observable-schema check."""
    start = support_s - spec.dose_history_s
    dose = np.zeros(4)
    uncertainty = np.zeros(4)
    valid = True
    quality = Counter()
    monitor_by_frame = {}
    for row in capture["monitors"]:
        if row["time_s"] <= support_s + 1e-12:
            monitor_by_frame.setdefault(round(row["time_s"] * 40), []).append(row)
    for frame in capture["command_frames"]:
        time_s = frame["time_s"]
        overlap = max(0., min(time_s + .025, support_s) - max(time_s, start))
        if overlap == 0:
            continue
        rows = monitor_by_frame.get(round(time_s * 40), [])
        for source, sign in enumerate(frame["route_signs"]):
            if not sign:
                continue
            matches = [row for row in rows if row["source_id"] == source and row["route_sign"] == sign]
            if len(matches) != 1:
                valid = False
                quality["MISSING_OR_AMBIGUOUS_MONITOR"] += 1
                continue
            row = matches[0]
            quality[row["quality"]] += 1
            if row["quality"] not in QUALIFIED_MONITOR_NAMES:
                valid = False
                continue
            index = 2 * source + (0 if sign > 0 else 1)
            weight = overlap / spec.dose_history_s
            dose[index] += weight * row["delivered_phase_charge_C"] / spec.nominal_phase_charge_c
            # Worst-aligned systematic monitor error is not reduced as sqrt(N).
            uncertainty[index] += weight * row["charge_uncertainty_C"] / spec.nominal_phase_charge_c
    return dose, uncertainty, valid, dict(quality)


def _baseline(capture):
    rows = [r["position_m"] for r in capture["positions"]
            if .05 <= r["support_time_s"] < .20 and r["valid"]]
    if not rows:
        raise ValueError("precommand observed baseline absent")
    return np.mean(rows, axis=0)


def fit_route_map(full_train_captures, spec=DomainSpec()):
    """Fit effective four-route gain without hidden recruitment normalization."""
    if len(full_train_captures) != 4:
        raise ValueError("four individual full-train route captures required")
    gains, uncertainties, routes = [], [], []
    for index, capture in enumerate(full_train_captures):
        _validate_observable(capture)
        pattern = tuple(PATTERNS)[index]
        if capture["pattern"] != pattern or capture["density"] != 1.:
            raise ValueError("full individual route ordering/profile changed")
        baseline = _baseline(capture)
        positions, doses, dose_uncertainties, qualifications = [], [], [], []
        for row in capture["positions"]:
            if spec.plateau_start_s <= row["support_time_s"] < spec.plateau_stop_s and row["valid"]:
                dose, uncertainty, qualified, _ = _monitored_input(capture, row["support_time_s"], spec)
                positions.append(row["position_m"])
                doses.append(dose[index])
                dose_uncertainties.append(uncertainty[index])
                qualifications.append(qualified)
        if not positions:
            raise ValueError("observed route plateau absent")
        response = np.mean(positions, axis=0) - baseline
        measured = float(np.mean(doses))
        dose_uncertainty = float(np.mean(dose_uncertainties))
        denominator = measured - dose_uncertainty
        sign = 1 if index % 2 == 0 else -1
        gain = response / max(measured, .01)
        uncertainty = (spec.calibration_position_allowance_m / max(denominator, .01)
                       + np.abs(response) * dose_uncertainty / (max(measured, .01) * max(denominator, .01)))
        sign_ok = sign * response[index // 2] > spec.calibration_position_allowance_m
        qualified = bool(all(qualifications) and denominator > 0 and sign_ok)
        reason = ("MONITOR_UNQUALIFIED" if not all(qualifications) else
                  "DOSE_INTERVAL_INCLUDES_ZERO" if denominator <= 0 else
                  "NULL_OR_WRONG_ROUTE_SIGN" if not sign_ok else "OBSERVED_ROUTE_SIGN_AND_DOSE")
        gains.append(gain)
        uncertainties.append(uncertainty)
        routes.append({"pattern": pattern, "recording_id": capture["recording_id"],
                       "response_m": response.tolist(), "measured_reference_dose": measured,
                       "dose_uncertainty": dose_uncertainty, "qualified": qualified, "reason": reason})
    gain = np.asarray(gains).T
    uncertainty = np.asarray(uncertainties).T
    effective = np.column_stack(((gain[:, 0] - gain[:, 1]) / 2, (gain[:, 2] - gain[:, 3]) / 2))
    effective_unc = np.column_stack(((uncertainty[:, 0] + uncertainty[:, 1]) / 2,
                                     (uncertainty[:, 2] + uncertainty[:, 3]) / 2))
    singular_margin = float(np.linalg.svd(effective, compute_uv=False)[-1] - np.linalg.norm(effective_unc, 2))
    return {"schema": "scci_rh.stage3.observed-four-route-map.v1",
            "gain_m_per_reference_dose": gain.tolist(), "gain_uncertainty_m": uncertainty.tolist(),
            "routes": routes, "authority_singular_margin_m": singular_margin,
            "qualified": bool(all(r["qualified"] for r in routes) and singular_margin > 0),
            "scope": "four effective gains at fixed3mA/200us/24V profile; no threshold, latent gain or body coefficient supplied"}


def observed_residuals(capture, response_map, spec=DomainSpec()):
    _validate_observable(capture)
    gain = np.asarray(response_map["gain_m_per_reference_dose"])
    gain_uncertainty = np.asarray(response_map["gain_uncertainty_m"])
    baseline = _baseline(capture)
    rows = []
    for observation in capture["positions"]:
        support = observation["support_time_s"]
        if not (spec.plateau_start_s <= support < spec.plateau_stop_s and observation["valid"]):
            continue
        dose, dose_uncertainty, qualified, quality = _monitored_input(capture, support, spec)
        prediction = gain @ dose
        propagated = propagate_correction_uncertainty(gain, gain_uncertainty, dose, dose_uncertainty)
        residual = np.asarray(observation["position_m"]) - baseline - prediction
        rows.append({"support_time_s": support, "available_time_s": observation["available_time_s"],
                     "measured_dose": dose.tolist(), "dose_uncertainty": dose_uncertainty.tolist(),
                     "prediction_m": prediction.tolist(), "residual_m": residual.tolist(),
                     "propagated_position_uncertainty_m": propagated.tolist(),
                     "monitor_qualified": qualified, "monitor_quality": quality})
    if not rows:
        raise ValueError("held-out residual support absent")
    return rows


def propagate_correction_uncertainty(gain, gain_uncertainty, dose, dose_uncertainty):
    """Bound both factors of (G+deltaG)(u+deltau), including their product."""
    return (gain_uncertainty @ np.abs(dose) + np.abs(gain) @ dose_uncertainty
            + gain_uncertainty @ dose_uncertainty)


def empirical_envelope(observable, response_map, spec=DomainSpec()):
    rows = observed_residuals(observable, response_map, spec)
    residual = np.asarray([r["residual_m"] for r in rows])
    systematic = np.max([r["propagated_position_uncertainty_m"] for r in rows], axis=0)
    lower, upper = np.min(residual, axis=0) - systematic, np.max(residual, axis=0) + systematic
    radius = float(np.max(np.maximum(np.abs(lower), np.abs(upper))))
    return {"recording_id": observable["recording_id"], "pattern": observable["pattern"],
            "density": observable["density"], "residual_lower_m": lower.tolist(),
            "residual_upper_m": upper.tolist(), "maximum_radius_m": radius,
            "sample_count": len(rows), "monitor_qualified": all(r["monitor_qualified"] for r in rows),
            "within_declared_correction_budget": bool(radius <= spec.correction_budget_m),
            "interval_status": "empirical extrema plus engineering systematic allowance; no guaranteed statistical coverage",
            "residual_witnesses": rows}


def assess_applicability(observable, response_map, envelope, spec=DomainSpec()):
    if (observable["recording_id"] == envelope["recording_id"] or
            observable["pattern"] != envelope["pattern"] or observable["density"] != envelope["density"]):
        raise ValueError("independent recording and exactly tested pattern/density required")
    rows = observed_residuals(observable, response_map, spec)
    residual = np.asarray([r["residual_m"] for r in rows])
    inside = (residual >= envelope["residual_lower_m"]) & (residual <= envelope["residual_upper_m"])
    joint_coverage = float(np.mean(np.all(inside, axis=1)))
    monitor_ok = all(r["monitor_qualified"] for r in rows)
    error_max = float(np.max(np.abs(residual)))
    reasons = []
    if not response_map["qualified"]:
        reasons.append("RESPONSE_MAP_UNQUALIFIED")
    if not envelope["within_declared_correction_budget"]:
        reasons.append("PROPAGATED_EMPIRICAL_ENVELOPE_EXCEEDS_25MM")
    if not monitor_ok or not envelope["monitor_qualified"]:
        reasons.append("MONITOR_UNQUALIFIED")
    if joint_coverage < spec.heldout_joint_coverage_floor:
        reasons.append("OBSERVED_HELDOUT_COVERAGE_BELOW_PREDECLARED_FLOOR")
    if error_max > spec.correction_budget_m:
        reasons.append("OBSERVED_HELDOUT_RESIDUAL_EXCEEDS_25MM")
    return {"recording_id": observable["recording_id"], "pattern": observable["pattern"],
            "density": observable["density"], "sample_count": len(rows),
            "empirical_component_coverage": np.mean(inside, axis=0).tolist(),
            "empirical_joint_coverage": joint_coverage,
            "maximum_absolute_residual_m": error_max,
            "residual_rmse_m": float(np.sqrt(np.mean(residual ** 2))),
            "applicable_within_tested_domain": not reasons, "reasons": reasons,
            "residual_witnesses": rows,
            "scope": "observed correlated plateau samples in this held-out recording; no confidence/guaranteed population coverage"}


def study_config(branch, biological_variant):
    if branch not in {"actual_nominal_delivery", "conditional_fast_assumed_delivery"}:
        raise ValueError("unknown delivery branch")
    return replace(motor.MotorConfig(), body_integration_method="midpoint_exact_cascade",
                   body_integration_step_s=.0025, biological_variant=biological_variant,
                   motor_onset_delay_s=.005 if branch == "conditional_fast_assumed_delivery" else .035)


def run_response_study(seed=0, branch="conditional_fast_assumed_delivery", biological_variant="nominal",
                       spec=DomainSpec()):
    config = study_config(branch, biological_variant)
    delivery = MotorDelivery() if branch == "actual_nominal_delivery" else None
    existing_map, _, existing_metadata = motor.calibrate(seed, config, delivery)
    existing_truth_pulses = existing_metadata["monitor_pulses"]
    existing_metadata = {**existing_metadata, "monitor_pulses": [
        {key: pulse[key] for key in ("time_s", "source_id", "route_sign",
          "delivered_phase_charge_C", "charge_uncertainty_C", "quality", "inhibit_next")}
        for pulse in existing_truth_pulses]}
    branch_index = 1 if branch == "actual_nominal_delivery" else 0
    biology_index = ("nominal", "no_authority", "cross_route_adverse").index(biological_variant)
    base_id = 1000000 + branch_index * 1000000 + biology_index * 100000 + seed * 1000
    training = [capture_response(seed, base_id + index, config, pattern, 1., branch, spec=spec)
                for index, pattern in enumerate(tuple(PATTERNS)[:4])]
    response_map = fit_route_map([c["observable"] for c in training], spec)
    validations = []
    for pattern_index, pattern in enumerate(PATTERNS):
        for density_index, density in enumerate(DENSITIES):
            offset = pattern_index * 30 + density_index * 3
            envelope_capture = capture_response(seed, base_id + 100 + offset, config, pattern, density, branch, spec=spec)
            envelope = empirical_envelope(envelope_capture["observable"], response_map, spec)
            heldout = capture_response(seed, base_id + 101 + offset, config, pattern, density, branch, spec=spec)
            changed = capture_response(seed, base_id + 102 + offset, config, pattern, density, branch,
                                       changed_context=True, spec=spec)
            nominal_assessment = assess_applicability(heldout["observable"], response_map, envelope, spec)
            context_assessment = assess_applicability(changed["observable"], response_map, envelope, spec)
            validations.append({"pattern": pattern, "density": density,
                                "envelope_capture": envelope_capture, "envelope": envelope,
                                "heldout_nominal_capture": heldout, "heldout_nominal": nominal_assessment,
                                "heldout_changed_context_capture": changed, "heldout_changed_context": context_assessment})
    pulse_counts = Counter()
    for capture in training + [v[key] for v in validations for key in (
            "envelope_capture", "heldout_nominal_capture", "heldout_changed_context_capture")]:
        pulse_counts.update(m["quality"] for m in capture["observable"]["monitors"])
    return {"schema": "scci_rh.stage3.response-domain-study.v1",
            "metadata": {"seed": seed, "branch": branch, "biological_variant": biological_variant,
                         "config": asdict(config), "spec": asdict(spec),
                         "profile_scope": "fixed3mA/200us/24V40Hz whole-frame density; no current/width/route-anatomy extrapolation",
                         "information_boundary": "fit/envelope/assessment accept sanitized measured positions, timestamped independent monitors and declared commands only",
                         "changed_context_evaluator": "same subject draw with declared .65 gain fraction and .40 asymmetric cross coupling; not disclosed to fit",
                         "calibration_exposure_s": 24., "extra_route_fit_exposure_s": 10.,
                         "envelope_exposure_s": 45., "heldout_nominal_exposure_s": 45.,
                         "heldout_changed_context_exposure_s": 45.,
                         "all_recording_ids_distinct": True, "learning_enabled": False},
            "existing_calibration_anchor": {"response_map": asdict(existing_map),
                                             "evidence": existing_metadata},
            "evaluator_only_calibration_pulse_witnesses": existing_truth_pulses,
            "response_map": response_map, "training_captures": training, "validations": validations,
            "summary": {"finite_pattern_density_cases": len(validations),
                        "nominal_applicable_cases": sum(v["heldout_nominal"]["applicable_within_tested_domain"] for v in validations),
                        "changed_context_applicable_cases": sum(v["heldout_changed_context"]["applicable_within_tested_domain"] for v in validations),
                        "nominal_minimum_joint_coverage": min(v["heldout_nominal"]["empirical_joint_coverage"] for v in validations),
                        "changed_context_minimum_joint_coverage": min(v["heldout_changed_context"]["empirical_joint_coverage"] for v in validations),
                        "maximum_empirical_envelope_radius_m": max(v["envelope"]["maximum_radius_m"] for v in validations),
                        "monitor_quality_pulse_counts": dict(pulse_counts)}}
