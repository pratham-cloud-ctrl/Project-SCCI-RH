# SCCI_RH-S4-DRV-01 - two-source current driver and admission circuit

**13 October 2026 - native editable digital design - artificial electrical loads only**

Open [current_driver.kicad_pro](current_driver.kicad_pro) in KiCad and open its
schematic editor. This package contains **156 components and five native sheets**:
one shared DAC/interface sheet, two analog driver sheets and two permission/timer
sheets. It has local symbols and footprint snapshots, a [five-page schematic
PDF](current_driver.pdf), [BOM](bom.csv), [pin/net manifest](connectivity.json),
[XML netlist](current_driver.xml), [native netlist](current_driver.net) and
[individual SVG sheets](svg/). The root and analog sheets use A3; the permission
sheets use A2 so their gates, latches and bypass parts remain readable when zoomed
or printed at the intended page size.

On this laptop, [OPEN_IN_KICAD.cmd](OPEN_IN_KICAD.cmd) launches the verified
installed KiCad explicitly, avoiding Windows file-association ambiguity. Other
machines can open the project from their KiCad installation.

This is a concrete circuit slice of Project SCCI RH's future spinal
recording-interpretation-stimulation-feedback system. Its selected operating
study is **24 V, approximately 3 mA, 200 microseconds per commanded phase**.
It does not implement the full architecture's 48 V/20 mA envelope, a 16-contact
router, recording front end, PCB or completed implant.

## Actual current and feedback paths

Each source has its own OPA192 servo, BSP89 sink, 100 ohm feedback resistor,
TMUX7212 four-switch bridge and two TMUX6219 switches. The two sources share
the DAC and supplied rails, so those remain common failure points.

```text
VH_24 -> selected upper switch -> A_BR
                                  |
                    external router and artificial pair load
                                  |
                  external signed monitor shunt, 2 ohm
                                  |
                B_BR -> selected lower switch -> BSP89 drain
                                                   |
                                     source / Kelvin sense
                                                   |
                                                100 ohm
                                                   |
                                                  GND
```

The diagram describes the positive direction. In the negative direction the
bridge exchanges which load terminal is connected to VH and to the sink. Native
SEL1/SEL4 form the positive diagonal; SEL2/SEL3 form the negative diagonal. With
RUN low all four commanded switch paths are open.

The 100 ohm resistor closes the current-regulation loop; it is **not** the
independent signed load-current monitor. The external 2 ohm monitor shunt must
remain between the artificial load's dedicated B return and B_BR. To connect
the existing [monitoring cell](../monitoring-cell/README.md), connect its
`CHx_RETURN_DRIVER` to this slice's `CHx_B_BR`, and its `CHx_RETURN_LOAD` to the
external load B terminal. Do not add a second 2 ohm shunt or move that shunt to
the sink's ground leg. The actual router, fixture and wiring are external.

With RUN low, the gate mux selects ground and the feedback mux closes local
unity feedback around the OPA192. This provides an explicit anti-windup state
instead of leaving the amplifier open-loop. RUN high selects the servo output
for the gate and the Kelvin source node for feedback. A 330 ohm gate resistor
and 100 kohm passive gate pulldown are drawn. C100/C200 are **DNP compensation
footprints**, not an assertion of loop stability. Switching skew, amplifier
recovery, device capacitance and parasitic paths still affect actual current.

All-off bridge commands and a grounded gate do not establish fail-open terminal
isolation. Analog switch clamps, monitor input bias, rail collapse and stuck
switches can create current paths outside the servo feedback measurement.

## Setpoint and package corrections

U1 is **DAC80502DRXR**. The exact DRX package has **ten lands and no central
exposed-pad connection**; the symbol and local footprint both use pins 1-10.
RSTSEL and SPI2C are grounded for zero-scale startup and SPI selection.
The reference has a nominal 220 nF bypass; its effective capacitance must remain
at least the manufacturer's 150 nF minimum. Supply bypasses are 100 nF and
4.7 microfarads.

Before external RESET_READY can rise, configure **GAIN register 0x04 to
0x0103**: divide the reference by two and use output buffer gain two on both
channels. This preserves a nominal 2.5 V output range while avoiding the
reference headroom problem of undivided reference at a nominal 5 V supply.
The chosen three-wire SPI interface is write-only; it does not provide register
readback. Independent setpoint/delivered-output verification remains required.

