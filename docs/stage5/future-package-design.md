# Conditional future interface: mechanical design basis

The Stage 5 future interface gives Project SCCI RH a specific physical identity:
rounded metal can, separate lid and weld seam, dielectric header, independently
insulated feedthroughs, keyed recording/stimulation connectors, tapered lead
boots, separate recording and stimulation paddles, and an explicit future RF
window. It is a proposal for the future implanted system. The current eight-board
digital reference belongs in its separate desktop assembly.

Both ambitions remain intact. A target-specific recording lead could supply
task-related observations for an expert-informed learner controller; a separately
calibrated stimulation lead could deliver admitted interventions during practice.
Retained learning still requires unassisted outcome evidence. A physiological
configuration would select a pathway, sensor and response map for one function;
the pressure-support concept still requires external pressure feedback. This CAD
does not establish neural decoding, selective recruitment, retention, anatomical
placement or efficacy, and one pictured lead set is not a universal spinal implant.

## Geometry and interfaces

| Item | Nominal proposal | Interpretation |
|---|---|---|
| Metal core | 60 × 48 × 14 mm; 5 mm plan corner radius | Stage 2 envelope retained; 1.2 mm nominal wall/floor |
| Header | 60 × 10 × 14 mm | Complete core/header envelope remains 60 × 58 × 14 mm |
| Can/lid joint | Can rim z=12.6; seam z=12.6–12.8; lid z=12.8–14 | Nominal joint geometry, with no welding/process qualification |
| RF window | 20 × 10 × 1.2 mm, with 0.15 mm radial seal region | Additional conditional window; no RF, strength or sealing pass |
| Functional feedthroughs | 36; x=4.5+3c mm, c=0…17; z=5 and 9 mm | Exact Stage 2 port identities and centres; axes parallel to +Y |
| Pin / ceramic / ferrule radii | 0.15 / 0.70 / 0.90 mm | 0.75 mm nominal pin-to-can and 0.55 mm pin-to-ferrule geometric separation |
| Recording connector | 18-way insert, left mechanical key | 16 signals, one shared reference, one distinct bounded body bias |
| Stimulation connector | 18-way insert, right mechanical key | 16 selectable contacts and two dedicated source returns |
| Strain-relief boots | 26 mm taper from broad connector to cable | Geometric strain-relief proposal; no strain/fatigue result |
| Recording cable / paddle | 8 mm cable width; 12 × 34 × 0.6 mm paddle | Separate illustrative surface interface; anatomy unassigned |
| Stimulation cable / paddle | 10 mm cable width; 14 × 44 × 1 mm paddle | Separate illustrative interface; anatomy unassigned |
| Distal contacts | Recording 2 × 2 × 0.2 mm; stimulation 3 × 3 × 0.2 mm; 0.35 mm corner radius | Areas are geometric, not a safe charge-density prescription |
| Illustrative conductors | 0.070 mm diameter; mitered sweep junctions | Every P01–P36 route is distinct; no physical bend-radius, fatigue or impedance qualification |

The nominal connectors have no spring, contact-force, torque, extraction or
fluid-seal qualification. Their zero-gap pin/socket surfaces describe electrical
contact in the model; they do not form a validated tolerance fit. The key slots
have 0.2 mm nominal side clearance and different X positions, so their
identity is inspectable in the geometry. Connector insert pockets have 0.1 mm
side clearance. No supplier tolerance, worst-case fit or sterilization allowance
has been earned by these nominal values.

The two rows of eighteen ports deliberately retain the original allocation.
Each pin has its own annular ceramic insulator and metal ferrule, with a separate
socket and lead conductor. The body-bias/reference conductors never become the
metal housing or stimulation returns. The [machine-readable map](../../cad/stage5/future-interface/port-map.csv)
lists every port, role, native object and distal contact centre. The Stage 5
cross-stage interface map separately relates these identities to the actual
Stage 4 connectors; the future feedthroughs are not installed components on the
large reference PCBs.

The four corner channels P01, P18, P19 and P36 use 2.0 mm long sleeves/ferrules
from y=46.0 to48.0; the remaining32 use the flat-wall1.2 mm length from y=46.8
to48.0. Their bores extend0.1 mm beyond each sleeve end. This removes the
rounded inner-wall shoulder rather than assuming that a flat-wall bore reaches
the cavity at every X position. Independent inspection found the earlier
flat-wall-only corner detail reduced pin-to-can clearance to0.216025 mm. The
corrected geometry retains the same port-axis datums and measures at least0.75 mm
pin-to-can clearance for all36 ports. This is a geometric separation, with no
dielectric, voltage, sealing or manufactured tolerance qualification.

