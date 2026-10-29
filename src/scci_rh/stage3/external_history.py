"""Capacity-matched causal external-history comparator for the motor study.

The learned input consists only of measured external positions.  Offline labels
use the same measured positions and partition-local differentiated labels as the
neural fit.  No simulator state, task phase, or neural feature value enters this
module.  Quality flags select a common offline comparison cohort; they do not
gate the external observer online.
"""
from collections import deque
from dataclasses import dataclass
import hashlib
import numpy as np


HISTORY_ROWS = 16
FEATURE_DIMENSION = 2 * HISTORY_ROWS
SAMPLE_INTERVAL_S = .005
PURGE_HALF_WIDTH_S = .100
RIDGE_PENALTY = .5
TIME_TOLERANCE_S = 1e-9


@dataclass(frozen=True)
class HistoryEstimate:
    """Structural StateEstimate contract; support is the last measured sample."""
    position_m: tuple[float, float]
    velocity_m_per_s: tuple[float, float]
    support_time_s: float
    uncertainty_m: float
    valid: bool
    source: str
    reason: str


def _packet_values(observation, freshness_s):
    now = float(observation.available_time_s)
    support = float(observation.external_measurement_time_s)
    position = np.asarray(observation.external_position_m, dtype=float)
    if (not np.isfinite(now) or not np.isfinite(support)
            or position.shape != (2,) or not np.all(np.isfinite(position))
            or not observation.external_valid or support > now
            or now - support > freshness_s):
        return None
    return now, support, position


def _feature_vector(rows):
    """Newest-to-oldest, two measured coordinates per lag; 0..75 ms support."""
    return np.asarray([position for _, position in reversed(rows)], dtype=float).ravel()


def _time_digest(times):
    # Explicit little-endian bytes make the physical support identity portable.
    return hashlib.sha256(np.asarray(times, dtype="<f8").tobytes()).hexdigest()


def fit_external_history(observations, *, heldout_fraction=.25,
                         external_freshness_s=.050):
    """Fit the 32-input ridge comparator on the neural comparator's cohort.

    Prior valid measured packets populate features, even when their neural
    quality is false. Target packets use neural.valid only to match the existing
    neural calibration cohort. This is offline row selection, not a neural
    information input. Each fit uses one chronological split, a 100 ms purge on
    each side, and differentiated labels formed independently per partition.
    Missing/gapped external histories are excluded and explicitly counted;
    exact row matching is then no longer claimed.
    """
    if (not np.isfinite(heldout_fraction) or not 0 < heldout_fraction < 1
            or not np.isfinite(external_freshness_s) or external_freshness_s <= 0):
        raise ValueError("Invalid split or freshness setting")
    observations = list(observations)
    selected_indices = [i for i, o in enumerate(observations)
                        if o.neural.valid and o.external_valid]
    if len(selected_indices) < 80:
        return None
    split = int(len(selected_indices) * (1 - heldout_fraction))
    cut_time = float(observations[selected_indices[split]].external_measurement_time_s)
    if not np.isfinite(cut_time):
        return None
    history = deque(maxlen=HISTORY_ROWS)
    records = {}
    last_support, last_arrival = -np.inf, -np.inf
    for index, observation in enumerate(observations):
        values = _packet_values(observation, external_freshness_s)
        if values is None:
            history.clear()
            continue
        now, support, position = values
        if support <= last_support or now <= last_arrival:
            history.clear()
            continue
        if history and abs(support-history[-1][0]-SAMPLE_INTERVAL_S) > TIME_TOLERANCE_S:
            history.clear()
        last_support, last_arrival = support, now
        history.append((support, position.copy()))
        if len(history) == HISTORY_ROWS:
            records[index] = _feature_vector(history)
    common = [i for i in selected_indices if i in records]
    times = np.array([observations[i].external_measurement_time_s for i in common])
    x = np.array([records[i] for i in common])
    y = np.array([observations[i].external_position_m for i in common])
    if len(common) < 80:
        return None
    train = np.flatnonzero(times < cut_time-PURGE_HALF_WIDTH_S)
    valid = np.flatnonzero(times > cut_time+PURGE_HALF_WIDTH_S)
    if len(train) < 40 or len(valid) < 20:
        return None
    targets = np.zeros((len(y), 4))
    for partition in (train, valid):
        # Differentiation may see future calibration samples WITHIN its own
        # offline partition; these targets are never constructed online.
        velocity = np.gradient(y[partition], times[partition], axis=0)
        smoothed = np.column_stack([
            np.convolve(velocity[:, j], np.ones(9)/9, mode="same") for j in range(2)])
        targets[partition] = np.column_stack((y[partition], smoothed))
    train, valid = train[4:-4], valid[4:-4]
    mean = x[train].mean(axis=0)
    scale = np.maximum(x[train].std(axis=0), 1e-6)
    z = np.column_stack((np.ones(len(x)), (x-mean)/scale))
    penalty = np.eye(z.shape[1])*RIDGE_PENALTY
    penalty[0, 0] = 1e-9
    weights = np.linalg.solve(z[train].T@z[train]+penalty, z[train].T@targets[train])
    residual = z[valid]@weights-targets[valid]
    return {"mean": mean, "scale": scale, "weights": weights,
            "rmse": float(np.sqrt(np.mean(residual[:, :2]**2))),
            "velocity_rmse": float(np.sqrt(np.mean(residual[:, 2:]**2))),
            "training_rows": len(train), "heldout_rows": len(valid),
            "purged_split_half_width_s": PURGE_HALF_WIDTH_S,
            "split_support_time_s": cut_time,
            "training_support_sha256": _time_digest(times[train]),
            "heldout_support_sha256": _time_digest(times[valid]),
            "calibration_observation_rows": len(observations),
            "matched_eligible_rows": len(selected_indices),
            "history_eligible_rows": len(common),
            "excluded_history_rows": len(selected_indices)-len(common),
            "exact_neural_cohort_matched": len(common) == len(selected_indices),
            "history_rows": HISTORY_ROWS, "history_duration_s": .075,
            "feature_dimension": FEATURE_DIMENSION, "output_dimension": 4,
            "coefficient_count": (FEATURE_DIMENSION+1)*4,
            "ridge_penalty": RIDGE_PENALTY,
            "scale_floor_m": 1e-6,
            "feature_order": "newest-to-oldest 16 measured external position pairs",
            "labels": "same-learner external position + offline differentiated external position",
            "cohort": "same neural-qualified offline target rows; prior measured external history only",
            "online_permissions": "measured external positions, support/arrival timestamps, external validity"}


