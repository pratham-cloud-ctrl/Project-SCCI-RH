"""Render saved finite route parasitics; does not regenerate evidence."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
data=json.loads((HERE/"parasitic-results.json").read_text(encoding="utf-8"))
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False,"svg.hashsalt":"scci_rh-router-20261013"})
fig,axs=plt.subplots(1,2,figsize=(11,4.6),layout="constrained")
with np.load(HERE/"parasitic-traces.npz") as traces:
    for pattern,label in (("aligned","Aligned edges"),("opposed_matched","Opposed / matched"),("opposed_asymmetric","Opposed / unequal"),("staggered","Staggered")):
        r=next(r for r in data["rows"] if r["contact_capacitance_F_assumed"]==1e-9 and r["bus0_mutual_F_assumed"]==15e-12 and r["pattern"]==pattern)
        a=traces[r["trace_key"]]
        axs[0].plot(a[:,0]*1e3,a[:,1],label=label)
axs[0].set(xlim=(0,1.2),xlabel="Time (ms)",ylabel="Unselected contact (V)",title="Off commands permit capacitive edge coupling")
axs[0].legend(fontsize=8)
xs=np.arange(3)
for j,(pattern,label) in enumerate((("aligned","Aligned"),("opposed_asymmetric","Opposed unequal"),("staggered","Staggered"))):
    rows=[next(r for r in data["rows"] if r["contact_capacitance_F_assumed"]==c and r["bus0_mutual_F_assumed"]==15e-12 and r["pattern"]==pattern) for c in (1e-9,100e-9,2e-6)]
    axs[1].bar(xs+(j-1)*.24,[r["max_abs_victim_V"]*1000 for r in rows],width=.24,label=label)
axs[1].set_yscale("log")
axs[1].set_xticks(xs,["1 nF","100 nF","2 microfarads"])
axs[1].set(xlabel="Assumed contact-to-body capacitance",ylabel="Peak unselected voltage (mV)",title="Contact impedance changes the consequence")
axs[1].legend(fontsize=8)
for ax in axs:ax.grid(axis="y",alpha=.15)
fig.suptitle("SCCI_RH routing study - assumed mutual capacitance; no tissue or switch-fault validation",fontsize=12)
fig.savefig(HERE/"router-parasitics.png",dpi=180)
fig.savefig(HERE/"router-parasitics.svg",metadata={"Date":None})
svg=HERE/"router-parasitics.svg"
svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines())+"\n",encoding="utf-8")
print("Saved router-parasitic figure pair")
