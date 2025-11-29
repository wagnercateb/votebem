#!/bin/bash

# Avoid __deploy_production.sh unless you want a self-contained stack with an Nginx container binding 80/443 (this can collide with your host Nginx).
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

# VoteBem - Production Deployment Script
# This script deploys the Django VoteBem application in production mode
# Run as votebem user from project root: ./scripts/deploy_production.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/votebem"
REPO_URL="git@github.com:wagnercateb/votebem.git"
BRANCH="main"
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

# Check if running as votebem user
if [[ $(whoami) != "votebem" ]]; then
   error "This script must be run as the 'votebem' user. Run: sudo su - votebem"
fi

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    error "Docker is not installed or not available to this user"
fi

if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed"
fi

log "Starting VoteBem Production Deployment..."

# Get domain for configuration (optional)
read -p "Enter your domain name (optional, leave empty for localhost): " DOMAIN

# Get VPS IP address for nginx configuration
read -p "Enter your VPS IP address: " VPS_IP

# Validate inputs
if [[ -z "$DOMAIN" ]]; then
    DOMAIN="localhost"
    warn "No domain provided. Using localhost. You can set up SSL later using ./scripts/setup_ssl.sh"
fi

if [[ -z "$VPS_IP" ]]; then
    error "VPS IP address is required for proper nginx configuration"
fi

# Update nginx configuration files with VPS IP
log "Updating nginx configuration with VPS IP: $VPS_IP"
if [[ -f "nginx/default.conf" ]]; then
    # Replace placeholder if it exists, otherwise replace any existing IP
    if grep -q "VPS_IP_PLACEHOLDER" nginx/default.conf; then
        sed -i "s/VPS_IP_PLACEHOLDER/$VPS_IP/g" nginx/default.conf
        log "Updated nginx/default.conf with VPS IP (replaced placeholder)"
    else
        # Replace any existing IP pattern in server_name line
        sed -i "s/server_name localhost [0-9.]\+ /server_name localhost $VPS_IP /" nginx/default.conf
        log "Updated nginx/default.conf with VPS IP (replaced existing IP)"
    fi
fi

if [[ -f "nginx/production.conf" ]]; then
    # Replace placeholder if it exists, otherwise replace any existing IP
    if grep -q "VPS_IP_PLACEHOLDER" nginx/production.conf; then
        sed -i "s/VPS_IP_PLACEHOLDER/$VPS_IP/g" nginx/production.conf
        log "Updated nginx/production.conf with VPS IP (replaced placeholder)"
    else
        # Replace any existing IP pattern in server_name line
        sed -i "s/server_name localhost [0-9.]\+ /server_name localhost $VPS_IP /" nginx/production.conf
        log "Updated nginx/production.conf with VPS IP (replaced existing IP)"
    fi
fi

# Navigate to application directory
cd "$APP_DIR"

# Check if repository is already cloned (by setup_linode_vps.sh)
if [[ -d ".git" ]]; then
    log "Repository already exists, updating..."
    
    # Check if remote origin exists and update to SSH if it's HTTPS
    CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$CURRENT_REMOTE" == https://github.com/* ]]; then
        log "Converting HTTPS remote to SSH..."
        git remote set-url origin "$REPO_URL"
    elif [[ -z "$CURRENT_REMOTE" ]]; then
        log "Adding SSH remote..."
        git remote add origin "$REPO_URL"
    fi
    
    # Try to update repository, but don't fail if SSH is not configured
    if ssh -T git@github.com -o StrictHostKeyChecking=no -o ConnectTimeout=10 2>&1 | grep -q "successfully authenticated"; then
        log "Updating repository with SSH..."
        git fetch origin
        git reset --hard origin/$BRANCH
        git clean -fd
    else
        warn "SSH key authentication not available. Using existing repository files."
        log "To enable updates, configure SSH key authentication with GitHub."
    fi
