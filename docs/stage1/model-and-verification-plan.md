# Stage 1 — mechanism model and verification plan

**Date:** 8 October 2026. **Status:** proposed specification for the full SCCI overhaul; no new model implementation, experiments or verification runs are reported here. Release 1.0 results remain evidence only for their original subsystem abstractions. This plan implements the staged scope in [overhaul-plan.md](../overhaul-plan.md). The associated [verification matrix](verification-matrix.csv) defines specification checks and later work, rather than reporting that those checks have passed.

The intended digital proof is a connected, inspectable mechanism. It must show what information reaches electrode contacts, what a causal decoder can infer, how an expert-derived representation can guide a particular learner, what electrical stimulation is actually delivered in the model, and what follows under an explicitly uncertain biological response. A successful digital design need not produce a positive learning or physiological result. It must make its outcomes traceable without supplying unavailable information or hiding favorable assumptions.

## 1. Decisions that remain open

The first motor task is not selected by this document. Upper-limb/finger coordination and lower-limb coordination remain candidates. Each candidate must define its task outcome, degree of freedom, relevant spinal region, observable state, usable external measurements, proposed stimulation response and learning/retention question. A single rhythmic scalar is a possible reduced model only if it answers the selected task's mechanism question; it does not determine the project scope.

Physiological candidates also require a target-specific comparison before commitment. Mean arterial pressure (MAP) regulation during a stand-like disturbance is a concrete candidate because the existing release provides a reusable software scaffold. That is not a reason by itself to select it. A triggered response, repeated response and maintained state are different control objectives and require different observations, pathways and failure criteria. Other candidates must specify these links just as explicitly.

The Stage 1 checkpoint should review a reasoned recommendation for the representative motor task and physiological target, permitted external sensors, placement alternative, and implant/companion responsibility split. Final contact count, channel count, dimensions, component selection, sampling rate and stimulation limits follow the mechanism and budgets. The old eight-contact geometry and desktop enclosure are reusable provisional assets, not fixed requirements.

## 2. One causal chain with separate evidence boundaries

The proposed model has this chain:

**Declared task/body state → spinal population/source hypothesis → electrode forward observation → protection/acquisition/ADC → causal decoder and uncertainty → expert learned representation + learner response identification → bounded application controller → electrical driver/routing → measured delivered waveform → uncertain recruitment/body response → external and spinal feedback.**

The offline expert library is a separate input. It is trained from declared expert observations and reference measurements; it cannot inspect a learner's hidden test state. A model evaluator may inspect hidden truth to score a test, but the decoder, calibration routine, controller, firmware and command-admission path may not.

The electronic module and interface proposals provide the partition: electrode interface, AFE, ADC/clock/buffer, local estimation/calibration, application controller, command admission/sequencing, driver/routing, independent delivery monitor, independent supervisor, power, telemetry, companion/external sensing, and offline expert library. Interface proposals S1-IF-03 through S1-IF-12 distinguish electrode volts, digitized timestamped samples, estimates with confidence, external measurements, control intent, pulse plans, measured delivery, artifact ledgers and fault requests. These IDs are proposed contracts, not evidence that modules already exist.

### Information permissions

| Information | Simulator/evaluator | Decoder or controller |
|---|---|---|
| True task phase, unobserved neural source state, true recruitment parameters | May generate and score data | Forbidden unless explicitly provided in an oracle comparison |
| Generated contact voltages after acquisition/ADC | Available | Available with timestamps and quality masks |
| External movement/pressure measurements | Available | Available if that comparison's sensor contract permits them |
| Task goal and declared instruction | Available | Available; distinguish a known goal from achieved state |
| Expert training recordings and reference measurements | Available | Only through the frozen declared training/representation pipeline |
| Learner calibration observations | Available | Available within the stated calibration budget |
| Future samples, future perturbations, test outcome labels | Available for evaluation after the event | Forbidden during online decisions |
| Delivered current/voltage monitor observations | Available | Available with modeled sensor error/latency; commanded current is not a substitute |

