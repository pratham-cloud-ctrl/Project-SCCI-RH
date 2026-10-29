# Project SCCI RH: full SCCI system overhaul

Planning baseline: 8 October 2026; status refreshed 16 October. Stages 1–2 and
Stage 3's conservative investigation/conditional concept are complete within
their stated scopes. Stage 4 now supplies complete native circuit integration,
bounded actual target firmware and eight genuinely routed populated boards.
The historical connected pilot retains its unfavorable active-assistance result;
the conditional future mechanism remains explicit. Stage 5 mechanical packaging
and Stage 6 illustrated paper/release follow. This programme preserves the main
ambition without treating a digital reference as a qualified human implant.
See [current status](../CURRENT_STATUS.md) and the [Stage 4 exit review](stage4/exit-review.md).

## The intended deliverable

Project SCCI RH is an entirely digital research and engineering project that gives
the 28-page SCCI concept a complete proposed technical embodiment. AstroSam's
Mind-Link inspires the progression from future vision to inspectable engineering.
The central object is an invasive spinal interface and its computing/control
system, with acquisition, interpretation, personalized stimulation and feedback.

The project preserves both expert-informed motor learning and selected
physiological automation. It also retains the paper's broader medical and consumer
possibilities in a capability map. Each capability must name its required
information, accessible pathways, intervention and outcome. A shared platform
does not imply one electrode placement can serve all functions simultaneously.

The future concept may use an explicitly assumed biological interface. Its
assumptions must specify measurable information, controllable outputs, latency,
selectivity and limits. Engineering should be designed around those interfaces.
No favorable biological result, unlimited control or acquisition multiplier is
made true merely by declaring an ideal interface.

The completed digital architecture should explain and connect electrode
interfaces, acquisition, conversion, processing, stimulation, monitoring, power,
communication, mechanical packaging and application control. Original synced
sources remain read-only. No physical implantation, fabrication or participant
testing is part of this project. Video and website work are outside this overhaul.

## What changes from release 1.0

Release `v1.0.0` remains a historical subsystem reference. Its tests and results
apply to its declared models and geometry. They are not evidence that the new
implant system is complete. The overhaul lives on `overhaul/full-scci-system`
until its required design and verification work is complete.

| Area | Useful existing work | Required overhaul |
|---|---|---|
| Research | Starting paper, selected primary references, evidence and claim registers | Reconstruct both causal mechanisms and evaluate architecture alternatives; review the full consumer/medical vision |
| Motor model | Seeded trials, timing/noise studies, retention separation, negative controls | Model observations generated at electrode contacts; represent expert information; identify learner responses; remove unavailable ground-truth access from the controller |
| Physiological model | Bounded feedback, rate limits, freshness gates, weak-authority cases | Connect delivered stimulation to an uncertain recruitment/response model; justify the selected regulated function |
| Learning mechanism | Explicitly labelled assumed benefit and zero-benefit comparison | Test adaptation rules under favorable, zero and harmful coupling; do not insert a desired speed-up and report it as a discovery |
| Electronics | Native KiCad generation, signal-chain analysis, current-servo concepts, charge/compliance studies, revision history | Full multichannel acquisition and ADC, embedded processing, programmable stimulation/routing, monitoring, power, telemetry and fault supervision |
| Firmware | Portable C scheduling and fault tests | On-device responsibilities, peripheral interfaces, buffering, timestamping, application modes and timing integration |
| Mechanical design | Parametric solids, board registration, export and intersection checks | Mechanism-derived lead/contact geometry, implant/package and companion device concepts, populated component envelopes, connectors and mechanical interfaces |
| Paper/repository | Reproduction scripts, source files, results, attribution and provenance | Clear design status, system-level evidence traceability, readable technical figures, complete manuscript and native design handoff |

