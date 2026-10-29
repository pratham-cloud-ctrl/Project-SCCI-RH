# Understanding and defending the integrated Project SCCI RH

This guide supports learning after the digital release. Read the manuscript and
open the native designs, then explain them in your own words. A polished file set
does not prove that you understand it. Keep predictions and personal revisions
in the [contribution record](contributions.md).

## The project in one minute

SCCI_RH proposes an implanted spinal recording and stimulation platform. It asks
whether task-relevant spinal information and individualized stimulation could
help practice produce better later unassisted movement, and whether a selected
physiological response could be maintained using feedback. It builds a digital
engineering account of those mechanisms: evidence, explicit future assumptions,
models, electronics, executable target firmware and CAD. AstroSam's Mind-Link
inspired the progression from an ambitious vision to an inspectable engineering
body. SCCI_RH has no human recordings, fabricated implant or proven consumer benefit.

## Explain a theoretical user session

**Motor practice.** A learner selects a defined coordination drill and an expert
reference. Expert performance supplies timing/coordination in task coordinates,
aligned to the learner; the reference is not a transferable voltage waveform.
Calibration identifies the learner's useful observations and reachable response
directions. While the learner actively attempts the movement, a local policy
estimates state and selects bounded, timed stimulation. Delivery monitoring
checks the electrical action; independent movement measurements check the
behavioral result. Later pulse-free OFF trials test what remains without help.
Faster retained learning requires an additional favorable adaptation mechanism;
temporary assistance alone does not establish it.

**Physiological support.** A target-specific configuration pairs individualized
lower-thoracic stimulation with external pressure measurement in the selected
pressure-support example. The controller uses fresh pressure and calibration to
adjust a bounded pressor programme, while delivery monitoring checks its action.
Loss of valid sensing, inadequate authority or altered response can inhibit or
withdraw support. Removing positive pressor drive does not give arbitrary active
pressure-lowering authority. Optional spinal context/evoked-response sensing is
a separate hypothesis; spinal recording has not been shown to replace the blood
pressure sensor here. The SCI precedent does not demonstrate healthy-consumer
benefit or universal autonomic control.

Modes and lead placements are target-specific. A shared controller does not mean
one contact array can read or control all spinal functions simultaneously.

## Trace one full command path

1. Start at an identified observation: artificial raw contact data, a causal
   model feature or an external measurement. State which abstraction you are
   using and its support time, arrival time and quality.
2. Follow acquisition/protection, interpretation and calibration into a policy.
   Identify unavailable or stale data and the conditions under which the system
   should withhold output.
3. Trace one source, held route, waveform/phase request, independent permission
   and supervised terminal connection through the actual native schematics.
   Body-facing stimulation contacts are downstream of the guards.
4. Distinguish commanded current from measured delivered current, phase charge,
   compliance and a modeled biological response. Show which failures latch the
   system and which explicit rearm is required.
5. Follow the returned observation. Separate electrical delivery feedback from
   a movement or pressure outcome, and assistance from retained adaptation.

Use the [board index](../../electronics/stage4/integrated-pcb/BOARD_INDEX.md),
[integrated design](../stage4/integrated-pcb-design.md) and
[mechanical index](../../cad/stage5/README.md) while doing this. The 36-port body
map ends at protected electrical boundaries: recording/reference/bias are
distinct from stimulation/returns. The body bias is not a stimulation return.

## Numerical facts to understand, with their scope

| Fact | What you should explain |
|---|---|
| 16 differential recording streams and two physical stimulation sources | Contact selection is not sixteen independent simultaneous stimulation sources; nominal planned rates differ from implemented firmware |
| 1,298 positions / 1,296 fitted on eight native routed boards | Two optional driver capacitors are DNP; source/pad/parity and population are separate checks |
| 80 master sheets and 258 harness rows | Electrical identities, independent rearm signals and domain returns must survive integration |
| Actual target profile: nominal 100 us monitor opportunities and 1 ms neural frames | Polling gaps remain; this is not continuous 450k aggregate / 4k acquisition or measured hardware timing |
| Current target acquires RHD recording frames only in OBSERVE mode | The new host replay supplies conditional spinal features and companion plans; it does not demonstrate implemented live spinal decoding during active target stimulation |
| 53,648-byte flash and 98,000-byte RAM extents | A target-linked image is stronger than a host-only test, but neither proves execution on a physical board |
| Conditional 3.154 W / 4.880 h resource allocation | A calculated reference budget is not a measured battery runtime or a closed implant thermal design |
| 600 x 310 x 240 mm reference chassis, including feet | It packages the actual large boards at true scale |
| 60 x 58 x 14 mm future can/header, before leads | It expresses a separate future body; its internal allocations require redesigned electronics |
| 260 combined reference objects; 230 future physical solids plus six allocations | Valid native geometry and export parity are digital geometric evidence |
| 36 body ports | Sixteen recording, reference and bias, sixteen stimulation and two returns have distinct identities |

