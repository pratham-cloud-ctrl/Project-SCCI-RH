# Current-driver component and interface review

**13 October 2026 — independent AI engineering review of the proposed 24 V, 3 mA, 200 µs digital circuit slice.**

The selected devices can support an inspectable, conditional current-driver design. Two corrections are adopted for the new native slice: configure the DAC reference divider with sufficient headroom, and use the actual ten-pad DRX package without an invented exposed pad. The timer is a healthy-component phase window; fresh-request admission, rearm, rail supervision and timer-fault coverage remain explicit external contracts.

This review checks manufacturer parts and circuit interfaces. It does not establish biological response or replace a closed-loop transient analysis. The [12 October proposal](current-driver-design.md) remains a historical handoff; this document records the subsequent corrections.

## Package and pin contracts

The following tables were independently checked against the primary documents linked below. Pin numbers refer to the named package, not a visually similar alternative. Local symbol/netlist agreement is a separate native export check.

| Selected part | Checked pin contract | Disposition |
|---|---|---|
| DAC80502DRXR, DRX WSON-10 | 1 VDD; 2 VOUTA; 3 RSTSEL; 4 AGND; 5 SPI2C; 6 SCLK; 7 SYNC; 8 SDIN; 9 VOUTB; 10 VREFIO | RSTSEL/SPI2C grounded. DRX0010A drawing has **ten lands and no central exposed pad**; visually checked. |
| OPA192IDBVR, DBV SOT-23-5 | 1 OUT; 2 V−; 3 IN+; 4 IN−; 5 V+ | Correct at 15 V/GND. Do not reuse the monitoring cell's OPA391DCK pin map. |
| BSP89H6327XTSA1, PG-SOT223 | 1 gate; 2 drain; 3 source; 4 drain tab | Manufacturer page-1 diagram visually checked. Both drain lands must connect to the same drain net. |
| TMUX7212PWR, PW TSSOP-16 | 1 SEL1; 2 D1; 3 S1; 4 VSS; 5 GND; 6 S4; 7 D4; 8 SEL4; 9 SEL3; 10 D3; 11 S3; 12 NC; 13 VDD; 14 S2; 15 D2; 16 SEL2 | Correct for the proposed two diagonals. NC may float or connect to GND. |
| TMUX6219DGKR, DGK VSSOP-8 | 1 D; 2 S1; 3 GND; 4 VDD; 5 EN; 6 SEL; 7 VSS; 8 S2 | EN=1: SEL=0 selects S1; SEL=1 selects S2. EN=0 disconnects both and is unsuitable as the sole grounded-gate default. |
| LTC6993HS6-1#TRPBF, S6 TSOT-23-6 | 1 TRIG; 2 GND; 3 SET; 4 DIV; 5 V+; 6 OUT | **-1** is rising-edge/non-retriggerable; **H** grade covers −40 to +125 °C. |

| 3.3 V logic part | Checked pins and function |
|---|---|
| SN74LVC1G86DBVR | 1 A; 2 B; 3 GND; 4 Y; 5 VCC. XOR. |
| SN74LVC1G32DBVR | 1 A; 2 B; 3 GND; 4 Y; 5 VCC. OR. |
| SN74LVC1G08DBVR | 1 A; 2 B; 3 GND; 4 Y; 5 VCC. AND. |
| SN74LVC1G04DBVR | 1 NC; 2 A; 3 GND; 4 Y; 5 VCC. Inverter; pin 1 is not a second input. |
| SN74LVC1G11DBVR | **Six pins:** 1 A; 2 GND; 3 B; 4 Y; 5 VCC; 6 C. Three-input AND. |
| SN74LVC1G74DCUR | 1 CLK; 2 D; 3 /Q; 4 GND; 5 Q; 6 /CLR; 7 /PRE; 8 VCC. Rising-edge DFF; /CLR=0 forces Q=0; keep /PRE high. Both asynchronous controls low is a nonstable state. |

