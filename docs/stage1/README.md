# Project SCCI RH: Stage 1 design dossier

8 October 2026. Full-system proposal; electronics/CAD implementation follows.

Read the [illustrated brief](../../output/pdf/SCCI_RH_stage1_system_specification.pdf)
for an overview, then the [mechanism specification](system-specification.md) for
the complete proposed device and its two application chains.

| File | Review purpose |
|---|---|
| [Application mechanisms](application-mechanisms.md) | Motor task and physiological endpoint comparison; primary evidence and provisional recommendation |
| [Architecture and interfaces](architecture-and-interfaces.md) | Access alternatives; complete implant/companion responsibilities; units, modes and fault handling |
| [Model and verification plan](model-and-verification-plan.md) | Observable-only modeling; fair expert/neural comparisons; electrical and CAD integration |
| [Requirements](requirements.csv) | 36 full-system requirements with planned stages and verification links |
| [Assumptions](assumptions.csv) | Biological, transfer, model and integration premises and how they could fail |
| [Capability map](capability-map.csv) | Both consumer ambitions and the original paper's wider medical/sensory/physiological directions |
| [Source audit](source-audit.csv) | Decision-relevant primary sources, access date and exact limits |
| [Verification matrix](verification-matrix.csv) | What each digital or future biological check can establish |
| [Stage 1 verification receipt](../../provenance/stage1-verification.json) | Specification consistency and visual checks actually completed |
| [Review and source record](../../provenance/stage1-review.json) | Manual specification review, PDF visual review and preserved input-source identity |

The source hypothesis paper keeps its 30 September 2026 evidence cutoff. This
design dossier records primary-source checking on 8 October 2026. It does not
silently turn the paper into a systematic review or add experimental results.

## Decisions for the next stage

The recommendation is a lower-limb coordination reference and a blood-pressure
regulation reference, while retaining cervical/piano and other endpoint variants
in the platform. Compare separate intradural surface recording plus epidural
stimulation with shared epidural access and penetrating recording; final
geometry follows the selected information and recruitment requirements.

These reference cases make a tractable first quantitative design. They do not
prove that expert spinal information is transferable or that physiological
automation applies to all functions. If another motor case is preferred, its
anatomical and information requirements should replace the first reference
before detailed electronics and CAD.

Video and website work remain parked. The v1.0.0 manuscript, circuit, enclosure
and synthetic results remain historical subsystem references. Completion of this
dossier means the mechanism and requirements are ready for review; the full
implant design remains in progress.
