#!/usr/bin/env python
import os
import sys

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings')
from votebem.utils.devlog import dev_log  # Use dev_log for unified dev logging

dev_log(f"Django settings module: {os.environ.get('DJANGO_SETTINGS_MODULE')}")

# Check if decouple is working before Django setup
try:
    from decouple import config
    dev_log(f"Decouple DEBUG (before Django): {config('DEBUG', default='NOT_SET')}")
    dev_log(f"Decouple ALLOWED_HOSTS (before Django): {config('ALLOWED_HOSTS', default='NOT_SET')}")
except Exception as e:
    dev_log(f"Decouple error: {e}")

# Test importing the settings module directly
try:
    dev_log("\n--- Testing direct import of votebem.settings ---")
    import votebem.settings as direct_settings
    dev_log(f"Direct import DEBUG: {getattr(direct_settings, 'DEBUG', 'NOT_FOUND')}")
    dev_log(f"Direct import ALLOWED_HOSTS: {getattr(direct_settings, 'ALLOWED_HOSTS', 'NOT_FOUND')}")
except Exception as e:
    dev_log(f"Direct import error: {e}")

# Test importing development settings directly
try:
    dev_log("\n--- Testing direct import of votebem.settings.development ---")
    import votebem.settings.development as dev_settings
    dev_log(f"Development DEBUG: {getattr(dev_settings, 'DEBUG', 'NOT_FOUND')}")
    dev_log(f"Development ALLOWED_HOSTS: {getattr(dev_settings, 'ALLOWED_HOSTS', 'NOT_FOUND')}")
except Exception as e:
    dev_log(f"Development import error: {e}")

# Now setup Django
import django
from django.conf import settings

django.setup()

dev_log(f"\n--- After Django setup ---")
dev_log(f"Settings file: {settings.SETTINGS_MODULE}")
dev_log(f"DEBUG: {settings.DEBUG}")
dev_log(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")