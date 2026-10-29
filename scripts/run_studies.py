"""Reproduce all synthetic SCCI_RH studies and figures from the repository root."""
from pathlib import Path
import sys
import json
import csv
import platform
from dataclasses import replace, asdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from scci_rh.motor import MotorConfig, simulate_motor
from scci_rh.pressure import PressureConfig, simulate_pressure

RESULTS, FIGURES = ROOT/"results", ROOT/"figures"
RESULTS.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)
SEEDS = list(range(24000, 24040))
COLORS = {"unassisted": "#60768d", "calibrated": "#087f89", "uncalibrated": "#be7c28",
          "shuffled": "#b7485d", "oracle": "#7664a6", "closed_loop": "#087f89", "fixed": "#be7c28"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold", "figure.dpi": 160,
                     "savefig.facecolor": "white", "axes.labelcolor": "#0b1424",
                     "text.color": "#0b1424", "axes.grid": True, "grid.alpha": 0.15})


def write_csv(name, rows):
    if not rows:
        return
    with (RESULTS/name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_trace(name, trace):
    keys = list(trace)
    write_csv(name, [dict(zip(keys, values)) for values in zip(*(trace[k] for k in keys))])


def estimate(values):
    x = np.array(values, dtype=float)
    rng = np.random.default_rng(20261007)
    samples = np.mean(x[rng.integers(0, len(x), size=(2000, len(x)))], axis=1)
    return {"mean": float(x.mean()), "sd": float(x.std(ddof=1)),
            "ci95_bootstrap": [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))],
            "n": len(x)}


def save(fig, name):
    fig.savefig(FIGURES/(name+".png"), dpi=200, bbox_inches="tight")
    fig.savefig(FIGURES/(name+".svg"), bbox_inches="tight")
    plt.close(fig)


