"""Reproduce SCCI_RH's electrical models, not a biological or safety validation.

Requires numpy/matplotlib. Optional NGSPICE_DLL runs the included generic-device
SPICE circuit using ngspice's shared-library API. No vendor transistor/op-amp
macromodel is claimed. The analytical study runs without ngspice.
"""
from pathlib import Path
import ctypes as ct
import csv,json,os,math,re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

ROOT=Path(__file__).resolve().parents[1]; E=ROOT/'electronics'
FIG=ROOT/'figures';FIG.mkdir(exist_ok=True)
SIM=E/'simulation';SIM.mkdir(exist_ok=True)
P=dict(seed=260107,supply_V=5.0,ref_top_ohm=49900.0,ref_bottom_ohm=1020.0,
       sense_ohm=1000.0,switch_Ron_ohm=70.0,sink_headroom_V=0.3,
       output_leg_resistance_ohm=12000.0,output_leg_tolerance=0.001,
       pulse_width_us=200.0,gap_us=50.0,period_ms=20.0,
       load_series_ohm=1000.0,load_Rct_ohm=20000.0,load_Cdl_F=100e-9,
       input_series_ohm=10000.,input_bias_ohm=1e6,coupling_F=1e-6,
       gain_Rf_ohm=20000.,gain_Rg_ohm=1000.,output_R_ohm=1000.,output_C_F=47e-9,
       opamp_GBW_Hz=350000.,opamp_white_noise_V_rtHz=55e-9,temperature_K=298.15)
(SIM/'parameters.json').write_text(json.dumps(P,indent=2)+'\n')
I0=P['supply_V']*P['ref_bottom_ohm']/(P['ref_top_ohm']+P['ref_bottom_ohm'])/P['sense_ohm']
G=1+P['gain_Rf_ohm']/P['gain_Rg_ohm'];KB=1.380649e-23
plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,
                     'axes.labelcolor':'#26354c','text.color':'#26354c','axes.edgecolor':'#c3cbd5',
                     'xtick.color':'#526074','ytick.color':'#526074','font.size':10,'savefig.facecolor':'white'})
