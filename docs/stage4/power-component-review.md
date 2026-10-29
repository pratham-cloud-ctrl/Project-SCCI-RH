# Power component review

Reviewed 14 October 2026 against manufacturer documents. This review fixes a
finite digital power architecture for the SCCI_RH demonstrator. It does not qualify
an implant supply, medical isolation, battery construction or physical thermal
performance. The saved native design and quantitative study supply the final
values and tests; recommendations below are not measurements.

## Final native review

The frozen package contains 156 components, 449 exported pin connections and
15 sheets. A bounded final review of the actual connectivity and XML confirms
the buck SW/VOS/feedback paths, boost diode polarity and feed-through path,
AFE regulator polarity and isolated grounds, module remote/NC pins, local
footprint identities, capacitor networks and native enable/interlock paths.
The saved read-only verifier passed, including zero ERC violations and all
256 combinations of the eight independent gate inputs. No critical pin,
feedback, polarity or ground error was found within this review's scope.

The five actual TPS3700DDCR windows have nominal rising thresholds of
6.60/8.60 V for battery, 3.10/3.50 V for SUP_3V3, 4.75/5.25 V for SUP_5,
3.98/4.22 V for MON_VREF and 1.98/2.12 V for MON_VMID. They use 10 kΩ lower
divider resistors; actual corner/hysteresis limits belong to the saved power
study. REF_OK qualifies U237's POWER_RUN_OK output without gating initial
HOST_ENABLE, so reference startup does not depend on its own qualification.
U235 receives POWER_RUN_OK on pin 2 and provides the open-drain PWR_FAULT_N
on pin 4. The existing supervisor's fault node supplies its pull-up. These
connections support immediate inhibition with valid supervisor power;
unpowered buffer behavior and whole-battery loss are not an asserted-low
guarantee.

## Battery and input

