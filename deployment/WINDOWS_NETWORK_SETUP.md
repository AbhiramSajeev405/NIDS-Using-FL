# Windows Laptop Network Setup for LSCUDAPORT

## The Problem with Windows Networking

Windows laptops have these issues when connecting directly:
1. **Hostname resolution fails** - `\\LAPTOP-PC1` won't work reliably
2. **Network Profile defaults to "Public"** - blocks all incoming connections
3. **Firewall blocks ports silently** - no error message, just timeout
4. **Power management** - can disable ethernet adapter to "save power"
5. **IPv6 preference** - tries IPv6 first, fails if not configured

## The Solution: Static IPs + Explicit Port Rules

This setup **bypasses all Windows networking issues**:

---

## Step-by-Step: Windows 10/11 Setup (All 4 Laptops)

### Prerequisites
- Ethernet cables for all laptops
- A switch/hub (or connect directly if 2 laptops)
- Admin access on all machines

---

### Step 1: Disable Power Saving on Ethernet (All Laptops)

1. **Device Manager** → **Network adapters**
2. Right-click your **Ethernet controller** → **Properties**
3. **Power Management** tab
4. **UNCHECK**: "Allow the computer to turn off this device to save power"
5. Click OK

**Why**: Windows will disable ethernet when idle, killing your FL connections.

---

### Step 2: Set Static IP (All Laptops)

#### Server Laptop (192.168.1.100):
1. **Settings** → **Network & Internet** → **Ethernet**
2. Click your ethernet connection
3. **Edit** IP assignment → **Manual**
4. Enable **IPv4**:
   ```
   IP address: 192.168.1.100
   Subnet prefix length: 24 (or 255.255.255.0)
   Gateway: (leave blank)
   Preferred DNS: (leave blank)
   ```
5. Save

#### Client Laptop 1 (192.168.1.101):
1. Same steps as above
2. IP configuration:
   ```
   IP address: 192.168.1.101
   Subnet prefix length: 24
   Gateway: 192.168.1.100
   Preferred DNS: 8.8.8.8
   ```

#### Client Laptop 2 (192.168.1.102):
```
IP: 192.168.1.102
Subnet: 24
Gateway: 192.168.1.100
DNS: 8.8.8.8
```

#### Client Laptop 3 (192.168.1.103):
```
IP: 192.168.1.103
Subnet: 24
Gateway: 192.168.1.100
DNS: 8.8.8.8
```

---

### Step 3: Change Network Profile to "Private" (All Laptops)

Windows defaults to "Public" which blocks everything.

**PowerShell (run as Admin):**
```powershell
# Check current profile
Get-NetConnectionProfile

# Change to Private
Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private
```

**Or via GUI:**
1. **Settings** → **Network & Internet** → **Ethernet**
2. Click your connection
3. **Network profile type** → Select **Private**

---

### Step 4: Create Firewall Rules (All Laptops)

#### Server Laptop: Allow port 8080
```cmd
# Run as Administrator
netsh advfirewall firewall add rule name="FL Server Port 8080" dir=in action=allow protocol=TCP localport=8080
```

#### Client Laptops: Allow client ports
```cmd
# Client PC 1 (ports 9001-9003)
netsh advfirewall firewall add rule name="FL Client Ports" dir=in action=allow protocol=TCP localport=9001-9003

# Client PC 2 (ports 9004-9006)
netsh advfirewall firewall add rule name="FL Client Ports" dir=in action=allow protocol=TCP localport=9004-9006

# Client PC 3 (ports 9007-9009)
netsh advfirewall firewall add rule name="FL Client Ports" dir=in action=allow protocol=TCP localport=9007-9009
```

#### Allow Python through Firewall (All Laptops):
```cmd
# Run as Administrator
netsh advfirewall firewall add rule name="Python Embedded Allowed" dir=in action=allow program="%~dp0deployment_tools\python_embedded\python.exe" enable=yes
```

---

### Step 5: Verify Network Connectivity (Test on All Laptops)

Run this from **each laptop**:

```cmd
REM Test connectivity to server
ping 192.168.1.100

REM Test connectivity to other clients
ping 192.168.1.101
ping 192.168.1.102
ping 192.168.1.103
```

**Expected result**: <1ms latency, 0% packet loss

**If ping fails**:
- Check ethernet cable is plugged in (link light on)
- Verify static IP is set correctly (`ipconfig`)
- Ensure all laptops are on same switch/hub

---

### Step 6: Disable IPv6 (Optional but Recommended)

Windows tries IPv6 first, which can cause timeouts.

**PowerShell (Admin):**
```powershell
# Disable IPv6 temporarily (until reboot)
Disable-NetAdapterBinding -Name "Ethernet" -ComponentID ms_tcpip6

# Or permanently via Device Manager:
# Device Manager → Network adapters → Right-click Ethernet → Properties
# Uncheck "Internet Protocol Version 6 (TCP/IPv6)"
```

