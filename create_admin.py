#!/usr/bin/env python
"""
Script to create a superuser for VoteBem Django application.
"""
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.development')

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
django.setup()

from django.contrib.auth import get_user_model
from votebem.utils.devlog import dev_log  # Use dev_log to print and file-log

def create_superuser():
    """Create a superuser if one doesn't exist."""
    User = get_user_model()
    
    # Check if superuser already exists
    if User.objects.filter(is_superuser=True).exists():
        dev_log("✅ Superuser already exists!")
        superuser = User.objects.filter(is_superuser=True).first()
        dev_log(f"   Email: {superuser.email}")
        return superuser
    
    # Create superuser
    username = "admin"
    email = "admin@votebem.com"
    password = "admin123"
    
    try:
        superuser = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        dev_log("✅ Superuser created successfully!")
        dev_log(f"   Username: {username}")
        dev_log(f"   Email: {email}")
        dev_log(f"   Password: {password}")
        dev_log(f"   Admin URL: http://localhost:8000/admin/")
        return superuser
    except Exception as e:
        dev_log(f"❌ Error creating superuser: {e}")
        return None

if __name__ == "__main__":
    create_superuser()