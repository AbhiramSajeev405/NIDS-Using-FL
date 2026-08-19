@echo off
echo ========================================
echo LSCUDAPORT - Client PC 1 (3 instances)
echo ========================================
echo Server: 192.168.1.100:8080
echo Clients: Client_01, Client_02, Client_03
echo.

chcp 65001 >nul
set PYTHONUTF8=1

start "Client_01" cmd /k "cd /d %~dp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_01 --insecure --tls"
timeout /t 2 /nobreak >nul

start "Client_02" cmd /k "cd /d %~dp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_02 --insecure --tls"
timeout /t 2 /nobreak >nul

start "Client_03" cmd /k "cd /d %~bp0..\ && deployment_tools\python_embedded\python.exe -m flwr.client --host 192.168.1.100 --port 8080 --client-id Client_03 --insecure --tls"

echo.
echo All 3 clients started!
echo Watch each terminal window for connection status.
echo.
pause
