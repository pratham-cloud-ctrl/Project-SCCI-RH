"""Finite supervisor threshold and interrupted-load study; read-only by default.

Declared component limits and engineering fixture assumptions remain distinct.
No vendor nonlinear model, biological dose or arbitrary-fault proof is implied.
"""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import math
import numpy as np

HERE=Path(__file__).resolve().parent
RAILS={
    "SUP_3V3":(3.3,3.10,3.50,1.),
    "SUP_5":(5.,4.75,5.25,1.),
    "HOST_3V3":(3.3,3.10,3.50,1.),
    "HOST_5":(5.,4.75,5.25,1.),
    "HOST_15":(15.,13.5,16.5,1.),
    "HOST_24":(24.,22.8,25.2,1.),
    "AFE_3V3":(3.45,3.34,3.54,1.),
    "AFE_P5":(5.30,5.20,5.42,1.),
    "AFE_N5_MAG":(5.10,4.75,5.50,.1),
}
ASSUMPTIONS={
    "resistor_fraction":.001,
    "rail_bottom_R_ohm":10000.,
    "TPS3700_rising_threshold_V":[.396,.404],
    "TPS3700_falling_threshold_V":[.387,.400],
    "TPS3700_UV_input_current_A":[-25e-9,25e-9],
    "TPS3700_OV_input_current_A":[-15e-9,15e-9],
    "comparator_offset_V_bound":.006,
    "buffer_offset_V_allowance":.0006,
    "monitor_signal_offset_V_allowance":.001,
    "monitor_gain_fraction_allowance":.005,
    "reference_V_nominal":4.096,
    "reference_fraction_allowance":.002,
    "AFE_comp_bias_A_allowance":2e-9,
    "guard_on_delay_s_assumed":5e-6,
    "guard_off_delay_s_assumed":5e-6,
    "detector_delay_s_assumed":20e-6,
    "secondary_timer_max_s_model":264e-6,
    "watchdog_max_s":.230,
    "guard_edge_injection_C_assumed":300e-12,
    "load_R_ohm_assumed":1000.,
    "load_C_F_assumed":2e-6,
    "current_A_assumed":.003,
    "independent_SUP_power_generation_implemented":False,
}


def sha(path):return hashlib.sha256(path.read_bytes().replace(b"\r\n",b"\n")).hexdigest()


def rail_rows():
    rows=[];tol=ASSUMPTIONS['resistor_fraction'];rbnom=10000.
    for name,(nom,lo,hi,gain) in RAILS.items():
        bounds={}
        dividers={}
        for side,target,current in (('UV',lo,25e-9),('OV',hi,15e-9)):
            rt=(target*gain/.4-1)*rbnom
            dividers[side]={'top_R_ohm':rt,'bottom_R_ohm':rbnom}
            for edge,thresholds in (('rising',(.396,.404)),('falling',(.387,.400))):
                values=[]
                for tr,tb,threshold,ib in itertools.product((-tol,tol),(-tol,tol),thresholds,(-current,current)):
                    rtop=rt*(1+tr);rbot=rbnom*(1+tb)
                    # Exact divider KCL: Vrail = Vthreshold*(1+Rt/Rb)+Ib*Rt.
                    sensed=threshold*(1+rtop/rbot)+ib*rtop
                    if gain == 1.:
                        values.append(sensed)
                    else:
                        # Inverting OPA391: 100k input /10k feedback, both0.1%,
                        # explicit600uV offset allowance. Magnitude monitor.
                        for di,df,vos in itertools.product((-tol,tol),(-tol,tol),(-.0006,.0006)):
                            actual_gain=gain*(1+df)/(1+di)
                            values.append((sensed-vos*(1+actual_gain))/actual_gain)
                bounds[f'{side}_{edge}_V']=[min(values),max(values)]
        rows.append({'rail':name,'nominal_magnitude_V':nom,'declared_scaling_gain':gain,
                     'negative_monitor_gain_and_offset_included':True if gain!=1 else None,
                     'nominal_UV_rising_V':lo,'nominal_OV_rising_V':hi,'dividers':dividers,
                     'corner_bounds':bounds,
                     'startup_nominal_inside_all_rising_limits':bounds['UV_rising_V'][1]<nom<bounds['OV_rising_V'][0],
                     'nominal_OV_recovery_guaranteed':nom<bounds['OV_falling_V'][0]})
    return rows


