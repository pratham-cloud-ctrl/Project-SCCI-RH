[Explore](README.md) · [Theory](theory.md) · [CAD](cad.md) · [Electronics](electronics.md) · **Firmware**

# Firmware: what the current processor image actually does

SCCI_RH includes a real, cross-compiled **nRF5340 application-core image for the BT40F carrier**. Its source handles commissioning, requests, observations, routing and faults. The current entry is the [v2.0.1 UART correction](../../firmware/nrf5340/uart-revision/README.md), with a **53,776-byte flash LOAD extent** and **98,000-byte RAM address extent**. The image has been compiled and linked; it has not been flashed or physically executed.

## Follow the implementation

| Layer | Inspect | Responsibility |
|---|---|---|
| Application entry | [main.c](../../firmware/nrf5340/app/src/main.c) | Service peripherals, dispatch companion commands and advance policy |
| Current hardware backend | [revised scci_rh_backend.c](../../firmware/nrf5340/uart-revision/src/scci_rh_backend.c) | Actual SPI/UART/GPIO/timer operations, observations and frame transmission |
| Shared production policy | [scci_rh_runtime.c](../../firmware/nrf5340/core/scci_rh_runtime.c) · [explanation](../../firmware/nrf5340/core/README.md) | Inhibition, leases, routing admission, recovery, OFF trials and faults |
| Target configuration | [revision CMake definition](../../firmware/nrf5340/uart-revision/CMakeLists.txt) · [pin map](../../docs/stage4/nrf5340-pin-map.csv) | Select the current backend and retained carrier/peripheral configuration |
| Target outputs | [ELF](../../firmware/nrf5340/uart-revision/artifacts/scci_rh.elf) · [HEX](../../firmware/nrf5340/uart-revision/artifacts/scci_rh.hex) · [BIN](../../firmware/nrf5340/uart-revision/artifacts/scci_rh.bin) · [link map](../../firmware/nrf5340/uart-revision/artifacts/scci_rh.map) | Inspectable compiled application and its linked allocation |

The revision reuses the original main entry and production core. Older `firmware/nrf5340/artifacts/` and carrier-profile images remain historical checkpoints; use **`uart-revision/artifacts/`** for the current image.

## Read one operating cycle

The processor boots inhibited. It commissions interfaces, validates observations and waits for explicit session, configuration and permission. A trusted wired companion supplies a bounded event plan. The runtime admits it only after the required health, quiet state, route readback and rearm sequence. Timer/DPPI hardware is configured to clear requests at the deadline. Invalid required support, expired permission or a hard trip removes requests and leaves sticky inhibition; a fresh packet does not automatically restart output.

| Mode | Current behavior |
|---|---|
| **OBSERVE** | Sixteen RHD streams at nominal 1 ms opportunities, with timestamps, validity and known polling gaps; stimulation inhibited |
| **MOTOR** | External prequalified motor-event plans; separate OFF trials issue no stimulation requests |
| **PRESSURE** | External prequalified plans with checked, timestamped pressure support |
| **DIAGNOSTIC** | Bounded raw electrical capture; stimulation events not admitted |

**Recording is inhibited while armed.** This image does not decode live spinal activity during stimulation, infer a skill from an expert recording or supply a biological recruitment model. The companion connection is **wired UART, without a radio or network-core image**. CRC detects transmission errors; authentication remains outside this implementation. The [protocol and backend reference](../../firmware/nrf5340/app/README.md) specifies envelopes, commands and telemetry; its UART callback is superseded by the current revision.

## Inspect the correction and reproduce its evidence

The review found that a partially sent diagnostic frame could be interrupted by normal telemetry, corrupting the receiver's envelope. The revised callback retains queue ownership until one complete frame ends. The [actual-callback regression](../../firmware/nrf5340/uart-revision/tests/check_uart_framing.py) compiles that C callback against FIFO/interrupt stubs: **1,172 scenarios pass**, while **334 fail in the preserved historical callback**. These are host tests, not measured UART timing.

Run from the repository root using the [reproduction guide](reviewer-guide.md#reproduce-the-current-engineering):

```text
python firmware/nrf5340/uart-revision/verify_revision.py
python firmware/nrf5340/uart-revision/tests/check_uart_framing.py
python firmware/nrf5340/tests/check_runtime.py
python scripts/stage6/verify_digital_path.py
```

The current image audit has **70 checks**; the unchanged production policy has **75 scenarios and 713 assertions**. The integrated digital-path runner connects that production C core to explicit synthetic movement/pressure models. Body dynamics and current-to-recruitment mapping remain model assumptions; pressure packets exercise the C parser, while motor features enter through the host bridge. See the [current image receipt](../../firmware/nrf5340/uart-revision/verification.json) and [integration evidence](../../results/stage6/digital-path-verification.json).

Rebuilding the ARM image additionally needs the documented Nordic SDK/toolchain: [setup record](../../docs/stage4/firmware-toolchain.md) and [current build helper](../../firmware/nrf5340/uart-revision/build_revision.py). No flash operation is included. Host framing tests require a native C compiler. Neither compilation nor software scenarios establish hardware edge timing, sustained raw throughput, analog precision or retained biological learning.

**Next:** [theory and conditional results](theory.md) · [electronics and native circuits](electronics.md).
