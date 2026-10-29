"""Causal observable/dose and conditional qualification contracts."""
from dataclasses import asdict, fields, replace
from itertools import product
import unittest
import numpy as np

from scci_rh.stage3.assisted_prediction import (PredictionSpec, KnownInstruction,
    MeasuredPosition, ObservedDose, PlannedFrame, PredictionInput, feature_vector,
    packet_at, predict_assisted, validate_assisted_recording, correction_uncertainty,
    coupling_admission)
from scci_rh.stage3.motor import LearnerMap, ExpertRepresentation


def packet(now=.600):
    history = tuple(MeasuredPosition(now-.025-(15-i)*.005, now-(15-i)*.005, (0., 0.)) for i in range(16))
    plan = tuple(PlannedFrame(i*.025, (0, 0)) for i in range(40))
    return PredictionInput(now, history, (), plan, KnownInstruction())


def model():
    return {'training_recording_ids': ['trainingA', 'trainingB'], 'context_validation': {},
        'models': [{'horizon_s': i*.005, 'mean': np.zeros(226), 'scale': np.ones(226),
                    'weights': np.zeros((227, 2)), 'qualified': True,
                    'empirical_maximum_component_residual_m': 0.,
                    'empirical_error_allocation_m': .003} for i in range(31)]}


def recording(name='new_independent', offset=0.):
    positions = [MeasuredPosition(i*.005, i*.005+.025, (offset, -offset)) for i in range(120)]
    return {'recording_id': name, 'measurements': positions, 'observed_dose': (),
            'planned_frames': tuple(PlannedFrame(i*.025, (0, 0)) for i in range(40)),
            'instruction': KnownInstruction(), 'schedule_identity': 'TEST_FIXED_NO_OUTPUT'}


class ObservableContracts(unittest.TestCase):
    def test_future_monitor_evidence_and_premature_profile_completion_rejected(self):
        for dose in (ObservedDose(.600, .6005, 0, 1, 1.012, .074, 'ASSUMED_NOMINAL'),
                     ObservedDose(.575, .5751, 0, 1, 1.012, .074, 'ASSUMED_NOMINAL')):
            with self.assertRaises(ValueError): feature_vector(replace(packet(), observed_dose=(dose,)), .150)

    def test_future_plan_is_an_assumption_and_never_a_measured_dose(self):
        p = packet()
        plan = tuple(replace(f, signed_routes=(1, -1)) if abs(f.frame_time_s-.625)<1e-9 else f for f in p.planned_frames)
        features, intervals, witness = feature_vector(replace(p, planned_frames=plan), .100)
        self.assertEqual(witness['observed_dose_cells'], 0)
        self.assertGreater(witness['prospective_assumed_dose_cells'], 0)
        self.assertIn(1.012, features); self.assertIn(-1.012, features)
        self.assertIn(.074, intervals)
        self.assertEqual(witness['prospective_qualification'], 'UNQUALIFIED_NOMINAL_ASSUMPTION')
        # A later planned command cannot affect an earlier target's features.
        early, _, _ = feature_vector(replace(p, planned_frames=plan), .025)
        original, _, _ = feature_vector(p, .025)
        np.testing.assert_array_equal(early, original)

    def test_past_nonzero_command_needs_available_route_consistent_monitor(self):
        p = packet(); plan = tuple(replace(f, signed_routes=(1, 0)) if abs(f.frame_time_s-.550)<1e-9 else f for f in p.planned_frames)
        p = replace(p, planned_frames=plan)
        with self.assertRaises(ValueError): feature_vector(p, .100)
        dose = ObservedDose(.550, .5505, 0, 1, 1.012, .074, 'ASSUMED_NOMINAL')
        _, _, witness = feature_vector(replace(p, observed_dose=(dose,)), .100)
        self.assertGreater(witness['observed_dose_cells'], 0)
        with self.assertRaises(ValueError): feature_vector(replace(p, observed_dose=(replace(dose, route_sign=-1),)), .100)

    def test_stale_replayed_future_and_invalid_positions_rejected(self):
        p = packet()
        bad = (replace(p, now_s=.7),
               replace(p, history=p.history[:-1]+(replace(p.history[-1], support_s=p.history[-2].support_s),)),
               replace(p, history=p.history[:-1]+(replace(p.history[-1], available_s=.601),)),
               replace(p, history=p.history[:-1]+(replace(p.history[-1], valid=False),)),
               replace(p, history=p.history[:-1]+(replace(p.history[-1], position_m=(np.nan, 0.)),)))
        for value in bad:
            with self.assertRaises(ValueError): feature_vector(value, .150)

    def test_frame_plan_contract_and_frozen_horizon_limits(self):
        p = packet()
        for frame in (PlannedFrame(.625, (.5, 0)), PlannedFrame(.626, (1, 0)),
                      PlannedFrame(.625, (1, 0), .601), PlannedFrame(.625, (1, 0), qualification='MEASURED_FUTURE')):
            with self.assertRaises(ValueError): feature_vector(replace(p, planned_frames=p.planned_frames+(frame,)), .100)
        for horizon in (-.005, .151, .155):
            with self.assertRaises(ValueError): feature_vector(p, horizon)
        with self.assertRaises(ValueError): PredictionSpec(maximum_horizon_s=.200)

    def test_no_hidden_body_or_future_label_contract_and_invalid_neural_remains_invalid(self):
        permitted = {f.name for f in fields(PredictionInput)}
        self.assertEqual(permitted, {'now_s', 'history', 'observed_dose', 'planned_frames', 'instruction'})
        with self.assertRaises(TypeError): PredictionInput(**{**packet().__dict__, 'true_phase': 0.})
        _, _, witness = feature_vector(packet(), .150)
        self.assertFalse(witness['neural_packet_used_by_forecaster'])
        self.assertFalse(witness['latest_neural_packet_valid'])


