# Native recording slice and system boundary

This Stage 4 package makes the recording half of SCCI_RH's proposed bidirectional
spinal interface inspectable in native electronics. Eighteen contacts provide
sixteen positive inputs, one shared reference feeding sixteen negative inputs,
and one separately resistance-bounded bias contact. These yield sixteen
differential streams through one multiplexed ADC. Reference/bias contacts are
never stimulation returns. The assumed implanted spinal information and its
learner-specific or physiological interpretation remain the conditional Stage 3
design baseline, rather than new biological results of this circuit.

## Concrete circuit

The [native KiCad package](../../electronics/stage4/recording-front-end/README.md)
contains seven sheets, 151 components and 594 pin assignments: isolated root
interfaces; actual RHD2216 acquisition core; four four-channel input banks;
and shared reference/bias. Local symbols, footprints, BOM, exported connectivity,
reviewed schematic PDF/SVGs and a read-only verifier accompany the sources.

Each recording/reference path is `contact -> 4.99 kohm -> TMUX7412F protected S
-> internal D node with 10 Mohm bleeder -> TMUX6219 ground/record selector ->
RHD input`. Sixteen positive pins have 470 pF C0G shunt capacitors; the shared
reference has 2.2 nF. Five production **TMUX7412FRRPR** WQFN parts supply seventeen
used paths; unused paths are grounded and disabled. The datasheet's preview
TSSOP package is not used as an available production component.

The RHD and local switches occupy **AFEAGND**, separate from **HOSTGND**.
External isolated supplies are named AFE_P5, AFE_N5 and AFE_3V3. No power converter
is implemented here. AFE_P5 must actually remain at or above 5.0 V and the bipolar
span within the fault-switch operating range; a negative tolerance on a nominal
+5 V source is insufficient. RHD itself requires 3.2-3.6 V. Component isolation
ratings do not qualify assembled insulation, tissue paths or implant leakage.

With qualified rails, default-LOW mode commands disconnect the fault switches
and ground the RHD inputs. CONNECT_HIGH alone reconnects protected nodes while
the RHD stays grounded. CONNECT_HIGH AND RECORD_HIGH selects recording.
Fault flags report large source overvoltage, not the RHD's small pin envelope.
Stable-state logic does not qualify asynchronous transitions or detect a powered
host frozen high. Sudden link loss can drop both commands together; it is not
the verified clamp-first ordered analogue sequence. Seventeen control loads
also need a real fanout/delay allocation in the integrated design.

## Connection to the driver

The [control contract](recording-front-end-control-contract.md) requires the
future external controller to hold both driver requests low, ground recording
inputs, disconnect contact paths and observe allocated guards before admitting
stimulation. Afterwards it observes delivered-current quiescence, reconnects
while grounded, separately qualifies voltages, releases the clamp and qualifies
analogue/filter recovery before issuing valid features.

The driver's RESET_READY, RAILS_QUALIFIED, ROUTE_LOCKED, external supervisor and
per-source quiescence inputs remain external requirements. This package adds
ordering obligations; it does **not** wire a new independently verified isolation
detector into the driver. Commanded states and clean ERC do not replace observed
pin voltage or delivered current. The next integrated package must implement and
connect those responsibilities.

## Explicit architecture revisions

Stage 2 remains a historical proposal. Its direct 8 MHz SPI becomes **4 MHz**
after isolation: the 8 MHz return-path setup margin is negative 4.5 ns before
board allowance. Nineteen 5 microsecond slots occupy 95 of each 250 microsecond
frame, preserving 4 ksample/s per stream. Actual neural apertures span 75
microseconds. CONVERT word n samples at local CS n+1 and returns at n+2;
the command timestamp is one slot early. ADC buffer/MUX bias must respect the
200 ksample/s intra-burst spacing, rather than just the 68 kconversion/s average.

The old 4.5 mW assembled AFE allocation is unclosed. Two isolators at the
manufacturer's static-high maximum-current test condition alone imply about
80.5 mW at 3.3 V across both domains, before switches, RHD, logic, loading and
converter losses. This is a particular table condition, not a system ceiling.
The full battery/thermal/package budget must be revised openly; new parts cannot
silently fit the old 0.5 mW generic protection/bias allowance.

## Finite evidence and limits

The [input-network study](../../electronics/stage4/recording-study/README.md)
preserves eight quiet cases and nine transients. Seven transients remain inside
the sampled DC envelope; 300 pC injection and an unblanked 600 mV fault fail.
This is a passive two-node model with assumed parasitics, not vendor nonlinear
fault protection or amplifier saturation. An independent scalar/DC/KCL audit
checks 175 conditions; same-model replay is reported separately.

Errors from the same common-mode sinusoid are coherently bounded. The nominal
10 microvolt/50 Hz input misses the 10 dB allocation at about **9.96 dB**; the
nominal 50 microvolt case passes conditionally. High recording/reference impedance
fails more severely. Weak-signal qualification is **unearned**. Specific future
options include reference impedance control, characterization or revised montage.
This finite result neither blocks the digital concept nor establishes biological
feasibility. No threshold was tuned to make it pass.

The protocol study checks seventeen scenario groups and 56 assertions. Observable
missing/stale metadata and timing violations invalidate full frames; plausible
untagged ADC replay can escape detection. Firmware buffer ownership and fault
tests remain necessary. RHD fast settle at 300 Hz has a recommended duration of
8.33 ms; neither that recommendation nor passive pin settling qualifies restored
analogue linearity or downstream features. The historical 100 ms filter failures
remain unchanged. No generic 20 ms neural recovery is claimed.

## Package completion and next engineering work

This checkpoint delivers native connectivity, primary-source package/pin review,
unexcluded ERC, readable exports, finite studies and portable saved-data checks.
No hardware was fabricated or measured. The
[component review](recording-front-end-component-review.md) records source
conditions and typical-versus-guaranteed distinctions.

Stage 4 still needs integrated contact routing, independent supervision and
observed shutdown/voltage qualification, isolated power and full system budgets,
monitor ADC/reference/telemetry connections, nRF5340 firmware, populated PCB
layout and DRC. These lead to Stage 5 populated engineering CAD and the final
illustrated manuscript/repository release. Undemonstrated biological efficacy
is not an additional completion gate for the digital concept.
