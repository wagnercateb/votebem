#!/usr/bin/env bash
set -euo pipefail

# __docker_deploy.sh
# Refactors the deployment to standardize Docker bind mounts under /dados.
# Host paths use a unified pattern like:
#   /dados/votebem/... (code, logs, static, media, backups, ssl)
#   /dados/postgres/votebem/... (database)
#   /dados/valkey/votebem/... (valkey)
#   /dados/nginx/conf.d/... (nginx site config)
# The script generates a docker-compose file with absolute host paths.

##############################
# Utilities
##############################
log()  { echo -e "[INFO]  $*"; }
warn() { echo -e "[WARN]  $*"; }
err()  { echo -e "[ERROR] $*" >&2; }

# SUDO helper: use sudo when not running as root
if [[ $(id -u) -ne 0 ]]; then SUDO="sudo"; else SUDO=""; fi

# Detect docker compose command (plugin vs legacy)
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  err "Docker Compose is not installed (plugin or legacy). Install Docker + Compose first."; exit 1
fi

# Basic dependencies
command -v docker >/dev/null 2>&1 || { err "Docker not found"; exit 1; }
command -v git >/dev/null 2>&1     || { err "git not found"; exit 1; }
command -v openssl >/dev/null 2>&1 || { warn "openssl not found; generating secrets may fail"; }

##############################
# Configuration
##############################
APP_NAME="votebem"                 # application identifier
BASE_DIR="/dados/${APP_NAME}"     # app-specific base dir
REPO_DIR="${BASE_DIR}/app"        # project code directory
COMPOSE_FILE="${BASE_DIR}/docker-compose.yml"
ENV_FILE="${BASE_DIR}/.env"
LOG_DIR="${BASE_DIR}/logs"
STATIC_DIR="/dados/nginx/app/static"
MEDIA_DIR="/dados/nginx/app/media"
BACKUPS_DIR="${BASE_DIR}/backups"
SSL_DIR="${BASE_DIR}/ssl"

# Service-specific roots
POSTGRES_DIR="/dados/postgres/${APP_NAME}/data"
VALKEY_DIR="/dados/valkey/${APP_NAME}/data"
REDIS_DIR="/dados/redis/${APP_NAME}/data"
NGINX_CONF_DIR="/dados/nginx/conf.d"
NGINX_DEFAULT_CONF="${NGINX_CONF_DIR}/default.conf"

# Repository (adjust if needed)
REPO_URL_SSH="git@github.com:wagnercateb/votebem.git"
REPO_URL_HTTPS="https://github.com/wagnercateb/votebem.git"

##############################
# Input (domain, IP)
# Set default domain and prompt with fallback
DOMAIN_DEFAULT="votebem.online"
read -rp "Enter domain (default: ${DOMAIN_DEFAULT}): " DOMAIN_INPUT || DOMAIN_INPUT=""
DOMAIN="${DOMAIN_INPUT:-$DOMAIN_DEFAULT}"
VPS_IP_DEFAULT="104.131.170.158"
read -rp "Enter VPS public IP (default: ${VPS_IP_DEFAULT}): " VPS_IP_INPUT || VPS_IP_INPUT=""
VPS_IP="${VPS_IP_INPUT:-$VPS_IP_DEFAULT}"

##############################
# User Management - Create votebem user with sudo privileges
##############################
log "Checking/creating votebem user with sudo privileges"

# Check if votebem user exists
if ! id "votebem" &>/dev/null; then
    log "Creating votebem user..."
    ${SUDO} useradd -m -s /bin/bash votebem
    ${SUDO} usermod -aG docker votebem    # Add to docker group for container management
    ${SUDO} usermod -aG sudo votebem      # Add to sudo group for administrative privileges
    
    # Set password for votebem user
    if [[ -n "${VOTEBEM_PASSWORD:-}" ]]; then
        log "Setting password for votebem user from environment variable"
        echo "votebem:$VOTEBEM_PASSWORD" | ${SUDO} chpasswd
    else
        log "Setting password for votebem user..."
        echo "Please set a password for the 'votebem' user:"
        read -s -p "Enter password for votebem user: " VOTEBEM_PASS
        echo
        if [[ -z "$VOTEBEM_PASS" ]]; then
            err "Password cannot be empty"
            exit 1
        fi
        echo "votebem:$VOTEBEM_PASS" | ${SUDO} chpasswd
        log "Password set for votebem user"
    fi
    
    log "User 'votebem' created successfully with sudo privileges"
