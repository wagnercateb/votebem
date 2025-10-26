#!/bin/bash

# Multisite-friendly deployment of VoteBem on a VPS already serving baixavideo.site
# Idempotent, runs as non-root 'votebem' user. First run bootstraps user and re-execs.
# - Keeps existing baixavideo.site running
# - Deploys Django app via Docker Compose (no container nginx)
# - Proxies new domain to the app through host nginx (80/443)

set -Eeuo pipefail

echo "=== VoteBem Multisite Deployment (Idempotent) ==="

# Defaults (non-interactive)
DEFAULT_DOMAIN="votebem.online"
DEFAULT_EMAIL="wagnercateb@gmail.com"

# Bootstrap: ensure 'votebem' sudoer exists and switch to it before doing anything else
CURRENT_USER=$(id -un)
if [ "${RUN_AS_USER:-}" != "1" ]; then
  # Create user only if missing; prompt for password only on creation
  if ! id -u votebem >/dev/null 2>&1; then
    echo "Creating sudo-capable user 'votebem' (you will set its password)."
    sudo useradd -m -s /bin/bash votebem || true
    sudo usermod -aG sudo votebem || true
    # Docker group (so systemd service can run docker without sudo)
    if getent group docker >/dev/null 2>&1; then
      sudo usermod -aG docker votebem || true
    fi
    echo "Please set password for 'votebem' (you will be prompted)."
    sudo passwd votebem
  else
    echo "User 'votebem' already exists."
    # Ensure groups (no password prompts/changes)
    sudo usermod -aG sudo votebem >/dev/null 2>&1 || true
    if getent group docker >/dev/null 2>&1; then
      sudo usermod -aG docker votebem >/dev/null 2>&1 || true
    fi
  fi

  # Only switch if we are not already 'votebem'
  if [ "$CURRENT_USER" != "votebem" ]; then
    # Re-exec this script as 'votebem' with defaults for DOMAIN/EMAIL
    SCRIPT_PATH=$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")
    export DOMAIN="${DOMAIN:-$DEFAULT_DOMAIN}"
    export EMAIL="${EMAIL:-$DEFAULT_EMAIL}"
    echo "Switching to 'votebem' to perform deployment..."
    # Use sudo -u to preserve terminal context and avoid su issues
    exec sudo -u votebem -H bash -c "export RUN_AS_USER=1 DOMAIN='$DOMAIN' EMAIL='$EMAIL' HOME=/home/votebem; cd /home/votebem; bash '$SCRIPT_PATH'"
  fi
fi

# From here, we are 'votebem'

# Verify host nginx is running
if ! systemctl is-active --quiet nginx; then
  echo "Error: nginx is not running. Ensure baixavideo.site is already deployed."; exit 1
fi

# Inputs (non-interactive defaults)
DOMAIN="${DOMAIN:-$DEFAULT_DOMAIN}"
EMAIL="${EMAIL:-$DEFAULT_EMAIL}"

APP_DIR="/opt/votebem"
REPO_URL="git@github.com:wagnercateb/votebem.git"
BRANCH="main"
PORT="8001"   # host port for Django app (proxied by nginx)

# Ensure Docker + Compose plugin (will prompt for sudo password as needed)
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  sudo apt update
  sudo apt install -y docker.io
  sudo systemctl enable docker
  sudo systemctl start docker
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Installing Docker Compose plugin..."
  sudo apt install -y docker-compose-plugin
fi

# Prepare app directory
sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER":"$USER" "$APP_DIR"
cd "$APP_DIR"

# Clone or update repository
if [ -d .git ]; then
  echo "Repository exists, updating..."
  CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
  if [ -z "$CURRENT_REMOTE" ]; then git remote add origin "$REPO_URL"; fi
  if ssh -T git@github.com -o StrictHostKeyChecking=no -o ConnectTimeout=10 2>&1 | grep -q "successfully authenticated"; then
    git fetch origin
    git reset --hard origin/$BRANCH
    git clean -fd
  else
    echo "Warning: SSH not available. Using existing files."
  fi
