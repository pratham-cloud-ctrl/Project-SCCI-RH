"""Independent ngspice comparison for the Stage 3 linear pair-load model.

Uses a locally installed shared library. No library binary is distributed.
The default prints results; --output records a receipt. Without a library,
portable/CI runs explicitly skip unless --require-library was requested.
This checks a linear ideal-current circuit, not device chemistry or efficacy.
"""
from __future__ import annotations

import argparse
import ctypes as ct
import ctypes.util
import json
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scci_rh.stage3.electrical import Load, simulate_pulse  # noqa: E402


class VectorInfo(ct.Structure):
    _fields_ = [
        ("name", ct.c_char_p), ("type", ct.c_int), ("flags", ct.c_short),
        ("real", ct.POINTER(ct.c_double)), ("complex", ct.c_void_p),
        ("length", ct.c_int),
    ]


class SharedNgspice:
    """Minimal synchronous adapter to the documented sharedspice.h API."""

    def __init__(self, library: str):
        self.library = library
        self.dll_directories = []
        if os.name == "nt" and Path(library).is_file():
            self.dll_directories.append(os.add_dll_directory(str(Path(library).parent)))
        self.lib = ct.CDLL(library)
        self.messages = []
        send_char = ct.CFUNCTYPE(ct.c_int, ct.c_char_p, ct.c_int, ct.c_void_p)
        controlled_exit = ct.CFUNCTYPE(ct.c_int, ct.c_int, ct.c_bool,
                                       ct.c_bool, ct.c_int, ct.c_void_p)
        send_data = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_int,
                                ct.c_int, ct.c_void_p)
        send_init = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_int, ct.c_void_p)
        background = ct.CFUNCTYPE(ct.c_int, ct.c_bool, ct.c_int, ct.c_void_p)

        def output(message, _identifier, _user):
            self.messages.append(message.decode("utf-8", errors="replace"))
            return 0

        def noop(*_args):
            return 0

        # Keep callback objects alive for the entire library session.
        self.callbacks = [send_char(output), send_char(noop),
                          controlled_exit(noop), send_data(noop),
                          send_init(noop), background(noop)]
        self.lib.ngSpice_Init.argtypes = [send_char, send_char, controlled_exit,
                                         send_data, send_init, background, ct.c_void_p]
        self.lib.ngSpice_Init.restype = ct.c_int
        self.lib.ngSpice_Command.argtypes = [ct.c_char_p]
        self.lib.ngSpice_Command.restype = ct.c_int
        self.lib.ngSpice_Circ.argtypes = [ct.POINTER(ct.c_char_p)]
        self.lib.ngSpice_Circ.restype = ct.c_int
        self.lib.ngGet_Vec_Info.argtypes = [ct.c_char_p]
        self.lib.ngGet_Vec_Info.restype = ct.POINTER(VectorInfo)
        if self.lib.ngSpice_Init(*self.callbacks, None) != 0:
            raise RuntimeError("ngSpice_Init failed")
        self.command("version")

    def command(self, command: str):
        if self.lib.ngSpice_Command(command.encode("ascii")) != 0:
            raise RuntimeError(f"ngspice command failed: {command}")

    def vector(self, name: str):
        pointer = self.lib.ngGet_Vec_Info(name.encode("ascii"))
        if not pointer or pointer.contents.length <= 0 or not pointer.contents.real:
            raise RuntimeError(f"ngspice vector unavailable: {name}")
        # The next ngGet_Vec_Info call may overwrite shared metadata. Copy now.
        vector = pointer.contents
        return np.ctypeslib.as_array(vector.real, shape=(vector.length,)).copy()

    def run(self, lines):
        self.command("destroy all")
        encoded = [line.encode("ascii") for line in lines]
        circuit = (ct.c_char_p * (len(encoded) + 1))(*encoded, None)
        if self.lib.ngSpice_Circ(circuit) != 0:
            raise RuntimeError("ngSpice_Circ failed")
        self.command("run")
        return self.vector("time"), self.vector("v(pol)")


def pulse_netlist(max_step_s, passive_recovery):
    """1 ps edge ramps approximate the analytical instantaneous edges.

    Icommand injects signed current from ground to the driver terminal.
    A return switch connects that terminal to ground only after active drive;
    the discharge path is therefore Rseries + switch Ron, as in Load.
    """
    lines = [
        "SCCI_RH linear pair load independent transient",
        "Icommand 0 drive PWL(0 0 1p -3m 200u -3m 200.000001u 0 "
        "300u 0 300.000001u 3m 500u 3m 500.000001u 0 1.5m 0)",
        "Rseries drive pol 1000",
        "Cpair pol 0 2u IC=0",
        "Rleak pol 0 100k",
    ]
    if passive_recovery:
        lines.extend([
            "Vgate gate 0 PWL(0 0 500u 0 500.000001u 1 1.5m 1)",
            "Sreturn drive 0 gate 0 ReturnSwitch",
            ".model ReturnSwitch SW(Ron=20 Roff=1e12 Vt=0.5 Vh=0)",
        ])
    lines.extend([
        ".options reltol=1e-9 abstol=1e-13 vntol=1e-10 method=gear",
        ".save v(pol)",
        f".tran {max_step_s:.12g} 1.5m 0 {max_step_s:.12g} UIC",
        ".end",
    ])
    return lines


