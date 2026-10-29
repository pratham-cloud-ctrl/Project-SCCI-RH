import sys
from pathlib import Path
import unittest
import ctypes

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from scci_rh.pulse_binding import PulseBackend


class CompiledPulseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates=[p for p in (ROOT/"build"/"firmware").glob("*scci_rh_pulse.*") if p.suffix in [".dll",".so",".dylib"]]
        if not candidates:
            raise unittest.SkipTest("Compile the C library using scripts/build_firmware.py to run C binding tests")
        cls.library=candidates[0]

    def backend(self): return PulseBackend(self.library)

    def test_initial_inhibition_and_charge_balance(self):
        b=self.backend()
        self.assertEqual(b.controller.output.current_ua,0)
        self.assertFalse(b.start(0))
        b.sensor(0);self.assertTrue(b.rearm(0));self.assertTrue(b.start(0))
        segments=b.finish_segments()
        self.assertEqual(segments,[(100,200,1),(0,50,2),(-100,200,3),(0,19550,4)])
        self.assertEqual(sum(i*t for i,t,_ in segments),0)
        self.assertEqual(sum(t for _,t,_ in segments),20000)

    def test_software_fault_finishes_balance_then_latches(self):
        b=self.backend();b.sensor(0);self.assertTrue(b.start(0))
        b.sensor(100,False)
        segments=b.finish_segments()
        self.assertEqual(sum(i*t for i,t,_ in segments),0)
        self.assertEqual(segments[2][0],-100)
        self.assertFalse(b.start(20000))
        self.assertFalse(b.rearm(20000))
        b.sensor(20000);self.assertTrue(b.rearm(20000));self.assertTrue(b.start(20000))

    def test_stale_and_wraparound(self):
        b=self.backend();b.sensor(0)
        self.assertFalse(b.start(100001))
        b.sensor(2**32-501);self.assertTrue(b.rearm(2**32-501))
        self.assertTrue(b.start(300))
        b.finish_segments()

    def test_overlapping_pulse_rejected(self):
        b=self.backend();b.sensor(0);self.assertTrue(b.start(0))
        self.assertFalse(b.start(1))
        b.finish_segments()
        self.assertFalse(b.start(19999))
        b.sensor(20000);self.assertTrue(b.start(20000))

    def test_invalid_configuration_stays_off(self):
        for field,value in [("current_ua",251),("phase_us",0),("period_us",10000)]:
            b=self.backend()
            cfg=b.lib.scci_rh_default_config();setattr(cfg,field,value)
            self.assertFalse(b.lib.scci_rh_init(ctypes.byref(b.controller),cfg))
            b.sensor(0)
            self.assertFalse(b.rearm(0))
            self.assertFalse(b.start(0))
            self.assertEqual(b.controller.output.current_ua,0)


if __name__=="__main__": unittest.main()
