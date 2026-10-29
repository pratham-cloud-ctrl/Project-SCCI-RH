# Predeclared independent sensor-noise confirmation

12 October 2026. TMP ONLY. No capture may be generated until the root agent
independently reviews this protocol, producer/evaluator source and freeze
receipt. This continues the one frozen observed-state method; it does not refit
or replace the authoritative predictor/pilot/runtime.

## Precisely what is independent

Generate sixteen new independent sensor-noise draws over the same finite
four-family by four-scale domain as the development study. Subject seed remains
2, duration 3 s, learning=True, no dose, nominal 1 Hz cue from zero, observation
support every 5 ms and availability 25 ms later. This is independence of sensor
noise only. It is not a new subject, new family, new human observation, biological
validation or evidence of generalization outside the declared finite model.
Under no dose, favorable/zero share one learning law, and harmful/dependent
share another; four named families do not create four distinct no-dose laws.

The order is fixed: favorable, zero, harmful, dependent; within each family,
scales 0.9, 1.0, 1.15, 1.3. Noise IDs are respectively 261012000 through
261012015 in that order. Every ID must be absent from all records in the
declared calibration and development inputs, including the unused nominal
record. These IDs and the cohort manifest are frozen before any noise is drawn.

## Frozen observer and producer

Observer source SHA256:
`203a5bdd90ae20a67f1b6475b47c31a73880d96a5c4434957b51f28a2f767c44`.

Common measured-data method receipt SHA256:
`1157a4490d4455faba6773fe447560b22c218db852efe65fc95c180f373dce7f`.

Use exactly this common prior/diffusion and every frozen setting. No refit,
family selector, subject parameter, private theta/gain/scale, learned-parameter
update, covariance multiplier, additional model variant or post-outcome tuning.
Each trial resets independently from this common prior. The observer consumes
only sanitized measured rows and the fixed known cue/model. Family and scale
belong solely to the private producer and cohort provenance.

The explicit producer uses the existing `isolated_pilot.config()` unchanged
except `dataclasses.replace(..., body_integration_step_s=...)`, then constructs
`motor._World(2, config)`. Its initial theta scale/family are producer-only.
Its outer observation/advance loop matches `generate_unassisted`: observe x
before advancing each 5 ms interval, add declared independent 1.5 mm noise,
then advance zero dose with learning=True. No monkeypatch and no source edit.
The motor and isolated-pilot source byte hashes and a complete sorted byte-hash
manifest of every `src/scci_rh/**/*.py` file are frozen with the protocol, binding
transitive imports. Generation checks the complete manifest before and after
the cohort. The approved preflight receipt is immutable; rerunning preflight
can only verify identical content, never replace an approved freeze.

For each of the sixteen noise IDs, draw one 600x2 noise array. Produce paired
2.5 ms and 1.25 ms body-grid captures using that exact array, same subject and
private condition. Reuse within a pair is intentional; different pairs have
different IDs. Both grid captures are evaluated with the one unchanged observer.
Save the actual shared noise array and its little-endian float64 SHA256 as
producer-only evidence; it is not passed to the observer. Save private position
truth only for the paired grid diagnostic, never as a fit or forecast input.
Thus paired observed-position differences must agree with private-position
differences within 1e-14 m roundoff. No biological or continuum truth is inferred
from agreement between two grids of the same synthetic model.

## Complete evaluation and failure contract

For each of 32 captures, score exactly current indices20..569 (550 supports,
0.100..2.845 s) and all26 horizons25..150 ms at5 ms spacing, both coordinates.
The observer assimilates the already available measured prefix at each support;
future measured rows appear only in offline scoring labels. Initial0..0.095 s
supports are outside this predeclared window; final current supports beyond
2.845 s lack the complete150 ms label and are also outside it. No post-outcome
support/horizon/record exclusion is permitted.

Retain every raw forecast, label, residual, conditional covariance, causal
sensor-noise variance, availability, category, peak witness and failure. Report
maximum absolute observed coordinate residual plus the unchanged3 mm label
allocation for each horizon/condition/grid, and conservatively aggregate the
maximum across all16conditions and both grids. A finite confirmation arithmetic
pass requires complete availability/coverage of every declared support and all
26 aggregate allocations <= the unchanged15 mm budget. A failure is recorded,
not removed. The unchanged25 mm combined correction gate is not tested here.
Covariance does not replace the empirical maximum or authorize stimulation.

Report paired grid differences for all observed positions, all forecasts and
all residuals, per-horizon allocation differences and any changed budget
decision. Save peak supports/horizons/coordinates. Grid differences are
descriptive numerical-sensitivity evidence, with no error-driven adjustment or
new gate chosen after seeing them. Physical model convergence beyond these two
grids remains unproven. Both captures' full observed errors remain in the
conservative aggregate regardless of which grid performs better.

Save one raw gzip per noise pair, bounded below50 MB each, plus one small cohort
summary. Every file identifies the frozen source/receipt/calibration/generator
identities and pre-generation root review. Any missing/incomplete capture makes
the complete cohort unsuccessful. Existing files are never overwritten by a new
generation command. A reproduction check may later regenerate the same frozen
pairs to compare stored numeric fields within rtol2e-8/atol1e-11; this is
reproduction, not an additional independent-noise experiment.

## Interpretation and later boundary

This standalone confirmation can support only a bounded no-dose observer claim
within the declared finite synthetic domain and known60 ms structural prior.
The original failed pilot and all authoritative source/results remain unchanged.
No neural increment, SCCI recording/stimulation, expert transfer, assistance or
retained-learning claim follows. No electrode/hardware performance is tested.

Pilot integration requires a separately reviewed choice: whole-prefix causal
past-response correction/uncertainty, or a genuine single pre-dose forecast
freeze with independently observed pending-response monitoring. Neither is
implemented here. Finite support/action scope, empirical intervals, dose
monitoring and residual cancellation remain obligations before an active pilot.

## Portable execution and dependencies

The exact approved observer/source filenames and relative inputs can be placed
under a portable study-root/tmp, with the verified source snapshot under
study-root/src. A later packaging driver may construct that scratch layout
without changing the approved algorithm. All recorded relative paths use
forward slashes. Python3.12.14, NumPy2.3.5 and SciPy1.18.1 are the current pinned
dependencies. The observer math itself uses NumPy/stdlib; the existing motor
module imports SciPy.signal transitively through acquisition, so this producer
also requires SciPy even though it generates no acquisition/neural data. Use
one BLAS thread. This desktop calculation supplies no MCU resource evidence.
