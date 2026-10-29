# Measured finite-frame dynamic response

A steady pulse-train plateau gain does not predict the displacement caused by one sparse
whole-profile command. This separate experiment identifies its measured time course.
It changes no historical model, reference library, predictor or learning result.

## Declared experiment

The unchanged electrical adapter generates every nonzero calibration and validation
pulse: **3 mA, 200 microseconds per phase, 40 Hz whole-profile frames**. The private body
receives the adapter’s returned true signed charge fraction. Identification receives only
independently monitored completed dose and external position measurements. Nominal onset
stays **35 ms**, original movement/activation/plasticity constants stay fixed, and learning
is disabled. Event-split integration at 2.5 ms and 0.625 ms is compared. This is an
**external-only** experiment; there are no neural recordings or held-source claims.

The original reduced biological law still holds a charge-normalized command for its
25 ms frame after onset. The identified kernel qualifies that declared activation/body
surrogate. It does not establish the real spinal response to a 500-microsecond biphasic
electrode waveform; actual electrical delivery and assumed biological transduction remain
distinct parts of the digital experiment.

Calibration uses six isolated positive and six isolated negative pulses on each route,
each paired with a separately measured rest baseline. A fixed 0..600 ms table at 5 ms
physical supports estimates the two-foot response per monitored dose. Other noise
realizations, movement, route combinations and schedules remain excluded from fitting.
The body’s recruitment matrix, threshold, time constants, ODE state and future state are
never fit or prospective prediction inputs. Measured baseline subtraction is an explicit
paired-recording assumption; a subject/context change can invalidate it.

## Error accounting

The original actual monitor uncertainty (about 44.1% of nominal phase charge) is retained
in **all fitted gain intervals**. The calibration allocation is
`U_G = (2 SEM × d + |G| × U_d) / (d - U_d)`, with a positive denominator required.
`2 SEM` is an empirical repeated-recording allocation, not probability coverage or a
deterministic label bound. Prospective product error includes the cross term:
`U_G × d_future + |G| × U_future + U_G × U_future`.
The measured withheld residual, a separately declared **3 mm baseline-subtracted label
allowance**, and joint product allocation must together remain below **25 mm** at every
scored physical support. Positive principal-route directional authority is checked within
150 ms. These finite empirical gates do not establish a worst-case biological bound.

Directional single-command evidence does not qualify a full two-route inverse map.
A later controller must select only independently admitted response domains and include
its baseline/reference errors; the response table alone is not permission to stimulate.

The actual branch generates its own per-frame electrical/monitor records. For prospective
prediction it reuses the calibration trace mean/bound under the fixed modeled load; future
validation monitors are withheld. The nominal branch instead chooses **1.012 ± 0.074**.
A third branch chooses a **4% future-monitor allocation**. Both are unqualified prospective
assumptions and neither reduces the actual past calibration uncertainty.

## Independent observed domains

| Grid us | Recording | Actual electrical trace domain | Nominal future assumption | 4% future assumption |
|---:|---|---|---|---|
| 2500 | moving_single_0_1 | False | True | True |
| 2500 | moving_single_0_-1 | False | True | True |
| 2500 | moving_single_1_1 | False | True | True |
| 2500 | moving_single_1_-1 | False | True | True |
| 2500 | moving_paired_same | False | True | True |
| 2500 | moving_paired_opposite | False | True | True |
| 2500 | moving_sparse | False | False | False |
| 2500 | moving_sparse_paired | False | False | False |
| 2500 | moving_faster_sparse | False | False | False |
| 2500 | changed_subject_sparse | False | False | False |
| 2500 | unmatched_baseline_sparse | False | False | False |
| 2500 | unannounced_sensor_offset | False | False | False |
| 625 | moving_single_0_1 | False | True | True |
| 625 | moving_single_0_-1 | False | True | True |
| 625 | moving_single_1_1 | False | True | True |
| 625 | moving_single_1_-1 | False | True | True |
| 625 | moving_paired_same | False | True | True |
| 625 | moving_paired_opposite | False | True | True |
| 625 | moving_sparse | False | False | False |
| 625 | moving_sparse_paired | False | False | False |
| 625 | moving_faster_sparse | False | False | False |
| 625 | changed_subject_sparse | False | False | False |
| 625 | unmatched_baseline_sparse | False | False | False |
| 625 | unannounced_sensor_offset | False | False | False |

