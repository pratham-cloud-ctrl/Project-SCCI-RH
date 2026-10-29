# Stage 5 mechanical assembly and packaging - exit review

**16 October 2026 - complete within the bounded digital mechanical scope.**

Project SCCI RH now has an inspectable mechanical body linked to its actual
electrical architecture. The full-size reference chassis packages all eight
populated boards; a separate conditional implanted-interface design expresses
the future spinal platform without pretending those boards have been shrunk.
Both expert-informed retained motor learning and function-specific physiological
feedback retain their Stage 3 mechanisms and biological assumptions.

## Delivered mechanical work

| Package | Concrete deliverables |
|---|---|
| Full reference assembly | One native FreeCAD entry document with 260 physical objects, genuine populated board compounds and preserved editable construction dependencies |
| Reference chassis | 600 x 310 x 240 mm overall including feet; two bays and four tiers; eight removable trays; all 32 original PCB mount axes; 32 insulating standoffs, 64 board screws, covers, rails and passive cable passages |
| Reference source and exchange | Native 170-part chassis/electronics source, 162 mechanical STL parts, mechanical STEP, losslessly archived full populated and exploded STEP, mounting table and nine vector drawings |
| Mating interfaces | 78 internal and five external nominal cable housings aligned to actual native pins; two passive rear inserts and five cable grommet allocations |
| Electrical/mechanical trace | All 258 original wiring rows, 47 shared branch nodes and 525 terminal positions; 36-port bridge to actual protected electrical boundaries |
| Future implanted interface | 60 x 58 x 14 mm can/header envelope; 230 physical solids plus six explicitly separate allocations; 36 individually isolated feedthroughs and mapped conductors; two keyed lead interfaces, strain relief and distal contact arrays |
| Inspectable presentation | Fitted/exploded native views, four BRep-derived technical renders, Blender source, six-page dimensioned mechanical review and explicit launchers |

The [native CAD entry](../../cad/stage5/README.md) organizes the package. The
[reference design](reference-mechanical-design.md) and
[future package design](future-package-design.md) explain geometry, materials,
interfaces and evidence. The [assembly contract](../../cad/stage5/assembly-contract.json)
links the exact native sources and per-package decisions.

## Verification and one concrete correction

The separate native inspector reopens the saved FreeCAD and STEP geometry,
compares every placed board with its frozen populated source, derives mounting
and connector axes from the original native PCB, and checks actual material
intersections and declared clearances. The portable verifier binds those
native receipts to exact files, checks original electrical/port identities and
preserves 2,153 Stage 1-4 input/evidence files against commit `7a4371b`.

The [reference completion driver](../../scripts/inspect_stage5_reference.py)
retains four [actual completed source/export phases](../../provenance/stage5-reference-phases/README.md)
with their original executed-source and input hashes. It binds the separately
completed [exact solid-pair clearance inspection](../../provenance/stage5-reference-clearance/README.md),
then freshly reopens all 170 reference parts, verifies complete queried-solid
coverage, reproduces every nearest-pair distance and checks all **14,365 material
pairs / 248 exact candidates**. No unexplained intersection is present. The
interrupted original whole-compound run is not represented as a completed pass.
The final [reference native receipt](../../provenance/stage5-native-reference.json)
and [portable checkpoint](../../provenance/stage5-mechanical-verification.json)
record this explicit evidence chain.

The combined native assembly is separately reopened and compared with its two
source documents: **260 source parts, all valid, with zero residual in the
recorded geometry metrics and vertex coordinates**. Its report is
[stage5-combined-native.json](../../provenance/stage5-combined-native.json).

Independent review found four incomplete feedthrough bores at the rounded
inner corners of the future can. They left only 0.216 mm pin-to-can separation,
below the stated 0.75 mm allocation. The corner bores and sleeves were extended
through that shoulder; all 36 port positions and the package envelope remain
unchanged. Reinspection measures a **0.749999964 mm minimum**, matching 0.75 mm
within the stated CAD numerical tolerance. Pin-to-ferrule separation is nominal
0.55 mm; distal contact edge separation is at least 1.5 mm. These are geometric
allocations, without a dielectric or biological qualification claim.

STEP exchange is checked at an explicitly recorded **1 micrometre coordinate
tolerance**, alongside solid inventory, topology, material volume, face metrics
and curve geometry. Exchange numerical integration drift is retained rather
than treated as a physical measurement. Full populated reference STEP exceeds
GitHub's per-file limit, so deterministic lossless ZIPs preserve its exact bytes;
the supplied extraction launcher verifies the uncompressed hashes.

All 14 declared reference clearance gates pass on the saved BReps. The eight
board-to-own-tray minima are **8.615 mm**, against an 8 mm requirement. Five
upper-tray gaps are **27.845 mm** and the power-to-current-driver gap is
**24.785 mm**, against 20 mm requirements. The exact distance check decomposes
the shapes into their original solids and uses bounding boxes only to discard
pairs that cannot improve the current minimum; no solid or clearance gate is
removed.

## Boundaries carried forward

The actual eight-board reference remains at 1:1 scale. The future can needs a
new integrated electronics implementation, qualified energy storage, chronic
thermal closure and qualified interfaces. Stage 4's compact thermal failure is
preserved. Current firmware has no implemented radio image; the future RF
window/antenna reservation is explicitly conditional.

Cable routes are zero-volume, unsmoothed planning centerlines with proposed bend
and slack allowances. They preserve connectivity; they do not constitute a
packed manufacturing loom or wire cut list. Contact springs/crimps, locking,
wire gauge, shielding and electrical ratings remain unqualified. Tray rails and
closed covers support a stationary bench concept; positive transport latches,
shock retention, fastener loads, fatigue and environmental performance are not
established. Native geometry checks do not establish implantation, hermetic
leakage, anatomical suitability or efficacy.

## Next stage

Stage 6 connects the selected spinal observations, acquisition, control policy,
stimulation/delivery, modeled response and feedback into the final digital
integration account. It consolidates the illustrated research/engineering
manuscript, requirements/claims trace, contribution record, reproducible private
repository release and learning/defence material. Video and website remain
parked. New biological proof, a favorable learning result or universal body
automation is not a prerequisite for a coherent conditional concept paper.
