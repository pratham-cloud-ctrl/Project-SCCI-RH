# SCCI_RH-S4-PWR-01 - battery, rail generation and power interlock

**14 October 2026 - native digital engineering package - artificial loads**

Open [power.kicad_pro](power.kicad_pro), or use [OPEN_IN_KICAD.cmd](OPEN_IN_KICAD.cmd).
This package contains **156 components, 449 compared pin connections and 15
editable A2 sheets**, original pin-specific symbols, local footprint snapshots,
[BOM](bom.csv), [connectivity](connectivity.json), [XML](power.xml) and
[native netlist](power.net), [schematic PDF](power.pdf), [SVGs](svg/) and
[reviewed page renders](review/).

This supplies the concrete digital demonstrator architecture for SCCI_RH's spinal
recording, computation and learner-specific or physiological stimulation concept.
The selected pack, module and large discrete converters describe an inspectable
engineering demonstrator. They do not claim an implant-sized, chronically
implantable or clinically qualified power system. The project's conditional
biological mechanisms remain the Stage 3 baseline.

## Actual circuits

| Function | Native realization |
|---|---|
| Energy input | External protected Tenergy AT31004 2S pack, nominal 7.4 V / 2.6 Ah / 19.24 Wh; designed input range 6.4-8.4 V |
| Charging boundary | Compatible offboard TLP2000 PN01211 charger; no onboard or implanted charging circuit |
| Input protection | 2 A series fuse, SS34-E3/57T SMC reverse-polarity diode, external master switch and 100 uF bulk capacitor |
| Independent supervisor | Separate TPS62160DGKR converters generate SUP_3V3 and SUP_5 while the master remains on |
| Host low-voltage rails | TPS62160DGKR generates HOST_3V3; TPS62130ARGTR generates HOST_5, including the isolated module input load |
| Driver rails | Two LT8330ES6 converters with 4.7 uH inductors and PMEG6010CEJ rectifiers generate HOST_15 and VH_24 |
| Recording isolation | TRACO TMR3-0522 regulated 5 V to +/-12 V module, with distinct AFEAGND |
| AFE regulation | Two TPS7A4901DGNR positive regulators generate 3.45 V and +5.30 V directly from ISO_P12; TPS7A3001DGNR generates -5.10 V from ISO_N12 |
| Battery / startup readiness | Five TPS3700 windows monitor the battery, both supervisor rails, the existing 4.096 V reference and 2.048 V midpoint; native RC/Schmitt startup hold |
| Immediate power inhibition | Native AND gates and an open-drain SN74LVC1G07 pull the existing supervisor guard-fault net low when power readiness or reference readiness is lost |

The existing monitoring package owns the REF3440 and OPA391 reference circuits.
J6 takes their actual voltages; this package does not create duplicate references.
Its reference windows qualify readiness, not fine current-measurement accuracy.

## Enable and shutdown mechanism

The supervisor converters take PACK_BUS directly and remain independent of the
host request. SUP_READY requires both native supervisor rail windows and the
hardware startup hold. BATT_OK requires the battery window and startup hold.
HOST_ENABLE requires PWR_REQUEST, BATT_OK and SUP_READY. BOOST_ENABLE requires
HOST_ENABLE and the actual HOST_5 power-good output. HOST_5_PG is open drain and
can be high impedance while off, so it is never accepted on its own.

REF_OK requires both actual monitoring-reference windows. POWER_RUN_OK requires
BOOST_ENABLE and REF_OK. U235 pulls PWR_FAULT_N **low** whenever POWER_RUN_OK is
low; when healthy, it releases the drain. The integration wiring connects that
output to the existing supervision GUARD_FAULT_N wired fault node. The old
supervision package then consumes global ARM and commands all 18 body-facing
guards off. Returning power or reference health supplies no rearm clock.

Reference readiness deliberately does not gate HOST_ENABLE: the existing
reference circuits need the host rails to start. Global ARM, monitoring permit
and MCU firmware are also absent from the converter startup condition.

Disabling a boost stops switching but **does not disconnect its input-diode
path**. While the master remains on, HOST_15/VH_24 can settle near PACK_BUS minus
the rectifier drop. Buck output capacitors, module input energy and isolated
output capacitors also take time to decay. The independent open-drain power
interlock is therefore essential; guard shutdown is not credited to instant
rail collapse. Opening the master removes the input source, after which the
finite bleeders and loads discharge stored energy. Actual delays and faulted
switch behavior still require physical characterization.

