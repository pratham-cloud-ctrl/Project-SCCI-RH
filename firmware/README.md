# Timed biphasic pulse reference

This portable C module is a **host-validated digital state machine**, not flashed MCU firmware, an implant driver, or a tested safety system. It generates timed segment commands for an abstract hardware-timer backend.

Nominal sequence: +100 µA for 200 µs → 0 for 50 µs → −100 µA for 200 µs → 0 for 19,550 µs. The sequence period is 20 ms (50 Hz). Each phase has 20 nC and ideal signed net charge is zero. Limits are illustrative **electrical test-load limits**, not established tissue-safety limits.

Configuration limits: current 1–250 µA; phase 50–250 µs; interphase gap 20–1000 µs; period 20 ms–2 s; phase charge ≤62.5 nC. Fresh valid sensor data are required within a configurable timeout (nominal 100 ms). Repetition is requested externally after the recovery interval; the module never starts a new pulse automatically. An unsigned timestamp refractory check rejects starts closer than the configured period even if a caller incorrectly drains timer events early. A stale/invalid sensor latches an inhibition. Re-arming requires fresh valid data and the idle state.

An already scheduled pulse completes its balancing phase on a **software sensor fault**, then no further pulse starts. Power loss, timer failure, current mismatch, compliance loss, or a hardware emergency stop can interrupt balance. Independent analog current limiting, electrode discharge, watchdog circuitry, output monitoring, and a validated hardware timer are required for a real system and are not implemented here. The caller must treat the controller configuration as immutable between initialization and idle reconfiguration.

`scci_rh_timer_event` must be called exactly once at each segment boundary by a hardware backend. Its duration fields are commands; the code does not measure actual current or duration. A real backend needs measured timing-error bounds and measured charge imbalance. The host trace verifies ideal scheduling only.

Build and validate from the repository root:

```sh
python scripts/build_firmware.py
# Or: python scripts/build_firmware.py --cc /path/to/zig
python scripts/run_adapter.py
```

The build accepts GCC, Clang, or Zig's C frontend and treats warnings as errors. The host validator checks the initial disabled state, exact ideal net charge, the recovery period, fault inhibition, completion of balance after a software fault, configuration limits, non-overlapping pulses, and unsigned 32-bit timestamp wraparound. It writes `results/firmware_pulse_trace.csv` and `results/firmware_validation.json`. Binaries go to ignored `build/firmware/`.

The build also produces a host shared library. `src/scci_rh/pulse_binding.py` calls that actual C library through `ctypes`; it does not duplicate the state machine in Python. The application adapter reads the generated model traces and writes `results/application_pulse_events.csv`, `application_pulse_requests.csv`, and `adapter_validation.json`. Pressure requests use an illustrative frequency of 50 times normalized command Hz with the command held between samples. Motor requests occur at an increasing surrogate phase crossing after warm-up; the abstract signed trajectory correction is logged separately and is **not converted into current**. Fresh-data availability gates each request, and the C timeout is tested independently.

The adapter translates the ideal C output into circuit pin commands using the declared convention PHASE=0 for positive, PHASE=1 for negative, INHIBIT=1 for output off. During the inhibited gap, PHASE is prepared for the negative phase. A real backend must assert INHIBIT before changing PHASE, allow switching to settle, then deassert INHIBIT at the next timed boundary; an atomic ideal segment trace does not verify that order electrically. This convention must be verified against an actual backend's routing. It is a digital interface specification, not verification of switching transients, analog charge, current-source behavior, or clinical feedback. Five additional unit tests call the compiled C library when it is available; they are explicitly skipped if no library has been built.
