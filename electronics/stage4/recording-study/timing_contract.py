"""Finite isolated-SPI and recording/stimulation sequencing contract.

This standard-library model checks an explicit external-controller contract. It
does not simulate gate delays, diagnose an untagged ADC word, implement firmware,
or establish analogue recovery. Default/--check reproduces without writing.
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
RESULTS = HERE / "timing-results.json"
SLOT_NS = 5_000
FRAME_NS = 250_000
GUARD_NS = 5_000
CHANNELS = 16
WORDS = 19


def source_hash() -> str:
    data = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def spi_budget(clock_hz: int) -> dict[str, Any]:
    half = 1e9 / clock_hz / 2
    # Manufacturer limits plus separately identified SCCI_RH design allocations.
    forward_max, reverse_max, slave_miso, master_setup = 18, 18, 12, 19
    board_allocation, source_edge_allocation = 5, 10
    return {
        "clock_hz": clock_hz,
        "nominal_half_period_ns": half,
        "miso_forward_propagation_max_ns": forward_max,
        "miso_reverse_propagation_max_ns": reverse_max,
        "rhd_miso_valid_max_ns": slave_miso,
        "nrf_miso_setup_min_ns": master_setup,
        "scci_rh_board_uncertainty_allocation_ns": board_allocation,
        "scci_rh_source_clock_edge_allocation_ns": source_edge_allocation,
        "miso_margin_without_scci_rh_allocations_ns": half - forward_max - reverse_max - slave_miso - master_setup,
        "miso_margin_with_scci_rh_allocations_ns": half - forward_max - reverse_max - slave_miso - master_setup - board_allocation - source_edge_allocation,
        "mosi_master_valid_max_ns": 59,
        "same_direction_isolator_skew_max_ns": 6,
        "rhd_mosi_setup_min_ns": 10,
        "mosi_margin_with_scci_rh_allocations_ns": half - 59 - 6 - 10 - board_allocation - source_edge_allocation,
        "timing_admitted_under_allocations": half - forward_max - reverse_max - slave_miso - master_setup - board_allocation - source_edge_allocation > 0 and half - 59 - 6 - 10 - board_allocation - source_edge_allocation > 0,
    }


def schedule() -> list[dict[str, Any]]:
    rows = []
    for slot in range(WORDS):
        if slot < CHANNELS:
            command = f"CONVERT({slot})"
        elif slot == 16:
            command = "CONVERT(48)"
        else:
            command = "READ(63)"
        response_channel = slot - 2 if 2 <= slot <= 17 else None
        sampled_channel = slot - 1 if 1 <= slot <= 16 else None
        rows.append({
            "slot": slot,
            "controller_cs_assert_ns": slot * SLOT_NS,
            "first_controller_sclk_rise_ns": slot * SLOT_NS + 125,
            "last_controller_sclk_fall_ns": slot * SLOT_NS + 4_000,
            "controller_cs_release_ns": slot * SLOT_NS + 4_125,
            "command": command,
            "sampled_neural_channel_on_local_cs_fall": sampled_channel,
            "received_neural_channel": response_channel,
            "received_supply_observation": slot == 18,
            "received_discarded_previous_response": slot < 2,
        })
    return rows


def commissioning_ready(*, vref_age_ns: int, initialization_age_ns: int,
                        calibration_dummy_words: int, reg0: int,
                        reg1: int, calibrated: bool) -> bool:
    """Finite register/startup prerequisites; not a device initialization driver."""
    return (vref_age_ns >= 100_000 and initialization_age_ns >= 100_000
            and calibration_dummy_words >= 9 and reg0 == 0xDE
            and bool(reg1 & 0x40) and calibrated)


def decode_frame(*, word_count: int = WORDS, word_bits: int = 16,
                 expected_sequence: int = 7, received_sequence: int = 7,
                 expected_epoch: int = 3, received_epoch: int = 3,
                 spi_error: bool = False, known_stale: bool = False,
                 aperture_jitter_ns: float = 0, qualified: bool = True,
                 supplied_labels: list[int] | None = None) -> dict[str, Any]:
    """Conservative full-frame policy with observable metadata, not wire tags.

    supplied_labels is an independent model oracle for mapping tests. Real RHD
    conversion words have no such labels. Unknown replay of plausible raw codes
    therefore cannot be diagnosed by this function or credited as detected.
    """
    reasons = []
    if word_count != WORDS:
        reasons.append("word_count")
    if word_bits != 16:
        reasons.append("word_width")
    if received_sequence != expected_sequence:
        reasons.append("sequence")
    if received_epoch != expected_epoch:
        reasons.append("epoch")
    if spi_error:
        reasons.append("spi_error")
    if known_stale:
        reasons.append("known_stale")
    if abs(aperture_jitter_ns) > 125:
        reasons.append("aperture_jitter")
    if not qualified:
        reasons.append("acquisition_not_qualified")
    if supplied_labels is not None and supplied_labels != list(range(CHANNELS)):
        reasons.append("model_oracle_mapping_mismatch")
    return {"validity_mask": 0 if reasons else 0xFFFF, "reasons": reasons,
            "returned_channels": list(range(CHANNELS)) if not reasons else [],
            "wire_has_channel_or_frame_tag": False}


@dataclass
class Controller:
    """External ordered-controller witness, not an implemented hardware FSM."""

    time_ns: int = 0
    connect: bool = False
    record: bool = False
    rails_qualified: bool = False
    logic_valid: bool = True
    link_healthy: bool = True
    voltage_qualified: bool = False
    quiet: bool = False
    settled: bool = False
    filters_qualified: bool = False
    quiescent: bool = True
    driver_permissions: bool = True
    request: bool = False
    clamped_since_ns: int = 0
    disconnected_since_ns: int = 0
    connected_since_ns: int | None = None
    errors: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def select_acquire(self) -> bool | None:
        if not self.logic_valid:
            return None
        return self.connect and self.record and self.link_healthy

    @property
    def recording_valid(self) -> bool:
        return bool(self.select_acquire and self.rails_qualified and self.link_healthy
                    and self.voltage_qualified and self.quiet and self.settled
                    and self.filters_qualified and not self.request)

    @property
    def stim_contract_ready(self) -> bool:
        return bool(self.logic_valid and self.rails_qualified and self.link_healthy
                    and not self.connect and not self.record and self.quiescent
                    and self.driver_permissions
                    and self.time_ns - self.clamped_since_ns >= GUARD_NS
                    and self.time_ns - self.disconnected_since_ns >= GUARD_NS)

    def snapshot(self, label: str) -> None:
        self.history.append({"event": label, "time_ns": self.time_ns,
                             "connect_high": self.connect, "record_high": self.record,
                             "select_acquire": self.select_acquire,
                             "recording_valid": self.recording_valid,
                             "stim_contract_ready": self.stim_contract_ready,
                             "request": self.request, "logic_valid": self.logic_valid,
                             "rails_qualified": self.rails_qualified,
                             "link_healthy": self.link_healthy,
                             "voltage_qualified": self.voltage_qualified,
                             "quiet": self.quiet,
                             "quiescent": self.quiescent,
                             "driver_permissions": self.driver_permissions,
                             "settled": self.settled,
                             "filters_qualified": self.filters_qualified})

    def event(self, time_ns: int, label: str, **changes: bool) -> None:
        if time_ns < self.time_ns:
            raise ValueError("Time cannot run backwards")
        self.time_ns = time_ns
        old_connect, old_select = self.connect, self.select_acquire
        for key, value in changes.items():
            if key not in self.__dataclass_fields__ or key in {"time_ns", "history", "errors"}:
                raise ValueError(f"Unknown control input {key}")
            setattr(self, key, bool(value))
        # Default-LOW is credited only with operating receiving-side rails. A
        # brownout is explicitly unknown, not simulated as a working logic gate.
        if not self.link_healthy and self.logic_valid:
            self.connect = self.record = False
        if self.logic_valid and self.record and not self.connect:
            self.errors.append("invalid_01_command")
        if old_connect and not self.connect:
            if old_select is not False or self.time_ns - self.clamped_since_ns < GUARD_NS:
                self.errors.append("disconnect_without_qualified_clamp_guard")
            self.disconnected_since_ns = self.time_ns
            self.voltage_qualified = self.settled = self.filters_qualified = False
        elif self.connect and not old_connect:
            self.connected_since_ns = self.time_ns
            self.voltage_qualified = self.settled = self.filters_qualified = False
            if self.record or self.request or not self.quiescent:
                self.errors.append("connect_without_clamped_quiescent_state")
        new_select = self.select_acquire
        if old_select is True and new_select is False:
            self.clamped_since_ns = self.time_ns
            self.settled = self.filters_qualified = False
        elif old_select is False and new_select is True:
            # The analogue recovery and causal-filter support must subsequently
            # be qualified explicitly; switch release alone earns no samples.
            if (not self.voltage_qualified or not self.quiet or self.request
                    or self.connected_since_ns is None
                    or self.time_ns - self.connected_since_ns < GUARD_NS):
                self.errors.append("unclamp_without_voltage_quiet_connect_guard")
            self.settled = self.filters_qualified = False
        if not self.logic_valid or not self.rails_qualified or not self.link_healthy:
            self.voltage_qualified = self.settled = self.filters_qualified = False
        self.snapshot(label)

    def ask_stim(self, time_ns: int, label: str) -> bool:
        self.event(time_ns, label)
        allowed = self.stim_contract_ready
        if allowed:
            self.request = True
            self.snapshot("external_driver_request_admitted")
        else:
            self.errors.append("external_controller_rejected_stimulation")
        return allowed


def prepared() -> Controller:
    c = Controller()
    c.event(1_000, "rails_and_quiet_qualified", rails_qualified=True, quiet=True)
    c.event(10_000, "connect_while_clamped", connect=True)
    c.event(20_000, "protected_nodes_qualified", voltage_qualified=True)
    c.event(25_000, "release_clamp", record=True)
    c.event(50_000, "external_analogue_and_filter_qualification", settled=True, filters_qualified=True)
    assert c.recording_valid and not c.errors
    return c


def build_scenarios() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    def add(identifier: str, title: str, checks: dict[str, bool],
            controller: Controller | None = None, **extra: Any) -> None:
        for label, condition in checks.items():
            if not condition:
                raise AssertionError(f"{identifier}: {label}")
        cases.append({"id": identifier, "title": title,
                      "checks": [{"assertion": k, "pass": v} for k, v in checks.items()],
                      "history": [] if controller is None else controller.history,
                      "contract_errors": [] if controller is None else controller.errors,
                      **extra})

    fast, selected = spi_budget(8_000_000), spi_budget(4_000_000)
    add("T01", "Isolation requires an explicit Stage 2 SPI revision", {
        "8MHz fails MISO setup even before board allowances": fast["miso_margin_without_scci_rh_allocations_ns"] < 0,
        "4MHz passes declared MISO and MOSI allocations": selected["timing_admitted_under_allocations"],
        "95us burst fits 250us frame": WORDS * SLOT_NS < FRAME_NS,
        "provisional_cs_lead_clears20ns_minimum": 125 - 18 - 10 - 10 - 5 >= 20,
        "provisional_cs_hold_clears20ns_minimum": 125 - 18 - 10 - 5 >= 20,
        "provisional_cs_high_clears154ns_minimum": 875 - 7 - 10 - 5 >= 154,
    }, budgets=[fast, selected])

    rows = schedule()
    labels = [r["received_neural_channel"] for r in rows if r["received_neural_channel"] is not None]
    apertures = [r["controller_cs_assert_ns"] for r in rows if r["sampled_neural_channel_on_local_cs_fall"] is not None]
    add("T02", "Next-CS aperture and two-word response pipeline are distinct", {
        "sixteen neural responses are in slots2through17": labels == list(range(16)),
        "physical apertures occur on slots1through16": apertures == [i * SLOT_NS for i in range(1, 17)],
        "reference supply result is flushed in slot18": rows[18]["received_supply_observation"],
        "pairwise aperture span is75us": max(apertures) - min(apertures) == 75_000,
    })

    add("T03", "Unknown prior pipeline responses are discarded on each startup burst", {
        "first two responses never enter neural payload": all(rows[i]["received_discarded_previous_response"] for i in (0, 1)),
        "qualified burst labels are complete": decode_frame(supplied_labels=labels)["validity_mask"] == 0xFFFF,
        "startup analogue unqualified still invalidates entire frame": decode_frame(qualified=False)["validity_mask"] == 0,
    })

    bad_counts = [decode_frame(word_count=n) for n in (0, 1, 18, 20)]
    add("T04", "Incomplete or extra-word DMA bursts invalidate the full frame", {
        "all tested incorrect word counts invalidate": all(r["validity_mask"] == 0 for r in bad_counts),
        "byte-oriented incomplete words invalidate": decode_frame(word_bits=8)["validity_mask"] == 0,
    }, rejected_frames=bad_counts)

    add("T05", "Known stale metadata, SPI errors and channel mapping faults are rejected", {
        "stale epoch invalid": decode_frame(received_epoch=2)["validity_mask"] == 0,
        "stale sequence invalid": decode_frame(received_sequence=6)["validity_mask"] == 0,
        "known stale DMA buffer invalid": decode_frame(known_stale=True)["validity_mask"] == 0,
        "SPI error invalid": decode_frame(spi_error=True)["validity_mask"] == 0,
        "independent model detects one-slot mapping error": decode_frame(supplied_labels=labels[1:] + [0])["validity_mask"] == 0,
    })

    add("T06", "Aperture jitter bound is explicit and boundary-tested", {
        "125ns allocation endpoint admitted": decode_frame(aperture_jitter_ns=125)["validity_mask"] == 0xFFFF,
        "above125ns rejected": decode_frame(aperture_jitter_ns=126)["validity_mask"] == 0,
        "negative excursion also rejected": decode_frame(aperture_jitter_ns=-126)["validity_mask"] == 0,
    })

    c = Controller()
    c.snapshot("default_power_on")
    add("T07", "Default-LOW controls command clamp and isolation with valid logic", {
        "default selection is clamped": c.select_acquire is False,
        "unqualified rails cannot earn acquisition": not c.recording_valid,
        "unqualified startup cannot request stimulation": not c.stim_contract_ready,
    }, c)

    c = Controller()
    c.event(10_000, "invalid_record_without_connect", record=True, rails_qualified=True)
    add("T08", "Native CONNECT-and-RECORD gate clamps invalid01 command", {
        "invalid01 remains physically clamped": c.select_acquire is False,
        "invalid01 earns neither recording nor stimulation": not c.recording_valid and not c.stim_contract_ready,
        "command violation retained": "invalid_01_command" in c.errors,
    }, c)

    c = prepared()
    c.event(60_000, "clamp_before_stimulation", record=False)
    c.event(65_000, "disconnect_after_clamp_guard", connect=False)
    early = c.ask_stim(69_999, "reject4999ns_isolation_guard")
    allowed = c.ask_stim(70_000, "accept5000ns_isolation_guard")
    add("T09", "Ordered blanking earns only external-controller request permission", {
        "one_ns_early_guard_rejected": not early,
        "full_guard_request_admitted": allowed,
        "all_stimulation_intervals_neural_invalid": not c.recording_valid,
        "guard violation retained": "external_controller_rejected_stimulation" in c.errors,
    }, c)

    c = prepared()
    c.event(60_000, "unsafe_simultaneous_disconnect_and_clamp", record=False, connect=False)
    add("T10", "Simultaneous clamp/disconnect is not credited with a clamp guard", {
        "ordering_fault_is_retained": "disconnect_without_qualified_clamp_guard" in c.errors,
        "acquisition_is_invalidated": not c.recording_valid,
    }, c)

    c = prepared()
    c.event(60_000, "clamp", record=False)
    c.event(65_000, "disconnect", connect=False)
    assert c.ask_stim(70_000, "stimulus")
    c.event(270_000, "pulse_ended_current_not_yet_quiet", request=False, quiescent=False)
    c.event(300_000, "independent_current_quiet_confirmed", quiescent=True, quiet=True)
    c.event(305_000, "reconnect_while_clamped", connect=True)
    c.event(315_000, "protected_nodes_qualified_again", voltage_qualified=True)
    c.event(320_000, "release_clamp_again", record=True)
    before = c.recording_valid
    c.event(9_000_000, "external_analogue_settle_confirmed", settled=True)
    analogue_only = c.recording_valid
    c.event(200_000_000, "separate_filter_support_confirmed_example_only", filters_qualified=True)
    add("T11", "Switch release, analogue settle and causal-filter recovery are separate", {
        "switch_release_alone_does_not_earn_samples": not before,
        "analogue_settle_alone_does_not_earn_filtered_samples": not analogue_only,
        "explicit_separate_qualification_earns_samples": c.recording_valid,
        "properly_ordered_history_has_no_contract_error": not c.errors,
    }, c, note="Example times are chosen external qualification events, not measured9ms or200ms recovery guarantees. Earlier Stage3 failed filter-recovery cases remain unchanged.")

    c = prepared()
    c.event(60_000, "link_loss_with_operating_receiving_rails", link_healthy=False)
    c.event(100_000, "link_returns_controls_still_default", link_healthy=True)
    add("T12", "Link loss invalidates and link return cannot resume acquisition", {
        "controls_remain_low_after_return": not c.connect and not c.record,
        "return_does_not_restore_qualification": not c.recording_valid and not c.voltage_qualified,
    }, c, note="Modelled loss notification is external; default-LOW does not itself detect a powered controller freeze.")

    c = prepared()
    c.event(60_000, "rails_outside_logic_range", rails_qualified=False, logic_valid=False)
    add("T13", "Brownout logic is unknown rather than asserted safe", {
        "out_of_range_logic_not_boolean_safe": c.select_acquire is None,
        "recording_and_controller_stim_admission_invalid": not c.recording_valid and not c.stim_contract_ready,
    }, c)

    c = prepared()
    c.event(60_000, "stale_voltage_or_signal_envelope", voltage_qualified=False)
    add("T14", "Switch states cannot qualify node voltage or input signal amplitude", {
        "conducting_switches_do_not_earn_validity": c.select_acquire is True and not c.recording_valid,
        "unqualified_frame_full_mask_is_zero": decode_frame(qualified=c.recording_valid)["validity_mask"] == 0,
    }, c)

    truth = []
    for connect, record in itertools.product((False, True), repeat=2):
        truth.append({"connect_high": connect, "record_high": record,
                      "select_acquire": connect and record,
                      "clamp_command": not (connect and record)})
    add("T15", "All four stable native mode combinations match explicit AND gating", {
        "only11_selects_recording": sum(row["select_acquire"] for row in truth) == 1,
        "01_is_clamped": truth[1]["clamp_command"],
    }, stable_mode_truth_table=truth)

    undetectable = decode_frame()
    add("T16", "Untagged plausible raw-word replay remains an undetected fault witness", {
        "plausible_codes_without_observed_fault_can_pass_metadata_gate": undetectable["validity_mask"] == 0xFFFF,
        "wire_has_no_channel_or_frame_tag": not undetectable["wire_has_channel_or_frame_tag"],
    }, note="A replay preserving plausible 16-bit codes and current DMA metadata cannot be diagnosed by this model. Firmware ownership/counters and independent end-to-end tests remain required; no universal stale-data detection is claimed.")
    good_start = {"vref_age_ns": 100_000, "initialization_age_ns": 100_000,
                  "calibration_dummy_words": 9, "reg0": 0xDE, "reg1": 0x40,
                  "calibrated": True}
    add("T17", "Commissioning keeps Vref delay and calibration distinct from pipeline flush", {
        "qualified_register_and_startup_prerequisites_admitted": commissioning_ready(**good_start),
        "one_ns_early_Vref_delay_rejected": not commissioning_ready(**{**good_start, "vref_age_ns": 99_999}),
        "one_ns_early_initialization_delay_rejected": not commissioning_ready(**{**good_start, "initialization_age_ns": 99_999}),
        "eight_calibration_dummy_words_rejected": not commissioning_ready(**{**good_start, "calibration_dummy_words": 8}),
        "fast_settle_register_not_normal_recording": not commissioning_ready(**{**good_start, "reg0": 0xFE}),
        "supply_ADC_enable_required": not commissioning_ready(**{**good_start, "reg1": 0}),
        "calibration_completion_required": not commissioning_ready(**{**good_start, "calibrated": False}),
    }, commissioning_inputs=good_start,
        fast_settle_recommended_duration_ns=2.5 / 300 * 1e9,
        note="2.5/fH is Intan's recommended fast-settle duration, not a measured or guaranteed recovery bound. The two per-frame flush words do not replace nine calibration dummy commands.")
    return cases


def reproduce() -> dict[str, Any]:
    cases = build_scenarios()
    return {
        "schema": "scci_rh.stage4.recording-timing-contract.v1",
        "source_sha256_normalized_lf": source_hash(),
        "contract": "docs/stage4/recording-front-end-control-contract.md",
        "scope": "Finite external-controller/protocol model; no deployed firmware, actual circuit timing, analogue recovery or biological claim",
        "selected_timing": {"spi_hz": 4_000_000, "mode": 0, "word_bits": 16,
                            "commands_per_burst": WORDS, "slot_ns": SLOT_NS,
                            "burst_ns": WORDS * SLOT_NS, "frame_period_ns": FRAME_NS,
                            "per_stream_sample_rate_hz": 4_000,
                            "controller_aperture_offsets_ns": [i * SLOT_NS for i in range(1, 17)],
                            "aperture_forward_path_status": "Add CS isolator/inverter propagation plus measured timer/edge uncertainty; no interrupt timestamp substitution",
                            "pairwise_aperture_span_ns": 75_000,
                            "burst_occupancy_fraction": WORDS * SLOT_NS / FRAME_NS,
                            "CS_high_nominal_ns": 875,
                            "CS_high_min_after_scci_rh_edge_allocations_ns": 853,
                            "CS_high_edge_allocation_ns": 22,
                            "CS_inverter_delay_scci_rh_allocation_ns": 10,
                            "CS_lead_min_under_scci_rh_allocations_ns": 82,
                            "CS_hold_min_under_scci_rh_allocations_ns": 92,
                            "CS_high_datasheet_min_ns": 154,
                            "conversion_cycle_datasheet_min_ns": 950,
                            "external_mode_guard_allocation_ns": GUARD_NS,
                            "controller_aperture_jitter_allocation_ns": 125},
        "commissioning": {"reg0_normal": "0xDE", "reg0_fast_settle": "0xFE",
                          "Vref_enable_wait_min_ns": 100_000,
                          "initialization_to_calibrate_wait_min_ns": 100_000,
                          "calibration_dummy_words_min": 9,
                          "supply_adc_channel": 48, "reg1_supply_enable_mask": "0x40",
                          "supply_ADC_nominal_volts_per_count": 74.8e-6,
                          "ADC_buffer_bias_selected": 8, "MUX_bias_selected": 32,
                          "fast_settle_recommended_duration_ns_at300Hz": 2.5 / 300 * 1e9,
                          "fast_settle_is_guaranteed_recovery_bound": False},
        "primary_sources": [
            {"url": "https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf", "pages": "15-16,18-24,30,36", "checked": "2026-10-13"},
            {"url": "https://www.ti.com/lit/ds/symlink/iso6741.pdf", "pages": "21 and switching conditions", "checked": "2026-10-13"},
            {"url": "https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/spim.html", "section": "Electrical specification", "checked": "2026-10-13"},
        ],
        "assumptions": [
            "ISO6741F 3.3 V table: 18 ns maximum propagation each direction and 6 ns same-direction skew; stated datasheet operating/load conditions required.",
            "5 ns trace/edge uncertainty and 10 ns source-clock pulse-shortening allocations are SCCI_RH assumptions, not measurements.",
            "10 ns local CS inverter-delay allocation is provisional; 875 ns CS-high minus 7 ns isolator pulse-width distortion, 10 ns inverter and 5 ns board allocation leaves 853 ns.",
            "5 microsecond clamp/isolation/connect guards are provisional external-controller allocations, not manufacturer protection or recovery guarantees.",
            "Rails, protected-node voltage, current quiescence, quiet input range, analogue settle and causal-filter recovery are external qualified inputs.",
            "Brownout analogue protection, a frozen powered controller, and switch failures are outside this ideal Boolean model.",
            "Unknown plausible ADC-word replay is not detectable from untagged conversion codes alone.",
        ],
        "command_schedule": schedule(),
        "summary": {"scenario_groups": len(cases),
                    "assertions_passed": sum(len(c["checks"]) for c in cases),
                    "recorded_control_snapshots": sum(len(c["history"]) for c in cases),
                    "eight_MHz_isolated_SPI_admitted": False,
                    "four_MHz_admitted_under_declared_timing_allocations": True,
                    "physical_timing_or_recovery_verified": False,
                    "complete_firmware_implemented": False,
                    "universal_stale_data_detection": False},
        "scenarios": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-results", action="store_true", help="Explicitly save reproduced finite results")
    mode.add_argument("--check", action="store_true", help="Read-only deterministic reproduction (default)")
    args = parser.parse_args()
    actual = reproduce()
    if args.write_results:
        RESULTS.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    elif json.loads(RESULTS.read_text(encoding="utf-8")) != actual:
        raise AssertionError("Saved timing-contract results differ from deterministic reproduction")
    print(json.dumps({"status": "PASS", "mode": "write" if args.write_results else "read_only_check", **actual["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