Reference labels for training must be stated: for example, external movement measurements or other declared task observations. Direct supervised access to an unobservable latent biological variable is an additional assumption, not a free label. Data from the same performance, learner or context must not leak between training and held-out evaluation merely through overlapping windows.

## 3. Forward spinal observation and causal decoding

### Source and electrode models

The latent task/body model must describe only the states needed for the selected mechanism. Candidate source classes include task-related neural drive, sensory/reflex feedback and background activity. These are **synthetic source hypotheses**. Source identity, separability and causal timing are open assumptions until supported for the chosen placement.

A useful contact-level starting equation is

\[
v_i(t)=\sum_j (H_{ij} * s_j)(t)+c_i(t)+n_i(t)+a_i(t;I_{del},r_{stim}),
\]

where \(s_j\) is a declared source waveform, \(H_{ij}\) is a geometry-dependent transfer/lead-field approximation, \(c_i\) is common-mode or motion interference, \(n_i\) is recording noise, and \(a_i\) is stimulation artifact driven by **delivered** current and routing. The source and transfer units must be consistent so \(v_i\) is in volts. A quasi-static or lumped lead-field approximation may be used if its assumptions and missing anatomy are explicit. It must not imply neuron-level resolution or access to identified descending commands.

The AFE/ADC model then adds gain, filtering, input impedance, saturation/recovery, quantization, reference uncertainty, sampling timestamps, channel skew and invalid-data masks. The decoder receives these samples. Perfect quadratures cannot bypass this path. A simplified ideal observation may remain as an explicitly labeled upper-bound comparison.

The causal decoder can estimate task-relevant state from finite past history, with confidence and an abstention/fallback rule. Candidate features and estimators should be chosen after the signal mechanism is defined. No bidirectional/offline decoder may be presented as an online controller without accounting for its future-data access and latency.

### Identifiability is a first-class test

Include cases where different latent states produce similar contact observations, where recordings contain mainly redundant afferent information, and where artifacts or drift remove useful information. Do not assume a correct inverse merely because a forward model is available. The required outcome may be an uncertainty increase, failure to distinguish states, or inhibition. If external sensors perform equally well, report that finding rather than manufacture a spinal-recording advantage by giving the neural model privileged labels or lower latency without justification.

## 4. Expert representation and learner-specific intervention

### Expert information

Expert data should comprise multiple declared performances and contexts, paired with task outcomes/reference observations. For this digital project the data may be synthetic, but their population, generation rules and any genuine external source must be identified separately. The learned representation could encode a task-conditioned timing distribution, coordination relationship or predictive feature. It is not an expert voltage waveform transferred into another person.

The design must answer two distinct questions:

1. Does expert information improve a policy over adaptation using only the learner's own observations?
2. Do expert **spinal observations** add anything beyond expert task trajectories, external measurements or task goals?

A representation that simply reproduces a known trajectory answers neither question automatically. Expert information must be mapped into learner-specific coordinates using observations and calibration; electrode-to-electrode identity across people is not assumed.

### Learner calibration and uncertain response

Define a latent learner response model with recruitment thresholds, sign/polarity conventions, cross-coupling, contextual dependence, delay, saturation and variability at the necessary approximation level. A linear response matrix may be a local surrogate, but its validity range must be declared. Its true coefficients belong to the simulator, not the controller.

Identification uses bounded calibration inputs and observed task/sensor changes, together with the modeled measured electrical delivery. The learner-specific map must retain uncertainty and be evaluated on held-out input/context combinations. Unidentifiable directions, incorrect sign mappings, non-monotonic responses and inadequate authority must be explicit failure cases. The controller should not silently solve them by accessing true parameters.

Include an explicit sensory-interference pathway where stimulation changes the feedback available to the learner or decoder, rather than only adding useful motor drive. A smaller task error during assistance can coexist with degraded sensory information, altered coordination or worse subsequent learning. Recording artifacts, sensory disruption and recruitment cross-coupling are distinct effects and should not be collapsed into one generic noise term.

