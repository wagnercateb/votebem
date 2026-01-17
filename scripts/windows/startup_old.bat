@echo off

REM =======================================================================
REM VoteBem Windows Django Development Startup (legacy, Docker-backed)
REM
REM Purpose:
REM   - Start the Django development server while also bringing up Docker-
REM     based dev services defined in docker-compose.dev-services.yml
REM     (MariaDB, Redis, Adminer, etc.).
REM   - Check for a Python virtual environment (.venv) and activate it.
REM   - If Docker or the dev-services stack are unavailable, fall back to
REM     running Django with SQLite only.
REM
REM Relation to startup_dev.bat:
REM   - startup_dev.bat is the newer, more robust local development entry
REM     point: it focuses on pure local dev (no Docker), enables DEBUG,
REM     configures console email and integrates debugpy for IDE debugging.
REM   - This script predates startup_dev.bat and duplicates its core job
REM     (starting a dev server), but with a weaker debugging setup and an
REM     extra responsibility of starting dev Docker services.
REM
REM Redundancy / Migration:
REM   - For day-to-day development, startup_dev.bat fully covers the needs
REM     of running Django locally with good debugging support.
REM   - Dev Docker services can be managed separately (e.g. via setup.bat
REM     and stop.bat, or direct docker-compose commands).
REM   - Keeping both startup.bat and startup_dev.bat is confusing and adds
REM     maintenance overhead.
REM   - Therefore, startup_dev.bat is considered the canonical dev starter
REM     and this script can be safely removed once you adopt that workflow.
REM =======================================================================

REM Change to project root directory (parent of scripts folder)
cd /d "%~dp0\.."

echo ========================================
echo VoteBem Django Development Startup
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run 'setup.bat' first to set up the development environment.
    pause
    exit /b 1
)

echo [1/5] Checking Docker availability...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Docker is not available
    echo Django will run with SQLite database
    echo To use MariaDB, please install and start Docker Desktop
    goto skip_docker_startup
)

echo Docker is available, starting services...
docker-compose -f docker-compose.dev-services.yml up -d
if %errorlevel% neq 0 (
    echo WARNING: Failed to start Docker services
    echo Django will use SQLite database instead
    goto skip_docker_startup
)

echo.
echo [2/5] Waiting for services to be ready...
timeout /t 15 /nobreak >nul

echo.
echo [3/5] Checking service health...
docker-compose -f docker-compose.dev-services.yml ps

goto activate_venv

:skip_docker_startup
echo Skipping Docker services...

:activate_venv
echo.
echo [4/5] Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [5/5] Starting Django development server...
echo.
echo ========================================
echo Development server starting...
echo ========================================
echo.
echo Available URLs:
echo - Main Application: http://localhost:8000
echo - Admin Panel: http://localhost:8000/admin
echo - Adminer (DB UI): http://localhost:8080
echo - Redis Commander: http://localhost:8081
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Set environment variables
set DJANGO_SETTINGS_MODULE=votebem.settings.production

REM Start Django development server
python manage.py runserver 0.0.0.0:8000 --settings=votebem.settings.production

echo.
echo ========================================
echo Django server stopped.
echo ========================================
echo.
echo To stop all services, run:
echo   docker-compose -f docker-compose.dev-services.yml down
echo.
pause
