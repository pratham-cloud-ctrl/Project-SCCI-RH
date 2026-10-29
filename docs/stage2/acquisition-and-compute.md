# Stage 2: acquisition and local computation

Design proposal checked on 8 October 2026. This is a quantitative architecture
contract, not a completed circuit, implant BOM or measured device. It implements
the responsibilities of S1-MOD-01 through S1-MOD-06 and interfaces S1-IF-03 through
S1-IF-08. Numerical inputs and their provenance are in
[acquisition-budget-inputs.json](acquisition-budget-inputs.json); the independent
source audit is [electrical-source-audit.csv](electrical-source-audit.csv).

## Provisional decision

Use one **Intan RHD2216** as a feasibility witness for sixteen differential
amplifiers and a shared multiplexed ADC. Connect sixteen recording contacts to
the positive inputs and a separate shared reference to the negative inputs. A
separate body-reference/bias contact establishes the input common-mode potential.
The resulting eighteen recording-side contacts provide sixteen sampled
differences, not sixteen independent bipolar electrode pairs. The two-driver
stimulation reference has its own contacts/returns; it does not borrow the neural
reference as a current return. Exact protection, bias network and lead geometry
are Stage 4/5 design work.

Use an **nRF5340 application core at 128 MHz when delivered-output monitoring is
active**, with the network core responsible for authenticated companion transport.
Training, model fitting and the expert library remain off device. Local acquisition,
causal feature extraction, bounded inference, pulse admission and state validity
remain on device. The independent electrical supervisor cannot depend on the
decoder, Bluetooth stack or application-core clock remaining healthy.

Acquire each stream at **4 ksample/s**. The motor estimator receives the causal
4 ksample/s path. A separate, explicitly delayed archive path is filtered and
decimated to 2 ksample/s. This small oversampling increase makes the analog
anti-alias requirement more credible than direct 2 ksample/s conversion. It does
not recover information absent from the selected population band.

## Evidence boundary and alternatives

