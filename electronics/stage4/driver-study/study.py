"""Restricted artificial-load driver model, not vendor/component qualification.

The behavioral opamp and level-1 MOSFET expose a closed servo, bridge path,
Kelvin feedback, load polarization and independent return shunt. Native gates
are investigated separately; these analog controls are explicit fixture inputs.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "monitoring-study"))
from ngspice_shared import SharedNgspice, find_library

GRIDS = (100e-9, 25e-9)
STOP = 1.4e-3
VSET = 7864 * 2.5 / 65536


@dataclass(frozen=True)
class Case:
    name: str
    pair_R_ohm: float = 1000.0
    polarization_C_F: float = 2e-6
    initial_polarization_V: float = 0.0
    opamp_ugb_Hz: float = 10e6
    opamp_slew_V_per_s: float = 20e6
    gate_cap_F: float = 70e-12
    feedback_stuck_active: bool = False
    feedback_early_s: float = 0.0
    bias_load_A: float = 0.0
    bias_bridge_A: float = 0.0
    common_mode_C_F: float = 1e-12
    sink_short: bool = False
    forced_inhibit_at_s: float = 10.0
    phase_s: float = 200e-6


CASES = (
    Case("nominal"),
    Case("high_load", pair_R_ohm=2000, polarization_C_F=0.5e-6, initial_polarization_V=1),
    Case("forced_beyond_compliance", pair_R_ohm=10000),
    Case("slow_servo_stress", opamp_ugb_Hz=1e6, opamp_slew_V_per_s=2e6, gate_cap_F=500e-12),
    Case("feedback_reset_stuck_active", feedback_stuck_active=True),
    Case("feedback_early_200ns", feedback_early_s=200e-9),
    Case("monitor_bias_both_45uA", bias_load_A=45e-6, bias_bridge_A=45e-6),
    Case("common_mode_cap_1nF", common_mode_C_F=1e-9),
    Case("sink_short_inhibit_25us", pair_R_ohm=500, sink_short=True, forced_inhibit_at_s=425e-6),
    Case("long_request_healthy_timer", phase_s=235.159981e-6),
)


def sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix not in (".npz", ".png"):
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def pulse(a, b, *, shift=0.0):
    # Finite 1 ns fixture edges, not manufacturer worst-case switching times.
    a += shift
    b += shift
    return f"PWL(0 0 {a:.15g} 0 {a+1e-9:.15g} 3.3 {b:.15g} 3.3 {b+1e-9:.15g} 0)"


def window(c: Case, source: int):
    start = 400e-6 + source * 25e-6
    # The restricted timer window is per phase. A fixture inhibit is immediate
    # at its supplied time; actual guard detection/propagation is not simulated.
    first_end = min(start + c.phase_s, c.forced_inhibit_at_s)
    second_start = start + c.phase_s + 100e-6
    second_end = min(second_start + c.phase_s, c.forced_inhibit_at_s)
    return start, max(start, first_end), second_start, max(second_start, second_end)


def circuit(c: Case, step: float):
    lines = ["SCCI_RH S4 restricted closed-loop current-driver surrogate",
             "Vhv hv 0 24", f"Vset set 0 {VSET:.15g}",
             ".model BR SW(Ron=10 Roff=1e12 Vt=1.65 Vh=0)",
             ".model MX SW(Ron=2 Roff=1e12 Vt=1.65 Vh=0)",
             ".model FET NMOS(Level=1 Vto=1.3 Kp=0.05 Lambda=0.005)",
             ".model CLAMP D(Is=1e-12 N=1 Rs=1)"]
    vectors = []
    for source in (0, 1):
        s = str(source)
        a, b, d, e = window(c, source)
        valid_first, valid_second = b > a, e > d
        lines += [f"Vplus{s} cp{s} 0 " + (pulse(a, b) if valid_first else "0"),
                  f"Vminus{s} cm{s} 0 " + (pulse(d, e) if valid_second else "0"),
                  f"Brun{s} run{s} 0 V={{max(v(cp{s}),v(cm{s}))}}",
                  f"Boff{s} off{s} 0 V={{3.3-v(run{s})}}"]
        if c.feedback_stuck_active:
            lines += [f"Vfbctl{s} fc{s} 0 3.3"]
        elif c.feedback_early_s:
            # Feedback selects active 200 ns before gate release; fixture only.
            pa = pulse(a, b, shift=-c.feedback_early_s) if valid_first else "0"
            pb = pulse(d, e, shift=-c.feedback_early_s) if valid_second else "0"
            lines += [f"Vfa{s} fa{s} 0 {pa}", f"Vfb{s} fx{s} 0 {pb}",
                      f"Bfbctl{s} fc{s} 0 V={{max(v(fa{s}),v(fx{s}))}}"]
        else:
            lines += [f"Bfbctl{s} fc{s} 0 V={{v(run{s})}}"]
        lines += [f"Bfboff{s} foff{s} 0 V={{3.3-v(fc{s})}}",
                  f"S1_{s} hv a{s} cp{s} 0 BR", f"S4_{s} dr{s} br{s} cp{s} 0 BR",
                  f"S2_{s} hv br{s} cm{s} 0 BR", f"S3_{s} dr{s} a{s} cm{s} 0 BR",
                  f"Rpair{s} a{s} pol{s} {c.pair_R_ohm:.15g}",
                  f"Cpol{s} pol{s} ret{s} {c.polarization_C_F:.15g} IC={c.initial_polarization_V:.15g}",
                  f"Rpol{s} pol{s} ret{s} 100k", f"Rshunt{s} ret{s} br{s} 2",
                  f"Rfeedback{s} sense{s} 0 100", f"Rgate{s} muxg{s} gate{s} 330",
                  f"Rpull{s} gate{s} 0 100k", f"Cgs{s} gate{s} sense{s} {c.gate_cap_F:.15g}",
                  f"Cgd{s} gate{s} dr{s} 10p", f"Cds{s} dr{s} sense{s} 1.2p",
                  f"Sgate_on{s} amp{s} muxg{s} run{s} 0 MX", f"Sgate_off{s} 0 muxg{s} off{s} 0 MX",
                  f"Sfeedback_on{s} sense{s} fb{s} fc{s} 0 MX",
                  f"Sfeedback_off{s} amp{s} fb{s} foff{s} 0 MX",
                  f"Cinput{s} fb{s} 0 5p IC={VSET:.15g}", f"Rinput{s} fb{s} 0 1e9",
                  f"IBload{s} ret{s} 0 {c.bias_load_A:.15g}",
                  f"IBbridge{s} br{s} 0 {c.bias_bridge_A:.15g}",
                  f"Ccommon{s} ret{s} 0 {c.common_mode_C_F:.15g} IC=0",
                  f"Rret{s} ret{s} 0 1e12", f"Rdr{s} dr{s} 0 1e12", f"Ra{s} a{s} 0 1e12"]
        if c.sink_short:
            lines += [f"Rshort{s} dr{s} sense{s} 0.05"]
        else:
            lines += [f"Mdriver{s} dr{s} gate{s} sense{s} sense{s} FET W=1 L=1"]
        # A one-pole, finite-gain, slew/rail-limited behavioral amplifier. None
        # of these equations is the OPA192 vendor macro model.
        rate = f"(max(-{c.opamp_slew_V_per_s:.15g},min({c.opamp_slew_V_per_s:.15g},{2*np.pi*c.opamp_ugb_Hz:.15g}*(v(set)-v(fb{s}))))-{2*np.pi*c.opamp_ugb_Hz/1e5:.15g}*v(state{s}))"
        bounded = f"(v(state{s})>14.95 ? min(0,{rate}) : (v(state{s})<0.05 ? max(0,{rate}) : {rate}))"
        lines += [f"Bamp{s} 0 state{s} I={{1e-9*{bounded}}}",
                  f"Cdom{s} state{s} 0 1n IC={VSET:.15g}",
                  f"Bout{s} amp{s} 0 V={{max(0.05,min(14.95,v(state{s})))}}"]
        for node in (f"a{s}", f"br{s}", f"dr{s}"):
            lines += [f"Dhi_{node} {node} hv CLAMP", f"Dlo_{node} 0 {node} CLAMP"]
        vectors += [f"v({n}{s})" for n in ("a", "pol", "ret", "br", "dr", "sense", "gate", "amp", "run")]
    lines += [".options reltol=1e-8 abstol=1e-13 vntol=1e-10 method=gear",
              ".save " + " ".join(vectors), f".tran {step:.15g} {STOP:.15g} 0 {step:.15g} UIC", ".end"]
    return lines, vectors


def integral(t, y, a, b):
    inside = (t > a) & (t < b)
    tt = np.r_[a, t[inside], b]
    yy = np.r_[np.interp(a, t, y), y[inside], np.interp(b, t, y)]
    return float(np.trapezoid(yy, tt))


def analyze(c, step, data):
    t = data["time"]
    channels = []
    for source in (0, 1):
        s = str(source)
        load = (data[f"v(a{s})"] - data[f"v(pol{s})"]) / c.pair_R_ohm
        shunt = (data[f"v(ret{s})"] - data[f"v(br{s})"]) / 2
        sink = data[f"v(sense{s})"] / 100
        a, b, d, e = window(c, source)
        records = []
        for name, start, stop in (("first", a, b), ("gap", b, d),
                                  ("second", d, e), ("whole_profile", a, min(STOP, e+300e-6))):
            qload = integral(t, load, start, stop)
            qshunt = integral(t, shunt, start, stop)
            qcap = c.common_mode_C_F * (np.interp(stop, t, data[f"v(ret{s})"]) - np.interp(start, t, data[f"v(ret{s})"]))
            residual = qload - qshunt - c.bias_load_A * (stop-start) - qcap
            records.append(dict(interval=name, start_s=start, end_s=stop,
                                load_charge_C=qload, signed_shunt_charge_C=qshunt,
                                unsigned_feedback_charge_C=integral(t,sink,start,stop),
                                return_cap_charge_C=float(qcap), integrated_return_KCL_residual_C=float(residual)))
        active = (t > a+30e-6) & (t < b-20e-6)
        settled = None if not active.any() else float(np.median(load[active]))
        channels.append(dict(source=source, maximum_load_current_A=float(np.max(np.abs(load))),
                             maximum_shunt_current_A=float(np.max(np.abs(shunt))),
                             settled_first_current_A=settled,
                             final_polarization_V=float(data[f"v(pol{s})"][-1]-data[f"v(ret{s})"][-1]),
                             intervals=records))
    return dict(case=c.name, maximum_step_s=step, samples=len(t), channels=channels)


def run(only=None):
    engine = SharedNgspice(find_library())
    results = []
    (HERE / "netlists").mkdir(exist_ok=True)
    (HERE / "traces").mkdir(exist_ok=True)
    for c in CASES:
        if only and c.name != only:
            continue
        for step in GRIDS:
            name = f"{c.name}-{round(step*1e9):d}ns"
            lines, vectors = circuit(c, step)
            data, messages = engine.run(lines, vectors)
            (HERE / "netlists" / (name + ".cir")).write_text("\n".join(lines)+"\n", encoding="utf-8", newline="\n")
            np.savez_compressed(HERE / "traces" / (name + ".npz"), **data)
            completed = bool(data["time"][-1] >= STOP * 0.999)
            row = analyze(c, step, data) if completed else dict(
                case=c.name, maximum_step_s=step, samples=len(data["time"]),
                channels=[], solver_failure_retained=True, last_time_s=float(data["time"][-1]))
            row["completed"] = completed
            row["trace"] = "traces/" + name + ".npz"
            row["netlist"] = "netlists/" + name + ".cir"
            row["engine_warning_or_error_lines"] = [m for m in messages if "error" in m.lower() or "warning" in m.lower()]
            results.append(row)
            print(name, "samples",len(data["time"]), "first Q/nC",
                  results[-1]["channels"][0]["intervals"][0]["load_charge_C"]*1e9 if completed else "INCOMPLETE", flush=True)
    payload = dict(schema="scci_rh.stage4.driver-study.v1", date="2026-10-13",
                   scope="Restricted behavioral artificial-load servo/bridge model, not vendor or complete native-circuit simulation",
                   native_circuit_modified=False, full_charge_accuracy_earned=False,
                   digital_controls="Explicit fixture inputs, separate native permission/latch contract",
                   amplifier_model="Chosen finite-gain one-pole slew/rail-limited surrogate; no vendor macro model",
                   mosfet_model="Chosen level-1 surrogate; no vendor or linear-SOA qualification",
                   setpoint_V=VSET, cases=[asdict(c) for c in CASES if not only or c.name==only],
                   grids_s=list(GRIDS), engine=engine.version_messages,
                   helper_source_sha256=sha(HERE.parent/"monitoring-study/ngspice_shared.py"),
                   source_sha256=sha(Path(__file__)), runs=results)
    (HERE / "results.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8",newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--case")
    args = parser.parse_args()
    if not args.run:
        parser.error("Use --run for a deliberate local simulation; portable checks are separate")
    run(args.case)
