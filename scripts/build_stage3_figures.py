"""Scientific figures and interpretation tables from saved Stage3 study outputs."""
from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'results/stage3'
DOC=ROOT/'docs/stage3'
FIG=DOC/'figures'
MMHG=133.322387415
plt.rcParams.update({'font.size':10,'svg.hashsalt':'SCCI_RH-STAGE3','axes.spines.top':False,
                     'axes.spines.right':False,'figure.facecolor':'white'})


def read(name):return json.loads((RESULT/name).read_text(encoding='utf-8'))
def save(fig,name):
    FIG.mkdir(parents=True,exist_ok=True)
    svg=FIG/f'{name}.svg'
    fig.savefig(svg,bbox_inches='tight',metadata={'Date':None})
    # Matplotlib path markup contains insignificant end-of-line spaces.
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',
                   encoding='utf-8',newline='\n')
    fig.savefig(FIG/f'{name}.png',dpi=170,bbox_inches='tight')
    plt.close(fig)


def electrical_figure(data):
    cases=data['cases']; first=cases[0]
    t=np.array(first['trace']['times_s'])*1e6
    fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
    ax=axes[0,0]
    ax.plot(t,np.array(first['trace']['current_A'])*1e3,color='#067a78')
    ax.set(xlabel='Time (us)',ylabel='Independent ADC current (mA)',title='Motor reference: resolved microsecond phases')
    ax.axhline(0,color='#b6c4ca',lw=.8);ax.set_xlim(0,800)
    ax=axes[0,1]
    ax.plot(t,np.array(first['trace']['polarization_truth_V'])*1e3,color='#1c4b6d')
    ax.axhspan(-20,20,color='#e6e4d6',alpha=.6,label='Chosen ±20mV engineering gate')
    ax.set(xlabel='Time (us)',ylabel='Lumped polarization truth (mV)',title='Balanced drive charge leaves residual voltage')
    ax.legend(fontsize=8,loc='lower right')
    ax=axes[1,0]
    selected=[cases[i] for i in (0,2,3,4,5)]
    labels=['Reference','Compliance','Prepolarized','Interrupted','Recharge +2%']
    residual=[c['summary']['polarization_after_recovery_V'] for c in selected]
    ax.bar(labels,residual,color=['#067a78','#a64a36','#a64a36','#a64a36','#1c4b6d'])
    ax.set_yscale('symlog',linthresh=.001)
    ax.set(ylabel='Residual after 1ms recovery (V)',title='Recovery is finite; failures remain visible')
    ax.tick_params(axis='x',labelrotation=20)
    ax=axes[1,1]
    actual=np.array([c['summary']['true_cathodic_charge_C'] for c in cases])*1e6
    measured=np.array([c['summary']['measured_cathodic_charge_C'] for c in cases])*1e6
    uncertainty=np.array([c['summary']['charge_uncertainty_C'] for c in cases])*1e6
    ax.errorbar(actual,measured,yerr=uncertainty,fmt='o',color='#067a78',capsize=3)
    ax.plot([0,10],[0,10],color='#b6c4ca',linestyle='--',lw=1)
    ax.set(xlabel='Actual cathodic charge (uC)',ylabel='Measured charge ±conditional bound (uC)',
           title='Measurement is separate from body dose')
    fig.suptitle('Stage3 reduced electrical model · assumed linear pair load',fontsize=15)
    save(fig,'electrical-delivery')


def pressure_figure(runs):
    groups=defaultdict(dict)
    for r in runs:groups[r['metadata']['scenario']['name']][(r['metadata']['seed'],r['metadata']['mode'])]=r
    names=list(groups)
    fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    ax=axes[0]
    for mode,color in [('off','#8b9aa4'),('feedback','#067a78')]:
        value=[r['summary']['disturbance_rmse_pa']/MMHG for group in groups.values() for (seed,m),r in group.items() if m==mode]
        x=np.arange(len(names))+( -.13 if mode=='off' else .13)
        mean=[];low=[];high=[]
        for name in names:
            v=[r['summary']['disturbance_rmse_pa']/MMHG for (seed,m),r in groups[name].items() if m==mode]
            mean.append(np.mean(v));low.append(np.mean(v)-min(v));high.append(max(v)-np.mean(v))
        ax.errorbar(x,mean,yerr=[low,high],fmt='o',color=color,label=mode,capsize=2)
    ax.set_xticks(range(len(names)),[n.replace('_','\n') for n in names],fontsize=7,rotation=65)
    ax.set(ylabel='Disturbance SBP RMSE (mmHg)',title='Four paired seeds per structural family')
    ax.legend(frameon=False)
    ax=axes[1]
    means=[];low=[];high=[]
    for name in names:
        v=[r['summary']['overshoot_above_target_pa']/MMHG for (seed,m),r in groups[name].items() if m=='feedback']
        mean=np.mean(v);means.append(mean);low.append(mean-min(v));high.append(max(v)-mean)
    ax.bar(range(len(names)),means,color='#a64a36',alpha=.85)
    ax.errorbar(range(len(names)),means,yerr=[low,high],fmt='none',color='#233d4d',capsize=2)
    ax.set_xticks(range(len(names)),[n.replace('_','\n') for n in names],fontsize=7,rotation=65)
    ax.set(ylabel='Overshoot above chosen target (mmHg)',title='Improved low-pressure support can overshoot')
    fig.suptitle('Pressure feedback · assumed response families, external observations',fontsize=14)
    save(fig,'pressure-comparisons')