The TMR3 remote input is current controlled. It is explicitly unconnected, which
means ON with a valid HOST_5 input. It is not driven by an invented TTL enable.
Removing HOST_5 conversion removes sustained input power, subject to residual
energy and any future backfeed paths.

## Rail trim and operating assumptions

Nominal feedback values produce the selected voltages. The TPS7A49 full
operating tolerance of approximately +/-2.5%, combined with resistor error, can
place some nominal AFE units outside the tight existing startup windows. This is
a recorded **safe-inhibit case**, not a hidden claim of guaranteed startup.
J410/J411/J412 provide output, feedback and floating-return test points. In a
quiescent artificial-load fixture with stimulation disconnected, select the
upper feedback resistor to reach the documented +/-0.5% operating target.
This is an explicit calibration/characterization assumption; it is not automatic
trimming, and a room-temperature trim alone does not prove full-temperature
stability. A drifting or untrimmed rail must remain inhibited when its actual
supervision window fails.

The two 22 uF boost capacitors per output have a modeled combined effective
capacitance of 30 uF and ESR of 0.1 ohm. The 100 uF input capacitor has a modeled
effective capacitance of 80 uF. These are declared bias/temperature assumptions,
not measured capacitor performance. Exact capacitor, fuse, resistor-series and
inductor procurement selections, startup inrush, loop stability, ripple, EMI,
thermal layout and package-version checks remain PCB/fixture tasks.

## Interfaces

| Connector | Ordered signals |
|---|---|
| J1 | PACK_POS, GND |
| J2 | PWR_REQUEST, SUP_READY, BATT_OK, HOST_ENABLE, BOOST_ENABLE, HOST_3V3_PG, HOST_5_PG, SUP_3V3_PG, SUP_5_PG, SUP_3V3, PWR_FAULT_N, GND |
| J3 | SUP_3V3, SUP_5, HOST_3V3, HOST_5, HOST_15, VH_24, GND |
| J4 | AFE_3V3, AFE_P5, AFE_N5, AFEAGND |
| J5 | PACK_BUS, ISO_P12, ISO_N12, AFEAGND, GND; distinct return pins, never a ground jumper |
| J6 | MON_VREF, MON_VMID, GND |

PWR_REQUEST is a demonstrator control that may be jumpered to SUP_3V3; the native
10 kohm pulldown defaults it low. All connector footprints are digital fixture
allocations; they are not implanted connectors. The new package retains the
existing rail names, including the explicitly revised AFE nominal values.

## Verification and known limits

[verify_power.py](verify_power.py) independently compares all exported native
values, footprints and 449 pin nets with the package manifest. It checks the
selected manufacturer pin maps, input diode direction, actual switch/inductor
paths, negative-LDO enable polarity, unused DNC pins, distinct ground domains,
reference placement and all **256 combinations** of eight native gate inputs.
The final package has **zero full-severity ERC violations, no ignored checks**,
15 PDF/SVG pages, reviewed final renders and MCP geometry/pin/ERC results bound
to the saved schematic hashes.

The TRACO footprint records the manufacturer pin grid and missing position 4;
its pin-row-to-body Y allocation remains provisional pending package drawing
inspection in the populated PCB/CAD stage. The DGN0008D local land pattern is
explicit, with a 1.57 x 1.89 mm solder-mask opening over the exposed pad; incoming
package-version compatibility must be checked before fabrication. Local
footprint snapshots improve reviewability and do not establish assembly or
isolation-clearance qualification.

A functional module isolation rating and 200 pF stated interwinding capacitance
do not establish body leakage, clinical isolation or implanted safety. No cell
charging, battery-abuse test, measured loop response, hardware shutdown timing,
actual thermal rise or neural effectiveness is claimed. The sibling power study
and integration review quantify conditional budgets and fault histories.

Run the read-only verification with:

```text
python electronics/stage4/power/verify_power.py
```

Intentional regeneration uses build_power.py and native_render.py, followed by
KiCad netlist/PDF/SVG export, full ERC, MCP inspection, final rendered-page
review and an explicit --write-receipt refresh. Neither regeneration nor receipt
refresh is part of a routine verification run.
