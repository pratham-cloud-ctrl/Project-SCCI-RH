"""New teacher recordings evaluated at actual contact apertures.

The source generator alone receives an idealized expert time constant. Library
fitting receives sanitized observations and measured task labels. Historical
held-source teacher recordings/results remain unchanged.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from scci_rh.stage3.motor import MotorConfig
from scci_rh.stage3.expert_validation import qualify_observed_expert
from scci_rh.stage3.source_sensitivity import MovingBodyReference, capture
from scci_rh.stage3.teacher_library import build_teacher_library
from run_stage3_studies import close_nested

SOURCE_PATHS = ('src/scci_rh/stage3/source_sensitivity.py', 'src/scci_rh/stage3/teacher_library.py',
                'src/scci_rh/stage3/expert_validation.py', 'src/scci_rh/stage3/motor.py',
                'src/scci_rh/stage3/acquisition.py', 'src/scci_rh/stage3/filter_residual.py',
                'scripts/stage3_resolved_teacher_study.py')


def source_identity():
    return {p: hashlib.sha256((ROOT/p).read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
            for p in SOURCE_PATHS}


def plain(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    raise TypeError(type(value).__name__)


def teacher_coefficients(config, generator, cadence):
    # EVALUATOR / GENERATOR ONLY. No private time constant reaches a decoder.
    lead = config.foot_amplitude_m*config.movement_tau_s*2*np.pi*cadence if generator == 'idealized_inverse' else 0.
    row = np.array([config.foot_amplitude_m, lead, 0., 0.])
    return np.array([row, -row])


def observed_capture(reference, performance_seed, generator, config):
    record, observations = capture(reference, 'aperture_resolved', recording_seed=performance_seed)
    external = [{'support_time_s': o.external_measurement_time_s, 'available_time_s': o.available_time_s,
                 'position_m': list(o.external_position_m), 'valid': o.external_valid} for o in observations]
    meta = {'generator': generator, 'performance_seed': performance_seed, 'subject_seed': reference.seed,
            'cadence_hz': reference.cadence_hz, 'external_noise_seed': performance_seed+800000,
            'voltage_noise_seed': performance_seed, 'contact_geometry_seed': reference.seed+8300,
            'duration_s': reference.seconds, 'config': asdict(config),
            'privilege': 'PRIVATE_EXPERT_MOVEMENT_TAU_IN_GENERATOR_ONLY' if generator == 'idealized_inverse' else 'declared amplitude voluntary template',
            'source_variant': 'aperture_resolved', 'source_hold_s': 0.,
            'aperture_scope': '20x16 actual acquisition apertures per5msblock; private continuous reference evaluated before packet becomes available'}
    return {'generation_metadata': meta, 'observations': observations, 'external_records': external,
            'qualification': qualify_observed_expert(external, config, heldout=reference.cadence_hz == 1.15),
            'source_observation_witness': record}


def experiment():
    before = source_identity()
    config = MotorConfig(body_integration_step_s=.0025, body_integration_method='midpoint_exact_cascade',
                         acquisition_qualification_mode='bounded_residual', acquisition_clock_uncertainty_s=20e-6)
    captures, references, refinements = [], [], []
    for generator in ('legacy_voluntary', 'idealized_inverse'):
        for cadence in (1., 1.15):
            reference = MovingBodyReference(51000, 'moving_clean', seconds=12.,
                theta_m=teacher_coefficients(config, generator, cadence), cadence_hz=cadence, learning=False)
            references.append({'generator': generator, **reference.receipt()})
            for performance in (51000, 61007, 71014, 81021):
                print(f'Resolved teacher {generator} {cadence:g}Hz performance{performance}', flush=True)
                captures.append(observed_capture(reference, performance, generator, config))
            if generator == 'idealized_inverse' and cadence == 1.:
                fine = MovingBodyReference(51000, 'moving_clean', maximum_step_s=.000625, seconds=12.,
                    theta_m=teacher_coefficients(config, generator, cadence), cadence_hz=cadence, learning=False)
                fine_capture = observed_capture(fine, 51000, generator, config)
                coarse = next(c for c in captures if c['generation_metadata']['generator'] == generator
                              and c['generation_metadata']['cadence_hz'] == cadence
                              and c['generation_metadata']['performance_seed'] == 51000)
                feature_difference = float(np.max(np.abs(np.array([o.neural.values_uv for o in coarse['observations']])
                                                         -np.array([o.neural.values_uv for o in fine_capture['observations']]))))
                position_difference = float(np.max(np.abs(np.array([o.external_position_m for o in coarse['observations']])
                                                          -np.array([o.external_position_m for o in fine_capture['observations']]))))
                assert feature_difference <= 2.4 and position_difference <= .00015
                refinements.append({'generator': generator, 'cadence_hz': cadence,
                    'internal_steps_s': [.0025, .000625], 'same_noise_and_observation_support': True,
                    'feature_difference_uv': feature_difference, 'feature_allocation_uv': 2.4,
                    'position_difference_m': position_difference, 'position_allocation_m': .00015,
                    'qualified_for_tested_recording': True})
    libraries = {}
    for generator in ('legacy_voluntary', 'idealized_inverse'):
        library = build_teacher_library(captures, config, generator=generator)
        # A regenerated floating observation digest is platform specific. Bind
        # this new protocol ID to exact source/settings/recording identities;
        # the full numeric recordings are independently compared with tolerance.
        identity = {'sources': before, 'config': asdict(config), 'generator': generator,
                    'captures': [c['generation_metadata'] for c in captures
                                 if c['generation_metadata']['generator'] == generator]}
        stable_id = 'SCCI_RH-S3-RESOLVED-TEACHER-1:'+generator+':'+hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:20]
        qualification = json.loads(json.dumps(library.qualification, default=plain))
        for domain in qualification['domains'].values():
            for reference in domain['references'].values():
                reference['reference_id'] = reference['reference_id'].replace(library.library_id, stable_id)
        library = replace(library, library_id=stable_id, qualification=qualification,
                          source_limits={**library.source_limits,
            'qualification_scope': 'new aperture-resolved measured synthetic captures; not real biological data',
            'source_hold_s': 0., 'source_hold_fidelity_qualified': False,
            'source_hold_limit': 'no held source used; old held approximation remains unqualified',
            'aperture_resolved_source': True,
            'aperture_reference_refinement_scope': 'one nominal inverse teacher recording plus source-sensitivity reference study; no universal error proof'})
        libraries[generator] = library.to_record()
    assert source_identity() == before, 'Source changed during resolved teacher experiment'
    return {'schema': 'scci_rh.stage3.resolved-teacher.v1', 'result_id': 'SCCI_RH-S3-RESOLVED-TEACHER-1',
            'date': '2026-10-09', 'source_identity': before, 'config': asdict(config),
            'capture_count': len(captures), 'libraries': libraries, 'reference_refinements': refinements,
            'captures': [{**c, 'observations': [asdict(o) for o in c['observations']]} for c in captures],
            'private_evaluator_only': {'reference_trajectories': references},
            'scope': 'Fresh complete-aperture synthetic teacher recordings and independently qualified measured references. No historical recording replaced; no learner intervention or human transfer demonstrated.'}


def summary(raw):
    return {k: v for k, v in raw.items() if k not in ('captures', 'private_evaluator_only')} | {
        'captures': [{'identity': c['generation_metadata'], 'qualification': c['qualification'],
                      'observation_summary': c['source_observation_witness']['summary'],
                      'noise': c['source_observation_witness']['noise']} for c in raw['captures']]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    directory = ROOT/'results/stage3/resolved-teacher'
    path = directory/'raw.json.gz'
    raw = json.loads(json.dumps(experiment(), default=plain, allow_nan=False))
    if args.check:
        expected = json.loads(gzip.decompress(path.read_bytes()))
        # Noise bytes and adaptive ODE evaluation counts are within-host diagnostics.
        from stage3_source_sensitivity import compare
        compare(raw, expected)
        compare(summary(raw), json.loads((directory/'summary.json').read_text(encoding='utf-8')))
        print('Resolved teacher observations/libraries reproduced')
    else:
        directory.mkdir(exist_ok=True, parents=True)
        buffer = io.BytesIO()
        with gzip.GzipFile(filename='', fileobj=buffer, mode='wb', mtime=0) as stream:
            stream.write(json.dumps(raw, separators=(',', ':'), allow_nan=False).encode())
        path.write_bytes(buffer.getvalue())
        (directory/'summary.json').write_text(json.dumps(summary(raw), indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({g: v['qualification']['domains'] for g, v in raw['libraries'].items()}, indent=2))


if __name__ == '__main__': main()
