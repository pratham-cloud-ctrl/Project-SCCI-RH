"""Finite ideal-Boolean histories for the native current-driver permission contract.

This is an executable state/event model, not a device, gate-delay or biology model.
Default/--check is read-only; --write-results is the only artifact-writing mode.
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
RESULTS = HERE / "control-contract-results.json"
TIMER_NS = 225_024
APERTURE_NS = 2


@dataclass
class Driver:
    """One source, with separate timer/BLOCK/TIMEOUT/direction state.

    Events at different integer-nanosecond times are exactly ordered. The selected
    two-nanosecond coincidence exclusion is a declared diagnostic assumption; it
    is not a qualified clock/data aperture for the actual assembled circuit.
    """

    name: str = "source0"
    time_ns: int = 0
    request: bool = False
    phase_plus: bool = True
    phase_minus: bool = False
    rearm: bool = False
    mon_permit: bool = True
    ext_sup_ok: bool = True
    route_locked: bool = True
    reset_ready: bool = False
    rails_qualified: bool = True
    quiescent_ok: bool = True
    logic_valid: bool = True
    timer_ready: bool = True
    timer_stuck_high: bool = False
    timer_out: bool = False
    timer_due_ns: int | None = None
    block: bool = True
    timeout: bool | None = None
    latched_plus: bool = False
    safe_rearm: bool = False
    last_request_change_ns: int | None = None
    ambiguous_classification: bool = False
    unqualified_seen: bool = False
    timer_starts: int = 0
    ignored_busy_triggers: int = 0
    ignored_unready_triggers: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._settle()
        self.record("initial_reset_asserted")

    @property
    def base_good(self) -> bool:
        return bool(
            self.mon_permit
            and self.ext_sup_ok
            and self.route_locked
            and self.reset_ready
            and self.rails_qualified
            and (self.phase_plus != self.phase_minus)
        )

    @property
    def run(self) -> bool | None:
        if not self.logic_valid:
            return None
        return bool(
            self.request
            and self.timer_out
            and self.base_good
            and not self.block
            and self.timeout is False
        )

    def _settle(self, *, timer_fell: bool = False) -> None:
        if not self.logic_valid:
            self.unqualified_seen = True
            self.safe_rearm = False
            return
        safe = bool(
            self.rearm
            and self.base_good
            and not self.request
            and not self.timer_out
            and self.quiescent_ok
        )
        n_pre = self.base_good and not (self.timer_out and not self.request)
        n_clr = not safe
        if not n_pre and not n_clr:
            raise AssertionError("Stable asynchronous PRE/CLR conflict")
        if not n_pre:
            self.block = True
        elif not n_clr:
            self.block = False
        if safe:
            self.timeout = False
            self.ambiguous_classification = False
        elif timer_fell:
            near = (
                self.last_request_change_ns is not None
                and abs(self.time_ns - self.last_request_change_ns) <= APERTURE_NS
            )
            if near or self.ambiguous_classification:
                self.timeout = None
                self.ambiguous_classification = True
            elif self.request:
                self.timeout = True
            # When request is low, Q OR 0 retains the old timeout, including
            # unknown initial state. Qualified safe rearm resolves that state.
        if not self.reset_ready:
            self.latched_plus = False
        elif safe and not self.safe_rearm:
            self.latched_plus = self.phase_plus
        self.safe_rearm = safe

    def record(self, event: str) -> None:
        run = self.run
        self.history.append(
            {
                "event": event,
                "source": self.name,
                "time_ns": self.time_ns,
                "request": self.request,
                "rearm": self.rearm,
                "raw_phase": [self.phase_plus, self.phase_minus],
                "base_good": self.base_good,
                "safe_rearm": self.safe_rearm,
                "block": self.block if self.logic_valid else None,
                "timeout": self.timeout if self.logic_valid else None,
                "latched_plus": self.latched_plus if self.logic_valid else None,
                "timer_out": self.timer_out if self.logic_valid else None,
                "timer_due_ns": self.timer_due_ns,
                "run": run,
                "bridge_plus": None if run is None else run and self.latched_plus,
                "bridge_minus": None if run is None else run and not self.latched_plus,
                "logic_valid": self.logic_valid,
                "ambiguous_timeout_classification": self.ambiguous_classification,
            }
        )

    def advance(self, time_ns: int) -> None:
        if time_ns < self.time_ns:
            raise ValueError("Event time cannot move backward")
        if self.timer_due_ns is not None and self.timer_due_ns <= time_ns:
            self.time_ns = self.timer_due_ns
            self.timer_due_ns = None
            if self.timer_stuck_high:
                self.record("injected_timer_failure_prevents_expiry")
            else:
                self.timer_out = False
                self._settle(timer_fell=True)
                self.record("timer_expiry")
        self.time_ns = time_ns

    def event(self, time_ns: int, label: str, **inputs: bool) -> None:
        # An externally specified request transition exactly at expiry has no
        # established physical ordering. Mark it before advance processes expiry.
        if (
            "request" in inputs
            and inputs["request"] != self.request
            and self.timer_due_ns is not None
            and abs(time_ns - self.timer_due_ns) <= APERTURE_NS
        ):
            self.ambiguous_classification = True
        self.advance(time_ns)
        old_request = self.request
        old_logic_valid = self.logic_valid
        for key, value in inputs.items():
            if key not in {
                "request", "phase_plus", "phase_minus", "rearm", "mon_permit",
                "ext_sup_ok", "route_locked", "reset_ready", "rails_qualified",
                "quiescent_ok", "logic_valid", "timer_ready", "timer_stuck_high",
            }:
                raise ValueError(f"Unknown input {key}")
            setattr(self, key, bool(value))
        if self.request != old_request:
            self.last_request_change_ns = self.time_ns
        if not old_logic_valid and self.logic_valid:
            if self.reset_ready:
                raise AssertionError("Recovery requires externally asserted reset")
            self.timer_out = False
            self.timer_due_ns = None
            self.timeout = None
            self.safe_rearm = False
        if self.logic_valid and self.request and not old_request:
            if not self.timer_ready:
                self.ignored_unready_triggers += 1
            elif self.timer_out:
                self.ignored_busy_triggers += 1
            else:
                self.timer_out = True
                self.timer_due_ns = self.time_ns + TIMER_NS
                self.timer_starts += 1
        self._settle()
        if self.ambiguous_classification and not self.timer_out:
            self.timeout = None
        self.record(label)

    def admit(self, start_ns: int = 100, *, plus: bool = True) -> None:
        self.event(start_ns, "qualified_readiness_direction_preload",
                   reset_ready=True, phase_plus=plus, phase_minus=not plus)
        self.event(start_ns + 100, "explicit_quiescent_rearm", rearm=True)
        self.event(start_ns + 200, "rearm_released", rearm=False)


class Scenario:
    def __init__(self, identifier: str, title: str) -> None:
        self.identifier = identifier
        self.title = title
        self.checks: list[dict[str, Any]] = []
        self.drivers: list[Driver] = []
        self.notes: list[str] = []

    def driver(self, name: str = "source0") -> Driver:
        driver = Driver(name=name)
        self.drivers.append(driver)
        return driver

    def expect(self, name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(f"{self.identifier}: {name}")
        self.checks.append({"assertion": name, "pass": True})

    def result(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "checks": self.checks,
            "notes": self.notes,
            "sources": [
                {
                    "name": d.name,
                    "timer_starts": d.timer_starts,
                    "ignored_busy_triggers": d.ignored_busy_triggers,
                    "ignored_unready_triggers": d.ignored_unready_triggers,
                    "history": d.history,
                }
                for d in self.drivers
            ],
        }


def build_scenarios() -> list[dict[str, Any]]:
    cases: list[Scenario] = []

    s = Scenario("C01", "Startup is inhibited without assuming DFF power-on state")
    d = s.driver()
    s.expect("reset-low sets block and holds RUN low", d.block and d.run is False)
    s.expect("timeout is explicitly unknown until safe rearm", d.timeout is None)
    cases.append(s)

    s = Scenario("C02", "Held request through readiness return cannot gain admission")
    d = s.driver()
    d.event(1_000, "request_while_reset_asserted", request=True)
    due = d.timer_due_ns
    d.event(20_000, "readiness_returns_while_request_high", reset_ready=True)
    d.event(30_000, "attempt_rearm_while_request_high", rearm=True)
    s.expect("readiness did not create another trigger", d.timer_starts == 1 and d.timer_due_ns == due)
    s.expect("held request cannot clear block or RUN", d.block and not d.safe_rearm and d.run is False)
    d.advance(250_000)
    s.expect("held invalid request eventually records timeout", d.timeout is True and d.run is False)
    cases.append(s)

    s = Scenario("C03", "Qualified positive and negative phases end normally without false timeout")
    d = s.driver()
    d.admit()
    s.expect("safe rearm resolves latches and captures positive direction", not d.block and d.timeout is False and d.latched_plus)
    d.event(1_000, "positive_phase_start", request=True)
    s.expect("positive bridge admitted", d.run is True and d.latched_plus)
    d.event(201_000, "normal_200us_request_end", request=False)
    s.expect("normal completion consumes admission immediately", d.block and d.run is False and d.timeout is False)
    d.advance(250_000)
    s.expect("later timer expiry does not falsely record timeout", d.timeout is False and not d.timer_out)
    d.admit(260_000, plus=False)
    d.event(301_000, "negative_phase_start_after_rearm_and_gap", request=True)
    s.expect("next rearm captures negative direction", d.run is True and not d.latched_plus)
    d.event(501_000, "negative_normal_end", request=False)
    d.advance(550_000)
    s.expect("second normal phase also avoids false timeout", d.timeout is False and d.block)
    s.notes.append("The example includes a 100us all-off gap and explicit rearm after the first timer expires; physical current quiescence is an input assumption.")
    cases.append(s)

    s = Scenario("C04", "Early request drop consumes admission without an automatic balancing phase")
    d = s.driver()
    d.admit()
    d.event(1_000, "phase_start", request=True)
    d.event(51_000, "early_request_drop", request=False)
    s.expect("50us phase stops and remains consumed", d.run is False and d.block)
    d.advance(250_000)
    s.expect("no timeout or automatic new trigger follows", d.timeout is False and d.timer_starts == 1)
    cases.append(s)

    s = Scenario("C05", "Request low-high within one timer interval cannot reopen output")
    d = s.driver()
    d.admit()
    d.event(1_000, "phase_start", request=True)
    due = d.timer_due_ns
    d.event(51_000, "request_drop", request=False)
    d.event(61_000, "request_rerise_inside_old_window", request=True)
    s.expect("busy trigger is ignored without timer extension", d.ignored_busy_triggers == 1 and d.timer_due_ns == due)
    s.expect("consumed block prevents reopened RUN", d.block and d.run is False)
    d.event(71_000, "second_request_end", request=False)
    d.advance(250_000)
    s.expect("ended repeated request does not create a false timeout", d.timeout is False)
    cases.append(s)

    s = Scenario("C06", "New timer after expiry has no authority without explicit rearm")
    d = s.driver()
    d.admit()
    d.event(1_000, "phase_start", request=True)
    d.event(201_000, "normal_request_end", request=False)
    d.event(301_000, "new_raw_request_without_rearm", request=True)
    s.expect("raw request can start an internal second timer", d.timer_starts == 2 and d.timer_out)
    s.expect("second timer does not restore consumed admission", d.block and d.run is False)
    cases.append(s)

    s = Scenario("C07", "Stuck request is cut off by timer and sticky timeout")
    d = s.driver()
    d.admit()
    d.event(1_000, "phase_start_with_stuck_request", request=True)
    d.advance(226_024)
    s.expect("timer directly removes RUN at nominal expiry", not d.timer_out and d.run is False and d.timeout is True)
    d.event(240_000, "request_drops_after_timeout", request=False)
    d.event(250_000, "request_returns_without_rearm", request=True)
    s.expect("later request edge cannot clear sticky timeout", d.timeout is True and d.run is False)
    d.event(260_000, "late_request_drop", request=False)
    d.advance(500_000)
    s.expect("later timer ending with request low preserves timeout", d.timeout is True)
    d.event(510_000, "explicit_quiescent_rearm_after_timeout", rearm=True)
    d.event(510_100, "post_timeout_rearm_released", rearm=False)
    s.expect("only explicit safe rearm clears the timeout", d.timeout is False and not d.block)
    d.event(511_000, "fresh_request_after_explicit_rearm", request=True)
    s.expect("fresh request after rearm can be admitted", d.run is True)
    cases.append(s)

    s = Scenario("C08", "Request/timer coincidence leaves timeout classification unqualified")
    d = s.driver()
    d.admit()
    d.event(1_000, "phase_start", request=True)
    d.event(226_024, "request_drop_exactly_at_expiry", request=False)
    s.expect("timer gate still commands RUN low", d.run is False and not d.timer_out)
    s.expect("classification is unknown rather than favourable", d.timeout is None and d.ambiguous_classification)
    s.notes.append("This is a rejected classification trace; Boolean event ordering cannot resolve the actual setup/hold/metastability event.")
    cases.append(s)

    s = Scenario("C09", "Each permission drop consumes admission and recovery cannot resume")
    for port in ("mon_permit", "ext_sup_ok", "route_locked", "reset_ready", "rails_qualified"):
        d = s.driver(port)
        d.admit()
        d.event(1_000, "phase_start", request=True)
        d.event(51_000, f"{port}_drops", **{port: False})
        s.expect(f"{port} loss sets block and stops RUN", d.block and d.run is False)
        d.event(61_000, f"{port}_returns_while_request_high", **{port: True})
        s.expect(f"{port} recovery cannot reopen RUN", d.block and d.run is False)
    cases.append(s)

    s = Scenario("C10", "Both-high and both-low phase bits inhibit and consume admission")
    for bits in ((True, True), (False, False)):
        d = s.driver(f"invalid_{int(bits[0])}{int(bits[1])}")
        d.admit()
        d.event(1_000, "phase_start", request=True)
        d.event(51_000, "invalid_live_direction", phase_plus=bits[0], phase_minus=bits[1])
        s.expect(f"invalid {bits} drops BASE_GOOD and RUN", not d.base_good and d.block and d.run is False)
        d.event(61_000, "valid_bits_restored", phase_plus=True, phase_minus=False)
        s.expect(f"restored bits after {bits} do not resume", d.block and d.run is False)
    cases.append(s)

    s = Scenario("C11", "Valid live raw direction swap cannot reverse captured diagonal")
    d = s.driver()
    d.admit()
    d.event(1_000, "phase_start", request=True)
    d.event(51_000, "simultaneous_valid_raw_direction_swap", phase_plus=False, phase_minus=True)
    s.expect("captured positive direction remains active", d.run is True and d.latched_plus)
    s.expect("XOR does not diagnose a valid simultaneous swap", d.base_good and not d.block)
    s.notes.append("The raw swap violates the held-input contract; captured-direction stability is demonstrated, complete command-consistency protection is not.")
    cases.append(s)

    s = Scenario("C12", "Unsafe rearm never clears state; explicit qualified rearm does")
    for inhibit in ("request", "timer", "quiescence", "monitor", "supervision", "invalid_direction"):
        d = s.driver(inhibit)
        d.event(100, "readiness", reset_ready=True)
        if inhibit == "request":
            d.event(200, "request_high", request=True)
        elif inhibit == "timer":
            d.event(200, "trigger_while_blocked", request=True)
            d.event(300, "request_low_timer_still_high", request=False)
        elif inhibit == "quiescence":
            d.event(200, "current_not_quiescent", quiescent_ok=False)
        elif inhibit == "monitor":
            d.event(200, "monitor_fault", mon_permit=False)
        elif inhibit == "supervision":
            d.event(200, "supervision_not_ready", ext_sup_ok=False)
        else:
            d.event(200, "invalid_direction", phase_plus=True, phase_minus=True)
        d.event(400, "unsafe_rearm_attempt", rearm=True)
        s.expect(f"{inhibit} prevents latch clearance", not d.safe_rearm and d.block and d.run is False)
    d = s.driver("valid_explicit_rearm")
    d.admit()
    s.expect("qualified explicit rearm clears unknown timeout and block", not d.block and d.timeout is False)
    s.expect("driver rearm does not modify the monitor input", d.mon_permit is True)
    cases.append(s)

    s = Scenario("C13", "Two sources retain independent timer and rearm ownership")
    a, b = s.driver("source0"), s.driver("source1")
    a.admit()
    b.admit(100, plus=False)
    a.event(1_000, "source0_start", request=True)
    b.event(1_000, "source1_start", request=True)
    a.event(51_000, "source0_monitor_fault", mon_permit=False)
    b.event(61_000, "source1_still_running")
    s.expect("source0 fault does not interrupt independently permitted source1", a.run is False and b.run is True)
    b.event(201_000, "source1_normal_end", request=False)
    b.admit(260_000, plus=True)
    b.event(301_000, "source1_second_start", request=True)
    a.event(301_000, "source0_monitor_permission_returns", mon_permit=True)
    s.expect("source1 rearm cannot clear source0 consumed block", a.block and a.run is False and b.run is True)
    cases.append(s)

    s = Scenario("C14", "Brownout leaves model unqualified until external reset and rearm")
    d = s.driver()
    d.admit()
    d.event(1_000, "phase_start", request=True)
    d.event(51_000, "qualified_rail_warning_before_invalid_logic", rails_qualified=False, reset_ready=False)
    s.expect("qualified warning first inhibits output", d.block and d.run is False)
    d.event(52_000, "logic_supply_outside_operating_range", logic_valid=False)
    s.expect("out-of-range state is unknown, not falsely safe", d.run is None and d.unqualified_seen)
    d.event(101_000, "logic_recovers_with_external_reset_asserted", logic_valid=True, request=False)
    s.expect("recovery begins blocked with unknown timeout", d.block and d.run is False and d.timeout is None)
    d.event(102_000, "rails_and_startup_requalified", rails_qualified=True, reset_ready=True)
    s.expect("readiness alone does not rearm", d.block and d.run is False)
    d.event(103_000, "explicit_post_brownout_rearm", rearm=True)
    d.event(104_000, "post_brownout_rearm_released", rearm=False)
    s.expect("explicit safe rearm resolves control state", not d.block and d.timeout is False)
    s.notes.append("Timer/output/DFF behaviour during invalid supply is not simulated as valid hardware logic. External reset and timer-startup qualification are assumed on recovery.")
    cases.append(s)

    s = Scenario("C15", "Timer failure witness remains unprotected without external interruption")
    d = s.driver()
    d.admit()
    d.event(1_000, "phase_start_with_injected_timer_stuck_high", request=True, timer_stuck_high=True)
    d.advance(501_000)
    d.record("500us_after_start_without_timer_falling_edge")
    s.expect("stuck-high timer has no falling edge and no sticky timeout", d.timer_out and d.timeout is False)
    s.expect("driver alone permits a 500us held request under this injected fault", d.run is True)
    d.event(502_000, "external_watchdog_drops_supervision", ext_sup_ok=False)
    s.expect("external supervisor interruption stops RUN and sets block", d.run is False and d.block)
    d.event(503_000, "supervision_recovers", ext_sup_ok=True)
    s.expect("supervision recovery cannot resume", d.run is False and d.block)
    s.notes.extend([
        "UNPROTECTED witness: the native timer plus these latches cannot bound duration if timer OUT itself fails high and request remains high.",
        "SET-open is an unqualified analogue timer fault, not simulated as a vendor-established stuck-high transfer function. This injected stuck-high witness demonstrates why a reliable timeout is not credited for SET-open.",
        "An external watchdog is represented only by EXT_SUP_OK dropping; no watchdog circuit is implemented or validated by this study.",
        "Conditional bookkeeping: 3mA for 500us would be 1500nC; current regulation and actual delivered charge are outside this Boolean model.",
    ])
    cases.append(s)

    assert len(cases) == 15
    return [case.result() for case in cases]


def reproduce() -> dict[str, Any]:
    truth_rows = []
    for good, request, timer, quiet, rearm in itertools.product((False, True), repeat=5):
        safe = rearm and good and not request and not timer and quiet
        n_pre = good and not (timer and not request)
        n_clr = not safe
        assert n_pre or n_clr
        truth_rows.append({
            "base_good": good, "request": request, "timer_out": timer,
            "quiescent_ok": quiet, "rearm": rearm,
            "safe_rearm": safe, "n_block_pre": n_pre, "n_block_clr": n_clr,
            "simultaneous_assertion": False,
        })
    scenarios = build_scenarios()
    return {
        "schema": "scci_rh.stage4.driver-control-contract-study.v1",
        "scope": "Finite ideal-Boolean/event model; digital artificial-load concept only",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "contract": "docs/stage4/current-driver-control-contract.md",
        "assumptions": {
            "timer_nominal_ns": TIMER_NS,
            "timer_pulse_model": "Instantaneous positive non-retriggerable pulse; no gate or timer propagation model",
            "coincidence_exclusion_ns": APERTURE_NS,
            "coincidence_exclusion_status": "Declared diagnostic assumption, not a certified physical aperture",
            "explicit_rearm_precedes_request": True,
            "rearm_is_released_before_request": True,
            "direction_captured_on_safe_rearm": True,
            "reset_ready_low_through_qualified_startup": True,
            "quiescence_and_supervision_external": True,
            "physical_brownout_logic_modelled": False,
            "biological_effect_modelled": False,
        },
        "summary": {
            "scenario_groups": len(scenarios),
            "assertions_passed": sum(len(s["checks"]) for s in scenarios),
            "source_histories": sum(len(s["sources"]) for s in scenarios),
            "recorded_state_snapshots": sum(len(d["history"]) for s in scenarios for d in s["sources"]),
            "stable_async_combinations": len(truth_rows),
            "simultaneous_async_assertions": 0,
            "safe_rearm_truth_combinations": sum(row["safe_rearm"] for row in truth_rows),
            "timer_failure_protection": "UNPROTECTED_WITHOUT_EXTERNAL_INTERRUPTION",
            "physical_gate_timing_verified": False,
            "actual_circuit_or_hardware_verified": False,
        },
        "stable_async_truth_table": truth_rows,
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-results", action="store_true", help="Explicitly save reproduced finite results")
    mode.add_argument("--check", action="store_true", help="Reproduce and compare saved results without writing (default)")
    args = parser.parse_args()
    actual = reproduce()
    if args.write_results:
        RESULTS.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    else:
        expected = json.loads(RESULTS.read_text(encoding="utf-8"))
        if expected != actual:
            raise AssertionError("Saved control-contract results differ from deterministic reproduction")
    print(json.dumps({"status": "PASS", "mode": "write" if args.write_results else "read_only_check", **actual["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
