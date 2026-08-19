#!/usr/bin/env python3
"""
Distributed FL System - Automated Setup Script
==============================================

This script automates the setup process for the 5-laptop distributed system.

Run this script on EACH laptop to:
1. Detect which laptop it's running on
2. Configure network settings
3. Test connectivity
4. Start the appropriate role
"""

import os
import sys
import yaml
import socket
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
CONFIG_PATH = PROJECT_ROOT / "distributed_5laptop.yaml"

# ANSI Color Codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(title):
    """Print a formatted header."""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def print_success(msg):
    print(f"{GREEN}[✓]{RESET} {msg}")

def print_error(msg):
    print(f"{RED}[✗]{RESET} {msg}")

def print_warning(msg):
    print(f"{YELLOW}[!]{RESET} {msg}")

def print_info(msg):
    print(f"{BLUE}[i]{RESET} {msg}")

def get_current_ip():
    """Get current IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return None

def detect_laptop_role():
    """Detect which laptop this is based on IP."""
    current_ip = get_current_ip()

    if not current_ip:
        return None, "Cannot detect IP address"

    expected_roles = {
        "192.168.1.100": ("Laptop2_GlobalServer", "Global Server"),
        "192.168.1.101": ("Laptop3_CountryA", "Country A"),
        "192.168.1.102": ("Laptop4_CountryB", "Country B"),
        "192.168.1.103": ("Laptop5_CountryC", "Country C"),
        "192.168.1.104": ("Laptop1_Attacker", "Attacker")
    }

    return expected_roles.get(current_ip), current_ip

def check_connectivity(target_ips):
    """Check connectivity to other laptops."""
    print_header("Step 3: Testing Network Connectivity")

    results = {}
    for name, ip in target_ips.items():
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", ip],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print_success(f"{name} ({ip}): Reachable")
                results[ip] = True
            else:
                print_error(f"{name} ({ip}): NOT reachable")
                results[ip] = False
        except:
            print_error(f"{name} ({ip}): Ping failed")
            results[ip] = False

    return results

def check_required_files(role):
    """Check if required files exist."""
    print_header("Step 4: Checking Required Files")

    required_files = [
        "federated/server_global.py",
        "federated/server_country.py",
        "federated/client.py",
        "models/factory.py",
        "config/distributed_5laptop.yaml"
    ]

    # Add client data files for Country laptops
    client_data = []
    if role == "Laptop3_CountryA":
        client_data = ["data/processed/Client_01.csv", "data/processed/Client_02.csv", "data/processed/Client_03.csv"]
    elif role == "Laptop4_CountryB":
        client_data = ["data/processed/Client_04.csv", "data/processed/Client_05.csv", "data/processed/Client_06.csv"]
    elif role == "Laptop5_CountryC":
        client_data = ["data/processed/Client_07.csv", "data/processed/Client_08.csv", "data/processed/Client_09.csv"]

    all_files = required_files + client_data
    missing_files = []

    for file in all_files:
        file_path = PROJECT_ROOT / file
        if file_path.exists():
            print_success(f"{file}")
        else:
            print_error(f"{file} - MISSING")
            missing_files.append(file)

    return missing_files

def check_ports(role):
    """Check if required ports are free."""
    print_header("Step 5: Checking Network Ports")

    port_mapping = {
        "Laptop2_GlobalServer": [8080, 8501],
        "Laptop3_CountryA": [9001, 8081],
        "Laptop4_CountryB": [9002, 8082],
        "Laptop5_CountryC": [9003, 8083],
        "Laptop1_Attacker": [9999]
    }

    required_ports = port_mapping.get(role, [])

    for port in required_ports:
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True
            )
            if f":{port}" in result.stdout:
                print_warning(f"Port {port}: In use")
            else:
                print_success(f"Port {port}: Available")
        except:
            print_warning(f"Port {port}: Cannot verify")

def show_startup_instructions(role, role_name):
    """Show startup instructions based on role."""
    print_header("Step 6: Startup Instructions")

    startup_order = {
        "Laptop2_GlobalServer": "START FIRST (Priority 1)",
        "Laptop3_CountryA": "START SECOND (Priority 2)",
        "Laptop4_CountryB": "START SECOND (Priority 2)",
        "Laptop5_CountryC": "START SECOND (Priority 2)",
        "Laptop1_Attacker": "START LAST (Optional)"
    }

    print_info(f"Role: {role_name}")
    print_info(f"Startup: {startup_order.get(role, 'Unknown')}")
    print()

    script_mapping = {
        "Laptop2_GlobalServer": "start_laptop2_global_server.py",
        "Laptop3_CountryA": "start_laptop3_country_a.py",
        "Laptop4_CountryB": "start_laptop4_country_b.py",
        "Laptop5_CountryC": "start_laptop5_country_c.py",
        "Laptop1_Attacker": "start_laptop1_attacker.py"
    }

    startup_script = script_mapping.get(role)

    if startup_script:
        print(f"{BOLD}To start this laptop:{RESET}")
        print(f"  cd {PROJECT_ROOT}")
        print(f"  python {startup_script}")
        print()

        if role == "Laptop2_GlobalServer":
            print(f"{YELLOW}Wait for all 3 countries to connect before starting training{RESET}")
        elif role in ["Laptop3_CountryA", "Laptop4_CountryB", "Laptop5_CountryC"]:
            print(f"{YELLOW}Ensure Laptop 2 (Global Server) is running first{RESET}")
        elif role == "Laptop1_Attacker":
            print(f"{YELLOW}Ensure Laptops 2-5 are running before attacking{RESET}")

def ask_to_start(role):
    """Ask if user wants to start the system."""
    print_header("Step 7: Ready to Start")

    response = input(f"{BOLD}Start the system now? (yes/no): {RESET}").strip().lower()

    if response in ['yes', 'y']:
        script_mapping = {
            "Laptop2_GlobalServer": "start_laptop2_global_server.py",
            "Laptop3_CountryA": "start_laptop3_country_a.py",
            "Laptop4_CountryB": "start_laptop4_country_b.py",
            "Laptop5_CountryC": "start_laptop5_country_c.py",
            "Laptop1_Attacker": "start_laptop1_attacker.py"
        }

        startup_script = script_mapping.get(role)
        if startup_script:
            script_path = PROJECT_ROOT / startup_script

            print_info(f"Starting {startup_script}...")
            time.sleep(2)

            try:
                subprocess.run([sys.executable, str(script_path)], check=True)
            except KeyboardInterrupt:
                print_info("\nSystem stopped by user")
            except Exception as e:
                print_error(f"Failed to start: {e}")
        else:
            print_error(f"No startup script found for {role}")
    else:
        print_info("Setup complete. Run manually when ready.")

def setup_wizard():
    """Main setup wizard."""
    print_header("DISTRIBUTED FL SYSTEM - AUTOMATED SETUP WIZARD")

    print_info("This wizard will:")
    print("  1. Detect your laptop's role")
    print("  2. Configure network settings")
    print("  3. Test connectivity to other laptops")
    print("  4. Verify required files")
    print("  5. Check network ports")
    print("  6. Provide startup instructions")
    print()

    input(f"{BOLD}Press ENTER to begin...{RESET}")

    # Step 1: Detect role
    print_header("Step 1: Detecting Laptop Role")

    (role, role_name), current_ip = detect_laptop_role()

    if role:
        print_success(f"Detected: {role_name}")
        print_info(f"IP Address: {current_ip}")
        print_info(f"Role: {role}")
    else:
        print_error(f"Could not detect laptop role")
        print_info(f"Current IP: {current_ip or 'Unknown'}")
        print_warning("Please configure static IP first:")
        print("  Laptop 2 (Global):  192.168.1.100")
        print("  Laptop 3 (Country A): 192.168.1.101")
        print("  Laptop 4 (Country B): 192.168.1.102")
        print("  Laptop 5 (Country C): 192.168.1.103")
        print("  Laptop 1 (Attacker): 192.168.1.104")
        print()
        print_warning("Set static IP and run this script again.")
        return

    # Step 2: Verify config
    print_header("Step 2: Verifying Configuration")

    if CONFIG_PATH.exists():
        print_success(f"Config found: {CONFIG_PATH}")

        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)

        print_info("Network Configuration:")
        print(f"  Global Server: {config['network']['global_server']['ip']}")
        print(f"  Country A: {config['network']['countries']['country_A']['ip']}")
        print(f"  Country B: {config['network']['countries']['country_B']['ip']}")
        print(f"  Country C: {config['network']['countries']['country_C']['ip']}")
        print(f"  Attacker: {config['network']['attacker']['ip']}")
    else:
        print_error("Config file not found!")
        print_warning(f"Expected: {CONFIG_PATH}")
        return

    # Step 3: Connectivity test
    target_ips = {
        "Global Server": config['network']['global_server']['ip'],
        "Country A": config['network']['countries']['country_A']['ip'],
        "Country B": config['network']['countries']['country_B']['ip'],
        "Country C": config['network']['countries']['country_C']['ip'],
        "Attacker": config['network']['attacker']['ip']
    }

    # Remove self from ping list
    target_ips = {k: v for k, v in target_ips.items() if v != current_ip}

    connectivity = check_connectivity(target_ips)

    failed = [ip for ip, success in connectivity.items() if not success]
    if failed:
        print_warning(f"\nSome laptops are not reachable:")
        print("  This is OK if they haven't started yet")
        print("  Ensure all laptops are configured with correct IPs")

    # Step 4: Check files
    missing = check_required_files(role)

    if missing:
        print_error(f"\nMissing {len(missing)} required files!")
        print_warning("Copy entire CUDIND folder to this laptop")
        return

    # Step 5: Check ports
    check_ports(role)

    # Step 6: Show instructions
    show_startup_instructions(role, role_name)

    # Step 7: Ask to start
    ask_to_start(role)

if __name__ == "__main__":
    try:
        setup_wizard()
    except KeyboardInterrupt:
        print_info("\n\nSetup interrupted by user")
    except Exception as e:
        print_error(f"\nSetup failed: {e}")
        import traceback
        traceback.print_exc()