The primary circumferential spinal study used 32 channels at 30 ksample/s, seven
bands extending to 3 kHz, bidirectional filters and overlapping 500 ms motor
feature windows. Its representative 300–2000 Hz traces had RMS amplitudes of
20.9–22.1 µV at rest and 44.2–52.1 µV during walking. Those rat measurements do
not establish human 1–300 Hz amplitudes or a causal fast decoder for foot
placement. SCCI_RH's reduced band and compact causal decoder are new hypotheses.
[El Hadwe et al., methods and Fig. 2](https://www.nature.com/articles/s41467-026-75128-z)

| Acquisition witness | Useful property | Cost or limitation for this reference |
|---|---|---|
| RHD2216, selected | Differential inputs; electrode DC rejection before fixed gain; bandwidth selectable in hardware | One multiplexed ADC, input common-mode limits, typical noise without a guaranteed maximum, protection/recovery still external |
| Two ADS1299 | Sixteen simultaneous 24-bit streams and programmable gain | 5 V analog supply; approximately 78 mW typical / 84 mW maximum for two chips under the stated normal-mode conditions; input DC/common mode still need an explicit front end |
| RHD2132 | Thirty-two inputs in one package | Shared-reference topology rather than independent differential pins; reference loading is inherent |
| Discrete differential AFE plus simultaneous ADC | Freedom to design protection, common mode and recovery | More component area, noise sources and verified power/timing work; becomes the revision if the selected integrated AFE cannot meet the artifact envelope |

The ADS1299's 0.14 µV RMS typical figure applies to 250 sample/s, gain 24 and
65 Hz bandwidth. At 4 ksample/s / gain 12 the table instead gives 0.65 µV RMS
typical over 1048 Hz. Neither is a guaranteed noise maximum or a direct
same-band comparison with the selected AFE. [TI ADS1299 Rev. C, §§7–8](https://www.ti.com/lit/ds/symlink/ads1299.pdf)

These catalog chips demonstrate realizable functions. The cited sources do not
qualify their packages, lifetime, materials, RF link or assembled electronics for
a chronic consumer implant. Plastic QFN parts must remain inside a separately
justified package. Bare-die availability does not establish a finished implant.

## Contact, montage and channel scaling

| Configuration | Recording contacts | Extra reference / bias contacts | Differential streams | AFE chips / physical ADCs | Raw 4 ksample/s payload |
|---|---:|---:|---:|---:|---:|
| Reduced | 8 | 1 / 1 | 8 | 1 / 1; eight amplifiers disabled | 512 kbit/s |
| Selected | 16 | 1 / 1 | 16 | 1 / 1 | 1.024 Mbit/s |
| Expansion | 32 | 2 / 1, one reference per sixteen-input group | 32 | 2 / 2 | 2.048 Mbit/s |
| Local bipolar alternative | 16 | 0 shared / 1 bias | 8 | 1 / 1 | 512 kbit/s |

ADC count is not sampled-stream count. Electrode count is not source count, and
recording stream count is not the number of independent output currents.
The selected stimulation architecture has two independent drivers and admits at
most two simultaneous configurations. Four-driver expansion requires a new
monitoring, power, routing and mechanical budget.

Eight streams reduce physical access and data burden but may lose spatial
information; there is no evidence here that eight or sixteen suffice for all
foot-placement states. Thirty-two streams are useful for spatial comparisons but
double acquisition/filter/storage costs. Comparing equal task/data budgets in
Stage 3 determines whether extra contacts contribute useful information. A
reference that fails electrically should be changed rather than treated as an
extra feature that an algorithm will automatically repair.

## Signal chain, offset and dynamic range

The proposed chain is:

`contact + reference -> modeled protection/isolation -> integrated AC-coupled
differential amplifier -> analog bandwidth limits -> multiplexed ADC -> aperture
timestamp + validity -> causal fast estimator / separately delayed archive`.

The manufacturer states input gain 192 V/V, an electrode-referred step of
0.195 µV, an AC linear range of ±5 mV, and DC input potentials within ±0.4 V
of chip ground. Its input noise is 2.4 µV RMS typical and varies less than 15%
with bandwidth; that is not a guaranteed worst-case limit. The stated supply is
3.2–3.6 V. [Intan RHD2000 datasheet, pp. 6–7 and 27](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

Input coupling removes differential electrode DC **before** the large amplifier
gain. This differs from subtracting a digital baseline after a saturated PGA.
Nevertheless, coupling does not permit arbitrary pin voltages: each contact and
the reference need a valid common-mode return near the floating AFE ground.
The proposed ordinary offset envelope is ±0.2 V per pin, with ±0.3 V qualification
cases. Excursions toward ±0.4 V increase input current substantially and are not
normal operating headroom. Neither a 40 V stimulation terminal nor a grounded
external instrument may be connected directly to an AFE input.

A passive, current-bounded body-bias path, separate from stimulation returns,
requires a tissue/lead/common-mode model. Exact impedance and protection devices
are not yet selected. Input protection must precede gain and must be evaluated
with supply off, open leads, routing faults and the maximum stimulation coupling.
Clamps, isolation switches and series impedance add leakage, charge injection,
noise and recovery time. The chip's ESD structures do not establish this protection.
The external protection/bias power and parasitic allowance below is provisional.

Use a declared quiet-state signal family of **10–500 µV RMS** for the digital
forward model; a 5:1 crest factor at its upper end gives 2.5 mV peak. These are
SCCI_RH test assumptions, not a measured human signal range. At 4 mV peak issue a
range warning/invalidate the channel; at or beyond 5 mV the model cannot claim
linear acquisition. The nominal quantization contribution is
`0.195 / sqrt(12) = 0.0563 µV RMS`. Sixteen output bits do not mean sixteen
effective neural bits. With a 5 mV-peak sine and 2.4 µV typical AFE noise, the
noise-limited amplitude SNR is approximately 63.4 dB before electrode/common-mode
noise. Calibration must verify gain/scale, not assume the nominal number forever.

## Noise and the shared reference failure case

For quiet acquisition only, use

`v_total² = v_AFE² + 4 k T B Re(Z_record + Z_reference + Z_series)
             + v_quant² + v_alias² + v_CM_intrinsic² + v_CM_mismatch²`.

This RSS model assumes the listed contributions are uncorrelated. In particular,
structured common mode and movement artifacts are not white noise; the result is
a budget, not a decoder performance prediction. Use 310 K for the passive thermal
term and 314.16 Hz equivalent noise bandwidth for a third-order 300 Hz low-pass.
The input-series allocation is 4.99 kΩ per leg for noise arithmetic only; Stage 4
may replace it when protecting the actual fault envelope.

| Quiet-state case | Nominal | Deliberately adverse |
|---|---:|---:|
| Effective recording / reference resistance | 20 kΩ / 2 kΩ | 1 MΩ / 20 kΩ |
| 50 Hz common mode at contacts | 1 mV RMS | 10 mV RMS |
| AFE RMS contribution | 2.4 µV typical | 3 µV chosen design allowance |
| Johnson contribution | 0.415 µV | 2.354 µV |
| Source-capacitance common-mode mismatch | 0.045 µV | 25.635 µV |
| Intrinsic CMRR contribution using typical 82 dB | 0.079 µV | 0.794 µV |
| Quantization / alias allowance | 0.056 / 0.6 µV | 0.056 / 0.6 µV |
| Total RSS | 2.511 µV | 25.936 µV |
| 10 µV signal SNR | 12.00 dB | −8.28 dB |
| 50 µV signal SNR | 25.98 dB | 5.70 dB |

The reference feeds sixteen input capacitances: nominally 192 pF rather than one
12 pF input. The loading model uses
`H_record = 1/(1+j 2π f R_record C_in)` and
`H_reference = 1/(1+j 2π f R_reference 16 C_in)`.
Its converted common mode is `|H_record−H_reference| × V_CM`. A chip's typical
CMRR does not remove this source-impedance imbalance. The adverse case fails the
proposed quiet-channel SNR gate of 10 dB at a 10 µV signal. A notch filter may
remove some mains contamination but is not accepted as a universal repair.
Channel validity, an improved reference, a local bipolar montage, buffering or a
different AFE are possible responses. Typical datasheet noise/CMRR still lack a
guaranteed maximum; the numerical design allowances are hypotheses to test.

## Sampling, anti-aliasing and causal delay

Select analog high-pass corner **0.1 Hz** and third-order Butterworth low-pass
corner **300 Hz**. The band is deliberately not flat through 300 Hz: the analog
response is −3.01 dB there. Features and their training data must use this same
transfer function. A one-pole high-pass has
`τ_g,HP(f) = f_L / (2π (f²+f_L²))`.
For the third-order low-pass, with `w=f/f_H`,

`τ_g,LP(f) = [1/(1+w²) + (1+w²)/((1−w²)²+w²)]/(2π f_H)`.

The ideal transfer functions give **1.4554 ms maximum group delay over 20–300 Hz**,
near 245 Hz, and **16.819 ms at 1 Hz**. Component/calibration tolerances and
post-ADC feature filtering remain additional terms. The 2 ms fast-band AFE
allocation therefore closes only for the ideal declared 20–300 Hz response.
A fast loop based on low-frequency movement history must account for its actual
information age. A short software deadline cannot make slow features fresh.

For frequencies folding into 1–300 Hz, the first high-frequency alias edge is
`f_s−300`. A third-order low-pass gives −45.20 dB at 1700 Hz for direct 2 ksample/s
conversion, versus −65.46 dB at 3700 Hz for 4 ksample/s conversion. A single
1 mV RMS tone at these edges would contribute approximately 5.50 µV or 0.533 µV
respectively. The 0.6 µV alias allowance thus depends on a bounded aggregate
out-of-band spectrum; it is not proved by one-tone arithmetic. Broadband spectra,
strong interference and saturation must be exercised. Blanked stimulation
artifacts are outside this quiet-state anti-alias budget.

The archive uses a proposed 31-tap Blackman-windowed sinc low-pass with 500 Hz
ideal cutoff, normalized DC gain and decimation by two. Its calculated amplitude
at 300 Hz is −0.442 dB and maximum magnitude over 1700–2000 Hz is −92.95 dB.
It adds **3.75 ms fixed delay**. These are numerical design calculations, not
measured hardware or implemented firmware. Coefficients are included in the
input JSON so Stage 3/4 can reproduce them. Invalid-sample masks propagate through
the FIR support; interpolating a gap does not restore validity. The motor path
does not silently receive this delayed archive stream.

## SPI and timestamp contract

The neural bus uses 8 MHz, mode 0, 16-bit transfers with a separate CS pulse for
every word. Select a provisional 3 µs command slot: 2 µs clock time plus setup,
hold and CS-high margin. Nineteen slots per sixteen-channel frame include
conversion/pipeline housekeeping and one supply observation. The burst occupies
57 µs of each 250 µs frame; neural aperture span is 45 µs. The source's 950 ns
minimum conversion cycle, 154 ns minimum CS-high time and two-command pipeline
must all be respected. [Intan SPI protocol, pp. 15–16](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

The selected neural peripheral is **SPIM0**, with timer/DPPI/GPIOTE controlling
CS and an EasyDMA array of two-byte transfers. This is a peripheral topology
proposal, not a tested register program. It must demonstrate precisely nineteen
transactions, no buffer overrun, correct pipeline mapping, and bounded aperture
jitter under concurrent radio/monitor DMA. The SPIM hardware exposes array-list
DMA, and the non-high-speed instances require GPIO CS control. [Nordic SPIM](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/spim.html),
[EasyDMA](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/easydma.html)

Timestamp the analog aperture, not completion of the interrupt or radio packet.
Store one 64-bit frame tick with versioned per-channel aperture offsets and the
identified command-to-sample pipeline. At the proposed 3 µs offsets, pretending
sixteen channels are simultaneous introduces up to 4.86° relative phase at
300 Hz. Any causal alignment/interpolation must add its own delay and invalidity.
Incomplete words, skipped bursts, timing excursions, rails outside range and
artifact recovery invalidate samples even if their ADC values look ordinary.

The monitor has its **own SPIM4 bus at 16 MHz**. A provisional 450 kword/s,
16-bit monitor stream uses 45% wire occupancy before CS gaps. This bus is not
shared with neural conversion. The rate reserves two active current measurements
at 200 ksample/s each, two voltage measurements at 20 ksample/s each and
10 ksample/s health/idle measurements. Exact current/charge accuracy, monitor
settling and independent trip response are in the stimulation contract; the
neural ADC and main MCU are not substitutes for independent shutdown.

## Throughput, storage and telemetry

The sixteen-stream raw ADC payload is 128,000 byte/s at 4 ksample/s. A frame
container adds a 64-bit aperture tick, 32-bit sequence number and two 16-bit
validity/range masks: `frame_bytes = 2N + 16`. Configuration epochs, per-channel
aperture offsets, reason codes and artifact intervals are separate versioned
metadata. A 48-byte selected frame uses 192,000 byte/s on the 4 ksample/s path,
or 96,000 byte/s after decimation. Thirty-two streams need two 32-bit masks and
a 20-byte header, giving 84 bytes per frame rather than 48. CRC/authentication is transport overhead, not
silently part of these raw storage sizes.

| Application RAM allocation | Bytes |
|---|---:|
| Two-second 2 ksample/s archive ring | 192,000 |
| DMA/short 4 ksample/s working buffers | 8,192 |
| Filter state, causal features and compact parameters | 32,768 |
| Firmware stack/heap/OS allowance | 131,072 |
| Telemetry, command and validity queues | 32,768 |
| Bounded delivered-current integration/monitor DMA | 8,192 |
| Total / remaining within 512 KiB | 404,992 / 119,296 |

The model/OS allowance is an allocation, not a linked-image measurement. The
separate network-core RAM is not counted as free application memory. A 256 KiB
MCU cannot hold this exact layout; reduce the archive window or change the memory
architecture. Thirty-two streams require **589,952 bytes** when the larger
84-byte frame, doubled feature/fast-buffer allocations and unchanged monitor/
OS/queue allocations are all counted, exceeding the physical application RAM;
reduce the ring to one second,
use separately budgeted memory or revise the MCU.

Normal telemetry carries state/features and faults: a proposed 128-byte payload
at 50 Hz is 51.2 kbit/s before protocol overhead. Companion clocks and sensor
uncertainty remain explicit. Continuous raw 4 ksample/s frame transport would
require 1.536 Mbit/s before RF overhead, so it is not a guaranteed Bluetooth
operating mode. A 2 ksample/s raw archive still needs 768 kbit/s. Use bounded,
leased diagnostic transfers and later upload; do not claim unlimited recording
from a two-second volatile buffer. Tissue attenuation, antenna/case interaction,
packet loss, security overhead and receiver placement need their own link budget.
No external flash is included for free.

### Flash and network memory

The [selected inputs](system-design.json) now allocate all application flash:
640 KiB firmware, 64 KiB boot/recovery, 64 KiB immutable session expert policy,
32 KiB configuration/calibration and 8 KiB bounded fault journal. The total is
**827,392 bytes**, leaving 221,184 bytes (21.09%) of 1 MiB. This is a **single
application image**. A second resident image, network-update cache or atomic OTA
update is not included. Flash service/recovery occurs with stimulation disabled;
actual recovery, interrupted writes and linked images require Stage 4 checks.

The network domain separately reserves 160 KiB firmware and 16 KiB boot/config:
180,224 of 262,144 bytes (31.25% spare). Its RAM reserves 32 KiB radio state,
8 KiB DMA, 4 KiB IPC and 4 KiB queues: 49,152 of 65,536 bytes (25% spare).
These are finite **allocations**, not measured Bluetooth stack usage. The two
domains do not borrow each other's unused memory. Nordic's separate capacities
are [manufacturer witnesses](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/keyfeatures_html5.html).

Output configuration has a third reserved bus, **SPIM1 at 8 MHz**. Up to
128 bytes for an admission transaction takes 128 microseconds on the wire,
leaving 122 microseconds of the existing 250-microsecond admission allowance
for local checks/setup. Pressure scheduling reserves 64 bytes per source event:
360 events/s uses 2.304% average wire capacity. Pulse edges use local timer/
gate control, rather than depending on an SPI transfer at each edge. The actual
DAC/routing protocol and transfer gaps must meet these allowances in Stage 4.
SPIM0, SPIM1 and SPIM4 are separately reserved; pin mapping and peripheral
conflicts with other serial modes remain native implementation checks.

## Computation budget and embedded partition

The arithmetic witness is a deliberately compact causal model: four simple
biquad band features per channel (proposed 1–4, 4–30, 30–100 and 100–300 Hz
features, with their actual causal responses calibrated), running power envelopes, the separate archive
FIR, and a 64-input/eight-output linear inference example at 200 Hz. The number
of output states is a budget witness, not the final task or neural decoder.
The source paper's LSTM/GRU and noncausal pipeline are not claimed to run here.

| Work | Arithmetic or scheduling rate |
|---|---:|
| Four biquads per channel, five MACs each | 1,280,000 MAC/s |
| Four power envelopes, two MACs each | 512,000 MAC/s |
| 31-tap decimation output at 2 ksample/s | 992,000 MAC/s |
| Linear witness, 64×8, 200 Hz | 102,400 MAC/s |
| Sum of MACs | 2,886,400 MAC/s |
| Assumed ten cycles per MAC | 28,864,000 cycle/s |
| Acquisition burst interrupts, 4000×300 cycles | 1,200,000 cycle/s |
| Policy, queues, masks and administration allocation | 3,000,000 cycle/s |
| Monitor integration, 450,000×10 assumed cycles | 4,500,000 cycle/s |
| Sum plus 15% computation contingency | 43,198,600 cycle/s |

At 128 MHz this is 33.75% of cycles, inside a chosen 60% ceiling. At 64 MHz it
is 67.50%, beyond that ceiling. The cycles/MAC and administration allowances
are unmeasured assumptions; CoreMark is not a MAC benchmark or a worst-case
execution-time proof. Stage 4 must compile the actual filters/decoder, measure or
bound cache/DMA/radio contention and verify each scheduling deadline. The
nRF5340 supplies an FPU, DSP instructions, 1 MiB application flash and 512 KiB
application RAM; these capabilities do not prove any particular model fits.
[Nordic product specification](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/keyfeatures_html5.html)

For thirty-two streams, the same arithmetic witness with doubled feature input
and channel-dependent administration, two acquisition bursts and the same monitor
needs approximately 81.22 Mcycle/s
including contingency: it exceeds the 60% ceiling even at 128 MHz. Fewer
features, a different model, reduced archive cost or a different processor is
required before adopting that expansion. These scaling failures are design inputs,
not hidden speed-ups.

## Power and implementation gates

The manufacturer's current-estimation model gives, for the selected chip:

`I_AFE = 200 + 16×7.6×0.3 + 510 + 2.14×(19×4) + 10
       = 919.12 µA`, hence `P_AFE = 3.033 mW at 3.3 V`.

This includes enabled supply sensing, with impedance testing and temperature
sensing off; CMOS switching/lead capacitance and external protection are separate.
Allocate **4.5 mW** including 25% model contingency and a 0.5 mW external
protection/bias allowance. It is not a vendor maximum. An LVDS implementation
adds approximately 18.8 mW/chip before its external link and cannot be substituted
without changing the budget. [Intan power model, pp. 34–35](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

Nordic's typical CoreMark current at 3 V / 25°C / DC/DC operation is 3.6 mA at
64 MHz or 8.0 mA at 128 MHz with the stated clock, cache/compiler and limited
retained-RAM conditions. The latter is **24 mW for that test scenario**, not an
assembled-device maximum. Allocate **35 mW** for compute, peripherals, active
memory, intermittent network processing and local-feature radio, pending actual
firmware duty/energy evidence. Do not sum every datasheet whole-chip current
scenario as if they were independent blocks. Continuous raw radio, diagnostic
wideband or continuous network-core computation needs a separate power case.
[Nordic current-consumption scenarios](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/current_consumption/doc/current_consumption.html)

A diagnostic 20 ksample/s/channel mode is possible as a separate experiment:
sixteen channels alone produce 5.12 Mbit/s. At a 7.5 kHz upper analog corner the
same manufacturer model gives approximately 8.07 mW/chip before external I/O,
but its anti-alias spectrum, burst schedule, memory and decoder cost must be
reopened. The 8 MHz / nineteen-slot / 57 µs burst does not fit a 50 µs frame.
This mode is therefore **not admitted by the selected fast-path contract**.
A higher-speed interface or continuous round-robin schedule is needed.

The neural witnesses need 3.3 V regulation despite the selected cell varying
below 3.2 V. They share no unbudgeted high-voltage power source. The stimulation,
monitor, supervisor, converter loss, cell and thermal budgets are separate and
must include the costs above. A third-party biomedical acquisition part and a
radio-capable MCU do not solve tissue selectivity, chronic recording stability,
retained learning or pressure-control authority.

Before native implementation: (1) verify quiet-channel and common-mode envelopes
against the generated contact model; (2) verify the chosen analog transfer and
archive filter numerically including invalid masks; (3) close the combined
timing/blanking, power and monitor budget; (4) implement/prove the peripheral
sequence and bounded memory image; (5) select and simulate actual protection and
bias circuits. A failure changes the architecture or its admitted mode rather
than being removed from the evidence register.
