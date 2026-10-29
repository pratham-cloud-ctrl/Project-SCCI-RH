"""Scientific Stage2 budget figures and review brief; analytical, not measured."""
from pathlib import Path
import json
import math
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak

ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'docs/stage2/figures'
OUT=ROOT/'output/pdf/SCCI_RH_stage2_architecture_budgets.pdf'
D=json.loads((ROOT/'docs/stage2/system-design.json').read_text(encoding='utf-8'))
B=json.loads((ROOT/'results/stage2/budget-summary.json').read_text(encoding='utf-8'))
INK='#15293D'; BLUE='#225B86'; TEAL='#12756D'; AMBER='#AD671C'; RED='#A54242'; GRAY='#627485'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
    'axes.spines.right':False,'axes.labelcolor':INK,'text.color':INK,'svg.fonttype':'none','svg.hashsalt':'SCCI_RH-STAGE2'})


def typography(text):
    # Keep XML/link attributes intact; improve the human-readable text only.
    fragments=re.split(r'(<[^>]+>)',text)
    for i in range(0,len(fragments),2):
        s=fragments[i]
        protected={}
        def part_number(match):
            token='SCCIRHPART'+'Z'*(len(protected)+1)+'_END'
            protected[token]=match.group(0)
            return token
        s=re.sub(r'\b(?:RHD\d+|nRF\d+|ADS\d+|LT\d+|SPIM\d+)\b',part_number,s)
        s=re.sub(r'(?<=[A-Za-z])(?=\d)',' ',s)
        s=re.sub(r'(?<=\d)(?=[A-Za-zµ°])',' ',s)
        s=re.sub(r'(?<=\d)(?=(?:MHz|KiB|Mbit|kbit|bit|ksample|µs|µF|µC|µA|mA|mW|mm|ms|s|Hz|K/W|J/K|K|V|A|dB|kΩ|°C)\b)',' ',s)
        s=re.sub(r'\b(chosen|assumed|at|including|needs|gives|two|Base|Only|Three|with|and|per|of|fails|through|only|to|grows|uses|masks|invalid|mask|gaps|plus|ring|ceiling|C|A|leave|reserves|after|before|in|source)(?=\d)',r'\1 ',s,flags=re.IGNORECASE)
        s=re.sub(r';(?=\S)','; ',s)
        s=re.sub(r',(?=[A-Za-z])',', ',s)
        s=re.sub(r':(?=\S)',': ',s)
        s=s.replace('raw4k','raw 4k').replace('raw2k','raw 2k')
        s=s.replace('Contego200','Contego 200').replace('etal.','et al.')
        for token,number in protected.items():s=s.replace(token,number)
        fragments[i]=s
    return ''.join(fragments)


