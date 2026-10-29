"""Finite causal transport schedule, sample identity and companion protocol.

Default is a read-only exact-model replay. --write-results explicitly writes the
saved calculation. No target firmware, analog settling, radio or biology proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULT = HERE / "transport-results.json"
HEADER = struct.Struct("<2sBBIIQQQHH")
SBP = struct.Struct("<ffI")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def raw_schedule() -> dict:
    # Tick is 62.5 ns. Each 32-bit transaction is 34 ticks, not 32 ticks.
    idle = {14, 24, 39, 44, 49}
    special = {4: "PAIR0", 29: "PAIR0", 9: "PAIR1", 34: "PAIR1", 19: "HEALTH"}
    channel = {"I0": 0, "I1": 1, "PAIR0": 2, "PAIR1": 3, "HEALTH": 4}
    rows = []
    end = -100
    for slot in range(50):
        if slot in idle:
            continue
        name = special.get(slot, "I0" if slot % 10 in {0, 2, 5, 7} else "I1")
        start = max(slot * 32, end)
        end = start + 34
        rows.append({"index": len(rows), "nominal_slot": slot, "channel_name": name,
                     "channel": channel[name], "aperture_tick": start,
                     "wire_end_tick": start + 33, "next_permitted_tick": end})
    block = rows
    rows = []
    for phase in range(4):
        for source in block:
            row = dict(source)
            row["index"] = len(rows)
            row["block_phase"] = phase
            for field in ("aperture_tick", "wire_end_tick", "next_permitted_tick"):
                row[field] += phase * 1600
            if row["channel_name"] == "HEALTH":
                row["channel"] = 4 + phase
            rows.append(row)
    for i, row in enumerate(rows):
        next_channel = rows[(i + 1) % len(rows)]["channel"]
        row["command_selects_next_channel"] = next_channel
        row["manual_command_hex"] = f"{0xC000 + next_channel * 0x400:04X}"
        row["result_identity"] = {"configuration_epoch": 1, "channel": row["channel"],
                                  "capture_id": i, "aperture_tick": row["aperture_tick"]}
    cadence = {}
    for name in channel:
        times = [r["aperture_tick"] for r in rows if r["channel_name"] == name]
        gaps = [b-a for a, b in zip(times, times[1:] + [times[0]+6400])]
        grid = {"I0": (0, 80), "I1": (40, 80), "PAIR0": (times[0], 800),
                "PAIR1": (times[0], 800), "HEALTH": (times[0], 1600)}[name]
        jitter = [t-(grid[0]+i*grid[1]) for i, t in enumerate(times)]
        cadence[name] = {"samples_per_400us": len(times), "rate_per_s": len(times)*2500,
                         "minimum_gap_us": min(gaps)/16, "maximum_gap_us": max(gaps)/16,
                         "grid_jitter_us": [min(jitter)/16, max(jitter)/16]}
    for ch in range(4, 8):
        cadence[f"HEALTH_ADC{ch}"] = {"samples_per_400us": 1, "rate_per_s": 2500,
                                       "minimum_gap_us": 400, "maximum_gap_us": 400}
    return {"hyperperiod_ticks": 6400, "tick_ns": 62.5, "SPI_Hz": 16000000,
            "SPI_frame_bits": 32, "frame_allocation_ticks": 34,
            "CS_setup_ns": 31.25, "CS_hold_ns": 31.25, "CS_high_ns": 62.5,
            "cycle_minimum_us": 2, "SCLK_maximum_Hz": 17000000,
            "priming": "MAN_CH0 frame discarded before acquisition; read back range/configuration; new epoch after reset or lost transaction",
            "hardware_channel_id_enabled": False, "channel_identity_requires_healthy_command_path": True,
            "missed_or_unknown_transaction_action": "invalidate epoch and all affected samples; stop new dose admission; reset/readback/prime before explicit rearm",
            "frames": rows, "cadence": cadence, "active_fraction": len(rows)*34/6400,
            "uniform_5us_current_apertures_earned": False,
            "analog_bandwidth_typ_Hz": 15000,
            "raw_sampling_rate_is_not_analog_bandwidth": True}


def endpoint_schedule() -> dict:
    class Arbiter:
        def __init__(self):
            self.last_cnv = None
            self.last_read = -math.inf
            self.keys = set()
            self.epoch = 1

        def reserve(self, t, capture, label, *, epoch=1, tail=True, history=True,
                    original_aperture=None):
            if epoch != self.epoch:
                return False, "configuration_epoch_changes_mid_event", []
            if capture in self.keys:
                return False, "duplicate_source_capture_id", []
            if not history:
                return False, "integrator_clipped", []
            if "TAIL" in label and not tail:
                return False, "missing_first_phase_tail", []
            if original_aperture is not None and original_aperture != t:
                return False, "late_result_retagged_as_new_aperture", []
            if self.last_cnv is not None and t-self.last_cnv < 10:
                return False, "CNV_9us_after_previous", []
            if t <= self.last_read:
                return False, "CNV_12us_shared_8MHz_reads", []
            reads = []
            for source in (0, 1):
                start = t+9+source*2.125
                reads.append({"source": source, "CS_low_us": start, "read_complete_us": start+2.125})
            self.last_cnv, self.last_read = t, reads[-1]["read_complete_us"]
            self.keys.add(capture)
            return True, "simultaneous_capture_distinct_readouts", reads

    labels = [(0, "BASELINE_A"), (14, "BASELINE_B"), (260, "CATH_TAIL_A"),
              (274, "CATH_TAIL_B"), (660, "ANODE_TAIL_A"), (674, "ANODE_TAIL_B"),
              (820, "NET_A"), (834, "NET_B")]
    rows = []
    arbiter = Arbiter()
    for capture, (t, label) in enumerate(labels):
        admitted, _, reads = arbiter.reserve(t, capture, label)
        assert admitted
        for read in reads:
            source, read_start = read["source"], read["CS_low_us"]
            rows.append({"event_id": 1, "configuration_epoch": 1, "source": source,
                         "capture_id": capture, "label": label, "CNV_us": t,
                         "result_ready_by_us": t+8.8, "CS_low_us": read_start,
                         "read_complete_us": read_start+2.125, "DIN_high_at_CNV": True,
                         "CNV_high_through_read": True, "known_integrator_history": True,
                         "tail_observed_qualified": label.startswith("BASELINE") or "TAIL" in label,
                         "phase_charge_precision_certified": False})
    witnesses = []
    requests = [(14, 1, {}), (9, 1, {}), (12, 1, {}),
                (14, 1, {"tail": False}), (14, 1, {"history": False}),
                (14, 1, {"original_aperture": 0}), (14, 1, {"epoch": 2}), (14, 0, {})]
    for t, capture, options in requests:
        a = Arbiter()
        assert a.reserve(0, 0, "BASELINE_A")[0]
        admitted, reason, reads = a.reserve(t, capture, "CATH_TAIL_A", **options)
        witnesses.append({"case": reason, "admitted": admitted, "requested_CNV_us": t,
                          "previous_CNV_us": 0, "previous_read_complete_us": 13.25,
                          "capture_id": capture, "options": options, "reads": reads})
    return {"SPI_Hz": 8000000, "read_bits_per_source": 16,
            "read_allocation_us": 2.125, "conversion_max_us": 8.8,
            "acquisition_min_us": 1.2, "conversion_spacing_min_us": 10,
            "chosen_simultaneous_CNV_spacing_min_us": 14,
            "aperture_delay_typ_ns": 4, "cross_converter_aperture_skew_bound_earned": False,
            "endpoint_ADC_instances": ["monitoring-cell/U103", "monitoring-cell/U203"],
            "shared_MISO": {"native_package": "monitoring-transport",
                            "source_series_resistors": ["R30", "R31"],
                            "series_resistance_ohm": 330, "join_net": "MON_MISO",
                            "host_header": "J22", "host_MISO_pin": "2",
                            "requires_nonoverlapping_CS": True,
                            "both_CS_active_is_not_a_valid_read": True,
                            "first_rising_sample_after_CS_ns": 62.5,
                            "first_SCLK_falling_after_CS_ns": 125,
                            "last_SCLK_falling_after_CS_ns": 2000,
                            "CS_rising_after_CS_ns": 2031.25,
                            "next_CS_falling_after_CS_ns": 2125,
                            "DOUT_enable_max_ns": 12.3,
                            "DOUT_disable_max_ns": 13.2,
                            "DOUT_propagation_max_ns": 13.4,
                            "illustrative_added_RC_load_pF": 25,
                            "illustrative_RC_tau_ns": 330*25e-3,
                            "illustrative_RC_to70percent_ns": -330*25e-3*math.log(.3),
                            "RC_screen_is_manufacturer_timing_guarantee": False,
                            "physical_bus_timing_qualified": False},
            "bus_separate_from_raw_ADC": True, "captures": rows, "witnesses": witnesses,
            "pressure_events_per_s_per_source": 360, "captures_per_event_per_source": 8,
            "aggregate_conversions_per_s": 5760, "wire_reserved_fraction": 5760*2.125e-6,
            "conditional_tail_windows": True, "native_target_peripheral_code_implemented": False}


def pack_packet(seq=1, epoch=7, support=(900000, 900000), extraction=950000,
                pressure=120.0, uncertainty=5.0, quality=0, calibration=1) -> bytes:
    payload = SBP.pack(pressure, uncertainty, calibration)
    header = HEADER.pack(b"AT", 1, 2, epoch, seq, *support, extraction, len(payload), quality)
    body = header+payload
    return body+struct.pack("<I", zlib.crc32(body))


@dataclass
class Receiver:
    epoch: int = 7
    offset_min_us: int | None = -500
    offset_max_us: int | None = 500
    trusted_session: bool = True
    sequence: int | None = None
    support_start: int | None = None
    blocked: bool = True
    last_packet: dict | None = None

    def receive(self, wire: bytes, arrival_us: int, now_us: int) -> tuple[bool, str]:
        def bad(reason):
            self.blocked = True
            self.last_packet = None
            return False, reason
        if len(wire) != HEADER.size+SBP.size+4:
            return bad("length")
        if zlib.crc32(wire[:-4]) != struct.unpack("<I", wire[-4:])[0]:
            return bad("CRC")
        magic, version, kind, epoch, seq, first, last, extract, size, quality = HEADER.unpack(wire[:HEADER.size])
        pressure, uncertainty, calibration = SBP.unpack(wire[HEADER.size:-4])
        if (magic, version, kind, size) != (b"AT", 1, 2, SBP.size):
            return bad("schema")
        if not self.trusted_session or epoch != self.epoch:
            return bad("session_epoch")
        if self.offset_min_us is None or self.offset_max_us is None or self.offset_max_us-self.offset_min_us > 1000 or self.offset_min_us > self.offset_max_us:
            return bad("clock_unbounded")
        if self.sequence is not None and not 0 < ((seq-self.sequence) & 0xFFFFFFFF) < 0x80000000:
            return bad("sequence_replay_or_reorder")
        if not first <= last <= extract or not arrival_us <= now_us:
            return bad("causal_order")
        if last+self.offset_max_us > arrival_us or extract+self.offset_min_us > arrival_us:
            return bad("future_support_or_extraction")
        age = now_us-(first+self.offset_min_us)
        if not 0 <= age <= 2000000:
            return bad("oldest_support_age")
        if self.support_start is not None and first <= self.support_start:
            return bad("support_replay")
        if quality != 0 or not math.isfinite(pressure) or not math.isfinite(uncertainty) or not 50 <= pressure <= 250 or not 0 <= uncertainty <= 50 or calibration != 1:
            return bad("quality_range_or_calibration")
        self.sequence, self.support_start = seq, first
        self.last_packet = {"sequence": seq, "support_start_us": first, "arrival_us": arrival_us,
                            "oldest_age_at_accept_us": age, "pressure_mmHg": pressure}
        return True, "accepted_pending_explicit_rearm" if self.blocked else "accepted"

    def fresh(self, now_us: int) -> bool:
        if (self.last_packet is None or self.offset_min_us is None or self.offset_max_us is None
                or self.offset_min_us > self.offset_max_us or self.offset_max_us-self.offset_min_us > 1000
                or not self.trusted_session):
            self.blocked = True
            return False
        age = now_us-(self.last_packet["support_start_us"]+self.offset_min_us)
        if not 0 <= age <= 2000000:
            self.blocked = True
            return False
        return True

    def rearm(self, now_us: int) -> bool:
        if self.trusted_session and self.fresh(now_us):
            self.blocked = False
            return True
        return False


def protocol_cases() -> dict:
    cases = []
    def scenario(name, wire=None, receiver=None, arrival=1000000, now=1000000, preload=False):
        r = receiver or Receiver()
        if preload:
            assert r.receive(pack_packet(), 1000000, 1000000)[0]
            assert r.rearm(1000000)
        previous_sequence, previous_support = r.sequence, r.support_start
        ok, reason = r.receive(wire if wire is not None else pack_packet(), arrival, now)
        cases.append({"case": name, "accepted": ok, "reason": reason, "blocked": r.blocked,
                      "packet_hex": (wire if wire is not None else pack_packet()).hex(),
                      "arrival_us": arrival, "now_us": now, "offset_interval_us": [r.offset_min_us, r.offset_max_us],
                      "preloaded": preload, "trusted_session": r.trusted_session, "expected_epoch": r.epoch,
                      "previous_sequence": previous_sequence, "previous_support_us": previous_support})
        return r
    scenario("fresh_SBP_waits_for_rearm")
    corrupt = bytearray(pack_packet()); corrupt[20] ^= 1
    scenario("corrupt_CRC", bytes(corrupt))
    scenario("truncated_packet", pack_packet()[:-1])
    scenario("old_epoch", pack_packet(epoch=6))
    scenario("untrusted_session", receiver=Receiver(trusted_session=False))
    scenario("unknown_clock_offset", receiver=Receiver(offset_min_us=None, offset_max_us=None))
    scenario("excess_clock_uncertainty", receiver=Receiver(offset_min_us=-501, offset_max_us=501))
    scenario("future_shifted_clock", pack_packet(support=(5900000, 5900000), extraction=5950000))
    scenario("arrival_is_not_support_time", pack_packet(support=(0, 0), extraction=2990000), arrival=3000000, now=3000000)
    scenario("support_interval_oldest_edge", pack_packet(support=(0, 900000), extraction=950000), arrival=2100000, now=2100000)
    scenario("duplicate_sequence", preload=True)
    scenario("new_sequence_old_support", pack_packet(seq=2), preload=True)
    scenario("reordered_sequence", pack_packet(seq=0, support=(910000, 910000), extraction=960000), preload=True)
    scenario("support_after_extraction", pack_packet(support=(960000, 960000), extraction=950000))
    scenario("invalid_quality", pack_packet(quality=1))
    scenario("out_of_range_SBP", pack_packet(pressure=400))
    scenario("NaN_SBP", pack_packet(pressure=float("nan")))
    scenario("unknown_calibration", pack_packet(calibration=2))
    scenario("future_arrival", arrival=1000001)
    scenario("new_fresh_packet_keeps_explicit_rearm", pack_packet(seq=2, support=(910000, 910000), extraction=960000))
    wrap = Receiver(sequence=0xFFFFFFFF, support_start=800000, blocked=False)
    scenario("uint32_sequence_wrap", pack_packet(seq=0), receiver=wrap)
    r = Receiver()
    assert r.receive(pack_packet(support=(0, 0), extraction=50000), 100000, 100000)[0]
    assert r.rearm(100000)
    checks = []
    for t in range(100000, 3100001, 250000):
        valid = r.fresh(t)
        checks.append({"now_us": t, "oldest_support_age_us": t+500,
                       "fresh": valid, "new_adaptation_permit": valid and not r.blocked})
    first_stale = next(x["now_us"] for x in checks if not x["fresh"])
    fallbacks = []
    for variant in ("stop", "hold_500ms", "ramp_500ms"):
        for dt in (0, 125000, 250000, 500000, 750000):
            value = 0 if variant == "stop" else (0.6 if dt < 500000 else 0) if variant.startswith("hold") else 0.6*max(0, 1-dt/500000)
            fallbacks.append({"variant": variant, "elapsed_after_detection_us": dt,
                              "normalized_output": value, "hard_trip_output": 0,
                              "new_adaptation_permit": False})
    leases = []
    for name, duration, input_alive in (("motor_local_observations", 250000, True),
                                        ("pressure_independent_sensor", 3000000, True),
                                        ("pressure_sensor_path_lost", 3000000, False)):
        for t in (0, 249999, 250000, 1999500, 2000000, 2500000, 2999999, 3000000):
            fresh = input_alive or t+500 <= 2000000
            leases.append({"case": name, "elapsed_us": t, "lease_us": duration,
                           "observations_fresh": fresh, "permit": t < duration and fresh,
                           "hard_trip_permit": False})
    recovery = Receiver()
    recovery_steps = []
    for label, wire in (("initial_valid", pack_packet()), ("CRC_fault", bytes(corrupt)),
                         ("new_valid_after_fault", pack_packet(seq=2, support=(910000, 910000), extraction=960000))):
        ok, _ = recovery.receive(wire, 1000000, 1000000)
        before = recovery.blocked
        rearmed = recovery.rearm(1000000)
        recovery_steps.append({"step": label, "packet_accepted": ok,
                               "blocked_before_rearm": before, "explicit_rearm_accepted": rearmed,
                               "blocked_after_rearm": recovery.blocked})
    return {"format": "little-endian <2sBBIIQQQHH + SBP <ffI + CRC32",
            "header_bytes": HEADER.size, "SBP_payload_bytes": SBP.size, "CRC_bytes": 4,
            "SBP_wire_bytes": len(pack_packet()), "CRC_is_authentication": False,
            "cryptographic_authentication_implemented": False,
            "clock_uncertainty_max_us": 500, "max_oldest_support_age_us": 2000000,
            "service_period_us": 250000, "pressure_lease_us": 3000000,
            "motor_lease_us": 250000, "range_mmHg": [50, 250],
            "range_is_clinical_threshold": False, "cases": cases,
            "no_arrival_service_history": checks, "first_stale_detection_us": first_stale,
            "fallbacks": fallbacks, "lease_histories": leases, "recovery_history": recovery_steps,
            "fallback_is_clinically_qualified": False,
            "actual_sensor_accuracy_or_clock_truth_verified": False,
            "malicious_sender_or_false_clock_bound_detected_by_CRC": False}


def resources() -> dict:
    raw_words = 450000*0.0025
    mask = math.ceil(raw_words/8)
    raw_block = math.ceil((2*raw_words+2*mask+64)/32)*32
    memory = {"ping_pong_blocks": int(2*raw_block), "endpoint_ring_64x32": 2048,
              "identity_error_state": 512}
    # Security tag bytes reserve space only; cryptographic protection is not implemented.
    streams = [("features", 128, 50), ("SBP", 12, 1), ("health", 24, 10),
               ("commands", 40, 4), ("lease", 0, 20)]
    normal = [{"stream": n, "payload_bytes": p, "packets_per_s": f,
               "wire_bytes": p+40+4+16, "wire_bits_per_s": (p+60)*f*8} for n, p, f in streams]
    aggregate = sum(r["wire_bits_per_s"] for r in normal)
    cases = []
    for rate in (4000, 2000):
        for service in (1000000, 800000):
            incoming = rate/10*(10*48+60)
            served = service/8
            growth = incoming-served
            cases.append({"frame_rate_Hz": rate, "framed_base_bits_per_s": rate*48*8,
                          "transport_bits_per_s": incoming*8, "service_payload_bits_per_s": service,
                          "growth_bytes_per_s": growth, "continuous_fits": growth <= 0,
                          "queue_capacity_bytes": 16384,
                          "overflow_after_s": None if growth <= 0 else 16384/growth,
                          "100ms_burst_peak_bytes": max(0, growth)*0.1,
                          "100ms_burst_fits": max(0, growth)*0.1 <= 16384})
    return {"monitor_rate_words_per_s": 450000, "DMA_half_period_us": 2500,
            "words_per_half": int(raw_words), "mask_bytes_each_per_half": mask,
            "header_bytes_per_half": 64, "aligned_bytes_per_half": int(raw_block),
            "monitor_memory_bytes": memory, "monitor_total_bytes": sum(memory.values()),
            "monitor_allocation_bytes": 8192, "consumer_budget_us": 2000,
            "consumer_release_to_reuse_deadline_us": 2500,
            "consumer_3ms_delay_overruns": True,
            "DMA_service_cases": [{"consumer_latency_us": t,
                                    "completes_before_reuse": t <= 2500,
                                    "overrun_latches_invalid_epoch": t > 2500,
                                    "new_dose_admission": t <= 2500}
                                   for t in (0, 2000, 2500, 2501, 3000)],
            "normal_streams": normal, "normal_wire_bits_per_s": aggregate,
            "reserved_future_envelope_bytes_per_packet": 16,
            "reserved_envelope_generated_or_authenticated": False,
            "normal_with20percent_reserve_bits_per_s": aggregate*1.2,
            "normal_service_reservation_bits_per_s": 160000,
            "UART_baud": 1000000, "UART_bits_per_byte_8N1": 10,
            "UART_byte_payload_ceiling_bits_per_s": 800000,
            "old_raw_service_bits_per_s": 1000000,
            "old_raw_service_earned_by_UART": False,
            "raw_cases": cases,
            "queue_allocation_bytes": {"raw": 16384, "normal": 8192, "commands_and_validity": 8192},
            "shared_queue_budget_bytes": 32768,
            "raw_mode_exclusive_from_continuous_normal_features": True,
            "raw_lease_s": 0.1, "queue_full_action": "stop diagnostic capture, retain gap/overrun metadata; never overwrite as valid",
            "transport_service_is_physical_measurement": False}


def native_binding() -> dict:
    path = ROOT / "electronics/stage4/monitoring-transport/connectivity.json"
    old = ROOT / "electronics/stage4/monitoring-cell/connectivity.json"
    d = json.loads(old.read_text(encoding="utf-8-sig"))
    parts = {p["ref"]: p for p in d["parts"]}
    endpoints = []
    for ref, source in (("U103", 0), ("U203", 1)):
        p = parts[ref]
        assert p["value"] == "ADS8866IDGSR"
        for pin, suffix in (("6", "CNV"), ("7", "DOUT"), ("9", "CS_N")):
            assert p["nets"][pin] == f"CH{source}_{suffix}"
            endpoints.append({"package": "monitoring-cell", "reference": ref, "pin": pin, "net": p["nets"][pin]})
        assert p["nets"]["8"] == "MON_SCLK"
        endpoints.append({"package": "monitoring-cell", "reference": ref, "pin": "8", "net": "MON_SCLK"})
    bindings = {str(old.relative_to(ROOT)).replace("\\", "/"): sha(old)}
    native = None
    if path.exists():
        n = json.loads(path.read_text(encoding="utf-8-sig"))
        bindings[str(path.relative_to(ROOT)).replace("\\", "/")] = sha(path)
        export = path.with_name("monitoring_transport.xml")
        bindings[str(export.relative_to(ROOT)).replace("\\", "/")] = sha(export)
        selected = [p for p in n["parts"] if str(p["value"]).startswith("ADS8688")]
        assert len(selected) == 1
        adc = selected[0]
        native = {"ADC_reference": adc["ref"], "ADC_value": adc["value"], "pins": adc["nets"],
                  "component_count": len(n["parts"])}
    return {"source_sha256_lf": bindings, "endpoint_pins": endpoints, "new_native": native}


def calculate() -> dict:
    return {"schema": "scci_rh.stage4.transport-contract.v1", "date": "2026-10-14",
            "scope": "finite digital schedule, protocol and queue contract; target implementation and physical behavior unearned",
            "producer_sha256_lf": sha(Path(__file__)), "native_binding": native_binding(),
            "raw_ADC": raw_schedule(), "endpoints": endpoint_schedule(),
            "companion": protocol_cases(), "resources": resources(),
            "main_project": {"motor": "expert-informed learner-specific policy; OFF retained learning is a separate conditional biological hypothesis",
                             "physiology": "target-specific pressure feedback; external measured SBP, finite pressor authority and fallback variants",
                             "universal_body_control_or_voltage_replay": False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-results", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = calculate()
    if args.write_results:
        RESULT.write_text(json.dumps(data, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    else:
        saved = json.loads(RESULT.read_text(encoding="utf-8"))
        assert saved == data, "saved transport contract differs; regenerate explicitly after reviewing source changes"
    print(json.dumps({"status": "pass", "raw_frames": len(data["raw_ADC"]["frames"]),
                      "current_maximum_gap_us": data["raw_ADC"]["cadence"]["I0"]["maximum_gap_us"],
                      "protocol_cases": len(data["companion"]["cases"]),
                      "monitor_memory_bytes": data["resources"]["monitor_total_bytes"]}))


if __name__ == "__main__":
    main()
