"""
ASGI config for votebem project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Default safely to production settings for ASGI.
# See wsgi.py comments for rationale. Override via environment if needed.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')

application = get_asgi_application()