The reviewed LVC inputs require VIH ≥2 V and VIL ≤0.8 V at VCC=3–3.6 V. Their 3.3 V outputs can drive the light logic/mux loads, but external pins must have defined states. Supply-off Ioff specifications limit backflow; they do not guarantee an asserted safety logic level during a rail ramp. Avoid slow or floating CMOS inputs. These are logic interfaces, not high-voltage level shifters.

Size the default resistors from leakage and fanout. A 100 kΩ pull-down with one 10 µA powered-off LVC output can reach 1 V, already beyond a mux's 0.8 V low limit. RUN feeds two mux selectors and two AND inputs: a conservative `10 + 2×2 + 2×5 = 24 µA` leakage allocation gives 0.528 V with **22 kΩ**, before resistor tolerance. Each diagonal's two selectors gives 14 µA/0.308 V with 22 kΩ. Use stronger pull-downs for shared high-fanout external qualification inputs as needed; 10 kΩ with 50 µA allocation gives 0.5 V. These budgets require compatible external drivers and do not qualify intermediate supply ramps.

## DAC correction and restricted settled-current calculation

Use GAIN register **0x0103**: REF-DIV=1, both output-buffer gain bits=1. The net output range remains 2.5 V. With REF-DIV=0 the allowed reference is at most 0.5×VDD; nominal 5 V leaves no margin for the 2.5025 V maximum initial internal reference or rail droop. Configure while inhibited.

For code 7864 and 100 Ω:

```text
Vnom = 7864 × 2.5 / 65536 = 0.29998779296875 V
Inom = 2.9998779296875 mA
DAC TUE = ±0.1% FSR = ±2.5 mV = ±25 µA at 100 Ω
Imin = (Vnom − 2.5 mV − 75 µV) / 100.1 Ω = 2.971156773 mA
Imax = (Vnom + 2.5 mV + 75 µV) / 99.9 Ω = 3.028656586 mA
Q200µs = 594.231355 … 605.731317 nC
```

This arithmetic combines table TUE, OPA192 offset and a **specified** 0.1% feedback-resistor tolerance. Do not add offset/gain/INL again on top of DAC TUE. The DAC specification has unloaded/end-point-fit conditions, codes 256–64511; code 7864 qualifies, but this is not a loaded-loop guarantee. Resistor temperature coefficient, CMRR/PSRR, finite gain, leakage and transients remain outside the calculation. DAC settling is typical, not a guaranteed launch delay. At 0.1 mA the same ±25 µA table bound alone is 25%.

## Gate reset, polarity and isolation

With RUN low, the gate mux selects GND and the feedback mux connects OUT to IN−; the amplifier follows the setpoint in local unity feedback. With RUN high, the gate connects to OUT and feedback to the Kelvin source node. This topology addresses off-state windup; it does not establish transition stability.

At 15 V, TMUX6219 accepts 3.3 V control (VIH=1.3 V). Its EN pin may be tied high in the qualified 15 V domain. A 330 Ω gate resistor limits an illustrative 15 V discharge to 45.45 mA before switch resistance. The DGK current table gives 100 mA at 125 °C for +12 V ±10%; **15 V is not that characterized condition**. Treat the clamp current, propagation skew and switch injection as circuit-study inputs, not a guaranteed discharge waveform. Retain a passive gate pull-down.

TMUX7212 is active-high and supports 4.5–44 V single supply. Thus 24 V is in range and 48 V is not. The proposed 10 Ω/channel is a simulation stress assumption, not a published 24 V maximum. Independent SPST channels do not enforce diagonal dead time. Their analog rail clamps remain connected when the switches are commanded off. Opposite phase requires an explicit all-off interval; all-off is not terminal isolation.

The low-side sink resistor measures unsigned sink current. Keep the separate signed return shunt in both phase paths. Monitor-input bias, bridge recirculation, common-mode capacitance and rail-clamp current can bypass that feedback measurement; the behavioural study must retain load and return currents separately.

## Healthy timer and rearm contract

For NDIV=64 and RSET=175.8 kΩ ±0.1%:

