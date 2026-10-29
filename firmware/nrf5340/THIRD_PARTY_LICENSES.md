# Target image attribution

SCCI_RH's original application and policy code use the repository's license. The
linked firmware also includes code from nRF Connect SDK v3.4.1 and its selected
modules; it is not wholly original SCCI_RH code. The complete SDK is installed
separately and is not redistributed in this repository.

| Linked source family | Notice retained here |
|---|---|
| Zephyr kernel and drivers | [Apache 2.0](licenses/Apache-2.0.txt); individual source copyright notices remain in the separately installed SDK |
| Arm CMSIS core support | Apache 2.0, with Arm source copyright notices in the SDK |
| Nordic nrfx drivers | [Nordic BSD 3-Clause notice](licenses/Nordic-nrfx-BSD-3-Clause.txt) |
| Nordic Zephyr HAL integration | [Nordic 5-Clause notice](licenses/Nordic-5-Clause.txt), including its Nordic-device use condition |
| SEGGER RTT debug transport | [Retained source notice](licenses/SEGGER-RTT-notice.txt) |
| Toolchain-selected Picolibc/Newlib C runtime | [Picolibc notices](licenses/COPYING.picolibc) and [Newlib notices](licenses/COPYING.NEWLIB) from the matching SDK's runtime source collection; the build configuration records toolchain runtime selection |

The Arm compiler's runtime support is subject to its own runtime-library license
and exception. See [GCC Runtime Library Exception](https://www.gnu.org/licenses/gcc-exception-3.1.html).
Compiler, SDK and module identities are recorded in the build receipt and
primary-source review. Original third-party source files were not modified.
Build artifacts target Nordic nRF5340; no endorsement by Nordic, Arm, SEGGER
or an educational institution is claimed.
