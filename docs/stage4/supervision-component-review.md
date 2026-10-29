# Independent supervision: manufacturer review and design conditions

**14 October 2026 — Project SCCI RH, Stage 4 — digital circuit design.**

This review supports the independent shutdown package connecting the restricted
24 V, approximately 3 mA, 200 microsecond driver, recording front end, signed
monitor and contact router. The component facts below were checked against
manufacturer PDFs. A second timer, observed current/voltage windows and terminal
disconnects add distinct mechanisms; they do not establish a clinically qualified
implant, zero leakage or immunity to every common-cause failure.

## Package and pin witnesses

| Exact identity / package | Independent manufacturer pin witness |
|---|---|
| TPS3431SDRBR, DRB VSON-8 plus pad | 1 VDD; 2 CWD; 3 EN; 4 GND; 5 SET1; 6 WDI; 7 WDO; 8 ENOUT. Exposed pad is internally grounded and connects to GND. |
| TPS3700DDCR, DDC SOT-6 | 1 OUTA; 2 GND; 3 INA+; 4 INB−; 5 VDD; 6 OUTB. The DSE package has a different map. |
| TLV3202DGKR, DGK VSSOP-8 | 1 OUT1; 2 IN1−; 3 IN1+; 4 GND; 5 IN2+; 6 IN2−; 7 OUT2; 8 VCC. |
| OPA2192IDGKR, DGK VSSOP-8 | 1 OUTA; 2 INA−; 3 INA+; 4 V−; 5 INB+; 6 INB−; 7 OUTB; 8 V+. |
| LTC6993HS6-1#TRPBF, S6 TSOT-23-6 | 1 TRIG; 2 GND; 3 SET; 4 DIV; 5 V+; 6 OUT. The selected −1 variant responds to a rising trigger and is non-retriggerable. |
| TMUX7412FRRPR, RRP WQFN-16 plus pad | 1 S1; 2 VSS; 3 GND; 4 S4; 5 D4; 6 SEL4; 7 SEL3; 8 D3; 9 S3; 10 FF; 11 VDD; 12 S2; 13 D2; 14 SEL2; 15 SEL1; 16 D1. Pad is internally NC; connect to GND. |
| OPA391DCKR, DCK SC70-5 | 1 IN+; 2 V−; 3 IN−; 4 OUT; 5 V+. Do not substitute the DBV pin map. |
| ISO6742FDWR, DW SOIC-WB-16 | 1 VCC1; 2 GND1; 3 INA; 4 INB; 5 OUTC; 6 OUTD; 7 EN1; 8 GND1; 9 GND2; 10 EN2; 11 IND; 12 INC; 13 OUTB; 14 OUTA; 15 GND2; 16 VCC2. |
| SN74LVC1G17DBVR, DBV SOT23-5 | 1 NC; 2 A; 3 GND; 4 Y; 5 VCC. |
| SN74LVC1G74DCUR, DCU VSSOP-8 | 1 CLK; 2 D; 3 Q; 4 GND; 5 Q-bar; 6 CLR-bar; 7 PRE-bar; 8 VCC. |
| BAT54WS-7-F, SOD323 | Single diode, cathode identified by physical package band. Local footprint numbering 1 K / 2 A is the project's library convention. |

The witnesses are independent of schematic placement. Actual symbol roles,
footprint pads and exported connections must also agree; an ERC pass by itself
does not check these manufacturer identities. The exact switch selection uses
RRP, rather than the TSSOP package marked preview in the reviewed revision.
TPS3431's actual **DRB0008A** drawing uses a **1.50 × 1.75 mm** exposed
thermal pad, 0.65 mm pin pitch and nominal 3 × 3 mm body. The example land
uses 0.60 × 0.31 mm peripheral pads with centers at x=±1.10 mm and
y=±0.975/±0.325 mm. A generic 1.50 × 2.25 mm or 1.65 × 2.40 mm exposed
pad is not that drawing. A local footprint preserves the reviewed geometry;
paste, vias and manufacturing qualification remain PCB work.