def main():
    motor_config = MotorConfig()
    motor_rows, session_rows, curves, demos = [], [], {}, {}
    policies = ["unassisted", "calibrated", "uncalibrated", "shuffled", "oracle"]
    for policy in policies:
        curves[policy] = []
        for seed in SEEDS:
            sessions, summary, demo = simulate_motor(seed, policy, motor_config)
            summary["scenario"] = "nominal_beta_0.8"
            for s in sessions:
                s["scenario"] = summary["scenario"]
            motor_rows.append(summary)
            session_rows.extend(sessions)
            curves[policy].append([s["unassisted_rmse"] for s in sessions])
            if seed == SEEDS[0]:
                demos[policy] = demo
    zero_rows = []
    for seed in SEEDS:
        sessions, summary, demo = simulate_motor(seed, "calibrated", replace(motor_config, teaching_beta=0))
        summary["scenario"] = "zero_teaching_benefit"
        for s in sessions:
            s["scenario"] = summary["scenario"]
        motor_rows.append(summary)
        zero_rows.append(summary)
        session_rows.extend(sessions)
    sensitivity = []
    for delay in [0.02, 0.15, 0.40]:
        for noise in [0.08, 0.25, 0.60]:
            for seed in SEEDS[:12]:
                _, sm, _ = simulate_motor(seed, "calibrated", replace(motor_config, delay=delay, noise=noise))
                sm["scenario"] = "phase_sensitivity"
                sensitivity.append(sm)
    beta_rows = []
    for beta in [0.0, 0.4, 0.8, 1.2]:
        for seed in SEEDS:
            _, sm, _ = simulate_motor(seed, "calibrated", replace(motor_config, teaching_beta=beta))
            beta_rows.append(sm)
    mismatch_rows = []
    for seed in SEEDS:
        _, sm, _ = simulate_motor(seed, "calibrated", replace(motor_config, delay=.40, assumed_delay=.08))
        sm["scenario"] = "unmodeled_latency"
        mismatch_rows.append(sm)
    write_csv("motor_trials.csv", motor_rows)
    write_csv("motor_sessions.csv", session_rows)
    write_csv("motor_sensitivity.csv", sensitivity)
    write_csv("motor_beta_sensitivity.csv", beta_rows)
    write_csv("motor_latency_mismatch.csv", mismatch_rows)
    write_trace("motor_example_trace.csv", demos["calibrated"])
    motor_summary = {}
    for policy in policies:
        subset = [r for r in motor_rows if r["policy"] == policy and r["scenario"] == "nominal_beta_0.8"]
        motor_summary[policy] = {key: estimate([r[key] for r in subset]) for key in
                                ["retained_rmse", "first_assisted_rmse", "phase_rmse_rad"]}
        reached = [r["sessions_to_threshold"] for r in subset if r["sessions_to_threshold"] is not None]
        motor_summary[policy]["threshold_reached_n"] = len(reached)
        motor_summary[policy]["sessions_to_threshold_conditional"] = estimate(reached) if reached else None
    baseline = [r for r in motor_rows if r["policy"] == "unassisted"]
    calibrated = [r for r in motor_rows if r["policy"] == "calibrated" and r["scenario"] == "nominal_beta_0.8"]
    paired_improvement = [100*(a["retained_rmse"]-b["retained_rmse"])/a["retained_rmse"] for a,b in zip(baseline, calibrated)]
    speed_pairs = [(a,b) for a,b in zip(baseline,calibrated)
                   if a["sessions_to_threshold"] is not None and b["sessions_to_threshold"] is not None]
    motor_summary["paired_retained_error_reduction_percent"] = estimate(paired_improvement)
    motor_summary["threshold_speed_ratio_both_reached_only"] = estimate([a["sessions_to_threshold"]/b["sessions_to_threshold"] for a,b in speed_pairs])
    motor_summary["zero_beta_retention_difference_max"] = float(max(abs(a["retained_rmse"]-b["retained_rmse"]) for a,b in zip(baseline,zero_rows)))
    motor_summary["threshold_speed_ratio_censored_n"] = len(SEEDS)-len(speed_pairs)
    motor_summary["unmodeled_latency"] = {key:estimate([r[key] for r in mismatch_rows]) for key in
                                           ["retained_rmse","first_assisted_rmse","phase_rmse_rad"]}
    print("Motor paired trials and parameter controls finished.", flush=True)

    fig, ax = plt.subplots(2,2, figsize=(12,8.7))
    for policy in policies:
        ys = np.array(curves[policy])
        ax[0,0].plot(np.arange(46), ys.mean(axis=0), label=policy.replace("_", " "), color=COLORS[policy])
        ax[0,0].fill_between(np.arange(46), np.quantile(ys, .1,axis=0), np.quantile(ys,.9,axis=0), color=COLORS[policy], alpha=.08)
    ax[0,0].axhline(motor_config.threshold, color="#0b1424", linestyle=":", label="illustrative threshold")
    ax[0,0].set(xlabel="Practice session", ylabel="Unassisted trajectory RMSE\n(normalized amplitude)", title="A   Learning state under assumed β = 0.8")
    ax[0,0].legend(fontsize=8)
    labels, online = [], []
    for policy in ["unassisted", "calibrated", "uncalibrated", "shuffled"]:
        labels.append(policy.replace("_", "\n"))
        online.append(motor_summary[policy]["first_assisted_rmse"]["mean"])
    ax[0,1].bar(labels, online, color=[COLORS[p] for p in ["unassisted","calibrated","uncalibrated","shuffled"]])
    ax[0,1].set(ylabel="Session 1 trajectory RMSE\n(normalized amplitude)", title="B   Immediate performance with assistance")
    betas = [0,.4,.8,1.2]
    bmean = [np.mean([r["retained_rmse"] for r in beta_rows if r["teaching_beta"] == beta]) for beta in betas]
    ax[1,0].plot(betas, bmean, "o-", color=COLORS["calibrated"], label="calibrated assistance")
    ax[1,0].axhline(np.mean([r["retained_rmse"] for r in baseline]), color=COLORS["unassisted"], linestyle="--", label="unassisted")
    ax[1,0].set(xlabel="Assumed teaching-benefit parameter β", ylabel="Retained unassisted RMSE\n(normalized amplitude)", title="C   Retention depends on the learning assumption")
    ax[1,0].legend(fontsize=8)
    grid = np.array([[np.mean([r["phase_rmse_rad"] for r in sensitivity if r["delay_s"]==delay and r["noise"]==noise]) for noise in [.08,.25,.6]] for delay in [.02,.15,.4]])
    image = ax[1,1].imshow(grid, cmap="YlGnBu", origin="lower", aspect="auto")
    ax[1,1].set(xticks=range(3),xticklabels=[.08,.25,.6], yticks=range(3),yticklabels=[.02,.15,.4],xlabel="Quadrature noise SD (normalized)",ylabel="Known latency (s)",title="D   Phase estimation sensitivity")
    for i in range(3):
        for j in range(3):
            ax[1,1].text(j,i,f"{grid[i,j]:.3f}",ha="center",va="center",color="white" if grid[i,j] > .16 else "#0b1424")
    fig.colorbar(image,ax=ax[1,1],label="Phase RMSE (rad)",shrink=.8)
    fig.suptitle("SCCI_RH motor study | synthetic signals and explicit learning assumptions", fontsize=14, y=.99)
    fig.text(.03,.015,"40 paired synthetic learners; shading = 10–90% simulated learner range. Sensitivity = 12 paired seeds/cell. No biological validation.",fontsize=9)
    fig.tight_layout(rect=[0,.04,1,.96])
    save(fig,"motor_study")

    pressure_rows, pressure_demos, robustness = [], {}, []
    pcfg = PressureConfig()
    for policy in ["unassisted","fixed","closed_loop"]:
        for seed in SEEDS:
            summary, trace = simulate_pressure(seed,policy,pcfg)
            summary["scenario"] = "nominal"
            pressure_rows.append(summary)
            if seed == SEEDS[0]:
                pressure_demos[policy] = trace
    cases = {"low_gain":replace(pcfg,gain_scale=.60), "high_gain":replace(pcfg,gain_scale=1.40),
             "slow_noisy_sensor":replace(pcfg,sensor_delay=1.5,sensor_noise=2.0),
             "actuator_limited":replace(pcfg,output_limit=.65),
             "sensor_faults":replace(pcfg,dropout=True,invalid_sensor=True)}
    fault_trace = None
    for name, config in cases.items():
        for seed in SEEDS:
            sm, trace = simulate_pressure(seed,"closed_loop",config)
            sm["scenario"] = name
            robustness.append(sm)
            if name=="sensor_faults" and seed==SEEDS[0]:
                fault_trace = trace
    write_csv("pressure_trials.csv",pressure_rows)
    write_csv("pressure_robustness.csv",robustness)
    write_trace("pressure_example_trace.csv",pressure_demos["closed_loop"])
    write_trace("pressure_fault_trace.csv",fault_trace)
    pressure_summary = {}
    for policy in ["unassisted","fixed","closed_loop"]:
        rows = [r for r in pressure_rows if r["policy"] == policy]
        pressure_summary[policy] = {key:estimate([r[key] for r in rows]) for key in
                                    ["mae_mmhg","target_band_fraction","saturation_fraction","minimum_mmhg"]}
    pressure_summary["robustness"] = {name: {key:estimate([r[key] for r in robustness if r["scenario"]==name]) for key in
                                               ["mae_mmhg","target_band_fraction","saturation_fraction"]} for name in cases}
    pressure_summary["stale_sensor_nonzero_commands"] = sum(r["stale_nonzero_steps"] for r in robustness if r["scenario"]=="sensor_faults")
    pa = [r for r in pressure_rows if r["policy"]=="unassisted"]
    pb = [r for r in pressure_rows if r["policy"]=="closed_loop"]
    pressure_summary["paired_mae_reduction_percent"] = estimate([100*(a["mae_mmhg"]-b["mae_mmhg"])/a["mae_mmhg"] for a,b in zip(pa,pb)])

    fig, ax = plt.subplots(2,2,figsize=(12,8.7))
    for policy,tr in pressure_demos.items():
        ax[0,0].plot(tr["time_s"],tr["map_mmhg"],label=policy.replace("_"," "),color=COLORS[policy])
    ax[0,0].axhspan(85,95,color="#24c4c7",alpha=.10,label="illustrative ±5 mmHg band")
    ax[0,0].axvline(20,color="#0b1424",ls=":")
    ax[0,0].set(xlabel="Time (s)",ylabel="Synthetic MAP (mmHg)",title="A   Example orthostatic disturbance")
    ax[0,0].legend(fontsize=8,loc="lower right")
    vals = [pressure_summary[p]["mae_mmhg"] for p in ["unassisted","fixed","closed_loop"]]
    means = np.array([v["mean"] for v in vals])
    errs = np.array([[v["mean"]-v["ci95_bootstrap"][0] for v in vals],[v["ci95_bootstrap"][1]-v["mean"] for v in vals]])
    ax[0,1].bar(["unassisted","fixed input","closed loop"],means,yerr=errs,capsize=4,color=[COLORS[p] for p in ["unassisted","fixed","closed_loop"]])
    ax[0,1].set(ylabel="MAP mean absolute error (mmHg)",title="B   Forty paired synthetic plants")
    ax[1,0].plot(fault_trace["time_s"],fault_trace["map_mmhg"],color=COLORS["closed_loop"])
    ax[1,0].axhspan(85,95,color="#24c4c7",alpha=.10)
    ax[1,0].axvspan(75,88,color="#be7c28",alpha=.15,label="sensor absent")
    ax[1,0].axvspan(105,110,color="#b7485d",alpha=.12,label="invalid + recovery wait")
    ax[1,0].set(xlabel="Time (s)",ylabel="Synthetic MAP (mmHg)",title="C   Fault inhibition sacrifices regulation")
    ax[1,0].legend(fontsize=8)
    twin=ax[1,0].twinx()
    twin.plot(fault_trace["time_s"],fault_trace["command"],color="#be7c28",alpha=.8,lw=1)
    twin.set(ylabel="Normalized command (0–1)",ylim=(0,1.1))
    robnames=list(cases)
    robmeans=[pressure_summary["robustness"][name]["mae_mmhg"]["mean"] for name in robnames]
    ax[1,1].barh(["low gain (×0.6)","high gain (×1.4)","slow/noisy sensor","actuator cap 0.65","sensor faults"],robmeans,color="#087f89")
    ax[1,1].set(xlabel="MAP mean absolute error (mmHg)",title="D   Gain, sensing and authority limits")
    fig.suptitle("SCCI_RH physiological-control study | external MAP sensor and synthetic plant",fontsize=14,y=.99)
    fig.text(.03,.015,"40 paired seeds/case; error bars = bootstrap 95% intervals across synthetic plants. Normalized actuation is not a stimulation dose.",fontsize=9)
    fig.tight_layout(rect=[0,.04,1,.96])
    save(fig,"pressure_study")
    metadata={"study_type":"fully synthetic conditional engineering simulation", "master_seeds":SEEDS,
              "bootstrap_seed":20261007,"bootstrap_replicates":2000,
              "motor_config":asdict(motor_config),"pressure_config":asdict(pcfg),
              "pressure_robustness_configs":{k:asdict(v) for k,v in cases.items()},
              "python":platform.python_version(),"numpy":np.__version__,"matplotlib":matplotlib.__version__,
              "confidence_interval_scope":"Monte Carlo variability in chosen synthetic population; excludes biological model uncertainty"}
    (RESULTS/"study_metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    combined={"motor":motor_summary,"pressure":pressure_summary,"claims":"conditional synthetic results; no clinical or biological validation"}
    (RESULTS/"summary.json").write_text(json.dumps(combined,indent=2),encoding="utf-8")
    print(json.dumps({"motor_retained_error_reduction_percent":motor_summary["paired_retained_error_reduction_percent"],
                      "motor_speed_ratio_conditional":motor_summary["threshold_speed_ratio_both_reached_only"],
                      "zero_beta_retention_difference":motor_summary["zero_beta_retention_difference_max"],
                      "pressure_mae_reduction_percent":pressure_summary["paired_mae_reduction_percent"],
                      "stale_sensor_nonzero_commands":pressure_summary["stale_sensor_nonzero_commands"]},indent=2),flush=True)


if __name__=="__main__":
    main()
