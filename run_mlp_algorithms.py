#!/usr/bin/env python3
"""
Run MLP experiments with different algorithms for 30 rounds
"""

import os
import sys
import time
import subprocess
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

def run_experiment(strategy, port, rounds=30):
    """Run a single FL experiment with the given strategy."""
    print("="*70)
    print(f"MLP + {strategy.upper()} - {rounds} Round Experiment")
    print("="*70)

    # Create config
    config = {
        "experiment": {"name": f"mlp_{strategy}_30", "seed": 42},
        "model_type": "mlp",
        "input_dim": 78,
        "num_classes": 2,
        "training": {
            "optimizer": "adam", "lr": 0.001, "batch_size": 256, "epochs": 3
        },
        "federated": {
            "architecture": "flat",
            "strategy": strategy,
            "num_rounds_global": rounds,
            "num_clients": 9
        },
        "network": {"global_server": {"ip": "127.0.0.1", "port": port}}
    }

    config_path = PROJECT_ROOT / "config" / f"mlp_{strategy}_temp.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

    # Start 9 clients first (they will wait for server)
    print(f"\n[1/3] Starting 9 clients on port {port}...")
    clients = []
    for i in range(1, 10):
        cid = f"Client_{i:02d}"
        client_cmd = [
            sys.executable,
            str(PROJECT_ROOT / "federated" / "client.py"),
            "--cid", cid,
            "--server_ip", "127.0.0.1",
            "--port", str(port),
            "--config", str(config_path)
        ]
        proc = subprocess.Popen(client_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clients.append(proc)
        print(f"  {cid}: OK")

    time.sleep(3)
    print(f"\n[2/3] Starting Global Server on port {port}...")
    print("-"*70)

    # Start server
    server_cmd = [
        sys.executable,
        str(PROJECT_ROOT / "federated" / "server_global.py"),
        "--port", str(port),
        "--config", str(config_path),
        "--min_clients", "9"
    ]

    server = subprocess.Popen(server_cmd)

    print(f"\n[3/3] Training will run for {rounds} rounds...")
    print("Press Ctrl+C to stop experiment\n")

    # Wait for server to complete
    try:
        server.wait()
    except KeyboardInterrupt:
        print("\n\nStopping experiment...")

    # Cleanup clients
    print("\nCleaning up clients...")
    for p in clients:
        p.kill()

    # Cleanup config
    if config_path.exists():
        config_path.unlink()

    print("\nExperiment complete!")
    return 0


def main():
    print("="*70)
    print("MLP ALGORITHM COMPARISON EXPERIMENT")
    print("Running MLP with FedAvg and FedMedian (30 rounds each)")
    print("="*70)

    # Run FedAvg first on port 8900
    port_fedavg = 8900
    print(f"\n\n>>> Starting Experiment 1: FedAvg on port {port_fedavg}")
    run_experiment("fedavg", port_fedavg, rounds=30)

    # Wait a bit between experiments
    time.sleep(5)

    # Run FedMedian on port 8901
    port_fedmedian = 8901
    print(f"\n\n>>> Starting Experiment 2: FedMedian on port {port_fedmedian}")
    run_experiment("fedmedian", port_fedmedian, rounds=30)

    print("\n" + "="*70)
    print("ALL EXPERIMENTS COMPLETE!")
    print("="*70)
    print("Check the logs/ directory for detailed output files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
