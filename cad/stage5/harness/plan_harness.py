"""Bind mechanical mating and routing allocations to the frozen electrical system.

Run with ordinary Python. These routes are service-planning centerlines, not a
manufacturing wire loom or electrical signal-integrity model.
"""
from pathlib import Path
import csv
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ST4 = ROOT / 'electronics/stage4/integrated-pcb/integration'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def digest(path):
    data = (ROOT / path).read_bytes()
    if str(path).endswith(('.json', '.csv', '.py', '.kicad_pcb')):
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def main():
    reference = read('cad/stage5/reference/contract.json')
    datums = read(reference['source_datums'])
    electrical = read('electronics/stage4/integrated-pcb/integration/harness.json')
    system = read('electronics/stage4/integrated-pcb/integration/system.json')
    boards = {b['board']: b for b in reference['boards']}
    native_connectors = {(b['board'], c['reference']): c
                         for b in datums['boards'] for c in b['connectors']}
    components = {(c['board'], c['reference']): c for c in system['components']}
    used = {(c['board'], c['pcb_reference']): c for c in electrical['connectors']}
    external = {('recording-front-end', 'J30003'): 'recording artificial input',
                ('supervision', 'J50101'): 'post-guard artificial load output',
                ('power', 'J60001'): 'external protected pack / supply',
                ('monitoring-transport', 'J70008'): 'external isolated companion',
                ('controller-carrier', 'J80002'): 'external target SWD'}
    assert not (set(used) & set(external))
    mates = []
    endpoints = {}
    for key in sorted(set(used) | set(external)):
        board_id, ref = key
        b = boards[board_id]
        c = native_connectors[key]
        comp = components[key]
        pins = {p['number']: p for p in comp['pins']}
        pads = sorted(c['pads'], key=lambda p: int(p['number']))
        assert len(pads) == len(pins)
        tr = b['translation_mm']
        axis_pins = []
        for p in pads:
            x, y = p['position_mm']
            position = [tr[0] + x, tr[1] - y, tr[2] + 4.2]
            end = dict(board=board_id, reference=ref, pin=p['number'],
                       net=pins[p['number']]['net'], source_net=pins[p['number']]['source_net'],
                       axis_mm=position, wire_exit_mm=[position[0], position[1], tr[2] + 18.2])
            endpoints[(board_id, ref, p['number'])] = end
            axis_pins.append(end)
        a, z = axis_pins[0]['axis_mm'], axis_pins[-1]['axis_mm']
        ux, uy = z[0]-a[0], z[1]-a[1]
        length = math.hypot(ux, uy)
        assert abs(length - 2.54*(len(pads)-1)) < 1e-5
        unit = [ux/length, uy/length, 0]
        mates.append(dict(board=board_id, pcb_reference=ref,
                          label=f'Mate_{board_id.replace("-", "_")}_{ref}',
                          category='internal_mate' if key in used else 'external_mate',
                          purpose=external.get(key, used.get(key, {}).get('value')),
                          pin_count=len(pads), pins=axis_pins,
                          pin1_mm=a, direction_unit=unit,
                          housing_length_mm=2.54*(len(pads)-1)+2.74,
                          housing_width_mm=2.50, housing_height_mm=14,
                          square_cavity_mm=0.95, nominal_pin_mm=0.64,
                          material='Nominal black PPE+PS housing envelope',
                          candidate_family='Harwin M20-106; final plating/contact/gauge and retention unqualified'))

    # Each unique terminal gets one branch lead. Shared logical rows do not
    # require several physical conductors to be forced into the same crimp.
    terminal_routes = []
    for idx, (key, e) in enumerate(sorted(endpoints.items())):
        b = boards[e['board']]
        x, y, z = e['wire_exit_mm']
        route_z = b['board_bottom_z_mm'] + 26
        spine_x = 346 if b['bay'] == 'left' else 364
        points = [e['wire_exit_mm'], [x, y, route_z], [spine_x, y, route_z]]
        terminal_routes.append(dict(id=f'T{idx+1:03}', endpoint=e,
                                    connector_key=[key[0], key[1]], points_mm=points,
                                    purpose='Connector fanout to service spine; nonphysical planning centerline',
                                    bend_radius_allocation_mm=5,
                                    bend_status='Polyline corners require a later detailed flexible routing design'))
    routes_by_end = {(r['endpoint']['board'], r['endpoint']['reference'],
                      r['endpoint']['pin']): r for r in terminal_routes}
    wires = []
    for w in electrical['wires']:
        ends = [endpoints[(e['board'], e['reference'], str(e['pin']))] for e in w['ends']]
        assert len(ends) == 2
        assert all(e['net'] == w['net'] for e in ends)
        fan = [routes_by_end[(e['board'], e['reference'], str(e['pin']))] for e in w['ends']]
        p, q = fan[0]['points_mm'][-1], fan[1]['points_mm'][-1]
        # A cross-bay route crosses only in the unobstructed central spine.
        middle = [p, [p[0], q[1], p[2]], [q[0], q[1], p[2]], q]
        points = fan[0]['points_mm'] + middle[1:] + list(reversed(fan[1]['points_mm'][:-1]))
        nominal = sum(math.dist(a,b) for a,b in zip(points, points[1:]))
        wires.append(dict(id=w['id'], net=w['net'], purpose=w['purpose'], ends=ends,
                          terminal_routes=[r['id'] for r in fan], points_mm=points,
                          nominal_centerline_length_mm=round(nominal,3),
                          planning_length_with_slack_mm=5*math.ceil((nominal*1.2+30)/5),
                          length_status='Planning estimate only; shared branch rows are not independent wire cuts'))
    assert len(wires) == 258 and len(used) == 78

    old_ports = list(csv.DictReader((ROOT/'docs/stage2/functional-port-map.csv').open(newline='', encoding='utf-8')))
    port_map = []
    for index, port in enumerate(old_ports):
        key = ('recording-front-end', 'J30003', str(index+1)) if index < 18 else ('supervision', 'J50101', str(index-17))
        e = endpoints[key]
        port_map.append(dict(port_id=port['port_id'], logical_function=port['logical_function'],
                             board=e['board'], pcb_reference=e['reference'], pin=e['pin'],
                             source_net=e['source_net'], integrated_net=e['net'],
                             mechanical_mate=f'Mate_{e["board"].replace("-", "_")}_{e["reference"]}',
                             guard_boundary='AFE recording protection' if index<18 else 'After independent output disconnect guards',
                             scope='Artificial reference connection; future implanted port function only'))
    assert len(port_map) == 36 and len({p['integrated_net'] for p in port_map}) == 36
    fields=list(port_map[0])
    with (HERE/'body-port-bridge.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(port_map)
    with (HERE/'wire-length-planning.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['wire_id','net','end_a','end_b','nominal_centerline_mm','planning_slack_mm','status'])
        for w in wires:
            writer.writerow([w['id'],w['net'],*[f'{e["board"]}:{e["reference"]}:{e["pin"]}' for e in w['ends']],w['nominal_centerline_length_mm'],w['planning_length_with_slack_mm'],w['length_status']])
    paths=['cad/stage5/reference/contract.json',reference['source_datums'],
           'electronics/stage4/integrated-pcb/integration/harness.json',
           'electronics/stage4/integrated-pcb/integration/system.json',
           'docs/stage2/functional-port-map.csv', 'cad/stage5/harness/plan_harness.py']
    contract=dict(schema='scci_rh.stage5.harness-contract.v1', units='mm',
                  baseline_commit='7a4371b7ff891248a5ab4f12e3149268485d828f',
                  native='cad/stage5/harness/SCCI_RH_mating_interfaces.FCStd',
                  step='cad/stage5/harness/SCCI_RH_mating_interfaces.step',
                  routing_native='cad/stage5/harness/SCCI_RH_harness_routes.FCStd',
                  sources={p:digest(p) for p in paths},
                  mates=mates, wires=wires, terminal_routes=terminal_routes,
                  branch_nodes=electrical['splices'], body_ports=port_map,
                  internal_mates=78, external_mates=5,
                  rear_ports=reference['external_ports'],
                  routing_envelopes=reference['service_volumes'],
                  assumptions=[
                      'Mating envelopes use published Harwin M20-106 family dimensions; internal contact spring/crimp details are simplified away.',
                      'Housing cavities accept nominal 0.64mm square pins with a 0.95mm square modeled opening; contact pressure is not simulated.',
                      'Route centerlines are nonphysical planning annotations. Crossings do not establish a feasible packed loom.',
                      '5mm bend radius is reserved, not verified along these unsmoothed planning polylines.',
                      '20 percent service slack and 30mm termination allowance estimate routed lengths; this is not a wire cut list.',
                      '47 branched electrical nodes need insulated splices and one terminated branch per terminal, preserving distinct return domains.',
                      'Wire gauge, current derating, shield termination, locking, HV clearance and electrical timing remain unqualified.',
                      'Disconnect labeled plugs before tray withdrawal; no live sliding operation is proposed.'
                  ],
                  manufacturer_sources=[dict(title='Harwin M20-1060700 product and dimensions',url='https://www.harwin.com/products/M20-1060700', accessed='2026-10-16'),
                                        dict(title='Harwin M20-106 family drawing',url='https://content.harwin.com/asset/b9496f9a-d89f-420f-aea9-abb4534be02f/DRG-00376-Technical-Drawing-Datasheet-M20-106-pdf.pdf',accessed='2026-10-16')])
    (HERE/'contract.json').write_text(json.dumps(contract,indent=2)+'\n',encoding='utf-8')
    print(f'{len(mates)} mating housings, {len(terminal_routes)} unique terminal fanouts, 258 logical rows, 47 branch nodes and 36 cross-stage body functions bound.')


if __name__=='__main__':
    main()
