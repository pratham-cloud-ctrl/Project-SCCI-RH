"""Stage 3's observable, paired, synthetic foot-placement mechanism study.

This module separates the simulator-owned learner from observer/decoder/policy
records. It is a chosen reduced motor and plasticity model, not human evidence.
No controller receives learner coefficients, true recruitment or future state.
"""
from collections import deque
from dataclasses import asdict, dataclass, replace
from typing import Callable
import numpy as np
from .acquisition import AcquisitionConfig, ContactAcquisition, NeuralFeatures, artifact_coverage
from .external_history import fit_external_history, CausalExternalHistoryDecoder

FAMILIES = ("favorable", "zero", "harmful", "dependent")
CONDITIONS = ("observe_only", "external__learner_only", "external__expert_external",
              "external__expert_neural", "neural_external__learner_only",
              "neural_external__expert_external", "neural_external__expert_neural")
EXTERNAL_HISTORY_CONDITIONS = tuple("external_history__"+representation
                                    for representation in ("learner_only", "expert_external", "expert_neural"))


@dataclass(frozen=True)
class MotorConfig:
    dt_s: float = .005
    # Decision/acquisition time stays fixed. This is solely the private body's
    # maximum integration interval, not an extra measurement or policy tick.
    body_integration_step_s: float = .005
    body_integration_method: str = "legacy_endpoint"
    event_spacing_s: float = .5
    foot_amplitude_m: float = .10
    practice_blocks: int = 4
    practice_block_s: float = 3.0
    calibration_s: float = 12.0
    probe_s: float = 1.25
    assessment_s: float = 3.0
    pipeline_delay_s: float = .01185
    external_delay_s: float = .020
    external_noise_m: float = .0015
    external_freshness_s: float = .050
    controller_position_uncertainty_limit_m: float = .025
    motor_onset_delay_s: float = .035
    motor_activation_tau_s: float = .040
    movement_tau_s: float = .060
    nominal_gain_m: float = .060
    recruitment_threshold_fraction: float = .12
    sensory_interference_fraction: float = .15
    learning_step: float = .050
    stimulation_teaching_fraction: float = .30
    forgetting_fraction: float = .02
    retention_spatial_threshold_m: float = .018
    retention_timing_threshold_s: float = .025
    nominal_current_A: float = .003
    phase_s: float = .0002
    boost_V: float = 24.
    pulse_hz: float = 40.
    maximum_prediction_horizon_s: float = .100
    source_mode: str = "informative"
    biological_variant: str = "nominal"  # nominal/no_authority/cross_route_adverse
    heldout_gain_fraction: float = .65
    heldout_cross_coupling: float = .40
    save_trace_condition: str = "neural_external__expert_neural"
    acquisition_qualification_mode: str = "fixed_history"
    acquisition_clock_uncertainty_s: float = 0.

    def __post_init__(self):
        if self.dt_s != .005 or self.pulse_hz != 40 or self.event_spacing_s != .5:
            raise ValueError("The selected task uses 200 Hz decisions, 40 Hz profiles and 500 ms goals")
        if self.nominal_current_A != .003 or self.phase_s != .0002 or self.boost_V != 24:
            raise ValueError("This study fixes the Stage 2 illustrative motor pulse profile")
        if self.source_mode not in {"informative", "redundant", "absent"}:
            raise ValueError("invalid source mode")
        if self.biological_variant not in {"nominal", "no_authority", "cross_route_adverse"}:
            raise ValueError("invalid biological variant")
        if self.calibration_s < 3 or self.practice_blocks < 1 or self.practice_block_s < 1:
            raise ValueError("insufficient declared observation/practice exposure")
        if min(self.motor_activation_tau_s, self.movement_tau_s, self.probe_s) <= 0:
            raise ValueError("time constants and probe duration must be positive")
        step = self.body_integration_step_s
        if (not np.isfinite(step) or step <= 0 or step > self.dt_s
                or not np.isclose(self.dt_s/step, round(self.dt_s/step), rtol=0, atol=1e-10)):
            raise ValueError("body integration step must divide the fixed 5 ms decision interval")
        if self.body_integration_method not in {"legacy_endpoint", "midpoint_exact_cascade"}:
            raise ValueError("unknown private body integration method")
        if not np.isfinite(self.motor_onset_delay_s) or self.motor_onset_delay_s < 0:
            raise ValueError("motor onset delay must be finite and nonnegative")
        if (not np.isfinite(self.external_delay_s) or self.external_delay_s < 0
                or not np.isclose(self.external_delay_s/self.dt_s,
                                  round(self.external_delay_s/self.dt_s), rtol=0, atol=1e-10)):
            raise ValueError("external delay must remain on the fixed 5 ms measurement clock")
        if self.acquisition_qualification_mode not in {"fixed_history", "bounded_residual"}:
            raise ValueError("unknown acquisition qualification mode")
        if not np.isfinite(self.acquisition_clock_uncertainty_s) or self.acquisition_clock_uncertainty_s < 0:
            raise ValueError("finite nonnegative acquisition clock allowance required")


@dataclass(frozen=True)
class Observation:
    """The only online controller input from the world (units and support explicit)."""
    available_time_s: float
    external_position_m: tuple[float, float]
    external_measurement_time_s: float
    external_valid: bool
    neural: NeuralFeatures


@dataclass(frozen=True)
class StateEstimate:
    position_m: tuple[float, float]
    velocity_m_per_s: tuple[float, float]
    support_time_s: float
    uncertainty_m: float
    valid: bool
    source: str
    reason: str


@dataclass(frozen=True)
class LearnerMap:
    gain_m: tuple[tuple[float, float], tuple[float, float]]
    gain_uncertainty_m: tuple[tuple[float, float], tuple[float, float]]
    onset_delay_s: float
    onset_uncertainty_s: float
    qualified: bool
    rejected_routes: tuple[str, ...]
    calibration_pulses: int
    measured_dose_mean_fraction: float
    route_consistency_rmse_m: float
    heldout_response_rmse_m: float = 1.


@dataclass(frozen=True)
class ExpertRepresentation:
    kind: str
    coefficients_m: tuple[tuple[float, ...], tuple[float, ...]]
    reference_fit_rmse_m: float | None
    label_source: str
    training_subject: str
    training_seconds: float
    qualified: bool = True
    qualification_reason: str = "AVAILABLE_DECLARED_TASK_REFERENCE"


