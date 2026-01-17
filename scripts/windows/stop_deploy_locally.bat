@echo off
setlocal enabledelayedexpansion

REM =======================================================================
REM VoteBem Windows Docker deployment stop helper
REM
REM Purpose:
REM   - Safely stop the Windows Docker stack defined in docker-compose-windows.yml
REM     that runs the VoteBem application (MariaDB, Valkey, web and nginx).
REM   - Enforce that the script runs with Administrative privileges, matching
REM     the requirements of the deployment script and avoiding permission issues.
REM   - Change the working directory to the project root so docker compose
REM     is executed against the correct compose file and environment.
REM   - Confirm that docker-compose-windows.yml exists before attempting to
REM     stop containers, and guide the user to run the deployment script first
REM     if it is missing.
REM   - Normalize DATA_ROOT from a Windows path (C:\votebem_data) to a forward-
REM     slash form for Docker Compose by rewriting backslashes; this mirrors the
REM     transformation done during deployment so the same variable works here.
REM   - Call "docker compose -f docker-compose-windows.yml down" to gracefully
REM     stop and remove the containers that make up the VoteBem stack, without
REM     deleting the persisted data under C:\votebem_data.
REM
REM Usage:
REM   - Run as Administrator after the Windows deployment script has created
REM     docker-compose-windows.yml. It will stop all VoteBem containers while
REM     leaving volumes and data intact for the next startup.
REM   - Redundancy: this is the primary Windows stop helper; keep it paired
REM     with deploy_docker_locally.bat.
REM =======================================================================

REM Check for Admin privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Running with Administrative privileges.
) else (
    echo [ERROR] This script requires Administrative privileges.
    echo Please right-click and "Run as Administrator".
    pause
    exit /b 1
)

REM Change to project root directory
cd /d "%~dp0\..\.."

REM Configuration
set "DATA_ROOT=C:\votebem_data"
set "COMPOSE_FILE=docker-compose-windows.yml"

REM Check if compose file exists
if not exist "%COMPOSE_FILE%" (
    echo [ERROR] %COMPOSE_FILE% not found.
    echo Please run deploy_docker.bat first.
    pause
    exit /b 1
)

echo [INFO] Stopping services...
set "DATA_ROOT_FWD=%DATA_ROOT:\=/%"
set "DATA_ROOT=%DATA_ROOT_FWD%"

docker compose -f %COMPOSE_FILE% down

if %errorlevel% neq 0 (
    echo [ERROR] Failed to stop services.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Services Stopped Successfully!
echo ========================================
echo.
pause
