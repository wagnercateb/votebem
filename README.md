# VoteBem Project

A comprehensive voting system implementation with both PHP (legacy) and Django (modern) versions.

## 📁 Project Structure

This repository contains multiple implementations of the VoteBem voting system:

### Root Directory Files & Folders

#### 📂 **Folders**

##### `.venv/`
- **Description**: Python virtual environment for the Django project
- **Use Case**: Isolated Python environment containing all project dependencies
- **Contents**: Python interpreter, pip packages, activation scripts
- **Note**: Auto-generated folder, should not be committed to version control

##### `.vscode/`
- **Description**: Visual Studio Code workspace configuration
- **Use Case**: IDE-specific settings, debugging configurations, and extensions
- **Contents**: 
  - `launch.json` - Debug configurations
  - `settings.json` - Workspace-specific settings
- **Note**: Helps maintain consistent development environment across team

##### `00_VB_php/`
- **Description**: Legacy PHP implementation of VoteBem
- **Use Case**: Original CodeIgniter-based voting system
- **Contents**: Complete PHP web application with MVC structure
- **Key Features**:
  - CodeIgniter framework
  - Admin panel
  - User voting interface
  - SSO (Single Sign-On) integration
  - Database models and controllers
- **Status**: Legacy system, maintained for reference

##### `django_votebem/`
- **Description**: Modern Django implementation of VoteBem
- **Use Case**: Current active development - Python/Django voting system
- **Contents**: Complete Django web application
- **Key Features**:
  - Django 4.2+ framework
  - Docker containerization
  - MariaDB database
  - Redis caching
  - Nginx reverse proxy
  - User authentication
  - Admin interface
  - Voting modules
- **Status**: Active development

---

## 🚀 Django VoteBem (Main Project)

### Core Application Files

#### **Configuration Files**

##### `.env.example`
- **Description**: Environment variables template
- **Use Case**: Configuration template for different environments (dev/prod)
- **Contains**: Database settings, Django secret key, email config, Redis settings
- **Usage**: Copy to `.env` and customize for your environment

##### `.gitignore`
- **Description**: Git ignore rules
- **Use Case**: Prevents sensitive/unnecessary files from being committed
- **Excludes**: Virtual environments, database files, logs, cache, secrets

##### `requirements.txt`
- **Description**: Python dependencies list
- **Use Case**: Defines all Python packages needed for the project
- **Key Dependencies**: Django, MariaDB driver, Redis, authentication, forms
- **Usage**: `pip install -r requirements.txt`

##### `requirements-minimal.txt`
- **Description**: Minimal Python dependencies
- **Use Case**: Lightweight dependency list for basic functionality
- **Usage**: For minimal installations or testing

#### **Docker & Deployment**

##### `Dockerfile`
- **Description**: Production Docker image configuration
- **Use Case**: Builds optimized container for production deployment
- **Features**: Multi-stage build, security optimizations, minimal image size

##### `Dockerfile.dev`
- **Description**: Development Docker image configuration
- **Use Case**: Development environment with debugging tools and hot reload
- **Features**: Development tools, volume mounts, debug capabilities

##### `docker-compose.yml`
- **Description**: Production Docker services orchestration
- **Use Case**: Defines and runs multi-container production environment
- **Services**: Django app, MariaDB, Redis, Nginx

##### `docker-compose.dev.yml`
- **Description**: Development Docker services orchestration
- **Use Case**: Development environment with debugging and hot reload
- **Services**: Django app, MariaDB, Redis (development configurations)

##### `docker-compose.dev-services.yml`
- **Description**: Development support services only
- **Use Case**: Runs only database and Redis for local Django development
- **Services**: MariaDB, Redis (without Django container)

##### `Makefile`
- **Description**: Build automation and command shortcuts
- **Use Case**: Simplifies Docker operations and development workflow
- **Commands**: dev, prod, build, deploy, backup, restore, logs, shell

#### **Django Management**

##### `manage.py`
- **Description**: Django's command-line utility
- **Use Case**: Administrative tasks, migrations, server startup
- **Usage**: `python manage.py <command>`
- **Common Commands**: runserver, migrate, createsuperuser, collectstatic

##### `create_admin.py`
- **Description**: Script to create Django superuser
- **Use Case**: Automated admin user creation for deployment
- **Usage**: Creates admin user with predefined credentials

