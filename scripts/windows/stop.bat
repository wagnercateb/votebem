@echo off

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