"""Finite pilot reference, observable policy, clocks and true-delivery coupling."""
from dataclasses import asdict, replace
from unittest.mock import patch
import unittest
import numpy as np

from scci_rh.stage3.dynamic_response import (DynamicResponseModel, DynamicResponseSpec, ProspectiveDose,
                                        ResponsePosition, CompletedDose)
from scci_rh.stage3.sparse_baseline import ZeroFutureInput
from scci_rh.stage3 import motor
from scci_rh.stage3.isolated_pilot import (ARMS, ACTION_DOMAINS, PILOT_CONTEXT_ID, IsolatedPilotSpec, PilotReference,
    reference_from_library, choose_action, aggregate_context, run_trial)


def dynamic():
    kernel = np.zeros((121, 2, 2)); kernel[:, 0, 0] = .010; kernel[:, 1, 1] = .010
    uncertainty = np.zeros_like(kernel); uncertainty[:, 0, 0] = uncertainty[:, 1, 1] = .001
    return DynamicResponseModel('TEST_FINITE_RESPONSE', kernel, uncertainty, np.zeros_like(kernel),
                                DynamicResponseSpec(), {})


def reference(allocation=.003):
    return PilotReference('expert_external', ((.040, 0., 0., 0.), (0., 0., 0., 0.)),
                          allocation, True, 'TEST_INDEPENDENT_REFERENCE', ('a', 'b', 'c'))


def domains(qualified=True):
    return {name: {'qualified': qualified, 'target_residual_allocation_m': [.003, .003],
                  'dynamic_model_id': dynamic().model_id,
                  'target_support_s': 1.1, 'launch_s': 1.}
            for name in ACTION_DOMAINS.values() if name is not None}


def baseline():
    return {'baseline_contract': 'ZERO_FUTURE_COMMAND_BASELINE', 'candidate_future_response_included': False,
            'qualified_for_context': True, 'position_m': [0., 0.], 'total_forecast_allocation_m': [.003, .003],
            'context_id': PILOT_CONTEXT_ID, 'dynamic_model_id': dynamic().model_id,
            'support_s': .950, 'target_support_s': 1.1, 'horizon_s': .150}


def admission_packet():
    return ZeroFutureInput(.975, tuple(ResponsePosition(.875+i*.005, .900+i*.005, (0., 0.))
                                      for i in range(16)), (), 3., 'isolated_nominal')


def library():
    nominal = {'kind': 'expert_external', 'coefficients_m': [[.04, 0., 0., 0.], [0., 0., 0., 0.]],
               'reference_fit_rmse_m': .020, 'training_seconds': 12., 'qualified': True}
    records = [{'identity': {'generator': 'test', 'performance_seed': i, 'cadence_hz': 1.},
                'representations': {'expert_external': {'qualified': True, 'position_error_allocation_m': a}}}
               for i, a in ((2, .003), (3, .004), (4, .0035))]
    return {'references_by_cadence': {'1': {'expert_external': nominal}}, 'qualification': {
        'training_identity': {'performance_seed': 1}, 'independent_validation': records,
        'domains': {'1': {'references': {'expert_external': {'qualified': True, 'reference_id': 'independent'}}}}}}


