# SCCI_RH-S4-RTR-01 - two-source, sixteen-contact route command circuit

**13 October 2026 - editable native digital design - artificial loads only**

Open [contact_router.kicad_pro](contact_router.kicad_pro) in KiCad, or use
[OPEN_IN_KICAD.cmd](OPEN_IN_KICAD.cmd) on this laptop. This package contains
**155 components, 650 compared component pins and six native A2 sheets**.
The [schematic PDF](contact_router.pdf), [individual SVG sheets](svg/),
[BOM](bom.csv), [pin/net manifest](connectivity.json),
[XML netlist](contact_router.xml), [native netlist](contact_router.net),
[saved verification](verification.json) and [rendered review pages](review/)
are included. Local symbols and footprint snapshots keep it editable without
requiring the original workstation's global library configuration.

This advances Project SCCI RH's spinal recording, interpretation, learner-specific
stimulation and feedback architecture. It gives the existing two restricted
**24 V, approximately 3 mA, 200 microsecond** driver sources actual digital
contact-selection circuitry. Biological decoding, retained motor learning and
selected physiological regulation remain the conditional research mechanisms
documented in Stage 3; this routing package supplies no new biological evidence.

## Actual topology and shared contacts

Each source has two **TMUX6208PWR** eight-channel analog multiplexers. The two
common D pins for a source join its `CHx_A_ROUTER` net. Three active address
bits choose one of eight channels, and a fourth bit chooses the low or high
bank. Native gates prevent both banks of one source from being commanded on
simultaneously. Both sources can address the same set of sixteen contact nets.

The single provisional contact-side bench header **J7** has eighteen pins:

| Pins | Functional connection |
| --- | --- |
| 1-16 | `STIM00_CONTACT` through `STIM15_CONTACT` |
| 17 | Source 0 dedicated monitored load-side return |
| 18 | Source 1 dedicated monitored load-side return |

These are **sixteen shared selectable contacts and two distinct returns**,
matching the stimulation side of the Stage 2 functional-port map. The generic
pin-header footprints are digital bench stand-ins; implant lead connectors,
materials, dimensions and assembly are not selected here.

```text
current-driver CHx_A_BR
        |
required external terminal guard / disconnect
        |
router CHx_A_ROUTER -> selected TMUX6208 path -> STIM contact
                                                 |
                                         artificial load
                                                 |
J7 dedicated return -> CHx_RETURN_LOAD -> existing monitor 2 ohm shunt
                                                 |
                                    monitor CHx_RETURN_DRIVER
                                                 |
                                      current-driver CHx_B_BR
```

J100/J200 expose `A_ROUTER`, `RETURN_LOAD` and bench ground for the two source
interfaces. Connect `RETURN_LOAD` to the existing
[monitoring cell](../monitoring-cell/README.md) load-side return. Its driver-side
return connects to the [current driver](../current-driver/README.md) `B_BR`.
**Retain that existing 2 ohm signed-current monitor path.** There is no new
shunt in this package, no direct router shortcut to `B_BR`, and no connection
to the recording interface's reference or body-bias contact.

