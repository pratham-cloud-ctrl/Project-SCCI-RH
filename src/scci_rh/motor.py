"""Synthetic rhythmic practice model; learning benefit is an assumed parameter.

The quadratures are generated signals, not recordings of motor intent. No mapping
from a spinal electrode to these quadratures is established by this model.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class MotorConfig:
    dt: float = 0.01
    seconds: float = 12.0
    sessions: int = 45
    noise: float = 0.16
    delay: float = 0.08
    assumed_delay: float | None = None
    assistance: float = 0.65
    teaching_beta: float = 0.8
    motor_noise: float = 0.025
    retention_fraction: float = 0.97
    threshold: float = 0.075


def template(phase, skill):
    amplitude = 1.0 - 0.45 * np.exp(-skill)
    lag = 0.35 * np.exp(-skill)
    return amplitude * np.sin(phase - lag)


def unassisted_rmse(skill, noise=0.025):
    a = 1.0 - 0.45 * np.exp(-skill)
    lag = 0.35 * np.exp(-skill)
    return float(np.sqrt((a*a + 1 - 2*a*np.cos(lag))/2 + noise*noise))


def phase_estimate(phase, dt, noise, delay, rng, compensate=True, compensation_delay=None):
    """Causal quadrature averaging and frequency-based phase extrapolation."""
    delay_steps = int(round(delay / dt))
    delayed = np.concatenate((np.repeat(phase[0], delay_steps), phase))[:len(phase)]
    z = np.exp(1j * delayed) + noise * (rng.normal(size=len(phase)) + 1j*rng.normal(size=len(phase)))
    width = max(1, int(round(0.05 / dt)))
    padded = np.concatenate((np.repeat(z[0], width-1), z))
    cum = np.concatenate(([0j], np.cumsum(padded)))
    filtered = (cum[width:] - cum[:-width]) / width
    measured = np.unwrap(np.angle(filtered))
    window = int(round(1.0 / dt))
    freq = np.full(len(phase), 2*np.pi)
    freq[window:] = (measured[window:] - measured[:-window])/(window*dt)
    freq = np.clip(freq, 2*np.pi*0.5, 2*np.pi*1.5)
    if compensate:
        horizon = delay_steps*dt if compensation_delay is None else compensation_delay
        measured = measured + freq*(horizon + (width-1)*dt/2)
    return measured


def simulate_motor(seed, policy="calibrated", config=MotorConfig()):
    if policy not in {"unassisted", "calibrated", "uncalibrated", "shuffled", "oracle"}:
        raise ValueError("unknown policy")
    rng = np.random.default_rng(seed)
    learner_gain = float(rng.uniform(0.45, 1.65))
    baseline_rate = float(rng.uniform(0.07, 0.10))
    initial_skill = float(rng.uniform(0.12, 0.25))
    xcal = np.array([-0.6, -0.3, 0.3, 0.6])
    ycal = learner_gain*xcal + rng.normal(0, 0.025, len(xcal))
    estimated_gain = float(np.clip(xcal @ ycal / (xcal @ xcal), 0.25, 2.0))
    skill = initial_skill
    rows = [{"seed": seed, "policy": policy, "session": 0, "skill": skill,
             "unassisted_rmse": unassisted_rmse(skill, config.motor_noise),
             "assisted_rmse": unassisted_rmse(skill, config.motor_noise), "alignment": 0.0}]
    demo = None
    count = int(config.seconds/config.dt)
    t = np.arange(count)*config.dt
    for session in range(1, config.sessions+1):
        # Same random draws for every policy for paired synthetic learner trials.
        phase_offset = rng.uniform(-np.pi, np.pi)
        freq = 1.0 + 0.03*np.sin(2*np.pi*0.07*t + phase_offset)
        phase = phase_offset + np.cumsum(2*np.pi*freq*config.dt)
        predicted = phase_estimate(phase, config.dt, config.noise, config.delay, rng,
                                   compensate=policy != "uncalibrated", compensation_delay=config.assumed_delay)
        measured_noise = rng.normal(0, config.motor_noise, count)
        shuffled_order = rng.permutation(count)
        desired = np.sin(phase)
        base = template(phase, skill)
        if policy == "oracle":
            ph = phase
            gain = learner_gain
        elif policy == "shuffled":
            ph = predicted[shuffled_order]
            gain = estimated_gain
        else:
            ph = predicted
            gain = 1.0 if policy == "uncalibrated" else estimated_gain
        command = config.assistance * (np.sin(ph) - template(ph, skill))/gain
        command = np.clip(command, -0.8, 0.8)
        if policy == "unassisted":
            command[:] = 0
        assisted = base + learner_gain*command
        valid = t >= 2.0  # Explicit estimator warm-up excluded from scoring.
        e0 = np.mean((desired[valid]-base[valid])**2)
        e1 = np.mean((desired[valid]-assisted[valid])**2)
        alignment = float(np.clip((e0-e1)/max(e0, 1e-12), -1, 1))
        skill += baseline_rate*(1-skill/3.2)*(1 + config.teaching_beta*alignment)
        online_rmse = float(np.sqrt(np.mean((desired[valid] - assisted[valid] - measured_noise[valid])**2)))
        rows.append({"seed": seed, "policy": policy, "session": session, "skill": skill,
                     "unassisted_rmse": unassisted_rmse(skill, config.motor_noise),
                     "assisted_rmse": online_rmse, "alignment": alignment})
        if session == 1:
            phase_error = np.angle(np.exp(1j*(predicted-phase)))
            demo = {"time_s": t, "target": desired, "unassisted": base,
                    "assisted": assisted, "estimated_phase_rad": predicted,
                    "true_phase_rad": phase, "phase_error_rad": phase_error}
    threshold_session = next((r["session"] for r in rows if r["unassisted_rmse"] <= config.threshold), None)
    summary = {"seed": seed, "policy": policy, "teaching_beta": config.teaching_beta,
               "noise": config.noise, "delay_s": config.delay, "learner_gain": learner_gain,
               "assumed_delay_s": config.delay if config.assumed_delay is None else config.assumed_delay,
               "estimated_gain": estimated_gain, "baseline_rate": baseline_rate,
               "initial_skill": initial_skill, "final_skill": skill,
               "final_unassisted_rmse": unassisted_rmse(skill, config.motor_noise),
               "retained_rmse": unassisted_rmse(skill*config.retention_fraction, config.motor_noise),
               "first_assisted_rmse": rows[1]["assisted_rmse"],
               "first_unassisted_rmse": unassisted_rmse(initial_skill, config.motor_noise),
               "sessions_to_threshold": threshold_session,
               "phase_rmse_rad": float(np.sqrt(np.mean(demo["phase_error_rad"][t >= 2]**2)))}
    return rows, summary, demo
