# Integrated digital path: methods, results and evidence boundary

**16 October 2026. A finite host integration replay; no physical experiment.**

Project SCCI RH proposes implanted spinal acquisition, individualized computation,
selective stimulation and observed feedback. The motor branch concerns expert-
informed practice followed by stimulation-OFF assessment; the physiological
branch concerns externally observed pressure and a target-specific pressor
pathway. AstroSam's Mind-Link inspires the progression from a future interface
premise to inspectable engineering. It supplies no biological validation for SCCI_RH.

The executable [Stage 6 replay](../../scripts/stage6/verify_digital_path.py)
connects both conditional application policies to the **unchanged production C
runtime** used by the nRF5340 target. It also reuses the existing independent
supervisor state equations and checks the exact 36-port mechanical/electrical
bridge. All Stage 1–5 sources and their earlier results remain unchanged.

## What is actually joined

| Boundary | Executed here | What remains a premise or separate artifact |
|---|---|---|
| Spinal observation to learner state | Causal synthetic abstract features, Stage 3 feature mixing/decoder calibration, independent noise-free OFF-probe movement measurements | Useful human neural code; electrode voltage to these abstract features; artifact-free simultaneous recording during assistance |
| Observation validity | New companion adapter rejects stale, future, nonfinite or invalid features; production C checks raw-monitor identity and pressure packet support, CRC, epoch and sequence | The 50 ms abstract-feature age rule is a new companion assumption; raw-monitor identity is not neural validity |
| Policy to event | Learner-specific gain estimate and task-space reference, or bounded pressure feedback, become explicit two-source plans | Selected contact/recruitment directions and amplitude-to-response law need individual calibration |
| Local event admission | Actual compiled production C source checks mode/lease, route commit and active-address readback, 3,000 µA/200 µs envelope, phase sequencing and OFF trials | Synthetic input observations stand in for GPIO/SPIM/ADC; compiled output requests are not measured current |
| Independent shutdown | Unchanged Stage 4 ideal Supervisor model rejects stuck request, guard fault and monitor-permit loss | Gate propagation, analog delays, true switch position, physical timer and common-cause qualification remain separate |
| Body response and learning | Declared activation/recruitment/pressure response adapters use only completed host event requests; OFF evaluation follows modeled washout | A completed request does not prove delivery, recruitment, plasticity or a successful bodily response |
| Electrical boundary to mechanical port | All 36 source-bound identities checked; contacts and two returns terminate at supervision J50101 after guards | No physical continuity or tissue test |

The replay is a **contract-level integration demonstration with explicitly
conditional adapters**. It is not a transistor/field/tissue cosimulation or an
execution of the eight boards, CAD assembly and target binary together.

### A consequential current target limit

The real [backend source](../../firmware/nrf5340/app/src/scci_rh_backend.c) records
RHD frames only in OBSERVE. It inhibits recording while stimulation is armed.
Its 16 features are integer absolute-value EMAs in ADC counts; telemetry marks
`analog_qualified=0` and clears the transport mask outside OBSERVE or after
100 ms without an update. The EMA retains its original support time.

Those unsigned EMA features cannot silently become this replay's calibrated
signed abstract phase features. The current target therefore does **not**
implement continuous live spinal-feature feedback during MOTOR. It implements
the local event executor and observed digital safeguards; the future simultaneous
recording/decoding mechanism is a separately declared extension. Pre-session
OBSERVE/calibration and subsequent externally timed motor plans remain compatible
with the implemented mode separation.

The core's accepted initial raw-monitor sample is an identity/configuration
condition; it does not impose a continuing neural freshness deadline. The new
companion's explicit feature gate supplies that assumption in this replay.

## Execution method

Python builds the unchanged `scci_rh_runtime.c` and its header into a temporary
host shared library, with warnings treated as errors. A narrow
[bridge](../../scripts/stage6/runtime_bridge.c) calls only public runtime APIs
and reads selected output/state fields. It does not alter private runtime state
to force successful admission. The library is discarded after use.

Each bounded motor drill begins with inhibited initialization, configuration
readback, one known synthetic raw-monitor conversion, explicit pre-monitor
recovery, observed monitor permits and a separate final rearm. Plans then require
route commit, active-address comparison, acknowledgement and route rearm. Each
phase separately requires rearm consumption and observed readiness. First phase,
zero-request gap, opposite second phase and idle recovery are checked at exact
host-model timestamps. These timestamps are inputs to a host execution, not
measured nRF5340 interrupt latency.

The illustrative event adapter uses a 40 Hz train, at most 3,000 µA, 200 µs per
phase and a 200 µs gap. A signed task correction selects one of separately
proposed positive/negative recruitment directions: contact indices 2/3 for
source 0 and 9/10 for source 1. Electrical polarity reverses for balancing; it
does not encode a proven excitatory/inhibitory biological direction.

The amplitude relation `abs(normalized command) × 3000 µA` is an **unmeasured
calibration premise selected for this replay**. A 3,000 µA, 40 Hz train is assigned
one normalized recruitment unit. No historical simulation, driver calculation
or compiled request earns that tissue-response relation. The script reports the
relation explicitly and never describes the request as measured delivered dose.

### Motor response and OFF assessment

