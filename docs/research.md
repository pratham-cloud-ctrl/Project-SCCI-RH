# Scientific grounding and source audit

Project SCCI RH is an original digital engineering study of a future invasive spinal cord–computer interface. The literature supports particular recording and stimulation mechanisms; the repository tests selected control assumptions using artificial data. This is a targeted narrative review, checked on **7 October 2026**, rather than a systematic review, clinical protocol, or evidence of a new implant's effectiveness.

## What the scientific case requires

For immediate assistance, a system needs task information that can be estimated and an input that influences the required output. For retained learning, it additionally needs durable adaptation that improves unassisted behaviour. Reading a movement-correlated signal does not identify the stimulation command that caused the movement. SCCI_RH therefore uses a learner-specific response model and an explicit assumed learning-benefit parameter. For physiological feedback, SCCI_RH selects mean arterial pressure after a postural disturbance and openly uses external pressure measurement.

## Source map

| Evidence | Why SCCI_RH uses it | Boundary |
|---|---|---|
| [El Hadwe et al., 2026](https://doi.org/10.1038/s41467-026-75128-z) | Movement-related information from an intradural circumferential surface array | Short animal study; no chronic human decoder or skill transfer |
| [Capogrosso et al., 2013](https://doi.org/10.1523/JNEUROSCI.1688-13.2013) | Afferent-mediated effects of epidural stimulation | Not arbitrary writing of a recorded neural pattern |
| [Wagner et al., 2018](https://doi.org/10.1038/s41586-018-0649-2) | Movement timing, rehabilitation and outcomes without active stimulation matter | Rehabilitation after injury does not establish novice skill acceleration |
| [Formento et al., 2018](https://doi.org/10.1038/s41593-018-0262-6) | Sensory feedback can be disrupted by stimulation | More stimulation is not automatically more useful assistance |
| [Rowald et al., 2022](https://doi.org/10.1038/s41591-021-01663-5) | Task-specific spatial and temporal stimulation | Limited clinical cohort; not a general skill interface |
| [Thompson et al., 2013](https://doi.org/10.1523/JNEUROSCI.3968-12.2013) | Durable modification of a spinal reflex can accompany better function | Peripheral reflex-conditioning study; no expert-recording implant |
| [Nishimura et al., 2013](https://doi.org/10.1016/j.neuron.2013.08.028) | Timing can influence connection plasticity | Cortically triggered primate experiment; not SCCI_RH's spinal-only architecture |
| [Shadmehr and Mussa-Ivaldi, 1994](https://doi.org/10.1523/JNEUROSCI.14-05-03208.1994) | Practice, error and aftereffects are distinguishable | Human reaching adaptation; not spinal implantation |
| [Squair et al., 2021](https://doi.org/10.1038/s41586-020-03180-w) | Feedback-mediated spinal blood-pressure regulation | SCCI_RH does not reproduce its biological plant or clinical hardware |
| [Phillips et al., 2025](https://doi.org/10.1038/s41591-025-03614-w) | Specific lower thoracic access for pressure regulation | Feasibility evidence across four trials; not universal autonomic control |
| [Lorach et al., 2023](https://doi.org/10.1038/s41586-023-06094-5) | Comparison with a brain–spine system | Uses cortical recording; must be labelled a hybrid |

The machine-readable [evidence matrix](evidence-matrix.csv) records population, scope and design implication. [references.bib](references.bib) contains stable bibliographic identifiers. Publisher abstracts, methods/figure text where available, PubMed records, author-hosted manuscripts and Europe PMC article XML were consulted. Subscription-only details were not inferred from titles. These are selected sources, not every relevant study, and several studies belong to related research programmes rather than independent replications.

## Audit of the supplied hypothesis paper

The supplied 28-page review is the starting research map. It reports no original experiments and explicitly identifies illustrative learning curves. Its distinction between causal access, observation, assistance and retained learning is retained here. Its broad consumer possibilities remain future hypotheses.

**Correction:** page 7 says the freely moving experiments in El Hadwe et al. involved five rats. The primary study describes **15 implanted freely moving rats overall**; the motor-decoding analysis used **five**. Do not treat the subset as the complete cohort or the reported decoder score as independent evidence across 15 animals.

**Primary-source caution:** the [2026 article's Figure 5 caption](https://www.nature.com/articles/s41467-026-75128-z) describes a 21.29% chance baseline as uniform random classification over eight classes. Uniform eight-class random predictions have expected accuracy 12.5%, so that baseline description is internally inconsistent. SCCI_RH does not rely on the comparison. This wording issue alone does not invalidate the recording observations, but illustrates why even primary-source numbers require checking.

SCCI_RH further narrows the implementation to two testable digital studies. It separates the proposed intradural recording placement from epidural stimulation; recording performance is not assumed to transfer across these compartments. The physical CAD is a desktop reference enclosure, not the dimensions or materials of an implant. The paper's evidence cutoff was 30 September 2026; SCCI_RH's selected-source verification date is 7 October 2026, without claiming a comprehensive updated search.

## AstroSam attribution and technical boundary

AstroSam's [video](https://www.youtube.com/watch?v=5YxrpcqkTYA) and [Mind-Link repository](https://github.com/sam-astro/Mind-link) inspired the progression from future concept to tangible engineering. The reference repository was inspected at commit `a391eb851ee624be675057380f4e3b701ebf6ee8`. Its electronics files, printed meshes, firmware, visualizer and notebook make the design inspectable. Its checked-in firmware reads binary input states and the visualizer displays those states. These artifacts do not establish neural decoding or a functioning implanted human BCI.

SCCI_RH develops its own source, models and geometry. The inspiration is credited without claiming to have invented spinal interfaces or to have replicated Mind-Link's biological interface. The distinction matters: a physical appearance can explain a proposed architecture, but only evidence at the relevant layer can validate that architecture.

## Next evidence that would change the concept

The expert-informed learning idea would need neural measurements with information beyond body kinematics, participant-specific stimulation mapping, a mechanism for retained change, and blinded unassisted retention/transfer assessments against practice, sham and unmatched-template controls. Blood-pressure translation would require identified nonlinear dynamics, reliable sensing, bounded adverse responses and clinical evaluation. Neither requirement can be satisfied by aesthetic renders or a synthetic controller. The digital project is complete within its declared scope while these biological questions remain open.
