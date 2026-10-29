# SCCI_RH-S4-MON-01 — dual-source monitoring cell

**12 October 2026 · first native Stage 4 circuit slice · artificial electrical loads only**

Open [monitoring_cell.kicad_pro](monitoring_cell.kicad_pro) in KiCad, then its
schematic editor. The root sheet and two source sheets are editable native
sources, with original local symbols and local footprint snapshots. A readable
[three-page schematic PDF](monitoring_cell.pdf) and individual
[root](svg/monitoring_cell.svg), [source 0](svg/monitoring_cell-Source0_monitor.svg)
and [source 1](svg/monitoring_cell-Source1_monitor.svg) SVGs accompany them.

This circuit investigates actual delivered phase charge, the largest electrical
uncertainty identified in Stage 3. It is one concrete subsystem of the proposed
spinal recording–interpretation–stimulation–feedback architecture. It does not
include a current driver, spinal electrode interface, HV routing, full independent
supervision, MCU, PCB or populated implant CAD. Stage 3 and the wider Stage 4
design remain open; see the [entry plan](../../../docs/stage4/entry-plan.md) and
[requirements trace](../../../docs/stage4/requirements-trace.csv).

## How the connections work

| Circuit | Native connections and purpose |
|---|---|
| Shared reference | U1 REF3440 supplies 4.096 V. Its force/sense pins are tied locally. R1/R2 and U2 OPA391 create a buffered 2.048 V midpoint. Each endpoint ADC has its own reference bypass capacitor. |
| Actual source current | R100/R200 are separate 2 Ω output-return shunts. U100/U200 INA241A2 measure their signed voltage at gain 20, giving `I_MON = 2.048 V + 40 V/A × I`. Driver feedback is a different, unimplemented circuit. The INA NC pin is explicitly grounded, as the manufacturer requires. |
| Continuous charge | U101/U201 OPA391, R101/R201 10 kΩ and C100/C200 22 nF form signed integrators around the midpoint. U3 TMUX1136 closes the feedback reset when `INT_RUN` is low; high selects an intentionally unconnected branch, opening reset. This 5 V switch never routes HV stimulation. |
| Endpoint conversion | U102/U202 buffer the integrators. A provisional 33 Ω/1 nF network feeds separate U103/U203 ADS8866 SAR ADCs. AVDD and DVDD are 3.3 V; the reference is separately 4.096 V. Each source has its own CONVST, CS and DOUT, with shared SCLK. These are the four-wire CS interface connections. |
| Peak window and latch | U104/U204 TLV3202 compare each current signal against the reference divider. Healthy HI_OK and LO_OK outputs combine with external supervision through U105/U205 SN74LVC1G11. U106/U206 SN74LVC1G74 asynchronously clear permission on any low; a deliberate rising REARM clock can restore it only while CLEAR_N is high. External supervision and REARM have pulldowns. |
| External contracts | J1 supplies explicitly regulated lab rails. J2 exposes MCU controls and endpoint reads. J3 exposes two external supervisor-health inputs and permissions. J4 exposes continuous current signals to a separate current/health ADC. Each child sheet has return-shunt and driver-permission connectors. Global labels connect these named nets across sheets. |

The INA channels and integrators are separate from the missing driver servos,
but the fast current guard shares its INA measurement with the charge channel.
That shared amplifier is a common failure point. This slice is not a complete
independent analog safety chain. `EXT_SUP_OK` must stay low until independent
compliance, duration, watchdog, rail and reference supervision passes. A pullup
on that connector would bypass missing functions and is not an admitted design.
Power sequencing and external driver shutdown must be demonstrated separately.

The shunts sit in artificial-load dedicated returns. Their endpoints are not
tied to ground in the schematic. INA input bias nevertheless creates internal
paths to its grounded supply domain; this does **not** establish a floating,
isolated, chronically implantable return arrangement.

## Phase-resolved observation

For an interval between observed integrator endpoints,

`Q = −(10 kΩ × 22 nF)/(2 Ω × 20) × (V_end − V_start)`

so the nominal scale is **−5.5 µC/V** and a 600 nC phase changes the integrator
by **109.091 mV**. Keep a baseline, a cathodic-phase/tail endpoint, an
anodic-phase/tail endpoint and a later net/tail endpoint. Store the two phase
charges separately as well as the net. Opposed large phases can cancel to zero;
a near-zero final integral cannot certify their individual doses.

