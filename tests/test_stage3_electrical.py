"""Independent physical identities and fault cases for the reduced pulse model."""
import unittest
import numpy as np
from scipy.integrate import solve_ivp
from scci_rh.stage3.electrical import (Load,simulate_pulse,observe_delivery,
                                  sample_waveform,characterize,MotorDelivery,PressureDelivery)


class ElectricalMechanism(unittest.TestCase):
    def test_balanced_charge_does_not_force_zero_polarization(self):
        p=simulate_pulse(load=Load(leakage_ohm=10000))
        self.assertAlmostEqual(p['drive_net_charge_C'],0.,places=18)
        self.assertGreater(abs(p['polarization_after_drive_V']),.001)
        self.assertNotEqual(p['net_including_recovery_C'],0.)

    def test_compliance_analytic_matches_independent_ode(self):
        load=Load(series_ohm=2000,pair_capacitance_F=5e-7)
        p=simulate_pulse(.018,.0005,48,load,initial_V=4)
        state=4.; q=0.; expected_q={}
        for name,j,duration in [('cathodic',-.018,.0005),('gap',0.,.0001),('anodic',.018,.0005)]:
            def derivative(t,y):
                i=j if j==0 else np.clip(j,(-40-y[0])/load.series_ohm,(40-y[0])/load.series_ohm)
                return [(i-y[0]/load.leakage_ohm)/load.pair_capacitance_F,i]
            sol=solve_ivp(derivative,(0,duration),[state,0.],rtol=1e-10,atol=1e-13,max_step=1e-6)
            state,q=sol.y[:,-1]; expected_q[name]=q
        self.assertGreater(p['compliance_limited_s'],0.)
        for phase in expected_q:
            self.assertAlmostEqual(p['phase_charge_C'][phase],expected_q[phase],delta=2e-13)
        self.assertAlmostEqual(p['polarization_after_drive_V'],state,delta=2e-7)
        self.assertGreater(abs(p['drive_net_charge_C']),1e-7)

    def test_adc_error_bound_across_aperture_and_short_phase(self):
        for phase in (50e-6,200e-6,300e-6,497e-6):
            p=simulate_pulse(.003,phase)
            truth=-p['phase_charge_C']['cathodic']
            for offset in (0.,.1e-6,2.5e-6,4.99e-6):
                for gain,bias in ((.02,5e-6),(-.02,-5e-6)):
                    observed=observe_delivery(p,offset,gain,bias)
                    self.assertLessEqual(abs(observed['measured_cathodic_charge_C']-truth),
                        observed['phase_uncertainty_C']+1e-15)

    def test_interrupted_recharge_inhibits_readiness(self):
        result=characterize(.003,.0002,interrupted_after_phase1=True)
        self.assertFalse(result['qualified'])
        self.assertLess(result['drive_net_charge_C'],-5.9e-7)

    def test_recharge_fault_has_own_bound_and_both_phase_caps(self):
        load=Load(pair_capacitance_F=.1,leakage_ohm=1e6)
        p=simulate_pulse(.016,.0004102118145118042,48.,load,
                         gap_s=.00014054117443794163,recharge_gain=1.5)
        o=observe_delivery(p,.9271447023272923e-6,.02,5e-6)
        self.assertLessEqual(abs(o['measured_anodic_charge_C']-p['phase_charge_C']['anodic']),o['anodic_uncertainty_C'])
        cap=characterize(.016,.0005,48.,load,recharge_gain=1.5)
        self.assertGreater(cap['measured_anodic_charge_C'],1e-5)
        self.assertFalse(cap['qualified'])

    def test_prepolarized_current_differs_from_command_but_remains_bounded(self):
        p=simulate_pulse(.003,.0002,16.,Load(),initial_V=25.)
        o=observe_delivery(p,0.,.02,5e-6)
        self.assertGreater(-p['phase_charge_C']['cathodic'],.003*.0002)
        self.assertLessEqual(abs(o['measured_cathodic_charge_C']+p['phase_charge_C']['cathodic']),o['cathodic_uncertainty_C'])
        with self.assertRaises(ValueError):observe_delivery(p,gain_error=float('nan'))
        with self.assertRaises(ValueError):observe_delivery(p,offset_A=float('nan'))

    def test_prepolarized_load_cannot_hide_behind_short_terminal(self):
        result=characterize(.003,.0002,initial_V=4.)
        self.assertFalse(result['qualified'])
        self.assertGreater(abs(result['measured_open_residual_V']),1.)

    def test_adc_clock_cannot_miss_whole_microsecond_phase(self):
        p=simulate_pulse(.0001,.00005)
        observed=observe_delivery(p)
        self.assertEqual(sum(observed['times_s']<50e-6),10)
        self.assertGreater(observed['measured_cathodic_charge_C'],0.)

    def test_measured_estimate_distinct_from_true_body_input(self):
        result=MotorDelivery()({'command_current_A':.003,'phase_s':.0002,'boost_V':24.,'source_id':0})
        self.assertEqual(result['quality'],'VALID')
        self.assertNotEqual(result['delivered_phase_charge_C'],result['true_phase_charge_C'])
        self.assertGreater(result['charge_uncertainty_C'],0.)
        pressure=PressureDelivery()(.5,1.)
        self.assertNotEqual(pressure['effective_fraction'],pressure['measured_fraction'])

    def test_pressure_fraction_admits_whole_reference_frames(self):
        delivery=PressureDelivery()
        self.assertEqual(delivery(.02,0.)['effective_fraction'],0.)
        self.assertAlmostEqual(delivery(.10,0.)['effective_fraction'],3/30)
        self.assertAlmostEqual(delivery(.999,0.)['effective_fraction'],29/30)

    def test_post_delivery_failure_retains_already_delivered_body_dose(self):
        delivery=MotorDelivery(Load(pair_capacitance_F=5e-7))
        request={'command_current_A':.018,'phase_s':.0005,'boost_V':16.,'source_id':0}
        result=delivery(request)
        self.assertEqual(result['quality'],'DELIVERED_UNQUALIFIED')
        self.assertTrue(result['inhibit_next'])
        self.assertGreater(result['true_phase_charge_C'],0.)
        self.assertGreater(result['delivered_phase_charge_C'],0.)
        later=delivery(request)
        self.assertEqual(later['quality'],'INHIBITED')
        self.assertEqual(later['true_phase_charge_C'],0.)
        other=delivery({**request,'source_id':1})
        self.assertGreater(other['true_phase_charge_C'],0.)
        delivery.begin_session()
        self.assertGreater(delivery(request)['true_phase_charge_C'],0.)

    def test_command_envelope_and_failed_readiness_cannot_deliver(self):
        result=MotorDelivery()({'command_current_A':.02,'phase_s':.0005,'boost_V':48.,'source_id':0})
        self.assertEqual(result['quality'],'INHIBITED')
        self.assertEqual(result['true_phase_charge_C'],0.)
        delivery=PressureDelivery(Load(pair_capacitance_F=5e-7,leakage_ohm=1000))
        # Regardless of qualification, invalid normalized commands are refused.
        with self.assertRaises(ValueError):delivery(1.1,0.)


if __name__=='__main__':unittest.main()
