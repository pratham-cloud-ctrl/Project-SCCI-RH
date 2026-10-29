# Learning and defending Project SCCI RH

The polished repository is an AI-assisted engineering result. It becomes your research portfolio through your ability to explain its assumptions, reproduce its outputs, challenge them and document your own revisions. Possession of the files does not establish understanding.

## A clear explanation in one minute

Project SCCI RH is a digital engineering study of a future implanted spinal interface. It asks how useful spinal measurements and calibrated stimulation could support expert-informed practice and selected physiological feedback. The release tests a rhythmic training surrogate and a synthetic blood-pressure plant, documents representative electronics, and gives the concept an editable CAD identity. It separates assistance from retained learning. Its results are conditional simulations, not evidence that an implant copies skills or works in a person. AstroSam inspired the progression from concept to inspectable engineering; SCCI_RH's spinal application, models and design are its own.

Use this explanation as a starting point, then express it in your own words. Explain one figure without reading its caption. State one result, one assumption behind it and one observation that would disprove the associated claim.

## Suggested learning sequence

| Stage | Read or inspect | Demonstrate understanding |
|---|---|---|
| Scope | README, `docs/claim-register.csv` | Classify three statements as evidence, design choices or synthetic results |
| Access | Architecture and research documents | Explain intradural recording versus epidural stimulation and motor versus pressure placement |
| Motor model | `src/scci_rh/motor.py`, `docs/model-methods.md` | Predict what beta=0 does before rerunning it |
| Pressure model | `src/scci_rh/pressure.py`, generated traces | Explain the initial dip and the scored window |
| Electronics | Native sources, schematics and validation | Follow artificial input to conditioned output and command to dummy load |
| Mechanical design | CAD source and exports | Explain board coordinates, clearance and the conceptual leads |
| Reproducibility | Reproduction instructions and raw results | Rerun a study and match its summary |
| Ownership | Design decisions and contribution record | Make and defend one meaningful documented revision |

Use the repository's reproduction instructions for exact commands and dependencies. Pictures are convenient entry points; native files are the evidence that the work is inspectable and changeable.

## Motor model checkpoints

1. **What is measured?** Artificial quadrature signals represent known phase. They are not animal or human spinal recordings. The link from an implanted contact to these clean variables is unvalidated.
2. **Why two channels?** Sine and cosine carry phase around an entire cycle. The quadrature construction makes circular estimator error inspectable.
3. **Why circular error?** A phase near 2*pi and a phase near zero can be close. Ordinary subtraction can call that difference almost a full cycle; wrapping gives the relevant discrepancy.
4. **Why compensate delay?** An observation describes an earlier point in the rhythm. Prediction advances it using estimated frequency. Incorrect frequency or delay makes that advance wrong.
5. **What is calibrated?** Four artificial inputs estimate learner response gain. Delay compensation is separate. The uncalibrated comparison changes both, so its difference does not isolate gain alone.
6. **What does an expert supply?** A target timing/trajectory relationship in task coordinates. The controller computes a learner-specific correction rather than replaying an expert voltage.
7. **What is learning?** The model updates an intrinsic scalar state with a prescribed rule. Its teaching-benefit parameter, beta, is not fitted to biology.
8. **What is retention?** Final intrinsic state is multiplied by a presumed 0.97 factor and evaluated without assistance. No elapsed retention interval is measured.
9. **What does beta=0 show?** Ordinary practice still updates the learner while extra assistance benefit is removed. Online performance can improve without changing retention.
10. **Why is 1.685 not a human forecast?** It is a threshold ratio produced by a positive-beta update law and an illustrative criterion. It demonstrates an assumption's consequence, not its truth.

Write a prediction before changing beta. Compare 0, 0.4 and 0.8. Then change actual delay while holding assumed delay fixed. Explain phase error, online error and retained error separately. Keep original outputs intact and record a new configuration for your revision.

## Physiological model checkpoints

Externally measured mean arterial pressure is regulated. The actuator is normalized; it is not a conversion from mmHg to stimulation dose. Pressure relaxes toward a synthetic baseline, disturbed by posture and modified by a delayed actuator state. Time constants and gains are prescribed rather than fitted to participants.

