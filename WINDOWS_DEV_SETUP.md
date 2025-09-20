# VoteBem Django Application - Windows 11 Development Setup

This guide will help you set up the VoteBem Django application for development on Windows 11. The main Django application will run natively on Windows, while auxiliary services (PostgreSQL, Redis, Nginx) will run in Docker containers.

## Prerequisites

Before starting, ensure you have the following installed:

1. **Python 3.11+** - Download from [python.org](https://www.python.org/downloads/)
2. **Docker Desktop** - Download from [docker.com](https://www.docker.com/products/docker-desktop/)
3. **Git** - Download from [git-scm.com](https://git-scm.com/download/win)

## Quick Setup (Automated)

For a quick setup, simply run the provided batch scripts:

1. **First-time setup**: Run `setup.bat` (this will install dependencies and configure the environment)
2. **Start the application**: Run `startup.bat` (this will start all services and the Django app)

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
```

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

# Database Configuration (PostgreSQL in Docker)
DB_NAME=votebem_dev
DB_USER=votebem_user
DB_PASSWORD=votebem_dev_password
DB_HOST=localhost
DB_PORT=5432

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

Start PostgreSQL and Redis using Docker Compose:

```cmd
docker-compose -f docker-compose.dev-services.yml up -d
```

### Step 6: Initialize Database

Run Django migrations to set up the database:

```cmd
python manage.py migrate
```

### Step 7: Create Superuser (Optional)

```cmd
python manage.py createsuperuser
```

### Step 8: Collect Static Files

```cmd
python manage.py collectstatic --noinput
```

### Step 9: Start Django Development Server

```cmd
python manage.py runserver 0.0.0.0:8000
```

## Accessing the Application

- **Main Application**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## Development Workflow

### Starting the Application Daily

1. Ensure Docker Desktop is running
2. Run `startup.bat` or manually:
   ```cmd
   docker-compose -f docker-compose.dev-services.yml up -d
   .venv\Scripts\activate
   python manage.py runserver 0.0.0.0:8000
   ```

### Stopping the Application

1. Stop Django server: `Ctrl+C`
2. Stop Docker services:
   ```cmd
   docker-compose -f docker-compose.dev-services.yml down
   ```

### Database Management

- **View database**: Use pgAdmin or any PostgreSQL client connecting to `localhost:5432`
- **Reset database**: 
  ```cmd
  docker-compose -f docker-compose.dev-services.yml down -v
  docker-compose -f docker-compose.dev-services.yml up -d
  python manage.py migrate
  ```

### Making Code Changes

- Django will automatically reload when you make changes to Python files
- For template changes, refresh your browser
- For static file changes, you may need to run `python manage.py collectstatic`

## Troubleshooting

### Common Issues

1. **Port already in use**: 
   - Check if another application is using ports 8000, 5432, or 6379
   - Stop conflicting services or change ports in configuration

2. **Docker not starting**:
   - Ensure Docker Desktop is running
   - Check Docker Desktop settings and restart if necessary

3. **Database connection errors**:
   - Verify PostgreSQL container is running: `docker ps`
   - Check database credentials in `.env.dev`

4. **Python module not found**:
   - Ensure virtual environment is activated: `.venv\Scripts\activate`
   - Reinstall requirements: `pip install -r requirements.txt`

### Useful Commands

```cmd
# Check running Docker containers
docker ps

# View Django logs
python manage.py runserver --verbosity=2

# Check database connection
python manage.py dbshell

# Run tests
python manage.py test

# Create new Django app
python manage.py startapp <app_name>

# Make migrations after model changes
python manage.py makemigrations
python manage.py migrate
```

## File Structure

```
django_votebem/
├── setup.bat                 # Automated setup script
├── startup.bat               # Automated startup script
├── .env.dev                  # Development environment variables
├── docker-compose.dev-services.yml  # Docker services only
├── manage.py                 # Django management script
├── requirements.txt          # Python dependencies
├── votebem/                  # Main Django project
├── polls/                    # Polls application
├── users/                    # Users application
├── voting/                   # Voting application
└── templates/                # HTML templates
```

## Next Steps

1. Explore the codebase in your favorite IDE (VS Code recommended)
2. Check out the existing apps: `polls`, `users`, `voting`
3. Review the admin interface at http://localhost:8000/admin
4. Start developing new features!

For production deployment, refer to `DEPLOYMENT_GUIDE.md`.