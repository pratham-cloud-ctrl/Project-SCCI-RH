# Independent supervision: connected control and observation contract

**14 October 2026. Native digital artificial-load design; restricted 24 V source domain.**

This package connects independent request-duration limits and a heartbeat watchdog
to rail/current/internal-terminal observations, recording-pin voltage windows,
the existing driver and monitor permissions, and eighteen terminal guards.
It advances Stage 4 of SCCI_RH's record–interpret–stimulate–observe architecture.
The proposed expert-informed motor learning and function-specific physiological
responses remain the conditional Stage 3 research mechanisms. None of the finite
checks below reports an implanted experiment or biological efficacy.

The native design is [supervision](../../electronics/stage4/supervision/).
The executable [control study](../../electronics/stage4/supervision-study/control_study.py)
checks actual exported KiCad XML pin nets and package gate pins independently of
the circuit generator, then reproduces ideal event histories. Its saved
[results](../../electronics/stage4/supervision-study/control-results.json) are
read-only by default. The adjacent `analog-results.json` is authoritative for the
selected finite resistor/comparator/RC/guard assumptions and retained failures.

## Distinct observations and interfaces

| Signal or connection | What it establishes within the declared circuit assumptions |
|---|---|
| Raw `CHx_REQUEST` | Command intent. It directly triggers the separate secondary LTC6993-1; no readiness gate creates a new timer edge. |
| `CHx_RUN` and `CHx_ROUTE_LOCKED` | Existing driver and router command status. Neither is a measured current or actual mux-position readback. |
| `CHx_I_MON`, `MON_VMID`, `MON_VREF` | Existing signed INA241 current observation and its references. Quiescence is a separate measured window with a dwell network, rather than an inference from low REQUEST/RUN. |
| `CHx_PAIR_OK` | Window around an OPA2192 differential measurement of internal driver `A_BR minus B_BR`. This is not the voltage across tissue after the router, shunt and guards. |
| `AFE_BLANK_OBS_OK` | All seventeen actual RHD-side pin windows, local CONNECT low, ACQUIRE low and local valid rails/startup, crossing the isolation barrier through a default-low receiver. This is more evidence than host command status; it still does not prove every switch physically open. |
| `SENSE_HEALTH` / `CHx_MON_SUP_OK` | Physical-observation/watchdog prerequisites before monitor permission or supervisory ARM. Feed the old monitor's externally named `EXT_SUP_OK` from these **pre-MON** outputs. |
| `CHx_EXT_SUP_OK` | RAW_HEALTH plus supervisory ARM and no source timeout. Feed the old driver's `EXT_SUP_OK` from these **ARM-qualified** outputs. |
| `GLOBAL_GUARD_EN` | Common command for all eighteen body-facing guard paths after the router's canonical eighteen-contact connector. It is not proof of open contacts, zero leakage or removal of stored charge. |

The two old packages use the same printed name `EXT_SUP_OK` for different input
contracts. The integration map deliberately separates them. Tying both to the
new ARM-qualified output would create a startup deadlock: the old monitor cannot
rearm while its external supervision is low, while ARM waits for monitor permit.
The finite study checks the viable ordered startup sequence instead.

Preserve the existing dedicated return shunts: external load return -> guarded
canonical router return -> monitor `RETURN_LOAD` -> 2 ohm shunt -> monitor
`RETURN_DRIVER` -> driver `B_BR`. Recording reference and passive body bias are
separate contacts. Do not bridge `AFEAGND` to the stimulation/host ground.

## Stable equations and actual state elements

`&`, `|`, `!` mean AND, OR, NOT. These are stable valid-supply equations, not
propagation or metastability guarantees.

