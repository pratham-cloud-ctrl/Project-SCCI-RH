"""Observable known-instruction forecast and cancellable digital frame planner.

The 150 ms forecast family is distinct from the original 100 ms reactive policy.
Its errors are empirical synthetic-record diagnostics, not statistical bounds.
No simulator state or future achieved motion is an online input.
"""
from collections import deque
from dataclasses import dataclass
import hashlib
import numpy as np

from .motor import StateEstimate, LearnerMap, ExpertRepresentation, task_basis


@dataclass(frozen=True)
class CueConfig:
    maximum_forecast_horizon_s: float = .150
    forecast_grid_s: float = .005
    history_rows: int = 16
    sample_interval_s: float = .005
    frame_hz: float = 40.
    processing_delay_s: float = .01185
    packet_freshness_s: float = .050
    expiry_after_frame_s: float = .001
    forecast_error_limit_m: float = .015
    total_correction_uncertainty_limit_m: float = .025
    measured_label_uncertainty_m: float = .003
    purge_half_width_s: float = .100
    ridge_penalty: float = .5
    # Explicit prospective CHARACTERIZATION ASSUMPTION, never an already
    # measured future dose. Fractions refer to one nominal full-profile pulse.
    future_measured_pulse_fraction: float = 1.012
    future_pulse_uncertainty_fraction: float = .074
    future_delivery_qualification: str = "UNQUALIFIED_NOMINAL_ASSUMPTION"

    def __post_init__(self):
        if (self.maximum_forecast_horizon_s != .150 or self.forecast_grid_s != .005
                or self.history_rows != 16 or self.sample_interval_s != .005 or self.frame_hz != 40.):
            raise ValueError("The cue study fixes its separately declared information/horizon allocation")
        for value in (self.processing_delay_s, self.packet_freshness_s, self.expiry_after_frame_s,
                      self.forecast_error_limit_m, self.total_correction_uncertainty_limit_m,
                      self.measured_label_uncertainty_m, self.purge_half_width_s, self.ridge_penalty):
            if not np.isfinite(value) or value <= 0: raise ValueError("Invalid cue allocation")
        if (not np.isfinite(self.future_measured_pulse_fraction) or self.future_measured_pulse_fraction<=0
                or not np.isfinite(self.future_pulse_uncertainty_fraction) or self.future_pulse_uncertainty_fraction<0
                or self.future_delivery_qualification != "UNQUALIFIED_NOMINAL_ASSUMPTION"):
            raise ValueError("This cue prototype supports only explicitly unqualified prospective delivery")


def _external_packet(observation, now_s, c):
    position = np.asarray(observation.external_position_m, dtype=float)
    support = float(observation.external_measurement_time_s)
    arrival = float(observation.available_time_s)
    if (not np.isfinite(now_s) or not np.isfinite(support) or not np.isfinite(arrival)
            or position.shape != (2,) or not np.all(np.isfinite(position))
            or not observation.external_valid or support > arrival or arrival > now_s+1e-10
            or now_s-support > c.packet_freshness_s): return None
    return support, arrival, position


def _features(history, support, horizon):
    # Two measured coordinates per lag, plus current/future TASK instructions.
    # A task instruction is not an achieved movement or a true neural phase.
    return np.r_[np.asarray([p for _, p in reversed(history)]).ravel(),
                 task_basis(support), task_basis(support+horizon)]


def _offline_rows(observations, c):
    history = deque(maxlen=c.history_rows); records = {}
    previous = -np.inf
    for index, observation in enumerate(observations):
        packet = _external_packet(observation, observation.available_time_s, c)
        if packet is None:
            history.clear(); continue
        support, _, position = packet
        if support <= previous or (history and abs(support-history[-1][0]-c.sample_interval_s)>1e-9):
            history.clear()
        previous = support; history.append((support, position.copy()))
        if len(history) == c.history_rows: records[index] = tuple(history)
    return records


