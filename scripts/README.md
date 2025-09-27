# Scripts Directory

This directory contains all automation scripts for the VoteBem Django application. The scripts are organized by platform and purpose to support both development and production deployment workflows.

## Overview

The scripts in this directory serve different purposes:
- **Development Scripts (Windows)**: `.bat` files for local development setup and management
- **Production Scripts (Linux)**: `.sh` files for VPS provisioning and production deployment
- **Utility Scripts**: Common functions and shared utilities

## Windows Development Scripts (.bat)

These batch files are designed for Windows development environments and provide quick setup and management of the local development environment.

### setup.bat
**Purpose**: Initial development environment setup
**Use Case**: Run this script when setting up the project for the first time on a Windows machine
**What it does**:
- Checks Python version compatibility (3.8+)
- Creates a Python virtual environment (`venv`)
- Activates the virtual environment
- Upgrades pip to the latest version
- Installs all Python dependencies from `requirements.txt`

**Usage**: `.\scripts\setup.bat` (from project root) or `.\setup.bat` (from scripts folder)

### startup.bat
**Purpose**: Start the Django development environment with Docker services
**Use Case**: Daily development workflow when you want to use Docker for database and other services
**What it does**:
- Checks if virtual environment exists
- Attempts to start Docker services (if Docker is available)
- Activates the Python virtual environment
- Prepares the environment for Django development

**Usage**: `.\scripts\startup.bat` (from project root) or `.\startup.bat` (from scripts folder)

### startup_dev.bat
**Purpose**: Start pure local Django development mode
**Use Case**: Development without Docker dependencies, using SQLite database
**What it does**:
- Activates the virtual environment
- Sets up local development environment variables
- Uses SQLite database instead of PostgreSQL
- Enables DEBUG mode and Django Debug Toolbar
- Configures console email backend for testing
- Starts the Django development server

**Usage**: `.\scripts\startup_dev.bat` (from project root) or `.\startup_dev.bat` (from scripts folder)

### stop.bat
**Purpose**: Stop Docker services
**Use Case**: Clean shutdown of Docker containers when finishing development work
**What it does**:
- Stops all Docker Compose services
- Verifies that services have been stopped
- Provides feedback on the shutdown process

**Usage**: `.\scripts\stop.bat` (from project root) or `.\stop.bat` (from scripts folder)

### troubleshoot.bat
**Purpose**: Diagnose common development environment issues
**Use Case**: When experiencing problems with the development setup
**What it does**:
- Checks Python installation and version
- Verifies virtual environment status
- Tests Django installation
- Checks Docker availability and status
- Provides diagnostic information for troubleshooting

**Usage**: `.\scripts\troubleshoot.bat` (from project root) or `.\troubleshoot.bat` (from scripts folder)

## Linux Production Scripts (.sh)

These shell scripts are designed for Linux VPS environments and handle production deployment, SSL setup, and server provisioning.

### common_functions.sh
**Purpose**: Shared utility functions for other shell scripts
**Use Case**: Sourced by other scripts to provide consistent logging and utility functions
**What it provides**:
- Colored logging functions (log, info, warn, error, success, debug)
- Progress indicators
- Common validation functions
- Consistent error handling
- Date/time stamped output

**Usage**: Sourced by other scripts: `source "$(dirname "$0")/common_functions.sh"`

### provision_vps.sh
**Purpose**: Initial VPS server provisioning and security setup
**Use Case**: First-time setup of a fresh VPS for hosting the VoteBem application
**What it does**:
- Creates a sudoer user for server management
- Configures SSH key authentication
- Sets up basic security (firewall, fail2ban)
- Installs Docker and Docker Compose
- Configures automatic security updates
- Hardens SSH configuration
- Sets up log rotation

**Usage**: `curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/provision_vps.sh | bash`
**Requirements**: Must be run as root on a fresh VPS

