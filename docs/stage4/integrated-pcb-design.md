# Integrated populated circuit system

Project SCCI RH now brings its seven circuit packages and the actual nRF5340 carrier
into one native electrical hierarchy and an eight-board populated layout. This
is a digital engineering assembly for artificial signals and loads. It gives the
SCCI concept a concrete electrical implementation and inspectable component
placement; it does not establish implantation, biological decoding or retained
skill acquisition.

The modular board set is deliberate. The source architecture includes eighteen
terminal guards, seventeen protected recording paths, independent supervision,
several supply domains and extensive diagnostic connectors. Compressing that
architecture into an implant outline without supporting thermal, isolation and
assembly work would conceal its actual engineering size. The board dimensions,
placement, routing and remaining layout findings are reported in the PCB package.

## What is integrated

| Circuit board | Component positions | Role |
|---|---:|---|
| Monitoring cell | 71 | Two shunts, current amplifiers, signed integrators, endpoint ADCs and reference tap header |
| Current driver | 156 (154 fitted) | Restricted two-source current command, polarity bridge, native duration cutoff and sticky source inhibition |
| Recording front end | 153 | Sixteen RHD2216 streams with shared reference, separate bias, protection/blanking and isolated host communication; two added tap headers |
| Contact router | 155 | Two-source contact selection, candidate/preload/active-latch separation and active-address observations |
| Supervision | 479 | Independent terminal guards, health windows, watchdog, duration paths and three host observation taps on one added header |
| Power | 156 | Battery-input supply architecture, host/supervisor rails, isolated recording rails and open-drain power fault |
| Monitoring transport | 60 | ADS8688 raw electrical observation, charge-endpoint shared MISO and isolated companion UART |
| Controller carrier | 68 | Actual BT40F nRF5340 module, reset/SWD, 46 GPIO allocation, four 165 sideband devices and dedicated interface connectors |
| **Total** | **1,298 positions / 1,296 fitted** | **Eight physical circuit boards; 80 native schematic sheets including the integrated overview and three tap sheets** |

Driver C20100 and C20200 are deliberately marked DNP in the native source. Their
footprints and optional test nodes remain present; the assembly BOM retains the
same do-not-populate flags instead of silently fitting them.

The [editable master](../../electronics/stage4/integrated-pcb/integration/master/SCCI_RH_integrated.kicad_sch)
contains the actual circuit sheets, rather than a diagram that merely names
separate designs. Its native exported XML supplies the electrical graph for the
independent integration audit. Per-board editable schematic copies have the same
references, footprints and pin groups as their corresponding master subset.

The [populated BOM](../../electronics/stage4/integrated-pcb/integration/populated-bom.csv)
maps each global reference back to its original board, reference and sheet.
Original source projects, numerical studies and firmware remain unchanged.
Reference offsets are +10000 through +80000 in the table order. For example,
monitor U1 becomes U10001 and carrier U1 becomes U80001. Source symbol UUIDs are
retained, with separate explicit standalone-board and master hierarchy paths.

## Actual electrical connections

The [final wiring table](integrated-pcb-wiring.csv) contains **258 explicit
connections**: 166 retained legacy integration rows and 92 carrier rows. The
carrier rows include all fifty external endpoint bindings from the compiled
forty-six-GPIO firmware map, eight actual active-address bits, eighteen native
health observations, and explicit supply and return connections. The two GPIOs
for the parallel-load/serial-read sideband stay on the carrier itself.

Equal names in unrelated source projects do not automatically become the same
net. A source-qualified net is joined only by a listed connection. The resulting
global names retain source aliases and stable source-derived identifiers in
`system.json`. The independent checker reconstructs pin groups directly from the
eight source XML files and wiring tables, then compares every resulting group
with the actual master XML and all eight per-board XML exports.

Former component taps now have real board connectors. Monitor J19901 exposes
the existing REF3440 output and host ground. Recording J39901/J39902 expose the
nineteen local recording observations and separate AFE returns. Supervisor
J59901 exposes the two scaled pair-voltage outputs, the existing open-drain
guard-fault node and host return. These headers add connectivity; they do not add
a second reference, duplicate a sensor or change the guard authority.