else
  echo "Cloning repository..."
  if ssh -T git@github.com -o StrictHostKeyChecking=no -o ConnectTimeout=10 2>&1 | grep -q "successfully authenticated"; then
    git clone "$REPO_URL" .
  else
    echo "SSH not available, cloning via HTTPS..."
    git clone "https://github.com/wagnercateb/votebem.git" .
  fi
  git checkout "$BRANCH"
fi

# Create environment file (idempotent: generate only if missing; preserve secrets)
if [ ! -f .env ]; then
  echo "Creating .env with production settings"
  SERVER_IP=$(curl -s -4 ifconfig.me)
  cat > .env << EOF
DJANGO_SETTINGS_MODULE=votebem.settings.production
DEBUG=False
SECRET_KEY=$(openssl rand -base64 48)
SERVER_IP=$SERVER_IP
ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP,$DOMAIN,www.$DOMAIN
CORS_ALLOWED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN
DB_NAME=votebem_db
DB_USER=votebem_user
DB_PASSWORD=$(openssl rand -base64 32)
DB_HOST=db
DB_PORT=5432
REDIS_URL=redis://:$(openssl rand -base64 24)@redis:6379/0
USE_HTTPS=True
SECURE_SSL_REDIRECT=True
EOF
else
  echo "Using existing .env (secrets preserved)"
  # Check if CORS_ALLOWED_ORIGINS is missing and add it
  if ! grep -q "CORS_ALLOWED_ORIGINS" .env; then
    echo "Adding missing CORS_ALLOWED_ORIGINS to existing .env"
    echo "CORS_ALLOWED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN" >> .env
  fi
fi

