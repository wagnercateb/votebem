@echo off

REM =======================================================================
REM VoteBem Windows development services stop helper
REM
REM Purpose:
REM   - Stop the Docker-based development support services defined in
REM     docker-compose.dev-services.yml (for example, database/cache used
REM     during local Django development).
REM   - Change the working directory to the project root (parent of the
REM     scripts folder) so docker-compose picks up the correct compose file.
REM   - Call "docker-compose ... down" to stop and remove the dev containers,
REM     and then display their status with "docker-compose ... ps".
REM   - Provide a simple console workflow for developers to shut down dev
REM     services and remind them to use startup.bat to bring them back up.
REM
REM Redundancy:
REM   - This script is only useful if docker-compose.dev-services.yml is
REM     still part of your current development workflow. If you have moved
REM     fully to docker compose (without the legacy docker-compose CLI) or
REM     no longer use that dev-services file, this script can be safely
REM     removed, as it is not involved in production or Windows deployment.
REM
REM Usage:
REM   - Run on a Windows dev machine after working locally; it will stop the
REM     dev containers and show their final status before exiting.
REM =======================================================================

REM Change to project root directory (parent of scripts folder)
cd /d "%~dp0\.."

echo ========================================
echo VoteBem Django Development Stop
echo ========================================
echo.

echo [1/2] Stopping Docker services...
docker-compose -f docker-compose.dev-services.yml down

echo.
echo [2/2] Checking stopped services...
docker-compose -f docker-compose.dev-services.yml ps

echo.
echo ========================================
echo All services stopped successfully!
echo ========================================
echo.
echo To start again, run 'startup.bat'
echo.
pause
