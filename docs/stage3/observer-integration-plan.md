# Review: one pre-dose observer freeze for a finite Stage 3 pilot

12 October 2026. Read-only design review. No authoritative source, historical
result, numerical gate, frozen observer file or source-bound receipt was changed.
This document proposes a **new** integration module and study. It reports no new
experiment or outcome.

## Verdict

A genuine single pre-dose forecast freeze is a reasonable finite integration
route. It avoids the unqualified operation of feeding stimulation-contaminated
positions back into an observer whose states represent unassisted movement.
It does **not** by itself qualify nonzero learning-enabled actions. Two separate
blocks remain: the actual electrical trace domain fails every inherited isolated
action domain, and the inherited intervention-response validation disabled
learning. A negative, all-withheld closeout is an acceptable Stage 3 verdict.
Neither block should trigger an indefinite search for a favorable result.

The new no-dose confirmation supports finite baseline arithmetic only: all 32
paired-grid captures pass, with maximum allocation 11.353736 mm below the
unchanged 15 mm gate. This is sensor-noise independence for the fixed synthetic
subject and conditions, not new-subject or biological qualification. The observer
summarizes the whole accepted prefix and has a 60 ms synthetic movement prior;
it is not information-equivalent to the historical stateless predictor and is
not MCU-ready.

## Exact clock and state contract

1. Reset the position/activation/delay world, electrical monitor session, observer,
   residual guard and one-shot permit for every trial. Carry learned coefficients
   only where the protocol explicitly carries them. Complete physical washout is
   a simulator premise, not evidence from a timer.
2. Supply the one common frozen measured-data prior. Accept only finite, valid
   5 ms position supports on their actual availability clock, with 25 ms delay.
   Preserve observer ordering, gap-reset and sixteen-consecutive-sample rules.
   No private family, theta, recruitment, scale, future position or recording name
   may select an online parameter, context or passing alternative.
3. The existing warmup pattern can be retained without changing its resources:
   decisions 0.200..0.800 s at 25 ms spacing, one far-horizon 150 ms baseline
   commitment each. Its latest physical targets arrive before the final decision.
   Forecast errors or stale/missing targets latch a veto. This uses the new
   observer causally before the freeze, not the old failed baseline by accident.
4. At decision **0.975 s**, consume only observations with availability at or
   before 0.975 s; the newest physical support is exactly **0.950 s**. Freeze one
   complete vector of 26 predictions for **0.975..1.100 s** in 5 ms steps, its
   empirical allocations, model/context identities, source hashes and the whole
   empty action prefix. The observer is then sealed for that trial. Even newly
   arriving pre-launch observations must not revise this vector or the decision.
5. Freeze the candidate choice at 0.975 s. At **1.000 s**, first process every
   measurement already available, apply guard/latch checks and then consume at
   most one whole-frame permit. No replacement candidate or second frame is
   allowed. A launch-veto must not be interpreted as proof of zero biological
   response if an earlier physical profile had already been delivered.
6. Do not call `Observer.update` after sealing, including during commanded-OFF
   time. Actual measured positions then feed the independent residual comparison
   and evaluator only. A position measured under actuation is factual total
   position, not an observation of the unassisted counterfactual.

The first frozen physical target equals the creation clock: 0.975 s. The existing
`PredictionCommit` rejects `target_support_s <= created_s`. Preserve that class.
Use the 0.975 target as a separately recorded frozen delayed diagnostic/latch
comparison when its measurement arrives at 1.000 s, before launch. Commit the
other **25 future targets, 0.980..1.100 s**, through the existing guard. Do not
invent an earlier creation time or quietly drop this first target from coverage.
It is the only target from this final freeze whose delayed observation can stop
the first launch; all later comparisons occur after that launch. Earlier warmup
commitments provide separate pre-launch checks.
The compared measurement was physically generated at support **0.975 s**, before
any dose, and only becomes available at 1.000 s. It is not the position physically
sampled at 1.000 s, which remains unavailable until 1.025 s.