else
    # Repository not cloned yet, try to clone
    log "Repository not found, attempting to clone..."
    
    # Try SSH first, fall back to HTTPS if SSH fails
    if ssh -T git@github.com -o StrictHostKeyChecking=no -o ConnectTimeout=10 2>&1 | grep -q "successfully authenticated"; then
        log "Cloning repository with SSH..."
        git clone "$REPO_URL" .
        git checkout "$BRANCH"
    else
        warn "SSH key authentication not available. Cloning with HTTPS..."
        git clone "https://github.com/wagnercateb/votebem.git" .
        git checkout "$BRANCH"
        log "Repository cloned with HTTPS. For updates, configure SSH key authentication."
    fi
fi

# Create necessary directories
log "Creating necessary directories..."
mkdir -p logs
mkdir -p media
mkdir -p backups
mkdir -p ssl

# Set proper permissions for logs directory
log "Setting proper permissions for logs directory..."
chmod 755 logs
chown -R $USER:$USER logs

# Generate secure passwords and secrets
log "Generating secure configuration..."
DB_PASSWORD=$(openssl rand -base64 32)
SECRET_KEY=$(openssl rand -base64 50)
REDIS_PASSWORD=$(openssl rand -base64 32)

# Create production environment file
log "Creating production environment file..."
cat > .env << EOF
# Django Settings
DJANGO_SETTINGS_MODULE=votebem.settings.production
DEBUG=False
SECRET_KEY=$SECRET_KEY

# Use VPS IP provided by user
SERVER_IP=$VPS_IP

# Allowed Hosts (include server IP, localhost, domain, and 'web' for nginx internal communication)
ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP,$DOMAIN,www.$DOMAIN,web

# Database Configuration
DB_NAME=votebem_db
DB_USER=votebem_user
DB_PASSWORD=$DB_PASSWORD
DB_HOST=db
DB_PORT=3306

# Redis Configuration
REDIS_URL=redis://:$REDIS_PASSWORD@redis:6379/0

# Email Configuration (update with your SMTP settings)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@$DOMAIN

# Security Settings
USE_HTTPS=False
SECURE_SSL_REDIRECT=False
USE_TLS=False
CORS_ALLOWED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN

# Remote Debugging (disabled in production)
ENABLE_REMOTE_DEBUG=False

# Backup Configuration
BACKUP_ENABLED=True
BACKUP_RETENTION_DAYS=30
EOF

