#!/usr/bin/env python
import os
import sys

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings')

print(f"Django settings module: {os.environ.get('DJANGO_SETTINGS_MODULE')}")

# Check if decouple is working before Django setup
try:
    from decouple import config
    print(f"Decouple DEBUG (before Django): {config('DEBUG', default='NOT_SET')}")
    print(f"Decouple ALLOWED_HOSTS (before Django): {config('ALLOWED_HOSTS', default='NOT_SET')}")
except Exception as e:
    print(f"Decouple error: {e}")

# Test importing the settings module directly
try:
    print("\n--- Testing direct import of votebem.settings ---")
    import votebem.settings as direct_settings
    print(f"Direct import DEBUG: {getattr(direct_settings, 'DEBUG', 'NOT_FOUND')}")
    print(f"Direct import ALLOWED_HOSTS: {getattr(direct_settings, 'ALLOWED_HOSTS', 'NOT_FOUND')}")
except Exception as e:
    print(f"Direct import error: {e}")

# Test importing development settings directly
try:
    print("\n--- Testing direct import of votebem.settings.development ---")
    import votebem.settings.development as dev_settings
    print(f"Development DEBUG: {getattr(dev_settings, 'DEBUG', 'NOT_FOUND')}")
    print(f"Development ALLOWED_HOSTS: {getattr(dev_settings, 'ALLOWED_HOSTS', 'NOT_FOUND')}")
except Exception as e:
    print(f"Development import error: {e}")

# Now setup Django
import django
from django.conf import settings

django.setup()

print(f"\n--- After Django setup ---")
print(f"Settings file: {settings.SETTINGS_MODULE}")
print(f"DEBUG: {settings.DEBUG}")
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")