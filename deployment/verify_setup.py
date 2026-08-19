#!/usr/bin/env python3
"""
Verify 3-computer deployment setup before starting training.
Checks: network, data files, GPU, dependencies
"""
import sys
import socket
import pathlib
import subprocess

print("="*60)
print("LSCUDAPORT - Deployment Verification")
print("="*60)

PROJECT_ROOT = pathlib.Path(__file__).parent.parent

issues = []
warnings = []
passed = []

# Check 1: Data files
print("\n[1/5] Checking data files...")
data_path = PROJECT_ROOT / "data" / "processed"
expected_clients = [f"Client_{i:02d}.csv" for i in range(1, 10)]

for client_file in expected_clients:
    file_path = data_path / client_file
    if file_path.exists():
        size_mb = file_path.stat().st_size / (1024*1024)
        passed.append(f"Data: {client_file} ({size_mb:.1f} MB)")
        print(f"  [OK] {client_file}")
    else:
        issues.append(f"Missing data: {client_file}")
        print(f"  [FAIL] {client_file} - NOT FOUND")

# Check 2: Dependencies
print("\n[2/5] Checking dependencies...")
try:
    import torch
    passed.append(f"PyTorch: {torch.__version__}")
    print(f"  [OK] torch {torch.__version__}")
except ImportError:
    issues.append("PyTorch not installed")
    print("  [FAIL] torch - NOT INSTALLED")

try:
    import flwr
    passed.append(f"Flower: {flwr.__version__}")
    print(f"  [OK] flwr {flwr.__version__}")
except ImportError:
    warnings.append("Flower not installed")
    print("  [WARN] flwr - NOT INSTALLED")

try:
    import pandas
    passed.append("Pandas: installed")
    print("  [OK] pandas")
except ImportError:
    warnings.append("Pandas not installed")
    print("  [WARN] pandas - NOT INSTALLED")

# Check 3: GPU
print("\n[3/5] Checking GPU...")
try:
    import torch
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
        passed.append(f"GPU: {gpu_name}")
        print(f"  [OK] {gpu_name}")
        print(f"  [OK] {gpu_memory:.2f} GB VRAM")
    else:
        warnings.append("CUDA not available")
        print("  [WARN] CUDA not available - using CPU")
except Exception as e:
    warnings.append(f"GPU check failed: {e}")
    print(f"  [WARN] GPU check failed: {e}")

# Check 4: Network (if this computer is a client)
print("\n[4/5] Checking network...")
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
passed.append(f"Local IP: {local_ip}")
print(f"  Local IP: {local_ip}")

# Check if server is reachable
try:
    result = subprocess.run(
        ["ping", "-n", "2", "192.168.1.100"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode == 0:
        passed.append("Server reachable")
        print("  [OK] Server (192.168.1.100) reachable")
    else:
        warnings.append("Server not reachable")
        print("  [WARN] Server (192.168.1.100) not reachable")
except Exception as e:
    warnings.append(f"Network check failed: {e}")
    print(f"  [WARN] Network check failed: {e}")

# Check 5: Directory structure
print("\n[5/5] Checking directory structure...")
required_dirs = [
    "federated",
    "models",
    "data_pipeline",
    "utils",
    "deployment_tools/python_embedded"
]

for dir_path in required_dirs:
    full_path = PROJECT_ROOT / dir_path
    if full_path.exists():
        passed.append(f"Dir: {dir_path}")
        print(f"  [OK] {dir_path}/")
    else:
        issues.append(f"Missing directory: {dir_path}")
        print(f"  [FAIL] {dir_path}/ - NOT FOUND")

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print(f"Passed: {len(passed)} checks")
print(f"Warnings: {len(warnings)}")
print(f"Issues: {len(issues)}")

if issues:
    print("\n[CRITICAL] Issues must be fixed:")
    for issue in issues:
        print(f"  - {issue}")

if warnings:
    print("\n[WARNING] Items to review:")
    for warning in warnings:
        print(f"  - {warning}")

if not issues and not warnings:
    print("\n[SUCCESS] All checks passed! Ready for deployment.")
    sys.exit(0)
elif not issues:
    print("\n[WARNING] Deployment may work but review warnings.")
    sys.exit(0)
else:
    print("\n[FAILED] Fix critical issues before deploying.")
    sys.exit(1)
