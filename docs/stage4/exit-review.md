# Stage 4 digital engineering exit review

**16 October 2026 — complete within the bounded digital reference scope.**

Project SCCI RH now connects native recording/protection, two-source stimulation,
contact routing, independent supervision, power, monitoring/companion transport
and an actual nRF5340 carrier in one inspectable electrical system. The result
is an eight-board modular reference with genuine copper routes and populated
package geometry. It supplies the electronics input to Stage 5 mechanical work.

| Completion requirement | Saved evidence | Result |
|---|---|---|
| One real native hierarchy | 80-sheet master; source XML, BOM and 258-wire harness | 1,298 positions / 1,296 fitted; 4,781 pin identities; zero master and eight per-board ERC findings |
| Source preservation and electrical integration | Independent source pin groups, explicit harness joins and real observation headers | 9,540 assertions; all 50 firmware endpoints; distinct rearms and HOST/AFE/companion returns |
| Actual populated routed boards | Eight saved KiCad boards, local libraries and selected four-layer stackup | 21,039 trace segments, 2,335 vias and 32 mounting holes; zero DRC violations, unconnected items, parity issues or ignored checks |
| Independent schematic/board parity | Saved XML versus actual PCB pads, references, values, DNP flags and hierarchy paths | 14,273 assertions; two optional driver capacitors remain DNP |
| Actual controller and observation chain | 68-component BT40F carrier; 46 GPIO and four SN74LVC165A devices | All physical module pads mapped; 26 observations plus six fixed sentinel bits |
| Carrier-specific executable image | Pristine application-core ELF/HEX/BIN/configuration and independent byte audit | Manufacturer 11 pF HFXO setting; 83 checks; 53,648-byte flash and 98,000-byte RAM extents; no physical execution |
| Revised resource allocation | Additive power model plus independent decimal audit | HOST_3V3 160 mA cap; conditional 3.154 W / 4.880 h; 23 independent checks; earlier thermal failure retained |
| Inspectable populated exports | Populated STEP, native PNG/copper SVG, BOM, placement and Gerber/drill reference | Every fitted reference present in STEP; reimported valid solids; current output/source hashes verified |

The [board index](../../electronics/stage4/integrated-pcb/BOARD_INDEX.md) opens the
native designs. The [integration design](integrated-pcb-design.md),
[layout review](pcb-layout-review.md), [carrier review](controller-carrier-component-review.md)
and [TPS3431 land-pattern correction](tps3431-land-pattern-review.md) explain the
actual decisions. The portable checkpoint verifier and Git blob manifest bind
the final package. Native CAD checks and geometry reimports are distinguished
from portable replay of their saved evidence. Original circuit/study packages,
prior firmware and the synced reference paper remain preserved.

## Corrections resolved during integration

Two earlier wiring rows would have joined three independently driven rearm
outputs. The new system replaces exactly those rows and preserves the original
wiring record. Four real tap headers replace bare-component wiring endpoints.
The former source-qualified ground/shift-tail mix-up is separated in actual
copper. TI's watchdog land drawing places lead rows at +/-1.4 mm; the new
integrated footprint corrects the old +/-1.1 mm interpretation and passes the
ordinary clearance rule. No reduced-clearance exception was used.

The controller's dense lands require a selected 0.5 mm / 0.2 mm fine-via process
alongside ordinary 0.6 mm / 0.3 mm vias. Five LGA lands intersect drilled vias and
therefore require a filled/capped assembly process. These are explicit
fabrication requirements; they have not been qualified with a manufacturer.

## What remains conditional

The proposed SCCI still depends on useful spinal observations, selective
recruitment and individualized biological response. Expert-informed retained
learning and function-specific physiological regulation remain central. The
board set does not establish those biological premises or a 1.5x/2x learning
outcome. Prior conservative negative studies remain intact.

The implemented target profile retains nominal 100 us raw-monitor opportunities
and 1 ms recording frames, including known polling gaps. It does not implement
the historical 450k raw / 4k neural schedule. The companion supplies qualified
plans; the device has no implemented radio/network-core image. Analog recovery,
noise, actual dose precision, execution timing, SPI/harness signal integrity,
regulator dynamics, leakage and chronic implanted thermal performance remain
unmeasured. Mixed-domain diagnostic headers prevent a claim of globally
qualified medical creepage. ERC/DRC and nominal solids do not supply those tests.

The eight boards retain their actual large dimensions. A compact implanted
package is a future design problem. Stage 5 develops a coherent native
mechanical assembly, package and lead interfaces, drawings and nominal fit
checks from these populated board inputs. Stage 6 integrates the illustrated
research/engineering paper, explanation and verified private repository release.
Video and website work remain parked.