else
    log "User 'votebem' already exists"
    # Ensure user has proper groups
    ${SUDO} usermod -aG docker votebem
    ${SUDO} usermod -aG sudo votebem
    
    # Update password if provided via environment
    if [[ -n "${VOTEBEM_PASSWORD:-}" ]]; then
        echo "votebem:$VOTEBEM_PASSWORD" | ${SUDO} chpasswd
        log "Password updated for existing votebem user"
    else
        log "To change the password for existing votebem user, run: sudo passwd votebem"
    fi
fi

##############################
# Create directories and set ownership
##############################
log "Creating /dados directory structure for ${APP_NAME}"
${SUDO} mkdir -p \
  "/dados" \
  "${BASE_DIR}" "${LOG_DIR}" "${STATIC_DIR}" "${MEDIA_DIR}" "${BACKUPS_DIR}" "${SSL_DIR}" \
  "${POSTGRES_DIR}" "${VALKEY_DIR}" "${NGINX_CONF_DIR}" \
  "/dados/certbot/acme" "/dados/certbot/certs"

# Assign ownership to current user so we can write inside
USR="$(id -un)"; GRP="$(id -gn)"
${SUDO} chown -R "${USR}:${GRP}" \
  "${BASE_DIR}" "${POSTGRES_DIR%/data}" "${VALKEY_DIR%/data}" \
  "${POSTGRES_DIR}" "${VALKEY_DIR}" "${NGINX_CONF_DIR}" "${STATIC_DIR}" "${MEDIA_DIR}" \
  "/dados/certbot/acme" "/dados/certbot/certs"
${SUDO} chmod -R 0777 "${STATIC_DIR}" "${MEDIA_DIR}" "${LOG_DIR}"

##############################
# Prepare Nginx default.conf
##############################
log "Generating Nginx default.conf at ${NGINX_DEFAULT_CONF}"
cat > "${NGINX_DEFAULT_CONF}" << 'CONF'
server {
    listen 80 default_server;
    server_name _;

    # Static
    location /static/ {
        alias /app/staticfiles/;
    }
    # Media
    location /media/ {
        alias /app/media/;
    }
    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_redirect off;
        proxy_pass http://votebem-web:8000;
    }
}
CONF

# default.conf is now a catch-all and does not inject domain/IP.
# It uses `server_name _;` and `listen 80 default_server;`, and preserves `Host` via `$host`.

##############################
# GitHub SSH verification and deploy-key handling
##############################
GIT_SSH_CMD_DEFAULT="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

github_ssh_can_access() {
  local ssh_cmd="${1:-$GIT_SSH_CMD_DEFAULT}"
  GIT_SSH_COMMAND="$ssh_cmd" git ls-remote "${REPO_URL_SSH}" >/dev/null 2>&1
}

ensure_github_ssh() {
  if github_ssh_can_access "$GIT_SSH_CMD_DEFAULT"; then
    log "SSH to GitHub works with current user's key(s)."
    USE_GIT_SSH=1; GIT_SSH_CMD="$GIT_SSH_CMD_DEFAULT"; return 0
  fi
  warn "SSH to GitHub is not working for this user."
  warn "If repository requires SSH, paste the private deploy key now."
  read -r -p "Paste deploy key? (y/N): " yn
  if [[ "${yn,,}" != "y" ]]; then USE_GIT_SSH=0; return 1; fi
  local ssh_dir="${BASE_DIR}/.ssh"; local key_file="${ssh_dir}/deploy_key"
  mkdir -p "${ssh_dir}"; chmod 700 "${ssh_dir}"; chown "${USR}:${GRP}" "${ssh_dir}"
  echo "Paste the private key content below, then press Ctrl-D."
  cat > "${key_file}"
  # Normalize CRLF to LF to avoid libcrypto parse errors
  sed -i 's/\r$//' "${key_file}" || true
  chmod 600 "${key_file}"; chown "${USR}:${GRP}" "${key_file}"
  # Validate key format early (OpenSSH private key)
  if ! ssh-keygen -y -f "${key_file}" >/dev/null 2>&1; then
    err "Invalid or unsupported private key format. Please paste a valid OpenSSH private key."
    USE_GIT_SSH=0; return 1
  fi
  ssh-keyscan -H github.com >> "${ssh_dir}/known_hosts" 2>/dev/null || true
  GIT_SSH_CMD="ssh -i ${key_file} -o IdentitiesOnly=yes -o UserKnownHostsFile=${ssh_dir}/known_hosts -o StrictHostKeyChecking=accept-new"
  if github_ssh_can_access "$GIT_SSH_CMD"; then
    log "Deploy key works for GitHub and repository access."
    USE_GIT_SSH=1; return 0
  else
    err "Deploy key authentication failed. Will fall back to HTTPS if possible."
    USE_GIT_SSH=0; return 1
  fi
}

