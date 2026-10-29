# The idea and how it could work

[Explore](README.md) · **Theory** · [CAD](cad.md) · [Electronics](electronics.md) · [Firmware](firmware.md)

**A future spinal interface that helps a person practise a movement or supports a selected bodily function through feedback.** Project SCCI RH gives that idea a mechanism, mathematical models, electronics, firmware and a physical design. Everything in this repository is digital; the proposed biological capabilities remain conditional.

This page explains the concept without specialist software. The [illustrated paper](../../output/pdf/Project_SCCI_RH_Integrated_Manuscript.pdf) develops the full argument, equations, experiments and references.

## Start with the loop

An SCCI is a **spinal cord–computer interface**. In SCCI_RH's future concept, implanted contacts record useful spinal activity. A computer estimates a selected state, chooses an individually calibrated intervention, and sends a stimulation request. Electrical monitoring checks delivery; independent movement or pressure measurements check what happened to the person. Those observations inform the next request.

![SCCI_RH system diagram: spinal recording feeds interpretation and a learner- or function-specific policy; monitored stimulation produces a response that is independently measured.](../../manuscript/stage6/figures/01_system.png)

The proposal separates **intradural surface recording**—contacts inside the dura, the membrane surrounding the cord—from **epidural stimulation**, outside it. Whether this combination can provide stable, useful chronic human access is an explicit premise. SCCI_RH does not require brain recording; brain–spine experiments are identified separately as hybrid precedents.

## 1. Expert-informed practice: learn with help, then test without it

Imagine selecting a precisely defined coordination drill in a future companion application. An expert's task-labelled recordings provide a reference for successful timing or movement. Your own calibration identifies how selected stimulation programs affect your movement. The system aligns the reference to you and offers bounded assistance during your active attempts.

The proposed session has five steps:

1. **Choose a drill and reference.** The target is a specific component, such as rhythmic coordination, with independent performance measurements.
2. **Measure your baseline.** Unassisted attempts establish your starting performance and calibrate reachable responses.
3. **Practise actively.** Useful spinal features and external movement measurements inform the learner-specific policy.
4. **Observe delivery and outcome.** The system distinguishes a requested intervention, delivered current and achieved movement.
5. **Remove assistance and reassess.** Later stimulation-OFF tests ask whether learning persists; transfer to another condition is a further question.

![Motor mechanism: expert performance and learner calibration inform bounded assistance during active attempts; assumed adaptation is tested through later stimulation-OFF retention and transfer.](../../manuscript/stage6/figures/02_learning.png)

**The expert contributes a coordination reference, rather than a voltage waveform to replay.** Whole skills such as piano or football would require multiple components, sensory strategies and decisions. The current model studies a cyclic movement component.

The most revealing result is that improved assisted execution can coexist with very different retained outcomes. In the integrated synthetic replay:

| Model arm | First practice error | Final unassisted error |
|---|---:|---:|
| Unassisted practice | 31.414 mm | 5.605 mm |
| Assistance; neutral teaching | 16.668 mm | 5.605 mm |
| Assistance; favorable teaching | 16.668 mm | 2.897 mm |
| Assistance; adverse teaching | 16.668 mm | 34.845 mm |

The three assisted arms begin with the same execution benefit. Their different assumed adaptation laws determine what persists. These are model outputs, not measured human learning rates. No 1.5× or 2× acquisition claim is established. See [the protocol and results](../../manuscript/stage6/manuscript.md#82-finite-results); the earlier four-seed study has its own distinct protocol and values.

## 2. Physiological feedback: support one measured function

The concrete second example is pressure support under a modeled disturbance, motivated by spinal-cord-injury research. A future user selects a calibrated support mode. An **external blood-pressure sensor** reports pressure, measurement time and quality. The companion controller requests bounded spinal stimulation through a function-specific response map, repeatedly checks pressure and withdraws added support when appropriate.

![Pressure mechanism: external sensing informs bounded feedback; protected stimulation produces assumed selective pressor recruitment with delay and a withdrawal tail.](../../manuscript/stage6/figures/03_pressure.png)

Here, **pressor** means pressure-raising. Reducing the command removes added drive; it does not give the system an independent ability to lower arbitrary high pressure. The response can also continue after current stops. Delay, saturation, overshoot and stale or missing measurements therefore belong in the mechanism.

The integrated toy model reduced pressure error while retaining approximately 10 mmHg of overshoot. Its selected target and gains are simulation coordinates, not clinical settings. The platform remains a bidirectional SCCI concept, while this loop measures pressure externally. Bladder and other functions are research comparators; each would need its own accessible pathway, measured state and control mechanism. This is a route toward selected physiological automation, without assuming universal body control.

## What the project establishes

| Layer | What viewers can inspect | What remains conditional |
|---|---|---|
| Biological rationale | [Primary-source evidence review](../stage6/evidence-review.md), including population and access distinctions | The complete proposed combination, useful human decoding and healthy retained-learning benefit |
| Computational mechanism | [Paper's study results](../../manuscript/stage6/manuscript.md#5-study-design-and-preserved-results), favorable/neutral/adverse cases and preserved abstaining results | Whether the assumed information, recruitment and learning response hold in a person |
| Reference engineering | Eight native KiCad boards, target-linked firmware and full-scale FreeCAD assemblies | Physical electrical performance, execution timing and chronic implanted qualification |
| Future implant identity | A separate compact package, leads, contact mapping and allocations | Miniaturized circuitry, heat, sealing and anatomical suitability |

The current firmware restricts neural acquisition to **OBSERVE** mode. It does not implement simultaneous live spinal decoding during motor stimulation. The larger eight-board reference also does not fit inside the compact future can. These distinctions keep the functional vision connected to the artifacts viewers actually open.

## Follow the mathematics and evidence

The model asks three approachable questions: **What information is available now? Which correction can this learner's calibrated intervention produce? What changes after assistance ends?** The pressure model additionally asks how delay and lingering activation affect feedback.

For equations, start with [observation and timing](../../manuscript/stage6/manuscript.md#41-observation-support-and-availability), then [expert alignment](../../manuscript/stage6/manuscript.md#42-expert-alignment-and-reachable-correction), [retained learning](../../manuscript/stage6/manuscript.md#43-assistance-and-retained-learning) and [pressure dynamics](../../manuscript/stage6/manuscript.md#44-pressure-dynamics-and-authority). For scientific support, use the [evidence review](../stage6/evidence-review.md) and [reference register](../stage6/references.json); published studies motivate individual links rather than proving all of SCCI_RH together.

AstroSam's [Mind-Link](https://github.com/sam-astro/Mind-link) inspired the progression from future concept to inspectable engineering. SCCI_RH develops its own spinal mechanisms and designs. The [contribution record](../stage6/contributions.md) identifies project direction, AI-assisted work and third-party research.

**Next:** [see the physical design](cad.md), [follow the electronics](electronics.md), or [inspect the implemented firmware](firmware.md).
