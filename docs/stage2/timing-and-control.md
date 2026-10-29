# Timing, observations and control contracts

Document **S2-TIME-001**, 8 October 2026. The [timing input audit](timing-budget-inputs.json)
contains the numerical assumptions and failure examples; the
[contract register](control-contracts.json) defines eleven records. The
[selected system](selected-design.md) and [computed budgets](../../results/stage2/budget-summary.json)
are the current integrated arithmetic, not firmware benchmarks.

Every stream carries units, configuration/version, source clock epoch, physical
measurement support, sequence and validity. A timestamp on a newly transmitted
packet must not erase an old physical measurement. Unknown clock conversion
means unknown freshness; invalid masked samples cannot be replaced with model
ground truth.

| Contract | Carries | Important constraint |
|---|---|---|
| S2-C-001 | Raw acquisition blocks | Per-aperture times, channel masks, range and artifact reasons |
| S2-C-002 | Causal motor estimate | History support, confidence, latency and model version |
| S2-C-003 | External motion/contact observations | Actual sensor measurement time and transport delay |
| S2-C-004 | External SBP observation | Peak/support time, quality and freshness; not a generic MAP substitution |
| S2-C-005 | Expert/learner calibration | Identified response uncertainty and qualified contact mapping |
| S2-C-006 | Intervention request | Requested mode/profile, goal time, bounded magnitude and lease |
| S2-C-007 | Locally admitted plan | Joint limits, routes, start time and source-rate checks |
| S2-C-008 | Delivered-output evidence | Independent current/voltage, charge, clipping and faults |
| S2-C-009 | Artifact/recovery ledger | Predicted masks plus observed invalidity; recovery is not a fixed automatic release |
| S2-C-010 | Lease/fallback | Mode-specific stale-input, link-loss and suspension behavior |
| S2-C-011 | Unassisted assessment | Assistance off, practice budget, retention/transfer and comparison labels |

## Causal timing

The fast chain allocates 2 ms AFE group delay, 0.25 ms acquisition phase wait,
1 ms post-aperture conversion/pipeline-and-buffer release, 5 ms feature/policy
release wait, 2 ms estimator execution,
**0.75 ms policy execution**, 0.25 ms admission, 0.1 ms launch jitter and
0.5 ms clock-conversion uncertainty. Sum: **11.85 ms**. Estimator, policy and
admission execution together allocate 3 ms of each 5 ms tick, including streaming
work attributed to the estimator allowance. The independent output trip mechanism
has a separate electrical timing requirement: a 2 ms clock-health watchdog does
not bound a stuck 500 µs phase.

A trailing 20 ms uniform window has a nominal midpoint age of 10 ms; at delivery
it is 21.85 ms old. Actual sample weighting and masks change that number. Filter
history, execution delay and prediction horizon are distinct. No bidirectional
filter or future sample is allowed in the causal path. The archive FIR adds
3.75 ms and is excluded from fast control. The ideal 0.1 Hz high-pass/300 Hz
third-order low-pass gives approximately 16.819 ms group delay at 1 Hz, so slow
features cannot inherit the 2 ms fast-band allocation.

Free-running frames fail the selected 25 ms reactive target at 20, 40 and 60 Hz
(61.85, 36.85 and 28.52 ms including worst next-frame wait). The proposed motor
task has known paced goals. Advance admission may schedule an output at a known
goal time only when response predictions, fresh observations, per-profile
minimum period, physical-source availability, route and monitor health pass.
It cannot guarantee response timing for an unseen perturbation or evade a
profile's rate limits by changing the frame origin.

### Physical sources and profile rates

The 150 Hz ceiling is **per profile**, not per physical source. One source may
time-share several profiles. For the pressure reference, source 0 serves the
three 120 Hz profiles at offsets 0/2/4 ms: 360 pulses/s, with a minimum cyclic
start gap of 2 ms (last-to-first gap 4.333 ms). Source 1 is unused. This is a
chosen deterministic assignment, not a third source or an arbitrary rephasing.
The three logical profile identities are retained separately in the input and
cyclic checks. Reusing one identity for all three events fails both its repetition
ceiling and configured minimum period, even when the physical source is available.