def motor_figure(runs):
    label='conditional_fast_response_assumed_delivery'
    selected=[r['study'] for r in runs if r['configuration_label']==label]
    families=list(selected[0]['families']);conditions=list(selected[0]['families'][families[0]]['conditions'])
    fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    for ax,metric,title in zip(axes,['last_assisted_contact_spatial_rmse_m','retention_off'],
                             ['During final practice block','Retention with all pulses OFF']):
        values=[]
        for family in families:
            row=[]
            for condition in conditions:
                samples=[]
                for r in selected:
                    summary=r['families'][family]['conditions'][condition]['summary']
                    v=summary[metric] if metric!='retention_off' else summary[metric]['contact_spatial_rmse_m']
                    samples.append(v*1000)
                row.append(np.mean(samples))
            values.append(row)
        image=ax.imshow(values,cmap='viridis',aspect='auto')
        ax.set_xticks(range(len(conditions)),['Observe','External / learner','External / expert ext',
             'External / expert neural','Neural+ext / learner','Neural+ext / expert ext','Neural+ext / expert neural'],rotation=70,ha='right',fontsize=8)
        ax.set_yticks(range(len(families)),families)
        ax.set_title(title)
        fig.colorbar(image,ax=ax,label='Contact proxy spatial RMSE (mm)')
    fig.suptitle('CONDITIONAL motor mechanism · fast response + UNQUALIFIED assumed delivery',fontsize=13)
    save(fig,'conditional-motor-comparisons')


