# Stage 3: computational mechanism studies

**Complete within selected digital scope, 13 October 2026.** The conservative
qualification investigation and conditional concept v1 have separate outcomes.
The [conditional mechanism](conditional-concept.md) is the current design baseline;
its assumptions need not already be experimentally demonstrated. The historical implementation connects synthetic
spinal contact observations, causal interpretation, learner calibration, expert
representations, pulse delivery and modeled task response. Both motor learning
and selected physiological feedback remain central to Project SCCI RH.

This package is separate from the historical release1.0 models. It does not report
human recordings, human learning, a populated implant circuit or physical CAD fit.
The [Stage2 architecture](../stage2/README.md) remains the design baseline. Native
complete electronics and populated engineering CAD follow the mechanism work.

| Read or reproduce | Purpose |
|---|---|
| [Conditional concept v1](conditional-concept.md) / [15-entry premise ledger](conditional-concept/assumption-ledger.csv) / [design handoff](conditional-concept/engineering-handoff.md) | Evidence-grounded future architecture, explicit undemonstrated assumptions and finite completion boundary |
| [New conditional scenario study](../../experiments/stage3/conditional-concept/README.md) | 128 scenarios; causal synthetic spinal features and assistance; favorable/equal/adverse OFF learning; old frozen studies unchanged |
| [Portable historical pilot verifier](../../scripts/verify_frozen_pilot_portable.py) | Restores only hash-verified original CRLF inherited contexts in scratch; frozen study/auditor and repository originals stay unchanged |
| [Exit review](exit-review.md) / [integrated verdict](stage3-verdict.md) / [illustrated closeout report](../../output/pdf/SCCI_RH_stage3_closeout.pdf) | Finite digital investigation completed; active assistance and retained benefit remain unavailable under present evidence |
| [Final frozen-observer replay](../../experiments/stage3/frozen-observer-pilot/README.md) | 32 practice/64 OFF sessions; zero launches; sealed predictions and guards verified; no active delivery path implemented |
| [Continuation review and next work](continuation-review.md) | Verified numerical/input/response/teacher checks, integrated findings and remaining design tasks |
| [Evidence-to-design revision](evidence-to-design-revision.md) | Original paper and primary experiments mapped to specific engineering tests |
| [Competence-gated teacher library](teacher-library.md) / [aperture-resolved teacher revision](resolved-teacher.md) | Separate measured competence, decoder and reference gates; unsupported cadences remain unavailable |
| [Intervention-aware prediction](assisted-prediction.md) | 31 causal horizons, complete withheld intervention recordings and finite-context admission limits |
| [Moving-source sensitivity](source-sensitivity.md) | 75 captures, actual sample apertures, source-hold failures and an ambiguous-contact witness |
| [Delivery requirements](delivery-requirements.md) | Observed-map precision tradeoff; prospective monitor requirements remain unimplemented |
| [Finite-frame dynamic response](dynamic-response.md) | Actual pulse delivery, measured kernels, two integration grids and separately admitted isolated response domains |
| [Zero-future-command baseline](sparse-baseline.md) | Observed past-response strip/re-add; full uncertainty and explicit unsupported-tail rejection |
| [Coupled-pilot specification](dynamic-coupling-specification.md) | Candidate response added once, complete correction gate and timed residual cancellation |
| [Completed isolated pilot](isolated-pilot.md) | Independent learner drift rejects admission; 128 zero-launch practice trials and 64 pulse-free OFF assessments |
| [Observed-state observer confirmation](../../experiments/stage3/observed-state-observer/README.md) | Frozen measured-data method; 32 fresh-noise grid captures within the finite no-dose forecast budget; separate from the connected replay |
| [Observer integration plan](observer-integration-plan.md) / [independent saved-data review](observed-state-independent-review.md) | Preserved pre-implementation plan and component review; completed actual-only replay retains delivery/learning-interaction limits |
| [First Stage 4 monitoring slice](../stage4/entry-plan.md) | Native two-source phase-charge investigation and explicit power/leakage constraints; full electronics remain pending |
| [Illustrated mechanism revision report](../../output/pdf/SCCI_RH_stage3_mechanism_revision.pdf) | Eight-page technical report covering the selected teacher/source/prediction/precision and dynamic-response revisions |
| [Mathematical specification](mathematical-specification.md) | Causal information partitions, units, electrical equations and observation bounds |
| [Motor mechanism](motor-model.md) | Contact acquisition, expert/learner comparisons, active practice, OFF retention and transfer |
| [Pressure mechanism](pressure-model.md) | External SBP, identified pressor authority, support timing, faults and overshoot |
| [Results and interpretation](results-and-interpretation.md) | Paired seed results; integrated failures and separately labeled conditional mechanism |
| [Electrical review](electrical-review.md) / [motor review](motor-review.md) | Independent findings, corrections and evidence boundaries |
| [Progress and remaining work](verification-progress.csv) | Scoped coverage; concept completion does not establish complete biological or hardware verification |
| [Numerical verification](numerical-verification.md) / [original plan](numerical-convergence-plan.md) | 96 motor fixed-input refinements, five bounded closed-loop grids and 408 matched pressure runs |
| [Acquisition qualification](acquisition-qualification.md) | Range-bounded digital residuals, per-contact validity and missing-input sensitivity |
| [Information comparison](information-comparison.md) / [external-history baseline](external-history-baseline.md) | Seven studies with a capacity-matched learned external comparator and same-support scoring |
| [Expert competence correction](expert-validation.md) | Original teacher fails timing; separate competent synthetic benchmark and independent decoder transfer |
| [Observed response domain](response-validation.md) | Fixed-profile resting maps, held-out route/density/context cases and joint uncertainty |
| [Known-cue policy](cue-policy.md) | Separate forecasting/scheduling component; assisted-context and actual-delivery gates remain unqualified |
| [Mechanism-to-electronics handoff](mechanism-to-electronics-handoff.md) | Concrete monitor, acquisition, timing, power and integration requirements |
| [Motor precision requirements](motor-precision-requirements.md) | Monitor error budget, ADC/bus limits and conditional requirements for the next policy and circuit revision |
| [Tool selection](toolchain-selection.md) | Fresh laptop inventory and official free/student tool choices |
| [Parameter provenance](parameter-provenance.csv) | Newly chosen electrical assumptions; application parameters are recorded in every study configuration |
| [Raw results](../../results/stage3/) | Full compressed JSON traces, readable summaries and separate electrical witnesses |
| [Foundation receipt](../../provenance/stage3-verification.json) / [continuation receipt](../../provenance/stage3-continuation-verification.json) / [local test run](../../provenance/stage3-test-run.json) | Artifact identities, separate scope counts and completed full-suite result |