class CausalExternalHistoryDecoder:
    """Same-support linear observer plus a 32-input learned history correction."""
    def __init__(self, config, model):
        self.config = config
        self.model = model
        self._external = deque(maxlen=HISTORY_ROWS)
        self._last_support = -np.inf
        self._last_arrival = -np.inf

    def _invalid(self, support, reason):
        self._external.clear()
        return HistoryEstimate((0., 0.), (0., 0.), float(support), 1., False,
                               "NONE", reason)

    def estimate(self, observation):
        c = self.config
        values = _packet_values(observation, c.external_freshness_s)
        if values is None:
            return self._invalid(observation.external_measurement_time_s,
                                 "EXTERNAL_STALE_OR_INVALID")
        now, support, external = values
        if support <= self._last_support:
            return self._invalid(support, "EXTERNAL_REPEATED_OR_NONMONOTONIC")
        if now <= self._last_arrival:
            return self._invalid(support, "EXTERNAL_ARRIVAL_NONMONOTONIC")
        contiguous = (not self._external
                      or abs(support-self._external[-1][0]-SAMPLE_INTERVAL_S) <= TIME_TOLERANCE_S)
        self._last_support, self._last_arrival = support, now
        if not contiguous:
            self._external.clear()
        self._external.append((support, external.copy()))
        if len(self._external) < HISTORY_ROWS:
            return HistoryEstimate(tuple(external), (0., 0.), support, 1., False,
                                   "EXTERNAL_HISTORY", "DECODER_HISTORY_WARMUP")
        recent = list(self._external)[-9:]
        times = np.array([r[0] for r in recent])
        positions = np.array([r[1] for r in recent])
        centered = times-times.mean()
        velocity = centered@positions/np.sum(centered**2)
        position = positions.mean(axis=0)+velocity*(support-times.mean())
        uncertainty = c.external_noise_m*2+.005
        source, reason = "EXTERNAL_LINEAR_HISTORY", "EXTERNAL_HISTORY_MODEL_UNAVAILABLE"
        m = self.model
        if m is not None:
            z = (_feature_vector(self._external)-m["mean"])/m["scale"]
            budget = 2*m["rmse"]+2*c.maximum_prediction_horizon_s*m["velocity_rmse"]
            if (np.all(np.isfinite(z)) and np.max(np.abs(z)) <= 5.
                    and np.isfinite(budget) and budget >= 0
                    and budget < c.controller_position_uncertainty_limit_m):
                predicted = np.r_[1., z]@m["weights"]
                if np.all(np.isfinite(predicted)):
                    w = float(np.clip(uncertainty**2/(uncertainty**2+m["rmse"]**2+1e-8), 0., .85))
                    position = (1-w)*position+w*predicted[:2]
                    velocity = (1-w)*velocity+w*predicted[2:]
                    uncertainty = max(float(budget), .003)
                    source, reason = "LEARNED_EXTERNAL_HISTORY", "CALIBRATED_EXTERNAL_HISTORY"
                else:
                    reason = "EXTERNAL_HISTORY_NONFINITE_MODEL_OUTPUT"
            else:
                reason = "EXTERNAL_HISTORY_OUT_OF_CALIBRATION_OR_RESIDUAL_LIMIT"
        return HistoryEstimate(tuple(float(x) for x in position),
                               tuple(float(x) for x in velocity), support, uncertainty,
                               uncertainty <= c.controller_position_uncertainty_limit_m,
                               source, reason)
