"""Reproduce finite fixed-profile motor response applicability and failures."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
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
from scci_rh.stage3.response_validation import DomainSpec, run_response_study  # noqa: E402

SOURCE_PATHS = ("src/scci_rh/stage3/response_validation.py", "src/scci_rh/stage3/motor.py",
                "src/scci_rh/stage3/acquisition.py", "src/scci_rh/stage3/electrical.py",
                "src/scci_rh/stage3/external_history.py", "scripts/stage3_response_validation.py")
RTOL, ATOL = 2e-8, 1e-11
BRANCHES = ("conditional_fast_assumed_delivery", "actual_nominal_delivery")
VARIANTS = ("nominal", "no_authority", "cross_route_adverse")


def source_identity():
    return {path: hashlib.sha256((ROOT / path).read_text(encoding="utf-8").replace(
        "\r\n", "\n").encode("utf-8")).hexdigest() for path in SOURCE_PATHS}


def run_case(task):
    branch, variant, seed = task
    print(f"Response applicability: {branch} / {variant} / seed{seed}", flush=True)
    return run_response_study(seed, branch, variant)


def run_batch(jobs=1, scope="full"):
    initial_sources = source_identity()
    tasks = [(branch, variant, seed) for branch in BRANCHES for variant in VARIANTS for seed in range(4)]
    if scope == "smoke":
        tasks = [(branch, "nominal", 0) for branch in BRANCHES]
    if jobs == 1:
        studies = [run_case(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context("spawn")) as pool:
            studies = list(pool.map(run_case, tasks))
    if source_identity() != initial_sources:
        raise AssertionError("Model source changed during the response-domain experiment")
    return {"schema": "scci_rh.stage3.response-domain-batch.v1", "scope": scope,
            "source_identity": initial_sources,
            "specification": {"fixed_profile": "3mA,200us/phase,24V,40Hz; whole-frame density selection",
                              "densities": [.25, .5, 1.], "seeds": list(range(4)) if scope == "full" else [0],
                              "branches": list(BRANCHES), "biological_variants": list(VARIANTS),
                              "correction_budget_m": DomainSpec().correction_budget_m,
                              "empirical_joint_coverage_floor": DomainSpec().heldout_joint_coverage_floor,
                              "frozen_before_outcomes": True,
                              "interval_scope": "recording-specific empirical residual extrema plus propagated engineering allowances; no guaranteed population coverage",
                              "fit_inputs": ["observed external positions", "physical support/availability", "declared whole-frame commands", "independent qualified/conditionally assumed monitor charge and uncertainty"],
                              "forbidden_fit_inputs": ["actual charge", "latent recruitment threshold", "hidden response matrix", "future positions", "changed-context hidden parameters"],
                              "scope_limits": ["Resting fixed-profile kinematic probes, not dynamic assisted practice or anatomical recruitment validation.",
                                               "No current or phase-width generalization, learning-rate multiplier, human efficacy or live monitor-transport qualification."]},
            "reproduction": {"rtol": RTOL, "atol": ATOL,
                             "noise_policy": "Fixed independent capture IDs per training/envelope/heldout; subject draw shared within a seed. Numerical reconstruction compares all raw witnesses."},
            "studies": studies}


def readable_summary(batch):
    studies = []
    for study in batch["studies"]:
        cases = []
        for case in study["validations"]:
            envelope = {key: value for key, value in case["envelope"].items() if key != "residual_witnesses"}
            assessments = {key: {name: value for name, value in case[key].items() if name != "residual_witnesses"}
                           for key in ("heldout_nominal", "heldout_changed_context")}
            cases.append({"pattern": case["pattern"], "density": case["density"],
                          "envelope": envelope, **assessments})
        studies.append({"seed": study["metadata"]["seed"], "branch": study["metadata"]["branch"],
                        "biological_variant": study["metadata"]["biological_variant"],
                        "existing_calibration_map": study["existing_calibration_anchor"]["response_map"],
                        "observed_four_route_map": study["response_map"],
                        "summary": study["summary"], "finite_cases": cases})
    return {"schema": "scci_rh.stage3.response-domain-summary.v1", "scope": batch["scope"],
            "source_identity": batch["source_identity"], "specification": batch["specification"],
            "reproduction": batch["reproduction"],
            "batch_summary": {
                "study_count": len(studies), "finite_cases_per_study": 18,
                "heldout_nominal_case_count": len(studies) * 18,
                "heldout_changed_context_case_count": len(studies) * 18,
                "nominal_applicable_case_count": sum(s["summary"]["nominal_applicable_cases"] for s in studies),
                "changed_context_applicable_case_count": sum(s["summary"]["changed_context_applicable_cases"] for s in studies),
                "actual_delivery_qualified_map_count": sum(s["observed_four_route_map"]["qualified"]
                    for s in studies if s["branch"] == "actual_nominal_delivery"),
                "null_or_adverse_qualified_map_count": sum(s["observed_four_route_map"]["qualified"]
                    for s in studies if s["biological_variant"] != "nominal")},
            "studies": studies}


def read_receipt(path):
    contents = path.read_bytes()
    if path.suffix == ".gz":
        contents = gzip.decompress(contents)
    return json.loads(contents.decode("utf-8"))


def write_receipt(path, data):
    contents = (json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    if path.suffix == ".gz":
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
            stream.write(contents)
        contents = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def compare(actual, expected, path="root"):
    if isinstance(actual, dict):
        if not isinstance(expected, dict) or actual.keys() != expected.keys():
            raise AssertionError(f"Keys differ at {path}")
        for key in actual:
            compare(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, (list, tuple)):
        if not isinstance(expected, (list, tuple)) or len(actual) != len(expected):
            raise AssertionError(f"Sequence differs at {path}")
        if actual and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in actual):
            if not np.allclose(actual, expected, rtol=RTOL, atol=ATOL):
                raise AssertionError(f"Numeric series differs at {path}")
        else:
            for i, (a, b) in enumerate(zip(actual, expected)):
                compare(a, b, f"{path}[{i}]")
    elif isinstance(actual, float):
        if not isinstance(expected, (int, float)) or not np.isclose(actual, expected, rtol=RTOL, atol=ATOL):
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
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args()
    if args.summary_output and not args.output:
        parser.error("--summary-output requires --output")
    if args.summary_check and not args.check:
        parser.error("--summary-check requires --check")
    expected = read_receipt(args.check) if args.check else None
    if expected is not None and expected["scope"] != args.scope:
        parser.error("--scope must match the saved receipt")
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
        print(f"Response-domain receipt reproduced at rtol={RTOL:g}, atol={ATOL:g}; conditional/negative findings retained.")


if __name__ == "__main__":
    main()
