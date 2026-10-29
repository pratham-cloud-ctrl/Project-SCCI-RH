"""SCCI_RH-S4-PWR: finite, assumption-explicit electrical and resource budget.

Default invocation only checks the saved result. Writing is opt-in. This is a
steady-state/energy calculation, not a converter switching or tissue simulation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKAGES = ("monitoring-cell", "current-driver", "recording-front-end", "contact-router", "supervision")
V = {"HOST_3V3": 3.3, "HOST_5": 5.0, "HOST_15": 15.0, "HOST_24": 24.0,
     "SUP_3V3": 3.3, "SUP_5": 5.0, "AFE_3V3": 3.45, "AFE_P5": 5.30, "AFE_N5": 5.10}
CEILING_A = {"HOST_3V3": .070, "HOST_5": .020, "HOST_15": .005, "HOST_24": .005,
             "SUP_3V3": .025, "SUP_5": .006, "AFE_3V3": .035, "AFE_P5": .010, "AFE_N5": .005}
ALIASES = {"+3V3": "HOST_3V3", "VDD_3V3": "HOST_3V3", "+5VA": "HOST_5", "VDD_5": "HOST_5",
           "VA_15": "HOST_15", "VH_24": "HOST_24", **{k: k for k in V}}
SOURCE = {
 "tlv3202": "https://www.ti.com/lit/ds/symlink/tlv3202.pdf",
 "iso674x": "https://www.ti.com/lit/ds/symlink/iso6741.pdf",
 "tmux7412f": "https://www.ti.com/lit/ds/symlink/tmux7412f.pdf",
 "tmux6219": "https://www.ti.com/lit/ds/symlink/tmux6219.pdf",
 "ina241a": "https://www.ti.com/lit/ds/symlink/ina241a.pdf",
 "ads8866": "https://www.ti.com/lit/ds/symlink/ads8866.pdf",
 "dac80502": "https://www.ti.com/lit/ds/symlink/dac80502.pdf",
 "opa192": "https://www.ti.com/lit/ds/symlink/opa192.pdf",
 "opa391": "https://www.ti.com/lit/ds/symlink/opa391.pdf",
 "lvc": "https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf",
 "rhd": "https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf",
 "battery": "https://power.tenergy.com/AT-7.4-2600mAh-5A-batterypack/",
 "traco": "https://www.tracopower.com/products/tmr3.pdf",
 "lt8330": "https://www.analog.com/media/en/technical-documentation/data-sheets/lt8330.pdf",
 "tps62160": "https://www.ti.com/lit/ds/symlink/tps62160.pdf",
 "tps62130": "https://www.ti.com/lit/ds/symlink/tps62130.pdf",
 "tps7a49": "https://www.ti.com/lit/ds/symlink/tps7a49.pdf",
 "tps7a30": "https://www.ti.com/lit/ds/symlink/tps7a30.pdf",
}


def sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix in {".py", ".json", ".md"}:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def current_allocation(value: str, rail: str) -> tuple[float, str, str]:
    """Per-package allocation; all rows are design bounds, not vendor guarantees."""
    if value.startswith("SN74LVC1G"):
        return 10e-6, "lvc", "10uA static allocation per single gate; switching and output-load current separate"
    if value.startswith("SN74LVC"):
        return 100e-6, "lvc", "100uA static allowance per multi-gate package; switching and output loads separate"
    if value.startswith("ISO674"):
        return .008, "iso674x", "8mA per powered side; envelope of selected 3.3V +/-10% DC/1/10Mbps table rows,15pF; mixed rails/duty still require test"
    table = {"REF3440": (20e-6, "https://www.ti.com/lit/ds/symlink/ref3440.pdf"),
             "OPA391": (50e-6, "opa391"), "TMUX1136": (10e-6, "https://www.ti.com/lit/ds/symlink/tmux1136.pdf"),
             "INA241": (.004, "ina241a"), "ADS8866": (.001, "ads8866"),
             "TLV3202": (130e-6, "tlv3202"), "DAC80502": (.003, "dac80502"),
             "OPA2192": (.003, "opa192"), "OPA192": (.0015, "opa192"),
             "TMUX7212": (.0002, "https://www.ti.com/lit/ds/symlink/tmux7212.pdf"),
             "TMUX6208": (.0001, "https://www.ti.com/lit/ds/symlink/tmux6208.pdf"),
             "LTC6993": (.0001, "https://www.analog.com/media/en/technical-documentation/data-sheets/69931234fc.pdf"),
             "TPS3700": (20e-6, "https://www.ti.com/lit/ds/symlink/tps3700.pdf"),
             "TPS3431": (20e-6, "https://www.ti.com/lit/ds/symlink/tps3431.pdf"),
             "RHD2216": (.0012, "rhd")}
    if value.startswith("TMUX7412F"):
        return (.0005 if rail == "AFE_N5" else .0006), "tmux7412f", "allocation from +/-22V full-temperature supply rows; applied conservatively to selected rails, excludes load current"
    if value.startswith("TMUX6219"):
        a = .000015 if rail == "AFE_N5" else (.00005 if rail == "AFE_P5" else .0001)
        return a, "tmux6219", "dual-supply +50/-15uA allocation; single15V +100uA allowance; load current excluded"
    for prefix, (a, source) in table.items():
        if value.startswith(prefix):
            return a, source, "declared finite per-package current ceiling; not an all-condition vendor maximum"
    raise ValueError(f"Unallocated active component {value}")


def inventory() -> dict:
    rows, packages, bound = [], {}, {}
    sums = {k: 0.0 for k in V}
    for package in PACKAGES:
        p = ROOT / "electronics" / "stage4" / package / "connectivity.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        components = d["parts"]
        active = [x for x in components if x["ref"].startswith("U")]
        packages[package] = {"components": len(components), "active_packages": len(active),
                             "active_values": dict(sorted(Counter(x["value"] for x in active).items()))}
        bound[str(p.relative_to(ROOT)).replace("\\", "/")] = sha(p)
        for part in active:
            rails = sorted({ALIASES[part["nets"][str(pin[0])]] for pin in part["pins"]
                            if "power" in str(pin[2]) and part["nets"].get(str(pin[0])) in ALIASES})
            if not rails:
                raise ValueError(f"No recognized supply: {package}/{part['ref']}")
            for rail in rails:
                a, source, status = current_allocation(part["value"], rail)
                rows.append({"package": package, "reference": part["ref"], "value": part["value"],
                             "rail": rail, "allocated_current_A": a, "source": SOURCE.get(source, source),
                             "evidence_class": "declared design allocation informed by primary data", "condition": status})
                sums[rail] += a
    # Newly implemented power-window and enable logic are actual extra loads.
    native_path=ROOT/"electronics"/"stage4"/"power"/"connectivity.json"
    native=json.loads(native_path.read_text(encoding="utf-8"))
    control_parts=[p for p in native["parts"] if p["value"].startswith(("SN74LVC","TPS3700"))]
    for part in control_parts:
        rail="SUP_3V3"
        a,source,status=current_allocation(part["value"],rail)
        rows.append({"package":"power", "reference":part["ref"], "value":part["value"],
                     "rail":rail, "allocated_current_A":a, "source":SOURCE.get(source,source),
                     "evidence_class":"declared design allocation informed by primary data", "condition":status})
        sums[rail]+=a
    bound[str(native_path.relative_to(ROOT)).replace("\\","/")]=sha(native_path)
    # This MCU is reserved by the existing architecture, not yet a native part.
    sums["HOST_3V3"] += .015
    rows.append({"package": "future-controller", "reference": "nRF5340-allocation", "value": "nRF5340",
                 "rail": "HOST_3V3", "allocated_current_A": .015,
                 "source": "https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/current_consumption/doc/current_consumption.html",
                 "evidence_class": "reserved design allocation; native controller/firmware not implemented",
                 "condition": "15mA @3.3V ceiling reserved beyond older35mW allowance; actual firmware energy not measured"})
    rail_rows = {}
    for rail in V:
        if sums[rail] > CEILING_A[rail]:
            raise AssertionError(f"{rail} active allocation exceeds design ceiling")
        rail_rows[rail] = {"nominal_magnitude_V": V[rail], "active_allocations_A": sums[rail],
                           "passive_dynamic_output_load_contingency_A": CEILING_A[rail] - sums[rail],
                           "static_design_ceiling_A": CEILING_A[rail],
                           "static_design_ceiling_W": V[rail]*CEILING_A[rail],
                           "ceiling_status": "conditional design load cap, not measured maximum; includes unmodeled passives and switching"}
    return {"packages": packages, "power_control_active_packages":len(control_parts),
            "source_sha256_lf": bound, "active_load_rows": rows, "rails": rail_rows}


def power_case(inv: dict, mode: str, buck_eta: float = .80, boost_eta: float = .75, iso_eta: float = .65) -> dict:
    """All nonstimulating loads held at declared caps; no invented typical-system figure."""
    enabled = mode != "supervision-only"
    load = {k: CEILING_A[k] if enabled or k.startswith("SUP_") else 0.0 for k in V}
    # biphasic 2x200us,100Hz per source, two aligned3mA sources.
    stim_average_A = 2*.003*2*200e-6*100 if mode == "restricted-active" else 0.0
    load["HOST_24"] += stim_average_A
    # 100uA no-load datasheet maximum is not the loaded ground-current bound.
    # Allocate1mA per loaded LDO, including unearned load-dependent excess.
    ldo_iq = {"AFE_3V3": .001, "AFE_P5": .001, "AFE_N5": .001}
    iso_pos_A = sum(load[k]+ldo_iq[k] for k in ("AFE_3V3", "AFE_P5")) if enabled else 0.0
    iso_neg_A = load["AFE_N5"]+ldo_iq["AFE_N5"] if enabled else 0.0
    iso_output_W = 12*(iso_pos_A+iso_neg_A)
    # Fixed module overhead allocation and load-dependent efficiency are separate.
    # TMR3-0522 no-load input current is60mA TYP at5V, not a maximum.
    iso_fixed_W = .30 if enabled else 0.0
    iso_input_W = iso_output_W/iso_eta + iso_fixed_W
    ldo_output_W = sum(load[k]*V[k] for k in ("AFE_3V3", "AFE_P5", "AFE_N5"))
    ldo_loss_W = iso_output_W-ldo_output_W
    direct_outputs = {k: load[k]*V[k] for k in ("SUP_3V3", "SUP_5", "HOST_3V3", "HOST_5", "HOST_15", "HOST_24")}
    # HOST5 feeds isolatedmodule in addition to its host load; no double counting.
    direct_outputs["HOST_5"] += iso_input_W
    iq_A = {"SUP_3V3": 50e-6, "SUP_5": 50e-6, "HOST_3V3": 50e-6,
            "HOST_5": 100e-6, "HOST_15": .0012, "HOST_24": .0012}
    bus_V = 7.4-.5
    stages = []
    for rail, pout in direct_outputs.items():
        if not enabled and not rail.startswith("SUP_"):
            continue
        eta = boost_eta if rail in {"HOST_15", "HOST_24"} else buck_eta
        pin = pout/eta+bus_V*iq_A[rail]
        stages.append({"rail": rail, "output_W": pout, "load_dependent_efficiency_assumed": eta,
                       "fixed_input_current_allocation_A": iq_A[rail], "input_W": pin, "loss_W": pin-pout})
    bus_W = sum(x["input_W"] for x in stages)
    # Constant-power plus seriesdiode model solved exactly at each battery voltage.
    input_cases = []
    for battery_V in (6.4,7.4,8.4):
        a = bus_W/(battery_V-.5)
        input_cases.append({"battery_V":battery_V,"bus_V":battery_V-.5,"battery_A":a,
                            "battery_W":battery_V*a,"diode_W":.5*a})
    battery_W = input_cases[1]["battery_W"]
    useful_load_W = sum(load[k]*V[k] for k in V)
    stim_load_W = stim_average_A*24
    # Exact example1000ohm resistive load, equal3mA currents; rest conservatively heat.
    external_load_W = 2*(.003**2)*1000*(2*200e-6*100) if stim_average_A else 0.0
    heat_W = battery_W-external_load_W
    return {"mode":mode,"is_complete_system_operating_case":enabled,
            "supervision_only_excludes_disabled_host_feedthrough_leakage_and_is_lower_bound":not enabled,
            "rail_currents_A":load,"rail_useful_load_W":useful_load_W,
            "stimulation_rail_average_W":stim_load_W,"artificial_external_load_average_W":external_load_W,
            "iso_positive_current_A":iso_pos_A,"iso_negative_current_A":iso_neg_A,
            "isolated_module_output_W":iso_output_W,"isolated_module_fixed_overhead_allocation_W":iso_fixed_W,
            "isolated_module_input_W":iso_input_W,"isolated_module_loss_W":iso_input_W-iso_output_W,
            "LDO_loss_W":ldo_loss_W,"LDO_outputs_W":ldo_output_W,"converter_stages":stages,
            "pre_diode_bus_load_W":bus_W,"battery_cases":input_cases,"battery_nominal_W":battery_W,
            "device_heat_upper_allocation_W":heat_W,"runtime_h_at80percent_nominal_energy":19.24*.8/battery_W,
            "heat_interpretation":"batteryinput minus artificialexternalresistor energy; all other energy conservatively assigned to electronics/pack heat"}


def reservoir() -> dict:
    rows=[]
    for c in (2e-6,10e-6,30e-6,100e-6):
        for simultaneous in (1,2):
            i=simultaneous*.003
            for t in (200e-6,400e-6,264e-6):
                droop=i*t/c+i*.1
                rows.append({"effective_C_F":c,"sources":simultaneous,"integrated_on_time_s":t,
                             "assumed_ESR_ohm":.1,"drop_V":droop,"initial_V":24*.98,
                             "final_V":24*.98-droop,"uv_rising_design_V":22.8,
                             "passes_nominal_UV_margin":24*.98-droop>22.8,
                             "assumption":"no replenishment duringon-time; gap contributes no load increment; fullrailstaticload supplied by converter"})
    return {"cases":rows,"required_effective_C_F_for2x200us_6mA_0p5Vdrop":.006*400e-6/(.5-.006*.1),
            "capacitor_electrical_energy_J_at24V_30uF":.5*30e-6*24**2,
            "remaining_energy_not_harmless_or_a_shutdown_source":True}


def resources() -> dict:
    p = ROOT/"docs"/"stage2"/"acquisition-budget-inputs.json"
    d=json.loads(p.read_text(encoding="utf-8"))
    allocations=d["storage"]["RAM_allocations_bytes"]
    total=sum(allocations.values())
    neural_slots=19
    neural_burst_s=neural_slots*5e-6
    macs={"biquads":16*4000*4*5,"envelopes":16*4000*4*2,
          "archive_FIR":16*2000*31,"linear_witness":64*8*200}
    cpu=[]
    for monitor_rate in (200000,450000):
        cycles=(sum(macs.values())*10+4000*300+3_000_000+monitor_rate*10)*1.15
        cpu.append({"monitor_words_per_s":monitor_rate,"reserved_cycles_per_s":cycles,
                    "fraction_at128MHz":cycles/128e6,"within60percent_at128MHz":cycles<=.6*128e6,
                    "fraction_at64MHz":cycles/64e6,"within60percent_at64MHz":cycles<=.6*64e6,
                    "ADC_capacity_admitted":monitor_rate<=200000})
    # Native2x100ksps; old450k reservation is retained as rejected witness.
    return {"stage2_source_sha256_lf":sha(p),"streams":16,"neural_frames_per_s":4000,
            "neural_SPI_Hz":4_000_000,"neural_burst_s":neural_burst_s,
            "neural_burst_occupancy":neural_burst_s*4000,
            "neural_wire_bits_per_s":19*16*4000,
            "monitor_SPI_Hz":16_000_000,"old_planned_monitor_words_per_s":450000,
            "actual_ADC_count":2,"actual_ADC_max_words_per_s_each":100000,
            "actual_aggregate_ADC_words_per_s":200000,"old_monitor_schedule_admitted":False,
            "native_monitor_fullrate_wire_occupancy":200000*16/16_000_000,
            "old_monitor_wire_occupancy":450000*16/16_000_000,
            "ADC_rate_limitation":"ADS8866conversioncapacity rejects450kaggregate even thoughSPIwireoccupancyfits; no synthesizeddataorclaimed200kspsperADC",
            "archive_frame_bytes":48,"archive_frames_per_s":2000,"archive_window_s":2,
            "RAM_allocations_bytes":allocations,"RAM_total_bytes":total,"RAM_capacity_bytes":524288,
            "RAM_fraction":total/524288,"RAM_headroom_fraction":1-total/524288,
            "RAM_20percent_headroom_pass":total<=.8*524288,
            "normal_feature_payload_bits_per_s":51200,"Stage4_provisional_normal_link_ceiling_bits_per_s":160000,
            "raw4k_framed_bits_per_s":192000*8,"raw1Mbitservice_can_carry_continuous4k":False,
            "MAC_operations_per_s":macs,"CPU_allocation_cases":cpu,
            "assumed_cycles_per_MAC":10,"CPU_contingency_fraction":.15,
            "unearned":"CSgaps/arbitration/CPUWCET/linkpacketoverhead/actualfirmwareRAMandenergy remain laterpackage obligations"}


def startup() -> dict:
    p=ROOT/"electronics"/"stage4"/"supervision-study"/"analog-results.json"
    prior=json.loads(p.read_text(encoding="utf-8"))
    rows=[]
    for rail in prior["rail_windows"]:
        name=rail["rail"].replace("AFE_N5_MAG","AFE_N5")
        tol=.025 if name.startswith("AFE") else .02
        for error,name_of_case in ((tol,"untrimmed declared error"),(.005,"conditional selected/trimmed error")):
            low,high=V[name]*(1-error),V[name]*(1+error)
            b=rail["corner_bounds"]
            passed=low>b["UV_rising_V"][1] and high<b["OV_rising_V"][0]
            rows.append({"rail":name,"case":name_of_case,"fraction_error":error,"rail_range_V":[low,high],
                         "all_corner_cold_start_UV_limit_V":b["UV_rising_V"][1],
                         "all_corner_cold_start_OV_limit_V":b["OV_rising_V"][0],
                         "all_corner_cold_start_pass":passed,
                         "nominal_OV_recovery_guaranteed":rail["nominal_OV_recovery_guaranteed"]})
    # Bind actual native power parts and all six packages' capacitors. For an
    # unknown internal capacitor voltage, use the package supply span as an
    # intentionally loose energy bound. DNP compensation footprints are skipped.
    native_path=ROOT/"electronics"/"stage4"/"power"/"connectivity.json"
    native=json.loads(native_path.read_text(encoding="utf-8"))
    pots={**V,"AFE_N5":-5.1,"VH_24":24,"PACK_BUS":7.9,"PACK_POS":8.4,
          "ISO_P12":12,"ISO_N12":-12,"GND":0,"AFEAGND":0,"HOSTGND":0,
          "+3V3":3.3,"VDD_3V3":3.3,"+5VA":5,"VDD_5":5,"VA_15":15}
    maxspan={"monitoring-cell":5,"current-driver":24,"recording-front-end":10.4,
             "contact-router":24,"supervision":24,"power":24}
    caprows=[]
    for pkg in (*PACKAGES,"power"):
        src=ROOT/"electronics"/"stage4"/pkg/"connectivity.json"
        for part in json.loads(src.read_text(encoding="utf-8"))["parts"]:
            if not part["ref"].startswith("C") or "DNP" in part["value"].upper():continue
            match=re.match(r"([0-9.]+)\s*([pnuµm]?)",part["value"])
            if not match:raise ValueError(f"Unparsed capacitor {pkg}/{part['ref']}")
            c=float(match[1])*{"p":1e-12,"n":1e-9,"u":1e-6,"µ":1e-6,"m":1e-3,"":1}[match[2]]
            nets=list(part["nets"].values())
            direct=len(nets)==2 and all(n in pots for n in nets)
            dv=abs(pots[nets[0]]-pots[nets[1]]) if direct else maxspan[pkg]
            caprows.append({"package":pkg,"reference":part["ref"],"value":part["value"],
                            "capacitance_F":c,"voltage_bound_V":dv,"voltage_bound_is_direct_rail":direct,
                            "nominal_stored_energy_bound_J":.5*c*dv*dv})
    energy=sum(r["nominal_stored_energy_bound_J"]for r in caprows)
    upper=1.2*energy
    ramp=[{"assumed_charge_time_s":t,"capacitor_energy_bound_J":upper,
           "input_energy_J_at0p5effective_efficiency":upper/.5,
           "additional_average_input_current_A_at5p9V":upper/.5/t/5.9,
           "additional_average_alone_below2A_rating":upper/.5/t/5.9<2}
          for t in (.001,.005,.030,.100)]
    return {"source_sha256_lf":sha(p),"rail_qualification":rows,
            "power_native_source_sha256_lf":sha(native_path),
            "native_power_components":len(native["parts"]),
            "native_power_IC_values":dict(sorted(Counter(p["value"]for p in native["parts"]if p["ref"].startswith("U")).items())),
            "all_six_package_capacitors":caprows,"nominal_capacitor_energy_bound_J":energy,
            "plus20percent_capacitance_energy_bound_J":upper,
            "charge_energy_sensitivity":ramp,
            "meaning":"Illustrative charge-energy slopes, not peaks or implemented sequencing; all host and AFE rails may start together. TMR30ms start is typical only. Fuse2A is a rating, not an instantaneous current clamp.",
            "rearm_after_stable_rails_still_required":True,
            "full_tolerance_AFE_cold_start_guaranteed":False,
            "selected_trim_is_defensible_condition_not_factory_guarantee":True}


def build() -> dict:
    inv=inventory()
    cases=[power_case(inv,m) for m in ("supervision-only","recording-observe","restricted-active")]
    active=cases[-1]
    sensitivity=[]
    for eb in (.65,.80,.90):
        for ei in (.45,.65,.80):
            x=power_case(inv,"restricted-active",eb,.75,ei)
            sensitivity.append({"buck_efficiency_assumed":eb,"iso_efficiency_assumed":ei,
                                "battery_W":x["battery_nominal_W"],"runtime_h":x["runtime_h_at80percent_nominal_energy"]})
    heat=[]
    for r in (5,10,20,50):
        rise=active["device_heat_upper_allocation_W"]*r
        heat.append({"assumed_system_thermal_resistance_K_per_W":r,"steady_rise_K":rise,
                     "selected2Krise_allocation_pass":rise<=2,
                     "meaning":"lumped sensitivity only; no measuredcaseorbiologicalthermalpath"})
    # Source resistance is a selected sensitivity, not a measured cell model.
    brownout=[]
    peak_bus_W=active["pre_diode_bus_load_W"]+(.006-.00024)*24/.75
    for voc in (6.4,6.8,7.4,8.4):
        for r in (.1,.5,1,2,5):
            b=voc-.5;discriminant=b*b-4*r*peak_bus_W
            bus=(b+math.sqrt(discriminant))/2 if discriminant>=0 else None
            a=peak_bus_W/bus if bus else None
            brownout.append({"pack_open_circuit_V":voc,"assumed_source_R_ohm":r,
                             "peak_bus_power_W":peak_bus_W,"load_line_discriminant_V2":discriminant,
                             "bus_V":bus,"input_A":a,"source_resistance_loss_W":a*a*r if a else None,
                             "admitted_underload_bus_atleast5p9V":bus is not None and bus>=5.9,
                             "interpretation":"Underload6.4Vpackminimum,0.5Vdiodecondition; protectiontripcurveandcellimpedancenotmeasured"})
    return {"schema":"scci_rh.stage4.power-budget.v1","date":"2026-10-14",
            "scope":"digitalreference; DCandenergyequations with explicitconditionalcomponent/load/efficiency assumptions",
            "producer_sha256_lf":sha(Path(__file__)),"sources":SOURCE,"inventory":inv,
            "battery":{"part":"TenergyAT31004protected2S1P","nominal_V":7.4,"capacity_Ah":2.6,
                       "nominal_Wh":19.24,"continuous_rating_A":5,"design_operating_range_V":[6.4,8.4],
                       "usable_energy_fraction_assumed":.8,"usable_Wh":15.392,
                       "size_mm":[67,37,21],"mass_g":99,"seriesdiode_drop_V_assumed":.5,
                       "master_fuse_A":2,"onboard_charger":False,
                       "interpretation":"externaldigitalbenchreferencepack; notminiatureimplantbattery/sterilepackorwirelesspowerimplementation"},
            "assumptions":{"buck_load_efficiency":.8,"boost_load_efficiency":.75,"isolated_load_efficiency":.65,
                           "efficiencies_verified":False,"LDO_loaded_ground_current_allocation_A_each":.001,"isolated_no_load_overhead_W":.3,
                           "fullratedmoduleefficiency_not_used_as_lowloadguarantee":True,
                           "input_drop_and_efficiency_are_conditions_to_verify":True,
                           "pulse_current_A_each":.003,"sources":2,"phase_duration_s":.0002,
                           "phases_per_biphasic_pulse":2,"frequency_Hz":100,
                           "full48V20mAconcept_is_implemented":False},
            "operating_cases":cases,"efficiency_sensitivity":sensitivity,"reservoir":reservoir(),
            "aligned_peak_pre_diode_bus_power_W":peak_bus_W,"brownout_sensitivity":brownout,
            "thermal_sensitivity":heat,"required_lumped_Rth_for2Krise_K_per_W":2/active["device_heat_upper_allocation_W"],
            "resources":resources(),"startup":startup(),
            "rejected_or_unearned":["historical3.0to4.1V1Scellcontractincompatiblewithnew5Vbucktopology",
              "historical100mAaveragecellcapnotmetbynewnativecomponentloadceilings",
              "450kmonitorconversionspersecondexceeds2ADS8866capacity200k",
              "continuousraw4kframed1.536Mbit/sdoesnotfit1Mbit/sservice",
              "2Kcase/tissueheatcriterionnotproved; declaredlumpedRthsweeprejectsallselectedvalues",
              "AFEfullLDOtolerancecanfailrailqualification; selectedtrimconditionalstartupseparatelychecked",
              "converterstability,ripple,EMI,brownoutdynamics,chronicimplantthermalandisolationqualificationunearned"]}


def compare(a, b, at="root"):
    if isinstance(a,dict):
        assert isinstance(b,dict) and a.keys()==b.keys(), f"keys {at}"
        for k in a: compare(a[k],b[k],f"{at}.{k}")
    elif isinstance(a,list):
        assert isinstance(b,list) and len(a)==len(b),f"length {at}"
        for n,(x,y) in enumerate(zip(a,b)):compare(x,y,f"{at}[{n}]")
    elif isinstance(a,float): assert math.isclose(a,b,rel_tol=2e-10,abs_tol=1e-18), f"value {at}: {a} != {b}"
    else: assert a==b,f"value {at}"


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-results",action="store_true")
    args=parser.parse_args(); result=build(); out=HERE/"budget-results.json"
    if args.write_results:
        out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
    else: compare(result,json.loads(out.read_text(encoding="utf-8")))
    print(json.dumps({"status":"written"if args.write_results else"read-onlyreplaypassed",
                      "active_packages":sum(x["active_packages"]for x in result["inventory"]["packages"].values()),
                      "rail_count":len(V),"battery_W_active":result["operating_cases"][-1]["battery_nominal_W"],
                      "runtime_h_conditional":result["operating_cases"][-1]["runtime_h_at80percent_nominal_energy"]},indent=2))
