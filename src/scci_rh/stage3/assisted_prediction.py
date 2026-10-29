"""Causal measured-state prediction under explicitly assumed planned intervention.

Offline target measurements may train/validate a model. The online input contract
contains past measurements, available monitor records and known instructions only.
Empirical error allocations are not universal or statistical error bounds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import numpy as np


@dataclass(frozen=True)
class PredictionSpec:
    sample_s: float = .005
    history_rows: int = 16
    dose_history_s: float = .300
    maximum_horizon_s: float = .150
    frame_s: float = .025
    complete_profile_s: float = .000500
    forecast_limit_m: float = .015
    correction_limit_m: float = .025
    label_allowance_m: float = .003
    purge_s: float = .100
    ridge: float = .5
    feature_standardized_limit: float = 5.
    assumed_measured_fraction: float = 1.012
    assumed_uncertainty_fraction: float = .074
    prospective_qualification: str = "UNQUALIFIED_NOMINAL_ASSUMPTION"

    def __post_init__(self):
        if (self.sample_s != .005 or self.history_rows != 16 or self.dose_history_s != .300
                or self.maximum_horizon_s != .150 or self.frame_s != .025
                or self.forecast_limit_m != .015 or self.correction_limit_m != .025
                or self.complete_profile_s != .000500):
            raise ValueError("This experiment freezes its clocks, horizons and error allocations")
        numeric = [v for v in asdict(self).values() if isinstance(v, (float, int))]
        if not all(np.isfinite(v) and v > 0 for v in numeric):
            raise ValueError("Finite positive prediction specification required")
        if self.prospective_qualification != "UNQUALIFIED_NOMINAL_ASSUMPTION":
            raise ValueError("Future dose is a declared assumption, never qualified monitor evidence")


@dataclass(frozen=True)
class KnownInstruction:
    cadence_hz: float = 1.
    task_time_offset_s: float = 0.

    def __post_init__(self):
        if not np.isfinite(self.cadence_hz) or self.cadence_hz <= 0 or not np.isfinite(self.task_time_offset_s):
            raise ValueError("Finite known task instruction required")

    def basis(self, time_s):
        time_s = float(time_s)+self.task_time_offset_s
        direction = 1. if int(time_s//2) % 2 == 0 else -1.
        angle = 2*np.pi*self.cadence_hz*time_s
        return direction*np.array([np.sin(angle), np.cos(angle), np.sin(3*angle), np.cos(3*angle)])


@dataclass(frozen=True)
class MeasuredPosition:
    support_s: float
    available_s: float
    position_m: tuple[float, float]
    valid: bool = True
    neural_valid: bool = False


@dataclass(frozen=True)
class ObservedDose:
    frame_time_s: float
    available_s: float
    source_id: int
    route_sign: int
    measured_fraction: float
    uncertainty_fraction: float
    quality: str


@dataclass(frozen=True)
class PlannedFrame:
    frame_time_s: float
    signed_routes: tuple[int, int]
    known_since_s: float = 0.
    qualification: str = "UNQUALIFIED_NOMINAL_ASSUMPTION"


@dataclass(frozen=True)
class PredictionInput:
    now_s: float
    history: tuple[MeasuredPosition, ...]
    observed_dose: tuple[ObservedDose, ...]
    planned_frames: tuple[PlannedFrame, ...]
    instruction: KnownInstruction


def measured_record(observation):
    """Discard every simulator/decoder field; preserve qualification explicitly."""
    return MeasuredPosition(float(observation.external_measurement_time_s),
                            float(observation.available_time_s),
                            tuple(float(v) for v in observation.external_position_m),
                            bool(observation.external_valid), bool(observation.neural.valid))


def _frame_index(time_s, spec):
    cycles = float(time_s)/spec.frame_s
    if not np.isfinite(cycles) or abs(cycles-round(cycles)) > 1e-8:
        raise ValueError("Intervention must use complete 40 Hz profile frames")
    return int(round(cycles))


def validate_input(packet: PredictionInput, spec=PredictionSpec()):
    if not isinstance(packet, PredictionInput) or not isinstance(packet.instruction, KnownInstruction):
        raise ValueError("Sanitized prediction input contract required")
    if not np.isfinite(packet.now_s) or len(packet.history) != spec.history_rows:
        raise ValueError("Finite clock and complete measured history required")
    previous_support = previous_arrival = -np.inf
    for row in packet.history:
        values = np.r_[row.support_s, row.available_s, row.position_m]
        if (not isinstance(row, MeasuredPosition) or np.asarray(row.position_m).shape != (2,)
                or not np.all(np.isfinite(values)) or not row.valid
                or row.support_s > row.available_s or row.available_s > packet.now_s+1e-12
                or row.support_s <= previous_support or row.available_s <= previous_arrival):
            raise ValueError("Invalid, future, stale or replayed measured position")
        if np.isfinite(previous_support) and abs(row.support_s-previous_support-spec.sample_s) > 1e-9:
            raise ValueError("Measured history must remain on its physical support grid")
        previous_support, previous_arrival = row.support_s, row.available_s
    if packet.now_s-packet.history[-1].support_s > .050+1e-12:
        raise ValueError("Stale measured support")
    observed_keys = set()
    for dose in packet.observed_dose:
        if not isinstance(dose, ObservedDose): raise ValueError("Observed dose contract required")
        numeric = (dose.frame_time_s, dose.available_s, dose.measured_fraction, dose.uncertainty_fraction)
        key = (_frame_index(dose.frame_time_s, spec), dose.source_id)
        if (not all(np.isfinite(v) for v in numeric) or dose.source_id not in (0, 1)
                or dose.route_sign not in (-1, 1) or dose.measured_fraction < 0 or dose.uncertainty_fraction < 0
                or dose.available_s < dose.frame_time_s+spec.complete_profile_s-1e-12
                or dose.available_s > packet.now_s+1e-12
                or dose.quality not in {"VALID", "ASSUMED_NOMINAL"} or key in observed_keys):
            raise ValueError("Future, premature, duplicated or unqualified monitor evidence")
        observed_keys.add(key)
    plan_keys = set()
    for frame in packet.planned_frames:
        if not isinstance(frame, PlannedFrame): raise ValueError("Planned frame contract required")
        key = _frame_index(frame.frame_time_s, spec)
        if (not np.isfinite(frame.known_since_s) or frame.known_since_s > packet.now_s+1e-12
                or len(frame.signed_routes) != 2 or any(v not in (-1, 0, 1) for v in frame.signed_routes)
                or frame.qualification != spec.prospective_qualification or key in plan_keys):
            raise ValueError("Future knowledge, fractional pulse, duplicate frame or mislabeled planned dose")
        plan_keys.add(key)
    return packet.history[-1].support_s


def feature_vector(packet: PredictionInput, horizon_s, spec=PredictionSpec()):
    """Future dose cells use a known plan, not future monitor observations.

    A dose cell is the command frame held by the declared reduced body, not a
    continuous current waveform. Missing plan/monitor coverage is rejected.
    """
    support = validate_input(packet, spec)
    index = int(round(float(horizon_s)/spec.sample_s))
    if (not np.isfinite(horizon_s) or index < 0 or index > 30
            or abs(index*spec.sample_s-horizon_s) > 1e-9):
        raise ValueError("Horizon outside the frozen 0..150 ms 5 ms grid")
    observed = {(_frame_index(d.frame_time_s, spec), d.source_id): d for d in packet.observed_dose}
    planned = {_frame_index(f.frame_time_s, spec): f for f in packet.planned_frames}
    values, allowances = [], []
    assumptions = observed_cells = 0
    for offset in range(-60, 31):
        time = support+offset*spec.sample_s
        if offset > index or time < -1e-10:
            values.extend((0., 0.)); allowances.extend((0., 0.)); continue
        frame_index = int(np.floor((time+1e-10)/spec.frame_s))
        frame = planned.get(frame_index)
        if frame is None: raise ValueError("Missing declared frame coverage")
        for source in (0, 1):
            dose = observed.get((frame_index, source))
            route = frame.signed_routes[source]
            if dose is not None:
                if dose.route_sign != route: raise ValueError("Monitor route contradicts declared command")
                values.append(dose.route_sign*dose.measured_fraction)
                allowances.append(dose.uncertainty_fraction); observed_cells += 1
            elif route == 0:
                values.append(0.); allowances.append(0.)
            elif frame.frame_time_s+spec.complete_profile_s <= packet.now_s+1e-12:
                raise ValueError("A past nonzero command lacks available independent monitor evidence")
            else:
                values.append(route*spec.assumed_measured_fraction)
                allowances.append(spec.assumed_uncertainty_fraction); assumptions += 1
    history = np.asarray([row.position_m for row in reversed(packet.history)]).ravel()
    # The interval mean records known direction-change timing, rather than
    # pretending that its endpoint instruction applied throughout the horizon.
    instructions = np.array([packet.instruction.basis(support+k*spec.sample_s) for k in range(index+1)])
    task = np.r_[instructions[0], instructions[-1], instructions.mean(axis=0)]
    features = np.r_[history, task, values]
    uncertainty = np.r_[np.zeros(len(history)+len(task)), allowances]
    return features, uncertainty, {"observed_dose_cells": observed_cells,
        "prospective_assumed_dose_cells": assumptions, "support_s": support,
        "target_support_s": support+horizon_s,
        "prospective_qualification": spec.prospective_qualification,
        "neural_packet_used_by_forecaster": False,
        "latest_neural_packet_valid": packet.history[-1].neural_valid}


def packet_at(recording, index, spec=PredictionSpec()):
    """Offline iterator constructs only information available at this decision."""
    positions = recording["measurements"]
    if index < spec.history_rows-1: raise ValueError("History warmup")
    now = positions[index].available_s
    support = positions[index].support_s
    # Bound the passed monitor list for performance and exact causal auditing.
    dose = tuple(d for d in recording["observed_dose"]
                 if d.available_s <= now+1e-12 and d.frame_time_s >= support-spec.dose_history_s-spec.frame_s)
    plan = tuple(f for f in recording["planned_frames"]
                 if support-spec.dose_history_s-spec.frame_s <= f.frame_time_s <= support+spec.maximum_horizon_s+1e-12)
    return PredictionInput(now, tuple(positions[index-spec.history_rows+1:index+1]), dose, plan,
                           recording["instruction"])


def _rows(recording, spec):
    rows = []
    for index in range(spec.history_rows-1, len(recording["measurements"])-30):
        if recording["measurements"][index].support_s < .100: continue
        packet = packet_at(recording, index, spec)
        # A single full-horizon validation checks all sanitized observable inputs.
        feature_vector(packet, .150, spec)
        rows.append((index, packet))
    return rows


def fit_assisted_predictor(recordings, spec=PredictionSpec()):
    """Fit direct horizon models with purged chronological observed labels."""
    train, holdout, partitions = [], [], []
    identities = [r["recording_id"] for r in recordings]
    if len(set(identities)) != len(identities) or len(identities) < 2:
        raise ValueError("At least two distinct calibration recording identities required")
    for recording in recordings:
        rows = _rows(recording, spec)
        measurements = recording["measurements"]
        cut = measurements[int(len(measurements)*.75)].support_s
        local_train, local_holdout = [], []
        for index, packet in rows:
            if measurements[index+30].support_s < cut-spec.purge_s:
                local_train.append((recording, index, packet))
            if packet.history[0].support_s > cut+spec.purge_s:
                local_holdout.append((recording, index, packet))
        if len(local_train) < 100 or len(local_holdout) < 100:
            raise ValueError("Insufficient complete purged recording partitions")
        train.extend(local_train); holdout.extend(local_holdout)
        partitions.append({"recording_id": recording["recording_id"], "cut_support_s": cut,
            "training_rows": len(local_train), "heldout_rows": len(local_holdout),
            "latest_training_label_s": measurements[local_train[-1][1]+30].support_s,
            "earliest_heldout_history_s": local_holdout[0][2].history[0].support_s})
    models = []
    for hindex in range(31):
        horizon = hindex*spec.sample_s
        built = [feature_vector(packet, horizon, spec) for _, _, packet in train+holdout]
        features = np.array([b[0] for b in built])
        interval = np.array([b[1] for b in built])
        labels = np.array([r["measurements"][i+hindex].position_m for r, i, _ in train+holdout])
        mean = features[:len(train)].mean(axis=0)
        scale = np.maximum(features[:len(train)].std(axis=0), 1e-6)
        standardized = (features-mean)/scale
        design = np.column_stack((np.ones(len(features)), standardized))
        penalty = np.eye(design.shape[1])*spec.ridge; penalty[0, 0] = 1e-9
        weights = np.linalg.solve(design[:len(train)].T@design[:len(train)]+penalty,
                                  design[:len(train)].T@labels[:len(train)])
        residual = design[len(train):]@weights-labels[len(train):]
        dose_projection = interval[len(train):]@np.abs(weights[1:]/scale[:, None])
        maximum = float(np.max(np.abs(residual)))
        maximum_projection = float(np.max(dose_projection))
        allocation = maximum+spec.label_allowance_m+maximum_projection
        standardized_maximum = float(np.max(np.abs(standardized[len(train):])))
        models.append({"horizon_s": horizon, "mean": mean, "scale": scale, "weights": weights,
            "empirical_residual_rmse_m": float(np.sqrt(np.mean(residual**2))),
            "empirical_maximum_component_residual_m": maximum,
            "maximum_dose_input_interval_projection_m": maximum_projection,
            "empirical_error_allocation_m": allocation,
            "qualified": allocation <= spec.forecast_limit_m and standardized_maximum <= spec.feature_standardized_limit,
            "heldout_standardized_feature_maximum": standardized_maximum})
    return {"schema": "scci_rh.stage3.assisted-predictor.v1", "specification": asdict(spec),
        "models": models, "partitions": partitions, "training_recording_ids": identities,
        "training_rows_per_horizon": len(train), "chronological_heldout_rows_per_horizon": len(holdout),
        "feature_dimension": len(models[0]["mean"]),
        "feature_permission": "16past measured positions; current/target/mean known instructions; available past monitored dose and explicitly assumed known planned dose cells; no online future measured labels",
        "error_semantics": "finite empirical residual plus chosen label allowance plus fitted-model input-interval projection; no universal/statistical bound",
        "context_validation": {}}


def predict_assisted(model, packet, horizon_s, *, context_id=None, spec=PredictionSpec(), require_qualified=True):
    features, interval, witness = feature_vector(packet, horizon_s, spec)
    hindex = int(round(horizon_s/spec.sample_s)); fitted = model["models"][hindex]
    z = (features-np.asarray(fitted["mean"]))/np.asarray(fitted["scale"])
    if not np.all(np.isfinite(z)) or np.max(np.abs(z)) > spec.feature_standardized_limit:
        raise ValueError("Prediction inputs outside the fitted feature domain")
    if require_qualified:
        context = model["context_validation"].get(context_id)
        if context is None or not context["qualified"] or not context["horizons"][hindex]["qualified"]:
            raise ValueError("Independent assisted context/horizon is unqualified")
        if asdict(packet.instruction) != context["instruction"]:
            raise ValueError("Known instruction differs from the validated finite context")
        expected = {_frame_index(f["frame_time_s"], spec): tuple(f["signed_routes"])
                    for f in context["validated_planned_frames"]}
        if any(expected.get(_frame_index(f.frame_time_s, spec)) != tuple(f.signed_routes)
               for f in packet.planned_frames):
            raise ValueError("Command schedule differs from the validated finite context")
        start, end = context["validated_support_interval_s"]
        if not start-1e-12 <= packet.history[-1].support_s <= end+1e-12:
            raise ValueError("Observation support lies outside the validated finite context")
        if not fitted["qualified"]:
            raise ValueError("Chronological forecast allocation is unqualified")
    weights = np.asarray(fitted["weights"])
    prediction = np.r_[1., z]@weights
    projected = interval@np.abs(weights[1:]/np.asarray(fitted["scale"])[:, None])
    result = {**witness, "horizon_s": float(horizon_s), "position_m": prediction,
        "dose_input_interval_projection_m": projected,
        "empirical_training_error_allocation_m": fitted["empirical_error_allocation_m"],
        "context_id": context_id, "qualified_for_context": bool(require_qualified)}
    if require_qualified:
        checked = context["horizons"][hindex]
        residual_allowance = max(fitted["empirical_maximum_component_residual_m"],
                                 checked["maximum_component_residual_m"])+spec.label_allowance_m
        # Saved totals already include their respective maximum dose-input
        # projections. Retain those finite gates via max; do not add their
        # projections a second time to the current interval propagation.
        live_total = np.maximum(max(fitted["empirical_error_allocation_m"],
                                    checked["empirical_error_allocation_m"]),
                                residual_allowance+projected)
        if not np.all(np.isfinite(live_total)) or np.max(live_total) > spec.forecast_limit_m:
            raise ValueError("Current dose-input interval exceeds the qualified forecast allocation")
        result["live_forecast_error_allocation_m"] = live_total
        result["empirical_residual_plus_label_allowance_m"] = residual_allowance
    return result


def validate_assisted_recording(model, recording, spec=PredictionSpec()):
    """Entire independent recording, every requested horizon; no refitting."""
    if recording["recording_id"] in model["training_recording_ids"]:
        raise ValueError("Complete withheld recording identity must differ from training")
    rows = _rows(recording, spec)
    horizons, raw = [], []
    for hindex in range(31):
        errors, intervals, rejected = [], [], 0
        for index, packet in rows:
            try:
                predicted = predict_assisted(model, packet, hindex*spec.sample_s, spec=spec, require_qualified=False)
            except ValueError as exc:
                rejected += 1
                raw.append({"index": index, "horizon_s": hindex*spec.sample_s,
                            "reason": str(exc), "admitted": False})
                continue
            label = np.asarray(recording["measurements"][index+hindex].position_m)
            error = np.asarray(predicted["position_m"])-label
            errors.append(error); intervals.append(predicted["dose_input_interval_projection_m"])
            raw.append({"index": index, "horizon_s": hindex*spec.sample_s,
                        "reason": "WITHHELD_MEASURED_LABEL_EVALUATION", "admitted": True,
                        "prediction": predicted, "measured_target_m": label,
                        "target_available_s": recording["measurements"][index+hindex].available_s,
                        "residual_m": error})
        maximum = float(np.max(np.abs(errors))) if errors else None
        dose_allowance = float(np.max(intervals)) if intervals else None
        allocation = None if maximum is None else maximum+spec.label_allowance_m+dose_allowance
        fitted = model["models"][hindex]
        horizons.append({"horizon_s": hindex*spec.sample_s, "evaluated_rows": len(errors),
            "out_of_domain_rows": rejected, "maximum_component_residual_m": maximum,
            "rmse_m": float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
            "maximum_dose_interval_projection_m": dose_allowance,
            "empirical_error_allocation_m": allocation,
            "qualified": bool(errors) and rejected == 0 and fitted["qualified"]
                         and allocation <= spec.forecast_limit_m})
    context = {"recording_id": recording["recording_id"], "qualified": all(h["qualified"] for h in horizons),
        "horizons": horizons, "complete_recording_withheld": True,
        "scope": "one finite independent recorded intervention/instruction/context; no feedback-policy or population guarantee",
        "instruction": asdict(recording["instruction"]), "schedule_identity": recording["schedule_identity"],
        "validated_planned_frames": [asdict(f) for f in recording["planned_frames"]],
        "validated_support_interval_s": [rows[0][1].history[-1].support_s,
                                         rows[-1][1].history[-1].support_s],
        "neural_valid_packets": sum(row.neural_valid for row in recording["measurements"]),
        "neural_total_packets": len(recording["measurements"])}
    model["context_validation"][recording["recording_id"]] = context
    return {"context": context, "rows": raw}


def correction_uncertainty(gain, gain_uncertainty, prospective_fraction,
                           prospective_uncertainty, forecast_allocation_m):
    """Exact product-interval triangle allowance, including its joint term."""
    gain, gain_u = np.asarray(gain, dtype=float), np.asarray(gain_uncertainty, dtype=float)
    dose, dose_u = np.asarray(prospective_fraction, dtype=float), np.asarray(prospective_uncertainty, dtype=float)
    if (gain.shape != (2, 2) or gain_u.shape != (2, 2) or dose.shape != (2,) or dose_u.shape != (2,)
            or not np.all(np.isfinite(np.r_[gain.ravel(), gain_u.ravel(), dose, dose_u, forecast_allocation_m]))
            or np.any(gain_u < 0) or np.any(dose_u < 0) or forecast_allocation_m < 0):
        raise ValueError("Finite nonnegative correction allowances required")
    return gain_u@np.abs(dose)+np.abs(gain)@dose_u+gain_u@dose_u+forecast_allocation_m


def coupling_admission(model, context_id, response, representation, *, dynamic_response_qualified=False,
                       prospective_signed_command=(1., -1.), spec=PredictionSpec()):
    """Qualification audit only; this function does not launch or deliver pulses."""
    gain = np.asarray(response.gain_m); gain_u = np.asarray(response.gain_uncertainty_m)
    command = np.asarray(prospective_signed_command, dtype=float)
    if command.shape != (2,) or not np.all(np.isfinite(command)) or np.max(np.abs(command)) > 1:
        raise ValueError("Finite bounded prospective command required")
    authority = float(np.linalg.svd(gain, compute_uv=False)[-1]-np.linalg.norm(gain_u, 2))
    reasons = []
    if not response.qualified or authority <= 0: reasons.append("UNQUALIFIED_OBSERVED_AUTHORITY")
    if not representation.qualified: reasons.append("UNQUALIFIED_TEACHER_REPRESENTATION")
    context = model["context_validation"].get(context_id)
    if context is None or not context["qualified"]: reasons.append("UNQUALIFIED_ASSISTED_FORECAST_CONTEXT")
    if not dynamic_response_qualified: reasons.append("DYNAMIC_EXECUTION_RESPONSE_UNQUALIFIED")
    maximum_forecast = max((h["empirical_error_allocation_m"] or np.inf for h in context["horizons"]), default=np.inf) if context else np.inf
    allowance = None
    if np.isfinite(maximum_forecast):
        allowance = correction_uncertainty(gain, gain_u, command*spec.assumed_measured_fraction,
                                           np.abs(command)*spec.assumed_uncertainty_fraction, maximum_forecast)
        if np.max(allowance) > spec.correction_limit_m: reasons.append("JOINT_CORRECTION_ALLOCATION_EXCEEDED")
    return {"admitted": not reasons, "reasons": reasons, "authority_margin_m": authority,
        "prospective_signed_command": command, "total_correction_allowance_m": allowance,
        "prospective_delivery_qualification": spec.prospective_qualification,
        "dynamic_execution_response_qualified": bool(dynamic_response_qualified),
        "pulse_count": 0, "scope": "admission audit; no physical or coupled digital pulse launched"}
