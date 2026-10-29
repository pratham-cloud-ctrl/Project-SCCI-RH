"""A declared future-interface scenario, not a biological or circuit validation.

Run normally to write this package's small result set; --check reproduces and
compares saved numeric results without changing them. Historical studies are
neither imported nor modified. Only numpy and matplotlib are required.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ARMS = ("off", "expert_external", "expert_spinal_same_information",
        "spinal_live", "phase_shifted")
RHOS = (-1.0, 0.0, 1.0, 2.0)
SEEDS = (26101301, 26101302, 26101303, 26101304)
VARIANTS = ("nominal", "neural_absent", "neural_late", "gain_drift", "no_authority")


@dataclass(frozen=True)
class Config:
    dt_s: float = 0.005
    frame_s: float = 0.025
    practice_s: float = 2.0
    probe_s: float = 1.0
    blocks: int = 24
    amplitude_m: float = 0.10
    assistance_fraction: float = 0.65
    learning_rate_per_block: float = 0.08
    assumed_retention_fraction: float = 0.95
    off_threshold_m: float = 0.015
    neural_delay_s: float = 0.020
    external_delay_s: float = 0.060
    onset_delay_s: float = 0.035
    activation_tau_s: float = 0.040
    external_noise_m: float = 0.0015
    neural_feature_noise: float = 0.12
    assumed_dose_fraction: float = 1.0
    warmup_s: float = 0.20
    # A clocked two-second washout is paid after every practice block. The
    # residual actuator state is explicitly decayed, never reset on switching.
    washout_s: float = 2.0
    phase_calibration_s: float = 12.0
    common_calibration_s: float = 36.0


def basis(t: np.ndarray) -> np.ndarray:
    return np.column_stack((np.sin(2 * np.pi * t), np.cos(2 * np.pi * t)))


def unit(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 1e-10 else np.array([0.0, 1.0])


def rotate(v: np.ndarray, angle: float) -> np.ndarray:
    # v is [sin phase, cos phase].
    s, c = np.sin(angle), np.cos(angle)
    return np.array([v[0] * c + v[1] * s, v[1] * c - v[0] * s])


def rmse(theta: np.ndarray, reference: np.ndarray) -> float:
    # Exact per-coordinate RMS over a complete cycle of an OFF primitive.
    return float(np.linalg.norm(theta - reference) / 2)


def calibration(seed: int, c: Config, variant: str) -> dict:
    rng = np.random.default_rng(seed)
    initial = np.array([[0.060, -0.018], [0.012, 0.057]])
    initial += rng.normal(0, 0.003, (2, 2))
    gain = np.array([[0.060, 0.009], [0.007, 0.055]])
    gain *= rng.uniform(0.85, 1.15, (1, 2))
    if variant == "no_authority":
        gain[:] = 0
    # Abstract feature mixing, NOT raw voltages or a proven human neural code.
    mixing = rng.normal(0, 1, (16, 2))
    phase = basis(np.arange(0, c.phase_calibration_s, c.dt_s))
    measured = phase @ initial.T + rng.normal(0, c.external_noise_m, (len(phase), 2))
    fitted_theta = np.linalg.lstsq(phase, measured, rcond=None)[0].T
    external_phase_labels = measured @ np.linalg.inv(fitted_theta).T
    features = phase @ mixing.T + rng.normal(0, c.neural_feature_noise, (len(phase), 16))
    decoder = np.linalg.lstsq(features, external_phase_labels, rcond=None)[0]
    # Equilibrium responses from eight separate normalized program probes.
    probes = np.array([[1, 0], [-1, 0], [0, 1], [0, -1]] * 2, dtype=float)
    responses = probes @ gain.T + rng.normal(0, 0.001, probes.shape)
    fitted_gain = np.linalg.lstsq(probes, responses, rcond=None)[0].T
    usable = bool(np.linalg.svd(fitted_gain, compute_uv=False).min() > 0.010)
    return dict(initial=initial, gain=gain, fitted_gain=fitted_gain, mixing=mixing,
                decoder=decoder, usable=usable)


def simulate(seed: int, arm: str, rho: float, variant: str, c: Config,
             save_trace: bool = False) -> tuple[dict, list[dict], dict | None]:
    cal = calibration(seed, c, variant)
    initial = cal["initial"]
    theta = initial.copy()
    reference = np.eye(2) * c.amplitude_m
    gain = cal["gain"] * (0.5 if variant == "gain_drift" else 1.0)
    gain_hat = cal["fitted_gain"]
    gain_inverse = np.linalg.inv(gain_hat) if cal["usable"] else np.zeros((2, 2))
    n = int(round(c.practice_s / c.dt_s))
    t = np.arange(n) * c.dt_s
    frame = int(round(c.frame_s / c.dt_s))
    onset = int(round(c.onset_delay_s / c.dt_s))
    edelay = int(round(c.external_delay_s / c.dt_s))
    ndelay = int(round((0.120 if variant == "neural_late" else c.neural_delay_s) / c.dt_s))
    alpha = 1 - np.exp(-c.dt_s / c.activation_tau_s)
    activation = np.zeros(2)
    activation_hat = np.zeros(2)
    history: list[dict] = []
    trace = None
    threshold = None
    max_learning_identity_error = 0.0
    for block in range(c.blocks + 1):
        retained = initial + c.assumed_retention_fraction * (theta - initial)
        off = rmse(retained, reference)
        if threshold is None and off <= c.off_threshold_m:
            threshold = block
        row = dict(seed=seed, variant=variant, arm=arm, rho=rho, block=block,
                   assumed_post_washout_off_rmse_m=off,
                   ordinary_off_rmse_m=rmse(theta, reference))
        history.append(row)
        if block == c.blocks:
            break
        rng = np.random.default_rng(np.random.SeedSequence([seed, block, 1301]))
        # The OFF probe is paced by a known cue. Its measured positions, not
        # private learner coefficients, determine the runtime template estimate.
        probe_basis = basis(np.arange(0, c.probe_s, c.dt_s))
        probe_positions = probe_basis @ theta.T + rng.normal(
            0, c.external_noise_m, (len(probe_basis), 2))
        theta_hat = np.linalg.lstsq(probe_basis, probe_positions, rcond=None)[0].T
        theta_inverse = np.linalg.inv(theta_hat)
        # During practice the actual oscillator departs from its known 1 Hz cue.
        # Neither this phase nor future achieved motion enters the controller.
        phase = 2 * np.pi * t + rng.normal(0, 0.10)
        phase += 0.12 * np.sin(2 * np.pi * 0.4 * t + rng.uniform(-np.pi, np.pi))
        phi = np.column_stack((np.sin(phase), np.cos(phase)))
        target = phi @ reference.T
        voluntary = phi @ theta.T
        neural = phi @ cal["mixing"].T + rng.normal(0, c.neural_feature_noise, (n, 16))
        external_noise = rng.normal(0, c.external_noise_m, (n, 2))
        command = np.zeros((n, 2))
        stim = np.zeros((n, 2))
        predicted_stim = np.zeros((n, 2))
        position = np.zeros((n, 2))
        estimates = np.full((n, 2), np.nan)
        nonzero_frames = 0
        supports: list[tuple[float, float]] = []
        for i in range(n):
            stim[i] = gain @ activation
            predicted_stim[i] = gain_hat @ activation_hat
            position[i] = voluntary[i] + stim[i]
            if i and i % frame:
                command[i] = command[i - 1]
            elif i * c.dt_s >= c.warmup_s and arm != "off" and cal["usable"]:
                use_neural = arm in ("spinal_live", "phase_shifted") and variant != "neural_absent"
                age = ndelay if use_neural else edelay
                j = i - age
                if j >= 0:
                    if use_neural:
                        observed_phase = unit(neural[j] @ cal["decoder"])
                    else:
                        measured = position[j] + external_noise[j]
                        observed_phase = unit(theta_inverse @ (measured - predicted_stim[j]))
                    support = j * c.dt_s
                    availability = i * c.dt_s
                    assert support <= availability
                    supports.append((support, availability))
                    horizon = age * c.dt_s + c.onset_delay_s + c.activation_tau_s
                    estimate = rotate(observed_phase, 2 * np.pi * horizon)
                    if arm == "phase_shifted":
                        estimate = rotate(estimate, np.pi / 2)
                    estimates[i] = estimate
                    command[i] = np.clip(gain_inverse @ (
                        c.assistance_fraction * (reference - theta_hat) @ estimate), -1, 1)
                    nonzero_frames += bool(np.any(command[i]))
            delivered = command[i - onset] if i >= onset else np.zeros(2)
            activation += alpha * (c.assumed_dose_fraction * delivered - activation)
            activation_hat += alpha * (delivered - activation_hat)
        gram_inverse = np.linalg.inv(phi.T @ phi)
        residual_projection = (target - position).T @ phi @ gram_inverse
        stimulation_projection = stim.T @ phi @ gram_inverse
        change = c.learning_rate_per_block * (residual_projection + rho * stimulation_projection)
        # This identity exposes the assumed biological benefit instead of
        # concealing an imposed learning multiplier in a numerical loop.
        identity = c.learning_rate_per_block * (
            reference - theta + (rho - 1) * stimulation_projection)
        max_learning_identity_error = max(max_learning_identity_error,
                                         float(np.max(np.abs(change - identity))))
        theta += change
        row.update(practice_on_rmse_m=float(np.sqrt(np.mean((target - position) ** 2))),
                   nonzero_frames=nonzero_frames,
                   stimulation_projection_norm_m=float(np.linalg.norm(stimulation_projection)),
                   causal_observations=len(supports))
        if save_trace and block == 0:
            trace = dict(time_s=t.tolist(), target_m=target.tolist(),
                         position_m=position.tolist(), voluntary_m=voluntary.tolist(),
                         command_normalized=command.tolist(), actual_stimulation_effect_m=stim.tolist())
        # Charge/tissue recovery is outside this normalized interface. This is
        # only the modeled movement-response washout before the next OFF probe.
        for tail in range(onset):
            delivered = command[n - onset + tail]
            activation += alpha * (c.assumed_dose_fraction * delivered - activation)
            activation_hat += alpha * (delivered - activation_hat)
        washout = np.exp(-(c.washout_s - c.onset_delay_s) / c.activation_tau_s)
        activation *= washout
        activation_hat *= washout
    result = dict(seed=seed, variant=variant, arm=arm, rho=rho,
                  first_on_rmse_m=history[0]["practice_on_rmse_m"],
                  initial_off_rmse_m=history[0]["assumed_post_washout_off_rmse_m"],
                  final_off_rmse_m=history[-1]["assumed_post_washout_off_rmse_m"],
                  blocks_to_assumed_off_threshold=threshold,
                  total_nonzero_frames=sum(r.get("nonzero_frames", 0) for r in history),
                  all_observations_causal=True, local_gain_available=cal["usable"],
                  maximum_learning_identity_residual_m=max_learning_identity_error,
                  practice_seconds_to_threshold=None if threshold is None else threshold * c.practice_s,
                  total_seconds_to_threshold=None if threshold is None else (
                      c.common_calibration_s + threshold * (c.probe_s + c.practice_s + c.washout_s)))
    return result, history, trace


def run(c: Config) -> tuple[dict, list[dict], dict]:
    runs, histories, traces = [], [], {}
    for variant in VARIANTS:
        rhos = RHOS if variant == "nominal" else (2.0,)
        arms = ARMS if variant == "nominal" else ("off", "expert_external", "spinal_live")
        for seed in SEEDS:
            for rho in rhos:
                for arm in arms:
                    capture = seed == SEEDS[0] and rho == 2 and variant == "nominal"
                    result, rows, trace = simulate(seed, arm, rho, variant, c, capture)
                    runs.append(result)
                    histories.extend(rows)
                    if trace is not None:
                        traces[arm] = trace
    groups = {(r["variant"], r["seed"], r["rho"], r["arm"]): r for r in runs}
    checks = []
    for seed in SEEDS:
        for rho in RHOS:
            a = groups[("nominal", seed, rho, "expert_external")]
            b = groups[("nominal", seed, rho, "expert_spinal_same_information")]
            for key in ("first_on_rmse_m", "final_off_rmse_m", "total_nonzero_frames"):
                assert a[key] == b[key], "A neural label cannot create information"
            if rho == 1:
                baseline = groups[("nominal", seed, rho, "off")]["final_off_rmse_m"]
                for arm in ARMS:
                    assert abs(groups[("nominal", seed, rho, arm)]["final_off_rmse_m"] - baseline) < 1e-12
        assert groups[("neural_absent", seed, 2.0, "spinal_live")]["final_off_rmse_m"] == groups[("neural_absent", seed, 2.0, "expert_external")]["final_off_rmse_m"]
        for arm in ("off", "expert_external", "spinal_live"):
            assert groups[("no_authority", seed, 2.0, arm)]["total_nonzero_frames"] == 0
    assert max(r["maximum_learning_identity_residual_m"] for r in runs) < 1e-12
    checks.extend(("Equal-information reference arms give identical results",
                   "rho=1 gives identical OFF learning despite ON assistance",
                   "Absent neural features fall back exactly to the external policy",
                   "No identified recruitment authority gives zero commands",
                   "All control observations have support <= availability",
                   "Learning identity independently matches the integrated update"))
    summary = dict(schema="scci_rh.conditional-concept.v1", date="2026-10-13",
                   scope="Illustrative future-interface scenario; no biological or native-circuit validation",
                   source_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                   config=asdict(c), seeds=list(SEEDS), rhos=list(RHOS),
                   normalized_command_not_current=True,
                   human_parameters_fitted=False, historical_studies_modified=False,
                   checks=checks, run_count=len(runs), practice_block_count=len(runs) * c.blocks,
                   runs=runs)
    return summary, histories, traces


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--figures", action="store_true")
    args = parser.parse_args()
    summary, history, traces = run(Config())
    path = HERE / "summary.json"
    if args.check:
        saved = json.loads(path.read_text(encoding="utf-8"))
        def compare(a, b):
            if isinstance(a, dict):
                assert a.keys() == b.keys()
                for key in a: compare(a[key], b[key])
            elif isinstance(a, list):
                assert len(a) == len(b)
                for x, y in zip(a, b): compare(x, y)
            elif isinstance(a, float):
                assert np.isclose(a, b, rtol=2e-9, atol=1e-12), (a, b)
            else:
                assert a == b, (a, b)
        compare(summary, saved)
        compare(traces, json.loads((HERE / "first-practice-traces.json").read_text(encoding="utf-8")))
        with (HERE / "learning-curves.csv").open(encoding="utf-8", newline="") as stream:
            saved_rows = list(csv.DictReader(stream))
        assert len(saved_rows) == len(history)
        for row, saved_row in zip(history, saved_rows):
            for key, value in row.items():
                if isinstance(value, str): assert saved_row[key] == value
                else: assert np.isclose(float(saved_row[key]), value, rtol=2e-9, atol=1e-12)
        print(f"PASS: {len(summary['runs'])} scenarios, saved histories/traces, {len(summary['checks'])} mechanism checks")
    else:
        path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (HERE / "first-practice-traces.json").write_text(json.dumps(traces, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
        keys = list(history[0])
        with (HERE / "learning-curves.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            writer.writerows(history)
        print(f"Saved {len(summary['runs'])} scenarios and {len(history)} learning-curve rows")
    if args.figures:
        plot(summary, history, traces)


def plot(summary: dict, history: list[dict], traces: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "scci_rh-conditional-20261013"})
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), layout="constrained")
    for ax, rho in zip(axes, (0.0, 1.0, 2.0)):
        for arm, label in (("off", "Unaided"), ("expert_external", "External feedback"),
                           ("spinal_live", "Assumed spinal features")):
            values = [[r["assumed_post_washout_off_rmse_m"] * 1000 for r in history
                       if r["variant"] == "nominal" and r["seed"] == seed and r["arm"] == arm and r["rho"] == rho]
                      for seed in SEEDS]
            ax.plot(range(25), np.mean(values, axis=0), label=label, linewidth=2)
        ax.set_title(f"Assumed teaching coefficient rho = {rho:g}")
        ax.set_xlabel("Equal-duration practice blocks")
        ax.grid(alpha=0.15)
    axes[0].set_ylabel("Assumed retained OFF error (mm)")
    axes[0].legend(fontsize=8)
    fig.suptitle("Conditional model: assistance alone does not establish faster learning", fontsize=13)
    fig.savefig(HERE / "conditional-learning.png", dpi=180)
    fig.savefig(HERE / "conditional-learning.svg", metadata={"Date": None})
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 3.7), layout="constrained")
    for arm, label in (("off", "Unaided attempt"), ("spinal_live", "Conditional assistance"),
                       ("phase_shifted", "90-degree timing mismatch")):
        tr = traces[arm]
        ax.plot(tr["time_s"], np.array(tr["position_m"])[:, 0] * 1000, label=label)
    tr = traces["off"]
    ax.plot(tr["time_s"], np.array(tr["target_m"])[:, 0] * 1000, "k--", label="Expert task reference")
    ax.set(xlabel="Practice time (s)", ylabel="First task coordinate (mm)",
           title="Synthetic first practice: timing and reachable assistance")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.15)
    fig.savefig(HERE / "conditional-assistance.png", dpi=180)
    fig.savefig(HERE / "conditional-assistance.svg", metadata={"Date": None})
    plt.close(fig)


if __name__ == "__main__":
    main()
