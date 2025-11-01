#!/bin/bash
# VoteBem - SSL Diagnosis Script
# Collects environment, certificate paths, nginx, and Docker Compose details into a single report.
# Usage:
#   SSL_DOMAIN="votebem.online" bash ./scripts/linux/ssl_diagnosis.sh
#   or: bash ./scripts/linux/ssl_diagnosis.sh -d votebem.online
# The report will be saved to /dados/votebem/ssl_diagnosis-<timestamp>-<domain>.log

set -u
set -o pipefail

APP_DIR="/dados/votebem"
COMPOSE_FILE="${APP_DIR}/docker-compose.yml"

# Colors for output (also included in report for readability)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SUDO=""
if [ "${EUID}" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

DOMAIN="${SSL_DOMAIN:-}"
while getopts ":d:" opt; do
  case ${opt} in
    d)
      DOMAIN="${OPTARG}"
      ;;
    *)
      ;;
  esac
done

# Try to detect domain from nginx/ssl.conf
if [[ -z "${DOMAIN}" && -f "${APP_DIR}/nginx/ssl.conf" ]]; then
  DOMAIN=$(grep -E "server_name" "${APP_DIR}/nginx/ssl.conf" | head -1 | sed -E "s/.*server_name[[:space:]]+([^; ]+).*/\1/")
fi
# Fallback default
if [[ -z "${DOMAIN}" ]]; then DOMAIN="votebem.online"; fi

# Detect certificate directory name from nginx/ssl.conf (preferred)
CERT_DIR_BASENAME=$(grep -o 'ssl_certificate /etc/letsencrypt/live/[^/]*/fullchain.pem' "${APP_DIR}/nginx/ssl.conf" 2>/dev/null | sed -E 's#ssl_certificate /etc/letsencrypt/live/([^/]+)/fullchain.pem#\1#' | head -1)
if [[ -z "${CERT_DIR_BASENAME}" ]]; then CERT_DIR_BASENAME="${DOMAIN}"; fi

REPORT="${APP_DIR}/ssl_diagnosis-$(date +'%Y%m%d-%H%M%S')-${DOMAIN}.log"

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "${REPORT}"; }
warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" | tee -a "${REPORT}"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" | tee -a "${REPORT}"; }
section() { echo -e "\n${BLUE}=== $* ===${NC}" | tee -a "${REPORT}"; }

run() {
  local cmd="$*"
  echo "+ ${cmd}" | tee -a "${REPORT}"
  bash -lc "${cmd}" 2>&1 | tee -a "${REPORT}"
  local ec=${PIPESTATUS[0]}
  echo "exit_code=${ec}" | tee -a "${REPORT}"
  echo "" | tee -a "${REPORT}"
  return ${ec}
}

check_ssh_key() {
  local ssh_dir="$HOME/.ssh"
  local auth_keys_file="$ssh_dir/authorized_keys"

  log "Checking for SSH authorized_keys file..."

  if [ ! -d "$ssh_dir" ]; then
    log "'.ssh' directory not found. Creating it."
    mkdir -p "$ssh_dir"
    chmod 700 "$ssh_dir"
  fi

  if [ -f "$auth_keys_file" ] && [ -s "$auth_keys_file" ] && grep -q -E "^ssh-(rsa|dss|ed25519|ecdsa)" "$auth_keys_file"; then
    log "Found valid public key in '$auth_keys_file'."
  else
    if [ ! -f "$auth_keys_file" ]; then
      warn "SSH authorized_keys file not found at '$auth_keys_file'."
    else
      warn "'$auth_keys_file' exists but is empty or contains no valid public keys."
    fi
    warn "This file is important for secure remote access (e.g., using 'scp' to copy files)."
    
    # This is an interactive part, so it won't be fully logged in the same way as `run` commands.
    # The prompt will be logged by `tee`, but the user input will not.
    echo -e "${YELLOW}PASTE PUBLIC KEY (or press Enter to skip):${NC} " | tee -a "${REPORT}"
    read -r pub_key
    
    if [ -n "$pub_key" ]; then
      if [[ "$pub_key" =~ ^ssh-(rsa|dss|ed25519|ecdsa) ]]; then
        log "Adding public key to '$auth_keys_file'."
        echo "$pub_key" >> "$auth_keys_file"
        chmod 600 "$auth_keys_file"
        log "Public key added."
      else
        error "Invalid public key format. Skipping."
      fi
    else
      log "No public key provided. Skipping step."
    fi
  fi
}

log "Starting SSL diagnosis"
log "App dir: ${APP_DIR}"
log "Compose file: ${COMPOSE_FILE}"
log "Domain: ${DOMAIN}"
log "Cert dir basename: ${CERT_DIR_BASENAME}"
log "SUDO prefix: '${SUDO}' (blank means root)"

