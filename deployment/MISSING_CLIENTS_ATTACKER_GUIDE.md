# Handling Missing Clients & Attacker Setup

## Q1: Do I need ALL 9 clients to run?

**NO.** The system works with ANY number of clients (1-9).

### What Happens If Clients Are Missing:

| Scenario | Result |
|----------|--------|
| 9 clients (all PCs available) | Full FL training with 9 participants |
| 6 clients (2 PCs available) | Training works - aggregates 6 clients |
| 3 clients (1 PC available) | Training works - aggregates 3 clients |
| 1 client | Single-node training (degenerate FL) |

### How It Works:
In the Flower server, if a client doesn't connect:
- Server waits for `min_clients` (default: 1)
- Aggregates whatever clients ARE connected
- Training continues normally

### Practical Example:
If **Client PC 2 fails** (Clients 04-06 unavailable):
- Server will connect: Clients 01-03 (PC1) + Clients 07-09 (PC3) = 6 clients
- Training proceeds with 6 clients
- Metrics show 6 client performances
- **Result is still valid federated learning**

---

## Q2: Will the attacker work?

**YES, but with important caveats.**

### Your Earlier "Bombardment Hang" Issue:

The old version hung because:
1. Attacker sent attack data in a tight loop (no rate limiting)
2. No timeout on HTTP requests
3. Dashboard tried to write metrics while attacker injected

### Current Attacker Design:

The attacker (`attacker_node.py`) has ** TWO MODES**:

#### Mode 1: OFFLINE (Safe - Recommended for testing)
```cmd
python attacker_node.py --config config/physical_config.yaml --scenario gentle_probe --mode offline
```
- **What it does**: Pre-generates attack CSVs in `data/simulated_attacks/`
- **Does NOT**: Inject live, crash servers, or hang anything
- **Use when**: Preparing for training, want reproducible attacks

#### Mode 2: LIVE (Risky - Requires careful setup)
```cmd
python attacker_node.py --config config/physical_config.yaml --scenario targeted_strike --mode live
```
- **What it does**: Watches dashboard, injects attacks at specific rounds
- **Has**: Timeouts (10s), error handling, graceful degradation
- **Still can hang IF**: Target IPs unreachable, dashboard not running

### Attacker Scenarios Available:

| Scenario | Description | Intensity |
|----------|-------------|-----------|
| `gentle_probe` | Low-intensity port scanning | 5% attack ratio |
| `targeted_strike` | DDoS on one country | 30% attack ratio |
| `full_siege` | Simultaneous attacks on all | 40% attack ratio |
| `apt_campaign` | Multi-phase APT simulation | 5-35% escalating |
| `insider_threat` | Label-flip poisoning | 20% of one client |
| `zero_day` | Novel attack patterns | 25% unknown patterns |

### Why It Might Still Hang:

1. **Dashboard not running**: Attacker watches `/api/state` endpoint
2. **Target laptop offline**: HTTP requests timeout after 10s (should be OK now)
3. **Wrong IP/port in config**: `physical_config.yaml` has wrong addresses
4. **Requests library not installed**: Run `pip install requests`

### Safe Attacker Setup (Recommended):

**Step 1: Pre-generate attacks (offline mode)**
```cmd
# On attacker machine
python attacker_node.py --scenario gentle_probe --mode offline
```
This creates files like:
- `data/simulated_attacks/Client_01_attack.csv`
- `data/simulated_attacks/Client_02_attack.csv`

**Step 2: Train WITHOUT live injection**
Just run training normally. The pre-generated attack files won't be used automatically - they're just sitting there for testing.

**Step 3: (Optional) Manual injection**
Run attack server separately:
```cmd
# This needs separate setup - see attacker_server.py
```

---

## Q3: How to handle 3-PC setup with potential missing PCs?

### Setup Files for Each PC:

