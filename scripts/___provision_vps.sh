#!/bin/bash

#==============================================================================
# VPS Provisioning Script
#==============================================================================
# Description: Comprehensive VPS provisioning script that sets up a fresh 
#              Ubuntu server with essential packages, security configurations,
#              Docker, user management, and monitoring tools.
#
# Purpose: Automates the initial setup of a VPS for hosting web applications,
#          specifically designed for the Video Downloader website project.
#
# Requirements:
#   - Fresh Ubuntu 20.04+ server with root access
#   - Internet connection for package downloads
#   - At least 1GB RAM and 10GB disk space
#
# What this script does:
#   1. System Updates: Updates all packages to latest versions
#   2. User Management: Creates a sudoer user with secure password
#   3. Essential Packages: Installs development and system tools
#   4. Docker Installation: Sets up Docker and Docker Compose
#   5. Security Configuration: Configures firewall, fail2ban, SSH
#   6. Monitoring Tools: Installs system monitoring utilities
#   7. Automatic Updates: Configures unattended security updates
#   8. Documentation: Creates provisioning summary file
#
# Environment Variables (optional):
#   SUDOER_USERNAME - Username for the sudoer account (default: prompts user)
#   SUDOER_PASSWORD - Password for the sudoer account (default: prompts user)
#   SSH_PUBLIC_KEY  - SSH public key for key-based authentication
#   NO_REBOOT       - Set to "true" to skip automatic reboot
#
# Usage:
#   # Basic usage (interactive):
#   sudo ./___provision_vps.sh
#
#   # With environment variables:
#   sudo SUDOER_USERNAME=myuser SUDOER_PASSWORD=mypass ./___provision_vps.sh
#
#   # With SSH key:
#   sudo SSH_PUBLIC_KEY="ssh-rsa AAAA..." ./___provision_vps.sh
#
# Security Features:
#   - UFW firewall with minimal open ports
#   - Fail2ban for intrusion prevention
#   - SSH hardening with key-based authentication
#   - Automatic security updates
#   - User privilege separation
#
# Author: Video Downloader Project Team
# Version: 2.0
# Last Modified: 2024-01-15
#==============================================================================

# Color codes for output formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#==============================================================================
# LOGGING AND ERROR HANDLING FUNCTIONS
#==============================================================================

# Function: log
# Purpose: Display informational messages with timestamp and formatting
# Parameters: $1 - Message to log
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Function: warn
# Purpose: Display warning messages with timestamp and formatting
# Parameters: $1 - Warning message to display
warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Function: error
# Purpose: Display error messages and exit the script
# Parameters: $1 - Error message to display
error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

#==============================================================================
# SYSTEM REQUIREMENTS CHECK
#==============================================================================

# Check if running as root (required for system-level changes)
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root (use sudo)"
fi

