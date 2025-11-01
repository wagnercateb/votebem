#!/bin/bash

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

# VoteBem - SSL Setup Script with Let's Encrypt
# This script sets up SSL certificates using Let's Encrypt and configures nginx for HTTPS
# Run as votebem user from project root: ./scripts/setup_ssl.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/dados/votebem"
DOMAIN=""
EMAIL=""

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Ensure the script runs as 'votebem'; gracefully handle sudo/root
TARGET_USER="votebem"

# Determine SUDO prefix
if [ "$EUID" -eq 0 ]; then
  SUDO=""
else
  SUDO="sudo"
fi

# Create user if missing (only when root)
if ! id "$TARGET_USER" >/dev/null 2>&1; then
  if [ "$EUID" -ne 0 ]; then
    error "User '$TARGET_USER' does not exist. Please run this script with sudo so it can create the user automatically."
  fi
  log "Creating $TARGET_USER user..."
  useradd -m -s /bin/bash "$TARGET_USER" || true
  # Ensure docker group
  if ! getent group docker >/dev/null 2>&1; then
    log "Creating docker group..."
    groupadd docker
  fi
  usermod -aG docker "$TARGET_USER" || true
  # Ensure sudo privileges
  usermod -aG sudo "$TARGET_USER" || true
  # Set password if provided, otherwise prompt
  if [ -n "$VOTEBEM_PASSWORD" ]; then
    echo "$TARGET_USER:$VOTEBEM_PASSWORD" | chpasswd
    log "Password for $TARGET_USER set from VOTEBEM_PASSWORD env."
  else
    log "Please set a password for $TARGET_USER."
    passwd "$TARGET_USER"
  fi
  log "User '$TARGET_USER' ready (sudo + docker groups)."
fi

# Validate invoking user: allow sudo when SUDO_USER=votebem
CURRENT_USER="$(id -un)"
if [ "$CURRENT_USER" != "$TARGET_USER" ]; then
  if [ "$EUID" -eq 0 ] && [ "${SUDO_USER:-}" = "$TARGET_USER" ]; then
    log "Detected sudo invocation by '$TARGET_USER'; proceeding."
  else
    warn "Current user is '$CURRENT_USER'. This script must be run as '$TARGET_USER'."
    warn "Run it as: sudo -u $TARGET_USER -H bash /dados/votebem/scripts/linux/setup_ssl.sh"
    exit 1
  fi
fi

# Pre-flight sudo credential cache (prompts for $TARGET_USER password if needed)
if [ "$EUID" -ne 0 ]; then
  if ! groups "$TARGET_USER" | grep -qw sudo; then
    error "User '$TARGET_USER' lacks sudo privileges. Add to sudo group and re-run."
  fi
  log "Obtaining sudo credentials..."
  sudo -v || error "Failed to obtain sudo credentials for '$TARGET_USER'."
fi

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    error "Docker is not installed or not available to this user"
fi

# Detect docker compose command (plugin vs legacy)
COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    error "Docker Compose is not installed"
fi

log "Starting SSL Setup for VoteBem..."

# Get domain and email for SSL (with defaults)
DOMAIN_DEFAULT="votebem.online"
EMAIL_DEFAULT="wagnercateb@gmail.com"
read -rp "Enter your domain name (default: ${DOMAIN_DEFAULT}): " DOMAIN_INPUT
DOMAIN="${DOMAIN_INPUT:-$DOMAIN_DEFAULT}"
read -rp "Enter your email for SSL certificate (default: ${EMAIL_DEFAULT}): " EMAIL_INPUT
EMAIL="${EMAIL_INPUT:-$EMAIL_DEFAULT}"

# Validate inputs
if [[ -z "$DOMAIN" ]]; then
    error "Domain name is required for SSL setup"
fi

if [[ -z "$EMAIL" ]]; then
    error "Email is required for SSL certificate"
fi

# Navigate to application directory
cd "$APP_DIR"

COMPOSE_FILE="${APP_DIR}/docker-compose.yml"
# Check and start containers
if [[ ! -f "${COMPOSE_FILE}" ]]; then
    error "docker-compose.yml not found at ${COMPOSE_FILE}. Please run the deployment script first."
