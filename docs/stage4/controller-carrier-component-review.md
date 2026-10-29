# Controller carrier: primary component and pad review

14 October 2026. The carrier closes the hardware dependencies of the compiled
nRF5340 backend: 46 GPIO, four parallel-load shift registers, common endpoint
CNV, common driver rearm and independent phase-supervisor rearms. The selected
implementation is a **Fanstel BT40F module**, containing the nRF5340, both
crystals and regulator support. This is a populated digital bench board-set
design; useful spinal features and individualized biological recruitment remain
the conditional SCCI mechanisms already established by the research architecture.

The primary manufacturer document is [Fanstel BT40F/BT40N product specifications,
v1.09, July 2024](https://www.fanstel.com/s/BT40F_BT40N-Product-Specifications.pdf),
linked by the [manufacturer's download index](https://www.fanstel.com/download-document).
The footprint geometry comes from the manufacturer's
[BT40F Eagle package library](https://www.fanstel.com/s/BT40F-lib-11.lbr).
The source hashes and exact numeric-to-physical pad conversion are retained in
[module-footprint-source.json](../../electronics/stage4/controller-carrier/module-footprint-source.json).

## Why this module fits the actual firmware

The primary pin table on pages 16-17 and drawing on page 14 expose every assigned
pin from P0.02 through P0.31 and P1.00 through P1.15. P0.00/P0.01 are connected
to the module's internal 32.768 kHz crystal; module pads 3/4 are no-connect.
The carrier does not connect those pads or allocate those GPIO. The BT40F has
no nRF21540 amplifier or onboard external flash consuming the selected pins.
**BT40N/BT40NE are excluded substitutions:** their amplifier uses nine GPIO.
P0.02/P0.03 still require the frozen firmware's UICR NFC-to-GPIO setting.

The following mapping was checked against the manufacturer's pin table, rather
than inferred from the old BT840F's similar footprint. Pad names are actual
manufacturer identifiers, not logical GPIO numbers.

| GPIO range | BT40F physical pads in ascending GPIO order |
|---|---|
| P0.02-P0.11 | 7, 8, 5, 6, A1, A2, A3, 11, E6, 12 |
| P0.12-P0.21 | B5, B6, B3, B4, A4, B2, F3, B1, C5, C2 |
| P0.22-P0.31 | D5, C4, C3, C6, D1, D2, D3, D4, 13, C1 |
| P1.00-P1.07 | A5, D6, 1, 2, E0, E1, E2, E3 |
| P1.08-P1.15 | A6, Z0, Z1, Z2, Z3, Z4, Z5, Z6 |

The source has two editorial inconsistencies. Prose refers to a 61-pad footprint,
while the actual artwork and Eagle file contain **66 pads**. The comparison
table also calls the four large grounds F0-F3, colliding with signal F3. The
mechanical drawing and actual BT40F symbol identify these grounds as **H0-H3**;
signal F3 is P0.18. This carrier preserves the unambiguous physical names from
those drawings. All 66 pad positions are retained and independently compared
with the native symbol, netlist and BOM footprint.

The footprint datum follows the 14 mm lower pad region. Page 9's 15 mm upper
body extends 1 mm farther to the left: its nominal X bounds are -8 to +7 mm,
while the lower region is -7 to +7 mm. Both have Y bounds -10.5 to +10.5 mm,
with the lower-width notch beginning at nominal Y=+0.5 mm. The Fab polygon and
assembly visualization preserve that asymmetry. Pad coordinates retain the
manufacturer Eagle geometry rather than being stretched to those nominal
body dimensions; neither body height nor assembly tolerance is qualified.

## Supply, clocks, reset and programming

Module VDD pad 9 and VDDH pad F4 are joined on `MCU_3V3`, fed through R1 (0 ohm)
from HOST_3V3. This follows Nordic's [normal-voltage mode](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/regulators.html),
which requires VDDH connected to VDD. All nine module ground pads connect to
host GND. They never connect to the isolated AFE analog return. USB D+/D- and
VBUS are unused and left unconnected; internal DCCH pad F5 remains no-connect.
The carrier supplies 47 uF nominal bulk plus 1 uF and 100 nF local bypass. The
47 uF value does not establish effective capacitance under bias, acceptable
ripple or startup qualification. R1 is also a module-current measurement link.

Fanstel pages 18-19 specify **11 pF internal HFXO capacitance for BT40F**.
Their general example uses X2=25, appropriate to the BT40N's 12.5 pF setting;
the explicit BT40F table says **X2=22**. Installed SDK v3.4.1's
`zephyr/soc/nordic/nrf53/Kconfig` supports `SOC_HFXO_CAP_INTERNAL=y` and
`SOC_HFXO_CAP_INT_VALUE_X2=22`. The earlier DK-target image uses the default
clock setting. A separate integrated-carrier build configuration adopts the
module setting without rewriting that earlier evidence. The module LFXO is
present physically; firmware clock-source/loading configuration must agree
with the final derivative. No measured frequency accuracy is asserted.

Reset pad 14 has a 10 kohm pull-up and a normally open shorting header.
SWCLK pad 15 and SWDIO pad 16 reach a six-pin programming header. Its VREF
pin is a **target-voltage sense**, not permission to back-power the carrier.
The external probe is outside the populated BOM. The existing binary uses
application core only and disables the network-core/radio backend. The module's
integrated antenna does not establish an SCCI_RH wireless link.

## Four real sideband devices

Four **SN74LVC165APWR**, U10-U13, operate at HOST_3V3, with one 100 nF bypass
each. The [TI datasheet](https://www.ti.com/lit/gpn/sn74lvc165a) identifies
SH/LD=1, CLK=2, CLK INH=15, VCC=16, GND=8, QH=9 and SER=10. CLK INH is tied
low; inverted QH pin 7 is unused. U10 is nearest the MCU: its QH goes to module
Z6/P1.15. U11.QH feeds U10.SER, and so on, with farthest U13.SER grounded.
All loads share module Z5/P1.14; clocks share module D4/P0.29 with the DAC/router
candidate bus under exclusive firmware ownership.

Parallel H/G/F/E/D/C/B/A pins **6/5/4/3/14/13/12/11** carry ascending sample bits.
Bits 0-7 observe the eight actual route Q outputs. Bits 8-25 observe the eighteen
native health/status signals specified in the firmware review. Bits 26-31 are
hardwired **1,0,0,1,0,1**, yielding mask value 0xa4000000. The MCU samples QH
before each shift edge. The fixed pattern detects several disconnected/stuck
stream cases; it does not authenticate native observations or guarantee timing.

Common endpoint CNV is a real join of J12 pins 3/5 to module D5/P0.22. Common
driver rearm joins J15 pins 4/8 to module E2/P1.06. Phase-supervisor rearms stay
on distinct module Z1/P1.10 and Z2/P1.11 through J18 pins 6/7. The integrated
master intentionally supersedes two older driver-to-supervisor rearm wires;
retaining them would short three push-pull processor outputs.

## Reset loads and remaining evidence limits

Forty 10 kohm output-bias resistors set passive commissioning defaults. High
defaults include chip selects, both integrator-run controls, UART TX and shift
load. These biases are stronger than a conflicting legacy 100 kohm pull;
3.3 V with a 10 kohm pull against 100 kohm gives approximately 3.0 V high or
0.3 V low before leakage. This is a static calculation, not a proof of every
power-order transient. Inputs and external devices must be powered within their
specified voltage domain. A reset cannot preserve analog history physically
lost when its own supply disappears.

The maximum allocation for MCU plus the new sideband/reset loads must fit the
integrated HOST_3V3 budget. Neither a module typical current nor the four
shift-register static maxima constitutes a full dynamic worst-case power
measurement. The complete board-set budget records its chosen ceiling and
remaining thermal/measurement limits.

Native full-severity ERC, actual saved-file MCP pin/geometry inspection and
ten rendered PDF sheets are checked. These establish electrical representation
and inspectable engineering evidence. They do not establish production assembly,
oscillator accuracy, SPI eye margins, simultaneous startup safety, chronic
implant operation, clinical isolation or biological efficacy.
