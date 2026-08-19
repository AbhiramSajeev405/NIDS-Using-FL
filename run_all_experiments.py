#!/usr/bin/env python3
"""
COMPREHENSIVE FL-NIDS EXPERIMENT RUNNER
Runs all 30 combinations of models and algorithms

Usage: python run_all_experiments.py
"""

import os
import sys
import yaml
import time
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.resolve()

# ============================================================================
# CONFIGURATION
# ============================================================================

MODELS = ['mlp', 'cnn', 'lstm', 'resnet', 'autoencoder']
STRATEGIES = ['fedavg', 'fedprox', 'fedmedian', 'trimmed_mean', 'krum', 'fednova']
NUM_ROUNDS = 30
NUM_CLIENTS = 9

# Port allocation: base + model_index * 10 + strategy_index
PORT_BASES = {
    'mlp': 8900,
    'cnn': 8910,
    'lstm': 8920,
    'resnet': 8930,
    'autoencoder': 8940,
}

INPUT_DIMS = {
    'mlp': 78,
    'cnn': 78,
    'lstm': 78,
    'resnet': 78,
    'autoencoder': 78,
}

# ============================================================================
# RESULTS LOGGER
# ============================================================================

class ResultsLogger:
    def __init__(self):
        self.results_dir = PROJECT_ROOT / "experiment_results"
        self.results_dir.mkdir(exist_ok=True)
        self.results = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = self.results_dir / f"all_experiments_{self.timestamp}.csv"
        self.log_file = self.results_dir / f"all_experiments_{self.timestamp}.log"

    def log_experiment(self, model, strategy, metrics):
        result = {
            'model': model,
            'strategy': strategy,
            'timestamp': datetime.now().isoformat(),
            **metrics
        }
        self.results.append(result)
        self._save_csv()
        self._append_log(result)

    def _save_csv(self):
        import pandas as pd
        df = pd.DataFrame(self.results)
        df.to_csv(self.csv_file, index=False)

    def _append_log(self, result):
        with open(self.log_file, 'a') as f:
            f.write(f"\n=== {result['model']} + {result['strategy']} ===\n")
            for key, value in result.items():
                if key not in ['model', 'strategy', 'timestamp']:
                    f.write(f"  {key}: {value}\n")

# ============================================================================
# CONFIG CREATOR
# ============================================================================

def create_config(model, strategy, port):
    """Create a temporary config file for the experiment."""
    config = {
        "experiment": {
            "name": f"{model}_{strategy}",
            "seed": 42
        },
        "model_type": model,
        "input_dim": INPUT_DIMS[model],
        "num_classes": 2,
        "training": {
            "optimizer": "adam",
            "lr": 0.001,
            "batch_size": 256,
            "epochs": 3
        },
        "federated": {
            "architecture": "flat",
            "strategy": strategy,
            "num_rounds_global": NUM_ROUNDS,
            "num_clients": NUM_CLIENTS,
            "proximal_mu": 0.1,
            "trim_ratio": 0.1,
            "krum_num_malicious": 1,
            "krum_multi_k": 1,
        },
        "network": {
            "global_server": {
                "ip": "127.0.0.1",
                "port": port
            }
        }
    }

    config_path = PROJECT_ROOT / "config" / f"temp_{model}_{strategy}.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

    return config_path

# ============================================================================
# EXPERIMENT RUNNER
# ============================================================================

