"""Render the historical conservative Stage 3 qualification verdict from saved evidence.

Default output remains explicitly DRAFT while the final replay is unavailable.
An explicit replay summary and audit can be supplied only as a pair. Loading them
does not itself close Stage 3; the report always reserves the exit decision for
the independent root review. No source/result/receipt is rewritten by this file.
"""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/SCCI_RH_stage3_closeout.pdf"
INK, BLUE, TEAL, GRAY = "#15293D", "#225B86", "#12756D", "#627485"
WIDTH = 475
DATE = "12 October 2026"
OBSERVER = "experiments/stage3/observed-state-observer/frozen/observer-confirmation-summary-12oct.json"
DEVELOPMENT = "experiments/stage3/observed-state-observer/frozen/observer-development-summary-12oct.json"
HISTORICAL = "results/stage3/isolated-pilot/summary.json"
MONITOR = "electronics/stage4/monitoring-study/results.json"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def saved_evidence() -> tuple[dict, dict, dict, dict]:
    observer = load_json(ROOT / OBSERVER)
    development = load_json(ROOT / DEVELOPMENT)
    historical = load_json(ROOT / HISTORICAL)
    monitor = load_json(ROOT / MONITOR)
    # Fail if these report-specific scope assumptions change. Other studies keep
    # their own full auditors; this is not another scientific receipt writer.
    assert observer["no_dose"] and not observer["observer_private_inputs_used"]
    assert observer["independent_noise_pairs"] == 16 and observer["grid_captures"] == 32
    assert observer["current_supports_per_capture"] == 550 and observer["horizons_per_support"] == 26
    assert observer["coordinate_residuals"] == 915200 and observer["all_declared_coverage_available"]
    assert observer["all_conditions_both_grids_within_budget"]
    assert not observer["authoritative_predictor_or_pilot_changed"]
    assert not observer["neural_increment_assistance_or_retained_learning_tested"]
    assert historical["specification"]["practice_trials"] == 4
    assert historical["total_practice_launched_profiles"] == 0
    assert historical["total_off_launched_profiles"] == 0
    assert not historical["assisted_retained_advantage_established"]
    assert not monitor["four_percent_target_earned"] and len(monitor["runs"]) == 33
    return observer, development, historical, monitor


