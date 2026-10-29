"""Finite supervision histories and explicit upstream pin binding.

No physical device, gate-delay, biological, safety or arbitrary-fault proof.
Default / --check is read-only. Only --write-results changes a saved artifact.
Text hashes normalize CRLF and CR to LF for Windows/Linux reproducibility.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STAGE4 = HERE.parent
ROOT = STAGE4.parents[1]
RESULTS = HERE / "control-results.json"


def text_sha(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


# Independently stated physical pins from the previous committed packages.
# New supervision wiring must retain these actual observations and interfaces.
UPSTREAM = {
    "current-driver": {
        "J3": {"1": "CH0_REQUEST", "5": "CH1_REQUEST"},
        "J4": {"1": "RESET_READY", "2": "RAILS_QUALIFIED", "3": "CH0_MON_PERMIT", "4": "CH0_EXT_SUP_OK", "5": "CH0_ROUTE_LOCKED", "6": "CH0_QUIESCENT_OK", "7": "CH1_MON_PERMIT", "8": "CH1_EXT_SUP_OK", "9": "CH1_ROUTE_LOCKED", "10": "CH1_QUIESCENT_OK"},
        "J5": {"1": "CH0_RUN", "5": "CH1_RUN"},
        "J100": {"1": "CH0_A_BR", "2": "CH0_B_BR"},
        "J200": {"1": "CH1_A_BR", "2": "CH1_B_BR"},
    },
    "monitoring-cell": {
        "J3": {"1": "CH0_EXT_SUP_OK", "2": "CH1_EXT_SUP_OK", "3": "CH0_PERMIT", "4": "CH1_PERMIT"},
        "J4": {"1": "CH0_I_MON", "2": "CH1_I_MON", "3": "V_MID"},
        "J100": {"1": "CH0_RETURN_LOAD", "2": "CH0_RETURN_DRIVER"},
        "J200": {"1": "CH1_RETURN_LOAD", "2": "CH1_RETURN_DRIVER"},
    },
    "contact-router": {
        "J3": {"1": "CH0_WANT_ROUTE", "2": "CH1_WANT_ROUTE", "3": "CH0_REQUEST", "4": "CH1_REQUEST", "5": "CH0_RUN", "6": "CH1_RUN"},
        "J4": {"1": "RESET_READY", "2": "RAILS_QUALIFIED", "3": "WATCHDOG_OK", "4": "AFE_ISOLATED_READY", "5": "CH0_QUIESCENT_OK", "6": "CH1_QUIESCENT_OK", "8": "CH0_MON_PERMIT", "9": "CH1_MON_PERMIT"},
        "J5": {"7": "CH0_ROUTE_LOCKED", "8": "CH1_ROUTE_LOCKED"},
        "J100": {"1": "CH0_A_ROUTER", "2": "CH0_RETURN_LOAD"},
        "J200": {"1": "CH1_A_ROUTER", "2": "CH1_RETURN_LOAD"},
    },
    "recording-front-end": {
        "J1": {"1": "AFE_P5", "2": "AFE_N5", "3": "AFE_3V3", "4": "AFEAGND"},
        "J2": {"1": "HOST_3V3", "2": "HOSTGND", "7": "HOST_CONNECT_CMD", "8": "HOST_RECORD_CMD", "9": "HOST_FAULT_N"},
    },
}


def bind_upstream() -> dict[str, Any]:
    bindings = []
    hashes = {}
    for package, refs in UPSTREAM.items():
        path = STAGE4 / package / "connectivity.json"
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        parts = {p["ref"]: p for p in manifest["parts"]}
        hashes[str(path.relative_to(ROOT)).replace("\\", "/")] = text_sha(path)
        for ref, pins in refs.items():
            for pin, net in pins.items():
                assert parts[ref]["nets"][pin] == net, (package, ref, pin, net)
                bindings.append({"package": package, "ref": ref, "pin": pin, "net": net})
    assert len(bindings) == 58, len(bindings)
    return {"normalized_lf_manifest_sha256": hashes, "checked_pin_bindings": bindings}

SECONDARY_NS = 250_112
SECONDARY_MAX_NS = 264_000
WATCHDOG_MAX_NS = 230_000_000
COINCIDENCE_NS = 2


@dataclass
class Channel:
    request: bool = False
    run: bool = False
    route_locked: bool = True
    quiet: bool = True
    mon_permit: bool = False
    pair_ok: bool = True
    want_route: bool = False
    phase_rearm: bool = False
    sec_out: bool = False
    sec_due: int | None = None
    sec_stuck_high: bool = False
    block: bool | None = True
    timeout: bool | None = None
    last_request_change: int | None = None


@dataclass
class Supervisor:
    """Exact ideal state equations; all observations and supplies separately named.

    Setting run is an external observation of the existing driver logic, never an
    assertion that current flows. Quiet is an independent current-window output.
    """
    channels: list[Channel] = field(default_factory=lambda: [Channel(), Channel()])
    time_ns: int = 0
    reset_ready: bool = False
    startup_ready: bool = False
    host_rails_ok: bool = False
    afe_blank_observed: bool = False
    guard_fault_n: bool = True
    reference_ok: bool = True
    wd_enout_ok: bool = False
    wd_out_ok: bool = False
    wdi: bool = True
    wdi_seen: bool = False
    wd_due: int | None = None
    armed: bool | None = False
    sup_rearm: bool = False
    fault_reset: bool = False
    logic_valid: bool = True
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def watchdog_good(self) -> bool:
        return self.wd_enout_ok and self.wd_out_ok and self.wdi_seen

    @property
    def physical_health(self) -> bool:
        return bool(self.startup_ready and self.host_rails_ok
                    and self.afe_blank_observed and self.guard_fault_n
                    and self.watchdog_good
                    and all(c.pair_ok for c in self.channels))

    @property
    def raw_health(self) -> bool:
        return self.physical_health and all(c.mon_permit for c in self.channels)

    @property
    def quiet_all(self) -> bool:
        return all(c.quiet and not c.request and not c.run and not c.sec_out for c in self.channels)

    def allow(self, i: int) -> bool | None:
        if not self.logic_valid:
            return None
        c = self.channels[i]
        definite = self.raw_health and c.route_locked and c.request and c.sec_out and c.run
        if not definite or self.armed is False or c.timeout is True or c.block is True:
            return False
        if self.armed is None or c.timeout is None or c.block is None:
            return None
        return True

    @property
    def guard_command(self) -> bool | None:
        a, b = self.allow(0), self.allow(1)
        if a is True or b is True:
            return True
        return None if a is None or b is None else False

    def settle(self, timer_fell: tuple[int, ...] = ()) -> None:
        if not self.logic_valid:
            return
        if not (self.wd_enout_ok and self.wd_out_ok and self.host_rails_ok):
            self.wdi_seen = False
        # Reset requires observed quiet, both raw requests, both RUN and timers
        # low, and RAW_HEALTH. Timeout is deliberately absent to avoid self-lock.
        clear_timeout = self.fault_reset and self.raw_health and self.quiet_all
        for i, c in enumerate(self.channels):
            if clear_timeout:
                c.timeout = False
            elif i in timer_fell:
                if c.last_request_change is not None and abs(self.time_ns - c.last_request_change) <= COINCIDENCE_NS:
                    c.timeout = None
                elif c.request:
                    c.timeout = True
        if not self.raw_health or any(c.timeout is True for c in self.channels):
            self.armed = False
        elif any(c.timeout is None for c in self.channels):
            self.armed = None
        for c in self.channels:
            phase_base = self.armed if self.raw_health and c.route_locked else False
            pre_n = False if c.sec_out and not c.request else phase_base
            safe = phase_base if c.phase_rearm and c.quiet and not c.request and not c.run and not c.sec_out else False
            assert not (pre_n is False and safe is True), "Simultaneous async BLOCK preset/clear"
            if pre_n is False:
                c.block = True
            elif safe is True:
                c.block = False
            elif safe is None:
                c.block = None
            elif pre_n is None and c.block is not True:
                c.block = None

    def snapshot(self, event: str) -> None:
        self.history.append({
            "time_ns": self.time_ns, "event": event,
            "logic_valid": self.logic_valid,
            "physical_health": self.physical_health if self.logic_valid else None,
            "raw_health": self.raw_health if self.logic_valid else None,
            "watchdog_good": self.watchdog_good if self.logic_valid else None,
            "armed": self.armed if self.logic_valid else None,
            "guard_command_all_18": self.guard_command,
            "channels": [{"request": c.request, "run_status": c.run,
                          "quiet_observation": c.quiet, "mon_permit": c.mon_permit,
                          "secondary_out": c.sec_out if self.logic_valid else None,
                          "secondary_due_ns": c.sec_due,
                          "timeout": c.timeout if self.logic_valid else None,
                          "block": c.block if self.logic_valid else None,
                          "allow": self.allow(i)} for i, c in enumerate(self.channels)],
        })

    def event(self, at: int, event: str, *, channel: int | None = None, **changes: Any) -> None:
        self.advance(at)
        obj = self if channel is None else self.channels[channel]
        old_req = obj.request if channel is not None else None
        old_wdi = self.wdi
        old_rearm = self.sup_rearm
        for key, value in changes.items():
            assert hasattr(obj, key), key
            setattr(obj, key, value)
        if channel is not None and old_req != obj.request:
            obj.last_request_change = at
            if obj.request and self.logic_valid and not obj.sec_out:
                obj.sec_out = True
                obj.sec_due = None if obj.sec_stuck_high else at + SECONDARY_NS
        if channel is None and old_wdi and not self.wdi and self.logic_valid:
            self.wdi_seen = bool(self.wd_enout_ok and self.wd_out_ok and self.host_rails_ok)
            if self.wdi_seen:
                self.wd_due = at + WATCHDOG_MAX_NS
        self.settle()
        if channel is None and not old_rearm and self.sup_rearm and self.logic_valid:
            if self.raw_health and self.quiet_all and any(c.timeout is None for c in self.channels):
                self.armed = None
            else:
                self.armed = bool(self.raw_health and self.quiet_all and all(c.timeout is False for c in self.channels))
            self.settle()
        self.snapshot(event)

    def advance(self, to: int) -> None:
        assert to >= self.time_ns, (to, self.time_ns)
        while True:
            pending = [c.sec_due for c in self.channels if c.sec_due is not None]
            if self.wd_due is not None:
                pending.append(self.wd_due)
            if not pending or min(pending) > to:
                break
            self.time_ns = min(pending)
            fell = []
            for i, c in enumerate(self.channels):
                if c.sec_due == self.time_ns:
                    c.sec_due = None
                    c.sec_out = False
                    fell.append(i)
            if self.wd_due == self.time_ns:
                self.wd_due = None
                self.wd_out_ok = False
            self.settle(tuple(fell))
            self.snapshot("autonomous_deadline")
        self.time_ns = to

    def healthy_start(self) -> None:
        self.snapshot("startup_unqualified")
        self.event(5_000_000, "rails_startup_reset_and_blank_observation_qualified",
                   reset_ready=True, startup_ready=True, host_rails_ok=True,
                   afe_blank_observed=True, wd_enout_ok=True, wd_out_ok=True)
        self.event(5_010_000, "fresh_heartbeat_falling_edge", wdi=False)
        self.event(5_011_000, "heartbeat_return_high", wdi=True)
        # Existing monitor REARM first needs pre-MON physical supervision;
        # never invent MON_PERMIT by merely setting REQUEST/RUN low.
        for i in range(2):
            self.event(5_020_000 + i * 1_000, "separate_monitor_rearm_after_pre_monitor_health", channel=i, mon_permit=True)
        self.event(5_030_000, "explicit_fault_reset_while_all_observed_quiet", fault_reset=True)
        self.event(5_031_000, "fault_reset_released", fault_reset=False)
        self.event(5_040_000, "explicit_supervisory_rearm", sup_rearm=True)
        self.event(5_041_000, "supervisory_rearm_released", sup_rearm=False)

    def phase_arm(self, at: int, i: int = 0) -> None:
        self.event(at, "phase_rearm_with_route_held", channel=i, phase_rearm=True, want_route=True)
        self.event(at + 1_000, "phase_rearm_released", channel=i, phase_rearm=False)


@dataclass
class Case:
    code: str
    title: str
    model: Supervisor = field(default_factory=Supervisor)
    checks: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def expect(self, claim: str, condition: bool) -> None:
        assert condition, (self.code, claim)
        self.checks.append({"claim": claim, "passed": True})

    def result(self) -> dict[str, Any]:
        return {"id": self.code, "title": self.title, "checks": self.checks,
                "limitations": self.limitations, "history": self.model.history}

def cases() -> list[dict[str, Any]]:
    output: list[Case] = []
    base = 10_000_000

    s = Case("S01", "Startup requires fresh heartbeat, pre-MON health, separate resets and raw rearm")
    d = s.model
    d.snapshot("power_on_no_valid_state")
    d.event(5_000_000, "qualified_rails_but_no_heartbeat", reset_ready=True, startup_ready=True,
            host_rails_ok=True, afe_blank_observed=True, wd_enout_ok=True, wd_out_ok=True)
    d.event(5_010_000, "premature_supervisor_rearm", sup_rearm=True)
    s.expect("no first heartbeat means no watchdog-good and no admission", not d.watchdog_good and not d.armed and d.guard_command is False)
    d.event(5_011_000, "release_premature_rearm", sup_rearm=False)
    d.event(5_100_000, "first_falling_heartbeat", wdi=False)
    s.expect("pre-MON physical supervision becomes healthy independently of MON_PERMIT", d.physical_health and not d.raw_health)
    d.event(5_200_000, "source0_monitor_explicit_rearm", channel=0, mon_permit=True)
    s.expect("source1 monitor still prevents RAW_HEALTH", not d.raw_health)
    d.event(5_201_000, "source1_monitor_explicit_rearm", channel=1, mon_permit=True)
    s.expect("both monitors restore raw health without implicitly arming", d.raw_health and not d.armed)
    d.event(5_300_000, "explicit_quiet_fault_reset", fault_reset=True)
    d.event(5_301_000, "release_fault_reset", fault_reset=False)
    d.event(5_400_000, "explicit_supervisor_rearm", sup_rearm=True)
    s.expect("separate fault-reset then rearm establishes admission", d.armed and all(c.timeout is False for c in d.channels))
    s.limitations.append("SENSE_HEALTH -> old monitor EXT_SUP_OK; RAW_HEALTH/ARM-qualified EXT_SUP_OK -> old driver. Equating these distinct nets creates a startup deadlock.")
    output.append(s)

    s = Case("S02", "Normal two-phase sequence retains route intent through an allocated 200us gap")
    d = s.model
    d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "first_phase_request", channel=0, request=True, run=True, quiet=False)
    s.expect("first admitted phase closes the common guard command", d.allow(0) is True and d.guard_command is True)
    d.event(base + 210_000, "first_phase_ends_200us", channel=0, request=False, run=False, quiet=False)
    s.expect("normal request end immediately consumes per-phase block and opens all guards", d.channels[0].block and d.guard_command is False)
    d.advance(base + 261_000); d.snapshot("secondary_timer_completed_in_gap")
    s.expect("normal timer completion does not latch timeout or discard global arm", d.channels[0].timeout is False and d.armed)
    d.event(base + 335_000, "quiet_observation_qualified_after_declared_dwell", channel=0, quiet=True)
    d.phase_arm(base + 409_000)
    d.event(base + 410_000, "second_phase_request_after_allocated_200us_gap", channel=0, request=True, run=True, quiet=False)
    s.expect("explicit phase rearm admits opposite phase while route intent remains held", d.allow(0) is True and d.channels[0].want_route)
    d.event(base + 610_000, "second_phase_ends_200us", channel=0, request=False, run=False, quiet=True)
    s.limitations.append("Polarity capture is the old driver's separately bound function; this supervisor model never generates an opposite pulse. A 200us gap is a provisional engineering allocation and the model waits explicit qualified quiet plus secondary-low; the older 100us schedule is unearned under the selected RC/threshold/latency corners.")
    output.append(s)

    s = Case("S03", "Early end and repeated request cannot reopen the same phase window")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "request_start", channel=0, request=True, run=True, quiet=False)
    d.event(base + 60_000, "early_request_end", channel=0, request=False, run=False, quiet=True)
    d.event(base + 80_000, "repeated_request_in_active_timer", channel=0, request=True, run=True, quiet=False)
    s.expect("timer stays active but consumed BLOCK prevents reopening", d.channels[0].sec_out and d.channels[0].block and d.allow(0) is False)
    d.event(base + 90_000, "invalid_phase_rearm_while_request_high", channel=0, phase_rearm=True)
    s.expect("rearm cannot clear block while request remains high", d.channels[0].block)
    s.limitations.append("The phase-rearm level must be released before request. This is an admitted sequencing rule, not qualified glitch immunity.")
    output.append(s)

    s = Case("S04", "Primary timer stuck high is interrupted by the separately triggered secondary timer")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "injected_primary_timer_stuck_request_and_RUN_high", channel=0, request=True, run=True, quiet=False)
    d.advance(base + 245_000); d.snapshot("primary_would_have_timed_out_but_RUN_injected_high")
    s.expect("secondary interval is still admitted before its own deadline", d.allow(0) is True)
    d.advance(base + 10_000 + SECONDARY_NS); d.snapshot("secondary_nominal_expiry")
    s.expect("secondary expiry independently opens guards, latches timeout and removes global arm", d.allow(0) is False and d.channels[0].timeout is True and not d.armed)
    d.event(base + 400_000, "request_remains_high_health_still_good", channel=0, run=True)
    s.expect("timeout remains sticky rather than resuming", d.channels[0].timeout is True and d.guard_command is False)
    s.limitations.append("SET-open is conservatively represented by an injected primary timer stuck-high witness, not a manufacturer-defined SET-open transfer. 264us is the separate conservative analogue timing allocation before physical guard delay.")
    output.append(s)

    for code, field_name in [("S05", "host_rails_ok"), ("S06", "afe_blank_observed"), ("S07", "guard_fault_n")]:
        s = Case(code, f"{field_name} loss interrupts both sources; recovery does not resume")
        d = s.model; d.healthy_start(); d.phase_arm(base, 0); d.phase_arm(base + 2_000, 1)
        d.event(base + 10_000, "source0_phase", channel=0, request=True, run=True, quiet=False)
        d.event(base + 12_000, "source1_phase", channel=1, request=True, run=True, quiet=False)
        d.event(base + 50_000, "observed_health_loss", **{field_name: False})
        s.expect("global health loss opens the common eighteen-port guard command", d.guard_command is False and not d.armed)
        d.event(base + 60_000, "observed_health_recovers", **{field_name: True})
        s.expect("restored observation alone cannot resume either request", d.guard_command is False and all(c.block for c in d.channels))
        output.append(s)

    s = Case("S08", "Reference failure is a retained observer-boundary witness")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "phase_start", channel=0, request=True, run=True, quiet=False)
    d.event(base + 50_000, "injected_reference_fault_not_reported_by_monitor_or_pair_flags", reference_ok=False)
    s.expect("reference failure is not silently credited as an implemented health input", d.raw_health)
    s.expect("healthy-looking observers can leave an admitted phase despite reference failure", d.allow(0) is True)
    s.limitations.append("UNPROTECTED witness: no independent reference-window fault flag is wired into native SENSE_HEALTH. MON_VREF/MON_VMID tolerances and intact observer behaviour are explicit assumptions; corrupt reference/current/voltage sensing can mislead admission.")
    output.append(s)

    s = Case("S09", "Monitor permit loss is separate from supervisor and monitor rearm")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "phase_start", channel=0, request=True, run=True, quiet=False)
    d.event(base + 50_000, "monitor_latched_fault", channel=0, mon_permit=False)
    s.expect("monitor fault removes global raw health and arm", not d.raw_health and not d.armed and d.guard_command is False)
    d.event(base + 60_000, "supervisor_rearm_attempt_cannot_clear_monitor", sup_rearm=True)
    s.expect("supervisor rearm does not clear independent monitor permission", not d.channels[0].mon_permit and not d.armed)
    d.event(base + 70_000, "monitor_requalification_without_phase_admission", channel=0, mon_permit=True)
    s.expect("monitor recovery alone cannot resume an interrupted phase", d.guard_command is False and not d.armed)
    output.append(s)

    s = Case("S10", "Pair-terminal limit observes voltage independently of DAC and RUN")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "phase_start", channel=0, request=True, run=True, quiet=False)
    d.event(base + 50_000, "actual_pair_voltage_above_window", channel=0, pair_ok=False)
    s.expect("terminal observation loss inhibits even though request and RUN stay high", d.channels[0].request and d.channels[0].run and not d.armed and d.guard_command is False)
    d.event(base + 60_000, "voltage_recovers", channel=0, pair_ok=True)
    s.expect("voltage recovery never reopens output automatically", d.guard_command is False)
    s.limitations.append("The sensor is connected across internal driver A_BR/B_BR; this is neither tissue voltage nor physical mux-position readback. Window tolerance and differential-amplifier common-mode mismatch are retained separately.")
    output.append(s)

    s = Case("S11", "Raw supervisory rearm cannot acquire an edge when quiet returns")
    d = s.model; d.healthy_start()
    d.event(base, "remove_ARM_for_recovery_test", sup_rearm=True)
    d.event(base + 1_000, "rearm_released", sup_rearm=False)
    d.event(base + 2_000, "fault_drop_then_return", guard_fault_n=False)
    d.event(base + 3_000, "fault_return", guard_fault_n=True)
    d.event(base + 4_000, "nonzero_actual_current_despite_low_commands", channel=0, quiet=False)
    d.event(base + 5_000, "raw_supervisor_rearm_during_nonquiet", sup_rearm=True)
    s.expect("nonquiet observation rejects rearm despite low REQUEST/RUN", not d.armed)
    d.event(base + 6_000, "quiet_returns_while_rearm_held_high", channel=0, quiet=True)
    s.expect("returning quiet cannot generate a raw rearm edge", not d.armed)
    d.event(base + 7_000, "release_rearm", sup_rearm=False)
    d.event(base + 8_000, "fresh_explicit_rearm", sup_rearm=True)
    s.expect("fresh qualified edge rearms", d.armed)
    output.append(s)

    s = Case("S12", "Timeout clear needs separate quiet FAULT_RESET and SUP_REARM")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "held_request", channel=0, request=True, run=True, quiet=False)
    d.advance(base + 10_000 + SECONDARY_NS)
    d.event(base + 270_000, "fault_reset_attempt_while_request_high", fault_reset=True)
    s.expect("active request rejects timeout clearing", d.channels[0].timeout is True)
    d.event(base + 271_000, "fault_reset_released", fault_reset=False)
    d.event(base + 280_000, "stop_request_and_observe_quiet", channel=0, request=False, run=False, quiet=True)
    d.event(base + 300_000, "supervisor_rearm_before_fault_reset", sup_rearm=True)
    s.expect("SUP_REARM cannot clear timeout itself", not d.armed and d.channels[0].timeout is True)
    d.event(base + 301_000, "release_sup_rearm", sup_rearm=False)
    d.event(base + 320_000, "explicit_quiet_fault_reset", fault_reset=True)
    d.event(base + 321_000, "fault_reset_released", fault_reset=False)
    s.expect("FAULT_RESET clears timeout but does not automatically arm", d.channels[0].timeout is False and not d.armed)
    d.event(base + 340_000, "fresh_supervisor_rearm_after_fault_reset", sup_rearm=True)
    s.expect("ordered separate reset/rearm removes deadlock", d.armed)
    output.append(s)

    s = Case("S13", "Heartbeat watchdog timeout is much slower than phase duration limit")
    d = s.model; d.healthy_start()
    s.expect("fresh heartbeat makes initial watchdog-good", d.watchdog_good)
    due = d.wd_due
    assert due is not None
    d.advance(due); d.snapshot("watchdog_deadline_without_further_falling_edges")
    s.expect("missed heartbeat clears seen and arm", not d.watchdog_good and not d.wdi_seen and not d.armed)
    d.event(due + 1_000, "watchdog_output_recovers_but_no_fresh_WDI", wd_out_ok=True)
    s.expect("watchdog recovery does not fabricate first-edge evidence", not d.watchdog_good)
    d.event(due + 2_000, "fresh_heartbeat_high_to_prepare", wdi=True)
    d.event(due + 3_000, "fresh_heartbeat_after_watchdog_recovery", wdi=False)
    s.expect("fresh edge restores heartbeat evidence but not global arm", d.watchdog_good and not d.armed)
    s.limitations.append("170..230ms watchdog tolerance is not a microsecond pulse limiter or proof of correct firmware execution; falling edges can be generated by faulty firmware/peripherals.")
    output.append(s)

    s = Case("S14", "Shared power leaves Boolean model unqualified")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "phase_start", channel=0, request=True, run=True, quiet=False)
    d.event(base + 50_000, "rail_warning_while_logic_still_valid", host_rails_ok=False)
    s.expect("valid warning first opens guards", d.guard_command is False)
    d.event(base + 51_000, "logic_supply_outside_operating_range", logic_valid=False)
    s.expect("invalid-supply outputs are unknown rather than falsely safe", d.guard_command is None)
    d.event(base + 60_000, "recover_with_reset_inhibited", logic_valid=True, reset_ready=False)
    s.expect("recovery begins inhibited", d.guard_command is False and not d.armed)
    s.limitations.append("Power generation and rail-off analogue terminal isolation are not implemented by this ideal event model; common power can defeat comparator, timer, latch and switch logic.")
    output.append(s)

    s = Case("S15", "Dual timer stuck-high remains a preserved failure witness")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "both_primary_and_secondary_stuck_high_injected", channel=0, sec_stuck_high=True, request=True, run=True, quiet=False)
    d.advance(base + 510_000); d.snapshot("500us_held_request_with_no_secondary_falling_edge")
    s.expect("dual timer fault can leave an overlong admitted request", d.allow(0) is True and d.channels[0].timeout is False)
    s.limitations.append("UNPROTECTED witness: primary and secondary timers can fail together; a healthy millisecond heartbeat does not impose a microsecond limit. 3mA x500us=1500nC is bookkeeping, not a simulated delivered-charge result.")
    output.append(s)

    s = Case("S16", "False-quiet, welded AFE switch and stuck guard are not certified away")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "phase_start_under_injected_false_blank_observation", channel=0, request=True, run=True, quiet=False)
    s.expect("healthy-looking voltage/blank observation can admit despite unobserved welded switch", d.allow(0) is True)
    d.event(base + 50_000, "commanded_guard_open", guard_fault_n=False)
    s.expect("commanded guard opens after a reported fault", d.guard_command is False)
    s.limitations.extend([
        "UNPROTECTED witness: the AFE physical pin windows plus local blank commands do not prove every HV disconnect is unwelded. A welded source switch can remain connected while an RHD ground clamp keeps its pin inside the voltage window.",
        "UNPROTECTED witness: a guard stuck conducting does not obey guard_command=0. Leakage, coupling, bypass paths and stored electrode charge are not equal to Boolean guard state.",
        "UNPROTECTED witness: a failed current observer can assert quiet despite nonzero unobserved current. The model does not claim to diagnose that failure from REQUEST or RUN.",
    ])
    output.append(s)

    s = Case("S17", "One source timeout removes the common guard for both sources")
    d = s.model; d.healthy_start(); d.phase_arm(base, 0); d.phase_arm(base + 2_000, 1)
    d.event(base + 10_000, "source0_held_request", channel=0, request=True, run=True, quiet=False)
    d.event(base + 100_000, "source1_later_phase", channel=1, request=True, run=True, quiet=False)
    d.advance(base + 10_000 + SECONDARY_NS); d.snapshot("source0_secondary_timeout_with_source1_running")
    s.expect("source0 timeout removes shared ARM and both ALLOWs", not d.armed and d.allow(0) is False and d.allow(1) is False)
    s.limitations.append("All eighteen body-facing guards share one enable; fault interruption affects both sources. It does not automatically balance either interrupted phase.")
    output.append(s)

    s = Case("S18", "Request/timer coincidence cannot earn deterministic timeout classification")
    d = s.model; d.healthy_start(); d.phase_arm(base)
    d.event(base + 10_000, "held_request", channel=0, request=True, run=True, quiet=False)
    due = d.channels[0].sec_due
    assert due is not None
    d.event(due - 1, "request_falls_in_declared_two_ns_exclusion", channel=0, request=False, run=False, quiet=True)
    d.advance(due); d.snapshot("coincident_timer_fall")
    s.expect("timeout classification retained unknown while output remains inhibited", d.channels[0].timeout is None and d.guard_command is False)
    s.limitations.append("The 2ns exclusion is a diagnostic scenario choice, not a qualified DFF metastability aperture or propagation specification.")
    output.append(s)
    return [x.result() for x in output]

def stable_truth_checks() -> dict[str, Any]:
    count = 0
    allow_rows = 0
    safe_rows = 0
    # All independent stable factors of the phase latch and ALLOW. We derive
    # outputs from separately stated equations, never by importing the producer.
    for health, armed, route, request, sec, run, quiet, rearm, block, timeout in itertools.product((False, True), repeat=10):
        safe = rearm and health and armed and route and quiet and not request and not run and not sec
        pre_n = health and armed and route and not (sec and not request)
        clr_n = not safe
        assert pre_n or clr_n
        allow = health and armed and route and not block and not timeout and request and sec and run
        assert not allow or (health and armed and route and request and sec and run and not block and not timeout)
        assert not safe or (pre_n and not request and not run and not sec and quiet)
        count += 1
        allow_rows += int(allow)
        safe_rows += int(safe)
    # Explicit timeout reset predicate excludes timeout itself and ARM/MON_SUP_OK
    # feedback. RAW_HEALTH includes separately restored monitor permissions.
    reset_rows = 0
    for reset, health, q0, q1, req0, req1, run0, run1, sec0, sec1 in itertools.product((False, True), repeat=10):
        clear = reset and health and q0 and q1 and not any((req0, req1, run0, run1, sec0, sec1))
        if clear:
            assert reset and health and q0 and q1
            reset_rows += 1
    return {"phase_stable_combinations": count, "allow_true_rows": allow_rows,
            "phase_safe_rearm_true_rows": safe_rows, "simultaneous_BLOCK_async_assertions": 0,
            "fault_reset_combinations": 1024, "fault_reset_true_rows": reset_rows}


def native_bindings() -> dict[str, Any]:
    """Pin-identity audit against KiCad's actual exported XML, not generated JSON.

    The exported producer manifest is not sufficient: compare its every pin to
    XML and then independently audit functional gate/clock contracts below.
    """
    import xml.etree.ElementTree as ET
    native = STAGE4 / "supervision"
    path = native / "supervision.xml"
    tree = ET.parse(path).getroot()
    components = {c.attrib["ref"]: c.findtext("value") for c in tree.findall("./components/comp")}
    pin_nets: dict[str, dict[str, str]] = {ref: {} for ref in components}
    for net in tree.findall("./nets/net"):
        for node in net.findall("node"):
            pin_nets[node.attrib["ref"]][node.attrib["pin"]] = net.attrib["name"].lstrip("/")
    manifest = json.loads((native / "connectivity.json").read_text(encoding="utf-8-sig"))
    compared = 0
    for p in manifest["parts"]:
        assert components[p["ref"]] == p["value"], p["ref"]
        for pin, net in p["nets"].items():
            if net is None:
                continue
            assert pin_nets[p["ref"]].get(pin) == net, (p["ref"], pin, net, pin_nets[p["ref"]].get(pin))
            compared += 1
    return {"xml_sha256_lf": text_sha(path), "manifest_sha256_lf": text_sha(native / "connectivity.json"),
            "components": len(components), "compared_actual_XML_pin_nets": compared,
            "functional_audit": native_functional_audit(components, pin_nets)}


def native_functional_audit(values: dict[str, str], nets: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Final checked net names/identities are populated after native generation."""
    # Audit actual fixed IC pin roles. The gate evaluator below uses these fixed
    # physical pins, independent of generated symbol pin names or descriptions.
    gates = []
    ff = []
    timer = []
    for ref, value in values.items():
        pn = nets[ref]
        if value.startswith("SN74LVC1G08"):
            gates.append((ref, "and", [pn["1"], pn["2"]], pn["4"]))
        elif value.startswith("SN74LVC1G11"):
            gates.append((ref, "and", [pn["1"], pn["3"], pn["6"]], pn["4"]))
        elif value.startswith("SN74LVC1G32"):
            gates.append((ref, "or", [pn["1"], pn["2"]], pn["4"]))
        elif value.startswith("SN74LVC1G04"):
            gates.append((ref, "not", [pn["2"]], pn["4"]))
        elif value.startswith("SN74LVC1G86"):
            gates.append((ref, "xor", [pn["1"], pn["2"]], pn["4"]))
        elif value.startswith("SN74LVC1G74"):
            ff.append((ref, pn))
        elif value.startswith("LTC6993"):
            timer.append((ref, pn))
    assert len(timer) == 2, "Exactly two secondary timers are expected"
    assert all(values[ref] == "LTC6993HS6-1#TRPBF" for ref, _ in timer), "Only the rising-edge non-retriggerable -1 grade is admitted"
    for i in range(2):
        assert values[f"R{800 + i}0"] == "195.4k 0.1%"
        assert nets[f"R{800 + i}0"] == {"1": f"CH{i}_SEC_SET", "2": "GND"}
    assert {pn["1"] for _, pn in timer} == {"CH0_REQUEST", "CH1_REQUEST"}, "Secondary TRIG must be raw request, never health-gated"
    # These names are part of the public native integration contract. DFF clock
    # and asynchronous-control checks reject equivalent-looking gated clocks.
    return audit_gate_contract(gates, ff, timer, nets)


