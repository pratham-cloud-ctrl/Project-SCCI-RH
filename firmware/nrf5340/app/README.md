# SCCI_RH nRF5340 application-core commissioning backend

This is the target Zephyr/nrfx application, not the earlier desktop controller.
The publication build is `python scripts/build_nrf5340.py` from the repository
root using the verified local Nordic SDK v3.4.1 installation. No flash command
is included. `--incremental` is for development only. The exact selected sources,
ARM ELF/HEX/BIN/MAP, configuration, device tree and compiler evidence are bound
by `provenance/stage4-nrf5340-build.json`.

The board name selects the application-core SoC/linker target. The **46 GPIO
carrier mapping is not compatible with an unmodified development kit**: board
LEDs, buttons, external flash, NFC and forwarded network GPIO are disabled in
the software description, while physical attached circuits require a purpose
built carrier. The four SN74LVC165APWR input serializers are new explicit carrier
dependencies for the next populated PCB package, not components secretly
present in the seven frozen native circuit slices.

## Implemented path and deliberate timing boundary

- SPIM4: ADS8688 at 16 MHz, mode 1, RXDELAY 0, 40-clock tagged manual frames;
  all eight ranges and feature-format registers are written and independently
  read back. A command-readback check and prime/discard establish epoch 1.
- SPIM1: RHD2216 at 4 MHz mode 0. All 18 configuration registers, chip ID and
  amplifier count are read back. Vref/init delays, CALIBRATE plus nine dummy
  words and the fast-settle release are implemented. Nineteen-word OBSERVE
  bursts retain actual controller aperture brackets for sixteen signed streams
  and the supply observation. The mask certifies digital transport identity;
  it does not qualify analog recovery, neural information or decoding.
- SPIM2: the two ADS8866 endpoint converters at 8 MHz mode 0, simultaneous
  CNV fanout, sequential mutually exclusive CS, physical shared MISO. Baseline,
  first-tail and second-tail records retain event/phase/reset epochs. These
  fewer observations do not implement the earlier sixteen-capture high-rate
  schedule and do not earn 4% charge precision.
- SPIM3: write-only DAC80502 at 8 MHz mode 1. GAIN=0x0103 and both outputs
  zero are written at boot. GPIO clock takeover explicitly uninitializes SPIM3
  before shifting a route or reading the four-165 snapshot. DAC traffic changes
  candidate shift bits but cannot move the held active address. Route commit
  is followed by actual eight-Q snapshot, fresh ACK and fresh REARM.
- UARTE0: 1 Mbaud 8N1 interrupt-driven companion I/O with real bounded RX and
  normal/raw TX byte storage, CRC/length/sequence dispatch and explicit overflow
  faults. UART0 does not coexist with SPIM0; SPIM0 is unused. No radio or
  network-core image is built.
- TIMER0: 1 MHz 32-bit monotonic clock with checked wrap extension. Absolute
  CC2 publishes an allocated DPPI channel to both GPIOTE request-CLR tasks and CC1 capture. The ISR
  records that hardware event; main consumes it before advancing policy time.
  CPU GPIO start has a checked lead margin and interrupt-protected SET section.
  An unearned software/physical timing corner causes an inhibited fault rather
  than an automatic compensation phase.

The phase connection uses the SDK's GPPI allocator. Zephyr's UART enhanced-TX
support also allocates a DPPI connection, so channel zero is deliberately not
assumed free. Allocation or endpoint-attachment failure keeps requests inhibited.

Raw slots request a nominal 100 us cadence (10k aggregate ceiling, eight-channel
round robin); recording frames request 1 ms in OBSERVE. **Combined polling has
known gaps:** a nineteen-word recording burst and 32-bit health shift can delay
raw work. Actual aperture brackets, missed-slot/frame counters and known
transaction identity are retained. There is no catch-up burst and no continuous
450k monitor or 4k-per-stream recording claim. This is a functional commissioning
profile, not a physiological precision or real-time performance qualification.

Recording is only enabled in OBSERVE with outputs inhibited and actual quiet.
Switching to MOTOR/PRESSURE/DIAGNOSTIC blanks recording before an explicit
recovery request. A 10 ms startup discard is a heuristic, not an earned artifact
recovery duration. The companion receives absolute-value EMA features in ADC
counts, their oldest/current update timestamps, transport mask and an explicit
`analog_qualified=0`. Mode labels select lease and policy admission; a trusted
companion must supply any calibrated learner/physiological plan. No skill replay,
universal body automation or automatic physiological controller is claimed.

## Binary companion envelope

All integers are little endian. Envelope: `"AO"`, version u8=1, type u8,
payload length u16 (0..96), sequence u32, payload, CRC32 u32 over header+payload.
CRC is integrity/error detection, **not authentication**. Forward uint32 sequence
wrap is accepted; duplicates and half-range/backwards order are rejected. A new
trusted session establishes the explicit session/clock/calibration assumptions.
External clock estimates are supplied inputs, not a measured synchronization
protocol. Do not send a command until the preceding action/health transition is
visible; packets are not an authorization bypass around actual hardware state.

| Type | Payload | Operation |
|---|---|---|
| 0x01 | Exact 56-byte transport-study SBP packet | Inner CRC/session/time/quality/calibration parser |
| 0x02 | epoch u32, calibration u32, offset low i64, offset high i64 | Explicit trusted session |
| 0x03 | mode u8, three zero bytes, epoch u32, lease us u32 | OBSERVE=0, MOTOR=1, PRESSURE=2, DIAGNOSTIC=3 |
| 0x04 | Empty | Explicit monitor-first recovery; snapshot then fault reset/supervisor rearm |
| 0x05 | contact0 u8, contact1 u8 | Quiet preload/commit/actual-Q/fresh-ACK/rearm |
| 0x06 | epoch u32, event ID u32, current0/1 u16 in microamps, phase/gap u16 us, contact0/1 u8, source mask u8, off-trial u8 | Bounded external plan; core admission and hardware cutoff |
| 0x07 | Empty | Immediate sticky hard stop |
| 0x81 | 80-byte status/features described below | Device telemetry, 50 Hz requested |
| 0x83 | aperture low u64, epoch u32, capture u32, code u16, channel u8, valid u8, bracket width u32 | Diagnostic tagged raw record |

Status offsets: 0 local time u64; 8 configuration epoch u32; 12 fault total u32;
16 sticky reason u16; 18 mode u8; 19 state u8; 20 health u16; 22 analog-qualified
u8=0; 23 observing u8; 24 sixteen envelope u16 ADC counts; 56 RHD frame count
u32; 60 first feature-support time u64; 68 latest feature-update time u64;
76 feature transport mask u16; 78 reserved u16=0. An EMA retains older history;
the two timestamps describe that history, not a fabricated fresh sample window.
The feature mask is zero outside OBSERVE or after 100 ms without an update.

Diagnostic raw traffic can fill its 16 KiB queue at this encoding/rate; overflow
stops capture and inhibits, preserving an invalid gap rather than dropping data
silently. Normal telemetry uses its separate real 8 KiB queue. No claimed UART
or processor WCET, loss-free worst-case RX rate, battery current, hardware edge
timing or analog accuracy has been measured.
