@echo off

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