def comparator_rows():
    p=ASSUMPTIONS;t=p['resistor_fraction'];rows=[]
    for kind,(ra,rm,rb,gain) in {'quiet':(203800.,2000.,203800.,40.),'pair':(232000.,536000.,232000.,.0499)}.items():
        thresholds=[]
        for da,dm,db,referr,voslo,voshi,buflo,bufhi,sense,gerr in itertools.product(
                (-t,t),(-t,t),(-t,t),(-p['reference_fraction_allowance'],p['reference_fraction_allowance']),
                (-.006,.006),(-.006,.006),(-.0006,.0006),(-.0006,.0006),(-.001,.001),(-.005,.005)):
            ref=p['reference_V_nominal']*(1+referr);a=ra*(1+da);m=rm*(1+dm);b=rb*(1+db)
            low=ref*b/(a+m+b)+voslo+buflo
            high=ref*(b+m)/(a+m+b)+voshi+bufhi
            mid=ref/2
            thresholds.append(((low-mid-sense)/(gain*(1+gerr)),(high-mid-sense)/(gain*(1+gerr))))
        low=[v[0] for v in thresholds];high=[v[1] for v in thresholds]
        rows.append({'function':kind,'corner_rows':len(thresholds),'unit':'A' if kind=='quiet' else 'V',
                     'accepted_union':[min(low),max(high)],'accepted_intersection':[max(low),min(high)],
                     'empty_window_corner_count':sum(a>=b for a,b in thresholds),
                     'nominal_half_window':((p['reference_V_nominal']*rm/(ra+rm+rb))/2)/gain,
                     'sensor_error_status':'Declared allowance, not measured finished circuit',
                     'full_difference_amplifier_resistor_CMRR_model':False if kind=='pair' else None})
    return rows


def afe_rows():
    p=ASSUMPTIONS;t=p['resistor_fraction'];bounds=[]
    # Monitor loading and comparator-offset corners are explicit. All17 windows
    # share rails/thresholds; their systematic errors must not be divided by17.
    for r_sig,r_bias,rhi,rhb,rlo,rlb,supply,vos,buf,ib in itertools.product(
            (-t,t),(-t,t),(-t,t),(-t,t),(-t,t),(-t,t),(3.4155,3.4845),(-.006,.006),(-.0006,.0006),(-2e-9,2e-9)):
        rs=10e6*(1+r_sig);rb=1e6*(1+r_bias)
        k=rb/(rs+rb);bias=supply*rs/(rs+rb);rth=rs*rb/(rs+rb)
        hi=supply*(100e3*(1+rhb))/(9500*(1+rhi)+100e3*(1+rhb))
        lo=supply*(100e3*(1+rlb))/(10500*(1+rlo)+100e3*(1+rlb))
        bounds.append(((lo+vos+buf+ib*rth-bias)/k,(hi+vos+buf+ib*rth-bias)/k))
    low=[v[0] for v in bounds];high=[v[1] for v in bounds]
    loading=[]
    for name,rz in (('positive_nominal',20000.),('reference_nominal',2000.),('positive_adverse',1e6)):
        source=rz+4990.+12.1
        # Exact DC KCL with original protected-node10M bleeder approximated at
        # the same node (2.1ohm switch split is negligible here and stated).
        load_g=1/source+1/10e6
        voltage=(3.45/11e6)/(load_g+1/11e6)
        current=(3.45-voltage)/11e6
        loading.append({'case':name,'source_resistance_ohm':source,'added_input_DC_V':voltage,
                        'probe_bias_A':current,'linear_AC_range_proven':False})
    return {'corner_rows':len(bounds),'pin_voltage_accepted_union_V':[min(low),max(high)],
            'pin_voltage_accepted_intersection_V':[max(low),min(high)],
            'all_corners_include_zero':all(a<0<b for a,b in bounds),
            'guaranteed_below_RHD_0p4_DC_under_declared_bounds':min(low)>-.4 and max(high)<.4,
            'switch_state_or_isolation_proven':False,'AC_linearity_or_recovery_proven':False,
            'loading_fixture':loading,'monitored_pins':17}


