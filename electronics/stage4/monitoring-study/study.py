"""Scoped behavioral transient investigation of SCCI_RH-S4-MON-01.

Writes only this monitoring-study package with --run. Default --check reads the
frozen study and independently checks KCL, endpoint arithmetic and provenance.
It does not import Stage 3 models or modify the native monitoring-cell sources.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.linalg import expm
from ngspice_shared import SharedNgspice, find_library

HERE = Path(__file__).resolve().parent
CELL = HERE.parent / "monitoring-cell"
MID, VREF, K0 = 2.048, 4.096, 5.5e-6
LSB = VREF / 65536
GRIDS = (5e-7, 1e-7, 2.5e-8)
EDGE, RESET_OPEN = 1e-9, 100e-6
STOP = 1.8e-3

@dataclass(frozen=True)
class Case:
    name: str
    phase1_A: float = 3e-3
    phase2_A: float = 3e-3
    duration_s: float = 200e-6
    bias_load_A: float = 0.0
    bias_driver_A: float = 0.0
    reset_open_charge_C: float = 0.0
    differential_charge_C: float = 0.0
    drive_tau_s: float = 100e-9
    sensor_bw_Hz: float = 1.1e6
    opamp_gbw_Hz: float = 1e6
    buffer_ugb_Hz: float = 450e3
    shunt_ohm: float = 2.0
    sense_gain: float = 20.0
    int_R_ohm: float = 10000.0
    int_C_F: float = 22e-9
    sensor_offset_V: float = 0.0
    opamp_offset_V: float = 0.0
    int_leak_ohm: float = 1e12
    adc_gain_error: float = 0.0
    forced_guard_bypass: bool = False

CASES = [
    Case("nominal"),
    Case("load_side_bias_45uA", bias_load_A=45e-6),
    Case("driver_side_bias_45uA", bias_driver_A=45e-6),
    Case("both_input_bias_45uA", bias_load_A=45e-6, bias_driver_A=45e-6),
    Case("reset_open_6pC", reset_open_charge_C=6e-12),
    Case("differential_injection_6pC", differential_charge_C=6e-12),
    Case("slow_response", drive_tau_s=20e-6, sensor_bw_Hz=1e5, opamp_gbw_Hz=1e5, buffer_ugb_Hz=5e4),
    Case("scale_offset_corner", shunt_ohm=2.002, sense_gain=20.002,
         int_R_ohm=9990, int_C_F=21.89e-9, sensor_offset_V=15e-6,
         opamp_offset_V=45e-6, adc_gain_error=1e-4),
    Case("unequal_cancellation", phase1_A=6e-3, phase2_A=5.985e-3),
    Case("clipping_guard_bypassed", phase1_A=40e-3, phase2_A=40e-3,
         duration_s=500e-6, forced_guard_bypass=True),
    Case("reset_and_leakage_stress", reset_open_charge_C=6e-12, int_leak_ohm=1e7),
]

def pwl_value(points, t):
    return float(np.interp(t, [p[0] for p in points], [p[1] for p in points]))

def command_points(case, source):
    # Source 0 begins negative; source 1 begins positive and is staggered 25us.
    sign = -1 if source == 0 else 1
    a = 200e-6 + source * 25e-6
    b = a + case.duration_s
    c = b + 100e-6
    d = c + case.duration_s
    return [(0.,0.), (a,0.), (a+EDGE,sign*case.phase1_A),
            (b,sign*case.phase1_A), (b+EDGE,0.), (c,0.),
            (c+EDGE,-sign*case.phase2_A), (d,-sign*case.phase2_A), (d+EDGE,0.), (STOP,0.)]

def injection_points(case, source):
    events=[]
    for start, charge in ((RESET_OPEN+1e-6,case.reset_open_charge_C),
                          (350e-6+source*25e-6,case.differential_charge_C)):
        if charge:
            amplitude=charge/(201e-9)
            events.extend([(start,0.), (start+EDGE,amplitude),
                           (start+201e-9,amplitude), (start+202e-9,0.)])
    return [(0.,0.)]+events+[(STOP,0.)]

def pwl(points):
    return "PWL("+" ".join(f"{t:.15g} {v:.15g}" for t,v in points)+")"

def make_netlist(case, grid):
    lines=[f"SCCI_RH Stage4 behavioral monitor: {case.name}; NOT vendor model",
           "* Two independent sources; no driver-loop, electrode chemistry or biological model",
           "* Positive Iload enters load-return; positive Ishunt flows load to driver",
           ".model Reset SW(Ron=2 Roff=1e12 Vt=0.5 Vh=0)",
           f"Vreset reset 0 {pwl([(0.,1.),(RESET_OPEN,1.),(RESET_OPEN+EDGE,0.),(STOP,0.)])}"]
    saved=[]
    for source in (0,1):
        s=str(source)
        ta=1e6/(2*math.pi*case.opamp_gbw_Hz)
        ts=1/(2*math.pi*case.sensor_bw_Hz)
        tb=1/(2*math.pi*case.buffer_ugb_Hz)
        lines += [
            f"Vcmd{s} cmd{s} 0 {pwl(command_points(case,source))}",
            f"Rdrive{s} cmd{s} drive{s} 1",
            f"Cdrive{s} drive{s} 0 {case.drive_tau_s:.15g} IC=0",
            f"Bload{s} 0 load{s} I={{v(drive{s})}}",
            f"Vreturn{s} ret{s} 0 48",
            f"Rshunt{s} load{s} ret{s} {case.shunt_ohm:.15g}",
            f"Ibload{s} load{s} 0 {case.bias_load_A:.15g}",
            f"Ibdriver{s} ret{s} 0 {case.bias_driver_A:.15g}",
            f"Btarget{s} target{s} 0 V={{{case.sense_gain:.15g}*(v(load{s})-v(ret{s})+{case.sensor_offset_V:.15g})}}",
            f"Rsensor{s} target{s} sensor{s} 1",
            f"Csensor{s} sensor{s} 0 {ts:.15g} IC=0",
            f"Bmon{s} mon{s} 0 V={{max(0.02,min(4.8,{MID}+v(sensor{s})))}}",
            f"Rint{s} mon{s} sum{s} {case.int_R_ohm:.15g}",
            f"Cint{s} sum{s} out{s} {case.int_C_F:.15g} IC=0",
            f"Rleak{s} sum{s} out{s} {case.int_leak_ohm:.15g}",
            f"Sreset{s} sum{s} out{s} reset 0 Reset",
            f"Iinject{s} 0 sum{s} {pwl(injection_points(case,source))}",
            # Algebraically rescaled one-pole amplifier: C=1/(2pi GBW),
            # R=A0 and gm=1 give tau=A0/(2pi GBW), DC gain=A0. This
            # avoids a 1e6-gain behavioral voltage source/1ohm cancellation.
            f"Vopref{s} opref{s} 0 {MID+case.opamp_offset_V:.15g}",
            f"Gamp{s} 0 state{s} opref{s} sum{s} 1",
            f"Ramp{s} state{s} 0 1e6",
            f"Camp{s} state{s} 0 {ta/1e6:.15g} IC=0",
            f"Bout{s} out{s} 0 V={{max(0.05,min(4.95,{MID}+v(state{s})))}}",
            f"Rbuffer{s} out{s} buffer{s} 1",
            f"Cbuffer{s} buffer{s} 0 {tb:.15g} IC={MID}",
            f"Rfilter{s} buffer{s} adc{s} 33",
            f"Cfilter{s} adc{s} 0 1n IC={MID}",
        ]
        saved += [f"v({name}{s})" for name in ("drive","load","ret","sensor","mon","sum","state","out","buffer","adc")]
        saved += [f"i(vreturn{s})"]
    lines += [".options reltol=1e-9 abstol=1e-14 vntol=1e-11 method=gear",
              ".save "+" ".join(saved), f".tran {grid:.15g} {STOP:.15g} 0 {grid:.15g} UIC", ".end"]
    return lines,saved

def matrix(case, reset_closed):
    # Independent KCL state: [Iload, sensor_delta, Vcap=sum-out,
    # integrator_internal_delta, buffer_delta, ADC_delta, cumulative_load_charge].
    M=np.zeros((7,7)); f=np.zeros(7)
    td=case.drive_tau_s; ts=1/(2*math.pi*case.sensor_bw_Hz)
    ta=1e6/(2*math.pi*case.opamp_gbw_Hz)
    tb=1/(2*math.pi*case.buffer_ugb_Hz)
    G=(1/2 if reset_closed else 1/1e12)+1/case.int_leak_ohm
    rc=case.int_R_ohm*case.int_C_F
    M[0,0]=-1/td
    M[1,0]=case.sense_gain*case.shunt_ohm/ts; M[1,1]=-1/ts
    f[1]=case.sense_gain*(case.sensor_offset_V-case.shunt_ohm*case.bias_load_A)/ts
    M[2,1]=1/rc; M[2,2]=-1/rc-G/case.int_C_F; M[2,3]=-1/rc
    M[3,2]=-1e6/ta; M[3,3]=-(1e6+1)/ta
    f[3]=1e6*case.opamp_offset_V/ta
    # Passive 1-ohm buffer pole is loaded by the downstream 33-ohm/1nF
    # filter. Keep the loading term; treating the poles as isolated cascades
    # creates a systematic 1ns discrepancy against the actual netlist.
    M[4,3]=1/tb; M[4,4]=-1/tb-1/(33*tb); M[4,5]=1/(33*tb)
    M[5,4]=1/33e-9; M[5,5]=-1/33e-9
    M[6,0]=1
    return M,f

def analytical_states(case, source, queries):
    """Exact matrix exponential of piecewise-linear forcing, without ngspice.

    Valid only while the modeled sensor/integrator stay in their linear ranges.
    Hard clipping is intentionally absent; it is checked/rejected separately.
    """
    cmd=command_points(case,source); inj=injection_points(case,source)
    boundaries=sorted({0.,STOP,RESET_OPEN+EDGE/2,*[p[0] for p in cmd],*[p[0] for p in inj]})
    q=np.asarray(sorted(set(float(x) for x in queries)))
    result={}; state=np.zeros(7); cache={}
    for start,end in zip(boundaries,boundaries[1:]):
        closed=(start+end)/2 < RESET_OPEN+EDGE/2
        M,f=matrix(case,closed)
        u0=np.array([pwl_value(cmd,start),pwl_value(inj,start)])
        u1=np.array([pwl_value(cmd,end),pwl_value(inj,end)])
        B=np.zeros((7,2)); B[0,0]=1/case.drive_tau_s; B[2,1]=1/case.int_C_F
        A=np.zeros((9,9)); A[:7,:7]=M; A[:7,7]=f+B@u0; A[:7,8]=B@((u1-u0)/(end-start)); A[8,7]=1
        initial=np.r_[state,1.,0.]
        def evolve(dt):
            # Exact repeats are cached; no numerical integration step is chosen.
            key=(closed,tuple(u0),tuple((u1-u0)/(end-start)),round(dt,16))
            if key not in cache: cache[key]=expm(A*dt)
            return (cache[key]@initial)[:7]
        for t in q[(q>=start)&(q<=end)]: result[float(t)]=evolve(float(t-start))
        state=evolve(end-start)
    return np.asarray([result[float(t)] for t in queries])

def window_integral(time, values, start, end):
    inside=(time>start)&(time<end)
    t=np.r_[start,time[inside],end]
    v=np.r_[np.interp(start,time,values),values[inside],np.interp(end,time,values)]
    return float(np.trapezoid(v,t))

def endpoints(case,source):
    a=200e-6+source*25e-6; b=a+case.duration_s; c=b+100e-6; d=c+case.duration_s
    return {"pre_reset":80e-6,"baseline":a-20e-6,"phase1_start":a,
            "phase1_edge":b,"phase1_tail":b+25e-6,"phase2_start":c,
            "phase2_edge":d,"phase2_tail":d+25e-6,"late_tail":d+300e-6}

def analyze(case,grid,data):
    time=data["time"]; channels=[]
    for source in (0,1):
        s=str(source); iL=data[f"v(drive{s})"]
        iS=(data[f"v(load{s})"]-data[f"v(ret{s})"])/case.shunt_ohm
        iD=data[f"i(vreturn{s})"]
        out=data[f"v(out{s})"]; adc=data[f"v(adc{s})"]; mon=data[f"v(mon{s})"]
        ep=endpoints(case,source)
        samples={}
        for name, requested in ep.items():
            actual=requested+4e-9  # typical aperture delay, not a guaranteed bound
            raw=float(np.interp(actual,time,adc))
            code=int(np.clip(np.floor(raw*(1+case.adc_gain_error)/LSB+0.5),0,65535))
            samples[name]={"CNV_s":requested,"aperture_s":actual,"latest_conversion_complete_s":requested+8.8e-6,
                           "assumed_read_available_s":requested+9.8e-6,"raw_input_V":raw,"code":code,"code_voltage_V":code*LSB}
        intervals=[]
        for label,first,last in [("command_phase1","phase1_start","phase1_edge"),
                                 ("command_gap","phase1_edge","phase2_start"),
                                 ("command_phase2","phase2_start","phase2_edge"),
                                 ("observed_first","baseline","phase1_tail"),
                                 ("observed_second_includes_gap","phase1_tail","phase2_tail"),
                                 ("settled_net","baseline","late_tail"),
                                 ("wrong_pre_reset_baseline","pre_reset","phase1_tail")]:
            start=samples[first]["aperture_s"]; end=samples[last]["aperture_s"]
            rawQ=-K0*(samples[last]["raw_input_V"]-samples[first]["raw_input_V"])
            codeQ=-K0*(samples[last]["code_voltage_V"]-samples[first]["code_voltage_V"])
            loadQ=window_integral(time,iL,start,end); shuntQ=window_integral(time,iS,start,end)
            intervals.append({"name":label,"first":first,"last":last,"start_s":start,"end_s":end,
                              "load_charge_C":loadQ,"shunt_charge_C":shuntQ,
                              "raw_endpoint_charge_C":rawQ,"quantized_endpoint_charge_C":codeQ,
                              "raw_error_vs_load_C":rawQ-loadQ,"raw_error_vs_shunt_C":rawQ-shuntQ,
                              "KCL_expected_load_minus_shunt_C":case.bias_load_A*(end-start)})
        selected=np.unique(np.r_[np.linspace(10e-6,STOP,181), list(ep.values()),
                                  [RESET_OPEN+v for v in (0.,.05e-6,.5e-6,1e-6,1.1e-6,1.202e-6,2e-6,5e-6)]])
        oracle=analytical_states(case,source,selected)
        expected_out=MID+oracle[:,3]; expected_adc=MID+oracle[:,5]
        expected_sensor=MID+oracle[:,1]
        clipped=(expected_out<=.05)|(expected_out>=4.95)|(expected_sensor<=.02)|(expected_sensor>=4.8)
        if clipped.any(): valid=selected<selected[np.flatnonzero(clipped)[0]]
        else: valid=np.ones(len(selected),dtype=bool)
        # Compare before the first nonlinear saturation; no false linear oracle afterwards.
        error_out=np.abs(np.interp(selected,time,out)-expected_out)
        error_adc=np.abs(np.interp(selected,time,adc)-expected_adc)
        rail_clip=bool(np.any((out<=.050001)|(out>=4.949999)))
        adc_clip=bool(np.any((adc<0)|(adc>VREF)))
        sense_clip=bool(np.any((mon<=.020001)|(mon>=4.799999)))
        peak_trip=bool(np.any(np.abs((mon-MID)/40)>25.0107e-3))
        intervals_by_name={x["name"]:x for x in intervals}
        qnet=intervals_by_name["settled_net"]["raw_endpoint_charge_C"]
        q1=intervals_by_name["observed_first"]["raw_endpoint_charge_C"]
        q2=intervals_by_name["observed_second_includes_gap"]["raw_endpoint_charge_C"]
        timing_sweep={}
        for shift in (-1e-6,-1e-7,0.,1e-7,1e-6):
            a=ep["phase1_start"]+4e-9+shift; b=ep["phase1_edge"]+4e-9-shift
            timing_sweep[str(shift)]=-K0*float(np.interp(b,time,adc)-np.interp(a,time,adc))
        channels.append({"source":source,"first_phase_sign":-1 if source==0 else 1,"samples":samples,"intervals":intervals,
                         "peak_load_current_A":float(np.max(np.abs(iL))),
                         "KCL_max_load_residual_A":float(np.max(np.abs(iL-iS-case.bias_load_A))),
                         "KCL_max_driver_residual_A":float(np.max(np.abs(iS-iD-case.bias_driver_A))),
                         "linear_oracle_comparison_samples":int(valid.sum()),
                         "linear_oracle_max_out_error_V":float(error_out[valid].max()),
                         "linear_oracle_max_ADC_error_V":float(error_adc[valid].max()),
                         "integrator_saturated":rail_clip,"ADC_outside_measurement_range":adc_clip,
                         "sense_saturated":sense_clip,"current_guard_threshold_crossed":peak_trip,
                         "range_or_bypassed_guard_fault_rejected":bool(rail_clip or adc_clip or sense_clip or case.forced_guard_bypass),
                         "net_only_within_24nC":abs(qnet)<=24e-9,
                         "individual_600nC_targets_missed_by_over24nC":abs(abs(q1)-600e-9)>24e-9 or abs(abs(q2)-600e-9)>24e-9,
                         "command_phase1_clock_strip_sweep_C":timing_sweep,
                         "oracle_queries_s":selected.tolist(),"oracle_expected_ADC_V":expected_adc.tolist(),
                         "oracle_linear_valid":valid.tolist()})
    return {"case":case.name,"max_step_s":grid,"samples":len(time),"channels":channels}

def witnesses():
    tau=100e-6; A=3e-3; T=200e-6; gap=100e-6
    def F(t): return 0. if t<0 else t-tau*(-math.expm1(-t/tau))
    finite={str(t):A*(F(t)-F(t-T)-F(t-T-gap)+F(t-2*T-gap)) for t in (T,T+gap,2*T+gap,1e-3)}
    scale=(20.002/20)*(2.002/2)*(10000/9990)*(22e-9/21.89e-9)
    return {"signed_600nC_delta_V":{ "positive":-600e-9/K0,"negative":600e-9/K0},
            "load_side_45uA_200us_mismatch_C":45e-6*200e-6,
            "driver_side_bias_direct_load_shunt_mismatch_C":0.,
            "both_bias_load_driver_200us_mismatch_C":90e-6*200e-6,
            "reset_6pC_unobserved_differential_equivalent_C":250*6e-12,
            "fixed_prebaseline_reset_jump_ideal_contribution_C":0.,
            "ADC_two_endpoint_INL_plus_rounding_bound_C":K0*LSB*5,
            "ADC_bound_exceeds_proposed_1p5nC_allocation":K0*LSB*5>1.5e-9,
            "typical_aperture_delay_s":4e-9,"assumed_1us_two_endpoint_local_3mA_bound_C":2*3e-3*1e-6,
            "component_scale_corner_exact_product":scale,"scale_only_600nC_error_C":600e-9*(scale-1),
            "first_order_100us_math_stress_C":finite,
            "unequal_opposed_phases_C":[1200e-9,-1197e-9],"unequal_net_C":3e-9,
            "same_600nC_with_interior_reversal_absolute_charge_C":1200e-9,
            "scope":"Analytical topology/arithmetic witnesses, not device guarantees or achieved accuracy"}

def normalized_hash(p):
    data=p.read_bytes()
    if p.suffix.lower() not in {".npz",".png",".pdf"}:
        data=data.replace(b"\r\n",b"\n").replace(b"\r",b"\n")
    return hashlib.sha256(data).hexdigest()

def run(library):
    sim=SharedNgspice(library)
    (HERE/"netlists").mkdir(exist_ok=True);(HERE/"traces").mkdir(exist_ok=True)
    runs=[]; logs=[]
    for case in CASES:
        for grid in GRIDS:
            tag=f"{case.name}__{int(round(grid*1e9))}ns"
            lines,vectors=make_netlist(case,grid)
            (HERE/"netlists"/(tag+".cir")).write_text("\n".join(lines)+"\n",encoding="utf-8")
            data,messages=sim.run(lines,vectors)
            record=analyze(case,grid,data)
            raw={"time_s":data["time"]}
            for source in (0,1):
                s=str(source)
                for old,new in [("drive","Iload_A"),("sensor","sensor_delta_V"),("mon","Imon_V"),("sum","sum_V"),("state","internal_delta_V"),("out","integrator_V"),("buffer","buffer_V"),("adc","ADC_input_V")]:
                    raw[f"source{source}_{new}"]=data[f"v({old}{s})"]
                raw[f"source{source}_Ishunt_A"]=(data[f"v(load{s})"]-data[f"v(ret{s})"])/case.shunt_ohm
                raw[f"source{source}_Idriver_A"]=data[f"i(vreturn{s})"]
            file=HERE/"traces"/(tag+".npz");np.savez_compressed(file,**raw)
            record["trace_file"]=file.relative_to(HERE).as_posix()
            record["netlist_file"]="netlists/"+tag+".cir"
            record["trace_sha256"]=normalized_hash(file)
            record["netlist_normalized_sha256"]=normalized_hash(HERE/record["netlist_file"])
            runs.append(record); logs.append({"run":tag,"messages":messages})
            print(json.dumps({"run":tag,"samples":len(data["time"]),"max_oracle_error_V":max(c["linear_oracle_max_ADC_error_V"] for c in record["channels"])}),flush=True)
    convergence=[]
    for case in CASES:
        records=[r for r in runs if r["case"]==case.name]
        for coarse,fine in zip(records,records[1:]):
            delta=max(abs(a["raw_endpoint_charge_C"]-b["raw_endpoint_charge_C"])
                      for ca,cb in zip(coarse["channels"],fine["channels"])
                      for a,b in zip(ca["intervals"],cb["intervals"]))
            convergence.append({"case":case.name,"coarse_step_s":coarse["max_step_s"],"fine_step_s":fine["max_step_s"],"max_interval_charge_delta_C":delta})
    results={"schema":"scci_rh.stage4.monitoring-study.v1","date":"2026-10-12",
             "engine":"ngspice shared library","library":library,"engine_messages":sim.version_messages,
             "status":"behavioral_study_completed_not_analog_qualification","cases":[asdict(c) for c in CASES],
             "grids_s":list(GRIDS),"runs":runs,"refinement":convergence,"analytical_witnesses":witnesses(),
             "four_percent_target_earned":False,"native_cell_modified":False,
             "numerical_comparison_criteria":{"KCL_A":1e-10,"linear_oracle_V":2e-5,"fine_grid_interval_delta_C":1e-10},
             "provenance":{"study_source_normalized_sha256":{name:normalized_hash(HERE/name) for name in ("study.py","ngspice_shared.py")},
                           "native_manifest_normalized_sha256":normalized_hash(CELL/"connectivity.json"),
                           "native_root_schematic_normalized_sha256":normalized_hash(CELL/"monitoring_cell.kicad_sch")},
             "unmodeled":["manufacturer macromodel/internal poles and PWM commonmode disturbance","OPA slew/overload recovery/phase margin","SAR kickback and reference dynamic impedance/noise","clock distribution/protocol implementation","actual current-source servo/HV router/protection","input bias voltage-temperature-power-state topology","nonlinear electrode/chemistry/anatomy/biological recruitment","independent fault shutdown actuation"]}
    (HERE/"results.json").write_text(json.dumps(results,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (HERE/"ngspice-log.json").write_text(json.dumps(logs,indent=2)+"\n",encoding="utf-8")
    with (HERE/"interval-results.csv").open("w",encoding="utf-8",newline="") as f:
        fields=["case","grid_s","source",*runs[0]["channels"][0]["intervals"][0].keys()]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in runs:
            for ch in r["channels"]:
                for interval in ch["intervals"]:w.writerow({"case":r["case"],"grid_s":r["max_step_s"],"source":ch["source"],**interval})
    return results

def check():
    result=json.loads((HERE/"results.json").read_text(encoding="utf-8"))
    assert result["four_percent_target_earned"] is False
    assert result["native_cell_modified"] is False
    for name,expected in result["provenance"]["study_source_normalized_sha256"].items():
        assert normalized_hash(HERE/name)==expected, "Study source changed: "+name
    assert normalized_hash(CELL/"connectivity.json")==result["provenance"]["native_manifest_normalized_sha256"]
    assert normalized_hash(CELL/"monitoring_cell.kicad_sch")==result["provenance"]["native_root_schematic_normalized_sha256"]
    cases={c["name"]:Case(**c) for c in result["cases"]}
    criteria=result["numerical_comparison_criteria"]
    for r in result["runs"]:
        case=cases[r["case"]]
        assert normalized_hash(HERE/r["trace_file"])==r["trace_sha256"]
        assert normalized_hash(HERE/r["netlist_file"])==r["netlist_normalized_sha256"]
        with np.load(HERE/r["trace_file"]) as trace:
            t=trace["time_s"]
            assert np.all(np.diff(t)>0) and len(t)==r["samples"]
            for ch in r["channels"]:
                source=ch["source"]; p=f"source{source}_"
                assert np.max(np.abs(trace[p+"Iload_A"]-trace[p+"Ishunt_A"]-case.bias_load_A))<criteria["KCL_A"]
                assert np.max(np.abs(trace[p+"Ishunt_A"]-trace[p+"Idriver_A"]-case.bias_driver_A))<criteria["KCL_A"]
                if r["max_step_s"]==min(result["grids_s"]):
                    assert ch["linear_oracle_max_ADC_error_V"]<criteria["linear_oracle_V"], (r["case"],ch["source"],ch["linear_oracle_max_ADC_error_V"])
                for interval in ch["intervals"]:
                    QL=window_integral(t,trace[p+"Iload_A"],interval["start_s"],interval["end_s"])
                    QS=window_integral(t,trace[p+"Ishunt_A"],interval["start_s"],interval["end_s"])
                    assert math.isclose(QL,interval["load_charge_C"],abs_tol=1e-16)
                    assert math.isclose(QS,interval["shunt_charge_C"],abs_tol=1e-16)
                    assert abs(QL-QS-case.bias_load_A*(interval["end_s"]-interval["start_s"]))<1e-14
    for r in result["refinement"]:
        if r["fine_step_s"]==min(result["grids_s"]):
            assert r["max_interval_charge_delta_C"]<criteria["fine_grid_interval_delta_C"],r
    cancellation=[r for r in result["runs"] if r["case"]=="unequal_cancellation"]
    assert all(c["net_only_within_24nC"] and c["individual_600nC_targets_missed_by_over24nC"] for r in cancellation for c in r["channels"])
    faults=[r for r in result["runs"] if r["case"]=="clipping_guard_bypassed"]
    assert all(c["range_or_bypassed_guard_fault_rejected"] for r in faults for c in r["channels"])
    assert any(c["ADC_outside_measurement_range"] for r in faults for c in r["channels"])
    print(json.dumps({"read_only_check":"passed","runs":len(result["runs"]),"sources_per_run":2,"four_percent_target_earned":False}))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",action="store_true",help="Run live installed ngspice and rewrite only this study package")
    parser.add_argument("--check",action="store_true",help="Read-only validation of frozen study; default action")
    parser.add_argument("--library",help="Installed shared library; otherwise NGSPICE_LIBRARY/known local path/search")
    args=parser.parse_args()
    if args.run:
        library=find_library(args.library)
        if not library:raise RuntimeError("ngspice shared library unavailable; no study was run")
        run(library)
    check()

if __name__=="__main__":main()
