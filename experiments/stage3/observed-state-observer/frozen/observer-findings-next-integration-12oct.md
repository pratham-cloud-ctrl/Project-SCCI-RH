# Frozen observed-state development outcome

12 October 2026. This is a no-dose-only, tmp-only development investigation.
It does not replace the current predictor or authorize a pilot action. A
persistent unassisted observer must never silently assimilate stimulation-
contaminated positions as if they represented voluntary drive.

## Bounded result

One method was frozen and independently reviewed by the root agent before the
sixteen already inspected drift targets were loaded/scored. No covariance,
seed, state-capacity, support, horizon, or gate change followed the outcome.

| Observed development group | Complete records within all 26 budgets | Current supports | Coordinate residuals | Largest error + unchanged 3 mm allocation |
| --- | ---: | ---: | ---: | ---: |
| Previously inspected 3 s drift captures | 16 / 16 | 8,800 | 457,600 | 12.418841 mm |
| Last 4 s of eight calibration records, not used in parameter fitting | 8 / 8 | 6,000 | 312,000 | 9.409502 mm |

Every declared support was available. Every 25..150 ms horizon in 5 ms steps was
scored. The unchanged forecast budget is 15 mm; the unchanged combined
correction gate is 25 mm and was not tested here. The largest drift residual
itself is 9.418841 mm, at current support 0.100 s, target 0.225 s, left coordinate
in `pilot_withheld_harmful_scale1`. The largest drift allocation whose recent
75 ms spans a reversal is 8.250091 mm; when only the future spans a reversal it
is 7.850855 mm. Thus the development peak moved to startup rather than hiding
reversal cases. Full unrounded forecasts/residuals and witnesses are saved.

The old corpus-only 40-input revisions failed on these same inspected records;
their failure remains a useful negative diagnostic. This result does not
isolate a single cause of improvement: the observer combines exact synthetic
dynamics, a measured-data prior, cue-dependent propagation and persistent trial
memory. It is not an information-equivalent or capacity-matched ablation of
the old stateless predictor. No neural data are used, so it supplies no evidence
of added spinal-information value, expert skill transfer, physiological
automation, assistance efficacy or retained learning.

## What was frozen

State: two positions plus eight voluntary harmonic coefficients. Exact known
cue forcing is propagated through a conditional 60 ms movement model, splitting
two-second direction reversals. Coefficients have uncertain zero-mean Brownian
drift rather than a private family-specific plasticity equation.

Only the eight existing 12 s measured calibration records were used: 64 s fit
the prior/drift (first 8 s each); the remaining 32 s were temporal development
holdout. The separate nominal 12 s record was unused. The common prior is the
mean and conservative covariance of first-two-second observed block fits.
Coefficient diffusion is the uncentered second moment of 24 adjacent two-second
block coefficient differences, divided by two seconds. This observed-data
heuristic includes noise/model mismatch; it is not a recovered biological
learning law. Recording names/family/scale/gain/theta never select runtime
parameters or enter the update.

There are ten persistent means and 55 unique covariance entries, plus clocks
and a consecutive-sample count. The common prior/drift has 101 learned scalar
entries. The Python implementation stores all 100 covariance entries, and its
deterministic F/Q cache has a maximum float64 payload of 1,638,400 bytes before
object overhead. That cache exceeds the proposed 512 KB target RAM. This is a
desktop calculation, with no MCU resource or deadline claim. Persistent state
summarizes the complete accepted trial prefix, not merely sixteen recent rows.

Runtime enforces finite valid clocked measurements with
0 <= support <= availability <= decision, monotone support/decision clocks,
and transactional rejection. A gap greater than 50 ms resets from the common
prior and the new observed position, then requires sixteen consecutive samples.
All 26 means remain diagnostic outputs, but a vector with any target earlier
than decision time is unavailable. Forecast covariance is conditional model
uncertainty, never a stimulation permission or a hard empirical error bound.

## Verification and resources

