# VoteBem Scripts Documentation

This directory contains scripts for deploying and managing the VoteBem application.

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

- **Application**: `/opt/votebem/`
- **Logs**: `/opt/votebem/logs/`
- **SSL Certificates**: `/opt/votebem/ssl/`
- **Backups**: `/opt/votebem/backups/`
- **Environment**: `/opt/votebem/.env`

## Security Considerations

- All passwords are automatically generated with high entropy
- SSL certificates are automatically renewed (when SSL is enabled)
- Firewall is configured to allow only necessary ports
- Application runs with non-privileged user (votebem)
- Database and Redis are password-protected
- Nginx includes security headers