| Grid us | Recording | Branch | Measured RMSE mm | Largest empirical allocation mm |
|---:|---|---|---:|---:|
| 2500 | moving_single_0_1 | actual_electrical_trace_domain | 2.137 | 27.530 |
| 2500 | moving_single_0_1 | nominal_future_assumption | 2.137 | 19.712 |
| 2500 | moving_single_0_1 | four_percent_future_monitor_assumption | 2.137 | 18.990 |
| 2500 | moving_single_0_-1 | actual_electrical_trace_domain | 2.082 | 26.721 |
| 2500 | moving_single_0_-1 | nominal_future_assumption | 2.082 | 18.903 |
| 2500 | moving_single_0_-1 | four_percent_future_monitor_assumption | 2.082 | 18.181 |
| 2500 | moving_single_1_1 | actual_electrical_trace_domain | 2.148 | 26.930 |
| 2500 | moving_single_1_1 | nominal_future_assumption | 2.148 | 19.262 |
| 2500 | moving_single_1_1 | four_percent_future_monitor_assumption | 2.148 | 18.554 |
| 2500 | moving_single_1_-1 | actual_electrical_trace_domain | 2.123 | 26.244 |
| 2500 | moving_single_1_-1 | nominal_future_assumption | 2.123 | 19.432 |
| 2500 | moving_single_1_-1 | four_percent_future_monitor_assumption | 2.123 | 18.801 |
| 2500 | moving_paired_same | actual_electrical_trace_domain | 2.170 | 30.164 |
| 2500 | moving_paired_same | nominal_future_assumption | 2.170 | 21.757 |
| 2500 | moving_paired_same | four_percent_future_monitor_assumption | 2.170 | 20.991 |
| 2500 | moving_paired_opposite | actual_electrical_trace_domain | 2.165 | 31.603 |
| 2500 | moving_paired_opposite | nominal_future_assumption | 2.165 | 22.589 |
| 2500 | moving_paired_opposite | four_percent_future_monitor_assumption | 2.165 | 21.801 |
| 2500 | moving_sparse | actual_electrical_trace_domain | 2.359 | 37.711 |
| 2500 | moving_sparse | nominal_future_assumption | 2.359 | 27.676 |
| 2500 | moving_sparse | four_percent_future_monitor_assumption | 2.359 | 26.749 |
| 2500 | moving_sparse_paired | actual_electrical_trace_domain | 2.526 | 50.396 |
| 2500 | moving_sparse_paired | nominal_future_assumption | 2.525 | 37.818 |
| 2500 | moving_sparse_paired | four_percent_future_monitor_assumption | 2.525 | 36.774 |
| 2500 | moving_faster_sparse | actual_electrical_trace_domain | 2.361 | 36.688 |
| 2500 | moving_faster_sparse | nominal_future_assumption | 2.360 | 26.188 |
| 2500 | moving_faster_sparse | four_percent_future_monitor_assumption | 2.360 | 25.219 |
| 2500 | changed_subject_sparse | actual_electrical_trace_domain | 2.367 | 39.633 |
| 2500 | changed_subject_sparse | nominal_future_assumption | 2.365 | 29.318 |
| 2500 | changed_subject_sparse | four_percent_future_monitor_assumption | 2.365 | 28.365 |
| 2500 | unmatched_baseline_sparse | actual_electrical_trace_domain | 59.351 | 140.372 |
| 2500 | unmatched_baseline_sparse | nominal_future_assumption | 59.351 | 131.671 |
| 2500 | unmatched_baseline_sparse | four_percent_future_monitor_assumption | 59.351 | 131.360 |
| 2500 | unannounced_sensor_offset | actual_electrical_trace_domain | 34.722 | 74.979 |
| 2500 | unannounced_sensor_offset | nominal_future_assumption | 34.722 | 64.677 |
| 2500 | unannounced_sensor_offset | four_percent_future_monitor_assumption | 34.722 | 63.751 |
| 625 | moving_single_0_1 | actual_electrical_trace_domain | 2.137 | 27.530 |
| 625 | moving_single_0_1 | nominal_future_assumption | 2.137 | 19.712 |
| 625 | moving_single_0_1 | four_percent_future_monitor_assumption | 2.137 | 18.990 |
| 625 | moving_single_0_-1 | actual_electrical_trace_domain | 2.082 | 26.721 |
| 625 | moving_single_0_-1 | nominal_future_assumption | 2.082 | 18.903 |
| 625 | moving_single_0_-1 | four_percent_future_monitor_assumption | 2.082 | 18.181 |
| 625 | moving_single_1_1 | actual_electrical_trace_domain | 2.148 | 26.930 |
| 625 | moving_single_1_1 | nominal_future_assumption | 2.148 | 19.262 |
| 625 | moving_single_1_1 | four_percent_future_monitor_assumption | 2.148 | 18.554 |
| 625 | moving_single_1_-1 | actual_electrical_trace_domain | 2.123 | 26.244 |
| 625 | moving_single_1_-1 | nominal_future_assumption | 2.123 | 19.432 |
| 625 | moving_single_1_-1 | four_percent_future_monitor_assumption | 2.123 | 18.801 |
| 625 | moving_paired_same | actual_electrical_trace_domain | 2.170 | 30.164 |
| 625 | moving_paired_same | nominal_future_assumption | 2.170 | 21.757 |
| 625 | moving_paired_same | four_percent_future_monitor_assumption | 2.170 | 20.991 |
| 625 | moving_paired_opposite | actual_electrical_trace_domain | 2.165 | 31.603 |
| 625 | moving_paired_opposite | nominal_future_assumption | 2.165 | 22.589 |
| 625 | moving_paired_opposite | four_percent_future_monitor_assumption | 2.165 | 21.801 |
| 625 | moving_sparse | actual_electrical_trace_domain | 2.359 | 37.711 |
| 625 | moving_sparse | nominal_future_assumption | 2.359 | 27.676 |
| 625 | moving_sparse | four_percent_future_monitor_assumption | 2.359 | 26.749 |
| 625 | moving_sparse_paired | actual_electrical_trace_domain | 2.526 | 50.396 |
| 625 | moving_sparse_paired | nominal_future_assumption | 2.525 | 37.818 |
| 625 | moving_sparse_paired | four_percent_future_monitor_assumption | 2.525 | 36.774 |
| 625 | moving_faster_sparse | actual_electrical_trace_domain | 2.361 | 36.688 |
| 625 | moving_faster_sparse | nominal_future_assumption | 2.360 | 26.188 |
| 625 | moving_faster_sparse | four_percent_future_monitor_assumption | 2.360 | 25.219 |
| 625 | changed_subject_sparse | actual_electrical_trace_domain | 2.367 | 39.633 |
| 625 | changed_subject_sparse | nominal_future_assumption | 2.365 | 29.318 |
| 625 | changed_subject_sparse | four_percent_future_monitor_assumption | 2.365 | 28.365 |
| 625 | unmatched_baseline_sparse | actual_electrical_trace_domain | 59.351 | 140.372 |
| 625 | unmatched_baseline_sparse | nominal_future_assumption | 59.351 | 131.671 |
| 625 | unmatched_baseline_sparse | four_percent_future_monitor_assumption | 59.351 | 131.360 |
| 625 | unannounced_sensor_offset | actual_electrical_trace_domain | 34.722 | 74.979 |
| 625 | unannounced_sensor_offset | nominal_future_assumption | 34.722 | 64.677 |
| 625 | unannounced_sensor_offset | four_percent_future_monitor_assumption | 34.722 | 63.751 |

