"""Reproducible manuscript figures from frozen source data and explicit diagrams."""
from pathlib import Path
import hashlib, json, textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=HERE/'figures'
OUT.mkdir(parents=True,exist_ok=True)
NAVY='#172d45'; TEAL='#087f8c'; GOLD='#c17b28'; RED='#a94141'; GRAY='#607283'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'axes.labelcolor':NAVY,'text.color':NAVY,
                     'axes.titleweight':'bold','savefig.facecolor':'white','svg.hashsalt':'project-scci-rh-stage6'})
INPUTS=['experiments/stage3/conditional-concept/summary.json','results/stage3/pressure-summary.json',
        'results/stage6/integration-summary.json','provenance/stage5-mechanical-verification.json']

def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=210,bbox_inches='tight',pad_inches=.18)
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',pad_inches=.18,metadata={'Date':None})
    plt.close(fig)

def box(ax,x,y,w,h,text,color=TEAL,font_size=10):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.014,rounding_size=0.018',
                              edgecolor=color,facecolor=color+'10',linewidth=1.3))
    if font_size<10:
        text='\n'.join(textwrap.fill(line,width=max(16,int(w*105))) for line in text.splitlines())
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=font_size,linespacing=1.30 if font_size<10 else 1.45)

def arrow(ax,a,b,color=GRAY,style='-'):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=13,color=color,
                                linewidth=1.4,linestyle=style,connectionstyle='arc3'))

def diagram(name,title,boxes,arrows,note,font_size=10):
    fig,ax=plt.subplots(figsize=(10,5.4));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    ax.text(.02,.96,title,fontsize=15,weight='bold',va='top')
    for b in boxes:box(ax,*b,font_size=font_size)
    for a,b in arrows:arrow(ax,a,b)
    ax.text(.02,.015,note,fontsize=8.5,color=GRAY,va='bottom',wrap=True)
    save(fig,name)

