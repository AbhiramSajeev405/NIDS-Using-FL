@echo off
echo ========================================
echo LSCUDAPORT - Network Connectivity Test
echo ========================================
echo.

echo Testing connection to Server (192.168.1.100)...
ping -n 2 192.168.1.100 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Server reachable
) else (
    echo [FAIL] Server NOT reachable - check network cable and IP
)
echo.

echo Testing loopback...
ping -n 2 127.0.0.1 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Local network stack working
) else (
    echo [FAIL] Local network stack failed
)
echo.

echo Checking if Server port 8080 is open...
powershell -Command "Test-NetConnection -ComputerName 192.168.1.100 -Port 8080 -InformationLevel Quiet" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Port 8080 is open
) else (
    echo [WARN] Port 8080 not responding - start server first
)
echo.

echo Current IP configuration:
ipconfig | findstr /i "IPv4"
echo.

echo ========================================
echo Test complete!
echo ========================================
pause