def fit_known_cue_forecast(observations, config=CueConfig()):
    """Offline measured future labels stay inside purged chronology partitions."""
    observations = list(observations); c = config
    if len(observations) < 1000: raise ValueError("The declared cue calibration requires at least 5 s")
    records = _offline_rows(observations, c)
    times = np.array([o.external_measurement_time_s for o in observations])
    cut = times[int(len(times)*.75)]
    maximum_rows = int(round(c.maximum_forecast_horizon_s/c.sample_interval_s))
    train, valid = [], []
    for index, history in records.items():
        last = index+maximum_rows
        if last >= len(times) or times[index] < .100: continue
        if abs(times[last]-times[index]-c.maximum_forecast_horizon_s)>1e-9: continue
        if times[last] < cut-c.purge_half_width_s: train.append(index)
        if history[0][0] > cut+c.purge_half_width_s: valid.append(index)
    if len(train)<200 or len(valid)<100: raise ValueError("Insufficient purged forecast partitions")
    models = []
    for horizon_index in range(maximum_rows+1):
        horizon = horizon_index*c.forecast_grid_s
        x = np.array([_features(records[i], times[i], horizon) for i in train+valid])
        y = np.array([observations[i+horizon_index].external_position_m for i in train+valid])
        mean, scale = x[:len(train)].mean(axis=0), np.maximum(x[:len(train)].std(axis=0), 1e-6)
        z = np.column_stack((np.ones(len(x)), (x-mean)/scale))
        penalty = np.eye(z.shape[1])*c.ridge_penalty; penalty[0, 0] = 1e-9
        weights = np.linalg.solve(z[:len(train)].T@z[:len(train)]+penalty, z[:len(train)].T@y[:len(train)])
        residual = z[len(train):]@weights-y[len(train):]
        maximum = float(np.max(np.abs(residual)))
        models.append({"horizon_s": horizon, "mean": mean, "scale": scale, "weights": weights,
            "heldout_rmse_m": float(np.sqrt(np.mean(residual**2))),
            "heldout_maximum_component_error_m": maximum,
            "empirical_error_allocation_m": maximum+c.measured_label_uncertainty_m,
            "qualified": maximum+c.measured_label_uncertainty_m <= c.forecast_error_limit_m})
    support_digest = lambda indices: hashlib.sha256(np.asarray(times[indices], dtype="<f8").tobytes()).hexdigest()
    return {"schema": "scci_rh.stage3.known-cue-forecast.v1", "models": models,
            "context_validation": {"nominal_unassisted": {"qualified": all(m["qualified"] for m in models),
                "error_allocation_m": max(m["empirical_error_allocation_m"] for m in models),
                "scope": "chronological withheld same-subject unassisted nominal-cadence measured record"}},
            "training_rows": len(train), "heldout_rows": len(valid), "split_support_time_s": float(cut),
            "training_support_sha256": support_digest(train), "heldout_support_sha256": support_digest(valid),
            "purge_half_width_s": c.purge_half_width_s,
            "training_latest_label_support_s": float(times[max(train)+maximum_rows]),
            "heldout_earliest_history_support_s": float(records[min(valid)][0][0]),
            "feature_dimension": 40, "coefficient_count_per_horizon": 82,
            "horizon_grid_s": [m["horizon_s"] for m in models],
            "permissions": "40 inputs:32 finite past measured coordinates +4current/4future known taskinstruction components; no future achieved motion online",
            "error_semantics": "maximum measured holdout error plus chosen3mm label allocation; empirical qualification, not universal/statistical bound"}


def validate_forecast_context(model, observations, context_id, config=CueConfig()):
    """Independent observed target records qualify only their declared context."""
    observations = list(observations); c = config; records = _offline_rows(observations, c)
    errors = []; out_of_domain = 0
    for index, history in records.items():
        if observations[index].external_measurement_time_s < .100: continue
        for hindex in (10, 20, 30):
            if index+hindex >= len(observations): continue
            m = model["models"][hindex]; support = observations[index].external_measurement_time_s
            if abs(observations[index+hindex].external_measurement_time_s-support-m["horizon_s"])>1e-9: continue
            z = (_features(history, support, m["horizon_s"])-m["mean"])/m["scale"]
            if not np.all(np.isfinite(z)) or np.max(np.abs(z)) > 5.:
                out_of_domain += 1; continue
            predicted = np.r_[1., z]@m["weights"]
            errors.append(predicted-np.asarray(observations[index+hindex].external_position_m))
    error = float(np.max(np.abs(errors))) if errors else 1.
    allocation = error+c.measured_label_uncertainty_m
    record = {"qualified": bool(errors) and out_of_domain == 0 and allocation <= c.forecast_error_limit_m,
              "error_allocation_m": allocation, "rmse_m": float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
              "evaluated_horizons_s": [.050, .100, .150], "target_rows": len(errors),
              "out_of_domain_rows": out_of_domain,
              "scope": "independent measured capture only; no closed-loop/context generalization claimed"}
    # Sparse context probes cannot qualify every intervening forecast horizon.
    record["qualified_horizons_s"] = [.050, .100, .150] if record["qualified"] else []
    model["context_validation"][context_id] = record
    return record


