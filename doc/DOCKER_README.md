# VoteBem Docker Deployment Guide

This guide provides comprehensive instructions for deploying the VoteBem Django application using Docker in both development and production environments.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [VPS Setup (Linode)](#vps-setup-linode)
- [Remote Debugging](#remote-debugging)
- [Management Commands](#management-commands)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

## 🔧 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git
- 2GB+ RAM
- 10GB+ disk space

## 🚀 Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/wagnercateb/votebem.git
cd django-votebem

# Start development environment
docker-compose -f docker-compose.dev.yml up --build

# Access the application
open http://localhost:8000
```

### Production Deployment

```bash
# Clone the repository
git clone https://github.com/wagnercateb/votebem.git
cd django-votebem

# Copy and configure environment
cp .env.example .env
# Edit .env with your production settings

# Start production environment
docker-compose -f docker-compose.yml up --build -d
```

## 🛠 Development Setup

### 1. Environment Setup

```bash
# Create development environment file
cp .env.example .env.dev

# Edit .env.dev for development
DEBUG=True
DJANGO_SETTINGS_MODULE=votebem.settings.development
ENABLE_REMOTE_DEBUG=True
```

### 2. Start Development Services

```bash
# Build and start all services
docker-compose -f docker-compose.dev.yml up --build

# Or start in background
docker-compose -f docker-compose.dev.yml up --build -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

### 3. Development Commands

```bash
# Run migrations
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate --settings=votebem.settings.development

# Create superuser
docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser --settings=votebem.settings.development

# Collect static files
docker-compose -f docker-compose.dev.yml exec web python manage.py collectstatic --settings=votebem.settings.development

# Run tests
docker-compose -f docker-compose.dev.yml exec web python manage.py test --settings=votebem.settings.development

# Access Django shell
docker-compose -f docker-compose.dev.yml exec web python manage.py shell --settings=votebem.settings.development

# Access container bash
docker-compose -f docker-compose.dev.yml exec web bash
```

### 4. Code Quality Tools

```bash
# Format code with Black
docker-compose -f docker-compose.dev.yml exec web black .

# Sort imports with isort
docker-compose -f docker-compose.dev.yml exec web isort .

# Lint with flake8
docker-compose -f docker-compose.dev.yml exec web flake8 .

# Run coverage
docker-compose -f docker-compose.dev.yml exec web coverage run --source='.' manage.py test
docker-compose -f docker-compose.dev.yml exec web coverage report
```

## 🏭 Production Deployment

### 1. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Configure production settings
vim .env
```

### Environment Configuration (.env) — Production

The production stack reads environment from `/dados/votebem/.env` on the server. The `.env` at the repository root is for local development only.

Set these keys and keep credentials stable across deploys:

```env
# Core
DJANGO_SECRET_KEY=keep-existing-generated-once
DEBUG=False
USE_HTTPS=True

# Domain and proxy
BASE_URL=https://votebem.online
ALLOWED_HOSTS=votebem.online,www.votebem.online
CSRF_TRUSTED_ORIGINS=https://votebem.online,http://votebem.online,https://www.votebem.online,http://www.votebem.online
CORS_ALLOWED_ORIGINS=https://votebem.online,http://votebem.online,https://www.votebem.online,http://www.votebem.online
USE_X_FORWARDED_HOST=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https

# Database
DB_NAME=votebem_db
DB_USER=votebem_user
DB_PASSWORD=your-secure-password
DB_HOST=db
DB_PORT=3306

# Redis
REDIS_PASSWORD=your-redis-password

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

Rules and tips:
- `ALLOWED_HOSTS` does not include scheme; domains only.
- `CSRF_TRUSTED_ORIGINS` and `CORS_ALLOWED_ORIGINS` must include scheme; add both `https://` and `http://` for the domain and `www` subdomain.
- Keep `DJANGO_SECRET_KEY`, `DB_*`, and `REDIS_PASSWORD` consistent between runs; changing `DB_PASSWORD` after MariaDB is initialized requires updating the DB user or resetting the data directory.
- After deployment, verify config: `docker-compose -f docker-compose.yml exec -T web python manage.py check --deploy`.

### 2. Deploy Application

```bash
# Build and start production services
docker-compose up --build -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Run initial setup
docker-compose exec web python manage.py migrate --settings=votebem.settings.production
docker-compose exec web python manage.py collectstatic --noinput --settings=votebem.settings.production
docker-compose exec web python manage.py createsuperuser --settings=votebem.settings.production
```

### 3. SSL Configuration

```bash
# Install Certbot (on host)
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Copy certificates to Docker volume
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./ssl/key.pem

# Restart nginx
docker-compose restart nginx
```

## 🖥 VPS Setup (Linode)

### Automated Setup

```bash
# Run the VPS setup script (as root)
curl -sSL https://raw.githubusercontent.com/wagnercateb/django-votebem/main/scripts/setup_linode_vps.sh | bash

# Switch to votebem user
sudo su - votebem

# Run deployment script
./scripts/deploy_production.sh
```

### Manual Setup

1. **Create Linode Instance**
   - Ubuntu 22.04 LTS
   - 2GB RAM minimum
   - 25GB storage minimum

2. **Initial Server Setup**
   ```bash
   # Update system
   apt update && apt upgrade -y
   
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   
   # Install Docker Compose
   curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   chmod +x /usr/local/bin/docker-compose
   
   # Create application user
   useradd -m -s /bin/bash votebem
   usermod -aG docker votebem
   usermod -aG sudo votebem
   ```

3. **Security Configuration**
   ```bash
   # Configure firewall
   ufw allow ssh
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw --force enable
   
   # Configure fail2ban
   apt install fail2ban
   systemctl enable fail2ban
   ```

## 🐛 Remote Debugging

### VS Code Setup

1. **Install Python Extension**
   - Install "Python" extension by Microsoft
   - Install "Remote - Containers" extension

2. **Configure Launch Configuration**
   
   Create `.vscode/launch.json`:
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
               ],
               "justMyCode": false
           }
       ]
   }
   ```

3. **Start Debugging**
   ```bash
   # Start development environment with debugging
   docker-compose -f docker-compose.dev.yml up
   
   # In VS Code, press F5 or go to Run > Start Debugging
   ```

### PyCharm Setup

1. **Configure Remote Interpreter**
   - Go to Settings > Project > Python Interpreter
   - Add > Docker Compose
   - Select `docker-compose.dev.yml` and `web` service

2. **Configure Debug Server**
   - Go to Run > Edit Configurations
   - Add > Python Debug Server
   - Set host to `0.0.0.0` and port to `5678`

## 📊 Management Commands

### Application Management

```bash
# Start application
./start.sh

