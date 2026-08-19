#!/usr/bin/env python3
"""
LSCUDAPORT - Manual Attack Launcher
====================================
Interactive terminal attack controller - FULL manual control.
Click a button to attack, choose target, choose attack type.
"""

import os
import sys
import time
import json
import yaml
import requests
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Import attack generation from attacker_node
sys.path.insert(0, str(PROJECT_ROOT))
from attacker_node import generate_attack_features, SCENARIOS

# API Key check
_API_KEY = os.environ.get("FL_NIDS_API_KEY", None)
_HEADERS = {"X-API-Key": _API_KEY} if _API_KEY else {}


def load_config():
    config_path = PROJECT_ROOT / "config" / "physical_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def check_dashboard():
    """Check if dashboard is running and return status."""
    config = load_config()
    port = config.get("dashboard", {}).get("port", 456)
    url = f"http://127.0.0.1:{port}"

    try:
        resp = requests.get(f"{url}/api/state", timeout=2)
        state = resp.json()
        return True, state
    except requests.RequestException as e:
        return False, str(e)


def generate_and_send_attack(client_id, attack_type, attack_ratio):
    """Generate attack data and send to country server."""
    config = load_config()

    # Find which country this client belongs to
    target_ip = None
    inject_port = None

    for country_key, country_data in config.get("network", {}).get("countries", {}).items():
        if client_id in country_data.get("clients", []):
            target_ip = country_data.get("ip", "127.0.0.1")
            inject_port = country_data.get("inject_port", 9091)
            break

    if not target_ip or not inject_port:
        print(f"ERROR: Could not find country config for {client_id}")
        return False

    # Load original client data
    client_file = PROJECT_ROOT / "data" / "processed" / f"{client_id}.csv"
    if not client_file.exists():
        print(f"ERROR: Client file not found: {client_file}")
        return False

    import pandas as pd
    df = pd.read_csv(client_file)
    num_features = len(df.columns) - 1
    feature_cols = df.columns[:-1].tolist()
    label_col = df.columns[-1]

    # Generate attack samples
    num_attack = int(len(df) * attack_ratio)
    attack_features = generate_attack_features(num_attack, num_features, attack_type)

    attack_df = pd.DataFrame(attack_features, columns=feature_cols)
    attack_df[label_col] = 1  # Mark as attack

    # Combine with original
    combined = pd.concat([df, attack_df], ignore_index=True).sample(frac=1.0).reset_index(drop=True)

    # Send to country server
    csv_data = combined.to_csv(index=False)

    try:
        resp = requests.post(
            f"http://{target_ip}:{inject_port}/inject",
            json={
                "client_id": client_id,
                "attack_type": attack_type,
                "csv_data": csv_data
            },
            headers=_HEADERS,
            timeout=10
        )

        if resp.status_code == 200:
            # Log incident to dashboard
            try:
                dashboard_port = config.get("dashboard", {}).get("port", 456)
                requests.post(
                    f"http://127.0.0.1:{dashboard_port}/api/incident",
                    json={
                        "client_id": client_id,
                        "attack_type": attack_type,
                        "description": f"Manual attack: {attack_type} on {client_id}",
                        "severity": "high" if attack_ratio > 0.2 else "medium",
                        "status": "Investigating",
                        "timestamp": datetime.now().isoformat()
                    },
                    timeout=3
                )
            except requests.RequestException:
                pass  # Dashboard might not be running

            return True
        else:
            print(f"ERROR: Server returned {resp.status_code}")
            return False

    except requests.RequestException as e:
        print(f"ERROR: Could not reach {target_ip}:{inject_port} - {e}")
        return False


