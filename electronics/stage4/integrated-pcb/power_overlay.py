"""Add the populated controller to the preserved seven-package power budget.

No physical power measurement is implied. Run --write-results only to publish
a reviewed new revision; the default checks the saved numerical result.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def calculate():
    files = [ROOT/'electronics/stage4/power-study/budget-results.json',
             ROOT/'electronics/stage4/transport-study/input-results.json',
             ROOT/'electronics/stage4/controller-carrier/connectivity.json',
             HERE/'firmware-profile/build-receipt.json', Path(__file__)]
    old, transport, carrier, firmware = [json.loads(p.read_text()) for p in files[:4]]
    prev = transport['power_overlay']
    rail = old['inventory']['rails']['HOST_3V3']
    voltage = carrier['nominal']['host_supply_V']
    biases = [p for p in carrier['parts'] if p['ref'].startswith('R') and p['value'] == '10k']
    assert len(biases) == 41
    bias_current = len(biases)*voltage/10000
    allocation = {
        'previous_active_packages_A': rail['active_allocations_A'],
        'previous_passive_dynamic_contingency_A': rail['passive_dynamic_output_load_contingency_A'],
        'transport_new_parts_A': prev['HOST_3V3_new_parts_A'],
        'BT40F_module_declared_A': .060,
        'four_serializers_dynamic_declared_A': .005,
        'all_41_biases_opposed_A': bias_current,
    }
    cap = .160
    assert sum(allocation.values()) < cap
    efficiency = old['assumptions']['buck_load_efficiency']
    bus_extra = (cap-prev['HOST_3V3_new_cap_A'])*voltage/efficiency
    battery = old['battery']
    nominal = battery['nominal_V']
    bus = nominal-battery['seriesdiode_drop_V_assumed']
    added_battery = bus_extra*nominal/bus
    active = prev['active_W']+added_battery
    caps = []
    for p in carrier['parts']:
        if not p['ref'].startswith('C'):
            continue
        m = re.match(r'([0-9.]+)([un])', p['value'])
        assert m and set(p['nets'].values()) <= {'GND', 'MCU_3V3', 'HOST_3V3'}
        farads = float(m[1])*{'u':1e-6, 'n':1e-9}[m[2]]
        caps.append(dict(reference=p['ref'], capacitance_F=farads,
                         voltage_V=voltage, energy_J=.5*farads*voltage**2))
    sensitivity = []
    for eff in (.7, .8, .9):
        extra = (cap-prev['HOST_3V3_new_cap_A'])*voltage/eff*nominal/bus
        sensitivity.append(dict(incremental_buck_efficiency_assumed=eff,
                                active_W=prev['active_W']+extra,
                                runtime_h=battery['usable_Wh']/(prev['active_W']+extra)))
    return dict(
        schema='scci_rh.integrated-controller-power.v1', date='2026-10-15',
        scope='Conditional declared-load digital budget; not measured peak, runtime or thermal performance',
        source_sha256_lf={p.relative_to(ROOT).as_posix():sha(p) for p in files},
        preserved_previous_results=True,
        HOST_3V3_previous_cap_A=prev['HOST_3V3_new_cap_A'], HOST_3V3_new_cap_A=cap,
        allocations_A=allocation, allocated_A=sum(allocation.values()),
        unallocated_margin_A=cap-sum(allocation.values()),
        bias_resistors=[p['ref'] for p in biases],
        bias_interpretation='All 41 10k biases simultaneously opposed is a conservative sum, not an operating-state prediction; previous reserves retained',
        module_and_serializer_currents_are_design_allocations=True,
        previous_transport_active_W=prev['active_W'],
        incremental_bus_W=bus_extra, incremental_battery_W=added_battery,
        active_W=active, usable_energy_Wh=battery['usable_Wh'], runtime_h=battery['usable_Wh']/active,
        assumed_buck_efficiency=efficiency, nominal_battery_V=nominal, nominal_bus_V=bus,
        incremental_efficiency_sensitivity=sensitivity,
        capacitors=caps, carrier_capacitance_F=sum(c['capacitance_F'] for c in caps),
        carrier_energy_J=sum(c['energy_J'] for c in caps),
        carrier_energy_plus20percent_J=1.2*sum(c['energy_J'] for c in caps),
        target_image=dict(FLASH_bytes=firmware['memory']['FLASH']['used_bytes'],
                          RAM_bytes=firmware['memory']['RAM']['used_bytes']) if 'memory' in firmware else
                     dict(build_receipt='firmware-profile/build-receipt.json'),
        compact_implanted_thermal_2K_earned=False,
        converter_stability_inrush_efficiency_and_physical_execution_measured=False,
        limits=['Module 60 mA and serializer 5 mA are declared allocations, not guaranteed all-corner maxima.',
                'Incremental efficiency sweep changes only the new controller contribution; previous converters retain their frozen assumptions.',
                'External companion supply remains outside host battery allocation.',
                'Existing compact implant thermal failure remains; the eight large reference boards do not establish implant miniaturization.'])


def compare(actual, expected, path=''):
    if isinstance(actual, dict):
        assert actual.keys() == expected.keys(), path
        for key in actual: compare(actual[key], expected[key], path+'/'+key)
    elif isinstance(actual, list):
        assert len(actual) == len(expected), path
        for i, (a, b) in enumerate(zip(actual, expected)): compare(a, b, path+f'/{i}')
    elif isinstance(actual, float):
        assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-15), path
    else:
        assert actual == expected, path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--write-results', action='store_true')
    args = parser.parse_args(); result = calculate(); output = HERE/'power-overlay.json'
    if args.write_results: output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    else: compare(result, json.loads(output.read_text()))
    print(f"Integrated power: HOST_3V3 {result['allocated_A']*1000:.3f}/{result['HOST_3V3_new_cap_A']*1000:.0f} mA; conditional {result['active_W']:.6f} W / {result['runtime_h']:.6f} h")
