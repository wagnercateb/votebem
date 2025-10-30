#!/bin/bash

# VoteBem Application Setup Script
# This script configures the VoteBem Django application on a provisioned VPS
# Run as sudoer user: curl -sSL https://raw.githubusercontent.com/wagnercateb/votebem/main/scripts/setup_votebem.sh | bash
#
# Prerequisites: VPS must be provisioned with provision_vps.sh first
#
# Environment Variables (optional):
# - INSTALL_CERTBOT: Set to "true" to install Certbot for SSL certificates
# - VOTEBEM_DOMAIN: Domain name for the application (for SSL certificate)
# - VOTEBEM_PASSWORD: Password for the votebem user (will prompt if not provided)

set -e  # Exit on any error

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/common_functions.sh" ]]; then
    source "$SCRIPT_DIR/common_functions.sh"
else
    # Fallback: define basic logging functions if common_functions.sh is not available
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
    
    log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"; }
    warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"; }
    error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"; exit 1; }
    success() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] SUCCESS: $1${NC}"; }
    info() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"; }
fi

# Check if running as non-root user with sudo privileges
if [[ $EUID -eq 0 ]]; then
   error "This script should NOT be run as root. Run as a sudoer user instead."
fi

# Check if user has sudo privileges
# First check if user is in sudo group or wheel group
if ! groups | grep -qE '\b(sudo|wheel|admin)\b'; then
    # If not in sudo group, try a simple sudo command with timeout
    if ! timeout 10 sudo -v 2>/dev/null; then
        error "This script requires sudo privileges. Please ensure your user is in the sudo group or has sudo access."
    fi
else
    # User is in sudo group, validate sudo access
    if ! sudo -v 2>/dev/null; then
        error "Failed to validate sudo access. Please check your sudo configuration."
    fi
fi

log "Starting VoteBem Application Setup..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    error "Docker is not installed. Please run provision_vps.sh first."
fi

# Check if user is in docker group
if ! groups | grep -q docker; then
    error "Current user is not in docker group. Please run provision_vps.sh first or add user to docker group."
fi

