# Stage 5 - mechanical assembly and packaging

Project SCCI RH now has two deliberately linked mechanical embodiments: a real-size
reference chassis containing the eight populated electronic boards, and a
separate conditional future implanted spinal interface with its own leads.
AstroSam's [Mind-Link](https://github.com/sam-astro/Mind-link) inspired the
progression from a future interface idea to an inspectable engineered object.
The spinal architecture, models, circuits and mechanical design here are SCCI_RH's
own documented contribution.

## Open the engineering package

| Entry | Contents |
|---|---|
| [OPEN_REFERENCE_ASSEMBLY.cmd](OPEN_REFERENCE_ASSEMBLY.cmd) | One complete native FreeCAD assembly, opened as a session-only cutaway so all populated tiers can be inspected; hidden covers remain in the tree |
| [Mechanical review drawing set](drawings/SCCI_RH_Stage5_Mechanical_Review.pdf) | Six illustrated sheets: dimensions, service, conditional package, port bridge and engineering boundaries |
| [Reference native source](reference/README.md) | Editable enclosure/trays/mounts, all actual board compounds, exploded view, BOM, lossless STEP archives and mechanical STLs |
| [Future implanted-interface native source](future-interface/README.md) | Conditional can/header/feedthroughs, keyed recording and stimulation leads, distal contacts and internal reservations |
| [Mating and cable interface source](harness/README.md) | 83 mating housing envelopes, passive rear inserts, all electrical endpoint identities and explicitly nonphysical route plans |
| [Technical renders](renders/) | Assembled/cutaway and exploded views generated from saved BReps; Blender derivative included |
| [Assembly contract](assembly-contract.json) | Links exact per-package dimensions, source hashes, object identities and evidence boundaries |
| [Combined mechanical BOM](MECHANICAL_BOM.csv) | All 260 reference assembly objects, categories, nominal materials/families and source-document identities; individual electronic positions remain in the integrated PCB BOM |

The full reference assembly is **600 x 310 x 240 mm overall, including feet**,
before local cable grommet protrusions. It holds all eight boards at **1:1 scale**. Its 32 original
PCB hole axes have separate standoffs and upper/lower mounting screws. Removable
trays and covers permit inspection after power and plugs are disconnected.

[OPEN_REFERENCE_CLOSED.cmd](OPEN_REFERENCE_CLOSED.cmd) opens the saved closed-case
view. The inspection launcher changes only the current display state. It does
not remove geometry or save over the source design. Tray rails and closed-cover
containment are intended for a stationary bench reference; positive transport
latches and shock retention remain future qualification work.

The future can/header envelope is **60 x 58 x 14 mm**, before leads. It has
**36 functional ports**: 16 recording inputs, shared recording reference,
current-bounded body bias, 16 selectable stimulation contacts and two separate
stimulation returns. The [cross-stage port bridge](harness/body-port-bridge.csv)
maps these names to the actual recording-input and **post-guard** output
boundaries. Body bias remains distinct from a stimulation return.

## What the assembly means

For expert-informed practice, a future useful spinal observation would inform a
learner-specific controller that supplies bounded assistance; retained learning
is assessed after assistance is removed. For physiological regulation, a
function-specific measured state and accessible pathway would supply the
feedback loop. These remain conditional biological mechanisms from Stages 1-3.
The package expresses their engineering interfaces; its appearance does not
establish biological efficacy.

The reference electronics do **not** fit the future can. A future integrated
electronic design, qualified energy storage, hermetic feedthroughs, appropriate
recording access, selective stimulation, heat management and anatomical lead
design remain explicit premises or subsequent qualification work. Current
firmware has no implemented radio image. The conditional RF window/antenna
allocation belongs to the future architecture.

Native fit checks concern saved nominal geometry. They do not qualify material
strength, torque, fatigue, leakage, chronic thermal performance, sterilization,
biocompatibility, implantation, electrical measurement or human/animal use.
All work remains digital. Video and website work remain parked.

## Reproduce and inspect

1. Read the per-package contracts and documentation before changing dimensions.
2. Run the native generators with the installed FreeCAD Python; the reference
   extraction script additionally uses native KiCad Python for original pad and
   mounting datums. No paid service is required.
3. Apply the supplied FreeCAD display macros to save the intended visibility
   and palette; hidden construction operands remain editable in the tree.
4. Reopen saved FCStd and STEP using the separate native inspector. The
   [reference completion driver](../../scripts/inspect_stage5_reference.py)
   explicitly binds the preserved completed source/export phases and exact
   solid-pair clearance inspection, then freshly checks saved native validity,
   solid coverage, nearest-pair witnesses and material interference. Changed
   inputs invalidate the old evidence and require fresh inspection.
5. Refresh derived drawings/renders and the Git blob manifest only after any
   changed geometry passes its declared finite checks.

Replay the committed evidence with `python scripts/verify_stage5_mechanics.py`
from the repository root. This portable check verifies actual native-inspection
receipts and exact source bindings; it does not emulate FreeCAD on CI. The native
drivers require the FreeCAD Python runtime. Producer summaries alone are not fit
evidence.

The [Stage 5 exit review](../../docs/stage5/exit-review.md) records the exact
completion evidence. The original paper and all Stage 1-4 engineering inputs
remain preserved. The following stage integrates this work into the final
illustrated research/engineering manuscript and private repository release.
