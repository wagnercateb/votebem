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
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')
os.environ.setdefault('DB_NAME', config('DB_NAME', default='votebem_dev'))
os.environ.setdefault('DB_USER', config('DB_USER', default='votebem_user'))
os.environ.setdefault('DB_PASSWORD', config('DB_PASSWORD', default='votebem_dev_password'))
os.environ.setdefault('DB_HOST', config('DB_HOST', default='localhost'))
os.environ.setdefault('DB_PORT', config('DB_PORT', default='3306'))
os.environ.setdefault('REDIS_URL', config('REDIS_URL', default='redis://localhost:6379/0'))

# Setup Django
import django
django.setup()

# Run migrations
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py', 'migrate'])