```text
tnom = 225.024 µs
tmin = 225.024 × 0.956 × 0.999 = 214.907821056 µs
tmax = 225.024 × 1.044 × 1.001 = 235.159981056 µs
```

Use the full-temperature **±4.4%** specification, not the ±3.4% room-temperature value. The 976 kΩ/182 kΩ divider gives 0.157168×V+ and 153.396 kΩ source impedance, inside the DIVCODE=2 window and 500 kΩ impedance limit. With ideal resistors, maximum 10 nA DIV leakage shifts that ratio by 0.000465 at 3.3 V. Specify divider tolerances and timing-resistor drift. Typical startup is approximately 1.758 ms, not a guaranteed ready deadline.

An open RSET can reduce ISET below approximately 500 nA and **prevent the pulse from ending**. The external watchdog must cover this fault. Non-retriggerability only ignores edges during a healthy active window.

The following circuit-level interface conclusions informed the new implementation:

- The rejected `TRIG = REQUEST & GOOD` creates a trigger when GOOD restores while REQUEST is held high. The selected implementation clocks the timer from **raw REQUEST** and puts health/admission in the independent output gate.
- `RUN = REQUEST & TIMER_OUT & GOOD` alone permits interruption and resumption inside one timer window. The new **BLOCK latch** sets asynchronously on a health failure or request ending while TIMER_OUT remains high. Health recovery cannot clear it.
- Deliberate **SAFE_REARM** requires health good, REQUEST low, TIMER_OUT low and externally observed quiescence. It clears BLOCK/timeout and clocks a direction latch; the captured direction drives the bridge. Release and settle rearm before the next fresh request edge. The external observer/supervisor is a required subsystem, not implemented by those input names.
- Timeout uses `D = TIMEOUT | REQUEST` at timer fall. A distinct source cannot clear its neighbour's latches. Clearing/resetting a status record is not proof of delivered charge.
- At 3.3 V the selected DFF requires data setup 1.3 ns, hold 1.2 ns and /CLR release recovery 1.2 ns. Request/timer coincidence is not deterministic timeout classification. The direct TIMER_OUT gate still interrupts RUN. Asserted asynchronous preset/clear must not overlap during admitted rearm; rail-ramp and propagation hazards remain circuit-analysis limits.

## Power and thermal arithmetic

| Contribution | Arithmetic and interpretation |
|---|---|
| Two OPA192 at 15 V | **30 mW typical; 36 mW maximum at 25 °C; 45 mW maximum over temperature**, before output charging. Exceeds the historical 8 mW driver allocation. |
| Shared DAC at 5 V | Internal-reference/static full-scale table: 1.9/2.6 mA → **9.5/13 mW** typical/maximum. SPI activity and external loads add power. |
| Two bridge ICs | Reusing the 44 V table's 44/105 µA at 24 V gives **2.112/5.04 mW** provisional arithmetic, not a guaranteed 24 V power bound. |
| Four gate/feedback muxes | The 12 V table gives 10 µA typical, 55 µA full-temperature maximum at its stated conditions. Multiplying by four and 15 V gives **0.6/3.3 mW**, a provisional estimate rather than a 15 V bound. |
| Logic | Most selected gates/latches specify 10 µA static maximum; the XOR permits 15 µA through 125 °C. At 3.3 V that is 33/49.5 µW per device, excluding intermediate-level input current and switching. Each asserted 22 kΩ/10 kΩ pull-down adds **0.495/1.089 mW** from its driving rail. |
| Timers | At 5.5 V, RSET=50 kΩ and NDIV≤64 the table specifies 165/200 µA typical/maximum. Do not call that an exact 3.3 V, 175.8 kΩ value. Two 200 µA stress allowances at 3.3 V give **1.32 mW**; two DIV dividers add **18.81 µW**. |
| Sink during a 3 mA phase | Conservative product ≤24 V×3 mA=**72 mW**. For 8.2 V terminal requirement and 100+2+20 Ω series loss, VDS=15.434 V and power=**46.302 mW**. |

