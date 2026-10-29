"""Application traces -> actual C pulse backend -> ideal PHASE/INHIBIT trace.

This is a digital protocol demonstration. Mapping normalized actuation to pulse
frequency is illustrative; no tissue or plant response is inferred from current.
"""
from pathlib import Path
import sys
import json
import csv
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from scci_rh.pulse_binding import PulseBackend


def read_csv(name):
    with (ROOT/"results"/name).open(encoding="utf-8") as f:
        return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--library")
    args=parser.parse_args()
    candidates=list((ROOT/"build"/"firmware").glob("*scci_rh_pulse.*"))
    candidates=[p for p in candidates if p.suffix in [".dll",".so",".dylib"]]
    library=args.library or (str(candidates[0]) if candidates else None)
    if not library: parser.error("Build the C library with scripts/build_firmware.py first.")
    events=[]
    requests=[]
    accepted_counts={}
    checks={"powerup_off":True,"no_pulses_without_valid_sensor":True,"balanced_each_pulse":True,
            "max_frequency_50hz":True,"bounded_nominal_segments":True,"phase_inhibit_consistent":True,
            "stale_request_rejected":True}
    for application in ["pressure","motor"]:
        backend=PulseBackend(library)
        checks["powerup_off"] &= backend.controller.output.current_ua==0 and not backend.start(0)
        rows=read_csv("pressure_fault_trace.csv" if application=="pressure" else "motor_example_trace.csv")
        starts=[]
        next_start=0
        activity=0.0
        old_phase=None
        count=0
        for i,row in enumerate(rows):
            now=int(round(row["time_s"]*1e6))
            interval_end=int(round(rows[i+1]["time_s"]*1e6)) if i+1<len(rows) else now
            if application=="pressure":
                fresh=bool(row["sensor_available"]) and not bool(row["sensor_stale"])
                # Both external BP availability and application-level inhibition gate pulses.
                activity=float(np.clip(row["command"],0,1))
                abstract_command=row["command"]
                period=max(20000,int(round(1e6/(50*max(activity,1e-9)))))
                if activity>0 and fresh:
                    request_times=list(range(max(now,next_start),interval_end,period))
                elif activity>0:
                    request_times=[now]  # Deliberate attempt to exercise compiled inhibition.
                else:
                    request_times=[]
            else:
                fresh=row["time_s"]>=2
                phase=row["estimated_phase_rad"]
                crossed=old_phase is not None and np.floor(phase/(2*np.pi))>np.floor(old_phase/(2*np.pi))
                old_phase=phase
                abstract_command=row["assisted"]-row["unassisted"]
                activity=float(min(1,abs(abstract_command)))
                request_times=[now] if crossed and fresh and now>=next_start else []
            if fresh:
                backend.sensor(now,True)
                # The digital demo automatically rearms only when application data are declared fresh.
                backend.rearm(now)
            else:
                backend.poll(now)
                backend.sensor(now,False)
            for now in request_times:
                accepted=backend.start(now)
                requests.append({"application":application,"time_us":now,"abstract_command":abstract_command,
                                 "normalized_activity":activity,"sensor_fresh":int(fresh),"accepted":int(accepted),
                                 "firmware_fault":int(backend.controller.fault)})
                if accepted:
                    checks["no_pulses_without_valid_sensor"] &= fresh
                    if starts: checks["max_frequency_50hz"] &= now-starts[-1]>=20000
                    starts.append(now)
                    segments=backend.finish_segments()
                    charge=sum(current*duration for current,duration,_ in segments)
                    checks["balanced_each_pulse"] &= charge==0
                    checks["bounded_nominal_segments"] &= segments==[(100,200,1),(0,50,2),(-100,200,3),(0,19550,4)]
                    offset=0
                    for current,duration,state in segments:
                        inhibit=int(current==0)
                        # Circuit convention: PHASE=0 positive; PHASE=1 negative; INHIBIT=1 output off.
                        phase_pin=int(state in (2,3))  # Prepare reversal during inhibited gap.
                        decoded_current=0 if inhibit else 100*(1-2*phase_pin)
                        checks["phase_inhibit_consistent"] &= decoded_current==current
                        events.append({"application":application,"pulse_id":count,"start_us":now+offset,
                                       "duration_us":duration,"current_ua":current,"phase_pin":phase_pin,
                                       "inhibit_pin":inhibit,"abstract_command":abstract_command,
                                       "normalized_activity":activity,"state":state,"ideal_net_pulse_charge_nc":charge/1000})
                        offset+=duration
                    count+=1
                    # No new request can arrive before the C recovery interval finishes.
                    period=20000 if application=="motor" else max(20000,int(round(1e6/(50*max(activity,1e-9)))))
                    next_start=now+period
        accepted_counts[application]=count
        # Forced stale-data attempt tests the compiled C gate rather than trusting trace suppression.
        backend.sensor(0,True)
        backend.rearm(0)
        checks["stale_request_rejected"] &= not backend.start(100001)
    if not all(checks.values()): raise AssertionError(checks)
    for filename,data in [("application_pulse_events.csv",events),("application_pulse_requests.csv",requests)]:
        with (ROOT/"results"/filename).open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    result={"status":"passed","checks":checks,"accepted_pulses":accepted_counts,
            "source":"ctypes calls into the compiled scci_rh_pulse.c shared library",
            "pressure_mapping":"requested frequency = 50 * normalized command Hz with piecewise-held application commands and integer-us scheduling",
            "motor_mapping":"one pulse request per increasing surrogate phase crossing after warm-up; signed correction is logged only",
            "scope":"ideal digital protocol; no fitted stimulation-to-physiology or stimulation-to-learning conversion",
            "sensor_source":"external pressure availability for BP; generated quadrature after estimator warm-up for motor"}
    (ROOT/"results"/"adapter_validation.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True)
    xs=[0,200,250,450,700]
    axes[0].step(xs,[100,0,-100,0,0],where="post",color="#087f89",linewidth=2)
    axes[0].set(ylabel="Ideal current (µA)",title="A   Fixed biphasic test-load command")
    axes[0].axhline(0,color="#60768d",lw=.7)
    axes[1].plot(xs,[0,20,20,0,0],color="#be7c28",linewidth=2)
    axes[1].set(ylabel="Signed accumulated charge (nC)",title="B   Equal ideal phase areas cancel")
    axes[2].step(xs,[0,1,1,0,0],where="post",label="PHASE",color="#087f89",linewidth=2)
    axes[2].step(xs,[0,1,0,1,1],where="post",label="INHIBIT",color="#be7c28",linewidth=2)
    axes[2].set(xlabel="Time within pulse (µs)",ylabel="Digital pin state",yticks=[0,1],ylim=(-.15,1.15),title="C   Declared switching interface")
    axes[2].legend(loc="upper right")
    for ax in axes:
        ax.spines["top"].set_visible(False);ax.spines["right"].set_visible(False)
        ax.grid(alpha=.15)
        ax.axvspan(200,250,color="#60768d",alpha=.10)
    fig.suptitle("SCCI_RH application-to-pulse adapter | ideal C timing and digital routing",fontsize=14)
    fig.text(.05,.012,"100 µA × 200 µs = 20 nC per phase; nominal repetition ≤50 Hz. No measured analog/tissue charge or biological dose mapping.",fontsize=9)
    fig.tight_layout(rect=[0,.035,1,.965])
    (ROOT/"figures").mkdir(exist_ok=True)
    fig.savefig(ROOT/"figures"/"pulse_protocol.png",dpi=200,bbox_inches="tight")
    fig.savefig(ROOT/"figures"/"pulse_protocol.svg",bbox_inches="tight")
    plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=="__main__": main()
