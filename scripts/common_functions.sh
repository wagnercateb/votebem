#!/bin/bash

# Common Functions for VoteBem VPS Setup Scripts
# This file contains shared utilities used by both provision_vps.sh and setup_votebem.sh
# Source this file in other scripts: source "$(dirname "$0")/common_functions.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] SUCCESS: $1${NC}"
}

debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${PURPLE}[$(date +'%Y-%m-%d %H:%M:%S')] DEBUG: $1${NC}"
    fi
}

# Progress indicator
progress() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')] PROGRESS: $1${NC}"
}

# Check if running as root
check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should NOT be run as root. Run as a regular user with sudo privileges."
    fi
}

# Check if user has sudo privileges
check_sudo_privileges() {
    if ! sudo -n true 2>/dev/null; then
        error "This script requires sudo privileges. Please run as a sudoer user."
    fi
}

# Check if running on supported OS
check_supported_os() {
    if [[ ! -f /etc/os-release ]]; then
        error "Cannot determine OS version. This script supports Ubuntu/Debian systems."
    fi
    
    . /etc/os-release
    case $ID in
        ubuntu|debian)
            info "Detected supported OS: $PRETTY_NAME"
            ;;
        *)
            error "Unsupported OS: $PRETTY_NAME. This script supports Ubuntu/Debian systems only."
            ;;
    esac
}

# Update system packages
update_system() {
    log "Updating system packages..."
    sudo apt update
    sudo apt upgrade -y
    sudo apt autoremove -y
    sudo apt autoclean
    success "System packages updated successfully"
}

