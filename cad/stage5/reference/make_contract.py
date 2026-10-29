"""Freeze Stage 5 reference transforms and native mounting datums before CAD generation."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
datums=json.loads((HERE/'board-datums.json').read_text())
left=['supervision','power','current-driver','contact-router'];right=['recording-front-end','monitoring-cell','monitoring-transport','controller-carrier']
boards=[];mounts=[];parts=[]
for d in datums['boards']:
    name=d['board'];slug=name.replace('-','_'); bay='left' if name in left else 'right'; tier=(left if bay=='left' else right).index(name)
    width,depth=[round(v,6) for v in d['outline_mm']];x=24 if bay=='left' else 390;y=30;z=28+50*tier
    board_label='PCB_'+slug
    boards.append(dict(board=name,label=board_label,bay=bay,tier=tier,source_step=d['step'],source_step_sha256=d['step_sha256'],source_pcb=d['pcb'],source_pcb_sha256_lf=d['pcb_sha256_lf'],translation_mm=[x,y+depth,z],rotation_axis_angle=[0,0,1,0],board_bottom_z_mm=z,board_outline_mm=[width,depth],fitted_components=d['fitted_components'],tray_label='Tray_'+slug))
    parts.append(dict(label=board_label,category='populated_board'))
    parts.append(dict(label='Tray_'+slug,category='tray'))
    parts.append(dict(label='Pull_'+slug,category='tray_pull'))
    for h in d['mounts']:
        hx,hy=h['position_mm'];axis=[x+hx,y+depth-hy];tag=slug+'_'+h['reference']
        m=dict(board=name,reference=h['reference'],axis_xy_mm=axis,board_hole_radius_mm=h['pads'][0]['drill_mm'][0]/2,standoff_label='Standoff_'+tag,upper_screw_label='UpperScrew_'+tag,lower_screw_label='LowerScrew_'+tag,standoff_outer_radius_mm=3.0,standoff_bore_radius_mm=1.5,screw_shaft_radius_mm=1.45,screw_head_radius_mm=2.75,tray_bottom_z_mm=16+50*tier,tray_top_z_mm=18+50*tier,standoff_bottom_z_mm=18+50*tier,standoff_top_z_mm=z,board_top_z_mm=z+1.53)
        mounts.append(m)
        parts.extend([dict(label=m['standoff_label'],category='board_standoff'),dict(label=m['upper_screw_label'],category='board_screw'),dict(label=m['lower_screw_label'],category='board_screw')])
for name in ['Base','SideLeft','SideRight','FrontPanel','RearPanel','Lid']:
    parts.append(dict(label=name,category='enclosure_panel'))
for bay,x0,x1 in [('left',18,330),('right',380,565)]:
    for tier in range(4):
        for side in ['left','right']:parts.append(dict(label=f'Rail_{bay}_{tier}_{side}',category='rail'))
for col in range(4):
    for row in range(2):
        parts.extend([dict(label=f'Post_{col}_{row}',category='frame_post'),dict(label=f'LidScrew_{col}_{row}',category='lid_screw')])
for i in range(4):parts.append(dict(label=f'Foot_{i}',category='foot'))
checks=[]
for b in boards:
    # Reference clearances measured from actual frozen package compounds, not from a substitute box.
    checks.append(dict(a=b['label'],b=b['tray_label'],minimum_mm=8.0,reason='Underside pin tips clear tray; mounting hardware checked separately'))
    if b['tier']<3:
        upper=(left if b['bay']=='left' else right)[b['tier']+1].replace('-','_')
        checks.append(dict(a=b['label'],b='Tray_'+upper,minimum_mm=20,reason='Minimum physical clearance between actual populated source and next tray'))
contract=dict(schema='scci_rh.stage5.reference-contract.v1',units='mm',design_scope='Serviceable eight-board digital reference chassis; no implant scale claim',case_dimensions_mm=[600,310,240],enclosure_material_allocations={'base_sides_rear_front':'nominal aluminium, no temper or process qualification','lid':'nominal clear polycarbonate, no impact qualification','trays':'nominal insulating polymer, no flammability or creep qualification','standoffs':'nominal insulating M3 female/female, thread detail omitted','fasteners':'nominal M3 fasteners, threads omitted with radial clearance'},tier_pitch_mm=50,tray_thickness_mm=2,standoff_length_mm=10,source_datums='cad/stage5/reference/board-datums.json',native='cad/stage5/reference/SCCI_RH_reference_assembly.FCStd',step='cad/stage5/reference/SCCI_RH_reference_assembly.step',exploded_step='cad/stage5/reference/SCCI_RH_reference_exploded.step',mechanical_step='cad/stage5/reference/SCCI_RH_reference_mechanical.step',boards=boards,mounts=mounts,parts=parts,allowed_intersections=[],clearance_checks=checks,service_volumes=[dict(name='central_cable_spine',min_mm=[336,20,18],max_mm=[374,290,230]),dict(name='rear_cable_corridor',min_mm=[18,296,18],max_mm=[565,307,229]),dict(name='right_cable_corridor',min_mm=[571,20,18],max_mm=[597,290,229])],external_ports=[dict(name='rear_artificial_load',cutout_min_mm=[32,307,194],cutout_max_mm=[122,310,222],purpose='Root-owned artificial-load harness pass-through; strain relief proposal'),dict(name='rear_companion',cutout_min_mm=[390,307,194],cutout_max_mm=[490,310,222],purpose='Root-owned companion/power/debug harness pass-through; connector choice unqualified')],service_instructions=['Remove lid and front cover, isolate external power, disconnect and label harness plugs before withdrawing any tray','Withdraw each tray toward negativeY; reserve at least310mm free front access','Boards do not carry mechanical loads from case panels; all32 original axes have independent10mm nominal standoffs','The cable service volumes are reservations; root-owned harness CAD and interference audit determine actual routes'],assembly_assumptions=['Native source package geometry is nominal and retains all original populated solids','Board holes are directly extracted from frozen nativePCB footprints; no5mm inset assumption','Connector mating allowances and bends are not electrical or fatigue qualification','No load, thermal, EMI, ingress, implant biocompatibility or sterilization qualification is claimed'])
(HERE/'contract.json').write_text(json.dumps(contract,indent=2)+'\n')
print('Frozen',len(boards),'boards,',len(mounts),'mount axes and',len(parts),'mechanical/board parts')
