# Independent motor mechanism review

**Continuation note:** This document records the foundation review. [Numerical verification](numerical-verification.md), [digital acquisition qualification](acquisition-qualification.md), and the [learned external-history comparator](external-history-baseline.md) now extend it. The original coarse conditional results remain preliminary after the numerical defect found in the continuation; later study receipts identify their solver and qualification modes explicitly.

8 October 2026. This review covers the first Stage 3 motor and contact-acquisition
package against the Stage 1 [model plan](../stage1/model-and-verification-plan.md)
and Stage 2 [control contracts](../stage2/control-contracts.json). It is an audit
of a synthetic computational mechanism, not a finding about implanted human
recording, motor skill transfer or clinical safety.

The reviewed implementation is [motor.py](../../src/scci_rh/stage3/motor.py) and
[acquisition.py](../../src/scci_rh/stage3/acquisition.py), with the separate
[electrical delivery adapter](../../src/scci_rh/stage3/electrical.py). Test receipts
and the study outputs are separate evidence; this document does not replace them.

The frozen package includes 14 motor/acquisition checks. The project-level
verification receipt reports 67 passing tests across motor, electrical, pressure
and preserved earlier checks; this review did not rerun that full suite.

## Information boundaries and comparisons

The online policy receives a timestamped external observation, volts-derived
neural features, an observed learner response map, a frozen expert representation
and known task instructions. Internal learner coefficients, contact mixing
coefficients, true recruitment and actual delivered charge remain inside the
simulator or evaluator. The expert has a distinct synthetic subject and contact
geometry. Its neural representation is decoded using its own external labels
and mapped into task coordinates, rather than copied as a voltage waveform into
the learner.

The seven conditions comprise unassisted practice and external-only versus
neural-plus-the-same-external sensing crossed with learner-only, expert external
and expert neural representations. Paired conditions use the same subject,
external noise draws, calibration budget, task, practice duration, electrical
limits and evaluation exposure. Expert resource cost is separately declared.
This structure can distinguish spinal observation and expert information only
when the relevant representation and intervention are actually admitted. Equal
outcomes caused by zero delivered intervention do not establish that neural or
expert information has no value.

Practice performance, stimulation-off retention and stimulation-off transfer
have separate metrics. The retention and transfer runs start with zero movement
and activation state and apply a declared artificial forgetting factor to the
learned coefficients. That is an idealized state reset, not measured biological
washout or an elapsed-time retention experiment. Transfer changes cadence and
response context; because stimulation is off, the changed recruitment cannot
validate intervention under a new response context. It is not generalization
to piano, football or arbitrary skills.
The favorable, zero, harmful and dependent adaptation laws remain chosen
structural hypotheses. None contains a target acquisition multiplier.

## Findings corrected during this review

| Finding | Reviewed correction | Remaining interpretation |
|---|---|---|
| Identification initially divided the measured response by the simulator's true recruitment threshold. | The fit now estimates effective gain at the tested fixed-profile dose, without subtracting the hidden threshold. | Effective gain does not identify the biological threshold or extrapolate to a different pulse profile. |
| Neighboring feature windows and symmetric differentiated labels overlapped the chronological decoder split. | Training and validation now have a 100 ms purge on both sides; differentiated and smoothed labels are constructed separately inside each retained partition. | This is within-subject chronological validation, not independent anatomical or human validation. |
| Future, nonfinite and repeated external support records could enter decoder history; replayed neural packets could remain usable after their support aged. | Finite/order gates reject invalid inputs, older records are rejected, repeated physical timestamps do not add history and neural consumption requires support within the selected 5 ms latest-support gate. | Full transport, clock conversion, sequence and session payload integration remains later work. |
| A body end-state was initially used to generate earlier acquisition apertures. | Acquisition now holds the state known at the interval start; the body advances afterward. Evaluator body support time is recorded separately from block availability. | The 5 ms source/body discretization remains a reduced-model approximation. |
| Zero-filled invalid samples contaminated recursive filter state while raw coverage alone could qualify features. | A separate chosen 100 ms uninterrupted filter-history gate now invalidates features after masking, clipping or missing history. | This duration is an explicit assumption, not a measured settling time or mathematical contamination bound for the 0.1 Hz filter. |
| White input noise was reduced by filtering below the intended integrated allocation. | White excitation is normalized by the causal filter noise gain to target the declared steady-state output RMS. | A white spectral model does not reproduce an actual amplifier's measured noise spectrum. |
| Dose uncertainty was not propagated to gain qualification or policy admission. | The response interval includes monitored-dose uncertainty; a singular-value margin gates identification and a correction uncertainty budget gates policy requests. | The interval is an engineering allowance, not a statistical coverage guarantee. |
| A failed post-delivery recovery report could be treated as if no body dose occurred, or allow repeated rearm. | Actual delivered charge is retained for the body, while unqualified monitor evidence is excluded. The electrical adapter latches subsequent source inhibition until an explicit independent experiment boundary. | A fresh simulation session is not an operational requalification procedure for an implant. |
| Signed route agreement was named held-out validation although both routes were used in the fit. | The field is now named `route_consistency_rmse_m`. A separate 4 s mixed-route capture, withheld from fitting and using a distinct sensor-noise realization for the same subject, reports `heldout_response_rmse_m`. | The narrow same-profile, same-posture plateau validation is implemented; assisted validation across dose profiles and response contexts remains open. |
| Unavailable expert neural evidence could silently use external trajectories under the same label. | The expert neural representation now retains unavailable status and its policy abstains. | This prevents substitution; it does not establish useful neural expertise. |

