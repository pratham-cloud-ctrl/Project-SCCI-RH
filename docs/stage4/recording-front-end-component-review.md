# Recording front-end: primary component review

Reviewed 13 October 2026 for the native Stage 4 recording slice. This review
checks component identities, pins and stated operating conditions. It does not
qualify an implant, a finished PCB or stimulation artifact recovery. The
four manufacturer PDFs were downloaded directly; page diagrams were rendered
where extraction omitted pin numbers or land dimensions.

## Decisions supported by the sources

| Device | Selected package | Result |
|---|---|---|
| Intan RHD2216 | 8 × 8 mm, 56-pin QFN, 0.5 mm pitch | Sixteen differential amplifiers, one multiplexed ADC. Sixteen positives and one shared negative contact produce sixteen streams; tying negatives together is an SCCI_RH montage decision. |
| TI TMUX7412FRRPR | RRP WQFN-16, 4 × 4 mm | Active-high switch; protected **S** faces the contact, unprotected **D** faces the circuit. Five devices provide seventeen used paths and three grounded unused paths. |
| TI TMUX6219DGKR | DGK VSSOP-8 | Bipolar SPDT ground/record selection on qualified ±5 V rails; EN high enables, SEL low selects S1, SEL high selects S2. |
| TI ISO6741FDWR | DW wide SOIC-16 | Three forward channels and one reverse; suffix F defaults low. Requires separate isolated power, local CS inversion and explicit startup qualification. |

