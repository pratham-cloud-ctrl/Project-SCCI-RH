"""Independent saved-data audit of KCL, power flow, capacitor energy and resources.

Does not import or execute budget_study. All input files are read-only unless the
optional verification-report flag is requested. Failures stay failures.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
checks=0


def check(ok, why):
    global checks
    checks+=1
    if not ok:raise AssertionError(why)


def near(a,b,why):
    check(math.isclose(a,b,rel_tol=3e-10,abs_tol=1e-16),why)


def digest(p):
    b=p.read_bytes()
    if p.suffix in {".py",".json",".md"}:b=b.replace(b"\r\n",b"\n")
    return hashlib.sha256(b).hexdigest()


def verify():
    d=json.loads((HERE/"budget-results.json").read_text(encoding="utf-8"))
    near(d["battery"]["nominal_V"]*d["battery"]["capacity_Ah"],d["battery"]["nominal_Wh"],"battery nominalenergy")
    near(d["battery"]["nominal_Wh"]*.8,d["battery"]["usable_Wh"],"battery usableenergy")
    check(d["battery"]["design_operating_range_V"]==[6.4,8.4],"frozen2Srange")
    check(d["battery"]["onboard_charger"] is False,"no inventedimplantedcharger")
    inv=d["inventory"]
    for p,h in inv["source_sha256_lf"].items():check(digest(ROOT/p)==h,f"source changed:{p}")
    check(digest(HERE/"budget_study.py")==d["producer_sha256_lf"],"producer binding")
    row_totals=Counter()
    seen=set()
    for row in inv["active_load_rows"]:
        key=(row["package"],row["reference"],row["rail"])
        check(key not in seen,f"duplicateactive supplyallocation:{key}");seen.add(key)
        check(row["allocated_current_A"]>=0,"negativecurrent")
        check(row["source"].startswith("https://"),"missingprimaryURL")
        row_totals[row["rail"]]+=row["allocated_current_A"]
    for pkg,record in inv["packages"].items():
        src=json.loads((ROOT/"electronics"/"stage4"/pkg/"connectivity.json").read_text(encoding="utf-8"))
        u=[p for p in src["parts"]if p["ref"].startswith("U")]
        check(len(src["parts"])==record["components"],f"componentcount:{pkg}")
        check(len(u)==record["active_packages"],f"ICcount:{pkg}")
        check(dict(Counter(p["value"]for p in u))==record["active_values"],f"ICvalues:{pkg}")
        for part in u:
            matching=[r for r in inv["active_load_rows"]if r["package"]==pkg and r["reference"]==part["ref"]]
            check(bool(matching),f"activepartmissing:{pkg}/{part['ref']}")
            aliases={"+3V3":"HOST_3V3","VDD_3V3":"HOST_3V3","+5VA":"HOST_5",
                     "VDD_5":"HOST_5","VA_15":"HOST_15","VH_24":"HOST_24",
                     **{k:k for k in inv["rails"]}}
            actual={aliases[part["nets"][str(pin[0])]] for pin in part["pins"]
                    if "power"in str(pin[2]) and part["nets"].get(str(pin[0]))in aliases}
            check(actual=={r["rail"]for r in matching},f"physicalpowerpinallocation:{pkg}/{part['ref']}")
    for rail,row in inv["rails"].items():
        near(row_totals[rail],row["active_allocations_A"],f"ICsum:{rail}")
        near(row["active_allocations_A"]+row["passive_dynamic_output_load_contingency_A"],row["static_design_ceiling_A"],f"currentKCL:{rail}")
        check(row["passive_dynamic_output_load_contingency_A"]>=0,f"negativecontingency:{rail}")
        near(row["static_design_ceiling_A"]*row["nominal_magnitude_V"],row["static_design_ceiling_W"],f"railVI:{rail}")
    modes={c["mode"]:c for c in d["operating_cases"]}
    for case in d["operating_cases"]:
        rails=case["rail_currents_A"]
        enabled=case["is_complete_system_operating_case"]
        vi=sum(i*inv["rails"][k]["nominal_magnitude_V"]for k,i in rails.items())
        near(vi,case["rail_useful_load_W"],"allrailVI")
        if enabled:
            near(case["iso_positive_current_A"],rails["AFE_3V3"]+rails["AFE_P5"]+.002,"isolatedpositiveKCL")
            near(case["iso_negative_current_A"],rails["AFE_N5"]+.001,"isolatednegativeKCL")
        else:
            check(case["supervision_only_excludes_disabled_host_feedthrough_leakage_and_is_lower_bound"],"standbylowerboundlabel")
        near(12*(case["iso_positive_current_A"]+case["iso_negative_current_A"]),case["isolated_module_output_W"],"moduledualrailVI")
        near(case["LDO_outputs_W"]+case["LDO_loss_W"],case["isolated_module_output_W"],"LDOenergybalance")
        near(case["isolated_module_output_W"]+case["isolated_module_loss_W"],case["isolated_module_input_W"],"moduleenergybalance")
        check(case["iso_positive_current_A"]<=.125 and case["iso_negative_current_A"]<=.125,"nominalmodulecurrentratings")
        check(case["isolated_module_output_W"]<=3,"module3Wrating")
        stage_input=0.0
        for s in case["converter_stages"]:
            near(s["input_W"]*s["load_dependent_efficiency_assumed"],s["output_W"]+6.9*s["fixed_input_current_allocation_A"]*s["load_dependent_efficiency_assumed"],"switcherpowerflow")
            near(s["input_W"]-s["output_W"],s["loss_W"],"switcherloss")
            check(s["loss_W"]>=0,"switchernegativeheat")
            if s["rail"]=="HOST_5":near(s["output_W"],5*rails["HOST_5"]+case["isolated_module_input_W"],"HOST5feedsislandexactlyonce")
            stage_input+=s["input_W"]
        near(stage_input,case["pre_diode_bus_load_W"],"busKCLpower")
        for b in case["battery_cases"]:
            near(b["battery_A"]*b["bus_V"],stage_input,"batteryconstantpower")
            near(b["battery_W"],stage_input+b["diode_W"],"diodeenergybalance")
            check(b["battery_A"]<2,"selectedDCloadbelow2Afuserating")
            check(b["battery_A"]<5,"selectedDCloadbelow5Apackrating")
        near(case["battery_nominal_W"],case["battery_cases"][1]["battery_W"],"nominalbatteryrow")
        near(case["runtime_h_at80percent_nominal_energy"]*case["battery_nominal_W"],15.392,"runtimeenergy")
        near(case["device_heat_upper_allocation_W"]+case["artificial_external_load_average_W"],case["battery_nominal_W"],"heatplusloadenergy")
    active=modes["restricted-active"]
    stim_q_per_second=2*.003*2*200e-6*100
    near(active["stimulation_rail_average_W"],24*stim_q_per_second,"biphasiccurrentdutyenergy")
    near(active["artificial_external_load_average_W"],2*.003**2*1000*.04,"artificialresistorheat")
    check(active["battery_cases"][1]["battery_A"]>.1,"old100mAcellcapmustreject")
    for r in d["reservoir"]["cases"]:
        q=r["sources"]*.003*r["integrated_on_time_s"]
        near((r["drop_V"]-r["sources"]*.003*r["assumed_ESR_ohm"])*r["effective_C_F"],q,"reservoirchargeconservation")
        near(r["final_V"]+r["drop_V"],r["initial_V"],"reservoirvoltagebalance")
        check(r["passes_nominal_UV_margin"]==(r["final_V"]>22.8),"reservoiracceptance")
    check(any(not r["passes_nominal_UV_margin"]for r in d["reservoir"]["cases"]),"missingbrownoutsmallcapwitness")
    for b in d["brownout_sensitivity"]:
        if b["bus_V"]is not None:
            near(b["input_A"]*b["bus_V"],b["peak_bus_power_W"],"sourceconstantpower")
            near(b["bus_V"]+.5+b["input_A"]*b["assumed_source_R_ohm"],b["pack_open_circuit_V"],"sourcevoltageKVL")
            near(b["input_A"]**2*b["assumed_source_R_ohm"],b["source_resistance_loss_W"],"sourceJouleheat")
            check(b["admitted_underload_bus_atleast5p9V"]==(b["bus_V"]>=5.9),"sourcebrownoutcriterion")
        else:check(b["load_line_discriminant_V2"]<0 and not b["admitted_underload_bus_atleast5p9V"],"loadlinecollapse")
    check(any(not b["admitted_underload_bus_atleast5p9V"]for b in d["brownout_sensitivity"]),"missingbrownoutrejections")
    for h in d["thermal_sensitivity"]:
        near(h["steady_rise_K"],h["assumed_system_thermal_resistance_K_per_W"]*active["device_heat_upper_allocation_W"],"lumpedthermalrise")
        check(not h["selected2Krise_allocation_pass"],"selectedthermalcasescannotbeclaimedclosed")
    near(d["required_lumped_Rth_for2Krise_K_per_W"]*active["device_heat_upper_allocation_W"],2,"thermalRrequirement")
    resources=d["resources"]
    near(sum(resources["RAM_allocations_bytes"].values()),resources["RAM_total_bytes"],"RAMsum")
    near(resources["RAM_total_bytes"]+resources["RAM_capacity_bytes"]*resources["RAM_headroom_fraction"],resources["RAM_capacity_bytes"],"RAMheadroom")
    check(resources["RAM_total_bytes"]==404992,"historicalRAMreservationchanged")
    check(resources["RAM_20percent_headroom_pass"],"RAMreserve")
    check(resources["actual_aggregate_ADC_words_per_s"]==2*100000,"actualADCrate")
    check(resources["old_planned_monitor_words_per_s"]>resources["actual_aggregate_ADC_words_per_s"]and not resources["old_monitor_schedule_admitted"],"overratewitness")
    near(resources["neural_burst_occupancy"],19*5e-6*4000,"neuraloccupiedtime")
    check(resources["raw4k_framed_bits_per_s"]>1_000_000 and not resources["raw1Mbitservice_can_carry_continuous4k"],"rawlinkratewitness")
    near(sum(resources["MAC_operations_per_s"].values()),2_886_400,"MACarithmetic")
    for c in resources["CPU_allocation_cases"]:
        expected=(2_886_400*10+1_200_000+3_000_000+c["monitor_words_per_s"]*10)*1.15
        near(c["reserved_cycles_per_s"],expected,"CPUarithmetic")
        near(c["fraction_at128MHz"],expected/128_000_000,"CPU128fraction")
        check(c["within60percent_at128MHz"],"CPU128allocationfits")
        check(not c["within60percent_at64MHz"],"CPU64allocationmustreject")
        check(c["ADC_capacity_admitted"]==(c["monitor_words_per_s"]<=200000),"CPUfitdoesnotcreateADCrate")
    start=d["startup"]
    check(digest(ROOT/"electronics"/"stage4"/"supervision-study"/"analog-results.json")==start["source_sha256_lf"],"startupthresholdbinding")
    check(digest(ROOT/"electronics"/"stage4"/"power"/"connectivity.json")==start["power_native_source_sha256_lf"],"newnativebinding")
    cap_actual={}
    for pkg in (*inv["packages"],"power"):
        source=json.loads((ROOT/"electronics"/"stage4"/pkg/"connectivity.json").read_text(encoding="utf-8"))
        for part in source["parts"]:
            if part["ref"].startswith("C")and "DNP"not in part["value"].upper():cap_actual[(pkg,part["ref"])]=part
    check(len(cap_actual)==len(start["all_six_package_capacitors"]),"allpopulatedcapacitorspresent")
    cap_ids={(r["package"],r["reference"])for r in start["all_six_package_capacitors"]}
    check(cap_ids==set(cap_actual),"exactnativecapacitorset")
    e=0
    for c in start["all_six_package_capacitors"]:
        actual=cap_actual[(c["package"],c["reference"])]
        check(c["value"]==actual["value"],"nativecapacitorvaluematches")
        first=actual["value"].split()[0].lower().replace("f","")
        suffix=first[-1]
        factor={"p":1e-12,"n":1e-9,"u":1e-6,"µ":1e-6,"m":1e-3}
        independent_C=float(first[:-1])*factor[suffix] if suffix in factor else float(first)
        near(independent_C,c["capacitance_F"],"nativecapacitorunitconversion")
        near(.5*c["capacitance_F"]*c["voltage_bound_V"]**2,c["nominal_stored_energy_bound_J"],"capacitorenergy")
        e+=c["nominal_stored_energy_bound_J"]
    near(e,start["nominal_capacitor_energy_bound_J"],"allcapacitorenergy")
    near(e*1.2,start["plus20percent_capacitance_energy_bound_J"],"capacitorpositiveallowance")
    for ramp in start["charge_energy_sensitivity"]:
        near(ramp["additional_average_input_current_A_at5p9V"]*5.9*ramp["assumed_charge_time_s"],e*1.2/.5,"startupinputenergy")
    check(any(not r["additional_average_alone_below2A_rating"]for r in start["charge_energy_sensitivity"]),"faststartuprejectionwitness")
    for q in start["rail_qualification"]:
        lo,hi=q["rail_range_V"]
        check(q["all_corner_cold_start_pass"]==(lo>q["all_corner_cold_start_UV_limit_V"]and hi<q["all_corner_cold_start_OV_limit_V"]),"startuprailgate")
    check(all(q["all_corner_cold_start_pass"]for q in start["rail_qualification"]if q["case"].startswith("conditional")),"conditionaltrimstartup")
    check(any(not q["all_corner_cold_start_pass"]for q in start["rail_qualification"]if q["case"].startswith("untrimmed")),"untrimmedstartupfailurewitness")
    return {"schema":"scci_rh.stage4.power-budget-audit.v1","status":"passed","independent_assertions":checks,
            "results_sha256_lf":digest(HERE/"budget-results.json"),
            "unearned_claims_preserved":["untrimmedAFEstartup","450kADCcapacity","1Mbitraw4klink","2Kthermalclosure","all-conditionefficiency","physicalconvertertransients"]}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report",action="store_true")
    args=parser.parse_args();result=verify()
    if args.write_report:(HERE/"budget-verification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(result,indent=2))
