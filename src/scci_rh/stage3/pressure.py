"""Causal, external-SBP feedback study for the Stage 3 SCCI mechanism.

All biological coefficients and the example target are artificial sensitivity
assumptions.  The controller never receives the plant, its coefficients, future
samples, or the delivered-dose truth.  This is a digital model, not a dose policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from collections import deque
from typing import Callable, Mapping
import math
import numpy as np

PA_PER_MMHG = 133.322387415


@dataclass(frozen=True)
class PressureObservation:
    """Contract S2-C-004: physical peak/support time survives packet transport."""
    sbp_pa: float
    support_start_s: float
    support_end_s: float
    peak_time_s: float
    arrival_s: float
    sequence: int
    valid: bool = True
    clock_uncertainty_s: float = 0.0005
    uncertainty_pa: float = 2.0 * PA_PER_MMHG

    def age_bound_s(self, now_s: float) -> float:
        return now_s - self.peak_time_s + self.clock_uncertainty_s

    def fresh(self, now_s: float, maximum_age_s: float = 2.0) -> bool:
        return (self.valid and math.isfinite(self.sbp_pa)
                and math.isfinite(self.clock_uncertainty_s) and self.clock_uncertainty_s >= 0
                and math.isfinite(self.uncertainty_pa) and self.uncertainty_pa >= 0
                and self.support_start_s <= self.peak_time_s <= self.support_end_s
                and self.support_end_s <= self.arrival_s <= now_s
                and 0 <= self.age_bound_s(now_s) <= maximum_age_s)


@dataclass(frozen=True)
class DeliveryMonitorObservation:
    """Controller-visible delivery record contains no actual-delivery truth."""
    measured_fraction: float | None
    uncertainty_fraction: float
    qualified: bool
    reason: str


@dataclass(frozen=True)
class DeliveryEvidence:
    """Actual dose is simulator input; measured dose alone is controller evidence.