##############################
# Clone or update repository
##############################
if [[ -d "${REPO_DIR}/.git" ]]; then
  log "Repository exists; updating ${REPO_DIR}"
  origin_url="$(cd "${REPO_DIR}" && git remote get-url origin || echo "")"
  if [[ "${origin_url}" == git@github.com* ]]; then
    if ensure_github_ssh; then
      (cd "${REPO_DIR}" && GIT_SSH_COMMAND="${GIT_SSH_CMD}" git fetch --all && GIT_SSH_COMMAND="${GIT_SSH_CMD}" git reset --hard origin/main && git clean -fd)
    else
      warn "Switching origin to HTTPS due to SSH failure."
      (cd "${REPO_DIR}" && git remote set-url origin "${REPO_URL_HTTPS}" && git fetch --all && git reset --hard origin/main && git clean -fd)
    fi
  else
    (cd "${REPO_DIR}" && git fetch --all && git reset --hard origin/main && git clean -fd)
  fi
else
  log "Cloning repository into ${REPO_DIR}"
  # If REPO_DIR exists but is empty, remove it so git clone can recreate
  if [[ -d "${REPO_DIR}" ]] && [[ -z "$(ls -A "${REPO_DIR}")" ]]; then
    rmdir "${REPO_DIR}" || true
  fi
  # If REPO_DIR exists and is not a git repo, convert to git or fetch into it
  if [[ -d "${REPO_DIR}" ]] && [[ ! -d "${REPO_DIR}/.git" ]]; then
    warn "Found non-git directory at ${REPO_DIR}; initializing git repo and fetching origin."
    ensure_github_ssh || true
    remote_url="${REPO_URL_HTTPS}"
    if [[ "${USE_GIT_SSH:-0}" -eq 1 ]]; then remote_url="${REPO_URL_SSH}"; fi
    (cd "${REPO_DIR}" && git init && git remote remove origin >/dev/null 2>&1 || true && git remote add origin "${remote_url}" && \
      { [[ "${USE_GIT_SSH:-0}" -eq 1 ]] && GIT_SSH_COMMAND="${GIT_SSH_CMD}" git fetch origin || git fetch origin; } && \
      git reset --hard origin/main && git clean -fd)
  else
    ensure_github_ssh || true
    if [[ "${USE_GIT_SSH:-0}" -eq 1 ]]; then
      GIT_SSH_COMMAND="${GIT_SSH_CMD}" git clone "${REPO_URL_SSH}" "${REPO_DIR}"
    else
      warn "Using HTTPS for clone; ensure repository is public or credentials are set."
      git clone "${REPO_URL_HTTPS}" "${REPO_DIR}"
    fi
  fi
fi

##############################
# .env generation (basic, preserve secrets if exists)
##############################
log "Creating .env at ${ENV_FILE}"
DB_NAME_DEFAULT="votebem"
DB_USER_DEFAULT="votebem_user"
DB_PASSWORD_DEFAULT="$(openssl rand -base64 24 2>/dev/null || echo pass_votebem)"
REDIS_PASSWORD_DEFAULT="$(openssl rand -base64 24 2>/dev/null || echo redis_votebem)"
DJANGO_SECRET_KEY_DEFAULT="$(openssl rand -hex 32 2>/dev/null || echo secretkey)"

