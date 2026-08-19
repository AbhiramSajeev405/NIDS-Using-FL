# LSCUDAPORT 3-Computer Deployment - Quick Checklist

## Pre-Deployment (All Computers)

- [ ] All 4 computers physically connected via ethernet to same switch/hub
- [ ] CRCK folder copied to all computers
- [ ] Dependencies installed on all computers:
  ```cmd
  .\deployment_tools\python_embedded\Scripts\pip.exe install -r requirements.txt
  .\deployment_tools\python_embedded\Scripts\pip.exe install flwr[superlink]
  ```

## Network Configuration

### Server PC (192.168.1.100)
- [ ] Ethernet connected
- [ ] Static IP set: 192.168.1.100/255.255.255.0
- [ ] Firewall allows port 8080

### Client PC 1 (192.168.1.101)
- [ ] Ethernet connected
- [ ] Static IP set: 192.168.1.101/255.255.255.0
- [ ] Gateway: 192.168.1.100
- [ ] Run `network_test.bat` - all tests pass

### Client PC 2 (192.168.1.102)
- [ ] Ethernet connected
- [ ] Static IP set: 192.168.1.102/255.255.255.0
- [ ] Gateway: 192.168.1.100
- [ ] Run `network_test.bat` - all tests pass

### Client PC 3 (192.168.1.103)
- [ ] Ethernet connected
- [ ] Static IP set: 192.168.1.103/255.255.255.0
- [ ] Gateway: 192.168.1.100
- [ ] Run `network_test.bat` - all tests pass

## Deployment Order (CRITICAL!)

### Step 1: Server PC
- [ ] Run `deployment\server_launcher.bat`
- [ ] Wait for server to start (should show "Waiting for clients")

### Step 2: Client PC 1
- [ ] Run `deployment\clients_pc1_launcher.bat`
- [ ] Verify all 3 terminals show "Connected to server"

### Step 3: Client PC 2
- [ ] Run `deployment\clients_pc2_launcher.bat`
- [ ] Verify all 3 terminals show "Connected to server"

### Step 4: Client PC 3
- [ ] Run `deployment\clients_pc3_launcher.bat`
- [ ] Verify all 3 terminals show "Connected to server"

### Step 5: Training Begins
- [ ] Server terminal shows "9 clients connected"
- [ ] Training rounds start automatically
- [ ] Each client prints training progress

## Monitoring

### During Training
- **Server PC**: Watch for round summaries
- **Client PCs**: Each terminal shows its client's training progress
- **Expected duration**: ~15-30 minutes for 3 rounds

### Expected Output
```
[Server] Starting round 1/3
[Client_01] Training... Loss=0.4523
[Client_01] Completed round 1, Acc=0.8853
[Client_02] Training... Loss=0.3891
...
[Server] Round 1 complete, aggregating 9 clients
```

## Troubleshooting

### Server won't start?
```cmd
# Check port 8080 is not in use
netstat -ano | findstr :8080
```

### Clients can't connect?
```cmd
# Test connectivity from client to server
ping 192.168.1.100

# Check firewall
netsh advfirewall firewall add rule name="FL" dir=in action=allow protocol=TCP localport=8080
```

### One client fails?
- Check data file exists: `data/processed/Client_XX.csv`
- Check Python/Flower versions match across all PCs

## Post-Deployment

- [ ] Training completes successfully
- [ ] Metrics saved to `utils/logs/`
- [ ] Results in `results/full_grid_20rounds_results.txt`
- [ ] Dashboard shows all 9 clients

## Success Criteria

| Metric | Target |
|--------|--------|
| All 9 clients connect | Yes |
| Training rounds complete | 3+ |
| Average Accuracy | >85% |
| Detection Rate | 100% |
| FPR | <5% |

---

**Files in this deployment folder:**
- `THREE_PC_SETUP.md` - Complete setup guide
- `server_launcher.bat` - Server startup script (PC 0)
- `clients_pc1_launcher.bat` - 3 clients on PC 1
- `clients_pc2_launcher.bat` - 3 clients on PC 2
- `clients_pc3_launcher.bat` - 3 clients on PC 3
- `network_test.bat` - Connectivity verification
- `DEPLOYMENT_CHECKLIST.md` - This file