```text
I_nominal = code * 2.5 V / 65536 / 100 ohm
code 7864 -> 2.99987793 mA
200 microseconds -> 599.975586 nC ideal command charge
```

Those numbers are ideal arithmetic. DAC errors, resistor errors, settling,
switching and tails remain separate. Zero DAC code is not a physical disconnect.

The local BSP89 footprint preserves KiCad's generic SOT223 geometry but
explicitly numbers the large drain tab **4**, matching Infineon's package
contract. Lead 2 and tab 4 share the native drain net. The verifier checks the
actual local pad set is exactly 1,2,3,4. OPA192 uses the DBV pin table; the
TMUX7212 symbol uses its own pin table, which differs from TMUX8212. These
footprints are preliminary library lands; their geometry, mask, paste, thermal
layout and exact passive MPNs still require PCB/assembly review.

## Independent duration and sticky admission

Each source has its own LTC6993-1 non-retriggerable timer, direction latch,
consumed-admission BLOCK latch, sticky TIMEOUT latch and actual LVC logic gates.
The following equations are implemented by the exported native gate connections:

```text
VALID_DIR = PLUS_RAW XOR MINUS_RAW
BASE_GOOD = MON_PERMIT & EXT_SUP_OK & ROUTE_LOCKED
            & RESET_READY & RAILS_QUALIFIED & VALID_DIR
SAFE_REARM = REARM & BASE_GOOD & QUIESCENT_OK & !REQUEST & !TIMER

BLOCK /PRE = BASE_GOOD & !(TIMER & !REQUEST)
BLOCK /CLR = !SAFE_REARM
TIMEOUT D = TIMEOUT OR REQUEST; clock = rising edge of !TIMER
TIMEOUT /CLR = !SAFE_REARM

Direction D = PLUS_RAW; clock = SAFE_REARM rising edge
RUN = REQUEST & TIMER & BASE_GOOD & !BLOCK & !TIMEOUT
Positive diagonal = RUN & PLUS_LATCHED
Negative diagonal = RUN & MINUS_LATCHED
```

The timer receives the **raw request edge**, so restoring readiness cannot
manufacture a trigger from a request that stayed high. Any loss of BASE_GOOD
sets BLOCK. A normal request ending while the timer is still active also sets
BLOCK, consuming that admission without calling the normal end a timeout.
Restoring health or repeating the request cannot clear BLOCK. Holding a request
through the timer's falling edge records sticky TIMEOUT; the timer gates RUN
directly regardless of ambiguity in timeout classification near setup/hold.

Direction is captured at SAFE_REARM **while request and timer are both low**,
before the active phase. Changing raw direction during a phase cannot commutate
the bridge. An invalid raw direction drops BASE_GOOD and sets BLOCK. The external
controller must return REARM low and allow the captured direction and control
paths to settle before a fresh request; REARM is not an autorun level.

At startup the external supervisor must hold RESET_READY low through qualified
supplies and timer readiness, then explicitly rearm in an independently observed
quiescent state. This initializes BLOCK and the direction state; qualified rearm
clears TIMEOUT. Driver rearm does not rearm the separate monitoring-cell latch.
The native gates do not implement the external observation or supervisor.

RUN/DIAG pulldowns are **22 kohm**. Conservative specified leakage arithmetic
is 24 microamps x 22 kohm = 0.528 V for RUN and 14 microamps x 22 kohm =
0.308 V per diagonal. External health/control inputs and SPI defaults use
10 kohm. These are valid-supply/off-state leakage checks, **not** qualification
of arbitrary supply ramps or of asynchronous preset/clear hazards. SAFE_REARM
must be externally stable and nonoverlapping with fault transitions; a stable
Boolean truth table cannot establish physical hazard immunity.

The fixed timing network is RSET=175.8 kohm, with 976 kohm/182 kohm selecting
DIVCODE=2 and NDIV=64. Nominal timer OUT is **225.024 microseconds**, with
**214.907821-235.159981 microseconds** arithmetic using the stated full-temperature
timer error and 0.1% RSET tolerance. These are healthy timer-output bounds before
additional drift, logic delay and current tails. An open SET resistor can leave
a pulse active indefinitely; timer stuck-high and related faults require the
external independent supervisor/watchdog. The timer alone is not a complete
delivered-charge or single-fault protection system.

