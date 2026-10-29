"""Reduced-order synthetic MAP plant with external sensor PI feedback.

mmHg values are illustrative model coordinates, never clinical prescriptions.
Normalized input is an abstract actuator, not a stimulation-dose conversion.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class PressureConfig:
    dt: float = 0.05
    seconds: float = 160.0
    setpoint: float = 90.0
    sensor_delay: float = 0.30
    sensor_noise: float = 0.60
    stale_seconds: float = 0.50
    kp: float = 0.045
    ki: float = 0.008
    output_limit: float = 1.0
    slew_per_second: float = 0.40
    gain_scale: float = 1.0
    dropout: bool = False
    invalid_sensor: bool = False


def simulate_pressure(seed, policy="closed_loop", config=PressureConfig()):
    if policy not in {"unassisted", "fixed", "closed_loop"}:
        raise ValueError("unknown policy")
    rng = np.random.default_rng(seed)
    gain = float(rng.uniform(28, 42)*config.gain_scale)
    tau = float(rng.uniform(6, 10))
    actuator_tau = float(rng.uniform(1, 2.5))
    disturbance_size = float(rng.uniform(26, 34))
    n = int(config.seconds/config.dt)
    t = np.arange(n)*config.dt
    pressure = np.full(n, config.setpoint)
    command = np.zeros(n)
    actuator = np.zeros(n)
    measurement = np.full(n, np.nan)
    stale = np.zeros(n, dtype=bool)
    available = np.ones(n, dtype=bool)
    if config.dropout:
        available[(t >= 75) & (t < 88)] = False
    invalid = np.zeros(n, dtype=bool)
    if config.invalid_sensor:
        invalid[(t >= 105) & (t < 108)] = True
    noise = rng.normal(0, config.sensor_noise, n)
    delay_steps = int(round(config.sensor_delay/config.dt))
    last_seen = 0.0
    measured = config.setpoint
    integral = 0.0
    valid_since = 0.0
    latched_invalid = False
    raw_u = 0.0
    disturbance = disturbance_size*np.clip((t-20)/2, 0, 1)
    for i in range(n):
        if available[i] and not invalid[i]:
            measured = pressure[max(0, i-delay_steps)] + noise[i]
            last_seen = t[i]
            measurement[i] = measured
            if valid_since is None:
                valid_since = t[i]
            if latched_invalid and t[i]-valid_since >= 2.0:
                latched_invalid = False
                integral = 0.0
        elif invalid[i]:
            latched_invalid = True
            valid_since = None
        else:
            valid_since = None
        stale[i] = bool(t[i]-last_seen > config.stale_seconds or latched_invalid)
        if policy == "unassisted":
            raw_u = 0.0
        elif policy == "fixed":
            raw_u = 0.85 if t[i] >= 20 else 0.0
        else:
            error = config.setpoint-measured
            candidate = config.kp*error + integral
            # Conditional integration avoids wind-up into an output constraint.
            if (0 < candidate < config.output_limit or
                    (candidate >= config.output_limit and error < 0) or
                    (candidate <= 0 and error > 0)) and not stale[i]:
                integral += config.ki*error*config.dt
            raw_u = float(np.clip(config.kp*error + integral, 0, config.output_limit))
        if stale[i] and policy == "closed_loop":
            command[i] = 0.0  # Sensor inhibition overrides ramping immediately.
        else:
            previous = command[i-1] if i else 0.0
            command[i] = float(np.clip(raw_u, previous-config.slew_per_second*config.dt,
                                      previous+config.slew_per_second*config.dt))
        if i+1 < n:
            actuator[i+1] = actuator[i] + config.dt*(command[i]-actuator[i])/actuator_tau
            pressure[i+1] = pressure[i] + config.dt*(-(pressure[i]-config.setpoint+disturbance[i])
                                                  + gain*actuator[i])/tau
    window = (t >= 40) & (t < config.seconds-1)
    err = pressure[window]-config.setpoint
    summary = {"seed": seed, "policy": policy, "gain_mmhg": gain, "tau_s": tau,
               "actuator_tau_s": actuator_tau, "disturbance_mmhg": disturbance_size,
               "mae_mmhg": float(np.mean(abs(err))),
               "target_band_fraction": float(np.mean(abs(err) <= 5)),
               "minimum_mmhg": float(pressure.min()), "maximum_mmhg": float(pressure.max()),
               "saturation_fraction": float(np.mean(command[window] >= config.output_limit-0.001)),
               "effort_integral_s": float(command.sum()*config.dt),
               "stale_nonzero_steps": int(np.sum(stale & (command != 0))) if policy == "closed_loop" else None}
    trace = {"time_s": t, "map_mmhg": pressure, "setpoint_mmhg": np.full(n, config.setpoint),
             "command": command, "actuator": actuator, "measurement_mmhg": measurement,
             "disturbance_mmhg": disturbance, "sensor_stale": stale.astype(int),
             "sensor_available": available.astype(int)}
    return summary, trace