```text
WD_GOOD = WD_ENOUT_OK & WD_SEEN & HOST_RAILS_OK

SENSE_HEALTH = HOST_RAILS_OK & AFE_BLANK_OBS_OK & WD_GOOD
               & GUARD_FAULT_N & CH0_PAIR_OK & CH1_PAIR_OK
CH0_MON_SUP_OK = CH1_MON_SUP_OK = SENSE_HEALTH
RAW_HEALTH = SENSE_HEALTH & MON0_PERMIT & MON1_PERMIT

NO_ACTIVITY = !REQ0 & !REQ1 & !RUN0 & !RUN1 & !SEC0 & !SEC1
SAFE_IDLE = RAW_HEALTH & QUIET0 & QUIET1 & NO_ACTIVITY
TIMEOUT_CLR_N = !(FAULT_RESET & SAFE_IDLE)
ARM_CLR_N = RAW_HEALTH & !TIMEOUT0 & !TIMEOUT1

U900 SUP_ARMED:
  raw CLK=SUP_REARM; D=SAFE_IDLE; /CLR=ARM_CLR_N; /PRE=1

For each source x:
  U810/U811 TIMEOUT:
    CLK=!SECx; D=TIMEOUTx | REQx; /CLR=TIMEOUT_CLR_N; /PRE=1

  PHASE_HEALTHx = RAW_HEALTH & SUP_ARMED & ROUTE_LOCKEDx
  BLOCK_PRE_Nx = PHASE_HEALTHx & !(SECx & !REQx)
  PHASE_REARM_SAFEx = PHASE_REARMx & PHASE_HEALTHx & QUIETx
                      & !REQx & !RUNx & !SECx
  BLOCK_CLR_Nx = !PHASE_REARM_SAFEx

  U910/U911 BLOCK:
    CLK=0; D=0; /PRE=BLOCK_PRE_Nx; /CLR=BLOCK_CLR_Nx

  ALLOWx = PHASE_HEALTHx & !BLOCKx & !TIMEOUTx & REQx & SECx & RUNx
  EXT_SUP_OKx = RAW_HEALTH & SUP_ARMED & !TIMEOUTx

GLOBAL_GUARD_EN = ALLOW0 | ALLOW1
```

U301 captures the first **falling** raw WDI edge through an inverter. Its D is
`WD_ENOUT_OK`; its asynchronous clear is `WD_ENOUT_OK & HOST_RAILS_OK`. Both
open-drain TPS3431 watchdog/enable-status outputs share the native
`WD_ENOUT_OK` wire. A static healthy-looking output with no first heartbeat
therefore cannot establish WD_SEEN. A watchdog fault clears the seen latch;
output recovery needs a new heartbeat and separate subsequent rearm.

U800/U801 are two distinct LTC6993HS6-1 devices with separate setting resistors.
Their raw trigger pins connect directly to the two REQUESTs. The existing driver
has its own two timer devices; the added timers do not reuse those timer outputs
or firmware timestamps. Both generations still share a part family and can
share power, ground and fault causes.

A normal early request end presets the source BLOCK while SEC is still high.
A second request inside the same interval cannot reopen output. The timer
continues independently. Its later fall with request low retains TIMEOUT=0.
A held-high request at secondary expiry latches TIMEOUT=1 and asynchronously
removes common ARM, inhibiting both sources. Health recovery alone cannot clear
ARM or the consumed per-phase blocks.

The stable BLOCK equations never assert asynchronous preset and clear together.
Transient overlap from skew/slew is outside this Boolean result. `SUP_REARM` is a
raw clock: holding it high while readiness returns does not create a fresh edge.
`PHASE_REARM` is an asynchronous-clear qualification level; release it before
REQUEST and allow the latch/driver controls to settle. Its level behavior must
not be mislabeled raw-clock immunity.

## Ordered admission and recovery

1. Keep both requests, RUN statuses and timers inactive while supplies/startup,
   the recording blank observation and physical sensor windows qualify. Use
   actual qualified outputs; fixed elapsed time alone is insufficient.
2. Establish a fresh falling heartbeat. The pre-MON supervision outputs can now
   become healthy without already requiring MON_PERMIT or ARM.
3. Deliberately rearm each existing monitoring-cell latch. Supervisor rearm does
   not clear those independent monitor latches.
4. With both observed quiet outputs healthy and no REQUEST/RUN/SEC activity,
   pulse **FAULT_RESET**, then release it. This initializes/clears the secondary
   timeout latches. No power-up TIMEOUT value is silently assumed.
5. Issue a separate raw **SUP_REARM** edge, then release it. Commit/read back/
   explicitly rearm the router under its existing contract.
6. Hold the accepted route intent through the two phases and gap. With the
   source observed quiet and its secondary timer low, pulse **PHASE_REARM**,
   release it, perform the existing driver's direction/rearm sequence and only
   then issue a phase request.
7. After interruption, stop both requests; retain integrator endpoints, current
   observations and fault history. Wait for qualified quiet and repeat the
   necessary monitor/fault/supervisor/route/phase admission steps. Do not
   automatically resume or emit a compensating opposite pulse.

FAULT_RESET qualification excludes TIMEOUT and ARM themselves, allowing an
explicit recovery rather than a self-lock. It still requires RAW_HEALTH and both
sources quiet/inactive. A timeout cannot be cleared by SUP_REARM alone or while
its request remains asserted. Clear/reset pulses during active phases are
rejected. Do not reset the charge integrator to erase unknown interrupted dose.

## Timing and threshold boundaries

The secondary timer uses `NDIV=64`, `RSET=195.4 kohm`: nominal
**250.112 microseconds**. The ideal event study uses that nominal width. The
analogue study retains a separate conservative **264 microsecond** maximum
allocation before physical interruption tails. These are not measured gate-to-
load shutdown bounds. The independent heartbeat watchdog has a **170–230 ms**
timeout interval; it cannot replace a microsecond phase limiter or prove correct
firmware execution.