def report(pressure,motor,fallbacks):
    lines=['# Stage3 results and interpretation','',
      '> **Foundation results at the frozen coarse reference.** Subsequent [numerical verification](numerical-verification.md) found material motor discretization and closed-loop decision differences. These original conditional motor numbers remain reproducible but are preliminary, rather than stable quantitative benefit estimates. New comparisons use an explicitly selected solver and acquisition qualification; see the Stage 3 dossier for the continuation results. The pressure refinement findings retain all reported frame sensitivities.','',
      '8 October 2026. These are reproducible artificial model results, not human or implanted-device measurements.',
      'Stage3 remains **in progress**. Negative integrated outcomes and conditional biological investigations have different evidence scopes.','',
      '## Study scope','',
      f"The pressure batch contains {len(pressure)} runs:13 structural families ×4 paired seeds ×3 modes. Off and feedback share calibration; oracle uses hidden information solely as a labeled diagnostic. Eight additional finite-hold/ramp sensor-loss runs supplement the stop cases.",
      f"The motor batch contains {len(motor)} configuration/seed studies, each with4 plasticity families and7 comparison arms. It separates nominal electrical integration, faster-response electrical sensitivity, and conditional fast response with an explicitly unqualified assumed delivery model. Six negative-control witnesses run at seed0 in each branch.",
      '', 'All four-seed ranges below describe Monte Carlo variation **within chosen assumptions**; they are not confidence intervals for biology.',
      '', '## Motor: identify the bottleneck before claiming a learning effect','',
      '| Branch | Seed | Observed onset (ms) | Dose bound / measured charge (%) | Local map qualified | Practice pulses across arms/families |',
      '|---|---:|---:|---:|---|---:|']
    for r in motor:
        s=r['study'];response=s['calibration']['response_map']
        pulses=sum(b['pulse_count'] for f in s['families'].values() for c in f['conditions'].values() for b in c['practice_blocks'])
        uncertainty=max((p['charge_uncertainty_C']/abs(p['delivered_phase_charge_C'])
                         for p in s['calibration']['monitor_pulses'] if abs(p['delivered_phase_charge_C'])>0),default=0)*100
        lines.append(f"| {r['configuration_label']} | {s['seed']} | {response['onset_delay_s']*1000:.2f} | {uncertainty:.2f} | {response['qualified']} | {pulses} |")
    lines+=['',
      'The nominal reactive controller must include physical observation age,11.85ms processing allocation, measured response onset and onset uncertainty. A request that exceeds the100ms chosen horizon is withheld. The conservative independent charge bound also widens response-map uncertainty; its authority gate may abstain even in a faster-response plant.',
      '',
      'When an arm emits no assistance, equal outcomes do not establish that neural or expert information has no value. They show that the chosen integrated policy failed to earn an intervention. The conditional branch investigates what the mechanism could do if future timing and delivery identification meet tighter assumptions. It does not demonstrate that the current electrical design supplies them.',
      '', '![Conditional motor comparisons](figures/conditional-motor-comparisons.svg)', '',
      'Each artificial plasticity family has separate assisted practice, OFF retention and OFF transfer. The zero-coupling family can have online assistance without additional retained learning. No acquisition multiplier is inserted or claimed. Artificial thresholds that are not reached are censored, not scored as a speed-up.',
      '',
      'The motor figure averages four paired seeds. Each panel has its own color scale; lower RMSE is better. OFF assessment begins with movement and activation reset to zero and a chosen 2% forgetting factor. This idealized post-washout comparison does not simulate physiological withdrawal or a specified human retention interval.',
      '', '## Pressure: benefits and failures are both outcomes','',
      '| Structural family | Feedback disturbance RMSE mean [range] (mmHg) | Off mean (mmHg) | Feedback overshoot mean [range] (mmHg) | Qualified calibration /4 |',
      '|---|---:|---:|---:|---:|']
    groups=defaultdict(list)
    for r in pressure:groups[r['metadata']['scenario']['name']].append(r)
    for name,values in groups.items():
        feedback=[r for r in values if r['metadata']['mode']=='feedback'];off=[r for r in values if r['metadata']['mode']=='off']
        rmse=[r['summary']['disturbance_rmse_pa']/MMHG for r in feedback]
        over=[r['summary']['overshoot_above_target_pa']/MMHG for r in feedback]
        lines.append(f"| {name} | {np.mean(rmse):.2f} [{min(rmse):.2f}–{max(rmse):.2f}] | {np.mean([r['summary']['disturbance_rmse_pa']/MMHG for r in off]):.2f} | {np.mean(over):.2f} [{min(over):.2f}–{max(over):.2f}] | {sum(r['calibration']['qualified'] for r in feedback)} |")
    lines+=['', '![Pressure comparisons](figures/pressure-comparisons.svg)','',
      'Dense stimulation does not qualify a neural pressure decoder. External waveform support, peak time and arrival remain distinct; new arrival cannot refresh an old bodily measurement. Nonnegative pressor drive cannot independently lower a high baseline. No/adverse response and stale calibration can prevent qualification; subsequent context reversal can invalidate previously identified authority.',
      '', 'A finite fallback may preserve support briefly or withdraw it. None is labeled universally safe. Recovery overshoot remains visible after current is reduced because the assumed response has activation and release dynamics.',
      '',
      '| Sensor-loss fallback | Fallback nadir mean [range] (mmHg) | Mean full-train equivalent delivered during fallback (s) |',
      '|---|---:|---:|']
    fallback_runs=[r for r in pressure if r['metadata']['scenario']['name']=='sensor_loss' and r['metadata']['mode']=='feedback']+fallbacks
    for policy in ('stop','finite_hold','ramp'):
        rows=[r for r in fallback_runs if r['metadata']['config']['fallback']==policy]
        nadirs=[r['summary']['fallback_min_sbp_pa']/MMHG for r in rows]
        dose=[r['summary']['fallback_delivered_train_equivalent_s'] for r in rows]
        lines.append(f"| {policy} | {np.mean(nadirs):.2f} [{min(nadirs):.2f}–{max(nadirs):.2f}] | {np.mean(dose):.3f} |")
    lines+=[
      '', 'These four-seed fallback comparisons reuse the same sensor-loss scenario. Longer support is a modeled tradeoff, not a safety ranking.',
      '', '## Electrical evidence and the next engineering decisions','',
      '![Electrical delivery](figures/electrical-delivery.svg)','',
      'Event-aligned analytical load integration agrees with independent ngspice on the scoped linear cases, and an independent numerical ODE comparison checks compliance transitions. The current ADC estimates charge; it is not a copy of commands. Both phases have separate conservative bounds. A post-delivery failure preserves past body dose and latches subsequent source admission.',
      '',
      'The next Stage3 work should resolve a feasible observed-data motor policy and calibration domain: examine per-profile response identification with independent delivery evidence, known-cue prediction within explicit uncertainty, and which monitor/guard precision Stage4 must earn. It should also complete motor numerical convergence, broader expert/source studies and joint structural sensitivity. This is a requirement-driven revision, not a reason to substitute desired outcomes.',
      '',
      'Continuous shared-source routing, full power/transient coupling, actual independent guards, electrode chemistry, tissue-field recruitment, anatomy and chronic operation remain later or separate evidence. Complete KiCad and populated CAD are not claimed by these studies.',
      '',
      'Reproduce with `scripts/run_stage3_studies.py`; raw JSON gzip files and readable summaries are in [results/stage3](../../results/stage3/). Review [verification-progress.csv](verification-progress.csv) for precise remaining scope.']
    (DOC/'results-and-interpretation.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    electrical=read('electrical.json');pressure=read('pressure-summary.json')['runs'];motor=read('motor-summary.json')['runs']
    fallbacks=read('pressure-fallbacks-summary.json')['runs']
    electrical_figure(electrical);pressure_figure(pressure);motor_figure(motor)
    report(pressure,motor,fallbacks)
    print('Three SVG/PNG figure pairs and the results interpretation written from saved studies.')


if __name__=='__main__':main()