def evaluate_gates(gates: list[tuple], seeds: dict[str, bool]) -> dict[str, bool]:
    env = dict(seeds)
    pending = list(gates)
    while pending:
        next_pending = []
        changed = False
        for ref, kind, inputs, output in pending:
            if all(n in env for n in inputs):
                args = [env[n] for n in inputs]
                value = all(args) if kind == "and" else any(args) if kind == "or" else not args[0] if kind == "not" else args[0] != args[1]
                if output in env:
                    assert env[output] == value, ("Conflicting driven logic", ref, output)
                env[output] = value
                changed = True
            else:
                next_pending.append((ref, kind, inputs, output))
        if not changed:
            break
        pending = next_pending
    return env

def audit_gate_contract(gates: list[tuple], ff: list[tuple], timer: list[tuple], nets: dict[str, dict[str, str]]) -> dict[str, Any]:
    by_q = {pn["5"]: (ref, pn) for ref, pn in ff}
    required_ff = {
        "SUP_ARMED": {"1": "SUP_REARM", "2": "SAFE_IDLE", "6": "ARM_CLR_N", "7": "SUP_3V3"},
        "WD_SEEN": {"1": "WDI_N", "2": "WD_ENOUT_OK", "6": "WD_SEEN_CLR_N", "7": "SUP_3V3"},
    }
    for i in range(2):
        required_ff[f"CH{i}_TIMEOUT"] = {"1": f"CH{i}_SEC_N", "2": f"CH{i}_TIMEOUT_D", "6": "TIMEOUT_CLR_N", "7": "SUP_3V3"}
        required_ff[f"CH{i}_BLOCK"] = {"1": "GND", "2": "GND", "6": f"CH{i}_BLOCK_CLR_N", "7": f"CH{i}_BLOCK_PRE_N"}
    for q, pins in required_ff.items():
        ref, actual = by_q[q]
        for pin, net in pins.items():
            assert actual[pin] == net, (ref, pin, net, actual[pin])
    outputs = {g[3] for g in gates}
    leaves = {n for _, _, inputs, _ in gates for n in inputs} - outputs

    def seeds(**overrides: bool) -> dict[str, bool]:
        result = {n: True for n in leaves}
        result.update({"GND": False, "AFEAGND": False, "SUP_3V3": True, "AFE_3V3": True,
                       "CH0_BLOCK": True, "CH1_BLOCK": True, "CH0_TIMEOUT": False,
                       "CH1_TIMEOUT": False, "SUP_ARMED": False,
                       "CH0_REQUEST": False, "CH1_REQUEST": False,
                       "CH0_RUN": False, "CH1_RUN": False,
                       "CH0_SEC_TIMER": False, "CH1_SEC_TIMER": False,
                       "CH0_PHASE_REARM": False, "CH1_PHASE_REARM": False,
                       "AFE_CONNECT": False, "AFE_ACQUIRE": False})
        result.update(overrides)
        return result

    rows = 0
    for i in range(2):
        prefix = f"CH{i}_"
        for h, arm, route, req, sec, run, quiet, rearm, block, timeout in itertools.product((False, True), repeat=10):
            initial = seeds(MON0_PERMIT=h, SUP_ARMED=arm)
            initial.update({prefix + "ROUTE_LOCKED": route, prefix + "REQUEST": req,
                            prefix + "SEC_TIMER": sec, prefix + "RUN": run,
                            prefix + "QUIESCENT_OK": quiet, prefix + "PHASE_REARM": rearm,
                            prefix + "BLOCK": block, prefix + "TIMEOUT": timeout})
            env = evaluate_gates(gates, initial)
            safe = rearm and h and arm and route and quiet and not req and not run and not sec
            pre_n = h and arm and route and not (sec and not req)
            expected = h and arm and route and not block and not timeout and req and sec and run
            assert env[prefix + "ALLOW"] == expected, (i, initial, env[prefix + "ALLOW"])
            assert env[prefix + "BLOCK_PRE_N"] == pre_n
            assert env[prefix + "BLOCK_CLR_N"] == (not safe)
            assert env[prefix + "EXT_SUP_OK"] == (h and arm and not timeout)
            assert env[prefix + "TIMEOUT_D"] == (timeout or req)
            assert env[prefix + "SEC_N"] == (not sec)
            assert pre_n or not safe
            assert env["GLOBAL_GUARD_EN"] == expected
            rows += 1

    reset_rows = 0
    for reset, h, q0, q1, req0, req1, run0, run1, sec0, sec1 in itertools.product((False, True), repeat=10):
        env = evaluate_gates(gates, seeds(FAULT_RESET=reset, MON0_PERMIT=h,
             CH0_QUIESCENT_OK=q0, CH1_QUIESCENT_OK=q1, CH0_REQUEST=req0,
             CH1_REQUEST=req1, CH0_RUN=run0, CH1_RUN=run1, CH0_SEC_TIMER=sec0, CH1_SEC_TIMER=sec1))
        idle = h and q0 and q1 and not any((req0, req1, run0, run1, sec0, sec1))
        assert env["SAFE_IDLE"] == idle
        assert env["TIMEOUT_CLR_N"] == (not (reset and idle))
        reset_rows += 1

    health_rows = 0
    for host, blank, wd_seen, guard, pair0, pair1, mon0, mon1 in itertools.product((False, True), repeat=8):
        env = evaluate_gates(gates, seeds(SUP3_RAIL_OK=host, AFE_BLANK_OBS_OK=blank,
                WD_SEEN=wd_seen, GUARD_FAULT_N=guard, CH0_PAIR_HI_OK=pair0,
                CH1_PAIR_HI_OK=pair1, MON0_PERMIT=mon0, MON1_PERMIT=mon1))
        sense = host and blank and wd_seen and guard and pair0 and pair1
        assert env["SENSE_HEALTH"] == sense
        assert env["RAW_HEALTH"] == (sense and mon0 and mon1)
        assert env["CH0_MON_SUP_OK"] == sense and env["CH1_MON_SUP_OK"] == sense
        health_rows += 1

    blank_rows = 0
    blank_flags = [f"REC{i:02d}_{side}_OK" for i in range(16) for side in ("HI", "LO")] + ["REF_HI_OK", "REF_LO_OK"]
    for failed in [None, *blank_flags, "A3_RAIL_OK", "AP_RAIL_OK", "AN_RAIL_OK", "AFE_STARTUP_OK", "AFE_CONNECT", "AFE_ACQUIRE"]:
        initial = seeds()
        if failed is not None:
            initial[failed] = failed in ("AFE_CONNECT", "AFE_ACQUIRE")
        env = evaluate_gates(gates, initial)
        assert env["AFE_BLANK_LOCAL_OK"] == (failed is None), failed
        blank_rows += 1

    # Actual post-router series guard pad roles: S faces artificial body load;
    # D faces router, preserving source-side fault protection on external pads.
    guard_paths = []
    tuples = [("1", "16", "15"), ("12", "13", "14"), ("9", "8", "7"), ("4", "5", "6")]
    for index in range(18):
        ref = f"U{100 + index // 4}"
        sp, dp, enp = tuples[index % 4]
        tail = f"STIM{index:02d}" if index < 16 else f"RETURN{index - 16}"
        assert nets[ref][sp] == "BODY_" + tail
        assert nets[ref][dp] == "ROUTED_" + tail
        assert nets[ref][enp] == "GLOBAL_GUARD_EN"
        assert nets[ref]["10"] == "GUARD_FAULT_N"
        guard_paths.append({"ref": ref, "source_pad": sp, "drain_pad": dp, "enable_pad": enp, "functional_port": tail})
    assert nets["U710"]["6"] == "AFE_BLANK_OBS_OK" and nets["U710"]["11"] == "AFE_BLANK_LOCAL_OK"
    assert nets["U710"]["5"] == "AFE_RAIL_OBS_OK" and nets["U710"]["12"] == "AFE_RAIL_LOCAL_OK"
    return {"gate_pin_identity_source": "Fixed package pins from primary component tables; actual KiCad XML net names",
            "phase_gate_combinations": rows, "reset_gate_combinations": reset_rows,
            "health_startup_combinations": health_rows, "AFE_blank_single_fault_rows": blank_rows,
            "raw_clocks_and_async_controls_checked_DFFs": len(required_ff),
            "independent_raw_request_timer_inputs": len(timer), "body_facing_guard_paths": guard_paths,
            "physical_switch_position_or_gate_delay_proven": False}


