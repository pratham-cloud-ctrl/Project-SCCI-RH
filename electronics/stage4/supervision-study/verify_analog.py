"""Independent saved-data KCL/energy audit, read-only unless --write-receipt.

Does not import the producer or credit unmeasured semiconductor dynamics.
"""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import math
import numpy as np

HERE=Path(__file__).resolve().parent
CHECKS=0


def close(a,b,absolute=1e-15):
    global CHECKS
    assert math.isclose(a,b,rel_tol=2e-10,abs_tol=absolute),(a,b)
    CHECKS+=1


def digest(path,normalized=False):
    b=path.read_bytes()
    if normalized:b=b.replace(b'\r\n',b'\n')
    return hashlib.sha256(b).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write-receipt',action='store_true');args=ap.parse_args()
    data=json.loads((HERE/'analog-results.json').read_text(encoding='utf-8'))
    assert data['source_sha256_lf']==digest(HERE/'analog_study.py',True)
    assert len(data['rail_windows'])==9 and len(data['interruptions'])==7
    p=data['assumptions'];t=p['resistor_fraction']
    # Independent KCL: the top resistor current supplies bottom current + bias.
    for rail in data['rail_windows']:
        for side,ibmax in [('UV',25e-9),('OV',15e-9)]:
            divider=rail['dividers'][side]
            rt=divider['top_R_ohm'];rb=divider['bottom_R_ohm']
            close(rail['nominal_'+side+'_rising_V']*rail['declared_scaling_gain']/(1+rt/rb),.4)
            for edge,limits in [('rising',(.396,.404)),('falling',(.387,.400))]:
                values=[]
                for r1,r2,threshold,ib in itertools.product(
                        (rt*(1-t),rt*(1+t)),(rb*(1-t),rb*(1+t)),limits,(-ibmax,ibmax)):
                    divider_input=threshold+r1*(threshold/r2+ib)
                    if rail['declared_scaling_gain']==1:
                        values.append(divider_input)
                    else:
                        for ri,rf,vos in itertools.product((100e3*(1-t),100e3*(1+t)),
                                (10e3*(1-t),10e3*(1+t)),(-.0006,.0006)):
                            # Inverting node is at input offset; use input and
                            # feedback currents, rather than a nominal gain.
                            values.append(divider_input*ri/rf-vos*(1+ri/rf))
                reported=rail['corner_bounds'][side+'_'+edge+'_V']
                close(min(values),reported[0]);close(max(values),reported[1])
        assert rail['startup_nominal_inside_all_rising_limits']
    quiet=next(r for r in data['comparator_windows'] if r['function']=='quiet')
    low=[];high=[]
    for a,m,b,ref,cl,ch,bl,bh,s,g in itertools.product(
            (203800*(1-t),203800*(1+t)),(2000*(1-t),2000*(1+t)),
            (203800*(1-t),203800*(1+t)),(4.096*.998,4.096*1.002),
            (-.006,.006),(-.006,.006),(-.0006,.0006),(-.0006,.0006),(-.001,.001),(40*.995,40*1.005)):
        ladder_current=ref/(a+m+b)
        low.append((ladder_current*b+cl+bl-ref/2-s)/g)
        high.append((ref-ladder_current*a+ch+bh-ref/2-s)/g)
    close(quiet['accepted_union'][0],min(low));close(quiet['accepted_union'][1],max(high))
    close(quiet['accepted_intersection'][0],max(low));close(quiet['accepted_intersection'][1],min(high))
    assert quiet['empty_window_corner_count']==0
    # Pair voltage: solve input/feedback KCL at each comparator boundary.
    pl=[];ph=[]
    for d in itertools.product((-t,t),repeat=7):
        a,m,b,rin_a,rref,rin_b,rf=[v*(1+x) for v,x in zip((232000,536000,232000,1e6,49900,1e6,49900),d)]
        for ref,common,vos,cl,ch,bl,bh in itertools.product((4.096*.998,4.096*1.002),
                (0.,24.),(-.0005,.0005),(-.006,.006),(-.006,.006),(-.0006,.0006),(-.0006,.0006)):
            mid=ref/2;ladder_current=ref/(a+m+b)
            for threshold,into in [(ladder_current*b+cl+bl,pl),(ref-ladder_current*a+ch+bh,ph)]:
                vminus=(common/rin_b+threshold/rf)/(1/rin_b+1/rf)
                vplus=vminus-vos
                va=vplus+rin_a*(vplus-mid)/rref
                into.append(va-common)
    pair=data['difference_amplifier']
    close(min(pl),pair['accepted_union_V'][0]);close(max(ph),pair['accepted_union_V'][1])
    close(max(pl),pair['accepted_intersection_V'][0]);close(min(ph),pair['accepted_intersection_V'][1])
    # AFE blank window: solve probe KCL for original pin voltage at each limit.
    al=[];ah=[]
    for d in itertools.product((-t,t),repeat=6):
        rs,rb,rhi,rhb,rlo,rlb=[v*(1+x) for v,x in zip((10e6,1e6,9500,100000,10500,100000),d)]
        for supply,comp,buffer,ib in itertools.product((3.4155,3.4845),(-.006,.006),(-.0006,.0006),(-2e-9,2e-9)):
            for rt,rbot,into in [(rlo,rlb,al),(rhi,rhb,ah)]:
                node=supply*rbot/(rt+rbot)+comp+buffer
                pin=node+rs*((node-supply)/rb+ib)
                into.append(pin)
    afe=data['AFE_blank_observation']
    close(min(al),afe['pin_voltage_accepted_union_V'][0]);close(max(ah),afe['pin_voltage_accepted_union_V'][1])
    close(max(al),afe['pin_voltage_accepted_intersection_V'][0]);close(min(ah),afe['pin_voltage_accepted_intersection_V'][1])
    assert afe['all_corners_include_zero'] and afe['guaranteed_below_RHD_0p4_DC_under_declared_bounds']
    for row in afe['loading_fixture']:
        v=row['added_input_DC_V'];source=row['source_resistance_ohm']
        # Probe current must equal original source/bleeder DC currents.
        close((3.45-v)/11e6,v/source+v/10e6)
        close(row['probe_bias_A'],v/source+v/10e6)
    max_residual=0.;points=0
    with np.load(HERE/'analog-traces.npz') as traces:
        for row in data['interruptions']:
            a=traces[row['trace_key']];start=row['guard_open_s'];stop=row['energized_observation_end_s']
            I=row['current_A'];R=row['load_R_ohm'];C=row['load_C_F'];tau=R*C
            assert a.shape[1]==3 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
            duration=stop-start;fraction=-math.expm1(-duration/tau)
            vc=I*R*fraction
            close(row['external_port_charge_C'],I*duration)
            close(row['load_voltage_at_observation_end_V'],vc)
            close(row['stored_energy_at_observation_end_J'],C*vc*vc/2)
            # Charge balance over energized interval: resistor integral+stored.
            resistor_charge=I*(duration-tau*fraction)
            close(row['external_port_charge_C'],resistor_charge+C*vc)
            cutoff=row['cutoff_authority_in_fixture']
            if cutoff:
                close(row['guard_close_s'],stop)
                close(row['internal_load_discharge_charge_C'],C*vc)
                assert row['external_shunt_after_cutoff_current_A']==0.
            else:
                assert row['guard_close_s'] is None and row['internal_load_discharge_charge_C'] is None
                assert row['external_shunt_after_cutoff_current_A'] is None
                close(a[-1,0],stop);close(a[-1,1],I)
            for time,current,voltage in a:
                dt=max(0.,min(time,stop)-start)
                expected=I*R*(-math.expm1(-dt/tau))*math.exp(-max(time-stop,0.)/tau)
                close(voltage,expected)
                close(current,I if time>=start and (time<stop or not cutoff) else 0.)
                max_residual=max(max_residual,abs(voltage-expected));points+=1
    assert not data['zero_current_after_all_faults_claimed']
    close(data['secondary_timer_nominal_s'],250.112e-6)
    for hold in data['RC_holds']:
        values=[];never=0
        for er,ec,high,threshold,leak in itertools.product((-hold['R_fraction'],hold['R_fraction']),
                (-hold['C_fraction'],hold['C_fraction']),(3.,3.6),(1.48,2.74),(-5e-6,7e-6)):
            resistance=hold['R_ohm']*(1+er);cap=hold['C_F']*(1+ec)
            # Integrate dV/dt=(Iconstant-V/R)/C analytically at threshold.
            charging_current=high/resistance+leak
            if charging_current<=threshold/resistance:never+=1;continue
            values.append(resistance*cap*math.log(
                (charging_current-hold['initial_V_assumed']/resistance)/(charging_current-threshold/resistance)))
        close(min(values),hold['min_rise_s_under_assumptions'])
        close(max(values),hold['max_finite_rise_s_under_assumptions'])
        assert never==hold['nonreleasing_corner_count']
    assert data['RC_holds'][0]['nonreleasing_corner_count']>0
    assert data['RC_holds'][2]['nonreleasing_corner_count']==0
    assert not data['old_100us_interphase_gap_earned']
    receipt={'schema':'scci_rh.stage4.supervision-independent-analog.v1','date':'2026-10-14',
             'checks':CHECKS,'trajectory_points':points,'max_trajectory_residual_V':max_residual,
             'rail_windows':9,'interrupted_load_cases':7,
             'independent_of_producer_import':True,'physical_delay_or_tissue_validation':False,
             'sha256':{name:digest(HERE/name,normalized=name.endswith(('.py','.json')))
                       for name in ('analog_study.py','analog-results.json','analog-traces.npz','verify_analog.py')}}
    path=HERE/'analog-verification.json'
    if args.write_receipt:path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    else:
        saved=json.loads(path.read_text(encoding='utf-8'))
        assert saved.keys()==receipt.keys()
        for k in receipt:
            if isinstance(receipt[k],float):assert math.isclose(saved[k],receipt[k],rel_tol=2e-10,abs_tol=1e-15)
            else:assert saved[k]==receipt[k],k
    print(f'Independent supervision analog audit: {CHECKS} checks, {points} trajectory points; no producer import')


if __name__=='__main__':main()