def run_experiment(model, strategy, logger):
    """Run a single FL experiment."""
    print(f"\n{'='*70}")
    print(f"Running: {model.upper()} + {strategy.upper()}")
    print(f"{'='*70}")

    port = PORT_BASES[model] + STRATEGIES.index(strategy)
    config_path = create_config(model, strategy, port)

    start_time = time.time()
    metrics = {}

    try:
        # Start 9 clients
        print(f"\n[1/3] Starting {NUM_CLIENTS} clients on port {port}...")
        clients = []
        for i in range(1, NUM_CLIENTS + 1):
            client_id = f"Client_{i:02d}"
            client_cmd = [
                sys.executable,
                str(PROJECT_ROOT / "federated" / "client.py"),
                "--cid", client_id,
                "--server_ip", "127.0.0.1",
                "--port", str(port),
                "--config", str(config_path)
            ]
            proc = subprocess.Popen(client_cmd,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
            clients.append(proc)
            print(f"  {client_id}: OK")

        time.sleep(3)

        # Start server and monitor output
        print(f"\n[2/3] Starting server...")
        server_cmd = [
            sys.executable,
            str(PROJECT_ROOT / "federated" / "server_global.py"),
            "--port", str(port),
            "--config", str(config_path),
            "--min_clients", str(NUM_CLIENTS)
        ]

        server = subprocess.Popen(server_cmd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 text=True)

        print(f"\n[3/3] Training in progress...")

        # Find the generated log file
        log_pattern = str(PROJECT_ROOT / "logs" / f"server_*.log")

        # Wait for server to complete
        server.wait(timeout=2000)

        end_time = time.time()
        metrics['runtime_seconds'] = round(end_time - start_time, 2)
        print(f"\nTraining completed in {metrics['runtime_seconds']}s")

        # Try to extract metrics from log
        metrics = extract_metrics_from_log(PROJECT_ROOT / "logs", model, strategy, metrics)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        metrics['error'] = str(e)
        metrics['runtime_seconds'] = round(time.time() - start_time, 2)

    finally:
        # Cleanup clients
        print("Cleaning up clients...")
        for proc in clients:
            proc.kill()

        # Cleanup config
        if config_path.exists():
            config_path.unlink()

    # Log results
    logger.log_experiment(model, strategy, metrics)

    print(f"\nExperiment complete: {model} + {strategy}")
    return metrics

# ============================================================================
# METRICS EXTRACTION
# ============================================================================

def extract_metrics_from_log(logs_dir, model, strategy, metrics):
    """Extract metrics from the server log file."""
    import re
    import glob
    from datetime import datetime

    # Find most recent log file for this experiment
    log_files = sorted(logs_dir.glob("server_2026*.log"),
                      key=lambda x: x.stat().st_mtime,
                      reverse=True)

    for log_file in log_files[:3]:  # Check last 3 files
        with open(log_file, 'r') as f:
            content = f.read()

        # Check if this log matches our experiment
        if f'Strategy: {strategy}' not in content:
            continue

        # Extract metrics
        try:
            # Final round metrics
            accuracy_match = re.search(r"'accuracy': \[.*, \(\d+, ([\d.]+)\)\]", content)
            loss_match = re.search(r"round 30: ([\d.]+)", content)
            f1_match = re.search(r"'f1_score': \[.*, \(\d+, ([\d.]+)\)\]", content)
            detection_match = re.search(r"'detection_rate': \[.*, \(\d+, ([\d.]+)\)\]", content)
            fpr_match = re.search(r"'fpr': \[.*, \(\d+, ([\d.]+)\)\]", content)
            precision_match = re.search(r"'precision': \[.*, \(\d+, ([\d.]+)\)\]", content)

            metrics['final_accuracy'] = float(accuracy_match.group(1)) if accuracy_match else None
            metrics['final_loss'] = float(loss_match.group(1)) if loss_match else None
            metrics['final_f1_score'] = float(f1_match.group(1)) if f1_match else None
            metrics['final_detection_rate'] = float(detection_match.group(1)) if detection_match else None
            metrics['final_fpr'] = float(fpr_match.group(1)) if fpr_match else None
            metrics['final_precision'] = float(precision_match.group(1)) if precision_match else None

            # Round 1 metrics
            round1_accuracy = re.search(r"'accuracy': \[\(\d+, ([\d.]+)\)", content)
            round1_loss = re.search(r"round 1: ([\d.]+)", content)
            round1_f1 = re.search(r"'f1_score': \[\(\d+, ([\d.]+)\)", content)

            metrics['round1_accuracy'] = float(round1_accuracy.group(1)) if round1_accuracy else None
            metrics['round1_loss'] = float(round1_loss.group(1)) if round1_loss else None
            metrics['round1_f1_score'] = float(round1_f1.group(1)) if round1_f1 else None

            break

        except Exception as e:
            print(f"  Warning: Could not extract metrics: {e}")

    return metrics

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("="*70)
    print("COMPREHENSIVE FL-NIDS EXPERIMENT RUNNER")
    print("="*70)
    print(f"Models: {', '.join(MODELS)}")
    print(f"Strategies: {', '.join(STRATEGIES)}")
    print(f"Total experiments: {len(MODELS) * len(STRATEGIES)}")
    print(f"Estimated time: 5-8 hours")
    print("="*70)

    confirm = input("\nPress ENTER to start all experiments...")

    logger = ResultsLogger()
    print(f"\nResults will be saved to: {logger.results_dir}")

    completed = 0
    failed = 0

    for model in MODELS:
        for strategy in STRATEGIES:
            try:
                metrics = run_experiment(model, strategy, logger)
                if 'error' in metrics:
                    failed += 1
                else:
                    completed += 1

                print(f"\nProgress: {completed} completed, {failed} failed")

                # Wait between experiments
                time.sleep(5)

            except KeyboardInterrupt:
                print(f"\n\n[ABORT] User interrupted")
                logger.log_experiment(model, strategy, {
                    'runtime_seconds': 0,
                    'error': 'User interrupted'
                })
                break

    print(f"\n{'='*70}")
    print("ALL EXPERIMENTS COMPLETE")
    print(f"{'='*70}")
    print(f"Results saved to: {logger.csv_file}")
    print(f"Final: {completed} successful, {failed} failed")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
