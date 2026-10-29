"""Independent saved-event/interval/pin audit; never imports the producer.

Default reads source/results only. --write-report explicitly saves the audit.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
checks = 0


def check(value, reason):
    global checks
    checks += 1
    if not value:
        raise AssertionError(reason)


def near(a, b, reason):
    check(math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-12), reason)


def sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def protocol_verdict(row):
    """Decode saved bytes independently and evaluate the rejection predicates."""
    wire = bytes.fromhex(row["packet_hex"])
    if len(wire) != 56:
        return False, "length"
    crc = int.from_bytes(wire[-4:], "little")
    if crc != zlib.crc32(wire[:-4]):
        return False, "CRC"
    magic = wire[:2]
    version, kind = wire[2], wire[3]
    epoch, sequence = struct.unpack_from("<II", wire, 4)
    first, last, extraction = struct.unpack_from("<QQQ", wire, 12)
    size, quality = struct.unpack_from("<HH", wire, 36)
    pressure, uncertainty, calibration = struct.unpack_from("<ffI", wire, 40)
    if (magic, version, kind, size) != (b"AT", 1, 2, 12):
        return False, "schema"
    if not row["trusted_session"] or epoch != row["expected_epoch"]:
        return False, "session_epoch"
    lo, hi = row["offset_interval_us"]
    if lo is None or hi is None or hi-lo > 1000 or lo > hi:
        return False, "clock_unbounded"
    previous = row["previous_sequence"]
    if previous is not None:
        advance = (sequence-previous) % 4294967296
        if advance == 0 or advance >= 2147483648:
            return False, "sequence_replay_or_reorder"
    if not first <= last <= extraction or row["arrival_us"] > row["now_us"]:
        return False, "causal_order"
    if last+hi > row["arrival_us"] or extraction+lo > row["arrival_us"]:
        return False, "future_support_or_extraction"
    if not 0 <= row["now_us"]-first-lo <= 2000000:
        return False, "oldest_support_age"
    if row["previous_support_us"] is not None and first <= row["previous_support_us"]:
        return False, "support_replay"
    if quality or not math.isfinite(pressure) or not math.isfinite(uncertainty) or not 50 <= pressure <= 250 or not 0 <= uncertainty <= 50 or calibration != 1:
        return False, "quality_range_or_calibration"
    return True, "accepted"


def verify():
    d = json.loads((HERE/"transport-results.json").read_text(encoding="utf-8"))
    check(d["producer_sha256_lf"] == sha(HERE/"transport_contract.py"), "producer identity")
    for p, h in d["native_binding"]["source_sha256_lf"].items():
        check(sha(ROOT/p) == h, f"source binding {p}")
    old = json.loads((ROOT/"electronics/stage4/monitoring-cell/connectivity.json").read_text(encoding="utf-8"))
    oldparts = {p["ref"]: p for p in old["parts"]}
    for row in d["native_binding"]["endpoint_pins"]:
        check(oldparts[row["reference"]]["nets"][row["pin"]] == row["net"], "actual endpoint pin")
    native = json.loads((ROOT/"electronics/stage4/monitoring-transport/connectivity.json").read_text(encoding="utf-8"))
    nparts = {p["ref"]: p for p in native["parts"]}
    adc = nparts["U1"]
    check(adc["value"] == "ADS8688IDBTR", "raw ADC identity")
    expected = {"1": "RAW_SDI_PAD", "2": "RAW_RST_N", "3": "GND", "4": "GND",
                "5": "RAW_REFIO", "6": "GND", "7": "RAW_REFCAP", "9": "HOST_5",
                "12": "ADC6", "14": "ADC7", "16": "ADC0", "18": "ADC1",
                "21": "ADC2", "23": "ADC3", "25": "ADC4", "27": "ADC5",
                "30": "HOST_5", "34": "HOST_3V3", "35": None,
                "36": "RAW_SDO", "37": "RAW_SCLK_PAD", "38": "RAW_CS_N"}
    for pin, net in expected.items():
        check(adc["nets"][pin] == net, f"actual ADS8688 pin{pin}")
    root = ET.parse(ROOT/"electronics/stage4/monitoring-transport/monitoring_transport.xml").getroot()
    xmlpins = {}
    for net in root.findall("./nets/net"):
        for node in net.findall("node"):
            xmlpins[node.attrib["ref"], node.attrib["pin"]] = net.attrib["name"]
    for pin, net in expected.items():
        if net is not None:
            actual = xmlpins.get(("U1", pin), "").split("/")[-1]
            check(actual == net, f"native XML ADS8688 pin{pin}")
    # Separate endpoint DOUTs reach the diagnostic header and an explicit
    # resistor join. They are never silently treated as one native net.
    for pin in range(1, 8):
        check(nparts["J4"]["nets"][str(pin)] == nparts["J20"]["nets"][str(pin)], "independent endpoint handoff")
    for ref, source in (("R30", 0), ("R31", 1)):
        check(nparts[ref]["value"] == "330R", "shared MISO series resistance")
        check(nparts[ref]["nets"] == {"1": f"CH{source}_DOUT", "2": "MON_MISO"}, "explicit resistive MISO join")
        for pin, net in nparts[ref]["nets"].items():
            check(xmlpins.get((ref, pin), "").split("/")[-1] == net, "XML MISO series join")
    expected_bus = {"1": "MON_SCLK", "2": "MON_MISO", "3": "CH0_CNV", "4": "CH0_CS_N",
                    "5": "CH1_CNV", "6": "CH1_CS_N", "7": "GND"}
    check(nparts["J22"]["nets"] == expected_bus, "actual shared endpoint host header")
    check(nparts["U20"]["nets"]["4"] == "GND" and nparts["U20"]["nets"]["5"] == "COMP_GND", "distinct companion grounds")

    a = d["raw_ADC"]
    frames = a["frames"]
    check(len(frames) == 180, "180 conversions per400us")
    count = Counter(r["channel_name"] for r in frames)
    check(count == {"I0": 80, "I1": 80, "PAIR0": 8, "PAIR1": 8, "HEALTH": 4}, "per-channel throughput")
    check(a["SPI_Hz"] <= 17000000, "raw SPI clock ceiling")
    near(a["SPI_frame_bits"]/a["SPI_Hz"]*1e9, 2000, "raw32bit wire time")
    check(a["CS_setup_ns"] >= 30 and a["CS_hold_ns"] >= 10 and a["CS_high_ns"] >= 30, "CS timing margins")
    near(2000+a["CS_setup_ns"]+a["CS_hold_ns"]+a["CS_high_ns"], a["frame_allocation_ticks"]*a["tick_ns"], "transaction budget")
    near(a["active_fraction"], 180*34/6400, "scheduled occupancy")
    check(a["active_fraction"] < 1, "schedule fits")
    for i, f in enumerate(frames):
        following = frames[(i+1) % len(frames)]
        dt = (following["aperture_tick"]-f["aperture_tick"]) % a["hyperperiod_ticks"]
        check(dt >= 34, "no overlapping ADC cycles")
        check(f["next_permitted_tick"] == f["aperture_tick"]+34, "frame interval")
        check(f["command_selects_next_channel"] == following["channel"], "one-frame channel command causality")
        check(int(f["manual_command_hex"], 16) == 0xC000+following["channel"]*1024, "manual mux command")
        check(f["result_identity"]["channel"] == f["channel"] and f["result_identity"]["aperture_tick"] == f["aperture_tick"], "aperture/result identity")
        check(f["index"] == i == f["result_identity"]["capture_id"], "capture uniqueness")
    for name in count:
        ticks = [f["aperture_tick"] for f in frames if f["channel_name"] == name]
        gaps = [(b-a) % 6400 for a, b in zip(ticks, ticks[1:]+ticks[:1])]
        near(min(gaps)/16, a["cadence"][name]["minimum_gap_us"], "minimum cyclic gap")
        near(max(gaps)/16, a["cadence"][name]["maximum_gap_us"], "maximum cyclic gap")
        near(len(ticks)/.0004, a["cadence"][name]["rate_per_s"], "sample rate")
    check({r["channel"] for r in frames if r["channel_name"] == "HEALTH"} == {4, 5, 6, 7}, "all four health taps rotate")
    check(a["hardware_channel_id_enabled"] is False and a["channel_identity_requires_healthy_command_path"], "software identity premise explicit")
    check(a["uniform_5us_current_apertures_earned"] is False, "nonuniform current sampling explicit")

    e = d["endpoints"]
    check(e["bus_separate_from_raw_ADC"], "endpoint dedicated bus")
    check(e["shared_MISO"]["requires_nonoverlapping_CS"] and e["shared_MISO"]["both_CS_active_is_not_a_valid_read"], "tri-state MISO ownership premise")
    check(not e["shared_MISO"]["physical_bus_timing_qualified"], "schematic does not earn physical SPI timing")
    bus = e["shared_MISO"]
    near(bus["illustrative_RC_tau_ns"], 330*25e-3, "explicit RC premise")
    near(bus["illustrative_RC_to70percent_ns"], -bus["illustrative_RC_tau_ns"]*math.log(.3), "conditional RC threshold time")
    check(bus["first_rising_sample_after_CS_ns"] > bus["DOUT_enable_max_ns"]+bus["illustrative_RC_to70percent_ns"], "conditional initial MSB edge screen")
    check(62.5 > bus["DOUT_propagation_max_ns"]+bus["illustrative_RC_to70percent_ns"], "conditional half-cycle data edge screen")
    check(bus["next_CS_falling_after_CS_ns"]-bus["last_SCLK_falling_after_CS_ns"] > bus["DOUT_disable_max_ns"], "DOUT released before next selection")
    near(bus["next_CS_falling_after_CS_ns"], e["read_allocation_us"]*1000, "shared bus read allocation")
    check(not bus["RC_screen_is_manufacturer_timing_guarantee"], "RC model remains conditional")
    keys = set()
    reads = []
    for row in e["captures"]:
        key = row["configuration_epoch"], row["source"], row["event_id"], row["capture_id"]
        check(key not in keys, "unique endpoint identity"); keys.add(key)
        check(row["CS_low_us"] >= row["CNV_us"]+8.8, "read after worst-case conversion")
        near(row["read_complete_us"]-row["CS_low_us"], 2.125, "endpoint16bit read allocation")
        check(row["DIN_high_at_CNV"] and row["CNV_high_through_read"], "ADS8866 four-wire mode")
        check(not row["phase_charge_precision_certified"], "transport does not grant charge precision")
        reads.append((row["CS_low_us"], row["read_complete_us"]))
    for left, right in zip(sorted(reads), sorted(reads)[1:]):
        check(left[1] <= right[0], "endpoint CS reads do not collide")
    for source in (0, 1):
        rows = [r for r in e["captures"] if r["source"] == source]
        for p, q in zip(rows, rows[1:]):
            check(q["CNV_us"]-p["CNV_us"] >= 14, "reserved CNV spacing")
            check(p["read_complete_us"] < q["CNV_us"], "no overwritten unread endpoint")
    near(e["aggregate_conversions_per_s"], 2*8*360, "endpoint conversion rate")
    near(e["wire_reserved_fraction"], 5760*2.125e-6, "endpoint bus occupancy")
    check(sum(w["admitted"] for w in e["witnesses"]) == 1, "endpoint rejection witnesses retained")
    for row in e["witnesses"]:
        opts = row["options"]
        valid = (opts.get("epoch", 1) == 1 and row["capture_id"] != 0
                 and opts.get("history", True) and opts.get("tail", True)
                 and opts.get("original_aperture", row["requested_CNV_us"]) == row["requested_CNV_us"]
                 and row["requested_CNV_us"]-row["previous_CNV_us"] >= 10
                 and row["requested_CNV_us"] > row["previous_read_complete_us"])
        check(valid == row["admitted"], "independent endpoint arbiter admission")
        check(bool(row["reads"]) == valid, "rejected arbiter request creates no readout")

    c = d["companion"]
    for row in c["cases"]:
        accepted, reason = protocol_verdict(row)
        check(accepted == row["accepted"], f"packet verdict {row['case']}")
        check(reason == row["reason"] or accepted and row["reason"].startswith("accepted"), f"packet reason {row['case']}")
        if not accepted:
            check(row["blocked"], "invalid packet latches transport inhibition")
    history = c["no_arrival_service_history"]
    for row in history:
        check(row["fresh"] == (row["now_us"]+500 <= 2000000), "age grows without arrivals")
        check(row["new_adaptation_permit"] == row["fresh"], "no-arrival adaptation gate")
    near(c["first_stale_detection_us"], min(r["now_us"] for r in history if not r["fresh"]), "first stale service tick")
    check(c["first_stale_detection_us"] <= 2250000, "stale detection bounded by250ms tick")
    for row in c["fallbacks"]:
        t = row["elapsed_after_detection_us"]
        if row["variant"] == "stop": expected = 0
        elif row["variant"] == "hold_500ms": expected = .6 if t < 500000 else 0
        else: expected = max(0, .6-.6*t/500000)
        near(row["normalized_output"], expected, "finite fallback envelope")
        check(row["hard_trip_output"] == 0 and not row["new_adaptation_permit"], "hard trip overrides fallback")
    for row in c["lease_histories"]:
        check(row["permit"] == (row["elapsed_us"] < row["lease_us"] and row["observations_fresh"]), "lease and independent freshness")
        check(not row["hard_trip_permit"], "lease cannot override electrical trip")
    recovery = c["recovery_history"]
    check([r["packet_accepted"] for r in recovery] == [True, False, True], "fault recovery accepts new valid support only")
    check([r["explicit_rearm_accepted"] for r in recovery] == [True, False, True], "CRC fault clears previous validity before explicit rearm")
    check([r["blocked_before_rearm"] for r in recovery] == [True, True, True], "new valid support does not automatically restore permission")
    check([r["blocked_after_rearm"] for r in recovery] == [False, True, False], "explicit recovery chronology")
    check(not c["CRC_is_authentication"] and not c["fallback_is_clinically_qualified"], "claim boundaries")
    check(not c["cryptographic_authentication_implemented"], "no authentication implementation implied")

    r = d["resources"]
    check(r["reserved_future_envelope_bytes_per_packet"] == 16 and not r["reserved_envelope_generated_or_authenticated"], "future wire allowance is only reserved space")
    check(r["words_per_half"] == 450000*.0025, "DMA sample count")
    check(r["mask_bytes_each_per_half"] == math.ceil(r["words_per_half"]/8), "both validity and range masks")
    need = 2*r["words_per_half"]+2*r["mask_bytes_each_per_half"]+64
    check(r["aligned_bytes_per_half"] == math.ceil(need/32)*32, "DMA alignment")
    check(sum(r["monitor_memory_bytes"].values()) == r["monitor_total_bytes"] <= 8192, "monitor RAM bound")
    for row in r["DMA_service_cases"]:
        check(row["completes_before_reuse"] == (row["consumer_latency_us"] <= 2500), "DMA reuse deadline")
        check(row["overrun_latches_invalid_epoch"] == (row["consumer_latency_us"] > 2500), "overrun invalidates")
    for row in r["normal_streams"]:
        near(row["wire_bits_per_s"], (row["payload_bytes"]+60)*row["packets_per_s"]*8, "normal frame arithmetic")
    near(sum(x["wire_bits_per_s"] for x in r["normal_streams"]), r["normal_wire_bits_per_s"], "normal total")
    near(r["normal_with20percent_reserve_bits_per_s"], 1.2*r["normal_wire_bits_per_s"], "normal contingency")
    check(r["normal_with20percent_reserve_bits_per_s"] < 160000 < r["UART_byte_payload_ceiling_bits_per_s"], "normal fits actual UART")
    near(r["UART_byte_payload_ceiling_bits_per_s"], 1000000/10*8, "8N1 framing capacity")
    for row in r["raw_cases"]:
        incoming = row["frame_rate_Hz"]*(48+60/10)
        near(row["transport_bits_per_s"], incoming*8, "raw packet overhead")
        growth = incoming-row["service_payload_bits_per_s"]/8
        near(row["growth_bytes_per_s"], growth, "queue flow conservation")
        check(row["continuous_fits"] == (growth <= 0), "continuous service criterion")
        if growth > 0:
            near(row["overflow_after_s"]*growth, 16384, "finite queue saturation time")
        near(row["100ms_burst_peak_bytes"], max(0, growth)*.1, "leased burst backlog")
        check(row["100ms_burst_fits"], "100ms burst fits allocated queue")
    check(sum(r["queue_allocation_bytes"].values()) == 32768, "shared queue RAM sum")
    check(not r["old_raw_service_earned_by_UART"], "1Mpayload service rejected on1MbaudUART")
    return {"schema": "scci_rh.stage4.transport-verification.v1", "status": "pass",
            "assertions": checks, "results_sha256_lf": sha(HERE/"transport-results.json"),
            "raw_ADC_frames": len(frames), "endpoint_captures": len(e["captures"]),
            "protocol_cases": len(c["cases"]), "producer_imported": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    report = verify()
    if args.write_report:
        (HERE/"transport-verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
