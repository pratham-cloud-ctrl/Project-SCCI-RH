"""Competence-gated observed teacher references for a new mechanism revision.

This module never imports a body simulator or reads private generation records.
All fitting uses measured voltage-derived features and measured external labels.
Historical motor studies retain their original references and are not modified.
"""
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import numpy as np
from .acquisition import AcquisitionConfig, NeuralFeatures
from .expert_validation import qualify_observed_expert, validate_observed_teacher_decoder
from .motor import ExpertRepresentation, MotorConfig, Observation, _fit_neural, _metrics, task_basis

KINDS = ('learner_only', 'expert_external', 'expert_neural')
CADENCES_HZ = (1., 1.15)
SCHEMA = 'scci_rh.stage3.teacher-library.v1'


def observed_capture_view(capture):
    """Select the public measurements and declared source identity only.

    Accepts both live capture objects and saved JSON captures. Private evaluator
    fields and the expert generator's movement time constant are never read.
    """
    meta = capture['generation_metadata']
    identity = {key: meta[key] for key in ('generator', 'performance_seed', 'subject_seed',
                'cadence_hz', 'external_noise_seed', 'voltage_noise_seed',
                'contact_geometry_seed', 'duration_s', 'privilege')}
    identity['source_mode'] = meta['config']['source_mode']
    observations = []
    for value in capture['observations']:
        if isinstance(value, Observation):
            observations.append(value)
        else:
            neural = NeuralFeatures(**value['neural'])
            observations.append(Observation(value['available_time_s'], tuple(value['external_position_m']),
                                            value['external_measurement_time_s'], value['external_valid'], neural))
    return {'observations': observations, 'external_records': capture['external_records'],
            'identity': identity,
            'generation_metadata': {'performance_seed': identity['performance_seed'],
                                    'cadence_hz': identity['cadence_hz']}}


def _capture_permissions(view, config, *, neural=True):
    """External labels retain permission independently of neural availability."""
    observations, records = view['observations'], view['external_records']
    errors = []
    if len(observations) != len(records) or len(observations) < 80:
        return ['OBSERVATION_EXTERNAL_RECORD_LENGTH_MISMATCH']
    duration = view['identity']['duration_s']
    if (not np.isfinite(duration) or duration <= 0
            or len(observations) != round(duration/config.dt_s)
            or not np.allclose([o.available_time_s for o in observations],
                               config.dt_s*np.arange(1, len(observations)+1), rtol=0., atol=1e-10)):
        errors.append('COMPLETE_RECORDING_CLOCK_OR_DURATION_FAILED')
    previous = previous_external = previous_neural_end = -np.inf
    for o, r in zip(observations, records):
        n = o.neural
        values = np.r_[o.available_time_s, o.external_measurement_time_s, o.external_position_m]
        if np.asarray(o.external_position_m).shape != (2,) or not np.all(np.isfinite(values)):
            errors.append('NONFINITE_OR_WRONG_DIMENSION_MEASUREMENT'); break
        if (o.available_time_s <= previous or o.external_measurement_time_s <= previous_external
                or o.external_measurement_time_s > o.available_time_s
                or o.available_time_s-o.external_measurement_time_s > config.external_freshness_s):
            errors.append('MEASUREMENT_SUPPORT_OR_CLOCK_INVALID'); break
        if (r['support_time_s'] != o.external_measurement_time_s
                or r['available_time_s'] != o.available_time_s
                or r['valid'] != o.external_valid
                or not np.array_equal(r['position_m'], o.external_position_m)):
            errors.append('EXTERNAL_LABEL_SOURCE_MISMATCH'); break
        if neural:
            neural_values = np.r_[n.available_time_s, n.support_start_s, n.support_end_s,
                                  n.representative_time_s, n.clock_uncertainty_s, n.values_uv]
            if not np.all(np.isfinite(neural_values)) or len(n.values_uv) != 32:
                errors.append('NONFINITE_OR_WRONG_DIMENSION_MEASUREMENT'); break
            if (n.support_end_s <= previous_neural_end or n.available_time_s > o.available_time_s
                    or n.clock_uncertainty_s < 0 or n.support_start_s > n.support_end_s
                    or not n.support_start_s <= n.representative_time_s <= n.support_end_s
                    or n.support_end_s+2*n.clock_uncertainty_s > n.available_time_s
                    or n.acquired_samples != 320):
                errors.append('MEASUREMENT_SUPPORT_OR_CLOCK_INVALID'); break
        previous = o.available_time_s
        previous_external, previous_neural_end = o.external_measurement_time_s, n.support_end_s
    return errors


