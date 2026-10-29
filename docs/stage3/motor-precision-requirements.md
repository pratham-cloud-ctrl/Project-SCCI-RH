# Motor precision and timing requirements for the next design revision

8 October 2026. This is a scalar engineering analysis of the **frozen Stage 3
models and saved results**, not a changed controller, a new simulation batch or a
selected circuit. Every prospective rate, peak bound and precision target below
is conditional and unqualified. Project SCCI RH still concerns the complete proposed
spinal recording → interpretation → learner-specific stimulation → feedback
chain, including retained learning and selected physiological feedback.

The current motor intervention fails its observed authority qualification. That
failure supplies an engineering requirement; it does not establish that spinal
expert information is useless or that a different system would work in people.
See the [results interpretation](results-and-interpretation.md),
[motor review](motor-review.md), [electrical review](electrical-review.md) and
[Stage 2 design baseline](../stage2/system-design.json).

## Where the present charge bound comes from

The frozen [electrical implementation](../../src/scci_rh/stage3/electrical.py)
independently observes signed current at 200 kHz with a chosen ±25 mA input span,
12-bit quantization, a 2% gain-error bound and a 5 µA offset bound. Its complete
analog-waveform peak premise is 25 mA, including between samples. This premise
is **not proved by nonsaturated samples or by the requested 3 mA amplitude**.

For the 3 mA, 200 µs motor reference, the
[saved electrical witness](../../results/stage3/electrical.json) contains:

- Nominal and evaluator actual cathodic charge: 600 nC.
- Independently measured cathodic charge, `Qhat`: 607.91015625 nC.
- Actual sampled support, `Tadc`: 40 samples ×5 µs =200 µs.
- Controller-visible cathodic uncertainty, `Uq`: 264.67235332 nC.

The current signed span gives `LSB =50 mA/4096 =12.20703125 µA`. The implemented
bound, stated in the [mathematical specification](mathematical-specification.md),
is

```text
Uq = [0.02 |Qhat| + (LSB/2 + 5 µA) Tadc]/0.98
     + 2 (25 mA) (5 µs).
```

The division by 0.98 accounts conservatively for gain inversion. Splitting the
same formula into its contributions gives:

| Contribution | Charge allowance (nC) | Percentage of measured charge |
|---|---:|---:|
| Gain, `0.02 |Qhat|/0.98` | 12.40633 | 2.04082% |
| Quantization, `(LSB/2) Tadc/0.98` | 1.24562 | 0.20490% |
| Offset, `(5 µA) Tadc/0.98` | 1.02041 | 0.16786% |
| Two phase edges, `2 Ipeak δedge` | 250.00000 | 41.12450% |
| Total | **264.67235** | **43.53807%** |

The same total is **44.11206% of nominal charge**. Thus the results table's
43.54% and the motor review's approximately 44.1% use different denominators;
they describe the same uncertainty. The edge term supplies approximately 94.46%
of the total. The realized 7.91016 nC measurement error in this one artificial
pulse is much smaller than the allowance, which must cover the stated domain
rather than only the nominal realization.

The old rectangular-command witness is 44.22070 nC, approximately 7.37% of
nominal charge. It uses the command amplitude in the edge term and cannot replace
the general bound for increased recharge, prepolarization or a faulted waveform.
The separate assumed-delivery motor branch declares 7.4% of nominal charge
explicitly; it does not establish that the implemented monitor achieves this.
Both cathodic and anodic phases need their own valid bound, and the net-drive
bound remains their sum. A small net difference cannot certify either phase.

## Prospective precision tradeoffs

Let `g`, `o`, `B`, `Ipeak` and `δedge` denote independently bounded gain error,
offset, effective quantization step, complete-waveform peak and edge uncertainty.
A prospective version of the present allowance would be

```text
A = [g |Qhat| + (B/2 + o) Tadc]/(1-g)
Uq = A + 2 Ipeak δedge.
```

This expression retains the tested bounded monotone/rectangular phase and
integration premises. A peak bound alone cannot make the two-edge allowance
cover arbitrary intersample oscillations or repeated spikes throughout a phase.
Real circuit waveforms need a qualified bandwidth/variation or integration-error
bound; any extra interior-waveform error must be added rather than absorbed into
the nominal edge term.

