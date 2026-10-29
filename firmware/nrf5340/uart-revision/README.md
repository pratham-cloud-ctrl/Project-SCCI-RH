# Current BT40F firmware: UART frame correction

**v2.0.1 review, 17 October 2026.** This additive application corrects a real
companion-wire framing defect found during the whole-project review. It is the
current target firmware entry. The original application and both original
image/receipt sets remain unchanged as historical v2.0.0 evidence.

When the original UART callback had sent only part of a diagnostic raw frame,
new normal telemetry could take queue priority before that raw frame ended.
The receiver then saw bytes from two envelopes interleaved, invalidating their
length/CRC interpretation. A finite host reproducer compiled the actual original
callback and demonstrated that sequence. The correction retains the selected
queue through one complete envelope and applies normal priority between frames.
The pin map, biological policy and circuits are unchanged. Physical timing
remains unmeasured.

The [revised backend](src/scci_rh_backend.c) changes only the UART callback and two
persistent ownership variables. The [application definition](CMakeLists.txt)
reuses the original main entry, production policy core, headers, pin map,
peripheral configuration and device-tree overlay. It also reuses the reviewed
BT40F 11 pF HFXO configuration. No original file is modified.

## Inspectable evidence

- [Actual ARM ELF](artifacts/scci_rh.elf), [HEX](artifacts/scci_rh.hex),
  [binary](artifacts/scci_rh.bin), [link map](artifacts/scci_rh.map),
  [configuration](artifacts/build.config) and [compile records](artifacts/compile-records.json).
- [Exact-source target build receipt](build-receipt.json) and
  [independent load-image audit](verification.json).
- [Actual-callback regression runner](tests/check_uart_framing.py) and
  [reviewed host results](uart-framing-tests.json): **1,172 scenarios pass** in
  the correction; **334 of those scenarios fail** in the historical callback.
  These are finite FIFO/interrupt-stub tests, not physical UART measurements.
- [Project electronics review](../../../docs/review-v2.0.1/electronics-review.md)
  and [native board index](../../../electronics/stage4/integrated-pcb/BOARD_INDEX.md).
- [Retained SDK/image licenses](../THIRD_PARTY_LICENSES.md); this revision uses
  the same reviewed third-party startup, driver and runtime dependencies.

Run from the repository root:

```text
python firmware/nrf5340/uart-revision/verify_revision.py
python firmware/nrf5340/uart-revision/tests/check_uart_framing.py
```

The verifier checks the actual revision source bindings and compile path,
independently parses ELF/HEX/BIN load bytes, confirms the unchanged BT40F
hardware configuration, re-exercises the regression and preserves both
historical firmware receipts. It requires a native C compiler for the finite
host test; GCC, Clang or the existing local Zig installation is supported.
Its default operation is read-only.

The pristine corrected image has a **53,776-byte flash LOAD extent** and a
**98,000-byte RAM address extent**, within its 1 MiB flash and 448 KiB linker
RAM allocations. These values describe the current image. The prior carrier's
53,648-byte flash extent remains unchanged in its historical receipt.

A pristine local target rebuild uses the installed Nordic SDK/toolchain:

```text
python firmware/nrf5340/uart-revision/build_revision.py
```

This compiles and links a separate application image; it never flashes a board.
Changing sources requires an explicit reviewed update of this revision's
receipts. The SDK dependency and short-path setup remain those documented in
the original [toolchain record](../../../docs/stage4/firmware-toolchain.md).

## Unchanged scope and assumptions

This is the eight-board reference carrier's wired commissioning profile. Its
nominal raw-monitor opportunities remain 100 us, and sixteen neural streams
have nominal 1 ms frames in OBSERVE. Polling has documented gaps. RHD recording
remains inhibited while armed; the current image does not decode live spinal
activity during stimulation. The companion supplies prequalified event plans.
There is no radio or network-core image, physical execution, analog recovery
qualification, clinical validation or demonstrated retained biological learning.

Diagnostic raw encoding can still exceed the UART's capacity and fill its bounded
queue. That separate documented overflow removes requests and leaves sticky
inhibition. Preserving frame boundaries does not establish sustainable raw
throughput, hardware timing, current precision or biological usefulness.

The future bidirectional SCCI concept and its two ambitions remain intact:
expert-informed, learner-specific retained motor learning and selected
physiological regulation. Their biological mappings remain explicit assumptions;
the current firmware is an inspectable implementation of part of that concept.
