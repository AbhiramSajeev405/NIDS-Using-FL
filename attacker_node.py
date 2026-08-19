"""
FL-NIDS Physical Testbed — Attacker Node
==========================================
Standalone attacker script for Laptop 2. Reads a scenario profile from config
and injects attack data into country laptops via HTTP or pre-generates CSVs.

Modes:
    offline — Pre-generates attack CSVs into data/simulated_attacks/
    live    — Waits for training to start, then sends attack payloads to
              country laptops via HTTP (/inject endpoint)

Usage:
    python attacker_node.py --config config/physical_config.yaml --scenario gentle_probe
    python attacker_node.py --scenario full_siege --mode live
"""

import os
import sys
import time
import json

# API key for authenticating with attacker_server. Set the same FL_NIDS_API_KEY
# environment variable on both the attacker and country laptops.
_API_KEY = os.environ.get("FL_NIDS_API_KEY", None)
_API_KEY_HEADERS = {"X-API-Key": _API_KEY} if _API_KEY else {}
import random
import argparse
import logging
from pathlib import Path
from datetime import datetime

import yaml
import numpy as np
import pandas as pd
from utils.experiment_manager import set_seed

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("attacker")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("[%(asctime)s] ATTACKER %(levelname)s %(message)s", "%H:%M:%S"))
logger.addHandler(ch)


# ═══════════════════════════════════════════════════════════════════
#   SCENARIO DEFINITIONS
# ═══════════════════════════════════════════════════════════════════

