# LSCUDAPORT - 3-Computer Distributed Deployment

## Quick Start

1. **First Time Setup** (All PCs):
   ```cmd
   .\deployment_tools\python_embedded\Scripts\pip.exe install -r ..\requirements.txt
   .\deployment_tools\python_embedded\Scripts\pip.exe install flwr
   ```

2. **Verify Setup** (All PCs):
   ```cmd
   python deployment\verify_setup.py
   ```

3. **Test Network** (All PCs):
   ```cmd
   deployment\network_test.bat
   ```

4. **Start Server** (Server PC only):
   ```cmd
   deployment\server_launcher.bat
   ```

5. **Start Clients** (Each client PC):
   - PC 1: `deployment\clients_pc1_launcher.bat`
   - PC 2: `deployment\clients_pc2_launcher.bat`
   - PC 3: `deployment\clients_pc3_launcher.bat`

## Files in This Folder

| File | Purpose | Which PC |
|------|---------|----------|
| `server_launcher.bat` | Start Flower server | Server PC |
| `clients_pc1_launcher.bat` | Start 3 clients (01-03) | Client PC 1 |
| `clients_pc2_launcher.bat` | Start 3 clients (04-06) | Client PC 2 |
| `clients_pc3_launcher.bat` | Start 3 clients (07-09) | Client PC 3 |
| `network_test.bat` | Verify network connectivity | All PCs |
| `verify_setup.py` | Check data/GPU/dependencies | All PCs |
| `THREE_PC_SETUP.md` | Detailed setup guide | Reference |
| `DEPLOYMENT_CHECKLIST.md` | Step-by-step checklist | All PCs |

## Network Topology

```
                    [Ethernet Switch]
                           |
          +----------------+----------------+
          |                |                |
   192.168.1.100    192.168.1.101    192.168.1.102
      Server PC      Client PC 1      Client PC 2
                   (Clients 01-03)   (Clients 04-06)
                           |
                    192.168.1.103
                      Client PC 3
                     (Clients 07-09)
```

## Expected Timeline

| Time | Action |
|------|--------|
| 0:00 | Start server (Server PC) |
| 0:30 | Start Client PC 1 |
| 1:00 | Start Client PC 2 |
| 1:30 | Start Client PC 3 |
| 2:00 | All 9 clients connected, training begins |
| 10:00 | Round 1 complete |
| 20:00 | Round 2 complete |
| 30:00 | Round 3 complete |
| 31:00 | Training finished, results saved |

## Dashboard (Server PC)

After training starts, open dashboard on Server PC:

```cmd
deployment_tools\python_embedded\Scripts\streamlit.exe run ..\utils\dashboard_streamlit.py
```

This shows live metrics from all 9 clients!

## Troubleshooting

### "Address already in use"
The port is occupied. Close other programs or change the port.

### Clients not connecting
1. Run `network_test.bat` to verify network
2. Ensure server is started BEFORE clients
3. Check firewall allows ports 8080

### Missing data errors
Run `verify_setup.py` to check if all client CSV files exist in `data/processed/`

---

**Need help?** Check `THREE_PC_SETUP.md` for detailed setup instructions.