def _public_identity(views, config):
    digest = hashlib.sha256()
    digest.update(SCHEMA.encode())
    public_settings = {key: getattr(config, key) for key in (
        'dt_s', 'external_freshness_s', 'foot_amplitude_m', 'event_spacing_s',
        'retention_spatial_threshold_m', 'retention_timing_threshold_s',
        'controller_position_uncertainty_limit_m', 'maximum_prediction_horizon_s', 'source_mode')}
    digest.update(json.dumps(public_settings, sort_keys=True, separators=(',', ':')).encode())
    for view in views:
        digest.update(json.dumps(view['identity'], sort_keys=True, separators=(',', ':')).encode())
        for o in view['observations']:
            digest.update(json.dumps(asdict(o), sort_keys=True, separators=(',', ':')).encode())
    return digest.hexdigest()


def _decoded_positions(model, observations):
    selected = [o for o in observations if o.external_valid and o.neural.valid]
    if model is None or len(selected) < 20:
        return selected, None, None
    z = (np.array([o.neural.values_uv for o in selected])-model['mean'])/model['scale']
    decoded = np.column_stack((np.ones(len(z)), z))@model['weights']
    return selected, decoded, z


def _metric_record(times, positions, config, *, cadence_hz):
    if len(times) < 80 or not np.all(np.isfinite(positions)):
        return {'qualified': False, 'reason': 'INSUFFICIENT_OR_NONFINITE_REPRESENTATION', 'metrics': None}
    metrics = _metrics(times, positions, config, heldout=cadence_hz == 1.15)
    qualified = (metrics['scored_contact_events'] > 0
                 and metrics['contact_spatial_rmse_m'] is not None
                 and metrics['contact_timing_rmse_s'] is not None
                 and metrics['contact_spatial_rmse_m'] <= config.retention_spatial_threshold_m
                 and metrics['contact_timing_rmse_s'] <= config.retention_timing_threshold_s)
    return {'qualified': bool(qualified), 'reason': 'DECLARED_CONTACT_CRITERION_PASSED' if qualified else 'DECLARED_CONTACT_CRITERION_FAILED',
            'metrics': metrics}


