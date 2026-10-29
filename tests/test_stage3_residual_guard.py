import unittest
from dataclasses import replace
from scci_rh.stage3.assisted_prediction import MeasuredPosition
from scci_rh.stage3.residual_guard import DelayedResidualGuard, PredictionCommit


class DelayedResidualTests(unittest.TestCase):
    def forecast(self):
        return PredictionCommit(.100, .200, (.010, -.010), (.005, .005), 'frozen_model', 'finite_context')

    def measurement(self, support=.200, position=(.011, -.009)):
        return MeasuredPosition(support, support+.025, position)

    def test_forecast_cannot_be_scored_before_its_measured_target_arrives(self):
        guard = DelayedResidualGuard(); guard.commit(self.forecast())
        result = guard.observe(self.measurement(.195), now_s=.220)
        self.assertEqual(result['checked_forecasts'], 0)
        self.assertEqual(len(guard.pending), 1)
        result = guard.observe(self.measurement(), now_s=.225)
        self.assertEqual(result['checked_forecasts'], 1)
        self.assertTrue(guard.scored[0]['passed']); self.assertFalse(guard.pending)

    def test_observed_failure_latches_cancels_and_cannot_undo_prior_delivery(self):
        guard = DelayedResidualGuard(); guard.commit(self.forecast())
        guard.commit(replace(self.forecast(), target_support_s=.250))
        result = guard.observe(self.measurement(position=(.040, -.010)), now_s=.225)
        self.assertFalse(result['continuation_allowed'])
        self.assertEqual(result['cancelled_forecasts'], 2)
        self.assertEqual(result['physical_pulses'], 0)
        self.assertFalse(guard.commit(replace(self.forecast(), created_s=.230, target_support_s=.300))['continuation_allowed'])
        self.assertFalse(guard.observe(self.measurement(.300), now_s=.325)['continuation_allowed'])

    def test_future_target_measurement_is_not_online_evidence(self):
        guard = DelayedResidualGuard(); guard.commit(self.forecast())
        self.assertFalse(guard.observe(self.measurement(), now_s=.220)['continuation_allowed'])
        self.assertFalse(guard.scored)

    def test_missing_target_rejects_without_interpolating_later_truth(self):
        guard = DelayedResidualGuard(); guard.commit(self.forecast())
        result = guard.observe(self.measurement(.205), now_s=.230)
        self.assertEqual(result['reason'], 'COMMITTED_TARGET_MEASUREMENT_MISSING')

    def test_total_sensor_loss_expires_on_policy_clock_without_a_new_observation(self):
        guard = DelayedResidualGuard(); guard.commit(self.forecast())
        self.assertTrue(guard.check(now_s=.249)['continuation_allowed'])
        result = guard.check(now_s=.251)
        self.assertEqual(result['reason'], 'COMMITTED_TARGET_ARRIVAL_EXPIRED')
        self.assertFalse(result['continuation_allowed']); self.assertFalse(guard.pending)
        self.assertFalse(guard.commit(replace(self.forecast(), created_s=.260, target_support_s=.300))['continuation_allowed'])

    def test_observation_stream_and_replayed_policy_clock_expire_without_pending_target(self):
        guard = DelayedResidualGuard()
        guard.observe(self.measurement(.100), now_s=.125)
        self.assertEqual(guard.check(now_s=.151)['reason'], 'OBSERVATION_STREAM_EXPIRED')
        guard = DelayedResidualGuard(); guard.check(now_s=.200)
        self.assertEqual(guard.check(now_s=.199)['reason'], 'INVALID_OR_REPLAYED_POLICY_CLOCK')

    def test_replayed_stale_and_invalid_measurements_stop_continuation(self):
        guard = DelayedResidualGuard(); row = self.measurement(.100)
        self.assertTrue(guard.observe(row, now_s=.125)['continuation_allowed'])
        self.assertFalse(guard.observe(row, now_s=.130)['continuation_allowed'])
        for row, now in ((self.measurement(), .300), (replace(self.measurement(), valid=False), .225)):
            self.assertFalse(DelayedResidualGuard().observe(row, now_s=now)['continuation_allowed'])

    def test_invalid_duplicate_and_excess_commitments_are_rejected(self):
        guard = DelayedResidualGuard(capacity=1)
        for row in (replace(self.forecast(), target_support_s=.100),
                    replace(self.forecast(), allowance_m=(-.001, .001)),
                    replace(self.forecast(), position_m=(float('nan'), 0.)),
                    replace(self.forecast(), model_id='')):
            with self.assertRaises(ValueError): guard.commit(row)
        guard.commit(self.forecast())
        with self.assertRaises(ValueError): guard.commit(self.forecast())
        self.assertFalse(guard.commit(replace(self.forecast(), target_support_s=.300))['continuation_allowed'])


if __name__ == '__main__': unittest.main()