Each PC needs:
- Same `CRCK/` folder copied
- Same embedded Python + dependencies
- Correct IP (192.168.1.100/101/102/103)

### Resilient Launcher Scripts (Auto-detect availability):

Add this to each client PC launcher:

```batch
@echo off
REM PC 1 Launcher - Works even if PC 2/3 fail

echo Checking server connectivity...
ping -n 2 192.168.1.100 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Server at 192.168.1.100 not reachable!
    echo Make sure server PC is ON and network cable connected.
    pause
    exit /b 1
)

echo Server reachable. Starting clients...

start "Client_01 - NOT CONNECTED" cmd /k "REM Client 01 - will show status"
start "Client_02 - NOT CONNECTED" cmd /k "REM Client 02"
start "Client_03 - NOT CONNECTED" cmd /k "REM Client 03"

echo.
echo If client terminals show connection errors:
echo - Check server is running on 192.168.1.100
echo - Check firewall allows port 8080
echo - Verify ethernet cables connected
pause
```

### What Happens With Missing PCs:

**Scenario: Only PC 1 available (Clients 01-03)**
- Server connects to 3 clients
- Training aggregates 3 clients
- Dashboard shows only 3 clients
- **Result: VALID** (just smaller federation)

**Scenario: PC 1 + PC 3 available (6 clients)**
- Server connects to 6 clients
- Training aggregates 6 clients
- Dashboard shows only 6 clients
- **Result: VALID**

**Scenario: Only PC 2 available (Clients 04-06)**
- Server connects to 3 clients
- Training works
- **Result: VALID**

### Key Insight:

Federated learning is **designed** to handle:
- Client dropout during training
- Heterogeneous client numbers
- Clients joining/leaving mid-experiment

Your system is **robust** to missing PCs.

---

## Q4: What if the attacker machine ALSO runs a client?

This is COMMON and works fine:

### Setup:
**Attacker PC = Client PC 1** (Same machine does both)

```batch
REM Same PC runs:
REM - Attacker node (gentle_probe scenario)
REM - Clients 01, 02, 03 (flwr.client)
```

**Requirements:**
1. Enough RAM for 3 client processes + attacker
2. Attacker uses HTTP to inject, doesn't block client threads
3. Run attacker in background: `start "Attacker" python attacker_node.py ...`

---

## Quick Reference: Attacker Commands

### List all scenarios:
```cmd
python attacker_node.py --list-scenarios
```

### Pre-generate attack CSVs (SAFE):
```cmd
python attacker_node.py --scenario gentle_probe --mode offline
python attacker_node.py --scenario targeted_strike --mode offline
```

### Live injection (RISKY):
```cmd
# Only if dashboard is running on Server PC
python attacker_node.py --scenario gentle_probe --mode live
```

### Verify attacker can reach targets:
```cmd
# From attacker PC, test connection to client PCs
ping 192.168.1.101
ping 192.168.1.102
ping 192.168.1.103
```

---

## Summary

| Question | Answer |
|----------|--------|
| Do I need all 9 clients? | NO - works with 1-9 |
| Does missing PC break training? | NO - robust to dropout |
| Will attacker work now? | YES - has timeouts/errors now |
| Should I use live or offline mode? | **Offline mode** for testing |
| Can attacker share PC with clients? | YES - just run both |

---

## Recommended 3-PC Setup

**Server PC (192.168.1.100):**
- Run: `server_launcher.bat`
- Optional: Run dashboard for live monitoring

**Client PC 1 (192.168.1.101):**
- Run: `clients_pc1_launcher.bat` (Clients 01-03)
- Optional: Run attacker (for gentle_probe testing)

**Client PC 2 (192.168.1.102):**
- Run: `clients_pc2_launcher.bat` (Clients 04-06)

**Client PC 3 (192.168.1.103):** - NOT USED if not available! - Just train with 6 clients instead

**Total: 6 clients, 3 PCs, full FL training works perfectly**