The leads are laid out straight and separated for CAD inspection. Their pictured
lengths are display allocations, not patient measurements. The conductors are
continuous nominal solids, with separate noncrossing left/right paddle fanouts;
the right column reverses port order. This routing convention is recorded in the
map rather than inferred from appearance. The two stimulation returns remain
individually identified contacts.

## Defensible premises and source scope

**Published/manufacturer precedent:** titanium housings, Pt/Pt-Ir conductors and
ceramic-insulated multi-pin feedthroughs are established component families.
[IJ Research's medical-feedthrough description](https://www.ijresearch.com/medical-feed-through/)
describes this material combination. That supports the material family and
construction logic; it does not qualify SCCI_RH's dimensions, joints or hermetic seal.

**Published manufacturer precedent:** the Boston Scientific Precision system's
technical specifications list silicone/polyurethane insulation, platinum or
platinum/iridium contacts and a 16-contact surgical paddle. These are useful
mechanical/material comparisons, and they are separate from an 18-contact
recording/stimulation SCCI_RH lead. SCCI_RH's wider connector, shortened display length,
conductor routing, contact areas and signal roles are our proposals.
[Manufacturer clinician manual, technical specifications, printed pp.61–64](https://www.accessdata.fda.gov/cdrh_docs/pdf3/P030017S363D.pdf)

**Engineering inference:** a dielectric header over a continuous metal wall does
not itself give an internal antenna an RF path. The model therefore adds a
distinct glass window in the lid, with an explicit seal region and an antenna
reservation underneath. SCHOTT describes glass as an RF-transmissive electrical
insulator for implant packaging. This supports a plausible material approach,
not a tested antenna/window combination, charging solution or SCCI_RH radio link.
[SCHOTT implant packaging](https://www.schott.com/en-us/products/customized-enclosures-and-feedthroughs-for-implantable-medical-devices-p1001211)

All three sources were checked on 16 October 2026. No manufacturer's shape or
medical instructions are reproduced as an SCCI_RH manufacturing or implantation
procedure. The proposal is a digital concept, with no human/animal connection.

## Internal allocations and acceptance limits

The unpopulated 50 × 40 × 1 mm board, 3 mm component zone, 24 × 14 × 3 mm HV bank
and 35.1 × 17 × 5.5 mm battery bounding box retain Stage 2's allocations. They are
not populated electronics. The battery remains case-negative and electrically
isolated; the new 0.15 mm bounding insulation shell is a proposed spatial
allowance, not a selected insulating system. It leaves nominal 0.35 mm clearance
above the component zone and 0.85 mm below the lid. Battery shape, swelling,
compression, electrical leakage and final tolerance stacks remain unverified.
The antenna reservation occupies z=12.1–12.6 below the RF window and has no
overlap with the battery allocation. Capacitance at working bias, lifetime,
thermal resistance and wireless energy transfer are still unresolved.

The eight Stage 4 reference boards contain over a thousand fitted components.
Putting their functions in this compact envelope would require a new integrated
electronics implementation, part reduction/ASIC or equivalent packaging work,
new interconnects, new power/thermal verification and new qualification. The
current concept does not claim that this miniaturization has already occurred.
The original compact-package thermal concerns remain open; changing geometry
alone cannot convert them into a thermal pass.

The finite mechanical acceptance gate is saved native valid single-solid parts,
36 distinct complete port identities, explicit nominal dimensions and interfaces,
no unlisted positive-volume physical-part intersections, and a valid STEP
reimport preserving part count and material volume. Internal allocations are
separately named and excluded from occupied-part interference claims. Nominal
contacts are retained in a finite list; no broad collision suppression is used.
An independent inspector checks the saved files rather than trusting these
generator assertions. These gates provide digital geometry evidence only.

The [native CAD package](../../cad/stage5/future-interface/README.md) includes
editable dimensions, dependency links, STEP/STL exchange, fitted/exploded
inspection views, per-part volumes and hash-bound receipts. These deliverables
make the proposal reviewable while leaving mechanical, biological, electrical,
RF and thermal qualification as explicit later engineering work.

