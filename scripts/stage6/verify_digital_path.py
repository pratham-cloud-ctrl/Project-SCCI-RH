"""Replay both conditional SCCI_RH policies through the unchanged production C core.

Default is read-only and compares saved results. --write-results regenerates only
Stage 6 outputs. Requires numpy and a C11 compiler (CC, GCC, Clang or local Zig).
This is host software integration plus declared response/supervisor models,
not an execution of the target peripherals, circuit, implant or human biology.
"""
from __future__ import annotations

import argparse
from collections import deque
import csv
import ctypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/stage6"
ASSERTIONS = 0


def check(condition, message):
    global ASSERTIONS
    ASSERTIONS += 1
    if not condition:
        raise AssertionError(message)


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def stable(value):
    """Numerical replay tolerance is explicit: 10 decimal digits in saved floats."""
    if isinstance(value, float):
        return round(value, 10)
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def conditional_feature_usable(values, support_us, arrival_us, now_us, valid=True):
    """New companion adapter rule, not the target's analog qualification flag."""
    return bool(valid and support_us <= arrival_us <= now_us
                and 0 <= now_us-support_us <= 50000
                and np.isfinite(np.asarray(values, dtype=float)).all())


def pressure_command(observation):
    return min(1., max(0., (120.-observation)/30.))


class Runtime:
    def __init__(self, dll):
        self.dll = ctypes.CDLL(str(dll))
        self.dll.scci_rh_replay_call.argtypes = [ctypes.c_uint] + [ctypes.c_uint64] * 5
        self.dll.scci_rh_replay_call.restype = ctypes.c_uint64
        self.dll.scci_rh_replay_get.argtypes = [ctypes.c_uint]
        self.dll.scci_rh_replay_get.restype = ctypes.c_uint64
        self.dll.scci_rh_replay_packet.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint,
                                              ctypes.c_uint64]
        self.dll.scci_rh_replay_packet.restype = ctypes.c_uint64

    def call(self, op, t, a=0, b=0, c=0, d=0):
        return int(self.dll.scci_rh_replay_call(op, t, a, b, c, d))

    def get(self, key):
        return int(self.dll.scci_rh_replay_get(key))

    def packet(self, data, now):
        wire = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        return bool(self.dll.scci_rh_replay_packet(wire, len(data), now))

    def start(self, mode, now, transport, pressure=100.0):
        self.call(0, now)
        self.call(1, now, 127 & ~16, 3)
        check(self.call(2, now, 1, 1), "configure with observed readback")
        check(self.call(3, now, now, 1, 0, 1), "known raw conversion identity")
        if mode == 2:
            check(self.call(4, now), "bounded clock/session")
            check(self.packet(transport.pack_packet(seq=1, support=(now-100000, now-50000),
                         extraction=now-10000, pressure=pressure), now), "fresh SBP at startup")
        check(self.call(5, now, mode, 1, 3000000 if mode == 2 else 250000), "mode lease")
        check(self.call(16, now), "pre-monitor recovery is separate")
        check(self.call(7, now) == 64, "monitor rearm action only")
        self.call(1, now, 127, 3)
        check(self.call(6, now), "explicit final rearm")
        check(self.call(7, now) == 48, "fault reset and independent supervisor rearm")

    def route(self, now, contacts=(2, 9), observed=None):
        check(self.call(8, now, *contacts), "route proposal")
        check(self.call(7, now) == 1, "route commit consumed")
        result = self.call(9, now, *(observed or contacts))
        if result:
            check(self.call(7, now) == 6, "active route comparison before ack/rearm")
        return bool(result)

    def plan(self, now, currents, contacts, event_id, off=False):
        mask = sum(1 << i for i, current in enumerate(currents) if current)
        return bool(self.call(10, now, *currents, contacts[0] | contacts[1] << 8,
                              mask | (int(off) << 2) | event_id << 8))

    def event(self, now, currents, contacts, event_id, off=False):
        check(self.route(now, contacts), "route readback accepted")
        check(self.plan(now, currents, contacts, event_id, off), "bounded event admitted")
        if off:
            check(self.get(1) == 0 and self.get(4) == 0, "OFF event emits no request")
            return 0
        mask = sum(1 << i for i, current in enumerate(currents) if current)
        check(self.call(7, now) == 8, "first phase independent rearm requested")
        check(self.call(11, now), "observed first phase ready")
        check(self.call(12, now), "first phase start")
        check(self.get(1) == mask and self.get(2) == mask, "first phase identities")
        self.call(13, now + 200)
        check(self.get(1) == 0 and self.get(4) == 3, "gap no output")
        self.call(14, now + 400)
        check(self.call(7, now+400) == 8, "second phase independently rearmed")
        check(self.call(11, now+400), "observed second phase ready")
        check(self.call(12, now+400), "second phase start")
        check(self.get(1) == mask and self.get(2) == 0, "second polarity identities")
        self.call(13, now + 600)
        self.call(14, now + 601)
        check(self.get(4) == 0 and self.get(1) == 0 and self.get(10) == 0,
              "completed event returns idle with no requested output")
        return mask