## Reproduction

Use Python3.12 and the pinned direct dependencies in `requirements-lock.txt`.
The tested local runtime is3.12.14; numerical results are checked with stated
tolerances, while Git provenance checks exact committed bytes.
Use a project virtual environment so updates to an application-bundled Python
runtime do not silently replace the scientific dependencies. From the repository
root on Windows, create it once with `python -m venv .venv`, then install with
`.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt`.
Invoke that same executable in place of `python` below. The local 12 October
continuation uses this isolated environment; `.venv` is excluded from Git.

```text
python -m pip install -r requirements-lock.txt
python scripts/run_stage3_studies.py
python scripts/run_stage3_studies.py --check
python scripts/stage3_electrical_sweep.py --check results/stage3/electrical-sweep.json
python scripts/stage3_pressure_convergence_probe.py --check results/stage3/pressure-convergence-probe.json
python scripts/build_stage3_figures.py
python scripts/verify_stage3_foundation.py
python scripts/verify_stage3_continuation.py
python -m unittest discover -s tests -v
```

The runner supports `--module electrical`, `pressure`, `fallbacks` or `motor`.
`--jobs 2` runs independent motor configuration/seed studies in two worker
processes; the allowed range is1–4 and the default is1. Each worker creates a
fresh electrical adapter, and saved branch/seed ordering stays fixed. Other
modules remain serial. The CI reproduction uses two workers.
It keeps all seed-level summaries and raw application traces in JSON gzip files.
These can be read with Python's standard `gzip` and `json` modules; no proprietary
data format is required. It resolves electrical edges analytically, rather than
pretending the 5ms body step resolves microsecond phases.

