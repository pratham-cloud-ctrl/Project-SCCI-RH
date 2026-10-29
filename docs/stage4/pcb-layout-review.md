# Integrated populated PCB layout review

Project SCCI RH now has an inspectable modular **digital electrical reference**: eight actual populated KiCad boards representing the monitoring, stimulation, recording, routing, independent supervision, power, transport, and nRF5340 carrier circuits. They use the audited physical pin graph and genuine component land patterns. The reference is deliberately large enough to expose each functional circuit; these boards are not a compact implant layout.

## Board organization

| Board | Electrical parts | Outline (mm) | Copper layers |
| --- | ---: | ---: | ---: |
| Monitoring cell | 71 | 120 × 145 | 4 |
| Current driver | 156 | 175 × 155 | 4 |
| Recording front end | 153 | 155 × 190 | 4 |
| Contact router | 155 | 175 × 155 | 4 |
| Independent supervision | 479 | 300 × 250 | 4 |
| Power | 156 | 175 × 185 | 4 |
| Monitoring and companion transport | 60 | 125 × 140 | 4 |
| nRF5340 controller carrier | 68 | 155 × 150 | 4 |

The 1,298 electrical footprints include the four new physical observation headers and the 68-part carrier. Two optional current-driver capacitors remain explicitly DNP in both schematic and PCB. Each board additionally has four mechanical mounting holes, marked board-only and excluded from assembly BOM/placement exports. These are modular laboratory reference boards, joined by an explicit wiring loom, rather than an eight-board implant stack.

Final saved native reports for all eight boards show **zero DRC violations, zero unconnected items, zero schematic parity issues and zero ignored checks**. The layouts contain 21,039 actual trace segments and 2,335 vias. Those counts describe the final files; initial routing jobs are retained as construction history and must not be reimported over the reviewed boards.

Placement follows the original functional schematic sheets. IC anchors and the passive parts connected to them are grouped using their actual courtyards; headers retain their genuine pad numbers, pin-1 markings, and visible silkscreen references. Supply, input, and protection paths remain explicit copper and pad assignments. The design does not substitute a decorative body or board-edge-only component arrangement for an electrical layout.

## Stackup and routing rules

Each saved PCB contains a nominal 1.6 mm, four-copper-layer FR4 stackup: 35 µm copper per layer, 0.20/1.06/0.20 mm dielectric sections, and nominal ENIG finish. This is a documented digital material allocation; a fabricator has not approved dielectric tolerances or impedance.

The baseline copper clearance and minimum trace width are both 0.15 mm. The default routed width is 0.20 mm. Most vias use 0.60 mm diameter and 0.30 mm drill with a minimum 0.15 mm annular ring. The carrier also uses nine 0.50/0.20 mm vias, retaining the same 0.15 mm annular ring and copper clearance. This smaller carrier drill is an explicit fabrication premise, not a measured manufacturing capability.

The layer allocation is a routed reference, with signals permitted on all four layers. It does not establish a controlled return-plane structure, precision analog grounding, power-current capability, RF performance, or impedance control. The BT40F radio is disabled in the implemented firmware; neither the carrier layout nor the existing module model establishes a qualified antenna installation.

## Evidence and bounded repairs

Native KiCad DSN exports, local Freerouting sessions, actual SES imports, and explicit copper repairs produce the saved layouts. KiCad's final DRC/connectivity and schematic parity reports are the acceptance authority. Autorouter progress counters are not substituted for native results: imported partial routes can make those counters count fragments differently from KiCad.

The shared CNV signal required one real copper join on the monitoring board after the carrier intentionally drove the formerly separate source CNV inputs together. The router's corrected harness return required removal and rerouting of the old merged ground copper. Local BT40F escapes were completed after removing short foreign-net segments crossing beneath previously unrouted pads, then rerouting those displaced connections. These repairs change geometry, not just labels.

The supervision review also found a genuine land-pattern error in the earlier TPS3431 DRB0008A footprint. Its lead-row centres were incorrectly interpreted as ±1.1 mm. The primary drawing specifies a 2.8 mm centre-to-centre row span; the new integrated land pattern therefore uses ±1.4 mm. Its 1.5 × 1.75 mm exposed pad is retained. The original frozen circuit package is preserved; the integrated schematic library, PCB library, and nominal package model carry the corrected geometry. See [the primary land-pattern review](tps3431-land-pattern-review.md).

The carrier's actual drill-circle/pad intersection audit finds five BT40F pads with via drill overlap: **D5, C3, A5, D2 and A4**. Its assembly reference consequently requires a filled and capped via-in-pad process for those positions. A board house and assembler must approve that process, stencil and reflow details before any fabrication. The exact coordinates and via dimensions are saved in `electronics/stage4/integrated-pcb/boards/controller-carrier/LGA-fabrication-allocation.json`.

Each final board's `drc-binding.json` binds the PCB, project, sibling schematic, and native report by LF-normalized SHA-256. No DRC exclusions or suppressed check severities are used. The independent audit separately compares actual PCB pads, net names, references, values, footprint identifiers, DNP flags and schematic paths against the native exported schematic graph.

## Physical qualification remains outside this completion claim

Electrical separation of HOST, AFE and companion nets is retained. The automatic routing and ordinary 0.15 mm rules do **not** establish a qualified creepage/clearance barrier or medical isolation. Existing mixed-domain diagnostic headers, including the power converter test header, require explicit redesign or restricted test fixtures before any isolation-qualified implementation. There is no globally qualified copper-free isolation corridor in this reference.

Similarly, zero native DRC violations does not establish switching converter stability, transient/EMI behaviour, precision acquisition noise, stimulation waveform accuracy, thermal performance, connector contact ratings, assembly yield, or operation in living tissue. Route geometry and the large demonstration harness must be analysed alongside the firmware timing and resource limits before any physical design is proposed. The source current-driver restriction and the project's artificial-load-only boundary remain in force.

The populated STEP exports combine the real saved board with standard KiCad package models and explicitly identified nominal custom package geometry. Nominal models use source footprint datums and package-body allocations; they are not manufacturer-certified dimensional models. Export, assembly, and source-graph receipts belong to this digital reference and do not claim fabrication readiness.

## Reproduction entry points

- `electronics/stage4/integrated-pcb/layout/build_boards.py` creates the initial real-footprint placement and native DSN jobs. It refuses to overwrite an existing board by default; its explicit `--replace-generated` option deliberately discards final routing and must only be used for initial-placement regeneration.
- `layout/finalize_boards.py` binds final graph names, DNP/datasheet/path metadata, portable models/libraries, nominal stackup, and semantic labels. It also applies the documented integrated DRB land-pattern override to the new library snapshot.
- `layout/bind_drc.py` refuses nonzero violations, missing connections, parity issues, or ignored checks before writing exact revision bindings.
- `integration/verify_populated_boards.py` independently inspects the exported schematic and PCB files without relying on the layout producer's assertions.
- `export_boards.py` produces the populated STEP, renders, copper plots, and fabrication/assembly reference only after the board's native report passes.

KiCad's global footprint table on this installation can make a command-line check scan many unrelated libraries. The reviewed checks use a task-local empty **global** table and the board's explicit portable **project** footprint table. This changes library discovery only; all actual board libraries remain available, and no electrical or geometry check is disabled.
