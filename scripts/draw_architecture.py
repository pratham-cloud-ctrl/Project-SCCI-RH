"""Vector and raster system diagram; conceptual biological placements are explicit."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)
fig,ax=plt.subplots(figsize=(12,6.5));fig.patch.set_facecolor('#f3f5f7');ax.set_facecolor('#f3f5f7')
ax.set_xlim(0,12);ax.set_ylim(0,6.5);ax.axis('off')
def box(x,y,w,h,title,detail,color='#0b1424'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.08,rounding_size=.1',fc=color,ec='none'))
    ax.text(x+w/2,y+h*.7,title,ha='center',va='center',color='white',fontsize=10,fontweight='bold')
    ax.text(x+w/2,y+h*.32,detail,ha='center',va='center',color='#dce9ef',fontsize=8,linespacing=1.5)
def arrow(a,b,color='#24a0a7',dash=False):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,color=color,lw=1.7,linestyle='--' if dash else '-'))
ax.text(.2,6.15,'SCCI_RH / proposed spinal interface',fontsize=18,fontweight='bold',color='#0b1424')
ax.text(.2,5.75,'Future concept and digital implementation have distinct evidence boundaries.',fontsize=10,color='#536275')
box(.2,3.9,2.1,1,'Spinal recording','Intradural surface concept\nChronic access unverified')
box(3,3.9,2.1,1,'State estimation','Synthetic features\nLearner-specific calibration')
box(5.8,3.9,2.1,1,'Feedback policy','Motor practice or\npressure regulation')
box(8.6,3.9,2.9,1,'Guarded stimulation','Timing / bounds / inhibit\nSeparate epidural lead concept')
arrow((2.38,4.4),(2.9,4.4));arrow((5.18,4.4),(5.7,4.4));arrow((7.98,4.4),(8.5,4.4))
box(.2,1.55,2.1,1,'Body / spinal pathways','Reduced-order plant\nNo biological experiment','#27415b')
box(3,1.55,2.1,1,'External sensing','Kinematics or pressure\nExplicit sensor inputs','#27415b')
box(5.8,1.55,2.1,1,'Digital studies','Noise, delay, retention\nGain uncertainty, faults','#27415b')
box(8.6,1.55,2.9,1,'Desktop reference','Artificial analog input\nDummy-load current reversal','#27415b')
arrow((1.25,2.64),(1.25,3.8),dash=True);arrow((2.38,2.05),(2.9,2.05));arrow((4.05,2.64),(4.05,3.8))
arrow((10.05,3.8),(10.05,2.65),dash=True)
ax.plot([9.9,9.9,1.25],[3.8,3.13,3.13],color='#24a0a7',lw=1.7)
arrow((1.25,3.13),(1.25,2.64))
arrow((5.7,2.05),(5.2,2.05),dash=True)
ax.text(.25,.82,'Solid arrows: proposed information flow. Dashed arrows: biological mapping or digital abstraction.',fontsize=9,color='#536275')
ax.text(.25,.43,'8 recording + 8 stimulation contacts are a scalable proposal; the reference PCB implements one channel.',fontsize=9,color='#536275')
fig.tight_layout(pad=.3)
for ext in ('svg','png'):fig.savefig(OUT/f'architecture.{ext}',dpi=180,facecolor=fig.get_facecolor())
print('Architecture diagram saved.')
