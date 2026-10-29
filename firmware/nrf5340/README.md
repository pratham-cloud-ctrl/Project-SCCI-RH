# SCCI_RH nRF5340 firmware

This is the actual C/Zephyr firmware package for SCCI_RH's digital SCCI engineering
concept. It connects the proposed seven circuit packages to a bounded processor
backend, a production policy runtime and an isolated companion protocol. The
firmware supplies inspectable implementation and build evidence; it has not
been flashed, measured on a board or used with a biological interface.

The main project still investigates expert-informed, learner-specific practice
and selected physiological regulation. Useful spinal features, individualized
recruitment and retained learning remain conditional mechanisms. This package
implements the electrical/data control path, rather than claiming those effects.

## What is implemented

| Path | Implemented firmware profile |
|---|---|
| Raw electrical monitoring | ADS8688 on SPIM4 at 16 MHz; five-byte, 40-clock frames with a hardware channel tag; nominal 100 us opportunities, at most 10,000 aggregate conversions/s and 1,250/tap before polling gaps |
| Neural recording | RHD2216 on 4 MHz SPIM1; sixteen streams at nominal 1 ms OBSERVE opportunities; controller aperture brackets and missing-frame validity |
| Charge observations | Both ADS8866 endpoint converters on shared 8 MHz SPIM2, common CNV edge, separate CS, explicit event/phase/reset identities |
| DAC and routing | SPIM3 plus dedicated preload/commit controls; fresh complete route preload, all eight active-Q bits compared before acknowledgement |
| Request deadline | TIMER compare through an allocated DPPI connection and two GPIOTE clear tasks; allocation failure inhibits; recorded hardware event consumed by the policy core |
| Companion | Isolated 1 Mbaud UART; processed neural features/health and external prequalified commands; timestamped 56-byte SBP packet validation |
| Policy and faults | Boot inhibition, explicit recovery/rearm, exclusive modes, bounded command leases, OFF trials, sticky hard trips and bounded fault history |

These are configured and compiled profiles. A physical sustained rate, signal
quality or interruption latency has not been measured. The older 450k aggregate
monitor schedule and 4k neural-stream proposal are retained architecture studies;
they are **not** the implemented firmware rates. The lower raw rate cannot
certify the earlier high-rate current-observation or 4% phase-charge target.
Combined polling has known gaps: nineteen RHD words with at least 8 us allocated
per word already occupy at least 152 us, exceeding one 100 us raw opportunity.
The serial health snapshot adds further delay. Counters and recorded timestamps
retain missed opportunities; the backend never inserts fabricated samples or
catches up by claiming a continuous earlier history.

## Where to start

- [Firmware design and evidence boundary](../../docs/stage4/nrf5340-firmware-design.md).
- [Primary component/peripheral review](../../docs/stage4/nrf5340-component-and-peripheral-review.md).
- [Pin map](../../docs/stage4/nrf5340-pin-map.csv).
- [Application entry](app/src/main.c), [backend interface](app/src/scci_rh_backend.h),
  and [production policy core](core/README.md).
- [Exact binary companion protocol and backend details](app/README.md).
- [Compiled policy test results](runtime-tests.json) and
  [read-only test runner](tests/check_runtime.py).
- [Linked ELF](artifacts/scci_rh.elf), [HEX](artifacts/scci_rh.hex),
  [binary](artifacts/scci_rh.bin), [link map](artifacts/scci_rh.map),
  [configuration](artifacts/build.config) and [device tree](artifacts/zephyr.dts).
- [Target build receipt](../../provenance/stage4-nrf5340-build.json) and
  [independent verification receipt](../../provenance/stage4-nrf5340-verification.json).
- [Third-party image attribution and retained licenses](THIRD_PARTY_LICENSES.md).

The application uses nRF Connect SDK v3.4.1 and the supported
`nrf5340dk/nrf5340/cpuapp` build target. That target supplies startup and linker
support; it does not turn the DK into an SCCI_RH carrier. Its existing buttons, LEDs,
flash and debugger connections conflict with some proposed pins. The dedicated
SCCI_RH carrier remains the next PCB package.

The new carrier dependency is explicit: four SN74LVC165A devices serialize eight
active-address bits and eighteen health/status bits, plus six fixed sentinel
bits. This permits the current design to use 46 GPIO. The devices are not yet
present in the seven frozen native circuits. The pin map also specifies the
common endpoint CNV and common driver-rearm fanouts.

## Recovery and operation

The processor starts with requests inhibited and retained charge history marked
unqualified. It commissions interfaces and observes health without granting
stimulation authority. A companion/operator must explicitly establish the
appropriate session and current configuration, issue a bounded mode/lease, and
request recovery.

Recovery first requests monitor-latch rearm under pre-monitor health and actual
quiet. It then waits for observed monitor permits before the separate fault-reset
and supervisor-rearm steps. It does not repeatedly clear a fault, infer quiet
from low REQUEST, or reset an interrupted dose out of the record. Route selection,
active-Q verification and per-phase rearm remain separate steps.

MOTOR and PRESSURE mode accept explicit qualified event plans. The firmware does
not autonomously decide which spinal contacts should teach a skill or produce a
pressor response. The companion policy must provide that individualized mapping.
An OFF trial records its plan without issuing requests. OBSERVE and DIAGNOSTIC
cannot admit a stimulation event. Diagnostic capture has a 100 ms lease; that
lease limits a data burst and is not a neural-recovery criterion.

Electrical health loss, expired permission, malformed or stale required input,
unknown conversion identity and queue overflow remove request/route intent and
leave sticky inhibition. New packets or restored health cannot restart output.
A fault never launches an automatic compensating phase. Immediate digital stop
is the selected stale-support behavior; the older study's hold/ramp alternatives
are not adopted as a clinical fallback.

## Verification

The [target build helper](../../scripts/build_nrf5340.py) uses the installed
Nordic SDK/toolchain and a path without spaces, as described in the
[toolchain record](../../docs/stage4/firmware-toolchain.md). Run it from the
repository root to rebuild the actual application:

```text
python scripts/build_nrf5340.py
```

The command compiles and links artifacts; it does not flash a device. The
[independent auditor](../../scripts/verify_nrf5340.py) checks the saved image,
source identities, pin bindings and resource evidence without requiring a board:

```text
python scripts/verify_nrf5340.py
```

Run the production core's finite host fault scenarios from the repository root:

```text
python firmware/nrf5340/tests/check_runtime.py
```

The runner compiles the same C source used in the target, with strict C11 warnings.
It independently creates the packet fixture using Python `struct` and `zlib`,
then compares results and source identities with the saved report. The default
run is read-only. Explicit `--write-results` refreshes the saved report.

At this checkpoint, the policy tests contain **75 scenarios and 713 assertions**.
The host runtime occupies **432 bytes**, including sixteen 16-byte fault records.
The final pristine target image uses **53,616 bytes of flash and 98,000 bytes of
RAM**. The linker gives this application 1 MiB flash and **448 KiB RAM**; the SoC
has 512 KiB physical RAM, with 64 KiB reserved by this board layout. The
[independent audit](../../provenance/stage4-nrf5340-verification.json) checks
those capacities and linked sections. This lower-rate implementation does not
include the full future models in the earlier 404,992-byte architectural budget;
its smaller footprint does not establish their complete deployment.

Actual recovery, stimulation artifacts, analog settling and implant behavior
are not established by a transport-valid sample. The configured 10 ms startup
discard is a heuristic, and the earlier fixed 100 ms recovery shorthand is
insufficient as a qualification rule. No neural decoder, pressure sensor,
authenticated radio link or biological benefit is manufactured by this firmware.