BSP89's board-dependent RθJA values are 115 K/W at minimum footprint and 70 K/W with the stated 6 cm² copper test board. Continuous 72 mW would give 8.28/5.04 K arithmetic rises under those respective conditions. At 20 mA/48 V, 0.96 W gives 110.4/67.2 K; this is not an admitted operating point. Pulse average power is `I×VDS×(2×tphase×fpair)`, and transient temperature needs the SOA/thermal curves and actual PCB. The 240 V VDS and ±20 V VGS ratings, threshold and switching-time tables do not certify the 3 mA servo's linear dynamics.

## Primary manufacturer references

All links accessed **13 October 2026**. Page numbers are PDF pages; revisions are the documents actually reviewed.

| Source | Review locations |
|---|---|
| [TI DAC80502, SBAS793A Rev A](https://www.ti.com/lit/ds/symlink/dac80502.pdf) | pp.3–8 pins/limits/errors/power; p.31 GAIN; pp.44–46 DRX drawing/lands |
| [TI OPA192, SBOS620E Rev E](https://www.ti.com/lit/ds/symlink/opa192.pdf) | pp.4,8–9 DBV pins, static and dynamic conditions |
| [Infineon BSP89 Rev 2.2](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bsp89-datasheet-en.pdf) | pp.1–4 pin diagram, ratings, thermal, capacitance and SOA |
| [TI TMUX7212, SCDS416D Rev D](https://www.ti.com/lit/ds/symlink/tmux7212.pdf) | pp.4–6 PW pins/rails; electrical tables and §8.5 truth table |
| [TI TMUX6219, SCDS420E Rev E](https://www.ti.com/lit/ds/symlink/tmux6219.pdf) | pp.3–5 pins/current limits; p.10 12 V table; p.32 truth table |
| [ADI LTC6993 Rev F](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc6993-6993-1-6993-2-6993-3-6993-4.pdf) | pp.3–5 grade/timing/logic; pp.10–15 SET fault, DIVCODE, startup and variants |
| [TI SN74LVC1G86, SCES222R Rev R](https://www.ti.com/lit/ds/symlink/sn74lvc1g86.pdf) | pp.3–6 DBV pins/3.3 V limits/static power |
| [TI SN74LVC1G04, SCES214AF Rev AF](https://www.ti.com/lit/ds/symlink/sn74lvc1g04.pdf) | pp.3–6 DBV NC and inverter contract |
| [TI SN74LVC1G32, SCES219W Rev W](https://www.ti.com/lit/ds/symlink/sn74lvc1g32.pdf) | pin/electrical/function tables |
| [TI SN74LVC1G08, SCES217AA Rev AA](https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf) | pin/electrical/function tables |
| [TI SN74LVC1G11, SCES487I Rev I](https://www.ti.com/lit/ds/symlink/sn74lvc1g11.pdf) | p.3 six-pin DBV map; electrical/function tables |
| [TI SN74LVC1G74, SCES794G Rev G](https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf) | pp.4,6–7,10 DCU pins, logic/timing and asynchronous truth table |

## Native export crosscheck

The subsequent **156-component** XML export and connectivity manifest were checked read-only against the critical contracts above: DAC pins and 0x0103 configuration note, ten-pad DRX footprint, both OPA192 servos, both BSP89 drain/tab nets and four-pad adaptations, both TMUX7212 bridge maps, all six 22 kΩ RUN/diagonal defaults, and the 10 kΩ SPI/external-control defaults. These checks passed. A configuration note does not establish that firmware has programmed a physical DAC.

```text
current_driver.xml SHA-256
4356039793894c5bfb5ce25aee98e6a00fb8bc8c9ae3c9f5eb3ddc625b89b887
connectivity.json SHA-256
a9789000b06304fc514197f03ae972c86b484f459262fb4c84b8076392c17041
```

The native package can proceed using these corrections and explicit external contracts. Its acceptance is an editable circuit, checked connectivity and a bounded behavioural study; full-envelope isolation, power conversion and recording integration remain subsequent engineering work. This crosscheck did not verify a PCB, vendor transistor macromodel, power-ramp waveform or biological effect.
