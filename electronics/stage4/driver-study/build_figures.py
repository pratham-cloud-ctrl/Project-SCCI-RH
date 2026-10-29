"""Illustrate saved driver traces only; no circuit or evidence regeneration."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
data=json.loads((HERE/"results.json").read_text(encoding="utf-8"))
fine={r["case"]:r for r in data["runs"] if r["maximum_step_s"]==min(data["grids_s"])}
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,
                    "axes.spines.top":False,"axes.spines.right":False,
                    "svg.hashsalt":"scci_rh-driver-20261013"})

fig,axes=plt.subplots(2,1,figsize=(10,6.6),layout="constrained")
row=fine["nominal"]
with np.load(HERE/row["trace"]) as tr:
    t=tr["time"]
    load=(tr["v(a0)"]-tr["v(pol0)"])/1000
    sink=tr["v(sense0)"]/100
    # Keep all extrema as well as uniform display points; raw arrays are saved.
    pick=np.unique(np.r_[np.linspace(0,len(t)-1,1800).astype(int),np.argmax(load),np.argmin(load)])
    axes[0].plot(t[pick]*1e6,load[pick]*1000,label="Signed load current")
    axes[0].plot(t[pick]*1e6,sink[pick]*1000,label="Unsigned feedback-leg current",alpha=.8)
axes[0].set(xlim=(350,1000),xlabel="Time (microseconds)",ylabel="Current (mA)",
            title="Nominal surrogate: regulated plateaus and switching edges")
axes[0].legend(fontsize=9,ncol=2)
axes[0].annotate("Model edge peak: 23.724 mA",xy=(400,23.724),xytext=(485,18),
                 arrowprops={"arrowstyle":"->","color":"#555"},fontsize=9)
names=["nominal","high_load","slow_servo_stress","feedback_reset_stuck_active", "feedback_early_200ns","monitor_bias_both_45uA","common_mode_cap_1nF","sink_short_inhibit_25us","long_request_healthy_timer"]
labels=["Nominal","High load","Slow servo","Reset stuck","200 ns skew","Bias paths","1 nF CM","Sink short","Timer max"]
values=[fine[n]["channels"][0]["intervals"][0]["load_charge_C"]*1e9 for n in names]
axes[1].bar(labels,values,color=["#2b8290"]*7+["#bc624d"]*2)
axes[1].axhline(600,color="black",linestyle="--",linewidth=1,label="Nominal command charge")
axes[1].tick_params(axis="x",labelrotation=28)
axes[1].set(ylabel="First-phase load charge (nC)",title="Selected model stresses; source 0, 25 ns maximum step")
axes[1].legend(fontsize=8)
for ax in axes:ax.grid(axis="y",alpha=.15)
fig.suptitle("SCCI_RH driver study - behavioral model, not component validation",fontsize=13)
fig.savefig(HERE/"driver-waveforms.png",dpi=180)
fig.savefig(HERE/"driver-waveforms.svg",metadata={"Date":None})
plt.close(fig)

fig,ax=plt.subplots(figsize=(9,4.4),layout="constrained")
names=["nominal","monitor_bias_both_45uA","common_mode_cap_1nF"]
labels=["Nominal (1 pF)","Two 45 microamp bias paths","1 nF return capacitance"]
positions=np.arange(3)
for i,(index,label,color) in enumerate(((0,"First phase","#2b8290"),(2,"Second phase","#bc624d"))):
    vals=[]
    for n in names:
        w=fine[n]["channels"][0]["intervals"][index]
        vals.append((w["load_charge_C"]-w["signed_shunt_charge_C"])*1e9)
    ax.bar(positions+(i-.5)*.3,vals,width=.3,label=label,color=color)
ax.set_xticks(positions,labels)
ax.set(ylabel="Load charge minus return-shunt charge (nC)",
       title="A calibrated sink and a return shunt observe different current paths")
ax.legend(fontsize=9)
ax.grid(axis="y",alpha=.15)
fig.savefig(HERE/"driver-charge-paths.png",dpi=180)
fig.savefig(HERE/"driver-charge-paths.svg",metadata={"Date":None})
plt.close(fig)
print("Two saved-data figure pairs generated; incomplete compliance stress excluded from phase bars.")
