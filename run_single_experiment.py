#!/usr/bin/env python3
"""
Run a SINGLE experiment: MLP + FedAvg for 15 rounds
"""

import os
import sys
import time
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

def main():
    print("="*70)
    print("MLP + FedAvg - 30 Round Experiment")
    print("="*70)

    # Create temporary config
    import yaml
    config = {
        "experiment": {"name": "mlp_fedavg_single", "seed": 42},
        "model_type": "mlp",
        "input_dim": 78,
        "num_classes": 2,
        "training": {
            "optimizer": "adam", "lr": 0.001, "batch_size": 256, "epochs": 3
        },
        "federated": {
            "architecture": "flat",
            "strategy": "fedavg",
            "num_rounds_global": 30,
            "num_clients": 9
        },
        "network": {"global_server": {"ip": "127.0.0.1", "port": 8080}}
    }

    config_path = PROJECT_ROOT / "config" / "mlp_fedavg_single.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

    # Start 9 clients first (they will wait for server)
    print("\n[1/3] Starting 9 clients...")
    clients = []
    for i in range(1, 10):
        cid = f"Client_{i:02d}"
        client_cmd = [
            sys.executable,
            str(PROJECT_ROOT / "federated" / "client.py"),
            "--cid", cid,
            "--server_ip", "127.0.0.1",
            "--port", "8080",
            "--config", str(config_path)
        ]
        proc = subprocess.Popen(client_cmd)
        clients.append(proc)
        print(f"  {cid}: OK")

    time.sleep(2)
    print(f"\n[2/3] Starting Global Server...")
    print("-"*70)

    # Start server - output will display directly in console
    server_cmd = [
        sys.executable,
        str(PROJECT_ROOT / "federated" / "server_global.py"),
        "--port", "8080",
        "--config", str(config_path),
        "--min_clients", "9"
    ]

    server = subprocess.Popen(server_cmd)

    print(f"\n[3/3] Training will run for 30 rounds...")
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

    print("\nExperiment complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
