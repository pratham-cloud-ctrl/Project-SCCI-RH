# SCCI_RH analog reference

An editable, routed **5 V artificial-signal / electrical-test-load circuit**.
It is one recording channel and one fixed-current biphasic load channel. It is
not implant electronics and contains no populated ADC, processor or biological
interface.

Open **`scci_rh_reference.kicad_pro`** in KiCad 10.0.6 or later. Local symbols,
footprints and component STEP models accompany the project. The 80 x 50 x
1.6 mm board has four 3.2 mm mounting holes at (10,10), (70,10), (10,40), (70,40).

- [Circuit explanation and boundaries](../docs/electronics.md)
- [Schematic PDF](exports/scci_rh_reference_schematic.pdf)
- [BOM](bom.csv)
- [Native board](scci_rh_reference.kicad_pcb)
- [Board STEP](exports/scci_rh_reference.step)
- [Gerber and drill reference exports](exports/gerbers/)
- [ERC report](reports/erc.json) and [DRC/parity report](reports/drc.json)
- [Model parameters](simulation/parameters.json) and [results](simulation/metrics.json)
- [Generic-device SPICE circuit](simulation/current_sink_generic.cir)
- [Third-party library licenses](THIRD_PARTY_LICENSES.md)

The retained reports have zero ERC violations, zero PCB DRC violations, zero
unconnected items and zero schematic parity issues, with no excluded violations.
Those checks establish connectivity/layout consistency, not analog stability.
The generic-device SPICE study exposed an unprotected switching transient;
revision B adds two 12 kΩ output resistors and reduces the nominal modeled peak
from 1361.36 to 102.58 μA. The before/after evidence is retained. The load and
parasitic assumptions remain conditional; no universal current cap is claimed.
Do not infer fabrication readiness or biological safety from a clean rule report.
