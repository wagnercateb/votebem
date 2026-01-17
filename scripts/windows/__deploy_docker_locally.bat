@echo off
setlocal enabledelayedexpansion

REM =======================================================================
REM VoteBem Windows Docker deployment helper
REM
REM Purpose:
REM   - Prepare a Windows-friendly data directory tree under C:\votebem_data
REM     that mirrors the Linux /dados layout used in production.
REM   - Ensure Docker Desktop is running and that the script is executed
REM     with Administrative privileges (needed for some filesystem operations).
REM   - Create or update the .env file, generate basic secrets on first run,
REM     and copy the effective .env into the data directory so the container
REM     stack can read it from /dados/votebem/.env.
REM   - Generate a minimal Nginx configuration that serves static and media
REM     files from bind‑mounted directories and reverse‑proxies HTTP traffic
REM     to the Django/Gunicorn application container.
REM   - Generate docker-compose-windows.yml, which defines four services:
REM       * db:       MariaDB 11 with volumes and healthcheck aligned to Linux
REM       * valkey:   Valkey (Redis‑compatible) for caching and background tasks
REM       * web:      Django app built from Dockerfile, running migrations,
REM                   collectstatic and Gunicorn, with volumes for logs,
REM                   media, embeddings and other persisted data
REM       * nginx:    Frontend proxy serving static/media and forwarding
REM                   requests to the web container on port 8000
REM     All services are attached to the external vps_network so that this
REM     stack behaves similarly to the Linux production deployment.
REM
REM Usage:
REM   - Run this script as Administrator from any location; it will cd into
REM     the project root, create all required directories and configuration
REM     files, then write docker-compose-windows.yml ready for:
REM         docker compose -f docker-compose-windows.yml up -d
REM   - Redundancy: this is the primary Windows deployment helper; keep it.
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
echo [INFO] Working directory: %CD%

REM Check for Docker and ensure it's running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running or not installed.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Configuration
set "DATA_ROOT=C:\votebem_data"
set "APP_NAME=votebem"
set "COMPOSE_FILE=docker-compose-windows.yml"
set "ENV_FILE=.env"

echo [INFO] Using Data Root: %DATA_ROOT%

REM Create Directory Structure
echo [INFO] Creating directory structure...
if not exist "%DATA_ROOT%" mkdir "%DATA_ROOT%"
if not exist "%DATA_ROOT%\mariadb\%APP_NAME%\data" mkdir "%DATA_ROOT%\mariadb\%APP_NAME%\data"
if not exist "%DATA_ROOT%\mariadb\%APP_NAME%\backups" mkdir "%DATA_ROOT%\mariadb\%APP_NAME%\backups"
if not exist "%DATA_ROOT%\valkey\%APP_NAME%\data" mkdir "%DATA_ROOT%\valkey\%APP_NAME%\data"
if not exist "%DATA_ROOT%\nginx\app\%APP_NAME%\static" mkdir "%DATA_ROOT%\nginx\app\%APP_NAME%\static"
if not exist "%DATA_ROOT%\votebem\%APP_NAME%\media" mkdir "%DATA_ROOT%\votebem\%APP_NAME%\media"
if not exist "%DATA_ROOT%\votebem\logs" mkdir "%DATA_ROOT%\votebem\logs"
if not exist "%DATA_ROOT%\nginx\conf.d" mkdir "%DATA_ROOT%\nginx\conf.d"
if not exist "%DATA_ROOT%\votebem" mkdir "%DATA_ROOT%\votebem"
if not exist "%DATA_ROOT%\embeddings" mkdir "%DATA_ROOT%\embeddings"
if not exist "%DATA_ROOT%\chroma" mkdir "%DATA_ROOT%\chroma"

REM Generate .env if missing
if not exist "%ENV_FILE%" (
    echo [INFO] Creating .env file from .env.example...
    copy .env.example "%ENV_FILE%" >nul
    
    REM Append DATA_ROOT to .env if not present (optional, mostly for compose)
    REM But we will pass it via environment variable to compose
    
    echo [INFO] Generating secrets...
    REM Simple random string generation for Windows
    set "DB_PASS=%RANDOM%%RANDOM%%RANDOM%%RANDOM%"
    set "REDIS_PASS=%RANDOM%%RANDOM%%RANDOM%%RANDOM%"
    set "SECRET_KEY=%RANDOM%%RANDOM%%RANDOM%%RANDOM%%RANDOM%%RANDOM%"
    
    REM Replace placeholders in .env (Basic replacement)
    REM Note: For robust replacement, PowerShell is better, but trying simple approach first or just appending
    
    echo.>> "%ENV_FILE%"
    echo # Auto-generated secrets>> "%ENV_FILE%"
    echo DB_PASSWORD=!DB_PASS!>> "%ENV_FILE%"
    echo REDIS_PASSWORD=!REDIS_PASS!>> "%ENV_FILE%"
    echo DJANGO_SECRET_KEY=!SECRET_KEY!>> "%ENV_FILE%"
    
    REM Copy .env to data dir
    copy "%ENV_FILE%" "%DATA_ROOT%\votebem\.env" >nul
) else (
    echo [INFO] .env file exists. Copying to data dir...
    copy /Y "%ENV_FILE%" "%DATA_ROOT%\votebem\.env" >nul
)