# Compose file: db, redis, web (gunicorn). Expose web on localhost:$PORT
cat > docker-compose.prod.yml << EOF
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: \${DB_NAME}
      POSTGRES_USER: \${DB_USER}
      POSTGRES_PASSWORD: \${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    restart: unless-stopped
  web:
    build: .
    env_file: [.env]
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
      - ./logs:/app/logs
    depends_on:
      - db
      - redis
    command: >
      sh -c "python manage.py migrate --settings=votebem.settings.production && \
             python manage.py collectstatic --noinput --settings=votebem.settings.production && \
             gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 votebem.wsgi:application"
    ports:
      - "127.0.0.1:$PORT:8000"
    restart: unless-stopped
volumes:
  postgres_data:
  static_volume:
  media_volume:
EOF

# Build and start containers (idempotent; rebuild only when needed)
mkdir -p logs
# Use --build to rebuild if Dockerfile changed; safe to re-run
docker compose -f docker-compose.prod.yml up -d --build

# Prepare webroot for ACME
sudo mkdir -p /var/www/html/.well-known/acme-challenge
sudo chown -R www-data:www-data /var/www/html

# Idempotent Nginx + Certbot setup: write HTTP config only if cert missing; otherwise write HTTPS.
NGINX_CONF_PATH=/etc/nginx/sites-available/votebem
HAS_CERT=false
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then HAS_CERT=true; fi

# Backup existing config before changes
if [ -f "$NGINX_CONF_PATH" ]; then
  BACKUP_TS=$(date +%s)
  sudo cp "$NGINX_CONF_PATH" "$NGINX_CONF_PATH.bak.$BACKUP_TS"
fi

if [ "$HAS_CERT" = false ]; then
  echo "Writing initial HTTP-only nginx site for ACME + proxy"
  sudo tee "$NGINX_CONF_PATH" > /dev/null << 'EOF'
server {
  listen 80;
  server_name __DOMAIN__ www.__DOMAIN__;
  location /.well-known/acme-challenge/ {
    root /var/www/html;
    try_files $uri =404;
  }
  location /static/ {
    alias __APP_DIR__/staticfiles/;
  }
  location /media/ {
    alias __APP_DIR__/media/;
  }
  location / {
    proxy_pass http://127.0.0.1:__PORT__;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
EOF
  # Substitute placeholders safely
  sudo sed -i "s#__DOMAIN__#$DOMAIN#g; s#__APP_DIR__#$APP_DIR#g; s#__PORT__#$PORT#g" "$NGINX_CONF_PATH"
  sudo ln -sf "$NGINX_CONF_PATH" /etc/nginx/sites-enabled/votebem
  if ! sudo nginx -t; then
    echo "Nginx config test failed; reverting changes"
    if [ -n "${BACKUP_TS:-}" ] && [ -f "$NGINX_CONF_PATH.bak.$BACKUP_TS" ]; then sudo mv "$NGINX_CONF_PATH.bak.$BACKUP_TS" "$NGINX_CONF_PATH"; fi
    exit 1
  fi
  sudo systemctl reload nginx

  # Obtain SSL certificate via webroot (idempotent: keep until expiring)
  sudo certbot certonly --webroot -w /var/www/html \
    --email "$EMAIL" --agree-tos --no-eff-email --keep-until-expiring \
    -d "$DOMAIN" -d "www.$DOMAIN"
fi

# Write HTTPS nginx site with redirect and security headers
echo "Writing HTTPS nginx site with redirect"
sudo tee "$NGINX_CONF_PATH" > /dev/null << 'EOF'
# HTTP -> HTTPS redirect + ACME
server {
  listen 80;
  server_name __DOMAIN__ www.__DOMAIN__;
  location /.well-known/acme-challenge/ { root /var/www/html; try_files $uri =404; }
  location / { return 301 https://$server_name$request_uri; }
}
# HTTPS
server {
  listen 443 ssl http2;
  server_name __DOMAIN__ www.__DOMAIN__;
  ssl_certificate /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;
  ssl_protocols TLSv1.2 TLSv1.3;
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
  add_header X-Frame-Options DENY always;
  add_header X-Content-Type-Options nosniff always;
  add_header X-XSS-Protection "1; mode=block" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
  location /static/ { alias __APP_DIR__/staticfiles/; expires 1y; add_header Cache-Control "public, immutable"; }
  location /media/  { alias __APP_DIR__/media/; }
  location / {
    proxy_pass http://127.0.0.1:__PORT__;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
  location ~ /\. { deny all; }
}
EOF
# Substitute placeholders safely
sudo sed -i "s#__DOMAIN__#$DOMAIN#g; s#__APP_DIR__#$APP_DIR#g; s#__PORT__#$PORT#g" "$NGINX_CONF_PATH"
sudo ln -sf "$NGINX_CONF_PATH" /etc/nginx/sites-enabled/votebem
if ! sudo nginx -t; then
  echo "Nginx config test failed; reverting changes"
  if [ -n "${BACKUP_TS:-}" ] && [ -f "$NGINX_CONF_PATH.bak.$BACKUP_TS" ]; then sudo mv "$NGINX_CONF_PATH.bak.$BACKUP_TS" "$NGINX_CONF_PATH"; fi
  exit 1
fi
sudo systemctl reload nginx

# Firewall + renewal
sudo ufw allow 'Nginx Full' >/dev/null 2>&1 || true
sudo systemctl enable snap.certbot.renew.timer >/dev/null 2>&1 || true
sudo systemctl start  snap.certbot.renew.timer >/dev/null 2>&1 || true

# Systemd service for auto-start (runs as 'votebem' without sudo; requires docker group membership)
sudo tee /etc/systemd/system/votebem.service > /dev/null << EOF
[Unit]
Description=VoteBem Django (Docker Compose)
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose -f $APP_DIR/docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f $APP_DIR/docker-compose.prod.yml down

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable votebem.service
# Start or restart service idempotently
if systemctl is-active --quiet votebem.service; then
  sudo systemctl restart votebem.service
else
  sudo systemctl start votebem.service
fi

echo "=== Deployment Complete ==="
echo "Domain: https://$DOMAIN"
echo "App proxied at: 127.0.0.1:$PORT (via host nginx)"
echo "Compose file: $APP_DIR/docker-compose.prod.yml"
echo "Service: votebem.service (enabled)"