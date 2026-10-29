"""Observed-data cue forecast and digital frame scheduling component witness.

Counterfactual scheduling replay does not apply commands to its source recording.
The separate context-barrier branch stops after its first authorized command.
No retained learning, efficacy or complete coupled cue controller is reported.
"""
from dataclasses import asdict, replace
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from scci_rh.stage3 import motor
from scci_rh.stage3.electrical import MotorDelivery
from scci_rh.stage3.cue_policy import (CueConfig, CuePolicy, CueFrameScheduler,
                                 fit_known_cue_forecast, validate_forecast_context)


def source_hash(relative):
    return hashlib.sha256((ROOT/relative).read_text(encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest()


def replay(observations, model, response, decoder_model, representation, c,
           *, fault=None, stop_after_first=False):
    policy = CuePolicy(model); scheduler = CueFrameScheduler(); decoder = motor.CausalDecoder(c, decoder_model)
    decisions, commands = [], []; reasons = Counter(); context = "nominal_unassisted"
    previous = None
    for index, original in enumerate(observations):
        # The tick occurs before the next observation block becomes available.
        at = original.available_time_s-c.dt_s
        launched = scheduler.tick(at)
        if launched:
            commands.append(asdict(launched))
            if stop_after_first: context = "cue_closed_loop_unvalidated"
        o = original
        if fault == "invalid" and index >= len(observations)//2:
            o = replace(o, external_valid=False)
        elif fault == "replay" and index >= len(observations)//2 and previous is not None:
            o = replace(o, external_position_m=previous.external_position_m,
                        external_measurement_time_s=previous.external_measurement_time_s)
        elif fault == "stale" and index >= len(observations)//2:
            o = replace(o, external_measurement_time_s=o.available_time_s-.100)
        elif fault == "context" and index >= len(observations)//2:
            context = "unvalidated_transfer"
        elif fault == "unannounced_sensor_offset" and index >= len(observations)//2:
            o = replace(o, external_position_m=tuple(np.asarray(o.external_position_m)+np.array([.040, -.040])))
        estimate = decoder.estimate(o, "neural_external")
        guard_reason = scheduler.observe_guard(o, estimate, o.available_time_s, context)
        command, reason = policy.propose(o, estimate, response, representation,
                                        o.available_time_s, context_id=context)
        if guard_reason: command = None
        scheduler.submit(command, o.available_time_s)
        reasons[reason] += 1
        decisions.append({"available_time_s": o.available_time_s,
            "external_support_s": o.external_measurement_time_s, "context": context,
            "state_estimate": asdict(estimate), "policy_reason": reason,
            "guard_reason": guard_reason,
            "planned_command": None if command is None else asdict(command)})
        previous = o
    scheduler.tick(observations[-1].available_time_s+.100)
    return {"scope": "digital scheduling replay of measured unassisted recording; commands do not drive source body",
            "fault": fault, "stop_after_first_command_for_unvalidated_coupling": stop_after_first,
            "summary": {"observation_packets": len(decisions), "launched_commands": len(commands),
                        "policy_reason_counts": dict(reasons), "cancellations": sum(e["event"]=="CANCEL" for e in scheduler.events),
                        "maximum_observed_delayed_forecast_residual_m": policy.maximum_observed_residual_m,
                        "first_residual_failure_arrival_s": policy.first_residual_failure_arrival_s,
                        "physical_pulses": 0, "retained_learning_measured": False},
            "commands": commands, "scheduler_events": scheduler.events, "decisions": decisions}


def run_study():
    c = motor.MotorConfig(body_integration_step_s=.0025, body_integration_method="midpoint_exact_cascade")
    observations, _, _, _ = motor._capture(2, c, 12.)
    model = fit_known_cue_forecast(observations)
    conditional_map, neural_model, conditional_calibration = motor.calibrate(2, c)
    actual_map, _, actual_calibration = motor.calibrate(2, c, MotorDelivery())
    library = motor._expert_library(2, c)
    reference = library["learner_only"]
    validation = {}
    independent, _, _, _ = motor._capture(12002, c, 4., subject_seed=2)
    validation["withheld_unassisted"] = validate_forecast_context(model, independent, "withheld_unassisted")
    assisted, _, pulses, _ = motor._capture(12003, c, 4., subject_seed=2,
        probe=lambda t: np.array([1., -1.]) if .5 <= t < 2.5 else np.zeros(2))
    validation["withheld_fixed_profile_assisted"] = validate_forecast_context(
        model, assisted, "withheld_fixed_profile_assisted") | {"pulse_count": len(pulses),
        "profile_scope": "independent observed same-subject nominal-cadence open-loop fixed-profile train; not cue closed-loop context"}
    drifted = [replace(o, external_position_m=tuple(np.asarray(o.external_position_m)
                    + (np.array([.040, -.040]) if o.available_time_s>=2. else np.zeros(2)))) for o in independent]
    validation["withheld_sensor_offset_step"] = validate_forecast_context(model, drifted, "withheld_sensor_offset_step")
    runs = [{"branch": "actual_nominal35ms_negative_precision", "delivery": "independent actual electrical calibration; no replay pulses",
             "response": asdict(actual_map), "authority_margin_m": actual_calibration["authority_singular_margin_m"],
             "replay": replay(independent, model, actual_map, neural_model, reference, c)},
            {"branch": "conditional_nominal35ms_cue_scheduling_component", "delivery": "UNQUALIFIED_NOMINAL_ASSUMPTION; no body coupling",
             "response": asdict(conditional_map), "authority_margin_m": conditional_calibration["authority_singular_margin_m"],
             "replay": replay(independent, model, conditional_map, neural_model, reference, c)},
            {"branch": "conditional_unvalidated_closed_loop_context_barrier", "delivery": "UNQUALIFIED_NOMINAL_ASSUMPTION; barrier witness",
             "replay": replay(independent, model, conditional_map, neural_model, reference, c, stop_after_first=True)}]
    for fault in ("invalid", "replay", "stale", "context", "unannounced_sensor_offset"):
        runs.append({"branch": "conditional_negative_control_"+fault, "delivery": "UNQUALIFIED_NOMINAL_ASSUMPTION; no body coupling",
                     "replay": replay(independent, model, conditional_map, neural_model, reference, c, fault=fault)})
    if runs[0]["replay"]["summary"]["launched_commands"]:
        raise AssertionError("Actual unqualified authority emitted a cue command")
    if runs[2]["replay"]["summary"]["launched_commands"]>1:
        raise AssertionError("Unvalidated assisted context was silently continued")
    return {"schema": "scci_rh.stage3.cue-policy-study.v1", "status": "component_witness_only",
        "source_identity": {name: source_hash(name) for name in (
            "src/scci_rh/stage3/cue_policy.py", "src/scci_rh/stage3/motor.py", "src/scci_rh/stage3/acquisition.py",
            "scripts/stage3_cue_policy_study.py")},
        "specification": asdict(CueConfig()), "motor_config": asdict(c),
        "task_reference": asdict(reference),
        "reference_competence": "known instructed goal; no expert training used. Existing recorded expert resource is not treated as task-competence qualified.",
        "original_reactive_prediction_cap_s": c.maximum_prediction_horizon_s,
        "new_forecast_family": "empirically tested known-instruction forecast150ms; original reactive100ms policy unchanged",
        "forecast": model, "context_validation": validation, "runs": runs,
        "limitations": ["Future known taskinstructions are allowed; future achievedbodystate/phase/coefficients/recruitment are forbidden online.",
            "External measured-history predictor has40inputs and is a different policyfamily; no spinalinformation advantage claimed.",
            "Maximum holdout error plus3mm chosen label allocation is empirical and is not a statistical confidence/universal errorbound.",
            "Replay commands do not affect their source recording; performance/learning/biological control cannot be inferred.",
            "Actual electrical authority remains negative; no refined measurement assumed silently.",
            "Independent assisted/context probes qualify only tested captures/horizons; cue closed-loop remains unvalidated and abstains.",
            "Scheduler emits signedfraction requests; continuous routing, pulse-density delivery/guard and power integration remain downstream work."]}


def plain(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    raise TypeError(type(value).__name__)


def close(actual, expected, path="root"):
    if isinstance(actual, dict):
        if actual.keys()!=expected.keys(): raise AssertionError("Key mismatch "+path)
        for key in actual: close(actual[key], expected[key], path+"."+key)
    elif isinstance(actual, (list, tuple, np.ndarray)):
        if len(actual)!=len(expected): raise AssertionError("Length mismatch "+path)
        try:
            a,b=np.asarray(actual),np.asarray(expected)
            if a.dtype.kind in "fiu" and b.dtype.kind in "fiu":
                if not np.allclose(a,b,rtol=2e-8,atol=1e-11): raise AssertionError("Numeric mismatch "+path)
                return
        except (ValueError, TypeError): pass
        for i,(a,b) in enumerate(zip(actual,expected)): close(a,b,f"{path}[{i}]")
    elif isinstance(actual,float):
        if not np.isclose(actual,expected,rtol=2e-8,atol=1e-11): raise AssertionError("Numeric mismatch "+path)
    elif actual!=expected: raise AssertionError("Mismatch "+path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path); parser.add_argument("--check",type=Path)
    args=parser.parse_args()
    if args.output and args.check: parser.error("Choose output or check")
    result=run_study()
    if args.check:
        with gzip.open(args.check,"rt",encoding="utf-8") as stream: expected=json.load(stream)
        close(result,expected); print("Cue component receipt reproduced with explicit negative/unvalidated gates")
    elif args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        encoded=(json.dumps(result,default=plain,separators=(",",":"),allow_nan=False)+"\n").encode()
        with args.output.open("wb") as stream:
            with gzip.GzipFile(filename="",fileobj=stream,mode="wb",mtime=0) as compressed: compressed.write(encoded)
        brief={k:v for k,v in result.items() if k not in {"forecast","runs"}}
        brief["raw_witness"]={"path":args.output.name,"sha256":hashlib.sha256(args.output.read_bytes()).hexdigest()}
        brief["forecast"]={k:v for k,v in result["forecast"].items() if k!="models"}
        brief["forecast"]["models"]=[{k:v for k,v in m.items() if k not in {"mean","scale","weights"}} for m in result["forecast"]["models"]]
        brief["runs"]=[{k:v for k,v in r.items() if k!="replay"}|{"summary":r["replay"]["summary"]} for r in result["runs"]]
        args.output.with_name("summary.json").write_text(json.dumps(brief,default=plain,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        print("Saved observed forecast/context validation and8digital scheduling replays")
    else: print(json.dumps({"status":result["status"],"runs":[r["replay"]["summary"] for r in result["runs"]]}))


if __name__=="__main__":main()