The proposed controller uses the task goal, decoded state distribution, external measurements when allowed, frozen expert representation and identified learner response to request a bounded intervention. The request is admitted or rejected by the electrical/timing/fault layer. A signed desired task correction is not equivalent to a current polarity, and a normalized policy output is not equivalent to a stimulation dose.

## 5. Assistance, adaptation, retention and transfer

Online task performance with assistance and assistance-free learning outcomes require separate trials and metrics. The surrogate learner's own policy/adaptation state may be modeled, but the SCCI_RH controller cannot read that internal state directly.

A candidate artificial adaptation family is

\[
\theta_{k+1}=\theta_k+\eta\,\mathcal E_k\,\delta_k,
\]

where \(\theta\) is the surrogate learner's internal controller, \(\mathcal E\) is a declared eligibility/history term, and \(\delta\) is a task/prediction error available to that surrogate through its specified feedback. This is an **assumed learning model**, not a validated human plasticity law. The exact form follows the selected task and must be specified before examining comparative outcomes.

Use multiple coupling assumptions: favorable transfer, zero stimulation-related learning benefit, harmful/dependent learning, and insufficient observability/authority. Assistance can reduce useful practice error or create dependence, rather than necessarily accelerate learning. Do not multiply a baseline learning rate by a desired speed-up and describe the result as evidence for achievable acceleration. Replacing that coefficient with a more elaborate equation does not remove model uncertainty.

Retention is evaluated by task performance after assistance is off. State reset, washout, simulated forgetting and any elapsed-time model must be declared. Transfer requires a held-out task context or perturbation, not the same training trajectory. If acquisition thresholds are used, define task-specific units and criteria before trials; report non-crossing/censoring. No fixed 1.5× or 2× outcome is an acceptance requirement.

## 6. Comparisons that can distinguish useful information

The core motor study is a factorial comparison, not only assisted versus unassisted:

| Sensing | Expert-informed policy | Learner-only adaptive policy |
|---|---|---|
| External sensors only | Tests expert contribution without spinal sensing | Baseline using task goal and learner calibration/practice |
| Spinal plus the same external sensors | Tests combined architecture | Tests the incremental value of spinal input without expert transfer |

Add an expert external-trajectory-only representation to separate expert neural content from ordinary task information. Where practical, an explicitly neural-only condition can clarify reliance on external sensing, but is not required if the mechanism legitimately uses both.

Across paired conditions, hold constant learner/context draws, task instructions, practice exposures, calibration effort, actuator constraints, disturbances, permitted external observations, evaluation trials and model-selection effort. Distinguish offline expert-resource cost from learner practice; disclose it rather than concealing extra expert data. Record sampling rates, time alignment, communication latency and computation differences so a sensing comparison does not accidentally compare unrelated hardware advantages.

Negative controls include shuffled expert/context associations, shuffled or removed neural information, an incorrect learner map, mismatched electrode/source geometry, unknown latency, saturated acquisition, stimulation artifacts, source drift, sensor/link faults, and insufficient recruitment/control authority. Oracle state/response access is a diagnostic upper bound only. No-superiority, mixed, zero and harmful outcomes are valid scientific results.

Predeclare the primary task metric, online-versus-retained contrast, incremental neural-information contrast, incremental expert-information contrast, and failure criteria. Later simulations should use paired seeds and raw traces. Quantify Monte Carlo variability separately from structural/biological uncertainty, and do not treat more synthetic trials as evidence that the assumed biology is correct.

## 7. Target-specific physiological feedback

After candidate selection, define one output, one requested behavior, the observed state, the accessible intervention route and adverse/unreachable states. A MAP worked example would use an external pressure measurement in mmHg, a declared disturbance/context, and a recruitment-to-pressor-response model. It would not claim blood pressure is read directly from spinal voltages.

The required stimulus-to-response chain is

**Measured delivered current, pulse width, frequency and route → uncertain recruited population/response state → target-specific physiological dynamics → external measurement with noise, bias, delay and validity.**

