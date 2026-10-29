"""Reproduce SCCI_RH Stage 2 analytical allocations, not device measurements.

SI internally. Reads audited input files without fitting their assumptions to
desired results. --check compares committed results without modifying them.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'docs' / 'stage2'
OUTPUT = ROOT / 'results' / 'stage2'


def periodic_union(period, offsets, width, preguard=0.0):
    """Exact interval union on a periodic circle; handles wraps and overlaps."""
    if period <= 0 or width < 0 or preguard < 0:
        raise ValueError('Positive period, nonnegative durations required')
    if not offsets or width + preguard == 0:
        return [], 0.0
    if width + preguard >= period:
        return [(0.0, period)], 1.0
    intervals = []
    for offset in offsets:
        start = (offset - preguard) % period
        end = start + width + preguard
        if end <= period:
            intervals.append((start, end))
        else:
            intervals.extend([(start, period), (0.0, end - period)])
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + 1e-14:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged, sum(end - start for start, end in merged) / period


def blank_in_window(intervals, period, start, length):
    end = start + length
    total = 0.0
    for cycle in range(math.floor(start / period) - 1,
                       math.ceil(end / period) + 1):
        for lo, hi in intervals:
            total += max(0.0, min(end, hi + cycle * period)
                         - max(start, lo + cycle * period))
    return total


def minimum_window_usable(intervals, period, length):
    # Coverage is piecewise linear. Extrema occur when either window edge
    # crosses a mask edge, so no time-grid rounding is required.
    edges = [x for pair in intervals for x in pair]
    candidates = {0.0, *[e % period for e in edges],
                  *[(e - length) % period for e in edges]}
    return 1 - max(blank_in_window(intervals, period, s, length)
                   for s in candidates) / length


def phase_uncertainty(current, duration, monitor):
    lsb = monitor['signed_current_span_A'] / 2 ** monitor['adc_bits']
    # Constant rectangular phase witness. No unbounded inter-sample spike claim.
    return (2 * current * monitor['phase_edge_uncertainty_s']
            + (lsb / 2 + monitor['current_offset_bound_A']) * duration
            + monitor['current_gain_fraction_bound'] * current * duration)


def group_delay(f, fl=0.1, fh=300):
    w = f / fh
    return (fl / (2 * math.pi * (f*f + fl*fl))
            + (1 / (1+w*w) + (1+w*w) / ((1-w*w)**2+w*w))
            / (2 * math.pi * fh))


def memory_allocation(capacity, allocations, minimum_spare):
    """Finite byte allocations; unused memory is not an implicit second image."""
    if (type(capacity) is not int or capacity <= 0
            or not 0 <= minimum_spare < 1
            or any(type(v) is not int or v < 0 for v in allocations.values())):
        raise ValueError('Positive capacity, nonnegative integer bytes and valid spare fraction required')
    used = sum(allocations.values())
    return {'capacity_bytes': capacity, 'allocated_bytes': used,
            'remaining_bytes': capacity-used, 'headroom_fraction': 1-used/capacity,
            'headroom_gate_pass': used <= capacity*(1-minimum_spare)}


def source_schedule(profile, stimulation):
    """Periodic physical-source availability, distinct from per-profile rate.

    Also inspect the last-to-first interval. Recording recovery is a different
    mask and does not silently dictate driver rearm or electrode qualification.
    """
    if not math.isfinite(profile['frame_hz']) or profile['frame_hz'] <= 0:
        raise ValueError('Positive finite frame rate required')
    if not math.isfinite(profile['phase_s']) or profile['phase_s'] < 0:
        raise ValueError('Nonnegative finite phase duration required')
    period = 1/profile['frame_hz']
    offsets, routes = profile['offsets_s'], profile['source_ids_per_event']
    identities=profile['profile_ids_per_event']
    if (len(offsets) != profile['events_per_frame'] or len(routes) != len(offsets)
            or len(identities)!=len(offsets)
            or any(len(names)!=len(ids) or any(not isinstance(name,str) or not name for name in names)
                   for names,ids in zip(identities,routes))
            or any(not 0 <= offset < period for offset in offsets)
            or any(len(ids) != profile['sources_per_event'] or len(set(ids)) != len(ids)
                   or any(type(i) is not int or not 0 <= i < stimulation['independent_sources'] for i in ids)
                   for ids in routes)):
        raise ValueError('Invalid periodic source/event assignment')
    occupied = 2*profile['phase_s'] + stimulation['interphase_s']
    service = occupied + stimulation['source_rearm_and_reconfigure_s']
    rows = []
    for source in range(stimulation['independent_sources']):
        starts = sorted(offset for offset, ids in zip(offsets, routes) if source in ids)
        gaps = [((starts[(i+1)%len(starts)]-start) % period) if len(starts)>1 else period
                for i,start in enumerate(starts)]
        minimum = min(gaps) if gaps else None
        rows.append({'source_id': source, 'events_per_s': len(starts)/period,
            'minimum_cyclic_start_gap_s': minimum,
            'reserved_service_fraction': len(starts)*service/period,
            'no_service_overlap': minimum is None or minimum+1e-14 >= service})
    profile_rows=[]
    for name in sorted({name for names in identities for name in names}):
        starts=sorted(offset for offset,names in zip(offsets,identities) for item in names if item==name)
        gaps=[((starts[(i+1)%len(starts)]-start)%period) if len(starts)>1 else period
              for i,start in enumerate(starts)]
        profile_rows.append({'profile_id':name,'events_per_s':len(starts)/period,
            'minimum_cyclic_start_gap_s':min(gaps),
            'maximum_rate_gate_pass':min(gaps)+1e-14>=1/stimulation['max_rate_per_profile_hz'],
            'configured_period_gate_pass':min(gaps)+1e-14>=period})
    return {'id':profile['id'], 'electrical_occupied_s':occupied,
        'source_service_interval_s':service,
        'per_profile_rate_gate_pass': all(row['maximum_rate_gate_pass'] for row in profile_rows),
        'configured_profile_period_gate_pass':all(row['configured_period_gate_pass'] for row in profile_rows),
        'logical_profiles':profile_rows,
        'physical_sources':rows,
        'physical_source_schedule_gate_pass': all(row['no_service_overlap'] for row in rows),
        'qualification':'Allocated service timing only; actual rearm/route/return/polarization health still required'}


def evaluate_profile(profile, design, preguard):
    st, mon, pw = (design[k] for k in ('stimulation', 'monitoring', 'power'))
    current, duration, freq = (profile[k] for k in ('current_A', 'phase_s', 'frame_hz'))
    events, sources = profile['events_per_frame'], profile['sources_per_event']
    rail = profile['boost_V']
    terminal = min(st['max_usable_terminal_V'], rail - st['reserved_voltage_headroom_V'])
    charge = current * duration
    uncertainty = phase_uncertainty(current, duration, mon)
    rail_power = rail * current * 2 * duration * freq * events * sources
    base = sum(pw[k] for k in ('afe_allocation_W', 'compute_network_allocation_W',
        'monitor_reference_gate_allocation_W', 'low_voltage_regulation_allocation_W',
        'driver_quiescent_allocation_W', 'boost_overhead_allocation_W'))
    total_power = base + rail_power / pw['boost_efficiency']
    load_power = current**2 * profile['load_ohm'] * 2 * duration * freq * events * sources
    case_heat = total_power - load_power
    if case_heat < 0:
        raise ValueError('Load cannot consume more power than declared source supplies')
    rise = case_heat * pw['thermal_resistance_selected_K_per_W']
    terminal_need = current * profile['load_ohm'] + st['pair_polarization_allowance_V']
    intervals, blanked = periodic_union(1/freq, profile['offsets_s'],
        2*duration + st['interphase_s'] + profile['recovery_s'], preguard)
    gates = {
        'per_profile_rate':source_schedule(profile,st)['per_profile_rate_gate_pass'],
        'configured_profile_period':source_schedule(profile,st)['configured_profile_period_gate_pass'],
        'physical_source_availability':source_schedule(profile,st)['physical_source_schedule_gate_pass'],
        'joint_command_charge': charge <= st['command_charge_ceiling_C'],
        'delivery_charge_with_uncertainty': charge + uncertainty <= st['delivery_charge_ceiling_C'],
        'simple_compliance': terminal_need <= terminal,
        'average_cell_current_at_low_voltage': total_power / pw['battery_low_V'] <= pw['selected_average_cell_current_limit_A'],
        'steady_selected_package_rise': rise <= pw['package_temperature_rise_target_K'],
    }
    motor_observation_gates = {
        'global_coverage': 1-blanked >= .65,
        'each_20ms_history': minimum_window_usable(intervals, 1/freq, .02) >= .65,
    }
    target = pw['package_temperature_rise_target_K']
    time_to_rise = None if rise <= target else (
        -pw['thermal_resistance_selected_K_per_W'] * pw['effective_heat_capacity_J_per_K']
        * math.log(1 - target / rise))
    return {
        'id': profile['id'], 'phase_charge_uC': charge * 1e6,
        'phase_charge_uncertainty_uC': uncertainty * 1e6,
        'phase_charge_relative_uncertainty': uncertainty / charge,
        'charge_density_uC_per_cm2': charge * 1e6 / (st['active_contact_area_mm2'] / 100),
        'terminal_required_V': terminal_need, 'terminal_available_V': terminal,
        'base_power_mW': base * 1000, 'rail_power_mW': rail_power * 1000,
        'stim_battery_power_mW': rail_power / pw['boost_efficiency'] * 1000,
        'total_battery_power_mW': total_power * 1000,
        'bulk_load_power_mW': load_power * 1000,
        'conservative_case_heat_mW': case_heat * 1000,
        'average_cell_current_low_mA': total_power / pw['battery_low_V'] * 1000,
        'runtime_h_under_declared_energy': pw['battery_nominal_V'] * pw['battery_capacity_Ah'] * pw['usable_energy_fraction'] / total_power,
        'steady_package_rise_K': rise,
        'time_from_ambient_to_target_s': time_to_rise,
        'max_thermal_resistance_for_steady_target_K_per_W': target / case_heat,
        'blanked_fraction_with_preguard': blanked,
        'minimum_usable_fraction_in_20ms_history': minimum_window_usable(intervals, 1/freq, .02),
        'electrical_intervals_s': intervals,
        'selected_continuous_gates': gates,
        'all_selected_continuous_gates_pass': all(gates.values()),
        'motor_observation_gates': motor_observation_gates,
        'qualification': 'Conditional arithmetic only; recruitment, chemistry, hardware bounds and thermal resistance unqualified',
    }


def calculate():
    d = json.loads((INPUT / 'system-design.json').read_text(encoding='utf-8'))
    a = json.loads((INPUT / 'acquisition-budget-inputs.json').read_text(encoding='utf-8'))
    t = json.loads((INPUT / 'timing-budget-inputs.json').read_text(encoding='utf-8'))
    n, fs = d['recording']['sampled_differential_streams'], d['recording']['sample_rate_per_stream_hz']
    c, m = d['compute'], d['monitoring']
    memory_fields = ('firmware_stack_heap_bytes', 'feature_state_bytes', 'monitor_dma_bytes',
        'adc_dma_bytes', 'telemetry_command_validity_bytes', 'expert_policy_bytes')
    archive_bytes = c['archive_record_bytes_per_scan'] * d['recording']['archive_rate_per_stream_hz'] * c['archive_buffer_s']
    memory_bytes = archive_bytes + sum(c[k] for k in memory_fields)
    ac = a['compute']
    macs = n * (fs * (ac['simple_biquads_per_stream'] * ac['MACs_per_biquad_per_sample']
        + ac['power_envelopes_per_stream'] * ac['MACs_per_envelope_per_sample'])
        + d['recording']['archive_rate_per_stream_hz'] * a['archive_filter']['tap_count'])
    macs += ac['linear_witness_inputs'] * ac['linear_witness_outputs'] * ac['linear_witness_update_Hz']
    monitor_rate = d['stimulation']['max_simultaneous_sources'] * (m['current_rate_per_active_source_hz'] + m['voltage_rate_per_active_source_hz']) + m['other_health_samples_per_s']
    cycles = (macs * ac['assumed_cycles_per_MAC']
              + ac['channel_admin_cycle_allocation_per_s_at16streams']
              + fs * ac['acquisition_burst_ISR_cycles']
              + monitor_rate * ac['monitor_integration_assumed_cycles_per_sample']) * (1+ac['cycle_contingency_fraction'])
    compute = {
        'MAC_per_s': macs, 'analytical_cycles_per_s': cycles,
        'cpu_fraction_128MHz': cycles / c['clock_hz'],
        '128MHz_60pct_budget_pass': cycles <= c['clock_hz'] * c['cpu_fraction_limit'],
        '64MHz_60pct_budget_pass': cycles <= 64000000 * c['cpu_fraction_limit'],
        'archive_ring_bytes': archive_bytes, 'application_ram_allocated_bytes': memory_bytes,
        'application_ram_headroom_fraction': 1-memory_bytes/c['ram_bytes'],
        '20pct_ram_headroom_gate_pass': memory_bytes <= c['ram_bytes']*(1-c['ram_headroom_minimum_fraction']),
        'two_second_raw4k_ram_bytes': memory_bytes + archive_bytes,
        'two_second_raw4k_fits_physical_ram': memory_bytes + archive_bytes <= c['ram_bytes'],
        'neural_scan_occupancy_fraction': d['recording']['command_words_per_scan'] * d['recording']['command_word_interval_s'] * fs,
        'neural_scan_wire_fraction': d['recording']['command_words_per_scan'] * d['recording']['word_bits'] * fs / d['recording']['spi_clock_hz'],
        'monitor_samples_per_s': monitor_rate,
        'monitor_ADC_utilization': monitor_rate/m['adc_max_aggregate_hz'],
        'monitor_SPI_utilization_with_overhead': monitor_rate*m['spi_word_bits']/m['spi_clock_hz']*(1+m['command_overhead_fraction']),
    }
    flash = {
        'application_flash':memory_allocation(c['application_flash_bytes'],c['application_flash_allocations_bytes'],c['flash_headroom_minimum_fraction']),
        'network_flash':memory_allocation(c['network_flash_bytes'],c['network_flash_allocations_bytes'],c['flash_headroom_minimum_fraction']),
        'network_ram':memory_allocation(c['network_ram_bytes'],c['network_ram_allocations_bytes'],c['ram_headroom_minimum_fraction']),
        'linked_images_measured':False,
        'resident_second_application_image_included':False,
    }
    bus=d['output_configuration_bus']
    wire=bus['max_transaction_bytes']*8/bus['spi_clock_hz']
    pressure_profile=next(p for p in d['profiles'] if p['id']=='pressure_reference')
    command_bus={'peripheral':bus['peripheral'], 'maximum_transaction_wire_s':wire,
        'total_admission_allocation_s':wire+bus['nonwire_admission_allowance_s'],
        'admission_gate_pass':wire+bus['nonwire_admission_allowance_s']<=bus['admission_allowance_s']+1e-14,
        'pressure_mean_wire_utilization':bus['max_bytes_per_source_event']*8*pressure_profile['events_per_frame']*pressure_profile['sources_per_event']*pressure_profile['frame_hz']/bus['spi_clock_hz'],
        'actual_component_command_protocol_qualified':False}
    noise = []
    for case in a['signal_model_inputs']['noise_cases']:
        rr, rf = case['recording_effective_resistance_ohm'], case['reference_effective_resistance_ohm']
        omega = 2*math.pi*case['common_mode_frequency_Hz']
        cin = a['acquisition_witness']['input_capacitance_F']
        mismatch = abs(1/(1+1j*omega*rr*cin) - 1/(1+1j*omega*rf*n*cin))*case['common_mode_RMS_V']
        johnson = math.sqrt(4*1.380649e-23*310*(math.pi*300/3)*(rr+rf+2*4990))
        intrinsic = case['common_mode_RMS_V']*10**(-82/20)
        quant = d['recording']['input_lsb_uV']*1e-6/math.sqrt(12)
        total = math.sqrt(sum(x*x for x in [mismatch,johnson,intrinsic,quant,case['AFE_noise_RMS_V'],case['alias_RMS_allowance_V']]))
        snr = 20*math.log10(1e-5/total)
        noise.append({'id':case['id'], 'common_mode_mismatch_uV': mismatch*1e6,
            'Johnson_uV':johnson*1e6, 'intrinsic_CMRR_uV':intrinsic*1e6,
            'total_RSS_uV':total*1e6, 'SNR_at_10uV_dB':snr,
            'quiet_10dB_gate_pass':snr>=10})
    telemetry = d['telemetry']
    payload = sum(telemetry[k+'_records_per_s']*telemetry[k+'_record_bytes']
                  for k in ['feature','delivery','health'])*8*telemetry['payload_headroom_factor']
    preguard = t['parameters']['stimulus_preguard']['value']
    profiles = [evaluate_profile(p, d, preguard) for p in d['profiles']]
    archive_support=(a['archive_filter']['tap_count']-1)/fs
    for p,profile in zip(d['profiles'],profiles):
        _,archive_mask=periodic_union(1/p['frame_hz'],p['offsets_s'],
            2*p['phase_s']+d['stimulation']['interphase_s']+p['recovery_s']+archive_support,preguard)
        profile['archive_FIR_invalid_fraction_any_raw_invalid_rule']=archive_mask
    scaling=[]
    for alt in a['scaling_alternatives']:
        nn=alt['streams']; ratio=nn/n
        scaled_macs=macs*ratio
        scaled_cycles=(scaled_macs*ac['assumed_cycles_per_MAC']
            +ac['channel_admin_cycle_allocation_per_s_at16streams']*ratio
            +fs*ac['acquisition_burst_ISR_cycles']*alt['AFE_chips']
            +monitor_rate*ac['monitor_integration_assumed_cycles_per_sample'])*(1+ac['cycle_contingency_fraction'])
        scaled_ram=(nn*2+alt['header_bytes'])*2000*2 + 32768*ratio +8192*ratio+131072+32768+8192
        scaling.append({'streams':nn,'montage':'local_bipolar' if alt['references']==0 else 'shared_reference',
            'total_body_ports_including18_output':alt['record_contacts']+alt['references']+alt['bias']+18,
            'cycles_per_s':scaled_cycles,'RAM_bytes':scaled_ram,
            'CPU60pct_gate_pass':scaled_cycles<=128000000*.6,
            'RAM20pct_headroom_gate_pass':scaled_ram<=524288*.8,
            'task_information_sufficiency_established':False})
    coefficients=np.array(a['archive_filter']['coefficients'])
    def filter_db(freq):
        response=np.exp(-2j*np.pi*np.asarray(freq)[:,None]*np.arange(len(coefficients))/fs)@coefficients
        return 20*np.log10(np.maximum(np.abs(response),1e-15))
    pass_db=filter_db(np.linspace(0,300,3001)); stop_db=filter_db(np.linspace(1700,2000,3001))
    filters={'archive_taps':len(coefficients),'archive_DC_gain':float(coefficients.sum()),
        'archive_symmetry_error':float(np.max(np.abs(coefficients-coefficients[::-1]))),
        'archive_max_loss_0to300Hz_dB':float(-np.min(pass_db)),
        'archive_min_attenuation_1700to2000Hz_dB':float(-np.max(stop_db)),
        'archive_causal_support_s':archive_support,
        'fast_band_max_ideal_group_delay_ms':1000*max(group_delay(f) for f in np.linspace(20,300,10001)),
        'archive_0p5dB_passband_gate_pass':float(-np.min(pass_db))<=.5,
        'archive60dB_stopband_gate_pass':float(-np.max(stop_db))>=60,
        'recursive_feature_artifact_reset_and_warmup_qualified':False}
    compliance = []
    for load in d['stimulation']['pair_load_stress_ohm']:
        for cap in d['stimulation']['effective_pair_capacitance_stress_F']:
            st = d['stimulation']
            # Pair capacitance differs from per-contact capacitance. No double counting.
            imax = min(st['max_current_A'], (40-4)/load, (40-1)/(load+.0005/cap))
            compliance.append({'bulk_load_ohm':load,'pair_C_uF':cap*1e6,
                'max_current_at500us_mA':imax*1000, 'minimum_of_joint_voltage_bounds':True})
    blanking = []
    for recovery in [.001,.003,.005,.01325]:
        for guard in [0.0,preguard]:
            intervals, fraction = periodic_union(1/120,[0,.002,.004],.0006+.0001+recovery,guard)
            blanking.append({'recovery_ms':recovery*1000,'preguard_ms':guard*1000,
                'blanked_fraction':fraction,'minimum_20ms_usable_fraction':minimum_window_usable(intervals,1/120,.02)})
    timing = t['latency_analysis']
    chain = sum(x['maximum_s'] for x in timing['fast_unframed_chain'])
    frame_cases = [{'frame_hz':hz,'reactive_bound_ms':1000*(chain+1/hz),
        'passes25ms_chosen_deadline':chain+1/hz <=.025} for hz in [20,40,60,120]]
    thermal = []
    for profile in profiles:
        for rt in d['power']['thermal_resistance_stress_K_per_W']:
            rise = profile['conservative_case_heat_mW']/1000*rt
            thermal.append({'profile':profile['id'],'Rtheta_K_per_W':rt,
                'steady_rise_K':rise,'chosen2K_gate_pass':rise<=2})
    recharge = []
    for current in [.02,.1]:
        stored = current*4.0
        received = stored/.85
        heat = received-stored+.010
        recharge.append({'charge_current_mA':current*1000,'declared_battery_V':4.0,
            'received_DC_mW':received*1000,'stored_power_mW':stored*1000,
            'idle_and_conversion_case_heat_mW':heat*1000,
            'steady_selected_rise_K':heat*20,
            'ideal_capacity_over_current_h':.2/current,
            'status':'Idle-only assumed charging budget; coil RF loss, taper, alignment and operation while charging unresolved'})
    s = d['stimulation']
    reservoir_charge = s['max_simultaneous_sources']*s['max_current_A']*2*s['max_phase_s']
    return {
        'schema':'SCCI_RH-S2-budget-1', 'date':d['date'],
        'evidence_type':'Deterministic analytical allocations with declared assumptions; no hardware or biological measurements',
        'compute_and_transport':compute, 'quiet_noise':noise,'filters':filters,'channel_scaling':scaling,
        'companion_power': {
            'selected_external_source_W':d['companion_power']['external_regulated_source_V']*d['companion_power']['selected_source_current_limit_A'],
            'base_allocation_W':sum(d['companion_power'][k] for k in ['bridge_compute_network_allocation_W','display_allocation_W','sensor_interface_allocation_W','regulation_loss_allocation_W']),
            'external_pressure_sensor_is_separately_powered':True,
            'charger_and_RF_field_losses_closed':False},
        'telemetry': {'normal_service_with_headroom_bps':payload,
            'normal160k_target_pass':payload<=telemetry['normal_payload_capacity_bps'],
            'raw4k_framed_bps':fs*48*8,'raw4k_1M_target_pass':fs*48*8<=telemetry['raw_recording_payload_capacity_bps'],
            'raw2k_framed_bps':2000*48*8,
            'targets_verified_through_tissue':False},
        'profiles':profiles,'flash_and_network_memory':flash,
        'output_configuration_bus':command_bus,
        'physical_source_schedules':[source_schedule(p,d['stimulation']) for p in d['profiles']],
        'compliance_sweep':compliance,'pressure_blanking_sweep':blanking,
        'reactive_frame_wait':frame_cases, 'fast_chain_ms':chain*1000,
        'uniform20ms_history_representative_age_ms':(chain+.010)*1000,
        'with_archive_representative_age_ms':(chain+.010+.00375)*1000,
        'ideal_filter_group_delay_at1Hz_ms':group_delay(1)*1000,
        'thermal_sensitivity':thermal,'idle_charging':recharge,
        'reservoir': {'two_source_charge_uC':reservoir_charge*1e6,
            'droop_V':reservoir_charge/s['hv_reservoir_effective_F'],
            'droop2V_gate_pass':reservoir_charge/s['hv_reservoir_effective_F']<=2,
            'energy_at48V_mJ':.5*s['hv_reservoir_effective_F']*48**2*1000,
            'capacitor_effective_at_bias_verified':False},
        'continuous_operating_claim':'Reference profiles pass selected arithmetic gates only under stated load, thermal, efficiency and signal assumptions. Passing is not clinical, circuit or electrochemical qualification.',
        'rejected_scaling':['64MHz with selected monitor/feature workload','2s raw4k buffer in512KiB','continuous raw4k stream at1Mbit/s application target','all-max output combination','neural fast decode during dense pressure stimulation'],
    }


def write_outputs(result):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'budget-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    for name, key in [('noise','quiet_noise'),('compliance','compliance_sweep'),
                      ('blanking','pressure_blanking_sweep'),('thermal','thermal_sensitivity'),
                      ('reactive-timing','reactive_frame_wait'),('channel-scaling','channel_scaling')]:
        rows = result[key]
        with (OUTPUT/f'{name}.csv').open('w',encoding='utf-8',newline='') as out:
            writer=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)


def equivalent(a, b):
    """Cross-platform numerical comparison; categorical gates stay exact."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
    return a == b


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    result=calculate()
    if args.check:
        previous=json.loads((OUTPUT/'budget-summary.json').read_text(encoding='utf-8'))
        if not equivalent(previous, result):
            raise SystemExit('Committed Stage2 budgets differ from reproducible calculation')
        print('Stage2 analytical budgets reproduce within 1e-10 relative / 1e-12 absolute tolerance; gates exact')
    else:
        write_outputs(result)
        print('Wrote Stage2 analytical budgets; no measured efficacy or hardware qualification')


if __name__ == '__main__':
    main()
