# VoteBem VPS Setup Scripts

This directory contains scripts for setting up a VPS to run the VoteBem Django application. The setup process has been split into two main phases for better modularity and reusability.

## Overview

The VPS setup process is divided into two main scripts:

1. **`provision_vps.sh`** - VPS provisioning and basic security setup
2. **`setup_votebem.sh`** - VoteBem application-specific configuration

Additionally, there's a shared utilities file:

3. **`common_functions.sh`** - Common functions and utilities used by both scripts

## Quick Start

### Option 1: Two-Step Setup (Recommended)

```bash
# Step 1: Provision the VPS (run as root)
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/provision_vps.sh | bash

# Step 2: Setup VoteBem application (run as the sudoer user created in step 1)
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/setup_votebem.sh | bash
```

### Option 2: Environment Variables Setup

```bash
# Step 1: Provision with environment variables
export SUDOER_USERNAME="myuser"
export SUDOER_PASSWORD="secure_password123"
export SSH_PUBLIC_KEY="ssh-rsa AAAAB3NzaC1yc2E... your-key-here"
export NO_REBOOT="true"
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/provision_vps.sh | bash

# Step 2: Setup VoteBem with SSL
export INSTALL_CERTBOT="true"
export VOTEBEM_DOMAIN="yourdomain.com"
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/setup_votebem.sh | bash
```

## Script Details

### 1. provision_vps.sh

**Purpose**: Provisions a fresh VPS with basic security, Docker, and a sudoer user.

**Run as**: Root user

**What it does**:
- Updates system packages
- Installs essential packages (curl, wget, git, etc.)
- Installs Docker and Docker Compose
- Creates a sudoer user (prompts for username if not provided)
- Sets up SSH key authentication
- Creates the sudoer user's `.ssh/` directory with `chmod 700` and correct ownership
- Writes the SSH key to `.ssh/authorized_keys` with `chmod 600` and correct ownership
- Prompts interactively for an SSH public key if `SSH_PUBLIC_KEY` is not provided
- Configures UFW firewall
- Installs and configures Fail2Ban
- Applies basic security hardening
- Optionally reboots the system

**Environment Variables**:
- `SUDOER_USERNAME`: Username for the sudoer user (will prompt if not provided)
- `SUDOER_PASSWORD`: Password for the sudoer user (will prompt if not provided)
- `SSH_PUBLIC_KEY`: SSH public key for the sudoer user (will prompt if not provided)
- `NO_REBOOT`: Set to "true" to skip automatic reboot

**Example Usage**:
```bash
# Interactive setup (will prompt for username and SSH key)
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/provision_vps.sh | bash

# Automated setup
export SUDOER_USERNAME="deploy"
export SUDOER_PASSWORD="your_secure_password"
export SSH_PUBLIC_KEY="ssh-rsa AAAAB3NzaC1yc2E..."
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/provision_vps.sh | bash
```

### 2. setup_votebem.sh

**Purpose**: Configures the VoteBem Django application on a provisioned VPS.

**Run as**: Sudoer user (created by provision_vps.sh)

**Prerequisites**: VPS must be provisioned with `provision_vps.sh` first

**What it does**:
- Creates the `votebem` user
- Sets up application directories (`/dados/votebem`, `/var/log/votebem`, `/var/backups/votebem`)
- Configures log rotation
- Creates backup and monitoring scripts
- Sets up automated cron jobs
- Optionally installs Certbot for SSL certificates
- Clones the VoteBem repository
- Configures environment variables
- Sets up proper file permissions

**Environment Variables**:
- `INSTALL_CERTBOT`: Set to "true" to install Certbot for SSL certificates
- `VOTEBEM_DOMAIN`: Domain name for the application (for SSL certificate)

**Example Usage**:
```bash
# Basic setup
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/setup_votebem.sh | bash

# Setup with SSL support
export INSTALL_CERTBOT="true"
export VOTEBEM_DOMAIN="votebem.example.com"
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/setup_votebem.sh | bash
```

### 3. common_functions.sh

**Purpose**: Provides shared utilities and functions for both scripts.

**Features**:
- Colored logging functions (log, info, warn, error, success, debug, progress)
- System checks (OS support, sudo privileges, disk space, memory)
- User and group management utilities
- Directory management with proper ownership
- File download with retry logic
- Network utilities (IP detection, port checking, service waiting)
- File backup and restore functions
- Password generation and validation utilities

