"""Reproduce the finite moving-body/contact-aperture source sensitivity study.

This is a synthetic source/electronics applicability study, not a biological
observability result or a new closed-loop learning efficacy experiment.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import gzip
import hashlib
import io
import json
from multiprocessing import get_context
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scci_rh.stage3.source_sensitivity import BUDGETS, REFERENCE_GRIDS, SCENARIOS, SOURCE_VARIANTS, MovingBodyReference, run_study  # noqa: E402

SOURCE_PATHS = ("src/scci_rh/stage3/source_sensitivity.py", "src/scci_rh/stage3/motor.py",
                "src/scci_rh/stage3/acquisition.py", "src/scci_rh/stage3/filter_residual.py",
                "src/scci_rh/stage3/external_history.py", "scripts/stage3_source_sensitivity.py")
RTOL, ATOL = 2e-8, 1e-11


def source_identity():
    return {path: hashlib.sha256((ROOT / path).read_text(encoding="utf-8").replace(
        "\r\n", "\n").encode("utf-8")).hexdigest() for path in SOURCE_PATHS}


def run_case(seed):
    print(f"Moving-source sensitivity: subject seed {seed}", flush=True)
    return run_study(seed, extras=seed == 0)


def serializable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def run_batch(jobs=1, scope="full"):
    initial = source_identity()
    seeds = (0, 1) if scope == "full" else (0,)
    if jobs == 1:
        studies = [run_case(seed) for seed in seeds]
    else:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context("spawn")) as pool:
            studies = list(pool.map(run_case, seeds))
    if initial != source_identity():
        raise AssertionError("Actual study dependencies changed during the experiment")
    result = {"schema": "scci_rh.stage3.moving-source-sensitivity.v1", "scope": scope,
        "source_identity": initial,
        "specification": {"frozen_before_outcomes": True, "budgets": BUDGETS, "subject_seeds": list(seeds),
            "seconds_per_capture": 3., "source_variants": list(SOURCE_VARIANTS), "scenarios": list(SCENARIOS),
            "source_modes": ["informative", "redundant", "absent"], "reference_internal_steps_s": list(REFERENCE_GRIDS),
            "source_normalization": "position/.1m; physical velocity/(2pi*.1m/s), except historical previous5ms mean velocity",
            "reference_definition": "Independent event-split DOP853 solution of coupled activation, movement and chosen favorable coefficient ODE; right-continuous instantaneous derivative at physical apertures.",
            "delivery_scope": "Predetermined whole 3mA/200us-per-phase/40Hz-frame admitted-profile replay, normalized true dose1 per selected route. Evaluator assumption; no qualified monitor, hardware delivery or causal adaptive stimulation claim.",
            "fit_boundary": {"allowed": ["32 voltage-derived features", "packet quality/support", "observed external positions", "their declared support times"],
                "forbidden": ["private trajectory", "private lead matrix", "hidden recruitment", "ground-truth velocity", "source variant identity", "future evaluation labels"],
                "split": "Legacy clean calibration, chronological75/25 with100ms purge each side and differentiated labels constructed inside partitions. Evaluation recording/noise IDs independent of calibration IDs. Same scripted subject trajectory is reused to isolate aperture/source approximation; no independent task/human generalization claim."},
            "selected_faults": ["clock100us and120us", "lost5ms acquisition block", "changed source geometry at1.5s", "nonaligned37.37ms motor onset"],
            "ambiguity": "Paired distinct foot-swapped trajectories through a deliberately rank-deficient lead field; same exact physical noise and indistinguishable measured features, conflicting observed external positions.",
            "claim_limits": ["Finite synthetic voltage-source and sample-aperture study; no claim that spinal contacts encode these four chosen movement variables.",
                "Source-hold failures are retained. Fine integration cannot repair noninjective fields, residual artifact uncertainty or absent information.",
                "Observed conflict abstention uses already-available external measurements; no universal unknown-state ambiguity detector.",
                "No retained-learning, consumer efficacy, neural incremental value, safe implant or optimized electrode-placement qualification."]},
        "reproduction": {"rtol": RTOL, "atol": ATOL,
            "platform_local_diagnostics": ["actual_noise_sha256", "external_noise_sha256", "rhs_evaluations"],
            "reference_witness_policy": "Validate each maximum-position witness independently, including its coarse/fine positions recomputed at its own physical aperture using the frozen study subject/scenario/reference grids. If both maxima are below the fixed absolute reproduction tolerance, its argmax location is a roundoff diagnostic and may differ; all maxima, budgets, decisions and other numeric observations remain compared.",
            "noise_policy": "Within each execution, actual paired draws/hashes, generator states and observational schedules must be exactly equal. Across executions, raw numeric witnesses use declared tolerance; RNG states/counts exact, empirical moments numeric. Byte hashes and solver evaluation counts are platform diagnostics."},
        "studies": studies}
    result = json.loads(json.dumps(result, default=serializable, allow_nan=False))
    validate_receipt(result)
    return result


def all_captures(study):
    yield from study["training"]
    yield from study["captures"]
    yield from (row["capture"] for row in study["fine_grid_captures"])
    for fault in study["faults"]:
        yield from fault["captures"]
    if study["ambiguous_witness"] is not None:
        yield from study["ambiguous_witness"]["captures"]


def all_comparisons(study):
    yield from study["comparisons"]
    yield from (row["comparison"] for row in study["fine_grid_captures"])
    yield from (row["comparison"] for row in study["faults"])


def validate_receipt(batch):
    assert batch["schema"] == "scci_rh.stage3.moving-source-sensitivity.v1"
    seeds = [0, 1] if batch["scope"] == "full" else [0]
    assert [study["subject_seed"] for study in batch["studies"]] == seeds
    assert batch["specification"]["budgets"] == BUDGETS
    for study in batch["studies"]:
        assert len(study["training"]) == 3 and len(study["captures"]) == 27
        assert len(study["comparisons"]) == 27
        assert all(c["identical_actual_noise"] and c["paired_observation_support_pass"]
                   for c in all_comparisons(study))
        training_ids = {row["recording_seed"] for row in study["training"]}
        assert training_ids.isdisjoint(row["recording_seed"] for row in study["captures"])
        for ref in study["references"].values():
            assert ref["refinement"]["identical_physical_event_boundaries"]
            assert ref["refinement"]["position_budget_pass"] and ref["refinement"]["velocity_budget_pass"]
            assert ref["refinement"]["actual_contact_aperture_count"] == 192000
        for comparison in study["comparisons"]:
            if comparison["source_mode"] != "informative":
                assert comparison["maximum_feature_difference_uv"] == 0.
        for record in all_captures(study):
            assert record["aperture_support"]["all_apertures_before_packet_availability"]
            assert record["noise"]["scalar_count"] == 204000 and record["noise"]["calls"] == 1200
            assert all(row["support_end_s"] < row["available_time_s"] for row in record["rows"])
        for record in study["captures"]:
            if record["scenario"] == "moving_dense_train":
                assert record["summary"]["qualified_active_window_packets"] == 0, "Dense artifact failure was erased"
        if study["subject_seed"] == 0:
            assert len(study["fine_grid_captures"]) == 3 and len(study["faults"]) == 5
            for fine in study["fine_grid_captures"]:
                assert fine["comparison"]["within_predeclared_feature_allocation"]
                assert fine["comparison"]["within_predeclared_prediction_allocation"]
            faults = {f["name"]: f for f in study["faults"]}
            assert all(r["summary"]["qualified_packet_count"] == 0 for r in faults["clock_120us"]["captures"])
            assert all(r["summary"]["qualified_packet_count"] > 0 for r in faults["clock_100us"]["captures"])
            for lost in faults["lost_5ms_block"]["captures"]:
                baseline = next(r for r in study["captures"] if r["scenario"] == "moving_clean" and
                                r["source_mode"] == "informative" and r["source_variant"] == lost["source_variant"])
                assert lost["noise"] == baseline["noise"], "Lost block changed the physical noise stream"
                assert lost["summary"]["packet_count"] == 599
            ambiguous = study["ambiguous_witness"]
            assert ambiguous["measured_features_indistinguishable"] and ambiguous["paired_noise_exactly_equal"]
            assert ambiguous["observed_contradiction_count"] > 0
            assert ambiguous["observable_qualification"] == "AMBIGUOUS_FOR_25MM_TARGET_ABSTAIN"
            assert len(list(all_captures(study))) == 45
        else:
            assert len(list(all_captures(study))) == 30


def brief_capture(record):
    brief = {key: value for key, value in record.items() if key not in ("rows", "fit", "score")}
    if "fit" in record:
        brief["fit"] = None if record["fit"] is None else {key: value for key, value in record["fit"].items()
                                                         if key not in ("weights", "mean", "scale")}
    if "score" in record:
        brief["score"] = {key: value for key, value in record["score"].items() if key != "predictions"}
    return brief


def readable_summary(batch):
    studies, all_records, comparisons, refs = [], [], [], []
    for study in batch["studies"]:
        all_records.extend(all_captures(study))
        comparisons.extend(study["comparisons"])
        refs.extend(r["refinement"] for r in study["references"].values())
        ambiguity = study["ambiguous_witness"]
        if ambiguity is not None:
            ambiguity = {key: value for key, value in ambiguity.items() if key not in ("captures", "contradictions")}
            ambiguity["largest_observed_contradiction"] = max(study["ambiguous_witness"]["contradictions"],
                key=lambda row: row["minimum_unavoidable_component_error_m"])
        studies.append({"subject_seed": study["subject_seed"],
            "reference_refinements": {name: reference["refinement"] for name, reference in study["references"].items()},
            "training": [brief_capture(r) for r in study["training"]],
            "captures": [brief_capture(r) for r in study["captures"]], "comparisons": study["comparisons"],
            "fine_grid_captures": [{"capture": brief_capture(row["capture"]), "comparison": row["comparison"]}
                                   for row in study["fine_grid_captures"]],
            "faults": [{"name": row["name"], "captures": [brief_capture(r) for r in row["captures"]],
                        "comparison": row["comparison"]} for row in study["faults"]],
            "ambiguous_witness": ambiguity})
    main_captures = [r for study in batch["studies"] for r in study["captures"]]
    informative = [row for row in comparisons if row["source_mode"] == "informative"]
    feature_failures = [row for row in informative if not row["within_predeclared_feature_allocation"]]
    prediction_failures = [row for row in informative if row["within_predeclared_prediction_allocation"] is False]
    maximum_prediction = max((row["maximum_position_prediction_difference_m"] or 0.) for row in informative)
    aggregate = {"subject_count": len(studies), "capture_count_including_training_controls_and_witnesses": len(all_records),
        "training_capture_count": sum(len(s["training"]) for s in batch["studies"]),
        "main_capture_count": len(main_captures), "main_pair_comparison_count": len(comparisons),
        "independent_reference_grid_pair_count": len(refs),
        "total_acquired_raw_contact_samples": sum(r["summary"]["raw_sample_count"] for r in all_records),
        "informative_main_feature_budget_failure_count": len(feature_failures),
        "informative_main_prediction_budget_failure_count": len(prediction_failures),
        "maximum_informative_main_feature_difference_uv": max(row["maximum_feature_difference_uv"] for row in informative),
        "maximum_informative_common_qualified_feature_difference_uv": max(row["maximum_qualified_feature_difference_uv"] or 0. for row in informative),
        "maximum_informative_position_prediction_difference_m": maximum_prediction,
        "maximum_reference_position_difference_m": max(row["maximum_position_difference_m"] for row in refs),
        "maximum_reference_physical_velocity_difference_m_per_s": max(row["maximum_physical_velocity_difference_m_per_s"] for row in refs),
        "main_changed_packet_qualification_count": sum(row["changed_quality_packets"] for row in comparisons),
        "redundant_absent_control_feature_differences_all_zero": all(row["maximum_feature_difference_uv"] == 0. for row in comparisons if row["source_mode"] != "informative"),
        "dense_active_window_qualified_packets": sum(r["summary"]["qualified_active_window_packets"] for r in main_captures if r["scenario"] == "moving_dense_train"),
        "all_pair_noise_and_observation_schedule_invariants_pass": all(row["identical_actual_noise"] and row["paired_observation_support_pass"] for s in batch["studies"] for row in all_comparisons(s)),
        "source_hold_feature_allocation_qualified": not feature_failures,
        "source_hold_prediction_allocation_qualified": not prediction_failures,
        "decision": "RETAIN_FAILED_HOLD_ALLOCATION; USE_APERTURE_RESOLVED_SOURCE_FOR_NEW_SYNTHETIC_NEURAL_CAPTURES" if feature_failures or prediction_failures else "FINITE_HOLD_ENVELOPE_WITHIN_DECLARED_ALLOCATIONS",
        "scope": "Numeric reference checks and observation-boundary invariants pass. Source approximation failures, dense residual failure, negative information controls and ambiguous mapping remain; this does not establish real spinal observability."}
    return {"schema": "scci_rh.stage3.moving-source-sensitivity-summary.v1", "scope": batch["scope"],
        "source_identity": batch["source_identity"], "specification": batch["specification"],
        "reproduction": batch["reproduction"], "batch_summary": aggregate, "studies": studies}


def read_receipt(path):
    contents = path.read_bytes()
    return json.loads(gzip.decompress(contents) if path.suffix == ".gz" else contents)


def write_receipt(path, data):
    contents = (json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    if path.suffix == ".gz":
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
            stream.write(contents)
        contents = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def validate_position_witness(refinement, path):
    """Check a maximum-error witness against its own aperture and error value."""
    witness = refinement["largest_position_witness"]
    if set(witness) != {"block", "sample", "contact", "component", "time_s",
                        "coarse_position_m", "fine_position_m"}:
        raise AssertionError(f"Malformed position witness at {path}")
    for name, limit in (("block", refinement["actual_contact_aperture_count"]//320),
                        ("sample", 20), ("contact", 16), ("component", 2)):
        index = witness[name]
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < limit:
            raise AssertionError(f"Invalid witness {name} at {path}")
    time = witness["block"]/200 + witness["sample"]/4000 + witness["contact"]*3e-6
    if not np.isclose(witness["time_s"], time, rtol=0., atol=1e-12):
        raise AssertionError(f"Witness aperture differs at {path}")
    positions = [witness["coarse_position_m"], witness["fine_position_m"]]
    maximum = refinement["maximum_position_difference_m"]
    if not np.isfinite([*positions, maximum]).all() or maximum < 0:
        raise AssertionError(f"Nonfinite or negative witness error at {path}")
    if not np.isclose(abs(positions[0]-positions[1]), maximum, rtol=RTOL, atol=ATOL):
        raise AssertionError(f"Witness does not attain maximum at {path}")


@lru_cache(maxsize=12)
def reproduction_reference(subject_seed, scenario, internal_step_s):
    """Frozen study reference; cache repeated raw/summary witness checks only."""
    if scenario not in SCENARIOS or internal_step_s not in REFERENCE_GRIDS:
        raise AssertionError("Witness reference is outside the frozen study design")
    return MovingBodyReference(subject_seed, scenario, internal_step_s)


def validate_study_position_witnesses(study, path):
    """Bind raw and summary witnesses to their own recomputed physical support.

    The near-zero argmax may move, so its positions cannot be compared with
    positions at another aperture. Re-evaluating each aperture prevents a
    self-consistent but physically unrelated position pair from being skipped.
    This is evaluator-only receipt validation, never an observer input.
    """
    if "references" in study:
        refinements = {scenario: reference["refinement"]
                       for scenario, reference in study["references"].items()}
    else:
        refinements = study["reference_refinements"]
    for scenario, refinement in refinements.items():
        location = f"{path}.{scenario}.refinement"
        validate_position_witness(refinement, location)
        witness = refinement["largest_position_witness"]
        for grid, position_field in (("coarse", "coarse_position_m"),
                                     ("fine", "fine_position_m")):
            reference = reproduction_reference(study["subject_seed"], scenario,
                                               refinement[f"{grid}_internal_step_s"])
            position = reference.evaluate(witness["time_s"])[0][witness["component"]]
            if not np.isclose(witness[position_field], position, rtol=RTOL, atol=ATOL):
                raise AssertionError(f"Witness {grid} position differs from its physical aperture at {location}")


def compare(actual, expected, path="root"):
    if isinstance(actual, dict):
        if not isinstance(expected, dict) or actual.keys() != expected.keys():
            raise AssertionError(f"Keys differ at {path}")
        if "subject_seed" in actual and ("references" in actual or "reference_refinements" in actual):
            validate_study_position_witnesses(actual, path)
            validate_study_position_witnesses(expected, path)
        negligible_position_argmax = False
        if "largest_position_witness" in actual:
            validate_position_witness(actual, path)
            validate_position_witness(expected, path)
            negligible_position_argmax = max(actual["maximum_position_difference_m"],
                                             expected["maximum_position_difference_m"]) <= ATOL
        for key in actual:
            if key == "largest_position_witness" and negligible_position_argmax:
                continue
            if key not in ("actual_noise_sha256", "external_noise_sha256", "rhs_evaluations"):
                compare(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, (list, tuple)):
        if not isinstance(expected, (list, tuple)) or len(actual) != len(expected):
            raise AssertionError(f"Sequence differs at {path}")
        if actual and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in actual):
            if not np.allclose(actual, expected, rtol=RTOL, atol=ATOL):
                raise AssertionError(f"Numeric series differs at {path}")
        else:
            for index, (a, b) in enumerate(zip(actual, expected)):
                compare(a, b, f"{path}[{index}]")
    elif isinstance(actual, float):
        if not isinstance(expected, (float, int)) or not np.isclose(actual, expected, rtol=RTOL, atol=ATOL):
            raise AssertionError(f"Numeric value differs at {path}")
    elif actual != expected:
        raise AssertionError(f"Value differs at {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument("--output", type=Path)
    targets.add_argument("--check", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--summary-check", type=Path)
    parser.add_argument("--scope", choices=("full", "smoke"), default="full")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    if args.summary_output and not args.output:
        parser.error("--summary-output requires --output")
    if args.summary_check and not args.check:
        parser.error("--summary-check requires --check")
    expected = read_receipt(args.check) if args.check else None
    if expected is not None:
        if expected["scope"] != args.scope:
            parser.error("--scope must match the saved receipt")
        validate_receipt(expected)
    result = run_batch(args.jobs, args.scope)
    if expected is not None:
        compare(result, expected)
    summary = readable_summary(result)
    if args.summary_check:
        compare(summary, read_receipt(args.summary_check))
    if args.output:
        write_receipt(args.output, result)
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(summary["batch_summary"], indent=2))
    if args.check:
        print(f"Source/aperture receipt reproduced at rtol={RTOL:g}, atol={ATOL:g}; all failed allocations and information controls retained.")


if __name__ == "__main__":
    main()