## Finite baseline qualification and empty-action domain

Use one conservative context for all arms and private generator alternatives.
Bind the exact frozen observer/calibration/confirmation bytes and inherited
response model identity. Admission support is the common intersection of the
**development drift and fresh confirmation** exact-prefix domains, 0.100..2.845 s.
A reasonable predeclared admission allocation is the per-horizon maximum
absolute coordinate residual over both of those complete groups, plus the
existing 3 mm label allowance; retain all failures and unavailable supports.
The temporal calibration holdouts have current supports **8.100..11.845 s** and
do not overlap this domain. Report them separately as numerical stress evidence;
do not intersect them with startup domains or use them to grant startup authority.
They do not define the admission allocations proposed here. This proposal does
not refit the method or turn conditional covariance into a bound.

Every qualified packet must satisfy all of these conditions:

- Fixed synthetic subject, known 1 Hz instruction and original cue phase;
  60 ms structural prior and whole-prefix history are explicit shared resources.
- Current support on the declared 5 ms grid and within the common intersection
  of independently observed support domains, not a union. The confirmation's
  complete current-support range is 0.100..2.845 s. The warmup/final supports
  required here are 0.175..0.775 and 0.950 s, respectively.
- Horizons exactly 25..150 ms, all 26 qualified, with each allocation no greater
  than 15 mm. For final admission, support 0.950 and target 1.100 give 150 ms.
- Complete **empty** delivered/pending/planned past-action prefix through the
  frozen observation support and decision. There must be no unobserved earlier
  profile, incomplete monitor, held activation from an earlier trial, or command
  already scheduled before the selected one-shot frame.
- Known zero-future baseline is explicitly counterfactual: no candidate response
  is inside it. The proposed candidate is added once, separately, afterward.
  The no-command branch remains available when every nonzero branch is rejected.

The four scale alternatives and four family labels are generator/evaluator
coverage only; they do not establish an arbitrary theta-vector domain. Later
practice trials may acquire coefficient shapes outside these observed captures.
Do not assume that repeated intervention sessions are qualified merely because
their initial scalar norm is between 0.9 and 1.3.

## Response, dose and interval accounting

For a candidate signed route vector `s`, frozen no-dose baseline `b(t)`, response
kernel `G(t-1.000)` and prospective dose `d +/- u_d`, the total predicted position
is `b(t) + G(t-1.000) s d`. Sum the joint gain/dose interval across every selected
route as the existing model does:

`u_response = u_G*d + abs(G)*u_d + u_G*u_d`.

For frozen targets before 1.000 s the future response is exactly zero by command
causality. Pass no candidate frame to `predict_future_effect` for those targets;
that API correctly rejects a frame later than its requested target. At targets
on or after 1.000 s include the selected frame once. Do not impose a private
35 ms body-delay zero-response rule on the measured kernel or inject fitted
lag-zero measurement noise before the command has occurred.

Add the baseline empirical allocation, independently measured response residual
allocation at that exact support/phase, and any separately qualified interaction
allocation. Teacher-reference uncertainty belongs in the correction-against-
reference admission gate, but **not** in a residual prediction-of-actual-position
allowance. Adding teacher error to a total-position residual check would mask
response failure unrelated to teacher representation.

Keep the existing 25 mm combined correction gate. The candidate must pass at
the fixed scoring target 1.100 s. The new full-vector guard also needs an explicit
finite allowance at **every** frozen target. Extract exact support residuals from
the inherited full independent traces; do not repeat the 1.100 s allowance over
other phases or invent a flat residual bound. If any affected support lacks a
qualified finite response/interaction allocation, the nonzero candidate is
unavailable. Zero wins score ties. The two historically untested mixed routes
remain unavailable; do not infer them from opposite signs or linearity.