The response can be nonlinear, saturating, delayed, sign-changing or context-dependent at a selected reduced-order approximation level. An unknown stimulation gain is estimated or bounded rather than supplied perfectly to the controller. Models with no accessible influence, too little authority, adverse direction or multiple outputs affected by the intervention must be included.

Spinal recording is an optional additional observation only if the specification names a relevant observable and what it contributes. Compare the same controller with and without that input. External-sensor-only stimulation feedback can be a meaningful spinal-intervention architecture even when recording adds no advantage. A shared SCCI platform does not imply every application needs useful recording from the same contacts.

Report sustained regulation, transient dips/overshoot, response onset/termination, actuator effort, off-target effects represented in the model, and command/delivery failures separately. Inhibition during a sensing fault may sacrifice physiological support; it must not be called universally safe. Clinical targets, doses, autonomic selectivity and human safety are not established by these digital calculations.

## 8. Full digital electronics and feedback integration

The later demonstrator must use one declared timebase or quantified clock translations. Contact observations pass through acquisition/ADC into timestamped buffers; processing creates state estimates and requests; scheduling/driver/routing creates an electrical waveform; independent modeled monitors estimate delivered current, voltage, charge and compliance; that delivery drives the assumed recruitment/body model. The resulting task/body state generates the next feedback samples.

Required contracts carry units, channel/route identity, timestamps, uncertainty, validity, saturation/quality flags and interface versions. Recording contact count, sampled ADC channel count, independent stimulation driver count and simultaneous routing configurations are distinct quantities. Monitoring cannot declare perfect delivered charge by repeating a commanded-current value.

Reboot, link loss, stale data, invalid frame/route, missed timer boundaries, power sag, interrupted balancing phases, compliance clipping, abnormal electrode impedance/polarization and artifact recovery need defined transitions and traces. The independent supervisor's responsibility must be distinguished from application software. Real-hardware behavior remains outside the entirely digital project's verified evidence even when the simulation includes selected real components.

## 9. CAD follows the mechanism

Anatomical placement alternatives must identify the structures to observe and influence and keep recording and stimulation placements distinct when their evidence differs. Selected contact geometry/count and interconnect mapping follow source observability, recruitment selectivity, routing and electrical budgets. Parameterized anatomical references require provenance and variation ranges; geometry alone does not establish anatomical fit, chronic compatibility or tissue safety.

Mechanical deliverables later separate the **future implant/lead concept**, any required companion, and **desktop/test equivalents**. Native populated-board assemblies use selected component/connector/feedthrough envelopes, actual channel mapping, cable bend/strain-relief assumptions, mounting and tolerance budgets, and power/thermal constraints. An implant package is not a renamed desktop shell. A generic cable opening is not verified connector fit. A valid CAD solid is not evidence of hermeticity, biological compatibility or surgical feasibility.

## 10. Verification and Stage 1 exit

The matrix uses stable IDs grouped by scope: S1-V-001–010 specify Stage 1 consistency; 101–114 cover computational mechanisms; 201–204 cover quantitative architecture; 301–309 cover electronics/embedded integration; 401–405 cover mechanical development; 501–504 cover the integrated release; and 601–604 identify biological evidence that the digital project cannot supply.

Stage 1 is ready for review when both ambitions have complete proposed causal chains, controller-observable permissions are explicit, candidate task/target/placement recommendations are justified, comparisons can isolate spinal and expert contributions, assumptions and unclosed interfaces are registered, and later verification has defined objectives and evidence boundaries. Numeric tolerances still needing evidence are marked unresolved and scheduled for Stage 2; they are not silently set to guarantee success.

The matrix's future pass criteria refer to the declared model/engineering contract. They do not require that an intervention succeed biologically. A model may correctly reveal that its selected interface cannot identify a state or control a target; that failure is a result to report and may require an architecture revision. Actual new experiments, retained human skill, chronic recording, tissue safety and clinical efficacy remain outside the evidence generated by this project.
