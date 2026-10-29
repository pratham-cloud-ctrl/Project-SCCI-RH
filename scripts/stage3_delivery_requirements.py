"""Derive prospective monitor requirements from new observed motor calibration.

The unchanged actual electrical adapter generates the calibration. Counterfactual
uncertainty allocations hold its measured means/response records fixed; they are
requirements for a future monitor, not circuit or dynamic-response qualification.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from scci_rh.stage3.motor import MotorConfig, calibrate
from scci_rh.stage3.electrical import MotorDelivery

SOURCE_PATHS = ('src/scci_rh/stage3/motor.py', 'src/scci_rh/stage3/acquisition.py',
                'src/scci_rh/stage3/filter_residual.py', 'src/scci_rh/stage3/electrical.py',
                'src/scci_rh/stage3/external_history.py', 'scripts/stage3_delivery_requirements.py')


def source_hashes():
    return {p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for p in SOURCE_PATHS}


def observed_map(plateaus, measured_mean, uncertainty, response_allowance_m=.0095):
    """Same measured four-route map equations as motor.calibrate, no plant gain."""
    response = np.asarray(plateaus, dtype=float)
    if (response.shape != (4, 2) or not np.all(np.isfinite(response))
            or not np.all(np.isfinite([measured_mean, uncertainty, response_allowance_m]))
            or measured_mean <= 0 or uncertainty < 0 or uncertainty >= measured_mean
            or response_allowance_m < 0):
        raise ValueError('Finite observed routes and a positive dose lower bound required')
    gain, bound = np.zeros((2, 2)), np.zeros((2, 2))
    for route, sign in enumerate((1, -1, 1, -1)):
        source = route//2
        gain[:, source] += .5*sign*response[route]/measured_mean
        bound[:, source] += .5*(response_allowance_m/(measured_mean-uncertainty)
            +np.abs(response[route])*uncertainty/(measured_mean*(measured_mean-uncertainty)))
    margin = float(np.linalg.svd(gain, compute_uv=False)[-1]-np.linalg.norm(bound, 2))
    return gain, bound, margin


def command_envelope(plateaus, mean, uncertainty, forecast_m, direction,
                     *, response_allowance_m=.0095, correction_budget_m=.025):
    direction = np.asarray(direction, dtype=float)
    if (direction.shape != (2,) or not np.all(np.isfinite(direction))
            or np.max(np.abs(direction)) > 1 or np.all(direction == 0)
            or not np.isfinite(forecast_m) or forecast_m < 0):
        raise ValueError('Finite nonzero two-source direction and forecast allocation required')
    gain, gain_u, margin = observed_map(plateaus, mean, uncertainty, response_allowance_m)
    magnitude = np.abs(direction)
    # Every term is linear in a common nonnegative command magnitude. The
    # gain/dose product term remains present; correlated errors are not averaged.
    full = gain_u@(magnitude*mean)+np.abs(gain)@(magnitude*uncertainty)+gain_u@(magnitude*uncertainty)
    remaining = correction_budget_m-forecast_m
    admitted_scale = (min(1., max(0., remaining/float(np.max(full))))
                      if margin > 0 and remaining >= 0 and np.max(full) > 0 else 0.)
    total_full = full+forecast_m
    return {'authority_margin_m': margin, 'gain_m': gain.tolist(),
            'gain_uncertainty_m': gain_u.tolist(), 'full_direction': direction.tolist(),
            'forecast_allocation_m': forecast_m,
            'full_direction_correction_allowance_m': total_full.tolist(),
            'full_direction_budget_pass': bool(margin > 0 and np.max(total_full) <= correction_budget_m),
            'maximum_common_command_scale': admitted_scale,
            'maximum_scale_allowance_m': (admitted_scale*full+forecast_m).tolist(),
            'scope': 'local steady effective-map requirement; fractional magnitude is not permission to deliver a fractional pulse or an untested density'}


def largest_uncertainty_for_full_direction(plateaus, mean, forecast, direction,
                                         response_allowance_m=.0095):
    def passes(value):
        return command_envelope(plateaus, mean, value, forecast, direction,
                                response_allowance_m=response_allowance_m)['full_direction_budget_pass']
    if not passes(0.):
        return {'feasible_even_with_zero_charge_uncertainty': False,
                'maximum_uncertainty_fraction_of_nominal': None}
    low, high = 0., mean*(1-1e-9)
    for _ in range(70):
        middle = (low+high)/2
        if passes(middle): low = middle
        else: high = middle
    return {'feasible_even_with_zero_charge_uncertainty': True,
            'maximum_uncertainty_fraction_of_nominal': low}


def run():
    config = MotorConfig(body_integration_step_s=.0025,
                         body_integration_method='midpoint_exact_cascade',
                         acquisition_qualification_mode='bounded_residual',
                         acquisition_clock_uncertainty_s=20e-6)
    records = []
    for seed in range(4):
        response, _, calibration = calibrate(seed, config, MotorDelivery())
        mean = response.measured_dose_mean_fraction
        actual_u = calibration['measured_dose_uncertainty_fraction']
        allowance = 3*config.external_noise_m+.005
        gain, gain_u, _ = observed_map(calibration['route_plateaus_m'], mean, actual_u, allowance)
        assert np.allclose(gain, response.gain_m, rtol=1e-12, atol=1e-14)
        assert np.allclose(gain_u, response.gain_uncertainty_m, rtol=1e-12, atol=1e-14)
        rows, thresholds = [], []
        for forecast in (.008, .015):
            for label, direction in (('source0', (1, 0)), ('source1', (0, -1)), ('both', (1, -1))):
                thresholds.append({'direction_id': label, 'forecast_allocation_m': forecast,
                    **largest_uncertainty_for_full_direction(calibration['route_plateaus_m'], mean,
                                                           forecast, direction, allowance)})
                for uncertainty in (0., .02, .04, .074, .10, actual_u):
                    rows.append({'direction_id': label, 'uncertainty_fraction_of_nominal': uncertainty,
                        'is_implemented_monitor': bool(uncertainty == actual_u),
                        **command_envelope(calibration['route_plateaus_m'], mean, uncertainty,
                                           forecast, direction, response_allowance_m=allowance)})
        records.append({'subject_seed': seed, 'observed_actual_map': asdict(response),
            'route_plateaus_m': calibration['route_plateaus_m'],
            'actual_charge_uncertainty_fraction_of_nominal': actual_u,
            'response_allowance_m': allowance,
            'actual_map_recovered_from_observed_records': True,
            'calibration_resources_s': {'movement': calibration['movement_calibration_s'],
                'individual_routes': calibration['route_probe_calibration_s'],
                'withheld_mixed_routes': calibration['heldout_mixed_route_calibration_s']},
            'thresholds': thresholds, 'requirements': rows})
        print(f'Observed calibration and requirements seed {seed}: complete', flush=True)
    return {'schema': 'scci_rh.stage3.delivery-requirements.v1', 'date': '2026-10-09',
        'source_sha256': source_hashes(), 'config': asdict(config), 'records': records,
        'counts': {'independent_observed_calibrations': len(records),
                   'counterfactual_requirement_rows': sum(len(r['requirements']) for r in records),
                   'full_direction_precision_thresholds': sum(len(r['thresholds']) for r in records)},
        'scope': 'Unchanged actual-monitor calibration; counterfactual engineering requirements hold measured response and charge means fixed. No new monitor, policy, waveform, dynamic-map or biological qualification.',
        'assumptions': ['0.008m and0.015m forecast allocations are comparison inputs, not fitted predictor results',
            'Prospective charge uncertainty applies both to identification and future delivered dose',
            'Full gain/dose product cross term retained; no square-root averaging of correlated errors',
            'Lower charge uncertainty must be earned by a new independently evidenced circuit',
            'Nonzero command scales are local steady-map algebra; whole-frame and dynamic domains require separate validation']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT/'results/stage3/delivery-requirements/requirements.json'
    result = run()
    if args.check:
        from run_stage3_studies import close_nested
        close_nested(json.loads(output.read_text(encoding='utf-8')), result)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(result['counts'], indent=2))


if __name__ == '__main__': main()
