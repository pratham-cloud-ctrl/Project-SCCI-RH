# Physiological branch: a conditional spinal pressure-support concept

Research refresh: **13 October 2026**. This is a focused primary-source review and
design interpretation, not an exhaustive systematic review or a stimulation
prescription. The original 28-page paper was read as reference material; its
sections 14–15 and 22–23 already distinguish maintained pressure, other bodily
functions, direct physiological sensing and inferred spinal state. Its pages
16–17 and 24–25 support this direction without requiring every future subsystem
to have been demonstrated together.

**Design decision:** use external blood-pressure feedback as the primary
physiological measurement, targeted spinal stimulation as a proposed pressor
actuator, and separately labelled spinal recording as an optional source of
context or recruitment information. A spinal pressure decoder is a research
extension, not a prerequisite for the pressure-support concept. Undemonstrated
assumptions are permitted when their mechanism, consequences and failure
conditions are explicit.

## Primary experiments that anchor the concept

The six reports below are distinct evidence items, not six independent large
clinical validations. Early studies are small, participant independence across
publications must be checked before pooling, and stimulation location and indication differ.
Sample counts are reported for the relevant experiment rather than pooling
animal tests, implant cohorts, epidemiological surveys and repeated trials.

| Study and actual sample | Recording or sensing, stimulation and result | Limit and design implication |
| --- | --- | --- |
| **Harkema et al., 2018**, four people with chronic, motor-complete cervical SCI | A 16-contact epidural array covered L1–S1 **spinal segments**, at T11–L1 **vertebrae**. External finger plethysmography, calibrated against brachial pressure, guided participant-specific settings during five two-hour seated sessions. Pressure increased from hypotensive baseline while lower-limb EMG screened unwanted muscle activation. | Parameters were adjusted during sessions; this is not evidence for a fully autonomous spinal-recording controller. Individual mapping and independent BP sensing are useful architectural precedents. [Primary article](https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2018.00083/full) |
| **Aslan et al., 2018**, seven men with chronic C5–T4 SCI | External beat-to-beat BP, leg EMG and catecholamine measurements accompanied lumbosacral epidural stimulation. The three participants with hypotension and orthostatic intolerance showed pressure increases and improved standing tolerance; four without the same cardiovascular deficit did not show a further BP increase. | A single gain is not universal across people or states. The stimulation was configured for motor networks, not a purpose-built lower-thoracic pressure controller. [Primary article](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2018.00565/full) |
| **Phillips et al., 2018**, five people with motor-complete SCI: four cervical, one T2 | During an orthostatic challenge, externally measured BP and cerebral blood-flow velocity were assessed with thoracic **transcutaneous** stimulation between T7–T8 spinous processes. BP and several cardiovascular measures improved acutely; lower-limb EMG checked the muscle-pump explanation. Heart rate and stroke volume did not both return to baseline. | This noninvasive, acute demonstration is a mechanism comparator, not validation of SCCI_RH's implanted access, dose or chronic consumer benefit. [Primary article](https://journals.sagepub.com/doi/10.1089/neu.2017.5082) |
| **Squair et al., 2021**, multiple rodent experiments; closed-loop rat subsets of seven acute and six chronic SCI animals; three primates; one human | Targeted lower-thoracic epidural stimulation and measured pressure feedback formed a neuroprosthetic baroreflex. The human was a 38-year-old with clinically complete cervical SCI; peripheral muscle sympathetic nerve activity was also recorded. Animal mapping and perturbations linked pressor effects to sympathetic/splanchnic circuitry. | Species, injury stage and experimental subset matter. Human sympathetic microneurography is **peripheral nerve recording**, not a demonstrated implanted spinal BP decoder. It supports a feedback mechanism and target selection, with limited human generalization. [Primary article, especially Extended Data 7–10](https://www.nature.com/articles/s41586-020-03180-w) |
| **Phillips et al., 2025**, 14 intervention participants across staged SCI studies; smaller analysis subsets | A lower-thoracic hotspot and purpose-built implant/hub supported external Finometer SBP feedback controlling EES amplitude with PID. Main dynamic comparisons used three/four participants; a later repeated-transition analysis used five. Targeted stimulation improved pressure regulation during postural challenges. | The large surveys are not implant samples. Laboratory feedback, long-term use and each implant generation have different denominators. These results do not establish healthy-user enhancement or SCCI_RH's electrical design. [Primary article, Fig. 3 and Methods](https://www.nature.com/articles/s41591-025-03614-w) |
| **Mekhail et al., EVOKE, 2020**, 134 chronic back/leg pain patients randomized, 67 per group | Epidural stimulation recorded evoked compound action potentials (ECAPs) and adjusted output to regulate neural recruitment. The closed-loop group had a higher primary pain-response proportion than open-loop at three and twelve months. | This is a genuine spinal-recording feedback precedent in a different indication. ECAP recruitment is not BP, autonomic state or proof that a pressure-targeting lead provides the same useful signal. [Primary trial abstract](https://pubmed.ncbi.nlm.nih.gov/31870766/) |

One important timing distinction: the 2025 pressure study reports a 200 Hz
pressure waveform, extracted pressure measures at 1 Hz, and platform updates as
fast as 25 ms. These are different rates; a fast stimulation command does not
create new physiological observations. [Study Methods](https://www.nature.com/articles/s41591-025-03614-w)

## Evidence-supported core and proposed extensions

The supported starting chain is **measured pressure → error calculation →
individualized stimulation → changed vascular response → measured pressure**.
The proposed biological route is afferent recruitment followed by spinal
intermediary circuitry and sympathetic output to vascular effectors. The design
inference is to treat this as a bounded, context-dependent pressor pathway,
rather than a general command channel for organs.

| Architecture element | Evidence status | Conditional SCCI_RH implementation |
| --- | --- | --- |
| External BP feedback and bounded stimulation adjustment | Demonstrated in selected SCI experiments above | An external sensor sends timestamped BP, quality and calibration information to a wearable controller. IMU/posture may supply context, but does not silently replace pressure measurement. |
| Individual target and local input–output map | Supported by participant-specific mapping; a universal response is not established | A declared calibration model supplies usable gain, delay, saturation and off-target limits. For concept simulations these may be assumed and swept, rather than claimed to have been identified in SCCI_RH participants. |
| Spinal recording of evoked recruitment | Demonstrated for ECAP-controlled pain stimulation; transfer to the pressure target is unverified | Optional recording contacts and artifact-aware electronics could monitor a recruitment proxy. SCCI_RH must separately assume that a useful pressure-related proxy exists at its chosen site. Electrical delivered charge remains a different measurement. |
| Spinal decoding of impending hypotension or sympathetic state | Not established by the pressure studies reviewed here | A future learned decoder could augment external BP and posture. Its causal information, drift, artifact recovery and incremental value are explicit hypotheses, with an equal-external-sensor comparator. |
| Long-term adaptation, mobile use and healthy-consumer extensions | Selected chronic use supports further work; general healthy automation does not follow | Future consumer-facing modes could address a named, demonstrated deficit in an eligible population. Healthy-user performance and other involuntary functions require their own mechanism assumptions and studies. |

The pressure branch can therefore remain part of a bidirectional SCCI platform
without pretending that its principal feedback measurement comes from the
spinal cord. A future motor branch can use spinal recordings differently. A
common implant/controller does not imply a common electrode location or decoder
for every application; a modular target-specific lead concept is more
defensible.

## Explicit assumptions for a useful conditional design

1. **Accessible positive authority:** the selected person, contact pattern and
   state have a pressor response over a usable local range. Zero, weak,
   nonmonotonic and adverse responses remain possible scenarios. A healthy
   person's existing baroreflex may alter or remove the useful range.
2. **Sufficient observation:** an external BP sensor provides a suitably calibrated,
   timely estimate during relevant activities. A future wearable sensor can be
   assumed in the concept, but accuracy under motion and hydrostatic changes is
   a named dependency, not earned by laboratory finger-cuff results.
3. **Local stability over a control episode:** a calibrated response map remains
   adequate long enough to use, or changes slowly enough to detect. Fatigue,
   posture, medication and native autonomic activity can violate this premise.
4. **Finite and independently observed delivery:** a request is delivered within
   stated timing and effect uncertainty. Driver/charge monitoring does not
   directly measure the biological pressor effect, so physiological feedback
   remains necessary.
5. **Optional neural information:** recordings supply useful context or recruitment
   information beyond the allowed external sensors. This is a permissible future
   hypothesis, not required for the core pressure loop. Matched-information
   external controls must receive equal resources.
6. **Withdrawal dynamics:** reducing stimulation removes added pressor drive after
   a finite response tail. It does not provide an independent active way to lower
   arbitrary high pressure. Native recovery, persistent excitation and renewed
   hypotension must be represented after withdrawal.

These assumptions allow concrete engineering now. Failure of one restricts the
operating scenario; it need not invalidate the whole platform or justify an
indefinite search for biological proof before CAD and electronics can proceed.

## Compact model interpretation and useful boundaries

The existing [pressure model](../pressure-model.md) already supplies a suitable
two-state conditional abstraction. Preserve its historical simulations and
electrical qualification outcomes. A complementary concept scenario may state
its own usable actuator and observation assumptions openly:

\[
\tau_a\dot x=R(u_d(t-L))-x,\qquad
\tau_p\dot z=Gx-z,\qquad p(t)=p_{\rm ambient}(t)+z(t).
\]

Here \(u_d\in[0,1]\) is a normalized **delivered** intervention, \(R\) a chosen
recruitment law, \(x\) activation, and \(z\) added pressure. This is an assumed
input–output model, not a mechanistic digital twin of sympathetic circuitry.

| Quantity | Units and interpretation | How to use it honestly |
| --- | --- | --- |
| \(G\) | mmHg per unit activation, or Pa consistently throughout | A hypothetical local effect range. Include positive, zero and adverse gain. Adverse gain is a failed pressor assumption, not permission to advertise pressure-lowering authority. |
| \(\tau_a,\tau_p,L\) | Seconds | Activation, haemodynamic response and onset delay. Sweep them and report instability, lag or overshoot; do not infer them from the platform's command latency. |
| \(R\), saturation and release tail | Dimensionless recruitment, finite authority and seconds | Describe threshold, maximum effect and persistence explicitly. Published amplitude modulation does not validate a train-fraction response law. |
| Delivery uncertainty | Fraction of command/effect, with the mapping declared | Vary finite actuation quality. No dimensionless fraction-to-charge or charge-to-mmHg conversion is established without a separate recruitment map. |
| Sensor age, bias, noise and invalidity | Seconds and mmHg/Pa | Keep physical observation time distinct from arrival. Include delayed, missing, biased and stale measurements; a fresh biased measurement can still be wrong. |

For a constant pressure deficit of magnitude \(D\ge0\) and a positive monotone map, the simple
equilibrium requirement is \(0\le D\le G R(1)\) when the target equals the ambient
undisturbed reference. If the deficit exceeds maximum effect, no controller
tuning restores the target. If ambient pressure already exceeds the target, a
pressor-only actuator cannot make it reachable. Delay, response persistence and
sensor error impose additional limits even inside that static range.

A compact comparison should use identical disturbance, calibration opportunity
and sensor resources for stimulation-OFF, fixed stimulation and feedback. Report
pressure error **and** low-pressure nadir, recovery overshoot, saturation,
withdrawal response and invalid-data time. Selected numerical targets and
coefficients are illustrative design assumptions, not clinical prescriptions or
values fitted from the articles. An oracle supplied with hidden pressure, gain or
future disturbance is a diagnostic only.

The useful concept claim is conditional and concrete: **if** a selected spinal
site supplies calibrated positive authority and sufficiently timely external
feedback, a bounded controller can compensate some pressure deficits while
posture or other disturbances change. Neural augmentation, chronic packaging
and expansion to healthy consumers are separately stated future assumptions.
