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

def create_superuser():
    """Create a superuser if one doesn't exist."""
    User = get_user_model()
    
    # Check if superuser already exists
    if User.objects.filter(is_superuser=True).exists():
        print("✅ Superuser already exists!")
        superuser = User.objects.filter(is_superuser=True).first()
        print(f"   Email: {superuser.email}")
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
        print("✅ Superuser created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"   Admin URL: http://localhost:8000/admin/")
        return superuser
    except Exception as e:
        print(f"❌ Error creating superuser: {e}")
        return None

if __name__ == "__main__":
    create_superuser()