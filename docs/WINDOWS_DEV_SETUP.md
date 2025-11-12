# VoteBem Django Application - Windows 11 Development Setup

This guide will help you set up the VoteBem Django application for development on Windows 11. The main Django application will run natively on Windows, while auxiliary services (MariaDB, Redis, Nginx) will run in Docker containers.

## Prerequisites

Before starting, ensure you have the following installed:

1. **Python 3.11+** - Download from [python.org](https://www.python.org/downloads/)
2. **Docker Desktop** - Download from [docker.com](https://www.docker.com/products/docker-desktop/)
3. **Git** - Download from [git-scm.com](https://git-scm.com/download/win)
4. **DBeaver (Optional)** - Download from [dbeaver.io](https://dbeaver.io/download/) for database management

## Quick Setup (Automated)

For a quick setup, simply run the provided batch scripts:

1. **First-time setup**: Run `setup.bat` (this will install dependencies and configure the environment)
2. **Start the application**: Run `startup.bat` (this will start all services and the Django app)

## Alternative Quick Start (Using Custom Scripts)

If the batch scripts don't work, you can use the Python-based startup scripts:

1. **Start Docker services**: `docker-compose -f docker-compose.dev-services.yml up -d`
2. **Run migrations**: `python run_migrations.py`
3. **Start Django server**: `python run_server.py`

## Manual Setup Instructions

If you prefer to set up manually or need to troubleshoot:

### Step 1: Clone and Navigate to Project

```cmd
git clone <your-repo-url>
cd VotoBomPython\django_votebem
```

### Step 2: Create Python Virtual Environment

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### Step 3: Install Python Dependencies

```cmd
pip install -r requirements.txt
pip install python-decouple django-redis
```

**Note**: The application now prefers MariaDB instead of SQLite and requires additional packages for environment variable management and Redis caching.

### Step 4: Create Environment Configuration

Copy the example environment file and configure it:

```cmd
copy .env.example .env.dev
```

Edit `.env.dev` with the following development settings:

```env
# Django Settings
DJANGO_SETTINGS_MODULE=votebem.settings.development
DEBUG=True
SECRET_KEY=dev-secret-key-change-this

# Allowed Hosts
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration (MariaDB in Docker)
DB_NAME=votebem_dev
DB_USER=votebem_user
DB_PASSWORD=votebem_dev_password
DB_HOST=localhost
DB_PORT=3306

# Redis Configuration (Redis in Docker)
REDIS_URL=redis://localhost:6379/0

# Email Configuration (Console backend for development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Security Settings
USE_HTTPS=False

# Remote Debugging
ENABLE_REMOTE_DEBUG=True

# Social Authentication (Optional - leave empty for basic setup)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
```

### Step 5: Start Auxiliary Services (Docker)

Start MariaDB and Redis using Docker Compose:

```cmd
docker-compose -f docker-compose.dev-services.yml up -d
```

### Step 6: Initialize Database

Run Django migrations to set up the MariaDB database. You can use either method:

**Method 1 (Recommended)**: Using the migration script
```cmd
python run_migrations.py
```

**Method 2**: Manual migration with environment variables
```cmd
.venv\Scripts\activate
python manage.py migrate --settings=votebem.settings.development
```

### Step 7: Create Superuser (Optional)

```cmd
python manage.py createsuperuser --settings=votebem.settings.development
```

### Step 8: Collect Static Files

```cmd
python manage.py collectstatic --noinput --settings=votebem.settings.development
```

### Step 9: Start Django Development Server

You can use either method:

**Method 1 (Recommended)**: Using the server script
```cmd
python run_server.py
```

**Method 2**: Manual server start
```cmd
.venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000 --settings=votebem.settings.development
```

## Accessing the Application

- **Main Application**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **MariaDB**: localhost:3306
- **Redis**: localhost:6379

## Database Access with DBeaver

DBeaver is a powerful database management tool that supports both MariaDB and Redis connections.

### Setting up MariaDB Connection in DBeaver

1. **Open DBeaver** and click "New Database Connection"
2. **Select MySQL/MariaDB** from the database list
3. **Configure connection settings**:
   - **Host**: `localhost`
- **Port**: `3306`
   - **Database**: `votebem_dev`
   - **Username**: `votebem_user`
   - **Password**: `votebem_dev_password`
4. **Test Connection** to verify settings
5. **Click Finish** to save the connection

### Using Adminer (DB UI in Docker)

Adminer runs inside Docker and connects to the MariaDB service. You can also get helper instructions via:

```cmd
python config_mariadb_admin.py
```

Quick Adminer access and login details:

- **Open Adminer** at http://localhost:8080
- **System**: MySQL
- **Server**: `db` (Docker service name)
- **Username**: `votebem_user`
- **Password**: `votebem_dev_password`
- **Database**: `votebem_dev`

### Setting up Redis Connection in DBeaver

1. **Open DBeaver** and click "New Database Connection"
2. **Select Redis** from the NoSQL section
3. **Configure connection settings**:
   - **Host**: `localhost`
   - **Port**: `6379`
   - **Database**: `0` (default Redis database)
   - **Password**: Leave empty (no password configured)
4. **Test Connection** to verify settings
5. **Click Finish** to save the connection

### Using DBeaver for Database Management

**MariaDB Operations**:
- View all tables and their structure
- Execute SQL queries
- Browse table data
- Export/import data
- Monitor database performance

**Redis Operations**:
- View all keys and their values
- Monitor Redis memory usage
- Execute Redis commands
- Browse different Redis databases (0-15)

### Alternative Database Tools

If you prefer other tools:

**For MariaDB**:
- **Adminer**: Web-based MariaDB administration (included in Docker setup)
- **TablePlus**: Modern database management tool
- **DataGrip**: JetBrains database IDE

**For Redis**:
- **Redis Commander**: Web-based Redis management (included in Docker setup)
- **RedisInsight**: Official Redis GUI tool
- **Redis Desktop Manager**: Cross-platform Redis GUI

## Development Workflow

### Starting the Application Daily

1. **Ensure Docker Desktop is running**
2. **Choose one of these startup methods**:

   **Option A**: Using batch script
   ```cmd
   startup.bat
   ```

   **Option B**: Using Python scripts (recommended)
   ```cmd
   docker-compose -f docker-compose.dev-services.yml up -d
   python run_server.py
   ```

   **Option C**: Manual startup
   ```cmd
   docker-compose -f docker-compose.dev-services.yml up -d
   .venv\Scripts\activate
   python manage.py runserver 0.0.0.0:8000 --settings=votebem.settings.development
   ```

### Stopping the Application

1. **Stop Django server**: `Ctrl+C` (in the terminal running the server)
2. **Stop Docker services**:
   ```cmd
   docker-compose -f docker-compose.dev-services.yml down
   ```

### Restarting After Code Changes

- **Python/Django code**: Server auto-reloads, no restart needed
- **Environment variables**: Restart Django server (`Ctrl+C` then `python run_server.py`)
- **Database schema changes**: Run migrations first, then restart
- **Docker services**: Only restart if Docker configuration changed

### Database Management

- **View database**: Use Adminer or any MariaDB client connecting to `localhost:3306`
- **Reset database**: 
  ```cmd
  docker-compose -f docker-compose.dev-services.yml down -v
  docker-compose -f docker-compose.dev-services.yml up -d
  python manage.py migrate --settings=votebem.settings.development
  ```

### Making Code Changes

- Django will automatically reload when you make changes to Python files
- For template changes, refresh your browser
- For static file changes, you may need to run `python manage.py collectstatic --settings=votebem.settings.development`

## Troubleshooting

### Common Issues

1. **Port already in use**: 
   - Check if another application is using ports 8000, 3306, or 6379
   - Stop conflicting services or change ports in configuration
   - Use `netstat -ano | findstr :8000` to find processes using port 8000

2. **Docker not starting**:
   - Ensure Docker Desktop is running and fully started
   - Check Docker Desktop settings and restart if necessary
   - Verify Docker services are healthy: `docker-compose -f docker-compose.dev-services.yml ps`

3. **Database connection errors**:
   - Verify MariaDB container is running: `docker ps`
   - Check database credentials in `.env.dev` match Docker configuration
   - Ensure MariaDB container is healthy: `docker logs <mariadb_container_name>`
   - Try connecting manually: `docker exec -it <mariadb_container> mysql -u votebem_user -p -D votebem_dev`

4. **Python module not found**:
   - Ensure virtual environment is activated: `.venv\Scripts\activate`
   - Reinstall requirements: `pip install -r requirements.txt`
   - Install missing packages: `pip install python-decouple django-redis`

5. **Environment variable issues**:
   - Verify `.env.dev` file exists and has correct values
   - Check if `python-decouple` is installed: `pip show python-decouple`
   - Use `run_server.py` script which handles environment loading automatically

6. **Migration errors**:
   - Ensure MariaDB is running before migrations
   - Use `python run_migrations.py` for automatic environment setup
   - Clear migration history if needed: `docker-compose -f docker-compose.dev-services.yml down -v`

7. **Redis connection issues**:
   - Verify Redis container is running: `docker ps | grep redis`
   - Test Redis connection: `docker exec -it <redis_container> redis-cli ping`
   - Check Redis URL in `.env.dev`: should be `redis://localhost:6379/0`

8. **Static files not loading**:
   - Run `python manage.py collectstatic --noinput --settings=votebem.settings.development`
   - Check if `static/` directory exists
   - Verify `STATIC_ROOT` and `STATICFILES_DIRS` in settings

9. **Permission errors on Windows**:
   - Run terminal as Administrator if needed
   - Check file permissions in project directory
   - Ensure Docker Desktop has proper permissions

### Useful Commands

```cmd
# Check running Docker containers
docker ps

# Check Docker services status
docker-compose -f docker-compose.dev-services.yml ps

# View Docker service logs
docker-compose -f docker-compose.dev-services.yml logs

# Start Django server with environment loading
python run_server.py

# Run migrations with environment loading
python run_migrations.py

# Get Adminer connection info
python config_mariadb_admin.py

# View Django logs with verbosity
python manage.py runserver --verbosity=2 --settings=votebem.settings.development

# Check database connection (MariaDB)
python manage.py dbshell --settings=votebem.settings.development

# Connect to MariaDB directly
docker exec -it <mariadb_container> mysql -u votebem_user -p -D votebem_dev

# Connect to Redis directly
docker exec -it <redis_container> redis-cli

# Run tests
python manage.py test --settings=votebem.settings.development

# Create new Django app
python manage.py startapp <app_name> --settings=votebem.settings.development

# Make migrations after model changes
python manage.py makemigrations --settings=votebem.settings.development
python manage.py migrate --settings=votebem.settings.development

# Collect static files
python manage.py collectstatic --noinput --settings=votebem.settings.development

# Create superuser
python manage.py createsuperuser --settings=votebem.settings.development

# Check installed packages
pip list

# Check environment variables (in Python shell)
python -c "from decouple import Config, RepositoryEnv; config = Config(RepositoryEnv('.env.dev')); print(config('DB_NAME'))"

# Reset database (WARNING: destroys all data)
docker-compose -f docker-compose.dev-services.yml down -v
docker-compose -f docker-compose.dev-services.yml up -d
python run_migrations.py
```

## File Structure

```
django_votebem/
├── setup.bat                 # Automated setup script
├── startup.bat               # Automated startup script
├── stop.bat                  # Stop services script
├── troubleshoot.bat          # Troubleshooting script
├── .env.dev                  # Development environment variables
├── .env.example              # Environment variables template
├── docker-compose.dev-services.yml  # Docker services only
├── docker-compose.dev.yml    # Full development stack
├── docker-compose.yml        # Production stack
├── manage.py                 # Django management script
├── run_migrations.py         # Custom migration script with env loading
├── run_server.py             # Custom server startup script with env loading
├── requirements.txt          # Python dependencies
├── requirements-minimal.txt  # Minimal dependencies
├── Dockerfile                # Production Docker image
├── Dockerfile.dev            # Development Docker image
├── Makefile                  # Build automation commands
├── votebem/                  # Main Django project
│   ├── settings/             # Settings modules
│   │   ├── base.py           # Base settings
│   │   ├── development.py    # Development settings (MariaDB + Redis)
│   │   └── production.py     # Production settings
│   ├── urls.py               # URL routing
│   └── wsgi.py               # WSGI application
├── home/                     # Home page application
├── polls/                    # Polls application
├── users/                    # Users application
├── voting/                   # Voting application
├── templates/                # HTML templates
├── static/                   # Static files (CSS, JS, images)
├── nginx/                    # Nginx configuration files
├── scripts/                  # Deployment and setup scripts
└── doc/                      # Documentation
    ├── WINDOWS_DEV_SETUP.md  # This file
    ├── DEPLOYMENT_GUIDE.md   # Production deployment guide
    ├── DOCKER_README.md      # Docker-specific documentation
    └── SOCIAL_AUTH_GUIDE.md  # Social authentication setup
```

## Next Steps

1. Explore the codebase in your favorite IDE (VS Code recommended)
2. Check out the existing apps: `polls`, `users`, `voting`
3. Review the admin interface at http://localhost:8000/admin
4. Start developing new features!

For production deployment, refer to `DEPLOYMENT_GUIDE.md`.

## Windows Development Scripts (.bat)

These batch files automate common development tasks. Use them from the project root or from the `scripts` folder.

- `setup.bat`
  - Purpose: First-time setup (create venv, upgrade pip, install dependencies)
  - Usage: `.\scripts\setup.bat` (from project root) or `.\setup.bat` (inside scripts)
- `startup.bat`
- Purpose: Start daily development with Docker services (MariaDB, Redis) and app
  - Usage: `.\scripts\startup.bat` or `.\startup.bat`
- `startup_dev.bat`
  - Purpose: Start pure local development (SQLite), enable DEBUG tooling
  - Usage: `.\scripts\startup_dev.bat` or `.\startup_dev.bat`
- `stop.bat`
  - Purpose: Cleanly stop Docker Compose services
  - Usage: `.\scripts\stop.bat` or `.\stop.bat`
- `troubleshoot.bat`
  - Purpose: Diagnose common issues (Python install, venv status, Django, Docker availability)
  - Usage: `.\scripts\troubleshoot.bat` or `.\troubleshoot.bat`