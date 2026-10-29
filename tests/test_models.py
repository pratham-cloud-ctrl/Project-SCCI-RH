import sys
from pathlib import Path
import unittest
from dataclasses import replace
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from scci_rh.motor import MotorConfig, phase_estimate, simulate_motor
from scci_rh.pressure import PressureConfig, simulate_pressure


class MotorEvidenceTests(unittest.TestCase):
    def test_no_assumed_learning_benefit_means_no_retained_advantage(self):
        cfg=replace(MotorConfig(),sessions=12,teaching_beta=0)
        _,base,_=simulate_motor(24101,"unassisted",cfg)
        _,assist,_=simulate_motor(24101,"calibrated",cfg)
        self.assertEqual(base["final_skill"],assist["final_skill"])
        self.assertEqual(base["retained_rmse"],assist["retained_rmse"])
        self.assertLess(assist["first_assisted_rmse"],base["first_assisted_rmse"])

    def test_latency_compensation_helps_but_unknown_latency_breaks_alignment(self):
        dt=.01
        phase=2*np.pi*np.arange(1400)*dt
        good=phase_estimate(phase,dt,.08,.35,np.random.default_rng(1),True)
        bad=phase_estimate(phase,dt,.08,.35,np.random.default_rng(1),True,.05)
        direct=phase_estimate(phase,dt,.08,.35,np.random.default_rng(1),False)
        rmse=lambda p: np.sqrt(np.mean(np.angle(np.exp(1j*(p-phase)))[200:]**2))
        self.assertLess(rmse(good),.10)
        self.assertGreater(rmse(bad),1)
        self.assertGreater(rmse(direct),1)

    def test_phase_shuffling_can_harm_learning(self):
        cfg=replace(MotorConfig(),sessions=15)
        _,base,_=simulate_motor(24102,"unassisted",cfg)
        _,bad,_=simulate_motor(24102,"shuffled",cfg)
        self.assertGreater(bad["retained_rmse"],base["retained_rmse"])

    def test_study_is_reproducible(self):
        cfg=replace(MotorConfig(),sessions=3)
        a=simulate_motor(24103,"calibrated",cfg)
        b=simulate_motor(24103,"calibrated",cfg)
        self.assertEqual(a[0],b[0])
        self.assertEqual(a[1],b[1])
        np.testing.assert_array_equal(a[2]["assisted"],b[2]["assisted"])


class PressureEvidenceTests(unittest.TestCase):
    def test_closed_loop_improves_paired_nominal_plants(self):
        for seed in [24001,24003,24005]:
            base,_=simulate_pressure(seed,"unassisted")
            loop,tr=simulate_pressure(seed,"closed_loop")
            self.assertLess(loop["mae_mmhg"],base["mae_mmhg"])
            self.assertTrue(np.all((tr["command"]>=0)&(tr["command"]<=1)))

    def test_weak_actuator_cannot_meet_target(self):
        good,_=simulate_pressure(24000)
        weak,_=simulate_pressure(24000,config=replace(PressureConfig(),gain_scale=.6))
        self.assertGreater(weak["mae_mmhg"],good["mae_mmhg"]+5)
        self.assertGreater(weak["saturation_fraction"],.95)

    def test_missing_and_invalid_sensor_inhibit_output(self):
        cfg=replace(PressureConfig(),dropout=True,invalid_sensor=True)
        sm,tr=simulate_pressure(24000,config=cfg)
        self.assertEqual(sm["stale_nonzero_steps"],0)
        self.assertTrue(np.all(tr["command"][tr["sensor_stale"].astype(bool)]==0))
        missing=(tr["time_s"]>76)&(tr["time_s"]<87)
        self.assertTrue(np.all(tr["command"][missing]==0))
        invalid=(tr["time_s"]>=105)&(tr["time_s"]<110)
        self.assertTrue(np.all(tr["command"][invalid]==0))
        self.assertGreater(np.max(tr["command"][tr["time_s"]>115]),0)

    def test_reproducibility_and_finite_state(self):
        a,tr=simulate_pressure(24008)
        b,tr2=simulate_pressure(24008)
        self.assertEqual(a,b)
        np.testing.assert_array_equal(tr["map_mmhg"],tr2["map_mmhg"])
        self.assertTrue(np.all(np.isfinite(tr["map_mmhg"])))

    def test_every_available_fresh_sample_has_a_finite_measurement(self):
        for cfg in [PressureConfig(),replace(PressureConfig(),dropout=True,invalid_sensor=True)]:
            _,tr=simulate_pressure(24000,config=cfg)
            expected=tr["sensor_available"].astype(bool)&~tr["sensor_stale"].astype(bool)
            self.assertTrue(np.all(np.isfinite(tr["measurement_mmhg"][expected])))
            self.assertTrue(np.isfinite(tr["measurement_mmhg"][-1]))
            missing=~tr["sensor_available"].astype(bool)
            self.assertTrue(np.all(np.isnan(tr["measurement_mmhg"][missing])))
            if cfg.invalid_sensor:
                invalid=(tr["time_s"]>=105)&(tr["time_s"]<108)
                self.assertTrue(np.all(np.isnan(tr["measurement_mmhg"][invalid])))


if __name__=="__main__": unittest.main()
