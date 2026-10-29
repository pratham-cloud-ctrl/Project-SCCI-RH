# Stage 3: mathematical and information boundaries

8 October 2026. This is an artificial full-loop mechanism study, using Stage 2's
16-stream recording and two-source output architecture. The unknown human signal,
recruitment and plasticity links remain hypotheses. Website and video are parked.

## Causal partition

The simulator owns hidden task/source state and true plant coefficients. A contact
forward model generates volts; a causal acquisition model produces timestamped,
quantized observations with validity. Expert training and learner calibration use
separate, declared observation sets. The controller receives those observations,
frozen representation, task goals and independent delivery estimates. Only the
body plant and evaluator receive true delivered charge or true response parameters.

The motor and pressure studies have separate APIs in [motor-model.md](motor-model.md)
and [pressure-model.md](pressure-model.md). A known task cue may be scheduled in
advance; future achieved state may not. Biological latency is not renamed processing
latency. Pressure observations carry their waveform support times even when delayed
or replayed. A predicted or missing value is never an observed signal.

## Electrical delivery

Let p be a **lumped pair** polarization voltage, R the series path, C an ideal
pair capacitor, and Rp parallel leakage. The deliberately reduced load obeys

    dp/dt = (i - p/Rp)/C
    v_terminal = R i + p.

For a requested signed phase j, the finite-compliance abstraction is

    i = clip(j, (-V-p)/R, (V-p)/R), V = boost rail - 8 V.

Within constant-current regions p approaches j Rp with time constant Rp C.
Within a rail-clamped region p approaches signed V Rp/(R+Rp) with time constant
C/(1/R+1/Rp). The integrator finds crossings analytically and splits the interval
there. The open interphase gap has i=0 and time constant Rp C. A deliberately
switched passive discharge path uses i=-p/(R+Rswitch). It has finite current,
energy and duration; it is not an instantaneous reset.

For every segment, the implementation integrates actual signed i dt and R i² dt
analytically. Cathodic charge magnitude, anodic charge, net drive charge and passive
discharge charge are distinct. A negative net drive value does not encode a negative
biological control direction. Task directions require separately calibrated routes.

The reduced interface is motivated by [Krishnan and Kelly, 2012](https://pubmed.ncbi.nlm.nih.gov/23366780/),
whose original work explains residual voltage with Faradaic impedance. This study
does **not** adopt their load values as measurements of SCCI_RH's contacts. Real
electrochemical elements can be nonlinear and geometry-dependent; see the primary
study by [Vatsyayan and Dayeh, 2022](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2022.972252/full).
Neither the linear model nor Stage 2's charge caps establish chemical safety.

## Independent observations and readiness

A separate simulated 12-bit current ADC samples each active source at 200 kHz,
with ±25 mA span, gain/offset and quantization. Pulse identity and phase windows
come from timer metadata; samples determine charge. Stage 2's rectangular nominal
command witness was

    Uq = 2 Icmd (5 us) + (0.5 LSB + 5 uA) Tphase + 0.02 Icmd Tphase.

That expression cannot cover an unknown increased recharge amplitude or a
prepolarized load whose current differs from its request. Stage 3 returns the
nominal witness separately and uses a wider, observation-based bound for **each**
phase, with sampled signed charge Qhat and actual ADC support Tadc:

    Uphase = (0.02 abs(Qhat) + (0.5 LSB + 5 uA) Tadc)/0.98
             + 2 (25 mA) (5 us).

The net-drive bound is the sum of the two phase bounds. Both absolute measured
phase charges plus their own bound must pass the delivered-phase cap. Saturated
ADC observations invalidate these bounds. The 25 mA peak is an explicit assumption
about the **complete analog waveform**, including between samples; non-saturation
alone does not establish it. Numerical witnesses cover bounded monotone/rectangular
phases. An independent analog peak guard and its transient implementation remain
Stage 4. ADC capacity alone is not independent shutdown. The conservative bound
increases uncertainty substantially at SCCI_RH's low-current reference; calibration
must propagate it rather than replace it with the favorable command witness.

Shorted terminal voltage can hide interface polarization. The model releases
the short and takes a separate 20 kHz open-terminal aperture 25 us later. The
new, chosen ±50 V input span through an assumed divider yields 24.414 mV/LSB.
With 2% gain and 5 mV offset bounds, the readiness decision requires

    abs(v_measured) + Uv <= 20 mV,
    Uv = (0.5 voltage_LSB + 5 mV + 0.02 abs(v_measured)) / 0.98.

These are new **engineering assumptions**, not manufacturer specifications or a
tissue voltage window. The aperture is within the existing 250 us rearm allocation;
an actual divider, protection, recovery and ADC switching design must earn this
budget in Stage 4. A null measured value still has roughly 17.6 mV uncertainty.
The gate uses the measured bound, not evaluator polarization truth.

## Application reduction

Motor pulses use the 3 mA, 200 us, 24 V reference. The adapter supplies separately
named actual cathodic charge to the body and measured charge plus uncertainty to
observation/calibration. Post-delivery recovery failure retains the already
delivered body dose and sets a subsequent-rearm veto. Only a pre-command envelope
rejection can produce zero delivery; the model cannot cancel a past pulse.
The motor delivery adapter latches that veto per physical source. Independent
simulator runs explicitly start fresh sessions; they do not share fault latches.
Automatic runtime requalification of a faulted real circuit is not implemented.
Pressure uses a frozen, offline electrical profile-characterization lookup, with
pre-admission rejection of an unqualified characterized profile. It uses the
3-profile, 3 mA, 300 us, 120 Hz-per-profile
reference and a 250 ms admitted-train fraction. For the long physiological study,
actual and measured charge ratios from a characterized pulse scale an **averaged
input**. This is an explicit reduction, not a microsecond circuit replay throughout
the physiological trajectory. Separate route states are assumed recovered between
reference pulses; continuous routing/power transients remain Stage 4 integration.

Even perfect electrical delivery does not establish recruitment or retained
learning. The body response remains a chosen structural family. Retention is
evaluated with assistance off, transfer uses a held-out task context, and zero or
harmful learning coupling is preserved rather than tuned away. For pressure,
nonnegative drive can help only if an individually identified positive pressor
response exists; it cannot independently lower a high baseline.

## Model coverage and unfinished integration

This package provides observable-data calibration, comparative computational
studies and exact reduced electrical examples. Native KiCad transistor/device
transients, continuous shared-source routing, embedded execution, tissue fields,
anatomical fit and chronic chemistry are later evidence. Their absence must not
be concealed by a successful artificial trajectory. The [progress record](verification-progress.csv)
tracks specification coverage separately from scientifically established efficacy.