fi
if ! ${COMPOSE_CMD} -f "${COMPOSE_FILE}" ps | grep -q "Up"; then
    warn "Containers are not running. Attempting to start them..."
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" up -d
    sleep 30
    if ! ${COMPOSE_CMD} -f "${COMPOSE_FILE}" ps | grep -q "Up"; then
        error "Failed to start containers. Please run the deployment script first."
    fi
fi

log "Domain: $DOMAIN"
log "Email: $EMAIL"

# Get server IP for ALLOWED_HOSTS
log "Detecting server IP address..."
SERVER_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip || hostname -I | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    warn "Could not detect server IP address automatically"
    SERVER_IP="127.0.0.1"
fi
log "Server IP detected: $SERVER_IP"

# Create SSL directory
mkdir -p ssl

# Stop nginx temporarily to allow certbot to bind to port 80
# Nginx stop will be performed only if issuing a new cert

# Install certbot if not already installed
if ! command -v certbot &> /dev/null; then
    log "Installing certbot..."
    ${SUDO} apt update
    ${SUDO} apt install -y certbot
fi

# Idempotent certificate issuance: skip if already present
log "Checking for existing certificate for ${DOMAIN}..."
CERT_EXISTS=false
if ${SUDO} certbot certificates --cert-name "$DOMAIN" >/dev/null 2>&1; then
    CERT_EXISTS=true
    log "Existing certificate found for ${DOMAIN}; skipping issuance."
fi

if [ "$CERT_EXISTS" != true ]; then
    log "Stopping nginx container temporarily to issue certificate..."
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" stop nginx

    log "Generating SSL certificate with Let's Encrypt..."
    if ${SUDO} certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        --cert-name "$DOMAIN" \
        -d "$DOMAIN" \
        -d "www.$DOMAIN"; then
        log "SSL certificate generated successfully"
    else
        warn "Certbot issuance failed. Checking if a certificate already exists..."
        if ${SUDO} certbot certificates --cert-name "$DOMAIN" >/dev/null 2>&1; then
            log "A certificate for ${DOMAIN} exists; proceeding with sync."
        else
            error "Failed to generate SSL certificate and none exists. Please check DNS settings and try again."
        fi
    fi
fi

# Locate certificate directory and sync to container-mounted path
log "Locating certificate directory..."
CERT_SOURCE_DIR=""
CERT_DIR_BASENAME=""
CERT_INFO=$(${SUDO} certbot certificates 2>/dev/null || true)
log "Captured certbot inventory for ${DOMAIN}"
printf "%s\n" "$CERT_INFO" | sed 's/^/  /'

# Prefer existing destination if certs are already synced from previous runs
DEST_CAND=""
for d in "/dados/certbot/certs/live/${DOMAIN}" \
         "/dados/certbot/certs/live/www.${DOMAIN}" \
         "/dados/certbot/certs/live/${DOMAIN}"* \
         "/dados/certbot/certs/live/www.${DOMAIN}"*; do
  log "Probing destination candidate: $d"
  if [[ -d "$d" ]] && [[ -f "$d/fullchain.pem" && -f "$d/privkey.pem" ]]; then
    log "Found destination certs: $d"
    DEST_CAND="$d"; break
  fi
done
if [[ -n "$DEST_CAND" ]]; then
  CERT_DIR_BASENAME="$(basename "$DEST_CAND")"
  log "Found existing synced certs at ${DEST_CAND}; using basename ${CERT_DIR_BASENAME}"