The replay reuses the Stage 3 seed, learner calibration, mixing, decoder,
task basis, gain estimate and transparent learning identity. It is a **new
coarser model**, with 25 ms steps, a 50 ms delayed-response queue and a 40 ms
activation constant; it is not a rerun of the 5 ms/35 ms Stage 3 scenario.
Observed synthetic neural features come from the preceding frame. The policy
uses the calibrated decoder and independently measured OFF-probe template,
never the private learner coefficients or future achieved movement.

There are 24 separate initialized two-second drills per arm, each with a common
one-second OFF probe and two-second washout. Host time advances through those
intervals. Initial calibration cost is inherited from the illustrative Stage 3
premise and is not used to claim a human training-time multiplier. This compact
replay uses one seed and noise-free probe measurements to isolate integration;
the broader Stage 3 study retains its noise, null and adverse comparisons.

Only a completed two-phase C request supplies a normalized input to the assumed
response model. Queued response is flushed and the remaining activation decays
before OFF scoring; the unrounded residual is checked below 1e-18. The learning
identity is `Δθ = η[θ*−θ + (ρ−1) projection(response)]`. The favorable, neutral and
adverse teaching coefficients are selected hypotheses, not fitted measurements.
Retention is an explicitly assumed 0.95 fraction of acquired coefficients.

### Physiological response

A separate 60-second pressure surrogate uses one causal external SBP packet per
second, a 250 ms companion P-policy update and an explicit 40 Hz event train.
The value retains the preceding model frame's 250 ms old support; it is not
retagged as newly measured. The same actual C packet parser checks it before
local pressure-event admission. Synthetic pressure response has a selected
30 mmHg full-scale gain, 1.5 s activation and 6 s response constants. A 20 mmHg
deficit acts from 10 to 40 seconds.

The policy receives only the last accepted external pressure value; it does not
read private plant coefficients or future state. It has nonnegative pressor
authority and a unit cap. Withdrawal supplies no active depressor action.
Optional spinal recruitment/context sensing is not inserted as a pressure
measurement. This simple replay has no clinical parameter fit or outcome claim.

## Reproduced results

The [summary](../../results/stage6/integration-summary.json) and
[detailed result](../../results/stage6/digital-path-verification.json) report
**114,426 software assertions across 28 scenario groups**, including repeated
per-event state checks. That assertion count is not a count of independent
scientific findings. All 5,184 active motor events and 1,200 pressure events
complete two host-executed phases under the selected nominal observations.

| Motor arm | First-practice ON error, mm | Final retained OFF error, mm |
|---|---:|---:|
| Unassisted | 31.414 | 5.605 |
| Identical assistance, neutral teaching (`ρ=1`) | 16.668 | 5.605 |
| Identical assistance, favorable teaching (`ρ=2`) | 16.668 | 2.897 |
| Assistance, adverse teaching (`ρ=−1`) | 16.668 | 34.845 |

ON assistance and favorable assumed teaching can coexist with retained benefit
in this model. Equal OFF outcomes under neutral teaching and worse OFF outcomes
under adverse teaching remain visible. No expert skill transfer, unique spinal
information advantage or healthy acquisition-speed estimate is established.

During the selected pressure deficit, model RMSE is **11.871 mmHg**, compared
with 20 mmHg without pressor input. After the deficit ends, modeled pressure
peaks at **129.999 mmHg** against a 120 mmHg target. The overshoot is retained:
lower disturbed-period error alone does not establish an acceptable controller.

### Fault and boundary results

Thirteen production-core scenarios check invalid raw identity, stale SBP, CRC
corruption, SBP replay, pressure-packet loss, companion lease loss, mismatched
active-route readback, excessive amplitude, shared-contact conflict, OFF trial,
independent inhibit during a phase, late phase termination and restored health
without automatic rearm. Each rejected case leaves output request and desired
source masks zero; sticky faults leave the core disarmed. OFF trials retain
event identity while making no output request.

Four separate independent-supervisor scenarios exercise a normal phase, stuck
host request, guard fault and monitor-permit loss. The existing ideal hardware
model removes terminal permission even where host request remains high; no
physical opening delay is earned. Six companion feature cases exercise fresh,
stale, future-support, future-arrival, invalid/artifact and nonfinite data.

The port trace maps contact index 2 to `STIM_03 / P21 / J50101 pin 3`, source-0
return to `P35 / pin 17`, and source-1 return to `P36 / pin 18`. Recording starts
at `P01 / J30003 pin 1`. `P18 / BIAS_CONTACT` remains a recording-bias port and
cannot be substituted for a stimulation return. All body-facing stimulation
identities remain **after independent output guards**, rather than at the raw
router connector. Native source/electrical/mechanical audits establish their
saved design consistency; the replay does not measure physical conduction.

## Reproduction and finite closure

From the repository root:

```text
python scripts/stage6/verify_digital_path.py
```

Dependencies are Python, NumPy and a C11 host compiler. `CC` can select a compiler;
GCC/Clang are found on the normal path and the documented local Zig installation
is a Windows fallback. No FreeCAD, KiCad, Nordic SDK or internet connection is
required for this finite replay. `--write-results` explicitly regenerates only
the Stage 6 result files. Default execution is read-only, replays the code,
checks LF-normalized source hashes and compares all saved integer/hash values
exactly and floats rounded to ten decimal places.

The [requirements/claims trace](requirements-claims-trace.csv) covers all 36
original requirements without editing their historical statuses. It marks
physical, biological, authentication and thermal conditions as unresolved where
the original wording exceeds the digital deliverable. This package closes a
finite integration account; those empirical conditions are future research or
implementation work, not reasons to restart an unbounded qualification loop.
