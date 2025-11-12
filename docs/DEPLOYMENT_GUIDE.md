# Visão Geral
- para acessar o Git remoto (no bash): eval $(ssh-agent); ssh-add C:/Users/desig.cateb/.ssh/id_rsa_paraPutty.ppk
- no computador de casa (no bash): eval $(ssh-agent); ssh-add C:/Users/User/.ssh/id_rsa_paraPutty.ppk
- para conferir as chaves carregadas: ssh-add -l
- to set the SSH agent service to start automatically when you log in and starts it immediately:
    Set-Service -Name 'ssh-agent' -StartupType Automatic
    Start-Service ssh-agent

- copie o arquivo id_rsa_bcb2.ppk para ~/.ssh
- altere a permissão da chave (senão ela não funciona): chmod 600 ~/.ssh/id_rsa_bcb2.ppk
- ative o servidor ssh: eval $(ssh-agent)
- adicione a chave: ssh-add ~/.ssh/id_rsa_bcb2.ppk


# Complete Docker Setup for VoteBem Django Application

This comprehensive guide covers the complete dockerization of the VoteBem Django application with production-ready deployment on a VPS, including remote debugging capabilities.

## 🐳 Docker Configuration Overview

The application has been fully containerized with separate configurations for development and production environments:

### Production Configuration
- **Dockerfile**: Production-ready container with Gunicorn, MariaDB support, and remote debugging
- **docker-compose.yml**: Production stack (Django + MariaDB + Redis + Nginx)
- Optimized for performance and security
- Includes health checks and persistent volumes

### Development Configuration
- **Dockerfile.dev**: Development container with debugging tools and Jupyter support
- **docker-compose.dev.yml**: Development environment with debugging ports exposed
- Hot-reload capabilities for faster development
- Integrated debugging tools

## ⚙️ Django Settings Architecture

The Django settings have been restructured into a modular architecture:

```
votebem/settings/
├── __init__.py
├── base.py          # Common settings
├── development.py   # Development with SQLite and debug tools
└── production.py    # Production with MariaDB, Redis, security headers
```

### Key Features:
- **base.py**: Shared configuration for all environments
- **production.py**: MariaDB database, Redis caching, security headers, HTTPS settings
- **development.py**: SQLite database, debug toolbar, development-friendly settings

## 🌐 Nginx Reverse Proxy

Complete Nginx configuration with:
- SSL/HTTPS support
- Rate limiting for security
- Security headers (HSTS, CSP, etc.)
- Static and media file serving
- Health check endpoint

### Configuration Files:
- `nginx/nginx.conf`: Main Nginx configuration
- `nginx/default.conf`: Site-specific configuration

## 🚀 VPS Deployment Scripts

### 1. Linode VPS Setup Script (`scripts/setup_linode_vps.sh`)

This script completely configures a fresh Linode VPS from scratch:

#### What it does:
- **System Updates**: Updates all packages and installs essential tools
- **Docker Installation**: Installs Docker and Docker Compose
- **User Management**: Creates dedicated `votebem` user with proper permissions
- **Security Hardening**: 
  - Configures UFW firewall
  - Sets up Fail2ban for intrusion prevention
  - Hardens SSH configuration
  - Disables root login
- **Directory Structure**: Creates application directories with proper permissions
- **Monitoring**: Installs system monitoring tools
- **Backup System**: Sets up automated database and media backups
- **SSL Preparation**: Creates SSL certificate directories
- **Auto-updates**: Configures unattended security updates

#### Usage:
```bash
# On your local machine, copy the script to your VPS
scp scripts/setup_linode_vps.sh root@your-vps-ip:/tmp/

# SSH into your VPS as root
ssh root@your-vps-ip

# Make the script executable and run it
chmod +x /tmp/setup_linode_vps.sh
/tmp/setup_linode_vps.sh

# Follow the prompts for:
# - Domain name
# - Email address
# - SSH public key (optional but recommended)
```

