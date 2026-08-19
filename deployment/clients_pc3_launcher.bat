@echo off
echo ========================================
echo LSCUDAPORT - Client PC 3 (3 instances)
echo ========================================
echo Server: 192.168.1.100:8080
echo Clients: Client_07, Client_08, Client_09
echo.

chcp 65001 >nul
set PYTHONUTF8=1

start "Client_07" cmd /k "cd /d %~dp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_07 --insecure"
timeout /t 2 /nobreak >nul

start "Client_08" cmd /k "cd /d %~dp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_08 --insecure"
timeout /t 2 /nobreak >nul

start "Client_09" cmd /k "cd /d %~dp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_09 --insecure"

echo.
echo All 3 clients started!
echo Watch each terminal window for connection status.
echo.
pause
