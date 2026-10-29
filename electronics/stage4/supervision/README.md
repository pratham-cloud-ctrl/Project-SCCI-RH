# SCCI_RH-S4-SUP-01 - independent shutdown and supervision

**14 October 2026 - native digital engineering package - artificial loads only**

Open [supervision.kicad_pro](supervision.kicad_pro), or use
[OPEN_IN_KICAD.cmd](OPEN_IN_KICAD.cmd) on this laptop. This package contains
**478 components, 1,699 compared pin connections and 22 native A2 sheets**,
local symbols/footprint snapshots, [BOM](bom.csv), [connectivity](connectivity.json),
[XML netlist](supervision.xml), [native netlist](supervision.net),
[schematic review PDF](supervision.pdf), [SVG sheets](svg/) and
[reviewed page renders](review/). The explicit hierarchy separates the physical
observations, phase timers, retained permission and body-facing guards.

This implements the next bounded electronics step in SCCI_RH's future spinal
recording, interpretation, learner-specific stimulation and feedback architecture.
It is not an implanted device or evidence that the conditional motor-learning
and physiological hypotheses work in people. Those hypotheses remain the
Stage 3 baseline; this package addresses electrical admission and shutdown.

## What the native circuits do

| Circuit | Actual realization |
|---|---|
| Terminal shutdown | Five TMUX7412FRRPR quads guard all 16 selectable stimulation contacts and both dedicated returns after the canonical router/monitor paths; 18 channels used, two grounded and disabled |
| Secondary duration | Two separate LTC6993-1 devices and independent 195.4 kohm setting resistors; raw REQUEST edges, nominal 250.112 microseconds |
| Heartbeat | TPS3431SDRBR, fixed nominal 200 milliseconds, wired WDO/ENOUT and a separate falling-heartbeat-seen latch |
| Supplies | Nine TPS3700 UV/OV windows measure six host/supervisor rails and three floating AFE rails; actual startup RC/Schmitt holds |
| Current quiet | Two TLV3202 windows around the existing INA241 output, threshold buffers, RC dwell and Schmitt receivers |
| Differential voltage | One dual OPA2192 senses both internal driver A_BR/B_BR pairs; independent TLV3202 compliance windows |
| Recording blank observation | Seventeen actual RHD-side pin/reference DC windows plus actual receiving-side CONNECT/ACQUIRE levels and island rail qualification |
| Isolated status | ISO6742F sends distinct AFE rail and blank status across the electrical barrier |
| Permission | Native LVC gates and FFs retain faults, consume phase permission and require deliberate quiet rearm |

The approximately 250 microsecond limiter and approximately 200 millisecond
heartbeat watchdog have different jobs. A heartbeat cannot bound a stuck phase
on a microsecond time scale, and neither timer measures delivered charge.

## Connect to the existing circuit packages

The integration mapping and finite studies live in
[the control contract](../../../docs/stage4/supervision-control-contract.md),
[the component review](../../../docs/stage4/supervision-component-review.md)
and the sibling [supervision study](../supervision-study/). The physical interface
identities are also present in the exported native pin/net manifest.

- J100 receives all 18 canonical contact-router J7 conductors. J101 supplies
  their body-facing artificial-load counterparts. Guards are **after** the
  router and dedicated return-monitor paths; the existing 2 ohm shunts are
  not duplicated or bypassed.
- J600-J615 connect to the existing `AFE_IN00_P`-`AFE_IN15_P` RHD-side nodes;
  J616 connects to `AFE_REF`. These are post-clamp physical voltage taps.
- J4 takes both existing current observations and monitor-permit outputs,
  plus the existing 2.048 V midpoint and 4.096 V reference. `CHx_MON_SUP_OK`
  connects to the old monitoring-cell supervisory input. It deliberately
  excludes global ARM and MON_PERMIT so monitor startup does not deadlock.
- J5 `CHx_EXT_SUP_OK` connects to the driver supervisory input. It includes
  global ARM but does not require REQUEST/TIMER/RUN, so the driver can rearm.
  These outputs and the monitor supervisory inputs are different nets even
  though the historical packages used similar local labels.
- J6 senses driver-internal A_BR/B_BR directly. A passing differential window
  is not proof of the body voltage, guard state or selected contact continuity.
- J2 takes the actual island receiving-side CONNECT/ACQUIRE nets. Neither
  host command copies nor an ordinary fault flag substitute for these taps.

On a fault, all 18 guards are commanded off and global ARM is consumed.
Returning health does not rearm. Clear a timeout only during observed quiet
with both raw requests, RUN statuses and secondary timers low. Then issue a new
SUP_REARM edge and separate source PHASE_REARM edges. Normal request termination
consumes that source's phase block. No automatic retry, compensating reverse
pulse or integrator reset is added here.

## Quantitative boundaries are retained

`I_MON = 2.048 V + 40 V/A * I` comes from the existing 2 ohm / gain-20 monitor.
The new nominal +/-10 mV quiet window means **+/-250 microamperes**, not zero
current. Full-temperature comparator offset, amplifier/reference error and
leakage widen that band. The 3.3 kohm / 10 nF dwell has a finite assumed Schmitt
threshold interval. A provisional 200 microsecond quiet allocation still
requires actual QUIESCENT_OK, secondary-timer-low and explicit rearm.

The recording island's revised nominal supplies are **3.45 V, +5.30 V and
-5.10 V**; familiar net names are retained. This is an explicit revision of the
older slice's nominal 3.3 V / +/-5 V assumption to accommodate real rail-window
hysteresis and the TMUX7412F dual-supply minimum. Converters, power budgets and
startup sequencing are the next package. Supervisor supplies are distinct
externally provided always-on 3.3 V / 5 V ports, not fabricated converters.

Each RHD voltage probe adds 10 Mohm to the physical input and 1 Mohm to the
island logic rail: approximately **0.314 microamperes per input at 3.45 V and
zero input voltage**. It is not a free measurement. Native threshold dividers
and OPA391 buffers define the actual DC windows; offset, bias, tolerance and
the added recording load remain in the accompanying study.

`AFE_ISOLATED_READY` is a historical interface alias for **observed blank
voltage and receive-control qualification under the healthy-switch assumption**.
A welded switch at zero voltage can satisfy those observations. They therefore
do not prove an open analog path, zero body leakage, protection against every
fault, valid neural data or digital-filter recovery. Shared references, sensing
failure, dual timer faults, common power, guard leakage/capacitance and alternate
body paths remain explicit limitations. The 4% dose-precision target is not
earned by this package.

## Reproduce and inspect

Run `python verify_supervision.py` for read-only saved artifact, exported pin/net,
footprint/pad, critical native circuit and MCP-revision checks. `--write-receipt`
is for intentional changes only, after fresh exports and visual review.
`build_supervision.py` regenerates only this new directory's design artifacts;
it does not edit the older packages or create a PCB. Native ERC is zero with no
ignored checks. The MCP receipt records real saved-file project, component,
pin, overlap and ERC queries; it makes no claim about an unsaved editor or PCB.

Power generation, complete monitoring/companion transport, target firmware,
the integrated populated PCB and populated engineering CAD remain subsequent
Stage 4/5 work.