The independent DOP853 differential-equation crosscheck covered seven intervals,
including two reversals: maximum transition difference 1.681e-14 and covariance
difference 2.330e-21 m2. The 8/16-point quadrature comparison, covariance
semigroup, zero-noise propagation and reversal continuity passed. Explicit
causal past-measurement weights agree with recursive sensor covariance within
5.083e-21 m2; a finite perturbation verifies the actual estimator derivative
within 7.129e-18 m. Future measurement weights are exactly zero.

Availability, future poisoning, identifier/forbidden-field invariance,
out-of-order/nonfinite/negative-covariance rejection, clock rollback, gap reset
and startup checks passed. A separate saved-data audit binds every observed
target to the sanitized input, recomputes all 769,600 residuals/allocations and
peak witnesses, checks all coverage and covariance decomposition, and confirms
the frozen method/input identities. Overlapping forecasts are correlated; their
large residual count is not a count of independent scientific trials. Conditional
three-sigma values are not hard bounds and did not replace empirical maxima.

Dependencies: Python 3.12.14 and NumPy 2.3.5 for the candidate; SciPy 1.18.1 only
for the independent differential-equation oracle. One BLAS thread. Calibration
took approximately 0.47 s; the scoring calculation before output serialization
took 48.353 s. A process-memory sample during scoring saw about 201 MiB peak
working set at that point, not a final measured peak. The segmented result
design for later confirmation avoids a single large JSON output. No new training
or independent confirmation seconds were generated for this development study.

## Integration recommendation and boundary

The result justifies one independently frozen no-dose confirmation of this
same method, not another tuning search. Freeze generator/evaluator source and
the same common measured-data receipt, predeclare wholly new sensor-noise IDs,
then observe all finite conditions/supports/horizons on both body grids. Sensor
noise independence is not new-subject, human, family or biological validation.
Retain every failure and the 15 mm / 3 mm arithmetic. Root will independently
review that protocol before any new capture is generated.

Only after confirmation may an authoritative predictor package be considered.
It must preserve finite physical support/empty-action-prefix qualification,
causal uncertainty and runtime clocks. A conservative aggregate must fail if any
declared condition fails; private family labels cannot select a passing context.
External and neural arms must share this same state capacity, history, prior,
calibration exposure and synthetic plant knowledge before neural increment is
investigated.

For pilot integration, choose and verify either causal whole-prefix past-response
correction with propagated uncertainty, or a genuine one-shot pre-dose forecast
freeze followed by independently observed pending-response monitoring. The
existing isolated pilot permits one admission before any dose; that is a
possible bounded route. Even there, dose monitoring, interval arithmetic,
residual cancellation, future-response admission and stimulation-off assessment
remain separate obligations. This development result does not close them.

## Evidence entry points and identity

- `observer-protocol-12oct.md`
- `observed_state_observer_12oct.py`
- `observer-method-freeze-12oct.json` (all 32 calibration block fits/residuals)
- `observer-review-approval-12oct.md`
- `observer-independent-check-12oct.py` and `.json`
- `observer-development-summary-12oct.json`
- `observer-development-raw-12oct.json.gz` (29,340,888 bytes)
- `observer-saved-data-audit-12oct.py` and `.json`

Protocol SHA256: `d4f541a7d0d2b38f5e438ce30df148d45b753699d3c1251f79fe89b6f4ad84b2`.
Implementation: `203a5bdd90ae20a67f1b6475b47c31a73880d96a5c4434957b51f28a2f767c44`.
Method receipt: `1157a4490d4455faba6773fe447560b22c218db852efe65fc95c180f373dce7f`.
Development summary: `f76da8ef3641d81cf514164e1f3f1dd475be4a560c2b96be9d54b2c63b4246bf`.
Development raw: `5597eed3e622f2c7a87fb79ad229e1ae5cd6b0715eb72ce4907558db0a987357`.

All work remains under tmp. Authoritative sources/results/receipts, the failed
current pilot outcome, and Git state were not changed by this investigation.