# Create votebem user
log "Creating votebem user..."
if ! id "votebem" &>/dev/null; then
    sudo useradd -m -s /bin/bash votebem
    sudo usermod -aG docker votebem
    sudo usermod -aG sudo votebem
    log "User 'votebem' created successfully with sudo privileges"
    
    # Set password for votebem user
    log "Setting password for votebem user..."
    if [[ -n "$VOTEBEM_PASSWORD" ]]; then
        echo "votebem:$VOTEBEM_PASSWORD" | sudo chpasswd
        log "Password set for votebem user from environment variable"
    else
        echo "Please set a password for the 'votebem' user:"
        while true; do
            read -s -p "Enter password for votebem user: " VOTEBEM_PASS
            echo
            if [[ ${#VOTEBEM_PASS} -lt 8 ]]; then
                warn "Password must be at least 8 characters long. Please try again."
                continue
            fi
            read -s -p "Confirm password: " VOTEBEM_PASS_CONFIRM
            echo
            if [[ "$VOTEBEM_PASS" == "$VOTEBEM_PASS_CONFIRM" ]]; then
                echo "votebem:$VOTEBEM_PASS" | sudo chpasswd
                log "Password set for votebem user"
                break
            else
                warn "Passwords do not match. Please try again."
            fi
        done
    fi
else
    warn "User 'votebem' already exists"
    sudo usermod -aG docker votebem
    sudo usermod -aG sudo votebem
    log "Updated groups for existing user 'votebem' (added docker and sudo)"
    
    # Check if we should update the password for existing user
    if [[ -n "$VOTEBEM_PASSWORD" ]]; then
        echo "votebem:$VOTEBEM_PASSWORD" | sudo chpasswd
        log "Password updated for existing votebem user from environment variable"
    else
        log "To change the password for existing votebem user, run: sudo passwd votebem"
    fi
fi

# Create application directories
log "Creating application directories..."

# Clean and create /opt/votebem
if [ -d "/opt/votebem" ]; then
    log "Removing existing /opt/votebem directory..."
    # Change to a safe directory before removing /opt/votebem to avoid "No such file or directory" error
    cd /tmp
    sudo rm -rf /opt/votebem
fi
sudo mkdir -p /opt/votebem

# Clean and create /var/log/votebem
if [ -d "/var/log/votebem" ]; then
    log "Removing existing /var/log/votebem directory..."
    sudo rm -rf /var/log/votebem
fi
sudo mkdir -p /var/log/votebem

# Clean and create /var/backups/votebem
if [ -d "/var/backups/votebem" ]; then
    log "Removing existing /var/backups/votebem directory..."
    sudo rm -rf /var/backups/votebem
fi
sudo mkdir -p /var/backups/votebem

sudo chown -R votebem:votebem /opt/votebem
sudo chown -R votebem:votebem /var/log/votebem
sudo chown -R votebem:votebem /var/backups/votebem

# Set up log rotation
log "Setting up log rotation..."
sudo tee /etc/logrotate.d/votebem > /dev/null << EOF
/var/log/votebem/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 votebem votebem
    postrotate
        docker-compose -f /opt/votebem/docker-compose.yml restart web
    endscript
}
EOF

# Create backup script
log "Creating backup script..."
sudo tee /opt/votebem/backup.sh > /dev/null << 'EOF'
#!/bin/bash

# VoteBem Backup Script
BACKUP_DIR="/var/backups/votebem"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
echo "Creating database backup..."
# Use container env to avoid storing credentials here (supports MYSQL_* or MARIADB_* envs)
docker-compose -f /opt/votebem/docker-compose.yml exec -T db sh -lc '
  DB_NAME="${MYSQL_DATABASE:-$MARIADB_DATABASE}"
  DB_USER="${MYSQL_USER:-$MARIADB_USER}"
  DB_PASS="${MYSQL_PASSWORD:-$MARIADB_PASSWORD}"
  if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
    echo "Database variables not set in container (MYSQL_*/MARIADB_*)" >&2; exit 1
  fi
  mysqldump -u"$DB_USER" -p"$DB_PASS" "$DB_NAME"
' | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"

# Backup media files
echo "Creating media backup..."
tar -czf "$BACKUP_DIR/media_backup_$DATE.tar.gz" -C /opt/votebem media/

# Backup application code
echo "Creating code backup..."
tar --exclude='*.pyc' --exclude='__pycache__' --exclude='.git' -czf "$BACKUP_DIR/code_backup_$DATE.tar.gz" -C /opt/votebem .

# Remove old backups
echo "Cleaning old backups..."
find "$BACKUP_DIR" -name "*backup_*.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
EOF

sudo chmod +x /opt/votebem/backup.sh
sudo chown votebem:votebem /opt/votebem/backup.sh

# Set up cron job for backups
log "Setting up automated backups..."
(sudo crontab -u votebem -l 2>/dev/null; echo "0 2 * * * /opt/votebem/backup.sh >> /var/log/votebem/backup.log 2>&1") | sudo crontab -u votebem -

# Create system monitoring script
log "Creating monitoring script..."
sudo tee /opt/votebem/monitor.sh > /dev/null << 'EOF'
#!/bin/bash

# VoteBem System Monitor
LOG_FILE="/var/log/votebem/monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Check disk space
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "[$DATE] WARNING: Disk usage is ${DISK_USAGE}%" >> $LOG_FILE
fi

# Check memory usage
MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEM_USAGE -gt 80 ]; then
    echo "[$DATE] WARNING: Memory usage is ${MEM_USAGE}%" >> $LOG_FILE
fi

# Check if Docker containers are running
if ! docker-compose -f /opt/votebem/docker-compose.yml ps | grep -q "Up"; then
    echo "[$DATE] ERROR: Some Docker containers are not running" >> $LOG_FILE
fi

# Check application health
if ! curl -f http://localhost/health/ > /dev/null 2>&1; then
    echo "[$DATE] ERROR: Application health check failed" >> $LOG_FILE
fi
EOF

sudo chmod +x /opt/votebem/monitor.sh
sudo chown votebem:votebem /opt/votebem/monitor.sh

# Set up monitoring cron job
(sudo crontab -u votebem -l 2>/dev/null; echo "*/5 * * * * /opt/votebem/monitor.sh") | sudo crontab -u votebem -

# Create SSL certificate directory
log "Creating SSL certificate directory..."
if [ -d "/opt/votebem/ssl" ]; then
    log "Removing existing SSL directory..."
    sudo rm -rf /opt/votebem/ssl
fi
sudo mkdir -p /opt/votebem/ssl
sudo chown votebem:votebem /opt/votebem/ssl

# Install Certbot for Let's Encrypt (optional - set INSTALL_CERTBOT=true to install)
if [[ "$INSTALL_CERTBOT" == "true" ]]; then
    log "Installing Certbot..."
    sudo apt update
    sudo apt install -y certbot python3-certbot-nginx
    log "Certbot installed. Run 'certbot --nginx -d yourdomain.com' to get SSL certificate"
    
    # If domain is provided, attempt to get certificate
    if [[ -n "$VOTEBEM_DOMAIN" ]]; then
        log "Attempting to get SSL certificate for domain: $VOTEBEM_DOMAIN"
        warn "Make sure your domain points to this server before running certbot"
        log "To get SSL certificate, run: sudo certbot --nginx -d $VOTEBEM_DOMAIN"
    fi
else
    log "Certbot installation skipped (set INSTALL_CERTBOT=true to install)"
fi

# Clone the repository and set up the application
log "Cloning VoteBem repository..."
# Clone to a temporary directory first, then move contents to /opt/votebem
TEMP_CLONE_DIR="/tmp/votebem_clone_$$"
# Ensure we clone without authentication (public repository)
sudo -u votebem git -c credential.helper= clone https://github.com/wagnercateb/votebem.git "$TEMP_CLONE_DIR"

sudo -u votebem cp -r "$TEMP_CLONE_DIR"/* /opt/votebem/
sudo -u votebem cp -r "$TEMP_CLONE_DIR"/.* /opt/votebem/ 2>/dev/null || true  # Copy hidden files, ignore errors
sudo rm -rf "$TEMP_CLONE_DIR"
cd /opt/votebem

# Get server IP for ALLOWED_HOSTS configuration
log "Detecting server IP address..."
SERVER_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip || hostname -I | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    warn "Could not detect server IP address automatically"
    SERVER_IP="127.0.0.1"
fi
log "Server IP detected: $SERVER_IP"

# Create initial .env file with server IP included in ALLOWED_HOSTS
log "Creating initial environment configuration..."
sudo -u votebem cp .env.example .env

# Update ALLOWED_HOSTS to include server IP and domain if provided
ALLOWED_HOSTS="localhost,127.0.0.1,$SERVER_IP"
if [[ -n "$VOTEBEM_DOMAIN" ]]; then
    ALLOWED_HOSTS="$ALLOWED_HOSTS,$VOTEBEM_DOMAIN"
    log "Added domain to ALLOWED_HOSTS: $VOTEBEM_DOMAIN"
fi

sudo -u votebem sed -i "s|ALLOWED_HOSTS=localhost,127.0.0.1|ALLOWED_HOSTS=$ALLOWED_HOSTS|" .env

# Set proper ownership
sudo chown -R votebem:votebem /opt/votebem

# Set execute permissions on all scripts
log "Setting execute permissions on scripts..."
sudo chmod +x /opt/votebem/scripts/*.sh
sudo chmod +x /opt/votebem/manage.py
log "Execute permissions set for all scripts"

# Create deployment info file
log "Creating deployment info..."
sudo -u votebem tee /opt/votebem/deployment_info.txt > /dev/null << EOF
VoteBem Application Setup Completed
===================================
Date: $(date)
Server: $(hostname)
IP: $SERVER_IP
$([ -n "$VOTEBEM_DOMAIN" ] && echo "Domain: $VOTEBEM_DOMAIN")
Docker Version: $(docker --version)
Docker Compose Version: $(docker-compose --version)

Repository: Cloned and configured
ALLOWED_HOSTS: Configured with server IP ($SERVER_IP)$([ -n "$VOTEBEM_DOMAIN" ] && echo " and domain ($VOTEBEM_DOMAIN)")

Next Steps:
1. Review and update .env file: /opt/votebem/.env
2. Run the deployment script: cd /opt/votebem && ./scripts/deploy_production.sh
3. Access your application at: http://$SERVER_IP/$([ -n "$VOTEBEM_DOMAIN" ] && echo " or http://$VOTEBEM_DOMAIN/")

Important Files:
- Application: /opt/votebem/
- Logs: /var/log/votebem/
- Backups: /var/backups/votebem/
- SSL Certificates: /opt/votebem/ssl/

Monitoring:
- System monitor: /opt/votebem/monitor.sh
- Backup script: /opt/votebem/backup.sh
- Logs: tail -f /var/log/votebem/monitor.log

Quick Commands:
- Check application: curl http://$SERVER_IP/health/
- View logs: docker-compose -f docker-compose.yml logs web
- Restart containers: docker-compose -f docker-compose.yml restart
- Switch to votebem user: sudo su - votebem

VoteBem User Commands:
- Deploy application: cd /opt/votebem && ./scripts/deploy_production.sh
- View application logs: cd /opt/votebem && docker-compose logs -f web
- Restart application: cd /opt/votebem && docker-compose restart
EOF

# Display completion message
log "VoteBem application setup completed successfully!"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}VoteBem Application Setup Complete!${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "Server IP: ${YELLOW}$SERVER_IP${NC}"
if [[ -n "$VOTEBEM_DOMAIN" ]]; then
    echo -e "Domain: ${YELLOW}$VOTEBEM_DOMAIN${NC}"
fi
echo -e "Application User: ${YELLOW}votebem${NC}"
echo -e "Application Path: ${YELLOW}/opt/votebem${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}Next steps:${NC}"
echo -e "1. Switch to votebem user: ${YELLOW}sudo su - votebem${NC}"
echo -e "2. Review configuration: ${YELLOW}cd /opt/votebem && nano .env${NC}"
echo -e "3. Deploy application: ${YELLOW}cd /opt/votebem && ./scripts/deploy_production.sh${NC}"
if [[ -n "$VOTEBEM_DOMAIN" && "$INSTALL_CERTBOT" == "true" ]]; then
    echo -e "4. Get SSL certificate: ${YELLOW}sudo certbot --nginx -d $VOTEBEM_DOMAIN${NC}"
fi
echo -e "${BLUE}===========================================${NC}"

log "Application setup completed. Check /opt/votebem/deployment_info.txt for details."