# If an env file exists, preserve existing secrets to avoid credential drift
if [[ -f "${ENV_FILE}" ]]; then
  log "Existing .env found; preserving DB/Redis/Django secrets"
  DB_NAME="$(grep -E '^DB_NAME=' "${ENV_FILE}" | tail -n1 | cut -d= -f2- || echo "${DB_NAME_DEFAULT}")"
  DB_USER="$(grep -E '^DB_USER=' "${ENV_FILE}" | tail -n1 | cut -d= -f2- || echo "${DB_USER_DEFAULT}")"
  DB_PASSWORD="$(grep -E '^DB_PASSWORD=' "${ENV_FILE}" | tail -n1 | cut -d= -f2- || echo "${DB_PASSWORD_DEFAULT}")"
  REDIS_PASSWORD="$(grep -E '^REDIS_PASSWORD=' "${ENV_FILE}" | tail -n1 | cut -d= -f2- || echo "${REDIS_PASSWORD_DEFAULT}")"
  DJANGO_SECRET_KEY="$(grep -E '^DJANGO_SECRET_KEY=' "${ENV_FILE}" | tail -n1 | cut -d= -f2- || echo "${DJANGO_SECRET_KEY_DEFAULT}")"
else
  DB_NAME="${DB_NAME_DEFAULT}"
  DB_USER="${DB_USER_DEFAULT}"
  DB_PASSWORD="${DB_PASSWORD_DEFAULT}"
  REDIS_PASSWORD="${REDIS_PASSWORD_DEFAULT}"
  DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY_DEFAULT}"
fi

# Detect web build context (directory containing Dockerfile)
WEB_CONTEXT=""
if [[ -f "${REPO_DIR}/django_votebem/Dockerfile" ]]; then
  WEB_CONTEXT="${REPO_DIR}/django_votebem"
elif [[ -f "${REPO_DIR}/Dockerfile" ]]; then
  WEB_CONTEXT="${REPO_DIR}"
else
  WEB_CONTEXT="$(find "${REPO_DIR}" -maxdepth 3 -type f -name Dockerfile -printf '%h\n' | head -n 1 || true)"
fi
if [[ -z "${WEB_CONTEXT}" ]]; then
  err "Dockerfile not found under ${REPO_DIR}. Please ensure the project contains a Dockerfile."
  exit 1
fi

cat > "${ENV_FILE}" << EOF
# Django
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_DEBUG=False
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},${VPS_IP},localhost,127.0.0.1,web
CSRF_TRUSTED_ORIGINS=http://${DOMAIN},https://${DOMAIN},http://www.${DOMAIN},https://www.${DOMAIN}
CORS_ALLOWED_ORIGINS=https://${DOMAIN},http://${DOMAIN},https://www.${DOMAIN},http://www.${DOMAIN}
BASE_URL=https://${DOMAIN}
USE_X_FORWARDED_HOST=true
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https

# Database
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_HOST=valkey
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}

# Gunicorn
GUNICORN_WORKERS=3
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=120
EOF

# Patch Django settings to enforce env overrides and sanitize CORS
SETTINGS_FILE="$(find \"${REPO_DIR}\" -maxdepth 3 -type f -name 'settings.py' | head -n 1 || true)"
if [[ -n "${SETTINGS_FILE}" ]] && ! grep -q "Deploy overrides injected by __docker_deploy.sh" "${SETTINGS_FILE}"; then
  log "Injecting deploy overrides into ${SETTINGS_FILE}"
  cat >> "${SETTINGS_FILE}" << 'PY'
# Deploy overrides injected by __docker_deploy.sh
import os

def _csv(v):
    return [x.strip() for x in v.split(',') if x.strip()]

try:
    ALLOWED_HOSTS = _csv(os.getenv('ALLOWED_HOSTS', ','.join(ALLOWED_HOSTS)))
except Exception:
    ALLOWED_HOSTS = _csv(os.getenv('ALLOWED_HOSTS', 'votebem.online,www.votebem.online'))

try:
    CSRF_TRUSTED_ORIGINS = _csv(os.getenv('CSRF_TRUSTED_ORIGINS', ','.join(CSRF_TRUSTED_ORIGINS)))
except Exception:
    CSRF_TRUSTED_ORIGINS = _csv(os.getenv('CSRF_TRUSTED_ORIGINS', 'https://votebem.online,https://www.votebem.online,http://votebem.online,http://www.votebem.online'))

