@echo off
echo ========================================
echo LSCUDAPORT - Attacker Node
echo ========================================
echo.
echo Available scenarios:
echo   gentle_probe     - Low-intensity reconnaissance
echo   targeted_strike  - Focused DDoS on one country
echo   full_siege       - High-volume on all countries
echo   apt_campaign     - Multi-phase APT simulation
echo   insider_threat   - Label-flip poisoning
echo   zero_day         - Novel attack patterns
echo.

echo Mode:
echo   offline - Pre-generate attack CSVs (SAFE, recommended)
echo   live    - Real-time injection during training (RISKY)
echo.

set /p SCENARIO="Enter scenario (gentle_probe): " || set SCENARIO=gentle_probe
set /p MODE="Enter mode (offline/live): " || set MODE=offline

echo.
echo Starting attacker with scenario=%SCENARIO% mode=%MODE%
echo.

if "%MODE%"=="offline" (
    echo [INFO] OFFLINE MODE - Pre-generating attack CSVs
    echo [INFO] Attack files will be saved to: data\simulated_attacks\
    echo.
    deployment_tools\python_embedded\python.exe attacker_node.py --config config\physical_config.yaml --scenario %SCENARIO% --mode offline
) else (
    echo [WARN] LIVE MODE - Real-time attack injection
    echo [WARN] Requires dashboard running on server!
    echo [WARN] Press Ctrl+C to stop
    echo.
    deployment_tools\python_embedded\python.exe attacker_node.py --config config\physical_config.yaml --scenario %SCENARIO% --mode live
)

echo.
echo Attacker finished.
pause