def motor_replay(runtime, motor, transport):
    """New coarse integration adapter; borrows calibration/basis from Stage 3.

    The companion is given synthetic feature observations and independently
    measured OFF-probe positions, never private theta/actual future movement.
    A separately declared current-to-recruitment map connects admitted requests
    to model response. The C core alone does not validate that map.
    """
    c = motor.Config()
    cal = motor.calibration(26101301, c, "nominal")
    reference = np.eye(2) * c.amplitude_m
    dt, blocks, frames = .025, 24, 80
    alpha = 1 - np.exp(-dt/c.activation_tau_s)
    phase = motor.basis(np.arange(frames)*dt)
    summaries, traces = [], []
    for arm, rho in (("off", 1.), ("neutral", 1.), ("favorable", 2.), ("adverse", -1.)):
        theta = cal["initial"].copy()
        activation = np.zeros(2)
        first_on = None
        accepted = 0
        peak_current = 0
        max_tail = 0.
        history = []
        now = 2000000
        event_id, sequence = 0, 1
        for block in range(blocks):
            # Each bounded drill is a separate initialized replay session. Probe
            # and washout time also advances the host clock between drills.
            runtime.start(1, now, transport)
            event_id, sequence = 0, 1
            # Independent common OFF probe measured on known cue. No ground-truth
            # learner coefficient is passed to the online policy below.
            probe = phase @ theta.T
            theta_hat = np.linalg.lstsq(phase, probe, rcond=None)[0].T
            history.append(motor.rmse(theta, reference))
            delivered = np.zeros((frames, 2))
            positions = np.zeros((frames, 2))
            delayed = deque([np.zeros(2), np.zeros(2)])
            for i in range(frames):
                if i % 4 == 0:
                    sequence += 1
                    check(runtime.call(5, now, 1, sequence, 250000), "renewed motor lease")
                stimulation = cal["gain"] @ activation
                positions[i] = theta @ phase[i] + stimulation
                delivered[i] = stimulation
                command = np.zeros(2)
                support_us = None
                if i >= 8 and arm != "off":
                    # The previous frame's abstract neural features arrive now.
                    support_us = now - 25000
                    features = cal["mixing"] @ phase[i-1]
                    check(conditional_feature_usable(features,support_us,now,now),
                          "conditional neural feature quality/freshness")
                    observed = motor.unit(features @ cal["decoder"])
                    predicted = motor.rotate(observed, 2*np.pi*(.025+.050+c.activation_tau_s))
                    command = np.clip(np.linalg.solve(cal["fitted_gain"],
                        c.assistance_fraction*(reference-theta_hat) @ predicted), -1, 1)
                    check(support_us <= now, "motor observation causal")
                currents = tuple(int(round(abs(x)*3000)) for x in command)
                contacts = (2 if command[0] >= 0 else 3, 9 if command[1] >= 0 else 10)
                equivalent = np.zeros(2)
                if any(currents):
                    event_id += 1
                    mask = runtime.event(now, currents, contacts, event_id)
                    check(mask != 0, "request completed before model admits response")
                    equivalent = np.sign(command)*np.array(currents)/3000
                    accepted += 1
                    peak_current = max(peak_current, *currents)
                    if block == 0 and i % 8 == 0:
                        traces.append(dict(arm=arm, time_us=now, support_us=support_us,
                            contact=list(contacts), requested_current_ua=list(currents),
                            phase_us=200, gap_us=200, completed_phase_count=2,
                            delivered_fraction_assumed=equivalent.tolist(),
                            measured_position_model_m=positions[i].tolist()))
                lagged = delayed.popleft()
                delayed.append(equivalent)
                activation += alpha*(lagged-activation)
                now += 25000
            target = phase @ reference.T
            if first_on is None:
                first_on = float(np.sqrt(np.mean((target-positions)**2)))
            # Identical transparent Stage 3 teaching identity, now based on the
            # actually completed C-core event amplitude in this replay.
            gram_inverse = np.linalg.inv(phase.T @ phase)
            stim_projection = delivered.T @ phase @ gram_inverse
            theta += c.learning_rate_per_block*(reference-theta+(rho-1)*stim_projection)
            # Flush both queued delayed frames, then pay a two-second washout.
            for value in delayed:
                activation += alpha*(value-activation)
            activation *= math.exp(-c.washout_s/c.activation_tau_s)
            max_tail = max(max_tail, float(np.max(np.abs(activation))))
            check(max_tail < 1e-18, "OFF probe excludes modeled actuator tail")
            now += 3000000
        retained = cal["initial"] + c.assumed_retention_fraction*(theta-cal["initial"])
        summaries.append(dict(arm=arm, rho=rho, first_on_rmse_m=first_on,
            initial_off_rmse_m=history[0], final_off_rmse_m=motor.rmse(retained, reference),
            admitted_events=accepted, maximum_current_ua=peak_current,
            maximum_post_washout_activation=max_tail, practice_blocks=blocks,
            practice_seconds=blocks*2, common_probe_seconds=blocks,
            common_washout_seconds=blocks*2))
    by_arm = {r["arm"]:r for r in summaries}
    check(abs(by_arm["neutral"]["final_off_rmse_m"]-by_arm["off"]["final_off_rmse_m"]) < 1e-12,
          "neutral teaching does not manufacture retained benefit")
    check(by_arm["favorable"]["final_off_rmse_m"] < by_arm["off"]["final_off_rmse_m"],
          "favorable declared teaching can improve retained model outcome")
    check(by_arm["adverse"]["final_off_rmse_m"] > by_arm["off"]["final_off_rmse_m"],
          "adverse teaching remains worse")
    return dict(config=dict(dt_s=dt, frames_per_block=frames, blocks=blocks,
        current_ceiling_ua=3000, event_rate_hz=40, event_phase_us=200, gap_us=200,
        onset_delay_s=.050, activation_tau_s=.040, washout_s=2.,
        recruitment_map="Assumed gain columns per normalized 40 Hz train; 3000 uA maps to one, not a measured recruitment law",
        neural_source="Causal synthetic abstract features; not target RHD EMA telemetry",
        runtime_sample_identity="Synthetic known raw-monitor conversion at setup; not a neural-validity certificate",
        off_metrics="Assumed 0.95 retention of acquired theta after modeled washout"),
        arms=summaries, first_block_trace=traces)


