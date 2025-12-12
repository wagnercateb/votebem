# VoteBem - Quick Development Start Guide

## 🚀 Local Development Setup

### Quick Start (Recommended)
```bash
# Start local development server (no Docker needed)
.\startup_dev.bat
```

This script will:
- ✅ Activate the virtual environment
- ✅ Set DEBUG=True automatically
- ✅ Use SQLite database (no Docker required)
- ✅ Enable Django Debug Toolbar
- ✅ Run system checks
- ✅ Start development server with auto-reload

### Development Features Enabled

#### 🐛 Debug Mode
- **DEBUG=True** - Detailed error pages with stack traces
- **Django Debug Toolbar** - SQL queries, performance metrics, template context
- **Auto-reload** - Server restarts automatically when code changes

#### 📧 Email Testing
- **Console Email Backend** - All emails appear in the terminal
- No need to configure SMTP for development

#### 🗄️ Database
- **SQLite** by default - No Docker setup required
- Database file: `db.sqlite3` (easy to delete/reset)
- Can switch to MariaDB later if needed

#### 🔧 Development Tools
- **Django Extensions** - Additional management commands
- **Detailed Logging** - SQL queries logged to console
- **Internal IPs** configured for debug toolbar

### Available URLs
- **Main Application**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **Debug Toolbar**: Appears on all pages when DEBUG=True

### Development Workflow

1. **Start Development**:
   ```bash
   .\startup_dev.bat
   ```

2. **Create Superuser** (if needed):
   ```bash
   python manage.py createsuperuser
   ```

3. **Run Migrations** (if needed):
   ```bash
   python manage.py migrate
   ```

4. **Run Tests**:
   ```bash
   python manage.py test
   ```

5. **Stop Server**: Press `Ctrl+C` in the terminal

### Environment Configuration

The development environment uses these settings:
- **Settings Module**: `votebem.settings.production`
- **DEBUG**: `True`
- **Database**: SQLite (fallback to MariaDB if Docker available)
- **Cache**: Local memory cache
- **Email**: Console backend
- **Static Files**: Served by Django development server

### Debugging Tips

1. **Django Debug Toolbar**: 
   - Appears as a sidebar on web pages
   - Shows SQL queries, template context, performance metrics

2. **Console Logging**:
   - SQL queries are logged to the terminal
   - Email content appears in the terminal

3. **Error Pages**:
   - Detailed stack traces with local variables
   - Template error highlighting

4. **Database Inspection**:
   - SQLite database can be opened with any SQLite browser
   - Easy to reset: just delete `db.sqlite3`

### Alternative Startup Methods

If you prefer manual control:

```bash
# Activate virtual environment
.venv\Scripts\activate.bat

# Set environment variables
set DJANGO_SETTINGS_MODULE=votebem.settings.production
set DEBUG=True

# Start server
python manage.py runserver 127.0.0.1:8000
```

### Docker-based Development (Optional)

If you want to use MariaDB and Redis:

```bash
# Start with Docker services
.\startup.bat
```

This will start:
- MariaDB database
- Redis cache
- Adminer (database UI)
- Redis Commander (cache UI)

### Troubleshooting

1. **Virtual Environment Issues**:
   ```bash
   # Recreate virtual environment
   .\setup.bat
   ```

2. **Database Issues**:
   ```bash
   # Reset SQLite database
   del db.sqlite3
   python manage.py migrate
   ```

3. **Port Already in Use**:
   ```bash
   # Use different port
   python manage.py runserver 127.0.0.1:8001
   ```

4. **Package Issues**:
   ```bash
   # Reinstall requirements
   pip install -r requirements.txt
   ```

---

**Happy Coding! 🎉**

For more detailed information, check the `doc/` folder for comprehensive guides.