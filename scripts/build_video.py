"""Captioned 72-second digital project walkthrough; no synthetic narration.
pip install -r requirements-media.txt; python scripts/build_video.py
"""
from pathlib import Path
import sys,json,csv,textwrap,math
from PIL import Image,ImageDraw,ImageFont,ImageOps
import numpy as np
import matplotlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.tools'/'media'))
import imageio_ffmpeg
FONTROOT=Path(matplotlib.get_data_path())/'fonts'/'ttf'
def font(size,bold=False):return ImageFont.truetype(str(FONTROOT/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)
F_TITLE,F_BODY,F_SMALL=font(34,True),font(21),font(16)
W,H,FPS=1280,720,12
NAVY='#0b1424';TEAL='#24c4c7';IVORY='#f3f5f7';MUTED='#acbacb'
summary=json.loads((ROOT/'results'/'summary.json').read_text())
reduction=summary['motor']['paired_retained_error_reduction_percent']['mean']
scenes=[
 (8,'PROJECT SCCI RH','A future spinal interface,\nexpressed as digital engineering.','media/scci_rh-hero.png',['Primary literature','Two conditional computational studies','Editable electronics and CAD']),
 (9,'THE MECHANISM','Observe a state.\nCalibrate an intervention.','figures/architecture.png',['Recording and stimulation have distinct placements.','External pressure and movement sensing are explicit.','No brain recording or biological experiments.']),
 (11,'MOTOR PRACTICE','Assistance and retained\nlearning are different outcomes.','figures/motor_study.png',[f'{reduction:.1f}% lower retained model RMSE at assumed beta = 0.8.','Zero learning-benefit control: no retained advantage.','This conditional result is not human learning evidence.']),
 (10,'TIMING MATTERS','A wrong latency model\ncan make assistance harmful.','figures/motor_study.png',['40 paired synthetic learners; published seeds.','A 1 Hz rhythm and 80 ms delay imply 28.8 degrees.','Raw trials, sensitivity sweeps and controls are included.']),
 (11,'PHYSIOLOGICAL FEEDBACK','Reject a pressure disturbance\nwith a bounded controller.','figures/pressure_study.png',['Reduced-order synthetic mean arterial pressure plant.','Low gain and limited actuation expose failures.','Stale sensors inhibit new pulse requests.']),
 (8,'REFERENCE ELECTRONICS','An inspectable signal path\nand dummy-load output.','figures/electronics_stimulation.png',['Artificial input conditioning; one channel.','Nominal 100 uA, 200 us per phase; 20 nC per phase.','Digital timing is host-tested; no hardware was fabricated.']),
 (9,'MECHANICAL IDENTITY','Editable geometry.\nA coherent physical form.','media/scci_rh-exploded.png',['100 x 70 x 32 mm desktop enclosure.','80 x 50 mm reference PCB; matching mounting pattern.','STEP, STL, FreeCAD and Blender sources.']),
 (6,'THE CONTRIBUTION','A traceable engineering argument.','media/scci_rh-hero.png',['Created for Pratham Varma with AI assistance.','Inspired by AstroSam; original spinal architecture.','Digital validation is separate from biological validation.'])]
def wrap(draw,text,x,y,width=400,fill=IVORY,ft=F_BODY,line=34):
    words=text.split();rows=[];row=''
    for word in words:
        candidate=(row+' '+word).strip()
        if draw.textlength(candidate,font=ft)>width and row:rows.append(row);row=word
        else:row=candidate
    if row:rows.append(row)
    for row in rows:draw.text((x,y),row,font=ft,fill=fill);y+=line
    return y
frames=[]
encoder=imageio_ffmpeg.write_frames(str(ROOT/'media'/'SCCI_RH_walkthrough.mp4'),(W,H),fps=FPS,codec='libx264',pix_fmt_in='rgb24',pix_fmt_out='yuv420p',quality=8,output_params=['-movflags','+faststart'])
encoder.send(None)
total=sum(s[0] for s in scenes)*FPS;frame_index=0
for index,(seconds,eyebrow,title,imagefile,bullets) in enumerate(scenes):
    path=ROOT/imagefile
    if not path.exists():path=ROOT/'media'/'scci_rh-exploded.png'
    art=Image.open(path).convert('RGB')
    base=Image.new('RGB',(W,H),NAVY);d=ImageDraw.Draw(base)
    d.text((55,35),'SCCI_RH / DIGITAL ENGINEERING STUDY',font=F_SMALL,fill=TEAL)
    d.text((55,105),eyebrow,font=F_SMALL,fill=MUTED)
    y=154
    for line in title.split('\n'):y=wrap(d,line,55,y,430,IVORY,F_TITLE,43)
    y=max(y+30,340)
    for bullet in bullets:
        d.ellipse((56,y+9,61,y+14),fill=TEAL)
        y=wrap(d,bullet,75,y,390,MUTED,F_BODY,30)+18
    assert y<645, f'Captions exceed safe area in scene {index+1}: {y}'
    panel=Image.new('RGB',(700,455),'#17263b')
    fitted=ImageOps.contain(art,(700,455),Image.Resampling.LANCZOS)
    panel.paste(fitted,((700-fitted.width)//2,(455-fitted.height)//2))
    base.paste(panel,(525,145))
    d.text((55,658),'Synthetic results / no human, animal or fabricated-hardware data',font=F_SMALL,fill=MUTED)
    d.text((1150,658),f'{index+1:02d} / 08',font=F_SMALL,fill=TEAL)
    for f in range(seconds*FPS):
        img=base.copy();d=ImageDraw.Draw(img)
        d.rectangle((55,697,1225,701),fill='#24384d')
        d.rectangle((55,697,55+1170*(frame_index+1)/total,701),fill=TEAL)
        # Brief fades between captioned plates keep all frames legible.
        alpha=min(1,(f+1)/4,(seconds*FPS-f)/4)
        if alpha<1:img=Image.blend(Image.new('RGB',(W,H),NAVY),img,alpha)
        encoder.send(np.asarray(img));frame_index+=1
        if f==seconds*FPS//2:
            p=ROOT/'tmp'/'video-review';p.mkdir(parents=True,exist_ok=True);img.save(p/f'scene-{index+1}.png')
encoder.close()
(ROOT/'media'/'walkthrough-metadata.json').write_text(json.dumps({'seconds':sum(s[0] for s in scenes),'fps':FPS,'resolution':[W,H],'audio':'none; captioned','frames':frame_index},indent=2))
print('Captioned walkthrough saved:',frame_index,'frames.')
