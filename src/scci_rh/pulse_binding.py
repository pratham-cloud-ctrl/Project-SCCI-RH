"""ctypes binding of the actual portable C state machine, not a Python clone."""
from pathlib import Path
import ctypes as C


class Config(C.Structure):
    _fields_=[("current_ua",C.c_uint16),("phase_us",C.c_uint16),("gap_us",C.c_uint16),
              ("period_us",C.c_uint32),("sensor_timeout_us",C.c_uint32)]


class Segment(C.Structure):
    _fields_=[("current_ua",C.c_int16),("duration_us",C.c_uint32)]


class Controller(C.Structure):
    _fields_=[("config",Config),("state",C.c_int),("fault",C.c_int),
              ("sensor_time_us",C.c_uint32),("sensor_valid",C.c_bool),
              ("configured",C.c_bool),("output",Segment),
              ("last_start_us",C.c_uint32),("has_started",C.c_bool)]


class PulseBackend:
    def __init__(self, library):
        self.lib=C.CDLL(str(Path(library).resolve()))
        self.lib.scci_rh_default_config.argtypes=[]
        self.lib.scci_rh_default_config.restype=Config
        self.lib.scci_rh_init.argtypes=[C.POINTER(Controller),Config]
        self.lib.scci_rh_init.restype=C.c_bool
        self.lib.scci_rh_sensor_update.argtypes=[C.POINTER(Controller),C.c_uint32,C.c_bool]
        self.lib.scci_rh_sensor_update.restype=None
        self.lib.scci_rh_poll.argtypes=[C.POINTER(Controller),C.c_uint32]
        self.lib.scci_rh_poll.restype=None
        self.lib.scci_rh_start_pulse.argtypes=[C.POINTER(Controller),C.c_uint32]
        self.lib.scci_rh_start_pulse.restype=C.c_bool
        self.lib.scci_rh_timer_event.argtypes=[C.POINTER(Controller)]
        self.lib.scci_rh_timer_event.restype=None
        self.lib.scci_rh_rearm.argtypes=[C.POINTER(Controller),C.c_uint32]
        self.lib.scci_rh_rearm.restype=C.c_bool
        self.controller=Controller()
        if not self.lib.scci_rh_init(C.byref(self.controller),self.lib.scci_rh_default_config()):
            raise RuntimeError("default configuration rejected")

    def sensor(self, now_us, valid=True):
        self.lib.scci_rh_sensor_update(C.byref(self.controller),int(now_us),bool(valid))

    def rearm(self, now_us):
        return bool(self.lib.scci_rh_rearm(C.byref(self.controller),int(now_us)))

    def poll(self, now_us):
        self.lib.scci_rh_poll(C.byref(self.controller),int(now_us))

    def start(self, now_us):
        return bool(self.lib.scci_rh_start_pulse(C.byref(self.controller),int(now_us)))

    def finish_segments(self):
        segments=[]
        guard=0
        while self.controller.state != 0:
            guard+=1
            if guard>4: raise RuntimeError("state machine failed to drain")
            segments.append((int(self.controller.output.current_ua),int(self.controller.output.duration_us),int(self.controller.state)))
            self.lib.scci_rh_timer_event(C.byref(self.controller))
        return segments
