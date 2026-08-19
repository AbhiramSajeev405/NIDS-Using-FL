"""
Per-Client Fairness Metrics for Federated Learning.

Tracks and computes fairness-related metrics across clients:
  - Per-client accuracy, F1, AUC
  - Variance and std across clients (lower = more fair)
  - Worst-case client performance
  - Jain's Fairness Index: J(x) = (Σx)² / (n * Σx²) ∈ [1/n, 1]
    where 1 = perfectly fair, 1/n = maximally unfair

Reference: Jain, Chiu, Hawe (1984) — 'A Quantitative Measure of Fairness'
"""

import numpy as np
import json
import os


def jains_fairness_index(values):
    """Compute Jain's Fairness Index.

    J(x) = (sum(x))^2 / (n * sum(x^2))
    Range: [1/n, 1] where 1 = perfectly fair

    Args:
        values: List/array of per-client metric values

    Returns:
        Float in [1/n, 1]
    """
    values = np.array(values, dtype=np.float64)
    n = len(values)
    if n == 0 or np.sum(values ** 2) == 0:
        return 0.0
    return (np.sum(values) ** 2) / (n * np.sum(values ** 2))


def compute_fairness_report(client_metrics):
    """Compute comprehensive fairness metrics.

    Args:
        client_metrics: Dict mapping client_id -> metric_dict
            e.g., {'Client_01': {'accuracy': 0.85, 'f1': 0.82}, ...}

    Returns:
        Dict with fairness summary
    """
    if not client_metrics:
        return {}

    # Extract per-metric lists
    metric_names = list(next(iter(client_metrics.values())).keys())
    report = {}

    for metric in metric_names:
        values = [m[metric] for m in client_metrics.values() if metric in m]
        if not values:
            continue

        values = np.array(values)
        report[metric] = {
            'per_client': {cid: m[metric] for cid, m in client_metrics.items() if metric in m},
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'variance': float(np.var(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'range': float(np.max(values) - np.min(values)),
            'worst_client': list(client_metrics.keys())[int(np.argmin(values))],
            'best_client': list(client_metrics.keys())[int(np.argmax(values))],
            'jains_index': float(jains_fairness_index(values)),
            'coefficient_of_variation': float(np.std(values) / np.mean(values)) if np.mean(values) > 0 else 0,
        }

    # Overall fairness summary
    if 'accuracy' in report:
        acc_data = report['accuracy']
        report['_summary'] = {
            'overall_fairness': (
                'HIGH' if acc_data['jains_index'] > 0.9 else
                'MEDIUM' if acc_data['jains_index'] > 0.7 else
                'LOW'
            ),
            'accuracy_jains_index': acc_data['jains_index'],
            'accuracy_std': acc_data['std'],
            'worst_client': acc_data['worst_client'],
            'worst_accuracy': acc_data['min'],
        }

    return report


def save_fairness_report(report, output_path):
    """Save fairness report to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"[Fairness] Report saved to {output_path}")


def print_fairness_report(report):
    """Pretty-print fairness report."""
    print("\n" + "=" * 60)
    print("FAIRNESS REPORT")
    print("=" * 60)

    if '_summary' in report:
        s = report['_summary']
        print(f"  Overall Fairness: {s['overall_fairness']}")
        print(f"  Jain's Index (accuracy): {s['accuracy_jains_index']:.4f}")
        print(f"  Accuracy Std: {s['accuracy_std']:.4f}")
        print(f"  Worst Client: {s['worst_client']} ({s['worst_accuracy']:.4f})")

    for metric, data in report.items():
        if metric.startswith('_'):
            continue
        print(f"\n  --- {metric} ---")
        print(f"    Mean: {data['mean']:.4f} ± {data['std']:.4f}")
        print(f"    Range: [{data['min']:.4f}, {data['max']:.4f}]")
        print(f"    Jain's Index: {data['jains_index']:.4f}")
        print(f"    Best: {data['best_client']} | Worst: {data['worst_client']}")

    print("=" * 60)