## Numerical and composition limits

Both grids make identical domain decisions: **True**.
Largest fitted kernel difference: **1.54e-17 m per dose fraction**.
Raw independent trajectories, measured labels, monitor records, private generator-only
pulse witnesses and every scored error trace are retained in the deterministic gzip files.

`response_model_from_record(...)` loads a separately provenance-verified model receipt.
`predict_future_effect(...)` accepts only known whole frames from the current decision
to a physical target within 150 ms. It accepts no future monitor or measurement. Its
output may be added only to a **zero-future-command baseline forecast**. The baseline
already contains the effects of past commands; adding them again or adding this table
to an assisted forecast would double-count intervention. Baseline prediction error,
reference availability, acquisition, scheduling and residual guards remain separate
prerequisites for any later coupled experiment.

`predict_observed_past_response(...)` separately provides past-dose means and the same
joint intervals for stripping measured history and adding ongoing past response at a
target. It accepts only completed monitors already available at the decision and requires
the complete past monitor history. **Release after 600 ms is unqualified**: older effects
raise an explicit error instead of being silently treated as zero. A release rule or
longer kernel domain needs separate qualification before long-running use.

The existing actual steady-map rejection is linked with its saved source identity in
the receipt and remains unchanged. New dynamic outcomes cannot retrospectively qualify
that map or the historical 280-row learning comparison. No closed-loop policy, new
retained-learning result, real neural recording or real consumer efficacy is established.

## Reproduction

`python -X utf8 scripts/stage3_dynamic_response_study.py --check` reruns the actual
per-frame electrical delivery, both integration grids, measured fits and all heldout
domains, and compares saved receipts/report at relative tolerance 2e-8, absolute 1e-11.
Schemas: `scci_rh.stage3.dynamic-response-study.v1`, `scci_rh.stage3.dynamic-response-model.v1`,
and `scci_rh.stage3.dynamic-response-recordings.v1`. All new files are separate from frozen
Stage 3 studies. Model identities bind normalized sources, specification and declared
recording/noise/schedule identities; numeric observations are compared separately with
tolerance. ODE right-hand-side evaluation counts are platform-local diagnostics. The
inherited JSON receipt uses a canonical digest independent of text line endings.
Any failure remains a declared unavailable dynamic domain.