Fractions describe pulse-train dose relative to the selected 3-profile electrical
reference.  They are not volts, current, dose prescriptions or recruitment.
"""
    effective_fraction: float
    measured_fraction: float | None
    uncertainty_fraction: float = 0.03
    qualified: bool = True
    reason: str = "chosen_reference_delivery_surrogate"

    def controller_view(self) -> DeliveryMonitorObservation:
        return DeliveryMonitorObservation(self.measured_fraction, self.uncertainty_fraction,
                                          self.qualified, self.reason)

    @classmethod
    def from_value(cls, value: DeliveryEvidence | Mapping) -> DeliveryEvidence:
        evidence = value if isinstance(value, cls) else cls(**dict(value))
        if not (math.isfinite(evidence.effective_fraction)
                and 0 <= evidence.effective_fraction <= 1):
            raise ValueError("effective delivery fraction outside [0, 1]")
        if evidence.measured_fraction is not None and not math.isfinite(evidence.measured_fraction):
            raise ValueError("measured delivery fraction must be finite or unknown")
        if not math.isfinite(evidence.uncertainty_fraction) or evidence.uncertainty_fraction < 0:
            raise ValueError("delivery uncertainty must be finite and nonnegative")
        return evidence


@dataclass(frozen=True)
class PressureConfig:
    duration_s: float = 420.0
    integration_step_s: float = 0.005
    waveform_sample_hz: int = 200
    extraction_period_s: float = 1.0
    policy_period_s: float = 0.25
    freshness_limit_s: float = 2.0
    target_pa: float = 120.0 * PA_PER_MMHG
    calibration_end_s: float = 144.0
    disturbance_start_s: float = 180.0
    disturbance_end_s: float = 340.0
    sensor_noise_pa: float = 0.35 * PA_PER_MMHG
    fallback: str = "stop"
    finite_hold_s: float = 2.0
    ramp_fraction_per_s: float = 0.20
    maximum_fraction: float = 1.0
    rise_slew_fraction_per_s: float = 0.12
    minimum_gain_pa: float = 3.0 * PA_PER_MMHG
    gain_relative_uncertainty: float = 0.25
    heldout_error_limit_pa: float = 4.0 * PA_PER_MMHG

    def validate(self) -> None:
        if self.fallback not in {"stop", "finite_hold", "ramp"}:
            raise ValueError("unknown fallback")
        if self.duration_s <= self.disturbance_end_s or self.calibration_end_s >= self.disturbance_start_s:
            raise ValueError("study must contain calibration, disturbance and recovery")
        if self.integration_step_s <= 0 or self.waveform_sample_hz != 200:
            raise ValueError("positive integration step and selected 200Hz waveform required")
        for period in (1 / self.waveform_sample_hz, self.policy_period_s, self.extraction_period_s):
            if abs(period / self.integration_step_s - round(period / self.integration_step_s)) > 1e-7:
                raise ValueError("integration grid must exactly divide sensor/policy periods")
        if self.policy_period_s != 0.25 or self.extraction_period_s != 1.0 or self.freshness_limit_s != 2.0:
            raise ValueError("selected Stage 2 rates/freshness must remain explicit")
        if not 0 < self.maximum_fraction <= 1 or not 0 <= self.gain_relative_uncertainty < 1:
            raise ValueError("invalid controller bound")


@dataclass(frozen=True)
class PressureScenario:
    """Evaluator-owned hidden plant/sensor parameters, never controller inputs."""
    name: str = "nominal"
    baseline_pa: float = 120 * PA_PER_MMHG
    gain_pa: float = 36 * PA_PER_MMHG
    activation_tau_s: float = 1.5
    response_tau_s: float = 6.0
    onset_delay_s: float = 0.8
    release_delay_s: float = 2.0
    recruitment_threshold: float = 0.0
    disturbance_pa: float = 28 * PA_PER_MMHG
    sensor_delay_s: float = 0.15
    sensor_bias_pa: float = 0.0
    dropout_interval_s: tuple[float, float] | None = None
    invalid_interval_s: tuple[float, float] | None = None
    stale_replay_interval_s: tuple[float, float] | None = None
    changed_gain_pa: float | None = None
    change_time_s: float = 260.0


def default_scenarios() -> dict[str, PressureScenario]:
    """Preregistered structural families; none is fitted to a desired outcome."""
    base = PressureScenario()
    variants = {
        "nominal": base,
        "weak_authority": replace(base, name="weak_authority", gain_pa=5 * PA_PER_MMHG),
        "no_response": replace(base, name="no_response", gain_pa=0),
        "adverse_response": replace(base, name="adverse_response", gain_pa=-15 * PA_PER_MMHG),
        "high_threshold": replace(base, name="high_threshold", recruitment_threshold=0.6),
        "slow_release": replace(base, name="slow_release", activation_tau_s=8.0,
                                response_tau_s=25.0, onset_delay_s=8.0, release_delay_s=40.0),
        "sensor_delayed": replace(base, name="sensor_delayed", sensor_delay_s=2.4),
        "sensor_loss": replace(base, name="sensor_loss", dropout_interval_s=(250, 285)),
        "sensor_invalid": replace(base, name="sensor_invalid", invalid_interval_s=(250, 270)),
        "stale_replay": replace(base, name="stale_replay", stale_replay_interval_s=(250, 285)),
        "sensor_bias": replace(base, name="sensor_bias", sensor_bias_pa=8 * PA_PER_MMHG),
        "unreachable_high": replace(base, name="unreachable_high", baseline_pa=142 * PA_PER_MMHG,
                                     disturbance_pa=0),
        "context_reversal": replace(base, name="context_reversal", changed_gain_pa=-15 * PA_PER_MMHG),
    }
    return variants


@dataclass(frozen=True)
class CalibrationEvidence:
    gain_pa_per_fraction: float | None
    gain_interval_pa: tuple[float, float] | None
    estimated_effect_lag_s: float | None
    one_step_error_pa: float | None
    heldout_recursive_error_pa: float | None
    qualified: bool
    reason: str
    observation_count: int
    dose_observation_count: int
    baseline_observed_pa: float | None
    autoregressive_a: float | None = None


def identify_response(observations: list[PressureObservation], dose_history: list[tuple],
                      config: PressureConfig) -> CalibrationEvidence:
    """Fit a bounded ARX surrogate using past observations and monitored delivery.

