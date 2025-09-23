#!/bin/bash

# VPS Provisioning Script
# This script provisions a VPS with basic security, Docker, and a sudoer user
# Run as root: curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/provision_vps.sh | bash
#
# Environment Variables (optional):
# - SUDOER_USERNAME: Username for the sudoer user (will prompt if not provided)
# - SUDOER_PASSWORD: Password for the sudoer user (will prompt if not provided)
# - SSH_PUBLIC_KEY: SSH public key for the sudoer user (will prompt if not provided)
# - NO_REBOOT: Set to "true" to skip automatic reboot

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

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
fi

log "Starting VPS Provisioning..."

# Get sudoer username
if [[ -z "$SUDOER_USERNAME" ]]; then
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${YELLOW}VPS Provisioning Setup${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo -e "This script will create a sudoer user for managing your VPS."
    echo -e "Please provide a username for the sudoer user:"
    echo -e "${BLUE}===========================================${NC}"
    read -p "Enter username: " SUDOER_USERNAME
    
    # Validate username
    if [[ -z "$SUDOER_USERNAME" ]]; then
        error "Username cannot be empty"
    fi
    
    if [[ ! "$SUDOER_USERNAME" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
        error "Invalid username. Use only lowercase letters, numbers, underscores, and hyphens. Must start with a letter or underscore."
    fi
    
    if [[ ${#SUDOER_USERNAME} -gt 32 ]]; then
        error "Username too long. Maximum 32 characters."
    fi
fi

log "Using sudoer username: $SUDOER_USERNAME"

# Get sudoer password
if [[ -z "$SUDOER_PASSWORD" ]]; then
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${YELLOW}Password Setup${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo -e "Please set a password for the sudoer user '$SUDOER_USERNAME':"
    echo -e "Password requirements:"
    echo -e "- At least 8 characters long"
    echo -e "- Mix of letters, numbers, and special characters recommended"
    echo -e "${BLUE}===========================================${NC}"
    
    while true; do
        read -s -p "Enter password: " SUDOER_PASSWORD
        echo
        
        # Validate password
        if [[ -z "$SUDOER_PASSWORD" ]]; then
            warn "Password cannot be empty. Please try again."
            continue
        fi
        
        if [[ ${#SUDOER_PASSWORD} -lt 8 ]]; then
            warn "Password must be at least 8 characters long. Please try again."
            continue
        fi
        
        read -s -p "Confirm password: " SUDOER_PASSWORD_CONFIRM
        echo
        
        if [[ "$SUDOER_PASSWORD" != "$SUDOER_PASSWORD_CONFIRM" ]]; then
            warn "Passwords do not match. Please try again."
            continue
        fi
        
        break
    done
    
    log "Password set successfully for user '$SUDOER_USERNAME'"
else
    log "Using password from environment variable for user '$SUDOER_USERNAME'"
fi

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
    tree \
    net-tools 

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

# Create sudoer user
log "Creating sudoer user: $SUDOER_USERNAME"
if ! id "$SUDOER_USERNAME" &>/dev/null; then
    useradd -m -s /bin/bash "$SUDOER_USERNAME"
    usermod -aG docker "$SUDOER_USERNAME"
    usermod -aG sudo "$SUDOER_USERNAME"
    
    # Set user password
    echo "$SUDOER_USERNAME:$SUDOER_PASSWORD" | chpasswd
    
    log "User '$SUDOER_USERNAME' created successfully with password"
else
    warn "User '$SUDOER_USERNAME' already exists"
    usermod -aG docker "$SUDOER_USERNAME"
    usermod -aG sudo "$SUDOER_USERNAME"
    
    # Update password for existing user
    echo "$SUDOER_USERNAME:$SUDOER_PASSWORD" | chpasswd
    
    log "Updated groups and password for existing user '$SUDOER_USERNAME'"
fi

# Set up SSH key for sudoer user (optional - set SSH_PUBLIC_KEY environment variable)
if [[ -n "$SSH_PUBLIC_KEY" ]]; then
    log "Setting up SSH key authentication for $SUDOER_USERNAME user..."
    # Remove existing SSH directory if it exists
    if [ -d "/home/$SUDOER_USERNAME/.ssh" ]; then
        rm -rf "/home/$SUDOER_USERNAME/.ssh"
        log "Removed existing SSH directory"
    fi
    sudo -u "$SUDOER_USERNAME" mkdir -p "/home/$SUDOER_USERNAME/.ssh"
    echo "$SSH_PUBLIC_KEY" | sudo -u "$SUDOER_USERNAME" tee "/home/$SUDOER_USERNAME/.ssh/authorized_keys"
    sudo -u "$SUDOER_USERNAME" chmod 700 "/home/$SUDOER_USERNAME/.ssh"
    sudo -u "$SUDOER_USERNAME" chmod 600 "/home/$SUDOER_USERNAME/.ssh/authorized_keys"
    log "SSH key added for $SUDOER_USERNAME user"
else
    log "No SSH key provided (set SSH_PUBLIC_KEY environment variable to add one)"
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

# Install monitoring tools
log "Installing monitoring tools..."
apt install -y htop iotop nethogs

# Configure SSH security
log "Configuring SSH security..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Configure SSH settings
sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
echo "AllowUsers root $SUDOER_USERNAME" >> /etc/ssh/sshd_config

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

# Get server IP for information
log "Detecting server IP address..."
SERVER_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip || hostname -I | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    warn "Could not detect server IP address automatically"
    SERVER_IP="127.0.0.1"
fi
log "Server IP detected: $SERVER_IP"

# Create provisioning info file
log "Creating provisioning info..."
cat > /root/vps_provisioning_info.txt << EOF
VPS Provisioning Completed
==========================
Date: $(date)
Server: $(hostname)
IP: $SERVER_IP
Sudoer User: $SUDOER_USERNAME
Docker Version: $(docker --version)
Docker Compose Version: $(docker-compose --version)

Services Configured:
- Docker: systemctl status docker
- Fail2ban: systemctl status fail2ban
- UFW: ufw status

Security:
- SSH configured for key-based authentication
- Password authentication disabled
- Firewall configured (ports 22, 80, 443, 5678)
- Fail2ban configured for SSH and Nginx protection
- Automatic security updates enabled

Next Steps:
1. Switch to sudoer user: sudo su - $SUDOER_USERNAME
2. Run the VoteBem setup script: setup_votebem.sh
3. Configure your application-specific settings

SSH Access:
- ssh $SUDOER_USERNAME@$SERVER_IP (with SSH key)
- ssh root@$SERVER_IP (with SSH key)

- copie o arquivo id_rsa_bcb2.ppk para ~/.ssh
- altere a permissão da chave (senão ela não funciona): chmod 600 ~/.ssh/id_rsa_bcb2.ppk
- ative o servidor ssh: eval $(ssh-agent)
- adicione a chave: ssh-add ~/.ssh/id_rsa_bcb2.ppk
- em uma linha (após copiar): chmod 600 ~/.ssh/id_rsa_bcb2.ppk; eval $(ssh-agent); ssh-add ~/.ssh/id_rsa_bcb2.ppk

- para acessar o Git remoto (no bash): eval $(ssh-agent); ssh-add C:/Users/desig.cateb/.ssh/id_rsa_paraPutty.ppk
- no computador de casa (no bash): eval $(ssh-agent); ssh-add C:/Users/User/.ssh/id_rsa_paraPutty.ppk
- para conferir as chaves carregadas: ssh-add -l
- to set the SSH agent service to start automatically when you log in and starts it immediately:
    Set-Service -Name 'ssh-agent' -StartupType Automatic
    Start-Service ssh-agent

EOF

# Final system cleanup
log "Cleaning up..."
apt autoremove -y
apt autoclean

# Display completion message
log "VPS provisioning completed successfully!"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}VPS Provisioning Complete!${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "Server IP: ${YELLOW}$SERVER_IP${NC}"
echo -e "Sudoer User: ${YELLOW}$SUDOER_USERNAME${NC}"
echo -e "SSH Access: ${YELLOW}ssh $SUDOER_USERNAME@$SERVER_IP${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}Next steps:${NC}"
echo -e "1. Switch to sudoer user: ${YELLOW}sudo su - $SUDOER_USERNAME${NC}"
echo -e "2. Run VoteBem setup script: ${YELLOW}setup_votebem.sh${NC}"
echo -e "3. Configure your application"
echo -e "${BLUE}===========================================${NC}"

log "Provisioning completed. Check /root/vps_provisioning_info.txt for details."

# Reboot recommendation
if [[ "$NO_REBOOT" = "true" ]]; then
    log "Rebooting server automatically (set NO_REBOOT=true to skip)..."
    reboot
else
    warn "Reboot skipped (NO_REBOOT=true set). Please reboot the server manually when convenient"
fi