"""
Experiment Management for FL-NIDS.

Provides tools for reproducible experiment tracking:
  - Config hashing for unique experiment IDs
  - Seed management for reproducibility
  - Results directory management
  - Multi-experiment comparison reports
"""

import os
import json
import hashlib
import random
import numpy as np
import torch
import pandas as pd
from datetime import datetime


def set_seed(seed):
    """Set random seeds for full reproducibility.

    Args:
        seed: Integer seed value
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # Deterministic mode (may slow down training)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    print(f"[ExperimentManager] Set all random seeds to {seed}")


def hash_config(config):
    """Create a deterministic hash of the experiment config.

    Ignores network IPs and paths (those don't affect experiment results).

    Args:
        config: Full config dict

    Returns:
        8-character hex hash string
    """
    # Extract only experiment-relevant keys
    relevant_keys = ['model', 'model_type', 'input_dim', 'num_classes',
                     'training', 'learning', 'federated', 'data', 'defense']
    relevant = {k: config[k] for k in relevant_keys if k in config}
    config_str = json.dumps(relevant, sort_keys=True, default=str)
    return hashlib.sha256(config_str.encode()).hexdigest()[:8]


def get_experiment_id(config):
    """Generate a human-readable experiment ID.

    Format: {model}_{strategy}_{distribution}_{hash}

    Args:
        config: Full config dict

    Returns:
        String experiment ID (e.g., 'cnn_fedmedian_noniid_a1b2c3d4')
    """
    model = config.get('model', {}).get('type', config.get('model_type', 'unknown'))
    strategy = config.get('federated', {}).get('strategy', 'unknown')
    distribution = config.get('data', {}).get('distribution', 'iid')
    config_hash = hash_config(config)
    return f"{model}_{strategy}_{distribution}_{config_hash}"


def setup_experiment(config, base_dir=None):
    """Set up experiment directory and reproducibility.

    Creates:
      results/{experiment_id}/
        config.json    — Frozen copy of the config
        metrics/       — For per-round metrics

    Args:
        config: Full experiment config dict
        base_dir: Project root directory

    Returns:
        experiment_id, results_dir
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Set seed
    seed = config.get('experiment', {}).get('seed', 42)
    set_seed(seed)

    # Create experiment directory
    exp_id = get_experiment_id(config)
    results_dir = os.path.join(base_dir, "results", exp_id)
    os.makedirs(os.path.join(results_dir, "metrics"), exist_ok=True)

    # Save frozen config
    config_path = os.path.join(results_dir, "config.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, default=str)

    # Save experiment metadata
    meta = {
        "experiment_id": exp_id,
        "timestamp": datetime.now().isoformat(),
        "seed": seed,
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
    }
    meta_path = os.path.join(results_dir, "metadata.json")
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"[ExperimentManager] Experiment ID: {exp_id}")
    print(f"[ExperimentManager] Results dir: {results_dir}")

    return exp_id, results_dir


def compare_experiments(results_base_dir, output_path=None):
    """Generate a comparison report across multiple experiments.

    Scans all subdirectories under results_base_dir, loads their
    metrics CSVs, and produces a summary comparison table.

    Args:
        results_base_dir: Path to the 'results/' directory
        output_path: Optional path to save the comparison CSV

    Returns:
        pandas DataFrame with comparison
    """
    if not os.path.exists(results_base_dir):
        print(f"[ExperimentManager] No results directory found at {results_base_dir}")
        return None

    all_results = []

    for exp_id in os.listdir(results_base_dir):
        exp_dir = os.path.join(results_base_dir, exp_id)
        if not os.path.isdir(exp_dir):
            continue

        # Load config
        config_path = os.path.join(exp_dir, "config.json")
        if not os.path.exists(config_path):
            continue

        with open(config_path, 'r') as f:
            config = json.load(f)

        # Load metrics (find any CSV in the metrics/ folder)
        metrics_dir = os.path.join(exp_dir, "metrics")
        if os.path.exists(metrics_dir):
            csv_files = [f for f in os.listdir(metrics_dir) if f.endswith('.csv')]
            if csv_files:
                metrics_df = pd.read_csv(os.path.join(metrics_dir, csv_files[-1]))  # Latest
                avg_metrics = {
                    "experiment_id": exp_id,
                    "model": config.get('model', {}).get('type', config.get('model_type', '?')),
                    "strategy": config.get('federated', {}).get('strategy', '?'),
                    "distribution": config.get('data', {}).get('distribution', '?'),
                    "avg_accuracy": metrics_df['accuracy'].mean() if 'accuracy' in metrics_df else None,
                    "avg_f1": metrics_df['f1_score'].mean() if 'f1_score' in metrics_df else None,
                    "avg_detection_rate": metrics_df['detection_rate'].mean() if 'detection_rate' in metrics_df else None,
                    "avg_fpr": metrics_df['false_positive_rate'].mean() if 'false_positive_rate' in metrics_df else None,
                }
                all_results.append(avg_metrics)

    if not all_results:
        print("[ExperimentManager] No experiment results found.")
        return None

    comparison_df = pd.DataFrame(all_results)

    if output_path:
        comparison_df.to_csv(output_path, index=False)
        print(f"[ExperimentManager] Comparison saved to {output_path}")

    # Print comparison table
    print("\n" + "=" * 80)
    print("EXPERIMENT COMPARISON")
    print("=" * 80)
    print(comparison_df.to_string(index=False))
    print("=" * 80)

    return comparison_df


def log_round_metrics(results_dir, round_num, metrics_dict):
    """Log per-round metrics to a JSONL file for convergence tracking.

    Args:
        results_dir: Experiment results directory
        round_num: Current FL round number
        metrics_dict: Dict of metrics (e.g., {'loss': 0.5, 'accuracy': 0.85})
    """
    log_path = os.path.join(results_dir, "metrics", "round_metrics.jsonl")
    entry = {"round": round_num, "timestamp": datetime.now().isoformat(), **metrics_dict}
    with open(log_path, 'a') as f:
        f.write(json.dumps(entry) + '\n')