Train on beat records ending at <=104s; recursively predict disjoint held-out
105..144s records. Lag grid 0..10s, single exponential is deliberately a model
approximation to the hidden two-state response. No true biological input exists.
"""
    records = [o for o in observations if o.valid and o.arrival_s <= config.calibration_end_s
               and o.age_bound_s(o.arrival_s) <= config.freshness_limit_s]
    doses = [(row[0], row[1], row[2] if len(row) > 2 else 0.0) for row in dose_history
             if row[1] is not None and math.isfinite(row[1])]
    fail = lambda reason: CalibrationEvidence(None, None, None, None, None, False, reason,
                                              len(records), len(doses), None)
    if len(records) < 100 or len(doses) < 100:
        return fail("insufficient_fresh_calibration_or_monitor_observations")
    # Missing/replayed beat identity cannot be filled using latent pressure.
    times = np.array([o.support_end_s for o in records])
    if np.max(np.diff(times)) > 1.001:
        return fail("noncontiguous_calibration_observations")
    y = np.array([o.sbp_pa for o in records])
    baseline = float(np.mean(y[times <= 18]))
    ys = y - baseline
    dose_times = np.array([item[0] for item in doses])
    dose_values = np.array([item[1] for item in doses])
    dose_uncertainties = np.array([item[2] for item in doses])
    active_doses = np.abs(dose_values) > 0.01
    if not np.any(active_doses):
        return fail("no_identifiable_monitored_calibration_excitation")
    dose_relative_uncertainty = float(np.max(dose_uncertainties[active_doses] / np.abs(dose_values[active_doses])))
    if dose_relative_uncertainty >= 1:
        return fail("calibration_dose_interval_includes_zero")
    best = None
    for lag in range(11):
        # Zero-order hold of earlier measured dose, never interpolation into future.
        indices = np.searchsorted(dose_times, times[:-1] - lag, side="right") - 1
        u = np.where(indices >= 0, dose_values[np.maximum(indices, 0)], 0)
        training = (times[1:] >= 20) & (times[1:] <= 104)
        matrix = np.column_stack((ys[:-1][training], u[training]))
        coefficients, _, rank, _ = np.linalg.lstsq(matrix, ys[1:][training], rcond=None)
        if rank < 2:
            continue
        a, b = map(float, coefficients)
        if not 0 <= a < 0.9995:
            continue
        residual = ys[1:][training] - matrix @ coefficients
        training_mse = float(np.mean(residual ** 2))
        if best is None or training_mse < best[0]:
            best = (training_mse, a, b, lag, u)
    if best is None:
        return fail("unstable_or_unidentifiable_response_surrogate")
    mse, a, b, lag, u = best
    gain = b / (1 - a)
    # No test-set model selection: held-out predictions only qualify the chosen fit.
    heldout_indices = np.flatnonzero(times[1:] > 104)
    prediction = float(ys[heldout_indices[0]])
    errors = []
    for index in heldout_indices:
        prediction = a * prediction + b * u[index]
        errors.append(prediction - ys[index + 1])
    heldout_rmse = float(np.sqrt(np.mean(np.square(errors))))
    noise_rmse = math.sqrt(mse)
    uncertainty = max(abs(gain) * (config.gain_relative_uncertainty + dose_relative_uncertainty),
                      2 * noise_rmse / 0.2, heldout_rmse / 0.2)
    lower, upper = gain - uncertainty, gain + uncertainty
    qualified = lower > config.minimum_gain_pa and heldout_rmse <= config.heldout_error_limit_pa
    if gain <= 0:
        reason = "adverse_or_zero_observed_response"
    elif lower <= config.minimum_gain_pa:
        reason = "insufficient_or_uncertain_positive_authority"
    elif heldout_rmse > config.heldout_error_limit_pa:
        reason = "heldout_response_model_mismatch"
    else:
        reason = "conditional_positive_response_model"
    return CalibrationEvidence(gain, (lower, upper), float(lag), noise_rmse,
                               heldout_rmse, qualified, reason, len(records), len(doses), baseline, a)


class PressureController:
    """Bounded nonnegative PI request, observing sensor/monitor evidence only."""
    def __init__(self, config: PressureConfig, calibration: CalibrationEvidence):
        self.config = config
        self.calibration = calibration
        self.integral = 0.0
        self.previous_fraction = 0.0
        self.fault_started_s: float | None = None
        self.fault_fraction = 0.0
        self.last_sequence = -1
        self.reason = "observe"

    def update(self, now_s: float, observation: PressureObservation | None,
               measured_delivery: DeliveryMonitorObservation | None) -> float:
        config = self.config
        if not self.calibration.qualified:
            self.previous_fraction = 0
            self.reason = "response_unqualified:" + self.calibration.reason
            return 0.0
        delivery_ok = measured_delivery is not None and measured_delivery.qualified \
            and measured_delivery.measured_fraction is not None
        fresh = observation is not None and observation.fresh(now_s, config.freshness_limit_s)
        if not delivery_ok:
            self.integral = 0
            self.previous_fraction = 0
            self.reason = "delivery_unqualified"
            return 0.0
        if not fresh:
            if self.fault_started_s is None:
                self.fault_started_s, self.fault_fraction = now_s, self.previous_fraction
            age = now_s - self.fault_started_s
            self.integral = 0
            if config.fallback == "finite_hold":
                fraction = self.fault_fraction if age < config.finite_hold_s else 0
            elif config.fallback == "ramp":
                fraction = max(0, self.fault_fraction - config.ramp_fraction_per_s * age)
            else:
                fraction = 0
            self.reason = "sensor_fault:" + config.fallback
            self.previous_fraction = fraction
            return fraction
        self.fault_started_s = None
        if observation.sbp_pa > config.target_pa + 5 * PA_PER_MMHG:
            self.integral = 0
            self.previous_fraction = 0
            self.reason = "high_pressure:no_independent_lowering_authority"
            return 0.0
        # Repeated 4Hz decisions on a 1Hz beat do not integrate that beat four times.
        error = config.target_pa - observation.sbp_pa
        gain = max(self.calibration.gain_pa_per_fraction, config.minimum_gain_pa)
        if observation.sequence != self.last_sequence:
            next_integral = self.integral + 0.025 * error / gain
            raw = 0.55 * error / gain + next_integral
            if not (raw >= config.maximum_fraction and error > 0) and not (raw <= 0 and error < 0):
                self.integral = next_integral
            self.last_sequence = observation.sequence
        desired = float(np.clip(0.55 * error / gain + self.integral, 0, config.maximum_fraction))
        requested = min(desired, self.previous_fraction + config.rise_slew_fraction_per_s * config.policy_period_s)
        self.reason = "pressor_feedback" if error > 0 else "withdraw_added_pressor_drive"
        self.previous_fraction = requested
        return requested


def _calibration_request(time_s: float) -> float:
    if 20 <= time_s < 50:
        return 0.20
    if 64 <= time_s < 98:
        return 0.40
    return 0.0


def _default_delivery(requested_fraction: float, time_s: float) -> DeliveryEvidence:
    del time_s
    return DeliveryEvidence(0.95 * requested_fraction, 0.94 * requested_fraction,
                            0.03 * requested_fraction)


class TimestampedPressureBody:
    """Evaluator-only delayed-dose events on their exact physical timestamps.

    This optional numerical path preserves the declared cascade equations and
    release-hold rule. It never rounds a dose onset, release expiry or gain
    change to the body integration grid. The legacy aligned-grid baseline is
    retained separately by ``run_study(exact_events=False)``.
    """

    def __init__(self, scenario: PressureScenario):
        self.scenario = scenario
        self.time_s = 0.0
        self.activation = 0.0
        self.added_pressure = 0.0
        self.delayed_fraction = 0.0
        self.last_scheduled_fraction = 0.0
        self.falling = False
        self.release_until_s = -1.0
        self.pending: deque[tuple[float, float]] = deque()
        self.applied_events: list[tuple[float, float]] = []

    def schedule_dose(self, command_time_s: float, fraction: float) -> None:
        if not (math.isfinite(command_time_s) and math.isfinite(fraction)
                and command_time_s >= self.time_s - 1e-10 and 0 <= fraction <= 1):
            raise ValueError("dose event must be a finite present/future command")
        if fraction == self.last_scheduled_fraction:
            return
        timestamp = command_time_s + self.scenario.onset_delay_s
        if self.pending and timestamp < self.pending[-1][0]:
            raise ValueError("delayed dose events must be chronological")
        self.pending.append((timestamp, fraction))
        self.last_scheduled_fraction = fraction

    def _apply_ready_events(self) -> None:
        while self.pending and self.pending[0][0] <= self.time_s + 1e-12:
            timestamp, fraction = self.pending.popleft()
            if fraction < self.delayed_fraction - 1e-12 and not self.falling:
                self.falling = True
                self.release_until_s = timestamp + self.scenario.release_delay_s
            elif fraction > self.delayed_fraction + 1e-12:
                self.falling = False
            self.delayed_fraction = fraction
            self.applied_events.append((timestamp, fraction))

    def advance(self, end_s: float) -> None:
        """Advance at most one numerical step, splitting all interior events."""
        if not math.isfinite(end_s) or end_s < self.time_s - 1e-12:
            raise ValueError("body time cannot reverse")
        scenario = self.scenario
        while self.time_s < end_s - 1e-13:
            self._apply_ready_events()
            boundary = end_s
            if self.pending:
                boundary = min(boundary, self.pending[0][0])
            if self.falling and self.release_until_s > self.time_s + 1e-12:
                boundary = min(boundary, self.release_until_s)
            if scenario.changed_gain_pa is not None and scenario.change_time_s > self.time_s + 1e-12:
                boundary = min(boundary, scenario.change_time_s)
            duration = boundary - self.time_s
            recruited = max(0.0, self.delayed_fraction - scenario.recruitment_threshold) / (
                1 - scenario.recruitment_threshold)
            if self.falling and self.time_s < self.release_until_s - 1e-12:
                recruited = max(recruited, self.activation)
            gain = scenario.gain_pa
            if scenario.changed_gain_pa is not None and self.time_s >= scenario.change_time_s - 1e-12:
                gain = scenario.changed_gain_pa
            self.activation += (recruited - self.activation) * (
                -math.expm1(-duration / scenario.activation_tau_s))
            self.added_pressure += (gain * self.activation - self.added_pressure) * (
                -math.expm1(-duration / scenario.response_tau_s))
            self.time_s = boundary
        self._apply_ready_events()


def run_study(seed: int = 0, scenario: str | PressureScenario = "nominal", mode: str = "feedback",
              delivery: Callable[[float, float], DeliveryEvidence | Mapping] | None = None,
              config: PressureConfig | None = None, *, exact_events: bool = False) -> dict:
    """Run one paired reproducible model; returned arrays contain evaluator truth.

