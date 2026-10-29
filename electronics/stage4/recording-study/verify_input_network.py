"""Read-only, independent scalar audits of saved recording-network evidence."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import numpy as np

HERE = Path(__file__).resolve().parent


def transfer_scalar(f, source, cd, cp, p):
    # Independently expand the two-node admittance determinant; do not import
    # the generator, matrix solver, or its circuit-construction functions.
    gs = 1 / (source + p["series_ohm"] + p["hv_on_ohm_assumed"])
    gb = 1 / p["bleeder_ohm"]
    gx = 1 / p["clamp_on_ohm_assumed"]
    s = 2j * math.pi * f
    return gs * gx / ((gs + gb + gx + s * cp) * (gx + s * cd) - gx * gx)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args()
    data = json.loads((HERE / "input-results.json").read_text(encoding="utf-8"))
    p = data["parameters"]
    sha = hashlib.sha256((HERE / "input_network_study.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert data["source_sha256_lf"] == sha
    assert len(data["quiet"]) == 8 and len(data["transient"]) == 9
    checks = 0
    for row in data["quiet"]:
        cp = p["protected_node_F_assumed"]
        cd = p["mux_drain_and_board_F_assumed"] + p["positive_input_F"]
        cr = p["mux_drain_and_board_F_assumed"] + p["reference_input_F"]
        if row["native_added_capacitance"]:
            cd += p["positive_added_F"]
            cr += p["reference_added_F"]
        hp = transfer_scalar(50, row["record_source_ohm"], cd, cp, p)
        hr = transfer_scalar(50, row["reference_source_ohm"], cr, cp, p)
        cm = abs(hp - hr) * row["common_mode_50Hz_V_rms"]
        assert math.isclose(cm, row["converted_common_mode_V_rms"], rel_tol=2e-7)
        assert math.isclose(abs(transfer_scalar(300, row["record_source_ohm"], cd, cp, p)), row["signal_300Hz_gain"], rel_tol=2e-7)
        assert row["signal_frequency_Hz"] == 50
        assert math.isclose(abs(hp), row["signal_50Hz_gain"], rel_tol=2e-7)
        snr = 20 * math.log10(10e-6 * abs(hp) / row["total_noise_allocation_V_rms"])
        assert math.isclose(snr, row["snr_10uV_dB"], rel_tol=2e-7)
        intrinsic = row["common_mode_50Hz_V_rms"] * 10**(-p["cmrr_dB_typical"]/20)
        coherent = math.sqrt((cm+intrinsic)**2 + row["thermal_allocation_V_rms"]**2 + p["afe_noise_V_typical"]**2 + p["quantization_V_rms"]**2 + p["alias_allowance_V"]**2)
        assert math.isclose(coherent, row["coherent_CM_noise_allocation_V_rms"], rel_tol=2e-7)
        assert math.isclose(20*math.log10(10e-6*abs(hp)/coherent), row["coherent_snr_10uV_dB"], rel_tol=2e-7)
        assert row["quiet_10dB_gate"] == (row["coherent_snr_10uV_dB"] >= 10)
        assert row["RSS_illustration_10dB_pass"] == (row["snr_10uV_dB"] >= 10)
        checks += 9
    failures = set()
    max_balance = 0.0
    for row in data["transient"]:
        with np.load(HERE / row["trace"]) as tr:
            a = tr["trace"]
        assert a.shape[1] == 4 and np.isfinite(a).all()
        assert np.diff(a[:, 0]).min() >= -1e-15
        assert math.isclose(abs(a[:, 2]).max(), row["max_all_pin_V"], abs_tol=1e-14)
        assert row["sampled_pin_DC_envelope_pass"] == (row["max_all_pin_V"] <= p["dc_limit_V"])
        if not row["sampled_pin_DC_envelope_pass"]:
            failures.add(row["case"])
        dc = row["reconnection_DC_V_assumed"]
        expected = dc * p["bleeder_ohm"] / (p["bleeder_ohm"] + row["source_ohm"] + p["series_ohm"] + p["hv_on_ohm_assumed"])
        # A finite 10 ms endpoint is not mathematical infinity. Even the 1 Mohm
        # source case is within a declared 10 nV of its independent DC limit.
        assert math.isclose(row["final_pin_V"], expected, rel_tol=1e-10, abs_tol=1e-8)
        assert math.isclose(a[-1, 2], expected, rel_tol=1e-10, abs_tol=1e-8)
        cd = p["mux_drain_and_board_F_assumed"] + p["reference_input_F" if row["shared_reference"] else "positive_input_F"]
        cd += p["reference_added_F" if row["shared_reference"] else "positive_added_F"]
        cp = p["protected_node_F_assumed"] + row["source_feedthrough_F_assumed"]
        cx = row["off_path_mutual_F_assumed"]
        # Integrate whole-network KCL: internal switch/mutual currents cancel.
        # The logarithmic saved grid is a finite quadrature, so use a declared
        # 1% normalized charge-balance allowance, not exact transient identity.
        for seg in np.unique(a[:, 3]).astype(int):
            s = a[a[:, 3] == seg]
            released = row["bad_release"] or seg == 5
            connected = row["bad_release"] or seg >= 4
            vin = dc if connected else (24 if seg == 0 else -24 if seg == 2 else 0)
            gs = 1 / (row["source_ohm"] + p["series_ohm"] + p["hv_on_ohm_assumed"]) if connected else 0
            gc = 0 if released else 1 / p["clamp_on_ohm_assumed"]
            current = gs * (vin - s[:, 1]) - s[:, 1] / p["bleeder_ohm"] - gc * s[:, 2]
            delta_q = cp * (s[-1, 1] - s[0, 1]) + cd * (s[-1, 2] - s[0, 2])
            integrated = np.trapezoid(current, s[:, 0])
            scale = max(abs(delta_q), np.trapezoid(abs(current), s[:, 0]), 1e-12)
            residual = abs(delta_q - integrated) / scale
            max_balance = max(max_balance, residual)
            assert residual < 0.01, (row["case"], seg, residual)
            checks += 1
        checks += 6
    assert failures == {"injection_300pC", "unblanked_600mV"}, failures
    native = [row for row in data["quiet"] if row["native_added_capacitance"]]
    assert not any(row["quiet_10dB_gate"] for row in native)
    assert native[0]["coherent_snr_50uV_dB"] > 10
    assert data["ideal_HP_200mV_step_at_100ms_V"] > p["ac_limit_V"]
    assert math.isclose(data["fast_settle_guideline_s"], 1/120, rel_tol=1e-12)
    paths = ["input_network_study.py", "verify_input_network.py", "input-results.json", "build_input_figures.py", "input-network.png", "input-network.svg", "README.md"]
    paths += sorted(row["trace"] for row in data["transient"])
    hashes = {}
    for name in paths:
        content = (HERE / name).read_bytes()
        if Path(name).suffix in (".py", ".json", ".svg", ".md"):
            content = content.replace(b"\r\n", b"\n")
        hashes[name] = hashlib.sha256(content).hexdigest()
    receipt = {"schema": "scci_rh.stage4.recording-input-audit.v1", "independent_scalar_and_KCL_checks": checks,
               "max_normalized_saved_grid_KCL_residual": max_balance, "KCL_allowance": 0.01,
               "finite_transient_failures_retained": sorted(failures), "sha256_lf_text_exact_binary": hashes}
    path = HERE / "input-verification.json"
    if args.write_receipt:
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    else:
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["sha256_lf_text_exact_binary"] == hashes
        assert saved["independent_scalar_and_KCL_checks"] == checks
        assert saved["finite_transient_failures_retained"] == sorted(failures)
        assert math.isclose(saved["max_normalized_saved_grid_KCL_residual"], max_balance, rel_tol=1e-7, abs_tol=1e-12)
    print(f"Recording-network audit: {checks} scalar/KCL checks; two finite fault failures retained; worst balance {max_balance:.6%}")


if __name__ == "__main__":
    main()