def reproduce() -> dict[str, Any]:
    scenarios = cases()
    native = native_bindings()
    return {
        "schema": "scci_rh.stage4.supervision-control.v1", "date": "2026-10-14",
        "scope": "Finite valid-supply ideal event model and independent actual native XML gate/pin audit; artificial signals and loads only",
        "source_sha256_lf": text_sha(Path(__file__)),
        "assumptions": {
            "secondary_nominal_ns": SECONDARY_NS, "secondary_conservative_max_ns_analogue_allocation": SECONDARY_MAX_NS,
            "secondary_timers_are_different_devices_and_setting_resistors": True,
            "secondary_timer_family_or_shared_power_common_cause_excluded": False,
            "watchdog_latest_deadline_ns": WATCHDOG_MAX_NS,
            "event_timer_and_gate_delay_model": "Ideal instantaneous valid-supply state transitions; physical latencies separately declared by analog study",
            "request_timer_coincidence_diagnostic_exclusion_ns": COINCIDENCE_NS,
            "coincidence_exclusion_is_device_qualification": False,
            "illustrative_startup_qualification_time_is_a_guaranteed_RC_bound": False,
            "provisional_interphase_gap_ns": 200_000,
            "old_100us_gap_earned": False,
            "launch_requires_actual_qualified_quiet_and_secondary_low": True,
            "quiet_is_exact_zero_current": False,
            "physical_RHD_windows_prove_all_switches_open": False,
            "MON_SUP_OK_is_distinct_from_driver_EXT_SUP_OK": True,
            "independent_reference_fault_trip_implemented": False,
            "after_interruption_automatically_balance_or_resume": False,
            "logic_outside_operating_supply_is_simulated_safe": False,
            "biological_response_or_retained_learning_modelled": False,
        },
        "upstream_bindings": bind_upstream(), "native_audit": native,
        "stable_equation_audit": stable_truth_checks(),
        "summary": {"scenario_groups": len(scenarios), "assertions_passed": sum(len(x["checks"]) for x in scenarios),
                    "state_snapshots": sum(len(x["history"]) for x in scenarios),
                    "primary_stuck_timer_secondary_cutoff": "CONDITIONAL_PASS",
                    "dual_timer_stuck_high": "UNPROTECTED_WITNESS_PRESERVED",
                    "welded_AFE_or_guard_switch": "UNPROTECTED_WITNESS_PRESERVED",
                    "common_supply_fault_outside_valid_logic": "UNKNOWN_PHYSICAL_STATE",
                    "zero_fault_current_or_4_percent_dose_claim_earned": False},
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-results", action="store_true", help="Explicitly refresh deterministic saved results after intentional reviewed changes")
    mode.add_argument("--check", action="store_true", help="Read-only deterministic reproduction and saved-result comparison (default)")
    args = parser.parse_args()
    actual = reproduce()
    if args.write_results:
        RESULTS.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    else:
        expected = json.loads(RESULTS.read_text(encoding="utf-8"))
        assert expected == actual, "Saved supervision results differ from deterministic read-only reproduction"
    print(json.dumps({"status": "PASS", "mode": "write" if args.write_results else "read_only_check", **actual["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
