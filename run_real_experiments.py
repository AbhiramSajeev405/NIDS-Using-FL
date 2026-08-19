#!/usr/bin/env python3
"""
LSCUDAPORT - REAL Training Experiment Runner (FIXED VERSION)
============================================================

This version runs ACTUAL federated learning training (NOT simulated).
FIXED: Proper output buffering handling and monitoring loop.

Configuration:
- 15 rounds (FIXED - matches physical_config.yaml)
- 9 clients (FIXED)
- 5 models x 6 strategies = 30 experiments
"""

import os
import sys
import json
import time
import yaml
import subprocess
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import threading
import queue

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration
RESULTS_DIR = PROJECT_ROOT / "experiment_results"
RESULTS_DIR.mkdir(exist_ok=True)

# FIXED CONFIGURATION
MODEL_TYPES = ["mlp", "cnn", "lstm", "resnet", "autoencoder"]
STRATEGIES = ["fedavg", "fedprox", "fedmedian", "trimmed_mean", "krum", "fednova"]
NUM_ROUNDS = 15 # FIXED (matches physical_config.yaml)
NUM_CLIENTS = 9 # FIXED


class ExperimentLogger:
    """Logger for experiment results."""

    def __init__(self, results_dir):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.current_experiment = {}
        self.all_results = []

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_file = self.results_dir / f"real_experiments_{timestamp}.json"
        self.csv_file = self.results_dir / f"real_experiments_{timestamp}.csv"

    def start_experiment(self, config: Dict):
        self.current_experiment = {
            "config": config,
            "start_time": datetime.now().isoformat(),
            "rounds": [],
            "status": "running"
        }

    def log_round(self, round_num: int, metrics: Dict):
        self.current_experiment["rounds"].append({
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            **metrics
        })

    def end_experiment(self, success: bool = True, error: str = None):
        self.current_experiment["end_time"] = datetime.now().isoformat()
        self.current_experiment["status"] = "completed" if success else "failed"
        if error:
            self.current_experiment["error"] = error

        self.all_results.append(self.current_experiment)
        self._save_results()

    def _save_results(self):
        with open(self.results_file, 'w') as f:
            json.dump(self.all_results, f, indent=2)

        if self.all_results:
            rows = []
            for exp in self.all_results:
                if exp["status"] == "completed" and exp["rounds"]:
                    final_round = exp["rounds"][-1]
                    rows.append({
                        "model": exp["config"]["model"],
                        "strategy": exp["config"]["strategy"],
                        "final_accuracy": final_round.get("accuracy", 0),
                        "final_detection_rate": final_round.get("detection_rate", 0),
                        "final_f1": final_round.get("f1", 0),
                        "final_loss": final_round.get("loss", 0),
                        "rounds_completed": len(exp["rounds"]),
                    })

            df = pd.DataFrame(rows)
            df.to_csv(self.csv_file, index=False)


