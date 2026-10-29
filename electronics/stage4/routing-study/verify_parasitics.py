"""Independent scalar charge and RC audits of saved routing evidence; read-only."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import numpy as np

HERE = Path(__file__).resolve().parent


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-19), (a, b)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-receipt", action="store_true")
    args = ap.parse_args()
    data = json.loads((HERE/"parasitic-results.json").read_text(encoding="utf-8"))
    assert len(data["rows"]) == 36
    sha = hashlib.sha256((HERE/"parasitic_study.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert sha == data["source_sha256_lf"]
    seen = set()
    checks = 0
    max_charge_residual = 0.0
    with np.load(HERE/"parasitic-traces.npz") as traces:
        for row in data["rows"]:
            combo = (row["contact_capacitance_F_assumed"], row["bus0_mutual_F_assumed"], row["pattern"])
            assert combo not in seen
            seen.add(combo)
            ct = row["contact_capacitance_F_assumed"] + row["off_source_shunt_F_assumed"] + row["bus0_mutual_F_assumed"] + row["bus1_mutual_F_assumed"]
            close(ct, row["total_capacitance_F"])
            prior, prior_t = 0., 0.
            q_ground = 0.
            q_abs = 0.
            injected = 0.
            peak = 0.
            for e in row["events"]:
                before = prior / math.exp((e["time_s"]-prior_t)/(row["discharge_R_ohm_assumed"]*ct))
                q = row["bus0_mutual_F_assumed"]*e["bus0_delta_V"] + row["bus1_mutual_F_assumed"]*e["bus1_delta_V"]
                dq = ct*(prior-before)
                close(before, e["before_V"])
                close(q, e["coupled_charge_C"])
                close(ct*(e["after_V"]-before), q)
                close(dq, e["ground_charge_since_prior_C"])
                q_ground += dq
                q_abs += abs(dq)
                injected += q
                peak = max(peak, abs(before), abs(e["after_V"]))
                prior, prior_t = e["after_V"], e["time_s"]
                checks += 4
            # Integrated KCL from initially uncharged to final stored charge.
            residual = abs(injected - q_ground - ct*prior)
            max_charge_residual = max(max_charge_residual, residual)
            assert residual < 1e-21
            close(q_ground, row["signed_ground_charge_C"])
            close(q_abs, row["absolute_ground_charge_C"])
            close(peak, row["max_abs_victim_V"])
            a = traces[row["trace_key"]]
            assert a.shape[1] == 2 and np.isfinite(a).all()
            assert np.diff(a[:,0]).min() >= -1e-15
            close(abs(a[:,1]).max(), peak)
            close(a[-1,1], row["final_victim_V"])
            # Independently expand superposition of every charge impulse rather
            # than executing the producer's recursive interval evolution.
            # Duplicate edge timestamps retain both the pre-edge and post-edge
            # values; the first occurrence excludes that instant's impulse.
            for index, (time, actual) in enumerate(a):
                before_edge = index+1 < len(a) and abs(a[index+1,0]-time) < 1e-15
                expected = 0.
                for e in row["events"]:
                    delta = time-e["time_s"]
                    if delta < -1e-15 or (abs(delta) < 1e-15 and before_edge):
                        continue
                    q = row["bus0_mutual_F_assumed"]*e["bus0_delta_V"] + row["bus1_mutual_F_assumed"]*e["bus1_delta_V"]
                    expected += q/ct*math.exp(-max(delta,0.)/(row["discharge_R_ohm_assumed"]*ct))
                assert math.isclose(actual,expected,rel_tol=1e-9,abs_tol=1e-15),(row["case"],index,actual,expected)
                checks += 1
            checks += 8
    matched = [r for r in data["rows"] if r["pattern"] == "opposed_matched"]
    asymmetric = [r for r in data["rows"] if r["pattern"] == "opposed_asymmetric"]
    assert all(r["max_abs_victim_V"] == 0 for r in matched)
    assert all(r["max_abs_victim_V"] > 0 for r in asymmetric)
    assert len(seen) == 36
    p = data["illustrative_budget"]
    close(p["current_A"]*p["phase_s"], p["nominal_phase_C"])
    for r,v in zip(p["router_on_R_ohm_assumed"],p["router_voltage_drops_V"]): close(p["current_A"]*r,v)
    close(p["on_capacitance_fixture_F"]*24, p["on_capacitance_24V_edge_charge_C"])
    close(p["off_paths_with_two_distinct_active_contacts"]*p["per_path_leakage_A_assumed"]*p["phase_s"],p["sum_absolute_off_path_charge_per_200us_C"])
    checks += 9
    paths = ["parasitic_study.py", "verify_parasitics.py", "parasitic-results.json", "parasitic-traces.npz", "build_parasitic_figures.py", "router-parasitics.png", "router-parasitics.svg", "README.md"]
    hashes = {}
    for name in paths:
        b = (HERE/name).read_bytes()
        if Path(name).suffix not in (".png", ".npz"): b = b.replace(b"\r\n",b"\n")
        hashes[name] = hashlib.sha256(b).hexdigest()
    receipt = {"schema":"scci_rh.stage4.router-parasitic-audit.v1", "scalar_charge_RC_checks":checks,
               "cases":36,"max_absolute_KCL_residual_C":max_charge_residual,
               "sha256_lf_text_exact_binary":hashes}
    if args.write_receipt:
        (HERE/"parasitic-verification.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    else:
        saved=json.loads((HERE/"parasitic-verification.json").read_text(encoding="utf-8"))
        assert saved["sha256_lf_text_exact_binary"] == hashes
        assert saved["scalar_charge_RC_checks"] == checks
        assert saved["max_absolute_KCL_residual_C"] < 1e-21
    print(f"Router parasitic audit: {checks} scalar/charge/RC checks across36 cases; maxKCL {max_charge_residual:.3g} C")


if __name__ == "__main__": main()
