"""
Communication Cost Tracker for Federated Learning.

Tracks the total bytes transmitted between clients and servers
across FL rounds. Important for comparing the communication
efficiency of different aggregation strategies.

Usage:
    tracker = CommTracker(model, n_clients=9)
    tracker.log_round(round_num, participating_clients=9)
    tracker.summary()
"""

import os
import json
import numpy as np


class CommTracker:
    """Track communication costs per FL round."""

    def __init__(self, model=None, param_count=None, n_clients=9):
        """
        Args:
            model: PyTorch model (used to compute parameter size)
            param_count: Alternative to model — directly provide parameter count
            n_clients: Total number of clients
        """
        if model is not None:
            self.param_count = sum(p.numel() for p in model.parameters())
            # Size in bytes: float32 = 4 bytes per parameter
            self.param_bytes = self.param_count * 4
        elif param_count is not None:
            self.param_count = param_count
            self.param_bytes = param_count * 4
        else:
            self.param_count = 0
            self.param_bytes = 0

        self.n_clients = n_clients
        self.round_logs = []
        self.total_upload_bytes = 0
        self.total_download_bytes = 0

    def log_round(self, round_num, participating_clients=None, extra_upload=0, extra_download=0):
        """Log communication for one FL round.

        In each round:
          - Each participating client UPLOADS its model parameters to the server
          - The server DOWNLOADS the aggregated model to all participating clients

        Args:
            round_num: Current round number
            participating_clients: Number of clients that participated (default: all)
            extra_upload: Additional upload bytes (e.g., metadata)
            extra_download: Additional download bytes
        """
        if participating_clients is None:
            participating_clients = self.n_clients

        # Upload: each client sends its full model
        round_upload = participating_clients * self.param_bytes + extra_upload

        # Download: server sends aggregated model to each client
        round_download = participating_clients * self.param_bytes + extra_download

        self.total_upload_bytes += round_upload
        self.total_download_bytes += round_download

        self.round_logs.append({
            'round': round_num,
            'participating_clients': participating_clients,
            'upload_bytes': round_upload,
            'download_bytes': round_download,
            'total_bytes': round_upload + round_download,
        })

    def get_total_bytes(self):
        """Total bytes transmitted (upload + download)."""
        return self.total_upload_bytes + self.total_download_bytes

    def summary(self):
        """Print and return communication summary."""
        total = self.get_total_bytes()

        summary = {
            'param_count': self.param_count,
            'param_size_bytes': self.param_bytes,
            'param_size_kb': self.param_bytes / 1024,
            'total_rounds': len(self.round_logs),
            'total_upload_mb': self.total_upload_bytes / (1024 * 1024),
            'total_download_mb': self.total_download_bytes / (1024 * 1024),
            'total_comm_mb': total / (1024 * 1024),
            'avg_per_round_mb': (total / len(self.round_logs) / (1024 * 1024)) if self.round_logs else 0,
            'round_details': self.round_logs,
        }

        print("\n" + "=" * 50)
        print("COMMUNICATION COST SUMMARY")
        print("=" * 50)
        print(f"  Model parameters:    {self.param_count:,}")
        print(f"  Parameter size:      {self.param_bytes / 1024:.1f} KB")
        print(f"  Total rounds:        {len(self.round_logs)}")
        print(f"  Total upload:        {summary['total_upload_mb']:.2f} MB")
        print(f"  Total download:      {summary['total_download_mb']:.2f} MB")
        print(f"  Total communication: {summary['total_comm_mb']:.2f} MB")
        print(f"  Avg per round:       {summary['avg_per_round_mb']:.2f} MB")
        print("=" * 50)

        return summary

    def save(self, output_path):
        """Save communication log to JSON."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(self.summary(), f, indent=2)


def estimate_comm_cost(model_type, input_dim, num_classes, n_clients, n_rounds):
    """Quick estimate of communication cost without training.

    Args:
        model_type: Model name (e.g., 'mlp', 'cnn')
        input_dim: Input feature dimension
        num_classes: Number of output classes
        n_clients: Number of clients
        n_rounds: Number of FL rounds

    Returns:
        Dict with cost estimates
    """
    from models.factory import get_model
    import torch
    model = get_model(model_type, input_dim, num_classes)
    param_count = sum(p.numel() for p in model.parameters())
    param_bytes = param_count * 4

    total = 2 * n_clients * n_rounds * param_bytes  # Upload + download
    return {
        'model_type': model_type,
        'param_count': param_count,
        'param_size_kb': param_bytes / 1024,
        'total_comm_mb': total / (1024 * 1024),
        'per_round_mb': (2 * n_clients * param_bytes) / (1024 * 1024),
    }
