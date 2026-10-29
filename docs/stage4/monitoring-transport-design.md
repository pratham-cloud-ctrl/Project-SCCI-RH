# Monitoring and companion interfaces

**14 October 2026 · SCCI_RH-S4-TRANSPORT-01 · bounded digital package**

The proposed spinal interface needs observations of delivered electrical output
and external physiological feedback, alongside its sixteen neural streams.
This package adds that observation transport to the existing native circuits.
It serves both expert-informed practice and target-specific pressure regulation.
Retained learning and selective physiological recruitment remain conditional
biological mechanisms; this package does not establish either benefit.

## Inspectable circuitry

The [native KiCad package](../../electronics/stage4/monitoring-transport/README.md)
contains an ADS8688 eight-channel raw-monitor ADC, input networks, internal
reference bypass, explicit endpoint ADC handoff, health observations and an
ISO6721BDR isolated bidirectional UART. The six earlier native packages remain
unchanged. The [primary component review](transport-component-review.md) records
manufacturer pins, reference behavior, timing and loading conditions.

| Observation | Circuit and allocation |
|---|---|
| Current | Existing nominal 2.048 V + 40 V/A taps; ADC0/1 average 200 ksps each |
| Pair voltage | Supervision's two scaled differential outputs; ADC2/3 each 20 ksps |
| Health | Reference, midpoint, pack divider and host 5 V divider; ADC4–7 each 2.5 ksps |
| Charge endpoints | Existing two ADS8866 devices, separate CNV/CS and shared 8 MHz MISO through two 330 Ω resistors |
| Companion | 1 Mbaud, 8N1 UART across ISO6721, separate externally powered companion ground |

The [new wiring plan](monitoring-transport-wiring.csv) joins actual power,
monitoring and supervision pins. Its independent audit also retains the earlier
134 wires. The raw ADC and endpoint buses are separate. Shared endpoint DOUT
requires mutually exclusive chip selects and release guards; passive resistors
do not guarantee correct data during simultaneous selection.

## Acquisition mechanism

The [control contract](transport-control-contract.md) gives every aperture,
command, readout and configuration epoch. A 400 µs superperiod contains 180
32-bit raw transfers at 16 MHz, each allocated 2.125 µs. Aggregate acquisition
is 450 ksps, within the ADC's stated 500 ksps capacity. Raw bus occupation is
95.625%; implementation must preserve the small timing margins.

The current taps have 4.25–6.375 µs gaps. The ADC samples the previously selected
channel while the current command chooses the next one. The selected format
has no hardware channel ID: configuration readback, priming and transaction
history are part of validity. A plausible wrong channel command can escape
detection. Lost or unknown transactions invalidate the epoch and new admission.

Only nRF5340 SPIM4 supports the proposed 16 MHz rate; its dedicated pins and
other peripheral ownership must be implemented in the next firmware package.
The saved event schedule is not a built target DMA implementation. The two
ADS8866 charge converters retain their 100 ksps-per-device capacity and a
14 µs minimum scheduled CNV separation. Their availability timestamps cannot
substitute for physical apertures or bounded cross-converter skew.

![Raw apertures and diagnostic queues](../../electronics/stage4/transport-study/figures/sampling-and-queues.png)

## Signal meaning and finite model

The [input study](../../electronics/stage4/transport-study/README.md) checks
192 divider corners, 16 direct-input corners and six artificial waveform cases.
Its DC model uses the manufacturer's 2.5 V equivalent input bias and input
resistance interval. A 10 Ω direct-source output resistance is a declared healthy
buffer assumption. Divider resistor tolerance and temperature drift are explicit.
The 100 Ω / 1 nF external network is present natively; its transient and actual
buffer stability are outside this finite model.

Three illustrative equal-pole filters span combined bandwidths of 7.5, 15 and
22.5 kHz around the typical 15 kHz internal bandwidth. These are model choices,
not vendor limits. The simulation uses exact piecewise-constant cascade updates;
an independent auditor recomputes every saved point by analytic superposition.
Quantized samples use actual nonuniform apertures and assumed exact DC calibration.
Offline charge diagnostics use only preceding samples at each hold interval.

A phase-only window misses filtered tail area. An extended window recovers more
area in this ideal model, while a 30 mA, 1 µs added spike is heavily attenuated.
Consequently this design does not certify instantaneous peaks or the earlier
4% phase-charge goal. The independent analog guards retain authority; digital
waveform estimates cannot replace them. A valid 5 V ADC supply means 4.75–5.25 V
at its pins; the existing gross rail window alone does not guarantee that range.

![Illustrative waveform and charge](../../electronics/stage4/transport-study/figures/filter-and-charge.png)

## Companion use in the theoretical system

During motor practice, the companion exchanges processed movement/neural
features and the expert-informed, learner-specific policy. The spinal system
admits only configured, qualified actions and records measured delivery.
Assistance-OFF assessments test retained learning separately. This is not
replaying an expert's voltage into another spinal cord.

During pressure mode, a separate sensor/estimator supplies timestamped SBP,
quality, calibration identity and uncertainty. The host checks the oldest support
age against 2 s, bounded clock uncertainty against 500 µs, sequence, session,
CRC and range before renewing authority. Data arrival is not measurement time.
Accepted observations still require deliberate rearm. The data range is an
engineering acceptance allocation, not a clinical treatment threshold.

A 3 s pressure lease and 250 ms motor lease prevent indefinite stale commands.
The saved hold/ramp fallback is a normalized policy assumption, not a validated
clinical response. Independent hard trips always inhibit output. CRC and a
trusted-session flag are not an implemented security protocol; sixteen additional
wire-budget bytes reserve a future envelope only. No radio, antenna, cuff,
through-tissue communication or pressure measurement device is built here.

## Resources and completion boundary

Monitor buffers require 7,808 of the existing 8,192-byte allocation. The overall
404,992-byte RAM allocation is unchanged pending the real link map. Normal
processed traffic including its reserve is 114,355.2 bit/s, below the allocated
160 kbit/s service. The UART has an 800 kbit/s byte ceiling before protocol
overhead. Continuous 4k raw export requires 1.728 Mbit/s; a 16 KiB queue fills
after about 141 ms. A 100 ms leased diagnostic burst fits the declared service
model. Even the 2k framed case exceeds this UART's continuous capacity.

The additive power overlay increases HOST3.3's cap from 70 to 80 mA and direct
HOST5 from 20 to 40 mA. The conditional active allocation becomes **2.800 W**,
or **5.497 h** at 15.392 Wh assumed usable energy. New capacitor energy is
counted separately; peer-side power is external. These are allocation equations,
not measured power or converter stability. The earlier compact thermal failure
and reference pack dimensions remain unchanged.

![Validity and power](../../electronics/stage4/transport-study/figures/validity-and-power.png)

This package is complete when its native exports/ERC/MCP/visual evidence,
independent schedule/protocol/input/integration audits and source bindings pass.
It does not wait for physical experiments or a miniature implant. Stage 4 then
has two bounded packages left: target firmware and consolidated populated PCB.
Stage 5 develops populated CAD; Stage 6 integrates the illustrated paper and
verified private release. Video and website remain parked.
