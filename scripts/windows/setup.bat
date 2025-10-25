@echo off
setlocal enabledelayedexpansion

REM Change to project root directory (parent of scripts folder)
cd /d "%~dp0\.."

echo ========================================
echo VoteBem Django Development Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/10] Checking Python version...
python --version

echo.
echo [2/10] Creating virtual environment...
if not exist ".venv" (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment already exists.
)

echo.
echo [3/10] Activating virtual environment and upgrading pip...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo WARNING: Failed to upgrade pip, continuing...
)

echo.
echo [4/10] Installing Python dependencies...
echo This may take a few minutes, especially for psycopg2-binary...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies
    echo.
    echo Common solutions:
    echo 1. Make sure you have Visual Studio Build Tools installed
    echo 2. Try: pip install --only-binary=all -r requirements.txt
    echo 3. Or install without PostgreSQL: pip install Django gunicorn whitenoise
    echo.
    pause
    exit /b 1
)

echo.
echo [5/10] Setting up environment configuration...
if exist ".env.dev" (
    echo Environment file .env.dev already exists.
) else (
    echo Environment file .env.dev was created during setup.
)

echo.
echo [6/10] Checking Docker availability...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Docker is not available
    echo You can still run Django with SQLite database
    echo To use PostgreSQL, please install and start Docker Desktop
    goto skip_docker
)

echo Docker is available, starting services...
echo [7/10] Starting Docker services (PostgreSQL, Redis, etc.)...
docker-compose -f docker-compose.dev-services.yml up -d
if %errorlevel% neq 0 (
    echo WARNING: Failed to start Docker services
    echo Django will use SQLite database instead
    goto skip_docker
)

echo.
echo [8/10] Waiting for services to be ready...
timeout /t 15 /nobreak >nul

echo.
echo Checking service health...
docker-compose -f docker-compose.dev-services.yml ps

goto setup_django

:skip_docker
echo.
echo [7-8/10] Skipping Docker services (will use SQLite)...

:setup_django
echo.
echo [9/10] Setting up Django database...
set DJANGO_SETTINGS_MODULE=votebem.settings.development
python manage.py migrate --settings=votebem.settings.development
if %errorlevel% neq 0 (
    echo ERROR: Failed to run Django migrations
    echo Make sure Django is properly installed
    pause
    exit /b 1
)

echo.
echo [10/10] Creating static files directory...
if not exist "static" mkdir static
python manage.py collectstatic --noinput --settings=votebem.settings.development
if %errorlevel% neq 0 (
    echo WARNING: Failed to collect static files, continuing...
)

echo.
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo Next steps:
echo 1. Run 'startup.bat' to start the development server
echo 2. Open http://localhost:8000 in your browser
echo 3. Access admin at http://localhost:8000/admin
echo.
echo Optional services:
echo - pgAdmin (Database UI): http://localhost:8080
echo - Redis Commander: http://localhost:8081
echo - Nginx Proxy: http://localhost (when enabled)
echo.
echo To create a superuser, run:
echo   .venv\Scripts\activate
echo   python manage.py createsuperuser --settings=votebem.settings.development
echo.
pause