# Update docker-compose for production
log "Updating docker-compose configuration..."
cat > docker-compose.prod.yml << EOF
services:
  db:
    image: mariadb:11
    container_name: votebem_db
    environment:
      MYSQL_DATABASE: \${DB_NAME}
      MYSQL_USER: \${DB_USER}
      MYSQL_PASSWORD: \${DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: \${DB_PASSWORD}
    volumes:
      - mariadb_data:/var/lib/mysql
      - ./backups:/backups
    restart: unless-stopped
    networks:
      - vps_network
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h localhost -u\${DB_USER} -p\${DB_PASSWORD} || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: votebem_redis
    command: redis-server --requirepass \${REDIS_PASSWORD:-redis_password} --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - vps_network
    healthcheck:
      test: ["CMD", "redis-cli", "--no-auth-warning", "-a", "\${REDIS_PASSWORD:-redis_password}", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  web:
    build: .
    container_name: votebem_web
    env_file:
      - .env
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
      - ./logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      vps_network:
        aliases:
          - votebem-web
    command: >
      sh -c "python manage.py migrate --settings=votebem.settings.production &&
             python manage.py collectstatic --noinput --settings=votebem.settings.production &&
             python manage.py createcachetable --settings=votebem.settings.production &&
             gunicorn --bind 0.0.0.0:8000 --workers 3 --worker-class gthread --threads 2 --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile - votebem.wsgi:application"

  nginx:
    image: nginx:alpine
    container_name: votebem_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf
      - static_volume:/app/staticfiles
      - media_volume:/app/media
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web
    restart: unless-stopped
    networks:
      - vps_network

volumes:
  mariadb_data:
  redis_data:
  static_volume:
  media_volume:

networks:
  vps_network:
    driver: bridge
  vps_network:
    external: true
EOF

# Update nginx configuration for production (HTTP-only)
log "Updating nginx configuration for production..."
# Use the production HTTP-only configuration
cp nginx/production.conf nginx/default.conf

# Update server name if domain is provided
if [[ "$DOMAIN" != "localhost" ]]; then
    sed -i "s/server_name localhost;/server_name $DOMAIN www.$DOMAIN;/g" nginx/default.conf
fi

# Stop existing containers if running
log "Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down --remove-orphans || true

# Clean up any problematic volumes if this is a fresh deployment
if [[ ! -f ".deployment_completed" ]]; then
    log "Fresh deployment detected. Cleaning up any existing volumes..."
    docker volume rm votebem_mariadb_data votebem_redis_data 2>/dev/null || true
    log "Cleaned up existing volumes for fresh start"
fi

# Build and start containers
log "Building and starting containers..."
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
log "Waiting for services to be ready..."
sleep 30

# Check if services are running
log "Checking service status..."
if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    log "Services are running successfully!"
else
    error "Some services failed to start. Check logs with: docker-compose -f docker-compose.prod.yml logs"
fi

# Wait for web container to be stable and ready
log "Waiting for web container to be stable..."
for i in {1..12}; do
    if docker-compose -f docker-compose.prod.yml exec -T web python manage.py check --deploy --settings=votebem.settings.production > /dev/null 2>&1; then
        log "Web container is ready!"
        break
    fi
    if [ $i -eq 12 ]; then
        log "Warning: Web container may not be fully ready. Proceeding anyway..."
        break
    fi
    log "Web container not ready yet, waiting... (attempt $i/12)"
    sleep 10
done

# Create superuser
log "Creating Django superuser..."
read -p "Do you want to create a Django superuser? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Additional check before creating superuser
    if docker-compose -f docker-compose.prod.yml ps web | grep -q "Up"; then
        docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser --settings=votebem.settings.production
    else
        error "Web container is not running. Cannot create superuser."
    fi
fi

# Set up SSL certificate if domain is provided
if [[ -n "$DOMAIN" && -n "$EMAIL" ]]; then
    log "Setting up SSL certificate..."
    read -p "Do you want to set up SSL certificate with Let's Encrypt? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Stop nginx temporarily
        docker-compose -f docker-compose.prod.yml stop nginx
        
        # Get SSL certificate
        sudo certbot certonly --standalone -d "$DOMAIN" -d "www.$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive
        
        # Copy certificates to ssl directory
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/cert.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/key.pem
        sudo chown votebem:votebem ssl/*.pem
        
        # Start nginx again
        docker-compose -f docker-compose.prod.yml start nginx
        
        # Set up certificate renewal
        echo "0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $APP_DIR/ssl/cert.pem && cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $APP_DIR/ssl/key.pem && chown votebem:votebem $APP_DIR/ssl/*.pem && docker-compose -f $APP_DIR/docker-compose.prod.yml restart nginx" | sudo crontab -
        
        log "SSL certificate configured successfully!"
    fi
fi

# Create deployment management scripts
log "Creating management scripts..."

# Start script
cat > start.sh << 'EOF'
#!/bin/bash
cd /opt/votebem
docker-compose -f docker-compose.prod.yml up -d
echo "VoteBem application started"
EOF

# Stop script
cat > stop.sh << 'EOF'
#!/bin/bash
cd /opt/votebem
docker-compose -f docker-compose.prod.yml down
echo "VoteBem application stopped"
EOF

# Restart script
cat > restart.sh << 'EOF'
#!/bin/bash
cd /opt/votebem
docker-compose -f docker-compose.prod.yml restart
echo "VoteBem application restarted"
EOF

# Update script
cat > update.sh << 'EOF'
#!/bin/bash
cd /opt/votebem
echo "Updating VoteBem application..."
git pull origin main
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
echo "VoteBem application updated"
EOF

# Logs script
cat > logs.sh << 'EOF'
#!/bin/bash
cd /opt/votebem
docker-compose -f docker-compose.prod.yml logs -f
EOF

# Status script
cat > status.sh << 'EOF'
#!/bin/bash
cd /opt/votebem
echo "=== Container Status ==="
docker-compose -f docker-compose.prod.yml ps
echo
echo "=== Application Health ==="
curl -s http://localhost/health/ | python3 -m json.tool || echo "Health check failed"
echo
echo "=== System Resources ==="
echo "Disk Usage: $(df -h / | awk 'NR==2 {print $5}')"
echo "Memory Usage: $(free -h | awk 'NR==2{printf "%.1f%%", $3*100/$2}')"
echo "Load Average: $(uptime | awk -F'load average:' '{print $2}')"
EOF

# Make scripts executable
chmod +x *.sh

# Create systemd service for auto-start
log "Creating systemd service..."
sudo tee /etc/systemd/system/votebem.service > /dev/null << EOF
[Unit]
Description=VoteBem Django Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=votebem
Group=votebem
WorkingDirectory=/opt/votebem
ExecStart=/opt/votebem/start.sh
ExecStop=/opt/votebem/stop.sh
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable votebem.service

# Final health check
log "Performing final health check..."
sleep 10

# Try multiple health check attempts
HEALTH_CHECK_ATTEMPTS=5
HEALTH_CHECK_SUCCESS=false

for i in $(seq 1 $HEALTH_CHECK_ATTEMPTS); do
    log "Health check attempt $i/$HEALTH_CHECK_ATTEMPTS..."
    if curl -f http://localhost/health/ > /dev/null 2>&1; then
        log "Application is healthy and responding!"
        HEALTH_CHECK_SUCCESS=true
        break
    else
        if [[ $i -lt $HEALTH_CHECK_ATTEMPTS ]]; then
            warn "Health check failed, retrying in 10 seconds..."
            sleep 10
        fi
    fi
done

if [[ "$HEALTH_CHECK_SUCCESS" == "false" ]]; then
    warn "Application health check failed after $HEALTH_CHECK_ATTEMPTS attempts."
    warn "Check logs with: ./logs.sh"
    warn "Check container status with: docker-compose -f docker-compose.prod.yml ps"
    
    # Show recent logs for debugging
    log "Recent container logs:"
    docker-compose -f docker-compose.prod.yml logs --tail=20 web
else
    # Mark deployment as completed
    touch .deployment_completed
    log "Deployment marked as completed successfully!"
fi

# Display completion message
log "Production deployment completed successfully!"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}VoteBem Production Deployment Complete!${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "Application URL: ${YELLOW}http://$DOMAIN${NC}"
if [[ -n "$DOMAIN" ]]; then
    echo -e "SSL URL: ${YELLOW}https://$DOMAIN${NC}"
fi
echo -e "Admin URL: ${YELLOW}http://$DOMAIN/admin/${NC}"
echo -e "Health Check: ${YELLOW}http://$DOMAIN/health/${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}Management Commands:${NC}"
echo -e "Start: ${YELLOW}./start.sh${NC}"
echo -e "Stop: ${YELLOW}./stop.sh${NC}"
echo -e "Restart: ${YELLOW}./restart.sh${NC}"
echo -e "Update: ${YELLOW}./update.sh${NC}"
echo -e "Logs: ${YELLOW}./logs.sh${NC}"
echo -e "Status: ${YELLOW}./status.sh${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}Important Files:${NC}"
echo -e "Environment: ${YELLOW}.env${NC}"
echo -e "Docker Compose: ${YELLOW}docker-compose.prod.yml${NC}"
echo -e "Logs: ${YELLOW}./logs/${NC}"
echo -e "Backups: ${YELLOW}./backups/${NC}"
echo -e "${BLUE}===========================================${NC}"

log "Deployment script completed. Your VoteBem application is now running in production mode!"

# Save deployment info
cat > deployment_summary.txt << EOF
VoteBem Production Deployment Summary
====================================
Date: $(date)
Domain: $DOMAIN
Application URL: http://$DOMAIN
SSL URL: https://$DOMAIN
Admin URL: http://$DOMAIN/admin/

Generated Passwords (KEEP SECURE):
Database Password: $DB_PASSWORD
Redis Password: $REDIS_PASSWORD
Secret Key: $SECRET_KEY

Next Steps:
1. Configure email settings in .env file
2. Set up monitoring and alerting
3. Configure regular backups
4. Update DNS records to point to this server
5. Test all functionality

Management:
- Start: ./start.sh
- Stop: ./stop.sh
- Restart: ./restart.sh
- Update: ./update.sh
- Logs: ./logs.sh
- Status: ./status.sh
EOF

log "Deployment summary saved to deployment_summary.txt"