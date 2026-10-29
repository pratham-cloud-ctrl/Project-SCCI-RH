# Stage 4 entry: native electronics with measured delivery

**13 October 2026 · SCCI_RH-S4-ENTRY-01 · detailed design in progress.**

**Latest, 14 October firmware checkpoint:** the
[actual nRF5340 application](nrf5340-firmware-design.md) now builds from SCCI_RH
production sources, with explicit peripherals, sample/endpoint records, route
readback, companion admission and timer/DPPI cutoff. Its lower-rate implemented
profile supersedes earlier proposed target-rate shorthand; known gaps and
unmeasured physical timing remain explicit. The new four-chip sideband carrier
and nRF5340 controller must enter the consolidated PCB, the last Stage 4 package.

**14 October monitoring/companion checkpoint:** the
[native power package](power-design.md) supersedes this entry plan's one-cell/
100 mA allocation with a protected 2S reference and nine generated rails.
The [monitoring/companion package](monitoring-transport-design.md) resolves the
450k aggregate conversion mismatch through a separate raw ADC, adds explicit
charge endpoint arbitration and isolated UART, and revises the conditional
budget to 2.800 W/5.497 h. Compact thermal closure remains unearned. Seven native
slices are complete within their scopes; target firmware and consolidated PCB
remain. The table below retains the historical entry assumptions where later
named packages have superseded them.

The conservative Stage 3 investigation and conditional concept v1 now have
separate completed scopes. Their [declared future-interface premises](../stage3/conditional-concept.md)
guide this electrical design without requiring prior human demonstration of the
whole concept. The complete objective
remains implanted spinal recording → interpretation → personalized stimulation
→ independently observed response → feedback, with assistance-OFF learning and
a separately calibrated physiological function. This document selects the next
electrical investigation, not an implant-ready implementation.

## First useful native circuit

Build **SCCI_RH-S4-MON-01**, a two-source current/phase-charge monitoring cell, under
[the new electronics directory](../../electronics/stage4/monitoring-cell/README.md).
Each source gets a separate output-path Kelvin shunt, bidirectional sense
amplifier, continuously integrating charge channel, endpoint ADC and latched
current-window comparator. Explicit external interfaces supply the current
drivers, routing, differential compliance evidence, independent watchdog/rail
supervision and MCU. These interfaces must be implemented before the full circuit
can operate; a connector is not a tested supervisor or driver.

This slice attacks the largest measured electrical problem. The preserved
[precision analysis](../stage3/motor-precision-requirements.md) identifies
264.672 nC uncertainty at 600 nC nominal phase charge: **44.112%**, of which
250 nC comes from the two-edge allowance. Raising the old ADC rate cannot simply
remove this term because its shared ADC/bus does not support MHz per source.
Continuous analog integration is a concrete alternative to investigate. It does
not automatically make the full waveform, integration window or leakage known.

The first native schematic is an **artificial-load monitoring slice**. Its
connectivity and exports can be checked now. Precision, analog stability, fault
coverage, power transients, output drivers, PCB and chronic implanted suitability
remain separate work. Preserve the earlier one-channel 5 V reference and host C
pulse state machine unchanged; neither implements this Stage 2 envelope.

The native revision now uses production OPA391DCKR parts with corrected pin
mapping; see the [package review](../../electronics/stage4/monitoring-cell/design-review.md).
An [initial independent behavioral study](../../electronics/stage4/monitoring-study/README.md)
adds 33 two-source transient runs and 462 phase/gap/tail/net intervals on three
grids. It identifies bias bypass, reset-baseline, finite-response, cancellation,
ADC-allocation and clipping limitations. Separate KCL/matrix-exponential checks
verify its stated equations. Its 3 mA/200 µs nominal fixture and selected stress
cases do not complete the broader waveform/load/rail/fault coverage below, and
the proposed 4% precision remains unearned.

The historical [driver design boundary](current-driver-design.md) now has a
[native implementation](../../electronics/stage4/current-driver/README.md):
156 components, 572 checked pins, five sheets, zero ERC violations and local
package libraries. The [component review](current-driver-component-review.md)
corrects DAC reference headroom and exact package/pull contracts. The
[control contract](current-driver-control-contract.md) adds sticky interruption
state and direction capture while inhibited. Its healthy timer is not a complete
watchdog or delivered-charge guard.

The [closed-servo behavioral study](../../electronics/stage4/driver-study/README.md)
retains 20 attempted transients (18 complete; two partial out-of-compliance
traces), both polarities/sources and 144 complete intervals. Fifteen finite
digital history groups complement the native gate checks. Native connectivity,
the chosen analog surrogate and ideal Boolean histories remain distinct scopes;
neither package earns the proposed 4% precision or a completed implant.