REM Generate Nginx Configuration
echo [INFO] Generating Nginx configuration...
(
echo server {
echo     listen 80 default_server;
echo     server_name _;
echo.
echo     location /static/ {
echo         alias /app/staticfiles/;
echo     }
echo.
echo     location /media/ {
echo         alias /app/media/;
echo     }
echo.
echo     location / {
echo         proxy_set_header Host $host;
echo         proxy_set_header X-Real-IP $remote_addr;
echo         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
echo         proxy_set_header X-Forwarded-Proto $scheme;
echo         proxy_pass http://web:8000;
echo     }
echo }
) > "%DATA_ROOT%\nginx\conf.d\default.conf"

REM Generate docker-compose-windows.yml
echo [INFO] Generating %COMPOSE_FILE%...
(
echo services:
echo   db:
echo     image: mariadb:11
echo     container_name: votebem_db
echo     environment:
echo       MARIADB_DATABASE: ${DB_NAME}
echo       MARIADB_USER: ${DB_USER}
echo       MARIADB_PASSWORD: ${DB_PASSWORD}
echo       MARIADB_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
echo     volumes:
echo       - ${DATA_ROOT}/mariadb/votebem/data:/var/lib/mysql
echo       - ${DATA_ROOT}/mariadb/votebem/backups:/backups
echo     ports:
echo       - "127.0.0.1:3306:3306"
echo     restart: unless-stopped
echo     healthcheck:
echo       test: ["CMD-SHELL", "mariadb -h 127.0.0.1 -uroot -p$${MARIADB_ROOT_PASSWORD} -e 'SELECT 1' >/dev/null 2>&1 || exit 1"]
echo       interval: 10s
echo       timeout: 10s
echo       retries: 12
echo       start_period: 30s
echo     networks:
echo       - vps_network
echo.
echo   valkey:
echo     image: valkey/valkey:7-alpine
echo     container_name: votebem_valkey
echo     volumes:
echo       - ${DATA_ROOT}/valkey/votebem/data:/data
echo     restart: unless-stopped
echo     networks:
echo       - vps_network
echo.
echo   web:
echo     build:
echo       context: .
echo       dockerfile: Dockerfile
echo     image: votebem-web:latest
echo     pull_policy: never
echo     container_name: votebem-web
echo     restart: unless-stopped
echo     environment:
echo       DJANGO_ENV_PATH: /dados/votebem/.env
echo       REDIS_URL: redis://valkey:6379/0
echo     env_file: .env
echo     ports:
echo       - "127.0.0.1:8001:8000"
echo     volumes:
echo       - ${DATA_ROOT}/nginx/app/votebem/static:/app/staticfiles
echo       - ${DATA_ROOT}/votebem/votebem/media:/app/media
echo       - ${DATA_ROOT}/votebem/logs:/app/logs
echo       - ${DATA_ROOT}/votebem/.env:/app/votebem/.env:ro
echo       - ${DATA_ROOT}/votebem:/dados/votebem
echo       - ${DATA_ROOT}/embeddings:/dados/embeddings
echo       - ${DATA_ROOT}/chroma:/dados/chroma
echo     depends_on:
echo       db:
echo         condition: service_healthy
echo       valkey:
echo         condition: service_started
echo     command: ^>
echo       sh -c "set -e;
echo              mkdir -p /dados/votebem/docs/noticias;
echo              python manage.py migrate --settings=votebem.settings.production;
echo              python manage.py collectstatic --noinput --settings=votebem.settings.production;
echo              gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 60 votebem.wsgi:application"
echo     networks:
echo       - vps_network
echo.
echo   nginx:
echo     image: nginx:alpine
echo     container_name: votebem_nginx
echo     ports:
echo       - "80:80"
echo     volumes:
echo       - ${DATA_ROOT}/nginx/conf.d:/etc/nginx/conf.d
echo       - ${DATA_ROOT}/nginx/app/votebem/static:/app/staticfiles:ro
echo       - ${DATA_ROOT}/votebem/votebem/media:/app/media:ro
echo     depends_on:
echo       - web
echo     networks:
echo       - vps_network
echo.
echo networks:
echo   vps_network:
echo     external: true
echo     name: vps_network
) > "%COMPOSE_FILE%"

REM Create network if not exists
docker network inspect vps_network >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Creating network vps_network...
    docker network create vps_network
)

REM Run Docker Compose
echo [INFO] Starting services...
REM We need to convert backslashes to forward slashes for docker compose variables or rely on it handling it.
REM Docker Compose on Windows usually handles backslashes in paths if passed as env var, but let's be safe.
set "DATA_ROOT_FWD=%DATA_ROOT:\=/%"

REM Export DATA_ROOT for substitution in docker-compose
set "DATA_ROOT=%DATA_ROOT_FWD%"

docker compose -f %COMPOSE_FILE% up -d --build

if %errorlevel% neq 0 (
    echo [ERROR] Docker Compose failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Deployment Completed!
echo ========================================
echo.
echo Access the application at: http://localhost
echo Logs are located at: %DATA_ROOT_FWD%/votebem/logs
echo Data is stored in: %DATA_ROOT_FWD%
echo.
pause