@dataclass(frozen=True)
class CueCommand:
    command_id: int
    created_time_s: float
    observation_support_s: float
    launch_time_s: float
    expiry_time_s: float
    expected_effect_time_s: float
    forecast_horizon_s: float
    empirical_forecast_error_m: float
    signed_fraction: tuple[float, float]
    context_id: str
    policy_reason: str
    future_delivery_qualification: str = "UNQUALIFIED_NOMINAL_ASSUMPTION"
    prospective_measured_fraction: tuple[float, float] = (0., 0.)
    prospective_dose_uncertainty_fraction: tuple[float, float] = (0., 0.)
    total_correction_error_allocation_m: tuple[float, float] = (0., 0.)


class CuePolicy:
    def __init__(self, model, config=CueConfig()):
        self.model = model; self.config = config
        self.history = deque(maxlen=config.history_rows)
        self.last_support = -np.inf; self.last_arrival = -np.inf; self.sequence = 0
        self._predictions = deque()
        self.residual_latched = False; self.maximum_observed_residual_m = 0.
        self.first_residual_failure_arrival_s = None

    def propose(self, observation, estimate: StateEstimate, response: LearnerMap,
                representation: ExpertRepresentation, now_s, *, context_id="nominal_unassisted"):
        c = self.config; packet = _external_packet(observation, now_s, c)
        def reject(reason): return None, reason
        if packet is None:
            self.history.clear(); return reject("INVALID_OR_STALE_OR_FUTURE_OBSERVATION")
        support, arrival, position = packet
        if support <= self.last_support or arrival <= self.last_arrival:
            self.history.clear(); return reject("REPLAYED_OR_NONMONOTONIC_OBSERVATION")
        if self.history and abs(support-self.history[-1][0]-c.sample_interval_s)>1e-9:
            self.history.clear()
        self.last_support, self.last_arrival = support, arrival
        self.history.append((support, position.copy()))
        # Previously forecast targets become checkable only when their actual
        # measured support arrives. This can detect a change after a finite
        # delay; it does not retroactively qualify earlier commands.
        future = deque()
        for target, prediction in self._predictions:
            if target > support+1e-9: future.append((target, prediction)); continue
            if abs(target-support)>1e-9: continue  # missing/replayed targets are not invented
            residual = float(np.max(np.abs(position-prediction)))
            self.maximum_observed_residual_m = max(self.maximum_observed_residual_m, residual)
            if residual > c.forecast_error_limit_m:
                self.residual_latched = True
                if self.first_residual_failure_arrival_s is None:
                    self.first_residual_failure_arrival_s = float(arrival)
        self._predictions = future
        gain = np.asarray(response.gain_m); uncertainty = np.asarray(response.gain_uncertainty_m)
        coefficients = np.asarray(representation.coefficients_m)
        values = np.r_[estimate.position_m, estimate.velocity_m_per_s, estimate.support_time_s,
            estimate.uncertainty_m, response.onset_delay_s, response.onset_uncertainty_s,
            gain.ravel(), uncertainty.ravel(), coefficients.ravel()]
        if (gain.shape!=(2, 2) or uncertainty.shape!=(2, 2) or not np.all(np.isfinite(values))
                or coefficients.shape!=(2, 4) or np.asarray(estimate.position_m).shape!=(2,)
                or np.asarray(estimate.velocity_m_per_s).shape!=(2,)
                or np.any(uncertainty<0) or response.onset_delay_s<0 or response.onset_uncertainty_s<0
                or estimate.uncertainty_m<0 or abs(estimate.support_time_s-support)>1e-9):
            return reject("INVALID_OBSERVABLE_CONTRACT")
        if not estimate.valid: return reject("INVALID_STATE")
        if not representation.qualified: return reject("UNAVAILABLE_EXPERT_REPRESENTATION")
        authority = np.linalg.svd(gain, compute_uv=False)[-1]-np.linalg.norm(uncertainty, 2)
        if not response.qualified or authority <= 0: return reject("UNQUALIFIED_OBSERVED_AUTHORITY")
        if self.residual_latched: return reject("RECENT_MEASURED_FORECAST_RESIDUAL_EXCEEDS_ALLOCATION")
        context = self.model["context_validation"].get(context_id)
        if context is None or not context["qualified"]: return reject("UNVALIDATED_FORECAST_CONTEXT")
        if len(self.history)<c.history_rows: return reject("FORECAST_HISTORY_WARMUP")
        launch = np.ceil((now_s+c.processing_delay_s-1e-12)*c.frame_hz)/c.frame_hz
        effect = launch+response.onset_delay_s+2*response.onset_uncertainty_s
        horizon = np.ceil((effect-support-1e-12)/c.forecast_grid_s)*c.forecast_grid_s
        if horizon > c.maximum_forecast_horizon_s+1e-12: return reject("CUE_FORECAST_HORIZON_EXCEEDS_VALIDATED_DOMAIN")
        if "qualified_horizons_s" in context and not any(abs(horizon-h)<1e-9 for h in context["qualified_horizons_s"]):
            return reject("CONTEXT_HORIZON_UNVALIDATED")
        index = int(round(horizon/c.forecast_grid_s)); m = self.model["models"][index]
        if not m["qualified"]: return reject("FORECAST_HELDOUT_ERROR_EXCEEDS_ALLOCATION")
        z = (_features(self.history, support, horizon)-m["mean"])/m["scale"]
        if not np.all(np.isfinite(z)) or np.max(np.abs(z))>5.: return reject("FORECAST_OUT_OF_CALIBRATION")
        forecast = np.r_[1., z]@m["weights"]
        desired = coefficients@task_basis(support+horizon)
        solved_measured_fraction = np.linalg.solve(gain.T@gain+np.eye(2)*1e-4, gain.T@(desired-forecast))
        request = np.clip(solved_measured_fraction/c.future_measured_pulse_fraction, -1., 1.)
        prospective_measured = request*c.future_measured_pulse_fraction
        prospective_uncertainty = np.abs(request)*c.future_pulse_uncertainty_fraction
        error = max(context["error_allocation_m"], m["empirical_error_allocation_m"])
        # (G±UG)(u±Uu) requires the joint term UG*Uu as well as its two
        # first-order terms. Command is not measured delivery: these u/Uu are
        # explicit future-assumption inputs and remain unqualified.
        total = (np.abs(uncertainty)@np.abs(prospective_measured)
                 +np.abs(gain)@prospective_uncertainty
                 +np.abs(uncertainty)@prospective_uncertainty+error)
        if np.max(total)>c.total_correction_uncertainty_limit_m:
            return reject("OBSERVED_MAP_PLUS_FORECAST_ERROR_EXCEEDS_ALLOCATION")
        self.sequence += 1
        self._predictions.append((float(support+horizon), forecast.copy()))
        return CueCommand(self.sequence, float(now_s), float(support), float(launch),
            float(launch+c.expiry_after_frame_s), float(support+horizon), float(horizon),
            float(error), tuple(float(v) for v in request), context_id,
            "KNOWN_CUE_EMPIRICALLY_QUALIFIED_DOMAIN", c.future_delivery_qualification,
            tuple(float(v) for v in prospective_measured),
            tuple(float(v) for v in prospective_uncertainty),
            tuple(float(v) for v in total)), "PLANNED_KNOWN_CUE_COMMAND"