def replay_inputs(args: argparse.Namespace, observer: dict, development: dict) -> tuple[dict | None, dict | None]:
    if bool(args.pilot_summary) != bool(args.pilot_audit):
        raise ValueError("Supply both --pilot-summary and --pilot-audit, or neither.")
    if not args.pilot_summary:
        return None, None
    summary_path, audit_path = args.pilot_summary.resolve(), args.pilot_audit.resolve()
    require(summary_path.parent == audit_path.parent, "Replay summary and audit must share their package root.")
    require(summary_path.name == "summary.json" and audit_path.name == "audit.json", "Use the frozen package summary.json/audit.json pair.")
    package = summary_path.parent
    summary, audit = load_json(summary_path), load_json(audit_path)
    require(summary.get("schema") == "scci_rh.stage3.frozen-observer-pilot.summary.v1", "Unreviewed replay summary schema.")
    require(audit.get("schema") == "scci_rh.stage3.frozen-observer-pilot.audit.v1", "Unreviewed replay audit schema.")
    manifest = load_json(package / "artifact-manifest.json")
    require(manifest.get("schema") == "scci_rh.stage3.frozen-observer-pilot.artifact-manifest.v1", "Unreviewed package manifest schema.")
    listed = set()
    for item in manifest["files"]:
        name = item["path"]
        path = (package / name).resolve()
        require(path.is_relative_to(package) and name not in listed, "Invalid/duplicate manifest path.")
        require(path.is_file() and path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"],
                f"Replay package bytes changed: {name}")
        listed.add(name)
    require({"summary.json", "audit.json", "preflight.json", "root-review.json"} <= listed, "Missing replay identity bindings.")
    require(summary["preflight_sha256"] == sha256(package / "preflight.json"), "Replay preflight hash mismatch.")
    require(summary["review_sha256"] == sha256(package / "root-review.json"), "Replay pre-generation review hash mismatch.")
    pre_generation = load_json(package / "root-review.json")
    require(pre_generation["authorized"] is True and pre_generation["preflight_sha256"] == summary["preflight_sha256"],
            "Replay pre-generation review is not bound to its preflight.")
    expected_counts = {"practice_trials": 32, "off_assessments": 64, "total_launched_profiles": 0,
        "total_off_launched_profiles": 0, "frozen_vectors": 32, "frozen_targets": 832,
        "current_diagnostics": 32, "future_guard_targets": 800, "warmup_guard_targets": 800,
        "guard_checks": 1600, "guard_failures": 0, "current_diagnostic_failures": 0, "distinct_noise_arrays": 12}
    for key, expected in expected_counts.items():
        require(summary[key] == expected, f"Changed finite replay scope/outcome: {key}")
    for key in ("all_observers_sealed", "all_updates_causal", "matched_arms_identical"):
        require(summary[key] is True, f"Replay contract failed: {key}")
    for key in ("retained_advantage_established", "expert_transfer_established", "learner_spinal_neural_increment_established",
                "active_delivery_path_implemented", "actual_monitoring_exercised", "stage3_completion_decided_here"):
        require(summary[key] is False, f"Unreviewed active/efficacy scope: {key}")
    context = summary["baseline_context"]
    require(context == load_json(package / "preflight.json")["baseline_context"], "Admission context differs from approved preflight.")
    require(context["qualified"] is True and context["action_prefix"] == [] and
            context["temporal_holdout_used_for_admission"] is False and context["private_family_selector"] is False,
            "Changed no-dose admission domain.")
    require(context["support_start_s"] == .1 and context["support_end_s"] == 2.845 and context["sample_s"] == .005,
            "Changed finite admission supports.")
    require(context["instruction_hz"] == 1.0 and context["task_time_offset_s"] == 0.0, "Changed known cue domain.")
    require(len(context["horizons_s"]) == 26 and len(context["allocation_m"]) == 26, "Incomplete horizon vector.")
    expected_allocations = [max(a, b) for a, b in zip(
        [max(row["allocation_by_horizon_m"][h] for row in development["development"]) for h in range(26)],
        observer["aggregate_allocation_by_horizon_m"])]
    for h, (horizon, actual, expected) in enumerate(zip(context["horizons_s"], context["allocation_m"], expected_allocations)):
        require(math.isclose(horizon, .025 + .005*h, abs_tol=1e-12), "Changed execution horizon.")
        require(math.isfinite(actual) and actual <= .015 and math.isclose(actual, expected, rel_tol=2e-8, abs_tol=1e-11),
                "Admission allocation differs from development/confirmation evidence.")
    require(math.isclose(summary["maximum_allocation_m"], max(expected_allocations), rel_tol=2e-8, abs_tol=1e-11),
            "Wrong maximum admission allocation.")
    expected_audit = {"saved_records": 8, "sessions": 96, "sanitized_measurements_checked": 57600,
        "controller_replays": 32, "frozen_target_predictions_checked": 1664, "actual_noise_arrays_checked": 12}
    for key, expected in expected_audit.items():
        require(audit[key] == expected, f"Changed saved audit scope: {key}")
    for key in ("all_predeclared_sessions_present", "all_outcomes_retained", "source_input_freeze_verified"):
        require(audit[key] is True, f"Saved audit failed: {key}")
    require(audit["negative_controls"]["passed"] == 15 and audit["negative_controls"]["failed"] == 0,
            "Software contract probes failed or changed scope.")
    require(summary["tested_candidate_failed_gate_counts"] == {
        "independent_actual_response_domain_qualified": 192, "learning_interaction_qualified": 192,
        "whole_vector_correction_interval_within25mm": 192, "policy_enabled": 48}, "Changed candidate gate findings.")
    require(summary["grid_differences"]["launch_decisions_changed"] == 0, "Grid changed launch outcome.")
    return summary, audit