Each ADC internally holds its input at its conversion aperture while the
integrator continues. Firmware must identify that aperture, its clock uncertainty
and its relationship to actual current observations. ADS8866 conversion-start
sampling and its aperture delay precede conversion completion/readout availability;
they are different timestamps. The four-wire CS protocol must establish DIN/CS
high at the CNV sampling edge and keep CNV high through the associated readout.
Command-edge timing alone
does not establish a waveform endpoint. Residual cathodic charge overlapping the
opposite phase cannot simply be assigned by command label; retain an interval or
reject the observation until the window/tail bound is qualified. Integrator reset
is allowed only after independently established output-off/recovery conditions;
it must never erase an unknown interrupted dose.

In particular, an anodic endpoint minus a cathodic endpoint also includes current
in the intervening gap/recovery interval. Admit phase attribution only with
measured zero-tail evidence or an explicit interval for that additional charge.
The endpoint ADC does not provide continuous waveform evidence by itself.

The ideal 16-bit charge step is **0.34375 nC**. This is arithmetic, not a measured
accuracy. Both endpoint errors, ADC INL/reference/settling, shunt/gain tolerances,
offset, reset injection, leakage, saturation and unobserved tails enter the full
interval. The tentative **24 nC / 4% at 600 nC** target is unearned. The old
**264.672 nC / 44.112%** result remains unchanged.

## Material constraints before extending this circuit

- **Power:** two INA241A2 devices alone can require 32 mW at 5 V, exceeding the
  old 20 mW total monitor/reference/gate allocation. Five OPA391 channels add up
  to 0.8 mW static at their 32 µA maximum; reference, ADC, comparator, logic,
  dynamic loads and conversion losses add more. A complete revised budget is
  required. The entry plan compares lower-IQ INA190/INA282 alternatives and
  explains their common-mode/bandwidth/accuracy restrictions.
- **Bias bypass:** INA241 inputs draw 25–45 µA each under specified conditions.
  One load-side 45 µA path over 200 µs is already 9 nC, larger than the proposed
  3 nC bypass allocation. A conservative two-input 90 µA × 200 µs stress is 18 nC, already 3% of the motor
  phase. It is an error-budget stress, not proof that both currents take that path.
  Resolve their actual paths and shunt-to-load charge relation over voltage,
  temperature and power state before making a dose claim.
- **Guard threshold:** the 10 kΩ/19.1 kΩ/10 kΩ divider gives nominal 1.04757 V
  and 3.04843 V thresholds, approximately ±25.0107 mA. This is a trip setting,
  not a proven peak cap. Amplifier/comparator/latch/driver delays and overshoot
  remain unbounded. The TLV3202 typical delay cannot certify the complete loop.
- **Analog behavior:** capacitor tolerance/absorption, reset-switch charge and
  leakage, amplifier stability, ADC charge kickback and effective 22 µF
  reference capacitance remain to be modeled. Selected passive values are
  requirements; exact purchasable resistor/capacitor MPNs are not selected.
  A reset injection at the integrator is magnified by
  `Rint/(gain × Rshunt) = 250` when expressed as electrode-equivalent charge;
  an unobserved differential 6 pC jump between endpoints corresponds to 1.5 nC,
  the entire proposed reset allocation. A settled baseline sampled after reset
  opens can cancel a fixed initial jump in endpoint subtraction; do not count
  that same jump twice. Settling, headroom, leakage and any later reset edge
  still require bounds. A typical switch charge specification cannot serve as
  its bound.
  The 5 V buffer can also drive beyond the 4.096 V ADC measurement range under
  faults. Input protection and saturation detection remain open; clipping or an
  unknown integrator history must reject dose certification, with no reset that
  silently discards that history.
- **Missing system:** compliance is differential across actual stimulation
  terminals; no compliance circuit is drawn here. HV driver/polarity/16-contact
  routing, separate watchdog/duration/reference health, acquisition, converters,
  telemetry and target firmware remain separate native design work. Existing
  package solids have not been populated with these components.

Commercial manufacturer specifications support circuit feasibility only.
None of these parts has been qualified here for an implanted chronic assembly,
biocompatibility, hermetic packaging or a demonstrated biological outcome.

