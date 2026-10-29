"""Event-aligned, linear electrode/load and independent delivery observations.

This reduced model has no chemical safety or biological efficacy authority.
Capacitance/leakage are lumped pair assumptions, not Pt-Ir measurements.
Pulse edges and compliance transitions are analytic events, not a 4 kHz grid.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, log, isfinite, floor
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Load:
    series_ohm: float = 1000.0
    pair_capacitance_F: float = 2e-6
    leakage_ohm: float = 100000.0
    short_switch_ohm: float = 20.0

    def __post_init__(self):
        if not all(isfinite(v) for v in asdict(self).values()):
            raise ValueError('Finite load parameters required')
        if min(self.series_ohm, self.pair_capacitance_F, self.leakage_ohm) <= 0:
            raise ValueError('Positive R, C and leakage required')
        if self.short_switch_ohm < 0:
            raise ValueError('Nonnegative short switch resistance required')


@dataclass(frozen=True)
class Segment:
    start_s: float
    end_s: float
    initial_V: float
    equilibrium_V: float
    decay_per_s: float
    current_constant_A: float
    current_exponential_A: float
    mode: str
    phase: str

    def at(self, time_s):
        dt = np.asarray(time_s) - self.start_s
        e = np.exp(-self.decay_per_s * dt)
        p = self.equilibrium_V + (self.initial_V - self.equilibrium_V) * e
        i = self.current_constant_A + self.current_exponential_A * e
        return i, p

    @property
    def charge_C(self):
        dt = self.end_s - self.start_s
        b = self.decay_per_s
        return self.current_constant_A * dt + self.current_exponential_A * (-np.expm1(-b*dt)) / b

    def bulk_energy_J(self, resistance_ohm):
        dt = self.end_s - self.start_s
        a, c, b = self.current_constant_A, self.current_exponential_A, self.decay_per_s
        return resistance_ohm * (a*a*dt + 2*a*c*(-np.expm1(-b*dt))/b
                                + c*c*(-np.expm1(-2*b*dt))/(2*b))


def _crossing(initial, equilibrium, decay, threshold, max_dt):
    denominator = initial - equilibrium
    if abs(denominator) < 1e-30:
        return None
    ratio = (threshold - equilibrium) / denominator
    if not 0 < ratio < 1:
        return None
    t = -log(ratio) / decay
    return t if 1e-14 < t < max_dt - 1e-14 else None


def integrate_interval(load, start_s, duration_s, initial_V, command_A,
                       usable_V, phase, passive_short=False):
    """Exact linear segments, splitting every rail-compliance crossing."""
    if duration_s < 0 or usable_V <= 0 or not all(isfinite(v) for v in
            (start_s, duration_s, initial_V, command_A, usable_V)):
        raise ValueError('Finite interval, nonnegative duration, positive compliance required')
    end = start_s + duration_s
    t, p, segments = start_s, initial_V, []
    r, rp, c = load.series_ohm, load.leakage_ohm, load.pair_capacitance_F
    for _ in range(8):  # at most two compliance changes for a monotone interval
        remaining = end - t
        if remaining <= 1e-14:
            return segments, p
        if passive_short:
            path = r + load.short_switch_ohm
            eq, b, a, d, mode = 0., (1/path+1/rp)/c, 0., -p/path, 'passive_short'
            cross = None
        elif command_A == 0:
            eq, b, a, d, mode = 0., 1/(rp*c), 0., 0., 'open'
            cross = None
        else:
            required = r * command_A + p
            dp_current = (command_A - p/rp)/c
            upper, lower = usable_V-r*command_A, -usable_V-r*command_A
            high = required > usable_V + 1e-11 or (abs(required-usable_V) <= 1e-11 and dp_current > 0)
            low = required < -usable_V - 1e-11 or (abs(required+usable_V) <= 1e-11 and dp_current < 0)
            if high or low:
                rail = usable_V if high else -usable_V
                eq, b = rail*rp/(r+rp), (1/r+1/rp)/c
                a, d, mode = (rail-eq)/r, -(p-eq)/r, 'compliance'
                cross = _crossing(p, eq, b, upper if high else lower, remaining)
            else:
                eq, b, a, d, mode = command_A*rp, 1/(rp*c), command_A, 0., 'current'
                times = [_crossing(p, eq, b, limit, remaining) for limit in (lower, upper)]
                cross = min((v for v in times if v is not None), default=None)
        dt = remaining if cross is None else cross
        segment = Segment(t, t+dt, p, eq, b, a, d, mode, phase)
        segments.append(segment)
        p = float(segment.at(t+dt)[1])
        t += dt
    raise RuntimeError('Unexpected nonconvergent compliance transitions')


def simulate_pulse(current_A=.003, phase_s=.0002, boost_V=24., load=None,
                   initial_V=0., gap_s=.0001, recovery_s=.001,
                   recharge_gain=1., interrupted_after_phase1=False):
    """Cathodic-first pulse, open gap, positive recharge, switched passive recovery."""
    load = load or Load()
    if not 0 < current_A <= .025 or not 0 < phase_s <= .001 or boost_V <= 8:
        raise ValueError('Pulse outside model bounds')
    if recovery_s < 0 or gap_s < 0 or not .5 <= recharge_gain <= 1.5:
        raise ValueError('Invalid pulse timing or recharge gain')
    commands = [('cathodic', -current_A, phase_s, False), ('gap', 0., gap_s, False)]
    if not interrupted_after_phase1:
        commands.append(('anodic', current_A*recharge_gain, phase_s, False))
    commands.append(('recovery', 0., recovery_s, True))
    t, p, all_segments = 0., initial_V, []
    for name, current, duration, short in commands:
        segments, p = integrate_interval(load,t,duration,p,current,boost_V-8,name,short)
        all_segments.extend(segments)
        t += duration
    q_by_phase = {name: float(sum(s.charge_C for s in all_segments if s.phase==name))
                  for name in ('cathodic','gap','anodic','recovery')}
    drive_end = 2*phase_s+gap_s if not interrupted_after_phase1 else phase_s+gap_s
    pre_recovery = next((s.initial_V for s in all_segments if s.phase=='recovery'), p)
    return {
        'segments': all_segments, 'load': load, 'current_A':current_A, 'phase_s':phase_s,
        'boost_V':boost_V, 'initial_V':initial_V, 'drive_end_s':drive_end, 'gap_s':gap_s,
        'duration_s':t, 'phase_charge_C':q_by_phase,
        'drive_net_charge_C':q_by_phase['cathodic']+q_by_phase['anodic'],
        'net_including_recovery_C':sum(q_by_phase.values()),
        'polarization_after_drive_V':pre_recovery,'polarization_after_recovery_V':p,
        'compliance_limited_s':sum(s.end_s-s.start_s for s in all_segments if s.mode=='compliance'),
        'bulk_energy_J':sum(s.bulk_energy_J(load.series_ohm) for s in all_segments),
        'interrupted':interrupted_after_phase1,
        'scope':'linear assumed pair load; not chemistry, current servo transient or neural efficacy'
    }


def sample_waveform(pulse, sample_times_s):
    times=np.asarray(sample_times_s)
    current=np.zeros(times.shape); polarization=np.full(times.shape,pulse['initial_V'])
    terminal=np.zeros(times.shape)
    for seg in pulse['segments']:
        selected=(times >= seg.start_s-1e-15) & (times < seg.end_s-1e-15)
        i,p=seg.at(times[selected]); current[selected]=i; polarization[selected]=p
        terminal[selected]=pulse['load'].series_ohm*i+p
    return current,terminal,polarization


def observe_delivery(pulse, adc_offset_s=1.3e-6, gain_error=.012, offset_A=2e-6):
    """Separate 200 kHz, 12-bit ADC. Integrate signed samples, carry edge uncertainty.

    Uncertainty excludes unbounded inter-sample spikes: no peak-proof claim.
    Edge identities are shared timer metadata, not analog-current truth.
    """
    if not all(isfinite(v) for v in (adc_offset_s,gain_error,offset_A)) or not 0 <= adc_offset_s < 5e-6 or abs(gain_error) > .02 or abs(offset_A) > 5e-6:
        raise ValueError('Monitor errors exceed declared Stage2 allocations')
    rate=200000.; dt=1/rate; lsb=.05/(2**12)
    times=np.arange(adc_offset_s,pulse['duration_s'],dt)
    current,voltage,polarization=sample_waveform(pulse,times)
    analog=current*(1+gain_error)+offset_A
    quantized=np.clip(np.rint(analog/lsb),-2048,2047)*lsb
    saturation=bool(np.any((analog < -.025) | (analog > .025-lsb)))
    cathodic=times < pulse['phase_s']
    anodic=(times >= pulse['phase_s']+pulse['gap_s']) & (times < pulse['drive_end_s'])
    # An interrupted pulse has no active second-phase window.
    if pulse['interrupted']:anodic[:]=False
    measured_cathodic=-float(quantized[cathodic].sum()*dt)
    measured_anodic=float(quantized[anodic].sum()*dt)
    nominal_witness=2*pulse['current_A']*5e-6+(.5*lsb+5e-6)*pulse['phase_s']+.02*pulse['current_A']*pulse['phase_s']
    # Controller-visible conservative bounds cannot secretly assume a faulted
    # phase follows the requested amplitude. Measured-charge gain inversion
    # plus a DECLARED complete-waveform +/-25mA peak assumption bounds tested
    # monotone phases. Non-saturated samples do not prove unseen peak amplitude.
    # This is intentionally looser than Stage2's rectangular-command witness.
    peak_assumption_A=.025
    def charge_bound(measured, mask):
        observed_support_s=float(mask.sum())*dt
        return ((.02*abs(measured)+(.5*lsb+5e-6)*observed_support_s)/(1-.02)
                +2*peak_assumption_A*5e-6)
    uncertainty=charge_bound(measured_cathodic,cathodic)
    anodic_uncertainty=charge_bound(measured_anodic,anodic) if not pulse['interrupted'] else 0.
    # Release the passive switch, then sample open-circuit terminals at the
    # next 20 kHz aperture. Shorted terminal voltage alone hides polarization.
    # Voltage range/error below are NEW chosen Stage3 monitoring assumptions.
    voltage_aperture_delay_s=25e-6
    residual_at_sample=pulse['polarization_after_recovery_V']*exp(-voltage_aperture_delay_s/
        (pulse['load'].leakage_ohm*pulse['load'].pair_capacitance_F))
    voltage_lsb=100/(2**12)  # signed +/-50 V input range through assumed divider
    measured_residual=float(np.clip(np.rint((residual_at_sample*1.01+.001)/voltage_lsb),-2048,2047)*voltage_lsb)
    residual_uncertainty_V=(.5*voltage_lsb+.005+.02*abs(measured_residual))/(1-.02)
    return {'times_s':times,'current_A':quantized,'terminal_truth_V':voltage,
            'polarization_truth_V':polarization,'measured_cathodic_charge_C':measured_cathodic,
            'measured_anodic_charge_C':measured_anodic,
            'measured_drive_net_charge_C':measured_anodic-measured_cathodic,
            'phase_uncertainty_C':uncertainty,'monitor_saturated':saturation,
            'cathodic_uncertainty_C':uncertainty,'anodic_uncertainty_C':anodic_uncertainty,
            'drive_net_uncertainty_C':uncertainty+anodic_uncertainty,
            'nominal_rectangular_witness_uncertainty_C':nominal_witness,
            'complete_waveform_peak_assumption_A':peak_assumption_A,
            'charge_bounds_valid_under_assumptions':not saturation,
            'measured_open_residual_V':measured_residual,
            'residual_uncertainty_V':residual_uncertainty_V,
            'voltage_aperture_delay_s':voltage_aperture_delay_s,
            'monitor_scope':'terminal/polarization arrays are evaluator truth; readiness uses separately quantized open terminal observation'}


def characterize(current_A, phase_s, boost_V=24., load=None, initial_V=0., **kwargs):
    pulse=simulate_pulse(current_A,phase_s,boost_V,load,initial_V,**kwargs)
    observed=observe_delivery(pulse)
    actual=-pulse['phase_charge_C']['cathodic']
    measured=observed['measured_cathodic_charge_C']
    nominal=current_A*phase_s
    # Conservative observation gate, not a ground-truth shortcut or chemistry
    # qualification. 25 us aperture fits in the selected 250 us rearm allocation.
    readiness=(abs(observed['measured_open_residual_V'])+observed['residual_uncertainty_V']) <= .02
    qualified=(readiness and observed['charge_bounds_valid_under_assumptions'] and
               measured >= 0 and observed['measured_anodic_charge_C'] >= 0 and
               abs(measured)+observed['cathodic_uncertainty_C'] <= 1e-5 and
               abs(observed['measured_anodic_charge_C'])+observed['anodic_uncertainty_C'] <= 1e-5
               and not pulse['interrupted'])
    return {'true_cathodic_charge_C':actual,'measured_cathodic_charge_C':measured,
            'charge_uncertainty_C':observed['phase_uncertainty_C'],
            'anodic_charge_uncertainty_C':observed['anodic_uncertainty_C'],
            'measured_anodic_charge_C':observed['measured_anodic_charge_C'],
            'drive_net_uncertainty_C':observed['drive_net_uncertainty_C'],
            'nominal_rectangular_witness_uncertainty_C':observed['nominal_rectangular_witness_uncertainty_C'],
            'nominal_cathodic_charge_C':nominal,'effective_fraction':actual/nominal,
            'measured_fraction':measured/nominal,
            'uncertainty_fraction':observed['phase_uncertainty_C']/nominal,
            'qualified':qualified,'reason':'MODEL_READY' if qualified else 'MODEL_RECOVERY_OR_DELIVERY_VETO',
            'drive_net_charge_C':pulse['drive_net_charge_C'],
            'polarization_after_drive_V':pulse['polarization_after_drive_V'],
            'polarization_after_recovery_V':pulse['polarization_after_recovery_V'],
            'measured_open_residual_V':observed['measured_open_residual_V'],
            'residual_uncertainty_V':observed['residual_uncertainty_V'],
            'compliance_limited_s':pulse['compliance_limited_s'],
            'bulk_energy_J':pulse['bulk_energy_J']}


class MotorDelivery:
    """Characterized isolated pulses at 40 Hz; separate route states assumed reset.

    This adapter does not replace Stage4 source/routing/circuit integration.
    Post-delivery failure retains delivered dose and vetoes subsequent rearm;
    it never retroactively erases an already delivered cathodic phase.
    'true_phase_charge_C' is a body/evaluator field, forbidden to controller.
    """
    def __init__(self,load=None):
        self.load=load or Load()
        self.begin_session()

    def begin_session(self):
        """Fresh independent simulator run, never automatic runtime rearm.

        The experiment owns this boundary. Real requalification/recovery from
        a fault requires monitored state and remains Stage4 circuit work.
        """
        self._source_inhibited=set()

    def __call__(self,request):
        current,phase=request['command_current_A'],request['phase_s']
        admissible=(.0001 <= current <= .02 and .00005 <= phase <= .0005
                    and current*phase <= 9e-6 and request['source_id'] in (0,1)
                    and request['boost_V'] in (16,24,36,48))
        if not admissible:
            return {'delivered_phase_charge_C':0., 'true_phase_charge_C':0.,
                    'charge_uncertainty_C':0., 'quality':'INHIBITED',
                    'electrical_evidence':{'reason':'COMMAND_ENVELOPE_VETO'}}
        source=request['source_id']
        if source in self._source_inhibited:
            return {'delivered_phase_charge_C':0.,'true_phase_charge_C':0.,
                    'charge_uncertainty_C':0.,'quality':'INHIBITED','inhibit_next':True,
                    'electrical_evidence':{'reason':'LATCHED_REARM_VETO'}}
        result=characterize(current,phase,request['boost_V'],self.load)
        if not result['qualified']:self._source_inhibited.add(source)
        return {'delivered_phase_charge_C':result['measured_cathodic_charge_C'],
                'true_phase_charge_C':result['true_cathodic_charge_C'],
                'charge_uncertainty_C':result['charge_uncertainty_C'],
                'quality':'VALID' if result['qualified'] else 'DELIVERED_UNQUALIFIED',
                'inhibit_next':not result['qualified'], 'electrical_evidence':result}


class PressureDelivery:
    """Averaged, separately routed 3 x 120 Hz reference dose over 250 ms.

    Fraction means admitted train fraction, not scaling biological gain.
    Dose averaging is declared; individual route transitions remain Stage4.
    """
    def __init__(self,load=None):
        self.evidence=characterize(.003,.0003,24.,load or Load())
    def __call__(self,requested_fraction,time_s):
        if not isfinite(requested_fraction) or not 0 <= requested_fraction <= 1:
            raise ValueError('Train fraction outside [0,1]')
        # 120 Hz *250 ms =30 complete reference frames; every admitted frame
        # contains all three distinct logical profiles at offsets0/2/4 ms.
        e=self.evidence
        admitted=floor(30*requested_fraction+1e-12)/30 if e['qualified'] else 0.
        return {'effective_fraction':admitted*e['effective_fraction'],
                'measured_fraction':admitted*e['measured_fraction'],
                'uncertainty_fraction':admitted*e['uncertainty_fraction'],
                'qualified':e['qualified'],'reason':e['reason']}