The continuation uses separate explicitly configured studies. Reproduce them
without overwriting the committed evidence:

```text
python scripts/stage3_motor_convergence.py --check results/stage3/numerical/motor-convergence.json.gz
python scripts/stage3_pressure_convergence.py --check results/stage3/numerical/pressure-convergence.json.gz --summary-check results/stage3/numerical/pressure-convergence-summary.json --jobs 2
python scripts/stage3_acquisition_qualification.py --check results/stage3/numerical/acquisition-qualification.json.gz
python scripts/stage3_information_comparison.py --check --jobs 2
python scripts/stage3_response_validation.py --check results/stage3/response-validation/response-domain-raw.json.gz --summary-check results/stage3/response-validation/response-domain-summary.json --jobs 2
python scripts/stage3_cue_policy_study.py --check results/stage3/cue-policy/raw.json.gz
python scripts/stage3_expert_validation.py --check
python scripts/stage3_teacher_library_study.py --check
python scripts/stage3_resolved_teacher_study.py --check
python scripts/stage3_assisted_prediction_study.py --check results/stage3/assisted-prediction/raw.json.gz
python scripts/stage3_source_sensitivity.py --jobs 2 --check results/stage3/source-sensitivity/raw.json.gz --summary-check results/stage3/source-sensitivity/summary.json
python scripts/stage3_delivery_requirements.py --check
python scripts/stage3_dynamic_response_study.py --check
python scripts/stage3_sparse_baseline_study.py --check results/stage3/sparse-baseline/raw.json.gz
python scripts/stage3_isolated_pilot_study.py --check results/stage3/isolated-pilot/raw.json.gz
python experiments/stage3/observed-state-observer/verify_study.py --reproduce
python scripts/verify_frozen_pilot_portable.py --reproduce
python scripts/verify_frozen_pilot_portable.py --audit-only
python scripts/verify_stage3_revision.py
```

These commands can take substantial time; the receipt verifiers check saved
evidence, while the commands above recompute it. CI performs both. Source hash
checks prevent silently reusing results from changed model implementations.

For direct unit-test execution, set `PYTHONPATH=src` (PowerShell:
`$env:PYTHONPATH='src'`). The reproduction scripts configure their own source path.

The independent circuit check uses the already installed ngspice shared library:

```text
python scripts/stage3_ngspice_check.py --require-library
```

Supply `--library` or `NGSPICE_LIBRARY` on another host. Absence of that library
is an explicit skip, never a passing circuit simulation. The committed local
receipt records actual engine46 runs, their assumptions and refinement checks.

## Interpret the branches correctly

The nominal motor branch uses the characterized electrical adapter and the chosen
nominal biological response. A separately declared fast-response sensitivity
keeps the same electrical evidence. Neither branch is tuned to produce assistance.
The `conditional_fast_response_assumed_delivery` branch instead uses an explicitly
unqualified nominal delivery assumption and fast biological response to examine
the learning mechanism **if** a future system can earn those capabilities. Its
results must not be relabeled as integrated electrical validation.

The original and fair-comparison teacher generators are **not task-competence
qualified**: the independent audit finds failed timing despite their "expert"
resource labels. The [separate competence benchmark](expert-validation.md) does
not retroactively replace those learning studies. The new
[aperture-resolved library](resolved-teacher.md) admits the nominal inverse-model
references after independent measured checks; its faster references remain
unavailable. This does not retroactively change older retained-learning results.
Historical coarse motor
statistics also require the numerical caveat in the continuation review.

The pressure branch uses external measurements because dense stimulation does not
qualify continuous neural recording. It uses a characterized, averaged pulse-dose
reduction; live continuous routing, actual analog guard behavior and chemistry are
later evidence. Improved modeled disturbance response can coexist with recovery
overshoot or loss of support when feedback stops.

The [finite exit review](exit-review.md) closes this selected digital investigation
with its negative active-assistance verdict and concrete detailed-design handoff.
Biological efficacy and future active model extensions remain separate evidence
requirements. Complete native electronics, target firmware, populated CAD and the
final integrated manuscript follow; this does not finish the full implant project.