SCENARIOS = {
    "gentle_probe": {
        "description": "Low-intensity reconnaissance scanning",
        "phases": [
            {"rounds": [1, 2, 3], "attack_ratio": 0.05, "attack_type": "port_scan", "targets": [0]},
        ],
    },
    "targeted_strike": {
        "description": "Focused DDoS attack on one country",
        "phases": [
            {"rounds": [2, 3], "attack_ratio": 0.30, "attack_type": "ddos", "targets": [0]},
        ],
    },
    "full_siege": {
        "description": "Simultaneous high-volume attack on all countries",
        "phases": [
            {"rounds": [1, 2, 3, 4, 5], "attack_ratio": 0.40, "attack_type": "mixed", "targets": [0, 1, 2]},
        ],
    },
    "apt_campaign": {
        "description": "Multi-phase APT: recon → establish → exfiltrate",
        "phases": [
            {"rounds": [1, 2], "attack_ratio": 0.05, "attack_type": "port_scan", "targets": [0]},
            {"rounds": [3, 4], "attack_ratio": 0.15, "attack_type": "c2_beacon", "targets": [0, 1]},
            {"rounds": [5, 6, 7], "attack_ratio": 0.35, "attack_type": "exfiltration", "targets": [0, 1, 2]},
        ],
    },
    "insider_threat": {
        "description": "Single compromised client sends poisoned updates",
        "phases": [
            {"rounds": [1, 2, 3, 4, 5], "attack_ratio": 0.20, "attack_type": "label_flip", "targets": [1]},
        ],
    },
    "zero_day": {
        "description": "Novel attack pattern not in training distribution",
        "phases": [
            {"rounds": [3, 4, 5], "attack_ratio": 0.25, "attack_type": "zero_day", "targets": [0, 1, 2]},
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════
#   ATTACK DATA GENERATION
# ═══════════════════════════════════════════════════════════════════

def generate_attack_features(num_samples: int, num_features: int, attack_type: str) -> np.ndarray:
    """Generate synthetic attack traffic features based on attack type."""
    base = np.random.randn(num_samples, num_features)

    if attack_type == "port_scan":
        # High variance in port-related features, low payload
        base[:, 0] *= 5.0    # src_port variance
        base[:, 1] *= 5.0    # dst_port variance
        base[:, 4] = 0.01    # tiny packet size
        base[:, 5] *= 0.1    # short duration

    elif attack_type == "ddos":
        # Extremely high packet rate, uniform source ports
        base[:, 0] = np.random.uniform(49152, 65535, num_samples)  # high src ports
        base[:, 2] = np.random.uniform(100, 1000, num_samples)     # high packet count
        base[:, 4] = np.random.uniform(64, 128, num_samples)       # small uniform packets
        base[:, 5] = np.random.uniform(0.001, 0.01, num_samples)   # very short duration

    elif attack_type == "c2_beacon":
        # Periodic, low-volume, consistent timing
        base[:, 2] = np.random.uniform(1, 5, num_samples)          # low packet count
        base[:, 5] = np.random.uniform(30, 60, num_samples)        # regular interval
        base[:, 6] = np.random.uniform(100, 200, num_samples)      # small payload

    elif attack_type == "exfiltration":
        # Large outbound data, unusual hours
        base[:, 3] = np.random.uniform(10000, 100000, num_samples) # large bytes out
        base[:, 5] = np.random.uniform(60, 300, num_samples)       # longer connections
        base[:, 7] = np.random.uniform(0, 4, num_samples)          # unusual hours

    elif attack_type == "label_flip":
        # Normal-looking features but labels will be flipped
        base = np.random.randn(num_samples, num_features) * 0.5

    elif attack_type == "zero_day":
        # Features from a different distribution entirely
        base = np.random.exponential(2.0, (num_samples, num_features))
        base += np.random.uniform(-1, 1, (num_samples, num_features))

    else:  # "mixed" or unknown
        # Blend multiple patterns
        for i in range(num_samples):
            pattern = random.choice(["ddos", "port_scan", "c2_beacon"])
            if pattern == "ddos":
                base[i, 2] = random.uniform(100, 1000)
                base[i, 4] = random.uniform(64, 128)
            elif pattern == "port_scan":
                base[i, 0] = random.uniform(1, 65535)
                base[i, 1] = random.uniform(1, 65535)
            elif pattern == "c2_beacon":
                base[i, 5] = random.uniform(30, 60)

    return base


def generate_attack_csv(
    client_csv_path: str,
    output_path: str,
    attack_ratio: float,
    attack_type: str,
) -> dict:
    """Generate an attack-injected CSV based on a client's original data."""
    df = pd.read_csv(client_csv_path)
    num_features = len(df.columns) - 1  # Last column is label
    feature_cols = df.columns[:-1].tolist()
    label_col = df.columns[-1]

    num_attack = int(len(df) * attack_ratio)

    if attack_type == "label_flip":
        # Don't add new samples — flip labels of existing benign samples
        benign_mask = df[label_col] == 0
        flip_indices = df[benign_mask].sample(n=min(num_attack, benign_mask.sum())).index
        df_mod = df.copy()
        df_mod.loc[flip_indices, label_col] = 1
        df_mod.to_csv(output_path, index=False)
        return {
            "type": attack_type,
            "original_samples": len(df),
            "modified_labels": len(flip_indices),
        }

    # Generate attack features
    attack_features = generate_attack_features(num_attack, num_features, attack_type)
    attack_df = pd.DataFrame(attack_features, columns=feature_cols)
    attack_df[label_col] = 1  # Mark as attack

    # Combine with original data
    combined = pd.concat([df, attack_df], ignore_index=True).sample(frac=1.0).reset_index(drop=True)
    combined.to_csv(output_path, index=False)

    return {
        "type": attack_type,
        "original_samples": len(df),
        "injected_samples": num_attack,
        "total_samples": len(combined),
        "attack_ratio": num_attack / len(combined),
    }


# ═══════════════════════════════════════════════════════════════════
#   OFFLINE MODE — Pre-generate attack CSVs
# ═══════════════════════════════════════════════════════════════════

def run_offline(config: dict, scenario_name: str):
    """Pre-generate attack CSVs for all phases of a scenario."""
    scenario = SCENARIOS.get(scenario_name)
    if not scenario:
        logger.error(f"Unknown scenario: {scenario_name}")
        logger.info(f"Available: {list(SCENARIOS.keys())}")
        return

    logger.info(f"Scenario: {scenario_name} — {scenario['description']}")

    countries = list(config["network"]["countries"].keys())
    output_dir = PROJECT_ROOT / "data" / "simulated_attacks"
    output_dir.mkdir(parents=True, exist_ok=True)

    for phase_idx, phase in enumerate(scenario["phases"]):
        logger.info(f"Phase {phase_idx + 1}: {phase['attack_type']} | "
                     f"ratio={phase['attack_ratio']} | rounds={phase['rounds']}")

        for target_idx in phase["targets"]:
            if target_idx >= len(countries):
                continue
            country = countries[target_idx]
            clients = config["network"]["countries"][country]["clients"]

            for cid in clients:
                src = PROJECT_ROOT / "data" / "processed" / f"{cid}.csv"
                if not src.exists():
                    logger.warning(f"  {cid}.csv not found, skipping")
                    continue

                out = output_dir / f"{cid}_attack.csv"
                result = generate_attack_csv(
                    str(src), str(out),
                    phase["attack_ratio"], phase["attack_type"]
                )
                logger.info(f"  {cid}: {result}")

    logger.info(f"Attack CSVs saved to {output_dir}")
    logger.info("Done.")


# ═══════════════════════════════════════════════════════════════════
#   LIVE MODE — Real-time injection via HTTP
# ═══════════════════════════════════════════════════════════════════

def run_live(config: dict, scenario_name: str):
    """Wait for training to start, then inject attacks per scenario phases."""
    try:
        import requests
    except ImportError:
        logger.error("requests package required for live mode. Install: pip install requests")
        return

    scenario = SCENARIOS.get(scenario_name)
    if not scenario:
        logger.error(f"Unknown scenario: {scenario_name}")
        return

    logger.info(f"LIVE MODE — Scenario: {scenario_name}")
    logger.info("Waiting for training to start...")

    global_ip = config["network"]["global_server"]["ip"]
    dash_port = config.get("dashboard", {}).get("port", 8050)
    base_url = f"http://{global_ip}:{dash_port}"

    # Wait for dashboard to come up
    while True:
        try:
            resp = requests.get(f"{base_url}/api/state", timeout=3)
            state = resp.json()
            status = state.get("training_status", {}).get("status", "idle")
            if status in ("training", "evaluating"):
                logger.info("Training detected! Beginning attack sequence.")
                break
        except Exception:
            pass
        time.sleep(3)

    countries = list(config["network"]["countries"].keys())

    for phase_idx, phase in enumerate(scenario["phases"]):
        logger.info(f"=== Phase {phase_idx + 1}: {phase['attack_type']} ===")

        # Wait for the right round
        target_round = phase["rounds"][0]
        logger.info(f"Waiting for round {target_round}...")

        while True:
            try:
                resp = requests.get(f"{base_url}/api/state", timeout=3)
                current_round = resp.json().get("training_status", {}).get("current_round", 0)
                if current_round >= target_round:
                    break
            except Exception:
                pass
            time.sleep(2)

        # Inject to targeted countries
        for target_idx in phase["targets"]:
            if target_idx >= len(countries):
                continue
            country = countries[target_idx]
            country_data = config["network"]["countries"][country]
            country_ip = country_data["ip"]
            inject_port = country_data.get("inject_port", 9090)

            clients = country_data["clients"]
            for cid in clients:
                src = PROJECT_ROOT / "data" / "processed" / f"{cid}.csv"
                if not src.exists():
                    continue

                attack_file = PROJECT_ROOT / "data" / "simulated_attacks" / f"{cid}_attack.csv"

                # Generate if not pre-existing
                if not attack_file.exists():
                    generate_attack_csv(
                        str(src), str(attack_file),
                        phase["attack_ratio"], phase["attack_type"]
                    )

                # Send to country laptop
                try:
                    with open(attack_file, "r") as f:
                        csv_data = f.read()
                    resp = requests.post(
                        f"http://{country_ip}:{inject_port}/inject",
                        json={
                            "client_id": cid,
                            "attack_type": phase["attack_type"],
                            "csv_data": csv_data,
                        },
                        headers=_API_KEY_HEADERS,
                        timeout=10,
                    )
                    if resp.ok:
                        logger.info(f"  ✓ Injected {phase['attack_type']} into {cid} @ {country_ip}")
                    else:
                        logger.warning(f"  ✗ Inject failed for {cid}: {resp.status_code}")
                except Exception as e:
                    logger.warning(f"  ✗ Could not reach {country_ip}:{inject_port} — {e}")

        # Log incident to dashboard
        try:
            requests.post(f"{base_url}/api/incident", json={
                "type": "attack",
                "attack_type": phase["attack_type"],
                "description": f"Phase {phase_idx+1}: {phase['attack_type']} injected to {len(phase['targets'])} countries",
                "severity": "high" if phase["attack_ratio"] > 0.2 else "medium",
                "timestamp": datetime.now().isoformat(),
            }, timeout=3)
        except Exception:
            pass

    logger.info("Attack campaign complete.")


# ═══════════════════════════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="FL-NIDS Attacker Node")
    parser.add_argument("--config", type=str, default="config/physical_config.yaml")
    parser.add_argument("--scenario", type=str, default="gentle_probe",
                        choices=list(SCENARIOS.keys()))
    parser.add_argument("--mode", type=str, default="offline",
                        choices=["offline", "live"],
                        help="offline = pre-generate CSVs, live = real-time HTTP injection")
    parser.add_argument("--list-scenarios", action="store_true",
                        help="List all available scenarios and exit")
    args = parser.parse_args()

    if args.list_scenarios:
        print("\nAvailable Attack Scenarios:")
        print("=" * 50)
        for name, info in SCENARIOS.items():
            phases = len(info["phases"])
            print(f"  {name:20s} — {info['description']} ({phases} phase{'s' if phases > 1 else ''})")
        return

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    # Set seed for reproducibility
    seed = config.get('experiment', {}).get('seed', 42)
    set_seed(seed)

    logger.info("=" * 50)
    logger.info("  FL-NIDS ATTACKER NODE")
    logger.info("=" * 50)

    if args.mode == "offline":
        run_offline(config, args.scenario)
    else:
        run_live(config, args.scenario)


if __name__ == "__main__":
    main()