Sources: [TI TPS3431 Rev A, pp. 3–7](https://www.ti.com/lit/ds/symlink/tps3431.pdf),
[TI TPS3700 Rev G, pp. 4–7](https://www.ti.com/lit/ds/symlink/tps3700.pdf),
[TI TLV3202 Rev C, pp. 3–6](https://www.ti.com/lit/ds/symlink/tlv3202.pdf),
[TI OPA2192 Rev E, pp. 4–6](https://www.ti.com/lit/ds/symlink/opa2192.pdf),
[ADI LTC6993 Rev F, pp. 2–5](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc6993-6993-1-6993-2-6993-3-6993-4.pdf),
[TI TMUX7412F Rev B, pp. 3–6](https://www.ti.com/lit/ds/symlink/tmux7412f.pdf).
Additional witnesses: [TI OPA391 Rev E, pp. 2, 5–8](https://www.ti.com/lit/ds/symlink/opa391.pdf),
[TI ISO674x Rev G, pp. 5–8](https://www.ti.com/lit/ds/symlink/iso6741.pdf),
[TI SN74LVC1G17 Rev Y, pp. 3–7](https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf),
[TI SN74LVC1G74 Rev G, pp. 4–7](https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf),
[Diodes Inc. BAT54WS DS30098 Rev 14-2](https://www.diodes.com/datasheet/download/BAT54WS.pdf).

## Heartbeat is a distinct, slow protection

For TPS3431, SET1 is tied high and CWD reaches VDD through 10 kohm. This selects
170/200/230 ms minimum/nominal/maximum watchdog timeout. WDI falling edges service
the watchdog. A static high or low input eventually times out. SET1 low disables
it, so this pin must not be treated as an ordinary active-low reset.

WDO and ENOUT are open-drain and can share a pull-up. EN low releases WDO but
holds ENOUT low, preventing a disabled watchdog from looking healthy at that
combined node. ENOUT can nevertheless become high after startup without proving
that firmware executed a heartbeat. A distinct heartbeat-seen/reset interlock is
therefore needed before initial permission. The circuit requires a fresh
qualified rearm after any watchdog fault; automatic WDO recovery is insufficient.

The 170–230 ms timeout cannot limit a 200 microsecond pulse. It detects stalled
control, while the secondary one-shot limits a phase. Below the watchdog's
valid supply range and during undefined power ramps, digital health alone is not
evidence of a safe output. [TPS3431](https://www.ti.com/lit/ds/symlink/tps3431.pdf)

## Rail windows are measurements with tolerances

TPS3700 operates from 1.8–18 V; power the detector from the monitored logic
domain and divide a 24 V rail into its sense input. Do not connect its supply
directly to 24 V. Its outputs pull low on undervoltage/overvoltage and can share
an active-low health node. For the reviewed conditions, rising sense threshold
is 396–404 mV and falling threshold is 387–400 mV (394.5 mV typical).

The two independent divider formulas are:

```text
V_sense = V_rail * R_bottom / (R_top + R_bottom)
UV release uses the rising threshold; UV fault uses the falling threshold.
OV fault uses the rising threshold; OV release uses the falling threshold.
```

Resistor tolerance, sense input bias (INA up to ±25 nA, INB up to ±15 nA under
their table conditions), hysteresis and startup must enter bounds. Outputs need
up to 450 microseconds after valid detector power. Sense filtering and detector
response introduce latency; nominal rail labels are not exact limits. The native
network and saved study state actual values and accepted operating windows.
[TPS3700](https://www.ti.com/lit/ds/symlink/tps3700.pdf)

The recording island's +3.3 V and bipolar supply measurements remain in its own
ground domain; only isolated logic carries their health result to HOSTGND.
Monitoring must not create a passive bridge across the existing digital barrier.
Generation of these rails belongs to the next power package.

The supervision revision intentionally raises the provisional recording-island
nominals to **+3.45 V, +5.30 V and −5.10 V**. This permits rail-window tolerance
margin above the RHD minimum and the fault switch's +5 V minimum. The previous
recording package's nominal +3.3/±5 labels are historical allocations, not this
updated quantitative power contract. Local UV rising setpoints are approximately
3.34 V and +5.20 V; corresponding OV setpoints are approximately 3.54 V and
+5.42 V. Calculate falling UV corners using the direct 387–400 mV table rather
than subtracting independently extreme rising threshold and hysteresis numbers.
The saved analog study includes resistor and bias-current corners. Some OV
recovery corners may require power cycling; they must not be forcibly cleared.

An OPA391 inverting attenuator maps the negative rail to a positive magnitude
measurement (`V_MAG = −0.1 × V_NEG` nominal), allowing an ordinary TPS3700
window to observe it. This is conditional on healthy amplifier power, resistor
ratio, input/output headroom and startup. An amplifier stuck at a healthy
voltage remains a residual sensor fault. OPA391DCK has a 1.7–5.5 V supply range;
its full-temperature input-offset table includes ±600 microvolts under the
stated common-mode condition. Do not use its ±45 microvolt room-temperature
mid-supply specification universally. [OPA391](https://www.ti.com/lit/ds/symlink/opa391.pdf)

## Current and quiescence use the actual monitor transfer

The preceding native monitoring cell uses a 2 ohm return shunt and INA241A2 gain
20. Its signal is **I_MON = 2.048 V + 40 V/A × I**, referenced to the REF3440
midpoint. It is not a 2.5 V midpoint or a 100 V/A transfer. The supervision window
must use that existing signal without inserting another shunt.

TLV3202's maximum offset is ±5 mV at room temperature and ±6 mV over its stated
temperature range, at the specified supply table points. A nominal ±10 mV window
corresponds to ±250 microamps; adding only the ±6 mV comparator offset already
allows ±400 microamps, before monitor offset, gain, resistor and reference errors.
Thus a high quiescence flag means an observed bounded window, not zero current or
zero electrode charge. The study uses the final selected divider values.

The native series ladder is 203.8 kohm / 2 kohm / 203.8 kohm across the 4.096 V
reference. Its ideal taps are exactly **2.038 V and 2.058 V**, buffered by
OPA391 devices. Buffer and divider error are additional to the comparator and
INA241 errors; their nominal symmetry does not cancel independent offsets.

The comparator's typical hysteresis is 1.2 mV. A 55 ns full-temperature delay
entry is conditioned on 100 mV overdrive; it must not be applied to an arbitrarily
small near-threshold signal. Actual fault-to-isolation latency remains separate
from a stable logic truth table. [TLV3202](https://www.ti.com/lit/ds/symlink/tlv3202.pdf)

Existing monitor input-bias paths bypass some return-current observation. They
remain documented in the monitoring study; this added supervision does not erase
them or earn the earlier 4% dose-precision target.

## Voltage/compliance must distinguish common mode from differential demand

An ordinary phase places one bridge terminal near 24 V and the other near the
sink's low potential. A rule demanding that both remain between 1 and 23 V would
reject that ordinary topology. A resistor-ratio differential amplifier referenced
to the existing midpoint instead measures the delivered pair voltage, and a
window comparator rejects excessive magnitude independently of phase polarity.

The selected difference gain is 49.9 kohm / 1 Mohm = 0.0499. The 232 kohm /
536 kohm / 232 kohm reference ladder gives nominal limits **0.950272 V and
3.145728 V**, corresponding to **±21.99856 V** about the 2.048 V midpoint.
Current/phase qualification determines when a compliance failure is meaningful;
the native logic and finite histories define that admission rule.

OPA2192 supports 4.5–36 V total supply. At 5 V it can implement an attenuating
difference circuit with output around 2.048 V; the native resistor network, rather
than the part's rail-to-rail label, determines its transfer, input loading and
headroom. Its typical bandwidth, settling and overload-recovery entries are not
universal maximum timing guarantees. Matched-resistor tolerances, common-mode
conversion, saturation and shutdown-edge capacitance remain model conditions.
[OPA2192](https://www.ti.com/lit/ds/symlink/opa2192.pdf)

Sense divider currents can bypass the return shunt. They must remain in the
terminal/leakage accounting, including the off state. A voltage window does not
establish adequate current or actual biological recruitment.

## Separate phase-duration bound

Each source receives a separate LTC6993-1, with its own oscillator, timing
resistor and divider. Its healthy pulse bound follows
`t = NDIV × RSET / 50 kohm × 1 microsecond`; use the ±4.4% full-temperature
specification for NDIV=64, plus resistor tolerance. The native design and study
record the selected resistance and resulting interval.

The secondary selection is **195.4 kohm ±0.1%, NDIV=64**, giving 250.112
microseconds nominal and **238.867965–261.378045 microseconds** for the stated
healthy-device arithmetic. A 264 microsecond model cutoff is an additional
conservative allocation, not a new manufacturer guarantee. The primary driver's
healthy maximum is 235.159981 microseconds; nominal separation does not itself
bound asynchronous path skew, current tails or shutdown charge.

This removes dependence on the primary driver's timing resistor and oscillator
for the modelled primary SET-open/stuck-high fault. It does not remove shared
rails, common trigger wiring, identical device design or simultaneous faults.
The secondary SET resistor opening can itself prevent pulse completion.
Startup/timing readiness must precede admission; a typical startup time is not
a guaranteed readiness deadline. [LTC6993](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc6993-6993-1-6993-2-6993-3-6993-4.pdf)

## Terminal disconnect: direction and residual paths matter

Five quad devices provide **eighteen used paths**: one at each of the sixteen
shared stimulation contacts after routing and one at each dedicated monitored
return. The remaining two channels are disabled and grounded. Global inhibition
commands all eighteen selectors low, so it also cuts a source fault reaching a
contact through an unintended router path. Two enabled source paths can still
share device supply and control failures; this is one terminal barrier layer,
not two independent barriers per contact. The signed return shunts remain on
the internal side of the corresponding return guards.

TMUX7412F's S pins face the external load; D pins face the internal driver and
monitor. Source pins provide specified fault/power-off protection, while D pins
do not. The active-high selectors have explicit low defaults. VSS=GND and
VDD=24 V meet its 8–44 V supply-span range. The manufacturer permits signals
between the valid rails; source fault protection extends to ±60 V under its
additional pin-to-supply/difference conditions.

The switch's published 12 V/36 V tables do not constitute an interpolated 24 V
worst-case model. Fault flag high is not proof that a channel opened. A source
fault makes the affected drain high impedance, but fault thresholds track the
rails. A shorted guard, parasitic capacitance, common rail collapse and unprotected
D overvoltage remain residual cases. A commanded disconnect therefore supports
the finite healthy-switch study, not a claim of zero current under every fault.
[TMUX7412F](https://www.ti.com/lit/ds/symlink/tmux7412f.pdf)

## Observed recording blanking and isolated status

Seventeen dual-comparator windows observe the actual sixteen positive RHD
inputs and their shared reference. Each input reaches a sense node through
10 Mohm; a 1 Mohm resistor pulls the node toward the local recording supply.
Ignoring comparator bias, `V_SENSE = (V_PIN + 10 × V_AFE) / 11`. Buffered
9.50 kohm / 100 kohm and 10.5 kohm / 100 kohm dividers establish nominal
upper/lower limits. At V_AFE=3.45 V these correspond to approximately +0.158 V
and −0.156 V at the RHD pin. The ±6 mV comparator offset alone corresponds
to ±66 mV at that pin; actual corners include buffer, bias and resistor errors.

This network adds approximately **0.314 microamps per pin at zero volts**,
before comparator input bias, and couples local supply noise to the neural
inputs. It therefore revises recording input loading; weak-signal performance
remains unearned. Shared reference loading is summed across its connected
amplifiers. The circuit measures low-voltage pin state together with local
CONNECT/ACQUIRE low; it does not observe the mechanical position of every
switch or prove that a welded contact has opened.

The extra **ISO6742F** transfers two distinct reverse status signals, recording
rail health and recording blanking health. Its A/B channels run side 1 to side
2; C/D run side 2 to side 1. Tie enables high in their own domains, ground
unused inputs, and leave unused outputs NC. Default-low receiver behavior
requires valid receiver supply; undefined ramp regions remain explicit. The
isolator provides no isolated power and its component rating does not certify
the completed system. [ISO674x](https://www.ti.com/lit/ds/symlink/iso6741.pdf)

## Logic levels and finite RC dwell/startup model

The selected LVC inputs accept up to 5.5 V even when powered at 3.3 V. Thus a
valid 5 V TLV3202 output may drive those inputs directly; arbitrary comparator
overvoltage or powered-down receiver behavior is a different condition. For
SN74LVC1G74 at 3–3.6 V supply, specified VIH is 2 V and VIL is 0.8 V.
Flip-flop reset, clock and data must satisfy setup/hold and recovery rules; a
stable Boolean model is not an asynchronous hazard proof.
[SN74LVC1G74](https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf)

The SN74LVC1G17 Schmitt buffer supports deliberately slow RC transitions. Its
reviewed threshold table specifies VT+ 1.48–1.92 V at **3.0 V**, and
2.19–2.74 V at **4.5 V**; these are not a direct 3.3 V table. The finite
study conservatively **assumes** VT+=1.48–2.74 V across a 3.0–3.6 V high level.
This bracketing assumption is explicit, rather than silently interpolating a
guarantee. Input leakage allowance is ±5 microamps.
[SN74LVC1G17](https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf)

BAT54WS-7-F's discharge diode faces anode at the RC node and cathode toward
the raw health signal, with 100 ohm series resistance. A low health signal
therefore discharges the capacitor quickly. The manufacturer's 2 microamp
reverse-leakage maximum is conditioned on 25 V and room temperature; a
2 microamp upper allowance at low voltage over temperature is a **study
assumption**, not that manufacturer's full-temperature guarantee.
[BAT54WS](https://www.diodes.com/datasheet/download/BAT54WS.pdf)

For the native **R ±1%**, quiet C ±5%, startup C ±10%, input leakage
±5 microamps and diode leakage 0–2 microamps, a 3.3 kohm/10 nF quiet dwell
rises in approximately **16.30–87.71 microseconds** in the stated
threshold/high-level model. It is not a guaranteed 30 microsecond dwell.
A 100 kohm/47 nF startup network has a modelled minimum rise of
**1.770 ms** from zero, or **1.140 ms** from an
initial 0.6 V; both exceed the TPS3700 450 microsecond startup allowance.
That minimum requires the stated initial voltage and leakage assumptions.
At an adverse low high-level/large opposing leakage/large threshold corner,
the final voltage may not cross the threshold, producing a **fail-closed
non-release** rather than a finite readiness deadline. Incomplete discharge,
arbitrary supply ramps, diode faults and altered capacitance remain residual
cases. These finite RC checks do not authorize a rail-good latch to ignore
ongoing rail faults.

The final bounded audit compared native resistor networks and transfer direction
with `analog_study.py` and its separate KCL verifier: rail dividers are ±0.1%,
the negative-rail amplifier uses 100 kohm input / 10 kohm feedback, the pair
network measures A_BR minus B_BR with gain 0.0499, and the RC tolerances match
the native values above. Comparator corners use ±6 mV and OPA391 corners use
±600 microvolts as declared allowances. The AFE threshold buffers must be
powered from AFE_P5 so their approximately 3.15 V inputs stay away from the
OPA391 upper common-mode region, where the reviewed room-temperature limit
alone can reach ±750 microvolts. This condition is checked on the final native
export; a supply change requires regenerating its exports and receipt.

## Completion boundary

The package is complete as an inspectable digital supervision slice when native
circuits, actual inter-package connections, component/pad checks and finite
fault/rearm studies agree. Unclosed analog delay, leakage, rail-ramp and switch
fault bounds are explicit results. They are not a reason to reopen Stage 3 or to
invent biological success; the power, transport, firmware and populated PCB
packages remain subsequent work.
