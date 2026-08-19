"""
Model Poisoning Detector for FL-NIDS.

Detects clients sending intentionally corrupted model updates using
spectral analysis, norm-based outlier detection, and activation clustering.

Usage:
    detector = PoisonDetector(sensitivity=0.8)
    results = detector.analyze_updates(client_weights, global_weights)
    # results = {client_id: {poisoned: bool, score: float, method: str}}
"""

import numpy as np


def _flatten(weights_list):
    """Flatten a list of numpy arrays into a single 1D vector."""
    return np.concatenate([w.flatten() for w in weights_list])


class PoisonDetector:
    """Detect model poisoning attacks from client weight updates."""

    def __init__(self, sensitivity=0.8, z_threshold=2.5):
        """
        Args:
            sensitivity: Detection sensitivity 0-1 (higher = more aggressive)
            z_threshold: Z-score threshold for norm outlier detection
        """
        self.sensitivity = sensitivity
        self.z_threshold = z_threshold * (2.0 - sensitivity)  # Adjusted by sensitivity
        self._history = []

    def analyze_updates(self, client_weights, global_weights):
        """
        Analyze client weight updates for poisoning.

        Args:
            client_weights: Dict of {client_id: [list of numpy arrays]}
            global_weights: List of numpy arrays (global model params)

        Returns:
            Dict of {client_id: {poisoned: bool, score: float, methods_triggered: list,
                                  norm_deviation: float, spectral_score: float}}
        """
        if not client_weights:
            return {}

        global_flat = _flatten(global_weights)

        # Compute update deltas (client - global)
        deltas = {}
        for cid, weights in client_weights.items():
            client_flat = _flatten(weights)
            deltas[cid] = client_flat - global_flat

        # --- Method 1: Norm-based outlier detection ---
        norm_results = self._norm_outlier_detection(deltas)

        # --- Method 2: Spectral analysis ---
        spectral_results = self._spectral_analysis(deltas)

        # --- Method 3: Direction deviation ---
        direction_results = self._direction_deviation(deltas)

        # Combine results
        results = {}
        for cid in client_weights:
            methods_triggered = []
            scores = []

            if norm_results.get(cid, {}).get("outlier", False):
                methods_triggered.append("norm_outlier")
                scores.append(norm_results[cid]["score"])

            if spectral_results.get(cid, {}).get("outlier", False):
                methods_triggered.append("spectral")
                scores.append(spectral_results[cid]["score"])

            if direction_results.get(cid, {}).get("outlier", False):
                methods_triggered.append("direction_deviation")
                scores.append(direction_results[cid]["score"])

            # Poisoned if ANY method triggers
            poisoned = len(methods_triggered) > 0
            combined_score = max(scores) if scores else 0.0

            results[cid] = {
                "poisoned": poisoned,
                "score": round(combined_score, 4),
                "methods_triggered": methods_triggered,
                "norm_deviation": round(norm_results.get(cid, {}).get("z_score", 0.0), 4),
                "spectral_score": round(spectral_results.get(cid, {}).get("score", 0.0), 4),
                "direction_score": round(direction_results.get(cid, {}).get("score", 0.0), 4),
            }

        # Store in history
        self._history.append({
            "num_clients": len(client_weights),
            "poisoned_clients": [c for c, r in results.items() if r["poisoned"]],
            "results": results,
        })

        return results

    def _norm_outlier_detection(self, deltas):
        """
        Detect outliers based on L2 norm of weight updates.
        A poisoned update typically has an unusually large or small norm.
        """
        norms = {cid: float(np.linalg.norm(d)) for cid, d in deltas.items()}

        if len(norms) < 3:
            # Not enough clients for statistical outlier detection
            return {cid: {"outlier": False, "z_score": 0.0, "score": 0.0}
                    for cid in deltas}

        values = np.array(list(norms.values()))
        mean_norm = float(np.mean(values))
        std_norm = float(np.std(values)) + 1e-10

        results = {}
        for cid, norm_val in norms.items():
            z = abs(norm_val - mean_norm) / std_norm
            is_outlier = z > self.z_threshold
            score = min(1.0, z / (self.z_threshold * 2))
            results[cid] = {
                "outlier": is_outlier,
                "z_score": z,
                "norm": norm_val,
                "score": score,
            }
        return results

    def _spectral_analysis(self, deltas):
        """
        Spectral analysis via PCA on client update matrix.
        Poisoned updates project strongly onto the top principal component.
        """
        client_ids = list(deltas.keys())
        if len(client_ids) < 3:
            return {cid: {"outlier": False, "score": 0.0} for cid in client_ids}

        # Build update matrix (clients x parameters)
        # Subsample parameters for efficiency
        max_params = 10000
        first_delta = list(deltas.values())[0]
        if len(first_delta) > max_params:
            indices = np.random.choice(len(first_delta), max_params, replace=False)
            matrix = np.array([deltas[cid][indices] for cid in client_ids])
        else:
            matrix = np.array([deltas[cid] for cid in client_ids])

        # Center the matrix
        matrix -= matrix.mean(axis=0)

        # SVD for top principal component
        try:
            U, S, Vt = np.linalg.svd(matrix, full_matrices=False)
            # Projection onto top-1 PC
            projections = np.abs(U[:, 0]) * S[0]

            # Outlier = projection > mean + z_threshold * std
            mean_proj = float(np.mean(projections))
            std_proj = float(np.std(projections)) + 1e-10

            results = {}
            for i, cid in enumerate(client_ids):
                z = abs(projections[i] - mean_proj) / std_proj
                is_outlier = z > self.z_threshold
                score = min(1.0, z / (self.z_threshold * 2))
                results[cid] = {
                    "outlier": is_outlier,
                    "projection": float(projections[i]),
                    "score": score,
                }
            return results
        except np.linalg.LinAlgError:
            return {cid: {"outlier": False, "score": 0.0} for cid in client_ids}

    def _direction_deviation(self, deltas):
        """
        Check if any client's update direction deviates strongly from the
        average update direction (cosine similarity).
        """
        client_ids = list(deltas.keys())
        if len(client_ids) < 3:
            return {cid: {"outlier": False, "score": 0.0} for cid in client_ids}

        # Compute average update direction
        avg_delta = np.mean([deltas[cid] for cid in client_ids], axis=0)
        avg_norm = np.linalg.norm(avg_delta) + 1e-10

        results = {}
        cosine_sims = {}
        for cid in client_ids:
            d_norm = np.linalg.norm(deltas[cid]) + 1e-10
            cos_sim = float(np.dot(deltas[cid], avg_delta) / (d_norm * avg_norm))
            cosine_sims[cid] = cos_sim

        # Outlier: cosine similarity < threshold (pointing in different direction)
        threshold = 1.0 - self.sensitivity  # e.g., sensitivity=0.8 → threshold=0.2
        for cid in client_ids:
            cos_sim = cosine_sims[cid]
            is_outlier = cos_sim < threshold
            # Score: how far below threshold (normalized)
            deviation = max(0, threshold - cos_sim)
            score = min(1.0, deviation / max(threshold, 0.001))
            results[cid] = {
                "outlier": is_outlier,
                "cosine_similarity": round(cos_sim, 4),
                "score": round(score, 4),
            }

        return results

    def get_history(self):
        """Return detection history for dashboard display."""
        return self._history

    def get_summary(self):
        """Return a summary of all detections."""
        total_checked = sum(h["num_clients"] for h in self._history)
        total_poisoned = sum(len(h["poisoned_clients"]) for h in self._history)
        return {
            "rounds_analyzed": len(self._history),
            "total_clients_checked": total_checked,
            "total_poisoned_detected": total_poisoned,
            "detection_rate": round(total_poisoned / max(total_checked, 1), 4),
        }
