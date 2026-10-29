# Numerical convergence: preserving the SCCI experiment

**Original planning baseline: 8 October 2026.** The clock separation, independent motor references and full pressure matrix have since been implemented in [numerical verification](numerical-verification.md). The text below preserves the original design rationale and proposed allocations; its descriptions of then-pending work are historical. The new bounded results do not establish overall model or biological qualification.

This review concerns numerical error in the chosen digital models. It does not establish spinal information, selective recruitment, electrical hardware performance or human learning. In particular, the integrated motor branches currently abstain. Agreement between two abstaining runs cannot establish accuracy of an assisted motor mechanism.

## What the current implementation permits

| Model | Current discretization | Consequence for a fair refinement |
|---|---|---|
| [Motor body and policy](../../src/scci_rh/stage3/motor.py) | `MotorConfig.dt_s = 5 ms` simultaneously determines body steps, 200 Hz decisions, external-history length, learning updates and trial row counts. Pulse frames use `k % 5`. | Changing this value alone changes observation and intervention rates; the configuration rejects it. Introduce a separate body integration step before attempting convergence. |
| [Contact acquisition](../../src/scci_rh/stage3/acquisition.py) | Each `observe` call always processes 20 samples per contact at 4 kHz, with 3 microsecond inter-contact aperture offsets. The four synthetic source coordinates are held at the block's starting state for all apertures. | Additional calls per smaller body step would increase the acquisition rate and change the noise draws, filter state and information budget. Keep one acquisition block per 5 ms decision interval. Body integration refinement and source interpolation refinement are different experiments. |
| [Pressure](../../src/scci_rh/stage3/pressure.py) | `integration_step_s` is independent of the 200 Hz waveform, 1 Hz extraction and 4 Hz policy. It must divide each period exactly. Random sensor noise is drawn only at waveform ticks. | A 5 / 2.5 / 1.25 ms comparison is already feasible without changing these rates or random draw counts. General delay/event alignment still needs explicit checking. |

Both bodies use exact exponential updates for individual first-order states. Their cascaded updates use the newly updated upstream state, so the entire coupled update is not an exact solution. Motor learning uses a first-order coefficient update, and task forcing changes with time. Exact scalar updates therefore do not remove the need for a convergence study.

## Motor experiment: first separate clocks without changing the baseline

Add `body_integration_step_s` while retaining the existing 5 ms decision interval. Initially require the new step to divide 5 ms exactly and preserve the declared biological delay on an exact event grid. At a 5 ms body step, the refactored implementation must reproduce the current baseline: initialization, calibration exposure, timestamps, voltages, filter validity, decoder inputs, pulse witnesses, plasticity coefficients and reported metrics. This is a refactor regression check, not a convergence check.

Preserve all these independent schedules at every refinement:

- 200 Hz decisions and external measurements; external support remains 20 ms behind block start and 25 ms old at packet availability.
- 4 kHz contact samples, the existing contact aperture offsets, 20 ms trailing features, 100 ms warmup/history allocations and 5 ms feature-age gate.
- Two physical motor sources with 40 Hz frames, complete fixed-profile pulses, the same pulse-density rule and 11.85 ms processing allocation.
- The same calibration durations, chronological split/purge boundaries, expert recordings, four 3 s practice blocks, OFF assessments, 2% chosen forgetting and 15% faster transfer schedule.
- One draw of the learner/electrode parameters per subject; independent expert subject identity; the same session/block seed identifiers.

Keep the frame schedule in physical time rather than changing `k % 5` to refer to body substeps. The present delayed-dose deque and external-position deque must no longer share a body-step index. Check the effective delay at input and output boundaries with an impulse witness; silently shifting a queue by one step would change onset as the grid refines. Split every input, direction-change, onset and trial-boundary event exactly. Report any event that has been rounded and its error; do not silently replace a biological delay by a nearby multiple of the numerical step.

At every 5 ms boundary, define the observation velocity as the displacement over the **same 5 ms interval**, matching the current finite-difference source definition. Do not substitute the last fine substep's velocity into that source during a body-only comparison. The motor learning coefficient remains a rate per second: substeps use their own duration in the same differential equation and preserve total practice exposure. They must not receive an extra full 5 ms learning increment each.

### Fix randomness by physical observation index

Materialize or deterministically replay each session's existing noise draws by acquisition-block index: one shared-reference array of shape `(20, 1)` and one contact array of shape `(20, 16)` per 5 ms block, in their present draw order. External noise remains one two-position draw per 5 ms observation. Draws must occur irrespective of validity or assistance so artifact-driven masking cannot change the subsequent noise stream.

Store hashes of the learner draw, electrode coefficients, carrier phases and noise arrays in the experiment receipt. Check exact equality across step sizes. Reusing a numeric seed while changing the number or ordering of random draws is insufficient. Electrical adapters must begin each matched simulation at the same explicit independent session boundary; a latch left over from another grid cannot become a numerical difference.