BASE_URL = os.getenv('BASE_URL', globals().get('BASE_URL', 'https://votebem.online'))
USE_X_FORWARDED_HOST = os.getenv('USE_X_FORWARDED_HOST', str(globals().get('USE_X_FORWARDED_HOST', 'true'))).lower() == 'true'
if os.getenv('SECURE_PROXY_SSL_HEADER'):
    SECURE_PROXY_SSL_HEADER = tuple(os.getenv('SECURE_PROXY_SSL_HEADER').split(','))


def _sanitize_origins(origins_list):
    cleaned = []
    for o in origins_list:
        o = o.strip()
        if not o:
            continue
        if not o.startswith(('http://', 'https://')):
            o = 'https://' + o
        cleaned.append(o)
    return cleaned

env_cors = _csv(os.getenv('CORS_ALLOWED_ORIGINS', ''))
if env_cors:
    CORS_ALLOWED_ORIGINS = _sanitize_origins(env_cors)
else:
    try:
        CORS_ALLOWED_ORIGINS = _sanitize_origins(CORS_ALLOWED_ORIGINS)
    except Exception:
        CORS_ALLOWED_ORIGINS = ['https://votebem.online', 'http://votebem.online', 'https://www.votebem.online', 'http://www.votebem.online']
PY
fi

##############################
# Generate docker-compose file with /dados bind mounts
##############################
log "Writing docker-compose to ${COMPOSE_FILE}"
cat > "${COMPOSE_FILE}" << EOF
name: ${APP_NAME}

