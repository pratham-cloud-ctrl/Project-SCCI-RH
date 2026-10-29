# Recording front end: isolation, sequencing and sample identity

This is the 13 October 2026 control contract for the native
[recording-front-end slice](../../electronics/stage4/recording-front-end/).
It connects sixteen RHD2216 differential streams to the existing stimulation
design through an **external ordered controller**. The native slice contains the
input switches, clamp selection and isolated digital links; it does not contain
the controller firmware, independent voltage qualification or a complete power
system. The finite study below checks that contract rather than claiming those
external functions already exist.

The project still concerns implanted spinal access, a calibrated learner-specific
intervention and feedback about the delivered response. These electrical choices
make one recording path concrete. They establish neither human decoding accuracy
nor accelerated retained learning or pressure-regulation efficacy. The Stage 3
conditional biological assumptions remain separate.

## Electrical domains and controls

The RHD2216, input switching and local digital logic use a floating **AFE_GND**
domain. The driver/controller ground is a separate domain. Isolated SPI and mode
signals cross that boundary; their isolators do not provide isolated power.
Qualified external AFE supplies remain explicit ports. The shared recording
reference feeds sixteen negative inputs; it is not a stimulation return.

The two forward mode commands are **CONNECT_HIGH** and **RECORD_HIGH**, with
default-LOW ISO6741F channels. The native AND gate generates
`SELECT_ACQUIRE = CONNECT_HIGH AND RECORD_HIGH` for the bipolar SPDT clamps.
“Clamp” means connecting the RHD-side inputs to AFE_GND; it does not assert that
the external contacts, protected nodes or tissue have reached a safe potential.

| CONNECT_HIGH | RECORD_HIGH | Fault-switch request | RHD input selection | Contract meaning |
|---|---|---|---|---|
| 0 | 0 | Disconnected | AFE_GND clamp | Blanked/isolated command state |
| 1 | 0 | Connected | AFE_GND clamp | Connect protected nodes while the RHD remains clamped |
| 1 | 1 | Connected | Recording inputs | Acquire only after separate qualification |
| 0 | 1 | Disconnected | AFE_GND clamp | Invalid command; AND gate keeps the RHD clamped |

These are stable commanded states with valid supplies. Receiving-side brownout,
switch failure and asynchronous analogue transition timing are not established
by a Boolean truth table. Default-LOW also does not detect a controller that
freezes while its supply and high outputs remain present. An independent watchdog
and rail supervision are still system requirements. Link-loss events in the
finite model are externally observed inputs, not a claim that every communication
failure produces an isolator default.

**CS_ASSERT** is active high before its isolated link. Its island inverter creates
the active-low RHD chip select, so a LOW default requests deselection. The SCLK and
MOSI defaults are LOW. MISO and fault observations return through separately
assigned reverse isolator channels; a returned fault flag is not an independent
measurement that every RHD pin is within its small operating range.

## Ordered transitions around a stimulation event

The external controller must stop admitting new acquisition frames and invalidate
the affected analogue and digital-filter support before changing modes. The
sequence for a stimulation request is:

1. Hold both existing driver REQUEST inputs LOW. Command RECORD_HIGH LOW while
   CONNECT_HIGH remains HIGH, selecting the RHD-side clamps.
2. Wait the provisional **5 microsecond clamp guard**, then command CONNECT_HIGH
   LOW to disconnect the fault-protected input paths.
3. Wait the provisional **5 microsecond isolation guard**. Only then may the
   external controller assert the driver's independent admission/rearm procedure
   and REQUEST, with its monitor, route-lock, quiescence, rail and supervisor
   conditions satisfied.

The guards are design allocations for the future controller, not datasheet
guarantees of charge removal, pin-voltage containment or assembled gate timing.
This slice does not wire an independently verified “recording isolated” detector
into the driver. The finite model rejects an early request, while the actual
driver remains responsible for its own permission inputs. An unimplemented
external-controller ordering check is not credited as a hardware interlock.

After stimulation, keep REQUEST LOW and the recording path blanked until the
independent delivered-current/return condition is quiescent. Then:

1. Keep RECORD_HIGH LOW and raise CONNECT_HIGH. The protected nodes reconnect
   while the RHD-side inputs remain clamped.
2. Wait at least the provisional **5 microsecond connect guard**, and separately
   qualify the protected-node voltages, AFE rails and quiet differential input
   envelope. A timer alone cannot qualify these voltages.
3. Raise RECORD_HIGH. Qualify the analogue recovery/settling again after this
   transition, including any fast-settle procedure and switch charge injection.
