#!/bin/bash

# VoteBem - Production Deployment Script
# This script deploys the Django VoteBem application in production mode
# Run as votebem user: ./scripts/deploy_production.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/votebem"
REPO_URL="https://github.com/wagnercateb/django-votebem.git"
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

# Get domain and email for SSL
read -p "Enter your domain name (e.g., votebem.com): " DOMAIN
read -p "Enter your email for SSL certificate: " EMAIL

# Validate inputs
if [[ -z "$DOMAIN" ]]; then
    warn "No domain provided. SSL will not be configured."
fi

# Navigate to application directory
cd "$APP_DIR"

# Clone or update repository
if [[ -d ".git" ]]; then
    log "Updating existing repository..."
    git fetch origin
    git reset --hard origin/$BRANCH
    git clean -fd
else
    log "Cloning repository..."
    git clone "$REPO_URL" .
    git checkout "$BRANCH"
fi

# Create necessary directories
log "Creating necessary directories..."
mkdir -p logs
mkdir -p media
mkdir -p backups
mkdir -p ssl

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

# Allowed Hosts
ALLOWED_HOSTS=localhost,127.0.0.1,$DOMAIN,www.$DOMAIN

# Database Configuration
DB_NAME=votebem_db
DB_USER=votebem_user
DB_PASSWORD=$DB_PASSWORD
DB_HOST=db
DB_PORT=5432

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
USE_HTTPS=True
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
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: votebem_db
    environment:
      POSTGRES_DB: \${DB_NAME}
      POSTGRES_USER: \${DB_USER}
      POSTGRES_PASSWORD: \${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    restart: unless-stopped
    networks:
      - votebem_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \${DB_USER} -d \${DB_NAME}"]
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
      - votebem_network
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
      - votebem_network
    command: >
      sh -c "python manage.py migrate &&
             python manage.py collectstatic --noinput &&
             python manage.py createcachetable &&
             gunicorn --bind 0.0.0.0:8000 --workers 3 --worker-class gthread --threads 2 --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 100 --access-logfile /app/logs/gunicorn_access.log --error-logfile /app/logs/gunicorn_error.log votebem.wsgi:application"

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
      - votebem_network

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:

networks:
  votebem_network:
    driver: bridge
EOF

# Update nginx configuration for production
log "Updating nginx configuration for production..."
if [[ -n "$DOMAIN" ]]; then
    sed -i "s/server_name localhost;/server_name $DOMAIN www.$DOMAIN;/g" nginx/default.conf
    
    # Enable SSL configuration
    sed -i 's/# listen 443 ssl http2;/listen 443 ssl http2;/' nginx/default.conf
    sed -i 's/# ssl_certificate/ssl_certificate/' nginx/default.conf
    sed -i 's/# ssl_certificate_key/ssl_certificate_key/' nginx/default.conf
    sed -i 's/# ssl_protocols/ssl_protocols/' nginx/default.conf
    sed -i 's/# ssl_ciphers/ssl_ciphers/' nginx/default.conf
    sed -i 's/# ssl_prefer_server_ciphers/ssl_prefer_server_ciphers/' nginx/default.conf
    sed -i 's/# ssl_session_cache/ssl_session_cache/' nginx/default.conf
    sed -i 's/# ssl_session_timeout/ssl_session_timeout/' nginx/default.conf
    
    # Enable HTTP to HTTPS redirect
    sed -i 's/# return 301 https/return 301 https/' nginx/default.conf
fi

# Stop existing containers if running
log "Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down --remove-orphans || true

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

# Create superuser
log "Creating Django superuser..."
read -p "Do you want to create a Django superuser? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
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
if curl -f http://localhost/health/ > /dev/null 2>&1; then
    log "Application is healthy and responding!"
else
    warn "Application health check failed. Check logs with: ./logs.sh"
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