def difference_amplifier_rows():
    """Include resistor mismatch, common mode and explicit amplifier allowance.

    Sweep B over0..24V independently of difference; this is a conservative
    superset of the restricted physical0..24V pair, not a new signal domain.
    """
    t=ASSUMPTIONS['resistor_fraction']; lows=[]; highs=[]
    for errors in itertools.product((-t,t),repeat=7):
        ra,rm,rb,rin_a,rref,rin_b,rf=[v*(1+d) for v,d in zip(
            (232000.,536000.,232000.,1e6,49900.,1e6,49900.),errors)]
        kb=rf/rin_b;ga=(1+kb)*rref/(rin_a+rref)
        for referr,cm,amp,cl,ch,bl,bh in itertools.product(
                (-.002,.002),(0.,24.),(-.0005,.0005),(-.006,.006),(-.006,.006),(-.0006,.0006),(-.0006,.0006)):
            ref=4.096*(1+referr);mid=ref/2
            baseline=(ga-kb)*cm+(1+kb)*mid*rin_a/(rin_a+rref)+amp*(1+kb)
            lows.append((ref*rb/(ra+rm+rb)+cl+bl-baseline)/ga)
            highs.append((ref*(rb+rm)/(ra+rm+rb)+ch+bh-baseline)/ga)
    return {'corners':len(lows),'accepted_union_V':[min(lows),max(highs)],
            'accepted_intersection_V':[max(lows),min(highs)],
            'common_mode_B_envelope_V':[0.,24.],
            'amplifier_offset_allowance_V':.0005,
            'resistor_mismatch_and_common_mode_included':True,
            'rail_saturation_dynamic_response_and_guard_drop_proven':False,
            'full_pair_voltage_measured_at':'Internal A_BR minus B_BR before router/monitor/18guard interposer'}


def rc_rows():
    rows=[]
    for name,r,c,v0 in [('startup_cold',100e3,47e-9,0.),('startup_reset',100e3,47e-9,.6),('quiet_dwell',3300.,10e-9,0.)]:
        rt=.01;ct=.05 if name=='quiet_dwell' else .1
        delays=[];never=0
        for resistance,cap,high,trip,leak in itertools.product(
                (r*(1-rt),r*(1+rt)),(c*(1-ct),c*(1+ct)),(3.,3.6),(1.48,2.74),(-5e-6,7e-6)):
            final=high+leak*resistance
            if final<=trip:never+=1;continue
            delays.append(resistance*cap*math.log((final-v0)/(final-trip)))
        rows.append({'function':name,'R_ohm':r,'C_F':c,'initial_V_assumed':v0,
                     'R_fraction':rt,'C_fraction':ct,
                     'threshold_V_assumed':[1.48,2.74],'driving_high_V_assumed':[3.,3.6],
                     'net_charge_leakage_A_assumed':[-5e-6,7e-6],
                     'min_rise_s_under_assumptions':min(delays),'max_finite_rise_s_under_assumptions':max(delays),
                     'nonreleasing_corner_count':never,'all_corner_upper_bound_earned':never==0,
                     'thresholds_are_direct_3p3V_datasheet_limits':False,
                     'reset_discharge_time_or_V0_guaranteed':False})
    return rows