class PilotPolicyContracts(unittest.TestCase):
    def choose(self, **changes):
        args = dict(baseline=baseline(), packet=admission_packet(), dynamic_model=dynamic(), independent_domains=domains(),
                    reference=reference(), prospective_dose=ProspectiveDose(),
                    now_s=.975, launch_s=1., target_s=1.1)
        args.update(changes)
        return choose_action(**args)

    def test_reference_uses_max_independent_2rmse_and_ignores_training_fit(self):
        value = reference_from_library(library(), 'expert_external')
        self.assertEqual(value.position_error_allocation_m, .004)
        self.assertNotIn('reference_fit_rmse_m', asdict(value))
        changed = library(); changed['references_by_cadence']['1']['expert_external']['reference_fit_rmse_m'] = 0.
        self.assertEqual(value, reference_from_library(changed, 'expert_external'))
        changed['qualification']['independent_validation'][0]['representations']['expert_external']['qualified'] = False
        with self.assertRaises(ValueError): reference_from_library(changed, 'expert_external')

    def test_reference_rejects_training_reuse_and_duplicate_or_excessive_records(self):
        value = library(); value['qualification']['independent_validation'][0]['identity']['performance_seed'] = 1
        with self.assertRaises(ValueError): reference_from_library(value, 'expert_external')
        value = library(); value['qualification']['independent_validation'][0]['identity']['performance_seed'] = 3
        with self.assertRaises(ValueError): reference_from_library(value, 'expert_external')
        value = library(); value['qualification']['independent_validation'][0]['representations']['expert_external']['position_error_allocation_m'] = .026
        with self.assertRaises(ValueError): reference_from_library(value, 'expert_external')

    def test_known_goal_requires_no_expert_training_and_zero_allocation(self):
        value = library()
        value['references_by_cadence']['1']['learner_only'] = {
            'coefficients_m': [[.1, 0., 0., 0.], [-.1, 0., 0., 0.]], 'reference_fit_rmse_m': None,
            'training_seconds': 0., 'qualified': True}
        goal = reference_from_library(value, 'learner_only')
        self.assertEqual(goal.position_error_allocation_m, 0.)
        self.assertEqual(goal.independent_recording_ids, ())
        value['references_by_cadence']['1']['learner_only']['training_seconds'] = 12.
        with self.assertRaises(ValueError): reference_from_library(value, 'learner_only')

    def test_candidate_added_once_with_full_product_and_independent_reference(self):
        value = self.choose()
        self.assertEqual(value['selected_routes'], [1, 0])
        np.testing.assert_allclose(value['selected_position_m'], [.01012, 0.])
        # U_G*u + |G|*U_u + U_G*U_u = .001012+.000740+.000074.
        np.testing.assert_allclose(value['selected_allowance_m'], [.010826, .009])
        self.assertEqual(value['candidate_future_response_counted'], 1)
        self.assertEqual(value['independent_reference_position_allocation_m'], .003)
        self.assertFalse(value['future_measurement_used']); self.assertFalse(value['future_monitor_used'])
        self.assertFalse(value['private_learner_parameters_used'])

    def test_independent_reference_can_close_gate_and_unseen_mixed_routes_stay_unavailable(self):
        value = self.choose(reference=reference(.020))
        self.assertEqual(value['selected_routes'], [0, 0])
        self.assertEqual(sum(row['reason'] == 'MIXED_ROUTE_NOT_INDEPENDENTLY_TESTED' for row in value['candidates']), 2)
        self.assertEqual(len(value['candidates']), 8)
        self.assertTrue(all(not row['eligible'] for row in value['candidates']))

    def test_zero_wins_ties_and_unqualified_domains_do_not_inherit_admission(self):
        at_reference = baseline(); at_reference['position_m'] = (np.asarray(reference().coefficients_m) @ motor.task_basis(1.1)).tolist()
        value = self.choose(baseline=at_reference)
        self.assertEqual(value['selected_routes'], [0, 0])
        self.assertEqual(value['candidate_future_response_counted'], 0)
        self.assertEqual(self.choose(independent_domains=domains(False))['selected_routes'], [0, 0])

    def test_invalid_baseline_reference_and_phase_cannot_be_called_admitted(self):
        for field, value in (('qualified_for_context', False), ('candidate_future_response_included', True),
                             ('total_forecast_allocation_m', [.016, .003])):
            changed = baseline(); changed[field] = value
            with self.assertRaises(ValueError): self.choose(baseline=changed)
        for changes in ({'reference': replace(reference(), qualified=False)}, {'target_s': 1.105},
                        {'now_s': .990}, {'prospective_dose': object()}):
            with self.assertRaises(ValueError): self.choose(**changes)
        with self.assertRaises(ValueError): IsolatedPilotSpec(subject_seed=3)

    def test_no_past_dose_and_exact_packet_context_support_clocks_are_required(self):
        packet = admission_packet()
        past = CompletedDose(.5, .5005, 0, 1, 1., .1, 'VALID')
        for changed in (replace(packet, completed_doses=(past,)), replace(packet, cadence_hz=1.15),
                        replace(packet, now_s=.970), replace(packet, committed_zero_until_s=1.099),
                        replace(packet, history=packet.history[:-1]),
                        replace(packet, history=(replace(packet.history[0], available_s=.899),)+packet.history[1:])):
            with self.assertRaises(ValueError): self.choose(packet=changed)
        for field, value in (('context_id', 'other'), ('dynamic_model_id', 'other'), ('support_s', .945),
                             ('target_support_s', 1.095), ('horizon_s', .145)):
            changed = baseline(); changed[field] = value
            with self.assertRaises(ValueError): self.choose(baseline=changed)
        changed = domains(); changed['moving_single_0_1']['launch_s'] = 1.025
        with self.assertRaises(ValueError): self.choose(independent_domains=changed)

    def test_conservative_context_includes_every_independent_drift_and_failure(self):
        contexts = []
        for i in range(3):
            horizons = [{'horizon_s': .025+j*.005, 'maximum_component_residual_m': .004+i*.001,
                         'empirical_error_allocation_m': .007+i*.001, 'qualified': True,
                         'exclusion_reasons': {'INITIAL_WARMUP': 5},
                         'eligible_domains': [{'support_start_s': .1+i*.005, 'support_end_s': 1.-i*.005,
                                               'observed_past_actions': []}]} for j in range(26)]
            contexts.append({'context': {'recording_id': str(i), 'dynamic_model_id': dynamic().model_id,
                             'family': 'isolated_nominal', 'horizons': horizons}})
        value = aggregate_context(contexts, context_id='all', dynamic_model_id=dynamic().model_id)
        self.assertTrue(value['qualified']); self.assertEqual(len(value['independent_recording_ids']), 3)
        self.assertAlmostEqual(value['horizons'][0]['empirical_error_allocation_m'], .009)
        self.assertEqual(value['horizons'][0]['eligible_domains'],
                         [{'support_start_s': .110, 'support_end_s': .990, 'observed_past_actions': []}])
        contexts[1]['context']['horizons'][0]['qualified'] = False
        self.assertFalse(aggregate_context(contexts, context_id='all', dynamic_model_id=dynamic().model_id)['qualified'])
        contexts[1]['context']['horizons'][0]['qualified'] = True
        contexts[1]['context']['horizons'][0]['exclusion_reasons']['PRIVATE_DRIFT_OUTSIDE_DOMAIN'] = 1
        self.assertFalse(aggregate_context(contexts, context_id='all', dynamic_model_id=dynamic().model_id)['qualified'])