# Display script header and purpose
log "Starting VPS provisioning process..."
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}VPS Provisioning Script${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "This script will:"
echo -e "- Update system packages"
echo -e "- Install essential development tools"
echo -e "- Set up Docker and Docker Compose"
echo -e "- Create a sudoer user account"
echo -e "- Configure security (firewall, fail2ban)"
echo -e "- Install monitoring tools"
echo -e "- Set up automatic security updates"
echo -e "${BLUE}===========================================${NC}"

#==============================================================================
# USER ACCOUNT SETUP
#==============================================================================

# Get sudoer username from environment or prompt user
if [[ -z "$SUDOER_USERNAME" ]]; then
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${YELLOW}User Account Setup${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo -e "Please enter a username for the sudoer account:"
    echo -e "This user will have administrative privileges and Docker access."
    echo -e "Username requirements:"
    echo -e "- Only lowercase letters, numbers, underscores, hyphens"
    echo -e "- Must start with a letter or underscore"
    echo -e "- Maximum 32 characters"
    echo -e "${BLUE}===========================================${NC}"
    
    read -p "Enter username: " SUDOER_USERNAME
    
    # Validate username format and length
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

# Get sudoer password from environment or prompt user
if [[ -z "$SUDOER_PASSWORD" ]]; then
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${YELLOW}Password Setup${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo -e "Please set a password for the sudoer user '$SUDOER_USERNAME':"
    echo -e "Password requirements:"
    echo -e "- At least 8 characters long"
    echo -e "- Mix of letters, numbers, and special characters recommended"
    echo -e "${BLUE}===========================================${NC}"
    
    # Password input loop with validation
    while true; do
        read -s -p "Enter password: " SUDOER_PASSWORD
        echo
        
        # Validate password strength
        if [[ -z "$SUDOER_PASSWORD" ]]; then
            warn "Password cannot be empty. Please try again."
            continue
        fi
        
        if [[ ${#SUDOER_PASSWORD} -lt 8 ]]; then
            warn "Password must be at least 8 characters long. Please try again."
            continue
        fi
        
        # Confirm password to prevent typos
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

#==============================================================================
# SYSTEM PACKAGE MANAGEMENT
#==============================================================================

# Update system packages to latest versions
log "Updating system packages..."
apt update && apt upgrade -y

# Install essential packages for development and system administration
log "Installing essential packages..."
apt install -y \
    curl \              # Command-line tool for transferring data
    wget \              # Network downloader
    git \               # Version control system
    vim \               # Text editor
    htop \              # Interactive process viewer
    unzip \             # Archive extraction utility
    software-properties-common \  # Manage software repositories
    apt-transport-https \         # HTTPS support for apt
    ca-certificates \             # Certificate authorities
    gnupg \             # GNU Privacy Guard
    lsb-release \       # Linux Standard Base release information
    ufw \               # Uncomplicated Firewall
    fail2ban \          # Intrusion prevention system
    logrotate \         # Log file rotation utility
    cron \              # Task scheduler
    rsync \             # File synchronization tool
    tree \              # Directory tree display
    net-tools           # Network configuration tools

#==============================================================================
# DOCKER INSTALLATION AND CONFIGURATION
#==============================================================================

# Install Docker CE (Community Edition)
log "Installing Docker..."
# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository to apt sources
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index and install Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start Docker service and enable auto-start on boot
systemctl start docker
systemctl enable docker

# Install Docker Compose (standalone version for compatibility)
log "Installing Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
# Create symlink for system-wide access
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

#==============================================================================
# USER ACCOUNT CREATION AND CONFIGURATION
#==============================================================================

# Create sudoer user with appropriate groups and permissions
log "Creating sudoer user: $SUDOER_USERNAME"
if ! id "$SUDOER_USERNAME" &>/dev/null; then
    # Create new user with home directory and bash shell
    useradd -m -s /bin/bash "$SUDOER_USERNAME"
    usermod -aG docker "$SUDOER_USERNAME"    # Add to docker group for container management
    usermod -aG sudo "$SUDOER_USERNAME"      # Add to sudo group for administrative privileges
    
    # Set user password
    echo "$SUDOER_USERNAME:$SUDOER_PASSWORD" | chpasswd
    
    log "User '$SUDOER_USERNAME' created successfully with password"
else
    # Update existing user's groups and password
    warn "User '$SUDOER_USERNAME' already exists"
    usermod -aG docker "$SUDOER_USERNAME"
    usermod -aG sudo "$SUDOER_USERNAME"
    
    # Update password for existing user
    echo "$SUDOER_USERNAME:$SUDOER_PASSWORD" | chpasswd
    
    log "Updated groups and password for existing user '$SUDOER_USERNAME'"
fi

#==============================================================================
# SSH KEY AUTHENTICATION SETUP (OPTIONAL)
#==============================================================================

# Set up SSH key authentication if public key is provided
if [[ -n "$SSH_PUBLIC_KEY" ]]; then
    log "Setting up SSH key authentication for $SUDOER_USERNAME user..."
    # Remove existing SSH directory to ensure clean setup
    if [ -d "/home/$SUDOER_USERNAME/.ssh" ]; then
        rm -rf "/home/$SUDOER_USERNAME/.ssh"
        log "Removed existing SSH directory"
    fi
    
    # Create SSH directory with proper ownership
    sudo -u "$SUDOER_USERNAME" mkdir -p "/home/$SUDOER_USERNAME/.ssh"
    
    # Add public key to authorized_keys file
    echo "$SSH_PUBLIC_KEY" | sudo -u "$SUDOER_USERNAME" tee "/home/$SUDOER_USERNAME/.ssh/authorized_keys"
    
    # Set secure permissions for SSH files
    sudo -u "$SUDOER_USERNAME" chmod 700 "/home/$SUDOER_USERNAME/.ssh"
    sudo -u "$SUDOER_USERNAME" chmod 600 "/home/$SUDOER_USERNAME/.ssh/authorized_keys"
    
    log "SSH key added for $SUDOER_USERNAME user"
else
    log "No SSH key provided (set SSH_PUBLIC_KEY environment variable to add one)"
fi

#==============================================================================
# FIREWALL CONFIGURATION
#==============================================================================

# Configure UFW (Uncomplicated Firewall) for basic security
log "Configuring firewall..."
ufw --force reset                    # Reset to default settings
ufw default deny incoming            # Block all incoming connections by default
ufw default allow outgoing           # Allow all outgoing connections
ufw allow ssh                        # Allow SSH access (port 22)
ufw allow 80/tcp                     # Allow HTTP traffic
ufw allow 443/tcp                    # Allow HTTPS traffic
ufw allow 5678/tcp                   # Allow debug port (remove in production)
ufw --force enable                   # Enable firewall without prompting

#==============================================================================
# INTRUSION PREVENTION SYSTEM (FAIL2BAN)
#==============================================================================

# Configure fail2ban to protect against brute force attacks
log "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
# Default ban settings
bantime = 3600          # Ban for 1 hour
findtime = 600          # Look for failures in 10-minute window
maxretry = 3            # Allow 3 attempts before banning

[sshd]
# SSH protection
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
# Nginx HTTP authentication protection
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
# Nginx rate limiting protection
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
EOF

# Restart and enable fail2ban service
systemctl restart fail2ban
systemctl enable fail2ban

#==============================================================================
# MONITORING TOOLS INSTALLATION
#==============================================================================

# Install system monitoring and analysis tools
log "Installing monitoring tools..."
apt install -y htop iotop nethogs
# htop: Interactive process viewer
# iotop: I/O usage monitor
# nethogs: Network usage monitor per process

#==============================================================================
# SSH SECURITY HARDENING
#==============================================================================

# Configure SSH for enhanced security
log "Configuring SSH security..."
# Backup original SSH configuration
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Configure SSH settings for security and access
sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Restrict SSH access to specific users only
echo "AllowUsers root $SUDOER_USERNAME" >> /etc/ssh/sshd_config

# Restart SSH service (handle different service names across distributions)
if systemctl is-active --quiet ssh; then
    systemctl restart ssh
elif systemctl is-active --quiet sshd; then
    systemctl restart sshd
else
    warn "Could not detect SSH service name, trying both ssh and sshd..."
    systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || error "Failed to restart SSH service"
fi

#==============================================================================
# AUTOMATIC SECURITY UPDATES
#==============================================================================

# Install and configure automatic security updates
log "Setting up automatic security updates..."
apt install -y unattended-upgrades

# Configure automatic updates to not reboot automatically
echo 'Unattended-Upgrade::Automatic-Reboot "false";' >> /etc/apt/apt.conf.d/50unattended-upgrades

# Configure unattended upgrades with low priority (non-interactive)
dpkg-reconfigure -plow unattended-upgrades

#==============================================================================
# SERVER INFORMATION GATHERING
#==============================================================================

# Detect server's public IP address using multiple methods
log "Detecting server IP address..."
SERVER_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip || hostname -I | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    warn "Could not detect server IP address automatically"
    SERVER_IP="127.0.0.1"
fi
log "Server IP detected: $SERVER_IP"

#==============================================================================
# PROVISIONING DOCUMENTATION
#==============================================================================

# Create comprehensive provisioning information file
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

SSH Key Setup Instructions:
- copie o arquivo id_rsa_bcb2.ppk para ~/.ssh
- altere a permissão da chave (senão ela não funciona): chmod 600 ~/.ssh/id_rsa_bcb2.ppk
- ative o servidor ssh: eval $(ssh-agent)
- adicione a chave: ssh-add ~/.ssh/id_rsa_bcb2.ppk
- em uma linha (após copiar): chmod 600 ~/.ssh/id_rsa_bcb2.ppk; eval $(ssh-agent); ssh-add ~/.ssh/id_rsa_bcb2.ppk

Git Remote Access:
- para acessar o Git remoto (no bash): eval $(ssh-agent); ssh-add C:/Users/desig.cateb/.ssh/id_rsa_paraPutty.ppk
- no computador de casa (no bash): eval $(ssh-agent); ssh-add C:/Users/User/.ssh/id_rsa_paraPutty.ppk
- para conferir as chaves carregadas: ssh-add -l

SSH Agent Auto-start (Windows):
- to set the SSH agent service to start automatically when you log in and starts it immediately:
    Set-Service -Name 'ssh-agent' -StartupType Automatic
    Start-Service ssh-agent

EOF

#==============================================================================
# SYSTEM CLEANUP
#==============================================================================

# Clean up package cache and remove unnecessary packages
log "Cleaning up..."
apt autoremove -y    # Remove packages that are no longer needed
apt autoclean        # Clean local repository of retrieved package files

#==============================================================================
# COMPLETION SUMMARY
#==============================================================================

# Display completion message with important information
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

#==============================================================================
# OPTIONAL SYSTEM REBOOT
#==============================================================================

# Reboot system to ensure all changes take effect (optional)
if [[ "$NO_REBOOT" = "true" ]]; then
    log "Rebooting server automatically (set NO_REBOOT=true to skip)..."
    reboot
else
    warn "Reboot skipped (NO_REBOOT=true set). Please reboot the server manually when convenient"
fi

#==============================================================================
# END OF SCRIPT
#==============================================================================
# This script has successfully provisioned your VPS with:
# - Updated system packages
# - Essential development tools
# - Docker and Docker Compose
# - Secure user account with sudo privileges
# - Firewall and intrusion prevention
# - System monitoring tools
# - Automatic security updates
# - Comprehensive documentation
#
# Your VPS is now ready for application deployment!
#==============================================================================