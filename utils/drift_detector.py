"""
Concept Drift Detector for FL-NIDS.

Monitors data distribution shifts over FL rounds to detect when the
model may need retraining. Uses Page-Hinkley test and KL divergence
to detect both gradual and sudden drift.

Usage:
    detector = DriftDetector(window_size=5, threshold=0.05)
    detector.update(round_num=1, features_batch=np.array(...))
    result = detector.detect()
    # result = {drift_detected: bool, drift_score: float, drift_type: str}
"""

import numpy as np
from collections import deque


class DriftDetector:
    """Sliding-window concept drift detector using statistical tests."""

    def __init__(self, window_size=5, threshold=0.05, sensitivity=0.01):
        """
        Args:
            window_size: Number of rounds to keep in sliding window
            threshold: KL divergence threshold to trigger drift alarm
            sensitivity: Page-Hinkley sensitivity parameter (delta)
        """
        self.window_size = window_size
        self.threshold = threshold
        self.sensitivity = sensitivity

        # Store per-round feature distribution summaries
        self._history = deque(maxlen=window_size * 2)
        self._round_stats = {}

        # Page-Hinkley state
        self._ph_sum = 0.0
        self._ph_min = 0.0
        self._ph_count = 0
        self._ph_mean = 0.0
        self._ph_threshold = 50.0  # PH alarm threshold

        # Results
        self._last_result = {
            "drift_detected": False,
            "drift_score": 0.0,
            "drift_type": "none",
            "details": {},
        }

    def update(self, round_num, features_batch):
        """
        Feed a batch of feature vectors for a given round.

        Args:
            round_num: FL round number
            features_batch: numpy array of shape (n_samples, n_features)
        """
        features_batch = np.asarray(features_batch, dtype=float)
        if features_batch.ndim == 1:
            features_batch = features_batch.reshape(1, -1)

        # Compute distribution summary: mean and variance per feature
        summary = {
            "round": round_num,
            "mean": np.mean(features_batch, axis=0),
            "var": np.var(features_batch, axis=0) + 1e-10,
            "n_samples": len(features_batch),
        }

        self._history.append(summary)
        self._round_stats[round_num] = summary

        # Update Page-Hinkley with mean of feature means
        overall_mean = float(np.mean(summary["mean"]))
        self._ph_count += 1
        self._ph_mean += (overall_mean - self._ph_mean) / self._ph_count
        self._ph_sum += overall_mean - self._ph_mean - self.sensitivity
        self._ph_min = min(self._ph_min, self._ph_sum)

    def detect(self):
        """
        Run drift detection on accumulated data.

        Returns:
            Dict with:
                drift_detected: bool
                drift_score: float (0-1 normalized)
                drift_type: 'none' | 'gradual' | 'sudden'
                details: dict with KL divergence and PH test values
        """
        if len(self._history) < 2:
            return self._last_result

        # --- KL Divergence between recent and older windows ---
        mid = len(self._history) // 2
        old_window = list(self._history)[:mid]
        new_window = list(self._history)[mid:]

        kl_div = self._compute_kl_divergence(old_window, new_window)

        # --- Page-Hinkley Test ---
        ph_value = self._ph_sum - self._ph_min
        ph_alarm = ph_value > self._ph_threshold

        # --- Decision ---
        kl_alarm = kl_div > self.threshold

        if kl_alarm and ph_alarm:
            drift_type = "sudden"
            drift_detected = True
        elif kl_alarm or ph_alarm:
            drift_type = "gradual"
            drift_detected = True
        else:
            drift_type = "none"
            drift_detected = False

        # Normalize drift score to 0-1
        drift_score = min(1.0, kl_div / max(self.threshold * 3, 0.001))

        self._last_result = {
            "drift_detected": drift_detected,
            "drift_score": round(drift_score, 4),
            "drift_type": drift_type,
            "details": {
                "kl_divergence": round(kl_div, 6),
                "kl_threshold": self.threshold,
                "page_hinkley_value": round(ph_value, 4),
                "page_hinkley_alarm": ph_alarm,
                "num_rounds_tracked": len(self._history),
            },
        }
        return self._last_result

    def _compute_kl_divergence(self, old_window, new_window):
        """
        Compute average KL divergence between feature distributions
        from two time windows using Gaussian approximation.
        """
        # Aggregate means and variances
        old_means = np.mean([s["mean"] for s in old_window], axis=0)
        old_vars = np.mean([s["var"] for s in old_window], axis=0)
        new_means = np.mean([s["mean"] for s in new_window], axis=0)
        new_vars = np.mean([s["var"] for s in new_window], axis=0)

        # KL(P || Q) for Gaussians: 0.5 * (log(var_q/var_p) + var_p/var_q
        #                             + (mu_p - mu_q)^2 / var_q - 1)
        var_ratio = new_vars / old_vars
        kl_per_feature = 0.5 * (
            np.log(var_ratio + 1e-10)
            + old_vars / new_vars
            + (old_means - new_means) ** 2 / new_vars
            - 1
        )

        # Average across features, clamp negatives from numerical noise
        kl_div = float(np.mean(np.maximum(kl_per_feature, 0)))
        return kl_div

    def get_history(self):
        """Return drift detection history for dashboard display."""
        return {
            "rounds_tracked": len(self._history),
            "window_size": self.window_size,
            "last_result": self._last_result,
            "round_means": [
                {
                    "round": s["round"],
                    "feature_mean": round(float(np.mean(s["mean"])), 4),
                    "feature_var": round(float(np.mean(s["var"])), 4),
                }
                for s in self._history
            ],
        }

    def reset(self):
        """Reset all state."""
        self._history.clear()
        self._round_stats.clear()
        self._ph_sum = 0.0
        self._ph_min = 0.0
        self._ph_count = 0
        self._ph_mean = 0.0
        self._last_result = {
            "drift_detected": False,
            "drift_score": 0.0,
            "drift_type": "none",
            "details": {},
        }