The TMUX7412F document marks **PW/TSSOP as preview** and its current orderable
addendum lists the RRP variant. A PWR package must therefore not appear as an
available production part in this design. [TI TMUX7412F, pp. 1, 3, orderable addendum](https://www.ti.com/lit/ds/symlink/tmux7412f.pdf)

## RHD2216 implementation facts

All VDD pins share 3.3 V; all GND, VESD and exposed-pad shielding share AFE ground.
Use two nearby 100 nF X7R/X5R, ≥16 V capacitors for CMOS signaling and a nearby
10 nF, ≥16 V ADC-reference capacitor. Unused auxiliary inputs connect to VDD;
auxout and negative SPI pins are NC. Grounding elec_test disables impedance
testing. Gain is 192; input-referred LSB 0.195 µV; AC linear range ±5 mV; input
DC range ±0.4 V. Noise 2.4 µV RMS and CMRR 82 dB are **typical**, not guaranteed
limits. [Intan RHD2000, pp. 5–7, 13, 27–28, 35](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

The 0.1/300 Hz register choices are supported. Fast settle uses register 0 bit 5;
the recommended pulse duration at 300 Hz is `2.5/300 = 8.333 ms`. This is a
manufacturer recommendation, not an SCCI_RH measured recovery bound. ADC buffer/MUX
bias must respect **intraburst** conversion spacing, not only the frame average.
[Intan, pp. 19, 24–27](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

Verified top-view pin map (EP number 57 is SCCI_RH's footprint convention):

```text
 1 in4+     2 in3-     3 in3+     4 in2-     5 in2+     6 in1-     7 in1+
 8 in0-     9 in0+    10 GND     11 GND     12 GND     13 VDD     14 auxin1
15 auxin2  16 auxin3  17 GND     18 CS-     19 CS+     20 SCLK-   21 SCLK+
22 MOSI-   23 MOSI+   24 MISO-   25 MISO+   26 VDD     27 auxout  28 ADC_ref
29 GND     30 LVDS_en 31 VDD     32 VESD    33 elec_test 34 in15-   35 in15+
36 in14-   37 in14+   38 in13-   39 in13+   40 in12-   41 in12+   42 in11-
43 in11+   44 in10-   45 in10+   46 in9-    47 in9+    48 in8-    49 in8+
50 in7-    51 in7+    52 in6-    53 in6+    54 in5-    55 in5+    56 in4-
57 EP: internally unconnected; solder and connect to AFE ground for shielding.
```

The custom peripheral lands use 0.25 × 0.90 mm, radial centers ±4.05 mm and
0.50 mm pitch; the center land is at most 6.10 × 6.10 mm. This follows the
**top-view** numbering and recommended outer land span of 9.0 mm; it must not
mirror the package's bottom-view drawing. [Intan, pp. 2, 38](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

## Switch connections and limits

```text
TMUX7412F RRP: 1 S1, 2 VSS, 3 GND, 4 S4, 5 D4, 6 SEL4, 7 SEL3, 8 D3,
               9 S3, 10 FF, 11 VDD, 12 S2, 13 D2, 14 SEL2, 15 SEL1, 16 D1.
               EP17 internally NC; tie to AFE ground in this footprint.
TMUX6219 DGK:  1 D, 2 S1, 3 GND, 4 VDD, 5 EN, 6 SEL, 7 VSS, 8 S2; no EP.
```

The fault switch allows ±5 V dual supplies but has **no ±5 V electrical table**;
its ±15 V on-capacitance 14 pF, charge injection −300 pC and leakage/timing
numbers cannot become guaranteed ±5 V values. Source overvoltage detection tracks
the supplies plus a threshold, far outside the RHD's ±0.4 V DC envelope. Selected
faulted drains float. Grounding, bleeders, clamp sequencing and declared parasitic
sweeps remain necessary. A high FF is not a near-zero-input detector. For a
shared wired-OR of five open-drain FF pins, use one shared pull-up; five parallel
1 kΩ pull-ups could exceed one FF output's current rating. Ground unused S/D/SEL.
[TI TMUX7412F, §§6–7, 9.3–9.4](https://www.ti.com/lit/ds/symlink/tmux7412f.pdf)

Its actual positive supply must be at least 5.0 V and its supply span at least
8.0 V. A nominal +5 V supply with a negative tolerance is not automatically
qualified; the external power contract must enforce these conditions or select
a slightly higher nominal supply. [TI TMUX7412F, §7.4](https://www.ti.com/lit/ds/symlink/tmux7412f.pdf)

RRP lands: 0.60 × 0.30 mm, radial centers **±1.90 mm**, 0.65 mm pitch and
2.60 mm square exposed pad. The 3.8 mm dimension is center-to-center, not the
outer copper span. [TI TMUX7412F, RRP0016A board-layout drawing, p. 46](https://www.ti.com/lit/ds/symlink/tmux7412f.pdf)

TMUX6219's ±5 V switching table gives 142 pF on-capacitance and 14 pC injection
as **typical**. Across −40…125 °C, listed maxima include 240 ns transition,
240 ns enable-on and 270 ns enable-off under its stated 35 pF/300 Ω fixture.
The electrical/leakage table uses +5/−8 V conditions despite the switching table's
±5 V conditions. Neither table guarantees injection, leakage or response into
SCCI_RH's high-impedance electrode network. Its internal pull-up on EN and pull-down
on SEL do not replace the drawn external defaults. [TI TMUX6219, pp. 3, 12–13, §7](https://www.ti.com/lit/ds/symlink/tmux6219.pdf)

## Digital isolation, timing and power

```text
ISO6741F DW: 1 VCC1, 2 GND1, 3 INA, 4 INB, 5 INC, 6 OUTD, 7 EN1, 8 GND1,
            9 GND2, 10 EN2, 11 IND, 12 OUTC, 13 OUTB, 14 OUTA, 15 GND2, 16 VCC2.
```

At 3.3 V ±10%, propagation delay is 11 ns typical / 18 ns maximum under the
stated 100 kbit/s measurement; same-direction skew max 6 ns, pulse-width
distortion max 7 ns. Output-valid startup is 300 µs. Default-low after input power
loss is specified from supply falling below 1.2 V; it does not detect a powered
controller stuck high. EN low makes outputs high impedance. Both local supplies
need decoupling; no conductive AFE-ground/host-ground connection crosses this
barrier. [TI ISO6741, pp. 5–6, 21, 31, 36](https://www.ti.com/lit/ds/symlink/iso6741.pdf)

Power is a real architecture revision: at 3.3 V and all-channel 10 Mbit/s test
conditions one ISO6741 has 8.2 mA typical / 11.3 mA maximum **combined** current.
The F-variant static-high table reaches 12.2 mA maximum combined; 50 Mbit/s
reaches 20.1 mA maximum. These are particular loads and signal conditions,
not an unconditional SCCI_RH power ceiling. Count both devices and both supply
domains; do not retain the earlier small generic protection allowance.
[TI ISO6741, p. 15](https://www.ti.com/lit/ds/symlink/iso6741.pdf)

## SCCI_RH conditions kept explicit

The proposed 470 pF positive-input and 2.2 nF shared-reference capacitors,
10 MΩ bleeders, split body-bias resistance and 4.99 kΩ series impedances are SCCI_RH
design choices. They change common-mode conversion, signal response and recovery.
Switch charge injection and mutual capacitance are swept assumptions unless
the precise assembly is characterized. RHD voltage limits, analog recovery,
digital filter recovery and decoder validity remain separate criteria. The
floating island does not remove biological coupling through tissue and bias.
External power qualification and the stimulation/record interlock are required
interfaces, not supplied by the isolator's component certification.

Primary download SHA-256 records (PDFs retained only in ignored temporary files):

| Source | SHA-256 |
|---|---|
| Intan RHD2000, updated 8 Dec 2023 | `03d9ee0cfe9895994573e91af3304db060b2ab2f638c2ad6319600a8552de416` |
| TI TMUX7412F, SCDS404B | `7396d8a34f80b178a8b5c72272b5bb0eb7da7ad3182e7d3cd80d294fc32f26e5` |
| TI TMUX6219, SCDS420E | `216e5fe55ce423e3d2e4702dd88ad203e7550e57d3b306ac7d1f31dae06394c0` |
| TI ISO6741, SLLSFJ6G | `18282cc8e701676eb7c2a283dad8bfc84b220ed4d2e9bb855f0c54fdb5f38805` |
