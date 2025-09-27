#!/bin/bash

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
APP_DIR="/opt/votebem"
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

# Check if votebem user exists, create if necessary
if ! id "votebem" &>/dev/null; then
    if [[ $(whoami) != "root" ]]; then
        error "User 'votebem' does not exist. Please run this script as root first to create the user, then re-run as votebem."
    fi
    
    log "Creating votebem user..."
    useradd -m -s /bin/bash votebem
    
    # Create docker group if it doesn't exist
    if ! getent group docker > /dev/null 2>&1; then
        log "Creating docker group..."
        groupadd docker
    fi
    
    usermod -aG docker votebem
    log "User 'votebem' created and added to docker group"
    log "Please now run this script as the votebem user: sudo su - votebem"
    log "Then navigate to $APP_DIR and run: ./scripts/setup_ssl.sh"
    exit 0
fi

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

log "Starting SSL Setup for VoteBem..."

# Get domain and email for SSL
read -p "Enter your domain name (e.g., votebem.com): " DOMAIN
read -p "Enter your email for SSL certificate: " EMAIL

# Validate inputs
if [[ -z "$DOMAIN" ]]; then
    error "Domain name is required for SSL setup"
fi

if [[ -z "$EMAIL" ]]; then
    error "Email is required for SSL certificate"
fi

# Navigate to application directory
cd "$APP_DIR"

# Check if containers are running
if ! docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    warn "Containers are not running. Attempting to start them..."
    if [[ -f "docker-compose.prod.yml" ]]; then
        docker-compose -f docker-compose.prod.yml up -d
        sleep 30
        if ! docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
            error "Failed to start containers. Please run the deployment script first."
        fi
    else
        error "docker-compose.prod.yml not found. Please run the deployment script first."
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
log "Stopping nginx container temporarily..."
docker-compose -f docker-compose.prod.yml stop nginx

# Install certbot if not already installed
if ! command -v certbot &> /dev/null; then
    log "Installing certbot..."
    sudo apt update
    sudo apt install -y certbot
fi

# Generate SSL certificate using Let's Encrypt
log "Generating SSL certificate with Let's Encrypt..."
if sudo certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"; then
    log "SSL certificate generated successfully"
else
    error "Failed to generate SSL certificate. Please check domain DNS settings and try again."
fi

# Copy certificates to ssl directory
log "Copying certificates to application directory..."
if [[ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" && -f "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ]]; then
    sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ssl/cert.pem
    sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ssl/key.pem
    sudo chown votebem:votebem ssl/cert.pem ssl/key.pem
    sudo chmod 600 ssl/key.pem
    sudo chmod 644 ssl/cert.pem
    log "Certificates copied successfully"
else
    error "Certificate files not found. SSL generation may have failed."
fi

# Create SSL-enabled nginx configuration
log "Creating SSL-enabled nginx configuration..."
cat > nginx/ssl.conf << EOF
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
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
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

# Update docker-compose to use SSL configuration
log "Updating docker-compose configuration for SSL..."
cp docker-compose.prod.yml docker-compose.prod.yml.backup

# Update nginx service in docker-compose to use SSL config
sed -i 's|./nginx/default.conf:/etc/nginx/conf.d/default.conf|./nginx/ssl.conf:/etc/nginx/conf.d/default.conf|' docker-compose.prod.yml

# Update environment variables for HTTPS
log "Updating environment variables for HTTPS..."
if grep -q "USE_HTTPS=False" .env; then
    sed -i 's/USE_HTTPS=False/USE_HTTPS=True/' .env
elif ! grep -q "USE_HTTPS=" .env; then
    echo "USE_HTTPS=True" >> .env
fi

# Update CORS origins for HTTPS
if grep -q "CORS_ALLOWED_ORIGINS=" .env; then
    sed -i "s|CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN|" .env
else
    echo "CORS_ALLOWED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN" >> .env
fi

# Update allowed hosts
log "Updating ALLOWED_HOSTS to include domain and server IP..."
if grep -q "ALLOWED_HOSTS=" .env; then
    sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP,$DOMAIN,www.$DOMAIN|" .env
else
    echo "ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP,$DOMAIN,www.$DOMAIN" >> .env
fi

# Restart containers with SSL configuration
log "Restarting containers with SSL configuration..."
if docker-compose -f docker-compose.prod.yml up -d --force-recreate nginx; then
    log "Nginx container restarted successfully"
else
    error "Failed to restart nginx container. Check docker-compose logs."
fi

# Wait for nginx to start
log "Waiting for nginx to start..."
sleep 15

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
    warn "  docker-compose -f docker-compose.prod.yml logs nginx"
    warn "  docker-compose -f docker-compose.prod.yml logs web"
fi

# Set up automatic certificate renewal
log "Setting up automatic certificate renewal..."
sudo crontab -l 2>/dev/null | grep -v "certbot renew" | sudo crontab -
(sudo crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | sudo crontab -

# Create certificate renewal script for Docker
cat > scripts/renew_ssl.sh << 'EOF'
#!/bin/bash
# SSL Certificate Renewal Script for Docker deployment

APP_DIR="/opt/votebem"
cd "$APP_DIR"

# Stop nginx container
docker-compose -f docker-compose.prod.yml stop nginx

# Renew certificate
sudo certbot renew --quiet

# Copy renewed certificates
DOMAIN=$(grep -o 'server_name [^;]*' nginx/ssl.conf | head -1 | awk '{print $2}' | tr -d ';')
if [[ -n "$DOMAIN" ]]; then
    sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ssl/cert.pem
    sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ssl/key.pem
    sudo chown votebem:votebem ssl/cert.pem ssl/key.pem
    sudo chmod 600 ssl/key.pem
    sudo chmod 644 ssl/cert.pem
fi

# Restart nginx container
docker-compose -f docker-compose.prod.yml start nginx
EOF

chmod +x scripts/renew_ssl.sh

# Update crontab to use the Docker renewal script
sudo crontab -l 2>/dev/null | grep -v "certbot renew" | sudo crontab -
(sudo crontab -l 2>/dev/null; echo "0 12 * * * /opt/votebem/scripts/renew_ssl.sh") | sudo crontab -

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
log "  docker-compose -f docker-compose.prod.yml up -d --force-recreate nginx"