class IndependentQualification(unittest.TestCase):
    def test_complete_withheld_recording_checks_all31_horizons_and_no_training_reuse(self):
        fitted = model(); r = recording()
        checked = validate_assisted_recording(fitted, r)
        self.assertTrue(checked['context']['qualified'])
        self.assertEqual(len(checked['context']['horizons']), 31)
        self.assertTrue(all(h['evaluated_rows'] > 0 for h in checked['context']['horizons']))
        prediction = predict_assisted(fitted, packet_at(r, 30), .150, context_id=r['recording_id'])
        self.assertTrue(prediction['qualified_for_context'])
        with self.assertRaises(ValueError): validate_assisted_recording(fitted, recording('trainingA'))
        with self.assertRaises(ValueError): predict_assisted(fitted, packet_at(r, 30), .150, context_id='unseen_feedback')

    def test_changed_context_failure_and_future_labels_never_enter_online_packet(self):
        fitted = model(); r = recording(offset=.040)
        checked = validate_assisted_recording(fitted, r)
        self.assertFalse(checked['context']['qualified'])
        self.assertTrue(all(not h['qualified'] for h in checked['context']['horizons']))
        before = packet_at(r, 30)
        changed = dict(r); changed['measurements'] = list(r['measurements'])
        changed['measurements'][60] = replace(changed['measurements'][60], position_m=(9., -9.))
        after = packet_at(changed, 30)
        self.assertEqual(before, after)
        with self.assertRaises(ValueError): predict_assisted(fitted, before, .150, context_id=r['recording_id'])

    def test_context_name_cannot_authorize_a_different_instruction_or_plan(self):
        fitted = model(); r = recording(); validate_assisted_recording(fitted, r)
        before = packet_at(r, 30)
        with self.assertRaises(ValueError):
            predict_assisted(fitted, replace(before, instruction=KnownInstruction(1.15)), .150,
                             context_id=r['recording_id'])
        changed_plan = tuple(replace(f, signed_routes=(1, 0)) if abs(f.frame_time_s-.200)<1e-9 else f
                             for f in before.planned_frames)
        with self.assertRaises(ValueError):
            predict_assisted(fitted, replace(before, planned_frames=changed_plan), .150,
                             context_id=r['recording_id'])

    def test_joint_gain_dose_uncertainty_encloses_independent_interval_corners(self):
        g = np.array([[.060, .010], [-.010, .050]])
        ug = np.array([[.002, .001], [.003, .002]])
        u = np.array([.8, -.6]); uu = np.array([.074, .050])
        bound = correction_uncertainty(g, ug, u, uu, 0.)
        for signs in product((-1., 1.), repeat=6):
            changed = (g+ug*np.array(signs[:4]).reshape(2, 2))@(u+uu*np.array(signs[4:]))
            self.assertTrue(np.all(np.abs(changed-g@u) <= bound+1e-15))
        np.testing.assert_allclose(bound, ug@np.abs(u)+np.abs(g)@uu+ug@uu)

    def test_live_monitor_uncertainty_can_reject_unchanged_in_domain_dose_mean(self):
        p = packet()
        plan = tuple(replace(f, signed_routes=(1, 0)) if abs(f.frame_time_s-.550)<1e-9 else f
                     for f in p.planned_frames)
        dose = ObservedDose(.550, .5505, 0, 1, 1.012, .074, 'ASSUMED_NOMINAL')
        p = replace(p, planned_frames=plan, observed_dose=(dose,))
        fitted = model(); horizon_index = 20
        m = fitted['models'][horizon_index]
        # Feature154 is source0's held dose25ms before the latest support.
        m['weights'][155, 0] = .010
        m['empirical_maximum_component_residual_m'] = .001
        m['empirical_error_allocation_m'] = .005
        horizons = [{'qualified': True, 'maximum_component_residual_m': .001,
                     'empirical_error_allocation_m': .005} for _ in range(31)]
        context = {'qualified': True, 'horizons': horizons,
                   'instruction': asdict(p.instruction),
                   'validated_planned_frames': [asdict(f) for f in p.planned_frames],
                   'validated_support_interval_s': [.575, .575]}
        fitted['context_validation']['fixed_test_context'] = context
        ordinary = predict_assisted(fitted, p, .100, context_id='fixed_test_context')
        # max(5mm saved gate,4mm residual/label +0.74mm current projection)
        # remains5mm: the saved1mm projection is not added a second time.
        np.testing.assert_allclose(ordinary['live_forecast_error_allocation_m'], (.005, .005))
        larger = replace(p, observed_dose=(replace(dose, uncertainty_fraction=2.),))
        np.testing.assert_array_equal(feature_vector(p, .100)[0], feature_vector(larger, .100)[0])
        diagnostic = predict_assisted(fitted, larger, .100, require_qualified=False)
        np.testing.assert_array_equal(diagnostic['position_m'], ordinary['position_m'])
        self.assertAlmostEqual(diagnostic['dose_input_interval_projection_m'][0], .020)
        self.assertFalse(diagnostic['qualified_for_context'])
        self.assertNotIn('live_forecast_error_allocation_m', diagnostic)
        with self.assertRaisesRegex(ValueError, 'Current dose-input interval'):
            predict_assisted(fitted, larger, .100, context_id='fixed_test_context')
        # Independent-context residuals must not be replaced by a smaller
        # training residual when forming the qualified runtime allowance.
        context['horizons'][horizon_index] = {'qualified': True,
            'maximum_component_residual_m': .003, 'empirical_error_allocation_m': .007}
        independent = predict_assisted(fitted, p, .100, context_id='fixed_test_context')
        np.testing.assert_allclose(independent['live_forecast_error_allocation_m'], (.007, .007))

    def test_static_map_and_empirical_predictor_cannot_silently_qualify_dynamic_feedback(self):
        fitted = model(); validate_assisted_recording(fitted, recording())
        response = LearnerMap(((.06, 0.), (0., .06)), ((.002, 0.), (0., .002)),
                              .0675, .005, True, (), 200, 1., .001, .001)
        reference = ExpertRepresentation('expert_neural', ((.1, 0., 0., 0.), (-.1, 0., 0., 0.)), .001,
                                         'observed qualified teacher test fixture', 'independent_subject', 12.)
        audit = coupling_admission(fitted, 'new_independent', response, reference)
        self.assertFalse(audit['admitted'])
        self.assertIn('DYNAMIC_EXECUTION_RESPONSE_UNQUALIFIED', audit['reasons'])
        self.assertEqual(audit['pulse_count'], 0)
        actual = replace(response, gain_uncertainty_m=((.08, 0.), (0., .08)), qualified=False)
        audit = coupling_admission(fitted, 'new_independent', actual, reference)
        self.assertIn('UNQUALIFIED_OBSERVED_AUTHORITY', audit['reasons'])


if __name__ == '__main__': unittest.main()