def main():
    diagram('01_system','Spinal access, interpretation, delivery and independent feedback',[
      (.02,.60,.20,.18,'Spinal contacts\n16 recording streams'),(.29,.60,.19,.18,'Acquisition\nvalidity + causal features'),
      (.55,.60,.18,.18,'Companion policy\nlearner / function specific'),(.80,.60,.18,.18,'Local admission\n2 current sources'),
      (.02,.20,.20,.18,'External outcome\nmovement / pressure'),(.29,.20,.19,.18,'Selected body\nresponse + adaptation'),
      (.55,.20,.18,.18,'Protected outputs\n16 contacts + 2 returns'),(.80,.20,.18,.18,'Independent\nmonitor + inhibit')],
      [((.22,.69),(.29,.69)),((.48,.69),(.55,.69)),((.73,.69),(.80,.69)),((.89,.60),(.89,.38)),
       ((.80,.29),(.73,.29)),((.55,.29),(.48,.29)),((.29,.29),(.22,.29)),((.12,.38),(.55,.60)),
       ((.38,.38),(.20,.60))],
      'Functional proposal. Target firmware, conditional body adapters and physical validation have distinct evidence levels.',font_size=9)
    diagram('02_learning','Expert-informed practice: retained learning is a separate endpoint',[
      (.02,.61,.23,.17,'Expert performance\nspinal data + task labels'),(.38,.61,.24,.17,'Aligned task reference\nlearner calibration'),
      (.76,.61,.22,.17,'Bounded assistance\nduring active attempts'),(.02,.20,.23,.17,'Learner features\n+ independent movement'),
      (.38,.20,.24,.17,'Assumed adaptation\nfavorable / neutral / adverse'),(.76,.20,.22,.17,'Stimulation-OFF\nretention + transfer')],
      [((.25,.695),(.38,.695)),((.62,.695),(.76,.695)),((.25,.285),(.38,.61)),((.87,.61),(.62,.37)),
       ((.62,.285),(.76,.285))],
      'A transferable representation and a useful learning law are premises. Expert voltage is not a portable skill.')
    diagram('03_pressure','Function-specific physiological feedback: positive pressor authority',[
      (.02,.60,.25,.18,'External pressure sensor\nsupport time + quality'),(.39,.60,.22,.18,'Bounded companion\nfeedback + fallback'),
      (.74,.60,.24,.18,'Protected spinal\nstimulation program'),(.02,.20,.25,.18,'Disturbance + pressure\nindependently observed'),
      (.39,.20,.22,.18,'Delayed activation\n+ withdrawal tail'),(.74,.20,.24,.18,'Assumed selective\npressor recruitment')],
      [((.27,.69),(.39,.69)),((.61,.69),(.74,.69)),((.86,.60),(.86,.38)),((.74,.29),(.61,.29)),
       ((.39,.29),(.27,.29)),((.145,.38),(.145,.60))],
      'Removing added drive does not grant active pressure-lowering authority. Parameters and outputs are synthetic.')

    s=json.loads((ROOT/INPUTS[0]).read_text());runs=s['runs']
    fig,axes=plt.subplots(1,2,figsize=(10,4.1))
    for arm,label,color in [('off','Unassisted',GRAY),('expert_external','Expert + external state',GOLD),('spinal_live','Conditional live spinal state',TEAL)]:
        for ax,key in zip(axes,['first_on_rmse_m','final_off_rmse_m']):
            values=[[r[key]*1000 for r in runs if r['variant']=='nominal' and r['rho']==rho and r['arm']==arm] for rho in s['rhos']]
            mean=np.mean(values,axis=1);lo=np.min(values,axis=1);hi=np.max(values,axis=1)
            ax.errorbar(s['rhos'],mean,yerr=[mean-lo,hi-mean],label=label,color=color,marker='o',capsize=3)
            ax.set(xlabel='Assumed teaching coefficient rho',ylabel='Movement RMSE (mm)',xticks=s['rhos'])
            ax.grid(alpha=.16)
    axes[0].set_title('First practice: assistance ON');axes[1].set_title('After 24 blocks: stimulation OFF')
    axes[1].annotate('Neutral teaching:\nidentical retained outcome',xy=(1,5.667),xytext=(-.15,27),
                     arrowprops={'arrowstyle':'->','color':GRAY},fontsize=8.5)
    fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',ncol=3,fontsize=8.5,bbox_to_anchor=(.5,-.03))
    fig.suptitle('Stage 3 conditional study: improved execution can coexist with worse learning',fontsize=13,weight='bold')
    fig.tight_layout(rect=(0,.08,1,.93));save(fig,'04_conditional_learning')

    fig,axes=plt.subplots(1,2,figsize=(9.6,3.8))
    arms=['off','expert_external','spinal_live'];names=['Unassisted','Expert + external','Conditional spinal']
    selected=[[r for r in runs if r['variant']=='nominal' and r['rho']==2 and r['arm']==a] for a in arms]
    for ax,key,title in [(axes[0],'practice_seconds_to_threshold','Practice exposure only'),(axes[1],'total_seconds_to_threshold','Calibration + probes + washout')]:
        vals=[np.mean([r[key] for r in group]) for group in selected]
        ax.bar(names,vals,color=[GRAY,GOLD,TEAL],width=.62);ax.set(ylabel='Seconds in synthetic protocol',title=title)
        ax.tick_params(axis='x',labelsize=8);ax.grid(axis='y',alpha=.15)
        for i,v in enumerate(vals):ax.text(i,v+1,f'{v:.1f}',ha='center',fontsize=9)
        ax.set_ylim(0,max(vals)*1.23)
    fig.suptitle('Favorable learning premise only: exposure accounting changes the comparison',fontsize=12.5,weight='bold')
    fig.tight_layout(rect=(0,0,1,.91));save(fig,'05_exposure')

    p=json.loads((ROOT/INPUTS[1]).read_text())
    nom={r['metadata']['mode']:r for r in p['runs'] if r['metadata']['seed']==0 and r['metadata']['scenario']['name']=='nominal'}
    fig,axes=plt.subplots(1,2,figsize=(9,3.8));modes=['off','feedback'];labels=['Unassisted','Feedback']
    for ax,key,title in [(axes[0],'evaluation_rmse_pa','Evaluation pressure error'),(axes[1],'overshoot_above_target_pa','Recovery overshoot')]:
        vals=[nom[m]['summary'][key]/133.322387415 for m in modes]
        ax.bar(labels,vals,color=[GRAY,TEAL],width=.55);ax.set(ylabel='mmHg, simulated',title=title)
        for i,v in enumerate(vals):ax.text(i,v+.5,f'{v:.2f}',ha='center');ax.set_ylim(0,max(vals)*1.3+1)
        ax.grid(axis='y',alpha=.15)
    fig.suptitle('Stage 3 pressure model, nominal seed 0: benefit and recovery cost',fontsize=12.5,weight='bold')
    fig.tight_layout(rect=(0,0,1,.91));save(fig,'06_pressure_tradeoff')

    n=json.loads((ROOT/INPUTS[2]).read_text())
    fig,axes=plt.subplots(1,2,figsize=(9.6,4.1))
    labels=[r['arm'].capitalize() for r in n['motor_arms']]
    on=[r['first_on_rmse_m']*1000 for r in n['motor_arms']];off=[r['final_off_rmse_m']*1000 for r in n['motor_arms']]
    x=np.arange(4);axes[0].bar(x-.17,on,.34,label='First ON',color=GOLD);axes[0].bar(x+.17,off,.34,label='Final OFF',color=TEAL)
    axes[0].set(xticks=x,xticklabels=labels,ylabel='Synthetic movement RMSE (mm)',title='New compiled-core replay');axes[0].legend(fontsize=8)
    axes[1].bar(['Core boundary cases','Supervisor cases','Feature cases'],[n['compiled_core_fault_cases'],n['separate_independent_supervision_cases'],n['conditional_companion_fault_cases']],color=[TEAL,NAVY,GOLD])
    axes[1].set(ylabel='Finite declared cases',title='Separate software boundaries');axes[1].tick_params(axis='x',labelsize=8)
    for ax in axes:ax.grid(axis='y',alpha=.15)
    fig.suptitle('Stage 6 integration: production admission code with declared body adapters',fontsize=12.5,weight='bold')
    fig.tight_layout(rect=(0,0,1,.92));save(fig,'07_integration')

    diagram('08_evidence','Three evidence levels remain visible throughout the release',[
      (.02,.49,.28,.28,'Published biological precedents\nrecording / recruitment / recovery\nselected pressure feedback'),
      (.36,.49,.28,.28,'SCCI_RH digital results\nmodels + compiled control code\nnative electronics + CAD'),
      (.70,.49,.28,.28,'Future combination\nuseful human spinal features\nselectivity + retained learning')],
      [((.30,.63),(.36,.63)),((.64,.63),(.70,.63))],
      'Evidence motivates a design premise. A completed digital design does not measure the biological premise.')
    diagram('09_runtime','Implemented runtime and future neural-feedback boundary',[
      (.02,.57,.25,.22,'OBSERVE\nRHD acquisition allowed\nfeature quality remains unqualified'),
      (.37,.57,.25,.22,'MOTOR / PRESSURE\nqualified companion plan\nrecording inhibited while armed'),
      (.73,.57,.25,.22,'Local phase state machine\nroute + readback + lease\nindependent inhibit inputs'),
      (.18,.17,.64,.19,'Future closed-loop spinal decoder needs demonstrated artifact recovery,\ncausal valid features and a controller that actually consumes them')],
      [((.27,.68),(.37,.68)),((.62,.68),(.73,.68))],
      'The host replay uses an explicit conditional feature adapter. It does not claim simultaneous target neural recording.',font_size=9)
    artifacts={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*')) if p.suffix in ('.png','.svg')}
    inputs={p:hashlib.sha256((ROOT/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in INPUTS}
    (OUT/'figure-manifest.json').write_text(json.dumps({'schema':'scci_rh.stage6.figures.v1','inputs_sha256_lf':inputs,'artifacts_sha256':artifacts},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'{len(artifacts)//2} figures rendered in PNG and SVG from frozen data.')

if __name__=='__main__':main()