def save(fig,name):
    for artist in fig.findobj(match=matplotlib.text.Text):
        artist.set_text(typography(artist.get_text()))
    FIG.mkdir(parents=True,exist_ok=True)
    fig.savefig(FIG/f'{name}.png',dpi=190,facecolor='white',bbox_inches='tight')
    path=FIG/f'{name}.svg'
    fig.savefig(path,facecolor='white',bbox_inches='tight',metadata={'Date':D['date']})
    path.write_text('\n'.join(s.rstrip() for s in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)


def figures():
    fig,axes=plt.subplots(1,2,figsize=(10,3.7),layout='constrained')
    x=[0,1]; noise=B['quiet_noise']
    axes[0].bar(x,[r['SNR_at_10uV_dB'] for r in noise],color=[TEAL,RED],width=.55)
    axes[0].axhline(10,color=AMBER,ls='--',label='Chosen10dB gate')
    axes[0].set(xticks=x,xticklabels=['Quiet nominal','Reference mismatch'],ylabel='SNR at10µV RMS (dB)',ylim=(-12,16))
    axes[0].legend(loc='lower left',fontsize=8)
    for i,row in enumerate(noise): axes[0].text(i,row['SNR_at_10uV_dB']+1,f"{row['SNR_at_10uV_dB']:.2f}dB",ha='center')
    c=B['compute_and_transport']
    axes[1].barh(['128MHz CPU','512KiB RAM'],[c['cpu_fraction_128MHz']*100,(1-c['application_ram_headroom_fraction'])*100],color=[BLUE,TEAL])
    axes[1].plot([60,80],[0,1],'|',markersize=24,color=AMBER,label='Chosen resource ceilings')
    axes[1].set(xlim=(0,100),xlabel='Allocated capacity (%)')
    axes[1].legend(fontsize=8,loc='lower right')
    axes[0].set_title('Shared reference can fail'); axes[1].set_title('Conditional embedded resource fit')
    save(fig,'recording-compute')

    fig,axes=plt.subplots(2,1,figsize=(10,4.6),layout='constrained')
    for ax,profile,label in zip(axes,B['profiles'][:2],['Motor: two aligned sources,40Hz','Pressure: three staggered profiles,120Hz']):
        rate=next(p['frame_hz'] for p in D['profiles'] if p['id']==profile['id'])
        period=1/rate; span=2*period
        for cycle in range(2):
            for lo,hi in profile['electrical_intervals_s']:
                ax.axvspan(1000*(cycle*period+lo),1000*(cycle*period+hi),color=RED,alpha=.3)
        ax.set(xlim=(0,span*1000),ylim=(0,1),yticks=[],xlabel='Core time (ms)')
        ax.set_title(f"{label} | raw mask{profile['blanked_fraction_with_preguard']*100:.1f}% | archive invalid{profile['archive_FIR_invalid_fraction_any_raw_invalid_rule']*100:.1f}%",loc='left',fontsize=10)
        ax.text(span*1000*.98,.5,'Red = recording invalid\n100µs preguard +1ms allocated recovery',ha='right',va='center',fontsize=9)
    save(fig,'artifact-timing')

    fig,axes=plt.subplots(1,2,figsize=(10,3.7),layout='constrained')
    loads=np.linspace(500,2500,120)
    for cap in [.5e-6,2e-6,10e-6]:
        ceiling=np.minimum(np.minimum(.020,36/loads),39/(loads+.0005/cap))
        axes[0].plot(loads/1000,1000*ceiling,label=f'Pair C = {cap*1e6:g}µF')
    axes[0].set(xlabel='Bulk path resistance (kΩ)',ylabel='500µs current ceiling (mA)',ylim=(8,22))
    axes[0].legend(fontsize=8); axes[0].set_title('40V terminal joint compliance')
    currents=[.0001,.003,.020]; durations=[.00005,.0002,.0003]
    m=D['monitoring']; lsb=m['signed_current_span_A']/2**m['adc_bits']
    unc=[]
    for i,t in zip(currents,durations):
        q=i*t; dq=2*i*m['phase_edge_uncertainty_s']+(lsb/2+m['current_offset_bound_A'])*t+.02*q
        unc.append(100*dq/q)
    axes[1].bar(range(3),unc,color=[AMBER,BLUE,TEAL],width=.6)
    axes[1].set(xticks=range(3),xticklabels=['0.1mA\n50µs','3mA\n200µs','20mA\n300µs'],ylabel='Allocated phase-charge uncertainty (%)',ylim=(0,40))
    axes[1].set_title('Monitor precision varies across range')
    save(fig,'compliance-monitor')

    fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
    labels=['Motor reference','Pressure reference','Pressure high stress','All-max rejected']
    profiles=B['profiles']; base=np.array([p['base_power_mW'] for p in profiles]); stim=np.array([p['stim_battery_power_mW'] for p in profiles])
    ax.bar(range(4),base,color=BLUE,label='Base acquisition/compute/monitor allocation')
    ax.bar(range(4),stim,bottom=base,color=AMBER,label='Stimulation including assumed converter loss')
    ax.axhline(300,color=RED,ls='--',label='100mA chosen cell cap at3.0V')
    for i,p in enumerate(profiles):ax.text(i,p['total_battery_power_mW']+8,f"{p['total_battery_power_mW']:.2f}mW",ha='center',fontsize=9)
    ax.set(xticks=range(4),xticklabels=labels,ylabel='Scheduled-average battery power (mW)',ylim=(0,515))
    ax.legend(loc='upper left',fontsize=8)
    save(fig,'power-envelope')

    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    time=np.linspace(0,1800,240)
    for p,color in zip(B['profiles'],[TEAL,BLUE,AMBER,RED]):
        rise=p['steady_package_rise_K']*(1-np.exp(-time/300))
        axes[0].plot(time/60,rise,color=color,label=p['id'].replace('_',' '))
    axes[0].axhline(2,color=GRAY,ls='--'); axes[0].set(xlabel='Time from ambient (min)',ylabel='Lumped package rise (K)',title='Assumed20K/W and15J/K')
    axes[0].legend(fontsize=7)
    for p,color in zip(B['profiles'][:2],[TEAL,BLUE]):
        rt=np.linspace(10,60,100)
        axes[1].plot(rt,p['conservative_case_heat_mW']/1000*rt,label=p['id'].replace('_',' '),color=color)
    axes[1].axhline(2,color=GRAY,ls='--',label='Chosen2K target')
    axes[1].set(xlabel='Unknown package thermal resistance (K/W)',ylabel='Steady rise (K)',title='Nominal profiles fail at higher resistance')
    axes[1].legend(fontsize=8)
    save(fig,'thermal-envelope')

    fig,axes=plt.subplots(1,2,figsize=(10,4.7),layout='constrained')
    ax=axes[0]
    for x,y,w,h,color,label in [(0,0,60,48,GRAY,'Can60×48'),(0,48,60,10,'#9FCBC6','Header /36 ports\nin2 height rows'),
        (5,4,50,40,TEAL,'Board'),(12,10,35.1,17,AMBER,'Battery'),(7,29,24,14,BLUE,'HV bank')]:
        ax.add_patch(Rectangle((x,y),w,h,facecolor=color,edgecolor=INK,alpha=.3))
        position=(30,1.8) if label.startswith('Can') else (30,6.5) if label=='Board' else (x+w/2,y+h/2)
        ax.text(*position,label,ha='center',va='center',fontsize=9)
    ax.plot(np.arange(18)*3+4.5,np.full(18,47.4),'o',ms=2,color=INK)
    ax.set(xlim=(-2,62),ylim=(-2,60),aspect='equal',xlabel='x (mm)',ylabel='y (mm)',title='Core plan: allocation blocks')
    ax=axes[1]
    ax.add_patch(Rectangle((0,0),60,14,fill=False,edgecolor=GRAY,lw=2))
    for x,z,w,h,color,label in [(5,1.8,50,1,TEAL,'PCB'),(5,2.8,50,3,BLUE,'Component zone'),(12,6.3,35.1,5.5,AMBER,'Battery box')]:
        ax.add_patch(Rectangle((x,z),w,h,color=color,alpha=.35));ax.text(x+w/2,z+h/2,label,ha='center',va='center',fontsize=9)
    ax.axhline(12.8,color=GRAY,ls='--'); ax.axhline(1.2,color=GRAY,ls='--')
    ax.set(xlim=(-2,62),ylim=(-1,16),aspect='equal',xlabel='x (mm)',ylabel='z (mm)',title='Height allocation: gaps0.5mm /1.0mm')
    save(fig,'mechanical-allocation')


def brief():
    font=Path(matplotlib.get_data_path())/'fonts/ttf'
    pdfmetrics.registerFont(TTFont('SCCIRH2',str(font/'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('SCCIRH2Bold',str(font/'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFontFamily('SCCIRH2',normal='SCCIRH2',bold='SCCIRH2Bold',italic='SCCIRH2',boldItalic='SCCIRH2Bold')
    body=ParagraphStyle('body',fontName='SCCIRH2',fontSize=10,leading=14.5,textColor=colors.HexColor(INK),spaceAfter=9)
    heading=ParagraphStyle('heading',parent=body,fontName='SCCIRH2Bold',fontSize=22,leading=28,spaceAfter=15)
    sub=ParagraphStyle('sub',parent=body,fontName='SCCIRH2Bold',fontSize=12,leading=17,spaceBefore=7)
    small=ParagraphStyle('small',parent=body,fontSize=8.5,leading=11.5)
    story=[]
    def p(text,style=body):story.append(Paragraph(typography(text),style))
    def h(text):p(text,heading)
    def img(name,width=475):
        from PIL import Image as PILImage
        path=FIG/f'{name}.png'
        with PILImage.open(path) as source:w,ht=source.size
        story.append(Image(str(path),width=width,height=width*ht/w));story.append(Spacer(1,9))
    def table(rows,widths=None):
        cells=[[Paragraph(typography(str(s)),small) for s in row] for row in rows]
        tab=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EAF0F5')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F6F9FB')]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
            ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        story.append(tab);story.append(Spacer(1,9))
    def page():story.append(PageBreak())

    p('PROJECT SCCI RH / DESIGN DOSSIER 02',sub)
    h('A quantitative architecture\nfor invasive spinal interfaces')
    p('Selected resources, timing, output limits and physical allocations',sub)
    p('8 October 2026 · Entirely digital · Proposed system under development')
    p('SCCI_RH links spinal recording, causal interpretation, learner-specific stimulation and feedback. '
      'This dossier gives the proposed implant a finite resource architecture. It preserves both '
      'expert-informed motor practice and selected physiological automation.')
    table([['Reference configuration','Causal purpose'],
        ['Paced multidirectional foot placement','Expert spinal representation → learner calibration → active practice with timed assistance → unassisted retention assessment'],
        ['External systolic-pressure feedback after SCI','Qualified epidural pressor profile → measured SBP → bounded feedback; optional spinal biomarker must show added value']], [170,305])
    p('<b>Selected access:</b> intradural surface recording plus separate epidural stimulation. '
      'Sixteen recorded streams, two current sources and independent delivered-output monitoring. '
      'Application modes are initially exclusive; access and recruitment remain target-specific.')
    p('The companion has a separately allocated5V/1A external source and1W base budget. '
      'The external pressure instrument and offline Studio are separately powered. Portable '
      'consumer sensing and transcutaneous charging losses remain open.',small)
    p('<b>What has been established here:</b> reproducible arithmetic, explicit data contracts, '
      'conditional nominal fit and rejected resource combinations. <b>What has not:</b> '
      'human neural observability, retained-learning benefit, safe electrode chemistry, complete '
      'circuits, populated implant CAD or chronic qualification.')
    p('AstroSam / Mind-Link is credited for the future-concept-to-inspectable-design approach. '
      'The SCCI mechanism, source audit, limits and engineering work are Project SCCI RH contributions.',small)
    page()

    h('01 / Recording and computation')
    img('recording-compute')
    table([['Resource','Selected budget / result'],
        ['RHD2216 witness','16 differential streams; one multiplexed16-bit ADC;4ksample/s per stream'],
        ['Neural SPI / apertures','8MHz;19 slots ×3µs=57µs per250µs scan;45µs aperture span'],
        ['nRF5340 application core','128MHz;43.1986M cycles/s estimated,33.75% including contingency'],
        ['Application RAM','404,992 /524,288 bytes;22.75% spare;2s archive ring192,000 bytes'],
        ['Application flash','827,392 /1,048,576 bytes;21.09% spare;single firmware image'],
        ['Normal aggregate telemetry','86,528bit/s including30% headroom;160kbit/s chosen service target']], [155,320])
    p('The quiet shared-reference case passes a chosen10dB screening gate. The high-impedance '
      'mismatch case fails it. Typical chip noise/CMRR are not guaranteed bounds. Neural validity '
      'can require local bipolar/reference redesign; an assumed decoder cannot repair missing information.')
    p('The same workload fails a60% CPU budget at64MHz. A2s raw-rate ring needs596,992 bytes '
      'and does not fit. Continuous raw4k recording is1.536Mbit/s and exceeds the1Mbit/s target. '
      'Network flash/RAM leave31.25%/25% spare under separate allocations. SPIM1 reserves128µs '
      'wire +122µs local work for output admission. Actual images, execution and RF remain unverified.',small)
    page()

    h('02 / Causal timing and artifacts')
    img('artifact-timing')
    table([['Timing quantity','Conditional allocation'],
        ['Unframed fast chain','11.85ms, with200Hz dispatch and0.75ms policy execution'],
        ['20ms uniform history midpoint at delivery','21.85ms; actual masks/feature weighting change age'],
        ['Archive FIR added to midpoint age','25.60ms total; archive excluded from fast motor loop'],
        ['Free-running40Hz frame','36.85ms worst reactive bound; fails25ms chosen target']], [240,235])
    p('Known paced goals can be pre-admitted. Event anchoring must respect per-profile rate limits '
      'and physical-source availability. Pressure source0 serves three120Hz profiles at360events/s: '
      '0.95ms service fits2ms minimum spacing. This allocation does not qualify electrode reset '
      'or guarantee a response to an unseen perturbation.')
    p('Pressure stimulation leaves only35.2% average usable raw recording in this mask model. '
      'At3ms recovery the mask grows to93.6%; at5ms it covers the frame. Use external pressure '
      'feedback in this mode. A1ms amplifier recovery allocation is not electrode reset or proven '
      'hardware recovery. The archive FIR uses7.5ms support: any invalid raw input invalidates '
      'its output. This masks36.4% of motor archive and100% of pressure archive; recursive-feature '
      'reset/warm-up also needs testing. Validity must qualify release.',small)
    page()

    h('03 / Output and delivered charge')
    img('compliance-monitor')
    table([['Output allocation','Meaning / limit'],
        ['Two independent sources','16 routable contacts +2 dedicated returns; at most2 concurrent'],
        ['0.1–20mA;50–500µs/phase','Joint ceiling9µC planned,10µC including delivery uncertainty'],
        ['48V rail /40V usable terminal','4V pair-polarization reserve:20mA through2kΩ needs44V and fails'],
        ['Independent ADS7953 monitor','450ksample/s;16MHz separate SPI;49.5% occupancy with chosen overhead'],
        ['Effective HV reservoir33µF','Two20mA/500µs symmetric pulses:40µC draw,1.212V droop']], [190,285])
    p('The waveform is an SCCI_RH symmetric active biphasic choice with100µs interphase. '
      'Matching a study pulse-width number does not prove equivalent recruitment or recharge. '
      'Equal commands are insufficient: integrate actual phase current and include clipping/faults.')
    p('Charge density is a geometric quantity, not a safe threshold. At6mm²,6µC gives100µC/cm² '
      'and10µC gives166.7µC/cm². Contact material, nonlinear polarization and chronic chemistry '
      'remain unqualified. Allocated monitor errors apply to a constant-phase witness, not '
      'unbounded inter-sample spikes.',small)
    page()

    h('04 / Power and stored energy')
    img('power-envelope')
    rows=[['Reference schedule','Battery mW','Runtime h','Continuous gates']]
    for p0,label in zip(B['profiles'],['Motor reference','Pressure reference','Pressure high stress','All-max corner']):
        rows.append([label,f"{p0['total_battery_power_mW']:.2f}",f"{p0['runtime_h_under_declared_energy']:.2f}",
                     'Conditional pass' if p0['all_selected_continuous_gates_pass'] else 'Reject'])
    table(rows,[190,80,80,125])
    p('Base74.5mW includes AFE4.5, compute/network35, monitor/analog20, LV regulation5, '
      'driver quiescent8 and boost overhead2mW. Converter efficiency is an assumed80%. '
      'All are engineering allocations with unresolved component/firmware behavior.')
    p('Contego200 provides a3.6V nominal200mAh capacity witness atC/5 and20°C. '
      'Chosen usable energy is80% ×0.72Wh=0.576Wh. Actual runtime depends on load, '
      'temperature and cell history. Its negative case requires isolation. High pressure '
      'stress draws111.23mA at3.0V and fails the selected100mA average-current cap.',small)
    page()

    h('05 / Heat, recovery and charging')
    img('thermal-envelope')
    p('Package heat is conservatively battery input minus modeled resistive electrode-load '
      'deposition. It is not a tissue hotspot model. The chosen2K rise target is an engineering '
      'constraint, not an established clinical safety threshold.')
    p('At an assumed20K/W, nominal motor/pressure rise is1.54/1.84K. Pressure requires '
      '≤21.74K/W for this target. Both references can fail at40 or60K/W; nominal closure '
      'depends on unknown package coupling. The stronger pressure case reaches2K in '
      'about155s from ambient in this lumped model. A warm start shortens that interval.')
    table([['Separate unresolved process','Calculated illustration'],
        ['Electrode residual recovery','Two5µF interfaces,1kΩ path:4V→20mV in13.25ms, even with ideal shorting'],
        ['Idle charging at20mA /4V','85% assumed receiver-to-cell efficiency +10mW idle:24.12mW case heat;10h capacity/current before taper']], [200,275])
    p('Thermal coupling, coil/RF losses, charging alignment, nonlinear chemistry, phase-trip '
      'response and power-loss balancing remain later circuit/field/biological checks. '
      'This stage does not silently assume energy recovery or successful passive discharge.',small)
    page()

    h('06 / A preliminary physical body')
    img('mechanical-allocation')
    table([['Allocation','Nominal envelope'],
        ['Core can + separate header','60×48×14mm metal-like can plus60×10×14mm dielectric allocation'],
        ['Board / component zone','50×40×1mm PCB with3mm component-height reservation'],
        ['Battery / HV bank','35.1×17×5.5mm bounding box;24×14×3mm effective-capacitor reservation'],
        ['Interfaces / companion','36 illustrative feedthrough ports;100×60×24mm companion']], [175,300])
    p('The parametric STEP source contains labelled solids, an open can and separate unsealed '
      'lid, board/battery/HV reservations, header, port bores/insulators/pins and companion. '
      'Nominal major-solid intersections and BRep validity are checked.')
    p('These are allocation models. The actual populated KiCad assembly, lead/contact geometry, '
      'tolerance stack, cell insulation, swelling, welds, qualified feedthroughs, strain relief, '
      'anatomical fit and antenna/coil must still determine the final body. A metal can does '
      'not establish RF transmission or thermal resistance.',small)
    page()

    h('07 / What this stage establishes')
    table([['Status','Concrete outcome'],
        ['Calculated and reproducible','Signal/noise; sampling/data; analytical compute/RAM; delivery-monitor capacity; blanking/latency; compliance/charge; energy/heat and envelope fit'],
        ['Specified','Eleven versioned control contracts; freshness/validity; output admission; two exclusive modes; assistance-off assessment'],
        ['Rejected explicitly','64MHz workload;2s raw4k ring; continuous raw4k target; all-max output; sustained high-pressure pattern in this package; neural fast mode during dense pressure output'],
        ['Unestablished','Actual neural information, selective recruitment, retained learning, safe chemistry, chronic packaging, full circuit/firmware operation, RF and real thermal coupling']], [140,335])
    p('<b>Next: computational mechanism.</b> Generate electrode observations from a declared spinal '
      'population model; decode observable samples without hidden state; identify uncertain '
      'learner response; connect bounded commands to delivered current and modeled body response. '
      'Compare neural/external and expert/learner policies, with zero-benefit and harmful coupling '
      'cases. Electronics and populated engineering CAD follow these shared contracts.')
    p('Reproduction: scripts/run_architecture_budgets.py; inputs/results/source audits under '
      'docs/stage2 and results/stage2. Full parameter provenance and unresolved gates are in '
      'the companion Markdown/JSON dossier.',small)
    p('Selected primary / manufacturer sources',sub)
    refs=[('Intan RHD2000 architecture/specifications','https://intantech.com/files/Intan_RHD2000_series_datasheet.pdf'),
        ('Nordic nRF5340 product specification','https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/keyfeatures_html5.html'),
        ('TI ADS7953 delivery converter','https://www.ti.com/product/ADS7953'),
        ('Analog Devices LT8365 power witness','https://www.analog.com/media/en/technical-documentation/data-sheets/LT8365.pdf'),
        ('Resonetics Contego200 battery datasheet','https://resonetics.com/wp-content/uploads/2022/08/15507-01-Battery-Brochure-Contego-200-mAh.pdf'),
        ('Phillips etal.2025: systolic-pressure feedback','https://doi.org/10.1038/s41591-025-03614-w'),
        ('Leung etal.2015: in-vivo charge injection','https://doi.org/10.1109/TBME.2014.2366514')]
    for label,url in refs:p(f'<link href="{url}" color="{BLUE}">{label}</link>',small)
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('SCCIRH2',8);canvas.setFillColor(colors.HexColor(GRAY))
        canvas.drawString(48,27,'PROJECT SCCI RH / STAGE 2 / ANALYTICAL DESIGN PROPOSAL')
        canvas.drawRightString(547,27,f'{doc.page} / 8');canvas.restoreState()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(OUT),pagesize=(595.28,841.89),rightMargin=60,leftMargin=60,
        topMargin=48,bottomMargin=48,title='Project SCCI RH - Stage2 quantitative architecture',author='Project SCCI RH')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print('Built Stage2 figures and illustrated analytical design brief')


if __name__=='__main__':figures();brief()