def _independent_validation(view, model, coefficients, config, permission_errors):
    cadence = float(view['identity']['cadence_hz'])
    observed = qualify_observed_expert(view['external_records'], config, heldout=cadence == 1.15)
    neural_errors = permission_errors['neural']
    selected, decoded, z = (_decoded_positions(model, view['observations']) if not neural_errors
                            else ([], None, None))
    decoding = (validate_observed_teacher_decoder(model, view) if not neural_errors else
                {'available': False, 'reason': 'MEASUREMENT_PERMISSION_FAILED'})
    decoder_reasons = list(neural_errors)
    expected_after_warmup = [o for o in view['observations']
                             if o.available_time_s >= AcquisitionConfig().warmup_s-1e-12]
    full_capture_eligible = bool(expected_after_warmup) and all(o.external_valid and o.neural.valid for o in expected_after_warmup)
    if not full_capture_eligible:
        decoder_reasons.append('POST_WARMUP_CAPTURE_INCOMPLETE')
    if not decoding['available'] or decoded is None:
        decoder_reasons.append('DECODER_OR_CAPTURE_UNAVAILABLE')
        budget = None
        decoded_task = {'qualified': False, 'reason': 'DECODER_UNAVAILABLE', 'metrics': None}
    else:
        budget = 2*decoding['position_rmse_m']+2*config.maximum_prediction_horizon_s*decoding['velocity_rmse_m_per_s']
        if not np.isfinite(budget) or budget >= config.controller_position_uncertainty_limit_m:
            decoder_reasons.append('DECODER_RESIDUAL_ALLOCATION_FAILED')
        if not np.all(np.isfinite(z)) or np.max(np.abs(z)) > 5.:
            decoder_reasons.append('NEURAL_FEATURE_RANGE_EXCEEDED')
        decoded_task = _metric_record([o.external_measurement_time_s for o in selected], decoded[:, :2], config, cadence_hz=cadence)
        if not decoded_task['qualified']:
            decoder_reasons.append('DECODED_TEACHER_CONTACT_CRITERION_FAILED')
    templates = {}
    times = np.array([r['support_time_s'] for r in view['external_records']])
    measured = np.array([r['position_m'] for r in view['external_records']])
    basis = np.array([task_basis(t, heldout=cadence == 1.15) for t in times])
    for kind, coef in coefficients.items():
        reasons = list(permission_errors['external'] if kind == 'expert_external' else neural_errors)
        predicted = basis@coef.T
        rmse = float(np.sqrt(np.mean((predicted-measured)**2)))
        # Allocate the existing observer's 2*position-RMSE term to this static
        # trajectory representation. No velocity prediction is claimed here.
        position_allocation = 2*rmse
        task = _metric_record(times, predicted, config, cadence_hz=cadence)
        if not task['qualified']:
            reasons.append('TEMPLATE_CONTACT_CRITERION_FAILED')
        if not np.isfinite(position_allocation) or position_allocation >= config.controller_position_uncertainty_limit_m:
            reasons.append('COMPLETE_TRAJECTORY_REPRESENTATION_ALLOCATION_FAILED')
        templates[kind] = {'qualified': not reasons, 'reasons': reasons,
                           'measured_trajectory_rmse_m': rmse,
                           'position_error_allocation_m': position_allocation,
                           'task_criterion': task,
                           'scope': 'all withheld external records, fixed nominal-trained coefficients; empirical allocation, not a confidence guarantee'}
    return {'identity': view['identity'], 'observed_teacher': observed,
            'decoder': {'qualified': not decoder_reasons, 'reasons': decoder_reasons,
                        'independent_residuals': decoding, 'error_allocation_m': budget,
                        'decoded_task_criterion': decoded_task,
                        'post_warmup_capture_complete': full_capture_eligible},
            'representations': templates}


@dataclass(frozen=True)
class TeacherLibrary:
    library_id: str
    generator: str
    references_by_cadence: dict
    qualification: dict
    resource_accounting: dict
    source_limits: dict
    decoder_model: dict | None

    @property
    def references(self):
        """Nominal-domain references; consumers of other cadences must select it."""
        return dict(self.references_by_cadence[1.])

    def reference_for(self, kind, *, cadence_hz=1.):
        if kind not in KINDS:
            raise ValueError('unknown teacher representation')
        if not np.isfinite(cadence_hz) or cadence_hz not in self.references_by_cadence:
            return replace(self.references[kind], qualified=False,
                           qualification_reason='TEACHER_REFERENCE_OUTSIDE_VALIDATED_CADENCE')
        return self.references_by_cadence[cadence_hz][kind]

    def reference_id_for(self, kind, *, cadence_hz=1.):
        self.reference_for(kind, cadence_hz=cadence_hz)
        return f'{self.library_id}:{kind}:{cadence_hz:g}Hz'

    def to_record(self):
        return {'schema': SCHEMA, 'library_id': self.library_id, 'generator': self.generator,
                'references_by_cadence': {f'{cadence:g}': {kind: asdict(ref) for kind, ref in refs.items()}
                                          for cadence, refs in self.references_by_cadence.items()},
                'qualification': self.qualification, 'resource_accounting': self.resource_accounting,
                'source_limits': self.source_limits,
                'decoder_model': None if self.decoder_model is None else {
                    key: value.tolist() if isinstance(value, np.ndarray) else value
                    for key, value in self.decoder_model.items()}}