# Stop application
./stop.sh

# Restart application
./restart.sh

# Update application
./update.sh

# View logs
./logs.sh

# Check status
./status.sh
```

### Database Management

```bash
# Create database backup
docker-compose exec db mysqldump -u votebem_user -p votebem_db | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Restore database backup
gunzip -c backup_file.sql.gz | docker-compose exec -T db mysql -u votebem_user -p votebem_db

# Access database shell
docker-compose exec db mysql -u votebem_user -p votebem_db
```

### Container Management

```bash
# View container status
docker-compose ps

# View container logs
docker-compose logs [service_name]

# Execute command in container
docker-compose exec [service_name] [command]

# Rebuild specific service
docker-compose build [service_name]

# Scale service
docker-compose up --scale web=3
```

## 📈 Monitoring & Maintenance

### Health Checks

```bash
# Application health
curl http://localhost/health/

# Container health
docker-compose ps

# System resources
docker stats
```

### Log Management

```bash
# View application logs
tail -f logs/django.log

# View nginx logs
docker-compose logs nginx

# View database logs
docker-compose logs db

# Clear logs
truncate -s 0 logs/*.log
```

### Backup Strategy

```bash
# Automated backup script (runs daily)
#!/bin/bash
BACKUP_DIR="/var/backups/votebem"
DATE=$(date +%Y%m%d_%H%M%S)

# Database backup
docker-compose exec -T db mysqldump -u votebem_user -p votebem_db | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Media files backup
tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" media/

# Remove old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete
```

### Performance Optimization

```bash
# Monitor resource usage
docker stats --no-stream

# Optimize database
docker-compose exec db mysql -u votebem_user -p votebem_db -e "OPTIMIZE TABLE;"

# Clear cache
docker-compose exec web python manage.py clear_cache --settings=votebem.settings.production

# Restart services
docker-compose restart
```

## 🔧 Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check logs
docker-compose logs [service_name]

# Check container status
docker-compose ps

# Rebuild container
docker-compose build --no-cache [service_name]
```

#### Database Connection Issues
```bash
# Check database status
docker-compose exec db sh -lc "mysqladmin ping -h localhost -u$MYSQL_USER -p$MYSQL_PASSWORD"

# Reset database
docker-compose down -v
docker-compose up -d db
docker-compose exec web python manage.py migrate --settings=votebem.settings.production
```

#### Permission Issues
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
sudo chmod -R 755 .

# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker
```

#### SSL Certificate Issues
```bash
# Renew certificate
sudo certbot renew

# Copy new certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/*.pem ./ssl/

# Restart nginx
docker-compose restart nginx
```

### Debug Mode

```bash
# Enable debug mode
echo "DEBUG=True" >> .env
docker-compose restart web

# View detailed error logs
docker-compose logs web

# Access Django shell for debugging
docker-compose exec web python manage.py shell --settings=votebem.settings.production
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Increase worker processes
# Edit docker-compose.yml:
# command: gunicorn --workers 4 ...

# Add more memory
# Edit docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       memory: 1G
```

## 📞 Support

For additional support:

- **Documentation**: Check this README and inline code comments
- **Issues**: Create an issue on GitHub
- **Logs**: Always include relevant logs when reporting issues
- **Health Check**: Use `/health/` endpoint to verify application status

## 🔐 Security Considerations

- Change all default passwords
- Use strong SECRET_KEY
- Enable HTTPS in production
- Keep Docker images updated
- Regular security updates
- Monitor access logs
- Use fail2ban for intrusion prevention
- Regular backups

---

**Note**: This guide assumes Ubuntu/Debian-based systems. Adjust commands for other distributions as needed.