4. Requalify the causal filter/feature support and issue a fresh acquisition
   epoch. A normal-looking ADC code or settled switch node alone earns no valid
   filtered feature.

The RHD input DC range and its approximately ±5 mV AC linear range are distinct
conditions. Fault protection against a much larger external excursion does not
extend either range. The finite model uses explicit external qualification flags;
it does not create a pin-voltage monitor that is absent from the schematic.
Example 9 millisecond or 200 millisecond events in the test histories are chosen
external qualification events, **not recovery measurements**. In particular, this package
does not turn the earlier 100 millisecond digital-filter failure into a passing
20 millisecond recovery claim.

## Explicit revision of the Stage 2 SPI proposal

Stage 2 proposed direct 8 MHz mode-0 SPI with 3 microsecond command slots.
Adding isolation changes the timing budget. The primary RHD specification gives
12 ns maximum MISO propagation from the relevant falling edge; nRF5340 SPIM
requires 19 ns MISO setup before the sampling edge. The selected 3.3 V ISO6741F
table gives 18 ns maximum propagation per direction. At 8 MHz the half-period is
62.5 ns, so the simple return-path margin is
`62.5 − 18 − 12 − 18 − 19 = −4.5 ns` before board or clock uncertainty.
The isolated slice therefore selects **4 MHz, mode 0, 16 bits per transaction**.
[Intan timing, p. 15](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf),
[TI ISO6741 timing table](https://www.ti.com/lit/ds/symlink/iso6741.pdf),
[Nordic SPIM electrical specification](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/spim.html)

| Timing item | Stage 2 historical proposal | Stage 4 isolated slice |
|---|---:|---:|
| SPI rate | 8 MHz | 4 MHz |
| Command slot | 3 microseconds | 5 microseconds |
| Nineteen-slot burst | 57 microseconds | 95 microseconds |
| Frame period / per-stream rate | 250 microseconds / 4 ksample/s | 250 microseconds / 4 ksample/s |
| Burst occupancy | 22.8% | 38.0% |
| First-to-last neural aperture spread | 45 microseconds | 75 microseconds |
| Pairwise phase spread at 300 Hz without alignment | 4.86 degrees | 8.10 degrees |

The 4 MHz return-path calculation leaves 58 ns before SCCI_RH allocations, or
**43 ns** after allocating 5 ns to board uncertainty and 10 ns to source-clock
edge/pulse shortening. The forward MOSI path allows **35 ns** after the Nordic
59 ns maximum MOSI-valid delay, 6 ns same-direction isolator skew, Intan's 10 ns
setup and the same SCCI_RH allocations. The 5 ns and 10 ns allocations are engineering
assumptions awaiting actual pin/load/layout timing, not measured guarantees.
Manufacturer timing limits only apply under their stated supply, temperature and
load conditions; the ISO propagation-table test condition is 100 kbit/s.

Within each 5 microsecond controller slot, CS_ASSERT rises at offset zero, the
first SCLK rising edge occurs at 125 ns, the sixteenth falling edge at 4,000 ns,
and CS_ASSERT falls at 4,125 ns. The nominal CS-inactive interval is 875 ns.
Local isolator/inverter edge delay must still preserve the RHD's 20 ns lead/hold,
154 ns CS-high and 950 ns conversion-cycle minima. The native inverter adds a
CS-path delay absent from the direct Stage 2 proposal. With a provisional 10 ns
inverter-delay allocation, the study computes 82 ns CS lead, 92 ns CS hold and
853 ns CS-high after its explicit propagation/edge allocations. The inverter
allocation must be checked against the selected SN74LVC1G04 and actual load. This is a schedule for
future timer/DPPI/GPIOTE/EasyDMA implementation, not a tested peripheral program.

The reserved neural peripheral remains SPIM0; driver preload and monitoring keep
their separate buses. The extra 38 microseconds per frame does not consume their
wire time, but concurrent DMA, interrupt, pin allocation and worst-case execution
must still be demonstrated. Slowing this neural bus does not validate either
of the other buses.

## Sample identity and aperture timestamps

The RHD pipeline has **two different offsets**: a CONVERT command received in
word `n` samples its selected analogue input on the **next local CS falling edge**
at word `n+1`, and its conversion result is returned during word `n+2`.
Consequently, timestamping the CONVERT command itself is one command slot early.
This is an explicit clarification of the historical Stage 2 timestamp proposal.
[Intan SPI pipeline, pp. 15–16](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

| Command slots | Commands sent | ADC responses retained |
|---|---|---|
| 0–15 | CONVERT(0) through CONVERT(15) | Neural results arrive in slots 2–17 |
| 16 | CONVERT(48), enabled supply observation | Supply result arrives in slot 18 |
| 17–18 | READ(63) pipeline flush words | No extra neural stream |

The first two received words of every burst are discarded, including after
startup or a lost epoch. Neural channel `c` is associated with response slot
`c+2` and local aperture at controller slot `c+1`, with **5, 10, …, 80 microsecond**
controller offsets. Add the actual CS isolator/inverter delay and its uncertainty
to those aperture timestamps. A DMA completion interrupt or radio packet time is
not an aperture. Equal timestamp offsets are not justified for sixteen multiplexed
streams.

This schedule sends 76,000 command words/s but requests **68,000 conversions/s**:
sixteen neural conversions and one supply conversion per frame. Its intra-burst
conversion spacing is 5 microseconds, equivalent to 200 ksample/s. The primary
RHD bias table therefore selects ADC-buffer bias **8** and MUX bias **32** for
the 220 ksample/s row until inter-burst settling is separately justified; applying
the ≤120 ksample/s bias row solely from the average rate is not sufficient.
Supply ADC channel 48 requires the VDD-sense enable bit in register 1; its nominal
scale is 74.8 microvolts/count. Configuration and readback are startup requirements,
not implemented firmware in this package.
[Intan registers, pp. 18 and 21–22; supply conversion p. 30](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

Startup must also leave at least 100 microseconds after enabling the internal
reference before claiming valid ADC operation, leave the specified initialization
delay before CALIBRATE, and complete **nine calibration dummy commands**. Those
nine commands are distinct from the two per-frame pipeline flush words. Under the
selected register-0 configuration, normal operation uses `0xDE`; `0xFE` asserts
amplifier fast settle. Intan recommends fast settle for `2.5/fH`, approximately
**8.333 milliseconds at 300 Hz**, followed by release of the fast-settle bit.
That recommendation is not a guaranteed bound on artefact, switch, amplifier,
electrode or digital-filter recovery. Actual recovery qualification remains
separate. The finite commissioning checks verify the delay/count/register
prerequisites only.
[Intan initialization and fast settle, pp. 19, 24 and 36](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf)

For this finite study, every frame requires nineteen complete 16-bit transfers,
the expected sequence and acquisition epoch, no observed SPI/DMA error, a bounded
aperture schedule and the external analogue/filter qualifications. A missing or
extra word, known stale buffer, epoch mismatch, wrong mapping in the independent
model or aperture-jitter excursion invalidates the **full sixteen-bit mask**.
The provisional controller aperture-jitter allocation is ±125 ns. A skipped frame
cannot borrow samples from the next frame to conceal the gap. The existing archive
FIR invalid-support rule remains in force.

RHD conversion words do **not** carry the synthetic channel/frame labels used
inside this mapping test. A replay of plausible 16-bit data that preserves current
DMA metadata may remain undetected. The study retains that failure witness rather
than claiming universal stale-data detection. Real firmware needs explicit buffer
ownership, transaction counters, configuration epochs and end-to-end fault tests.

## Verification and system consequences

The read-only command is:

```text
python electronics/stage4/recording-study/timing_contract.py --check
```

The saved [timing results](../../electronics/stage4/recording-study/timing-results.json)
contain **17 scenario groups, 56 passing assertions and 53 control snapshots**.
They cover the 8 MHz rejection/4 MHz revision, next-CS timestamps, pipeline flush,
incomplete/wrong/stale metadata, aperture-jitter boundaries, all four mode states,
ordered stimulation guards, unsafe simultaneous transitions, independent analogue
and filter recovery, link-loss return, unknown brownout and the undetectable replay
witness, plus startup delay, calibration count and fast-settle register checks.
The source checksum normalizes CRLF to LF for portable saved-result
verification. Only `--write-results` intentionally refreshes the result file.

The isolated front end also changes power and packaging. Its bipolar switches,
isolators, logic and external isolated supplies cannot fit inside the old
0.5 mW protection/bias allowance by assumption. The 4.5 mW Stage 2 total AFE
allocation is therefore not the assembled Stage 4 front-end budget. Manufacturer
typical currents, selected switching activity and unimplemented supply-conversion
losses need separate explicit accounting. The new components and isolation-domain
clearances also belong in the later PCB/CAD envelope. Neither a slower bus nor
a clean finite-study receipt resolves those costs automatically.

Before this contract becomes an operational system, complete the external
controller and voltage/rail supervision, native integrated driver connection,
isolated power, SPI configuration/readback and DMA implementation, measured pin
timing/load checks, actual analogue/filter recovery, PCB layout and the remaining
failure cases. These are bounded engineering tasks; they do not reopen the
conditional biological hypothesis as a prerequisite to completing the design.
