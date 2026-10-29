"""Read-only saved-data verification; ngspice/DLL/GUI are not required.

Independent return-node charge conservation and a DC MOS/opamp equilibrium
check complement the saved nonlinear solver. Incomplete stress traces remain
in the inventory and never receive fabricated full-profile measurements.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import numpy as np
import study
import control_contract_study

HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "verification.json"
KCL_BUDGET_C = 0.02e-9
GRID_BUDGET_C = 0.2e-9


def close(a, b, atol=1e-14):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a: close(a[k], b[k], atol)
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b): close(x, y, atol)
    elif isinstance(a, float):
        assert math.isclose(a, b, rel_tol=2e-10, abs_tol=atol), (a, b)
    else:
        assert a == b, (a, b)


def independent_integral(t, y, a, b):
    keep = (t > a) & (t < b)
    times = np.concatenate(([a], t[keep], [b]))
    vals = np.concatenate(([np.interp(a,t,y)], y[keep], [np.interp(b,t,y)]))
    return float(np.sum(np.diff(times) * (vals[1:] + vals[:-1]) / 2))


def dc_oracle(polarization_V):
    # Independent static MOS saturation equation plus finite opamp DC gain.
    # Only nominal settled intervals, not switched edges, are compared.
    lo, hi = 0.001, 0.005
    for _ in range(80):
        current = (lo + hi) / 2
        vds = 24 - current * (1000 + 2*10 + 2 + 100) - polarization_V
        assert vds > 1
        gate = 100*current + 1.3 + math.sqrt(2*current / (0.05*(1 + 0.005*vds)))
        output = gate * (1 + (330 + 2) / 100000)
        residual = 100*current + output / 1e5 - study.VSET
        if residual > 0: hi = current
        else: lo = current
    return (lo + hi) / 2


def verify():
    result = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    assert result["schema"] == "scci_rh.stage4.driver-study.v1"
    assert not result["native_circuit_modified"] and not result["full_charge_accuracy_earned"]
    assert result["source_sha256"] == study.sha(HERE / "study.py")
    assert result["helper_source_sha256"] == study.sha(HERE.parent/"monitoring-study/ngspice_shared.py")
    assert result["cases"] == [study.asdict(c) for c in study.CASES]
    assert result["grids_s"] == list(study.GRIDS)
    assert len(result["runs"]) == 20
    original_control = json.loads(control_contract_study.RESULTS.read_text(encoding="utf-8"))
    assert control_contract_study.reproduce() == original_control
    assert original_control["summary"]["scenario_groups"] == 15
    seen, by_case, max_kcl, completed, intervals = set(), {}, 0.0, 0, 0
    for row in result["runs"]:
        key = row["case"], row["maximum_step_s"]
        assert key not in seen
        seen.add(key)
        c = next(c for c in study.CASES if c.name == row["case"])
        assert row["maximum_step_s"] in study.GRIDS
        lines, expected_vectors = study.circuit(c, row["maximum_step_s"])
        assert (HERE/row["netlist"]).read_text(encoding="utf-8") == "\n".join(lines)+"\n"
        with np.load(HERE/row["trace"]) as archive:
            data = {k: archive[k].copy() for k in archive.files}
        assert set(data) == set(expected_vectors) | {"time"}
        t = data["time"]
        assert len(t) == row["samples"] and np.all(np.diff(t)>0)
        assert all(len(x)==len(t) and np.isfinite(x).all() for x in data.values())
        assert row["completed"] == (t[-1] >= study.STOP*0.999)
        if not row["completed"]:
            assert row["solver_failure_retained"] and row["channels"] == []
            assert row["last_time_s"] == t[-1]
            continue
        completed += 1
        recomputed = study.analyze(c, row["maximum_step_s"], data)
        close(recomputed, {k:row[k] for k in recomputed})
        by_case[key] = row
        for ch in row["channels"]:
            s = str(ch["source"])
            load = (data[f"v(a{s})"]-data[f"v(pol{s})"]) / c.pair_R_ohm
            shunt = (data[f"v(ret{s})"]-data[f"v(br{s})"]) / 2
            for witness in ch["intervals"]:
                a, b = witness["start_s"], witness["end_s"]
                ql = independent_integral(t,load,a,b)
                qs = independent_integral(t,shunt,a,b)
                cap = c.common_mode_C_F * (np.interp(b,t,data[f"v(ret{s})"])-np.interp(a,t,data[f"v(ret{s})"]))
                residual = ql-qs-c.bias_load_A*(b-a)-cap
                assert abs(residual) < KCL_BUDGET_C
                max_kcl = max(max_kcl,abs(residual)); intervals += 1
            if c.name == "nominal":
                assert abs(ch["settled_first_current_A"] - dc_oracle(0.15)) < 2e-6
    maximum_grid_delta = 0.0
    for c in study.CASES:
        a = by_case.get((c.name,study.GRIDS[0])); b = by_case.get((c.name,study.GRIDS[1]))
        if a is None or b is None:
            assert a is None and b is None
            continue
        for x,y in zip(a["channels"],b["channels"]):
            for xx,yy in zip(x["intervals"],y["intervals"]):
                for field in ("load_charge_C","signed_shunt_charge_C","unsigned_feedback_charge_C"):
                    delta = abs(xx[field]-yy[field])
                    assert delta < GRID_BUDGET_C
                    maximum_grid_delta = max(maximum_grid_delta,delta)
    assert completed == 18 and intervals == 144
    with (HERE/"interval-results.csv").open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))
    expected_table = [dict(case=r["case"], maximum_step_s=r["maximum_step_s"],
                           source=c["source"], **w)
                      for r in result["runs"] for c in r["channels"] for w in c["intervals"]]
    assert len(table) == len(expected_table) == 144
    for saved, expected in zip(table, expected_table):
        assert set(saved) == set(expected)
        for key, value in expected.items():
            if isinstance(value, str): assert saved[key] == value
            else: assert float(saved[key]) == value
    assert 0.003 * 10000 > 24  # The forced load cannot support the requested current.
    included = sorted(p for p in HERE.rglob("*") if p.is_file() and p != RECEIPT
                      and "__pycache__" not in p.parts)
    return dict(schema="scci_rh.stage4.driver-study.verification.v1",date="2026-10-13",
                scope="Saved surrogate-circuit math and ideal digital contracts; no vendor/native/physical/biological qualification",
                attempted_transients=20,completed_transients=completed,retained_partial_transients=2,
                phase_gap_profile_intervals=intervals,maximum_integrated_KCL_residual_C=max_kcl,
                maximum_grid_charge_difference_C=maximum_grid_delta,
                numerical_budgets_C={"KCL":KCL_BUDGET_C,"grid_charge":GRID_BUDGET_C},
                dc_oracle_nominal_A=dc_oracle(0.15),control_contract=original_control["summary"],
                full_charge_accuracy_earned=False,
                hash_policy="Normalize CRLF/CR for text; exact NPZ/PNG; exclude this receipt/cache",
                sha256={p.relative_to(HERE).as_posix():study.sha(p) for p in included})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-receipt",action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.write_receipt:
        RECEIPT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
    else:
        assert result == json.loads(RECEIPT.read_text(encoding="utf-8")), "Review intentional artifact changes before refreshing receipt"
    print(json.dumps({k:result[k] for k in ("attempted_transients","completed_transients","retained_partial_transients","phase_gap_profile_intervals","maximum_integrated_KCL_residual_C","maximum_grid_charge_difference_C")}))