## Directory Structure After Setup

```
/dados/votebem/               # Main application directory
├── django_votebem/           # Django application code
├── docker-compose.yml        # Docker Compose configuration
├── .env                      # Environment variables
├── backup.sh                 # Backup script
├── monitor.sh                # Monitoring script
├── ssl/                      # SSL certificates directory
└── deployment_info.txt       # Deployment information

/var/log/votebem/             # Application logs
├── monitor.log               # Monitoring logs
└── backup.log                # Backup logs

/var/backups/votebem/         # Backup storage
├── db_backup_*.sql.gz        # Database backups
├── media_backup_*.tar.gz     # Media file backups
└── code_backup_*.tar.gz      # Code backups
```

## Post-Setup Steps

After running both scripts, follow these steps to complete the deployment:

1. **Switch to the votebem user**:
   ```bash
   sudo su - votebem
   ```

2. **Review and update configuration**:
   ```bash
cd /dados/votebem
   nano .env  # Update database credentials, secret key, etc.
   ```

3. **Deploy the application**:
   ```bash
cd /dados/votebem
   ./scripts/deploy_production.sh
   ```

4. **Get SSL certificate** (if Certbot was installed):
   ```bash
   sudo certbot --nginx -d yourdomain.com
   ```

5. **Verify the deployment**:
   ```bash
   curl http://your-server-ip/health/
   ```

## Monitoring and Maintenance

### Automated Tasks

The setup creates several automated tasks:

- **Backups**: Daily at 2:00 AM (`/dados/votebem/backup.sh`)
- **Monitoring**: Every 5 minutes (`/dados/votebem/monitor.sh`)
- **Log Rotation**: Daily with 52-day retention

### Manual Commands

```bash
# Check application status
docker-compose -f /dados/votebem/docker-compose.yml ps

# View application logs
docker-compose -f /dados/votebem/docker-compose.yml logs -f web

# Restart application
docker-compose -f /dados/votebem/docker-compose.yml restart

# Run backup manually
/dados/votebem/backup.sh

# Check monitoring logs
tail -f /var/log/votebem/monitor.log

# Check system status
/dados/votebem/monitor.sh
```

## Troubleshooting

### Common Issues

1. **Script fails with permission errors**:
   - Ensure `provision_vps.sh` is run as root
   - Ensure `setup_votebem.sh` is run as a sudoer user (not root)

2. **Docker not found during setup_votebem.sh**:
   - Make sure `provision_vps.sh` completed successfully
   - Verify Docker is installed: `docker --version`

3. **Git clone fails**:
   - Check internet connectivity
   - Verify the repository URL is accessible

4. **SSL certificate issues**:
   - Ensure domain points to your server
   - Check firewall allows ports 80 and 443
   - Verify Certbot installation

### Log Locations

- **Provisioning logs**: Output to terminal during script execution
- **Application logs**: `/var/log/votebem/`
- **Docker logs**: `docker-compose logs`
- **System logs**: `/var/log/syslog`

## Security Considerations

The scripts implement several security measures:

- **Firewall**: UFW configured to allow only SSH, HTTP, and HTTPS
- **Fail2Ban**: Protects against brute force attacks
- **SSH**: Key-based authentication, password authentication disabled
- **User Isolation**: Separate users for system admin and application
- **File Permissions**: Proper ownership and permissions for all files
- **Regular Updates**: System packages are updated during provisioning

## Customization

### Modifying the Scripts

1. **Fork the repository** or download the scripts locally
2. **Edit the scripts** to match your requirements
3. **Test thoroughly** in a development environment
4. **Update the URLs** in your deployment commands

### Environment Variables

Both scripts support environment variables for automation. See the individual script sections above for available variables.

### Adding Custom Functions

Add new functions to `common_functions.sh` and they will be available in both scripts:

```bash
# Add to common_functions.sh
my_custom_function() {
    log "Executing custom function..."
    # Your code here
}

# Use in either script
my_custom_function
```

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the logs for error messages
3. Open an issue in the GitHub repository
4. Consult the Django and Docker documentation

## License

These scripts are part of the VoteBem project and follow the same license terms.