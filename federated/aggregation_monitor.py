"""
Aggregation Monitor for FL-NIDS.

Hooks into each FL round to capture weight divergence between clients,
aggregation timing, contribution scores, and convergence rate estimation.

Usage:
    monitor = AggregationMonitor()
    monitor.start_round(round_num=1)
    monitor.record_client_weights("Client_01", weights_numpy)
    monitor.record_client_weights("Client_02", weights_numpy)
    monitor.finish_round(global_weights_numpy)
    report = monitor.get_round_report(round_num=1)
"""

import os
import json
import time
import numpy as np
try:
    from utils.real_time_logger import RealTimeLogger
    _rt_logger = RealTimeLogger(init_file=False)
except Exception:
    _rt_logger = None
from datetime import datetime


def _flatten_weights(weights_list):
    """Flatten a list of numpy arrays into a single 1D vector."""
    return np.concatenate([w.flatten() for w in weights_list])


def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def l2_distance(a, b):
    """Compute L2 (Euclidean) distance between two vectors."""
    return float(np.linalg.norm(a - b))


class AggregationMonitor:
    """Monitor FL aggregation rounds for weight divergence and convergence."""

    def __init__(self, output_dir=None):
        """
        Args:
            output_dir: Directory to save round reports
        """
        if output_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(project_root, "results", "aggregation_logs")
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.rounds = {}
        self.global_weight_history = []  # Track global weights across rounds

    def start_round(self, round_num):
        """Begin recording a new FL round.

        Args:
            round_num: Current round number
        """
        self.rounds[round_num] = {
            "round": round_num,
            "start_time": time.time(),
            "end_time": None,
            "duration_seconds": None,
            "client_weights": {},       # client_id -> flat weight vector
            "global_weights": None,
            "divergence_matrix": {},     # (client_a, client_b) -> similarity
            "client_to_global": {},      # client_id -> {cosine, l2}
            "convergence_delta": None,   # Change from previous round
        }

    def record_client_weights(self, client_id, weights):
        """Record a client's model weights for this round.

        Args:
            client_id: Client identifier
            weights: List of numpy arrays (model parameters)
        """
        current_round = max(self.rounds.keys()) if self.rounds else 0
        if current_round not in self.rounds:
            return

        flat = _flatten_weights(weights)
        self.rounds[current_round]["client_weights"][client_id] = flat

    def finish_round(self, global_weights, round_num=None):
        """Finalize a round and compute all metrics.

        Args:
            global_weights: List of numpy arrays (aggregated global model)
            round_num: Round number (default: latest)
        """
        if round_num is None:
            round_num = max(self.rounds.keys()) if self.rounds else 0

        if round_num not in self.rounds:
            return

        rd = self.rounds[round_num]
        rd["end_time"] = time.time()
        rd["duration_seconds"] = round(rd["end_time"] - rd["start_time"], 3)

        global_flat = _flatten_weights(global_weights)
        rd["global_weights"] = global_flat

        # 1. Client-to-client divergence matrix
        clients = list(rd["client_weights"].keys())
        for i, ca in enumerate(clients):
            for j, cb in enumerate(clients):
                if i < j:
                    sim = cosine_similarity(rd["client_weights"][ca], rd["client_weights"][cb])
                    rd["divergence_matrix"][f"{ca}_vs_{cb}"] = round(sim, 6)

        # 2. Client-to-global divergence
        for cid, cw in rd["client_weights"].items():
            rd["client_to_global"][cid] = {
                "cosine_similarity": round(cosine_similarity(cw, global_flat), 6),
                "l2_distance": round(l2_distance(cw, global_flat), 6),
            }

        # 3. Convergence delta (change from previous round's global weights)
        if len(self.global_weight_history) > 0:
            prev_global = self.global_weight_history[-1]
            rd["convergence_delta"] = {
                "l2_distance": round(l2_distance(prev_global, global_flat), 6),
                "cosine_similarity": round(cosine_similarity(prev_global, global_flat), 6),
            }

        self.global_weight_history.append(global_flat)

        # Clear raw weights to save memory (keep metrics only)
        rd["client_weights"] = {}
        rd["global_weights"] = None

    def get_round_report(self, round_num):
        """Get the report for a specific round.

        Args:
            round_num: Round number

        Returns:
            Dict with round metrics
        """
        rd = self.rounds.get(round_num, {})
        # Return a clean copy without large arrays
        return {
            "round": rd.get("round"),
            "duration_seconds": rd.get("duration_seconds"),
            "num_clients": len(rd.get("client_to_global", {})),
            "divergence_matrix": rd.get("divergence_matrix", {}),
            "client_to_global": rd.get("client_to_global", {}),
            "convergence_delta": rd.get("convergence_delta"),
        }

    def get_convergence_trend(self):
        """Get the convergence trend across all recorded rounds.

        Returns:
            List of {round, l2_delta, cosine_delta} dicts
        """
        trend = []
        for rnum in sorted(self.rounds.keys()):
            rd = self.rounds[rnum]
            delta = rd.get("convergence_delta")
            if delta:
                trend.append({
                    "round": rnum,
                    "l2_delta": delta["l2_distance"],
                    "cosine_similarity": delta["cosine_similarity"],
                })
        return trend

    def get_client_divergence_summary(self):
        """Get a summary of client weight divergence across all rounds.

        Returns:
            Dict mapping client_id -> list of per-round divergence values
        """
        summary = {}
        for rnum in sorted(self.rounds.keys()):
            for cid, metrics in self.rounds[rnum].get("client_to_global", {}).items():
                if cid not in summary:
                    summary[cid] = []
                summary[cid].append({
                    "round": rnum,
                    "cosine_similarity": metrics["cosine_similarity"],
                    "l2_distance": metrics["l2_distance"],
                })
        return summary

    def save_all(self):
        """Save all round reports to disk."""
        all_reports = {}
        for rnum in sorted(self.rounds.keys()):
            all_reports[f"round_{rnum}"] = self.get_round_report(rnum)

        output_path = os.path.join(self.output_dir, "aggregation_monitor.json")
        with open(output_path, 'w') as f:
            json.dump(all_reports, f, indent=2)
        print(f"[AggregationMonitor] Saved {len(all_reports)} round reports to {output_path}")

    def print_round_summary(self, round_num):
        """Pretty-print a round summary."""
        report = self.get_round_report(round_num)
        print(f"\n{'='*60}")
        print(f"AGGREGATION MONITOR — Round {round_num}")
        print(f"{'='*60}")
        print(f"  Duration: {report.get('duration_seconds', '?')}s")
        print(f"  Clients:  {report.get('num_clients', 0)}")

        c2g = report.get("client_to_global", {})
        if c2g:
            print(f"\n  Client → Global Divergence:")
            for cid, m in c2g.items():
                print(f"    {cid}: cos={m['cosine_similarity']:.4f}  L2={m['l2_distance']:.4f}")

        delta = report.get("convergence_delta")
        if delta:
            print(f"\n  Convergence Delta (vs prev round):")
            print(f"    L2 distance:       {delta['l2_distance']:.6f}")
            print(f"    Cosine similarity: {delta['cosine_similarity']:.6f}")
        print(f"{'='*60}")
