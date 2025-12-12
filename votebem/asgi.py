"""
ASGI config for votebem project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import importlib.util

from django.core.asgi import get_asgi_application

# Default safely to production settings for ASGI.
# See wsgi.py comments for rationale. Override via environment if needed.
# Defensive default and validation of DJANGO_SETTINGS_MODULE.
# Mirrors wsgi.py logic to prevent ASGI startup failures when a
# non-existent settings module is provided via environment.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')
_settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')
if importlib.util.find_spec(_settings_module) is None:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'votebem.settings.production'

application = get_asgi_application()
