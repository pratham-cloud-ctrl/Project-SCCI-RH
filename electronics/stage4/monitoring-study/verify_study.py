"""Read-only, portable verification of committed monitoring-study evidence.

No ngspice, GUI, network, platform-specific DLL or file mutation is required.
--write-receipt is an explicit maintainer action after reviewing regenerated data.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import study

HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "artifact-manifest.json"
CRITERIA = {"KCL_A": 1e-10, "linear_oracle_V": 2e-5, "fine_grid_interval_delta_C": 1e-10}
INTERVALS = ["command_phase1", "command_gap", "command_phase2", "observed_first",
             "observed_second_includes_gap", "settled_net", "wrong_pre_reset_baseline"]
PAIRS = dict(zip(INTERVALS, [("phase1_start","phase1_edge"), ("phase1_edge","phase2_start"),
                            ("phase2_start","phase2_edge"), ("baseline","phase1_tail"),
                            ("phase1_tail","phase2_tail"), ("baseline","late_tail"),
                            ("pre_reset","phase1_tail")]))
HASH_POLICY = "SHA256; CRLF and CR normalized to LF for text; exact bytes for NPZ/PNG/PDF; receipt itself and __pycache__ excluded"

def files():
    return sorted(p for p in HERE.rglob("*") if p.is_file() and p != RECEIPT
                  and "__pycache__" not in p.relative_to(HERE).parts)

def hashes():
    return {p.relative_to(HERE).as_posix(): study.normalized_hash(p) for p in files()}

def close(a, b, atol=1e-16):
    assert math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=atol), (a, b)

def validate():
    study.check()
    result = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    assert result["schema"] == "scci_rh.stage4.monitoring-study.v1"
    assert result["four_percent_target_earned"] is False
    assert result["native_cell_modified"] is False
    assert result["numerical_comparison_criteria"] == CRITERIA
    assert result["cases"] == [asdict(c) for c in study.CASES]
    assert result["grids_s"] == list(study.GRIDS)
    cases = {c.name: c for c in study.CASES}
    expected = {(c.name, g) for c in study.CASES for g in study.GRIDS}
    runs = {(r["case"], r["max_step_s"]): r for r in result["runs"]}
    assert len(runs) == len(result["runs"]) == 33 and set(runs) == expected
    assert result["analytical_witnesses"] == study.witnesses()
    max_oracle = 0.0
    max_kcl = 0.0
    csv_expected = []
    for (name, grid), r in runs.items():
        case = cases[name]
        expected_lines, _ = study.make_netlist(case, grid)
        text = (HERE / r["netlist_file"]).read_text(encoding="utf-8")
        assert text == "\n".join(expected_lines) + "\n", r["netlist_file"]
        assert [c["source"] for c in r["channels"]] == [0, 1]
        with np.load(HERE / r["trace_file"]) as trace:
            assert len(trace.files) == 21
            assert all(np.all(np.isfinite(trace[k])) for k in trace.files)
            t = trace["time_s"]
            assert abs(t[-1] - study.STOP) < 1e-15 and np.all(np.diff(t) > 0)
            for channel in r["channels"]:
                source = channel["source"]
                prefix = f"source{source}_"
                adc = trace[prefix + "ADC_input_V"]
                out = trace[prefix + "integrator_V"]
                mon = trace[prefix + "Imon_V"]
                iL, iS, iD = (trace[prefix + n] for n in ("Iload_A", "Ishunt_A", "Idriver_A"))
                kclL = float(np.max(np.abs(iL - iS - case.bias_load_A)))
                kclD = float(np.max(np.abs(iS - iD - case.bias_driver_A)))
                max_kcl = max(max_kcl, kclL, kclD)
                assert max(kclL, kclD) < CRITERIA["KCL_A"]
                close(kclL, channel["KCL_max_load_residual_A"])
                close(kclD, channel["KCL_max_driver_residual_A"])
                close(channel["peak_load_current_A"], float(np.max(np.abs(iL))))
                assert channel["first_phase_sign"] == (-1 if source == 0 else 1)
                assert set(channel["samples"]) == set(study.endpoints(case, source))
                for endpoint, cnv in study.endpoints(case, source).items():
                    sample = channel["samples"][endpoint]
                    aperture = cnv + 4e-9
                    raw = float(np.interp(aperture, t, adc))
                    code = int(np.clip(np.floor(raw * (1 + case.adc_gain_error) / study.LSB + .5), 0, 65535))
                    close(sample["CNV_s"], cnv)
                    close(sample["aperture_s"], aperture)
                    close(sample["latest_conversion_complete_s"], cnv + 8.8e-6)
                    close(sample["assumed_read_available_s"], cnv + 9.8e-6)
                    close(sample["raw_input_V"], raw)
                    assert sample["code"] == code
                    close(sample["code_voltage_V"], code * study.LSB)
                assert [x["name"] for x in channel["intervals"]] == INTERVALS
                for interval in channel["intervals"]:
                    assert (interval["first"], interval["last"]) == PAIRS[interval["name"]]
                    first, last = (channel["samples"][interval[k]] for k in ("first", "last"))
                    close(interval["start_s"], first["aperture_s"])
                    close(interval["end_s"], last["aperture_s"])
                    rawQ = -study.K0 * (last["raw_input_V"] - first["raw_input_V"])
                    codeQ = -study.K0 * (last["code_voltage_V"] - first["code_voltage_V"])
                    close(interval["raw_endpoint_charge_C"], rawQ)
                    close(interval["quantized_endpoint_charge_C"], codeQ)
                    close(interval["raw_error_vs_load_C"], rawQ - interval["load_charge_C"])
                    close(interval["raw_error_vs_shunt_C"], rawQ - interval["shunt_charge_C"])
                    close(interval["KCL_expected_load_minus_shunt_C"], case.bias_load_A * (interval["end_s"] - interval["start_s"]))
                    csv_expected.append({"case": name, "grid_s": grid, "source": source, **interval})
                by_name = {x["name"]: x for x in channel["intervals"]}
                q1, q2, qnet = (by_name[n]["raw_endpoint_charge_C"] for n in ("observed_first", "observed_second_includes_gap", "settled_net"))
                assert channel["net_only_within_24nC"] == (abs(qnet) <= 24e-9)
                assert channel["individual_600nC_targets_missed_by_over24nC"] == (abs(abs(q1)-600e-9)>24e-9 or abs(abs(q2)-600e-9)>24e-9)
                rail = bool(np.any((out <= .050001) | (out >= 4.949999)))
                adc_clip = bool(np.any((adc < 0) | (adc > study.VREF)))
                sense = bool(np.any((mon <= .020001) | (mon >= 4.799999)))
                peak = bool(np.any(np.abs((mon-study.MID)/40) > 25.0107e-3))
                assert channel["integrator_saturated"] == rail
                assert channel["ADC_outside_measurement_range"] == adc_clip
                assert channel["sense_saturated"] == sense
                assert channel["current_guard_threshold_crossed"] == peak
                assert channel["range_or_bypassed_guard_fault_rejected"] == bool(rail or adc_clip or sense or case.forced_guard_bypass)
                ep = study.endpoints(case, source)
                assert set(channel["command_phase1_clock_strip_sweep_C"]) == {str(x) for x in (-1e-6,-1e-7,0.,1e-7,1e-6)}
                for shift in (-1e-6,-1e-7,0.,1e-7,1e-6):
                    a, b = ep["phase1_start"]+4e-9+shift, ep["phase1_edge"]+4e-9-shift
                    charge = -study.K0 * float(np.interp(b,t,adc)-np.interp(a,t,adc))
                    close(channel["command_phase1_clock_strip_sweep_C"][str(shift)], charge)
                if grid == min(study.GRIDS):
                    query = np.asarray(channel["oracle_queries_s"])
                    expected_query = np.unique(np.r_[np.linspace(10e-6,study.STOP,181), list(ep.values()),
                                                     [study.RESET_OPEN+v for v in (0.,.05e-6,.5e-6,1e-6,1.1e-6,1.202e-6,2e-6,5e-6)]])
                    assert np.array_equal(query, expected_query)
                    state = study.analytical_states(case, source, query)
                    expected_adc = study.MID + state[:, 5]
                    expected_out = study.MID + state[:, 3]
                    expected_mon = study.MID + state[:, 1]
                    clipped = (expected_out <= .05) | (expected_out >= 4.95) | (expected_mon <= .02) | (expected_mon >= 4.8)
                    valid = query < query[np.flatnonzero(clipped)[0]] if clipped.any() else np.ones(len(query), dtype=bool)
                    assert valid.tolist() == channel["oracle_linear_valid"]
                    assert int(valid.sum()) == channel["linear_oracle_comparison_samples"]
                    # 10nV cross-platform replay tolerance, separate from the frozen 20uV gate.
                    assert np.max(np.abs(expected_adc - channel["oracle_expected_ADC_V"])) < 1e-8
                    adc_error = float(np.max(np.abs(np.interp(query[valid], t, adc) - expected_adc[valid])))
                    out_error = float(np.max(np.abs(np.interp(query[valid], t, out) - expected_out[valid])))
                    close(adc_error, channel["linear_oracle_max_ADC_error_V"], 1e-8)
                    close(out_error, channel["linear_oracle_max_out_error_V"], 1e-8)
                    assert max(adc_error, out_error) < CRITERIA["linear_oracle_V"]
                    max_oracle = max(max_oracle, adc_error)
    with (HERE / "interval-results.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(csv_expected) == 462
    for actual, expected_row in zip(rows, csv_expected):
        assert set(actual) == set(expected_row)
        for key, expected_value in expected_row.items():
            if isinstance(expected_value, str):
                assert actual[key] == expected_value
            else:
                close(actual[key], expected_value)
    logs = json.loads((HERE / "ngspice-log.json").read_text(encoding="utf-8"))
    expected_tags = [f"{r['case']}__{int(round(r['max_step_s']*1e9))}ns" for r in result["runs"]]
    assert [l["run"] for l in logs] == expected_tags
    assert all(l["messages"] for l in logs)
    for log in logs:
        assert not any(word in "\n".join(log["messages"]).lower() for word in ("warning", "error", "failed", "convergence")), log["run"]
    expected_refinements = []
    for case in study.CASES:
        for coarse_grid, fine_grid in zip(study.GRIDS, study.GRIDS[1:]):
            coarse, fine = runs[(case.name, coarse_grid)], runs[(case.name, fine_grid)]
            delta = max(abs(a["raw_endpoint_charge_C"] - b["raw_endpoint_charge_C"])
                        for ca, cb in zip(coarse["channels"], fine["channels"])
                        for a, b in zip(ca["intervals"], cb["intervals"]))
            expected_refinements.append({"case": case.name, "coarse_step_s": coarse_grid,
                                         "fine_step_s": fine_grid, "max_interval_charge_delta_C": delta})
            if fine_grid == min(study.GRIDS):
                assert delta < CRITERIA["fine_grid_interval_delta_C"]
    assert result["refinement"] == expected_refinements
    return {"runs": 33, "channels": 66, "interval_rows": 462,
            "finest_grid_max_recomputed_ADC_oracle_error_V": max_oracle,
            "max_recomputed_KCL_residual_A": max_kcl, "four_percent_target_earned": False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args()
    evidence = validate()
    if args.write_receipt:
        receipt = {"schema": "scci_rh.stage4.monitoring-study.manifest.v1", "date": "2026-10-12",
                   "hash_policy": HASH_POLICY, "files": hashes(), "verification": evidence}
        RECEIPT.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["hash_policy"] == HASH_POLICY
    assert receipt["files"] == hashes(), "Study artifact set or content differs from reviewed receipt"
    assert receipt["verification"]["four_percent_target_earned"] is False
    print(json.dumps({"read_only_verification": "passed", **evidence}))

if __name__ == "__main__":
    main()
