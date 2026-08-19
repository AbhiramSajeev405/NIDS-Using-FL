@echo off
echo ========================================
echo LSCUDAPORT - Client PC 2 (3 instances)
echo ========================================
echo Server: 192.168.1.100:8080
echo Clients: Client_04, Client_05, Client_06
echo.

chcp 65001 >nul
set PYTHONUTF8=1

start "Client_04" cmd /k "cd /d %~dp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_04 --insecure"
timeout /t 2 /nobreak >nul

start "Client_05" cmd /k "cd /d %~dp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_05 --insecure"
timeout /t 2 /nobreak >nul

start "Client_06" cmd /k "cd /d %~dp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_06 --insecure"

echo.
echo All 3 clients started!
echo Watch each terminal window for connection status.
echo.
pause
