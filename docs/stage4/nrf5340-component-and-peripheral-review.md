# nRF5340 firmware: component, peripheral and carrier review

14 October 2026. This review binds the actual nRF Connect SDK **v3.4.1**
application-core backend to the seven frozen native circuit interfaces. It
separates cross-compiled firmware, host-executed policy tests and proposed
carrier wiring from physical execution. No board has been flashed or measured.
The intended spinal interpretation, expert-informed learning and selected
physiological control remain conditional biological applications.

## Processor and build target

The selected production witness is **nRF5340-QKAA**, application core. The build
board `nrf5340dk/nrf5340/cpuapp` supplies a supported startup/linker target; it
is **not** the SCCI_RH carrier schematic. The network core and radio are not needed
for the isolated UART companion implementation. The [pin map](nrf5340-pin-map.csv)
assigns **46 distinct GPIO** and reserves P0.00/P0.01 for the low-frequency
crystal. P0.02/P0.03 require the actual SDK devicetree property
`&uicr { nfct-pins-as-gpios; };`, in addition to disabling the NFCT peripheral.
The old `CONFIG_NFCT_PINS_AS_GPIOS` Kconfig symbol is undefined in SDK v3.4.1.
The installed UICR binding explicitly identifies nRF5340 P0.02/P0.03; Zephyr's
nrfx CMake integration converts the property to the compiler definition
`NRF_CONFIG_NFCT_PINS_AS_GPIOS`. The installed MDK startup then clears the
UICR NFCPINS protection bit through NVMC and resets once on a device that
still has NFC protection set. Restoring that protection requires erasing UICR.
The generated devicetree/compile definition is build evidence; a physical
UICR register has not been checked because this project has not been flashed.
Disabling the NFCT node alone does not establish GPIO ownership. The physical DK attaches
buttons, LEDs, external flash and debugger communication to several selected
pins, including buttons on P0.08/P0.09. A successful DK-target build does not
make those connections suitable for an attached SCCI_RH circuit. [Nordic pin
assignments](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html),
[DK buttons and LEDs](https://docs.nordicsemi.com/r/bundle/ug_nrf5340_dk/page/ug/dk/hw_buttons_leds.html).

## Peripheral ownership

| Function | Actual application-core peripheral | Selected bus / allocation |
|---|---|---|
| ADS8688 raw monitor | SPIM4 | 16 MHz, mode 1, RXDELAY 0; P0.08 SCK, P0.09 MOSI, P0.10 MISO, P0.11 GPIO CS |
| Isolated RHD2216 command/results | SPIM1 | 4 MHz; four-wire SPI plus separate connect, acquisition and fault lines |
| Two ADS8866 charge endpoints | SPIM2 | 8 MHz; common CNV output, independent CS, physical joined MISO |
| DAC80502 and route candidate | SPIM3 | 8 MHz, mode 1; shared SCK/MOSI, independent DAC SYNC and route preload/commit |
| Serialized sideband snapshot | GPIO, exclusive with SPIM3 | Same physical SCK; separate parallel-load and serial-data pins |
| Isolated companion UART | UARTE0 | 1 Mbaud, 8N1, P1.12/P1.13; debugger output does not share this link |
| Monotonic microsecond clock | TIMER0 | 1 MHz, 32-bit counter; software must extend wrap correctly |
| Pulse request deadline | TIMER0 CC2 / DPPI / GPIOTE | Compare clears both requests and captures CC1 without a CPU interrupt; IRQ reports the captured event |

SPIM0 is deliberately unused because it shares an instance ID with UARTE0.
Direct register ownership and Zephyr/nrfx driver ownership must not overlap.
SPIM1/2/3 do not implement SPIM4's automatic CS or rates above 8 MHz. Use GPIO
for their chip selects and wait for completed EasyDMA before changing buffers,
clock ownership or CS. The [Nordic SPIM specification](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/spim.html)
and installed SDK headers support this allocation.

The selected SPIM4 SCK/MOSI pins use H0H1 output drive at 16 MHz and the
backend retains ordinary PSEL/GPIO routing so its CS remains software controlled.
The SoC's dedicated peripheral setting becomes necessary for a 32 MHz design;
that mode would exceed this ADC's 17 MHz limit. The current 16 MHz choice is
not proof of PCB signal integrity or ADC supply/reference validity.

## Raw conversion cadence: implemented profile and retained architecture

The earlier transport proposal allocated 180 four-byte frames per 400 us:
450k aggregate conversions/s and 2.125 us frame slots. That is an architecture
capacity calculation, not a measured or target-executed schedule. SPIM4's
`IFTIMING.CSNDUR` uses 64 MHz ticks, so value 2 requests at least 31.25 ns at
CS edges. Nordic explicitly states that system turnaround dominates for small
values. Writing 2 therefore does not establish the exact aperture interval or
450k sustained rate under RAM contention.

The actual firmware package uses a bounded **10k aggregate samples/s**
commissioning opportunity profile: eight channels nominally at 1.25k samples/s
each before polling/competing work. It retains
source/channel/configuration identities, detects missed scheduled opportunities
and does not establish continuous history. RHD frame reads and sideband
snapshots can occupy more than a raw slot; counted missed opportunities must
remain visible. A valid individual conversion/tag is not proof that a whole
interval was observed. This rate
is a declared implementation profile, not an achieved hardware throughput or
a substitute for the proposed 200k/source continuous-current observer.

EasyDMA array lists are linear adjacent fixed-size buffers, not descriptors
that specify arbitrary addresses and not a circular-buffer mechanism. The
SDK exposes `RXD.LIST`, `TXD.LIST`, 16-bit MAXCNT and `SHORTS.END_START`.
An eventual high-rate backend must bound the transfer count, stop/re-prime the
ADC channel pipeline at a deliberate boundary, and prevent accesses beyond the
allocated array. A repeated START or END_START shortcut alone does not satisfy
these requirements. EasyDMA pointers must refer to accessible RAM, not flash;
AMOUNT and END must be checked before consuming data. [Nordic EasyDMA](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/easydma.html).

Unlike the historical 32-bit capacity proposal, this slower backend selects
ADS8688 SDO format **001** and clocks five bytes (40 clocks) per frame. It can
compare the actual four-bit channel address following the 16-bit conversion
result with the expected command-pipeline channel. The first two result bytes
precede conversion data; result bytes 2/3 contain the code and the upper nibble
of byte 4 contains the four-bit channel address. Feature Select register 0x03
is written/read back as 0x01; range registers 0x05…0x0c are 0x06 for 0…5.12 V.
Mode 1 launches SDI on rising edges and lets the ADC sample it on falling edges.
The MCU samples MISO on that falling edge with RXDELAY explicitly zero, before
the ADC changes SDO after its minimum 10 ns hold. The nrfx default RXDELAY 2
(31.25 ns) can instead sample the next SDO bit and invalidate this byte alignment. Matching this tag improves channel
identity evidence, while it does not detect every corrupted code or prove the
ADC reference or observed signal. [TI ADS8688 datasheet, Tables 13–14](https://www.ti.com/lit/ds/symlink/ads8688.pdf).
The 15 kHz typical analog bandwidth, unearned phase-charge precision and
short-transient limitations remain those of the
[transport review](transport-component-review.md).

The RHD commissioning profile retains sixteen streams with a nominal **1 ms
frame** and nineteen SPI words, each with at least an 8 us allocated slot.
Actual poll/aperture timestamps and frame-validity checks retain jitter and
missing history; these are not a physical 1 kHz uniform-rate qualification.
Its selected 20…300 Hz analog settings use registers 8…13 = **6,9,2,11,54,0**.
Register 4 = **0x40** selects signed two's complement for amplifier channels
and disables the optional DSP filter. The ADC supply channel remains unsigned.
A 9 ms fast-settle interval exceeds the manufacturer's 2.5/300 s recommendation;
the subsequent 10 ms discarded interval is a project heuristic, not proof of
analog or neural recovery. [Intan RHD2000 datasheet, register 4 and bandwidth
tables](https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf).

## Request cutoff and reset behavior

The nRF5340 application core has 32 DPPI channels, eight GPIOTE channels and
six capture/compare registers per TIMER0/1/2. One TIMER0 CC2 compare can publish
through an SDK-allocated DPPI connection subscribed by two GPIOTE CLR tasks and
TIMER0 CAPTURE1. The shared allocator avoids the connection already reserved by
the UART driver's enhanced polling-TX support. Allocation failure inhibits
startup; a fixed channel number is not assumed.
The compare IRQ only records this capture for the main owner of policy state. Requests must
be raised and cleared using GPIOTE tasks once it owns those pins: writing the
ordinary GPIO OUT register then has no effect. Configure an initial low state
before enabling the subscriptions. Interrupt or software stalls do not remove
the native external duration/watchdog/guard authority. [Nordic DPPI](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/dppi.html),
[GPIOTE](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/gpiote.html),
[TIMER](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/timer.html).

One common CNV GPIO fans out to both ADS8866 CNV pins, matching the simultaneous
requested-aperture contract; independent CS controls still serialize their
results. One common driver REARM GPIO fans out to the two driver rearm inputs.
These are explicit carrier joins, not hidden alternate pin functions. Both
sources must be idle and qualified before that common edge. Monitor rearm,
phase-supervisor rearm, router rearm, supervisor rearm and fault reset remain
separate outputs with their separate protocol meanings. Integration controls
retain an unknown interrupted integrator history; only independently qualified
quiet/recovery can authorize a reset. A processor power reset cannot preserve
an analog dose history that was physically erased or lost.

Production Revision 1 anomaly 135 can suppress SPIM4 output if the CPU sleeps
between enabling and starting it. The installed nrfx SPIM driver applies the
manufacturer's workaround around enable/disable. The backend uses the installed nrfx SPIM driver and retains its
revision-appropriate handling. [Nordic anomaly 135](https://docs.nordicsemi.com/r/bundle/errata_nrf5340_rev1/page/err/nrf5340/rev1/latest/anomaly_340_135.html).
Engineering A is excluded: it has unrelated nonfunctional SPI instances and
must not be treated as the production witness.

## Explicit new carrier sideband dependency

The frozen router exposes **eight parallel active Q outputs** on J6. Its
`ROUTE_SHIFT_TAIL` is candidate shift-register data and cannot verify the
active route. Directly connecting all required control and observation lines
would exceed the SoC's 48 GPIO. The proposed carrier therefore adds **four
SN74LVC165APWR**, operated at HOST_3V3 with 100 nF local bypass per device.
These parts are an explicit next-PCB dependency. They are not present in the
seven earlier native packages and their addition does not establish native
ERC or board routing evidence yet.

Each TSSOP device uses SH/LD pin 1, CLK pin 2, CLK INH pin 15 tied low, VCC pin
16 and GND pin 8. Standard QH pin 9 of the nearest device drives P1.15; the
next device's QH feeds the nearer device's SER pin 10. The farthest SER is tied
low. Inverted QH pin 7 is unused. All four SH/LD pins share P1.14 and CLK pins
share P0.29. With load low, inputs load asynchronously; on release high, read
QH before the first rising clock and then shift toward the MCU. Wire parallel
H/G/F/E/D/C/B/A, pins 6/5/4/3/14/13/12/11, to ascending sample bits. This
specifies the physical chain order rather than assuming an SPI bit order.
[TI SN74LVC165A, SCLSA16, pin table and functional modes](https://www.ti.com/lit/gpn/sn74lvc165a).

| Sample bits | Actual observation / hardwired pattern |
|---|---|
| 0…3 | Router J6 pins 1…4: CH0 active address bits 0…3 |
| 4…7 | Router J6 pins 5…8: CH1 active address bits 0…3 |
| 8,9,10,11 | RESET_READY, RAILS_QUALIFIED, WATCHDOG_OK, AFE_ISOLATED_READY |
| 12,13 | CH0_QUIESCENT_OK, CH1_QUIESCENT_OK |
| 14,15 | MON0_PERMIT, MON1_PERMIT |
| 16,17,18 | PWR_FAULT_N, SUP_ARMED, GLOBAL_GUARD_EN |
| 19,20 | CH0_RUN, CH1_RUN |
| 21,22 | CH0_TIMER, CH1_TIMER |
| 23 | ROUTE_COMMAND_READY |
| 24,25 | CH0_TIMEOUT, CH1_TIMEOUT |
| 26…31 | Fixed ascending bits 1,0,0,1,0,1: `(word & 0xfc000000) == 0xa4000000` |

The sentinel rejects an unconnected pull-down, all-zero or all-one serial
stream. It does not authenticate observations or detect every stuck, delayed
or miswired bit. Health is a simultaneous parallel-load snapshot with explicit
age, not a continuous event record. Independent native analog guards must
remain connected directly; serialized observations never replace them.

DAC80502 samples DIN on falling SCLK edges, so SPI3 uses **mode 1**, with
SYNC high during all route/sideband traffic. ADS8866 launches the next DOUT
bit on falling SCLK edges; its preloaded first bit is read using **mode 0**
on the preceding rising edge. [TI DAC80502 pin table and SPI timing](https://www.ti.com/lit/ds/symlink/dac80502.pdf),
[TI ADS8866 four-wire interface](https://www.ti.com/lit/ds/symlink/ads8866.pdf).

SPI3 DAC traffic also shifts the router candidate and sideband chain. It does
not clock the route preload latch or active commit. Always shift the complete
new route immediately before its dedicated preload pulse, then commit, read
all eight active bits, compare, acknowledge and rearm. Sideband read clocks
likewise change candidate data; they must never be followed by a preload pulse
that assumes old candidate contents. Disable SPIM3 and restore GPIO ownership
before sideband bit-banging; hold DAC SYNC high and route preload/commit low.
A single owner serializes these transactions.

The chosen device supports 1.1…3.6 V operation and 5.5 V-tolerant inputs;
standard QH at host supply drives only a low-current MCU input. A software
1 us half-clock/load guard comfortably exceeds the tabulated logic timing
under stated test conditions, while real carrier loading/edges remain
unmeasured. Four devices have a combined 160 uA maximum static-current figure
under the datasheet's 3.6 V rail/input condition. Its 17 pF CPD is typical, so
an estimated dynamic allowance is not a guaranteed maximum. Their bypass,
pulls, clock fanout and power must enter the consolidated PCB budget.

## Reviewed installed identities

The SDK copy is `E:/SCCI_RH-Nordic/ncs/v3.4.1`; no vendor file was edited. Its
`nrf` commit is `b20f8619ba9a5530f8c34b0a130d829947cfe55d`, and the
`modules/hal/nordic` commit is `69865c20dc4afbdd27060ad1e81af1b62d31f7af`.
The following SHA-256 values identify the reviewed local primary sources
(relative to the installed nrfx directory).

| File | SHA-256 |
|---|---|
| `bsp/stable/mdk/nrf5340_application_peripherals.h` | e6b515cab3b5ead433894893b81402b779cacedaabf8ccd56891d30b89e13794 |
| `bsp/stable/mdk/nrf5340_application_bitfields.h` | 35d04825caadff516b06c0a7d5af2d886565aba33e31908d9c49a8deac2667a6 |
| `bsp/stable/soc/nrfx_mdk_fixups.h` | b54a5f0a3ab5e54e309e357c41bddd05ba352211baeddecf0ade2d6794549cb7 |
| `bsp/stable/mdk/nrf53_erratas.h` | 1c0ff1c7a9303b116404cdbdeab65bfbcb4483fd6c06c3ac02beb0c546dd2918 |
| `drivers/src/nrfx_spim.c` | a9e7ad334ddfb757bf95ff834da0585c713efa4445510f76d248b07385436b82 |
| `hal/nrf_spim.h` | 6c438fe6aee3a5d2508fbc27e6b0bbaff92555c2af367c63eb1daa9e66360e7f |
| `hal/nrf_gpio.h` | 79c313ee754363f8a1b7f2fb19e430ee664388a8fdb63150d5584aad02e0f08b |
| SDK `zephyr/dts/bindings/arm/nordic,nrf-uicr.yaml` | e601cca47d9e56cd5729521266a37c1b08b3f22a23450596ddb59509f950ba19 |
| SDK `zephyr/modules/hal_nordic/nrfx/CMakeLists.txt` | 6e0902cfd192276baa5edd7f5ff76f9a222d4e89d58d9875f88dcc0c7ec8e51a |
| SDK `modules/hal/nordic/nrfx/bsp/stable/mdk/system_nrf5340_application.c` | 536453b65ee6ff16d58a8581ba305cbfcc0d99077e7de7aef40143d27ea0f365 |
| TI SN74LVC165A SCLSA16 PDF | cc3d7f3ea4a5d9f864da60f876883f45cf735b882bc5a3fcef87159c69abfe7e |

These are source and design-review identities. The actual ELF/source receipts,
link map and tests establish the completed firmware package's narrower
execution evidence. Physical timing, sensor truth, signal quality, radio,
security authentication and biological efficacy are separate boundaries.
