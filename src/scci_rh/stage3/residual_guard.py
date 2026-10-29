"""Causal delayed-residual latch for a future body-coupled digital policy.

This component supplies no prediction/domain qualification and launches nothing.
A violated observed residual stops continuation; it cannot undo an earlier dose.
"""
from dataclasses import dataclass
import numpy as np
from .assisted_prediction import MeasuredPosition


@dataclass(frozen=True)
class PredictionCommit:
    created_s: float
    target_support_s: float
    position_m: tuple[float, float]
    allowance_m: tuple[float, float]
    model_id: str
    context_id: str


class DelayedResidualGuard:
    def __init__(self, *, maximum_support_age_s=.050, capacity=64):
        if (not np.isfinite(maximum_support_age_s) or maximum_support_age_s <= 0
                or isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1):
            raise ValueError('Finite positive observation age and integer capacity required')
        self.maximum_support_age_s, self.capacity = maximum_support_age_s, capacity
        self.pending = []
        self.latched_reason = None
        self.last_support_s = self.last_arrival_s = -np.inf
        self.last_clock_s = -np.inf
        self.scored = []

    @property
    def continuation_allowed(self):
        return self.latched_reason is None

    def _stop(self, reason):
        if self.latched_reason is None: self.latched_reason = reason
        cancelled = len(self.pending)
        self.pending.clear()
        return {'continuation_allowed': False, 'reason': self.latched_reason,
                'cancelled_forecasts': cancelled, 'physical_pulses': 0}

    def check(self, *, now_s):
        """Poll on the policy clock before continuation, even without input.

        ``continuation_allowed`` is cached latch state. A caller must invoke
        this timed check before each prospective continuation/launch decision.
        """
        if not self.continuation_allowed: return self._stop(self.latched_reason)
        if not np.isfinite(now_s) or now_s < self.last_clock_s-1e-12:
            return self._stop('INVALID_OR_REPLAYED_POLICY_CLOCK')
        self.last_clock_s = now_s
        if any(now_s > f.target_support_s+self.maximum_support_age_s+1e-12 for f in self.pending):
            return self._stop('COMMITTED_TARGET_ARRIVAL_EXPIRED')
        if np.isfinite(self.last_support_s) and now_s-self.last_support_s > self.maximum_support_age_s+1e-12:
            return self._stop('OBSERVATION_STREAM_EXPIRED')
        return {'continuation_allowed': True, 'reason': 'TIMED_CONTINUATION_CHECK_PASSED', 'physical_pulses': 0}

    def commit(self, forecast: PredictionCommit):
        if not isinstance(forecast, PredictionCommit):
            raise ValueError('Sanitized forecast commitment required')
        values = np.r_[forecast.created_s, forecast.target_support_s,
                       forecast.position_m, forecast.allowance_m]
        if (np.asarray(forecast.position_m).shape != (2,) or np.asarray(forecast.allowance_m).shape != (2,)
                or not np.all(np.isfinite(values)) or np.any(np.asarray(forecast.allowance_m) < 0)
                or forecast.target_support_s <= forecast.created_s
                or forecast.created_s < self.last_arrival_s-1e-12
                or not forecast.model_id or not forecast.context_id):
            raise ValueError('Finite future target, nonnegative allowance and model/context identity required')
        if not self.continuation_allowed: return self._stop(self.latched_reason)
        timed = self.check(now_s=forecast.created_s)
        if not timed['continuation_allowed']: return timed
        if forecast in self.pending: raise ValueError('Duplicate forecast commitment')
        if len(self.pending) >= self.capacity: return self._stop('PENDING_CAPACITY_EXCEEDED')
        self.pending.append(forecast)
        self.pending.sort(key=lambda f: (f.target_support_s, f.created_s))
        return {'continuation_allowed': True, 'reason': 'WAIT_FOR_OBSERVED_TARGET', 'physical_pulses': 0}

    def observe(self, measurement: MeasuredPosition, *, now_s: float):
        if not self.continuation_allowed: return self._stop(self.latched_reason)
        timed = self.check(now_s=now_s)
        if not timed['continuation_allowed']: return timed
        if not isinstance(measurement, MeasuredPosition): return self._stop('INVALID_MEASUREMENT_CONTRACT')
        values = np.r_[now_s, measurement.support_s, measurement.available_s, measurement.position_m]
        if (np.asarray(measurement.position_m).shape != (2,) or not np.all(np.isfinite(values))
                or not measurement.valid or measurement.support_s > measurement.available_s
                or measurement.available_s > now_s+1e-12
                or now_s-measurement.support_s > self.maximum_support_age_s+1e-12
                or measurement.support_s <= self.last_support_s
                or measurement.available_s <= self.last_arrival_s):
            return self._stop('INVALID_STALE_REPLAYED_OR_FUTURE_MEASUREMENT')
        self.last_support_s, self.last_arrival_s = measurement.support_s, measurement.available_s
        matched = []
        for forecast in self.pending:
            if forecast.target_support_s < measurement.support_s-1e-9:
                return self._stop('COMMITTED_TARGET_MEASUREMENT_MISSING')
            if abs(forecast.target_support_s-measurement.support_s) > 1e-9: continue
            residual = np.abs(np.asarray(forecast.position_m)-measurement.position_m)
            passed = bool(np.all(residual <= np.asarray(forecast.allowance_m)+1e-12))
            witness = {'created_s': forecast.created_s, 'target_support_s': forecast.target_support_s,
                'observed_support_s': measurement.support_s, 'observed_available_s': measurement.available_s,
                'checked_at_s': now_s, 'model_id': forecast.model_id, 'context_id': forecast.context_id,
                'absolute_residual_m': residual.tolist(), 'allowance_m': list(forecast.allowance_m),
                'passed': passed}
            self.scored.append(witness); matched.append(forecast)
            if not passed: return self._stop('OBSERVED_RESIDUAL_ALLOCATION_EXCEEDED')
        self.pending = [f for f in self.pending if f not in matched]
        return {'continuation_allowed': True, 'reason': 'OBSERVED_RESIDUAL_PASSED' if matched else 'WAIT_FOR_OBSERVED_TARGET',
                'checked_forecasts': len(matched), 'physical_pulses': 0}
