# Development Scripts for Windows

This directory contains batch scripts to simplify development on Windows 11.

## Scripts Overview

### `setup.bat` - Initial Setup
**Run this ONCE when setting up the project for the first time.**

What it does:
- Creates Python virtual environment
- Installs all Python dependencies
- Starts Docker services (PostgreSQL, Redis, etc.)
- Runs Django migrations
- Collects static files

### `startup.bat` - Daily Development
**Run this EVERY TIME you want to start developing.**

What it does:
- Starts Docker services
- Activates Python virtual environment
- Starts Django development server on http://localhost:8000

### `stop.bat` - Clean Shutdown
**Run this to stop all services cleanly.**

What it does:
- Stops all Docker containers
- Shows status of stopped services

## Quick Start

1. **First time setup:**
   ```cmd
   setup.bat
   ```

2. **Daily development:**
   ```cmd
   startup.bat
   ```

3. **When done developing:**
   ```cmd
   stop.bat
   ```

## Available Services

After running `startup.bat`, these services will be available:

- **Django App**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **pgAdmin (Database UI)**: http://localhost:8080
  - Email: admin@votebem.dev
  - Password: admin123
- **Redis Commander**: http://localhost:8081

## Troubleshooting

### "Docker is not running"
- Start Docker Desktop
- Wait for it to fully load
- Try again

### "Virtual environment not found"
- Run `setup.bat` first
- Make sure it completed without errors

### "Port already in use"
- Check if another application is using ports 8000, 5432, 6379, 8080, or 8081
- Stop conflicting applications or change ports in configuration

### Database connection errors
- Ensure PostgreSQL container is running: `docker ps`
- Check if port 5432 is available
- Verify database credentials in `.env.dev`

## Manual Commands

If you prefer to run commands manually:

```cmd
# Start services
docker-compose -f docker-compose.dev-services.yml up -d

# Activate virtual environment
.venv\Scripts\activate

# Start Django
python manage.py runserver 0.0.0.0:8000

# Stop services
docker-compose -f docker-compose.dev-services.yml down
```