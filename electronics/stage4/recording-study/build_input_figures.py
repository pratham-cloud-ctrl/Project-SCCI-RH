"""Render saved passive-network results only; no model regeneration."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "input-results.json").read_text(encoding="utf-8"))
rows = {r["case"]: r for r in data["transient"]}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "svg.hashsalt": "scci_rh-recording-network-20261013"})
fig, axes = plt.subplots(2, 2, figsize=(11.4, 7.5), layout="constrained")
for case, label in (("nominal_positive", "Positive input"), ("nominal_reference", "Shared reference"), ("feedthrough_10pF", "10 pF transfer stress")):
    with np.load(HERE / rows[case]["trace"]) as tr:
        a = tr["trace"]
    axes[0, 0].plot(a[:, 0]*1e3, a[:, 2]*1e3, label=label)
axes[0, 0].set(xlim=(0, 2.4), xlabel="Time (ms)", ylabel="AFE pin (mV)", title="Blank, reconnect while clamped, then release")
axes[0, 0].legend(fontsize=8)
for case, label in (("injection_100pC", "100 pC"), ("qualification_offset_100pC", "0.3 V offset / 100 pC"), ("injection_300pC", "300 pC failure")):
    with np.load(HERE / rows[case]["trace"]) as tr:
        a = tr["trace"]
    pick = a[:, 3] == 5
    axes[0, 1].plot((a[pick, 0]-2e-3)*1e6, a[pick, 2], label=label)
axes[0, 1].axhline(.4, color="#b44a3a", linestyle="--", label="DC envelope boundary")
axes[0, 1].set(xlim=(0, 120), xlabel="Time after release (microseconds)", ylabel="AFE pin (V)", title="Charge injection is an explicit model stress")
axes[0, 1].legend(fontsize=8)
q = [r for r in data["quiet"] if r["native_added_capacitance"]]
axes[1, 0].bar(["Nominal", "High Z", "Adverse", "Reference high Z"], [r["coherent_snr_10uV_dB"] for r in q], color=["#bc624d"]*4)
axes[1, 0].axhline(10, color="black", linestyle="--", label="Conditional 10 dB allocation")
axes[1, 0].set(ylabel="10 microvolt / 50 Hz source SNR (dB)", title="Coherent common-mode bound fails the 10 dB gate")
axes[1, 0].tick_params(axis="x", labelrotation=12)
axes[1, 0].legend(fontsize=8)
t = np.linspace(0, 7, 500)
axes[1, 1].semilogy(t, .2*np.exp(-2*np.pi*.1*t)*1e3, color="#2b8290")
axes[1, 1].axhline(5, color="black", linestyle="--", label="5 mV AC linear range")
axes[1, 1].set(xlabel="Time (seconds)", ylabel="Ideal high-pass step residual (mV)", title="Passive pin settling does not establish AFE recovery")
axes[1, 1].legend(fontsize=8)
for ax in axes.flat:
    ax.grid(axis="y", alpha=.15)
fig.suptitle("SCCI_RH recording input network - finite passive model, not implant validation", fontsize=13)
fig.savefig(HERE / "input-network.png", dpi=180)
fig.savefig(HERE / "input-network.svg", metadata={"Date": None})
svg = HERE / "input-network.svg"
svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
print("Saved recording-network figure pair")
