"""Convert reviewed manufacturer pad geometry into native physical pad names.

The retained CSV is geometry extracted from Fanstel BT40F-lib-11.lbr.
The original Eagle file is a primary reference held in ignored tmp only.
"""
from pathlib import Path
import argparse,csv,hashlib,json,xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--primary-eagle',type=Path);a=ap.parse_args()
numeric_names={**{str(n):str(n) for n in range(1,17)},**{str(17+k*7+j):chr(65+k)+str(j) for k in range(5) for j in range(7)},**{str(52+j):'F'+str(3+j) for j in range(4)},**{str(56+j):'H'+str(j) for j in range(4)},**{str(60+j):'Z'+str(j) for j in range(7)}}
if a.primary_eagle:
 pads=ET.parse(a.primary_eagle).findall('./drawing/library/packages/package/smd')
 assert len(pads)==66 and {p.attrib['name'] for p in pads}==set(numeric_names)
 rows=[{'pad':numeric_names[p.attrib['name']],'eagle_pad':p.attrib['name'],'x_mm':float(p.attrib['x'])-7,'y_mm':10.5-float(p.attrib['y']),'width_mm':p.attrib['dx'],'height_mm':p.attrib['dy'],'shape':'circle' if p.attrib.get('roundness')=='100' else 'rect'} for p in pads]
 with (OUT/'module-pad-geometry.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 (OUT/'module-footprint-source.json').write_text(json.dumps({'source':'https://www.fanstel.com/s/BT40F-lib-11.lbr','source_sha256':hashlib.sha256(a.primary_eagle.read_bytes()).hexdigest(),'source_package':'BM40-B_1PRIMARY','manufacturer_specification':{'url':'https://www.fanstel.com/s/BT40F_BT40N-Product-Specifications.pdf','revision':'1.09 July 2024','sha256':'63e7cfabad1f13149c4b090cf02a79f46cf927af5549cb1614f3ecbc56101a22'},'actual_pad_count':66,'translation_mm':[-7,10.5],'y_axis_inverted':True,'numeric_to_physical_names':numeric_names,'body_geometry':{'nominal_envelope_mm':[15,21,2],'upper_x_bounds_mm':[-8,7],'lower_x_bounds_mm':[-7,7],'y_bounds_mm':[-10.5,10.5],'notch_y_mm':0.5,'policy':'Nominal mechanical drawing p9; lower14mmregioncentredonpad-gridreference,upper15mmbodyoverhangstoleft. Componentheight/tolerancesandassemblynotqualified.'},'review':'Fanstel v1.09 p9 physical geometry and p14/p16/p17 function table; 61-pad prose is inconsistent with actual66-pad artwork. H0..H3 distinguish ground pads from signal F3.'},indent=2)+'\n',encoding='utf-8')
else: rows=list(csv.DictReader((OUT/'module-pad-geometry.csv').open(encoding='utf-8')))
local=OUT/'scci_rh_controller.pretty';local.mkdir(exist_ok=True)
data='(footprint "BT40F_Manufacturer_66Pad" (version 20241229) (generator "scci_rh_carrier") (layer "F.Cu")\n (descr "Fanstel BT40F actual66pads; primary Eagle geometry with physical labels; radio unused") (attr smd)\n (fp_text reference "REF**" (at 0 12) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))\n (fp_text value "BT40F" (at 0 13.5) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))\n'
for row in rows:
 data+=f' (pad "{row["pad"]}" smd {row["shape"]} (at {float(row["x_mm"]):.4f} {float(row["y_mm"]):.4f}) (size {float(row["width_mm"]):.4f} {float(row["height_mm"]):.4f}) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
outline=[(-8,-10.5),(7,-10.5),(7,10.5),(-7,10.5),(-7,.5),(-8,.5)]
for start,end in zip(outline,outline[1:]+outline[:1]):
 data+=f' (fp_line (start {start[0]} {start[1]}) (end {end[0]} {end[1]}) (stroke (width .1) (type default)) (layer "F.Fab"))\n'
data+=' (fp_rect (start -8.5 -11) (end 7.5 11) (stroke (width .05) (type default)) (fill none) (layer "F.CrtYd"))\n (fp_line (start -8 -1) (end 7 -1) (stroke (width .15) (type dash)) (layer "F.SilkS"))\n (fp_text user "ANTENNA / RADIO OFF" (at -.5 -6) (layer "F.Fab") (effects (font (size .8 .8) (thickness .1))))\n)\n'
(local/'BT40F_Manufacturer_66Pad.kicad_mod').write_text(data,encoding='utf-8')
print('66 physical module pads generated from retained manufacturer geometry')