## What has been checked

[verification.json](verification.json) records:

- **156 components and 572 package-pin assignments** compared against the actual
  KiCad XML export, with independent critical pin tables and actual footprint
  pad-set checks.
- **Zero ERC violations across five sheets, with no ignored checks.** Passive
  external connectors explain why missing subsystems are not ERC errors; they
  remain explicit engineering gaps.
- **32,768 combinations** evaluated through the actual exported gate connections,
  including diagonal exclusivity, direct timer inhibition and qualified rearm.
- **20 ideal-event probes** using exported DFF/gate nets: startup inhibition,
  consumed admission, repeated requests, timeout, supervision recovery, invalid
  direction, captured direction and missing quiescent evidence.
- Five PDF pages rendered and manually inspected, with [retained review images](review/)
  and individual SVGs. These checks confirm readable native exports and logical
  connectivity; they do not demonstrate analog accuracy or biological efficacy.

The separate [driver behavioral study](../driver-study/README.md) investigates
conditional analog dynamics and fault counterexamples. It is a surrogate model,
not a vendor transistor/macromodel or simulation of every physical parasitic in
this native circuit. Its near-600 nC nominal phases must be read alongside its
onset peak, model failures and assumptions. Native ERC success does not turn
those numerical outcomes into component qualification. **No 4% delivered-charge
precision claim is earned by this package.**

## External boundaries

The following are deliberately external rather than omitted behind a completed
implant claim: regulated 24/15/5/3.3 V supplies and their startup sequencing;
the signed current/charge monitoring cell and its interface wiring; 16-contact
routing and route ownership; terminal disconnection and input-bias return
containment; differential compliance; an independent delivered-charge guard;
watchdog/reference/rail supervision; observed zero-current quiescence; MCU
firmware, duty/profile counting; spinal acquisition/protection; PCB and populated
CAD; chronic packaging and implant suitability. J1-J5 and J100/J200 expose
the native slice's supply, MCU, supervision, status and artificial-load contracts.

Two OPA192 servos at 15 V consume 30 mW typical and 45 mW full-temperature
maximum before dynamic loads. This exceeds the old 8 mW servo allocation; the
complete power budget needs a separately versioned reconciliation. A command
status pin does not establish actual delivery or residual charge. An interrupted
phase must preserve the monitoring history; no automatic balancing pulse or
retry is authorized by this circuit.

## Build and reproduce

For an audit of the saved package, normal Python is sufficient and the default
command is read-only:

```powershell
python verify_current_driver.py
```

To intentionally regenerate native sources and exports, run these from this
directory with KiCad CLI on PATH:

```powershell
python build_current_driver.py
kicad-cli sch export netlist --format kicadxml current_driver.kicad_sch -o current_driver.xml
kicad-cli sch export netlist current_driver.kicad_sch -o current_driver.net
kicad-cli sch export pdf current_driver.kicad_sch -o current_driver.pdf
kicad-cli sch export svg current_driver.kicad_sch -o svg
kicad-cli sch erc current_driver.kicad_sch --format json --exit-code-violations -o erc.json
pdftoppm -scale-to 2200 -png current_driver.pdf review/page
# Inspect all five rendered pages before intentionally refreshing the receipt.
python verify_current_driver.py --write-receipt
python verify_current_driver.py
```

`KICAD_SHARE` can override the generator's installed footprint-source directory.
Native files themselves use project-local symbol and footprint libraries.
KiCad 10.0.6 produced the saved exports. Text hashes normalize CRLF/CR to LF;
PNG/PDF hashes bind exact bytes. Local KiCad preferences, Python caches and
the verification receipt itself are excluded from artifact hashes.

Primary manufacturer links accompany each IC in the manifest/BOM. See the
[component review](../../../docs/stage4/current-driver-component-review.md),
[control contract](../../../docs/stage4/current-driver-control-contract.md) and
[design proposal](../../../docs/stage4/current-driver-design.md) for source
interpretation and the rejected alternatives. Local KiCad footprint snapshots
use CC-BY-SA 4.0 with the KiCad design exception; the BSP89 tab-number adaptation
is documented above. Attribution is in
[KICAD_LIBRARIES_LICENSE.md](../../KICAD_LIBRARIES_LICENSE.md).
