# Portable production policy core

`scci_rh_runtime.c` is linked into the nRF5340 target application and compiled without
changes by the host fault tests. It owns policy admission and state, rather than
GPIO, peripheral timing, packet authentication or a physiological model.

The runtime starts inhibited. Configuration readback, a known raw conversion,
qualified observed health, a current command lease and explicit rearm precede
route admission. Each route commit must be served before active-Q readback;
shift-register serial return is not a substitute for active-Q observations. A
route readback acknowledgement must match both requested addresses. Identical
addresses are rejected when both sources are requested.

Explicit recovery begins while still inhibited: `scci_rh_runtime_recovery_begin`
qualifies pre-monitor health and actual quiet, then requests one monitor-latch
rearm. The backend waits for the observed monitor permits before calling final
`scci_rh_runtime_rearm`, which requests the ordered fault-reset and supervisor-rearm
edges. This avoids requiring monitor permission before the action that creates
it. Neither function resets the charge integrator or automatically repeats a
fault clear; interrupted unknown charge history must be retained.

Motor and pressure mode accept bounded, prequalified event plans. The selected
plan limits are 3,000 microamperes, 200 microseconds per phase, a gap of at least
200 microseconds and at least 2,778 microseconds between event starts. Actual
quiet and inactive timers remain necessary even when the gap has elapsed. OFF
trials retain their event identity while requesting no output. The core does
not derive a stimulation policy from expert voltage or demonstrate learning.

After a normally completed first phase, the core can prepare a second phase.
The backend must serve the phase-rearm action and explicitly call phase-ready
and phase-start. Hardware records and clears requests at the scheduled phase
deadline; the core accepts that captured deadline. A late software service is
an interruption rather than a backdated normal endpoint. Any hard trip, health
loss, expired lease, invalid sample identity or queue overflow removes all
requests and route intent and leaves sticky inhibition. Recovery never emits
an automatic compensating phase.

The SBP parser consumes the existing 56-byte `AT` version-1, kind-2 packet. It
checks CRC32, exact schema, a trusted configured session, calibration identity,
uint32 forward sequence, newer oldest physical support, causal timestamps,
finite binary32 values, the 50–250 mmHg sanity range and 0–50 mmHg uncertainty
allocation. Quality zero means valid in this protocol. Offset-interval width
is at most 1,000 microseconds, representing at most 500 microseconds uncertainty
about its midpoint; large offsets themselves are allowed. Invalid packets
invalidate prior support and inhibit output. New support never clears a fault.
The oldest possible support expires after two seconds independently of arrival.
CRC is not sender authentication, clock proof, or sensor calibration.

The selected fallback is immediate digital stop when required support expires.
The earlier comparison study's hold/ramp alternatives are not silently adopted
as a physiological safety policy. Motor commands have at most a 250 ms lease,
pressure commands 3 s and diagnostic capture 100 ms. Diagnostic and observe
modes cannot admit stimulation events.

Raw identities carry epoch, capture sequence, expected/claimed channel,
aperture time and validity. These software checks do not discover a plausible
undetected hardware channel error. An unknown transaction, skipped/duplicate
identity, clipping or backwards aperture invalidates configuration and requires
a new readback epoch. Queue accounting retains 16,384 raw and 8,192 normal bytes;
the backend owns actual storage. Full queues preserve counters and inhibit
instead of labelling overwritten bytes valid.

Local time uses uint64 microseconds. The separate 32-bit tick-extension helper
accepts a modulo delta only below half range; the target must service it often
enough to exclude multiple wraps and convert ticks explicitly. Fault storage is
a fixed sixteen-entry ring with an independent saturating total count. No heap
allocation, variable-length array or native wire-struct cast is used.

Run `python firmware/nrf5340/tests/check_runtime.py` from the repository root.
It compiles this production source with strict C11 warnings and executes finite
fault scenarios. Python `struct` and `zlib` independently produce the packet
fixture. The default run only compares saved source-bound results; the explicit
`--write-results` option updates them. Target compilation and these host tests
remain separate from physical GPIO, SPIM, load, electrode and biological tests.