def build_teacher_library(captures, config=MotorConfig(), *, generator,
                          training_performance_seed=51000):
    """Fit one explicit nominal training capture; qualify all withheld recordings.

    No outcome-based training/reference selection is performed. Both cadence
    domains preserve independent competence, decoder, and representation gates.
    Rejection never substitutes external data under an expert-neural label.
    """
    if generator not in {'legacy_voluntary', 'idealized_inverse'}:
        raise ValueError('unsupported generator identity')
    views = [observed_capture_view(c) for c in captures
             if c['generation_metadata']['generator'] == generator]
    views.sort(key=lambda view: (view['identity']['cadence_hz'], view['identity']['performance_seed']))
    selected = [v for v in views if v['identity']['cadence_hz'] == 1.
                and v['identity']['performance_seed'] == training_performance_seed]
    if len(selected) != 1:
        raise ValueError('one explicitly identified nominal training capture required')
    training = selected[0]
    identity_errors = []
    if any(v['identity']['cadence_hz'] not in CADENCES_HZ for v in views):
        identity_errors.append('UNSUPPORTED_RECORDING_CADENCE')
    for cadence in CADENCES_HZ:
        group = [v for v in views if v['identity']['cadence_hz'] == cadence]
        noise_ids = [(v['identity']['external_noise_seed'], v['identity']['voltage_noise_seed']) for v in group]
        if len(group) != 4 or len(set(noise_ids)) != 4:
            identity_errors.append(f'INDEPENDENT_RECORDING_COUNT_FAILED_{cadence:g}HZ')
    if any(v['identity']['subject_seed'] != training['identity']['subject_seed']
           or v['identity']['contact_geometry_seed'] != training['identity']['contact_geometry_seed']
           or v['identity']['source_mode'] != config.source_mode
           or v['identity']['privilege'] != training['identity']['privilege'] for v in views):
        identity_errors.append('TEACHER_SOURCE_IDENTITY_MISMATCH')
    permissions = [{kind: _capture_permissions(v, config, neural=kind == 'neural')
                    for kind in ('external', 'neural')} for v in views]
    training_permission = permissions[next(i for i, v in enumerate(views) if v is training)]
    model = None if training_permission['neural'] else _fit_neural(training['observations'])
    public_id = _public_identity(views, config)
    library_id = 'SCCI_RH-S3-TEACHER-LIBRARY-1:'+generator+':'+public_id[:20]
    # A shared declared post-warmup time domain prevents failed neural capture
    # from removing or shifting the external-only comparator's measurements.
    nominal = [o for o in training['observations'] if o.external_valid
               and o.available_time_s >= AcquisitionConfig().warmup_s-1e-12]
    times = np.array([o.external_measurement_time_s for o in nominal])
    external = np.array([o.external_position_m for o in nominal])
    train = np.array([], dtype=int)
    cut = times[int(len(times)*.75)] if len(times) >= 80 else None
    if cut is not None and not training_permission['external']:
        train = np.flatnonzero(times < cut-.100)[4:-4]
    basis = np.array([task_basis(t) for t in times])
    external_coef = np.zeros((2, 4)); neural_coef = np.zeros((2, 4))
    fit_external = fit_neural = None
    if len(train) >= 40:
        external_coef = np.linalg.lstsq(basis[train], external[train], rcond=None)[0].T
        fit_external = float(np.sqrt(np.mean((basis[train]@external_coef.T-external[train])**2)))
    neural_nominal = [o for o in nominal if o.neural.valid]
    neural_times = np.array([o.external_measurement_time_s for o in neural_nominal])
    neural_train = (np.flatnonzero(neural_times < cut-.100)[4:-4]
                    if cut is not None and model is not None else np.array([], dtype=int))
    neural_training_complete = bool(nominal) and all(o.neural.valid for o in nominal)
    if len(neural_train) >= 40:
        neural_basis = np.array([task_basis(t) for t in neural_times])
        x = np.array([o.neural.values_uv for o in neural_nominal])
        z = (x-model['mean'])/model['scale']
        decoded = np.column_stack((np.ones(len(z)), z))@model['weights']
        neural_coef = np.linalg.lstsq(neural_basis[neural_train], decoded[neural_train, :2], rcond=None)[0].T
        fit_neural = float(np.sqrt(np.mean((neural_basis[neural_train]@neural_coef.T-decoded[neural_train, :2])**2)))
    coefficients = {'expert_external': external_coef, 'expert_neural': neural_coef}
    validations = [_independent_validation(v, model, coefficients, config, p)
                   for v, p in zip(views, permissions) if v is not training]
    observed = [{'identity': v['identity'], 'qualification': qualify_observed_expert(v['external_records'], config,
                  heldout=v['identity']['cadence_hz'] == 1.15)} for v in views]
    domains, references_by_cadence = {}, {}
    training_observed = next(r['qualification'] for r in observed if r['identity'] == training['identity'])
    train_budget = None if model is None else 2*model['rmse']+2*config.maximum_prediction_horizon_s*model['velocity_rmse']
    for cadence in CADENCES_HZ:
        domain_observed = [r for r in observed if r['identity']['cadence_hz'] == cadence]
        independent = [r for r in validations if r['identity']['cadence_hz'] == cadence]
        refs, kind_gates = {}, {}
        learner_coef = config.foot_amplitude_m*np.array([[1., 0., 0., 0.], [-1., 0., 0., 0.]])
        refs['learner_only'] = ExpertRepresentation('learner_only', tuple(map(tuple, learner_coef)), None,
                    'declared task goal; no expert evidence', 'known_task_no_subject', 0., True, 'AVAILABLE_DECLARED_TASK_REFERENCE')
        for kind in ('expert_external', 'expert_neural'):
            reasons = list(identity_errors)+list(training_permission['external' if kind == 'expert_external' else 'neural'])
            if not training_observed['qualified'] or not all(r['qualification']['qualified'] for r in domain_observed):
                reasons.append('OBSERVED_TEACHER_COMPETENCE_FAILED')
            if len(train if kind == 'expert_external' else neural_train) < 40:
                reasons.append('TRAINING_REFERENCE_UNAVAILABLE')
            if not independent:
                reasons.append('INDEPENDENT_RECORDING_VALIDATION_UNAVAILABLE')
            if not all(r['representations'][kind]['qualified'] for r in independent):
                reasons.append('INDEPENDENT_REPRESENTATION_ALLOCATION_FAILED')
            if kind == 'expert_neural':
                if not neural_training_complete:
                    reasons.append('POST_WARMUP_TRAINING_CAPTURE_INCOMPLETE')
                if train_budget is None or train_budget >= config.controller_position_uncertainty_limit_m:
                    reasons.append('PURGED_DECODER_FIT_ALLOCATION_FAILED')
                if not all(r['decoder']['qualified'] for r in independent):
                    reasons.append('INDEPENDENT_NEURAL_DECODER_QUALIFICATION_FAILED')
            reasons = list(dict.fromkeys(reasons))
            coef = coefficients[kind]
            refs[kind] = ExpertRepresentation(kind, tuple(map(tuple, coef)),
                         fit_external if kind == 'expert_external' else fit_neural,
                         'observed external teacher trajectory, nominal training partition' if kind == 'expert_external' else
                         'observed teacher voltage-derived features decoded through measured external labels; nominal training partition',
                         f"synthetic_expert_{training['identity']['subject_seed']}",
                         float(training['identity']['duration_s']), not reasons,
                         'QUALIFIED_OBSERVED_TEACHER_CAPTURE_DOMAIN' if not reasons else '+'.join(reasons))
            kind_gates[kind] = {'qualified': not reasons, 'reasons': reasons,
                                'reference_id': f'{library_id}:{kind}:{cadence:g}Hz'}
        domains[f'{cadence:g}'] = {'cadence_hz': cadence, 'observed_recordings': len(domain_observed),
                                  'independent_validation_recordings': len(independent), 'references': kind_gates}
        references_by_cadence[cadence] = refs
    seconds = sum(float(v['identity']['duration_s']) for v in views)
    resources = {'unique_teacher_recording_seconds': seconds,
                 'training_capture_seconds': float(training['identity']['duration_s']),
                 'independent_validation_seconds': seconds-float(training['identity']['duration_s']),
                 'nominal_recordings': sum(v['identity']['cadence_hz'] == 1. for v in views),
                 'faster_recordings': sum(v['identity']['cadence_hz'] == 1.15 for v in views),
                 'template_training_rows': len(train),
                 'neural_template_training_rows': len(neural_train),
                 'template_partition_scope': 'same external-defined post-warmup chronological cutoff and purge; external fit never requires neural validity',
                 'decoder_training_rows': 0 if model is None else model['training_rows'],
                 'decoder_withheld_rows_same_capture': 0 if model is None else model['heldout_rows'],
                 'same_expert_resource_budget_for_external_and_neural_references': True,
                 'training_capture_has_internal_holdout_not_additional_recording_seconds': True,
                 'distinct_observation_noise_realizations': len(set((v['identity']['external_noise_seed'],
                     v['identity']['voltage_noise_seed']) for v in views)),
                 'paired_noise_ids_across_cadences': True,
                 'independence_scope': '84 s withheld recordings: 36 s nominal new noise, 48 s withheld cadence; cadence performance0 reuses training noise identity'}
    limits = {'teacher_subject_seed': training['identity']['subject_seed'],
              'contact_geometry_seed': training['identity']['contact_geometry_seed'],
              'source_mode': config.source_mode, 'task': 'two-foot kinematic peak proxy',
              'tested_cadences_hz': list(CADENCES_HZ),
              'decoder_transfer_scope': 'independent observation noise and cadence within one fixed synthetic subject/geometry',
              'generator_privilege': training['identity']['privilege'],
              'qualification_scope': 'frozen measured capture model, not aperture-resolved embodiment',
              'source_hold_s': .005, 'source_hold_fidelity_qualified': False,
              'source_hold_limit': 'frozen captures hold the moving source for 5 ms; aperture-resolved fidelity remains unqualified',
              'reference_coordinates': 'external task coordinates; learner-specific response map still required',
              'does_not_establish': ['between-person decoder transfer', 'real spinal signal content',
                                     'expert-neural to novice retained benefit', 'qualified electrical delivery'],
              'private_inputs_excluded': ['expert movement time constant', 'expert theta', 'private evaluator/body truth']}
    qualification = {'identity_errors': identity_errors, 'training_identity': training['identity'],
                     'settings': {'contact_spatial_threshold_m': config.retention_spatial_threshold_m,
                                  'contact_timing_threshold_s': config.retention_timing_threshold_s,
                                  'maximum_prediction_horizon_s': config.maximum_prediction_horizon_s,
                                  'error_allocation_limit_m': config.controller_position_uncertainty_limit_m,
                                  'decoder_allocation': '2*position_RMSE + 2*maximum_horizon*velocity_RMSE',
                                  'template_allocation': '2*complete_trajectory_RMSE', 'neural_z_limit': 5.,
                                  'initial_warmup_s': AcquisitionConfig().warmup_s,
                                  'purged_split_half_width_s': .100,
                                  'threshold_scope': 'inherited task/observer allocations; empirical gates, not probability coverage'},
                     'purged_decoder_fit_error_allocation_m': train_budget,
                     'observed_competence': observed, 'independent_validation': validations, 'domains': domains}
    return TeacherLibrary(library_id, generator, references_by_cadence, qualification, resources, limits, model)