The existing single-ended amplifier is an artificial-signal reference. The fixed
current dummy-load board is not relabelled as a complete implant. The previous
eight-contact geometry and 100 x 70 mm desktop shell are provisional choices to
reopen, rather than constraints on the new architecture.

## Reviewable progress as of 8 October 2026

[Stage 1](stage1/README.md) specifies mechanisms and requirements.
[Stage 2](stage2/README.md) supplies quantitative architecture, contracts and
preliminary native geometry. Its [progress table](stage2/verification-progress.csv)
keeps identified functional authority open for Stage 3 rather than declaring
biological reachability from electrical arithmetic. Stage3 now has implemented
reduced full-loop studies and independently reviewed failures; its
[progress record](stage3/verification-progress.csv) remains partial. Complete
circuits, populated CAD and integrated manuscript remain later.

## Stage 1: mechanism, scope and requirements

Build a full-device specification before choosing final components or dimensions.

- Trace expert recordings through a task-relevant representation, learner
  calibration, intervention, active practice and retained unassisted outcome.
  Define what expert neural information contributes beyond task trajectories or
  an adaptive learner-only controller.
- Map physiological candidates to observations, controllable pathways and
  requested behavior: regulation, a triggered response, repetition or sustained
  influence. Compare candidates before committing the first worked example.
- Compare motor task families, including upper-limb/finger and lower-limb
  coordination. The anatomical and information requirements determine the design;
  the existing rhythmic surrogate does not determine the project's ambition.
- Define the biological-interface assumption, architecture alternatives, operating
  modes and responsibilities of implant, companion and application software.
- Separate published evidence, engineering requirements, biological hypotheses,
  idealizations and digitally verified quantities in a common register.
- Establish provisional signal ranges, units, timing requirements and acceptance
  criteria; identify which values still require primary-source investigation.

Deliver: system requirements, application/mechanism diagrams, capability map,
assumptions register, architecture trade study and verification matrix.

Completion: both ambitions have a traceable measurement-to-outcome mechanism;
every required function has an owner and interface; unknown links are explicit;
representative applications and architecture have a reasoned recommendation for
review. This stage does not claim biological efficacy.

## Stage 2: quantitative architecture and interface contracts

Resolve acquisition and stimulation topology, compute partition and channel
scaling. Distinguish electrode contacts, sampled ADC channels, independent output
drivers and simultaneous stimulation configurations.

Calculate signal/noise and dynamic-range budgets; sampling and data rates;
buffering, computation and memory; latency, synchronization and artifact recovery;
driver compliance and delivered charge; power, energy, heat and communication.
Include provisional mechanical envelopes and feedthrough/connector requirements
so board and package development can proceed together.

Deliver: selected architecture, interface contracts, budgets, timing diagrams,
state/mode definitions and preliminary implant/companion envelopes.

Completion: budgets close with declared margins and uncertainty cases, or a
specific architecture change resolves the gap. No module silently supplies
unavailable information, free energy, instantaneous communication or unlimited
stimulation authority.

## Stage 3: computational mechanism and full-loop demonstrator

Generate contact observations through a declared neural-population/electrode
forward model. Include noise, drift, stimulation artifacts, ambiguous states and
train/test separation. The decoder receives observable samples, not hidden true
phase or learner state. Any oracle comparison is explicitly labelled.

Construct expert representations from declared expert data or synthetic expert
performances. Identify learner response from calibration with uncertainty. Model
stimulation recruitment and task response at an appropriate approximation level.
Artificial adaptation can produce benefits or harms, but remains an assumed model
of learning rather than proof of human plasticity.

Compare neural-plus-external sensing against external sensing alone, and
expert-informed policies against learner-only adaptation with fair practice/data
budgets. Include shuffled information, incorrect mappings, zero-benefit and harmful
coupling, latency, saturation, sensor faults and insufficient control authority.
Assess online assistance, unassisted retention and transfer separately.

Deliver: mathematical specification, implemented models, raw results, comparisons,
sensitivity/failure studies and application interfaces ready for electronic models.