def interrupted_rows():
    p=ASSUMPTIONS;rows=[];traces={};R=p['load_R_ohm_assumed'];C=p['load_C_F_assumed'];I=p['current_A_assumed']
    cases={
        'normal_single_phase':(200e-6,True,'Normal request ending'),
        'primary_timer_stuck_secondary_healthy':(p['secondary_timer_max_s_model'],True,'Healthy independent secondary limit'),
        'secondary_stuck_primary_healthy':(235.160e-6,True,'Healthy original primary limit'),
        'rail_fault_at_80us':(80e-6+p['detector_delay_s_assumed'],True,'Assumed detector latency'),
        'monitor_fault_at_80us':(80e-6+p['detector_delay_s_assumed'],True,'Assumed observation latency'),
        'both_timers_stuck_watchdog_healthy':(p['watchdog_max_s'],True,'Multiple fault; heartbeat only'),
        'driver_and_both_pair_guards_welded':(5e-3,False,'Exposed finite5ms witness; no cutoff authority'),
    }
    for name,(trip,cutoff,scope) in cases.items():
        start=p['guard_on_delay_s_assumed']
        stop=trip+p['guard_off_delay_s_assumed'] if cutoff else trip
        end=max(stop+5*R*C,12e-3) if cutoff else trip
        v=I*R*(-math.expm1(-(stop-start)/(R*C)))
        q=I*(stop-start)
        ts=np.unique(np.r_[0.,start,np.linspace(start,stop,200),stop,np.linspace(stop,end,260)])
        active=(ts>=start)&((ts<stop) if cutoff else (ts<=stop))
        vv=np.where(ts<start,0.,np.where(ts<=stop,I*R*(1-np.exp(-np.maximum(ts-start,0)/(R*C))),v*np.exp(-np.maximum(ts-stop,0)/(R*C))))
        current=np.where(active,I,0.)
        tr=np.column_stack((ts,current,vv))
        # Ideal charge impulses at switching are accounted separately; no finite
        # peak current is assigned to zero-rise-time edges.
        injected=(2 if cutoff else 1)*p['guard_edge_injection_C_assumed']
        rows.append({'case':name,'scope':scope,'cutoff_authority_in_fixture':cutoff,
                     'guard_open_s':start,'observed_command_trip_s':trip,'guard_close_s':stop if cutoff else None,
                     'energized_observation_end_s':stop,
                     'current_A':I,'external_port_charge_C':q,
                     'selected_pair_edge_injection_absolute_C':injected,
                     'sum18_contact_one_edge_injection_absolute_C':18*p['guard_edge_injection_C_assumed'],
                     'load_voltage_at_observation_end_V':v,'stored_energy_at_observation_end_J':.5*C*v*v,
                     'internal_load_discharge_charge_C':C*v if cutoff else None,
                     'external_shunt_after_cutoff_current_A':0. if cutoff else None,
                     'load_R_ohm':R,'load_C_F':C,'finite_trace_end_s':end,'trace_key':name,
                     'dose_accuracy_or_tissue_safety_earned':False})
        traces[name]=tr
    return rows,traces


def generate():
    interruptions,traces=interrupted_rows()
    data={'schema':'scci_rh.stage4.supervision-analog.v1','date':'2026-10-14',
          'scope':'Finite threshold corners, passive loading and artificial interrupted load; not biological or whole-implant validation',
          'source_sha256_lf':sha(Path(__file__)),'assumptions':ASSUMPTIONS,'rail_windows':rail_rows(),
          'comparator_windows':comparator_rows(),'difference_amplifier':difference_amplifier_rows(),
          'AFE_blank_observation':afe_rows(),'RC_holds':rc_rows(),'interruptions':interruptions,
          'secondary_timer_nominal_s':64*195400/50000*1e-6,
          'secondary_timer_declared_min_s':64*195400/50000*1e-6*.956*.999,
          'secondary_timer_declared_max_s':64*195400/50000*1e-6*1.044*1.001,
          'provisional_interphase_quiet_allocation_s':200e-6,
          'old_100us_interphase_gap_earned':False,
          'open_guard_external_fault_leakage_assumption_A_per_pin':100e-6,
          'sum18_external_fault_leakage_assumption_A':18*100e-6,
          'zero_current_after_all_faults_claimed':False}
    return data,traces


def equal(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:equal(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):equal(x,y)
    elif isinstance(a,float):assert math.isclose(a,b,rel_tol=2e-10,abs_tol=1e-18),(a,b)
    else:assert a==b,(a,b)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-results',action='store_true');args=ap.parse_args()
    d,tr=generate()
    if args.write_results:
        (HERE/'analog-results.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
        np.savez_compressed(HERE/'analog-traces.npz',**tr)
        print('Saved9rail,2comparator,AFEcorner groups and7interrupted-load cases')
    else:
        equal(d,json.loads((HERE/'analog-results.json').read_text(encoding='utf-8')))
        with np.load(HERE/'analog-traces.npz') as saved:
            assert set(saved.files)==set(tr)
            for k,v in tr.items():np.testing.assert_allclose(v,saved[k],rtol=2e-10,atol=1e-18)
        print('Supervisor analog same-model replay matches; no files written')


if __name__=='__main__':main()