class _World:
    """Simulator only: internal adaptation/recruitment never enters Observation."""
    def __init__(self, seed, c, *, heldout=False):
        rng = np.random.default_rng(seed)
        self.c = c
        self.x = np.zeros(2)
        self.v = np.zeros(2)
        self.activation = np.zeros(2)
        self.theta = np.array([[rng.uniform(.055, .070), rng.uniform(-.025, -.015), 0., 0.],
                               [rng.uniform(-.070, -.055), rng.uniform(.015, .025), 0., 0.]])
        g = c.nominal_gain_m * rng.uniform(.8, 1.2, 2)
        cross = rng.uniform(.08, .22)
        self.recruitment = np.array([[g[0], cross*g[1]], [cross*g[0], g[1]]])
        if heldout:
            self.recruitment *= c.heldout_gain_fraction
            self.recruitment[0, 1] = c.heldout_cross_coupling * self.recruitment[1, 1]
            self.recruitment[1, 0] = -c.heldout_cross_coupling * self.recruitment[0, 0]
        if c.biological_variant == "no_authority":
            self.recruitment *= 0
        self.negative_route_sign = -1. if c.biological_variant == "nominal" else 1.
        if c.biological_variant == "no_authority":
            self.negative_route_sign = -1.
        # Timestamped changes, rather than a body-step deque. A command held
        # from block start s becomes biological input at s + onset_delay_s.
        # Non-grid-aligned transitions split a private body step exactly.
        self._drive_events = deque()
        self._delayed_drive = np.zeros(2)
        self._last_interval_end_s = None
        self.integration_substeps = 0
        self.delay_transitions = []
        self.last_voluntary = np.zeros(2)
        self.last_stim_effect = np.zeros(2)

    def advance(self, t, signed_true_dose, family, *, learning, rest=False, heldout=False):
        """Advance one fixed decision interval, preserving its source velocity.

        ``t`` is the interval's right endpoint, matching the foundation API.
        The source used in the next acquisition block is the displacement over
        this entire 5 ms interval, not the velocity of its final fine substep.
        """
        c = self.c
        start = t-c.dt_s
        if not np.isfinite(t) or (self._last_interval_end_s is not None
                and abs(start-self._last_interval_end_s) > 1e-10):
            raise ValueError("body intervals must be finite and contiguous on the decision clock")
        drive = np.array(signed_true_dose, dtype=float)
        if drive.shape != (2,) or not np.all(np.isfinite(drive)):
            raise ValueError("body dose must have two finite components")
        # Fixed pulse charge can fail a recruitment threshold entirely. This
        # artificial threshold does not infer biological effect from command.
        active = np.abs(drive) > c.recruitment_threshold_fraction
        drive = np.sign(drive)*np.maximum(0, np.abs(drive)-c.recruitment_threshold_fraction) * active
        drive = np.where(drive < 0, -self.negative_route_sign*drive, drive)
        self._drive_events.append((start+c.motor_onset_delay_s, drive))
        old_x = self.x.copy()
        pieces = int(round(c.dt_s/c.body_integration_step_s))
        cursor = start
        for index in range(pieces):
            endpoint = t if index == pieces-1 else start+(index+1)*c.body_integration_step_s
            while cursor < endpoint-1e-13:
                while self._drive_events and self._drive_events[0][0] <= cursor+1e-12:
                    when, self._delayed_drive = self._drive_events.popleft()
                    self.delay_transitions.append(float(when))
                stop = endpoint
                if self._drive_events and cursor+1e-12 < self._drive_events[0][0] < stop-1e-12:
                    stop = self._drive_events[0][0]
                # Known direction changes are forcing discontinuities. At an
                # exact endpoint the right-end convention remains the historic
                # one; the closed-form/ODE reference discloses that endpoint
                # quadrature error rather than erasing it from the baseline.
                direction_change = (np.floor(cursor/2)+1)*2
                if cursor+1e-12 < direction_change < stop-1e-12:
                    stop = direction_change
                h = c.dt_s if pieces == 1 and stop == t and cursor == start else stop-cursor
                self._advance_piece(stop, h, family, learning=learning, rest=rest, heldout=heldout)
                cursor = stop
        self._last_interval_end_s = t
        self.v = (self.x-old_x)/c.dt_s

    def _advance_piece(self, t, h, family, *, learning, rest, heldout):
        c = self.c
        if c.body_integration_method == "midpoint_exact_cascade":
            self._advance_midpoint(t-h, h, family, learning=learning, rest=rest, heldout=heldout)
            return
        phi = task_basis(t, heldout=heldout)
        desired = task_goal(t, c, heldout=heldout)
        voluntary = np.zeros(2) if rest else self.theta @ phi
        self.activation += (1-np.exp(-h/c.motor_activation_tau_s))*(self._delayed_drive-self.activation)
        stim_effect = self.recruitment @ self.activation
        self.x += (1-np.exp(-h/c.movement_tau_s))*(voluntary+stim_effect-self.x)
        self.integration_substeps += 1
        self.last_voluntary = voluntary
        self.last_stim_effect = stim_effect
        if learning and not rest:
            # All families share ordinary practice; the distinct causal coupling
            # terms are structural hypotheses, never a chosen speed-up factor.
            native_error = desired-voluntary
            sensory_error = desired-self.x
            if family == "zero":
                error = native_error
            elif family == "favorable":
                error = native_error + c.stimulation_teaching_fraction*stim_effect
            elif family == "harmful":
                error = sensory_error - c.sensory_interference_fraction*stim_effect
            elif family == "dependent":
                error = sensory_error
            else:
                raise ValueError("unknown learning family")
            self.theta += c.learning_step*h * np.outer(error, phi)

    def _advance_midpoint(self, start, h, family, *, learning, rest, heldout):
        """Second-order forcing/plasticity, exact held-input activation cascade.

        Delay and direction events have already split this interval. Midpoint
        forcing never applies a new direction over time preceding its event.
        The coarse legacy scheme remains a separate reproducible option.
        """
        c = self.c
        drive = self._delayed_drive
        initial_activation = self.activation.copy()
        initial_position = self.x.copy()
        initial_theta = self.theta.copy()

        def cascade(duration, voluntary):
            ea = np.exp(-duration/c.motor_activation_tau_s)
            ex = np.exp(-duration/c.movement_tau_s)
            if abs(c.motor_activation_tau_s-c.movement_tau_s) < 1e-14:
                coupled = duration/c.movement_tau_s*ex
            else:
                coupled = c.motor_activation_tau_s/(c.motor_activation_tau_s-c.movement_tau_s)*(ea-ex)
            activation = drive+(initial_activation-drive)*ea
            position = (initial_position*ex+(voluntary+self.recruitment@drive)*(1-ex)
                        +(self.recruitment@(initial_activation-drive))*coupled)
            return activation, position

        def rate(time, theta, position, activation):
            phi = task_basis(time, heldout=heldout)
            voluntary = np.zeros(2) if rest else theta@phi
            if not learning or rest:
                return np.zeros((2, 4))
            desired = task_goal(time, c, heldout=heldout)
            stimulation = self.recruitment@activation
            if family == "zero": error = desired-voluntary
            elif family == "favorable": error = desired-voluntary+c.stimulation_teaching_fraction*stimulation
            elif family == "harmful": error = desired-position-c.sensory_interference_fraction*stimulation
            elif family == "dependent": error = desired-position
            else: raise ValueError("unknown learning family")
            return c.learning_step*np.outer(error, phi)

        voluntary_start = np.zeros(2) if rest else initial_theta@task_basis(start, heldout=heldout)
        midpoint_activation, midpoint_position = cascade(h/2, voluntary_start)
        midpoint_theta = initial_theta+h/2*rate(start, initial_theta, initial_position, initial_activation)
        midpoint = start+h/2
        voluntary_midpoint = np.zeros(2) if rest else midpoint_theta@task_basis(midpoint, heldout=heldout)
        self.activation, self.x = cascade(h, voluntary_midpoint)
        self.theta = initial_theta+h*rate(midpoint, midpoint_theta, midpoint_position, midpoint_activation)
        self.integration_substeps += 1
        self.last_voluntary = voluntary_midpoint
        self.last_stim_effect = self.recruitment@self.activation


