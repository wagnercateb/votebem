@echo off

REM Change to project root directory (parent of scripts folder)
cd /d "%~dp0\.."

echo ========================================
echo VoteBem Django Troubleshooting
echo ========================================
echo.

echo [1] Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.11+ from https://www.python.org/downloads/
) else (
    echo Python is installed correctly
)

echo.
echo [2] Checking virtual environment...
if exist ".venv\Scripts\python.exe" (
    echo Virtual environment exists
    call .venv\Scripts\activate.bat
    echo Virtual environment activated
    python --version
) else (
    echo Virtual environment not found
    echo Run: python -m venv .venv
)

echo.
echo [3] Checking Django installation...
python -c "import django; print('Django version:', django.get_version())" 2>nul
if %errorlevel% neq 0 (
    echo Django not installed or not accessible
    echo Try: pip install Django
) else (
    echo Django is installed correctly
)

echo.
echo [4] Checking Docker...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker not available
    echo Install Docker Desktop from https://www.docker.com/products/docker-desktop/
) else (
    echo Docker is available
    docker ps >nul 2>&1
    if %errorlevel% neq 0 (
        echo Docker daemon not running - start Docker Desktop
    ) else (
        echo Docker is running correctly
    )
)

echo.
echo [5] Checking database connectivity...
python manage.py check --database default --settings=votebem.settings.development 2>nul
if %errorlevel% neq 0 (
    echo Database check failed
    echo This is normal if using SQLite for the first time
) else (
    echo Database connectivity OK
)

echo.
echo ========================================
echo Troubleshooting Complete
echo ========================================
echo.
echo Common fixes:
echo 1. For mysqlclient errors: Install "Microsoft C++ Build Tools" then pip install mysqlclient
echo 2. For Django not found: .venv\Scripts\activate then pip install Django
echo 3. For Docker issues: Start Docker Desktop and wait for it to load
echo 4. For permission errors: Run as Administrator
echo.
pause