TMUX6208 supports a valid 24 V single supply and rail-to-rail analog signals.
It was selected for this restricted slice in place of the higher-voltage
TMUX8108. Its primary 12 V and 36 V tables do not establish a complete 24 V
worst-case model. Powered-off paths, over/undershoot, charge injection,
capacitance, leakage and stuck switches remain relevant. See the
[component review](../../../docs/stage4/contact-router-component-review.md)
and the [manufacturer datasheet](https://www.ti.com/lit/ds/symlink/tmux6208.pdf).

## Candidate preload and frozen active addresses

U10, **SN74LVC595APWR**, stores eight pending address bits. Its shift clock and
preload-latch clock are separate from `ROUTE_COMMIT`. Candidate data can change
without moving the active route. QA-QD are source 0 bits 0-3; QE-QH are source 1
bits 0-3. When using a conventional eight-bit MSB-first serial write, send source
1 bit 3 first and source 0 bit 0 last, then pulse `ROUTE_PRELOAD_LATCH`.

Two **SN74LVC157APWR** data multiplexers feed eight **SN74LVC1G74DCUR** active
address flip-flops. When `QUIET_SAFE` is false, their D inputs feed back the
current active Q bits. When it is true, D selects the pending bits. All eight
active flip-flops receive the **unconditional raw `ROUTE_COMMIT` clock**.
Readiness never gates that clock or creates a commit edge when it recovers.

```text
BASE_HEALTH = RESET_READY & RAILS_QUALIFIED & WATCHDOG_OK
              & AFE_ISOLATED_READY & CH0_MON_PERMIT & CH1_MON_PERMIT

QUIET_SAFE = BASE_HEALTH & CH0_QUIESCENT_OK & CH1_QUIESCENT_OK
             & !CH0_WANT_ROUTE & !CH1_WANT_ROUTE
             & !CH0_REQUEST & !CH1_REQUEST & !CH0_RUN & !CH1_RUN

on raw COMMIT rising: active_address = QUIET_SAFE ? pending : active_address
```

`WANT_ROUTE` remains asserted across the positive phase, interphase gap,
negative phase and recovery. A temporary phase-low interval therefore cannot
authorize a reroute. To change the route, explicitly release both intents,
stop both phase requests, observe both drivers quiescent and allow the bank
outputs to turn off before COMMIT. Required pre-edge setup/hold and all-off
timing are physical protocol obligations, not consequences of an ideal Boolean
simulation. The circuit does not use COMMIT's own inhibit as evidence of quiet.

## Fresh verification and explicit rearm

Any COMMIT clears the previous route validation and readback acknowledgement.
`COMMIT_SEEN` records whether that edge occurred with `QUIET_SAFE` true. An
illegal commit holds the active addresses, records rejection and consumes the
prior permission.

J6 exposes all **eight actual active Q bits** for external readback. After
checking those bits against the requested addresses, the external controller
must issue a **fresh rising acknowledgement** on
`ROUTE_ACTIVE_BITS_VERIFIED`. A flag held high through COMMIT cannot acknowledge
the new route. The native `READBACK_SEEN` latch records that fresh event; it
does not compare the bits itself or observe the analog multiplexer position.
A wrongful fresh acknowledgement remains a stated external failure case.

Then a separate raw `ROUTE_REARM` edge captures:

```text
ROUTE_VALID = COMMIT_SEEN & READBACK_SEEN & QUIET_SAFE
```

After rearm, assert the required source intent, allow the analog route to
settle, and only then admit a phase. Both the all-off guard and route-settling
allocations are provisionally **25 microseconds**. These are explicit design
allocations; they are not validated 24 V switch or tissue-recovery bounds.

Health loss clears the accepted commit, acknowledgement and route validation.
Health restoration alone cannot restart a route. `RESET_READY` low also resets
the active addresses to zero, while all outputs remain inhibited until the
full commit, fresh verification and rearm sequence is completed.

## Shared-contact collision

Four actual XOR gates and an OR/inverter tree compare all four active address
bits, including the bank bit. If both source intents request the same contact,
native logic disables **both sources** and asynchronously clears validation.
There is no priority winner. Removing the conflict does not restore permission;
release both intents, establish quiet and explicitly rearm.

`ROUTE_COMMAND_READY`, `CHx_ROUTE_EN` and `CHx_ROUTE_LOCKED` are **digital command
status**. The latter can supply the existing driver's route-admission input,
but its name does not establish observed switch position, contact continuity,
isolation or delivered current. Different contacts also remain coupled through
shared tissue impedance; the digital collision check does not separate those
physical fields.

## Verification and scope

Run the default read-only verifier:

```powershell
& 'E:\Project SCCI RH\.venv\Scripts\python.exe' -X utf8 `
  'E:\Project SCCI RH\electronics\stage4\contact-router\verify_contact_router.py'
```

It checks all exported values, footprints and pin nets, actual package pad
identity, the common/selected paths, separate returns, all raw flip-flop clocks,
individual bypasses and safe-default resistors. It evaluates **262,144 control
combinations**, **8,192 address/collision/bank combinations** and **21 ideal event
probes**. Event probes include candidate changes during a phase, an illegal
commit during each activity condition, the interphase gap, collision removal,
stale-high acknowledgement, health recovery and reset-to-address-zero.

Native KiCad CLI and the installed KiCad MCP both ran ERC on this saved
revision with **zero violations and no ignored checks**. MCP also inspected the
actual saved component/pin identity and found no symbol-bound overlaps on the
six sheets. It does not include unsaved editor changes or prove physical
clearances, because no PCB exists in this package. All six final PDF pages were
rendered and visually reviewed. Saved hashes normalize text line endings and
preserve exact PDF/PNG bytes; default verification never rewrites receipts.

Independent terminal cutoff, watchdog circuitry, compliance sensing,
rail/startup supervision, observed quiescence and recording isolation remain
external inputs or future circuits. So do actual mux-state detection, analog
fault bounds, propagation/metastability, PCB routing, firmware, populated CAD
and implant qualification. These boundaries allow this finished routing slice
to connect to the existing slices without claiming a completed implant.