## Measurement and timing constraints

The final reduced electrical characterization gives the motor reference a
conservative phase-charge uncertainty of approximately **44.1% of nominal
charge**. Propagating this bound through response identification can remove the
positive authority margin, even when the separate mixed-route prediction error
is small. The motor tests preserve this rejection; lowering the fitted onset
alone does not resolve insufficient delivery precision.

A read-only timing diagnostic with seed 0 produced an observed local response
onset of approximately 70 ms and an onset allowance of 5 ms. Even if the
measurement/authority gate were satisfied, the online prediction horizon would
be approximately:

**25 ms external support age + 11.85 ms processing + 70 ms observed onset +
10 ms onset margin = 116.85 ms**, beyond the selected 100 ms qualification limit.

The executable results are authoritative for each final seed and configuration;
these diagnostics explain why the motor policy can correctly abstain.
The result must not be concealed by increasing the horizon or changing biology
after seeing outcomes. The actual-electrical fast-response sensitivity retains
the measurement bound. Separate assumed-delivery biological studies may exercise
admitted intervention conditional on tighter measurement capability, but their
delivery is explicitly labeled `UNQUALIFIED_NOMINAL_ASSUMPTION`. They must not
replace the actual-electrical result or establish an effective human pathway.

The 40 Hz output frame can add waiting even after a request is valid. The model
therefore explicitly does not guarantee the 25 ms reactive event target.
Known task cues permit advance planning in principle; this first local reactive
controller has not earned a complete cue-based predictive implementation.

## Work that remains before a complete Stage 3 exit

- Extend the completed narrow mixed-route validation to assistance in held-out
  dose profiles and task/posture contexts, with a declared uncertainty coverage
  and applicability test. Resolve or explicitly reject the current measured-dose
  precision and authority requirements.
- Add an equally capable learned external-history baseline before interpreting
  any neural fusion benefit as incremental information; the present external
  baseline is a trailing regression, while neural fusion uses a learned model.
- Establish a numerical motor step-convergence study and expose body/source
  discretization error separately from electrical pulse integration.
- Replace the chosen filter-history duration with an explicit residual/error
  qualification, and include clock uncertainty, contiguous gap criteria and
  calibrated feature support in the integrated observation contract.
- Expand expert training to independent performances and contexts; the present
  12 s capture is a frozen synthetic resource with limited diversity.
- Exercise informative, redundant, absent and ambiguous source conditions,
  source/geometry drift, wrong mappings, sensory costs and authority failures
  in a declared batch. A scalar altered learning-error term is a reduced
  sensory-interference hypothesis, not a complete sensory pathway model.
- Connect continuous contact routing, delivered artifact generation, source
  rearm, balancing interruptions, power and independent supervision to the
  same feedback timeline. Isolated pulse characterization does not supply
  that integration.

These open items are compatible with an honest first Stage 3 package. They
prevent declaring all Stage 3 verification objectives complete. Native KiCad
circuit transients, populated CAD, anatomical field/fit studies and chronic
biological evidence have their own later scope and must remain separately named.