The former 100 microsecond interphase schedule is **unearned** with the selected
quiet-dwell RC, Schmitt thresholds and detector/guard delay allowances. The new
finite healthy schedule allocates **200 microseconds** and still waits actual
QUIESCENT_OK and secondary-low before launching. It is not an automatic timer-
only launch or a proof for arbitrary loads, thresholds or startup corners.
Startup RC qualification can fail closed at selected slow/leakage corners;
there is no earned all-corner release deadline. The event history's illustrative
healthy startup time does not replace that result.

The current-monitor transfer remains
`I_MON = V_MID + (2 ohm x 20) I = V_MID + 40 V/A I`, with nominal 2.048 V midpoint.
The new nominal +/-10 mV quiet window corresponds to **+/-250 microamperes**.
The full-temperature comparator offset allowance is +/-6 mV. Combined selected
corners can accept approximately **+/-494 microamperes**, while the guaranteed
intersection is only about **+/-8.36 microamperes**. It is therefore a finite
quiet setting, not exact zero, a patient-current limit or proof that all current
paths cross the shunt. The final analogue JSON records exact corner values.

The pair sensor's nominal +/-22 V limit uses gain 0.0499 and midpoint 2.048 V.
Selected resistor mismatch/common-mode/offset corners extend acceptance to about
+22.34 V. This measurement is before router/shunt/guard drops and does not prove
physical tissue compliance or observation of guard-side stored voltage.

The seventeen recording-side physical DC windows nominally aim inside +/-0.15 V.
Their selected comparator/bias/resistor corners accept approximately
-0.264 to +0.264 V, inside the RHD +/-0.4 V DC envelope under those assumptions.
That does not qualify its much smaller differential AC linear range. Added
probe bias/loading has a real cost: the illustrative positive-input source sees
about 7.8 mV extra DC at nominal impedance and about 264 mV in the adverse
high-impedance fixture. Keep that result and the previous weak-signal/recovery
limitations; do not credit a window pass as proof of useful spinal recording.

The AFE supply proposal is now nominal +3.45 V, +5.3 V and -5.1 V, with revised
native window dividers. This openly revises the old nominal +3.3/+5/-5 allocation.
Host/isolated converters and a full quantitative power budget remain the next
Stage 4 package. Current sensor, reference and comparator performance always
requires the declared valid rails and component operating conditions.

## Finite checks and retained failure witnesses

The control study checks **58 previous-package physical pin bindings**, all
**1,667 non-NC pins** against native exported XML, **2,048 phase-gate combinations**,
**1,024 reset combinations**, **256 health/startup combinations**, **41 AFE blank
single-fault rows**, six raw-clock/asynchronous-control flip-flop contracts,
two raw timer triggers and all eighteen source/drain/enable guard pad roles.
The independent stable-equation check also examines 1,024 phase combinations
and 1,024 fault-reset combinations. These are distinct finite checks, not counts
of physical tests or claims of exhaustive arbitrary-fault coverage.

Its **18 event scenarios, 46 assertions and 297 snapshots** preserve startup,
biphasic sequencing, repeated requests, stuck primary timer, health loss/recovery,
separate monitor rearm, timeout reset, first-heartbeat evidence, dual-source
interruption and ambiguous request/timer coincidence. Unknown initial timeout,
coincident latch classification and invalid-supply logic remain unknown; they
are not forced to a favorable safe Boolean value.

The preserved witnesses include:

- Dual timer stuck-high faults can defeat the microsecond limit while a healthy
  millisecond heartbeat continues.
- A welded recording switch can remain connected while a ground clamp keeps its
  RHD pin inside the observed DC window. Physical DC observation plus command
  status is not proof of galvanic isolation or every switch open.
- An output guard stuck conducting does not obey its open command. Switch
  leakage/capacitance, observer bypass currents, alternate body paths and stored
  electrode charge do not vanish with GLOBAL_GUARD_EN=0.
- No independent reference-window fault flag is wired into SENSE_HEALTH. Corrupt
  MON_VREF/MON_VMID/current/voltage observation can report healthy values; the
  study retains this witness rather than inventing a reference-health gate.
- Shared supply/ground and rapid power loss can invalidate comparator/timer/latch
  outputs before a qualified warning. Once logic is outside its operating
  range, the event model reports unknown physical state.

The native and finite digital work finishes this inspectable supervisory
checkpoint under explicit assumptions. It does not earn the 4% delivered-dose
allocation, zero current under every fault, arbitrary-fault implant protection,
physical construction, or biological success. Those limitations are recorded
results, not a requirement to reopen Stage 3 or delay the future SCCI concept.
