#!/usr/bin/env python3
"""
Laptop 2: Global Server Launcher
=================================
Run this on the laptop designated as Global Server.

This starts:
- Global Federated Learning Server
- Dashboard for monitoring
"""

import os
import sys
import yaml
import time
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

def get_network_config():
    """Get network configuration."""
    config_path = PROJECT_ROOT / "config" / "distributed_5laptop.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

def start_global_server():
    """Start the Global FL Server."""
    config = get_network_config()

    global_ip = config['network']['global_server']['ip']
    global_port = config['network']['global_server']['port']

    print("="*70)
    print("LAPTOP 2: GLOBAL SERVER")
    print("="*70)
    print(f"Starting Global FL Server on {global_ip}:{global_port}")
    print("="*70)
    print("\nWaiting for country servers to connect...")
    print("Country A: Will connect from 192.168.1.101")
    print("Country B: Will connect from 192.168.1.102")
    print("Country C: Will connect from 192.168.1.103")
    print("="*70)

    # Start server
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "federated" / "server_global.py"),
        "--port", str(global_port),
        "--config", str(config_path),
        "--min_clients", "3"  # 3 country servers
    ]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\nShutting down Global Server...")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("IMPORTANT: Before starting, ensure:")
    print("="*70)
    print("1. All laptops are connected to same network")
    print("2. Firewall allows ports 8080, 8081-8083, 9001-9003")
    print("3. Your IP address is set to: 192.168.1.100")
    print("\nTo check your IP: ipconfig (Windows) or ifconfig (Linux/Mac)")
    print("="*70)

    input("\nPress ENTER when ready to start Global Server...")

    start_global_server()
