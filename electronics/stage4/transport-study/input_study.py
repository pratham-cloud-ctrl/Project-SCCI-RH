"""Finite input-loading/filter and incremental power model. Read-only by default.

The two equal-pole filter is illustrative, not a reconstruction of TI silicon.
No claim of dose precision, sensor accuracy, biological efficacy or implant heat.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def zoh_integral(t, y, start, stop):
    edges = np.r_[start, t[(t > start) & (t < stop)], stop]
    indices = np.searchsorted(t, edges[:-1], side="right") - 1
    if np.any(indices < 0):
        raise ValueError("unobserved beginning")
    return float(np.dot(np.diff(edges), y[indices]))


def compare(actual, saved, path="results"):
    """Permit floating library rounding only; identities and structure stay exact."""
    if isinstance(actual, dict):
        if actual.keys()!=saved.keys():raise AssertionError(path+" keys")
        for key in actual:compare(actual[key],saved[key],path+"."+key)
    elif isinstance(actual, list):
        if len(actual)!=len(saved):raise AssertionError(path+" length")
        for i,value in enumerate(actual):compare(value,saved[i],path+f"[{i}]")
    elif isinstance(actual,float):
        if not math.isclose(actual,saved,rel_tol=1e-11,abs_tol=1e-14):raise AssertionError(path)
    elif actual!=saved:raise AssertionError(path)


def study():
    contract = json.loads((HERE / "transport-results.json").read_text())
    native_path = ROOT / "electronics/stage4/monitoring-transport/connectivity.json"
    native = json.loads(native_path.read_text())
    parts = {p["ref"]: p for p in native["parts"]}
    power_path = ROOT / "electronics/stage4/power-study/budget-results.json"
    old = json.loads(power_path.read_text())
    rin_values = [r * (1 + drift) for r in (850000., 1150000.) for drift in (-.0025, .0025)]
    dc = []
    for name, rt, rb, sources in [("PACK_BUS", 4990., 2490., (5.9, 6.9, 7.9)),
                                  ("HOST_5", 2400., 2000., (4.9, 5., 5.1))]:
        for vs, rin, top, bottom, series in itertools.product(sources, rin_values, (-.001, .001), (-.001, .001), (-.001, .001)):
            a, b, rs = rt*(1+top), rb*(1+bottom), 100*(1+series)
            matrix = np.array([[1/a+1/b+1/rs, -1/rs], [-1/rs, 1/rs+1/rin]])
            vscale, vadc = np.linalg.solve(matrix, [vs/a, 2.5/rin])
            dc.append(dict(source=name, source_V=vs, top_ohm=a, bottom_ohm=b, series_ohm=rs,
                           Rin_ohm=rin, scaled_V=float(vscale), ADC_V=float(vadc),
                           nominal_unloaded_V=vs*rb/(rt+rb),
                           reconstructed_source_V=float(vadc)*(rt+rb)/rb))
    direct = []
    for source, rin in itertools.product((1.928, 2.048, 2.168, 4.096), rin_values):
        vadc = (source/110 + 2.5/rin)/(1/110+1/rin)
        direct.append(dict(source_V=source, source_resistance_ohm_assumed=10., series_ohm=100.,
                           Rin_ohm=rin, ADC_V=vadc, error_V=vadc-source))

    tick = contract["raw_ADC"]["tick_ns"]*1e-9
    period = contract["raw_ADC"]["hyperperiod_ticks"]*tick
    base = np.array([f["aperture_tick"]*tick for f in contract["raw_ADC"]["frames"] if f["channel_name"] == "I0"])
    st = np.concatenate([base + k*period for k in range(3)])
    st = st[st <= .001 + 1e-14]
    traces, cases = {}, []
    # Source changes at exact edges; model is right-continuous.
    for fc, spike in itertools.product((7500., 15000., 22500.), (False, True)):
        edges = [(50e-6, .003), (250e-6, -.003), (450e-6, -.003), (650e-6, .003)]
        if spike:
            edges += [(140e-6, .030), (141e-6, -.030)]
        edges.sort()
        et = np.array([e[0] for e in edges]); changes = np.array([e[1] for e in edges])
        t = np.unique(np.r_[np.arange(4001)*.25e-6, et, st])
        t = t[t <= .001+1e-14]
        tau = math.sqrt(math.sqrt(2)-1)/(2*math.pi*fc)
        first = second = current = 0.
        out = np.zeros(len(t)); source = np.zeros(len(t)); edge_index = 0
        for i, now in enumerate(t):
            if i:
                dt = now-t[i-1]; decay = math.exp(-dt/tau)
                second = current + ((second-current)+(first-current)*dt/tau)*decay
                first = current + (first-current)*decay
            while edge_index < len(et) and et[edge_index] <= now+1e-16:
                current += changes[edge_index]; edge_index += 1
            out[i] = second; source[i] = current
        observed = np.interp(st, t, out)
        gain = 1e6/(1e6+110)
        voltage = 2.5 + (2.048+40*observed-2.5)*gain
        codes = np.clip(np.rint(voltage/5.12*65536), 0, 65535).astype(np.uint16)
        estimate = (((codes.astype(float)*5.12/65536-2.5)/gain+2.5)-2.048)/40
        key = f"fc{int(fc)}_{'spike' if spike else 'normal'}"
        traces.update({key+"_time_s":t, key+"_source_A":source, key+"_filtered_A":out,
                       key+"_sample_time_s":st, key+"_code":codes, key+"_estimated_A":estimate})
        true_charge = 600e-9+(30e-9 if spike else 0)
        phase = zoh_integral(st, estimate, 50e-6, 250e-6)
        tail = zoh_integral(st, estimate, 50e-6, 400e-6)
        cases.append(dict(id=key, cutoff_3dB_Hz_assumed=fc, pole_time_constant_s=tau,
                          edges=[[float(a),float(b)] for a,b in edges],
                          dense_points=len(t), sample_points=len(st), true_cathodic_charge_C=true_charge,
                          phase_window_charge_C=phase, extended_tail_charge_C=tail,
                          phase_error_C=phase-true_charge, tail_error_C=tail-true_charge,
                          source_peak_A=.033 if spike else .003,
                          observed_peak_A=float(np.max(estimate)),
                          phase_charge_precision_certified=False))

    baseline = next(c for c in old["operating_cases"] if c["mode"] == "restricted-active")
    # Declared caps replace only HOST3.3 and direct HOST5 load caps, preserving old converters/AFE loads.
    host3_extra = .001+.0035+.00033+.000033+.000066+.0002
    host5_extra = .016+5/4400
    bus_extra = (3.3*.010+5*.020)/.8+6.9**2/7480
    battery_extra = bus_extra*7.4/6.9
    total = baseline["battery_nominal_W"]+battery_extra
    caps = []
    for p in native["parts"]:
        if not p["ref"].startswith("C"): continue
        m = re.match(r"([0-9.]+)([un])", p["value"])
        if not m: raise ValueError(p["value"])
        farad = float(m[1])*dict(u=1e-6,n=1e-9)[m[2]]
        nets = set(p["nets"].values())
        peer = "COMP_GND" in nets
        volts = 3.3 if peer or "HOST_3V3" in nets else 4.096 if {"RAW_REFIO", "RAW_REFCAP"}&nets else 5.25
        caps.append(dict(reference=p["ref"],value=p["value"],capacitance_F=farad,
                         voltage_allocation_V=volts,external_peer=peer,energy_J=.5*farad*volts**2))
    overlay = dict(baseline_active_W=baseline["battery_nominal_W"],
                   HOST_3V3_old_cap_A=.070, HOST_3V3_new_cap_A=.080, HOST_3V3_new_parts_A=host3_extra,
                   HOST_5_old_direct_cap_A=.020, HOST_5_new_direct_cap_A=.040, HOST_5_new_parts_A=host5_extra,
                   ADC_AVDD_max_A=.016, ADC_DVDD_allocation_A=.001, ISO_host_DC_max_A=.0035,
                   peer_external_DC_max_A=.0035, peer_external_DC_W=.0035*3.3,
                   efficiencies_are_assumptions=True, added_bus_W=bus_extra, added_battery_W=battery_extra,
                   active_W=total,usable_energy_Wh=old["battery"]["usable_Wh"],
                   runtime_h=old["battery"]["usable_Wh"]/total,
                   RAM_total_bytes=old["resources"]["RAM_total_bytes"],
                   monitor_used_bytes=contract["resources"]["monitor_total_bytes"],monitor_cap_bytes=8192,
                   capacitors=caps, host_added_capacitor_energy_J=sum(c["energy_J"] for c in caps if not c["external_peer"]),
                   host_added_capacitor_energy_plus20percent_J=1.2*sum(c["energy_J"] for c in caps if not c["external_peer"]),
                   compact_thermal_2K_earned=False, installed_converter_capacity_is_measured=False)
    result = dict(schema="scci_rh.stage4.transport-input.v1",date="2026-10-14",
                  scope="finite illustrative artificial-input model and conditional incremental power; not clinical or physical qualification",
                  source_sha256_lf={str(native_path.relative_to(ROOT)).replace('\\','/'):sha(native_path),
                                   str(power_path.relative_to(ROOT)).replace('\\','/'):sha(power_path),
                                   "electronics/stage4/transport-study/transport-results.json":sha(HERE/"transport-results.json"),
                                   "electronics/stage4/transport-study/input_study.py":sha(Path(__file__))},
                  source_documents=["https://www.ti.com/lit/ds/symlink/ads8688.pdf","https://www.ti.com/lit/ds/symlink/iso6721.pdf"],
                  assumptions=dict(ADC_bias_V=2.5, Rin_25C_ohm=[850000,1150000], Rin_drift_fraction_over100C=.0025,
                                   resistor_tolerance_fraction=.001, external_C_nominal_F=1e-9,
                                   external_C_tolerance_fraction=.05, direct_source_resistance_ohm_assumed=10.,
                                   filter="two equal real poles matched to declared combined -3dB bandwidth; illustrative shape, no vendor min/max bandwidth claim",
                                   external_RC_transient_included=False, buffer_reference_gain_noise_clipping_errors_included=False,
                                   exact_DC_calibration_assumed_for_quantized_filter_cases=True,
                                   zoh_integral="offline diagnostic using only latest sample at each interval; not real-time phase certification"),
                  divider_cases=dc,direct_cases=direct,filter_cases=cases,power_overlay=overlay)
    return result,traces


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--write-results",action="store_true");args=parser.parse_args()
    result,traces=study()
    if args.write_results:
        (HERE/"input-results.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        np.savez_compressed(HERE/"input-traces.npz",**traces)
    else:
        saved=json.loads((HERE/"input-results.json").read_text())
        compare(result,saved)
        with np.load(HERE/"input-traces.npz") as data:
            for k,v in traces.items():
                if not np.allclose(v,data[k],rtol=1e-11,atol=1e-14):raise AssertionError(k)
    print(f"Transport input: {len(result['divider_cases'])} divider corners, {len(result['direct_cases'])} direct corners, six filter cases; active {result['power_overlay']['active_W']:.6f} W / {result['power_overlay']['runtime_h']:.6f} h conditional")


if __name__=="__main__":main()
