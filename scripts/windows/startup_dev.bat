@echo off

REM Change to project root directory (two levels up from windows/)
REM Fix: from scripts\windows to project root requires ..\..
cd /d "%~dp0\..\.."

echo ========================================
echo VoteBem Django LOCAL Development Startup
echo ========================================
echo.
echo This script starts Django in pure local development mode
echo - No Docker dependencies
echo - SQLite database for easy debugging
echo - DEBUG=True enabled
echo - Django Debug Toolbar enabled
echo - Console email backend
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run 'setup.bat' first to set up the development environment.
    pause
    exit /b 1
)

echo [1/4] Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo.
echo [2/4] Setting up development environment variables...
REM Set Django to use development settings
set DJANGO_SETTINGS_MODULE=votebem.settings.production

REM Ensure DEBUG is enabled for local development
set DEBUG=True

REM Set allowed hosts for local development
set ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

REM Use console email backend for development
set EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

echo Environment configured for local development:
echo - DJANGO_SETTINGS_MODULE=%DJANGO_SETTINGS_MODULE%
echo - DEBUG=%DEBUG%
echo - ALLOWED_HOSTS=%ALLOWED_HOSTS%
echo - Database: SQLite (no Docker required)
echo.

REM Prepare logs directory and set dev debug log file path
if not exist "logs" (
    mkdir logs
)
set VOTEBEM_DEBUG_LOG=%CD%\logs\django_dev_debug.log
echo Dev log file will be written to: %VOTEBEM_DEBUG_LOG%
echo.

echo [3/5] Running Django system checks...
python manage.py check
if %errorlevel% neq 0 (
    echo ERROR: Django system check failed!
    echo Please fix the issues above before starting the server.
    pause
    exit /b 1
)

echo.
echo [4/5] Preparing Python debugger (debugpy)...
REM Ensure debugpy is installed in the virtual environment
python -c "import debugpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing debugpy in the virtual environment...
    pip install debugpy
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install debugpy
        pause
        exit /b 1
    )
)

REM Configure debugger host/port and Django reload behavior
if "%DEBUGPY_HOST%"=="" set DEBUGPY_HOST=127.0.0.1
if "%DEBUGPY_PORT%"=="" set DEBUGPY_PORT=5678
if "%DJANGO_AUTORELOAD%"=="" set DJANGO_AUTORELOAD=0
REM Default to waiting for debugger attach to avoid ECONNREFUSED on first attach
if "%DEBUGPY_WAIT%"=="" set DEBUGPY_WAIT=1
set RUNSERVER_FLAGS=
if "%DJANGO_AUTORELOAD%"=="0" set RUNSERVER_FLAGS=--noreload
set DEBUGPY_WAIT_FLAG=
if "%DEBUGPY_WAIT%"=="1" set DEBUGPY_WAIT_FLAG=--wait-for-client

echo.
echo ========================================
echo LOCAL Development server starting under debugger...
echo ========================================
echo.
echo Available URLs:
echo - Main Application: http://localhost:8000
echo - Admin Panel: http://localhost:8000/admin
echo.
echo Debugging:
echo - Debugger endpoint: %DEBUGPY_HOST%:%DEBUGPY_PORT%
echo - Waiting for IDE attach: %DEBUGPY_WAIT% (1=wait before start, 0=don't wait)
echo - VS Code attach:
echo    1) Open this folder in VS Code
echo    2) Run and Debug (Ctrl+Shift+D)
echo    3) Select "Attach to Django (debugpy)" and Start
echo    4) It will connect to %DEBUGPY_HOST%:%DEBUGPY_PORT% and then Django starts
echo - You can set DEBUGPY_WAIT=0 to start immediately and attach later.
echo - In VS Code: "Python: Attach" to %DEBUGPY_HOST%:%DEBUGPY_PORT%
echo - Auto-reload: disabled when DJANGO_AUTORELOAD=0 (better for breakpoints)
echo   Set DJANGO_AUTORELOAD=1 to re-enable autoreload if desired.
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

echo [5/5] Starting Django under debugpy...
REM Start Django under debugpy; optionally wait for IDE to attach
python -m debugpy --listen %DEBUGPY_HOST%:%DEBUGPY_PORT% %DEBUGPY_WAIT_FLAG% manage.py runserver 127.0.0.1:8000 %RUNSERVER_FLAGS%

echo.
echo ========================================
echo Django development server stopped.
echo ========================================
echo.
echo Development session ended.
echo Virtual environment is still active.
echo.
pause