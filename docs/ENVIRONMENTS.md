# Docker Compose Environments

This document explains the differences between the three Docker Compose files in this project and their intended use cases.

## 1. **docker-compose.yml** (Production)
**Purpose**: Production deployment with full application stack

**Key Features**:
- **Environment**: Production settings (`DEBUG=False`)
- **Django Settings**: `votebem.settings.production`
- **Database**: `votebem_db` (production database)
- **Web Server**: Uses **Gunicorn** with 3 workers for production
- **Nginx**: Full reverse proxy setup with SSL support
- **Security**: Production-grade secret keys and configurations
- **Volumes**: Includes backup directory mapping
- **Services**: db, redis, web (Django), nginx

**Usage**:
```bash
docker-compose up -d
```

## 2. **docker-compose.dev.yml** (Development)
**Purpose**: Development environment for coding and testing

**Key Features**:
- **Environment**: Development settings (`DEBUG=True`)
- **Django Settings**: `votebem.settings.development`
- **Database**: `votebem_dev` (separate dev database)
- **Web Server**: Uses Django's **development server** (`runserver`)
- **Code Mounting**: Maps local code directory (`.:/app`) for live editing
- **Debug Support**: Includes remote debugging port (5678)
- **Dockerfile**: Uses `Dockerfile.dev` for development-specific build
- **Services**: db, redis, web (Django only - no nginx)

**Usage**:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

## 3. **docker-compose.dev-services.yml** (Development Services Only)
**Purpose**: Provides only the supporting services for local development

**Key Features**:
- **No Django Web Container**: Only infrastructure services
- **Database Management**: Includes **Adminer** (port 8080) for database administration
- **Redis Management**: Includes **Redis Commander** (port 8081) for Redis monitoring
- **Nginx**: Optional reverse proxy for testing production-like setup
- **Network**: Dedicated development network
- **Services**: db, redis, nginx, Adminer, Redis Commander
- **Use Case**: When you want to run Django locally but use containerized databases

**Usage**:
```bash
docker-compose -f docker-compose.dev-services.yml up -d
# Then run Django locally with: python manage.py runserver
```

## Summary Table

| Feature | Production | Development | Services Only |
|---------|------------|-------------|---------------|
| **Django App** | ✅ (Gunicorn) | ✅ (Dev Server) | ❌ (Run locally) |
| **Database** | MariaDB | MariaDB | MariaDB |
| **Redis** | ✅ | ✅ | ✅ |
| **Nginx** | ✅ (Full config) | ❌ | ✅ (Optional) |
| **Adminer** | ❌ | ❌ | ✅ |
| **Redis Commander** | ❌ | ❌ | ✅ |
| **Debug Mode** | ❌ | ✅ | N/A |
| **Code Mounting** | ❌ | ✅ | N/A |
| **SSL Support** | ✅ | ❌ | ❌ |

## Service Ports

### Production (docker-compose.yml)
- **Web Application**: 8000
- **Database**: 3306
- **Redis**: 6379
- **Nginx**: 80, 443
- **Debug Port**: 5678

### Development (docker-compose.dev.yml)
- **Web Application**: 8000
- **Database**: 3306
- **Redis**: 6379
- **Debug Port**: 5678

### Services Only (docker-compose.dev-services.yml)
- **Database**: 3306
- **Redis**: 6379
- **Adminer**: 8080
- **Redis Commander**: 8081
- **Nginx**: 80, 443

## Current Setup

Based on the running containers, the project is currently using **docker-compose.dev-services.yml**, which provides:
- MariaDB database (`votebem_db_dev`)
- Redis cache (`votebem_redis_dev`)
- Adminer for database management (http://localhost:8080)
- Redis Commander for Redis monitoring (http://localhost:8081)
- Nginx reverse proxy

The Django application is running locally (not in a container), accessible at `http://localhost:8000`.

## Database Information

- **Database Type**: MariaDB (running in Docker container)
- **Database Name**: `votebem_dev`
- **Container**: `votebem_db_dev` (mariadb:11)
- **Host**: localhost
- **Port**: 3306
- **Data Storage**: Inside Docker container's persistent volume

## Switching Between Environments

To switch between different environments:

1. **Stop current containers**:
   ```bash
   docker-compose down
   ```

2. **Start desired environment**:
   ```bash
   # For production
   docker-compose up -d
   
   # For development
   docker-compose -f docker-compose.dev.yml up -d
   
   # For services only
   docker-compose -f docker-compose.dev-services.yml up -d
   ```

## Development Workflow

The recommended development workflow is:

1. Use `docker-compose.dev-services.yml` for infrastructure services
2. Run Django locally for faster development and debugging
3. Access database via Adminer at http://localhost:8080
4. Monitor Redis via Redis Commander at http://localhost:8081
5. Test production-like setup occasionally with `docker-compose.yml`