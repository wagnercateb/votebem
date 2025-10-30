# VoteBem Scripts Documentation

This directory contains scripts for deploying and managing the VoteBem application.

## Scripts Directory Overview

### Windows Development Scripts (.bat)
- `setup.bat`
  - Purpose: Initial development environment setup (venv, pip, deps)
  - Usage: `.\scripts\setup.bat` (from project root) or `.\setup.bat` (from scripts folder)
- `startup.bat`
  - Purpose: Start the Django development environment with Docker services
  - Usage: `.\scripts\startup.bat` or `.\startup.bat`
- `startup_dev.bat`
  - Purpose: Pure local Django development (SQLite), DEBUG tools enabled
  - Usage: `.\scripts\startup_dev.bat` or `.\startup_dev.bat`
- `stop.bat`
  - Purpose: Clean shutdown of Docker Compose services used in dev
  - Usage: `.\scripts\stop.bat` or `.\stop.bat`
- `troubleshoot.bat`
  - Purpose: Diagnose common development environment issues (Python, venv, Docker)
  - Usage: `.\scripts\troubleshoot.bat` or `.\troubleshoot.bat`

### Linux Production Scripts (.sh)
- `common_functions.sh`
  - Purpose: Shared utility functions (logging, validation, error handling)
  - Usage: Source from other scripts: `source "$(dirname "$0")/common_functions.sh"`
- `provision_vps.sh`
  - Purpose: Initial VPS provisioning and security setup (run as root)
  - Usage: `curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/provision_vps.sh | bash`
- `setup_votebem.sh`
  - Purpose: VoteBem application setup on a provisioned VPS (run as sudoer)
  - Usage: `curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/setup_votebem.sh | bash`
- `deploy_production.sh`
  - Purpose: Production deployment and updates (build, migrate, static, restart)
  - Usage: `./scripts/deploy_production.sh` (from project root)
- `setup_ssl.sh`
  - Purpose: SSL certificates with Let's Encrypt, HTTPS nginx configuration
  - Usage: `./scripts/setup_ssl.sh` (after DNS points to server)

## Script Dependencies and Workflow

### Development Workflow (Windows)
1. First-time setup: run `setup.bat`
2. Daily development: run `startup.bat` (or `startup_dev.bat` for pure local)
3. End of day: run `stop.bat`
4. Troubleshooting: run `troubleshoot.bat`

### Production Deployment Workflow (Linux)
1. VPS Setup: run `provision_vps.sh` (as root)
2. Application Setup: run `setup_votebem.sh` (as sudoer)
3. SSL Setup: run `setup_ssl.sh` (as sudoer, with domain configured)
4. Updates/Deploy: run `deploy_production.sh` (as application user)

## Environment Variables

### Windows Scripts
- No specific environment variables required; scripts handle environment setup.

### Linux Scripts
- `SUDOER_USERNAME`: Username for the sudoer user (provision_vps.sh)
- `SUDOER_PASSWORD`: Password for the sudoer user (provision_vps.sh)
- `SSH_PUBLIC_KEY`: SSH public key for authentication (provision_vps.sh)
- `VOTEBEM_DOMAIN`: Domain name for SSL certificates (setup_votebem.sh / setup_ssl.sh)
- `VOTEBEM_PASSWORD`: Password for the votebem user (setup_votebem.sh)
- `NO_REBOOT`: Skip automatic reboot (provision_vps.sh)

## Available Scripts

### 1. `deploy_production.sh`
**Purpose**: Main production deployment script that sets up the entire application with HTTP-only configuration by default.

**Usage:**
```bash
chmod +x scripts/deploy_production.sh
./scripts/deploy_production.sh
```

**What it does:**
- Clones or updates the repository
- Generates secure environment variables
- Creates production Docker Compose configuration
- Sets up HTTP-only nginx configuration
- Builds and starts all containers
- Optionally creates Django superuser

### 2. `setup_ssl.sh`
**Purpose**: Sets up SSL certificates using Let's Encrypt and configures HTTPS.

**Prerequisites**: 
- Application must be running (run `deploy_production.sh` first)
- Domain must point to your server's IP address
- Port 80 must be accessible from the internet

**Usage:**
```bash
chmod +x scripts/setup_ssl.sh
./scripts/setup_ssl.sh
```

**What it does:**
- Generates SSL certificates using Let's Encrypt
- Creates HTTPS-enabled nginx configuration
- Sets up automatic certificate renewal
- Redirects HTTP traffic to HTTPS

### 3. `fix_containers.sh`
**Purpose**: Quick fix script for common container issues (database authentication, SSL errors).

**Usage:**
```bash
chmod +x scripts/fix_containers.sh
./scripts/fix_containers.sh
```

**What it does:**
- Stops all containers and removes problematic volumes
- Creates clean HTTP-only nginx configuration
- Rebuilds containers with fresh database credentials
- Tests application health

### 4. `setup_linode_vps.sh`
**Purpose**: Initial VPS setup script specifically designed for Linode servers.

**Usage:**
```bash
chmod +x scripts/setup_linode_vps.sh
sudo ./scripts/setup_linode_vps.sh
```

**What it does:**
- Updates system packages
- Installs Docker and Docker Compose
- Creates votebem user with proper permissions
- Sets up SSH keys for GitHub access
- Configures firewall rules
- Prepares the system for application deployment

## Deployment Workflows

### Initial Deployment (HTTP-only)
1. **Initial VPS Setup** (run as root):
   ```bash
   sudo ./scripts/setup_linode_vps.sh
   ```

2. **Application Deployment** (run as votebem user):
   ```bash
   sudo su - votebem
   ./scripts/deploy_production.sh
   ```

3. **Create Superuser**:
   ```bash
   docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser --settings=votebem.settings.production
   ```

### Adding SSL (after initial deployment)
1. Ensure domain points to your server
2. Run SSL setup:
   ```bash
   ./scripts/setup_ssl.sh
   ```

### Fixing Container Issues
If containers are restarting or have authentication errors:
```bash
./scripts/fix_containers.sh
```

## Environment Variables

The deployment script automatically generates secure environment variables including:
- Database credentials
- Redis password
- Django secret key
- HTTPS configuration (when SSL is enabled)
- Email settings (template)

## SSL Configuration

SSL is set up separately using the `setup_ssl.sh` script. This approach:
- Keeps the main deployment simple and reliable
- Allows HTTP-only deployments for testing
- Provides clean SSL setup when needed
- Includes automatic certificate renewal

## Troubleshooting

### Common Issues

1. **Container Restart Loops**: Run `./scripts/fix_containers.sh`
2. **Database Authentication Errors**: Remove volumes and restart containers
3. **SSL Certificate Errors**: Use HTTP-only configuration first, then add SSL
4. **Permission Denied**: Ensure scripts are executable with `chmod +x`

### Useful Commands

```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs [service_name]

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Test application health
curl http://your-server-ip/health/

# Create superuser
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser --settings=votebem.settings.production
```

## File Locations

- **Application**: `/dados/votebem/`
- **Logs**: `/dados/votebem/logs/`
- **SSL Certificates**: `/dados/votebem/ssl/`
- **Backups**: `/dados/votebem/backups/`
- **Environment**: `/dados/votebem/.env`

## Security Considerations

- All passwords are automatically generated with high entropy
- SSL certificates are automatically renewed (when SSL is enabled)
- Firewall is configured to allow only necessary ports
- Application runs with non-privileged user (votebem)
- Database and Redis are password-protected
- Nginx includes security headers