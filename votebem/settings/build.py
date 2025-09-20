"""
Build-time settings for Docker container.
This settings file is used during the Docker build process to collect static files.
"""

from .base import *
import os

# Override settings for build time
DEBUG = False
SECRET_KEY = 'build-time-secret-key-for-collectstatic'

# Database - use a dummy database for build time
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Static files configuration for Docker build
STATIC_URL = '/static/'
STATIC_ROOT = '/app/staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'

# Disable cache for build
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Minimal logging for build
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}

# Disable remote debugging during build
ENABLE_REMOTE_DEBUG = False

# Simple email backend for build
EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'