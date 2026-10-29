"""Render scientific figures from saved evidence; no solver or qualification."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
RUNS = {r["case"]: r for r in DATA["runs"] if r["max_step_s"] == min(DATA["grids_s"])}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .18, "axes.axisbelow": True,
                     "figure.facecolor": "white", "savefig.facecolor": "white"})
COLORS = ["#235789", "#b85b22"]

def save(fig, name):
    fig.savefig(HERE / (name + ".png"), dpi=180)
    # Stable SVG IDs and no creation timestamp: source-driven export.
    with matplotlib.rc_context({"svg.hashsalt": "scci_rh-monitoring-study-v1"}):
        fig.savefig(HERE / (name + ".svg"), metadata={"Date": None})
    plt.close(fig)

def decimate(length, target=7000):
    return np.unique(np.r_[np.arange(0, length, max(1, length // target)), length - 1])

fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
nominal = RUNS["nominal"]
with np.load(HERE / nominal["trace_file"]) as trace:
    t = trace["time_s"] * 1e6
    d = decimate(len(t))
    for source, color in enumerate(COLORS):
        prefix = f"source{source}_"
        axes[0, 0].plot(t[d], trace[prefix+"Iload_A"][d]*1e3, color=color, label=f"Source {source}")
        axes[0, 1].plot(t[d], trace[prefix+"ADC_input_V"][d], color=color, label=f"Source {source}")
        channel = nominal["channels"][source]
        for name in ("baseline", "phase1_tail", "phase2_tail", "late_tail"):
            sample = channel["samples"][name]
            axes[0, 1].plot(sample["aperture_s"]*1e6, sample["raw_input_V"], "o", ms=4, color=color)
axes[0, 0].set(title="Nominal: two imposed load currents", ylabel="Load current (mA)", xlim=(150, 1100))
axes[0, 1].set(title="Nominal: cumulative charge observations", ylabel="ADC input (V)", xlim=(150, 1100))
axes[0, 0].legend(frameon=False)
axes[0, 1].legend(frameon=False)

fault = RUNS["clipping_guard_bypassed"]
with np.load(HERE / fault["trace_file"]) as trace:
    t = trace["time_s"] * 1e6
    d = decimate(len(t))
    for source, color in enumerate(COLORS):
        axes[1, 0].plot(t[d], trace[f"source{source}_integrator_V"][d], color=color, label=f"Source {source}")
        axes[1, 1].plot(t[d], trace[f"source{source}_ADC_input_V"][d], color=color, label=f"Source {source}")
axes[1, 0].axhline(.05, color="#777777", linestyle="--", linewidth=1)
axes[1, 0].axhline(4.95, color="#777777", linestyle="--", linewidth=1, label="Assumed model rails")
axes[1, 1].axhline(4.096, color="#9f2525", linestyle="--", linewidth=1.5, label="ADC measurement maximum")
axes[1, 1].axhline(0, color="#9f2525", linestyle="--", linewidth=1)
axes[1, 0].set(title="Deliberate 40 mA fault: lost integrator history", ylabel="Integrator output (V)", xlim=(150, 1700))
axes[1, 1].set(title="Deliberate fault: ADC over-range witness", ylabel="ADC input (V)", xlim=(150, 1700))
axes[1, 0].legend(frameon=False, fontsize=8, loc="center right")
axes[1, 1].legend(frameon=False, fontsize=8, loc="center right")
for ax in axes.flat:
    ax.set_xlabel("Time (µs)")
fig.suptitle("SCCI_RH Stage 4 • Behavioral monitor transients", fontsize=17, weight="bold")
fig.supxlabel("Assumed models on artificial loads; clipping continuation does not predict device survival or shutdown actuation.", fontsize=9)
save(fig, "waveforms")

fig, axes = plt.subplots(1, 2, figsize=(12, 5.7), layout="constrained")
labels = ["Nominal", "Load-side\n45 µA", "Prebaseline\n6 pC", "Differential\n6 pC", "Slow\nresponse"]
names = ["nominal", "load_side_bias_45uA", "reset_open_6pC", "differential_injection_6pC", "slow_response"]
first_errors, second_errors = [], []
for name in names:
    intervals = {x["name"]: x for x in RUNS[name]["channels"][0]["intervals"]}
    first_errors.append(intervals["observed_first"]["raw_error_vs_load_C"]*1e9)
    second_errors.append(intervals["observed_second_includes_gap"]["raw_error_vs_load_C"]*1e9)
x = np.arange(len(names))
axes[0].bar(x-.18, first_errors, width=.36, color=COLORS[0], label="First observed interval")
axes[0].bar(x+.18, second_errors, width=.36, color=COLORS[1], label="Second interval (includes gap)")
axes[0].axhline(0, color="#666666", linewidth=.8)
axes[0].set(xticks=x, xticklabels=labels, ylabel="Endpoint estimate − actual interval load charge (nC)",
            title="Source 0: interval errors remain distinct")
axes[0].legend(frameon=False, fontsize=8)

intervals = {x["name"]: x for x in RUNS["unequal_cancellation"]["channels"][0]["intervals"]}
values = [intervals[n]["raw_endpoint_charge_C"]*1e9 for n in ("observed_first", "observed_second_includes_gap", "settled_net")]
bars = axes[1].bar([0, 1, 2], values, color=[COLORS[0], COLORS[1], "#47865f"], width=.6)
axes[1].axhspan(-24, 24, color="#47865f", alpha=.15, label="±24 nC around zero")
axes[1].axhline(-600, color=COLORS[0], linestyle="--", linewidth=1)
axes[1].axhline(600, color=COLORS[1], linestyle="--", linewidth=1, label="Nominal ±600 nC phase targets")
axes[1].set(xticks=[0, 1, 2], xticklabels=["First observed", "Second + gap", "Final net"],
            ylabel="Signed endpoint estimate (nC)", title="Cancellation: small net conceals large phases", ylim=(-1450, 1500))
for bar, value in zip(bars, values):
    axes[1].text(bar.get_x()+bar.get_width()/2, value+(55 if value>=0 else -80), f"{value:+.2f}", ha="center", fontsize=10)
axes[1].legend(frameon=False, fontsize=8, loc="upper left")
fig.suptitle("SCCI_RH Stage 4 • Charge attribution counterexamples", fontsize=17, weight="bold")
fig.supxlabel("Finest grid: 25 ns. Raw analog endpoints before quantization. Numerical agreement does not earn the proposed 4% bound.", fontsize=9)
save(fig, "charge-witnesses")