Critical interaction limitation: `stage3_dynamic_response_study.py` generated
the inherited calibration and validation with **learning=False**. Under the
learning-enabled body equations, delivered stimulation can change theta and
therefore the voluntary component after launch. A no-dose frozen baseline plus
the fixed learning-OFF kernel does not automatically include this difference.
For nonzero learning-enabled qualification, either independently predeclare and
measure its additional residual over the exact first-trial domain, or keep that
active branch explicitly unqualified/withheld. Do not pass private plasticity
equations to the online policy or use its outcome to select a favorable family.

Actual monitoring is a separate channel from the prospective assumption:

- Inherited actual trace branch: measured fraction 1.01318359375 with uncertainty
  0.4411205888605442. Every isolated action domain is currently unqualified.
- Nominal future assumption: 1.012 +/- 0.074. Passing finite response arithmetic
  in this branch remains conditional on that future assumption.
- Future 4% monitor allocation: 1.012 +/- 0.04. It remains an unearned electronics
  target and cannot be silently substituted for the measured uncertainty. The
  33-run monitoring study and native monitoring schematic do not qualify it.

For actual launch, record independent monitor evidence as unavailable until
1.0005 s and, on the existing 5 ms decision clock, processed no earlier than
1.005 s. Bind every selected source/sign to exactly one completed monitor record;
keep the complete prefix, both route records for a paired frame, timing, quality,
uncertainty, saturation and inhibit status. Body truth may drive the private
simulator but never become a policy measurement. Invalid/missing monitoring makes
the pending response interval unknown and latches a fault; it is not evidence
that zero charge or zero response occurred.

Once a valid completed monitor is actually available, compute a separate causal
actual-dose pending-response trace with the frozen kernel and full product
interval at each permitted support. Keep the original prospective commitments
immutable; the actual-dose trace is an additional diagnostic and interval
confirmation, not a retrospective rewrite of the prediction or a second launch
permission. If actual dose does not lie in the predeclared prospective interval,
mark that assumption unconfirmed immediately and retain the original failed
comparison. A post-launch monitor/residual veto cannot undo the pulse.

The simulator holds the corresponding whole-frame equivalent body drive until
1.025 s. Do not erase that past physical intervention at 1.005 s merely because
monitoring then reports a fault. Physical 200 us phase completion and a modeled
25 ms response frame are distinct clocks.

## Residual horizons, expiry and pending response

Commit only positions and intervals computed before their target measurements
are available. Compare each frozen target with its actual delayed total-position
observation; retain support, availability, processing clock, both coordinate
residuals and pass/fail witness. Preserve missing-target, replay, nonfinite,
capacity, observation-age and clock-rollback rejection. The existing maximum
support age is 50 ms: the last target 1.100 normally arrives at 1.125 s and must
be rejected as expired if it is still missing after 1.150 s. Do not fabricate a
measurement while draining the queue.

Forecast **authority ends at physical support 1.100 s**. The one-shot permit is
already spent or irrevocably withheld at 1.000. A clean latch with no remaining
forecasts is not permission for a new pulse. Continue recording the remaining
trial, but label the total-position forecast unavailable beyond 1.100; the
frozen baseline has no supports there.

The response table ends at 600 ms lag, 1.600 s for this frame. Pending-response
records must not silently disappear at either 1.100 or 1.600. The former is a
total-position forecast horizon expiry; the latter is the measured response
window boundary. The inherited API explicitly has **no qualified release rule**
after 600 ms. A later response estimate becomes unavailable, not zero. Keep
commands disabled for the trial and document the complete-reset/washout premise
before any new trial; future physical rearming needs independent recovery
evidence, not a simulation timestamp.

## Minimal finite first experiment and stop rule

First implement a **new replay/integration study**, without changing any of the
21 bound `src/scci_rh` files, old study scripts or saved outcomes. It should prove
the clock, one-shot, domain, monitoring, residual and expiry contracts above,
using the exact frozen baseline method. It may import the immutable generator,
delivery, response and guard components, but new wrapper modules own the new
context and experiment. No blanket replacement of `predict_zero_future`.

Predeclare before generation:

