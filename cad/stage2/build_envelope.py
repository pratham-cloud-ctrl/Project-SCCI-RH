"""Parametric Stage2 allocation assembly; requires build123d0.13.

No anatomical, hermetic, RF, populated-board or fabricated-device claim.
All dimensions mm, read from the selected system configuration.
"""
from pathlib import Path
import json
from itertools import combinations
import build123d as b

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
d=json.loads((ROOT/'docs/stage2/system-design.json').read_text(encoding='utf-8'))
m=d['mechanical']
MIN=(b.Align.MIN,b.Align.MIN,b.Align.MIN)


def box(size,position,label,color):
    shape=b.Pos(*position)*b.Box(*size,align=MIN)
    shape.label=label
    shape.color=b.Color(color)
    return shape


def overlap(a,c):
    intersection=a.intersect(c)
    return 0.0 if intersection is None else intersection.volume


def build():
    w,h,z=m['can_outer_mm']; wall=m['wall_mm']
    outer=box((w,h,z-wall),(0,0,0),'Core_Can_Open','#8996A2')
    inner=box((w-2*wall,h-2*wall,z-2*wall),(wall,wall,wall),'void','#FFFFFF')
    can=outer-inner
    feedthroughs=[]
    for row in range(2):
        for col in range(18):
            x=4.5+3*col; height=5+4*row
            transform=b.Pos(x,h-wall-.1,height)*b.Rot(-90,0,0)
            bore=transform*b.Cylinder(.50,wall+.2,align=(b.Align.CENTER,b.Align.CENTER,b.Align.MIN))
            can=can-bore
            insulator=transform*(b.Cylinder(.49,wall+.2,align=(b.Align.CENTER,b.Align.CENTER,b.Align.MIN))
                - b.Cylinder(.17,wall+.2,align=(b.Align.CENTER,b.Align.CENTER,b.Align.MIN)))
            insulator.label=f'Unqualified_Insulator_{row*18+col+1:02d}'
            insulator.color=b.Color('#E3DCC5')
            pin=transform*b.Cylinder(.15,wall+.2,align=(b.Align.CENTER,b.Align.CENTER,b.Align.MIN))
            pin.label=f'Interface_Port_{row*18+col+1:02d}'
            pin.color=b.Color('#B3914B')
            feedthroughs.extend([insulator,pin])
    can.label='Core_Can_Open'; can.color=b.Color('#8996A2')
    lid=box((w,h,wall),(0,0,z-wall),'Core_Lid_Unsealed','#8996A2')
    header=box(m['header_mm'],(0,h,0),'Dielectric_Header_Allocation','#A4CFCF')
    pcb=box(m['pcb_mm'],(5,4,m['pcb_bottom_z_mm']),'Unpopulated_PCB_Allocation','#237A67')
    populated=box((50,40,m['component_height_allocation_mm']),(5,4,2.8),'Populated_Zone_Reservation','#B7CFCA')
    battery=box(m['battery_box_mm'],(12,10,m['battery_bottom_z_mm']),'Contego_200_Bounding_Box','#DCB868')
    bank=box((24,14,3),(7,29,2.8),'Effective_HV_Capacitor_Bank_Reservation','#527DAB')
    # Separate22mm body +2mm lid preserve the24mm total envelope.
    hub=box((100,60,22),(80,0,0),'Hub_Open_Housing','#8996A2')-box((96,56,20),(82,2,2),'void','#FFFFFF')
    hub.label='Hub_Open_Housing'
    hub_lid=box((100,60,2),(80,0,22),'Hub_Lid_Unsealed','#8996A2')
    physical=[can,lid,header,pcb,battery,bank,hub,hub_lid,*feedthroughs]
    # Parent populated zone intentionally contains the bank; it is a reservation
    # export, not a second occupied physical part in overlap analysis.
    collision_rows=[]
    for a,c in combinations(physical[:8],2):
        volume=overlap(a,c)
        collision_rows.append({'a':a.label,'b':c.label,'overlap_mm3':volume})
    assert all(r['overlap_mm3']<1e-6 for r in collision_rows),collision_rows
    assert overlap(can,battery)<1e-6
    interface_checks=[{'part':s.label,'metal_can_overlap_mm3':overlap(can,s)} for s in feedthroughs]
    assert all(r['metal_can_overlap_mm3']<1e-6 for r in interface_checks)
    assert m['battery_bottom_z_mm']+m['battery_box_mm'][2] <= z-wall
    assert m['body_feedthrough_ports']==36
    assembly=b.Compound(label='SCCI_RH_Stage2_Allocation',children=physical)
    b.export_step(assembly,str(OUT/'SCCI_RH_stage2_allocation.step'))
    b.export_step(populated,str(OUT/'populated_zone_reservation.step'))
    dimensions=[]
    for part in physical:
        bb=part.bounding_box()
        dimensions.append({'name':part.label,'volume_mm3':part.volume,
            'bbox_min_mm':list(bb.min),'bbox_max_mm':list(bb.max),'valid_BRep':part.is_valid})
    assert all(p['valid_BRep'] and p['volume_mm3']>0 for p in dimensions)
    report={'date':d['date'],'scope':'Nominal allocation solids, not finished implant CAD or anatomy',
        'core_outer_with_header_mm':[w,h+m['header_mm'][1],z],
        'hub_outer_mm':m['hub_outer_mm'],'ports':36,'assembly_solid_count':len(physical),
        'battery_to_component_zone_gap_mm':m['battery_bottom_z_mm']-(m['pcb_bottom_z_mm']+m['pcb_mm'][2]+m['component_height_allocation_mm']),
        'battery_to_lid_gap_mm':z-wall-(m['battery_bottom_z_mm']+m['battery_box_mm'][2]),
        'pairwise_major_solids_intersection_checks':collision_rows,
        'interface_can_checks':interface_checks,
        'reservation_semantics':'Header dielectric allocation contains interface pins/insulators; populated zone contains HV bank. These containment relations are intentional reservations, not an interference pass for a manufactured assembly.',
        'parts':dimensions,
        'unestablished':['Native populated KiCad board','Hermetic feedthrough construction','Anatomical fit','RF/coil dimensions and losses','Cell insulation thickness and final tolerance stack','Real effective HV capacitor footprint']}
    (OUT/'allocation-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'Exported{len(physical)} nominal solids;36 ports; major solids do not intersect')


if __name__=='__main__':build()