### Separate three sources of error

1. **Body integration with fixed observation approximation.** Preserve the existing 5 ms zero-order-held neural source. Refine only activation, movement and plasticity integration with 5 / 2.5 / 1.25 / 0.625 ms steps. Hold every admitted dose through its existing frame. This measures body numerical error without granting additional observations.
2. **Source discretization at fixed acquisition rates.** After the body study, compare the original source hold with a source evaluated along the privately simulated trajectory at the actual 4 kHz/contact-skew apertures. Keep the filter, quantization, noise realizations, physical support timestamps and decision availability unchanged. This requires an acquisition input supporting per-aperture source coordinates rather than one four-vector. It measures a source approximation; it is not merely another body-step convergence check.
3. **Hybrid closed-loop sensitivity.** Refit calibration using the same observation times and labels at each refinement, then rerun the paired policies. Quantization, threshold gates and frame admission can create discontinuous differences. Record these decisions explicitly rather than averaging them away.

For the aperture-resolved experiment, begin each interval with commands already authorized by earlier decisions. Advance the private body chronologically through sample apertures, finish the observation block, and only then make its next decision. No later decision or end-of-block state may populate an earlier sample. The private simulation can supply an aperture-time trajectory value to the acquisition boundary; the controller still receives only the resulting measured feature packet.

## Motor comparison matrix and suggested gate

Start with fixed-input replay before repeating every costly closed-loop study. Replay an explicit schedule of positive, negative, mixed-route and withdrawn pulses; test rest and instructed movement. Include zero recruitment, adverse route response, the nominal 35 ms onset, the already declared 5 ms sensitivity and a slow 150 ms onset. These are artificial model cases within the [Stage 2 stress envelope](../stage2/control-contracts.json). They must not be adjusted to obtain a desired learning result.

For fixed-input tests, freeze the same delivered-dose witnesses and observation noise across grids. An independent high-accuracy body reference should integrate the declared coupled differential equations with event splitting. With learning disabled and constant forcing, the two-state cascade has a closed-form solution; this is a useful independent implementation check. Time-varying task forcing and learning require a sufficiently resolved reference, not the assertion that each scalar exponential update is exact.

Then compare the saved four seeds and seven arms for all four plasticity families in both the actual electrical and separately labeled assumed-delivery branches. Include informative, redundant and absent source cases. Actual-device calibration probes exercise the body even if practice abstains. The assumed-delivery branch supplies an assisted sensitivity witness but must retain its unqualified status.

**The following acceptance allocations are proposed and untested.** Freeze them in a future experiment specification before examining the motor refinement outcomes:

| Quantity compared on identical physical support | Proposed budget |
|---|---|
| Maximum two-foot position component difference against the finer reference | 0.15 mm |
| Active, OFF-retention and OFF-transfer spatial RMSE differences | 0.10 mm each |
| Final coefficient component difference | 0.10 mm in the coefficient's displacement units |
| Same-support source velocity difference | 0.01 m/s |
| Contact timing score difference | 1 ms; keep the scoring sample grid fixed |

These budgets allocate numerical error below the chosen 1.5 mm external sample-noise scale and well below the 18 mm/25 ms artificial acquisition thresholds. They are engineering choices, not published accuracy requirements. Evaluate the default 5 ms result against the fine reference, not only the two finest results. If it exceeds a frozen budget, retain that finding and refine the production body step.

A result also needs stable qualitative interpretation: authority/abstention reasons, retained-benefit sign, zero-family null behavior and acquisition censoring. Report every changed frame, validity gate, onset estimate, route qualification and threshold crossing. A close-to-threshold flip is a sensitivity finding requiring an explicit uncertainty margin; it must not be hidden by declaring two nearly equal summary means converged. No universal observed convergence order is expected across discrete policy changes.

## Pressure: bounded diagnostic actually run

On 8 October 2026, six 420 s runs were evaluated without editing the frozen models: seed 17 nominal feedback at 5 / 2.5 / 1.25 ms, plus the no-response scenario at the same three steps. This diagnostic used the module's **chosen reference delivery surrogate**, not the integrated electrical adapter. Local runtime: Python 3.12.14, NumPy 2.3.5, SciPy 1.18.1. The six runs took approximately 13.4 s. Results below are observations from this limited diagnostic, not a general convergence qualification.

| Body step | Disturbance RMSE (mmHg) | Recovery overshoot (mmHg) | Delivered train equivalent (s) | Fitted gain (mmHg/fraction) | Fitted lag |
|---|---:|---:|---:|---:|---:|
| 5 ms | 9.8530401002 | 25.1709134006 | 94.43 | 39.7710050339 | 2 s |
| 2.5 ms | 9.8533470328 | 25.1732562743 | 94.43 | 39.7739515423 | 2 s |
| 1.25 ms | 9.8535005804 | 25.1744283216 | 94.43 | 39.7754261341 | 2 s |