## Architecture retained from Stage 2

| Responsibility | Detailed-design allocation and implementation boundary |
|---|---|
| Spinal acquisition | Retain 16 differential streams at 4 kHz, one shared reference and one separately current-bounded bias contact. RHD2216 remains a feasibility candidate. Its multiplexed apertures, two-command result pipeline, ±5 mV AC range and input common mode must be explicit. Input protection, reference fanout, bias, clipping and artifact recovery need native circuit evidence. |
| Compute | Retain nRF5340 application/network separation, finite flash/RAM, three reserved serial services and local timer/DPPI edge ownership. A linked target image and resource/peripheral schedule are required; desktop tests do not measure MCU deadlines. |
| Output | Two independently regulated physical current sources; at most two concurrent. Retain 16 selectable contacts and two dedicated returns. Initially admit disjoint routes only; motor and pressure applications remain exclusive. Current magnitude and biphasic reversal are separate from task-level correction sign. |
| Routing | Preload address, polarity and DAC state only while output is inhibited. Lock the pair through both phases and recovery. Enforce discharge, observed zero current, route ownership and source availability before reconfiguration. No make-up pulses. |
| Delivery | Independently record cathodic charge, anodic charge, net charge, measured current, terminal voltage, support/availability, route evidence, clipping, interruption and unknown residuals. Driver feedback and commanded DAC values are not delivery measurements. |
| Faults | Analog current-window latch plus separate waveform-duration, compliance, rail/brownout and watchdog supervision. Fault causes inhibit new output; interrupted charge remains uncertain. A software “finish balancing” rule cannot override an electrical emergency. |
| Pressure mode | External timestamped SBP remains the observed feedback; only calibrated pressor authority. Three 120 Hz profiles at 0/2/4 ms time-share source 0. Dense stimulation does not qualify continuous neural recording. |
| Power/telemetry | Retain 3.0–4.1 V battery operating range, nominal 3.6 V, chosen 100 mA average-cell cap, normal payload 160 kbit/s and separate 1 Mbit/s raw service. Actual native component energy and through-tissue payload remain unqualified. |
| Physical identity | Retain 36 functional ports and current package allocation as references. Populate native CAD only after circuit parts, connector/feedthrough arrangement, keepouts and height have been reconciled. The existing can/board solids are allocation envelopes. |

The authoritative starting contracts are [system-design.json](../stage2/system-design.json),
[control-contracts.json](../stage2/control-contracts.json),
[port map](../stage2/functional-port-map.csv),
[electrical source audit](../stage2/electrical-source-audit.csv) and
[system source audit](../stage2/system-source-audit.csv).

## Component choices and alternatives

Manufacturer documents were retrieved **12 October 2026**. Values below retain
their stated conditions; typical specifications are not guaranteed bounds.