else
  # Fast-path: use certbot's --cert-name to get the exact certificate path
  CERT_PATH=$(${SUDO} certbot certificates --cert-name "$DOMAIN" 2>/dev/null | awk -F': ' '/Certificate Path:/ {print $2; exit}')
  if [[ -n "$CERT_PATH" ]] && ${SUDO} test -f "$CERT_PATH"; then
    CERT_SOURCE_DIR="$(dirname "$CERT_PATH")"
    CERT_DIR_BASENAME="$(basename "$CERT_SOURCE_DIR")"
    log "Using source dir from --cert-name: ${CERT_SOURCE_DIR} (basename: ${CERT_DIR_BASENAME})"
  fi

  # Fallback: search classic and snap live paths, tolerate suffixed names (e.g., -0001)
  if [[ -z "$CERT_SOURCE_DIR" ]]; then
    for base in "/etc/letsencrypt/live" "/var/snap/certbot/common/etc/letsencrypt/live"; do
      log "Searching base path: $base"
      for d in "$base/${DOMAIN}" "$base/www.${DOMAIN}" "$base/${DOMAIN}"* "$base/www.${DOMAIN}"*; do
        log "Probing source candidate: $d"
        if ${SUDO} test -d "$d" && ${SUDO} test -f "$d/fullchain.pem" && ${SUDO} test -f "$d/privkey.pem"; then
          log "Selected cert source dir from search: $d"
          CERT_SOURCE_DIR="$d"; CERT_DIR_BASENAME="$(basename "$d")"; break 2
        fi
      done
    done
  fi

  # Last resort: find by filename with domain in path
  if [[ -z "$CERT_SOURCE_DIR" ]]; then
    log "Running last-resort search for fullchain.pem under certbot paths..."
    CAND=$(${SUDO} find /etc/letsencrypt /var/snap/certbot/common/etc/letsencrypt -maxdepth 5 -type f -name fullchain.pem -path "*${DOMAIN}*" 2>/dev/null | head -n1)
    if [[ -n "$CAND" ]]; then
      log "Found by find: $CAND"
      CERT_SOURCE_DIR="$(dirname "$CAND")"; CERT_DIR_BASENAME="$(basename "$CERT_SOURCE_DIR")"
    fi
  fi
fi

if [[ -z "$CERT_DIR_BASENAME" && -n "$CERT_SOURCE_DIR" ]]; then
  CERT_DIR_BASENAME="$(basename "$CERT_SOURCE_DIR")"
fi

if [[ -z "$CERT_SOURCE_DIR" && -z "$DEST_CAND" ]]; then
  warn "Could not locate cert source. Raw certbot inventory:"
  printf "%s\n" "$CERT_INFO" | sed 's/^/  /'
  log "Restoring HTTP-only nginx service..."
  # Try to bring nginx back up even if certs are missing
  if ! ${COMPOSE_CMD} -f "${COMPOSE_FILE}" start nginx; then
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" up -d nginx || true
  fi
  error "Certificate files not found for ${DOMAIN}. Inspect with: ${SUDO} certbot certificates"
fi

if [[ -n "$DEST_CAND" ]]; then
  log "Skipping copy; destination already has certs: ${DEST_CAND}"
else
  # Ensure destination directory mapped into nginx container exists
  DEST_BASE="/dados/certbot/certs/live/${CERT_DIR_BASENAME}"
  log "Ensuring destination directory exists: ${DEST_BASE}"
  ${SUDO} mkdir -p "${DEST_BASE}"
  log "Copying fullchain and privkey from ${CERT_SOURCE_DIR} to ${DEST_BASE}"
  ${SUDO} cp "${CERT_SOURCE_DIR}/fullchain.pem" "${DEST_BASE}/fullchain.pem"
  ${SUDO} cp "${CERT_SOURCE_DIR}/privkey.pem" "${DEST_BASE}/privkey.pem"
  ${SUDO} chmod 600 "${DEST_BASE}/privkey.pem"
  ${SUDO} chmod 644 "${DEST_BASE}/fullchain.pem"
  log "Synced certificates to ${DEST_BASE} for container mount"
  # Create soft links under host certbot paths pointing to /dados volume
  for host_live in "/etc/letsencrypt/live/${CERT_DIR_BASENAME}" "/var/snap/certbot/common/etc/letsencrypt/live/${CERT_DIR_BASENAME}"; do
    log "Ensuring host live dir exists: ${host_live}"
    ${SUDO} mkdir -p "${host_live}" || true
    log "Linking ${host_live}/fullchain.pem -> ${DEST_BASE}/fullchain.pem"
    ${SUDO} ln -sf "${DEST_BASE}/fullchain.pem" "${host_live}/fullchain.pem" || true
    log "Linking ${host_live}/privkey.pem -> ${DEST_BASE}/privkey.pem"
    ${SUDO} ln -sf "${DEST_BASE}/privkey.pem" "${host_live}/privkey.pem" || true
  done
fi

log "Using certificate basename ${CERT_DIR_BASENAME}"

# Create SSL-enabled nginx configuration directly in the shared nginx volume
NGINX_CONF_DIR="/dados/nginx/conf.d"
log "Writing SSL-enabled nginx configuration to ${NGINX_CONF_DIR}/default.conf"
${SUDO} tee "${NGINX_CONF_DIR}/default.conf" > /dev/null << EOF
upstream django {
    server web:8000;
}