---

## Automated Setup Script (For Each Laptop)

Create `setup_network.bat` on **each laptop**:

```batch
@echo off
echo ========================================
echo Windows Network Setup for LSCUDAPORT
echo ========================================
echo.

REM Step 1: Check current IP
echo [1/5] Checking IP configuration...
ipconfig | findstr /i "IPv4"

REM Step 2: Set Private Network Profile
echo [2/5] Setting network to Private...
powershell -Command "Set-NetConnectionProfile -NetworkCategory Private -ErrorAction SilentlyContinue"
echo Done.

REM Step 3: Open firewall ports
echo [3/5] Opening firewall ports...
netsh advfirewall firewall add rule name="FL All Ports" dir=in action=allow protocol=TCP localport=8080,9001-9009 enable=yes
echo Done.

REM Step 4: Disable power saving
echo [4/5] Verifying power settings...
powershell -Command "Get-PowerSetting -Identity (Get-GUID)\*{settings\guid}\*" 2>nul || echo [Note] Manual power settings may be needed"
echo Done.

REM Step 5: Test connectivity
echo [5/5] Testing network...
ping -n 2 192.168.1.100 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Server (192.168.1.100) reachable
) else (
    echo [FAIL] Server NOT reachable - check cable/IP
)

echo.
echo ========================================
echo Setup complete!
echo.
echo Next: Verify IPs with ipconfig
echo Then: Run deployment\network_test.bat
echo ========================================
pause
```

**Run this as Administrator on all laptops.**

---

## Common Issues and Fixes

### Issue: "Network is not discovered"
**Solution**: Doesn't matter! We use **direct IPs**, not network discovery.

### Issue: Ping works but Python fails to connect
**Cause**: Firewall blocking Python specifically
**Fix**:
```cmd
netsh advfirewall firewall add rule name="Python FL" dir=in action=allow program="deployment_tools\python_embedded\python.exe" enable=yes
```

### Issue: Connection drops after 10 minutes
**Cause**: Power saving disabling ethernet
**Fix**: Disable power saving (Step 1 above)

### Issue: "No route to host"
**Cause**: Gateway not set or wrong subnet
**Fix**: Verify all IPs are 192.168.1.X with subnet 255.255.255.0

### Issue: Laptop hostname can't be resolved
**Solution**: **Don't use hostnames!** Use explicit IPs like `192.168.1.100`

---

## Verification Checklist

Before starting FL training, verify on **each laptop**:

- [ ] Ethernet cable connected (link light ON)
- [ ] `ipconfig` shows correct static IP
- [ ] `ping 192.168.1.100` from client laptops succeeds
- [ ] `ping 127.0.0.1` succeeds (loopback)
- [ ] `netsh advfirewall show allprofiles` shows firewall ON (ports still open)
- [ ] Network profile is **Private** (not Public)
- [ ] Power saving disabled on ethernet adapter

---

## Quick Test (Before Full Deployment)

On **Server Laptop**, create `test_server.bat`:
```batch
@echo off
echo Starting simple TCP listener on port 8080...
python -c "import socket; s=socket.socket(); s.bind(('0.0.0.0', 8080)); s.listen(1); print('Listening...'); conn, addr = s.accept(); print(f'Connected from {addr}')"
```

On **Client Laptop 1**, create `test_client.bat`:
```batch
@echo off
echo Connecting to server...
python -c "import socket; s=socket.socket(); s.connect(('192.168.1.100', 8080)); print('Connected!'); s.close()"
```

Run server first, then client. If client prints "Connected!" you're good.

---

## Why This Works

| Windows Feature | Problem | Our Solution |
|-----------------|---------|--------------|
| Network discovery | Unreliable on Public profile | Don't use it - use direct IPs |
| Hostname resolution | Fails without DNS/WINS | Use `192.168.1.100` not `SERVER-PC` |
| Firewall | Blocks unknown apps | Explicit port rules + Python allowlist |
| Power management | Turns off ethernet | Disable power saving on adapter |
| IPv6 preference | Causes timeouts | Disable IPv6 |
| Public/Private profile | Public blocks incoming | Set to Private |

---

## Still Having Problems?

Run this diagnostic on the problem laptop:

```batch
REM Full network diagnostic
echo === IP Configuration ===
ipconfig /all

echo.
echo === Ping Tests ===
ping -n 2 192.168.1.100
ping -n 2 127.0.0.1

echo.
echo === Firewall Rules ===
netsh advfirewall firewall show rule name=all | findstr /i "FL 8080"

echo.
echo === Network Profile ===
powershell "Get-NetConnectionProfile"

echo.
echo === Active Connections ===
netstat -ano | findstr :8080

echo.
echo === Ethernet Adapter Status ===
powershell "Get-NetAdapter | Where-Object {$_.InterfaceCategory -eq 'LAN'}"
```

Send this output for debugging.