The [harness record](../../electronics/stage4/integrated-pcb/integration/harness.json)
identifies all 78 occupied board connectors and 47 branched electrical nodes.
Several earlier integration rows describe the same shared return or signal.
Their physical realization is a loom with insulated branches, rather than
forcing several independent mates onto one header pin. The record gives exact
connector pins and branch membership. Final locking mate part numbers, wire
lengths, gauge, shielding and assembly methods remain unqualified.

HOST GND, isolated AFEAGND and externally powered companion COMP_GND remain
separate in the exported electrical graph. Mixed-domain diagnostic connectors
already present in the source architecture are retained and identified by the
layout review; connector adjacency and a geometric isolation corridor do not
establish medically qualified creepage or leakage performance.

## One deliberate integration correction

The earlier supervision wiring table joined driver J3.4/J3.8 to supervisor
J3.10/J3.11 respectively. That was an earlier common-rearm contract. The actual
firmware instead owns one common driver rearm and two independent supervisor
phase-rearm GPIOs. Retaining those two old wires would connect three push-pull
processor outputs together.

The integrated assembly therefore excludes **exactly those two legacy rows**.
Carrier `BOTH_DRV_REARM` reaches both driver rearm inputs; `PHASE_REARM0` and
`PHASE_REARM1` reach their separate supervisor inputs. The firmware already
issues these actions separately. The original CSV and source circuits remain
frozen; the [integration change record](../../electronics/stage4/integrated-pcb/integration/integration-changes.json)
states the correction explicitly. The independent checker requires the three
processor outputs to remain on distinct nets.

Native PCB review also caught a geometry error in the earlier TPS3431 footprint.
The integrated library and board correct its lead-row centres from +/-1.1 mm to
the manufacturer's +/-1.4 mm. Pad identities and electrical nets remain the same.
The [primary land-pattern review](tps3431-land-pattern-review.md) explains the
dimension and the resulting 0.35 mm nominal pad-to-EP gap. The original source
snapshot is retained; the new board receives the corrected geometry and a fresh
DRC rather than a special reduced-clearance exception.

## Mechanism and relation to the main concept

Recording contacts feed the protected RHD paths. Isolated host communication
delivers timestamped recording words to the nRF5340 firmware, which retains
missing-frame and validity information. A companion supplies the proposed
individualized event plan and, for the pressure concept, a prequalified external
pressure observation. Session identity, freshness, explicit recovery and bounded
permission remain necessary before a command can become a request.

An admitted command sets the DAC/current-source plan and preloads the complete
route. The carrier reads the eight actual active address bits before sending
acknowledgement. The driver and independent supervisor retain separate cutoff
authority. Output current passes through the intended source, monitor, router
and downstream guard arrangement to artificial loads. Current, charge endpoint,
pair voltage and independent health observations return to the controller;
serialized health does not replace the directly connected native guards.

For the future motor-learning concept, the unproven mechanism is that useful
spinal features and learner-specific recruitment could support an expert-informed
practice policy whose benefit persists in OFF trials. For physiological
regulation, the unproven mechanism is that a selected accessible pathway and
individualized response model could support feedback around a specific function.
This integrated assembly implements the proposed electrical/data path under
those conditional assumptions. It does not copy expert voltage into a learner,
claim a 1.5x/2x learning result or provide universal body automation.

## Verification and limits

The integration checker is read-only. It requires source XML hashes, exact
component/footprint preservation, exhaustive pin-group equivalence, actual
physical tap-header connectivity, all fifty firmware endpoints, distinct rearm
outputs and three separate return domains. It also requires zero all-severity
ERC findings in the saved master and each board schematic. Native application
inspection is recorded separately from these independent checks.

PCB copper rules, populated component models, fabrication exports and electrical
connectivity are reviewed in the [integrated PCB package](../../electronics/stage4/integrated-pcb/README.md).
Passing ERC/DRC and viewing a populated board do not establish the previously
unearned phase-charge precision, physical execution timing, analog settling,
high-rate acquisition, implant thermal envelope, battery safety, radio approval
or biological benefit. The firmware retains its implemented lower acquisition
rates and explicit gaps; assembling a PCB does not implement the historical
450k aggregate monitoring proposal.

The bounded digital result supplies native circuit and populated board evidence
for Stage 4. Mechanical packaging and enclosure work belong to Stage 5; the
consolidated illustrated research/engineering paper belongs to the final stage.