def analytic_voltage(pulse, times_s):
    output = np.empty_like(times_s)
    assigned = np.zeros(times_s.shape, dtype=bool)
    for segment in pulse["segments"]:
        selected = (times_s >= segment.start_s) & (times_s <= segment.end_s)
        output[selected] = segment.at(times_s[selected])[1]
        assigned[selected] = True
    if not np.all(assigned):
        raise RuntimeError("Comparison times lie outside analytical model")
    return output


def crosscheck(simulator):
    pulse = simulate_pulse(.003, .0002, 24., Load(), recovery_s=.001)
    runs = []
    for recovery in (False, True):
        for max_step in (5e-7, 1e-7):
            times, voltage = simulator.run(pulse_netlist(max_step, recovery))
            if not (np.all(np.isfinite(times)) and np.all(np.isfinite(voltage))
                    and np.all(np.diff(times) >= 0) and len(times) == len(voltage)):
                raise RuntimeError("Invalid ngspice transient vectors")
            before_drive_end = times <= .0005
            ref_times = times if recovery else times[before_drive_end]
            ref_voltage = voltage if recovery else voltage[before_drive_end]
            reference = analytic_voltage(pulse, ref_times)
            waveform_error = float(np.max(np.abs(ref_voltage - reference)))
            drive_residual = float(np.interp(.0005, times, voltage))
            minimum = float(np.min(voltage[before_drive_end]))
            expected_min = float(pulse["segments"][0].at(.0002)[1])
            end_voltage = float(voltage[-1])
            expected_end = (pulse["polarization_after_recovery_V"] if recovery else
                            pulse["polarization_after_drive_V"] *
                            np.exp(-.001 / (Load().leakage_ohm * Load().pair_capacitance_F)))
            # 2 uV tolerance is an explicit numerical comparison criterion,
            # far below the circuit model assumptions; it is not sensor accuracy.
            scalar_error = max(abs(drive_residual - pulse["polarization_after_drive_V"]),
                               abs(minimum - expected_min), abs(end_voltage - expected_end))
            runs.append({
                "passive_recovery": recovery, "max_step_s": max_step,
                "samples": len(times), "max_waveform_absolute_error_V": waveform_error,
                "min_polarization_V": minimum, "analytical_min_polarization_V": expected_min,
                "residual_after_drive_V": drive_residual,
                "analytical_residual_after_drive_V": pulse["polarization_after_drive_V"],
                "residual_at_1p5ms_V": end_voltage,
                "analytical_residual_at_1p5ms_V": float(expected_end),
                "max_scalar_absolute_error_V": float(scalar_error),
                "passed": bool(waveform_error <= 2e-6 and scalar_error <= 2e-6),
            })
    convergence = []
    for recovery in (False, True):
        pair = [r for r in runs if r["passive_recovery"] == recovery]
        delta = abs(pair[0]["residual_at_1p5ms_V"] - pair[1]["residual_at_1p5ms_V"])
        convergence.append({"passive_recovery": recovery,
                            "refinement_delta_final_V": delta,
                            "passed": bool(delta <= 2e-6)})
    return {
        "schema_version": 1, "status": "passed" if all(r["passed"] for r in runs + convergence) else "failed",
        "library": simulator.library,
        "engine_version_messages": [m for m in simulator.messages if "ngspice-" in m],
        "warnings": sorted(set(m for m in simulator.messages if "Warning:" in m)),
        "api_source": "https://ngspice.sourceforge.io/shared.html",
        "reference_model": "src/scci_rh/stage3/electrical.py",
        "inputs": {"current_A": .003, "phase_s": .0002, "gap_s": .0001,
                   "recovery_s": .001, "series_ohm": 1000., "pair_capacitance_F": 2e-6,
                   "leakage_ohm": 100000., "passive_switch_ohm": 20.,
                   "initial_polarization_V": 0., "spice_edge_ramp_s": 1e-12},
        "acceptance_absolute_error_V": 2e-6,
        "runs": runs, "refinement_checks": convergence,
        "netlists": {"open_recovery": pulse_netlist(1e-7, False),
                     "passive_recovery": pulse_netlist(1e-7, True)},
        "scope": "Independent numerical verification of an assumed linear Rseries+(C||Rleak) pair load under ideal current, open gap, and optional switched passive recovery. No compliance clipping, current-source servo, nonlinearity, electrode chemistry, anatomy or biological recruitment is validated.",
    }


def find_library(requested):
    if requested:
        return requested
    configured = os.environ.get("NGSPICE_LIBRARY")
    if configured:
        return configured
    candidate = Path(r"E:\project workspace assests\EDA\KiCAD\bin\ngspice.dll")
    if os.name == "nt" and candidate.is_file():
        return str(candidate)
    return ctypes.util.find_library("ngspice")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", help="Path/name of an installed ngspice shared library")
    parser.add_argument("--require-library", action="store_true", help="Fail rather than skip if no library was found")
    parser.add_argument("--output", type=Path, help="Save a fresh JSON receipt; default only prints results")
    args = parser.parse_args()
    library = find_library(args.library)
    if library is None:
        result = {"status": "skipped", "reason": "No ngspice shared library found; use --library or NGSPICE_LIBRARY.",
                  "passed": False, "scope": "No independent circuit cross-check ran in this environment."}
    else:
        result = crosscheck(SharedNgspice(library))
    rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return int(result["status"] == "failed" or (result["status"] == "skipped" and args.require_library))


if __name__ == "__main__":
    raise SystemExit(main())