The scalar comparisons below **hold the measured charge, 200 µs support, signed
±25 mA span and error allocations fixed**. Only for this illustrative calculation
is `δedge =1/fs`. Changing the implementation would require a fresh derivation
and waveform/observation verification; these are not rerun model outcomes.

| Per-source current sample rate | Complete-waveform peak premise | Edge allowance (nC) | Total allowance (nC) | Percentage of measured charge | Status |
|---|---:|---:|---:|---:|---|
| 200 kHz | 25 mA | 250 | 264.67235 | 43.538% | Current reduced-model assumptions |
| 500 kHz | 25 mA | 100 | 114.67235 | 18.863% | Prospective, unqualified |
| 1 MHz | 25 mA | 50 | 64.67235 | 10.638% | Prospective, unqualified |
| 2 MHz | 25 mA | 25 | 39.67235 | 6.526% | Prospective, unqualified |
| 5 MHz | 25 mA | 10 | 24.67235 | 4.059% | Prospective, unqualified |
| 200 kHz | 5 mA | 50 | 64.67235 | 10.638% | Requires a separately proved lower peak bound |
| 1 MHz | 5 mA | 10 | 24.67235 | 4.059% | Requires both prospective timing and peak evidence |

The 5 mA rows retain the ±25 mA **ADC span**; they do not obtain extra precision
by silently narrowing the input range. A smaller peak premise would need an
independent analog limit and proven transient behavior across both phases,
prepolarization, route switching, loads and faults. Guard latency and any current
before shutdown must be included. A threshold setting or observed samples alone
cannot establish a hard complete-waveform maximum. Profiles intended to exceed
that peak need a different qualified domain; a per-profile setting must itself
have monitored ownership and fail behavior. No 5 mA guard has been designed here.

With unchanged nonedge allocations, `A =14.67235 nC`, or 2.41357% of measured
charge. For an **illustrative engineering target** `Uq/|Qhat| ≤r`, the simplified
sample-rate requirement would be

```text
fs ≥ 2 Ipeak / (r |Qhat| - A), provided r |Qhat| > A.
```

At the 25 mA premise, a 10% target needs approximately 1.084 MHz and a 5% target
approximately 3.180 MHz **per source**, assuming edge uncertainty alone shrinks
as `1/fs`. Targets below the 2.414% nonedge floor require better independently
qualified gain, offset or quantization allocations as well. Neither 5% nor 10%
is a derived human requirement or a guarantee that the motor policy qualifies.
The actual requirement must come from the observed response-map and correction
uncertainty budget. Repeating pulses does not average away correlated gain,
offset, timing or structural errors by a square-root rule.

The selected Stage 2 monitor candidate has a 1 MHz **aggregate** ADC allocation,
not 1 MHz per current source. With two simultaneous sources, 20 kHz voltage
sampling per source and 10 kHz other-health allocation, its demand is
`2 fs +50 ksample/s`: 450 ksample/s at the existing 200 kHz rate, but
1.05 Msample/s already at 500 kHz. The ADC-only ceiling is 475 kHz per source.
The selected 16 Mbit/s bus, 16-bit words and 10% command-overhead allowance reduce
the theoretical bus-only ceiling to approximately 429.55 kHz per source, before
additional scheduling margin. At that ceiling the illustrative 25 mA charge
bound remains approximately 21.56% of measured charge. These are capacity
ceilings, not recommended operating points. See the
[reproducible budget equations](../../scripts/run_architecture_budgets.py).

Consequently, MHz-per-source rows are requirements for a **revised Stage 4
monitor architecture**, not settings that can simply be applied to the selected
shared ADC/bus. Parallel paths, burst capture, independently observed edge timing
or analog charge integration could be investigated. Any choice must re-earn ADC
throughput, simultaneous-source behavior, memory, processing, power and timing
budgets. Average pulse duty cannot excuse inadequate instantaneous capture of
simultaneous phases. More sample rate only improves the edge term if aperture,
phase-window, clock, jitter, settling and missing-sample uncertainties support the
claimed `δedge`; otherwise their residual allowance must remain.

