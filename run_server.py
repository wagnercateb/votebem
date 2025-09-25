#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Add the project directory to the Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Load environment variables from .env.dev
from decouple import Config, RepositoryEnv
config = Config(RepositoryEnv('.env.dev'))

# Set environment variables
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.development')
os.environ.setdefault('DB_NAME', config('DB_NAME', default='votebem_dev'))
os.environ.setdefault('DB_USER', config('DB_USER', default='votebem_user'))
os.environ.setdefault('DB_PASSWORD', config('DB_PASSWORD', default='votebem_dev_password'))
os.environ.setdefault('DB_HOST', config('DB_HOST', default='localhost'))
os.environ.setdefault('DB_PORT', config('DB_PORT', default='5432'))
os.environ.setdefault('REDIS_URL', config('REDIS_URL', default='redis://localhost:6379/0'))
os.environ.setdefault('DEBUG', config('DEBUG', default='True'))
os.environ.setdefault('SECRET_KEY', config('SECRET_KEY', default='dev-secret-key-change-this-for-production'))
os.environ.setdefault('ALLOWED_HOSTS', config('ALLOWED_HOSTS', default='localhost,127.0.0.1,0.0.0.0'))

# Setup Django
import django
django.setup()

# Start the development server
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py', 'runserver', '0.0.0.0:8000'])