# HTTP server - redirect to HTTPS
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    # Allow Let's Encrypt challenges
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect all other HTTP traffic to HTTPS
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/${CERT_DIR_BASENAME}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${CERT_DIR_BASENAME}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;

    # OCSP stapling
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';" always;

    # Static files
    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Media files
    location /media/ {
        alias /app/media/;
        expires 1y;
        add_header Cache-Control "public";
    }

    # Health check endpoint
    location /health/ {
        proxy_pass http://django;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
        access_log off;
    }

    # Main application
    location / {
        proxy_pass http://django;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;

        # Increase timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
}
EOF

# Reload the active Nginx container that publishes :80 (multi-site)
log "Detecting active Nginx container publishing port 80..."
ACTIVE_NGINX=$(docker ps --format '{{.Names}} {{.Image}} {{.Ports}}' | awk '/0\.0\.0\.0:80->80/ && /nginx/ {print $1; exit}')
if [[ -n "$ACTIVE_NGINX" ]]; then
  log "Reloading active Nginx container: $ACTIVE_NGINX"
  docker exec -i "$ACTIVE_NGINX" sh -lc "nginx -t && nginx -s reload" || warn "Reload failed on $ACTIVE_NGINX"
else
  warn "No global Nginx publishing :80 found. Falling back to compose nginx reload."
  ${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T nginx sh -lc "nginx -t && nginx -s reload" || ${COMPOSE_CMD} -f "${COMPOSE_FILE}" restart nginx || true
fi

# Update environment variables for HTTPS
log "Updating environment variables for HTTPS..."
if grep -q "USE_HTTPS=False" .env; then
    sed -i 's/USE_HTTPS=False/USE_HTTPS=True/' .env
elif ! grep -q "USE_HTTPS=" .env; then
    echo "USE_HTTPS=True" >> .env
fi

# Update CORS origins to include http and https
if grep -q "CORS_ALLOWED_ORIGINS=" .env; then
    sed -i "s|CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://${DOMAIN},http://${DOMAIN},https://www.${DOMAIN},http://www.${DOMAIN}|" .env
else
    echo "CORS_ALLOWED_ORIGINS=https://${DOMAIN},http://${DOMAIN},https://www.${DOMAIN},http://www.${DOMAIN}" >> .env
fi

# Update allowed hosts
log "Updating ALLOWED_HOSTS to include domain and server IP..."
if grep -q "ALLOWED_HOSTS=" .env; then
    sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP,$DOMAIN,www.$DOMAIN|" .env
else
    echo "ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP,$DOMAIN,www.$DOMAIN" >> .env
fi

# Validate and reload Nginx instead of force-recreate (multi-site container)
log "Validating Nginx configuration..."
if ${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T nginx sh -lc "nginx -t"; then
    log "Nginx config is valid. Reloading..."
    if ${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T nginx sh -lc "nginx -s reload"; then
        log "Nginx reloaded successfully"
    else
        warn "nginx reload failed; attempting container restart"
        ${COMPOSE_CMD} -f "${COMPOSE_FILE}" restart nginx || error "Failed to restart nginx. Check logs."
    fi
else
    warn "nginx -t failed; attempting container restart"
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" restart nginx || error "Failed to restart nginx. Check logs."
fi

# Short wait to let Nginx apply changes
log "Waiting briefly for Nginx to apply changes..."
sleep 5

# Test SSL configuration with multiple attempts
log "Testing SSL configuration..."
SSL_TEST_SUCCESS=false
for i in {1..5}; do
    log "SSL test attempt $i/5..."
    if curl -s -I "https://$DOMAIN/health/" | grep -q "200 OK"; then
        SSL_TEST_SUCCESS=true
        break
    fi
    sleep 10
done

if [ "$SSL_TEST_SUCCESS" = true ]; then
    log "SSL setup completed successfully!"
    log "Your site is now available at: https://$DOMAIN"
    log "HTTP traffic will be automatically redirected to HTTPS"
else
    warn "SSL setup completed but health check failed. Possible issues:"
    warn "1. DNS not pointing to this server yet"
    warn "2. Firewall blocking HTTPS (port 443)"
    warn "3. Nginx configuration issues"
    warn ""
    warn "Check the logs with:"
    warn "  ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs nginx"
warn "  ${COMPOSE_CMD} -f ${COMPOSE_FILE} logs web"
fi

# Set up automatic certificate renewal
log "Setting up automatic certificate renewal..."
${SUDO} crontab -l 2>/dev/null | grep -v "certbot renew" | ${SUDO} crontab -
(${SUDO} crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | ${SUDO} crontab -

# Create certificate renewal script for Docker
cat > scripts/renew_ssl.sh << 'EOF'
#!/bin/bash
# SSL Certificate Renewal Script for Docker deployment

APP_DIR="/dados/votebem"
cd "$APP_DIR"

# Detect docker compose command (plugin vs legacy)
COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "Docker Compose is not installed" >&2
    exit 1
fi
COMPOSE_FILE="${APP_DIR}/docker-compose.yml"
# Stop nginx container
${COMPOSE_CMD} -f "${COMPOSE_FILE}" stop nginx

# Renew certificate
SUDO=""
if [ "$EUID" -ne 0 ]; then SUDO="sudo"; fi
${SUDO} certbot renew --quiet || true

# Copy renewed certificates (parse from /dados/nginx/conf.d)
CERT_DIR_BASENAME=$(grep -RhoE 'ssl_certificate /etc/letsencrypt/live/([^/]+)/fullchain\.pem' /dados/nginx/conf.d/*.conf 2>/dev/null | sed -E 's#ssl_certificate /etc/letsencrypt/live/([^/]+)/fullchain\.pem#\1#' | head -1)
if [[ -n "$CERT_DIR_BASENAME" ]]; then
    # Prefer classic path, fall back to snap path if needed
    SRC="/etc/letsencrypt/live/${CERT_DIR_BASENAME}"
    if [[ ! -d "$SRC" ]]; then
        SRC="/var/snap/certbot/common/etc/letsencrypt/live/${CERT_DIR_BASENAME}"
    fi
    DEST="/dados/certbot/certs/live/${CERT_DIR_BASENAME}"
    ${SUDO} mkdir -p "${DEST}"
    if [[ -f "${SRC}/fullchain.pem" && -f "${SRC}/privkey.pem" ]]; then
        ${SUDO} cp "${SRC}/fullchain.pem" "${DEST}/fullchain.pem"
        ${SUDO} cp "${SRC}/privkey.pem" "${DEST}/privkey.pem"
        ${SUDO} chmod 600 "${DEST}/privkey.pem"
        ${SUDO} chmod 644 "${DEST}/fullchain.pem"
    else
        echo "Renewed certificate files not found in ${SRC}" >&2
    fi
fi

# Reload nginx to pick up renewed certs
if ! ${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T nginx sh -lc "nginx -t && nginx -s reload"; then
  ${COMPOSE_CMD} -f "${COMPOSE_FILE}" restart nginx || true
fi
EOF

chmod +x scripts/renew_ssl.sh

# Update crontab to use the Docker renewal script
${SUDO} crontab -l 2>/dev/null | grep -v "certbot renew" | ${SUDO} crontab -
(${SUDO} crontab -l 2>/dev/null; echo "0 12 * * * /dados/votebem/scripts/renew_ssl.sh") | ${SUDO} crontab -

# Final check: ensure Nginx picks up updated certificates
log "Finalizing: ensuring Nginx picks up updated certificates..."
if ${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T nginx sh -lc "nginx -t && nginx -s reload"; then
    log "Nginx reloaded successfully with new certificates."
else
    warn "Reload failed; forcing Nginx container recreate to apply certs..."
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" up -d --force-recreate nginx || error "Failed to force-recreate nginx. Check logs."
fi

log "SSL setup completed!"
log ""
log "Summary:"
log "- SSL certificates generated for $DOMAIN and www.$DOMAIN"
log "- Nginx configured for HTTPS with security headers"
log "- HTTP traffic automatically redirected to HTTPS"
log "- Automatic certificate renewal configured"
log ""
log "Your site is now available at: https://$DOMAIN"
log ""
log "To revert to HTTP-only, run:"
log "  cp docker-compose.prod.yml.backup docker-compose.prod.yml"
log "  cp nginx/production.conf nginx/default.conf"
log "  ${COMPOSE_CMD} -f ${COMPOSE_FILE} up -d --force-recreate nginx"