def _pulse_frame(t, c):
    """Frame membership belongs to physical decision time, never body substeps."""
    cycles = t*c.pulse_hz
    return abs(cycles-round(cycles)) < 1e-10


def task_basis(t, heldout=False):
    # Known task instructions include the direction changes, not actual motion.
    omega = 2*np.pi*(1.15 if heldout else 1.)
    direction = 1 if (int(t // 2) % 2 == 0) else -1
    return direction*np.array([np.sin(omega*t), np.cos(omega*t),
                                np.sin(3*omega*t), np.cos(3*omega*t)])


def task_goal(t, c, heldout=False):
    return c.foot_amplitude_m * np.array([1., -1.]) * task_basis(t, heldout)[0]


def _assumed_delivery(request):
    """Unqualified fallback for unit studies only; no electrical proof is claimed."""
    q = request["command_current_A"]*request["phase_s"]
    return {"true_phase_charge_C": q, "delivered_phase_charge_C": q*1.012,
            "charge_uncertainty_C": q*.074, "quality": "ASSUMED_NOMINAL",
            "electrical_evidence": {"reason": "NO_ELECTRICAL_ADAPTER"}}


def _pulse(t, source, sign, delivery, c):
    request = {"time_s": float(t), "source_id": int(source),
               "command_current_A": c.nominal_current_A, "current_A": c.nominal_current_A,
               "phase_s": c.phase_s, "boost_V": c.boost_V,
               "profile_id": "motor_left" if source == 0 else "motor_right",
               "contact_route": f"foot_{source}_{'positive' if sign > 0 else 'negative'}",
               "return_id": int(source)}
    result = delivery(request)
    required = ("true_phase_charge_C", "delivered_phase_charge_C", "charge_uncertainty_C", "quality")
    if any(k not in result for k in required):
        raise ValueError("Delivery evidence missing a required independent-monitor/body field")
    if not all(np.isfinite(result[k]) and result[k] >= 0 for k in required[:3]):
        raise ValueError("Delivery charge/uncertainty must be finite and nonnegative")
    nominal = c.nominal_current_A*c.phase_s
    # A post-delivery failure cannot undo an already delivered pulse. Only the
    # monitor's qualified evidence is usable for identification/admission.
    truth = sign*result["true_phase_charge_C"]/nominal
    measured = (sign*result["delivered_phase_charge_C"]/nominal
                if result["quality"] in {"VALID", "ASSUMED_NOMINAL"} else 0.)
    # Only a sanitized monitor view is allowed to enter the identified map.
    monitor = {"time_s": float(t), "source_id": int(source), "route_sign": int(sign),
               "delivered_phase_charge_C": float(result["delivered_phase_charge_C"]),
               "charge_uncertainty_C": float(result["charge_uncertainty_C"]),
               "quality": str(result["quality"]),
               "inhibit_next": bool(result.get("inhibit_next", False))}
    witness = {**request, **monitor, "true_phase_charge_C": float(result["true_phase_charge_C"]),
               "electrical_evidence": result.get("electrical_evidence", {})}
    return truth, measured, monitor, witness


class CausalDecoder:
    """Local encoder fit uses learner calibration's external observations only."""
    def __init__(self, config, neural_model=None):
        self.config = config
        bundled = neural_model is not None and "external_history" in neural_model
        self.neural_model = neural_model["neural"] if bundled else neural_model
        self.external_history = CausalExternalHistoryDecoder(config, neural_model["external_history"] if bundled else None)
        self._external = deque(maxlen=9)

    def estimate(self, observation: Observation, sensing: str) -> StateEstimate:
        if sensing == "external_history":
            estimate = self.external_history.estimate(observation)
            return StateEstimate(**asdict(estimate))
        c = self.config
        now = observation.available_time_s
        support = observation.external_measurement_time_s
        external = np.asarray(observation.external_position_m, dtype=float)
        if (not np.isfinite(now) or not np.isfinite(support) or external.shape != (2,)
                or not np.all(np.isfinite(external)) or support > now
                or not observation.external_valid or now-support > c.external_freshness_s):
            return StateEstimate((0.,0.), (0.,0.), observation.external_measurement_time_s,
                                 1., False, "NONE", "EXTERNAL_STALE_OR_INVALID")
        if self._external and support < self._external[-1][0]:
            return StateEstimate((0.,0.), (0.,0.), support, 1., False, "NONE", "EXTERNAL_NONMONOTONIC")
        if not self._external or support > self._external[-1][0]:
            self._external.append((support, external))
        rows = list(self._external)
        times = np.array([r[0] for r in rows])
        positions = np.array([r[1] for r in rows])
        time_center = float(np.mean(times))
        centered = times-time_center
        if len(rows) < 3 or np.sum(centered**2) < 1e-12:
            return StateEstimate(tuple(positions[-1]), (0.,0.), times[-1], 1.,
                                 False, "EXTERNAL", "DECODER_WARMUP")
        velocity = (centered @ positions)/np.sum(centered**2)
        position = positions.mean(axis=0) + velocity*(times[-1]-time_center)
        uncertainty = c.external_noise_m*2 + .005
        source = "EXTERNAL"
        reason = "EXTERNAL_ONLY"
        neural = observation.neural
        clock = neural.clock_uncertainty_s
        neural_causal = (np.isfinite(clock) and clock >= 0 and neural.available_time_s <= now
                         and neural.support_end_s+2*clock <= neural.available_time_s
                         and neural.support_start_s <= neural.support_end_s
                         and np.isfinite(neural.available_time_s)
                         and now-neural.support_end_s+clock <= .005)
        if sensing == "neural_external" and neural.valid and neural_causal and self.neural_model is not None:
            m = self.neural_model
            features = np.array(neural.values_uv)
            z = (features-m["mean"])/m["scale"]
            neural_error_budget = 2*m["rmse"]+2*c.maximum_prediction_horizon_s*m["velocity_rmse"]
            if np.all(np.isfinite(z)) and np.max(np.abs(z)) <= 5.0 and neural_error_budget < c.controller_position_uncertainty_limit_m:
                # Predict external-labeled state at the SAME physical support
                # time as external-only, rather than assigning lower latency.
                pred = np.r_[1., z] @ m["weights"]
                neural_position, neural_velocity = pred[:2], pred[2:]
                w = float(np.clip((uncertainty**2)/(uncertainty**2+m["rmse"]**2+1e-8), .0, .85))
                position = (1-w)*position+w*neural_position
                velocity = (1-w)*velocity+w*neural_velocity
                uncertainty = max(neural_error_budget, .003)
                source, reason = "NEURAL_PLUS_SAME_EXTERNAL", "CALIBRATED_NEURAL"
            else:
                reason = "NEURAL_OUT_OF_CALIBRATION_OR_RESIDUAL_LIMIT"
        elif sensing == "neural_external":
            reason = "NEURAL_INVALID_EXTERNAL_FALLBACK"
        return StateEstimate(tuple(float(x) for x in position), tuple(float(x) for x in velocity),
                             float(times[-1]), float(uncertainty),
                             uncertainty <= c.controller_position_uncertainty_limit_m, source, reason)


def _fit_neural(observations, *, heldout_fraction=.25):
    selected = [o for o in observations if o.neural.valid and o.external_valid]
    if len(selected) < 80:
        return None
    x = np.array([o.neural.values_uv for o in selected])
    y = np.array([o.external_position_m for o in selected])
    times = np.array([o.external_measurement_time_s for o in selected])
    # Labels are finite differences of declared external calibration measurements,
    # not simulator velocities or future test labels. Only offline fitting uses
    # central differences; the online decoder is always causal.
    split = int(len(x)*(1-heldout_fraction))
    # Purge 100 ms on both sides: greater than feature overlap + the
    # differentiated label's symmetric support. Label construction is also
    # performed separately inside each retained partition.
    cut_time = times[split]
    train = np.flatnonzero(times < cut_time-.100)
    valid = np.flatnonzero(times > cut_time+.100)
    if len(train) < 40 or len(valid) < 20:
        return None
    targets = np.zeros((len(y), 4))
    for part in (train, valid):
        velocity = np.gradient(y[part], times[part], axis=0)
        smoothed = np.column_stack([np.convolve(velocity[:,j], np.ones(9)/9, mode="same")
                                    for j in range(2)])
        targets[part] = np.column_stack((y[part], smoothed))
    train, valid = train[4:-4], valid[4:-4]
    mean, scale = x[train].mean(axis=0), np.maximum(x[train].std(axis=0), .5)
    z = np.column_stack((np.ones(len(x)), (x-mean)/scale))
    penalty = np.eye(z.shape[1])*.5
    penalty[0,0] = 1e-9
    weights = np.linalg.solve(z[train].T@z[train]+penalty, z[train].T@targets[train])
    residual = z[valid]@weights-targets[valid]
    return {"mean": mean, "scale": scale, "weights": weights,
            "rmse": float(np.sqrt(np.mean(residual[:,:2]**2))),
            "velocity_rmse": float(np.sqrt(np.mean(residual[:,2:]**2))),
            "training_rows": len(train), "heldout_rows": len(valid),
            "purged_split_half_width_s": .100,
            "labels": "same-learner external position + offline differentiated external position"}


def _capture(seed, c, duration, *, rest=False, probe=None, delivery=None, expert=False,
             subject_seed=None):
    subject_seed = seed if subject_seed is None else subject_seed
    world = _World(subject_seed, c)
    if expert:
        world.theta = np.array([[c.foot_amplitude_m, 0., .0, .0],
                                [-c.foot_amplitude_m, 0., .0, .0]])
    acquisition = ContactAcquisition(subject_seed+8300, AcquisitionConfig(source_mode=c.source_mode,
                                      qualification_mode=c.acquisition_qualification_mode,
                                      clock_uncertainty_s=c.acquisition_clock_uncertainty_s),
                                     noise_seed=seed+17001)
    rng = np.random.default_rng(seed+9200)
    n = int(round(duration/c.dt_s))
    delay = int(round(c.external_delay_s/c.dt_s))
    history = deque([np.zeros(2) for _ in range(delay+1)], maxlen=delay+1)
    observations, data, witnesses = [], [], []
    held_true, held_measured = np.zeros(2), np.zeros(2)
    monitor_doses = []
    delivery = delivery or _assumed_delivery
    if hasattr(delivery, "begin_session"):
        delivery.begin_session()
    for k in range(n):
        t = k*c.dt_s
        if _pulse_frame(t, c):
            held_true.fill(0); held_measured.fill(0)
            signed = np.zeros(2) if probe is None else probe(t)
            for j in range(2):
                if signed[j] != 0:
                    truth, measured, monitor, witness = _pulse(t, j, int(np.sign(signed[j])), delivery, c)
                    held_true[j], held_measured[j] = truth, measured
                    monitor_doses.append(abs(measured))
                    witnesses.append(witness)
                    if truth != 0:
                        acquisition.add_artifact(t, c.phase_s)
        # The acquisition block samples the state available at its START.
        # Synthetic sources are zero-order held for 5 ms; x(t+5ms) must not
        # populate samples whose timestamps precede that future state.
        history.append(world.x.copy())
        measured_position = history[0]+rng.normal(0, c.external_noise_m, 2)
        neural = acquisition.observe(t, world.x/c.foot_amplitude_m,
                                     world.v/(2*np.pi*c.foot_amplitude_m),
                                     external_redundant_state=measured_position/c.foot_amplitude_m)
        o = Observation(t+c.dt_s, tuple(measured_position), t-c.external_delay_s,
                        True, neural)
        observations.append(o)
        data.append({"time_s": t+c.dt_s, "external_support_s": o.external_measurement_time_s,
                     "observed_position_m": measured_position.tolist(),
                     "measured_drive": held_measured.copy().tolist(),
                     "simulator_position_m": world.x.copy().tolist()})
        world.advance(t+c.dt_s, held_true, "zero", learning=False, rest=rest)
    return observations, data, witnesses, monitor_doses


def calibrate(seed, config=MotorConfig(), delivery=None, *, include_external_history=False):
    """Fit local decoder and route responses from finite, equal-budget observations."""
    c = config
    obs, _, _, _ = _capture(seed, c, c.calibration_s, delivery=delivery)
    model = _fit_neural(obs)
    external_model = (fit_external_history(obs, external_freshness_s=c.external_freshness_s)
                      if include_external_history else None)
    # Four observed rest/step/release probes; the true map is never queried.
    period = c.probe_s + .75
    def probes(t):
        index = min(3, int(t//period))
        within = t-index*period
        u = np.zeros(2)
        if .25 <= within < .25+c.probe_s:
            u[index//2] = 1 if index%2 == 0 else -1
        return u
    _, probe_data, pulses, dose = _capture(seed, c, 4*period, rest=True, probe=probes, delivery=delivery)
    times = np.array([d["external_support_s"] for d in probe_data])
    positions = np.array([d["observed_position_m"] for d in probe_data])
    gain = np.zeros((2,2)); unc = np.zeros((2,2))
    rejected, onset = [], []
    route_plateaus = []
    nominal_fraction = np.mean(dose) if dose else 0.
    qualified_pulses = [p for p in pulses if p["quality"] in {"VALID", "ASSUMED_NOMINAL"}]
    dose_unc = float(np.mean([p["charge_uncertainty_C"]/(c.nominal_current_A*c.phase_s)
                             for p in qualified_pulses])) if qualified_pulses else 1.
    for index in range(4):
        source, sign = index//2, 1 if index%2 == 0 else -1
        start = index*period+.25
        before = (times >= start-.20)&(times < start)
        steady = (times >= start+c.probe_s-.30)&(times < start+c.probe_s-.05)
        baseline = positions[before].mean(axis=0)
        response = positions[steady].mean(axis=0)-baseline
        response_unc = 3*c.external_noise_m + .005
        route_plateaus.append(response.tolist())
        if sign*response[source] <= response_unc or nominal_fraction < .2:
            rejected.append(f"source_{source}_{'positive' if sign > 0 else 'negative'}")
        # Empirical EFFECTIVE gain at the tested fixed pulse profile. The
        # unknown plant recruitment threshold is never supplied to the fit.
        signed_response = sign*response/max(nominal_fraction, .01)
        gain[:,source] += .5*signed_response
        denominator = max(nominal_fraction-dose_unc, .01)
        unc[:,source] += .5*(response_unc/denominator
                              + np.abs(response)*dose_unc/(max(nominal_fraction,.01)*denominator))
        transient = (times >= start)&(times < start+.5)
        response_series = sign*(positions[transient,source]-baseline[source])
        reached = np.flatnonzero(response_series > max(.003, abs(response[source])*.15))
        if len(reached):
            onset.append(float(times[transient][reached[0]]-start))
    identified_delay = float(np.median(onset)) if onset else .150
    onset_unc = max(.005, float(np.std(onset)) if onset else .150)
    condition = float(np.linalg.cond(gain)) if np.any(gain) else np.inf
    def mixed_probes(t):
        index = min(1, int(t//period))
        within = t-index*period
        return (np.array([1., 1. if index == 0 else -1.])
                if .25 <= within < .25+c.probe_s else np.zeros(2))
    _, validation_data, _, _ = _capture(seed+71000, c, 2*period, rest=True,
                                         probe=mixed_probes, delivery=delivery, subject_seed=seed)
    # Same synthetic subject/lead field, distinct sensor-noise realization and
    # two combinations withheld from the individual-route gain fit.
    validation_times = np.array([d["external_support_s"] for d in validation_data])
    validation_positions = np.array([d["observed_position_m"] for d in validation_data])
    validation_drive = np.array([d["measured_drive"] for d in validation_data])
    validation_residual = []
    for index in range(2):
        start = index*period+.25
        plateau = ((validation_times >= start+c.probe_s-.30)
                   & (validation_times < start+c.probe_s-.05))
        measured_input = validation_drive[plateau].mean(axis=0)
        validation_residual.append(validation_positions[plateau].mean(axis=0)-gain@measured_input)
    heldout_rmse = float(np.sqrt(np.mean(np.square(validation_residual))))
    authority_margin = (float(np.linalg.svd(gain,compute_uv=False)[-1])-float(np.linalg.norm(unc,2)))
    qualified = (not rejected and condition < 10 and authority_margin > 0
                 and heldout_rmse < c.controller_position_uncertainty_limit_m and identified_delay+2*onset_unc
                 <= c.maximum_prediction_horizon_s)
    # These probes also contributed to the gain fit: this is an in-calibration
    # sign/route consistency diagnostic, not independent held-out validation.
    agreement = np.array(route_plateaus)[::2]+np.array(route_plateaus)[1::2]
    response_map = LearnerMap(tuple(tuple(float(v) for v in row) for row in gain),
                             tuple(tuple(float(v) for v in row) for row in unc),
                             identified_delay, onset_unc, bool(qualified), tuple(rejected), len(pulses),
                             float(nominal_fraction), float(np.sqrt(np.mean(agreement**2))), heldout_rmse)
    metadata = {"movement_calibration_s": c.calibration_s,
                                "route_probe_calibration_s": 4*period,
                                "heldout_mixed_route_calibration_s": 2*period,
                                "same_budget_all_conditions": True,
                                "route_plateaus_m": route_plateaus,
                                "measured_dose_uncertainty_fraction": dose_unc,
                                "effective_gain_scope": "tested fixed-profile pulse-density response; no true threshold supplied",
                                "authority_singular_margin_m": authority_margin,
                                "route_validation_scope": "individual-route sign consistency plus separately captured mixed-route response validation at same profile/posture",
                                "monitor_pulses": pulses,
                                "decoder_fit": None if model is None else {
                                    k:v for k,v in model.items() if k not in {"mean","scale","weights"}}}
    if include_external_history:
        metadata["external_history_fit"] = None if external_model is None else {
            k: v for k, v in external_model.items() if k not in {"mean", "scale", "weights"}}
        model = {"neural": model, "external_history": external_model}
    return response_map, model, metadata


def _expert_library(seed, c):
    # The expert has a distinct subject/electrode geometry, its own observed
    # decoder and 12 s offline captures. Coefficients travel in external task
    # coordinates, never electrode-to-electrode voltage copying.
    observations, data, _, _ = _capture(seed+51000, c, 12., expert=True)
    model = _fit_neural(observations)
    selected = [i for i,o in enumerate(observations) if o.neural.valid]
    times = np.array([observations[i].external_measurement_time_s for i in selected])
    phi = np.array([task_basis(t) for t in times])
    external = np.array([observations[i].external_position_m for i in selected])
    coef_ext = np.linalg.lstsq(phi, external, rcond=None)[0].T
    neural_available = model is not None and model["rmse"] < c.controller_position_uncertainty_limit_m
    if neural_available:
        f = np.array([observations[i].neural.values_uv for i in selected])
        z = np.column_stack((np.ones(len(f)), (f-model["mean"])/model["scale"]))
        neural_labels = (z@model["weights"])[:,:2]
        coef_neural = np.linalg.lstsq(phi, neural_labels, rcond=None)[0].T
    else:
        # Unavailable neural evidence remains unavailable; it must never be
        # substituted with external trajectories under an expert-neural label.
        neural_labels = np.zeros_like(external)
        coef_neural = np.zeros((2,4))
    learner_coef = np.array([[c.foot_amplitude_m, 0., 0., 0.],[-c.foot_amplitude_m,0.,0.,0.]])
    lib = {}
    for kind, coefficients, labels, provenance in (
        ("learner_only", learner_coef, external, "declared event goal interpolation; no expert data"),
        ("expert_external", coef_ext, external, "offline expert external trajectories"),
        ("expert_neural", coef_neural, neural_labels,
         "offline expert contact-acquisition features decoded with expert external labels")):
        lib[kind] = ExpertRepresentation(kind, tuple(tuple(float(x) for x in r) for r in coefficients),
                                         (float(np.sqrt(np.mean((phi@coefficients.T-labels)**2)))
                                          if kind != "expert_neural" or neural_available else None),
                                         provenance, "known_task_no_subject" if kind=="learner_only" else "synthetic_expert_distinct_subject",
                                         0. if kind=="learner_only" else 12.,
                                         bool(neural_available) if kind=="expert_neural" else True,
                                         ("CALIBRATED_SEPARATE_EXPERT_NEURAL" if neural_available else "EXPERT_NEURAL_UNAVAILABLE")
                                         if kind=="expert_neural" else "AVAILABLE_DECLARED_OR_EXTERNAL_REFERENCE")
    return lib


def control_request(estimate: StateEstimate, response: LearnerMap,
                    representation: ExpertRepresentation, now_s: float,
                    config: MotorConfig, *, heldout=False):
    """Pure observable policy: no simulator, true phase, skill or true gain input."""
    c = config
    finite = np.r_[estimate.position_m, estimate.velocity_m_per_s, estimate.support_time_s,
                   estimate.uncertainty_m, now_s, np.asarray(response.gain_m).ravel(),
                   np.asarray(response.gain_uncertainty_m).ravel(),
                   np.asarray(representation.coefficients_m).ravel()]
    if (not np.all(np.isfinite(finite)) or estimate.support_time_s > now_s
            or estimate.uncertainty_m < 0 or np.any(np.asarray(response.gain_uncertainty_m)<0)):
        return np.zeros(2), "NONFINITE_OR_FUTURE_INPUT"
    if not estimate.valid:
        return np.zeros(2), "INVALID_STATE"
    if not representation.qualified:
        return np.zeros(2), "UNAVAILABLE_EXPERT_REPRESENTATION"
    if not response.qualified:
        return np.zeros(2), "UNQUALIFIED_LEARNER_MAP"
    # Prediction includes actual external support age, pipeline allocation and
    # calibrated onset uncertainty. A mean delay cannot qualify a long horizon.
    support_age = now_s-estimate.support_time_s
    horizon = support_age+c.pipeline_delay_s+response.onset_delay_s+2*response.onset_uncertainty_s
    if horizon > c.maximum_prediction_horizon_s:
        return np.zeros(2), "PREDICTION_HORIZON_EXCEEDS_SUPPORT"
    desired = np.array(representation.coefficients_m) @ task_basis(now_s+c.pipeline_delay_s+response.onset_delay_s,
                                                                  heldout=heldout)
    predicted = np.array(estimate.position_m)+np.array(estimate.velocity_m_per_s)*horizon
    error = desired-predicted
    gain = np.array(response.gain_m)
    # Regularized local inversion retains cross-coupling and uses only the
    # observed map; saturation/unreachable correction is logged below.
    requested = np.linalg.solve(gain.T@gain+np.eye(2)*1e-4, gain.T@error)
    correction_uncertainty = np.abs(np.array(response.gain_uncertainty_m)) @ np.abs(np.clip(requested,-1,1))
    if np.max(correction_uncertainty)+estimate.uncertainty_m > c.controller_position_uncertainty_limit_m:
        return np.zeros(2), "GAIN_UNCERTAINTY_EXCEEDS_CORRECTION_BUDGET"
    if np.max(np.abs(requested)) > 1:
        reason = "BOUNDED_REQUEST_UNREACHABLE_REMAINDER"
    else:
        reason = "ADMITTED_LOCAL_POLICY"
    return np.clip(requested, -1, 1), reason


def _metrics(times, x, c, *, heldout=False):
    times, x = np.asarray(times), np.asarray(x)
    goal = np.array([task_goal(t, c, heldout) for t in times])
    scored = times > .35
    spatial, timing = [], []
    # Alternating prescribed peak/contact times at .25/.75/... seconds; each
    # peak is an artificial contact proxy, not a biomechanical ground reaction.
    spacing = c.event_spacing_s/(1.15 if heldout else 1.)
    event_times = np.arange(spacing/2, times[-1]-.15, spacing)
    for event_index, event in enumerate(event_times):
        if event < .35 or abs(event % 2) < .15 or 2-event%2 < .15:
            continue  # direction discontinuities separately contribute trajectory RMSE
        foot = event_index%2
        window = (times >= event-.12)&(times <= event+.12)
        if not np.any(window):
            continue
        target = task_goal(event,c,heldout)[foot]
        idx = np.flatnonzero(window)[np.argmax(np.sign(target)*x[window,foot])]
        spatial.append(float(x[idx,foot]-target))
        timing.append(float(times[idx]-event))
    return {"trajectory_rmse_m": float(np.sqrt(np.mean((x[scored]-goal[scored])**2))),
            "contact_spatial_rmse_m": float(np.sqrt(np.mean(np.square(spatial)))) if spatial else None,
            "contact_timing_rmse_s": float(np.sqrt(np.mean(np.square(timing)))) if timing else None,
            "scored_contact_events": len(spatial),
            "contact_metric_scope": "local kinematic peak proxy; no force/contact mechanics"}


def _run_trial(seed, c, family, condition, response, neural_model, library, theta,
               duration, delivery, *, learning, heldout=False, save_trace=False,
               fault=None, subject_seed=None):
    subject_seed = seed if subject_seed is None else subject_seed
    world = _World(subject_seed, c, heldout=heldout)
    world.theta = theta.copy()
    if hasattr(delivery, "begin_session"):
        delivery.begin_session()
    acq = ContactAcquisition(subject_seed+8300, AcquisitionConfig(source_mode=c.source_mode,
                             qualification_mode=c.acquisition_qualification_mode,
                             clock_uncertainty_s=c.acquisition_clock_uncertainty_s),
                             noise_seed=seed+17001)
    decoder = CausalDecoder(c, neural_model)
    sensing = condition.split("__")[0] if condition != "observe_only" else "external"
    representation = library[condition.split("__")[-1]] if condition != "observe_only" else library["learner_only"]
    if fault == "shuffled_expert":
        coefficients = -np.array(representation.coefficients_m)[:,::-1]
        representation = replace(representation, coefficients_m=tuple(tuple(r) for r in coefficients))
    if fault == "incorrect_map":
        response = replace(response, gain_m=tuple(tuple(-v for v in row) for row in response.gain_m))
    rng = np.random.default_rng(seed+9200)
    ext_steps = int(round(c.external_delay_s/c.dt_s))
    history = deque([np.zeros(2) for _ in range(ext_steps+1)], maxlen=ext_steps+1)
    comparison = neural_model is not None and "external_history" in neural_model
    support_truth = {index: (np.zeros(2), np.zeros(2)) for index in range(-ext_steps, 0)}
    position_errors, velocity_errors = [], []
    external_history_used = 0
    plans = deque()
    # Pulse-density modulation selects whole qualified fixed-profile pulses.
    # The profile never changes polarity to represent a signed movement goal.
    accumulators = np.zeros(2)
    held_true = np.zeros(2)
    commanded = np.zeros(2)
    times, positions, trace, pulses = [], [], [], []
    neural_used = 0; neural_valid = 0; requests = {}; invalid = 0; max_measured_charge = 0.
    output_quality = {}; observation_age_max = 0.; decision_to_pulse = []
    last_ext = np.zeros(2); last_support = -c.external_delay_s
    for k in range(int(round(duration/c.dt_s))):
        t = k*c.dt_s
        # At launch, no more than one event/source/profile per 25 ms frame.
        if _pulse_frame(t, c):
            while plans and plans[0][0] <= t+1e-12:
                _, decision_t, candidate, valid = plans.popleft()
                commanded = candidate if valid else np.zeros(2)
                if valid:
                    decision_to_pulse.append(t-decision_t)
            held_true.fill(0)
            accumulators += np.abs(commanded)
            for source in range(2):
                if learning and condition != "observe_only" and accumulators[source] >= 1:
                    accumulators[source] -= 1
                    sign = int(np.sign(commanded[source]))
                    if sign:
                        truth, measured, monitor, witness = _pulse(t, source, sign, delivery, c)
                        held_true[source] = truth
                        output_quality[monitor["quality"]] = output_quality.get(monitor["quality"],0)+1
                        max_measured_charge = max(max_measured_charge, monitor["delivered_phase_charge_C"])
                        if save_trace:
                            pulses.append(witness)
                        if truth:
                            acq.add_artifact(t, c.phase_s,
                                             recovery_s=.010 if fault=="artifact_recovery" else None)
        history.append(world.x.copy())
        if comparison:
            support_truth[k] = (world.x.copy(), world.v.copy())
        ext = history[0]+rng.normal(0, c.external_noise_m, 2)
        physical_support = t-c.external_delay_s
        ext_valid = True
        if fault == "stale_external" and t > duration/2:
            ext, physical_support = last_ext.copy(), last_support
        else:
            last_ext, last_support = ext.copy(), physical_support
        if fault == "source_drift" and t > duration/2:
            acq.set_source_drift(np.eye(4)[[3,2,1,0]])
        neural = acq.observe(t, world.x/c.foot_amplitude_m,
                             world.v/(2*np.pi*c.foot_amplitude_m),
                             external_redundant_state=ext/c.foot_amplitude_m,
                             extra_saturation=fault=="saturation" and t > duration/2)
        o = Observation(t+c.dt_s, tuple(ext), physical_support, ext_valid, neural)
        estimate = decoder.estimate(o, sensing)
        if comparison and estimate.valid:
            # Evaluator-only truth on exactly the estimate's physical support;
            # it never enters the decoder, identification or control request.
            index = int(round(estimate.support_time_s/c.dt_s))
            if index in support_truth and abs(index*c.dt_s-estimate.support_time_s) <= 1e-9:
                true_position, true_velocity = support_truth[index]
                position_errors.append(np.asarray(estimate.position_m)-true_position)
                velocity_errors.append(np.asarray(estimate.velocity_m_per_s)-true_velocity)
        external_history_used += int(estimate.source == "LEARNED_EXTERNAL_HISTORY")
        neural_valid += int(neural.valid)
        neural_used += int(estimate.source == "NEURAL_PLUS_SAME_EXTERNAL")
        invalid += int(not estimate.valid)
        observation_age_max = max(observation_age_max, o.available_time_s-physical_support)
        u, reason = control_request(estimate, response, representation, o.available_time_s, c,
                                    heldout=heldout)
        if not learning or condition == "observe_only":
            u = np.zeros(2)
            reason = "OUTPUT_OFF_ASSESSMENT" if not learning else "OBSERVE_ONLY"
        requests[reason] = requests.get(reason,0)+1
        # Earliest launch includes 11.85 ms. A fixed 40 Hz frame may add waiting;
        # this is explicitly NOT a claim of 25 ms reactive onset compliance.
        launch_after = o.available_time_s+c.pipeline_delay_s
        plans.append((launch_after, o.available_time_s, u.copy(), estimate.valid))
        times.append(t); positions.append(world.x.copy())
        if save_trace:
            trace.append({"time_s": o.available_time_s, "source_state_time_s": t,
                          "task_goal_m": task_goal(t,c,heldout).tolist(),
                          "simulator_position_m": world.x.tolist(), "external_position_m": list(o.external_position_m),
                          "external_measurement_time_s": physical_support, "neural_usable_fraction": neural.usable_fraction,
                          "neural_valid": neural.valid, "estimate_source": estimate.source,
                          "estimated_position_m": list(estimate.position_m), "estimated_velocity_m_per_s": list(estimate.velocity_m_per_s),
                          "estimate_uncertainty_m": estimate.uncertainty_m, "estimate_valid": estimate.valid,
                          "requested_signed_fraction": u.tolist(), "launch_signed_fraction": commanded.tolist(),
                          "true_body_dose_fraction": held_true.tolist(), "policy_reason": reason})
        world.advance(t+c.dt_s, held_true, family, learning=learning, heldout=heldout)
    metrics = _metrics(times, positions, c, heldout=heldout)
    metrics.update({"pulse_count": sum(output_quality.values()), "output_quality_counts": output_quality,
                    "maximum_observed_phase_charge_C": max_measured_charge,
                    "neural_valid_fraction": neural_valid/len(times), "neural_used_fraction": neural_used/len(times),
                    "invalid_state_fraction": invalid/len(times), "policy_reason_counts": requests,
                    "maximum_external_support_age_s": observation_age_max,
                    "maximum_decision_to_frame_s": max(decision_to_pulse,default=0.),
                    "reactive_25ms_target_guaranteed": False,
                    "raw_sample_mask_fraction": acq.total_masked_samples/acq.total_raw_samples,
                    "assistance": "ON" if learning and condition!="observe_only" else "OFF"})
    if comparison:
        metrics["same_support_estimation"] = {
            "position_rmse_m": float(np.sqrt(np.mean(np.square(position_errors)))) if position_errors else None,
            "velocity_rmse_m_per_s": float(np.sqrt(np.mean(np.square(velocity_errors)))) if velocity_errors else None,
            "valid_scored_packets": len(position_errors), "total_packets": len(times),
            "scope": "evaluator-only private body at the external observation's identical physical support"}
        metrics["learned_external_history_used_fraction"] = external_history_used/len(times)
    return world.theta.copy(), metrics, {"samples": trace, "pulses": pulses}


def run_study(seed=0, config=MotorConfig(), delivery: Callable | None=None, *,
              families=FAMILIES, conditions=CONDITIONS, faults=()):
    """Return serializable paired study evidence, including first-trial raw witness.

    The caller can pass ``electrical.MotorDelivery``; the default delivery is an
    explicitly unqualified nominal assumption. Every condition receives the
    same learner draw, external noise, practice/calibration time and latency.
    ``faults`` optionally adds first-block negative controls for the neural expert
    condition. This run does not establish human decoding or learned skill.
    """
    c = config
    if any(f not in FAMILIES for f in families) or any(s not in CONDITIONS+EXTERNAL_HISTORY_CONDITIONS for s in conditions):
        raise ValueError("unknown study condition or plasticity family")
    delivery_callback = delivery or _assumed_delivery
    comparison = any(s in EXTERNAL_HISTORY_CONDITIONS for s in conditions)
    response, decoder_model, calibration = calibrate(seed, c, delivery_callback,
                                                    include_external_history=comparison)
    library = _expert_library(seed, c)
    initial_theta = _World(seed,c).theta.copy()
    serialized_config = asdict(c)
    # The original foundation artifacts are retained as a reproducible coarse
    # reference. Their config schema predates the independent body clock.
    if c.body_integration_step_s == c.dt_s and c.body_integration_method == "legacy_endpoint":
        serialized_config.pop("body_integration_step_s")
        serialized_config.pop("body_integration_method")
    if c.acquisition_qualification_mode == "fixed_history" and c.acquisition_clock_uncertainty_s == 0:
        serialized_config.pop("acquisition_qualification_mode")
        serialized_config.pop("acquisition_clock_uncertainty_s")
    output = {"schema": "SCCI_RH-S3-MOTOR-1", "seed": int(seed), "config": serialized_config,
              "calibration": {"response_map": asdict(response), **calibration},
              "expert_resource": {k:asdict(v) for k,v in library.items()},
              "artifact_audit": {"nominal": artifact_coverage(),
                                 "10ms_recovery_stress": artifact_coverage(recovery_s=.010)},
              "delivery_model": "independent electrical callback" if delivery else "UNQUALIFIED_NOMINAL_ASSUMPTION",
              "families": {}, "negative_controls": {},
              "information_permissions": {"controller_inputs": ["Observation", "StateEstimate", "LearnerMap", "ExpertRepresentation", "known task goal"],
                                          "simulator_only": ["internal theta", "true recruitment", "body state", "true_phase_charge_C"],
                                          "training_labels": "separate calibration/expert external measurements; no evaluation labels"},
              "limitations": ["All neural source/lead-field/recruitment/plasticity values are chosen artificial assumptions.",
                              "A single reduced two-foot kinematic plant is not walking biomechanics or force-contact validation.",
                              "The coherent 80 Hz modulation hypothesis is deliberately favorable and not shown at intradural contacts.",
                              "Measured route/polarization readiness and chemistry/circuit protection remain separate from neural benefit.",
                              "A fixed 40 Hz pulse frame cannot guarantee the Stage 2 25 ms reactive target; planned cadence is a known goal.",
                              "Expert neural representation is learned through expert external labels; extra neural information may be absent.",
                              "Raw artifact coverage does not qualify recursive filter history: a chosen 100 ms uninterrupted history gate may remove neural eligibility during 40 Hz assistance.",
                              "Body/source state is zero-order held across each 5 ms acquisition block; microsecond electrode/electrical timing is modeled separately.",
                              "Transfer is a held-out 15% faster cadence with changed response/cross-coupling, not a human skill-generalization result."]}
    if c.acquisition_qualification_mode == "bounded_residual":
        output["limitations"][6] = "Missing-input filter contamination uses the declared range-bounded digital residual model; it does not establish physical amplifier recovery."
        output["artifact_audit_scope"] = "separate historical fixed-history reference; actual coupled qualification mode is recorded in config"
    if comparison:
        output["comparison_design"] = {
            "added_external_history_conditions": [s for s in conditions if s in EXTERNAL_HISTORY_CONDITIONS],
            "learned_input_dimension_each": 32, "coefficient_count_each": 132,
            "common_training_labels": "measured external position and partition-local differentiated external position",
            "offline_common_cohort": "neural-qualified targets with purged chronological split; history exclusions declared",
            "online_external_comparator": "learned 75ms external history fused with the same nine-row linear external observer",
            "incremental_information_scope": "matched observable-input alternatives; measured-label fit alone is not body-state evidence"}
    for family in families:
        family_result = {"conditions": {}, "contrasts": {}}
        for condition in conditions:
            theta = initial_theta.copy()
            practice = []
            first_trace = None
            acquisition_block = None
            for block in range(c.practice_blocks):
                # Independent block IDs preserve paired noise across conditions
                # and families; learner changes arise only from the intervention.
                theta, metrics, raw = _run_trial(seed+1000*(block+1), c, family, condition,
                                                response, decoder_model, library, theta,
                                                c.practice_block_s, delivery_callback, learning=True,
                                                save_trace=(block==0 and family==families[0]
                                                            and condition==c.save_trace_condition), subject_seed=seed)
                practice.append(metrics)
                if raw["samples"]:
                    first_trace = raw
                theta_probe = theta*(1-c.forgetting_fraction)
                _, retained, _ = _run_trial(seed+60000, c, family, condition, response, decoder_model,
                                            library, theta_probe, c.assessment_s, delivery_callback,
                                            learning=False, subject_seed=seed)
                if (retained["contact_spatial_rmse_m"] is not None
                    and retained["contact_spatial_rmse_m"] <= c.retention_spatial_threshold_m
                    and retained["contact_timing_rmse_s"] <= c.retention_timing_threshold_s
                    and acquisition_block is None):
                    acquisition_block = block+1
            _, retained, retention_trace = _run_trial(seed+60000, c, family, condition, response, decoder_model,
                                                      library, theta*(1-c.forgetting_fraction), c.assessment_s,
                                                      delivery_callback, learning=False,
                                                      save_trace=(family==families[0] and condition==c.save_trace_condition),
                                                      subject_seed=seed)
            _, transferred, transfer_trace = _run_trial(seed+61000, c, family, condition, response, decoder_model,
                                                        library, theta*(1-c.forgetting_fraction), c.assessment_s,
                                                        delivery_callback, learning=False, heldout=True,
                                                        save_trace=(family==families[0] and condition==c.save_trace_condition),
                                                        subject_seed=seed)
            summary = {"first_assisted_contact_spatial_rmse_m": practice[0]["contact_spatial_rmse_m"],
                       "last_assisted_contact_spatial_rmse_m": practice[-1]["contact_spatial_rmse_m"],
                       "retention_off": retained, "transfer_off": transferred,
                       "practice_seconds": c.practice_blocks*c.practice_block_s,
                       "acquisition_block": acquisition_block, "threshold_censored": acquisition_block is None,
                       "threshold_scope": "artificial contact spatial <=18 mm AND timing <=25 ms in stimulation-off probe",
                       "assistance_off_verified": retained["pulse_count"] == 0 and transferred["pulse_count"] == 0}
            result = {"summary": summary, "practice_blocks": practice}
            if first_trace is not None:
                result["trace"] = {"practice": first_trace, "retention": retention_trace, "transfer": transfer_trace}
            family_result["conditions"][condition] = result
        def metric(name):
            return family_result["conditions"][name]["summary"]["retention_off"]["contact_spatial_rmse_m"]
        for rep in ("learner_only", "expert_external", "expert_neural"):
            ext, neural = "external__"+rep, "neural_external__"+rep
            if ext in conditions and neural in conditions:
                family_result["contrasts"]["neural_minus_external_retention_m__"+rep] = metric(neural)-metric(ext)
            history = "external_history__"+rep
            if history in conditions and neural in conditions:
                family_result["contrasts"]["neural_minus_external_history_retention_m__"+rep] = metric(neural)-metric(history)
        for sensing in ("external", "neural_external", "external_history"):
            learner, ext, neural = sensing+"__learner_only", sensing+"__expert_external", sensing+"__expert_neural"
            if all(k in conditions for k in (learner,ext,neural)):
                family_result["contrasts"]["expert_external_minus_learner_retention_m__"+sensing] = metric(ext)-metric(learner)
                family_result["contrasts"]["expert_neural_minus_expert_external_retention_m__"+sensing] = metric(neural)-metric(ext)
        output["families"][family] = family_result
    for fault in faults:
        if fault not in {"shuffled_expert", "incorrect_map", "stale_external", "artifact_recovery", "saturation", "source_drift"}:
            raise ValueError("unknown negative control")
        _, metrics, trace = _run_trial(seed+1000, c, families[0], "neural_external__expert_neural",
                                      response, decoder_model, library, initial_theta, c.practice_block_s,
                                      delivery_callback, learning=True, save_trace=True, fault=fault, subject_seed=seed)
        output["negative_controls"][fault] = {"metrics": metrics, "trace": trace}
    return output
