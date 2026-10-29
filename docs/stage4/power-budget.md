# Stage 4 power and resource budget

**14 October 2026 — finite digital reference and declared acceptance conditions**

The power reference supports Project SCCI RH's spinal recording, interpretation,
selective stimulation and feedback architecture. It preserves the motor-learning
and target-specific physiological-regulation concepts. It supplies a concrete
electrical implementation to investigate those ideas; it does not establish
expert-to-learner skill transfer or a physiological effect.

The implemented parts require a substantially larger power reference than the
old compact allocation. The chosen external battery alone is **99 g,
67 × 37 × 21 mm**, about **52.1 cm³**. The active allocation is **2.615 W** under
the conditions below. A compact continuously implanted version needs a lower
power implementation and a new packaging/thermal closure. The future consumer
mechanism remains defensible as a conditional concept, while this implementation
provides inspectable circuitry and quantified costs.

## Battery and topology revision

The native reference selects the protected **Tenergy AT31004**, a 2S1P pack
specified at 7.4 V, 2.6 Ah, 19.24 Wh and 5 A. Its modeled **under-load operating
range is 6.4–8.4 V**; series reverse-polarity protection is assigned a 0.5 V drop
and a 2 A master fuse is drawn. Charging is offboard using the compatible
charger described in the component review. No implanted charging circuit,
wireless energy link or certified implant battery is implemented.
[Tenergy product specifications](https://power.tenergy.com/AT-7.4-2600mAh-5A-batterypack/)

This intentionally supersedes the historical 3.0–4.1 V single-cell reference and
100 mA average-cell cap. A 5 V buck cannot produce 5 V from that single-cell
range, and the new native parts exceed that old power cap. Historical studies
remain unchanged; their envelope is not silently enlarged.

The four buck outputs are independent supervisor 3.3 V/5 V and enabled host
3.3 V/5 V. Two LT8330 converters produce host 15 V/24 V. HOST_5 also powers the
TMR3-0522 isolated ±12 V module; two positive LDOs independently derive floating
AFE 3.45 V and +5.30 V, and one negative LDO derives −5.10 V. Both positive LDOs
take input directly from +12 V. Their currents are counted once at the module
and once at its upstream HOST_5 converter, without double-counting output power.

## Actual components and declared rail loads

The five preceding native packages contain **306 active IC packages**. The new
power package contains 23 active packages, including its converters and module;
13 window/enable logic packages add loads to SUP_3V3. A 15 mA MCU allowance is
reserved separately because the controller is a later native package.

Every actual IC receives a source-linked current allocation in
[budget-results.json](../../electronics/stage4/power-study/budget-results.json).
These are declared design bounds informed by component data, not an assertion
that every number is a vendor maximum at every operating condition. Remaining
current in each rail cap covers passives, output loading, switching and
contingency. These load caps are conditions of the calculation; they are not
independent hardware current limiters or measured firmware consumption.

| Rail | IC/reserved allocation, mA | Remaining allowance, mA | Total cap, mA | Output power cap, mW |
|---|---:|---:|---:|---:|
| HOST_3V3 | 34.430 | 35.570 | 70 | 231.00 |
| HOST_5 | 11.540 | 8.460 | 20 | 100.00 |
| HOST_15 | 3.400 | 1.600 | 5 | 75.00 |
| HOST_24 | 3.800 | 1.200 | 5 | 120.00 |
| SUP_3V3 | 9.280 | 15.720 | 25 | 82.50 |
| SUP_5 | 3.720 | 2.280 | 6 | 30.00 |
| AFE_3V3, actually 3.45 V | 25.650 | 9.350 | 35 | 120.75 |
| AFE_P5, actually +5.30 V | 6.160 | 3.840 | 10 | 53.00 |
| AFE_N5, actually −5.10 V | 2.755 | 2.245 | 5 | 25.50 |

The dominant additions are three digital isolators, ten fault-protected quad
switch packages, the large explicit supervisor logic network and the 17 physical
recording-pin window circuits. The old 4.5 mW AFE allowance covered a proposed
chip/protection estimate; the actual floating-rail caps total **199.25 mW**
before isolated conversion and LDO loss. The old 35 mW compute allowance is
replaced by a **49.5 mW reserved MCU cap** plus separately counted external
logic, isolators and output loads.

The TLV3202 allowance is 130 microamps per dual package, based on twice the
65 microamp per-comparator full-temperature value. ISO674x receives 8 mA per
powered side, above the chosen 3.3 V DC/1/10 Mbit/s table rows; actual mixed-rail
switching and lead loading remain test conditions. TMUX7412F receives +0.6 mA
and, on floating dual supplies, −0.5 mA per package. The selected supply spans
differ from some characterization rows, so those allocations remain explicit.
[TLV3202 datasheet](https://www.ti.com/lit/ds/symlink/tlv3202.pdf),
[ISO674x datasheet](https://www.ti.com/lit/ds/symlink/iso6741.pdf),
[TMUX7412F datasheet](https://www.ti.com/lit/ds/symlink/tmux7412f.pdf)

## DC, instantaneous stimulation and conversion loss

All nonstimulation rail loads are held at their caps. The restricted active
example adds two aligned 3 mA sources, two 200 microsecond phases per pulse at
100 Hz. Its 24 V stimulation-rail average is **5.76 mW** and its instantaneous
increment is **144 mW**. Electrical availability does not imply biological
equivalence to a published protocol. This package does not expand the native
driver to 48 V/20 mA.

The selected load-dependent conversion assumptions are 80% for bucks, 75% for
boosts and 65% for the isolated module. Fixed current allocations are counted
separately. The resulting power flow is:

| Quantity | Conditional active value |
|---|---:|
| Isolated +12 V current | 47 mA |
| Isolated −12 V current magnitude | 6 mA |
| Isolated module output power | 636 mW |
| LDO output power | 199.25 mW |
| LDO loss including allocated ground current | 436.75 mW |
| Isolated-module input power | 1,278.46 mW |
| HOST_5 output including island and host load | 1,378.46 mW |
| Nominal battery input | 2,615.11 mW |
| Nominal battery current | 353.39 mA |
| Battery current at 6.4 V, selected diode drop | 413.29 mA |

TMR3 specifies 81% typical efficiency at full nominal resistive load and 60 mA
typical no-load input current for this model. Neither is a low-load maximum
guarantee. The study allocates 0.3 W fixed overhead in addition to the conditional
65% load-dependent path. Its 47/6 mA unequal loading lies outside the specific
25%/100% cross-regulation test condition. Adequate raw-rail headroom is therefore
a condition to qualify, even though both nominal currents and total power fit
the output ratings. No minimum load is required by the family specification.
[TRACO TMR3 datasheet](https://www.tracopower.com/products/tmr3.pdf)

Loaded LDO ground current is assigned 1 mA per device; their 100 microamp
no-load specification is not reused as a loaded maximum. Boost active input
quiescent allocation is 1.2 mA per converter. These conservative allocations
prevent typical low-power headlines from becoming unearned assembled-device
claims.
[TPS7A49 datasheet](https://www.ti.com/lit/ds/symlink/tps7a49.pdf),
[TPS7A30 datasheet](https://www.ti.com/lit/ds/symlink/tps7a30.pdf),
[LT8330 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/lt8330.pdf)

## Reservoir, startup and rejected brownout cases

The native 24 V output has two nominal 22 microfarad capacitors. With a declared
**30 microfarad effective total** and 0.1 ohm ESR, 6 mA over two 200 microsecond
phases removes 2.4 microcoulombs and gives **80.6 mV** droop if the converter
supplies the static load but replenishes none of the incremental pulse charge.
The study sweeps 2/10/30/100 microfarads, one/two sources and 200/400/264 microseconds
of total on-time. Two small-capacitor cases fail the selected 22.8 V boundary.
The capacitor retains energy after shutdown; that energy is not automatically
harmless and cannot be credited as an independent shutdown source.

The input load-line sensitivity uses selected 0.1–5 ohm source resistances and
6.4/6.8/7.4/8.4 V open-circuit pack levels. It solves constant-power load and
series-drop equations rather than assuming a fixed input current. **Ten of
twenty cases** fall below the selected 5.9 V bus minimum. These are deliberate
brownout rejections; source resistance, protection thresholds and impedance
remain unmeasured. The 6.4 V battery boundary means under load, not a promise
that a 6.4 V open-circuit pack can supply arbitrary current without sag.

Startup energy includes **423 populated capacitors** from all six packages,
with intentionally loose supply-span bounds where an internal-node voltage is
unknown. Nominal stored-energy accounting is **31.34 mJ**; a 20% positive
capacitance allowance gives **37.61 mJ**. At an assumed 50% effective charging
path and 5.9 V, spreading that energy over 1/5/30/100 ms gives additional average
input currents of 12.75/2.55/0.425/0.127 A. These are energy slopes, not predicted
peak inrush or a proof of the actual ramp. The 1/5 ms slopes exceed the 2 A rating;
the fuse's time-current behavior and converter current limits require their own
physical review. No artificial perfect sequencer is credited.

Full untrimmed AFE output tolerance can fail cold-start rail qualification.
Selected/trimmed ±0.5% output ranges fit every inherited rising-threshold corner
in this finite calculation. That is a defensible assembly/calibration condition,
not a factory guarantee. AFE overvoltage recovery can still require a power
cycle because of hysteresis; a healthy nominal rail does not automatically
clear every latched condition. The native supervision startup/rearm contract
remains applicable.

Disabling LT8330 does not physically disconnect its output: the inductor and
diode retain input-to-output feedthrough. Consequently, the saved
“supervision-only” figure counts only supervisor demand and is a **lower bound**,
not a complete standby or power-off runtime claim.

## Runtime and thermal result

The selected 80% usable-energy assumption gives **15.392 Wh**. Dividing by the
conditional active input produces **5.886 hours**. With the chosen efficiency
sensitivity, the active allocation spans **2.140–3.865 W**, giving **3.982–7.193
hours** at the same assumed usable energy. Battery temperature, aging, cell
discharge curves, protection cutoff, load duty and measured conversion efficiency
can change these figures. No measured runtime is reported.

For heat accounting, the example 1 kilohm artificial loads receive 0.72 mW on
average. All remaining battery input is conservatively allocated to the
electronics/pack: **2.6144 W**. A lumped 5/10/20/50 K/W sensitivity produces
13.07/26.14/52.29/130.72 K rises; all fail the selected 2 K rise allocation.
Meeting 2 K in that model would require an aggregate thermal resistance below
**0.765 K/W**, or reduced dissipation. These are mathematical sensitivities,
not measured surface or tissue temperatures. Continuous compact implant thermal
closure is **not achieved** by this reference implementation.

## Bus, memory and compute reconciliation

The selected neural burst is 19 five-microsecond slots at 4 MHz, giving 95
microseconds per 250 microsecond frame and **38% scheduled occupancy**. Its
19 × 16 × 4,000 wire-bit arithmetic is separate from slot overhead.

The native monitoring cell has two **ADS8866**, each rated to **100 ksample/s**.
Their 200,000-word/s aggregate capacity cannot meet the old 450,000-word/s
reservation, regardless of the SPI bus's 45% wire occupancy at that higher
rate. The admitted capacity row uses 200,000 words/s and 20% wire occupancy at
16 MHz; it does not claim that the old per-source current/integration contract
is now satisfied. Later transport/firmware work must revise the monitor rate
contract or its ADC implementation explicitly.
[ADS8866 datasheet](https://www.ti.com/lit/ds/symlink/ads8866.pdf)

The inherited RAM allocation totals **404,992 bytes of 524,288**, leaving
**22.75% headroom**, above the selected 20% reserve. It includes a two-second
2 ksample/s archive, DMA/work buffers, feature state, firmware/OS/heap, queues
and monitoring integration. This is an allocation, not linked firmware or
measured heap use. Four feature bands, 31-tap archive filtering and the linear
witness total **2,886,400 MAC/s**. With the inherited assumed 10 cycles/MAC,
administration and 15% contingency, the 450,000-word monitor reservation costs
33.75% of 128 MHz; the actual 200,000-word capacity case costs 31.50%. Neither
fits the selected 60% cap at 64 MHz. CPU arithmetic fitting does not create
missing ADC throughput or demonstrate neural decoding.

Normal feature payload is 51.2 kbit/s before transport overhead and within the
provisional 160 kbit/s link ceiling. Continuous framed 4 ksample/s raw data are
**1.536 Mbit/s**, exceeding a 1 Mbit/s service. Raw capture therefore needs bounded
bursts, a revised link or a different mode. Through-body RF performance, packet
overhead and security remain transport obligations.

## Verification and finite completion boundary

[budget_study.py](../../electronics/stage4/power-study/budget_study.py) reconstructs
the declared calculation and checks saved results read-only.
[verify_budget.py](../../electronics/stage4/power-study/verify_budget.py) independently
checks the saved source bindings, counts, current/power sums, losses, capacitor
charge and energy, input load lines, resource reservations and preserved failure
witnesses. It does not import the producer or convert rejected cases into passes.
The saved [verification report](../../electronics/stage4/power-study/budget-verification.json)
records the assertion count for this exact revision.

This closes the finite **digital power-reference and budget package** with its
explicit conditional loads, rail-trim assumption and failures. Converter layout,
loop stability, switching ripple, EMI, physical inrush, loaded-module asymmetry,
battery behavior, compact implant power and thermal qualification remain stated
engineering obligations. They are not reasons to erase the concrete reference
or indefinitely repeat its arithmetic before proceeding to the next package.
