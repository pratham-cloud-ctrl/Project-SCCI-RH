# Independent shutdown: finite circuit and control studies

**14 October 2026 — digital engineering package for Project SCCI RH.**

These studies connect the [native supervision circuit](../supervision/README.md)
to the existing monitor, restricted driver, contact router and recording front
end. They support the complete SCCI concept: record spinal activity, interpret
task-relevant information, admit personalized stimulation, observe delivery and
adjust a target-specific policy. They add no biological efficacy result.

## What is implemented

The hardware has a second phase one-shot for each source, a separate heartbeat
watchdog, measured rail/current/pair-voltage windows, observed local recording
commands and 17 RHD-side pin windows. Five quad switches provide **18 protected
body-facing disconnect paths after the existing router and monitor**. Sticky
global/source interlocks require explicit rearming; restored health cannot clock
the system back into operation. The [control contract](../../../docs/stage4/supervision-control-contract.md)
and [102-wire integration plan](../../../docs/stage4/supervision-wiring.csv)
state the actual package/pin connections.

The pre-monitor `MON_SUP_OK` signals deliberately differ from the arm-qualified
driver `EXT_SUP_OK` signals. The historical monitor and driver use the same label
for these external ports, but joining them would create a startup dependency
loop. The integration auditor verifies their separation and floating AFE ground.

## Analog evidence and assumptions

[analog-results.json](analog-results.json) records nine rail windows, two initial
comparator groups, 16,384 difference-amplifier corners, 1,024 recording-observer
corners, passive loading, three RC hold groups and seven interrupted-load cases.
[analog-traces.npz](analog-traces.npz) contains 2,961 trajectory points. This is
a scalar/KCL/closed-form study, without a nonlinear vendor semiconductor model.

| Result | Meaning and boundary |
|---|---|
| Secondary phase timer: 250.112 µs nominal; 238.868–261.378 µs arithmetic interval | Separate oscillator and timing resistor; 264 µs is the explicitly conservative model envelope. Does not cover simultaneous stuck timers or common-cause faults. |
| Watchdog: 170/200/230 ms | Detects a missed falling heartbeat edge. It cannot serve as a microsecond phase limiter. Fresh heartbeat and explicit rearm are separate. |
| Quiet window: nominal ±250 µA; chosen-corner accepted union about ±494 µA | Uses the real `2.048 V + 40 V/A × I` monitor transfer, ±6 mV comparator offset and ±600 µV threshold-buffer allowance. It is a bounded observation, not exact zero current. |
| Internal pair-voltage accepted union about −22.26 to +22.34 V | Includes four-resistor mismatch and common-mode conversion. Measured before router/shunt/terminal guards; their drops and dynamic saturation remain separate. |
| Recording blank accepted union about ±264 mV at each observed pin | Below ±400 mV DC under chosen bounds. Neither small-signal linearity nor actual switch position/recovery is proved. |
| Probe loading: about 7.80 mV positive-input and 2.19 mV shared-reference DC shifts in nominal fixtures | Each probe adds about 0.313 µA. A 1 MΩ source witness shifts about 264 mV; sensing is not free. |
| Quiet RC rise: about 16.3–87.7 µs under declared assumptions | Actual 1% resistor/5% capacitor. Schmitt thresholds are an assumed bracket, not an exact 3.3 V manufacturer guarantee. |
| Startup hold minimum: about 1.77 ms cold; 1.14 ms from ≤0.6 V | Actual 1% resistor/10% capacitor, assumed threshold/leakage/reset conditions. Some corners never release, which inhibits operation; a finite universal ready deadline is unearned. |

The AFE nominal rails are revised to **+3.45 V, +5.30 V and −5.10 V** while
retaining their historical net labels. This leaves room for monitor tolerances
and the selected devices' supply limits. The next power package must generate
and budget these supplies. Reference accuracy, gain and selected offset/leakage
allowances are explicit model conditions, not measured finished-circuit values.
The shared reference can fail plausibly without a separate reference-window flag.

![Threshold envelopes](figures/threshold-envelopes.png)

The interrupted-load fixture is an **artificial 1 kΩ parallel 2 µF load** driven
by an ideal regulated 3 mA source. Guard opening/closing each assumes 5 µs;
fault observation assumes 20 µs. These assembled-circuit delays are allocations,
not guaranteed manufacturer worst-case limits. Opening the external path does
not remove charge/energy already stored in the load. Current can continue inside
the load while the external shunt reads zero.

The welded-driver/guard witness ends at **5 ms with current still flowing**.
It does not invent a later shutdown. Edge injection is a separate assumed
300 pC per contact edge; open-switch leakage and sustained external fault sources
remain explicit. These models do not earn the earlier 4% dose target.

![Shutdown and residual energy](figures/shutdown-and-residual.png)

## Reproduce and audit

Run these from the repository root; their defaults are read-only:

```text
python electronics/stage4/supervision/verify_supervision.py
python electronics/stage4/supervision-study/control_study.py --check
python electronics/stage4/supervision-study/analog_study.py
python electronics/stage4/supervision-study/verify_analog.py
python electronics/stage4/supervision-study/verify_integration.py
```

The analog replay uses the producer again. The separate analog auditor imports
no producer code: it independently solves divider/probe/difference-amplifier KCL,
charge balance, RC hold timing and all saved load trajectories. Its saved
[receipt](analog-verification.json) records **6,079 checks**. The
[integration receipt](integration-verification.json) checks all 102 planned wires
against both saved XML and pin manifests, terminal-switch direction, actual
RHD pin taps, critical values and ground/permission separation.

Regeneration requires explicit `--write-results`, `--write-receipt` or
`--write-figures` as supported by the individual scripts. Saved artifacts retain
source identities. Full consolidated hierarchy, target firmware, routed PCB,
populated CAD and physical performance are subsequent packages.