def pressure_replay(runtime, transport):
    rows = []
    dt = .25
    pressure, activation, response = 120., 0., 0.
    last_observation = pressure
    now, sequence, event_id = 2000000, 1, 0
    runtime.start(2, now, transport, pressure)
    now += 250000
    command_sequence = 1
    for step in range(240):
        time = step*dt
        deficit = 20. if 10 <= time < 40 else 0.
        pressure = 120.-deficit+response
        if step % 4 == 0:
            # Only one pressure packet per second updates the policy. The value
            # was generated at the preceding frame, with its actual old support.
            last_observation = rows[-1]["pressure_model_mmHg"] if rows else 120.
            sequence += 1
            packet = transport.pack_packet(seq=sequence,
                support=(now-250000, now-250000), extraction=now-10000,
                pressure=last_observation)
            check(runtime.packet(packet, now), "actual C SBP parser accepts causal feedback")
            command_sequence += 1
            check(runtime.call(5, now, 2, command_sequence, 3000000), "pressure lease renewed")
        # Companion P control uses last observed pressure; the body model is private.
        # A rising target cannot synthesize active depressor authority.
        command = pressure_command(last_observation)
        current = int(round(3000*command))
        completed_fraction = 0.
        events = 0
        if current:
            # An explicit 40 Hz train: ten fully checked events per policy frame.
            for offset in range(0, 250000, 25000):
                event_id += 1
                runtime.event(now+offset, (current, 0), (2, 9), event_id)
                events += 1
            completed_fraction = current/3000.
        else:
            runtime.call(14, now)
        # Declared first-order illustrative physiology, not a calibrated BP patient.
        activation += (1-math.exp(-dt/1.5))*(completed_fraction-activation)
        response += (1-math.exp(-dt/6.))*(30*activation-response)
        rows.append(dict(time_s=time, measured_sbp_mmHg=last_observation,
            pressure_model_mmHg=pressure, requested_fraction=command,
            completed_current_ua=current, completed_events=events,
            modeled_pressor_response_mmHg=response,
            pressure_support_age_ms=250.+250*(step % 4)))
        now += 250000
    active = [r for r in rows if 10 <= r["time_s"] < 40]
    recovery = [r for r in rows if r["time_s"] >= 40]
    check(all(0 <= r["requested_fraction"] <= 1 for r in rows), "positive bounded pressure authority")
    check(any(r["completed_events"] for r in rows), "physiology loop has actual completed C events")
    check(max(r["pressure_model_mmHg"] for r in recovery) > 120., "withdrawal overshoot retained")
    return dict(config=dict(duration_s=60, policy_period_s=.25, packet_period_s=1,
         event_rate_hz=40, assumed_gain_mmHg=30, activation_tau_s=1.5,
         response_tau_s=6, deficit_mmHg=20, deficit_interval_s=[10,40],
         feedback="External causal SBP packets, not decoded spinal BP",
         policy="Illustrative companion P control, not a clinical prescription"),
         disturbed_rmse_mmHg=float(np.sqrt(np.mean([(120-r["pressure_model_mmHg"])**2 for r in active]))),
         unassisted_disturbed_rmse_mmHg=20.,
         maximum_recovery_sbp_mmHg=max(r["pressure_model_mmHg"] for r in recovery),
         completed_events=sum(r["completed_events"] for r in rows), trace=rows)


