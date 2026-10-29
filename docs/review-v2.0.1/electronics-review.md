# Electronics and firmware review for v2.0.1

**17 October 2026.** The bounded review inspected the current eight-board
electrical reference, application/backend and production policy code against
SCCI_RH's two ambitions and its digital-only scope. The goal was to resolve concrete
inconsistencies, not to require original biological proof before presenting a
defensible future concept.

## Corrected defect

**UART envelope interleaving, material software defect.** In the preserved
`firmware/nrf5340/app/src/scci_rh_backend.c`, the TX callback selected normal or raw
queue again after every FIFO opportunity. A normal telemetry frame arriving
after a partially transmitted raw frame could therefore appear inside the raw
frame. This corrupts companion framing/CRC and impairs inspectable telemetry.
The issue is demonstrated in compiled source, without claiming physical board
execution: the original callback produces `raw[:4] + normal + raw[4:]` for a
38-byte raw frame and a newly queued 94-byte status frame.

The additive [current firmware](../../firmware/nrf5340/uart-revision/README.md)
holds queue ownership until the selected complete envelope ends. It retains
normal-traffic priority at the next envelope boundary. A finite compiled
regression exercises every partial byte position in both frame types, FIFO
acceptance of 1/3/128 bytes, ring wrap, uint32 queue-index wrap and a temporarily
full FIFO. Of **1,172** shared scenarios, the historical callback fails **334**;
the revised callback passes all **1,172**. The actual callback body is compiled
against explicit interrupt/FIFO stubs rather than replaced by a Python model.

The existing main entry, production policy, pin/peripheral mapping, board
configuration, native circuits and historical images/receipts are preserved.
A separately compiled target image and independent ELF/HEX/BIN audit bind the
correction to a current carrier image. This correction does not imply that the
previous frozen release passed a test which had not yet been run.

The corrected application was actually cross-compiled and linked in a pristine
Nordic SDK v3.4.1 build. Its flash LOAD extent is **53,776 bytes** and RAM address
extent **98,000 bytes**; the original carrier's respective 53,648/98,000-byte
figures remain historical. The corrected image was not flashed or executed.

## Fresh native electrical checks

[Native check receipt](native-electronics-checks.json) records actual KiCad
10.0.6 checks through Konnect MCP 0.13.0, bound to 184 saved design files:

| Current native check | Result |
|---|---:|
| Eight populated boards, DRC violations | 0 on every board |
| Eight populated boards, unconnected items | 0 on every board |
| Eight populated boards, schematic parity findings | 0 on every board |
| Omitted DRC categories | None |
| Eight populated boards, warnings | 0 on every board |
| 80-sheet master schematic, ERC findings | 0 |

The UI was closed. These checks invoked the actual installed KiCad CLI on the
saved native files; they do not claim to have synchronized live unsaved editor
state. No user document was opened, changed or saved. KiCad 10.0.6 has a known
ERC coordinate-scaling quirk, which Konnect reports explicitly; there were no
violations requiring coordinate interpretation in this run.

The unchanged production C policy separately passes **75 host scenarios and
713 assertions**. The historical BT40F source/image audit still passes its
**83 checks**. Those historical counts remain historical; they do not replace
the new frame regression or corrected image audit.

## Mechanism and scope review

The code preserves boot inhibition, explicit monitor-first recovery, independent
supervisor rearm, route commit followed by actual-Q comparison, bounded leases,
checked pressure support, separate OFF plans, hardware timer/DPPI request cutoff
configuration and retained interrupted-dose history. No new automatic restart
or compensating stimulation behavior was added. Circuit/ERC/DRC and source
inspection provide digital consistency evidence; physical shutdown latency,
analog precision, thermal performance and manufactured-board operation remain
unmeasured.

The reference records 16 differential streams and routes two stimulation sources
through the documented contact interfaces. The future SCCI biological access,
useful spinal information, learner-specific recruitment and retained plasticity
remain proposed or conditional. Pressure feedback explicitly needs its external
pressure measurement and selected SCI/pressor pathway; it does not imply
universal body automation. The current target remains OBSERVE-only for neural
recording, with external plans while armed, and has no implemented radio image.

The old firmware README's seven-slice/"next carrier" statements describe its
frozen checkpoint. The new current entry links the existing eight-board
carrier and corrected image directly. The old receipts and source descriptions
are retained so a reviewer can inspect the sequence of revisions without
confusing preserved history with the current technical entry.