def create_temp_config(model_type: str, strategy: str) -> Path:
    """Create temporary config file for experiment."""
    config = {
        "experiment": {
            "name": f"real_{model_type}_{strategy}",
            "seed": 42
        },
        "model_type": model_type,
        "input_dim": 78,
        "num_classes": 2,
        "training": {
            "optimizer": "adam",
            "lr": 0.001,
            "batch_size": 256,
            "epochs": 3,
            "weight_decay": 0.0
        },
        "federated": {
            "architecture": "flat",
            "strategy": strategy,
            "num_rounds_global": NUM_ROUNDS,
            "num_clients": NUM_CLIENTS,
            "trim_ratio": 0.1,
            "krum_num_malicious": 1,
            "krum_multi_k": 1,
            "fedprox_mu": 0.1
        },
        "network": {
            "global_server": {
                "ip": "127.0.0.1",
                "port": 8080
            }
        }
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config_path = PROJECT_ROOT / "config" / f"temp_real_{timestamp}.yaml"

    with open(config_path, 'w') as f:
        yaml.dump(config, f)

    return config_path


def run_single_experiment(model_type: str, strategy: str, logger: ExperimentLogger) -> bool:
    """Run a single REAL FL experiment with FIXED monitoring."""
    print(f"\n{'='*70}")
    print(f"REAL Training: {model_type} + {strategy}")
    print(f"Rounds: {NUM_ROUNDS}, Clients: {NUM_CLIENTS}")
    print(f"{'='*70}")

    logger.start_experiment({
        "model": model_type,
        "strategy": strategy,
        "num_rounds": NUM_ROUNDS,
        "num_clients": NUM_CLIENTS
    })

    config_path = None
    server_process = None
    client_processes = []

    try:
        # Create config
        config_path = create_temp_config(model_type, strategy)

        # Start FL server
        print(f"\n[1/3] Starting Global Server...")
        server_cmd = [
            sys.executable,
            str(PROJECT_ROOT / "federated" / "server_global.py"),
            "--port", "8080",
            "--config", str(config_path),
            "--min_clients", str(NUM_CLIENTS)
        ]

        # Start with unbuffered output for real-time monitoring
        server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # Line buffered
        )

        # Wait for server to initialize
        print(f"[2/3] Waiting for server to initialize...")
        time.sleep(5)

        # Start clients
        print(f"[3/3] Starting {NUM_CLIENTS} clients...")

        for i in range(1, NUM_CLIENTS + 1):
            client_id = f"Client_{i:02d}"
            print(f" Starting {client_id}...", end=" ")

            client_cmd = [
                sys.executable,
                str(PROJECT_ROOT / "federated" / "client.py"),
                "--cid", client_id,
                "--server_ip", "127.0.0.1",
                "--port", "8080",
                "--config", str(config_path)
            ]

            client_process = subprocess.Popen(
                client_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            client_processes.append((client_id, client_process))
            print("[OK]")

        time.sleep(0.5)  # Stagger client starts

        print(f"\n[TRAINING] Running {NUM_ROUNDS} rounds...")
        print(f"Monitoring server output...\n")

        # FIXED: Use thread to read output and avoid buffering issues
        output_queue = queue.Queue()
        round_count = 0
        stop_event = threading.Event()

        def read_output(stream):
            """Read output in background thread."""
            try:
                while not stop_event.is_set():
                    line = stream.readline()
                    if not line:
                        break
                    output_queue.put(line)
            except Exception as e:
                output_queue.put(f"[ERROR] {e}")

        # Start output reader thread
        reader_thread = threading.Thread(target=read_output, args=(server_process.stdout,), daemon=True)
        reader_thread.start()

        # Main monitoring loop
        last_output_time = time.time()
        while round_count < NUM_ROUNDS:
            # Check if server is still running
            if server_process.poll() is not None:
                print(f"\n[MONITOR] Server process exited at round {round_count}")
                # Drain remaining output
                while not output_queue.empty():
                    line = output_queue.get_nowait()
                    print(f" {line.strip()}")
                break

            # Process available output
            try:
                while not output_queue.empty():
                    line = output_queue.get_nowait()
                    print(f" {line.strip()}")
                    last_output_time = time.time()

                    # Parse round completion
                    if "Round" in line and "Saved" in line:
                        try:
                            round_num = int(line.split("Round")[1].split(":")[0].strip())
                            if round_num > round_count:
                                round_count = round_num
                                logger.log_round(round_num, {
                                    "accuracy": 0.0,
                                    "message": f"Round {round_num} completed"
                                })
                                print(f"  [CONFIRMED] Round {round_count}/{NUM_ROUNDS}")
                        except (ValueError, IndexError) as e:
                            print(f"  [WARN] Parse error: {e}")
                            continue

            except Exception as e:
                print(f"  [WARN] Queue error: {e}")

            # Check for timeout (no output for 60 seconds)
            if time.time() - last_output_time > 60:
                print(f"\n[WARN] No output for 60 seconds. Training may be stuck.")
                print(f"  Current round: {round_count}/{NUM_ROUNDS}")

            time.sleep(0.5)

        # Signal thread to stop
        stop_event.set()
        reader_thread.join(timeout=2)

        # Drain remaining output
        while not output_queue.empty():
            line = output_queue.get_nowait()
            if "Training complete" in line:
                print(f" {line.strip()}")
                round_count = NUM_ROUNDS  # Force complete

        # Wait for processes to finish
        print(f"\nCleaning up...")
        for client_id, proc in client_processes:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()

        if round_count >= NUM_ROUNDS:
            logger.end_experiment(success=True)
            print(f"\n[OK] Experiment completed successfully ({round_count} rounds)")
            return True
        else:
            logger.end_experiment(success=False, error=f"Only completed {round_count}/{NUM_ROUNDS} rounds")
            print(f"\n[WARN] Experiment incomplete: {round_count}/{NUM_ROUNDS} rounds")
            return False

    except KeyboardInterrupt:
        print(f"\n\n[ABORT] User interrupted")
        logger.end_experiment(success=False, error="User interrupted")
        return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        logger.end_experiment(success=False, error=str(e))
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Force cleanup
        if server_process and server_process.poll() is None:
            server_process.kill()
        for _, proc in client_processes:
            if proc.poll() is None:
                proc.kill()
        if config_path and config_path.exists():
            config_path.unlink()


def run_all_real_experiments():
    """Run all REAL FL experiments."""
    total = len(MODEL_TYPES) * len(STRATEGIES)

    print(f"\n{'='*70}")
    print(f"REAL FL-NIDS EXPERIMENTS (NOT SIMULATED)")
    print(f"{'='*70}")
    print(f"Models: {', '.join(MODEL_TYPES)}")
    print(f"Strategies: {', '.join(STRATEGIES)}")
    print(f"Rounds: {NUM_ROUNDS} (FIXED)")
    print(f"Clients: {NUM_CLIENTS} (FIXED)")
    print(f"Total experiments: {total}")
    print(f"Estimated time: 15-25 hours (CPU) or 2-4 hours (GPU)")
    print(f"{'='*70}\n")

    input("Press ENTER to start REAL training (this will take hours)...")

    logger = ExperimentLogger(RESULTS_DIR)

    completed = 0
    failed = 0

    for model in MODEL_TYPES:
        for strategy in STRATEGIES:
            success = run_single_experiment(model, strategy, logger)

            if success:
                completed += 1
            else:
                failed += 1

            print(f"\nProgress: {completed + failed}/{total} "
                  f"({completed} success, {failed} failed)")

    print(f"\n{'='*70}")
    print(f"ALL EXPERIMENTS COMPLETE")
    print(f"{'='*70}")
    print(f"Results saved to: {RESULTS_DIR}")
    print(f"Final: {completed} succeeded, {failed} failed out of {total} total")


if __name__ == "__main__":
    try:
        run_all_real_experiments()
    except KeyboardInterrupt:
        print(f"\n\nInterrupted by user. Partial results saved.")