def faults(runtime, transport):
    results=[]
    t=2000000
    for case in ("invalid_raw_identity", "stale_sbp", "crc_corruption", "packet_replay",
                 "pressure_packet_loss", "companion_lease_loss", "active_route_mismatch",
                 "current_above_envelope", "shared_contact_conflict", "off_trial",
                 "independent_inhibit_midphase", "phase_timeout", "restored_health_no_autorearm"):
        mode=2 if case in {"stale_sbp","crc_corruption","packet_replay","pressure_packet_loss"} else 1
        runtime.start(mode,t,transport)
        if case=="invalid_raw_identity":
            check(not runtime.call(3,t+1,t+1,2,1,1),case)
            expected=9
        elif case in {"stale_sbp","crc_corruption","packet_replay"}:
            packet=transport.pack_packet(seq=2, support=(t-99999,t-50000),extraction=t-10000)
            if case=="stale_sbp":
                packet=transport.pack_packet(seq=2,support=(1,2),extraction=3)
                at=t+1000
            else:
                at=t
            if case=="crc_corruption":
                packet=packet[:-1]+bytes([packet[-1]^1])
            if case=="packet_replay":
                check(runtime.packet(packet,at),"first distinct SBP accepted")
            check(not runtime.packet(packet,at),case)
            expected=4
        elif case=="pressure_packet_loss":
            runtime.call(14,t+1900001)
            expected=5
        elif case=="companion_lease_loss":
            runtime.call(14,t+250000)
            expected=6
        elif case=="active_route_mismatch":
            check(not runtime.route(t,observed=(3,9)),case)
            expected=7
        elif case in {"current_above_envelope","shared_contact_conflict"}:
            contacts=(2,2) if case=="shared_contact_conflict" else (2,9)
            check(runtime.route(t,contacts),"valid preceding route")
            current=(3000,3000) if case=="shared_contact_conflict" else (3001,0)
            check(not runtime.plan(t,current,contacts,1),case)
            expected=8
        elif case=="off_trial":
            runtime.event(t,(3000,2500),(2,9),1,off=True)
            expected=0
        else:
            check(runtime.route(t),"valid preceding route")
            check(runtime.plan(t,(3000,0),(2,9),1),"first phase plan")
            check(runtime.call(7,t)==8,"phase rearm action")
            check(runtime.call(11,t) and runtime.call(12,t),"phase started")
            if case=="phase_timeout":
                runtime.call(14,t+201)
                expected=8
            else:
                runtime.call(1,t+100,127&~32,3)
                expected=3
                if case=="restored_health_no_autorearm":
                    runtime.call(1,t+101,127,3)
        check(runtime.get(3)==expected,case+" fault identity")
        check(runtime.get(1)==0 and runtime.get(10)==0,case+" no output request")
        if expected:
            check(runtime.get(0)==0,case+" inhibition remains")
        results.append(dict(case=case,passed=True,fault_code=runtime.get(3),
            output_request_mask=runtime.get(1),armed=bool(runtime.get(0)),
            scope="Compiled production core with synthetic health/input observations"))
    return results