Select the protected **Tenergy AT31004**, 2S1P, 7.4 V nominal, 2.6 Ah,
19.24 Wh, 5 A continuous, 67 x 37 x 21 mm, 99 g, bare leads. Distinguish this
AT-prefixed 5 A part from the related 31004 2.6 A part. The proposed electrical
operating allocation is 6.4–8.4 V at the pack connector. The manufacturer's
cell protection thresholds are emergency protection; they do not establish
that allocation or usable energy above its lower limit. Capacity and runtime
derating remain explicit study assumptions. [Manufacturer pack page](https://power.tenergy.com/AT-7.4-2600mAh-5A-batterypack/).

Select offboard **Tenergy TLP-2000, item 01211**, 500 mA, with the 7.4 V/2S
selection. The pack page lists it as compatible. Its manual requires a protected
pack. SCCI_RH has no onboard charger and does not claim charging while connected
to the electronics. [Charger manual](https://power.tenergy.com/content/manuals/01211_manual.pdf).

The input path uses a 2 A fuse, series reverse-polarity diode and physical master
disconnect. A fuse's printed current is not a precise electronic current limit;
its clearing time and fault selectivity remain unqualified. The battery
protection board, fuse and supervisor share the battery as an energy source.

## Bucks and exact pin identities

**TPS62160DGKR**, VSSOP-8, supplies independent SUP_3V3, SUP_5 and HOST_3V3
branches. Manufacturer limits are 3–17 V input, 0.9–6 V output and up to 1 A.
Its pin map is 1 PGND, 2 VIN, 3 EN, 4 AGND, 5 FB, 6 VOS, 7 SW, 8 PG.
There is no exposed pad on DGK. PG is open drain and becomes high impedance
when disabled; a pulled-up PG alone must never authorize stimulation.
VOS senses the output after the inductor. The standard starting LC network is
2.2 µH and 22 µF, with 10 µF input bypass. Nominal feedback is 0.8 V, so a
10 kΩ lower resistor gives 31.25 kΩ upper for 3.3 V and 52.5 kΩ for 5 V.
The suggested network is within the manufacturer's examples, but layout,
effective ceramic capacitance, ripple and dynamic stability require later
physical verification. [TI TPS62160, Rev. E](https://www.ti.com/lit/ds/symlink/tps62160.pdf).

**TPS62130ARGTR**, VQFN-16 with grounded exposed pad, supplies HOST_5 at up
to 3 A. Pins: 1/2/3 SW; 4 PG; 5 FB; 6 AGND; 7 FSW; 8 DEF; 9 SS/TR;
10 AVIN; 11/12 PVIN; 13 EN; 14 VOS; 15/16 PGND; pad 17 GND. Connect
FSW and DEF low for nominal output and nominal 2.5 MHz operation; use
3.3 nF from SS/TR to ground. A 2.2 µH/22 µF filter, 10 µF input capacitor
and 100 nF AVIN bypass follow the example. The same 0.8 V divider sets 5 V.
The A suffix deliberately gives PG low in shutdown while input remains present;
it becomes high impedance after input removal. PG still does not replace the
independent TPS3700 rail windows. [TI TPS62130A, Rev. F](https://www.ti.com/lit/ds/symlink/tps62130a.pdf).

## Boosts

Use separate **LT8330ES6** TSOT-23-6 converters for HOST_15 and HOST_24.
Pins are 1 SW, 2 GND, 3 FBX, 4 EN/UVLO, 5 INTVCC, 6 VIN.
The device has a 3–40 V input range, nominal 2 MHz oscillator and 1 A
minimum switch-current limit. Positive FBX is 1.6 V nominal, 1.568–1.632 V
over the stated temperature range. With 50 kΩ bottom resistors, upper values
are 418.75 kΩ for 15 V and 700 kΩ for 24 V. A 4.7 µH inductor,
10 µF input bypass, 1 µF INTVCC capacitor, 44 µF nominal output bank and
4.7 pF feed-forward capacitor are the selected starting network. Current
ceilings, minimum inductance/frequency, effective capacitance and conversion
efficiency must be checked together; the 1 A switch rating is not a 1 A
24 V output rating. **Disabling a boost stops switching but leaves the
VIN–inductor–diode–output conduction path.** [ADI LT8330, Rev. D](https://www.analog.com/media/en/technical-documentation/data-sheets/lt8330.pdf).

The chosen Bourns SRP5030T-2R2M/4R7M inductors have ±20% nominal tolerance,
35/53 mΩ maximum DCR and 9/6 A typical saturation-current definitions,
respectively. Their 5.7 x 5.2 x 2.8 mm package is a deliberate demonstrator
allocation, with current margin above the converter switch limit. Magnetic
loss at the actual switching frequency and board temperature remain outside
the simple budget. [Bourns SRP5030T](https://www.bourns.com/docs/Product-Datasheets/SRP5030T.pdf).

## Floating recording island

**TRACO TMR 3-0522** accepts 4.5–9 V and supplies regulated ±12 V,
125 mA per rail, 3 W total. Pins: 1 −VIN, 2 +VIN, 3 current-controlled remote,
5 NC, 6 +VOUT, 7 isolated common, 8 −VOUT; position 4 is absent. The
21.8 x 9.1 x 11.2 mm SIP outline uses 2.54 mm pin pitch with the missing
position represented physically. Leave remote open for on; it is not a
TTL enable. Manufacturer values include 60 mA **typical** no-load input,
81% typical full-load efficiency, no required minimum load, 470 µF maximum
external capacitance per ±12 V rail, 30 ms typical startup and 5% cross
regulation at a 25%/100% asymmetric test condition. The low unequal SCCI_RH
loads are not that test. The study's raw-rail and efficiency envelopes are
declared assumptions, not extrapolated guarantees. Its 1600 VDC/60 s test
is **functional insulation**, with up to 200 pF isolation capacitance.
[TRACO TMR 3 datasheet, February 2024](https://www.tracopower.com/products/tmr3.pdf).

Use **TPS7A4901DGNR** positive LDOs for +5.30 and +3.45 V. Pins are
1 OUT, 2 FB, 3 NC, 4 GND, 5 EN, 6 NR/SS, 7 DNC, 8 IN; ground pad 9.
Leave DNC electrically unconnected. EN may connect to IN. Nominal FB is
1.185 V, distinct from the NR/SS reference. A 10 kΩ lower divider needs
34.725738 kΩ upper for 5.30 V or 19.113924 kΩ for 3.45 V; actual saved
series values/trim arrangements take precedence. Use 10 µF input/output
capacitors, 10 nF NR/SS and 10 nF OUT-to-FB feed-forward. Output limit is
150 mA; maximum dropout is 600 mV at that load. Overall accuracy is
**±2.5%**, not the tighter initial/nominal figure. Thus full datasheet corners
can fail the supervision startup window safely. Selected/characterized ±0.5%
operation is an explicit conditional assumption, not a TI guarantee. The
feedback network draws over 5 µA, meeting the stated no-load stability
condition. [TI TPS7A49, Rev. E](https://www.ti.com/lit/ds/symlink/tps7a49.pdf).

**TPS7A3001DGNR** generates −5.10 V with the same pin names/numbers, but
negative IN and OUT. EN may connect to negative IN to enable. Nominal FB
is −1.176 V; 10 kΩ lower and 33.367347 kΩ upper set the nominal output.
Use the same capacitor network with ceramic parts; any polarized capacitor
on a negative rail has its positive terminal toward AFEAGND. Maximum output
is 200 mA, overall accuracy ±2.5%, and maximum dropout is 600 mV at 200 mA.
The lower feedback resistor supplies more than the required 5 µA at no load.
The DGN exposed pad connects to isolated ground, not the negative input.
[TI TPS7A30, Rev. D](https://www.ti.com/lit/ds/symlink/tps7a30.pdf).

The installed DGN0008D footprint matches the published DGN0008D land
pattern, including the 0.65 mm lead pitch and 1.57 x 1.89 mm exposed-pad
mask opening. The current package appendix also lists DGN0008G variants;
the final populated PCB must bind the purchased package drawing/version
before manufacturing. SIP pin-row position and mechanical tolerances remain
nominal footprint allocations until that board/assembly review.

## Diodes and shutdown boundaries

Select **Vishay SS34-E3/57T** for input reverse-polarity protection, with
SMC/DO-214AB footprint, 40 V reverse and 3 A forward rating. Do not assign
an SMA footprint merely because some vendors sell similarly named parts.
Its maximum forward-drop figure is 0.5 V at 3 A under the documented
25°C pulse condition; a constant drop in the budget is an allocation.
[Vishay SS32–SS36](https://www.vishay.com/docs/88751/ss32.pdf).

Select **Nexperia PMEG6010CEJ** boost rectifiers, 60 V/1 A, SOD323F/SC-90,
pin 1 cathode and pin 2 anode. The 660 mV maximum at 1 A is a pulsed
25°C condition; temperature-dependent leakage and PCB thermal resistance
remain meaningful. [Nexperia PMEG6010CEJ](https://assets.nexperia.com/documents/data-sheet/PMEG6010CEJ.pdf).

Always-on means independent of the application enable while the master input
is present, not independent of battery removal. A failed host branch need not
remove SUP rails, but a shared battery, shorted regulator or ground fault can.
Terminal shutdown remains the previously designed guard/driver supervision
mechanism. Converter disable, passive bleeds, output capacitor stored energy,
master removal and battery-board cutoff are different operations. Capacitor
discharge times are conditional on the saved bleeder/capacitance model and
absence of back-power paths; they are not universally guaranteed hardware
shutdown times. No medical or chronic body-leakage qualification follows from
these selected catalog parts.

The optional **SN74LVC1G07DBVR** open-drain level buffer uses pin 1 NC,
2 A, 3 GND, 4 Y, 5 VCC. Its output is not a source of high voltage; a pull-up
defines the released level. Inputs must have defined levels and acceptable
transition rates, and loss of VCC does not create a guaranteed asserted-low
output. [TI SN74LVC1G07, Rev. AG](https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf).