##### `config_mariadb_admin.py`
- **Description**: MariaDB admin configuration script
- **Use Case**: Sets up database admin user and permissions
- **Usage**: Database initialization and admin setup

##### `import_dummy_data.py`
- **Description**: Test data import script
- **Use Case**: Populates database with sample data for development/testing
- **Usage**: `python import_dummy_data.py`

##### `run_migrations.py`
- **Description**: Database migration runner
- **Use Case**: Applies database schema changes
- **Usage**: Automated migration execution in deployment

##### `run_server.py`
- **Description**: Django development server launcher
- **Use Case**: Starts Django development server with custom settings
- **Usage**: Alternative to `python manage.py runserver`

##### `debug_settings.py`
- **Description**: Debug-specific Django settings
- **Use Case**: Development debugging configuration
- **Features**: Debug toolbar, verbose logging, development middleware

#### **Database & Backup**

##### `db_dummy.sqlite3.bak`
- **Description**: SQLite database backup with sample data
- **Use Case**: Quick development database setup
- **Contents**: Sample users, polls, votes for testing

### Application Modules

#### **Django Apps**

##### `votebem/`
- **Description**: Main Django project configuration
- **Use Case**: Project settings, URL routing, WSGI/ASGI configuration
- **Contents**: Settings modules, main URL patterns, deployment configs

##### `home/`
- **Description**: Homepage and landing pages app
- **Use Case**: Main website pages, dashboard, general content
- **Features**: Welcome pages, navigation, general information

##### `users/`
- **Description**: User management and authentication app
- **Use Case**: User registration, login, profile management
- **Features**: Custom user model, authentication views, user profiles

##### `voting/`
- **Description**: Core voting functionality app
- **Use Case**: Poll creation, voting logic, results management
- **Features**: Poll models, voting views, results calculation, admin interface

##### `polls/`
- **Description**: Poll management app
- **Use Case**: Poll creation and management interface
- **Features**: Poll CRUD operations, question management, option handling

### Static & Templates

##### `static/`
- **Description**: Static files directory
- **Use Case**: CSS, JavaScript, images, and other static assets
- **Contents**: Frontend resources, admin customizations

##### `templates/`
- **Description**: Django HTML templates
- **Use Case**: Frontend presentation layer
- **Structure**: Base templates, app-specific templates, admin customizations

##### `nginx/`
- **Description**: Nginx web server configuration
- **Use Case**: Reverse proxy, static file serving, SSL termination
- **Files**: Production, development, and default configurations

### Documentation & Scripts

##### `doc/`
- **Description**: Project documentation
- **Use Case**: Development guides, deployment instructions, API docs
- **Contents**: Setup guides, environment docs, development workflows

##### `scripts/`
- **Description**: Automation and utility scripts
- **Use Case**: Development workflow automation, deployment scripts
- **Contents**: Setup scripts, startup scripts, SSL configuration, deployment automation
- **Note**: See `scripts/README.md` for detailed script documentation

---

## 🛠️ Quick Start

### For Django Development:
```bash
cd django_votebem
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### For Docker Development:
```bash
cd django_votebem
make dev
```

### For Production Deployment:
```bash
cd django_votebem
make prod
```

---

## 📚 Additional Documentation

- **Django Project**: See `django_votebem/doc/` for detailed documentation
- **Scripts**: See `django_votebem/scripts/README.md` for automation scripts
- **PHP Legacy**: See `00_VB_php/` for legacy implementation

---

## 🔧 Technology Stack

### Django Implementation:
- **Backend**: Django 4.2+, Python 3.11+
- **Database**: MariaDB
- **Cache**: Redis
- **Web Server**: Nginx
- **Containerization**: Docker & Docker Compose
- **Authentication**: Django Allauth
- **Frontend**: Bootstrap 5, Crispy Forms

### PHP Implementation (Legacy):
- **Backend**: CodeIgniter 3.x, PHP
- **Database**: MySQL/MariaDB
- **Frontend**: HTML, CSS, JavaScript
- **Authentication**: Custom SSO system

---

## 📄 License

This project is proprietary software for VoteBem voting system.

---

## 👥 Contributing

Please refer to the documentation in `django_votebem/doc/` for development guidelines and contribution instructions.