def supervisor_replay(supervision):
    rows=[]
    for case in ("normal_200us", "host_stuck_request", "guard_fault", "monitor_permit_loss"):
        s=supervision.Supervisor()
        s.healthy_start()
        s.phase_arm(5100000)
        s.event(5102000,"replayed_host_request",channel=0,request=True,run=True,quiet=False)
        check(s.allow(0) is True,"independent modeled path initially permits")
        if case=="normal_200us":
            s.event(5302000,"host_normal_phase_end",channel=0,request=False,run=False,quiet=True)
        elif case=="guard_fault":
            s.event(5202000,"independent_guard_fault",guard_fault_n=False)
        elif case=="monitor_permit_loss":
            s.event(5202000,"independent_monitor_loss",channel=0,mon_permit=False)
        else:
            s.advance(5102000+supervision.SECONDARY_NS)
        check(s.allow(0) is False,case+" terminal guard command removed")
        rows.append(dict(case=case,request_still_high=s.channels[0].request,
            terminal_allow=s.allow(0),armed=s.armed,time_ns=s.time_ns,
            source="Unchanged Stage4 ideal independent Supervisor state equations",
            physical_delay_qualified=False))
    return rows


def port_trace():
    path=ROOT/"cad/stage5/harness/body-port-bridge.csv"
    rows=list(csv.DictReader(path.open(encoding="utf-8-sig",newline="")))
    check(len(rows)==36,"36 exact future/interface ports")
    for i,row in enumerate(rows):
        check(row["port_id"]==f"P{i+1:02}","port identity")
        if i<18:
            check(row["board"]=="recording-front-end" and row["pcb_reference"]=="J30003"
                and row["pin"]==str(i+1),"recording input mapping")
        else:
            check(row["board"]=="supervision" and row["pcb_reference"]=="J50101"
                and row["pin"]==str(i-17),"protected body facing output mapping")
            check("After independent" in row["guard_boundary"],"guard cannot be bypassed")
    check(rows[17]["source_net"]=="BIAS_CONTACT","body bias distinct from stimulation return")
    check([r["source_net"] for r in rows[-2:]]==["BODY_RETURN0","BODY_RETURN1"],
          "two protected source returns")
    return dict(ports=len(rows),recording_header="J30003",protected_output_header="J50101",
        example=dict(contact_index=2,logical="STIM_03",port="P21",pin="3",return_port="P35",
                     return_pin="17",recording_port="P01",recording_pin="1"),
        no_physical_continuity_measurement=True)


def companion_faults():
    cases=[]
    for name, values, support, arrival, valid, expected in (
            ("fresh_feature",[1.,2.],1975000,2000000,True,True),
            ("stale_feature",[1.,2.],1949999,2000000,True,False),
            ("future_feature_support",[1.,2.],2000001,2000000,True,False),
            ("future_arrival",[1.,2.],1975000,2000001,True,False),
            ("invalid_or_artifact_flag",[1.,2.],1975000,2000000,False,False),
            ("nonfinite_feature",[float("nan"),2.],1975000,2000000,True,False)):
        usable=conditional_feature_usable(values,support,arrival,2000000,valid)
        check(usable==expected,name)
        cases.append(dict(case=name,accepted=usable,expected=expected,
            owner="New conditional companion adapter, not production C neural validity"))
    check(pressure_command(140.)==0.,"pressor policy has no active depressor authority")
    check(pressure_command(50.)==1.,"unreachable low pressure saturates without exceeding cap")
    return cases


def summary_of(actual):
    return dict(schema="scci_rh-stage6-integration-summary-v1",date=actual["date"],passed=True,
        source_report="results/stage6/digital-path-verification.json",
        source_report_sha256_lf=digest(OUT/"digital-path-verification.json"),
        assertions=actual["assertions"],
        scenario_groups=4+1+len(actual["fault_cases"])+len(actual["independent_supervision_cases"])
                        +len(actual["companion_fault_cases"]),
        motor_arms=actual["motor"]["arms"],
        motor_completed_events=sum(a["admitted_events"] for a in actual["motor"]["arms"]),
        physiology={k:v for k,v in actual["physiology"].items() if k!="trace"},
        compiled_core_fault_cases=len(actual["fault_cases"]),
        separate_independent_supervision_cases=len(actual["independent_supervision_cases"]),
        conditional_companion_fault_cases=len(actual["companion_fault_cases"]),
        protected_body_ports=actual["port_trace"]["ports"],
        live_rhd_feedback_while_motor_implemented=False,
        target_peripheral_execution=False,physical_integrated_execution=False,
        biological_efficacy_demonstrated=False,
        interpretation="Compiled production C admission/phase state machine plus declared companion/recruitment/body adapters; no measured current or biological benefit",
        model_to_current_relation="An illustrative unmeasured calibration premise, not a validated conversion or waveform prescription")


