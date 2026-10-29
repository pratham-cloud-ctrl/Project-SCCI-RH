# Measured, competence-gated teacher library

This is a new mechanism revision, built from the separately saved
[expert benchmark](expert-validation.md). It does not change the teacher or results in
the historical [280-row information comparison](information-comparison.md). The old teacher
failed the declared timing criterion. Its historical differences are conditional controller/
plasticity outcomes, not validated expert-to-novice learning.

## Separate admission gates

1. **Observed competence:** every recording in a cadence domain, and the nominal training
   recording, must satisfy the existing 18 mm contact spatial and 25 ms contact timing RMSE
   criteria. These are kinematic peak proxies; body truth never qualifies the teacher.
2. **Independent decoded representation:** the frozen voltage-feature decoder must satisfy
   the same task criterion on each complete withheld recording after initial acquisition
   warmup. Its externally measured residual allocation is
   `2 × position RMSE + 2 × 100 ms × velocity RMSE < 25 mm`; standardized inputs must stay
   within the existing ±5 range. The chronological, purged training-capture holdout must
   also satisfy that allocation. The external reference does not need a neural decoder.
3. **Complete trajectory representation:** the fixed nominal-trained sin/cos template must
   satisfy the task criterion and `2 × measured trajectory RMSE < 25 mm` on every complete
   withheld recording in the selected domain. This allocates the existing observer’s
   `2 × position RMSE` term to static trajectory mismatch; no template velocity uncertainty
   prediction is claimed. The thresholds were inherited before running this qualification,
   not selected from its outcomes. These are empirical engineering gates, not probability
   coverage or worst-case bounds. Downstream assisted prediction still needs its own gate.

Each decoder and each external/neural template is fitted only on nominal performance0.
Templates use the decoder’s same 1,757-row training partition: a chronological 75/25 split,
100 ms exclusion on both sides of the split, and four-row edge trimming. The decoder’s
velocity labels are differentiated and smoothed separately inside partitions. Complete
other recordings remain excluded from all fitting and model/threshold selection.

## Observed decisions

| Generator | Cadence Hz | Observed competent recordings | Withheld recordings | External reference | Neural reference |
|---|---:|---:|---:|---|---|
| legacy_voluntary | 1 | 0/4 | 3 | False | False |
| legacy_voluntary | 1.15 | 0/4 | 4 | False | False |
| idealized_inverse | 1 | 4/4 | 3 | True | True |
| idealized_inverse | 1.15 | 4/4 | 4 | False | False |

| Generator / cadence | Reference | Rejection reasons |
|---|---|---|
| legacy_voluntary / 1 Hz | expert_external | OBSERVED_TEACHER_COMPETENCE_FAILED; INDEPENDENT_REPRESENTATION_ALLOCATION_FAILED |
| legacy_voluntary / 1 Hz | expert_neural | OBSERVED_TEACHER_COMPETENCE_FAILED; INDEPENDENT_REPRESENTATION_ALLOCATION_FAILED; INDEPENDENT_NEURAL_DECODER_QUALIFICATION_FAILED |
| legacy_voluntary / 1.15 Hz | expert_external | OBSERVED_TEACHER_COMPETENCE_FAILED; INDEPENDENT_REPRESENTATION_ALLOCATION_FAILED |
| legacy_voluntary / 1.15 Hz | expert_neural | OBSERVED_TEACHER_COMPETENCE_FAILED; INDEPENDENT_REPRESENTATION_ALLOCATION_FAILED; INDEPENDENT_NEURAL_DECODER_QUALIFICATION_FAILED |
| idealized_inverse / 1 Hz | expert_external | qualified |
| idealized_inverse / 1 Hz | expert_neural | qualified |
| idealized_inverse / 1.15 Hz | expert_external | INDEPENDENT_REPRESENTATION_ALLOCATION_FAILED |
| idealized_inverse / 1.15 Hz | expert_neural | INDEPENDENT_REPRESENTATION_ALLOCATION_FAILED; INDEPENDENT_NEURAL_DECODER_QUALIFICATION_FAILED |

The faster task reverses direction at a nonzero position. The idealized teacher retains
finite body transients rather than instantaneously jumping. A teacher can pass contact
competence while the static template fails a full-trajectory allocation. Such a rejection
remains visible; it is not repaired by relaxing the criterion or refitting on validation.