# Install essential packages
install_essentials() {
    log "Installing essential packages..."
    sudo apt install -y \
        curl \
        wget \
        git \
        unzip \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        htop \
        nano \
        vim \
        tree \
        jq \
        fail2ban \
        ufw
    success "Essential packages installed successfully"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if user exists
user_exists() {
    id "$1" &>/dev/null
}

# Check if group exists
group_exists() {
    getent group "$1" >/dev/null 2>&1
}

# Create user with home directory
create_user() {
    local username="$1"
    local create_home="${2:-true}"
    
    if user_exists "$username"; then
        warn "User '$username' already exists"
        return 0
    fi
    
    if [[ "$create_home" == "true" ]]; then
        sudo useradd -m -s /bin/bash "$username"
    else
        sudo useradd -s /bin/bash "$username"
    fi
    
    success "User '$username' created successfully"
}

# Add user to group
add_user_to_group() {
    local username="$1"
    local groupname="$2"
    
    if ! user_exists "$username"; then
        error "User '$username' does not exist"
    fi
    
    if ! group_exists "$groupname"; then
        warn "Group '$groupname' does not exist, creating it..."
        sudo groupadd "$groupname"
    fi
    
    sudo usermod -aG "$groupname" "$username"
    success "User '$username' added to group '$groupname'"
}

# Create directory with proper ownership
create_directory() {
    local dir_path="$1"
    local owner="${2:-root}"
    local group="${3:-root}"
    local permissions="${4:-755}"
    
    if [[ -d "$dir_path" ]]; then
        warn "Directory '$dir_path' already exists"
    else
        sudo mkdir -p "$dir_path"
        info "Directory '$dir_path' created"
    fi
    
    sudo chown "$owner:$group" "$dir_path"
    sudo chmod "$permissions" "$dir_path"
    success "Directory '$dir_path' configured with owner=$owner:$group, permissions=$permissions"
}

# Clean directory (remove and recreate)
clean_directory() {
    local dir_path="$1"
    local owner="${2:-root}"
    local group="${3:-root}"
    local permissions="${4:-755}"
    
    if [[ -d "$dir_path" ]]; then
        log "Removing existing directory: $dir_path"
        sudo rm -rf "$dir_path"
    fi
    
    create_directory "$dir_path" "$owner" "$group" "$permissions"
}

# Download file with retry
download_file() {
    local url="$1"
    local output_file="$2"
    local max_retries="${3:-3}"
    local retry_count=0
    
    while [[ $retry_count -lt $max_retries ]]; do
        if curl -fsSL "$url" -o "$output_file"; then
            success "Downloaded: $url -> $output_file"
            return 0
        else
            retry_count=$((retry_count + 1))
            warn "Download failed (attempt $retry_count/$max_retries): $url"
            if [[ $retry_count -lt $max_retries ]]; then
                sleep 2
            fi
        fi
    done
    
    error "Failed to download after $max_retries attempts: $url"
}

# Get server IP address
get_server_ip() {
    local ip
    
    # Try multiple methods to get external IP
    ip=$(curl -s --max-time 10 ifconfig.me 2>/dev/null) || \
    ip=$(curl -s --max-time 10 ipinfo.io/ip 2>/dev/null) || \
    ip=$(curl -s --max-time 10 icanhazip.com 2>/dev/null) || \
    ip=$(hostname -I | awk '{print $1}' 2>/dev/null)
    
    if [[ -n "$ip" && "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "$ip"
    else
        warn "Could not detect server IP address, using localhost"
        echo "127.0.0.1"
    fi
}

# Check if port is available
check_port() {
    local port="$1"
    if netstat -tuln | grep -q ":$port "; then
        return 1  # Port is in use
    else
        return 0  # Port is available
    fi
}

# Wait for service to be ready
wait_for_service() {
    local host="${1:-localhost}"
    local port="$2"
    local timeout="${3:-60}"
    local interval="${4:-2}"
    local elapsed=0
    
    info "Waiting for service at $host:$port (timeout: ${timeout}s)..."
    
    while [[ $elapsed -lt $timeout ]]; do
        if nc -z "$host" "$port" 2>/dev/null; then
            success "Service is ready at $host:$port"
            return 0
        fi
        
        sleep "$interval"
        elapsed=$((elapsed + interval))
        progress "Waiting... (${elapsed}s/${timeout}s)"
    done
    
    error "Service at $host:$port did not become ready within ${timeout}s"
}

# Backup file with timestamp
backup_file() {
    local file_path="$1"
    local backup_suffix="${2:-$(date +%Y%m%d_%H%M%S)}"
    
    if [[ -f "$file_path" ]]; then
        local backup_path="${file_path}.backup_${backup_suffix}"
        sudo cp "$file_path" "$backup_path"
        success "File backed up: $file_path -> $backup_path"
        echo "$backup_path"
    else
        warn "File does not exist, no backup needed: $file_path"
        return 1
    fi
}

# Restore file from backup
restore_file() {
    local backup_path="$1"
    local original_path="${backup_path%%.backup_*}"
    
    if [[ -f "$backup_path" ]]; then
        sudo cp "$backup_path" "$original_path"
        success "File restored: $backup_path -> $original_path"
    else
        error "Backup file does not exist: $backup_path"
    fi
}

# Generate random password
generate_password() {
    local length="${1:-16}"
    local chars="A-Za-z0-9!@#$%^&*"
    
    tr -dc "$chars" < /dev/urandom | head -c "$length"
}

# Validate email address
validate_email() {
    local email="$1"
    local regex="^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    
    if [[ $email =~ $regex ]]; then
        return 0
    else
        return 1
    fi
}

# Validate domain name
validate_domain() {
    local domain="$1"
    local regex="^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
    
    if [[ $domain =~ $regex ]]; then
        return 0
    else
        return 1
    fi
}

# Check disk space
check_disk_space() {
    local path="${1:-/}"
    local min_free_gb="${2:-5}"
    
    local available_gb=$(df "$path" | awk 'NR==2 {print int($4/1024/1024)}')
    
    if [[ $available_gb -lt $min_free_gb ]]; then
        error "Insufficient disk space. Available: ${available_gb}GB, Required: ${min_free_gb}GB"
    else
        info "Disk space check passed. Available: ${available_gb}GB"
    fi
}

# Check memory
check_memory() {
    local min_free_mb="${1:-512}"
    
    local available_mb=$(free -m | awk 'NR==2{print $7}')
    
    if [[ $available_mb -lt $min_free_mb ]]; then
        warn "Low memory. Available: ${available_mb}MB, Recommended: ${min_free_mb}MB"
    else
        info "Memory check passed. Available: ${available_mb}MB"
    fi
}

# Print system information
print_system_info() {
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${GREEN}System Information${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo -e "Hostname: ${YELLOW}$(hostname)${NC}"
    echo -e "OS: ${YELLOW}$(lsb_release -d | cut -f2)${NC}"
    echo -e "Kernel: ${YELLOW}$(uname -r)${NC}"
    echo -e "Architecture: ${YELLOW}$(uname -m)${NC}"
    echo -e "CPU: ${YELLOW}$(nproc) cores${NC}"
    echo -e "Memory: ${YELLOW}$(free -h | awk 'NR==2{print $2}')${NC}"
    echo -e "Disk: ${YELLOW}$(df -h / | awk 'NR==2{print $2}')${NC}"
    echo -e "IP Address: ${YELLOW}$(get_server_ip)${NC}"
    echo -e "${BLUE}===========================================${NC}"
}

# Cleanup function for script exit
cleanup() {
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        success "Script completed successfully"
    else
        error "Script failed with exit code: $exit_code"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Export functions for use in other scripts
export -f log info warn error success debug progress
export -f check_not_root check_sudo_privileges check_supported_os
export -f update_system install_essentials command_exists user_exists group_exists
export -f create_user add_user_to_group create_directory clean_directory
export -f download_file get_server_ip check_port wait_for_service
export -f backup_file restore_file generate_password
export -f validate_email validate_domain check_disk_space check_memory
export -f print_system_info cleanup