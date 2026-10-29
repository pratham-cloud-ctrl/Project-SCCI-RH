# Integrated populated electronics — Project SCCI RH

**Complete within the bounded digital reference scope — 16 October 2026.**
All eight genuinely routed native boards pass DRC with zero violations,
unconnected items, schematic parity issues or ignored checks. The independent
pad/net audit passes 14,273 assertions. The 80-sheet master passes ERC and 9,540
independent electrical-integration assertions.

Start with the [board index and explicit launchers](BOARD_INDEX.md). The
[Stage 4 exit review](../../../docs/stage4/exit-review.md) records what this
package establishes and the remaining physical and biological evidence limits.

The architecture is an eight-board modular digital reference. It preserves the
actual sizes and parts needed by the chosen acquisition, drivers, routing,
independent supervision, supplies and companion interface. The proposed future
implant is explained by the research mechanism; these boards do not demonstrate
implant miniaturization. Use artificial electrical signals and loads.

| Board | Electrical component positions | Initial board outline, mm |
|---|---:|---|
| Monitoring cell | 71 | 120 × 145 |
| Current driver | 156 | 175 × 155 |
| Recording front end | 153 | 155 × 190 |
| Contact router | 155 | 175 × 155 |
| Independent supervision | 479 | 300 × 250 |
| Power | 156 | 175 × 185 |
| Monitoring/companion transport | 60 | 125 × 140 |
| BT40F controller carrier | 68 | 155 × 150 |
| **Total** | **1,298** | Four mounting holes on each board |

There are **1,296 fitted components** and two optional driver capacitors marked
do-not-populate. Those two positions retain their pads and electrical identities;
the fitted STEP assembly and assembly placement file exclude their bodies.

## Open the design

- [Native master schematic](integration/master/SCCI_RH_integrated.kicad_sch):
  80 sheets, 4,781 connected/NC pin identities, all actual circuit symbols.
- [Electrical integration review](../../../docs/stage4/integrated-pcb-design.md),
  [component BOM](integration/populated-bom.csv),
  [258-wire table](../../../docs/stage4/integrated-pcb-wiring.csv), and
  [78 connector / 47 branch-node harness record](integration/harness.json).
- Per-board native designs are in `boards/<board>/`; matching schematics are
  in `integration/boards/<board>/`. Their references and pins use the same
  master electrical graph. The [index](BOARD_INDEX.md) links all native launchers.
- `exports/<board>/` contains populated STEP, native top/bottom/isometric renders,
  copper SVG, source-bound receipts and digital fabrication references.
- [Nominal package geometry](package-models/README.md) identifies the eight
  missing package patterns represented by actual FreeCAD solids and STEP.
- [Carrier-specific firmware](firmware-profile/build-receipt.json) uses the
  compiled application and a manufacturer-supported 11 pF HFXO setting.
  Earlier firmware artifacts remain preserved.

## Power and implemented domain

[The new additive budget](power-overlay.json) preserves previous load reserves
and adds the actual controller: HOST_3V3 is allocated 160 mA, including 41 bias
resistors. Calculated active consumption is **3.154 W** and conditional runtime
is **4.880 h**, using the existing battery/efficiency assumptions. These are not
physical measurements. The earlier compact implanted thermal failure remains.

The target firmware implements nominal 100 µs raw acquisition opportunities and
1 ms recording frames with explicit gaps and validity, rather than the earlier
450k aggregate / 4k neural proposal. Direct independent guards retain shutdown
authority; serialized health is an additional observation path. Expert-informed
retained learning and function-specific physiological regulation remain
conditional biological mechanisms, not measured outcomes of this board set.

## Reproduce finite checks

From the repository root:

```text
python electronics/stage4/controller-carrier/verify_controller_carrier.py
python electronics/stage4/integrated-pcb/integration/verify_integration.py
python electronics/stage4/integrated-pcb/power_overlay.py
python electronics/stage4/integrated-pcb/verify_power.py
```

Saved native ERC, PCB routing/DRC and independent integration checks pass.
There are 21,039 trace segments and 2,335 vias. Manufacturing, analog settling,
timing/WCET, actual current accuracy, noise, EMI, leakage, chronic packaging and
biological efficacy require evidence beyond this digital package. Stage 5
develops the mechanical assembly and interfaces; Stage 6 joins the paper and
verified private repository release. Video and website work remain parked.

Initial DSN/SES and finite repair journals record construction history. The saved
final boards and current hash-bound native checks are authoritative; do not
reimport an initial SES over a finished board. See the [layout review](../../../docs/stage4/pcb-layout-review.md)
for stackup, route limits, the corrected TPS3431 land pattern and the five
controller LGA lands that require a filled/capped via process.
