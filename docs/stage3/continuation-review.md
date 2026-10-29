# Stage 3 continuation: verified mechanisms and remaining design work

Integration review: **12 October 2026**. The underlying studies were developed on
8–12 October and remain individually dated. Stage 3 is **in progress**.

Project SCCI RH gives the proposed invasive spinal interface a complete digital
engineering embodiment: recording contacts, acquisition, interpretation,
learner-specific stimulation, monitored delivery and feedback, eventually joined
to native electronics, firmware, engineering CAD and an illustrated paper.
AstroSam's Mind-Link inspires that progression. Both expert-informed retained
motor learning and selected physiological automation remain in scope.

## What this continuation resolves

| Question | Evidence now available | Limit that remains |
|---|---|---|
| Were the motor conclusions sensitive to numerical integration? | 96 fixed-input refinements, independent ODE/analytic references and five bounded closed-loop grids; [numerical review](numerical-verification.md) | Historical coarse conditional numbers are preliminary. The 2.5 ms midpoint/cascade recommendation covers the tested cases, not every future controller. |
| Is pressure refinement convincing beyond six probes? | 408 runs in 136 matched groups with identical actual noise and fixed observations; all chosen numerical budgets pass | 24 comparison-level frame sensitivities remain. Refinement validates the reduced equations, not physiological reachability. |
| Does waiting 100 ms make filtered signals usable after missing input? | Eight matched recordings with an explicit [digital residual bound](acquisition-qualification.md) | A fixed wait is insufficient in tested cases. Bounds concern range-clipped digital counterfactuals, not physical amplifier recovery. |
| What do spinal observations add beyond a strong external comparator? | Seven [capacity-matched studies](information-comparison.md), 280 plasticity/arm rows and same-support scoring | No consistent neural advantage. Actual monitored motor delivery yields no practice pulses. Different valid scoring populations and synthetic source assumptions are disclosed. |
| Was the synthetic teacher actually competent? | Separate [expert audit](expert-validation.md): 16 performances, unchanged task thresholds and independent decoder/cadence checks | All eight original-generator captures fail timing. Eight separately labeled inverse-model captures pass, but this new teacher has not replaced the older learning library. |
| Does the observed response map generalize across pulse patterns? | 24 [response-domain studies](response-validation.md), 432 independently recorded cases in each held-out context | Only the conditional nominal maps qualify. Finite resting-profile applicability does not qualify dynamic practice, untested profiles or contexts. |
| Can known task instructions address the reactive timing failure? | Eight [cue component replays](cue-policy.md), observed forecasts, frame scheduling, expiry/cancellation and causal residual monitoring | Actual authority rejects commands. Assisted forecast error exceeds its allocation. No coupled cue/body or retained-learning result is claimed. |

Teacher qualification concerns the declared contact-peak spatial/timing criteria.
The separate inverse generator retains finite direction-change transients;
passing those criteria does not imply perfect whole-trajectory execution.

The original foundation batch is preserved and reproduced under its historical
defaults. New results use explicit new solver/observer/qualification settings.
Corrections are not silently applied to old data. The separate teacher audit must
be read alongside the original information report before interpreting an
"expert" label as task competence.

## Findings that determine the next revision

The independent electrical monitor currently allows approximately **44.1% of
nominal phase charge** as uncertainty. That makes the observed motor authority
margin negative. Faster biological onset alone does not cure it. The present
shared ADC and bus cannot simply be set to the prospective MHz-per-source rates;
the [precision analysis](motor-precision-requirements.md) makes this constraint
explicit.

The new cue model predicts unassisted observations within its chosen 15 mm
allocation. Its assisted validation requires approximately **54.5 mm**, so the
planner cannot legitimately treat its first output as proof of a valid
closed-loop forecast. Conditional replay emits 34 scheduling requests into a
component witness; it delivers zero physical pulses. The coupled-context witness
stops after its first request. A 40 mm unannounced sensor offset is detected from
arriving measurements, not future truth.