TEAL='#149ca4';AMBER='#cc8a35';NAVY='#243b63';RED='#c64b5d'
def save(fig,name):
    fig.savefig(FIG/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(FIG/(name+'.svg'),bbox_inches='tight');plt.close(fig)
def write_csv(path,headers,data):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(headers);w.writerows(data)

def response(f):
    s=2j*np.pi*np.maximum(f,.000001)
    tau=(P['input_series_ohm']+P['input_bias_ohm'])*P['coupling_F']
    hp=P['input_bias_ohm']/(P['input_series_ohm']+P['input_bias_ohm'])*(s*tau)/(1+s*tau)
    amp=G/(1+s*G/(2*np.pi*P['opamp_GBW_Hz']))
    low=1/(1+s*P['output_R_ohm']*P['output_C_F'])
    return hp*amp*low
def output_noise_density(f):
    s=2j*np.pi*np.maximum(f,.01); z=P['input_series_ohm']+1/(s*P['coupling_F'])
    zi=1/(1/P['input_bias_ohm']+1/z)
    j_series=4*KB*P['temperature_K']*P['input_series_ohm']*np.abs(P['input_bias_ohm']/(P['input_bias_ohm']+z))**2
    j_bias=4*KB*P['temperature_K']/P['input_bias_ohm']*np.abs(zi)**2
    eamp=P['opamp_white_noise_V_rtHz']**2
    j_gain=4*KB*P['temperature_K']*P['gain_Rg_ohm']*(G-1)**2/G**2
    j_feedback=4*KB*P['temperature_K']*P['gain_Rf_ohm']/G**2
    gain=G/(1+s*G/(2*np.pi*P['opamp_GBW_Hz']))/(1+s*P['output_R_ohm']*P['output_C_F'])
    return np.sqrt(j_series+j_bias+eamp+j_gain+j_feedback)*np.abs(gain)

freq=np.geomspace(.01,100000,2000);h=response(freq)
noise_rms=float(np.sqrt(np.trapezoid(output_noise_density(freq)**2,freq)))
fs=100000.;n=10000;t=np.arange(n)/fs
signal=100e-6*np.sin(2*np.pi*200*t)+40e-6*np.sin(2*np.pi*700*t)
ff=np.fft.rfftfreq(n,1/fs);clean=np.fft.irfft(np.fft.rfft(signal)*response(ff),n)
rng=np.random.default_rng(P['seed']);white=rng.normal(size=n)
noise=np.fft.irfft(np.fft.rfft(white)*output_noise_density(ff)*np.sqrt(fs/2),n)
output=2.5+clean+noise
write_csv(SIM/'recording_trace.csv',['time_s','artificial_input_V','output_clean_V','output_noisy_V'],zip(t,signal,2.5+clean,output))
fig,ax=plt.subplots(1,2,figsize=(11,3.9))
ax[0].semilogx(freq,20*np.log10(np.abs(h)),color=TEAL,lw=2);ax[0].set(xlabel='Frequency (Hz)',ylabel='Voltage gain (dB)',title='Artificial-input transfer model',ylim=(-30,30));ax[0].grid(alpha=.2)
keep=t<.015;ax[1].plot(t[keep]*1000,clean[keep]*1000,label='Clean response',color=NAVY,lw=1.5);ax[1].plot(t[keep]*1000,(output[keep]-2.5)*1000,label='With modeled white / Johnson noise',color=TEAL,alpha=.7,lw=.9);ax[1].set(xlabel='Time (ms)',ylabel='Output relative to 2.5 V (mV)',title='100 / 40 uV at 200 / 700 Hz');ax[1].legend(fontsize=8,loc='upper right');fig.tight_layout();save(fig,'electronics_recording')

def pulse_case(series=1000.,rct=20000.,cdl=100e-9,width_negative_us=200.,supply=5.,gain=1.,dropout=False,initial_polarization=0.):
    dt=1e-6;tt=np.arange(0,.006,dt);i=np.zeros(len(tt));v=np.zeros(len(tt));vdl=np.zeros(len(tt));clip=np.zeros(len(tt),dtype=bool)
    I=supply*P['ref_bottom_ohm']/(P['ref_top_ohm']+P['ref_bottom_ohm'])/P['sense_ohm']*gain
    start=1000;positive=200;negative_start=1250;negative=int(round(width_negative_us))
    pol=np.zeros(len(tt));pol[start:start+positive]=1;pol[negative_start:negative_start+negative]=-1
    if dropout:pol[negative_start:negative_start+negative]=0
    state=initial_polarization
    for k in range(len(tt)):
        p=pol[k];available=max(0.,supply-P['sink_headroom_V']-p*state)
        lim=available/(series+2*P['switch_Ron_ohm']+2*P['output_leg_resistance_ohm'])
        magnitude=min(I,lim) if p else 0.;i[k]=p*magnitude;clip[k]=bool(p and lim<I)
        vdl[k]=state;v[k]=i[k]*series+state
        # Exact RC update for constant current during each time step.
        state=state*np.exp(-dt/(rct*cdl))+i[k]*rct*(1-np.exp(-dt/(rct*cdl)))
    qp=float(np.sum(i[i>0])*dt);qn=float(np.sum(i[i<0])*dt)
    end=negative_start+negative
    metrics={'positive_charge_nC':qp*1e9,'negative_charge_nC':qn*1e9,'net_charge_nC':(qp+qn)*1e9,
             'imbalance_percent':abs(qp+qn)/max(qp,1e-30)*100,
             'peak_load_voltage_V':float(np.max(np.abs(v))),
             'residual_polarization_at_pulse_end_mV':float(vdl[end]*1000),
             'compliance_limited_samples':int(np.sum(clip)),'peak_current_uA':float(np.max(np.abs(i))*1e6)}
    return tt,i,v,vdl,pol,metrics
tt,current,voltage,polarization,pol,nominal=pulse_case()
write_csv(SIM/'pulse_trace.csv',['time_s','load_current_A','load_voltage_V','polarization_V','command_polarity'],zip(tt,current,voltage,polarization,pol))
cases={'nominal':nominal}
for name,kw in [('high_impedance',{'series':50000.}),('phase_10us_timing_error',{'width_negative_us':190.}),('missing_negative_phase',{'dropout':True}),('low_supply',{'supply':4.75}),('small_double_layer',{'cdl':10e-9}),('precharged_double_layer',{'initial_polarization':2.0})]: cases[name]=pulse_case(**kw)[-1]
fig,ax=plt.subplots(2,2,figsize=(11,6.2));zoom=(tt>.0009)&(tt<.00165)
ax[0,0].step(tt[zoom]*1000,current[zoom]*1e6,color=TEAL,where='post',lw=2);ax[0,0].set(xlabel='Time (ms)',ylabel='Dummy-load current (uA)',title='200 us phases / 50 us inhibition');ax[0,0].axhline(0,color='#9eaaba',lw=.6)
ax[0,1].plot(tt*1000,voltage,color=NAVY,label='Terminal voltage');ax[0,1].plot(tt*1000,polarization,color=AMBER,label='RC polarization');ax[0,1].set(xlabel='Time (ms)',ylabel='Voltage (V)',title='Balanced charge can leave RC polarization');ax[0,1].legend(fontsize=8)
rs=np.geomspace(100,100000,120);actual=[];imbal=[]
for rr in rs:
    result=pulse_case(series=rr)[-1];actual.append(result['peak_current_uA']);imbal.append(result['imbalance_percent'])
ax[1,0].semilogx(rs,np.array(actual),color=TEAL,lw=2);ax[1,0].axhline(I0*1e6,color=NAVY,ls='--',lw=1,label='Nominal setpoint');ax[1,0].set(xlabel='Series test resistance (ohm)',ylabel='Peak current (uA)',title='5 V compliance limits high impedance');ax[1,0].legend(fontsize=8)
names=['Nominal','190 us reverse','Reverse missing'];charges=[cases[k]['net_charge_nC'] for k in ['nominal','phase_10us_timing_error','missing_negative_phase']]
ax[1,1].bar(names,charges,color=[TEAL,AMBER,RED]);ax[1,1].set(ylabel='Net injected charge (nC)',title='Timing and interrupted pulses matter');fig.tight_layout();save(fig,'electronics_stimulation')
write_csv(SIM/'compliance_sweep.csv',['series_load_ohm','peak_current_uA','charge_imbalance_percent'],zip(rs,actual,imbal))

# Supply-referenced current: resistor precision cannot remove supply variation.
corners=[]
for vs in (4.75,5.25):
    for rt in (.999,1.001):
        for rb in (.999,1.001):
            for sense in (.999,1.001):
                for offset in (-10e-6,10e-6):
                    value=(vs*P['ref_bottom_ohm']*rb/(P['ref_top_ohm']*rt+P['ref_bottom_ohm']*rb)+offset)/(P['sense_ohm']*sense)
                    corners.append(value*1e6)
metrics={'model_type':'deterministic analytical circuit abstraction; not measured hardware','seed':P['seed'],
         'nominal_current_uA':I0*1e6,'nominal_phase_charge_nC':I0*200e-6*1e9,
         'dc_gain':G,'input_highpass_corner_Hz':1/(2*np.pi*(P['input_series_ohm']+P['input_bias_ohm'])*P['coupling_F']),
         'output_lowpass_corner_Hz':1/(2*np.pi*P['output_R_ohm']*P['output_C_F']),
         'opamp_closedloop_pole_Hz':P['opamp_GBW_Hz']/G,'gain_at_200Hz':float(abs(response(np.array([200.]))[0])),
         'gain_at_700Hz':float(abs(response(np.array([700.]))[0])),
         'estimated_output_noise_rms_uV_0p01_to_100kHz':noise_rms*1e6,
         'white_noise_model_omits':'chopper ripple, 1/f noise, midpoint noise, switching pickup and artifacts',
         'corner_current_uA_5pct_supply_0p1pct_resistors_10uV_offset':[min(corners),max(corners)],
         'passive_resistance_bound':{'conditions':'5.25 V supply, conservative 1% resistor minimum (BOM specifies 0.1%), discharged/short load; ignore switch Ron conservatively',
                                    'short_load_current_bound_uA':5.25/(2*12000*.99)*1e6,
                                    'polarization_limit_for_250uA_V':250e-6*2*12000*.99-5.25,
                                    'precharged_2V_fault_bound_uA':(5.25+2)/(2*12000*.99)*1e6,
                                    'not_universal':'Stored RC polarization adds to driving voltage; no universal analog current cap is claimed'},
         'load_cases':cases,'spice':{'executed':False}}

SPICE='''SCCI_RH generic-device current-sink and switch test (NOT vendor macromodels)
* Matches R8/R9/R10/R11/R14/R15/Q1/Q2 and U3 A/B pin routing.
* OPA2333 buffer/servo represented by ideal behavioral voltage sources.
* 2N7002 is a generic level-1 NMOS; 74HC4053 is ideal Ron=70 ohm switch.
VDD vdd 0 5
R8 vdd refraw 49.9k
R9 refraw 0 1.02k
C4 refraw 0 100n
Eref ref 0 refraw 0 1
* Generic finite-bandwidth servo: Aol=100000, GBW=350kHz.
Eamp amp_internal 0 ref sense 100000
Rdominant amp_internal amp_state 100k
Cdominant amp_state 0 454.73n
Bservo gate_drv 0 V=max(0,min(5,V(amp_state)))
R11 gate_drv gate 1k
M1 sink gate sense sense NMTEST
R10 sense 0 1k
M2 vdd inhibit sink sink NMTEST
.model NMTEST NMOS (LEVEL=1 VTO=1.2 KP=0.03 LAMBDA=0.02)
* Generic gate parasitics, not a vendor 2N7002 characterization.
CGS gate sense 50p
CGD gate sink 5p
Vphase phase 0 PWL(0 0 1.2249m 0 1.225m 5 6m 5)
Vinhibit inhibit 0 PWL(0 5 0.9999m 5 1m 0 1.1999m 0 1.2m 5 1.2499m 5 1.25m 0 1.4499m 0 1.45m 5 6m 5)
Bca0 ca0 0 V=(1-V(phase)/5)*(1-V(inhibit)/5)
Bca1 ca1 0 V=V(phase)/5*(1-V(inhibit)/5)
SA0 sw_a vdd ca0 0 SWTEST
SA1 sw_a sink ca1 0 SWTEST
SB0 sw_b sink ca0 0 SWTEST
SB1 sw_b vdd ca1 0 SWTEST
.model SWTEST SW (RON=70 ROFF=1e12 VT=0.5 VH=0.05)
R14 sw_a duta 12k
R15 sw_b dutb 12k
Vcurrent duta load_a 0
Rseries load_a polar 1k
Rct polar dutb 20k
Cdl polar dutb 100n
* External-test-fixture leakage prevents a perfectly floating common mode.
RleakA duta 0 1G
RleakB dutb 0 1G
.options reltol=1e-4 abstol=1e-12 method=gear
.tran 0.5u 6m 0 0.5u
.end
'''
(SIM/'current_sink_generic.cir').write_text(SPICE)
def run_shared_ngspice(path,netlist=SPICE,tag='nominal'):
    # Callback types and vector_info follow ngspice sharedspice.h / manual ch.19.
    logs=[];lib=ct.CDLL(str(path));SEND=ct.CFUNCTYPE(ct.c_int,ct.c_char_p,ct.c_int,ct.c_void_p)
    EXIT=ct.CFUNCTYPE(ct.c_int,ct.c_int,ct.c_bool,ct.c_bool,ct.c_int,ct.c_void_p)
    @SEND
    def out(s,ident,user):logs.append(s.decode(errors='replace'));return 0
    @EXIT
    def ex(status,immediate,quitexit,ident,user):logs.append('controlled exit '+str(status));return 0
    lib.ngSpice_Init.argtypes=[ct.c_void_p]*7;lib.ngSpice_Init.restype=ct.c_int
    lib.ngSpice_Init(ct.cast(out,ct.c_void_p),ct.cast(out,ct.c_void_p),ct.cast(ex,ct.c_void_p),None,None,None,None)
    lib.ngSpice_Circ.argtypes=[ct.POINTER(ct.c_char_p)];lib.ngSpice_Circ.restype=ct.c_int
    lib.ngSpice_Command.argtypes=[ct.c_char_p];lib.ngSpice_Command.restype=ct.c_int
    lib.ngSpice_Command(b'destroy all')
    lines=netlist.splitlines();buf=(ct.c_char_p*(len(lines)+1))(*[s.encode() for s in lines],None)
    if lib.ngSpice_Circ(buf)!=0:raise RuntimeError('ngSpice_Circ failed')
    lib.ngSpice_Command.argtypes=[ct.c_char_p];lib.ngSpice_Command.restype=ct.c_int
    if lib.ngSpice_Command(b'run')!=0:raise RuntimeError('ngspice run failed')
    suffix='' if tag=='nominal' else '_'+tag
    (SIM/('ngspice_log'+suffix+'.txt')).write_text('\n'.join(logs)+'\n')
    class VecInfo(ct.Structure):
        _fields_=[('name',ct.c_char_p),('type',ct.c_int),('flags',ct.c_short),('real',ct.POINTER(ct.c_double)),('comp',ct.c_void_p),('length',ct.c_int)]
    lib.ngGet_Vec_Info.argtypes=[ct.c_char_p];lib.ngGet_Vec_Info.restype=ct.POINTER(VecInfo)
    def vec(name):
        ptr=lib.ngGet_Vec_Info(name.encode())
        if not ptr:raise RuntimeError('Missing SPICE vector '+name)
        v=ptr.contents
        if v.length<100:raise RuntimeError('Incomplete SPICE transient')
        return np.ctypeslib.as_array(v.real,shape=(v.length,)).copy()
    t=vec('time');i=vec('vcurrent#branch');va=vec('v(duta)');vb=vec('v(dutb)');vp=vec('v(polar)')
    if t[-1]<.005999 or any('aborted' in s for s in logs):
        raise RuntimeError('ngspice did not complete 6 ms; see ngspice_log.txt')
    write_csv(SIM/('spice_transient'+suffix+'.csv'),['time_s','load_current_A','load_voltage_V','polarization_V'],zip(t,i,va-vb,vp-vb))
    qp=np.trapezoid(np.maximum(i,0),t);qn=np.trapezoid(np.minimum(i,0),t)
    settled_positive=float(np.mean(i[(t>.00101)&(t<.00119)]))*1e6
    settled_negative=float(np.mean(i[(t>.00126)&(t<.00144)]))*1e6
    case_supply=float(re.search(r'^VDD vdd 0 ([0-9.]+)',netlist,re.M).group(1))
    expected=case_supply*P['ref_bottom_ohm']/(P['ref_top_ohm']+P['ref_bottom_ohm'])/P['sense_ohm']
    if tag=='nominal':
        fig,ax=plt.subplots(1,2,figsize=(11,3.9));window=(t>.00095)&(t<.0015)
        ax[0].plot(t[window]*1000,i[window]*1e6,color=TEAL,lw=1.5,label='Revision B: 12k per leg')
        oldfile=E/'revisions'/'revA'/'spice_transient.csv'
        if oldfile.exists():
            old=np.genfromtxt(oldfile,delimiter=',',skip_header=1);sel=(old[:,0]>.00095)&(old[:,0]<.0015)
            ax[0].plot(old[sel,0]*1000,old[sel,1]*1e6,color=RED,lw=.8,alpha=.6,label='Revision A: unprotected legs')
        ax[0].set(xlabel='Time (ms)',ylabel='Load current (uA)',title='Generic-device model: design revision');ax[0].legend(fontsize=8)
        edge=(t>.0012498)&(t<.001252)
        ax[1].plot((t[edge]-.00125)*1e6,i[edge]*1e6,color=TEAL,marker='.',ms=3,lw=1)
        ax[1].set(xlabel='Time relative to reverse enable (us)',ylabel='Load current (uA)',title='Revision B transition detail')
        fig.suptitle('Generic parasitics / behavioral op-amp: digital finding, not measured hardware',fontsize=11)
        fig.tight_layout();save(fig,'electronics_spice')
    return {'executed':True,'model':'generic level-1 MOSFET; behavioral op-amp; switch abstraction; not vendor verification',
            'transient_points':len(t),'positive_charge_nC':float(qp*1e9),'negative_charge_nC':float(qn*1e9),
            'net_charge_nC':float((qp+qn)*1e9),'peak_current_uA':float(np.max(np.abs(i))*1e6),
            'settled_positive_current_uA':settled_positive,'settled_negative_current_uA':settled_negative,
            'expected_case_current_uA':expected*1e6,
            'unresolved_limitation':'Series resistance reduces nominal modeled overshoot; generic model still needs vendor-model, parasitic and bench validation before fabrication',
            'validation':{'completed_6ms':bool(t[-1]>=.005999),'settled_current_within_1pct_of_case_setpoint':bool(abs(settled_positive-expected*1e6)<expected*1e6*.01),
                          'phase_charge_within_1pct_of_case_analytical':bool(abs(qp-expected*200e-6)<expected*200e-6*.01),
                          'peak_below250uA_in_this_run':bool(np.max(np.abs(i))*1e6<250)}}
if os.environ.get('NGSPICE_DLL'):
    try:
        dllpath=Path(os.environ['NGSPICE_DLL']);metrics['spice']=run_shared_ngspice(dllpath)
        sensitivity={}
        variants={
            'small_Cdl':SPICE.replace('Cdl polar dutb 100n','Cdl polar dutb 10n'),
            'precharged_positive_2V':SPICE.replace('.options','.ic V(polar)=2 V(dutb)=0\n.options'),
            'precharged_negative_2V':SPICE.replace('.options','.ic V(polar)=-2 V(dutb)=0\n.options'),
            'high_supply_small_C_min_resistors':SPICE.replace('VDD vdd 0 5','VDD vdd 0 5.25').replace('R14 sw_a duta 12k','R14 sw_a duta 11.88k').replace('R15 sw_b dutb 12k','R15 sw_b dutb 11.88k').replace('Cdl polar dutb 100n','Cdl polar dutb 10n')}
        for name,netlist in variants.items():
            (SIM/(name+'.cir')).write_text(netlist)
            try:sensitivity[name]=run_shared_ngspice(dllpath,netlist,name)
            except Exception as exc:sensitivity[name]={'executed':False,'error':str(exc)}
        metrics['spice_sensitivity']=sensitivity
    except Exception as exc:
        metrics['spice']={'executed':False,'error':str(exc)}
        (SIM/'ngspice_error.txt').write_text(str(exc)+'\n')

metrics['analytical_validation']={
    'nominal_integrated_charge_balanced':abs(nominal['net_charge_nC'])<1e-9,
    'nominal_load_not_compliance_limited':nominal['compliance_limited_samples']==0,
    'high_impedance_triggers_compliance_limit':cases['high_impedance']['compliance_limited_samples']>0,
    'ten_us_timing_error_produces_five_pct_imbalance':abs(cases['phase_10us_timing_error']['imbalance_percent']-5)<1e-9,
    'missing_phase_retains_positive_charge':abs(cases['missing_negative_phase']['net_charge_nC']-I0*200e-6*1e9)<1e-9,
    'balanced_charge_does_not_zero_rc_polarization':abs(nominal['residual_polarization_at_pulse_end_mV'])>1}
if not all(metrics['analytical_validation'].values()):raise RuntimeError('Electrical invariant check failed')
(SIM/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
print(json.dumps(metrics,indent=2))

# PCB overview is drawn from native connectivity coordinates, not a fictional PCB.
manifest=json.loads((E/'connectivity.json').read_text())
fig,ax=plt.subplots(figsize=(10,6.3));ax.add_patch(Rectangle((0,0),80,50,facecolor='#132c43',edgecolor='#0b1424',lw=2))
for x,y in manifest['mounting_holes_mm']:ax.add_patch(Circle((x,50-y),1.6,fc='white',ec='#aab2bb',lw=1.5))
for p in manifest['parts']:
    x,y=p['xy'];ref=p['ref'];w,h=(6.2,10.6) if ref=='U3' else (6.2,5.5) if ref.startswith('U') else (3,3) if ref.startswith('Q') else (2.6,2.54*len(p['nets'])) if ref.startswith('J') else (2.8,1.8)
    yc=50-y if not ref.startswith('J') else 50-(y+(len(p['nets'])-1)*1.27)
    color='#29313c' if ref.startswith(('U','Q')) else '#d2b886' if ref.startswith('J') else '#aab3bb'
    ax.add_patch(Rectangle((x-w/2,yc-h/2),w,h,facecolor=color,edgecolor='#d7dce2',lw=.6))
    ax.text(x,yc-h/2-1.1,ref,color='white',fontsize=6,ha='center',va='top')
ax.text(40,46.5,'SCCI_RH / ANALOG REFERENCE',color='#24c4c7',fontsize=13,ha='center')
ax.text(40,2.5,'DIGITAL DESIGN / ELECTRICAL TEST LOADS ONLY',color='#eab66a',fontsize=8,ha='center')
ax.set(xlim=(-2,82),ylim=(-2,52),aspect='equal');ax.axis('off');fig.tight_layout();save(fig,'electronics_board_overview')