## Precision alone does not resolve the nominal timing failure

The [saved motor summaries](../../results/stage3/motor-summary.json) show nominal
observed onset of 67.5–70 ms across four seeds, with a 5 ms onset allowance. The
frozen reactive policy uses

```text
horizon = physical state-support age + processing allocation
          + observed onset + 2 onset uncertainty.
```

At 25 ms external support age and 11.85 ms processing allocation, the nominal
horizon is **114.35–116.85 ms**, beyond the chosen 100 ms limit. Keeping these
other terms unchanged would require observed onset no larger than 53.15 ms to
meet that limit. This is arithmetic, not permission to shorten a physiological
parameter or replace an observed onset with the simulator's hidden delay.
Observed onset includes the chosen dynamics and the detector's definition.

The separately declared fast-response sensitivity has observed onset of
35–40 ms, giving 81.85–86.85 ms under the same calculation. It nevertheless
abstains with the actual electrical adapter because the local authority margin
is negative. Nominal map margins are approximately −31.12 to −38.52 mm despite
narrow same-profile withheld prediction error of 0.268–0.565 mm. Small residual
error cannot cancel a wide monitor-induced parameter allowance.

A known future task cue supplies **instructions**, not future achieved movement.
A next controller can schedule the desired expert-informed task response before
the cue while propagating current learner-state and response uncertainty to its
execution time. Its evidence must include observation support, cue changes,
processing, the 40 Hz output frame wait (up to almost 25 ms), observed onset and
onset uncertainty. Preplanned output also needs expiration and cancellation
when observed conditions invalidate it. Increasing the horizon silently, using
future body truth or relabeling this reactive policy as predictive would bypass
the unresolved mechanism. Predictive control remains proposed work.

## Per-profile calibration and staged continuation

The current learner map is an **effective observed response at one tested pulse
profile**. The calibration estimator correctly does not divide by the simulator's
hidden recruitment threshold. A future per-profile study should record actual
profile/route identity, independent measured phase charge and its interval,
admitted pulse pattern, external response support and context. It can estimate
bounded local maps from those records; it cannot recover an arbitrary threshold
or transfer its gain to an untested profile by normalization alone.

The next bounded work should proceed as follows:

1. Derive a declared acceptable delivery interval from response-map authority and
   the 25 mm chosen correction budget, including external-state and structural
   uncertainty. Retain low, null, adverse and unreachable response cases rather
   than making precision alone the success criterion.
2. Compare candidate independent monitoring/guard architectures against the
   required interval, simultaneous source use and Stage 2 budgets. Record their
   proposed bounds separately. Stage 4 must earn any changed rate, peak premise
   or analog edge/charge measurement through actual digital circuit evidence.
3. Introduce prospective monitor parameters in a separately labeled mechanism
   experiment only after the scalar assumptions are explicit. Preserve the
   frozen integrated-negative and assumed-delivery batches as references; do
   not replace either with a favorable configuration under the same label.
4. Identify and withhold profile, route, pulse-density and posture/context
   combinations using observable learner data. Test uncertainty coverage and
   abstention when a profile is outside the fitted domain. Separate onset
   identification, steady response and release. No plant threshold or true gain
   may enter fitting or policy admission.
5. Implement a known-cue prediction experiment with matched external-history
   and neural-plus-the-same-external information, frozen expert representations,
   equally charged calibration budgets and explicit timing/error tests. Add
   assisted-context validation and motor discretization convergence before
   interpreting an information or intervention advantage.
6. Keep assisted performance, output-OFF retained learning and output-OFF
   transfer distinct across favorable, zero, harmful and dependent plasticity
   families. Continue the specific physiological feedback branch with its own
   measured authority, support-loss and overshoot tests. Neither application
   grants universal spinal control or established healthy-consumer benefit.

This note supplies concrete revision requirements while Stage 3 remains
**in progress**. It changes no saved result, biological parameter, implemented
monitor, native electronics or CAD artifact, and establishes no useful human
stimulation dose.
