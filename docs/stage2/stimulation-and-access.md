# Stimulation, spinal access and the biological envelope

Document **S2-STIM-001** · Project SCCI RH · 8 October 2026. This is a numerical
design proposal for an entirely digital system. Values describing published
experiments, SCCI_RH engineering choices and unresolved biological properties are
kept separate. It specifies electrical tests, not a treatment protocol.

The machine-readable companion is [stimulation-budget-inputs.json](stimulation-budget-inputs.json).
The parameter/source audit is [biological-envelope-audit.csv](biological-envelope-audit.csv).
Application reasoning remains in the [Stage 1 mechanism dossier](../stage1/application-mechanisms.md).

## 1. What the selected access arrangement means

The reference platform has a **surface intradural recording interface** and a
**separate epidural stimulation interface**. Surface means nonpenetrating; it
does not mean noninvasive. Recording contacts, recording reference/ground,
stimulation contacts and stimulation return paths are distinct nets and physical
interfaces. A common controller does not make their biological roles equivalent.

For the motor reference, intradural observations near the thoracolumbar cord
are a hypothesis for observing population activity relevant to paced,
multidirectional foot placement. The stimulation target is the dorsal-root
entry/root organization serving selected lumbosacral motor pools. Recruitment
must be individualized. The task includes direction, placement accuracy and
coordination; rhythmic locomotor decoding alone does not establish its required
information. The 2026 circumferential recording study is short-term animal
evidence: 15 rats overall, five used for motor decoding, three acute pigs.
Its acquisition/decoder settings do not establish causal human intention
readout. [S2-BIO-003](https://doi.org/10.1038/s41467-026-75128-z).

For the physiological reference, an independently located epidural lead targets
the **last three thoracic spinal segments**, with external **systolic blood
pressure (SBP)** feedback. The reference actuator supplies calibrated **pressor
authority**. Lowering its command removes added pressor drive; it does not
supply an independent inhibitory or antihypertensive actuator. Continuous spinal
decoding is optional in this mode and must earn a measurable advantage over
external feedback. Motor and physiological application modes are initially
exclusive. This is an operating choice, not proof that the two anatomical
interfaces cannot coexist. [S2-BIO-001](https://doi.org/10.1038/s41591-025-03614-w).

Every anatomical drawing must label **spinal segment** or **vertebral level**.
Lumbar and sacral spinal segments are not located in identically numbered
vertebrae. Human spinal targets have no T13 segment. MRI-derived nerve-root
paths and the particular anatomy determine a proposed vertebral position; there
is no universal label conversion. Lead dimensions below are packaging
hypotheses, not a surgical placement plan.

## 2. Numerical evidence anchors and their limits

| Anchor | Directly supported electrical observation | What it does not establish |
|---|---|---|
| Phillips et al., 2025; 14 participants across four SCI trials | Pressor programs: 120 Hz, 0.3 ms width, up to 20 mA; three configurations, successive pulses separated by 2 ms. Earlier width mapping covered 100–500 µs. | The SCCI_RH symmetric recovery waveform, healthy consumer benefit, inhibitory authority or a universal chronic load. |
| Rowald et al., 2022; three participants with SCI | An illustrated program contrasts 20 Hz extensor/weight-acceptance and 100 Hz flexor bursts. Its control system supported up to four concomitant waveforms. | Four independent biological control directions, novice foot-placement learning, or all SCCI_RH amplitude/width settings. |
| Boston Scientific manufacturer documentation | A commercial current-programmed system exposes 0–25.5 mA, 20–1000 µs and 2–1200 Hz. Its programming manual imposes amplitude×width and shared-area scheduling restrictions. | Simultaneous operation at all extrema, applicability of its clinical approval to SCCI_RH, or a 40 V SCCI_RH compliance guarantee. |
| Medtronic manufacturer geometry | Listed 16-contact paddle examples use rectangular 1.5×4.0 mm contacts, 6.0 mm² each. | Anatomical fit or electrochemical qualification of an SCCI_RH lead. |

Sources: [S2-BIO-001](https://doi.org/10.1038/s41591-025-03614-w),
[S2-BIO-002](https://doi.org/10.1038/s41591-021-01663-5),
[S2-BIO-004](https://www.bostonscientific.com/content/dam/elabeling/nm/92469342-02_WaveWriter_Alpha_and_WaveWriter_Alpha_Prime_Implantable_Pulse_Generator_multi-OUS_s.pdf),
[S2-BIO-005](https://www.bostonscientific.com/content/dam/elabeling/nm/92395591-04_Rev_A_BionicNav_Program_Manual_multi-OUS_s.pdf),
[S2-BIO-006](https://www.medtronic.com/content/dam/medtronic-wide/public/united-states/products/neurological/2023-product-performance-report-neuromodulation.pdf).

Published **pulse width** is retained as that term. SCCI_RH additionally assumes two
actively driven, equal-duration phases. Matching a study's pulse-width number
does not prove equivalence of phase order, return shape, interphase interval,
field or recruited circuitry. Commercial active and passive recharge choices
demonstrate possible engineering approaches, not this system's biological effect.

## 3. Selected digital actuator contract

| Quantity | SCCI_RH reference choice | Status/meaning |
|---|---|---|
| Independently regulated drivers | **2**, maximum **2** concurrent | Selected architecture; four-driver scaling requires new budgets. |
| Routable stimulation contacts | **16**, plus **2** dedicated returns | Contact count is not driver count. Selected contacts may form bipolar pairs; dedicated returns are separately monitored. |
| Active current magnitude | 0.1–20 mA; zero disables stimulation | Hypothesized engineering range; polarity reverses in the balancing phase. Resolution/calibration remain a component-level contract. |
| Active phase duration | 50–500 µs | Engineering range spanning the pressure width anchor. |
| Pulse repetition per profile | 1–150 Hz | Engineering range; profile count, duration and routing constrain admitted schedules. |
| Command / delivery ceilings | 9 µC planned; 10 µC including delivery uncertainty | Selected software margin inside the electrical maximum; neither is a tissue-safety threshold. |
| Interphase gap | 100 µs nominal | SCCI_RH choice; both outputs high impedance during the gap. |
| Terminal compliance | 40 V usable differential | After driver/routing headroom; distinct from a 48 V boost rail. |
| Boost rail | Proposed16/24/36/48 V choices;48 V maximum | Fixed48 V stress examples below differ from the selected24 V low-current references; supply implementation remains pending. |
| Contact example | 6 mm²; 12 mm² sensitivity case | Manufacturer-sized illustration versus deliberate larger-contact alternative. |
| Dedicated return example | 24 mm² each | SCCI_RH area hypothesis; no assumed equal sharing or proven selectivity. |
| Contact material candidate | Pt-Ir, nominal 90/10 composition | Declared material hypothesis; surface finish/coating and chronic chemistry are unqualified. |

During an active phase, signed current is defined relative to the selected
source/return pair. It is **not** a signed biological command. A negative
balancing phase cannot be interpreted as negative pressure authority or selective
motor inhibition. Commands identify a qualified contact pair/profile, magnitude,
phase durations, start time and mode; an uncalibrated contact pattern has no
presumed functional meaning.

The nominal digital template uses −I for the first phase, zero in the gap and
+I for the second phase, with equal durations. The sign convention describes
current leaving the selected contact; a cathodic first phase is therefore
negative. Reversing order is a separate waveform test, not an assumed inverse
functional response. The chemistry of the candidate material, its surface finish
and any coating must be qualified together with the actual pulse waveform.

A source remains locked to its pair through both phases and recovery. Routing
changes only after discharge/monitor checks. The two sources require independent
current and compliance monitoring; concurrent patterns sharing a contact/return
are rejected initially. Two concurrent pulses do not establish independent
recruitment, because current fields and circuit responses may overlap.

## 4. Charge, area and polarization

For one rectangular phase, with SI units:

\[
Q_\phi=|I|t_\phi,\qquad
D_\phi=Q_\phi/A,\qquad
Q_{\rm net}=\int i_{\rm delivered}(t)\,dt.
\]

Equal commands imply zero ideal signed charge. Only integration of delivered
current establishes the model's actual residual. Clipped phases, timing errors,
leakage and interruption invalidate equality.

| Electrical example | Phase charge | Density at 6 mm² | Density at 12 mm² |
|---|---:|---:|---:|
| 0.1 mA, 50 µs | 0.005 µC | 0.0833 µC/cm² | 0.0417 µC/cm² |
| 10 mA, 300 µs | 3 µC | 50 µC/cm² | 25 µC/cm² |
| 20 mA, 300 µs | 6 µC | 100 µC/cm² | 50 µC/cm² |
| 20 mA, 500 µs | 10 µC | 166.7 µC/cm² | 83.33 µC/cm² |

These are geometric calculations. They do not establish reversible injection,
spatially uniform current density, absence of corrosion or safe tissue exposure.
Increasing contact area also changes field selectivity and lead dimensions.
A 24 mm² dedicated return receives 25 µC/cm² for 6 µC through that return,
or 41.67 µC/cm² for 10 µC; a selected 6 mm² bipolar return receives the same
nominal density as its paired contact. Neither may be replaced by an assumed
large case electrode without revising the current paths.

Primary platinum-macroelectrode experiments found lower and site-dependent
charge-injection capacity in vivo than in saline. A separate large Pt-Ir
experiment linked prolonged imbalance/residual potential to platinum dissolution;
its much larger electrodes and longer waveform differ from SCCI_RH. These results
support measuring the actual interface, rather than borrowing a universal metal
limit. [S2-BIO-007](https://doi.org/10.1109/TBME.2014.2366514),
[S2-BIO-008](https://doi.org/10.1371/journal.pone.0315779).

For electrical stress tests, each contact is approximated by a parallel
charge-transfer resistance and effective capacitance, with bulk path resistance
between contacts:

\[
C_k\dot\eta_k=i_k-\eta_k/R_{{ct},k},\qquad
V_{\rm terminal}=I R_{\rm bulk}+\eta_{\rm source}-\eta_{\rm return}.
\]

The declared, **unfitted** sweep is Rbulk=0.5/1/2 kΩ, Ceff=1/5/10/50 µF
**per contact**, Rct=10/100/1000 kΩ, initial polarization zero and adverse
nonzero states. The 5 µF nominal is a hypothesis, not a measured chronic
epidural property. A short phase gives approximately Δη=Q/C: 6 µC produces
6/1.2/0.6/0.12 V per contact across that capacitance sweep; 10 µC produces
10/2/1/0.2 V. The low-capacitance cases expose failure; capacitance cannot be
inflated until a desired current passes. Randles linearization cannot predict
irreversible chemistry at large excursions, and constant-phase/dynamic interface
models may be required. A two-terminal monitor cannot reconstruct each contact's
absolute potential against a chemical reference electrode.

## 5. Compliance is a conditional inequality

With 40 V already defined as usable terminal compliance:

\[
|I|R_{\rm bulk}+|\eta_{\rm source}|+|\eta_{\rm return}|
+V_{\rm blocking}\leq40\ {\rm V}.
\]

The 40 V limit applies at the maximum48 V rail. Lower rail choices retain the
8 V headroom allocation: the24 V reference has16 V usable terminal compliance.
Driver/routing headroom is allocated in the 48-to-40 V difference and is not
subtracted twice. For a deliberately chosen **4 V combined polarization reserve**
and zero additional blocking drop, 20 mA demands 14/24/44 V at 0.5/1/2 kΩ.
The 2 kΩ case fails. Its conditional current ceiling is **18 mA**, before
additional margins. The 4 V reserve is an electrical stress assumption, not a
permitted electrode potential. Larger polarization or blocking drops lower the
current ceiling further.

If two series blocking capacitors of 10 µF are used, a 10 µC phase can add
approximately 2 V of combined capacitor excursion. The same 2 kΩ ceiling then
falls to 17 mA. This is an illustrative topology calculation, not a selected
capacitor implementation. Differential swing, capacitors, switch ratings and
driver stability must be reconciled in Stage 4. Open/high-load requests cannot
be passed by assuming the load will become smaller.

## 6. Pulse scheduling, power and recovery

The pressure reference uses three **profiles**, not three simultaneously active
sources: offsets 0/2/4 ms inside an 8.333 ms frame (120 Hz). The assumed SCCI_RH
waveform occupies 0.7 ms electrically: 0.3 ms phase, 0.1 ms gap, 0.3 ms phase.
A separate **1 ms recording recovery allocation** gives a 1.7 ms blanked
interval per pattern. Global blanking totals **61.2%** for the nonoverlapping
three-pattern reference. This is why physiological mode uses external pressure
feedback and does not guarantee uninterrupted neural decoding. The timing
companion must test the interval union and longer-recovery cases; blanking is
not independent noise that can be averaged away.

The integrated [timing contract](timing-and-control.md) includes the100 µs
preguard, giving64.8% global masking rather than the61.2% unguarded illustration
above. It also separates the150 Hz **per-profile** ceiling from physical-source
service. Source0 can serve the three120 Hz profiles sequentially (360 events/s)
only if the0.95 ms waveform-plus-reconfiguration allocation and independently
qualified contact/return health fit the2 ms minimum start gap. The250 µs
reconfiguration allowance includes finite SPI and local admission work.

For symmetric pulses, active electrical duty per profile is d=2tφf. The
conservative fixed-rail energy allocation is

\[
P_{\rm rail}=\sum_j48|I_j|\,2t_{\phi,j}f_j,
\qquad P_{\rm battery,stim}=P_{\rm rail}/\epsilon,
\]

with **assumed conversion efficiency ε=0.8**. This assumes no regenerative
energy recovery and excludes converter idle draw, housekeeping, sensors,
recording, computation and telemetry. Simultaneous pulses create rail-current
peaks; sequential patterns still add average energy.

| Illustrative schedule | Rail power | Battery stimulation allocation | Bulk-load dissipation at 1 kΩ per pair |
|---|---:|---:|---:|
| One low-end profile: 0.1 mA, 50 µs, 1 Hz | 0.00048 mW | 0.00060 mW | 0.000001 mW |
| Two motor profiles: 10 mA, 300 µs, 100 Hz | 57.6 mW | 72 mW | 12 mW total |
| Three pressure profiles: 20 mA, 300 µs, 120 Hz | 207.36 mW | 259.2 mW | 86.4 mW total |
| Two upper-bound profiles: 20 mA, 500 µs, 150 Hz | 288 mW | 360 mW | 120 mW total |

These are scheduled-average allocations assuming each profile runs every
frame, not empirical usage statistics. The 10 mA motor row is a chosen budget
case, not a measured optimal setting. Two simultaneous upper-bound sources
draw 40 mA from the high-voltage current-output stage and allocate **1.92 W
instantaneous rail power** while phases are active. Bulk dissipation and driver
loss occur in different places; battery drain cannot all be assigned to implant
case heating, nor can tissue deposition be ignored.

The pressure and upper-bound cases are admitted continuously **only if** the
whole-device power, energy, component peak and thermal budgets permit them.
Otherwise the architecture must reduce current/profile use, duty or service
duration, improve a specifically modeled converter, or accept a larger energy
and thermal envelope. An admission controller must enforce the total allocation.
The scalar maxima above are not independent permissions to maximize everything.

Electrode discharge and amplifier recovery are separate processes. For two
equal 5 µF interfaces, the equivalent series capacitance is 2.5 µF. Even an
ideal shorting switch leaves the bulk path: at 1 kΩ, τ=2.5 ms. A 4 V adverse
pair polarization takes about **13.25 ms** to fall below an illustrative 20 mV
terminal-residual threshold through that path. A 1 ms recording allocation
cannot guarantee this reset. Such a state requires additional recovery,
inhibition and a failed readiness gate; it is not silently released at 1 ms.
The threshold is an electrical acceptance example, not a biological safety
criterion. Recovery effectiveness under chronic, nonlinear loads is unverified.

## 7. Evidence boundaries and Stage 2 acceptance

The publication-linked values support plausible electrical hardware ranges and
distinct spinal targets. The **full combination** of intradural recording,
personalized epidural intervention, healthy retained learning and automated
consumer physiology remains a proposed SCCI system. Neither the cited study
settings nor a successful digital budget establishes that combination.

Stage 2 acceptance requires these checks to remain visible:

1. Current, charge, compliance, active duty, routing, recovery and cumulative
   power are evaluated together for every admitted profile set. Failed requests
   are rejected or explicitly redesigned.
2. Both phase currents are integrated, including clipping and stop faults.
   Software stop completes the balancing action only if energy and circuitry
   remain available; power loss cannot guarantee balance.
3. Pressure commands are nonnegative pressor drive. Out-of-range SBP, stale
   sensing and uncertain authority have specified suspension/limit behavior.
4. Motor observation age, missing samples and artifacts are exposed. A 25 ms
   command deadline does not remove a 500 ms feature-window information delay.
5. Access, contact area, interface impedance and recruitment are assumptions
   that can fail independently. Physiology, chronic electrochemistry and tissue
   compatibility are **open biological validation items**, not closed numerical
   budgets.

Stage 4 must specify independently monitored current/voltage, discharge paths,
lead-fault detection, high-voltage isolation from acquisition, routing interlocks,
stored-energy stop behavior and actual component tolerances. Stage 5 must
reconcile contacts, lead strain relief, separate placements, feedthrough count
and populated component envelopes. No reduction in implant dimensions is
credited before those interfaces fit.

## 8. Source access and provenance

Sources were audited on 8 October 2026. Phillips and El Hadwe full text were
verified through publisher/Europe PMC XML; the Rowald publisher figures and
15-page author supplement were verified, but its separately hosted full-paper
PDF could not be fetched in this audit. Consequently its current/width/load
settings are not filled in from memory. Boston and Medtronic official manufacturer
PDFs were read directly. Leung's primary abstract and author manuscript link
were accessible; numerical conclusions used here are from the abstract. The
Pt-Ir study's full primary text was verified through Europe PMC XML.

Evidence grades in the CSV are **H**: human primary experiment; **A**: animal
primary experiment; **B**: primary material/bench experiment; **M**: official
manufacturer documentation; **D**: declared SCCI_RH design assumption/calculation.
These identify provenance, not certainty rankings. A clinical setting is not
automatically a safe setting for a different electrode, material or target.