Do not memorize counts as a substitute for tracing an example. Open an actual
board, find one component, follow a net, locate its housing in the CAD assembly
and identify the corresponding test or limitation.

## Results that deserve questions

The preserved conservative qualification branch withheld every active motor
intervention. Its all-withheld result is evidence about that branch's gates,
not proof that SCCI is impossible. A later conditional mechanism model makes
the assumed interface explicit. In 128 scenarios it can improve ON execution,
while favorable teaching improves OFF learning, neutral teaching leaves it equal
and dependence/adverse coupling can make it worse. Equal-information expert
spinal-labelled and external references match; a unique neural-information
advantage has not been established.

The pressure model reduces nominal disturbance error but retains large recovery
overshoot, failed calibration, inadequate authority and fault cases. A lower
single error score is insufficient to establish acceptable physiological control.
Explain the full trace, stopping behavior, biological assumption and scored window.

The historical 4% phase-charge monitoring target remains unearned. A compiled
event request and nominal amplitude scale do not establish delivered tissue
charge, analog accuracy or a biological response. The new integrated host replay
joins the production policy core to declared adapters; it does not execute the
target peripherals, eight physical boards or implant together.

The electrical and CAD reviews also contain real corrections: separate driven
rearm nets, an incorrect watchdog land pattern and four incomplete corner
feedthrough bores were corrected in new integrated artifacts. Earlier evidence
remains preserved. Find one correction and explain how its check detected it.

## Questions an examiner may ask

| Question | A defensible response |
|---|---|
| Is this a functioning implant? | It is a complete digital research/engineering concept within declared scope, with native reference designs and target-linked firmware; no physical implant was built or tested. |
| Why spinal access? | Specific spinal pathways offer task-related observations and causal recruitment precedents. Each selected task still needs suitable location, information and access. |
| Why not external sensors alone? | They are valid comparators and are used here. Invasive sensing must eventually demonstrate added information or a function that justifies it. The simple model does not establish that advantage. |
| What exactly does an expert transfer? | An aligned task-conditioned reference or representation; learner calibration converts error into that learner's permitted intervention. |
| What would prove faster learning? | Matched practice with credible controls, pulse-free delayed retention/transfer assessment and independently measured outcomes; ON assistance is insufficient. |
| Why allow an unproved assumption? | It permits a coherent conditional concept if evidence, mechanism, consequence and falsifier are explicit. The resulting simulation does not validate the premise. |
| What is the weakest motor premise? | A useful additional adaptation term that persists after assistance and adds benefit beyond ordinary matched practice. |
| Can the pressure mode automate any organ? | No. It uses a named pathway, measured state, response direction and bounded authority. Every other function needs a separate causal argument and configuration. |
| Does stimulation always reverse a movement error? | No. Task-error sign is not electrical excitation/inhibition; a calibrated reachable response is required and can drift or fail. |
| What does zero ERC/DRC mean? | Saved circuits and boards pass the selected digital connectivity/layout rules, including parity and unconnected checks. It does not establish analog, isolation, thermal or biological performance. |
| How can the big boards fit the small can? | They do not. The real reference remains full size; the small future package explicitly assumes a new miniaturized implementation. |
| Does symmetry guarantee balanced dose? | Symmetric commands can clip or fail asymmetrically. Actual delivered phase areas and uncertainty need independent observation. |
| Is the radio implemented? | No. The current carrier firmware has no radio/network-core image; the future window and antenna are conditional allocations. |
| What is original? | This synthesis, mechanism analysis, models/controls, engineering implementation, traceable assumptions and inspectable documentation; spinal interfaces themselves are prior work. |
| What did you personally do? | Describe project direction and only the calculations, explanations or revisions you actually performed. Disclose extensive AI implementation/design/writing assistance. |

## Four bounded exercises for your own contribution

1. **Predict learning before running it.** Read the conditional model's teaching
   law. Predict why neutral teaching can improve ON execution without OFF
   advantage. Rerun a copied configuration and compare favorable, neutral and
   adverse assumptions without editing frozen evidence.
2. **Trace a fault.** Choose sensor staleness, route mismatch or phase timeout.
   Explain which component or software state observes it, what output changes,
   and why a fresh command must not silently clear the fault.
3. **Check an engineering allocation.** Recalculate one phase charge or a
   reference tray gap from source dimensions. State which tolerances and
   physical effects that arithmetic omits.
4. **Challenge one scientific premise.** Choose a named assumption, find its
   primary evidence, distinguish population/access/task from SCCI_RH's proposal,
   and write a feasible future test with a result that would reject the premise.

Record a prediction before each run or change, preserve the release outputs,
and commit subsequent revisions separately. The strongest portfolio discussion
shows how your understanding changed when a result contradicted your expectation.