services:
  db:
    image: postgres:15-alpine
    container_name: ${APP_NAME}_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - ${POSTGRES_DIR}:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME} -h localhost -p 5432 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      ${APP_NAME}_net:
      vps_network:
        aliases:
          - votebem-web

  valkey:
    image: valkey/valkey:latest
    container_name: ${APP_NAME}_valkey
    restart: unless-stopped
    command: ["valkey-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - ${VALKEY_DIR}:/data
    networks:
      - ${APP_NAME}_net

  web:
    build:
      context: ${WEB_CONTEXT}
      dockerfile: Dockerfile
    container_name: ${APP_NAME}_web
    restart: unless-stopped
    env_file:
      - ${ENV_FILE}
    depends_on:
      db:
        condition: service_healthy
      valkey:
        condition: service_started
    volumes:
      - ${STATIC_DIR}:/app/staticfiles
      - ${MEDIA_DIR}:/app/media
      - ${LOG_DIR}:/app/logs
    networks:
      - ${APP_NAME}_net

  nginx:
    image: nginx:1.25-alpine
    container_name: ${APP_NAME}_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - web
    volumes:
      - ${NGINX_CONF_DIR}:/etc/nginx/conf.d
      - ${STATIC_DIR}:/app/staticfiles
      - ${MEDIA_DIR}:/app/media
      - /dados/certbot/certs:/etc/letsencrypt:ro
      - /dados/certbot/acme:/var/www/certbot:ro
    networks:
      - ${APP_NAME}_net

networks:
  ${APP_NAME}_net:
    driver: bridge
  vps_network:
    external: true
EOF

# Clean up legacy redis container if present
docker rm -f "${APP_NAME}_redis" >/dev/null 2>&1 || true

# Bring up the stack
${COMPOSE_CMD} -f "${COMPOSE_FILE}" up -d --build
log "Containers launched. Check logs with: ${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" logs -f"

# Ensure default server on port 80 and reload nginx
sed -i 's/listen 80;/listen 80 default_server;/' "${NGINX_DEFAULT_CONF}" || true
${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T nginx sh -lc "nginx -t && nginx -s reload" || ${COMPOSE_CMD} -f "${COMPOSE_FILE}" restart nginx || true

# Post-deploy database auth check and remediation
sleep 5
WEB_RECENT_LOGS="$( ${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" logs --tail=200 web 2>/dev/null || true )"
if echo "$WEB_RECENT_LOGS" | grep -q "password authentication failed"; then
  warn "Postgres auth failure detected from logs. Resetting ${POSTGRES_DIR} to apply current credentials."
  ${COMPOSE_CMD} -f "${COMPOSE_FILE}" down || true
  rm -rf "${POSTGRES_DIR}"
  mkdir -p "${POSTGRES_DIR}"
  ${SUDO} chown -R "${USR}:${GRP}" "${POSTGRES_DIR%/data}" "${POSTGRES_DIR}" || true
  ${COMPOSE_CMD} -f "${COMPOSE_FILE}" up -d --build
fi

# Direct DB connectivity test from web; auto-reset on failure
DB_TEST_CODE='import os, psycopg2; psycopg2.connect(host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"), dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD")); print("DB OK")'
if ! ${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T web python -c "$DB_TEST_CODE" >/dev/null 2>&1; then
  warn "DB connectivity failed from web. Resetting ${POSTGRES_DIR} to reapply credentials."
  ${COMPOSE_CMD} -f "${COMPOSE_FILE}" down || true
  rm -rf "${POSTGRES_DIR}"
  mkdir -p "${POSTGRES_DIR}"
  ${SUDO} chown -R "${USR}:${GRP}" "${POSTGRES_DIR%/data}" "${POSTGRES_DIR}" || true
  ${COMPOSE_CMD} -f "${COMPOSE_FILE}" up -d --build
fi

# Align static/media/logs ownership to web container user for Whitenoise
WEB_UID="$(${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T web sh -lc 'id -u' 2>/dev/null || echo 0)"
WEB_GID="$(${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T web sh -lc 'id -g' 2>/dev/null || echo 0)"
${SUDO} chown -R "${WEB_UID}:${WEB_GID}" "${STATIC_DIR}" "${MEDIA_DIR}" "${LOG_DIR}" || true

# Run Django migrations and collect static files
${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T web python manage.py migrate --noinput || true
${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T web python manage.py collectstatic --noinput || true

# Post-run guidance: how to correctly configure .env
ENV_PATH="${ENV_FILE:-/dados/votebem/.env}"
cat <<EOF
========================================================================
Environment file (.env) configuration — review required
Location: ${ENV_PATH}

Required keys (example production values):
  DJANGO_SECRET_KEY=(keep existing value; do not rotate arbitrarily)
  DEBUG=False
  USE_HTTPS=True
  BASE_URL=https://votebem.online
  ALLOWED_HOSTS=votebem.online,www.votebem.online
  CSRF_TRUSTED_ORIGINS=https://votebem.online,http://votebem.online,https://www.votebem.online,http://www.votebem.online
  CORS_ALLOWED_ORIGINS=https://votebem.online,http://votebem.online,https://www.votebem.online,http://www.votebem.online
  USE_X_FORWARDED_HOST=True
  SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
  DB_NAME=votebem_db
  DB_USER=votebem_user
  DB_PASSWORD=your-secure-password (must match Postgres; do not change casually)
  DB_HOST=db
  DB_PORT=5432
  REDIS_PASSWORD=your-redis-password

Tips:
  - Edit with: sudo nano ${ENV_PATH}
  - The repo .env is for local dev only; production reads ${ENV_PATH}.
  - If you change DB_PASSWORD after Postgres is initialized, update the DB user password or reset the data directory.
========================================================================
EOF

# Optional SSL bootstrap if certs exist
CERTS_BASE="/dados/certbot/certs/live"
if [[ -d "${CERTS_BASE}" ]]; then
  SSL_DOMAIN="${DOMAIN}"
  if [[ -z "${SSL_DOMAIN}" ]]; then
    SSL_DOMAIN="$(find "${CERTS_BASE}" -maxdepth 1 -mindepth 1 -type d -printf "%f\n" | head -n 1 || true)"
  fi
  if [[ -n "${SSL_DOMAIN}" ]] && [[ -f "${CERTS_BASE}/${SSL_DOMAIN}/fullchain.pem" ]] && [[ -f "${CERTS_BASE}/${SSL_DOMAIN}/privkey.pem" ]]; then
    log "Found certs for ${SSL_DOMAIN}; generating ssl.conf"
    cat > "${NGINX_CONF_DIR}/ssl.conf" << SSL
server {
    listen 443 ssl;
    server_name ${SSL_DOMAIN} ${VPS_IP} localhost;

    ssl_certificate /etc/letsencrypt/live/${SSL_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${SSL_DOMAIN}/privkey.pem;

    location /static/ { alias /app/staticfiles/; }
    location /media/  { alias /app/media/; }

    location / {
        proxy_set_header Host ${SSL_DOMAIN};
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        proxy_redirect off;
        proxy_pass http://votebem-web:8000;
    }
}
SSL
    # Reload nginx to apply SSL config
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" restart nginx || true
  else
    log "SSL certs not found under ${CERTS_BASE}; skipping ssl.conf."
  fi
fi