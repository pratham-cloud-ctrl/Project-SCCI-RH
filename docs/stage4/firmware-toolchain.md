# Target firmware tools

**14 October update:** the [actual SCCI_RH application](../../firmware/nrf5340/README.md)
now compiles and links for the application core. Its
[build receipt](../../provenance/stage4-nrf5340-build.json),
[independent audit](../../provenance/stage4-nrf5340-verification.json) and
[implementation review](nrf5340-firmware-design.md) supersede the readiness-only
status below. The older smoke receipt is preserved as a separate historical
tool-installation check; it is not the SCCI_RH image.

12 October 2026. **SDK installed and unmodified application-core example
successfully cross-compiled and linked.** This is a tool-readiness record.
The full SCCI_RH processor backend remains unimplemented.

The Stage 2 processor witness is nRF5340. Its native firmware work needs a
supported Arm compiler, Nordic/Zephyr headers, build tools and a linked target
image. The existing portable C tests execute on the host and do not provide
those results.

## Selection and observed installation

The official stable release selected is
[nRF Connect SDK v3.4.1](https://github.com/nrfconnect/sdk-nrf/releases/tag/v3.4.1).
Nordic's SDK manager reports its matching toolchain bundle as `4f5b6ad6dd`.
The supported [SDK-manager installer](https://docs.nordicsemi.com/r/bundle/nrfutil/page/nrfutil-sdk-manager/guides/sdk_manager_installing.html/basic-usage)
installs both SDK and toolchain. This project needs no paid IDE or physical
development board to cross-compile its digital artifacts.

Observed checks:

- Official nRF Util executable: **8.2.1**; Windows Authenticode signature valid,
  signer **Nordic Semiconductor**.
- Download SHA256: `22cb1bd03fc29016670c1fc8408a78bd213286ecc1156c70712485d77b097c75`.
- Installed SDK-manager command: **1.16.1**.
- Matching toolchain installed; its compiler responds as
  **arm-zephyr-eabi-gcc 14.3.0 (Zephyr SDK 1.0.1)**.
- SDK source installation completed. The unmodified `hello_world` example
  compiled and linked for **nrf5340dk/nrf5340/cpuapp**. All 172 build steps passed.
- Observed tools: **west 1.5.0**, **CMake 4.2.1**, **Ninja 1.13.2**.
- The [build receipt](../../provenance/stage4-nordic-toolchain-smoke.json) binds
  the actual command, source and ELF hashes, tool versions and section sizes.
  The example's linker reports 24,856 B flash and 6,048 B RAM. These are example
  sizes, not SCCI_RH firmware resource evidence.

The original installer, manager metadata and installation physically reside in
`E:\project workspace assests\Firmware\Nordic`. Nordic/Zephyr
[application paths cannot contain spaces](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/app_dev/create_application.html),
so local junctions initially provided short paths:

| Alias | Physical destination |
|---|---|
| `E:\SCCI_RH-Tools` | `E:\project workspace assests\Firmware\Nordic` |
| `E:\SCCI_RH` | `E:\Project SCCI RH` |

The SDK resolves module paths to their physical directory. Generated unquoted
Kconfig module paths then split the asset directory's spaces into arguments;
the first configure failed before compilation. An alias alone did not solve
that documented path restriction, and no usable Windows short filename existed.

A complete, separate copy of SDK `v3.4.1` and toolchain `4f5b6ad6dd` now resides
at **`E:\SCCI_RH-Nordic\ncs`**, a physical path without spaces. The original asset
installation remains intact. The copy included 157,478 SDK files and 47,229
toolchain files, with zero copy failures. It adds approximately 7.3 GiB of local
storage; it is not a project checkout or tracked repository artifact.

The check obtains the official manager environment and rebases only the copied
installation prefix in its child process. Explicit copied Python and compiler
paths, forward-slash CMake Python settings and a pristine build avoid old cache
and registry selections. No vendor source, global PATH, registry setting or
physical device was modified. The project junction still serves the ignored
build directory. Installer logs use the process-local
`NRFUTIL_HOME=E:\SCCI_RH-Tools\nrfutil-home` setting.

The completed original installation used:

```powershell
$env:NRFUTIL_HOME='E:\SCCI_RH-Tools\nrfutil-home'
& E:\SCCI_RH-Tools\nrfutil.exe sdk-manager install v3.4.1 --install-dir E:\SCCI_RH-Tools\ncs
```

## Repeat the build check

Run the [example cross-compilation check](../../scripts/check_nordic_toolchain.py)
after the documented original installation and short physical copy are present:

```powershell
.\.venv\Scripts\python.exe scripts\check_nordic_toolchain.py
```

It builds the **unmodified SDK hello_world** example for
`nrf5340dk/nrf5340/cpuapp` in an ignored project build directory. It records tool
versions, source/ELF identities and section sizes only after successful linking.
Its build log stays under `tmp/nordic-toolchain-check`. The command performs no
flashing or physical execution.

The passing result establishes the installation's basic build path. It does not
close SCCI_RH firmware integration, application/network memory budgets, ADC/DMA/bus
arbitration, timer/DPPI timing, delivered-charge observation or fault shutdown.
Those require the actual SCCI_RH backend and their own verification artifacts.
