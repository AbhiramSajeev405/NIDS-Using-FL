#!/usr/bin/env python3
"""
Laptop 3: Country A Launcher
=============================
Run this on the laptop designated as Country A.

This starts:
- Country A Aggregation Server
- Client_01, Client_02, Client_03
"""

import os
import sys
import yaml
import time
import threading
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

def get_network_config():
    """Get network configuration."""
    config_path = PROJECT_ROOT / "config" / "distributed_5laptop.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

def start_country_server():
    """Start Country A server."""
    config = get_network_config()

    country_ip = config['network']['countries']['country_A']['ip']
    country_port = config['network']['countries']['country_A']['server_port']
    global_ip = config['network']['global_server']['ip']
    global_port = config['network']['global_server']['port']

    print(f"\n[Country A] Starting Country Server on {country_ip}:{country_port}")
    print(f"[Country A] Will connect to Global Server at {global_ip}:{global_port}")

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "federated" / "server_country.py"),
        "--country", "country_A",
        "--port", str(country_port),
        "--global-ip", global_ip,
        "--global-port", str(global_port),
        "--config", str(PROJECT_ROOT / "config" / "distributed_5laptop.yaml")
    ]

    return subprocess.Popen(cmd)

def start_clients():
    """Start Client_01, Client_02, Client_03."""
    config = get_network_config()

    country_ip = config['network']['countries']['country_A']['ip']
    country_port = config['network']['countries']['country_A']['server_port']

    clients = ["Client_01", "Client_02", "Client_03"]
    processes = []

    for cid in clients:
        print(f"[{cid}] Starting client, connecting to Country A at {country_ip}:{country_port}")

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "federated" / "client.py"),
            "--cid", cid,
            "--server-ip", country_ip,
            "--port", str(country_port),
            "--config", str(PROJECT_ROOT / "config" / "distributed_5laptop.yaml")
        ]

        proc = subprocess.Popen(cmd)
        processes.append(proc)
        time.sleep(2)  # Stagger starts

    return processes

def main():
    config = get_network_config()

    print("="*70)
    print("LAPTOP 3: COUNTRY A")
    print("="*70)
    print(f"Your IP: {config['network']['countries']['country_A']['ip']}")
    print("Clients: Client_01, Client_02, Client_03")
    print("="*70)
    print("\nIMPORTANT:")
    print("1. Ensure Global Server (Laptop 2) is already running")
    print("2. Your IP is set to: 192.168.1.101")
    print("3. Firewall allows ports 9001, 8081")
    print("="*70)

    input("\nPress ENTER when ready to start Country A...")

    # Start country server
    print("\n[Step 1/2] Starting Country A Server...")
    country_proc = start_country_server()

    print("\n[Step 2/2] Waiting 5 seconds for server to initialize...")
    time.sleep(5)

    print("\n[Step 2/2] Starting Clients...")
    client_procs = start_clients()

    print("\n" + "="*70)
    print("COUNTRY A RUNNING")
    print("="*70)
    print("Country Server: Running")
    print("Clients: Client_01, Client_02, Client_03")
    print("\nPress Ctrl+C to stop all processes...")
    print("="*70)

    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down Country A...")
        country_proc.terminate()
        for proc in client_procs:
            proc.terminate()

if __name__ == "__main__":
    main()
