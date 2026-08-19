#!/usr/bin/env python3
"""
Laptop 1: Attacker Node
========================
Run this on the laptop designated as Attacker.

This can:
- Launch attacks against country servers
- Simulate malicious clients
- Send poisoned updates
"""

import os
import sys
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

if os.path.exists(PROJECT_ROOT / "attacker_node.py"):
    from attacker_node import main as attacker_main

def get_network_config():
    """Get network configuration."""
    config_path = PROJECT_ROOT / "config" / "distributed_5laptop.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

def show_attack_menu():
    """Display attack options."""
    config = get_network_config()

    print("="*70)
    print("LAPTOP 1: ATTACKER NODE")
    print("="*70)
    print(f"Your IP: {config['network']['attacker']['ip']}")
    print("="*70)
    print("\nTarget Country Servers:")
    print(f"  Country A: {config['network']['countries']['country_A']['ip']}")
    print(f"  Country B: {config['network']['countries']['country_B']['ip']}")
    print(f"  Country C: {config['network']['countries']['country_C']['ip']}")
    print("="*70)
    print("\nAttack Options:")
    print("  1. Launch DDoS attack")
    print("  2. Launch data poisoning")
    print("  3. Launch model poisoning")
    print("  4. Launch communication intercept")
    print("  5. Run interactive attacker_console")
    print("="*70)

def main():
    config = get_network_config()

    print("\n" + "="*70)
    print("IMPORTANT: Before starting, ensure:")
    print("="*70)
    print("1. All other laptops (2-5) are running")
    print("2. Your IP is set to: 192.168.1.104")
    print("3. Firewall allows outgoing connections")
    print("="*70)

    input("\nPress ENTER to continue...")

    show_attack_menu()

    choice = input("\nSelect option (1-5): ").strip()

    if choice == "5":
        # Run existing attacker console if available
        if os.path.exists(PROJECT_ROOT / "attacker_node.py"):
            print("\nStarting attacker console...")
            attacker_main()
        else:
            print("\nError: attacker_node.py not found")
            print("Check if CUDIND folder has attacker_node.py")
    else:
        print(f"\nOption {choice} selected")
        print("Attack implementation depends on your specific requirements")
        print("Edit this script to add custom attack logic")

if __name__ == "__main__":
    main()
