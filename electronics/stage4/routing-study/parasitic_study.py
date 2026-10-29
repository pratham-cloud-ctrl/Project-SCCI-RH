"""Finite unselected-contact charge coupling; default reproduces without writes.

This is a passive fixture with assumed interterminal capacitances, not a vendor
model. Datasheet source-to-ground Coff is never used as a guaranteed D-S coupling.
"""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import math
import numpy as np

HERE = Path(__file__).resolve().parent


def generate():
    rows = []
    traces = {}
    for ce, coupling, pattern in itertools.product((1e-9, 100e-9, 2e-6), (1e-12, 5e-12, 15e-12),
                                                 ("aligned", "opposed_matched", "opposed_asymmetric", "staggered")):
        c0 = coupling
        c1 = coupling / 3 if pattern == "opposed_asymmetric" else coupling
        shunt = 30e-12  # two off-source terminal-to-ground capacitances, chosen fixture lump
        ct = ce + shunt + c0 + c1
        resistance = 1e6
        if pattern == "aligned":
            events = [(100e-6, 24., 24.), (300e-6, 0., 0.)]
        elif pattern.startswith("opposed"):
            # Changes from precharged (0,24) to (24,0), then back. Equal ideal
            # coupling cancels at this one floating victim, not all electrodes.
            events = [(100e-6, 24., -24.), (300e-6, -24., 24.)]
        else:
            events = [(100e-6, 24., 0.), (150e-6, 0., 24.),
                      (300e-6, -24., 0.), (350e-6, 0., -24.)]
        v = 0.0
        time = 0.0
        tr = [[0., 0.]]
        event_rows = []
        signed_ground_q = 0.0
        absolute_ground_q = 0.0
        max_abs = 0.0
        for t, dv0, dv1 in events + [(10e-3, 0., 0.)]:
            before = v * math.exp(-(t-time)/(resistance*ct))
            flow = ct*(v-before)
            signed_ground_q += flow
            absolute_ground_q += abs(flow)
            for u in np.linspace(time, t, 80)[1:]:
                tr.append([float(u), float(v*math.exp(-(u-time)/(resistance*ct)))])
            injected = c0*dv0 + c1*dv1
            after = before + injected/ct
            event_rows.append({"time_s": t, "bus0_delta_V": dv0, "bus1_delta_V": dv1,
                               "before_V": before, "after_V": after,
                               "coupled_charge_C": injected, "ground_charge_since_prior_C": flow})
            tr.append([t, after])
            v, time = after, t
            max_abs = max(max_abs, abs(before), abs(after))
        case = f"C{ce:g}_X{coupling:g}_{pattern}".replace("+", "")
        rows.append({"case": case, "contact_capacitance_F_assumed": ce,
                     "off_source_shunt_F_assumed": shunt,
                     "bus0_mutual_F_assumed": c0, "bus1_mutual_F_assumed": c1,
                     "total_capacitance_F": ct, "discharge_R_ohm_assumed": resistance,
                     "pattern": pattern, "events": event_rows,
                     "max_abs_victim_V": max_abs,
                     "signed_ground_charge_C": signed_ground_q,
                     "absolute_ground_charge_C": absolute_ground_q,
                     "absolute_coupled_edge_charge_C": sum(abs(e["coupled_charge_C"]) for e in event_rows),
                     "final_victim_V": v, "trace_key": case})
        traces[case] = np.asarray(tr)
    source = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    data = {"schema": "scci_rh.stage4.router-parasitics.v1", "source_sha256_lf": source,
            "scope": "Finite passive unselected-contact fixture; assumed coupling; not a nonlinear switch/tissue or complete driver model",
            "rows": rows,
            "source_capacitance_is_not_interterminal_coupling": True,
            "digital_route_ownership_proves_zero_unselected_charge": False,
            "illustrative_budget": {
                "current_A": 0.003, "phase_s": 200e-6, "nominal_phase_C": 600e-9,
                "router_on_R_ohm_assumed": [4., 20., 60.],
                "router_voltage_drops_V": [0.012, 0.060, 0.180],
                "on_capacitance_fixture_F": 200e-12,
                "on_capacitance_24V_edge_charge_C": 4.8e-9,
                "bus_voltage_edge_V_assumed": 24.,
                "off_paths_with_two_distinct_active_contacts": 30,
                "per_path_leakage_A_assumed": 25e-9,
                "sum_absolute_off_path_charge_per_200us_C": 150e-12,
                "switch_injection_C_fixture": 3e-12,
                "power_4chips_24V_55uA_W_illustrative": 0.00528,
                "power_4chips_24V_105uA_W_illustrative": 0.01008,
                "24V_guaranteed_corner_bounds": False,
                "full_guard_latency_and_peak_current_qualified": False}}
    return data, traces


def compare(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a: compare(a[k], b[k])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b): compare(x, y)
    elif isinstance(a, float):
        assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-20), (a, b)
    else:
        assert a == b, (a, b)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-results", action="store_true")
    args = ap.parse_args()
    data, traces = generate()
    if args.write_results:
        (HERE/"parasitic-results.json").write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
        np.savez_compressed(HERE/"parasitic-traces.npz", **traces)
        print("Saved36 finite passive contact-coupling cases")
    else:
        compare(data, json.loads((HERE/"parasitic-results.json").read_text(encoding="utf-8")))
        with np.load(HERE/"parasitic-traces.npz") as saved:
            assert set(saved.files) == set(traces)
            for key, value in traces.items(): np.testing.assert_allclose(saved[key], value, rtol=1e-10, atol=1e-20)
        print("Router parasitic same-model replay matches; no files written")


if __name__ == "__main__": main()