Completion: one generated spinal observation can be traced through interpretation,
command and modeled body response for each selected application; information
leakage and desired outcomes are not hidden in the implementation. A negative or
mixed result is a valid outcome.

## Stage 4: complete electronics and embedded control

Choose devices against the budgets and develop readable native KiCad schematics
for neural acquisition/protection, ADC and synchronization, embedded computation,
programmable stimulation/routing, current/compliance monitoring, power and
communication, and independent fault supervision. Develop firmware modules and
the hardware abstraction needed to exercise them digitally.

Connect acquisition/filter/ADC models to estimator inputs and connect pulse
commands to modeled delivered current, electrode load and biological abstraction.
Use shared timing, explicit units and data formats. Recheck actual integrated
charge rather than infer it from symmetric commands alone.

Deliver: complete schematics, layout/board revisions, BOM, selected device
documentation, firmware architecture/implementation and electrical simulations.

Completion: electrical blocks and native netlists are consistent; recording and
stimulation coexist within declared artifact/recovery limits; load/compliance and
timing faults are exercised; link loss, reboot, interrupted pulses and power faults
have specified responses. Digital circuit checks are scoped to their models.

## Stage 5: implant and companion engineering CAD

Co-design populated board envelopes with the package and mechanical interfaces.
Model the proposed implant housing, feedthroughs, contacts/leads, attachment and
strain relief, and any required companion. Tie lead geometry and channel mapping
to the mechanism and electrical design. Document selected materials and anatomical
reference assumptions; geometry alone does not establish tissue compatibility.

Use parametric engineering CAD and native assemblies, matching pinouts, component
models, cable envelopes and interfaces. Produce assembly views, dimensions and
tolerance assumptions. Revise electronics when the package exposes a conflict.

Deliver: native engineering assemblies, parametric sources, STEP/STL, drawings,
component/lead mapping and nominal interference checks.

Completion: the proposed system has a mechanically coherent body; real selected
components and connectors fit its nominal geometry; modeled implants and external
equipment are clearly identified. Anatomical fit, chronic durability and sealing
claims remain tied to their actual evidence and analysis.

## Stage 6: integrated verification, paper and GitHub delivery

Run the complete digital signal path: declared spinal sources -> electrode
observations -> acquisition/ADC -> embedded decoding/control -> stimulation driver
-> delivered current -> modeled response -> feedback. Audit timing, energy,
interface versions, fault responses and every headline claim.

The manuscript develops throughout the project. Its final form combines the
original vision, evidence review, mechanism, equations, full architecture,
electronics and packaging design, comparative results, limitations and proposed
tests. Technical figures should expose the mechanism and actual design; presentation
polish follows substantive consistency. No fixed page count substitutes for coverage.

Deliver: illustrated paper and editable source, an organized private repository,
complete native design sources, reproducible results, design history, verification
receipts, citations, attribution and learning/defence material.

Completion: requirements and claims map to source/evidence/checks; digital
integration is demonstrated under stated assumptions; unresolved biological links
are stated precisely; source and exports agree. Only then is a new full-system
digital design release described as complete.

## Working method across prompts

Each work package ends with concrete artifacts, the checks executed, remaining
uncertainties and the next bounded task. `CURRENT_STATUS.md` records continuation
state in the repository. Requirements, assumptions and decisions are versioned.
Large choices are presented with a recommendation and trade-offs; routine research,
coding, checks and edits proceed within the authorized scope.

Scope checkpoints are reviews of actual work: mechanism/architecture selection,
quantitative design, electronics/mechanical integration and final release. They
are not repeated requests for permission to perform already authorized work.
The owner can steer task choice and review understanding between packages.

Work can span multiple prompts without restarting. Effort is judged by resolved
engineering questions and verified artifacts, rather than token expenditure. Video
and website are parked; they do not determine the technical design or acceptance.