def print_menu():
    """Print interactive menu."""
    print("\n" + "=" * 60)
    print("  LSCUDAPORT - MANUAL ATTACK CONTROLLER")
    print("=" * 60)
    print()
    print("  Attack Types:")
    print("    1.  port_scan      - Network reconnaissance (low intensity)")
    print("    2.  ddos           - DDoS flood attack (high intensity)")
    print("    3.  c2_beacon      - Command & control (C2) traffic")
    print("    4.  exfiltration   - Data theft pattern")
    print("    5.  label_flip     - Poisoning attack (flip benign→attack)")
    print("    6.  zero_day       - Novel attack pattern")
    print()
    print("  Target Clients:")
    print("    7.  Client_01 (Country A) - Bot-IoT")
    print("    8.  Client_02 (Country A) - CIC-IDS-2017")
    print("    9.  Client_03 (Country A) - Edge-IIoTSet")
    print("    10. Client_04 (Country B) - IDS2018")
    print("    11. Client_05 (Country B) - Scenario-B")
    print("    12. Client_06 (Country B) - UNSW-NB15")
    print("    13. Client_07 (Country C) - CIC-PortScan")
    print("    14. Client_08 (Country C) - IDS2018-Day2")
    print("    15. Client_09 (Country C) - TON-IoT")
    print()
    print("  Attack Ratio (how much of client data becomes attack):")
    print("    16. 10%  (Light)")
    print("    17. 30%  (Medium)")
    print("    18. 50%  (Heavy)")
    print()
    print("  Other:")
    print("    19. Check Dashboard Status")
    print("    20. View Recent Incidents")
    print("    21. Restore All Original Data")
    print()
    print("    0.  Exit")
    print()
    print("=" * 60)


