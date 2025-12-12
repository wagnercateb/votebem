"""
WSGI config for votebem project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Default safely to production settings for Gunicorn/WSGI.
# Rationale:
# - In Docker, process environment may not explicitly set DJANGO_SETTINGS_MODULE.
# - Defaulting to production avoids accidental dev settings on the server.
# - If you need to run development, override via environment:
#   DJANGO_SETTINGS_MODULE=votebem.settings.production
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')

application = get_wsgi_application()