A proportional term reacts to present error. An integral term accumulates persistent error. Bounds constrain the command, and conditional integration reduces windup. A slew limit makes nominal changes gradual; sensor inhibition overrides that ramp for stale or invalid observations.

Main MAE is computed over 40 <= t < 159 s; the disturbance begins at 20 s. The initial dip belongs in an honest explanation even though it is outside that scoring window. The whole-trace minimum exposes it. A large nominal error reduction does not mean pressure was held throughout the episode.

The low-gain and actuator-cap cases show an authority limit: maximum input may not balance the disturbance. Sensor faults show another limitation: inhibiting output avoids an unchecked command in software but permits pressure to fall. This fallback is a digital rule, not a clinical recommendation.

In the current source, nominal setpoint also serves as plant equilibrium baseline. Changing it shifts both together; this is not a clean independent target-tracking test. To ask that question, create a revision separating baseline and target, explain the changed equations and compare with the original.

## Electronics checkpoints

Trace each net by function: power and reference, artificial signal input, amplification/filtering, external measurement output, current regulation, polarity selection, inhibit and electrical load. Explain which parts are real component selections and which simulations idealize behaviour.

Calculate 100 microamperes times 200 microseconds = 20 nanocoulombs per phase. Calculate 100 microamperes times 1 kilohm = 0.1 V. Then explain why the latter is not the entire compliance requirement: switching resistance, current-source headroom and electrode polarization add voltage requirements.

Opposite phases should have equal delivered areas. A command can be symmetric while load current is asymmetric if a phase clips or fails. Explain how inhibit defaults, dead time, compliance flags and fault tests address different concerns. These calculations do not establish tissue safety or qualify an implant.

Explain the recorded circuit revision: a generic SPICE reversal peak of 1.361 mA prompted two 12 kilohm output-leg resistors; the revised nominal model peak is 102.58 microamperes. The added resistance reduces compliance. Its simple short-load bound assumes no stored polarization, so it is not a universal current cap. Compare the conservative 2 V fault estimate with the actual generic-model precharge runs and explain why they differ.

The representative acquisition circuit does not contain a populated multichannel ADC or complete implant controller. The external sequencer and application simulation are different abstractions. They should not be presented as a fabricated real-time device.

## CAD checkpoints

Explain millimetre coordinates. The board is 80 x 50 mm with hole pattern +/-30 by +/-15 mm relative to its centre. Show how enclosure mounts use the same contract. Identify floor, wall, lid, ports and mounting plane. Check a source dimension instead of estimating it from perspective.

Explain what a valid solid can prove. It supports export and numerical geometry; it does not establish printed fit, sealing or cable fatigue resistance. The case is a desktop reference and leads are illustrative.

## Questions an examiner might ask

| Question | A defensible answer |
|---|---|
| What have you demonstrated? | Reproducible declared models, reference circuits and geometry; no biological efficacy |
| Why spinal access? | Named movement and sympathetic tasks have bounded prior evidence for spinal access |
| Why not body sensors alone? | They are allowed; invasive sensing must eventually prove added information or function |
| Is this a BCI? | Proposed neural access is spinal; cortical brain–spine examples are labelled hybrids |
| Did you invent spinal interfaces? | No. Contribution is this architecture, implementation, assumptions analysis and presentation |
| What is the weakest learning assumption? | Positive durable assistance benefit beyond practice; beta is assumed |
| Why a simple model? | It exposes assumptions and failure conditions; fidelity is a separate question |
| What limits pressure claims? | Unknown biological dynamics and authority; a numerical plant does not prove patient efficacy |
| What did AstroSam contribute? | Inspiration for connecting concept, electronics, software and enclosure |
| What did AI contribute? | Research, formulation, implementation, design and writing assistance; own contributions must be documented |

## A personal contribution record

For each meaningful revision record its date, question, prediction, source/reason, changed files, run settings, result and interpretation. Add what surprised you and what remains uncertain. Do not backdate work or describe an AI-supplied derivation as independently discovered.

A useful first contribution is an ablation separating gain calibration from delay compensation, or pressure baseline from target. Both address an interpretive issue and can be explained clearly. The goal is to understand why results change rather than make every plotted line improve.