Reserve 250 microseconds after each biphasic waveform for zero-current break,
route reconfiguration and rearm. A 300-microsecond pressure phase therefore
uses 0.95 ms service time including its 100-microsecond gap; 2 ms spacing passes
the allocation. The two aligned motor sources each use 0.75 ms of their 25 ms
period. At the 500-microsecond phase corner service is 1.35 ms. The reproduction
checks include the cyclic last-to-first interval and reject overlapping use of
a source. These are chosen timing bounds, not circuit/firmware benchmarks.

The recording recovery mask is distinct from source rearm. Neither grants
automatic electrode/return reset: measured voltage, route health and qualified
polarization bounds can still veto reuse. Concurrent sources require disjoint
owned contact/return routes. A pressure profile retains its 8.333 ms minimum
period, and the 40 Hz motor profile retains its 25 ms minimum, even if launches
are anchored to a task event.

## Artifact accounting

Mask the union of every active source's pulse, interphase, preguard and observed
recovery intervals. Simultaneous independent sources share the global mask;
staggered profiles widen its union. The reproduction script calculates periodic
wrap and overlap exactly, and the worst usable fraction of any 20 ms trailing
history. Multiplying each pulse width and adding blindly overcounts overlaps.

Motor reference: two aligned 200 µs phases with 100 µs interphase, 1 ms allocated
recovery and 100 µs preguard yield 6.4% global masking at 40 Hz and 92% minimum
20 ms usable coverage. This passes chosen screening gates only if actual recovery
and signal quality match the assumptions. Pressure reference: three offsets
0/2/4 ms at 120 Hz, 300 µs phases, the same gap/recovery/preguard yield 64.8%
masking and about 30.3% worst-window usable coverage. It fails the motor
observation qualification. Pressure uses external sensing; pulse realignment is
not accepted without retesting its effect on recruitment.

Archive filtering extends the invalidity mask by its 7.5 ms causal support.
The nominal motor archive is 36.4% invalid; the pressure archive is entirely
invalid while the train runs. Archive values still carry masks and provenance.
Recursive causal features require a declared reset/recovery/warm-up policy;
their validity is not established simply by the arrival of a fresh raw sample.

## Pressure freshness and authority

The primary pressure study digitizes an external waveform at 200 Hz, extracts
SBP/DBP/MAP at 1 Hz, and can change its stimulation program as rapidly as 25 ms.
These are different rates. They do not prove 25 ms physical SBP freshness.
The SCCI_RH local policy tick is a chosen 250 ms. A completed beat, extraction wait,
transport and clock uncertainty all contribute to observation age. The declared
stress permits 3.0005 s age before a next beat record and fails a selected 2 s
freshness gate. An apparently recent packet must therefore trigger the stated
fallback when its underlying measurement is stale.

Pressor commands are nonnegative. Reducing output removes added pressor drive;
there is no assumed independent antihypertensive actuator. Qualified profiles,
upper output bounds, rate limits, overshoot, weak/absent authority, invalid sensor
quality and loss of input are separate tests. Output inhibition cannot be
described as clinically risk-free: support dependence belongs to future
biological validation and target-specific fallback design.

## Mode and provenance discipline

Motor/pressure are mutually exclusive application modes with leased
configuration versions. Calibration and capture cannot silently enable
unqualified profiles. Recovery and monitoring have authority to veto a request.
Link loss does not create fresh external data. Retention assessment forbids
active assistance, and logs actual delivered output rather than commanded zeros
alone. Later tests compare expert-informed/learner-only and neural/external-only
policies under equal practice/data and explicitly matched latency budgets.

No firmware deadline, recorded sample validity, biological response time or
benefit has been measured in this stage. The contract register deliberately leaves
these qualification tasks open.
