@echo off
echo ========================================
echo LSCUDAPORT - Flower SuperLink Server
echo ========================================
echo IP: 192.168.1.100:8080
echo Waiting for clients...
echo.
echo Press Ctrl+C to stop server
echo.

.\deployment_tools\python_embedded\python.exe -m flwr.server --host 192.168.1.100 --port 8080 --insecure

pause
