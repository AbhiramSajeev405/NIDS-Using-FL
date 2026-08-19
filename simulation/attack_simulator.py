import os
import pandas as pd
import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PROCESSED_DIR = os.path.join(_PROJECT_ROOT, "data", "processed")

def simulate_attack(client_id, processed_dir=None, attack_ratio=0.3):
    """
    Simulates an attack phase by reading the normal processed data for a client,
    and injecting rows from the Attacker.csv.
    """
    if processed_dir is None:
        processed_dir = _DEFAULT_PROCESSED_DIR
    client_file = os.path.join(processed_dir, f"{client_id}.csv")
    attacker_file = os.path.join(processed_dir, "Attacker.csv")

    if not os.path.exists(client_file) or not os.path.exists(attacker_file):
        raise FileNotFoundError(f"Missing {client_file} or {attacker_file}. Did you run feature_unifier.py?")

    df_normal = pd.read_csv(client_file)
    df_attack = pd.read_csv(attacker_file)

    # Determine how many attack rows to inject
    num_attacks = int(len(df_normal) * attack_ratio)

    # Sample randomly from attacker file
    if num_attacks > len(df_attack):
        # Sample with replacement if we need more attacks than exist
        injected_attacks = df_attack.sample(n=num_attacks, replace=True, random_state=42)
    else:
        injected_attacks = df_attack.sample(n=num_attacks, random_state=42)

    # Concatenate and shuffle
    simulated_traffic = pd.concat([df_normal, injected_attacks]).sample(frac=1, random_state=42).reset_index(drop=True)

    # Save to a temporary file for evaluation
    sim_dir = os.path.join(os.path.dirname(processed_dir), "simulated_attacks")
    os.makedirs(sim_dir, exist_ok=True)
    out_path = os.path.join(sim_dir, f"{client_id}_attack.csv")
    simulated_traffic.to_csv(out_path, index=False)
    print(f"[{client_id}] Injected {num_attacks} malicious flows. Saved to {out_path}")
    return out_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Attack Simulator")
    parser.add_argument("--client", type=str, required=True, help="Client ID to simulate attack against")
    parser.add_argument("--ratio", type=float, default=0.3, help="Ratio of attack rows relative to normal dataset size")
    args = parser.parse_args()
    simulate_attack(args.client, attack_ratio=args.ratio)