All three nominal runs retained the same qualification result, 420 beat records and 1,681 policy samples. Their frame decisions, controller-reason strings and extracted physical peak times were identical. Maximum differences in pressure at policy timestamps were 0.0034325575 mmHg (5 versus 2.5 ms), 0.0017171731 mmHg (2.5 versus 1.25 ms) and 0.0051497306 mmHg (5 versus 1.25 ms). Successive differences roughly halved, consistent with this coupled update's first-order behavior in this case. The substantial overshoot remained.

The three no-response runs produced **exactly identical external observation records**. Since their added pressure is zero, this is a specific witness that refinement retained sensor timing, noise draws, peak extraction and record transport under these aligned configurations. It does not prove equivalence for arbitrary delays or controller threshold crossings.

The existing [pressure test](../../tests/test_stage3_pressure.py) compares only nominal seed 17 disturbance RMSE at 5 and 2.5 ms, with a chosen 0.2 mmHg difference budget. It does not cover the full waveform, all structural scenarios, the integrated adapter, gain intervals, overshoot or fallback duration.

The six runs and their pairwise comparisons are independently reproducible through [the probe runner](../../scripts/stage3_pressure_convergence_probe.py) and [its JSON receipt](../../results/stage3/pressure-convergence-probe.json). The runner temporarily wraps the existing sensor RNG, forwarding every normal draw unchanged and recording its count, initial/final generator states and actual sample hash. All six runs have the same noise sample hash within this receipt. No new noise or body-truth field reaches the controller. Hashes are platform-local floating-point byte witnesses; cross-platform checking compares generator states, counts and numeric moments at `rtol=2e-8`, `atol=1e-11` rather than requiring identical noise bytes across operating systems.

```text
python scripts/stage3_pressure_convergence_probe.py --check results/stage3/pressure-convergence-probe.json
python scripts/stage3_pressure_convergence_probe.py --output results/stage3/pressure-convergence-probe.json
```

`--check` requires an existing receipt path and does not rewrite it. `--output` explicitly saves a new receipt. With neither option, the runner prints a compact diagnostic summary. Its successful exit confirms reproduction and noise/schedule identity under this chosen scope; it never reports a general convergence pass. The receipt retains each grid's configuration, source identity, calibration, summaries, frame/reason/record/peak comparison flags and coarse/fine metric differences.

### Remaining pressure coverage

Create a dedicated three-grid receipt for all thirteen scenarios, four saved seeds and feedback/off comparisons using a fresh `PressureDelivery` adapter for each run. Add all three sensor-loss fallback variants. Keep the oracle separately labeled if included. Compare traces at unchanged 4 Hz timestamps and beat records at unchanged physical support, as well as calibration signs/intervals, frame admissions, fault entry/exit, support-loss nadir and recovery tails.

**Proposed, untested general gate:** preserve the existing 0.2 mmHg summary budget, and add a 0.2 mmHg maximum policy-sample pressure budget, 0.25 s maximum fallback-duration difference and 0.5 s delivered-train-equivalent difference. Qualification/sign conclusions must remain stable or be explicitly marked sensitive. These choices are model verification allocations, not physiological tolerances. Report both adjacent refinements and 5 versus 1.25 ms; disclose any discontinuous frame decisions. Extend the diagnostic matrix to near-limit activation/response constants and non-grid-aligned delays. A timestamped delay/event queue or exact split at a delay transition is required before claiming refinement of those latter cases.

## Exact code work still required

1. Split motor body integration from decision time in `MotorConfig`, `_World`, `_capture` and `_run_trial`; replace body-indexed frame, delay and external-history scheduling with explicit separate clocks. First retain exact coarse baseline behavior.
2. Add the fixed-input independent body reference and matched-noise receipt; preserve 5 ms finite-difference source velocity in the body-only comparison.
3. Extend `ContactAcquisition` with a simulator-only per-aperture source interface while leaving 4 kHz sampling, filter state, validity and availability unchanged. Run this as a separately labeled source-discretization study.
4. Add a dedicated numerical-study runner and small meaningful scheduler/noise-boundary checks. Save every grid's configuration, source/noise identities, raw witnesses, metric differences and gate disposition. Do not overwrite the current foundation results during experimentation.
5. Expand pressure refinement using its existing integration-step option; add exact delay/event handling for deliberately nonaligned cases. No new software package is necessary for these experiments.

Until those comparisons are completed, motor numerical convergence and the full pressure convergence matrix remain open Stage 3 work. They support the larger SCCI mechanism and its claim boundaries; they do not replace the unresolved timing, measurement precision, authority and biological assumptions.