| Candidate | Primary facts and design decision |
|---|---|
| **INA241A2**, first full-envelope sense candidate | Gain 20; −5…110 V operating common mode; 2.7…20 V supply. The A2 offset maximum is **15 µV**, not the family's 10 µV headline. Its A-grade gain maximum is 0.01% under the specified conditions. The 1.1 MHz bandwidth is typical. Use a separately sensed 2 Ω shunt and 5 V supply in this slice. Its input bias and power are material limitations below. [Datasheet, pin table and electrical tables](https://www.ti.com/lit/ds/symlink/ina241a.pdf). |
| **INA190A1**, lower-power restricted alternative | Bidirectional gain 25 with tens-of-kHz bandwidth and approximately 50 µA typical current; the page/table maximum depends on grade/conditions and reaches 90 µA. Its −0.2…40 V operating common-mode range **cannot cover the 48 V rail**. A separately named 24/36 V-only revision could test its slower settled-integral path and input leakage advantage. It is not a drop-in full-envelope selection. [Datasheet](https://www.ti.com/lit/ds/symlink/ina190.pdf). |
| **INA282**, lower-current full-voltage alternative | −14…80 V bidirectional operation, 0.9 mA maximum quiescent current, but 10 kHz bandwidth, up to 70 µV offset and 1.4% gain error on the product specification. It needs much longer tail observation and tighter calibration evidence. Do not select it on IQ alone. [Manufacturer product/datasheet](https://www.ti.com/product/INA282). |
| **OPA391DCKR**, integrator and endpoint buffer | Production DCK package; its different pin mapping is checked in the native design. Single amplifier avoids unused channels; 1.7…5.5 V supply, 1 MHz typical GBW, 23.5 µA typical / 32 µA full-temperature maximum quiescent current under the stated conditions. Stability, settling, ADC-drive and PCB land-pattern review remain required. This replaces the initially considered 1 mA/channel OPA192 for this low-voltage monitoring function. [Datasheet](https://www.ti.com/lit/ds/symlink/opa391.pdf). |
| **TMUX1136**, integrator reset | Two low-voltage SPDT paths; tie each B terminal across its feedback capacitor, leave A unconnected. Low select resets; high select integrates. This is a **5 V-domain reset switch**, never an HV electrode router. Include injection, leakage, reset completion and powered/unpowered behavior. [Datasheet and truth table](https://www.ti.com/lit/ds/symlink/tmux1136.pdf). |
| **ADS8866**, one endpoint ADC per source | 16-bit, 100 kSPS. **AVDD 2.7…3.6 V**, DVDD 1.65…3.6 V and reference 2.5…5 V: this design uses 3.3 V analog/digital and 4.096 V reference, not 5 V AVDD. Maximum INL is ±2 LSB under specified conditions. Each reference needs ≥10 µF local decoupling. [Datasheet](https://www.ti.com/lit/ds/symlink/ads8866.pdf). |
| **REF3440**, reference candidate | 4.096 V, four-wire sense/force connections, specified initial accuracy/drift and capacitive-load conditions. Shared reference faults remain correlated; ADC/reference health needs independent checking. [REF34 datasheet](https://www.ti.com/lit/ds/symlink/ref34.pdf). |
| **TLV3202 + SN74LVC1G11 + SN74LVC1G74**, latched window | Two comparators report inside-upper and inside-lower bounds. Their AND with external supervision asynchronously clears a D latch; explicit rearm clocks in permission only while all conditions hold. Comparator delay is not total shutdown latency, and the shared sense amplifier is a common failure point. [Comparator](https://www.ti.com/lit/ds/symlink/tlv3202.pdf), [AND](https://www.ti.com/lit/ds/symlink/sn74lvc1g11.pdf), [latch](https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf). |
| **TMUX8108**, HV routing feasibility witness | A 100 V supply-difference, bidirectional 8:1 mux with break-before-make and low-state disable. Two per source could address 16 active contacts while retaining dedicated returns. Four devices have substantial HV quiescent power; power-off analog isolation is not implied by fail-safe logic. Evaluate against discrete back-to-back MOSFET routing before committing a full matrix. [Datasheet](https://www.ti.com/lit/ds/symlink/tmux8108.pdf). |

RHD2216 and nRF5340 remain candidates from the primary
[Intan documentation](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)
and [Nordic product specification](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/keyfeatures_html5.html).
The existing LT8365 power candidate remains an investigation, not a proven 3 V
to 48 V converter: [manufacturer datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/LT8365.pdf).
No catalog, automotive or “medical application” designation establishes chronic
implant qualification, hermeticity, electrode chemistry or biological efficacy.

## Phase-resolved charge mechanism and precision target

For each source, nominal `Rshunt=2 Ω`, sense gain `Gs=20`, integrator input
`Rint=10 kΩ`, feedback `Cint=22 nF`, and a buffered `Vmid=2.048 V` give

```text
Vsense = Vmid + 40 V/A × Ireturn
Qhat = −(Rint Cint / 40) × (Vintegrator_end − Vintegrator_start)
600 nC → 109.091 mV; 10 µC → 1.81818 V
ADC ideal LSB at 4.096 V = 62.5 µV → 0.34375 nC
```

These are nominal transfer calculations, not an uncertainty claim. A 22 nF
feedback capacitor needs a specified low-absorption dielectric, voltage/temperature
coefficient and tolerance or independent gain calibration; a generic X7R label
would not justify precision integration.

Open reset before output enable and measure a baseline. Keep the integrator
continuous through cathodic phase, the 100 µs gap, anodic phase and current tail.
Take separately identified endpoints after the first current tail and after the
second tail, plus repeated settled endpoints and final net/tail observations.
First-minus-baseline and second-minus-first yield distinct signed phase charges;
final net alone can cancel and cannot certify either phase. If the observed
settling/window does not fit inside the gap, reject phase separation rather than
labeling a command edge as the actual boundary. Unexpected polarity reversal or
unbounded interior variation invalidates a signed-integral-only phase bound.

The full uncertainty must include scale/tolerance, offset/drift, reference/ADC,
reset/injection/leakage, unobserved interval/tail area, finite front-end response,
phase attribution and **current bypassing the shunt**. A proposed 4% nominal
target is **24 nC per 600 nC phase**. An initial design allocation is 6 nC scale,
2 nC offset, 1.5 nC endpoint conversion, 1.5 nC reset/hold, 10 nC waveform/window,
and 3 nC bypass. These are allocated maxima to test, not achieved component
specifications. In particular, INA241's input-bias paths do not presently earn
the 3 nC bypass allocation. Failure of any allowance blocks the 4% claim.

An opposite-phase endpoint difference includes intervening gap/recovery current;
phase attribution needs measured zero tails or a retained interval for that
charge. ADS8866 samples at the CNV edge plus aperture delay, before its result
becomes available. Enforce DIN high at that edge and CNV high through readout in
the selected four-wire mode. Buffer overload, ADC clipping and unknown integrator
history reject certification; input protection against a 5 V buffer fault is
still required. Reset injection is amplified by `Rint/(gain × Rshunt) = 250`
in electrode-equivalent charge: an unobserved differential 6 pC jump between
endpoints becomes 1.5 nC, exhausting the proposed reset allocation. A settled
baseline after reset opens can cancel a fixed initial jump; do not add it twice.
Settling, headroom, leakage and later reset edges still need bounds. A typical
charge-injection value does not supply a bound.

The [observed steady-map requirement](../stage3/delivery-requirements.md) links
4% to an illustrative 8 mm forecast input, while the 15 mm input demands below
0.5%. It does not establish that this monitor, a predictor or a coupled controller
achieves either condition. Current dynamic results still reject actual-monitor
domains, and [sparse assisted baselines](../stage3/sparse-baseline.md) still fail
their 15 mm allocation. New circuit evidence must enter a separately versioned
mechanism experiment; it cannot overwrite the preserved actual-negative branch.

## Material power, leakage and capacity findings

- Two INA241 channels at 5 V and 3.2 mA maximum each give **32 mW**, before
  integrators, ADCs, reference, comparator, other-health ADC or routing. The old
  **20 mW monitor/reference/gate allocation is exceeded**. Five OPA391 channels
  add about 0.8 mW using their stated 32 µA maximum at 5 V; dynamic loading is
  additional. Revise the complete power/thermal budget openly.
- INA241 lists **25–45 µA input bias per input**. Those paths can draw current
  from either shunt terminal into supply/ground, creating measured-versus-load
  current differences and a body-reference leakage path. Model both explicitly.
  One load-side 45 µA input over 200 µs already corresponds to 9 nC, exceeding
  the proposed 3 nC bypass allocation. Two 45 µA paths over 200 µs correspond to 18 nC if their full current bypasses
  the measured return, already 3% nominal charge. Their actual topology matters;
  this is a stress allocation, not asserted realized leakage. The artificial-load
  slice does not qualify isolated chronic returns.
- Four TMUX8108 routers at 48 V use approximately **48 mW typical / 96 mW with
  500 µA per-device VDD current**, excluding switched signal loss and any other
  rail current. That alone exceeds the old 8 mW driver-quiescent allocation.
  These are inference calculations from datasheet currents, not a selected router
  board's measured power. Evaluate a lower-leakage/lower-power route architecture.
- Keep the old current/voltage/health ADC service at 450 ksample/s for its declared
  two-source case; with 16-bit words and 10% overhead it needs 7.92 Mbit/s.
  The separate endpoint converters avoid pretending to sample both currents at
  MHz rates on this bus. Budget conversion bursts, CS transactions, reference
  settling and arbitration explicitly. At eight endpoints/event and the selected
  pressure pattern, 360 events/s gives 2,880 endpoint conversions/s for source 0.
  This average does not prove gap-time service; both sources need simultaneous
  conversion and separately identified readout.
- An 8,192-byte monitor buffer cannot hold two 5 ms raw blocks at
  450 ksample/s ×2 bytes (9,000 bytes). Investigate two 2.5 ms sub-buffers
  (4,500 bytes total) and include headers, endpoint packets and DMA alignment.
  This is a proposed native buffering revision, not a change to saved Stage 3.

## Concrete completion tests

1. **Native connectivity:** pin-by-pin manufacturer audit, local library tables,
   KiCad schematic export, unexcluded ERC and exported netlist comparison against
   an explicit connection manifest. Unimplemented external inputs must remain
   named and documented; a clean ERC is not analog validation.
2. **Phase-charge evidence:** independent transient integration of actual load
   current versus endpoint estimates for both signs, 50/200/300/500 µs phases,
   0.1/3/20 mA, admissible and deliberately rejected charge combinations,
   16/24/36/48 V rails, the Stage 2 R/C load set, initial polarization and both
   sources aligned/staggered. Retain failures; do not derive all tolerances from
   nominal gain. Use event-aligned steps plus at least two refined grids.
3. **Monitor faults:** shunt-open/short, input leakage, sense saturation, reset
   stuck open/closed, ADC stale/missing/wrong identity, reference/rail movement,
   interphase tails, reversal and oscillatory/spike injections. A near-zero final
   integral with large opposed phases must not pass. Publish full interval/error
   budget and coverage; target 24 nC only in the explicitly tested motor domain.
4. **Guard and compliance:** simulate amplifier delay, comparator offset/hysteresis,
   latch/driver delay, overshoot and current before final isolation. Verify inhibit
   dominates rearm, watchdog/rail loss clears permission, and recovery never makes
   an automatic opposite pulse. Differential terminal voltage/compliance and
   independent duration supervision remain required even if charge is accurate.
5. **Routing and AFE:** prove no live switching or shared-contact admission,
   route readback/continuity checks, power-off isolation, leakage/capacitive
   injection and recording saturation/recovery. Evaluate RHD common mode and
   shared-reference loading with the full route model; preserve invalid masks.
6. **Embedded resource closure:** target build, linked app/network memory,
   measured or conservatively modeled peripheral schedule, 250 µs rearm,
   11.85 ms computation allocation, clock uncertainty and plan expiry. Retain
   execution-time prediction and residual-guard contracts; no future observations.
7. **System closure:** regenerate power/current/heat/runtime/bus budgets with
   actual components; check low-cell and simultaneous-source peaks. Populate
   PCB/CAD only after that revision, then ERC/DRC, clearance, height and assembly
   interference. An insufficient old package or power allowance must be revised.

The machine-readable [requirements trace](requirements-trace.csv) associates
these tests with the Stage 2/3 inputs. No positive biological result is needed
to make a useful circuit investigation, and passing circuit tests does not close
the motor-learning or function-specific physiological hypotheses.

## Available tools and next work order

The installed inventory was inspected read-only: KiCad **10.0.6** freshly
responded to its CLI; existing FreeCAD, build123d, Blender and KiCad's ngspice
library paths remain available under `E:\project workspace assests`. The
[Stage 3 tool inventory](../stage3/tool-inventory.json) records the prior smoke
tests; their success is not relabeled as a new whole-suite test. GitHub identity
was freshly checked as `pratham-cloud-ctrl`; no account secret is recorded here.
No new paid software or student entitlement is needed for this slice. The
existing Ansys caveats remain. Target Nordic/Arm tools need a separately verified
stable supported installation when target firmware starts.

The [target-tool setup](firmware-toolchain.md) records the signed Nordic
installer, matching SDK/compiler and successfully linked unmodified nRF5340
application-core example. The later [actual SCCI_RH firmware](nrf5340-firmware-design.md)
is a separately built target implementation with its own evidence and limits.

Work in order: **native monitor slice → independent transient/error budget →
driver/routing and separate supervisory circuits → AFE/power/target firmware →
whole-system budget revision → populated PCB/CAD**. The monitor and restricted
driver now have native sources and finite initial studies. The
[protected recording front end](recording-front-end-design.md) now adds seven
native sheets, isolated SPI/control and finite input/protocol studies. Timing
and power changes explicitly revise the historical Stage 2 proposal; weak-signal
and recovery allocations remain unearned. The [native contact router](contact-router-design.md)
now adds held addresses, two sixteen-way selectors, fixed monitored returns and
collision/fresh-acknowledgement admission. Its analogue and readback limitations
remain explicit. The [native supervision package](supervision-design.md) now
adds 18 downstream terminal guards, separate phase timers/watchdog, rail/current/
pair-voltage/RHD-pin windows and sticky admission across 22 sheets. Its 102-wire
integration plan and finite audits close the independent shutdown slice under
declared assumptions. The [power/budget package](power-design.md) is now complete
within its digital reference scope. Monitoring/companion interfaces and actual
target firmware are now implemented. The [integrated populated board set](../../electronics/stage4/integrated-pcb/BOARD_INDEX.md)
completes the bounded electronics package; its [exit review](exit-review.md)
defines the remaining evidence limits. Preserve old studies and assign new
source, calibration, profile and uncertainty IDs to each revision. Stage 5
mechanical assembly follows.