### 2. Production Deployment Script (`scripts/deploy_production.sh`)

This script handles the complete application deployment:

#### What it does:
- **Repository Management**: Clones or updates the application code
- **Environment Configuration**: Generates secure environment variables
- **SSL Setup**: Configures Let's Encrypt certificates
- **Docker Deployment**: Builds and starts all containers
- **Database Setup**: Runs migrations and creates superuser
- **Static Files**: Collects and serves static files
- **Health Checks**: Verifies deployment success
- **Helper Scripts**: Creates management scripts for ongoing operations
- **Systemd Service**: Sets up auto-start on boot

#### Usage:
```bash
# SSH into your VPS as the votebem user
ssh votebem@your-vps-ip

# Clone the repository (só vai funcionar com a chave SSH funcionando, ver acima)
git clone git@github.com:wagnercateb/votebem.git /dados/votebem
cd /dados/votebem

# Make the deployment script executable
chmod +x scripts/deploy_production.sh

# Run the deployment script
./scripts/deploy_production.sh

# Follow the prompts for:
# - Domain name
# - Email address
# - Database credentials
# - Django superuser details
```

## 🛠️ Development Tools

### Makefile Commands

The comprehensive Makefile provides easy-to-use commands for all Docker operations:

#### Development Commands:
```bash
make dev              # Start development environment
make dev-build        # Build and start development environment
make dev-down         # Stop development environment
make dev-logs         # View development logs
make dev-shell        # Access development container shell
```

#### Production Commands:
```bash
make prod             # Start production environment
make prod-build       # Build and start production environment
make prod-down        # Stop production environment
make prod-logs        # View production logs
make deploy           # Deploy to production
```

#### Database Operations:
```bash
make migrate          # Run database migrations
make makemigrations   # Create new migrations
make superuser        # Create Django superuser
make dbshell          # Access database shell
make backup           # Create database backup
make restore          # Restore database from backup
```

#### Testing & Quality:
```bash
make test             # Run tests
make coverage         # Run tests with coverage
make lint             # Run code linting
make format           # Format code with black
make check            # Run all quality checks
```

#### Utilities:
```bash
make clean            # Clean up containers and volumes
make logs             # View all logs
make status           # Show container status
make shell            # Access web container shell
make health           # Check application health
```

### Environment Configuration

Use the `.env.example` template to create your environment files:

#### For Development:
```bash
cp .env.example .env.dev
# Edit .env.dev with development settings
```

#### For Production:
```bash
cp .env.example .env
# Edit .env with production settings
```

## 🔧 Remote Debugging Setup

Both development and production environments support remote debugging:

### Port Configuration:
- **Port 5678**: Exposed for remote debugging with `debugpy`
- **Port 8000**: Django application (development)
- **Port 80/443**: Nginx reverse proxy (production)

### VS Code Configuration:

Add to your `.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Remote Attach",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5678
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "/app"
                }
            ]
        }
    ]
}
```

### PyCharm Configuration:
1. Go to Run → Edit Configurations
2. Add new Python Debug Server
3. Set Host: `localhost`, Port: `5678`
4. Set Path mappings: Local path to `/app`

## 📦 Complete Deployment Workflow

### Step 1: Prepare Your VPS

1. **Create a Linode VPS** (or any Ubuntu 20.04+ server)
2. **Copy the setup script**:
   ```bash
   scp scripts/setup_linode_vps.sh root@your-vps-ip:/tmp/
   ```
3. **Run the setup script**:
   ```bash
   ssh root@your-vps-ip
   chmod +x /tmp/setup_linode_vps.sh
   /tmp/setup_linode_vps.sh
   ```
4. **Reboot the server** when prompted

### Step 2: Deploy the Application

1. **SSH as the votebem user**:
   ```bash
   ssh votebem@your-vps-ip
   ```
2. **Clone your repository**:
   ```bash
   git clone https://github.com/yourusername/django_votebem.git
   cd django_votebem
   ```
