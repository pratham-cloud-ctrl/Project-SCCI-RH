# BT40F carrier firmware profile

This is the carrier-specific build of the existing SCCI_RH nRF5340 application. The
Fanstel BT40F hardware review specifies internal HFXO load capacitors of **11 pF**;
`bt40f.conf` selects that configuration through `VALUE_X2=22`. The application,
policy core, GPIO map and wired peripheral profile remain the previously reviewed
sources. The original firmware package and its build receipts are preserved.

The saved pristine build used nRF Connect SDK v3.4.1 and the
`nrf5340dk/nrf5340/cpuapp` startup/linker target. This target does not qualify DK
wiring or turn the development kit into the dedicated carrier. Compared with the
original saved configuration, the only configuration keys changed are the HFXO
selection/value and the SDK's `CONFIG_DEPRECATED=y` selection. No application or
policy source was changed for this variant.

| Saved image resource | Independent result |
|---|---:|
| Flash LOAD extent | 53,648 bytes / 1,048,576 bytes |
| RAM address extent | 98,000 bytes / 458,752 linker bytes |
| Physical application-core RAM | 524,288 bytes |
| RAM headroom against linker allocation | More than 20% |

The portable, standard-library-only verifier checks every build source and
artifact binding, the exact configuration delta, the ARM ELF's sections and
linked SCCI_RH functions, Intel HEX checksums and records, ELF/HEX load-byte parity,
and BIN parity including its eight-byte erased-flash gap. It also checks the
original firmware receipt's bindings without changing that package. Verification
is read-only unless explicitly asked to refresh the saved report:

```text
python electronics/stage4/integrated-pcb/firmware-profile/verify_bt40f.py
```

A local rebuild requires the installed Nordic SDK/toolchain and the short-path
junctions recorded by the existing toolchain package:

```text
python electronics/stage4/integrated-pcb/firmware-profile/build_bt40f.py
```

The image was compiled and linked, **not flashed or executed**. Neither compiler
success nor a completed routed PCB demonstrates analog recovery, physical
shutdown timing, sustained sampling rates, biological recording quality or
consumer benefit. The implementation still uses nominal 100 us raw-monitor
opportunities and 1 ms neural frames, with known polling gaps. It does not enable
a radio or network-core image. See the original [firmware scope and operating
limits](../../../../firmware/nrf5340/README.md) and [third-party image licenses](../../../../firmware/nrf5340/THIRD_PARTY_LICENSES.md).

The immutable [build receipt](build-receipt.json) records the October 14 build.
The [independent verification receipt](verification.json) records the October 15
review; it does not retrospectively change that build date.
