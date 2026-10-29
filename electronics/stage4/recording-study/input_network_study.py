"""Finite passive input-network study; not a vendor or biological AFE model.

Two-node charge conservation is solved with matrix exponentials. Independent
scalar/DC/energy limits are checked separately by verify_input_network.py.
Default operation writes nothing. --write-results explicitly refreshes evidence.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import numpy as np
from scipy.linalg import expm

HERE = Path(__file__).resolve().parent
SCHEMA = "scci_rh.stage4.recording-input-network.v1"
PARAMETERS = {
    "temperature_K": 310.0,
    "series_ohm": 4990.0,
    "hv_on_ohm_assumed": 10.0,
    "clamp_on_ohm_assumed": 2.1,
    "bleeder_ohm": 10e6,
    "protected_node_F_assumed": 94e-12,
    "positive_input_F": 12e-12,
    "reference_input_F": 16 * 12e-12,
    "mux_drain_and_board_F_assumed": 84e-12,
    "positive_added_F": 470e-12,
    "reference_added_F": 2.2e-9,
    "dc_normal_V": 0.2,
    "dc_qualification_V": 0.3,
    "dc_limit_V": 0.4,
    "ac_limit_V": 0.005,
    "low_corner_Hz": 0.1,
    "upper_corner_Hz": 300.0,
    "afe_noise_V_typical": 2.4e-6,
    "quantization_V_rms": 0.195e-6 / math.sqrt(12),
    "alias_allowance_V": 0.6e-6,
    "cmrr_dB_typical": 82.0,
    "noise_bandwidth_Hz": 314.16,
}


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def caps(reference=False, added=True, feed=1e-12, mutual=1e-12):
    p = PARAMETERS
    cd = p["mux_drain_and_board_F_assumed"] + p["reference_input_F" if reference else "positive_input_F"]
    if added:
        cd += p["reference_added_F" if reference else "positive_added_F"]
    cp = p["protected_node_F_assumed"]
    return np.array([[cp + feed + mutual, -mutual], [-mutual, cd + mutual]], float)


def conductance(source_r, connected=True, released=True):
    p = PARAMETERS
    gs = 1 / (source_r + p["series_ohm"] + p["hv_on_ohm_assumed"]) if connected else 0.0
    gb = 1 / p["bleeder_ohm"]
    gl = 1 / p["clamp_on_ohm_assumed"] if released else 0.0
    gc = 0.0 if released else 1 / p["clamp_on_ohm_assumed"]
    return np.array([[gs + gb + gl, -gl], [-gl, gl + gc]]), gs


def response(frequency, source_r, reference=False, added=True):
    # The off-state transfer parasitics do not represent a conducting switch;
    # in quiet mode only the chosen shunt capacitances are included.
    c = caps(reference, added, feed=0.0, mutual=0.0)
    g, gs = conductance(source_r)
    return np.linalg.solve(g + 2j * math.pi * frequency * c, np.array([gs, 0.0]))[1]


def quiet_rows():
    p = PARAMETERS
    rows = []
    for case, rr, rf, cm in (
        ("nominal", 20e3, 2e3, 1e-3),
        ("high_impedance", 100e3, 10e3, 1e-3),
        ("adverse", 1e6, 20e3, 10e-3),
        ("reference_high_impedance", 20e3, 1e6, 1e-3),
    ):
        for added in (False, True):
            hp = response(50, rr, False, added)
            hr = response(50, rf, True, added)
            mismatch = abs(hp - hr) * cm
            # A conservative series-resistance thermal allocation. The finite
            # shunt/RC transfer is not integrated into this noise approximation.
            rsum = rr + rf + 2 * (p["series_ohm"] + p["hv_on_ohm_assumed"] + p["clamp_on_ohm_assumed"])
            thermal = math.sqrt(4 * 1.380649e-23 * p["temperature_K"] * p["noise_bandwidth_Hz"] * rsum)
            intrinsic_cm = cm * 10 ** (-p["cmrr_dB_typical"] / 20)
            total = math.sqrt(sum(v*v for v in (mismatch, thermal, intrinsic_cm, p["afe_noise_V_typical"], p["quantization_V_rms"], p["alias_allowance_V"])))
            # Both common-mode terms originate in the same sinusoid; arbitrary
            # phase permits coherent addition. RSS is illustrative, not a bound.
            coherent = math.sqrt((mismatch + intrinsic_cm)**2 + sum(v*v for v in
                                (thermal, p["afe_noise_V_typical"], p["quantization_V_rms"], p["alias_allowance_V"])))
            signal_gain = abs(response(300, rr, False, added))
            rows.append({"case": case, "native_added_capacitance": added, "record_source_ohm": rr,
                         "reference_source_ohm": rf, "common_mode_50Hz_V_rms": cm,
                         "converted_common_mode_V_rms": mismatch, "thermal_allocation_V_rms": thermal,
                         "total_noise_allocation_V_rms": total,
                         "coherent_CM_noise_allocation_V_rms": coherent,
                         "signal_300Hz_gain": signal_gain,
                         "signal_frequency_Hz": 50.0, "signal_50Hz_gain": abs(hp),
                         "snr_10uV_dB": 20 * math.log10(10e-6 * abs(hp) / total),
                         "coherent_snr_10uV_dB": 20 * math.log10(10e-6 * abs(hp) / coherent),
                         "coherent_snr_50uV_dB": 20 * math.log10(50e-6 * abs(hp) / coherent),
                         "RSS_illustration_10dB_pass": 20 * math.log10(10e-6 * abs(hp) / total) >= 10,
                         "quiet_10dB_gate": 20 * math.log10(10e-6 * abs(hp) / coherent) >= 10})
    return rows


def evolve(v, c, g, b, dt):
    steady = np.linalg.solve(g, b)
    return steady + expm(-np.linalg.solve(c, g) * dt) @ (v - steady)


def transient(case, source_r, reference=False, feed=1e-12, mutual=1e-12,
              injection=30e-12, dc=0.2, bad_release=False):
    c = caps(reference, True, feed, mutual)
    v = np.zeros(2)
    t = 0.0
    vin = 0.0
    trace = []
    events = [
        ("blank_positive", 10e-6, 24.0, False, False, 0.0),
        ("blank_gap", 210e-6, 0.0, False, False, 0.0),
        ("blank_negative", 260e-6, -24.0, False, False, 0.0),
        ("blank_recovery", 460e-6, 0.0, False, False, 0.0),
        ("connected_clamped", 1e-3, dc, True, False, 0.0),
        ("released", 2e-3, dc, True, True, injection),
    ]
    if bad_release:
        events = [("unblanked_subrail_fault", 10e-6, dc, True, True, 0.0)]
    max_blank = 0.0
    max_all = 0.0
    released_initial = None
    final = None
    for index, (label, start, next_vin, connected, released, q) in enumerate(events):
        assert abs(start - t) < 1e-14 or index == 0
        if index == 0:
            t = start
        # Coupled charge conservation for source edge and switch injection.
        v += np.linalg.solve(c, np.array([feed * (next_vin - vin), q]))
        vin = next_vin
        g, gs = conductance(source_r, connected, released)
        b = np.array([gs * vin, 0.0])
        end = events[index+1][1] if index+1 < len(events) else start + 10e-3
        times = np.unique(np.r_[0.0, np.geomspace(1e-10, end - start, 220)])
        initial = v.copy()
        for delta in times:
            sample = evolve(initial, c, g, b, float(delta))
            trace.append([start + float(delta), float(sample[0]), float(sample[1]), index])
        v = evolve(initial, c, g, b, end - start)
        t = end
        peak = max(abs(row[2]) for row in trace if row[3] == index)
        if not released:
            max_blank = max(max_blank, peak)
        else:
            released_initial = float(initial[1])
        max_all = max(max_all, peak)
        final = float(v[1])
    tr = np.asarray(trace)
    return {"case": case, "source_ohm": source_r, "shared_reference": reference,
            "source_feedthrough_F_assumed": feed, "off_path_mutual_F_assumed": mutual,
            "injected_charge_C_assumed": injection, "reconnection_DC_V_assumed": dc,
            "bad_release": bad_release, "max_blank_pin_V": max_blank,
            "max_all_pin_V": max_all, "release_initial_pin_V": released_initial,
            "final_pin_V": final,
            "sampled_pin_DC_envelope_pass": max_all <= PARAMETERS["dc_limit_V"],
            "trace": f"traces/{case}.npz"}, tr


def generate():
    rows = []
    traces = {}
    for case, kw in (
        ("nominal_positive", {}),
        ("nominal_reference", {"reference": True, "source_r": 2e3}),
        ("negative_offset", {"dc": -0.2, "injection": -30e-12}),
        ("feedthrough_10pF", {"feed": 10e-12, "mutual": 10e-12}),
        ("injection_100pC", {"injection": 100e-12}),
        ("qualification_offset_100pC", {"dc": 0.3, "injection": 100e-12}),
        ("injection_300pC", {"injection": 300e-12}),
        ("high_source_impedance", {"source_r": 1e6}),
        ("unblanked_600mV", {"dc": 0.6, "bad_release": True, "injection": 0.0}),
    ):
        kw.setdefault("source_r", 20e3)
        row, trace = transient(case, **kw)
        rows.append(row)
        traces[row["trace"]] = trace
    p = PARAMETERS
    data = {"schema": SCHEMA, "parameters": p, "quiet": quiet_rows(), "transient": rows,
            "scope": "Finite passive two-node model; no vendor nonlinear fault, saturation, safety or biological recovery model",
            "fast_settle_guideline_s": 2.5 / p["upper_corner_Hz"],
            "ideal_HP_200mV_step_at_100ms_V": 0.2 * math.exp(-2 * math.pi * p["low_corner_Hz"] * 0.1),
            "unreset_200mV_step_time_to_5mV_s": math.log(0.2 / p["ac_limit_V"]) / (2 * math.pi * p["low_corner_Hz"]),
            "bias_24V_two_499k_A": 24 / (2 * 499e3),
            "bias_24V_one_499k_short_A": 24 / 499e3,
            "bleeder_25nA_open_source_V": 25e-9 * p["bleeder_ohm"],
            "source_sha256_lf": lf_sha(Path(__file__))}
    return data, traces


def compare(actual, saved, path="result"):
    if isinstance(actual, dict):
        assert actual.keys() == saved.keys(), path
        for key in actual:
            compare(actual[key], saved[key], path + "." + key)
    elif isinstance(actual, list):
        assert len(actual) == len(saved), path
        for i, (a, b) in enumerate(zip(actual, saved)):
            compare(a, b, f"{path}[{i}]")
    elif isinstance(actual, float):
        assert math.isclose(actual, saved, rel_tol=2e-8, abs_tol=1e-14), (path, actual, saved)
    else:
        assert actual == saved, (path, actual, saved)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-results", action="store_true")
    args = parser.parse_args()
    data, traces = generate()
    if args.write_results:
        for path, trace in traces.items():
            dest = HERE / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(dest, trace=trace)
        (HERE / "input-results.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {len(data['quiet'])} quiet rows and {len(traces)} finite transient cases")
    else:
        compare(data, json.loads((HERE / "input-results.json").read_text(encoding="utf-8")))
        for path, trace in traces.items():
            with np.load(HERE / path) as saved:
                np.testing.assert_allclose(trace, saved["trace"], rtol=2e-8, atol=1e-14)
        print("Input-network same-model replay matches; saved files unchanged")


if __name__ == "__main__":
    main()