def exit_review(args: argparse.Namespace, replay: dict | None) -> dict | None:
    if not args.exit_review:
        return None
    require(replay is not None, "An exit review requires the explicit frozen replay summary/audit pair.")
    review = load_json(args.exit_review)
    require(review.get("schema") == "scci_rh.stage3.closeout-review.v1", "Unreviewed exit-review schema.")
    require(review.get("decision") == "COMPLETE_WITHIN_SELECTED_DIGITAL_SCOPE", "Exit review does not authorize finite completion.")
    require(review.get("date") == "2026-10-12" and bool(review.get("reviewer")), "Missing explicit exit reviewer/date.")
    for key, path in [("reviewed_replay_summary_sha256", args.pilot_summary),
                      ("reviewed_replay_audit_sha256", args.pilot_audit),
                      ("package_manifest_sha256", args.pilot_summary.parent / "artifact-manifest.json")]:
        require(review.get(key) == sha256(path), f"Exit review is not bound to current {key}.")
    digest = review.get("independent_saved_data_review_sha256", "")
    require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "Missing independent saved-data review identity.")
    require(digest == sha256(ROOT / "docs/stage3/frozen-observer-pilot-independent-review.md"),
            "Independent saved-data review bytes differ from the exit decision.")
    for key, path in [("independent_audit_receipt_sha256", ROOT / "provenance/stage3-frozen-pilot-independent-audit.json"),
                      ("independent_auditor_sha256", ROOT / "scripts/audit_frozen_observer_pilot.py")]:
        require(review.get(key) == sha256(path), f"Independent audit identity differs: {key}")
    require(review.get("full_same_cohort_reproduction_passed") is True and
            review.get("source_and_original_evidence_unchanged") is True, "Exit decision lacks completed reproduction/source review.")
    require(review.get("active_delivery_implemented") is False and
            review.get("actual_monitoring_newly_validated") is False and
            review.get("retained_advantage_established") is False, "Exit decision overstates active/efficacy scope.")
    return review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--pilot-summary", type=Path)
    parser.add_argument("--pilot-audit", type=Path)
    parser.add_argument("--exit-review", type=Path, help="Explicit source-bound root decision; never inferred from file presence.")
    args = parser.parse_args()
    observer, development, historical, monitor = saved_evidence()
    replay, audit = replay_inputs(args, observer, development)
    review = exit_review(args, replay)
    pending = replay is None
    status = ("DRAFT / NEW REPLAY AND EXIT REVIEW PENDING" if pending else
              "CONSERVATIVE QUALIFICATION STUDY COMPLETE" if review else "EVIDENCE REPORT / ROOT EXIT REVIEW PENDING")

    font = Path(matplotlib.get_data_path()) / "fonts/ttf"
    for name, file in [("SCCIRH3C", "DejaVuSans.ttf"), ("SCCIRH3CBold", "DejaVuSans-Bold.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(font / file)))
    pdfmetrics.registerFontFamily("SCCIRH3C", normal="SCCIRH3C", bold="SCCIRH3CBold", italic="SCCIRH3C", boldItalic="SCCIRH3CBold")
    body = ParagraphStyle("body", fontName="SCCIRH3C", fontSize=9.3, leading=13.6,
                          textColor=colors.HexColor(INK), spaceAfter=8)
    heading = ParagraphStyle("heading", parent=body, fontName="SCCIRH3CBold", fontSize=22, leading=27, spaceAfter=15)
    sub = ParagraphStyle("sub", parent=body, fontName="SCCIRH3CBold", fontSize=11.3, leading=16, spaceBefore=7)
    small = ParagraphStyle("small", parent=body, fontSize=7.8, leading=11.1, spaceAfter=6)
    label = ParagraphStyle("label", parent=small, fontName="SCCIRH3CBold", textColor=colors.HexColor(TEAL))
    story = []

    def p(text: str, style=body) -> None:
        story.append(Paragraph(text, style))

    def h(text: str) -> None:
        p(text, heading)

    def page() -> None:
        story.append(PageBreak())

    def image(path: str, width: float = WIDTH, max_height: float | None = None) -> None:
        with PILImage.open(ROOT / path) as im:
            w, height = im.size
        drawn_height = width * height / w
        if max_height is not None and drawn_height > max_height:
            width *= max_height / drawn_height
            drawn_height = max_height
        story.append(Image(str(ROOT / path), width=width, height=drawn_height, hAlign="LEFT"))
        story.append(Spacer(1, 9))

    def table(rows: list[list[str]], widths: list[int]) -> None:
        tab = Table([[Paragraph(str(cell), small) for cell in row] for row in rows],
                    colWidths=widths, repeatRows=1, hAlign="LEFT")
        tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF0F5")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F9FB")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(tab)
        story.append(Spacer(1, 9))

    # Page 1: full project and evidence level.
    p("PROJECT SCCI RH / CONSERVATIVE STAGE 3 QUALIFICATION VERDICT", label)
    h("From a future spinal interface\nto a bounded design conclusion")
    p("Expert-informed motor practice and target-specific physiological feedback", sub)
    p(f"Pratham / Project SCCI RH / {DATE}", small)
    p(status, label)
    image("docs/stage1/figures/full-system.png", max_height=260)
    p("<b>Abstract.</b> Project SCCI RH proposes implanted spinal recording, computational interpretation, "
      "learner-specific stimulation and independently observed feedback. Stage 3 tests the intervening "
      "digital mechanisms, information limits, numerical sensitivity and qualification rules. The historical "
      "motor pilot withholds every pulse. A separately frozen causal no-dose observer now passes a finite "
      "external-position forecast allocation. Actual delivery uncertainty and learning-response interaction "
      "remain independent limits on nonzero practice. The pressure model supports conditional pressor "
      "feedback and exposes fault/recovery tradeoffs.")
    if pending:
        p("<b>Draft boundary.</b> The new one-practice actual-electrical replay and independent saved-data audit "
          "are not loaded. This report reserves their outcome and the finite Stage 3 exit decision; it does not "
          "declare a completed implant or a demonstrated consumer capability.")
    else:
        p("<b>Connected result.</b> The new actual-domain replay preserves 32 one-practice trials and 64 "
          "hard-OFF assessments, with zero launched profiles. The saved-data audit checks all 96 sessions "
          "and replays all 32 controllers. Nonzero delivery is not implemented in this replay: unexpected "
          "authorization records its prefix and halts before delivery.")
        p(("<b>Finite scope.</b> The explicit source-bound root review closes this conservative qualification "
           "study. Full native electronics, firmware, populated CAD and biological efficacy remain pending.")
          if review else
          ("<b>Exit review pending.</b> This evidence report does not itself close Stage 3 or declare a "
           "completed implant or demonstrated consumer capability."), small)
    p("<b>Scope clarification, 13 October.</b> Future concept design continues under explicit, defensible "
      "undemonstrated assumptions. This historical negative result does not establish future SCCI "
      "impossibility or complete the conditional concept investigation.", small)
    p("All observations here are generated by declared artificial source/body/electrical models. No new "
      "human, animal or physical-device experiment is reported. AstroSam / Mind-Link inspires the progression "
      "from future vision to inspectable engineering; complete native electronics, firmware and populated "
      "CAD remain later work.", small)
    page()

    # Page 2: integrated claim ledger.
    h("01 / Preserve the mechanism and its limits")
    p("The future consumer mechanism begins with a specific task or physiological endpoint. Recorded "
      "spinal information would have to be informative, causal and distinguishable from artifacts; "
      "personalized stimulation would have to act selectively within observed dose/response bounds. "
      "Feedback tests whether the intended response actually occurred.")
    table([
        ["Question", "Digital evidence", "Boundary retained"],
        ["Expert-informed motor learning", "Competent nominal synthetic teacher references; learner forecasts; independent response maps and OFF comparisons.", "No expert voltage replay, human learning multiplier or retained assisted benefit is established."],
        ["Spinal information value", "Capacity-matched external controls, absent/redundant fields, moving contact apertures and ambiguity witnesses.", "No consistent neural advantage or connected live learner spinal increment is established."],
        ["Causal no-dose prediction", "Frozen measured-data observer and fresh sensor-noise confirmation within 15 mm.", "External positions, known cue, persistent prefix and synthetic structural prior; no active correction qualification."],
        ["Actual motor intervention", "Whole-profile electrical adapter, finite response domains and explicit uncertainty rejection.", "Actual dose domains reject; learning-enabled response interaction is unqualified."],
        ["Physiological automation", "Conditional external-pressure feedback, positive pressor authority and fault fallbacks.", "No generic autonomic control, spinal pressure decoder or healthy-user efficacy."],
    ], [115, 185, 175])
    p("Assistance and retained learning are different endpoints", sub)
    p("A future expert reference informs a learner-specific policy after separate competence and fidelity "
      "checks. The learner must retain a measurable benefit during truly stimulation-OFF assessment. "
      "Matched practice exposure, resources and adverse/zero/dependent plasticity controls prevent a "
      "temporary assisted movement from being reported as acquired skill.")
    p("The original 28-page paper remains a research/hypothesis map. Primary experiments support selected "
      "links, not the entire expert-recording-to-retained-benefit conjunction. Original and faster teacher "
      "references that fail remain unavailable. The expert-neural arm is an offline expert representation, "
      "not qualified live learner spinal sensing.", small)
    page()

    # Page 3: the revised baseline with declared extra resources.
    h("02 / One frozen no-dose observer")
    image("experiments/stage3/observed-state-observer/observer-confirmation.png", max_height=265)
    p("<b>Figure 1.</b> Saved horizon allocations from development, temporal holdout and independently "
      "predeclared fresh sensor-noise confirmation. An allocation is maximum observed coordinate residual "
      "plus the unchanged 3 mm label allowance. Covariance is not this empirical bound.", small)
    table([
        ["Evidence group", "Complete captures passing", "Largest allocation"],
        ["Previously inspected drift development", "16 / 16", f"{1000*development['maximum_development_allocation_m']:.6f} mm"],
        ["Temporal calibration holdout", "8 / 8", f"{1000*development['maximum_temporal_calibration_holdout_allocation_m']:.6f} mm"],
        ["Fresh noise confirmation, both grids", "32 / 32", f"{1000*observer['maximum_aggregate_allocation_m']:.6f} mm / 15 mm"],
    ], [235, 120, 120])
    p("The ten-state observer uses measured external positions, known instructions and a declared 60 ms "
      "synthetic movement prior. Calibration supplies 64 s fit exposure and 32 s temporal holdout. Private "
      "family, scale, gain, theta and future achieved motion do not select runtime parameters. State "
      "summarizes the whole accepted trial prefix, which exceeds the old stateless 75 ms history.")
    p("Confirmation retains all 550 supports and all 26 horizons for every capture: 915,200 residuals. "
      "Independence is sensor noise within the same synthetic subject and finite laws, not new-subject "
      "or biological validation. Four family names reduce to two no-dose laws. Paired 2.5/1.25 ms grids "
      "differ by at most 5.285 micrometers in residuals, with no changed budget decisions.")
    p("<b>Resources.</b> Ten state means, 55 unique covariance entries and 101 learned prior/drift entries; "
      "the maximum deterministic cache payload is 1,638,400 bytes, exceeding the 512 KB target RAM. "
      "This desktop result has no dose, no 25 mm combined-correction test and no MCU-ready claim.", small)
    page()

    # Page 4: finite integration from the explicit frozen summary/audit pair.
    h("03 / The connected replay remains explicit")
    p("The historical four-practice pilot remains unchanged: its common changing-learner forecast context "
      "fails the 15 mm gate, all 128 practice trials withhold stimulation, and all 64 OFF assessments "
      "remain pulse-free. It demonstrates no delivered assistance or retained advantage. The new observer "
      "component does not retroactively repair that result.")
    p("The new protocol has <b>one practice trial</b> per matched arm/family/grid in the actual "
      "electrical domain. This exposure is distinct from the historical four-trial protocol. A genuine "
      "pre-dose vector avoids assimilating stimulated total motion as voluntary state.")
    if pending:
        table([
            ["Clock / physical support", "Frozen causal contract"],
            ["Decision 0.975 s / latest support 0.950 s", "Freeze 26 targets, 0.975-1.100 s, then seal the observer. No update or replacement candidate."],
            ["Launch opportunity 1.000 s", "Process available pre-launch checks first. Spend or irrevocably withhold one whole-frame permit."],
            ["Forecast boundary 1.100 s", "No new total-position authority afterward. Missing targets expire; an empty queue does not rearm."],
            ["Response window boundary 1.600 s", "No qualified release beyond 600 ms. Response becomes unavailable, not silently zero."],
        ], [165, 310])
        p("NEW REPLAY: NOT LOADED / ROOT EXIT REVIEW PENDING", label)
        p("Supply the explicit frozen summary/audit pair to render complete practice/OFF counts, candidate "
          "rejection reasons, coverage, freeze/clock witnesses, paired-grid differences and OFF comparisons.")
    else:
        table([
            ["Saved evidence", "Complete count / outcome"],
            ["Practice / hard-OFF assessment", f"{replay['practice_trials']} practice + {replay['off_assessments']} OFF; zero launched profiles in both."],
            ["Final frozen vector", f"{replay['frozen_vectors']} sealed vectors; {replay['frozen_targets']} targets, including {replay['current_diagnostics']} equal-time diagnostics and {replay['future_guard_targets']} strictly future targets."],
            ["Independent delayed guards", f"{replay['guard_checks']} checks: 800 warmup + 800 final future targets. Zero guard/current-diagnostic failures."],
            ["Shared baseline admission", f"{1000*replay['maximum_allocation_m']:.6f} mm maximum / 15 mm; development + fresh confirmation. Temporal holdout grants no startup authority."],
            ["Six independently tested route patterns", "192 candidate evaluations all fail actual response-domain, learning-interaction and whole-vector 25 mm gates. These are overlapping vetoes."],
        ], [155, 320])
        p("At 0.975 s, after supports through 0.950 s, freeze all 26 targets through 1.100 s and seal. "
          "At 1.000 s, process the delayed equal-time pre-dose diagnostic before irrevocable one-shot "
          "withholding. All updates are causal; matched arm trajectories and OFF metrics are identical.")
        grid = replay["grid_differences"]
        p(f"Paired grids differ by at most {1e6*grid['maximum_position_difference_m']:.6f} micrometers in position, "
          f"{1e6*grid['maximum_frozen_forecast_difference_m']:.6f} in frozen forecasts and "
          f"{1e6*grid['maximum_trajectory_rmse_difference_m']:.6f} in trajectory RMSE; no launch decision changes. "
          "Twelve distinct fresh noise arrays are matched across arms/grids. The independent audit retains "
          "all 96 sessions and 15 passing software contract probes.", small)
        retention = [1000*row["retention_off"]["trajectory_rmse_m"] for row in replay["arms"]]
        transfer = [1000*row["transfer_off"]["trajectory_rmse_m"] for row in replay["arms"]]
        p(f"OFF trajectory RMSE spans {min(retention):.6f}-{max(retention):.6f} mm at the same cadence and "
          f"{min(transfer):.6f}-{max(transfer):.6f} mm at the faster transfer cadence. All four arms are equal "
          "within each matched case; no retained advantage is established. Kinematic peak proxies do not "
          "model force/contact mechanics.", small)
    p("No active delivery path is implemented here: unexpected nonzero authorization persists its "
      "decision/prefix and halts before delivery. The all-withheld replay verifies freezing, clocks, "
      "guards, withholding and hard-OFF behavior; it supplies no new nonzero delivery, post-dose "
      "monitoring/cancellation or repeated-intervention evidence. Equal OFF outcomes after no "
      "intervention do not disprove the human learning hypothesis.", small)
    page()

    # Page 5: independent limits that a baseline pass cannot hide.
    h("04 / A prediction pass is not pulse authority")
    p("The baseline allocation stays at 15 mm, including the 3 mm label allowance; the complete correction "
      "gate stays at 25 mm. Live gain and dose intervals retain their full product, including the cross term.")
    p("<b>Response uncertainty:</b> u<sub>G</sub>|d| + |G|u<sub>d</sub> + u<sub>G</sub>u<sub>d</sub>", sub)
    p("Add the independently observed residual at the exact physical response support and any qualified "
      "learning-interaction allowance. Expert-reference uncertainty belongs in correction against the "
      "reference; adding it to a prediction-of-actual-position residual would conceal response failure.")
    table([
        ["Independent block", "Current evidence", "Required consequence"],
        ["Actual delivery interval", "Measured fraction 1.01318359375 with uncertainty 0.4411205888605442: about 44.1% of nominal phase charge.", "Every inherited actual isolated response domain rejects. Future 7.4% and 4% intervals remain assumptions."],
        ["Learning-response interaction", "Inherited pulse calibration and validation used learning=False.", "Nonzero learning-enabled actions require independently observed interaction coverage, or remain unavailable."],
        ["Runtime scope", "No-dose qualification covers finite physical supports, cue/resources and an empty past-action prefix.", "A context name cannot authorize later supports, changed action histories or arbitrary learner states."],
        ["Post-launch evidence", "An actual completed monitor and delayed total-position residual arrive after the choice.", "Keep commitments immutable; invalid/missing evidence latches a fault. Cancellation cannot undo a pulse."],
    ], [110, 185, 180])
    p("The observer's no-dose structural prior is not a learned biological response law. After stimulation, "
      "a future multi-action system would need causal whole-prefix response correction with uncertainty "
      "or another independently qualified state model. A one-shot freeze avoids contamination for this "
      "finite experiment; it does not establish repeated active practice.")
    p("The integration is allowed to end with an unavailable active mechanism. An honest negative exit "
      "preserves the architecture and yields a concrete redesign contract without searching indefinitely "
      "for a favorable result.", small)
    page()

    # Page 6: second original application, with conditional biology explicit.
    h("05 / Physiological feedback remains central")
    image("docs/stage3/figures/pressure-comparisons.png", max_height=290)
    p("<b>Figure 2.</b> Preserved conditional pressure studies. Disturbance improvement can coexist with "
      "delayed recovery overshoot; fault behavior is part of the outcome. These traces use external "
      "pressure feedback and the declared reduced pressor/dose model.", small)
    p("A future user-specific physiological mode would select a function and accessible pathway, measure "
      "its state, identify permitted response directions, and update stimulation from observed feedback. "
      "The implemented example concerns pressure support after spinal cord injury through a positive pressor effect. It grants "
      "neither active pressure lowering nor universal control of involuntary functions.")
    p("OFF and feedback modes face disturbances, delay, altered gain, sensor loss and invalid or stale data. "
      "A privileged diagnostic oracle is excluded from benefit claims. Stop, finite-hold and ramp fallbacks expose the tradeoff between unsupported "
      "delivery and loss of support. Whole reference-train frames are admitted; fractional catch-up "
      "pulses are not invented.")
    p("Pressure refinements retain 408 runs in 136 noise-matched groups, including 24 frame-sensitive "
      "comparisons. The transduction uses an averaged monitored pulse-dose reduction and assumed "
      "recruitment. Continuous routing, analog guard behavior, real tissue response and target-specific "
      "biology remain future evidence. Dense stimulation removes qualified continuous neural recording, "
      "so the branch explicitly uses external pressure rather than inventing a neural pressure value.", small)
    page()

    # Page 7: detailed-design handoff and current actual native state.
    h("06 / The electronics and CAD handoff")
    table([
        ["Responsibility", "Concrete detailed-design requirement"],
        ["Spinal acquisition", "16 streams at 4 kHz; native differential/filter/ADC circuitry, noise/range, actual aperture/availability clocks and analog artifact recovery."],
        ["Two-source stimulation", "Actual current drivers, HV polarity/contact routing, simultaneous ownership, whole-profile timing and independent shutdown."],
        ["Observed dose", "Cathodic/anodic phases, net charge and recovery tails; bias/leakage, gain/offset, window/settling and interrupted-dose intervals."],
        ["Embedded control", "Finite support/action domains, live uncertainty, cancellation/expiry, missing-evidence rejection, pending-response and reset/washout contracts."],
        ["Resources and package", "Revised actual component power, heat, buses, memory and worst-case schedules; populate native CAD from matched boards/components/package/lead interfaces."],
    ], [135, 340])
    p("The first native monitoring cell has <b>70 components, 245 independently checked pin assignments, "
      "three editable sheets and zero ERC violations</b>. Its separate behavioral study contains 33 runs "
      "and 462 phase/gap/tail/net intervals, with independent KCL and matrix-exponential checks. This "
      "is a concrete partial subsystem, not the completed invasive interface.")
    p("The proposed 4% phase-charge target is unearned. The model has no shutdown actuator; bias bypass, "
      "ADC protection/settling, current-driver loops and wider waveform/load/rail behavior remain open. "
      "Two INA241 channels alone allocate 32 mW at maximum specified quiescent current, exceeding the "
      "earlier 20 mW sensing allocation. Actual system power must be revised.")
    p("The production OPA391DCKR pin mapping is corrected; its nominal SC-70 footprint still needs PCB "
      "process/land-pattern review. The restricted 24 V / 3 mA / 200 microsecond driver boundary is a "
      "reviewed proposal, with native implementation pending. A linked processor SDK example is "
      "toolchain evidence; complete SCCI_RH firmware is pending.")
    p("Stage 2 allocation solids and illustrative ports are not populated implant CAD. Stage 5 requires "
      "actual boards/components, parametric assemblies, dimensions, STEP/STL and nominal fit checks. "
      "The final integrated manuscript and reproducible private release remain later work.", small)
    page()

    # Page 8: finite exit and exact evidence identity without an efficacy claim.
    h("07 / A finite verdict, not an efficacy claim")
    p("This conservative qualification study ends with an independently audited conclusion and "
      "a concrete hardware/software contract. A favorable learning result and resolution of all biological "
      "unknowns are not conditions to invent. A verified all-withheld replay is an acceptable negative "
      "exit; further model revisions become separately justified extensions.")
    p("CURRENT VERDICT: " + status, label)
    table([
        ["Supported now", "Conditional or unestablished"],
        ["Specified full architecture; finite synthetic acquisition/information/response studies; a frozen external no-dose forecast confirmation; conditional pressure feedback; an inspectable native monitor slice.", "Useful live spinal increment, qualified nonzero learning-enabled correction, retained assistance-OFF benefit, human skill acceleration, universal body automation, full native electronics/firmware or populated implant CAD."],
    ], [237, 238])
    p("Future positive claims would require independent informative spinal measurements, selective and "
      "reliable stimulation, observed response/interaction coverage, matched delivered practice and "
      "pulse-free retained benefit. New evidence can narrow or overturn a specific claim without "
      "erasing the project's inspectable engineering contribution.")
    if review:
        p("The explicit review is by the root AI engineering agent with a separate AI source/raw audit; "
          "it is not human, institutional or clinical approval. The separate auditor recomputes raw "
          "residuals, clocks, noise and all 192 tested candidate intervals without running the producer "
          "or controller. Its largest candidate correction allowance is 45.688604 mm against 25 mm.", small)
    p("Evidence and reproducibility entry points", sub)
    entries = [
        ("docs/stage3/stage3-verdict.md", "Full verdict and remaining decision fields"),
        ("docs/stage3/observer-integration-plan.md", "Reviewed one-shot clocks, scope and nonzero blocks"),
        ("docs/stage3/mechanism-to-electronics-handoff.md", "Concrete detailed-design requirements"),
        ("experiments/stage3/observed-state-observer/verify_study.py", "Frozen checks/audits; optional deterministic reproduction"),
        ("experiments/stage3/frozen-observer-pilot/verify_study.py", "96-session audit; 32 controller replays; same-cohort reproduction"),
    ]
    for path, purpose in entries:
        p(f"<b>{escape(path)}</b><br/>{escape(purpose)}", small)
    p("Saved numerical input identity (SHA256 prefixes)", sub)
    sources = [("Observer confirmation", ROOT/OBSERVER), ("Observer development", ROOT/DEVELOPMENT),
               ("Historical four-trial pilot", ROOT/HISTORICAL), ("Circuit behavioral model", ROOT/MONITOR)]
    if replay:
        sources += [("New frozen replay summary", args.pilot_summary), ("New replay audit", args.pilot_audit)]
    if review:
        sources += [("Explicit root exit review", args.exit_review)]
    for name, path in sources:
        p(f"{escape(name)}: {sha256(path)[:24]}", small)
    p("This renderer reads saved evidence and does not run or rewrite experiments. The individual "
      "package manifests and auditors remain the complete provenance authority. Rendered figures are "
      "preserved from reviewed study packages. Pratham defines the ambition and scope; Codex/ChatGPT "
      "assists research, modelling, implementation, review and writing. Contributions are recorded in "
      "provenance/CONTRIBUTIONS.md. Video and website work remain parked.", small)

    def footer(canvas: Canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E3EB"))
        canvas.line(60, 43, 535, 43)
        canvas.setFont("SCCIRH3C", 7.2)
        canvas.setFillColor(colors.HexColor(GRAY))
        footer_status = "DIGITAL STUDY COMPLETE" if review else "EXIT REVIEW PENDING"
        canvas.drawString(60, 28, "PROJECT SCCI RH / CONSERVATIVE QUALIFICATION / " + footer_status)
        canvas.drawRightString(535, 28, f"{doc.page} / 8")
        canvas.restoreState()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(args.output), pagesize=(595.28, 841.89),
        leftMargin=60, rightMargin=60, topMargin=49, bottomMargin=58,
        title="Project SCCI RH - conservative Stage 3 qualification verdict" + ("" if review else " (exit review pending)"), author="Project SCCI RH / Pratham",
        invariant=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=partial(Canvas, invariant=1))
    print(json.dumps({"path": relative(args.output), "sha256": sha256(args.output),
                      "status": status, "replay_summary_loaded": replay is not None,
                      "replay_audit_loaded": audit is not None, "stage3_exit_review": "complete_within_selected_digital_scope" if review else "pending"}))


if __name__ == "__main__":
    main()
