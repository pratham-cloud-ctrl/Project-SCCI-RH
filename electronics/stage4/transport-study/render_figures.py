"""Render scientific figures directly from the saved finite studies."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
OUT=HERE/'figures'


def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=180,facecolor='white')
    fig.savefig(OUT/(name+'.svg'),facecolor='white')
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    d=json.loads((HERE/'input-results.json').read_text());c=json.loads((HERE/'transport-results.json').read_text())
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.hashsalt':'SCCI_RH-transport-v1'})
    with np.load(HERE/'input-traces.npz') as data:
        fig,ax=plt.subplots(1,2,figsize=(11.5,4.4),layout='constrained')
        key='fc15000_spike'
        ax[0].plot(data[key+'_time_s']*1e6,data[key+'_source_A']*1e3,label='Artificial source',color='#555555',lw=1)
        ax[0].plot(data[key+'_time_s']*1e6,data[key+'_filtered_A']*1e3,label='Illustrative 15 kHz filter',color='#087f8c')
        ax[0].plot(data[key+'_sample_time_s']*1e6,data[key+'_estimated_A']*1e3,'.',label='Actual scheduled samples',color='#dc6b1c',ms=3)
        ax[0].set(xlim=(110,210),xlabel='Time (µs)',ylabel='Current (mA)',title='A narrow spike can be hidden by filtering')
        ax[0].legend(fontsize=8,loc='upper right')
        normal=[x for x in d['filter_cases'] if x['id'].endswith('normal')]
        x=np.arange(3)
        ax[1].bar(x-.18,[v['phase_error_C']*1e9 for v in normal],.36,label='50–250 µs phase window',color='#087f8c')
        ax[1].bar(x+.18,[v['tail_error_C']*1e9 for v in normal],.36,label='50–400 µs extended window',color='#dc6b1c')
        ax[1].axhline(-24,ls='--',color='#777777',label='−4% of 600 nC (reference)')
        ax[1].set(xticks=x,xticklabels=['7.5','15','22.5'],xlabel='Illustrative combined bandwidth (kHz)',ylabel='Charge error (nC)',title='Window choice changes the diagnostic integral')
        ax[1].legend(fontsize=8,loc='lower right')
        fig.suptitle('Artificial waveform study • assumed filter shapes and exact DC calibration • no precision certification',fontsize=11)
        save(fig,'filter-and-charge')
    fig,ax=plt.subplots(1,2,figsize=(11.5,4.2),layout='constrained')
    names=['I0','I1','VPAIR0','VPAIR1','MON_VREF','MON_VMID','PACK_BUS','HOST_5']
    actual_names=list(dict.fromkeys(f['channel_name'] for f in c['raw_ADC']['frames']))
    for i,name in enumerate(actual_names):
        times=[f['aperture_tick']*.0625 for f in c['raw_ADC']['frames'] if f['channel_name']==name]
        ax[0].scatter(times,[i]*len(times),marker='|',s=45,color='#087f8c' if i<2 else '#dc6b1c')
    ax[0].set(yticks=range(len(actual_names)),yticklabels=actual_names,xlim=(0,400),xlabel='Aperture time within superperiod (µs)',title='450k aggregate conversions/s; current gaps vary')
    for row in c['resources']['raw_cases']:
        if row['service_payload_bits_per_s']!=800000:continue
        times=np.linspace(0,.25,200)
        backlog=np.maximum(0,times*row['growth_bytes_per_s'])/1024
        ax[1].plot(times*1000,backlog,label=f"{row['frame_rate_Hz']/1000:g}k neural frames/s")
    ax[1].axhline(16,color='#777777',ls='--',label='16 KiB queue capacity')
    ax[1].axvline(100,color='#777777',ls=':',label='100 ms diagnostic lease')
    ax[1].set(xlabel='Capture time (ms)',ylabel='Unserved data (KiB)',title='1 Mbaud UART: 800 kbit/s before packet overhead')
    ax[1].legend(fontsize=8)
    fig.suptitle('Finite transport allocation • target DMA, CS timing and UART service remain implementation conditions',fontsize=11)
    save(fig,'sampling-and-queues')
    fig,ax=plt.subplots(1,2,figsize=(11.5,4),layout='constrained')
    p=d['power_overlay'];base=p['baseline_active_W'];extra=p['added_battery_W']
    ax[0].barh(['Before transport','With transport'],[base,base],color='#087f8c',label='Frozen power reference')
    ax[0].barh(['With transport'],[extra],left=[base],color='#dc6b1c',label='Revised load caps + divider')
    ax[0].set(xlim=(0,3.4),ylim=(-.6,2.1),xlabel='Conditional battery input (W)',title='Added observation has a power cost')
    ax[0].text(p['active_W']+.04,1,f"{p['active_W']:.3f} W",va='center')
    ax[0].legend(fontsize=8,loc='upper left')
    rows=c['companion'].get('cases',[])
    rejected=sum(not r['accepted'] for r in rows)
    ax[1].axis('off')
    ax[1].text(.02,.96,f"{len(rows)} packet histories\n{rejected} rejected; accepted data still need explicit rearm\n\nOldest pressure support age ≤ 2 s\nBounded clock uncertainty ≤ 500 µs\n3 s pressure lease; 250 ms motor lease\n\n{p['runtime_h']:.3f} h from assumed 15.392 Wh usable energy\nCompact 2 K thermal allocation remains unearned",va='top',linespacing=1.5)
    fig.suptitle('Companion validity and updated resources • finite digital reference, not measured device performance',fontsize=11)
    save(fig,'validity-and-power')
    # Deterministic formatting for reviewable vector artifacts.
    for path in OUT.glob('*.svg'):
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n',encoding='utf-8')


if __name__=='__main__':main()