### setup_votebem.sh
**Purpose**: VoteBem application setup and configuration
**Use Case**: Deploy the VoteBem application after VPS provisioning
**What it does**:
- Creates the `votebem` user for application management
- Clones the application repository
- Sets up the application directory structure
- Configures environment variables
- Sets up Docker containers for the application
- Configures nginx reverse proxy
- Sets up application-specific services

**Usage**: `curl -sSL https://raw.githubusercontent.com/wagnercateb/votebem/main/scripts/setup_votebem.sh | bash`
**Requirements**: Must be run as a sudoer user after VPS provisioning

### deploy_production.sh
**Purpose**: Production deployment and updates
**Use Case**: Deploy new versions of the application to production
**What it does**:
- Pulls latest code from the repository
- Builds new Docker images
- Performs database migrations
- Updates static files
- Restarts application services with zero-downtime deployment
- Validates deployment success
- Provides rollback capabilities

**Usage**: `./scripts/deploy_production.sh` (from project root)
**Requirements**: Must be run as the `votebem` user on a configured server

### setup_ssl.sh
**Purpose**: SSL certificate setup with Let's Encrypt
**Use Case**: Enable HTTPS for the production application
**What it does**:
- Installs Certbot for Let's Encrypt certificates
- Configures nginx for SSL termination
- Obtains SSL certificates for the domain
- Sets up automatic certificate renewal
- Configures secure SSL settings
- Updates nginx configuration for HTTPS

**Usage**: `./scripts/setup_ssl.sh` (from project root)
**Requirements**: Must be run as the `votebem` user with a configured domain

## Script Dependencies and Workflow

### Development Workflow (Windows)
1. **First Time Setup**: Run `setup.bat`
2. **Daily Development**: Run `startup.bat` or `startup_dev.bat`
3. **End of Day**: Run `stop.bat`
4. **Troubleshooting**: Run `troubleshoot.bat`

### Production Deployment Workflow (Linux)
1. **VPS Setup**: Run `provision_vps.sh` (as root)
2. **Application Setup**: Run `setup_votebem.sh` (as sudoer)
3. **SSL Setup**: Run `setup_ssl.sh` (as votebem user)
4. **Updates**: Run `deploy_production.sh` (as votebem user)

## Environment Variables

### Windows Scripts
- No specific environment variables required (scripts handle environment setup)

### Linux Scripts
- `SUDOER_USERNAME`: Username for the sudoer user (provision_vps.sh)
- `SUDOER_PASSWORD`: Password for the sudoer user (provision_vps.sh)
- `SSH_PUBLIC_KEY`: SSH public key for authentication (provision_vps.sh)
- `VOTEBEM_DOMAIN`: Domain name for SSL certificates (setup_ssl.sh)
- `VOTEBEM_PASSWORD`: Password for the votebem user (setup_votebem.sh)
- `NO_REBOOT`: Skip automatic reboot (provision_vps.sh)

## Security Considerations

- **Windows Scripts**: Run in local development environment only
- **Linux Scripts**: Include security hardening and follow production best practices
- **SSH Keys**: Use key-based authentication for production servers
- **SSL/TLS**: Automatic HTTPS setup with Let's Encrypt certificates
- **User Separation**: Dedicated users for different functions (sudoer, votebem)

## Troubleshooting

### Windows Development Issues
- Run `troubleshoot.bat` for automated diagnostics
- Check Python version compatibility (3.8+)
- Verify Docker Desktop installation and status
- Ensure virtual environment is properly activated

### Linux Production Issues
- Check script logs for detailed error messages
- Verify user permissions and sudo access
- Ensure Docker and Docker Compose are properly installed
- Check firewall settings and port availability
- Verify domain DNS configuration for SSL setup

## Contributing

When adding new scripts:
1. Follow the existing naming conventions
2. Include proper error handling and logging
3. Add comprehensive comments explaining the script's purpose
4. Update this README with the new script's documentation
5. Test scripts in appropriate environments before committing