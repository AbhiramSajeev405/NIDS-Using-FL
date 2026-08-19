# LSCUDAPORT - 3-Computer Deployment Guide

## Overview
- **Server PC**: 1 computer running the Flower SuperLink server
- **Client PCs**: 3 computers, each running 3 client instances (9 total)
- **Attacker**: Integrated into one of the clients (optional testing mode)
- **Connection**: Ethernet cables forming a local network

## Network Configuration

### Physical Setup
```
[Server PC] --ethernet--> [Switch/Hub] <--ethernet--[Client PC 1]
                                                    <--ethernet--[Client PC 2]
                                                    <--ethernet--[Client PC 3]
```

### IP Address Assignment (Static IPs via Ethernet)

| Computer | Role | IP Address | Port | Client Instances |
|----------|------|------------|------|------------------|
| Server PC | Server | 192.168.1.100 | 8080 | - |
| Client PC 1 | Clients | 192.168.1.101 | 9001-9003 | Client_01, Client_02, Client_03 |
| Client PC 2 | Clients | 192.168.1.102 | 9004-9006 | Client_04, Client_05, Client_06 |
| Client PC 3 | Clients | 192.168.1.103 | 9007-9009 | Client_07, Client_08, Client_09 |

---

## Step 1: Configure Network on All Computers

### Windows Network Setup (All 4 PCs)

1. Connect all computers via ethernet to same switch/hub
2. Open **Network and Sharing Center** → **Change adapter settings**
3. Right-click Ethernet adapter → **Properties**
4. Select **Internet Protocol Version 4 (TCP/IPv4)** → **Properties**

**Server PC (192.168.1.100):**
```
IP: 192.168.1.100
Subnet: 255.255.255.0
Gateway: (leave blank)
DNS: (leave blank)
```

**Client PC 1 (192.168.1.101):**
```
IP: 192.168.1.101
Subnet: 255.255.255.0
Gateway: 192.168.1.100
DNS: (leave blank)
```

**Client PC 2 (192.168.1.102):**
```
IP: 192.168.1.102
Subnet: 255.255.255.0
Gateway: 192.168.1.100
DNS: (leave blank)
```

**Client PC 3 (192.168.1.103):**
```
IP: 192.168.1.103
Subnet: 255.255.255.0
Gateway: 192.168.1.100
DNS: (leave blank)
```

### Verify Connectivity

On each computer, open Command Prompt and run:
```cmd
ping 192.168.1.100
```

All computers should be able to ping the server.

---

## Step 2: Install Dependencies on Each PC

### All Computers
```cmd
cd D:\CUDIND2\CUDIND\CRCK
.\deployment_tools\python_embedded\Scripts\pip.exe install -r requirements.txt
.\deployment_tools\python_embedded\Scripts\pip.exe install flwr[superlink]
```

---

## Step 3: Start Server (Server PC Only)

Create: `server_launcher.bat` on Server PC

```batch
@echo off
echo ========================================
echo LSCUDAPORT - Server
echo ========================================
echo IP: 192.168.1.100:8080
echo.

.\deployment_tools\python_embedded\python.exe -m flwr.server --host 192.168.1.100 --port 8080 --insecure
```

**Run this first on Server PC**

---

## Step 4: Start Clients (Each Client PC)

### Client PC 1 (Runs Client_01, Client_02, Client_03)

Create: `clients_pc1_launcher.bat`

```batch
@echo off
echo ========================================
echo LSCUDAPORT - Client PC 1 (3 instances)
echo ========================================
echo Server: 192.168.1.100:8080
echo Clients: 01, 02, 03
echo.

start "Client 01" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_01 --insecure"
start "Client 02" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_02 --insecure"
start "Client 03" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_03 --insecure"

echo All 3 clients started!
pause
```

### Client PC 2 (Runs Client_04, Client_05, Client_06)

Create: `clients_pc2_launcher.bat`

```batch
@echo off
echo ========================================
echo LSCUDAPORT - Client PC 2 (3 instances)
echo ========================================
echo Server: 192.168.1.100:8080
echo Clients: 04, 05, 06
echo.

start "Client 04" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_04 --insecure"
start "Client 05" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_05 --insecure"
start "Client 06" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_06 --insecure"

echo All 3 clients started!
pause
```

### Client PC 3 (Runs Client_07, Client_08, Client_09)

Create: `clients_pc3_launcher.bat`

```batch
@echo off
echo ========================================
echo LSCUDAPORT - Client PC 3 (3 instances)
echo ========================================
echo Server: 192.168.1.100:8080
echo Clients: 07, 08, 09
echo.

start "Client 07" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_07 --insecure"
start "Client 08" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_08 --insecure"
start "Client 09" cmd /k "cd /d D:\CUDIND2\CUDIND\CRCK && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_09 --insecure"

echo All 3 clients started!
pause
```

---

## Step 5: Training Sequence

### Order of Operations:
1. **Server PC**: Run `server_launcher.bat`
2. **Client PC 1**: Run `clients_pc1_launcher.bat`
3. **Client PC 2**: Run `clients_pc2_launcher.bat`
4. **Client PC 3**: Run `clients_pc3_launcher.bat`
5. **Server PC**: All 9 clients connect, training begins automatically

---

## Troubleshooting

### Firewall Rules (All PCs)
Add Windows Firewall exceptions for:
```
cmd /c netsh advfirewall firewall add rule name="FL Server" dir=in action=allow protocol=TCP localport=8080
cmd /c netsh advfirewall firewall add rule name="FL Client" dir=in action=allow protocol=TCP localport=9001-9009
```

### Clients Not Connecting?
1. Check all computers can ping each other
2. Verify firewall allows ports 8080 and 9001-9009
3. Ensure static IPs are correctly configured
4. Check server is running before clients

### One Client Fails to Connect?
- Check data file exists: `data/processed/Client_XX.csv`
- Verify CUDA is available: `deployment_tools\python_embedded\python.exe -c "import torch; print(torch.cuda.is_available())"`

---

## Files Needed on Each PC

Copy this folder structure to each computer:
```
CRCK/
├── data/processed/      (all 9 client datasets)
├── deployment_tools/    (embedded Python)
├── federated/
├── models/
├── data_pipeline/
├── utils/
├── requirements.txt
└── launcher scripts
```

---

## Expected Results

After 3 rounds of federated training:
- **Accuracy**: 88-93%
- **Detection Rate**: 100%
- **FPR**: <5%

Dashboard will show real-time updates for all 9 clients!