The response-domain study finds 63 of 72 conditional nominal same-context cases
meeting finite gates, and 34 of 72 changed-context cases. Some other changed
contexts have zero empirical coverage. Both accepted and rejected samples remain
in the receipt. No universal response-map transfer is inferred.

## Next owned work package

**12 October continuation:** the [dynamic response](dynamic-response.md),
[zero-future baseline](sparse-baseline.md) and [connected pilot](isolated-pilot.md)
now have separate complete evidence records. The pilot uses independently
measured teacher-reference allocations and sixteen independent learner-drift
captures. All aggregate forecast horizons fail the unchanged 15 mm allocation;
all 128 practice trials abstain and all 64 OFF assessments show no assisted-arm
advantage. This resolves the first pilot as a negative admission experiment. It
does not exercise delivered assistance in the saved full study. Focused tests
separately exercise actual-charge body coupling and fault cancellation.

Review also closed an API scope gap: validated physical support and exact past
pulse patterns must match at runtime. The added restrictions preserve every
pre-existing numerical and decision value. The full local suite passed 224
tests. The next mechanism revision needs a drift-tolerant forecaster trained and
validated from permitted observations, followed by the same matched/OFF protocol.
The [native monitoring investigation](../stage4/entry-plan.md) can proceed in
parallel because the dose-precision requirement is already concrete.

**9 October revision:** the [teacher library](teacher-library.md),
[fresh aperture-resolved teacher captures](resolved-teacher.md),
[intervention-aware observer](assisted-prediction.md),
[75-capture source sensitivity](source-sensitivity.md) and
[observed-map precision requirements](delivery-requirements.md) now address the
first three items below. The earlier table/results above describe their preserved
input studies. Nominal teacher admission and selected predetermined forecast
passes do not yet qualify a feedback-dependent motor controller. The remaining
integration at that checkpoint was dynamic response/policy qualification and new
equal-practice/OFF studies; the 12 October paragraph records their current scope.
The [paper-to-design review](evidence-to-design-revision.md) explains how
the original experimental precedents motivate these tests.

1. **Teacher/library revision:** admit references using measured task competence;
   qualify their frozen decoders on independent performances/cadence, preserve
   unavailable references and charge equal expert/calibration resources to every
   comparison. Give this revision new result identities.
2. **Assisted observation and prediction:** fit and independently validate during
   delivered intervention, changes in context and cue timing. Bound observed
   residuals at execution support, include the full gain/dose cross term and
   reject unsupported forecasts. Couple the policy to the body only when its
   tested context earns admission.
3. **Acquisition sensitivity:** compare full moving-body voltage sources at their
   actual apertures, ambiguous contact fields, clock/error allocations and neural
   information hypotheses. Keep external-only comparisons capacity matched.
4. **Mechanism re-run and electronics handoff:** repeat equal-budget practice,
   OFF retention/transfer and unfavorable plasticity controls with the revised
   library/policy. Derive monitor and scheduling requirements, then develop and
   verify complete native circuits/firmware against the
   [electronics handoff](mechanism-to-electronics-handoff.md).

Digital-stage completion does not require human experiments. It requires a
coherent model/information boundary, adequate numerical evidence, fair
comparisons, tested failure behavior and concrete requirements for the detailed
design. A hypothesis can remain unproven biologically; an unsupported model
qualification must remain rejected. Neither a positive speed multiplier nor a
successful consumer effect is an exit requirement to manufacture.

## Evidence and reproduction

The [continuation receipt](../../provenance/stage3-continuation-verification.json)
checks saved source identities, raw/summary consistency, numerical counts,
finite-domain limits, observed tests and reviewed figures. CI separately
recomputes every committed main study. The foundation receipt is refreshed after
rechecking its preserved batch, while its prior version remains in Git history.
The Git manifest binds the actual committed blobs.

![Motor numerical verification](figures/motor-numerical-verification.svg)

![Pressure numerical verification](figures/pressure-numerical-verification.svg)

![Digital filter qualification](figures/acquisition-qualification.svg)