| Generator | Cadence Hz | Performance | Decoder allocation mm | External template allocation mm | Neural template allocation mm |
|---|---:|---:|---:|---:|---:|
| legacy_voluntary | 1 | 61007 | 13.541 | 15.137 | 15.138 |
| legacy_voluntary | 1 | 71014 | 13.836 | 15.103 | 15.103 |
| legacy_voluntary | 1 | 81021 | 13.674 | 15.223 | 15.223 |
| legacy_voluntary | 1.15 | 51000 | 21.721 | 32.530 | 32.485 |
| legacy_voluntary | 1.15 | 61007 | 22.408 | 32.444 | 32.399 |
| legacy_voluntary | 1.15 | 71014 | 22.288 | 32.543 | 32.498 |
| legacy_voluntary | 1.15 | 81021 | 21.772 | 32.464 | 32.419 |
| idealized_inverse | 1 | 61007 | 16.850 | 3.096 | 3.103 |
| idealized_inverse | 1 | 71014 | 17.027 | 3.147 | 3.155 |
| idealized_inverse | 1 | 81021 | 16.539 | 3.132 | 3.135 |
| idealized_inverse | 1.15 | 51000 | 22.782 | 33.130 | 33.117 |
| idealized_inverse | 1.15 | 61007 | 23.679 | 33.119 | 33.106 |
| idealized_inverse | 1.15 | 71014 | 23.222 | 33.150 | 33.137 |
| idealized_inverse | 1.15 | 81021 | 22.812 | 33.056 | 33.042 |

## Resource and source limits

Each generator uses eight existing 12 s recordings: **96 s total**, comprising one 12 s
training capture and **84 s of withheld recordings** (36 s nominal and 48 s faster). There
are four observation-noise identities per cadence, paired between cadences; faster
performance0 shares the training noise identity but its trajectory/cadence is withheld.
Thus 84 s is independent recording/cadence exposure, not seven independent subjects or
seven unique noise identities. External and neural references receive the same measured
expert resource budget. The training capture has 1,757 fit and 568 purged holdout rows.

All recordings share one artificial subject and contact geometry. Qualified nominal
references do not establish between-person decoding, transfer to other tasks/cadences,
changed electrodes, real spinal signal content, retained learner benefit, or electrical
delivery. The inverse generator uses the private expert movement time constant to create
synthetic skill (`voluntary = desired + tau × desired velocity`). That privilege remains
explicit; the library and controller receive only measured voltage features, external
measurements and source identity. They receive no expert tau, voluntary coefficients,
private evaluator or future online body state. Offline derivative labels are allowed
within the disjoint training/validation recordings; they are not online predictors.

**Admission is within the frozen capture model.** Its moving source is held for each
5 ms acquisition block. Aperture-resolved source fidelity remains unqualified; nominal
reference admission does not establish the full embodied acquisition chain. This limit
is machine-readable as `source_hold_fidelity_qualified: false`. A new aperture-resolved
capture revision would require fresh measured qualification rather than inheriting these
admissions or changing the frozen recordings.

## Consumer contract

`build_teacher_library(captures, config, generator=...)` returns a `TeacherLibrary`.
`library.references` is the nominal 1 Hz mapping of the existing frozen
`ExpertRepresentation` type. Consumers of another cadence must call
`library.reference_for(kind, cadence_hz=...)`; unsupported cadences return an explicit
unqualified reference. Rejected references retain coefficients and reasons for inspection,
but `control_request` returns zero with `UNAVAILABLE_EXPERT_REPRESENTATION`. External
data never substitutes under an expert-neural label. The declared `learner_only` goal
remains separate from expert evidence. Consumers must retain `library.library_id` and
`reference_id_for(...)` in their new study provenance and honor the selected cadence gate.

The saved pure-policy witnesses test availability behavior only. They are not new learner
calibration, pulse-delivery or retained-learning experiments. A newly qualified reference
is a prerequisite for revised coupled studies, not proof of their outcome.

## Reproduction

`python -X utf8 scripts/stage3_teacher_library_study.py --check` verifies all 16 frozen
gzip input identities, refits and independently validates the two libraries, and compares
the resulting receipts and this report (relative tolerance 2e-8, absolute 1e-11).
Result schema: `scci_rh.stage3.teacher-library-study.v1`; each library is
`scci_rh.stage3.teacher-library.v1`. Raw benchmark recordings remain under
`results/stage3/expert-validation/`; no new recordings or historical replacements occur.