1. One reset 3 s trial per arm/family/branch for the initial mechanism experiment,
   subject seed 2 and initial scale 1.0; one common exact prior and resource
   budget. Four arms: observe-only, known learner goal, expert external reference,
   expert neural-derived reference. Four structural families remain evaluator-
   only. Use matched actual sensor-noise arrays and initial state across arms,
   and paired 2.5/1.25 ms integration grids. Fresh IDs cannot overlap any frozen
   observer/teacher/dynamic study identity. The expert-neural arm is an offline
   expert representation, **not** qualified live learner spinal sensing.
2. Primary actual-electrical branch with all honest gates; it is expected to
   withhold nonzero actions given the currently unqualified response domains.
   Save all candidate reasons and guard witnesses. Optional nominal/4% branches
   must be separately declared *unqualified sensitivity branches*. Neither may
   be promoted to an actual monitoring result or retrospectively repaired by
   its observed charge. A negative result is a finished result for this step.
3. For any nonzero learning-enabled branch, predeclare the missing independently
   observed interaction qualification; without it, it remains unavailable.
   A learning-OFF mechanism replay can test signal/charge/body coupling under
   its stated conditional dose assumption, but establishes no retained learning.
4. Evaluate one same-cadence and one faster-cadence assessment per practice arm,
   each 3 s, learning disabled and output hard-OFF. All assessments have exactly
   zero launched profiles, including delayed commands and any carryover queue.
   Apply the same declared forgetting factor to each arm. Preserve assisted
   practice and assistance-OFF retention/transfer as different outcomes.
5. Save complete sanitized observations, immutable forecast commitments, actual
   monitors, pending-response intervals, residual checks and source/input hashes.
   Keep all private truth and plasticity values solely in evaluator records.
   Report complete counts, withheld/launch reasons, paired-grid differences,
   uncertainty failures and all OFF metrics; do not only display passing trials.

This minimal first experiment has **one practice trial**, not the historical
four. Label its evidence accordingly; do not compare the retention magnitude
as if practice exposure were identical. Four-trial follow-on would require
predeclared coverage of intervention-modified state across sessions, rather than
assuming the current no-dose scalar-scale context qualifies every later theta.
It is optional and must not be a condition for ending Stage 3.

The finite closeout decision is: verified baseline freeze + honest connected
gate/monitor behavior + complete outcome interpretation, or a documented
unavailable active mechanism. Keep the original failed pilot and its zero
retained advantage. No result here would demonstrate human expert-skill transfer,
biological spinal-information value, a learning multiplier or universal body
automation. Stage 4 may progress on explicitly conditional electronics while
Stage 3 ends with an unfavorable or bounded verdict.

## Source evidence inspected

- `src/scci_rh/stage3/isolated_pilot.py`: pure chooser at 103; conservative context
  aggregation at 229; trial wrapper at 258; actual monitor handling at 292;
  pre-launch warmup at 310; frozen historical decision at 324; launch at 345;
  whole-frame body-drive completion at 356.
- `src/scci_rh/stage3/residual_guard.py`: age/expiry at 22 and 54; strictly future
  commit condition at 67; replay/age and missing-target rejection at 89 and 97.
- `src/scci_rh/stage3/dynamic_response.py`: observed isolated calibration at 153;
  full gain/dose product at 234; future response at 259; complete past-response
  history and unqualified tail-release boundary at 288.
- `src/scci_rh/stage3/sparse_baseline.py`: exact support/action-pattern domains,
  intersection rather than union, strip/re-add live interval mechanism.
- `scripts/stage3_dynamic_response_study.py`: explicit learning=False at 72
  and 94; exact inherited action-response receipt in the saved summary.
- `scripts/stage3_isolated_pilot_study.py`: frozen inputs at 46; historical four
  practice trials at 119; forgetting and hard-OFF assessments at 125..131.
- `experiments/stage3/observed-state-observer/README.md`, frozen observer at
  219/277, measured-data method receipt, development integration discussion,
  confirmation summary and independent causality/uncertainty checks.

Prepared as a design review only. No implementation, new outcomes or change to
the historical/frozen evidence was performed.