def main():
    print()
    print(" MANUAL ATTACK CONTROLLER")
    print()
    print(" Launch attacks interactively during your presentation.")
    print(" Dashboard updates IN REAL-TIME when attack is sent.")
    print()
    input("Press ENTER to start...")

    while True:
        print_menu()

        choice = input("Select option (0-21): ").strip()

        # Attack Type Selection
        attack_type = None
        if choice == "1": attack_type = "port_scan"
        elif choice == "2": attack_type = "ddos"
        elif choice == "3": attack_type = "c2_beacon"
        elif choice == "4": attack_type = "exfiltration"
        elif choice == "5": attack_type = "label_flip"
        elif choice == "6": attack_type = "zero_day"

        # Client Selection
        client_id = None
        if choice == "7": client_id = "Client_01"
        elif choice == "8": client_id = "Client_02"
        elif choice == "9": client_id = "Client_03"
        elif choice == "10": client_id = "Client_04"
        elif choice == "11": client_id = "Client_05"
        elif choice == "12": client_id = "Client_06"
        elif choice == "13": client_id = "Client_07"
        elif choice == "14": client_id = "Client_08"
        elif choice == "15": client_id = "Client_09"

        # Attack Ratio Selection
        attack_ratio = None
        if choice == "16": attack_ratio = 0.10
        elif choice == "17": attack_ratio = 0.30
        elif choice == "18": attack_ratio = 0.50

        if choice == "0":
            print("\nExiting attack controller...")
            break

        elif choice == "19":
            # Check dashboard status
            online, info = check_dashboard()
            if online:
                status = info.get("training_status", {}).get("status", "unknown")
                round_num = info.get("training_status", {}).get("current_round", 0)
                print(f"\n  Dashboard: ONLINE")
                print(f"  Status: {status}")
                print(f"  Round: {round_num}")
            else:
                print(f"\n  Dashboard: OFFLINE")
                print(f"  Error: {info}")
            input("\nPress ENTER to continue...")

        elif choice == "20":
            # View recent incidents
            try:
                config = load_config()
                port = config.get("dashboard", {}).get("port", 456)
                resp = requests.get(f"http://127.0.0.1:{port}/api/incident", timeout=3)
                if resp.ok and "incidents" in resp.json():
                    incidents = resp.json()["incidents"][-10:]
                    print(f"\n  Recent Incidents ({len(incidents)}):")
                    for inc in reversed(incidents):
                        print(f"    - {inc.get('client_id')} | {inc.get('attack_type')} | {inc.get('status')}")
                else:
                    print("\n  No recent incidents or dashboard offline")
            except Exception as e:
                print(f"\n  Error: {e}")
            input("\nPress ENTER to continue...")

        elif choice == "21":
            # Restore all data
            confirm = input("\n  WARNING: This will overwrite all attack data!")
            confirm2 = input("  Restore all clients to original? (yes/no): ")
            if confirm2.lower() == "yes":
                for cid in ["Client_01", "Client_02", "Client_03", "Client_04", "Client_05",
                           "Client_06", "Client_07", "Client_08", "Client_09"]:
                    try:
                        config = load_config()
                        for country_key, country_data in config.get("network", {}).get("countries", {}).items():
                            if cid in country_data.get("clients", []):
                                target_ip = country_data.get("ip", "127.0.0.1")
                                inject_port = country_data.get("inject_port", 9091)
                                resp = requests.post(
                                    f"http://{target_ip}:{inject_port}/restore",
                                    json={"client_id": cid},
                                    headers=_HEADERS,
                                    timeout=10
                                )
                                if resp.ok:
                                    print(f"    Restored {cid}")
                                else:
                                    print(f"    Failed {cid}: {resp.status_code}")
                                break
                    except Exception as e:
                        print(f"    Error {cid}: {e}")
                print("\n  Restore complete")
            input("\nPress ENTER to continue...")

        elif attack_type and client_id:
            # Direct attack selection (attack type + client)
            print(f"\n  Attack Type: {attack_type}")
            print(f"  Target: {client_id}")
            confirm = input("  Launch attack? (yes/no): ")
            if confirm.lower() == "yes":
                print(f"\n  Generating {attack_type} attack data...")
                print(f"  Sending to {client_id}...")
                success = generate_and_send_attack(client_id, attack_type, 0.30)
                if success:
                    print(f"\n  ✓ Attack successfully INJECTED!")
                    print(f"  Dashboard will show incident immediately.")
                else:
                    print(f"\n  ✗ Attack failed - check logs above")
            input("\nPress ENTER to continue...")

        elif attack_type:
            # Only attack type selected - ask for client
            print(f"\n  Attack type selected: {attack_type}")
            print("  Now select a client (7-15 or type name):")
            client_choice = input("  Client: ").strip()
            client_map = {
                "7": "Client_01", "8": "Client_02", "9": "Client_03",
                "10": "Client_04", "11": "Client_05", "12": "Client_06",
                "13": "Client_07", "14": "Client_08", "15": "Client_09"
            }
            client_id = client_map.get(client_choice)
            if not client_id:
                print(f"  Invalid client selection")
                continue

            # Ask for ratio
            ratio_choice = input("  Attack ratio (16=10%, 17=30%, 18=50%): ").strip()
            ratio_map = {"16": 0.10, "17": 0.30, "18": 0.50}
            attack_ratio = ratio_map.get(ratio_choice, 0.30)

            confirm = input(f"\n  Launch {attack_type} on {client_id} ({attack_ratio*100:.0f}%)? (yes/no): ")
            if confirm.lower() == "yes":
                print(f"\n  Generating {attack_type} attack data...")
                print(f"  Sending to {client_id}...")
                success = generate_and_send_attack(client_id, attack_type, attack_ratio)
                if success:
                    print(f"\n  ✓ Attack successfully INJECTED!")
                    print(f"  Dashboard will show incident immediately.")
                    print(f"  Watch for weight divergence spikes!")
                else:
                    print(f"\n  ✗ Attack failed - check logs above")
            input("\nPress ENTER to continue...")

        elif client_id:
            # Only client selected - ask for attack type
            print(f"\n  Client selected: {client_id}")
            print("  Now select attack type (1-6 or type name):")
            attack_choice = input("  Attack type: ").strip()
            attack_map = {
                "1": "port_scan", "2": "ddos", "3": "c2_beacon",
                "4": "exfiltration", "5": "label_flip", "6": "zero_day"
            }
            attack_type = attack_map.get(attack_choice)
            if not attack_type:
                print(f"  Invalid attack type selection")
                continue

            ratio_choice = input("  Attack ratio (16=10%, 17=30%, 18=50%): ").strip()
            ratio_map = {"16": 0.10, "17": 0.30, "18": 0.50}
            attack_ratio = ratio_map.get(ratio_choice, 0.30)

            confirm = input(f"\n  Launch {attack_type} on {client_id} ({attack_ratio*100:.0f}%)? (yes/no): ")
            if confirm.lower() == "yes":
                print(f"\n  Generating {attack_type} attack data...")
                print(f"  Sending to {client_id}...")
                success = generate_and_send_attack(client_id, attack_type, attack_ratio)
                if success:
                    print(f"\n  ✓ Attack successfully INJECTED!")
                    print(f"  Dashboard will show incident immediately.")
                else:
                    print(f"\n  ✗ Attack failed")
            input("\nPress ENTER to continue...")

        else:
            print("\n  Please select specific attack type, client, or use menu options 19-21")
            input("Press ENTER to continue...")


if __name__ == "__main__":
    main()