## Sources, build and verification

[connectivity.json](connectivity.json) is the explicit component/pin/net manifest
and records primary manufacturer links and pending external functions.
[bom.csv](bom.csv) lists **70 components**. Revision 0.2 uses production
**OPA391DCKR** for all five amplifiers. TI's Rev E datasheet identifies DBV as
preview information; DCK has a different pinout: 1=IN+, 2=V−, 3=IN−, 4=OUT, 5=V+.
The critical pin checks independently verify all five DCK roles, INA241A2's 15 µV offset condition
from other family grades, and SN74LVC1G74 **DCUR** from the differently sized
DCTR package. ADS8866 AVDD is 3.3 V, not the 5 V analog supply. KiCad calls the
selected TI DGS 10-pin geometry `MSOP-10_3x3mm_P0.5mm`; package equivalence still
needs the assembly drawing review before PCB release.

The DCK snapshot is KiCad's `SOT-353_SC-70-5`, with 0.65 mm lead pitch and five
numbered pads. It is a nominal library land pattern, not a reproduction of TI's
DCK0005A recommended board layout. Its pad centers/dimensions differ from TI's
example; compare the package tolerances, copper, mask and stencil against the
selected assembly process before any PCB release. The pin remap preserves all
functional nets, 70 components and 245 pins. See the [package design review](design-review.md).

Generate sources with normal Python and the local KiCad share tree:

```powershell
python build_monitoring_cell.py
kicad-cli sch export pdf monitoring_cell.kicad_sch -o monitoring_cell.pdf
kicad-cli sch export svg monitoring_cell.kicad_sch -o svg
kicad-cli sch export netlist --format kicadxml monitoring_cell.kicad_sch -o monitoring_cell.xml
kicad-cli sch export netlist monitoring_cell.kicad_sch -o monitoring_cell.net
kicad-cli sch erc monitoring_cell.kicad_sch --format json --exit-code-violations -o erc.json
python verify_monitoring_cell.py --write-receipt
```

Run these from this directory. `KICAD_SHARE` can override the installed footprint
source path used by the generator; native files themselves are self-contained
with local library tables. No `pcbnew` Python module is needed. Prefer absolute
input/output paths in scripted exports. Sheet names
are portable and contain no Windows path punctuation.

The live export sequence is optional for auditing a frozen revision. Run
`python verify_monitoring_cell.py` from any platform to compare the committed
netlist, manifest, BOM, ERC, PDF/SVG and hashes with the frozen receipt. That
default command is read-only and uses the Python standard library; installed
`pypdf` supplies an additional PDF page-count check when available. Only the
explicit `--write-receipt` command rewrites the receipt, after intentional
native exports and visual review.

Receipt SHA256 hashes normalize CRLF/CR to LF for source/export text, including
native KiCad files, library tables, netlists and XML. PNG/PDF hashes use exact
bytes. Local KiCad preferences, caches and ignored failed-export placeholders
are excluded. This makes a frozen revision auditable after a Windows-to-Linux
checkout without rewriting the native exports.

KiCad **10.0.6** exported all three pages, SVGs and both netlist formats.
[erc.json](erc.json) records **zero violations and no ignored checks**.
The three externally supplied J1 rails have explicit power-output markers;
those markers declare lab supplies, not completed battery converters.
Passive connectors explain why missing external functions do not appear as ERC
errors: their absence remains a documented engineering limitation. No warnings
were suppressed to hide them.

[verify_monitoring_cell.py](verify_monitoring_cell.py) compares every exported
pin/net assignment with the manifest and checks critical supplies, polarity,
reset connections, footprint identity, BOM, ERC and export integrity.
[verification.json](verification.json) records the resulting counts and hashes.
All three PDF pages were rendered and visually inspected; retained
[review images](review/) support that check. These checks establish native
connectivity and inspectable exports only. Analog qualification comes next.

Local footprint snapshots are KiCad community libraries under CC-BY-SA 4.0
with the KiCad design exception; attribution and license text are in
[KICAD_LIBRARIES_LICENSE.md](../../KICAD_LIBRARIES_LICENSE.md). Native custom
symbols and the circuit generator are original project work. Some footprint
3D model references use KiCad's standard model variables; no populated PCB or
bundled enclosure/implant model is claimed by these snapshots.
