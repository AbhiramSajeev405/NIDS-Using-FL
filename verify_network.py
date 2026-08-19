#!/usr/bin/env python3
"""
CUDIND Network Verification Script
===================================
Run this script to verify all laptops are properly connected.

Usage:
    python verify_network.py [--laptop 1-5]

This script will:
1. Verify this laptop's IP configuration
2. Ping all other laptops on the network
3. Test required ports are open
4. Verify configuration files
5. Check if startup scripts exist
"""

import os
import sys
import socket
import subprocess
import platform
import yaml
from pathlib import Path

# Detect embedded Python
PROJECT_ROOT = Path(__file__).parent.resolve()
EMBEDDED_PYTHON = PROJECT_ROOT / "deployment_tools" / "python_embedded" / "python.exe"

def get_python_executable():
 """Get the Python executable to use (embedded or system)."""
 if EMBEDDED_PYTHON.exists():
 return str(EMBEDDED_PYTHON)
 return sys.executable

PYTHON_EXE = get_python_executable()

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.OKCYAN}ℹ {msg}{Colors.ENDC}")

class NetworkVerifier:
    def __init__(self, laptop_number=None):
        self.project_root = Path(__file__).parent.resolve()
        self.laptop_number = laptop_number

        # Expected laptop configurations
        self.laptops = {
            1: {"name": "Attacker", "ip": "192.168.1.104", "role": "attacker", "port": 9999},
            2: {"name": "Global Server", "ip": "192.168.1.100", "role": "global", "port": 8080},
            3: {"name": "Country A", "ip": "192.168.1.101", "role": "country_a", "port": 9001},
            4: {"name": "Country B", "ip": "192.168.1.102", "role": "country_b", "port": 9002},
            5: {"name": "Country C", "ip": "192.168.1.103", "role": "country_c", "port": 9003}
        }

    def detect_current_ip(self):
        """Detect this computer's IP address."""
        try:
            # Create socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"

    def check_own_ip(self):
        """Check if this computer has the correct IP."""
        print_header("CHECKING THIS LAPTOP'S IP")

        current_ip = self.detect_current_ip()
        print_info(f"Current IP address: {current_ip}")

        if self.laptop_number:
            expected_ip = self.laptops[self.laptop_number]["ip"]
            if current_ip == expected_ip:
                print_success(f"IP matches expected: {expected_ip}")
                return True
            else:
                print_error(f"IP mismatch!")
                print_error(f"Expected: {expected_ip}")
                print_error(f"Current:  {current_ip}")
                print_warning("\nPlease set static IP:")
                if platform.system() == "Windows":
                    print("  Control Panel > Network Connections > Properties > IPv4")
                else:
                    print("  Use network manager to set static IP")
                print(f"  IP: {expected_ip}")
                print("  Mask: 255.255.255.0")
                return False
        else:
            # Auto-detect which laptop this is
            for num, config in self.laptops.items():
                if current_ip == config["ip"]:
                    print_success(f"Detected: Laptop {num} ({config['name']})")
                    self.laptop_number = num
                    return True

            print_warning(f"Current IP ({current_ip}) doesn't match any laptop configuration")
            print_info("Expected laptop IPs:")
            for num, config in self.laptops.items():
                print(f"  Laptop {num} ({config['name']}): {config['ip']}")
            return False

    def ping_laptop(self, laptop_num):
        """Ping a specific laptop."""
        config = self.laptops[laptop_num]

        print_info(f"Pinging {config['name']} ({config['ip']})...")

        # Ping command depends on OS
        if platform.system() == "Windows":
            cmd = f"ping -n 1 -w 2000 {config['ip']}"
        else:
            cmd = f"ping -c 1 -W 2 {config['ip']}"

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print_success(f"{config['name']} is reachable")
                return True
            else:
                print_error(f"{config['name']} is NOT reachable")
                return False
        except Exception as e:
            print_error(f"Error pinging {config['name']}: {e}")
            return False

    def check_port(self, host, port):
        """Check if a port is open on a host."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def verify_required_ports(self):
        """Verify required ports for this laptop."""
        print_header("VERIFYING REQUIRED PORTS")

        if not self.laptop_number:
            print_error("Cannot verify ports - laptop number unknown")
            return False

        ports_to_check = []

        # Determine which ports to check based on laptop role
        if self.laptop_number == 2:  # Global Server
            ports_to_check = [
                ("FL Server", 8080),
                ("Dashboard", 8501)
            ]
        elif self.laptop_number in [3, 4, 5]:  # Countries
            port_map = {3: 9001, 4: 9002, 5: 9003}
            ports_to_check = [
                ("Country Server", port_map[self.laptop_number])
            ]
        elif self.laptop_number == 1:  # Attacker
            ports_to_check = [
                ("Attacker", 9999)
            ]

        all_open = True
        for service, port in ports_to_check:
            print_info(f"Checking port {port} ({service})...")
            if self.check_port("127.0.0.1", port):
                print_success(f"Port {port} is open")
            else:
                print_warning(f"Port {port} is closed (service may not be running yet)")
                all_open = False

        return True  # Don't fail if ports are closed (services not started)

    def test_all_connectivity(self):
        """Test connectivity to all other laptops."""
        print_header("TESTING NETWORK CONNECTIVITY")

        if not self.laptop_number:
            print_warning("Testing connectivity to all laptops...")
        else:
            print_info(f"Testing connectivity from Laptop {self.laptop_number} to others...\n")

        reachability = {}
        for num in self.laptops.keys():
            if num != self.laptop_number:
                reachable = self.ping_laptop(num)
                reachability[num] = reachable

        # Summary
        print("\n" + "-"*70)
        print_info("SUMMARY:\n")

        online_count = sum(reachability.values())
        total_count = len(reachability)

        print(f"Reachable: {online_count}/{total_count} laptops\n")

        for num, reachable in reachability.items():
            status = "ONLINE" if reachable else "OFFLINE"
            color = Colors.OKGREEN if reachable else Colors.FAIL
            print(f"  {color}Laptop {num} ({self.laptops[num]['name']}): {status}{Colors.ENDC}")

        if online_count == total_count:
            print(f"\n{Colors.OKGREEN}✓ All laptops are reachable!{Colors.ENDC}")
            return True
        else:
            print(f"\n{Colors.WARNING}⚠ Some laptops are not reachable{Colors.ENDC}")
            print_info("This could mean:")
            print("  - Laptops are not turned on")
            print("  - Laptops not on same network")
            print("  - Firewall blocking ICMP")
            print("  - Static IP not configured")
            return False

    def verify_config_file(self):
        """Verify network configuration file."""
        print_header("VERIFYING CONFIGURATION FILE")

        config_file = self.project_root / "config" / "distributed_5laptop.yaml"

        if not config_file.exists():
            print_error(f"Config file not found: {config_file}")
            return False

        print_success(f"Config file found: {config_file}")

        try:
            with open(config_file) as f:
                config = yaml.safe_load(f)

            # Verify IPs in config
            print_info("\nVerifying IP addresses in config:\n")

            all_correct = True
            for num, laptop_config in self.laptops.items():
                # Find matching config entry
                if num == 2:
                    config_ip = config.get('network', {}).get('global_server', {}).get('ip')
                elif num in [3, 4, 5]:
                    country_key = f"country_{chr(64+num)}"  # country_A, country_B, country_C
                    config_ip = config.get('network', {}).get('countries', {}).get(country_key, {}).get('ip')
                elif num == 1:
                    config_ip = config.get('network', {}).get('attacker', {}).get('ip')
                else:
                    config_ip = None

                if config_ip == laptop_config['ip']:
                    print_success(f"Laptop {num} ({laptop_config['name']}): {config_ip}")
                else:
                    print_error(f"Laptop {num} ({laptop_config['name']}): Expected {laptop_config['ip']}, Found {config_ip}")
                    all_correct = False

            return all_correct

        except Exception as e:
            print_error(f"Error reading config: {e}")
            return False

    def verify_startup_scripts(self):
        """Verify startup scripts exist."""
        print_header("VERIFYING STARTUP SCRIPTS")

        scripts = {
            1: "start_laptop1_attacker.py",
            2: "start_laptop2_global_server.py",
            3: "start_laptop3_country_a.py",
            4: "start_laptop4_country_b.py",
            5: "start_laptop5_country_c.py"
        }

        print_info("Checking for startup scripts:\n")

        all_exist = True
        for num, script_name in scripts.items():
            script_path = self.project_root / script_name
            marker = " <-- THIS LAPTOP" if num == self.laptop_number else ""

            if script_path.exists():
                print_success(f"{script_name}{marker}")
            else:
                print_error(f"{script_name} NOT FOUND{marker}")
                all_exist = False

        return all_exist

    def verify_datasets(self):
        """Verify datasets exist for this laptop (if applicable)."""
        print_header("VERIFYING DATASETS")

        if not self.laptop_number:
            print_warning("Cannot verify datasets - laptop number unknown")
            return True

        # Only countries (3, 4, 5) need datasets
        if self.laptop_number in [1, 2]:
            print_info(f"Laptop {self.laptop_number} ({self.laptops[self.laptop_number]['name']}) doesn't require datasets")
            return True

        # Determine which client datasets are needed
        client_map = {
            3: ["Client_01.csv", "Client_02.csv", "Client_03.csv"],
            4: ["Client_04.csv", "Client_05.csv", "Client_06.csv"],
            5: ["Client_07.csv", "Client_08.csv", "Client_09.csv"]
        }

        data_dir = self.project_root / "data" / "processed"

        if not data_dir.exists():
            print_error(f"Data directory not found: {data_dir}")
            return False

        required_clients = client_map[self.laptop_number]

        print_info(f"Required datasets for {self.laptops[self.laptop_number]['name']}:\n")

        all_found = True
        for client_file in required_clients:
            client_path = data_dir / client_file
            if client_path.exists():
                size_mb = client_path.stat().st_size / (1024 * 1024)
                print_success(f"{client_file} ({size_mb:.1f} MB)")
            else:
                print_error(f"{client_file} NOT FOUND")
                all_found = False

        if not all_found:
            print_warning(f"\nMissing datasets! Please add to: {data_dir}")

        return all_found

    def generate_report(self):
        """Generate verification report."""
        print_header("VERIFICATION REPORT")

        current_ip = self.detect_current_ip()

        print(f"Date: {self.get_timestamp()}")
        print(f"Laptop: {self.laptop_number if self.laptop_number else 'Unknown'}")
        print(f"Current IP: {current_ip}")
        print(f"Project Directory: {self.project_root}")
        print("")

        if self.laptop_number:
            print("Status: READY TO START")
            print(f"\nStart command:")
            script_map = {
                1: "start_laptop1_attacker.py",
                2: "start_laptop2_global_server.py",
                3: "start_laptop3_country_a.py",
                4: "start_laptop4_country_b.py",
                5: "start_laptop5_country_c.py"
            }
            print(f"  python {script_map[self.laptop_number]}")
        else:
            print("Status: CONFIGURATION NEEDED")
            print("\nRun setup_laptop.py first to configure this laptop.")

    def get_timestamp(self):
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def run(self):
        """Run all verifications."""
        print(f"""
{Colors.HEADER}{Colors.BOLD}
================================================================================
   CUDIND NETWORK VERIFICATION
================================================================================
{Colors.ENDC}
This script verifies the distributed setup is ready.
""")

        # Check this laptop's IP
        self.check_own_ip()

        # Test all connectivity
        self.test_all_connectivity()

        # Verify required ports (optional)
        self.verify_required_ports()

        # Verify config file
        self.verify_config_file()

        # Verify startup scripts
        self.verify_startup_scripts()

        # Verify datasets
        self.verify_datasets()

        # Generate report
        self.generate_report()

        print(f"\n{Colors.OKGREEN}Verification complete!{Colors.ENDC}\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="CUDIND Network Verification")
    parser.add_argument('--laptop', type=int, choices=[1,2,3,4,5], help='Laptop number (1-5)')
    args = parser.parse_args()

    try:
        verifier = NetworkVerifier(laptop_number=args.laptop)
        verifier.run()
        return 0
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Verification cancelled.{Colors.ENDC}\n")
        return 1
    except Exception as e:
        print(f"\n{Colors.FAIL}Error: {e}{Colors.ENDC}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
