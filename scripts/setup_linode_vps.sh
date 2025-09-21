#!/bin/bash

# VoteBem - Linode VPS Setup Script
# This script configures a fresh Linode VPS for hosting the Django VoteBem application
# Run as root: curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/setup_linode_vps.sh | bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
fi

log "Starting VoteBem VPS Setup..."

# Update system
log "Updating system packages..."
apt update && apt upgrade -y

# Install essential packages
log "Installing essential packages..."
apt install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    logrotate \
    cron \
    rsync \
    tree

# Install Docker
log "Installing Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Install Docker Compose (standalone)
log "Installing Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Create votebem user
log "Creating votebem user..."
if ! id "votebem" &>/dev/null; then
    useradd -m -s /bin/bash votebem
    usermod -aG docker votebem
    usermod -aG sudo votebem
else
    warn "User 'votebem' already exists"
fi

# Set up SSH key for votebem user (optional)
read -p "Do you want to set up SSH key authentication for votebem user? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter the public SSH key: " ssh_key
    if [[ -n "$ssh_key" ]]; then
        sudo -u votebem mkdir -p /home/votebem/.ssh
        echo "$ssh_key" | sudo -u votebem tee /home/votebem/.ssh/authorized_keys
        sudo -u votebem chmod 700 /home/votebem/.ssh
        sudo -u votebem chmod 600 /home/votebem/.ssh/authorized_keys
        log "SSH key added for votebem user"
    fi
fi

# Configure firewall
log "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 5678/tcp  # Debug port (remove in production)
ufw --force enable

# Configure fail2ban
log "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
EOF

systemctl restart fail2ban
systemctl enable fail2ban

# Create application directories
log "Creating application directories..."
mkdir -p /opt/votebem
mkdir -p /var/log/votebem
mkdir -p /var/backups/votebem
chown -R votebem:votebem /opt/votebem
chown -R votebem:votebem /var/log/votebem
chown -R votebem:votebem /var/backups/votebem

# Set up log rotation
log "Setting up log rotation..."
cat > /etc/logrotate.d/votebem << EOF
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

# Install monitoring tools
log "Installing monitoring tools..."
apt install -y htop iotop nethogs

# Create backup script
log "Creating backup script..."
cat > /opt/votebem/backup.sh << 'EOF'
#!/bin/bash

# VoteBem Backup Script
BACKUP_DIR="/var/backups/votebem"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
echo "Creating database backup..."
docker-compose -f /opt/votebem/docker-compose.yml exec -T db pg_dump -U votebem_user votebem_db | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"

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

chmod +x /opt/votebem/backup.sh
chown votebem:votebem /opt/votebem/backup.sh

# Set up cron job for backups
log "Setting up automated backups..."
(crontab -u votebem -l 2>/dev/null; echo "0 2 * * * /opt/votebem/backup.sh >> /var/log/votebem/backup.log 2>&1") | crontab -u votebem -

# Create system monitoring script
log "Creating monitoring script..."
cat > /opt/votebem/monitor.sh << 'EOF'
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

chmod +x /opt/votebem/monitor.sh
chown votebem:votebem /opt/votebem/monitor.sh

# Set up monitoring cron job
(crontab -u votebem -l 2>/dev/null; echo "*/5 * * * * /opt/votebem/monitor.sh") | crontab -u votebem -

# Configure SSH security
log "Configuring SSH security..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# o ideal é não permitir root login
sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/' /etc/ssh/sshd_config

sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
echo "AllowUsers root votebem" >> /etc/ssh/sshd_config

# Detect SSH service name and restart
if systemctl is-active --quiet ssh; then
    systemctl restart ssh
elif systemctl is-active --quiet sshd; then
    systemctl restart sshd
else
    warn "Could not detect SSH service name, trying both ssh and sshd..."
    systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || error "Failed to restart SSH service"
fi

# Install and configure automatic updates
log "Setting up automatic security updates..."
apt install -y unattended-upgrades
echo 'Unattended-Upgrade::Automatic-Reboot "false";' >> /etc/apt/apt.conf.d/50unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# Create SSL certificate directory
log "Creating SSL certificate directory..."
mkdir -p /opt/votebem/ssl
chown votebem:votebem /opt/votebem/ssl

# Install Certbot for Let's Encrypt (optional)
read -p "Do you want to install Certbot for SSL certificates? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Installing Certbot..."
    apt install -y certbot python3-certbot-nginx
    log "Certbot installed. Run 'certbot --nginx -d yourdomain.com' to get SSL certificate"
fi

# Clone the repository and set up the application
log "Cloning VoteBem repository..."
sudo -u votebem git clone https://github.com/wagnercateb/django-votebem.git /opt/votebem
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

# Update ALLOWED_HOSTS to include server IP
sudo -u votebem sed -i "s|ALLOWED_HOSTS=localhost,127.0.0.1|ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP|" .env

# Set proper ownership
chown -R votebem:votebem /opt/votebem

# Create deployment info file
log "Creating deployment info..."
cat > /opt/votebem/deployment_info.txt << EOF
VoteBem VPS Setup Completed
============================
Date: $(date)
Server: $(hostname)
IP: $SERVER_IP
Docker Version: $(docker --version)
Docker Compose Version: $(docker-compose --version)

Repository: Cloned and configured
ALLOWED_HOSTS: Configured with server IP ($SERVER_IP)

Next Steps:
1. Switch to votebem user: sudo su - votebem
2. Run the deployment script: cd /opt/votebem && ./scripts/deploy_production.sh
3. Access your application at: http://$SERVER_IP/

Important Files:
- Application: /opt/votebem/
- Logs: /var/log/votebem/
- Backups: /var/backups/votebem/
- SSL Certificates: /opt/votebem/ssl/

Services:
- Docker: systemctl status docker
- Fail2ban: systemctl status fail2ban
- UFW: ufw status

Monitoring:
- System monitor: /opt/votebem/monitor.sh
- Backup script: /opt/votebem/backup.sh
- Logs: tail -f /var/log/votebem/monitor.log

Quick Commands:
- Check application: curl http://$SERVER_IP/health/
- View logs: docker-compose -f docker-compose.prod.yml logs web
- Restart containers: docker-compose -f docker-compose.prod.yml restart
EOF

chown votebem:votebem /opt/votebem/deployment_info.txt

# Final system cleanup
log "Cleaning up..."
apt autoremove -y
apt autoclean

# Display completion message
log "VPS setup completed successfully!"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}VoteBem VPS Setup Complete!${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "Server IP: ${YELLOW}$(curl -s ifconfig.me)${NC}"
echo -e "SSH User: ${YELLOW}votebem${NC}"
echo -e "Application Path: ${YELLOW}/opt/votebem${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}Next steps:${NC}"
echo -e "1. Switch to votebem user: ${YELLOW}sudo su - votebem${NC}"
echo -e "2. Clone repository and deploy application"
echo -e "3. Configure domain and SSL certificate"
echo -e "${BLUE}===========================================${NC}"

log "Setup script completed. Check /opt/votebem/deployment_info.txt for details."

# Reboot recommendation
read -p "Do you want to reboot the server now? (recommended) (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Rebooting server..."
    reboot
else
    warn "Please reboot the server manually when convenient"
fi