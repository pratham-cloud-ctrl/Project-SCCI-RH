"""Finite two-source contact-router ownership and commit study.

This is an ideal stable-Boolean/event study, not a propagation, analogue-switch,
readback-authenticity, or biological model. Default/--check does not write files.
Only --write-results refreshes the deterministic saved result.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
RESULTS = HERE / "route-results.json"
QUALIFIERS = (
    "reset_ready", "rails_qualified", "monitor0_ok", "monitor1_ok",
    "afe_blanked", "watchdog_ok",
)


def sha_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bank_commands(addresses: tuple[int, int], wants: tuple[bool, bool], *,
                  base_good: bool, block: bool, commit: bool) -> tuple[tuple[bool, bool], tuple[bool, bool]]:
    """Gate-form router: two 8:1 banks/source, one high address bank bit."""
    a0, a1 = addresses
    same = all(((a0 >> bit) & 1) == ((a1 >> bit) & 1) for bit in range(4))
    conflict = wants[0] and wants[1] and same
    common = base_good and not block and not commit and not conflict
    answer = []
    for source in range(2):
        route = common and wants[source]
        high = bool((addresses[source] >> 3) & 1)
        answer.append((route and not high, route and high))
    return tuple(answer)  # type: ignore[return-value]


def ownership_oracle(addresses: tuple[int, int], wants: tuple[bool, bool], *,
                     base_good: bool, block: bool, commit: bool) -> tuple[frozenset[int], frozenset[int]]:
    """Independent set allocation; does not decode bank bits or mux equations."""
    requested = tuple(frozenset({addresses[s]}) if wants[s] else frozenset() for s in range(2))
    if requested[0].intersection(requested[1]):
        return (frozenset(), frozenset())
    if not base_good or block or commit:
        return (frozenset(), frozenset())
    return requested  # type: ignore[return-value]


def selected_contacts(addresses: tuple[int, int], banks: tuple[tuple[bool, bool], tuple[bool, bool]]) -> tuple[frozenset[int], frozenset[int]]:
    return tuple(frozenset(bank * 8 + (addresses[s] & 7) for bank in range(2) if banks[s][bank]) for s in range(2))  # type: ignore[return-value]


@dataclass
class Router:
    """Unconditional COMMIT clock, with a quiet-qualified D-input hold mux.

    Ordering is exact only for the separated events in these histories. There is
    no attempt to represent clock/data setup/hold, asynchronous clear recovery,
    hazards, mux break-before-make time, or terminal-current interruption tails.
    """

    name: str = "router"
    reset_ready: bool = False
    rails_qualified: bool = True
    monitor0_ok: bool = True
    monitor1_ok: bool = True
    afe_blanked: bool = True
    watchdog_ok: bool = True
    quiescent0_ok: bool = True
    quiescent1_ok: bool = True
    active_bits_verified: bool = False
    want0: bool = False
    want1: bool = False
    request0: bool = False
    request1: bool = False
    run0: bool = False
    run1: bool = False
    commit: bool = False
    rearm: bool = False
    logic_valid: bool = True
    shifted: tuple[int, int] = (0, 0)
    active: tuple[int, int] = (0, 0)
    valid: bool = False
    commit_seen: bool = False
    readback_seen: bool = False
    active_valid: bool = False
    commit_epoch: int = 0
    verified_epoch: int | None = None
    external_readback: tuple[int, int] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.record("startup_reset_asserted")

    @property
    def base_good(self) -> bool:
        return all(getattr(self, key) for key in QUALIFIERS)

    @property
    def quiet_safe(self) -> bool:
        return bool(self.base_good and self.quiescent0_ok and self.quiescent1_ok and not any((
            self.want0, self.want1, self.request0, self.request1, self.run0, self.run1,
        )))

    @property
    def conflict(self) -> bool:
        return self.want0 and self.want1 and self.active[0] == self.active[1]

    @property
    def fresh_external_check(self) -> bool:
        return bool(self.readback_seen and self.active_valid and
                    self.verified_epoch == self.commit_epoch and self.external_readback == self.active)

    @property
    def block(self) -> bool:
        return not self.valid

    @property
    def banks(self) -> tuple[tuple[bool, bool], tuple[bool, bool]] | None:
        if not self.logic_valid:
            return None
        return bank_commands(self.active, (self.want0, self.want1),
                             base_good=self.base_good, block=self.block, commit=self.commit)

    @property
    def locked(self) -> tuple[bool, bool] | None:
        if self.banks is None:
            return None
        return tuple(any(bank) for bank in self.banks)  # type: ignore[return-value]

    def record(self, label: str) -> None:
        self.history.append({
            "event": label, "shifted_addresses": list(self.shifted),
            "active_addresses": list(self.active) if self.logic_valid else None,
            "active_valid": self.active_valid if self.logic_valid else None,
            "want": [self.want0, self.want1], "request": [self.request0, self.request1],
            "run_observed": [self.run0, self.run1], "commit": self.commit,
            "rearm": self.rearm, "base_good": self.base_good,
            "quiet_safe": self.quiet_safe, "conflict": self.conflict,
            "block": self.block if self.logic_valid else None,
            "commit_seen": self.commit_seen if self.logic_valid else None,
            "readback_seen": self.readback_seen if self.logic_valid else None,
            "active_bits_verified_input": self.active_bits_verified,
            "bank_commands": None if self.banks is None else [list(bank) for bank in self.banks],
            "route_locked": None if self.locked is None else list(self.locked),
            "commit_epoch": self.commit_epoch, "verified_epoch": self.verified_epoch,
            "fresh_external_address_check": self.fresh_external_check,
            "qualifiers": {key: getattr(self, key) for key in QUALIFIERS},
            "quiescent_observed": [self.quiescent0_ok, self.quiescent1_ok], "logic_valid": self.logic_valid,
        })

    def event(self, label: str, **inputs: Any) -> None:
        old_commit = self.commit
        old_rearm = self.rearm
        old_ack = self.active_bits_verified
        old_valid = self.logic_valid
        for key, value in inputs.items():
            if key == "shifted":
                if len(value) != 2 or any(not 0 <= int(a) < 16 for a in value):
                    raise ValueError("Two four-bit shifted addresses required")
                self.shifted = tuple(int(a) for a in value)  # type: ignore[assignment]
            elif key in {*QUALIFIERS, "quiescent0_ok", "quiescent1_ok", "active_bits_verified", "want0", "want1", "request0", "request1", "run0", "run1", "commit", "rearm", "logic_valid"}:
                setattr(self, key, bool(value))
            else:
                raise ValueError(f"Unknown router input {key}")
        if not self.logic_valid:
            self.record(label)
            return
        if not old_valid:
            if self.reset_ready:
                raise AssertionError("Logic recovery requires external reset asserted")
            self.active = (0, 0)
            self.active_valid = False
            self.verified_epoch = None
            self.external_readback = None
            self.valid = False
            self.commit_seen = False
            self.readback_seen = False
        if not self.reset_ready:
            self.active = (0, 0)
            self.active_valid = False
            self.verified_epoch = None
            self.external_readback = None
        if self.commit and not old_commit:
            self.commit_epoch += 1
            # Clock is the raw COMMIT edge. The D input is a hold mux; a returning
            # health level cannot generate a new active-register clock.
            if self.quiet_safe:
                self.active = self.shifted
                self.active_valid = True
            self.commit_seen = self.quiet_safe
        if not self.base_good:
            self.commit_seen = False
        if not self.base_good or self.commit:
            self.readback_seen = False
        elif self.active_bits_verified and not old_ack:
            self.readback_seen = self.commit_seen
        if not self.base_good or self.commit or self.conflict:
            self.valid = False
        elif self.rearm and not old_rearm:
            self.valid = self.commit_seen and self.readback_seen and self.quiet_safe
        self.record(label)

    def verify_active(self, label: str, readback: tuple[int, int] | None,
                      *, epoch: int | None = None) -> None:
        """External protocol oracle, not an implemented silicon comparator."""
        self.external_readback = readback
        self.verified_epoch = self.commit_epoch if epoch is None else epoch
        self.event(label, active_bits_verified=(readback == self.active and self.active_valid and
                                               self.verified_epoch == self.commit_epoch))

    def configure(self, addresses: tuple[int, int] = (2, 11)) -> None:
        self.event("qualified_reset_release", reset_ready=True)
        self.event("shift_payload_only", shifted=addresses, active_bits_verified=False)
        self.event("explicit_quiet_commit_rising", commit=True)
        self.event("commit_released", commit=False)
        self.verify_active("fresh_active_Q_readback_compared", addresses)
        self.event("explicit_separate_rearm_rising", rearm=True)
        self.event("rearm_released_before_route_enable", rearm=False)


class Scenario:
    def __init__(self, identifier: str, title: str) -> None:
        self.identifier = identifier
        self.title = title
        self.routers: list[Router] = []
        self.checks: list[dict[str, Any]] = []
        self.notes: list[str] = []

    def router(self, *, configured: bool = False, addresses: tuple[int, int] = (2, 11)) -> Router:
        router = Router(name=f"{self.identifier}_{len(self.routers)}")
        self.routers.append(router)
        if configured:
            router.configure(addresses)
        return router

    def expect(self, text: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(f"{self.identifier}: {text}")
        self.checks.append({"assertion": text, "pass": True})

    def result(self) -> dict[str, Any]:
        return {"id": self.identifier, "title": self.title, "checks": self.checks,
                "notes": self.notes, "routers": [{"name": r.name, "history": r.history} for r in self.routers]}


def exhaustive_checks() -> dict[str, Any]:
    truth_rows = []
    conflicts = 0
    for a0, a1, w0, w1, good, block, commit in itertools.product(range(16), range(16), (False, True), (False, True), (False, True), (False, True), (False, True)):
        addresses, wants = (a0, a1), (w0, w1)
        banks = bank_commands(addresses, wants, base_good=good, block=block, commit=commit)
        selected = selected_contacts(addresses, banks)
        expected = ownership_oracle(addresses, wants, base_good=good, block=block, commit=commit)
        if selected != expected or any(sum(bank) > 1 for bank in banks):
            raise AssertionError("Mux-bank equations disagree with independent contact-ownership oracle")
        if w0 and w1 and a0 == a1:
            conflicts += 1
            if any(any(bank) for bank in banks):
                raise AssertionError("Same-contact demand must inhibit both sources")
        truth_rows.append([a0, a1, int(w0), int(w1), int(good), int(block), int(commit), [[int(x) for x in b] for b in banks]])

    commit_rows = []
    # Every current/next address pair, both quiet states: explicit clock with a
    # D hold mux versus an independent before/after register-state rule.
    for old0, old1, next0, next1, quiet in itertools.product(range(16), range(16), range(16), range(16), (False, True)):
        old, next_address = (old0, old1), (next0, next1)
        d_bits = tuple(((next_address[s] >> bit) & 1) if quiet else ((old[s] >> bit) & 1) for s in range(2) for bit in range(4))
        captured = tuple(sum(d_bits[s * 4 + bit] << bit for bit in range(4)) for s in range(2))
        expected = next_address if quiet else old
        if captured != expected:
            raise AssertionError("D-input hold mux does not preserve inadmissible commit")
        commit_rows.append([old0, old1, next0, next1, int(quiet), *captured])

    qualification_rows = []
    names = QUALIFIERS + (
        "quiescent0_ok", "quiescent1_ok", "want0", "want1", "request0", "request1", "run0", "run1",
    )
    for values in itertools.product((False, True), repeat=len(names)):
        signals = dict(zip(names, values))
        expected = all(signals[key] for key in names[:8]) and not any(signals[key] for key in names[8:])
        router = Router(**signals)
        if router.quiet_safe != expected:
            raise AssertionError("Commit qualification differs from independent all-required/no-activity oracle")
        qualification_rows.append([*[int(x) for x in values], int(expected)])
    return {
        "route_truth_rows": len(truth_rows), "same_contact_demand_rows_all_inhibited": conflicts,
        "route_truth_sha256": sha_json(truth_rows), "active_register_commit_rows": len(commit_rows),
        "active_register_commit_sha256": sha_json(commit_rows),
        "quiet_qualification_input_names": list(names), "quiet_qualification_rows": len(qualification_rows),
        "quiet_qualification_sha256": sha_json(qualification_rows),
        "quiet_admitted_rows": sum(row[-1] for row in qualification_rows),
        "independent_oracle_disagreements": 0,
    }


def native_export_checks() -> dict[str, Any]:
    """Read the exported KiCad XML, not the builder's Boolean implementation.

    Manufacturer package pin roles are encoded here independently of local
    symbol pin names. Every exported connection is first compared with the
    reviewable connectivity table; stable gate outputs are then independently
    evaluated against this study's ownership and quiet-admission oracles.
    """
    native = HERE.parent / "contact-router"
    exported = ET.parse(native / "contact_router.xml").getroot()
    connectivity = json.loads((native / "connectivity.json").read_text(encoding="utf-8"))
    values = {item.attrib["ref"]: item.findtext("value") for item in exported.findall("./components/comp")}
    pins: dict[str, dict[str, str]] = {ref: {} for ref in values}
    for net in exported.findall("./nets/net"):
        name = net.attrib["name"].split("/")[-1]
        for node in net.findall("node"):
            pins[node.attrib["ref"]][node.attrib["pin"]] = name
    checked = 0
    for part in connectivity["parts"]:
        if values.get(part["ref"]) != part["value"]:
            raise AssertionError("Exported component value differs from connectivity table")
        for pin, net in part["nets"].items():
            if net is not None:
                checked += 1
                if pins[part["ref"]].get(str(pin)) != net:
                    raise AssertionError(f"Exported connection differs: {part['ref']}.{pin}")

    rules = {
        "SN74LVC1G08": (("1", "2"), "4", "and"),
        "SN74LVC1G11": (("1", "3", "6"), "4", "and"),
        "SN74LVC1G32": (("1", "2"), "4", "or"),
        "SN74LVC1G86": (("1", "2"), "4", "xor"),
        "SN74LVC1G04": (("2",), "4", "not"),
    }
    gates = []
    for ref, value in values.items():
        for prefix, (inputs, out, operation) in rules.items():
            if value and value.startswith(prefix):
                gates.append((tuple(pins[ref][pin] for pin in inputs), pins[ref][out], operation))

    def evaluate(inputs: dict[str, bool]) -> dict[str, bool]:
        state = {"GND": False, "VDD_3V3": True, **inputs}
        pending = list(gates)
        while pending:
            remaining = []
            for names, out, operation in pending:
                if not all(name in state for name in names):
                    remaining.append((names, out, operation))
                    continue
                args = [state[name] for name in names]
                state[out] = (all(args) if operation == "and" else any(args) if operation == "or"
                              else args[0] != args[1] if operation == "xor" else not args[0])
            if len(remaining) == len(pending):
                raise AssertionError(f"Native gate graph has unresolved inputs: {remaining[:2]}")
            pending = remaining
        return state

    # All eleven clocks/async controls are checked at their manufacturer pin
    # numbers; no local symbol label can redefine the pin's role.
    ffs = [(ref, pins[ref]) for ref, value in values.items() if value and value.startswith("SN74LVC1G74")]
    if len(ffs) != 11:
        raise AssertionError("Expected eight active-address and three handshake flip-flops")
    for ref, pinmap in ffs:
        q = pinmap["5"]
        if q.startswith("CH") and "_ADDR" in q:
            expected = {"1": "ROUTE_COMMIT", "2": q.replace("_ADDR", "_ADDR_D"), "6": "RESET_READY"}
        elif q == "COMMIT_SEEN":
            expected = {"1": "ROUTE_COMMIT", "2": "QUIET_SAFE", "6": "BASE_HEALTH"}
        elif q == "READBACK_SEEN":
            expected = {"1": "ROUTE_ACTIVE_BITS_VERIFIED", "2": "COMMIT_SEEN", "6": "ACK_CLR_N"}
        elif q == "ROUTE_VALID":
            expected = {"1": "ROUTE_REARM", "2": "REARM_D", "6": "VALID_CLR_N"}
        else:
            raise AssertionError(f"Unexpected native flip-flop Q {q}")
        expected |= {"4": "GND", "7": "VDD_3V3", "8": "VDD_3V3"}
        if any(pinmap.get(pin) != net for pin, net in expected.items()):
            raise AssertionError(f"Native raw-clock/D/async-control contract differs at {ref}")

    selector_pins = (("2", "3", "4"), ("5", "6", "7"), ("11", "10", "9"), ("14", "13", "12"))
    selectors = [(ref, pins[ref]) for ref, value in values.items() if value and value.startswith("SN74LVC157A")]
    if len(selectors) != 2:
        raise AssertionError("Expected one four-bit D-input selector per source")
    for ref, pinmap in selectors:
        if any(pinmap.get(pin) != net for pin, net in {"1": "QUIET_SAFE", "15": "GND", "16": "VDD_3V3", "8": "GND"}.items()):
            raise AssertionError(f"Native D-input selector control differs at {ref}")
        for bit, (a, b, y) in enumerate(selector_pins):
            source = pinmap[a].split("_", 1)[0]
            if (pinmap[a], pinmap[b], pinmap[y]) != (f"{source}_ADDR{bit}", f"{source}_PENDING{bit}", f"{source}_ADDR_D{bit}"):
                raise AssertionError(f"Native active/shifted/held D selector wiring differs at {ref} bit {bit}")

    common = {"RESET_READY": True, "RAILS_QUALIFIED": True, "WATCHDOG_OK": True,
              "AFE_ISOLATED_READY": True, "CH0_MON_PERMIT": True, "CH1_MON_PERMIT": True,
              "CH0_QUIESCENT_OK": True, "CH1_QUIESCENT_OK": True,
              "CH0_REQUEST": False, "CH1_REQUEST": False, "CH0_RUN": False, "CH1_RUN": False,
              "COMMIT_SEEN": True, "READBACK_SEEN": True}
    route_rows = 0
    for a0, a1, w0, w1, good, block, commit in itertools.product(range(16), range(16), (False, True), (False, True), (False, True), (False, True), (False, True)):
        inputs = {**common, "RAILS_QUALIFIED": good, "ROUTE_VALID": not block, "ROUTE_COMMIT": commit,
                  "CH0_WANT_ROUTE": w0, "CH1_WANT_ROUTE": w1}
        inputs |= {f"CH{s}_ADDR{bit}": bool((address >> bit) & 1) for s, address in enumerate((a0, a1)) for bit in range(4)}
        state = evaluate(inputs)
        banks = tuple(tuple(state[f"CH{s}_BANK{bank}_EN"] for bank in range(2)) for s in range(2))
        if selected_contacts((a0, a1), banks) != ownership_oracle((a0, a1), (w0, w1), base_good=good, block=block, commit=commit):
            raise AssertionError("Native exported gate truth differs from independent ownership oracle")
        if state["ACK_CLR_N"] != (good and not commit) or state["VALID_CLR_N"] != (good and not commit and not (w0 and w1 and a0 == a1)):
            raise AssertionError("Native asynchronous handshake clear equation differs")
        route_rows += 1
    mapping = {
        "reset_ready": "RESET_READY", "rails_qualified": "RAILS_QUALIFIED",
        "monitor0_ok": "CH0_MON_PERMIT", "monitor1_ok": "CH1_MON_PERMIT",
        "afe_blanked": "AFE_ISOLATED_READY", "watchdog_ok": "WATCHDOG_OK",
        "quiescent0_ok": "CH0_QUIESCENT_OK", "quiescent1_ok": "CH1_QUIESCENT_OK",
        "want0": "CH0_WANT_ROUTE", "want1": "CH1_WANT_ROUTE",
        "request0": "CH0_REQUEST", "request1": "CH1_REQUEST", "run0": "CH0_RUN", "run1": "CH1_RUN",
    }
    quiet_rows = 0
    for values_tuple in itertools.product((False, True), repeat=len(mapping)):
        values_by_name = dict(zip(mapping, values_tuple))
        inputs = {**common, "ROUTE_VALID": False, "ROUTE_COMMIT": False,
                  **{f"CH{s}_ADDR{bit}": False for s in range(2) for bit in range(4)},
                  **{mapping[name]: value for name, value in values_by_name.items()}}
        state = evaluate(inputs)
        expected = all(values_by_name[name] for name in tuple(mapping)[:8]) and not any(values_by_name[name] for name in tuple(mapping)[8:])
        if state["QUIET_SAFE"] != expected or state["REARM_D"] != expected:
            raise AssertionError("Native exported quiet/rearm gate truth differs from qualification oracle")
        quiet_rows += 1
    return {"native_export_connected_pins_checked": checked, "native_raw_clock_ffs_checked": len(ffs),
            "native_D_hold_selectors_checked": len(selectors), "native_ownership_truth_rows": route_rows,
            "native_quiet_truth_rows": quiet_rows, "native_export_oracle_disagreements": 0}


def scenarios() -> list[dict[str, Any]]:
    cases = []

    s = Scenario("startup", "Reset and request-high readiness recovery cannot start routing")
    r = s.router()
    r.event("request_present_during_reset", request0=True, want0=True)
    s.expect("Reset startup has no enabled bank", r.locked == (False, False))
    r.event("readiness_returns_without_commit_or_rearm", reset_ready=True, active_bits_verified=True)
    s.expect("Returning health does not create an active-register clock or permission", r.active == (0, 0) and r.block and r.locked == (False, False))
    r.event("inadmissible_rearm_request_high", rearm=True)
    s.expect("High request and route intent prevent rearm", r.block)
    cases.append(s)

    s = Scenario("two_distinct_routes", "Both sources route distinct contacts with fixed dedicated returns")
    r = s.router(configured=True)
    s.expect("Commit requires separate fresh readback and rearm before permission", not r.block and r.fresh_external_check)
    r.event("enable_two_distinct_routes", want0=True, want1=True)
    s.expect("Two routes admitted without priority", r.locked == (True, True))
    s.expect("Low and high contact banks decode addresses 2 and 11", r.banks == ((True, False), (False, True)))
    r.event("source0_phase1", request0=True, run0=True)
    s.expect("Current-phase command leaves routing fixed", r.active == (2, 11) and r.locked == (True, True))
    r.event("source0_interphase_gap", request0=False, run0=False)
    r.event("source0_phase2", request0=True, run0=True)
    r.event("source0_recovery", request0=False, run0=False)
    s.expect("Phase, gap and recovery retain both routes", all(h["active_addresses"] == [2, 11] for h in r.history[-4:]))
    cases.append(s)

    s = Scenario("same_contact", "Simultaneous demand for the same contact inhibits both sources")
    r = s.router(configured=True, addresses=(7, 7))
    r.event("both_want_same_contact", want0=True, want1=True)
    s.expect("Collision inhibits both banks without winner or priority", r.conflict and r.block and r.locked == (False, False))
    r.event("one_want_drops_after_collision", want1=False)
    s.expect("Collision resolution alone cannot automatically restart either source", not r.conflict and r.block and r.locked == (False, False))
    r.event("release_route_and_rearm", want0=False, rearm=True)
    r.event("release_rearm", rearm=False)
    r.event("only_one_source_now_wants_contact", want0=True)
    s.expect("Single-source ownership of equal stored addresses is admissible after explicit rearm", r.locked == (True, False))
    cases.append(s)

    s = Scenario("freeze_and_illegal_commit", "Commit during a phase, interphase gap or recovery holds active addresses and blocks output")
    for label, inputs in (
        ("phase", {"want0": True, "request0": True, "run0": True}),
        ("gap", {"want0": True}), ("recovery", {"want0": True, "quiescent0_ok": False}),
    ):
        r = s.router(configured=True)
        r.event(f"{label}_precondition", shifted=(5, 14), **inputs)
        r.event(f"illegal_commit_during_{label}", commit=True)
        s.expect(f"{label}: active address held despite raw COMMIT clock", r.active == (2, 11))
        s.expect(f"{label}: COMMIT inhibits both bank commands and consumes permission", r.block and r.locked == (False, False))
        r.event(f"{label}_commit_released", commit=False)
        s.expect(f"{label}: commit release cannot restart routing", r.block and r.locked == (False, False))
    s.notes.append("This stable-state hold result does not establish safe operation for COMMIT edges inside the actual DFF/mux setup/hold aperture.")
    cases.append(s)

    s = Scenario("every_commit_guard", "Each independent qualification or nonquiet observation rejects a commit")
    guards = [(key, False) for key in QUALIFIERS] + [
        ("quiescent0_ok", False), ("quiescent1_ok", False), ("want0", True), ("want1", True),
        ("request0", True), ("request1", True), ("run0", True), ("run1", True),
    ]
    for key, bad in guards:
        r = s.router(configured=True)
        r.event(f"inject_{key}", shifted=(9, 4), **{key: bad})
        before = r.active
        r.event(f"commit_rejected_by_{key}", commit=True)
        # Asserted reset intentionally clears active address; it is not a
        # permitted address-update event and cannot create route permission.
        s.expect(f"{key}: COMMIT cannot replace the already held address", r.active == before)
        s.expect(f"{key}: bank outputs remain inhibited", r.locked == (False, False) and r.block)
    cases.append(s)

    s = Scenario("no_clock_from_health", "Health recovery with COMMIT held high cannot create a delayed address capture")
    r = s.router(configured=True)
    r.event("load_new_payload_and_make_watchdog_bad", shifted=(12, 3), watchdog_ok=False)
    r.event("commit_edge_while_unqualified", commit=True)
    r.event("watchdog_returns_while_commit_high", watchdog_ok=True)
    s.expect("Unconditional raw COMMIT clock has no new rising edge when health returns", r.active == (2, 11))
    s.expect("COMMIT high directly inhibits banks", r.locked == (False, False) and r.block)
    r.event("commit_returns_low", commit=False)
    s.expect("Commit falling edge cannot update positive-edge register", r.active == (2, 11))
    r.event("new_explicit_quiet_commit_edge", commit=True)
    s.expect("Only a new qualified raw COMMIT edge captures the payload", r.active == (12, 3))
    cases.append(s)

    s = Scenario("readback_missing_or_wrong", "Post-commit active-Q verification is required by the external admission protocol")
    for readback in (None, (3, 12)):
        r = s.router()
        r.event("qualified_startup", reset_ready=True)
        r.event("payload_shifted", shifted=(2, 11))
        r.event("quiet_commit", commit=True)
        r.event("commit_low", commit=False)
        r.verify_active("missing_or_wrong_active_Q_readback", readback)
        r.event("rearm_attempt_without_qualified_address", rearm=True)
        r.event("route_requested_without_qualified_address", rearm=False, want0=True)
        s.expect(f"{readback}: denied external address qualification leaves bank outputs off", r.block and r.locked == (False, False) and not r.fresh_external_check)
    s.notes.append("The comparison in verify_active is an explicit external protocol oracle. It is not silently credited to the router's gates or to a 595 serial return pin.")
    cases.append(s)

    s = Scenario("stale_readback", "A held-high verification cannot survive COMMIT or manufacture a fresh acknowledgement")
    r = s.router(configured=True)
    old_epoch = r.commit_epoch
    r.event("new_payload_ack_still_high", shifted=(4, 13))
    r.event("new_quiet_commit", commit=True)
    s.expect("COMMIT asynchronously clears readback-seen despite an old high ACK", not r.readback_seen)
    r.event("commit_low", commit=False)
    r.event("rearm_with_ack_held_high", rearm=True)
    s.expect("No new raw ACK edge means no rearm admission", r.block and not r.readback_seen)
    r.event("rearm_low", rearm=False)
    r.verify_active("stale_payload_and_old_epoch", (2, 11), epoch=old_epoch)
    r.event("rearm_with_stale_check_rejected", rearm=True)
    s.expect("Old epoch/readback cannot satisfy the external fresh-check protocol", r.block and not r.fresh_external_check)
    r.event("rearm_low", rearm=False)
    r.verify_active("fresh_correct_active_Q_check", (4, 13))
    r.event("rearm_after_fresh_ack_edge", rearm=True)
    s.expect("Fresh correct acknowledgement followed by new REARM admits", not r.block and r.fresh_external_check)
    s.notes.append("ACK is the raw external rising-edge clock. COMMIT clears READBACK_SEEN independently of the ACK level; no health-gated clock is used.")
    cases.append(s)

    s = Scenario("false_fresh_ack", "A genuinely new but erroneous ACK edge is an exposed external correctness boundary")
    r = s.router(configured=True)
    old_epoch = r.commit_epoch
    r.event("new_payload_ack_driven_low", shifted=(4, 13), active_bits_verified=False)
    r.event("new_quiet_commit", commit=True)
    r.event("commit_low", commit=False)
    r.external_readback = (2, 11)
    r.verified_epoch = old_epoch
    r.event("inject_fresh_ack_edge_despite_wrong_stale_bits", active_bits_verified=True)
    r.event("rearm_after_false_fresh_ack", rearm=True)
    r.event("request_route_after_false_qualification", rearm=False, want0=True)
    s.expect("Exposed witness: a fresh ACK edge can falsely claim that active bits were checked", r.locked == (True, False) and not r.fresh_external_check)
    s.notes.extend([
        "UNPROTECTED witness: the native circuit earns a fresh post-COMMIT ACK edge; it cannot prove that the external checker compared the correct bits or intended command.",
        "Reading all eight active FF Q bits establishes digital command state only. Neither that nor 595 QH-prime establishes analogue mux position, low on-resistance, or absence of a failed-on path.",
    ])
    cases.append(s)

    s = Scenario("faults_during_pulse", "Each shared permission loss interrupts and remains blocked after recovery")
    for key in QUALIFIERS:
        r = s.router(configured=True)
        r.event("both_sources_active", want0=True, want1=True, request0=True, run0=True, request1=True, run1=True)
        r.event(f"{key}_drops_during_pulse", **{key: False})
        s.expect(f"{key}: bank commands interrupt immediately in ideal stable logic", r.locked == (False, False) and r.block)
        r.event(f"{key}_recovers_without_rearm", **{key: True})
        s.expect(f"{key}: permission recovery cannot resume an existing phase", r.locked == (False, False) and r.block)
    s.notes.append("Actual current continues through parasitic, fixed-return and failed-switch paths; this study provides no analogue interruption latency or zero-charge result.")
    cases.append(s)

    s = Scenario("host_freeze_watchdog", "Powered host freeze requires independent watchdog observation")
    r = s.router(configured=True)
    r.event("host_freezes_with_route_intent_and_request_high", want0=True, request0=True, run0=True)
    s.expect("Exposed witness: a router is not a pulse timer or host watchdog", r.locked == (True, False))
    r.event("independent_watchdog_removes_permission", watchdog_ok=False)
    s.expect("Watchdog loss removes bank enables and consumes admission", r.locked == (False, False) and r.block)
    r.event("watchdog_returns_host_command_still_high", watchdog_ok=True)
    s.expect("Watchdog recovery cannot restart route", r.locked == (False, False) and r.block)
    s.notes.append("The watchdog is an external qualified port in this slice. Its implementation, timeout and ability to remain powered through host faults are not earned here.")
    cases.append(s)

    s = Scenario("shift_during_route", "Changing shift payload does not change active routes before COMMIT")
    r = s.router(configured=True)
    r.event("routes_enabled", want0=True, want1=True)
    for address in ((0, 15), (15, 0), (7, 7), (2, 11)):
        r.event("shift_register_changes_behind_active_register", shifted=address)
        s.expect(f"Shift payload {address} does not change active route", r.active == (2, 11) and r.locked == (True, True))
    cases.append(s)

    s = Scenario("logic_rail_invalid", "Logic-domain brownout makes state unqualified; reset and new verification are required")
    r = s.router(configured=True)
    r.event("active_route", want0=True)
    r.event("rails_fail_while_logic_still_valid", rails_qualified=False)
    s.expect("Qualified rail-drop input first inhibits banks", r.locked == (False, False) and r.block)
    r.event("logic_supply_leaves_operating_range", logic_valid=False)
    s.expect("No valid logic output is invented through brownout", r.banks is None and r.locked is None)
    r.event("logic_recovers_under_external_reset", logic_valid=True, reset_ready=False, want0=False, active_bits_verified=False, rails_qualified=True)
    r.event("startup_readiness_returns", reset_ready=True)
    s.expect("Readiness alone cannot restore old route permission", r.active == (0, 0) and not r.active_valid and r.block and r.locked == (False, False))
    cases.append(s)

    s = Scenario("rearm_not_commit", "Rearm cannot substitute for COMMIT or manufacture a new active address")
    r = s.router(configured=True)
    r.event("change_shift_payload_only", shifted=(14, 1))
    r.event("explicit_rearm_without_commit", rearm=True)
    r.event("release_rearm_enable_route", rearm=False, want0=True)
    s.expect("Rearm is not an active-register clock", r.active == (2, 11))
    s.expect("Router continues using previously verified active command", r.locked == (True, False) and r.fresh_external_check)
    s.notes.append("If firmware intended the shifted rather than active address, this is a command/protocol error. The physical active-Q readback must be compared against the intended route before enabling it.")
    cases.append(s)

    s = Scenario("commit_ack_order", "Release, settle, COMMIT, active-Q check, separate rearm, then route enable")
    r = s.router(configured=True)
    r.event("both_routes_in_use", want0=True, want1=True)
    r.event("release_both_route_intents", want0=False, want1=False, quiescent0_ok=False, quiescent1_ok=False)
    r.event("observe_settled_quiescent_current", quiescent0_ok=True, quiescent1_ok=True)
    r.event("preload_next_payload_and_clear_check", shifted=(15, 8), active_bits_verified=False)
    r.event("quiet_commit", commit=True)
    s.expect("COMMIT captures intended new addresses but cannot itself arm output", r.active == (15, 8) and r.block and r.locked == (False, False))
    r.event("commit_released", commit=False)
    r.verify_active("fresh_active_Q_check", (15, 8))
    s.expect("Fresh address check does not automatically clear block", r.block and r.locked == (False, False))
    r.event("separate_rearm_rising", rearm=True)
    r.event("rearm_released", rearm=False)
    r.event("route_enable_after_settling", want0=True, want1=True)
    s.expect("Only separate rearm permits the newly committed routes", r.locked == (True, True) and r.fresh_external_check)
    cases.append(s)

    return [case.result() for case in cases]


def reproduce() -> dict[str, Any]:
    exhaustive = exhaustive_checks()
    native = native_export_checks()
    histories = scenarios()
    return {
        "schema": "scci_rh.stage4.contact-router-control-contract.v1",
        "scope": "Finite stable ideal-Boolean/address/ownership study; digital concept only",
        "source_sha256_normalized_lf": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "contract": "docs/stage4/contact-router-control-contract.md",
        "assumptions": {
            "sources": 2, "shared_selectable_contacts": 16, "dedicated_fixed_returns": 2,
            "muxes": "Four TMUX6208 8:1 banks, two per source, restricted 24 V driver slice",
            "active_address_bits_per_source": 4,
            "address_capture": "Raw unconditional positive COMMIT clock; quiet-qualified D-input hold mux",
            "want_held_through_phases_gap_recovery": True,
            "quiet_observation_external": True,
            "fresh_ack_edge_latched_in_native_logic": True,
            "address_check_correctness_external": True,
            "qualifier_truth_external": True,
            "logic_reset_external": True,
            "event_setup_hold_and_gate_skew_resolved": False,
            "analogue_switch_position_readback": False,
            "off_means_zero_leakage_or_terminal_isolation": False,
        },
        "summary": {
            **exhaustive,
            **native,
            "scenario_groups": len(histories),
            "router_histories": sum(len(s["routers"]) for s in histories),
            "state_snapshots": sum(len(r["history"]) for s in histories for r in s["routers"]),
            "assertions_passed": sum(len(s["checks"]) for s in histories),
            "stale_high_ack_through_commit": "REJECTED_UNTIL_NEW_RAW_ACK_RISING_EDGE",
            "false_fresh_ack_correctness": "UNPROTECTED_TRUST_BOUNDARY",
            "host_freeze_without_watchdog_loss": "UNPROTECTED_BY_ROUTER_ALONE",
            "physical_gate_or_mux_timing_verified": False,
        },
        "scenarios": histories,
        "analogue_handoff": {
            "off_path_current": "Budget separately for both off-bank leakage, capacitance, charge injection, driver output/clamp paths and fixed dedicated return; off is not zero current.",
            "collision": "Inhibiting both bank commands is a conditional stable state, not proof that a failed-on analogue switch disconnects.",
            "commit_aperture": "Unqualified near-edge changes of quiet/data/commit are rejected, not assigned a favourable outcome.",
            "recording_recovery": "AFE_BLANKED is an observed external qualification; router logic does not establish RHD input voltage or filtered-neural recovery.",
            "charge_monitor": "Delivered current/charge permission is independent; address ownership alone cannot replace monitor or driver timeout permission.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-results", action="store_true", help="Explicitly regenerate saved results")
    mode.add_argument("--check", action="store_true", help="Read-only deterministic reproduction (default)")
    args = parser.parse_args()
    actual = reproduce()
    if args.write_results:
        RESULTS.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    else:
        expected = json.loads(RESULTS.read_text(encoding="utf-8"))
        if expected != actual:
            raise AssertionError("Saved route contract differs from deterministic reproduction")
    print(json.dumps({"status": "PASS", "mode": "write" if args.write_results else "read_only_check", **actual["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