class CueFrameScheduler:
    """Latest qualified plan; every new packet can cancel it before launch."""
    def __init__(self, config=CueConfig()):
        self.config = config; self.pending = None; self.events = []
        self._plans = {}
        self.last_support = -np.inf; self.last_arrival = -np.inf
        self.guard_valid = False; self.context_id = None; self.last_command_id = 0
        self.last_tick_time_s = -np.inf

    def cancel(self, now_s, reason):
        for command in sorted(self._plans.values(), key=lambda item: item.launch_time_s):
            self.events.append({"time_s": float(now_s), "event": "CANCEL", "reason": reason,
                                "command_id": command.command_id})
        self._plans.clear(); self.pending = None

    def observe_guard(self, observation, estimate, now_s, context_id):
        packet = _external_packet(observation, now_s, self.config)
        state_values = np.r_[estimate.position_m, estimate.velocity_m_per_s,
                             estimate.support_time_s, estimate.uncertainty_m]
        reason = None
        if (packet is None or not estimate.valid or not np.all(np.isfinite(state_values))
                or estimate.uncertainty_m < 0): reason = "INVALID_OR_STALE_OBSERVER"
        elif packet[0] <= self.last_support or packet[1] <= self.last_arrival: reason = "REPLAYED_OBSERVER"
        elif abs(estimate.support_time_s-packet[0])>1e-9: reason = "OBSERVER_SUPPORT_MISMATCH"
        elif self.context_id is not None and context_id != self.context_id: reason = "CONTEXT_CHANGED"
        if packet is not None:
            self.last_support = max(self.last_support, packet[0]); self.last_arrival = max(self.last_arrival, packet[1])
        self.guard_valid = reason is None; self.context_id = context_id
        if reason: self.cancel(now_s, reason)
        return reason

    def submit(self, command, now_s):
        if command is None: self.cancel(now_s, "POLICY_ABSTAINED"); return False
        c = self.config
        values = np.r_[now_s, command.created_time_s, command.observation_support_s, command.launch_time_s,
                       command.expiry_time_s, command.expected_effect_time_s, command.forecast_horizon_s,
                       command.empirical_forecast_error_m, command.signed_fraction,
                       command.prospective_measured_fraction, command.prospective_dose_uncertainty_fraction,
                       command.total_correction_error_allocation_m]
        if (not np.all(np.isfinite(values)) or not self.guard_valid
                or command.context_id != self.context_id or command.command_id <= self.last_command_id
                or abs(command.created_time_s-now_s)>1e-9
                or abs(command.observation_support_s-self.last_support)>1e-9
                or command.launch_time_s+1e-12 < now_s+c.processing_delay_s
                or command.expiry_time_s < command.launch_time_s
                or not 0 <= command.forecast_horizon_s <= c.maximum_forecast_horizon_s
                or not 0 <= command.empirical_forecast_error_m <= c.forecast_error_limit_m
                or np.asarray(command.signed_fraction).shape != (2,)
                or abs(command.expected_effect_time_s-command.observation_support_s-command.forecast_horizon_s)>1e-9
                or command.expected_effect_time_s < command.launch_time_s
                or command.future_delivery_qualification != c.future_delivery_qualification
                or np.any(np.asarray(command.prospective_dose_uncertainty_fraction)<0)
                or np.any(np.asarray(command.total_correction_error_allocation_m)<0)
                or np.max(command.total_correction_error_allocation_m)>c.total_correction_uncertainty_limit_m
                or np.max(np.abs(command.signed_fraction)) > 1.):
            self.cancel(now_s, "INVALID_OR_REPLAYED_COMMAND"); return False
        if abs(command.launch_time_s*c.frame_hz-round(command.launch_time_s*c.frame_hz))>1e-9:
            self.cancel(now_s, "COMMAND_NOT_ON_FRAME"); return False
        # A newer plan replaces only its own frame. Replacing every pending
        # command would continually postpone older eligible frames and starve
        # output even with perfectly valid observations.
        self._plans[round(command.launch_time_s*c.frame_hz)] = command
        self.pending = min(self._plans.values(), key=lambda item: item.launch_time_s)
        self.last_command_id = command.command_id
        return True

    def tick(self, now_s):
        if not np.isfinite(now_s): self.cancel(0., "INVALID_CLOCK"); return None
        if now_s < self.last_tick_time_s-1e-12:
            self.cancel(now_s, "NONMONOTONIC_CLOCK"); return None
        self.last_tick_time_s = now_s
        command = self.pending
        if command is None: return None
        if now_s > command.expiry_time_s+1e-12: self.cancel(now_s, "COMMAND_EXPIRED"); return None
        if now_s > command.launch_time_s+1e-9: self.cancel(now_s, "MISSED_FRAME"); return None
        if now_s < command.launch_time_s-1e-9: return None
        if self.last_arrival > now_s+1e-12:
            self.cancel(now_s, "FUTURE_OBSERVER_AT_LAUNCH"); return None
        if not self.guard_valid or now_s-self.last_support > self.config.packet_freshness_s:
            self.cancel(now_s, "OBSERVER_STALE_AT_LAUNCH"); return None
        self._plans.pop(round(command.launch_time_s*self.config.frame_hz))
        self.pending = min(self._plans.values(), key=lambda item: item.launch_time_s) if self._plans else None
        self.events.append({"time_s": float(now_s), "event": "LAUNCH", "command_id": command.command_id,
                            "support_time_s": self.last_support, "context_id": command.context_id})
        return command