3. **Run the deployment script**:
   ```bash
   chmod +x scripts/deploy_production.sh
   ./scripts/deploy_production.sh
   ```
4. **Follow the prompts** for domain, email, and credentials

### Step 3: Verify Deployment

1. **Check application health**:
   ```bash
   curl -f http://your-domain.com/health/
   ```
2. **View container status**:
   ```bash
   make status
   ```
3. **Check logs**:
   ```bash
   make logs
   ```

### Step 4: SSL Certificate Setup

The deployment script automatically sets up Let's Encrypt SSL certificates. If you need to renew or reconfigure:

```bash
make ssl-setup
```

## 🔒 Security Features

### Application Security:
- Non-root user execution
- Security headers (HSTS, CSP, X-Frame-Options)
- Rate limiting
- CORS configuration
- Debug mode disabled in production

### Server Security:
- UFW firewall configuration
- Fail2ban intrusion prevention
- SSH hardening
- Automatic security updates
- Regular backup system

## 📊 Monitoring and Maintenance

### Health Checks:
- Application health endpoint: `/health/`
- Database connectivity check
- Redis cache check
- Container health checks

### Backup System:
- Automated daily database backups
- Media files backup
- Log rotation
- Backup retention policy

### Monitoring Commands:
```bash
make monitor          # Complete system status
make health           # Application health check
make status           # Container status
make logs             # View recent logs
```

## 🚀 Quick Start Commands

### Local Development:
```bash
# Setup development environment
make setup-dev
make dev

# Access at http://localhost:8000
# Debug port: 5678
```

### Production Deployment:
```bash
# Local Development
make setup-dev && make dev

# Production Deployment (on VPS)
# (não sei isso já foi feito acima)
./scripts/setup_linode_vps.sh

# On VPS (after setup)
./scripts/deploy_production.sh

# Or using make commands
make setup-prod
make prod
```

## 🔧 Troubleshooting

### Common Issues:

1. **Container won't start**:
   ```bash
   make logs
   docker-compose ps
   ```

2. **Database connection issues**:
   ```bash
   make dbshell
docker-compose exec db mysql -u votebem_user -p -D votebem_db
   ```

3. **SSL certificate issues**:
   ```bash
   sudo certbot renew
   make ssl-setup
   ```

4. **Permission issues**:
   ```bash
sudo chown -R votebem:votebem /dados/votebem
   ```

### Log Locations:
- Application logs: `/var/log/votebem/`
- Nginx logs: `/var/log/nginx/`
- Docker logs: `docker-compose logs`

## 📚 Additional Resources

### File Structure:
```
django_votebem/
├── Dockerfile                 # Production container
├── Dockerfile.dev            # Development container
├── docker-compose.yml        # Production stack
├── docker-compose.dev.yml    # Development stack
├── Makefile                  # Command shortcuts
├── .env.example              # Environment template
├── DOCKER_README.md          # Docker documentation
├── DEPLOYMENT_GUIDE.md       # This file
├── nginx/                    # Nginx configuration
│   ├── nginx.conf
│   └── default.conf
├── scripts/                  # Deployment scripts
│   ├── setup_linode_vps.sh
│   └── deploy_production.sh
└── votebem/settings/         # Django settings
    ├── __init__.py
    ├── base.py
    ├── development.py
    └── production.py
```

### Environment Variables:
Refer to `.env.example` for all required environment variables including:
- Django settings (SECRET_KEY, DEBUG, ALLOWED_HOSTS)
- Database configuration (MariaDB)
- Redis configuration
- Email settings
- Security settings
- SSL/HTTPS settings
- Remote debugging settings

### Performance Optimization:
- Gunicorn with multiple workers
- Redis caching
- Static file serving via Nginx
- Database connection pooling
- Gzip compression

This setup provides a production-ready, scalable, and secure Django application deployment with comprehensive monitoring, backup, and debugging capabilities.