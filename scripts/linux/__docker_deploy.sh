#!/usr/bin/env bash

# Avoid __docker_deploy.sh unless you intend to run a multisite Nginx inside Docker on a shared vps_network and move away from host Nginx. It’s a different architecture and will complicate your current setup.
# Continue with linuxScripts/3__deploy_votebem_in_baixavideo.sh . It is designed for your exact scenario: a VPS already serving baixavideo.site with host-level Nginx, adding votebem.online as another site and proxying to the Django app on port 8001 .

# --- SSH authorized_keys check (resilient, optional input) ---
ensure_authorized_keys_for_user() {
  local user="$1"
  local home_dir
  home_dir=$(eval echo "~$user")
  if [ -z "$home_dir" ] || [ ! -d "$home_dir" ]; then
    echo "SSH: Home directory for '$user' not found. Skipping."
    return 0
  fi
  local ssh_dir="$home_dir/.ssh"
  local auth="$ssh_dir/authorized_keys"
  local SUDO=""
  if [ "${EUID:-$(id -u)}" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

  if [ ! -d "$ssh_dir" ]; then
    echo "SSH: Creating $ssh_dir for '$user'."
    $SUDO mkdir -p "$ssh_dir" || true
    $SUDO chmod 700 "$ssh_dir" || true
    if id "$user" >/dev/null 2>&1; then $SUDO chown "$user:$user" "$ssh_dir" || true; fi
  fi

  if [ -f "$auth" ] && grep -qE '^ssh-(rsa|dss|ed25519|ecdsa)' "$auth"; then
    echo "SSH: '$user' already has a public key in authorized_keys."
    return 0
  fi

  if [ ! -f "$auth" ]; then
    echo "SSH: authorized_keys not found for '$user' at '$auth'."
  else
    echo "SSH: authorized_keys exists for '$user' but no valid public keys."
  fi
  echo "SSH: authorized_keys enables passwordless SSH/SCP access to this account."
  read -r -p "Paste a public key for '$user' (optional, Enter to skip): " PUBKEY || true
  if [ -n "$PUBKEY" ]; then
    if printf '%s' "$PUBKEY" | grep -qE '^ssh-(rsa|dss|ed25519|ecdsa)'; then
      echo "SSH: Adding provided public key to '$auth'."
      printf '%s\n' "$PUBKEY" | $SUDO tee -a "$auth" >/dev/null || true
      $SUDO chmod 600 "$auth" || true
      if id "$user" >/dev/null 2>&1; then $SUDO chown "$user:$user" "$auth" || true; fi
    else
      echo "SSH: Provided key format seems invalid. Skipping."
    fi
  else
    echo "SSH: No public key provided. Skipping."
  fi
}

# Run check for current and 'votebem' users, if present
ensure_authorized_keys_for_user "$(whoami)"
if id votebem >/dev/null 2>&1; then ensure_authorized_keys_for_user "votebem"; fi

set -euo pipefail

# __docker_deploy.sh — Deployment orchestrator for VoteBem on Docker
#
# Overview
# - Standardizes host bind mounts under `/dados` for portability and backup discipline.
# - Generates a `docker-compose.yml` with absolute host paths and sane defaults.
# - Provisions required directories and ownership, creates/updates `.env`, and patches Django settings.
# - Builds and launches services: MariaDB (`db`), Valkey/Redis (`valkey`), Django+Gunicorn (`web`), and Nginx (`nginx`).
#
# Multi‑site Nginx and networking assumptions
# - This app is accessed via a multi‑site Nginx container that reverse‑proxies requests.
# - Cross‑stack service discovery relies on a shared Docker network: `vps_network`.
# - The Django/Gunicorn container must join `vps_network` with an alias like `votebem-web` so Nginx can resolve it.
# - The Nginx default site proxies to `http://votebem-web:8000`, which resolves via Docker’s embedded DNS on `vps_network`.
#
# Bind mount structure (host → container)
# - `/dados/votebem/app` → project repository (build context for `web`).
# - `/dados/votebem/logs` → `/app/logs` (app logs, rotated externally if desired).
# - `/dados/nginx/app/static` → `/app/staticfiles` (collected static; served by Nginx or Whitenoise).
# - `/dados/nginx/app/media` → `/app/media` (user uploads; served by Nginx).
# - `/dados/mariadb/votebem/data` → MariaDB data dir (persistent DB state).
# - `/dados/valkey/votebem/data` → Valkey data dir (persistent cache state when AOF is enabled).
# - `/dados/nginx/conf.d` → Nginx site configs inside container.
# - `/dados/certbot/certs` → `/etc/letsencrypt` (TLS certificates inside Nginx).
# - `/dados/certbot/acme` → `/var/www/certbot` (ACME HTTP‑01 challenge directory).
#
# Generated configuration artifacts
# - `.env`: app environment (DB, Redis, Django, domains), with secrets preserved if already present.
# - `docker-compose.yml`: defines containers, volumes, networks, health checks, and dependencies.
# - `default.conf`: Nginx catch‑all site for non‑mapped domains, proxying to `votebem-web:8000`.
#
# Security and operational notes
# - Uses `set -euo pipefail` for strict error handling; missing variables and failing commands abort.
# - Health checks ensure MariaDB readiness before `web` starts; logs are scanned for common auth issues.
# - If DB auth fails, the script can reset the MariaDB data directory to reapply credentials (destructive).
# - Certificates are expected to be managed by Certbot on the host and mounted read‑only into Nginx.
#
# Usage
# - Run on the target host with Docker/Compose installed.
# - Provide domain/IP when prompted (defaults exist), or script reads from `.env` after creation.
# - After launch, verify `vps_network` membership and DNS resolution: `getent hosts votebem-web` within Nginx.
#
# The remainder of the script implements these steps and generates the runtime configuration.

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

# Warn if legacy docker-compose via snap is detected (can cause /var/lib/snapd/void cwd issues)
if [[ "${COMPOSE_CMD}" == "docker-compose" ]]; then
  DOCKER_COMPOSE_BIN="$(command -v docker-compose || echo "")"
  if [[ "${DOCKER_COMPOSE_BIN}" == *snap* ]]; then
    warn "Detected docker-compose installed via snap; using absolute -f paths to avoid snap cwd issues."
  fi
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
MEDIA_DIR="/dados/votebem/votebem/media"   #arquivos de midia ficam no próprio diretorio do repo original
BACKUPS_DIR="${BASE_DIR}/backups"
SSL_DIR="${BASE_DIR}/ssl"

# Service-specific roots
MARIADB_DIR="/dados/mariadb/${APP_NAME}/data"
VALKEY_DIR="/dados/valkey/${APP_NAME}/data"
REDIS_DIR="/dados/redis/${APP_NAME}/data"
NGINX_CONF_DIR="/dados/nginx/conf.d"
NGINX_DEFAULT_CONF="${NGINX_CONF_DIR}/default.conf"

# Repository (adjust if needed)
REPO_URL_SSH="git@github.com:wagnercateb/votebem.git"
REPO_URL_HTTPS="https://github.com/wagnercateb/votebem.git"

# Normalize paths to avoid CRLF issues when the script is edited on Windows (WSL)
strip_cr() { printf '%s' "$1" | tr -d '\r'; }
trim_ws() {
  local s="$1"
  # Remove leading whitespace
  s="${s#${s%%[![:space:]]*}}"
  # Remove trailing whitespace
  s="${s%${s##*[![:space:]]}}"
  printf '%s' "$s"
}
BASE_DIR="$(strip_cr "${BASE_DIR}")"
REPO_DIR="$(strip_cr "${REPO_DIR}")"
COMPOSE_FILE="$(strip_cr "${COMPOSE_FILE}")"
ENV_FILE="$(strip_cr "${ENV_FILE}")"
LOG_DIR="$(strip_cr "${LOG_DIR}")"
STATIC_DIR="$(strip_cr "${STATIC_DIR}")"
MEDIA_DIR="$(strip_cr "${MEDIA_DIR}")"
BACKUPS_DIR="$(strip_cr "${BACKUPS_DIR}")"
SSL_DIR="$(strip_cr "${SSL_DIR}")"
MARIADB_DIR="$(strip_cr "${MARIADB_DIR}")"
VALKEY_DIR="$(strip_cr "${VALKEY_DIR}")"
NGINX_CONF_DIR="$(strip_cr "${NGINX_CONF_DIR}")"
NGINX_DEFAULT_CONF="$(strip_cr "${NGINX_DEFAULT_CONF}")"

# Prompt helper with default value (supports silent input for secrets)
prompt_with_default() {
  local label="$1"; local def="$2"; local silent="${3:-0}"; local input="";
  if [[ "$silent" -eq 1 ]]; then
    read -s -p "Enter ${label} (default: ${def}): " input; echo
  else
    read -p "Enter ${label} (default: ${def}): " input
  fi
  if [[ -z "$input" ]]; then printf '%s' "$def"; else printf '%s' "$input"; fi
}

##############################
# Input (domain, IP)
# Set default domain and prompt with fallback
DOMAIN_DEFAULT="votebem.online"
read -rp "Enter domain (default: ${DOMAIN_DEFAULT}): " DOMAIN_INPUT || DOMAIN_INPUT=""
DOMAIN="${DOMAIN_INPUT:-$DOMAIN_DEFAULT}"
VPS_IP_DEFAULT="45.55.144.233"
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
  "${MARIADB_DIR}" "${VALKEY_DIR}" "${NGINX_CONF_DIR}" \
  "/dados/certbot/acme" "/dados/certbot/certs"

# Assign ownership to invoking user (preserve original user when running via sudo)
USR="${SUDO_USER:-$(id -un)}"; GRP="$(id -gn "${USR}")"
${SUDO} chown -R "${USR}:${GRP}" \
  "${BASE_DIR}" "${MARIADB_DIR%/data}" "${VALKEY_DIR%/data}" \
  "${MARIADB_DIR}" "${VALKEY_DIR}" "${NGINX_CONF_DIR}" "${STATIC_DIR}" "${MEDIA_DIR}" \
  "/dados/certbot/acme" "/dados/certbot/certs"
${SUDO} chmod -R 0777 "${STATIC_DIR}" "${MEDIA_DIR}" "${LOG_DIR}"

##############################
# Prepare Nginx default.conf
##############################
log "Generating Nginx default.conf at ${NGINX_DEFAULT_CONF}"
cat > "${NGINX_DEFAULT_CONF}" << 'CONF'
# Default catch‑all site for non‑mapped domains
# This runs inside the multi‑site Nginx container and proxies to the app
# using the Docker DNS alias `votebem-web` on the shared `vps_network`.
server {
    listen 80 default_server;      # default vhost for HTTP requests without a specific server_name
    server_name _;                 # wildcard: applies when no other vhost matches

    # Static files (if needed for default site)
    location /static/ {
        alias /app/staticfiles/;   # bind‑mounted from host: /dados/nginx/app/static
        # Consider adding cache headers here for performance if used
    }

    # Media uploads (optional)
    location /media/ {
        alias /app/media/;         # bind‑mounted from host: /dados/nginx/app/media
    }

    # Proxy all other requests to the upstream app container
    location / {
        # Preserve original request metadata for Django behind a reverse proxy
        proxy_set_header Host $host;                       # original host (domain)
        proxy_set_header X-Real-IP $remote_addr;           # client IP as seen by Nginx
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; # proxy chain
        proxy_set_header X-Forwarded-Proto $scheme;        # http/https scheme
        proxy_set_header X-Forwarded-Host $host;           # forwarded host
        proxy_set_header X-Forwarded-Port $server_port;    # forwarded port
        proxy_redirect off;                                # do not rewrite Location headers

        # Upstream target: DNS name must be resolvable via Docker DNS on vps_network
        proxy_pass http://votebem-web:8000;                # Gunicorn listens on 8000 inside app container

        # Optional tuning (uncomment and adjust as needed)
        # proxy_connect_timeout 5s;
        # proxy_read_timeout 60s;
        # proxy_buffering on;
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
# Ensure repository directory exists after clone/update
if [[ ! -d "${REPO_DIR}" ]]; then
  err "Repository directory ${REPO_DIR} not found after clone. Check permissions or SSH setup."
  exit 1
fi
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

# Prompt user to confirm or override secrets (defaults shown). Password prompts hidden.
DB_PASSWORD="$(prompt_with_default 'DB_PASSWORD' "${DB_PASSWORD}" 1)"; DB_PASSWORD="$(trim_ws "$(strip_cr "${DB_PASSWORD}")")"
REDIS_PASSWORD="$(prompt_with_default 'REDIS_PASSWORD' "${REDIS_PASSWORD}" 1)"; REDIS_PASSWORD="$(trim_ws "$(strip_cr "${REDIS_PASSWORD}")")"
DJANGO_SECRET_KEY="$(prompt_with_default 'DJANGO_SECRET_KEY' "${DJANGO_SECRET_KEY}")"; DJANGO_SECRET_KEY="$(trim_ws "$(strip_cr "${DJANGO_SECRET_KEY}")")"

# Detect web build context (directory containing Dockerfile)
WEB_CONTEXT=""
if [[ -f "${REPO_DIR}/django_votebem/Dockerfile" ]]; then
  WEB_CONTEXT="${REPO_DIR}/django_votebem"
elif [[ -f "${REPO_DIR}/Dockerfile" ]]; then
  WEB_CONTEXT="${REPO_DIR}"
elif [[ -d "${REPO_DIR}" ]]; then
  WEB_CONTEXT="$(find "${REPO_DIR}" -maxdepth 3 -type f -name Dockerfile -printf '%h\n' 2>/dev/null | head -n 1 || true)"
fi
# Sanitize path (strip CR) for WSL/Windows-edited script
WEB_CONTEXT="$(strip_cr "${WEB_CONTEXT}")"
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
DB_PORT=3306

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
SETTINGS_FILE="$(find "${REPO_DIR}" -maxdepth 3 -type f -name 'settings.py' 2>/dev/null | head -n 1 || true)"
# Sanitize path (strip CR) for WSL/Windows-edited script
SETTINGS_FILE="$(strip_cr "${SETTINGS_FILE}")"
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
# Ensure compose directory exists
mkdir -p "$(dirname "${COMPOSE_FILE}")"
# Detailed explanation of the generated docker-compose.yml
#
# Top-level keys
# - `name`: Compose project name; used as a prefix for network and resource scoping.
#
# services:
# - `db` (MariaDB 11):
#   - `environment`: DB name/user/pass exported to container.
#   - `volumes`: bind-mount persistent data at `${MARIADB_DIR}`.
#   - `healthcheck`: waits until `mysqladmin ping` reports ready before dependent services start.
#   - `networks`: joins `${APP_NAME}_net` (private app network). If connected to `vps_network` with an alias,
#                 note that cross-stack alias is intended for the `web` app, not the database.
#
# - `valkey` (Redis-compatible Valkey):
#   - `command`: enables append-only file (AOF) and sets a password.
#   - `volumes`: persistent data at `${VALKEY_DIR}`.
#   - `networks`: private app network only.
#
# - `web` (Django + Gunicorn):
#   - `build`: uses `${WEB_CONTEXT}/Dockerfile` as the build context.
#   - `env_file`: loads runtime env from `${ENV_FILE}`.
#   - `depends_on`: waits for `db` (healthy) and `valkey` (started).
#   - `volumes`: mounts static, media, and logs directories.
#   - `networks`: joins `${APP_NAME}_net`. To allow Nginx (in a separate stack) to resolve the app,
#                 this service must also join `vps_network` with alias `votebem-web`. If the alias appears under
#                 another service, move it under `web` for correct upstream resolution.
#
# - `nginx` (reverse proxy):
#   - `ports`: exposes 80 and 443 to the host.
#   - `depends_on`: starts after `web`.
#   - `volumes`: site configs, static/media, certs, and ACME directory mounts.
#   - `networks`: joins `${APP_NAME}_net` (within this stack). In a multi-site deployment, an external Nginx may live
#                 in another stack attached to `vps_network`.
#
# networks:
# - `${APP_NAME}_net`: private bridge for intra-stack communication.
# - `vps_network`: external network enabling cross-stack service discovery via Docker DNS.
#   Ensure this exists and both Nginx and the `web` container are attached to it.
cat > "${COMPOSE_FILE}" << EOF
name: ${APP_NAME}

services:
  db:
    image: "mariadb:11"
    container_name: ${APP_NAME}_db
    restart: unless-stopped
    environment:
      MARIADB_DATABASE: "${DB_NAME}"
      MARIADB_USER: "${DB_USER}"
      MARIADB_PASSWORD: "${DB_PASSWORD}"
      MARIADB_ROOT_PASSWORD: "${DB_PASSWORD}"
      TZ: "UTC"
    volumes:
      - "${MARIADB_DIR}:/var/lib/mysql"
    ports:
      - "${DB_HOST_PORT:-3307}:3306"
    healthcheck:
      test: ["CMD-SHELL", "mariadb -h 127.0.0.1 -uroot -p${DB_PASSWORD} -e 'SELECT 1' >/dev/null 2>&1 || exit 1"]
      interval: 10s
      timeout: 10s
      retries: 12
      start_period: 60s
    networks:
      - ${APP_NAME}_net

  valkey:
    image: valkey/valkey:latest
    container_name: ${APP_NAME}_valkey
    restart: unless-stopped
    command: ["valkey-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - "${VALKEY_DIR}:/data"
    networks:
      - ${APP_NAME}_net

  web:
    build:
      context: "${WEB_CONTEXT}"
      dockerfile: Dockerfile
    container_name: ${APP_NAME}_web
    restart: unless-stopped
    env_file:
      - "${ENV_FILE}"
    depends_on:
      db:
        condition: service_healthy
      valkey:
        condition: service_started
    volumes:
      - "${STATIC_DIR}:/app/staticfiles"
      - "${MEDIA_DIR}:/app/media"
      - "${LOG_DIR}:/app/logs"
    networks:
      ${APP_NAME}_net:
      vps_network:
        aliases:
          - votebem-web

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
      - "${NGINX_CONF_DIR}:/etc/nginx/conf.d"
      - "${STATIC_DIR}:/app/staticfiles"
      - "${MEDIA_DIR}:/app/media"
      - "/dados/certbot/certs:/etc/letsencrypt:ro"
      - "/dados/certbot/acme:/var/www/certbot:ro"
    networks:
      - ${APP_NAME}_net

networks:
  ${APP_NAME}_net:
    driver: bridge
  vps_network:
    external: true
EOF

# Normalize line endings in generated files (avoid CRLF issues)
sed -i 's/\r$//' "${COMPOSE_FILE}" 2>/dev/null || true
sed -i 's/\r$//' "${ENV_FILE}" 2>/dev/null || true

# Prepare a temp copy to mitigate environment-specific path resolution issues
TMP_COMPOSE="/tmp/${APP_NAME}-compose.yml"
cp -f "${COMPOSE_FILE}" "${TMP_COMPOSE}" 2>/dev/null || true

# Clean up legacy redis container if present
docker rm -f "${APP_NAME}_redis" >/dev/null 2>&1 || true

# Bring up the stack using absolute compose file path for robustness across environments
COMPOSE_TO_USE="${COMPOSE_FILE}"
if [[ ! -f "${COMPOSE_FILE}" ]]; then
  warn "Compose file not found at ${COMPOSE_FILE}. Directory contents of $(dirname "${COMPOSE_FILE}"):"
  ls -la "$(dirname "${COMPOSE_FILE}")" || true
fi
# If compose plugin fails to parse the main file, fallback to /tmp copy
if ! ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" config >/dev/null 2>&1; then
  warn "Compose failed to open ${COMPOSE_TO_USE}; falling back to ${TMP_COMPOSE}"
  COMPOSE_TO_USE="${TMP_COMPOSE}"
fi
# Ensure the shared external network exists (avoids: 'network vps_network declared as external, but could not be found')
if ! docker network inspect vps_network >/dev/null 2>&1; then
  log "Creating shared Docker bridge network 'vps_network'"
  docker network create --driver=bridge vps_network || warn "Failed to create vps_network; stack startup may fail."
fi
${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" up -d --build
log "Containers launched. Check logs with: ${COMPOSE_CMD} -f \"${COMPOSE_TO_USE}\" logs -f"

# Auto-remediate MariaDB tc.log corruption (Bad magic header)
# If MariaDB aborts startup due to a corrupted tc.log, remove it and retry DB startup.
DB_RECENT_LOGS="$(${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" logs --tail=200 db 2>/dev/null || true)"
if echo "$DB_RECENT_LOGS" | grep -qi "Bad magic header in tc log"; then
  warn "Detected MariaDB tc.log corruption (Bad magic header). Removing tc.log and retrying DB startup."
  ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" stop db || true
  rm -f "${MARIADB_DIR}/tc.log" || true
  ${SUDO} chown -R "${USR}:${GRP}" "${MARIADB_DIR%/data}" "${MARIADB_DIR}" || true
  ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" up -d db || true
  # Give MariaDB a moment to re-initialize cleanly
  sleep 5
fi

# Auto-remediate common permission/ownership issues on data dir
DB_RECENT_LOGS="$(${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" logs --tail=200 db 2>/dev/null || true)"
if echo "$DB_RECENT_LOGS" | grep -qiE "Permission denied|Can't create/write to file|Can't change dir to '/var/lib/mysql'"; then
  warn "Detected MariaDB data directory permission issue. Fixing ownership to uid:gid 999:999 and restarting DB."
  ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" stop db || true
  ${SUDO} chown -R 999:999 "${MARIADB_DIR%/data}" "${MARIADB_DIR}" || true
  ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" up -d db || true
  sleep 5
fi

# Ensure default server on port 80 and reload nginx
sed -i 's/listen 80;/listen 80 default_server;/' "${NGINX_DEFAULT_CONF}" || true
${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" exec -T nginx sh -lc "nginx -t && nginx -s reload" || ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" restart nginx || true

# Post-deploy database auth check and remediation
sleep 5
WEB_RECENT_LOGS="$( ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" logs --tail=200 web 2>/dev/null || true )"
if echo "$WEB_RECENT_LOGS" | grep -qi "access denied for user\|authentication"; then
  warn "MariaDB auth failure detected from logs. Resetting ${MARIADB_DIR} to apply current credentials."
  ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" down || true
  rm -rf "${MARIADB_DIR}"
  mkdir -p "${MARIADB_DIR}"
  ${SUDO} chown -R "${USR}:${GRP}" "${MARIADB_DIR%/data}" "${MARIADB_DIR}" || true
  ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" up -d --build
fi

# Direct DB connectivity test from web; auto-reset on failure
DB_TEST_CODE='import os, pymysql; pymysql.connect(host=os.getenv("DB_HOST"), port=int(os.getenv("DB_PORT", "3306")), db=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD")); print("DB OK")'
if ! ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" exec -T web python -c "$DB_TEST_CODE" >/dev/null 2>&1; then
  warn "DB connectivity failed from web. Resetting ${MARIADB_DIR} to reapply credentials."
  ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" down || true
  rm -rf "${MARIADB_DIR}"
  mkdir -p "${MARIADB_DIR}"
  ${SUDO} chown -R "${USR}:${GRP}" "${MARIADB_DIR%/data}" "${MARIADB_DIR}" || true
  ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" up -d --build
fi

# Align static/media/logs ownership to web container user for Whitenoise
WEB_UID="$(${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" exec -T web sh -lc 'id -u' 2>/dev/null || echo 0)"
WEB_GID="$(${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" exec -T web sh -lc 'id -g' 2>/dev/null || echo 0)"
${SUDO} chown -R "${WEB_UID}:${WEB_GID}" "${STATIC_DIR}" "${MEDIA_DIR}" "${LOG_DIR}" || true

# Run Django migrations and collect static files
${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" exec -T web python manage.py migrate --noinput || true
${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" exec -T web python manage.py collectstatic --noinput || true

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
  DB_PASSWORD=your-secure-password (must match MariaDB; do not change casually)
  DB_HOST=db
  DB_PORT=3306
  REDIS_PASSWORD=your-redis-password

Tips:
  - Edit with: sudo nano ${ENV_PATH}
  - The repo .env is for local dev only; production reads ${ENV_PATH}.
  - If you change DB_PASSWORD after MariaDB is initialized, update the DB user password or reset the data directory.
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
    ${COMPOSE_CMD} -f "${COMPOSE_TO_USE}" restart nginx || true
  else
    log "SSL certs not found under ${CERTS_BASE}; skipping ssl.conf."
  fi
fi