def run():
    global ASSERTIONS
    ASSERTIONS=0
    motor=module("stage6_motor_source","experiments/stage3/conditional-concept/study.py")
    transport=module("stage6_transport_source","electronics/stage4/transport-study/transport_contract.py")
    supervision=module("stage6_supervision_source","electronics/stage4/supervision-study/control_study.py")
    test=module("stage6_compiler_source","firmware/nrf5340/tests/check_runtime.py")
    with tempfile.TemporaryDirectory(prefix="scci_rh-stage6-") as temporary:
        lib=Path(temporary)/("scci_rh_replay.dll" if os.name=="nt" else "scci_rh_replay.so")
        command=test.compiler()+["-std=c11","-O2","-Wall","-Wextra","-Werror","-Wpedantic",
             "-shared","-I",str(ROOT/"firmware/nrf5340/core"),
             str(ROOT/"firmware/nrf5340/core/scci_rh_runtime.c"),
             str(ROOT/"scripts/stage6/runtime_bridge.c"),"-o",str(lib)]
        if os.name!="nt":
            command+= ["-fPIC"]
        subprocess.run(command,check=True,capture_output=True,text=True)
        runtime=Runtime(lib)
        try:
            motor_result=motor_replay(runtime,motor,transport)
            pressure_result=pressure_replay(runtime,transport)
            fault_result=faults(runtime,transport)
            supervisor_result=supervisor_replay(supervision)
        finally:
            # Windows cannot remove a loaded DLL; release even on a failed check.
            if os.name=="nt":
                import _ctypes
                _ctypes.FreeLibrary(runtime.dll._handle)
    native_sources=["firmware/nrf5340/core/scci_rh_runtime.c","firmware/nrf5340/core/scci_rh_runtime.h",
        "firmware/nrf5340/tests/check_runtime.py","experiments/stage3/conditional-concept/study.py",
        "electronics/stage4/transport-study/transport_contract.py",
        "electronics/stage4/supervision-study/control_study.py",
        "cad/stage5/harness/body-port-bridge.csv","firmware/nrf5340/app/src/scci_rh_backend.c",
        "scripts/stage6/runtime_bridge.c",
        "scripts/stage6/verify_digital_path.py"]
    ports=port_trace()
    companion_cases=companion_faults()
    return stable(dict(schema="scci_rh-stage6-digital-path-v1",date="2026-10-16",passed=True,
        assertions=ASSERTIONS,baseline_commit="736015848cf581df66488bf53aa6360152eb767b",
        scope="Conditional companion/response replay through unchanged compiled production C core; separate ideal supervision model; no physical/target/biological execution",
        current_profile_limit="Target records RHD only in OBSERVE; live synthetic spinal feature adapter is conditional and not implemented by target",
        numerical_compare="Round floating results to 10 decimal places; integer and hash identities exact",
        source_sha256_lf={p:digest(ROOT/p) for p in native_sources},
        motor=motor_result,physiology=pressure_result,fault_cases=fault_result,
        companion_fault_cases=companion_cases,
        independent_supervision_cases=supervisor_result,port_trace=ports))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-results",action="store_true")
    args=parser.parse_args()
    actual=run()
    report=OUT/"digital-path-verification.json"
    if args.write_results:
        OUT.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(actual,indent=2)+"\n",encoding="utf-8")
        (OUT/"integration-summary.json").write_text(json.dumps(summary_of(actual),indent=2)+"\n",
                                                   encoding="utf-8")
    else:
        expected=json.loads(report.read_text(encoding="utf-8"))
        check(actual==expected,"Stage6 saved replay and source identities reproduce")
        check(summary_of(actual)==json.loads((OUT/"integration-summary.json").read_text(encoding="utf-8")),
              "Stage6 summary matches detailed source-bound results")
    print(json.dumps(dict(passed=True,assertions=actual["assertions"],
        motor_completed_events=sum(a["admitted_events"] for a in actual["motor"]["arms"]),
        physiology_completed_events=actual["physiology"]["completed_events"],
        core_fault_cases=len(actual["fault_cases"]),
        independent_supervision_cases=len(actual["independent_supervision_cases"]))))


if __name__=="__main__":
    main()