def observed_forecast(model, dynamic_model, packet, horizon_s, **kwargs):
    support = packet.history[-1].support_s
    return {**baseline(), 'position_m': np.asarray(packet.history[-1].position_m),
            'total_forecast_allocation_m': [.010, .010],
            'target_support_s': support+horizon_s, 'support_s': support, 'horizon_s': horizon_s}


class TrialCoupling(unittest.TestCase):
    def trial(self, true_fraction=1., uncertainty=.074, learning=True, heldout=False, arm='expert_external'):
        def delivery(request):
            nominal = request['command_current_A']*request['phase_s']
            return {'true_phase_charge_C': nominal*true_fraction,
                    'delivered_phase_charge_C': nominal*1.012, 'charge_uncertainty_C': nominal*uncertainty,
                    'quality': 'VALID', 'inhibit_next': False}
        with patch('scci_rh.stage3.isolated_pilot.predict_zero_future', side_effect=observed_forecast):
            return run_trial(theta=np.zeros((2, 4)), family='favorable', arm=arm, noise_seed=101,
                baseline_model={}, dynamic_model=dynamic(), context_id=PILOT_CONTEXT_ID, independent_domains=domains(),
                reference=reference(), prospective_dose=ProspectiveDose(), learning=learning,
                heldout=heldout, delivery=delivery)[0]

    def test_whole_frame_actual_charge_body_coupling_and_causal_evidence(self):
        live, zero_charge = self.trial(), self.trial(true_fraction=0.)
        self.assertEqual(live['launched_frames'], 1); self.assertEqual(live['launched_profiles'], 1)
        self.assertEqual(live['launches'][0]['time_s'], 1.)
        self.assertEqual(live['decision']['baseline']['target_support_s'], 1.1)
        self.assertTrue(live['launch_clock_check']['continuation_allowed'])
        self.assertTrue(live['residual_checks'])
        self.assertTrue(all(row['checked_at_s']+1e-12 >= row['observed_available_s'] for row in live['residual_checks']))
        self.assertGreater(np.max(abs(np.asarray(live['private_evaluator_only']['positions_m'])-
                                     zero_charge['private_evaluator_only']['positions_m'])), .001)
        self.assertEqual(live['pending_forecasts_at_end'], 0)

    def test_later_monitor_failure_does_not_undo_actual_earlier_pulse(self):
        value = self.trial(uncertainty=.441)
        self.assertEqual(value['launched_profiles'], 1)
        self.assertEqual(value['continuation_stop_reason'], 'ACTUAL_MONITOR_INTERVAL_EXCEEDS_PROSPECTIVE_ASSUMPTION')
        self.assertTrue(value['actual_monitor_records'][0]['prospective_interval_not_confirmed'])
        self.assertGreaterEqual(value['actual_monitor_records'][0]['processed_at_s'], 1.0005)
        self.assertTrue(value['private_evaluator_only']['true_charge_used_only_by_body'])

    def test_observe_only_and_off_assessments_never_launch(self):
        for changes in ({'arm': 'observe_only'}, {'learning': False}, {'learning': False, 'heldout': True}):
            value = self.trial(**changes)
            self.assertEqual(value['launched_profiles'], 0)
            self.assertEqual(value['launched_frames'], 0)
            self.assertFalse(value['actual_monitor_records'])
            self.assertEqual(value['baseline_only_forecasts_committed'], 0)

    def test_prewarmup_observed_rejection_cancels_pending_launch(self):
        with patch('scci_rh.stage3.isolated_pilot.predict_zero_future', side_effect=ValueError('INDEPENDENT_CONTEXT_FAILED')):
            value = run_trial(theta=np.zeros((2, 4)), family='favorable', arm='expert_external', noise_seed=1,
                baseline_model={}, dynamic_model=dynamic(), context_id=PILOT_CONTEXT_ID, independent_domains=domains(),
                reference=reference(), prospective_dose=ProspectiveDose(), learning=True)[0]
        self.assertEqual(value['launched_profiles'], 0)
        self.assertIn('INDEPENDENT_CONTEXT_FAILED', value['decision']['reason'])


if __name__ == '__main__': unittest.main()