section "System Info"
run "date"
run "hostname -A || hostname -I || true"
run "uname -a"
run "cat /etc/os-release || lsb_release -a || true"
run "id"
run "groups"

section "SSH Key Diagnosis"
check_ssh_key

section "Certbot & Snap"
run "which certbot || true"
run "certbot --version || ${SUDO} certbot --version || true"
run "${SUDO} certbot certificates || true"
run "snap version || true"

section "Certificate Paths: Classic and Snap"
run "${SUDO} ls -la /etc/letsencrypt/live || true"
run "${SUDO} ls -la /var/snap/certbot/common/etc/letsencrypt/live || true"

SRC="/etc/letsencrypt/live/${CERT_DIR_BASENAME}"
if ! ${SUDO} test -d "${SRC}"; then
  SRC="/var/snap/certbot/common/etc/letsencrypt/live/${CERT_DIR_BASENAME}"
fi
log "Selected certificate source: ${SRC}"
run "${SUDO} ls -la \"${SRC}\" || true"
run "${SUDO} stat -c '%n: mode=%a owner=%u:%g' \"${SRC}/fullchain.pem\" \"${SRC}/privkey.pem\" || true"
run "${SUDO} readlink -f \"${SRC}/fullchain.pem\" || true"
run "${SUDO} readlink -f \"${SRC}/privkey.pem\" || true"

section "Destination Mounted Path"
DEST="/dados/certbot/certs/live/${CERT_DIR_BASENAME}"
log "Destination path expected: ${DEST}"
run "${SUDO} ls -la \"${DEST}\" || true"

section "Nginx Host Config"
run "${SUDO} ls -la /dados/nginx/conf.d || true"
run "${SUDO} ls -la /dados/nginx/conf.d/default.conf || true"
run "${SUDO} grep -nE 'ssl_certificate(_key)?|server_name' /dados/nginx/conf.d/default.conf || true"

section "Docker & Compose"
run "docker --version || true"
run "docker info | sed -n '1,25p' || true"

COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
fi
log "Detected COMPOSE_CMD: ${COMPOSE_CMD:-none}"

if [[ -n "${COMPOSE_CMD}" && -f "${COMPOSE_FILE}" ]]; then
  section "Compose PS"
  run "${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" ps || true"
  NGINX_CID=$(${COMPOSE_CMD} -f "${COMPOSE_FILE}" ps -q nginx 2>/dev/null || true)
  log "nginx container id: ${NGINX_CID:-none}"
  if [[ -n "${NGINX_CID}" ]]; then
    section "Container Mounts"
    run "docker inspect \"${NGINX_CID}\" --format '{{range .Mounts}}{{printf \"%s -> %s\\n\" .Source .Destination}}{{end}}' || docker inspect \"${NGINX_CID}\" || true"

    section "Nginx In-Container Checks"
    run "${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" exec -T nginx nginx -t || true"
    run "${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" exec -T nginx ls -la /etc/letsencrypt/live || true"
    run "${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" exec -T nginx ls -la /etc/letsencrypt/live/${CERT_DIR_BASENAME} || true"
    run "${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" logs --no-color --tail=200 nginx || true"
  fi
else
  warn "Compose not detected or compose file missing. Skipping container checks."
fi

section "Network Ports"
run "${SUDO} ss -tlnp | grep ':443' || ${SUDO} netstat -tlnp | grep ':443' || true"
run "${SUDO} iptables -S || true"

section "HTTP/HTTPS Tests"
run "curl -s -I http://${DOMAIN} | tr -d '\r' || true"
run "curl -s -I https://${DOMAIN}/health/ | tr -d '\r' || true"

section "Renewal & Cron"
run "${SUDO} crontab -l || true"
run "${SUDO} systemctl list-timers --all | grep -i certbot || true"
run "${SUDO} systemctl status certbot.timer || ${SUDO} systemctl status snap.certbot.renew.timer || true"

section "Let\'s Encrypt Renewal Configs"
run "${SUDO} ls -la /etc/letsencrypt/renewal || true"
run "${SUDO} ls -la /var/snap/certbot/common/etc/letsencrypt/renewal || true"
run "${SUDO} grep -R -n \"${CERT_DIR_BASENAME}\" /etc/letsencrypt/renewal /var/snap/certbot/common/etc/letsencrypt/renewal 2>/dev/null || true"

section "Filesystem Scan for PEMs"
run "${SUDO} find /etc/letsencrypt/live /var/snap/certbot/common/etc/letsencrypt/live -maxdepth 2 -type f -name 'fullchain.pem' -o -name 'privkey.pem' 2>/dev/null || true"

log "Diagnosis finished. Report saved to: ${REPORT}"
log "Please share the report content so I can pinpoint the issue."