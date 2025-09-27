@echo off

REM Change to project root directory (parent of scripts folder)
cd /d "%~dp0\.."

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
set DJANGO_SETTINGS_MODULE=votebem.settings.development

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

echo [3/4] Running Django system checks...
python manage.py check
if %errorlevel% neq 0 (
    echo ERROR: Django system check failed!
    echo Please fix the issues above before starting the server.
    pause
    exit /b 1
)

echo.
echo [4/4] Starting Django development server...
echo.
echo ========================================
echo LOCAL Development server starting...
echo ========================================
echo.
echo Available URLs:
echo - Main Application: http://localhost:8000
echo - Admin Panel: http://localhost:8000/admin
echo - Django Debug Toolbar: Available on all pages
echo.
echo Development Features Enabled:
echo - DEBUG=True (detailed error pages)
echo - Django Debug Toolbar (SQL queries, performance)
echo - Console email backend (emails in terminal)
echo - SQLite database (easy to inspect/reset)
echo - Auto-reload on code changes
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Start Django development server with auto-reload
python manage.py runserver 127.0.0.1:8000

echo.
echo ========================================
echo Django development server stopped.
echo ========================================
echo.
echo Development session ended.
echo Virtual environment is still active.
echo.
pause