Modes feedback/off share the identical calibration exposure and all random
draws. Oracle reads hidden current pressure and gain only in its diagnostic
request branch, and is explicitly excluded from operational benefit claims.
"""
    config = config or PressureConfig()
    config.validate()
    if isinstance(scenario, str):
        scenario = default_scenarios()[scenario]
    if mode not in {"feedback", "off", "oracle"}:
        raise ValueError("mode must be feedback, off or diagnostic oracle")
    if not (0.5 <= scenario.activation_tau_s <= 10 and 1 <= scenario.response_tau_s <= 30
            and 0.1 <= scenario.onset_delay_s <= 10 and 0.1 <= scenario.release_delay_s <= 60
            and -20 * PA_PER_MMHG <= scenario.gain_pa <= 60 * PA_PER_MMHG
            and 0 <= scenario.recruitment_threshold < 1 and scenario.sensor_delay_s >= 0):
        raise ValueError("plant outside declared Stage 2 synthetic envelope")
    rng = np.random.default_rng(seed)
    deliver = delivery or _default_delivery
    dt = config.integration_step_s
    n = int(round(config.duration_s / dt)) + 1
    sensor_every = int(round(1 / config.waveform_sample_hz / dt))
    extract_every = int(round(config.extraction_period_s / dt))
    policy_every = int(round(config.policy_period_s / dt))
    onset_steps = max(1, int(round(scenario.onset_delay_s / dt)))
    dose_queue = deque([0.0] * onset_steps, maxlen=onset_steps)
    activation = 0.0
    added_pressure = 0.0
    release_until = -1.0
    falling = False
    last_delayed = 0.0
    timestamped_body = TimestampedPressureBody(scenario) if exact_events else None
    fraction = 0.0
    evidence = DeliveryEvidence(0, 0)
    latest_observation = None
    incoming: deque[PressureObservation] = deque()
    observation_history = []
    dose_history = []
    all_records = []
    waveform = []
    last_good_record = None
    calibration = None
    controller = None
    trace = {key: [] for key in (
        "time_s", "true_sbp_pa", "baseline_disturbance_pa", "observed_sbp_pa",
        "observation_peak_s", "observation_support_start_s", "observation_support_end_s",
        "observation_arrival_s", "observation_age_bound_s", "observation_fresh",
        "requested_fraction", "admitted_fraction", "admitted_reference_frames",
        "actual_delivered_fraction", "measured_delivered_fraction",
        "delivery_uncertainty_fraction", "delivery_qualified", "activation_truth",
        "added_pressure_truth_pa", "controller_reason", "synthetic_spinal_contact_v",
        "neural_recording_quality", "neural_archive_validity"
    )}
    reason = "calibration"
    for step in range(n):
        time_s = step * dt
        disturbance_fraction = float(np.clip((time_s - config.disturbance_start_s) / 5, 0, 1)
                                     - np.clip((time_s - config.disturbance_end_s) / 5, 0, 1))
        ambient = scenario.baseline_pa - scenario.disturbance_pa * disturbance_fraction
        gain = scenario.gain_pa
        if scenario.changed_gain_pa is not None and time_s >= scenario.change_time_s:
            gain = scenario.changed_gain_pa
        true_pressure = ambient + added_pressure
        if step % sensor_every == 0:
            # Explicit synthetic 1Hz cardiac waveform; the peak is SBP, not MAP.
            phase = 2 * math.pi * (time_s + 0.25)
            cardiac = 40 * PA_PER_MMHG * (1 - math.cos(phase)) / 2
            sample = true_pressure - cardiac + scenario.sensor_bias_pa + rng.normal(0, config.sensor_noise_pa)
            waveform.append((time_s, float(sample)))
        if step and step % extract_every == 0:
            window = waveform[-config.waveform_sample_hz:]
            peak_index = int(np.argmax([value for _, value in window]))
            peak_time, peak = window[peak_index]
            valid = scenario.invalid_interval_s is None or not (
                scenario.invalid_interval_s[0] <= time_s < scenario.invalid_interval_s[1])
            record = PressureObservation(peak, time_s - config.extraction_period_s, time_s,
                                         peak_time, time_s + scenario.sensor_delay_s,
                                         step // extract_every, valid)
            replaying = scenario.stale_replay_interval_s is not None and (
                scenario.stale_replay_interval_s[0] <= time_s < scenario.stale_replay_interval_s[1])
            if replaying and last_good_record is not None:
                # New packet arrival/sequence never changes old physical peak/support.
                record = replace(last_good_record, arrival_s=time_s + scenario.sensor_delay_s,
                                 sequence=step // extract_every)
            else:
                last_good_record = record
            dropping = scenario.dropout_interval_s is not None and (
                scenario.dropout_interval_s[0] <= time_s < scenario.dropout_interval_s[1])
            all_records.append({**asdict(record), "transported": not dropping, "stale_replay": replaying})
            if not dropping:
                incoming.append(record)
        while incoming and incoming[0].arrival_s <= time_s + 1e-9:
            candidate = incoming.popleft()
            if latest_observation is None or candidate.sequence > latest_observation.sequence:
                latest_observation = candidate
                if candidate.arrival_s <= config.calibration_end_s:
                    observation_history.append(candidate)
        if step % policy_every == 0:
            if time_s < config.calibration_end_s:
                fraction = _calibration_request(time_s)
                reason = "bounded_calibration_protocol"
                calibration_fresh = latest_observation is not None and latest_observation.fresh(
                    time_s, config.freshness_limit_s)
                if not calibration_fresh or not evidence.qualified or evidence.measured_fraction is None:
                    fraction = 0.0
                    reason = "calibration_sensor_or_monitor_gate"
            else:
                if calibration is None:
                    calibration = identify_response(observation_history, dose_history, config)
                    controller = PressureController(config, calibration)
                if mode == "off":
                    fraction, reason = 0.0, "off_after_equal_calibration"
                elif mode == "oracle":
                    # Deliberately privileged diagnostic; no sensor/plant access elsewhere.
                    fraction = float(np.clip((config.target_pa - ambient) / gain, 0, 1)) if gain > 0 else 0
                    reason = "DIAGNOSTIC_ORACLE:uses_hidden_ambient_and_gain"
                else:
                    fraction = controller.update(time_s, latest_observation, evidence.controller_view())
                    reason = controller.reason
            # 120Hz x .25s = 30 complete frames. Keep all three profiles in each
            # admitted frame; thinning never creates a catch-up or rephasing burst.
            admitted_frames = int(math.floor(30 * fraction + 1e-12))
            admitted_fraction = admitted_frames / 30
            evidence = DeliveryEvidence.from_value(deliver(admitted_fraction, time_s))
            dose_history.append((time_s, evidence.measured_fraction if evidence.qualified else None,
                                 evidence.uncertainty_fraction))
            fresh = latest_observation is not None and latest_observation.fresh(time_s, config.freshness_limit_s)
            row = {
                "time_s": time_s, "true_sbp_pa": true_pressure, "baseline_disturbance_pa": ambient,
                "observed_sbp_pa": None if latest_observation is None else latest_observation.sbp_pa,
                "observation_peak_s": None if latest_observation is None else latest_observation.peak_time_s,
                "observation_support_start_s": None if latest_observation is None else latest_observation.support_start_s,
                "observation_support_end_s": None if latest_observation is None else latest_observation.support_end_s,
                "observation_arrival_s": None if latest_observation is None else latest_observation.arrival_s,
                "observation_age_bound_s": None if latest_observation is None else latest_observation.age_bound_s(time_s),
                "observation_fresh": fresh, "requested_fraction": fraction,
                "admitted_fraction": admitted_fraction, "admitted_reference_frames": admitted_frames,
                "actual_delivered_fraction": evidence.effective_fraction,
                "measured_delivered_fraction": evidence.measured_fraction,
                "delivery_uncertainty_fraction": evidence.uncertainty_fraction,
                "delivery_qualified": evidence.qualified, "activation_truth": activation,
                "added_pressure_truth_pa": added_pressure, "controller_reason": reason,
                # Forward source witness only: no validated neural-pressure readout.
                "synthetic_spinal_contact_v": 10e-6 * math.sin(2 * math.pi * 23 * time_s)
                    + (0.01 if evidence.effective_fraction > 0 else 0),
                "neural_recording_quality": "DENSE_TRAIN_UNQUALIFIED" if evidence.effective_fraction > 0
                    else "SYNTHETIC_UNUSED",
                "neural_archive_validity": "INVALID_CONSERVATIVE_ACTIVE_BLOCK" if evidence.effective_fraction > 0
                    else "UNUSED_NO_DECODER",
            }
            for key, value in row.items():
                trace[key].append(value)
        if timestamped_body is not None:
            timestamped_body.schedule_dose(time_s, evidence.effective_fraction)
            if step < n - 1:
                timestamped_body.advance(time_s + dt)
            activation = timestamped_body.activation
            added_pressure = timestamped_body.added_pressure
            continue
        delayed = dose_queue[0]
        dose_queue.append(evidence.effective_fraction)
        if delayed < last_delayed - 1e-12 and not falling:
            falling = True
            release_until = time_s + scenario.release_delay_s
        elif delayed > last_delayed + 1e-12:
            falling = False
        recruited = max(0.0, delayed - scenario.recruitment_threshold) / (1 - scenario.recruitment_threshold)
        if falling and time_s < release_until:
            recruited = max(recruited, activation)
        activation += (recruited - activation) * (-math.expm1(-dt / scenario.activation_tau_s))
        added_pressure += (gain * activation - added_pressure) * (-math.expm1(-dt / scenario.response_tau_s))
        last_delayed = delayed
    t = np.asarray(trace["time_s"])
    p = np.asarray(trace["true_sbp_pa"])
    actual = np.asarray(trace["actual_delivered_fraction"])
    # Final endpoint is a state sample, not another250ms exposure interval.
    evaluation = (t >= config.disturbance_start_s) & (t < config.duration_s)
    disturbance_mask = (t >= config.disturbance_start_s) & (t < config.disturbance_end_s)
    recovery = (t >= config.disturbance_end_s) & (t < config.duration_s)
    error = p - config.target_pa
    freshness = np.asarray(trace["observation_fresh"], dtype=bool)
    reasons = trace["controller_reason"]
    fallback_mask = np.array(["sensor_fault" in reason for reason in reasons]) & evaluation
    result = {
        "schema": "scci_rh.stage3.pressure-study.v1",
        "metadata": {"seed": seed, "scenario": asdict(scenario), "mode": mode,
                     "config": asdict(config), "pressure_unit": "Pa", "display_pa_per_mmhg": PA_PER_MMHG,
                     "delivery_boundary": "caller_electrical_evidence" if delivery else "chosen_reference_surrogate",
                     "oracle_excluded_from_claims": mode == "oracle",
                     "neural_input_to_controller": False,
                     "electrical_reference": {"profile_count": 3, "physical_source": 0,
                       "per_profile_hz": 120, "offsets_s": [0, .002, .004], "current_a": .003,
                       "phase_width_s": .0003, "interphase_s": .0001, "zero_current_rearm_s": .00025},
                     "frame_admission": "floor(30*request)/30 per250ms; all3profiles retained in each wholeframe",
                     "dose_reduction": "averaged monitored reference-train cathodic charge; recruitment is an assumption"},
        "calibration": asdict(calibration),
        "summary": {
            "evaluation_rmse_pa": float(np.sqrt(np.mean(error[evaluation] ** 2))),
            "disturbance_rmse_pa": float(np.sqrt(np.mean(error[disturbance_mask] ** 2))),
            "disturbance_min_sbp_pa": float(np.min(p[disturbance_mask])),
            "recovery_peak_sbp_pa": float(np.max(p[recovery])),
            "overshoot_above_target_pa": float(max(0, np.max(error[evaluation]))),
            "fraction_time_within_5mmhg": float(np.mean(np.abs(error[evaluation]) <= 5 * PA_PER_MMHG)),
            "delivered_train_equivalent_s": float(np.sum(actual[evaluation]) * config.policy_period_s),
            "sensor_unqualified_time_s": float(np.sum(~freshness[evaluation]) * config.policy_period_s),
            "fallback_time_s": float(sum("sensor_fault" in r for i, r in enumerate(reasons) if evaluation[i])
                                     * config.policy_period_s),
            "fallback_min_sbp_pa": float(np.min(p[fallback_mask])) if np.any(fallback_mask) else None,
            "fallback_peak_sbp_pa": float(np.max(p[fallback_mask])) if np.any(fallback_mask) else None,
            "fallback_delivered_train_equivalent_s": float(np.sum(actual[fallback_mask]) * config.policy_period_s),
            "response_unqualified": not calibration.qualified,
            "high_pressure_no_lowering_time_s": float(sum("no_independent_lowering" in r for i, r in enumerate(reasons)
                                                         if evaluation[i]) * config.policy_period_s),
            "support_remaining_after_command_zero": any(actual[i] == 0 and trace["added_pressure_truth_pa"][i] > 5 * PA_PER_MMHG
                                                        for i in range(len(t)) if evaluation[i]),
        },
        "trace": trace,
        "external_observation_records": all_records,
    }
    if timestamped_body is not None:
        result["metadata"]["body_event_timing"] = "exact_timestamped_onset_release_gain_events"
        result["body_event_witness"] = {
            "declared_onset_delay_s": scenario.onset_delay_s,
            "declared_release_delay_s": scenario.release_delay_s,
            "onset_rounding_error_s": 0.0,
            "applied_delayed_dose_events": timestamped_body.applied_events,
            "gain_change_s": scenario.change_time_s if scenario.changed_gain_pa is not None else None,
            "pending_after_final_endpoint": list(timestamped_body.pending),
        }
    return result


def run_batch(seeds: tuple[int, ...] = (0, 1, 2), scenarios: tuple[str, ...] | None = None,
              delivery=None, config: PressureConfig | None = None) -> list[dict]:
    """Paired modes per seed; returned results preserve null/adverse scenarios."""
    names = scenarios or tuple(default_scenarios())
    return [run_study(seed, name, mode, delivery, config)
            for name in names for seed in seeds for mode in ("off", "feedback", "oracle")]
