"""
WSGI config for votebem project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import importlib.util

from django.core.wsgi import get_wsgi_application

# Default safely to production settings for Gunicorn/WSGI.
# Rationale:
# - In Docker, process environment may not explicitly set DJANGO_SETTINGS_MODULE.
# - Defaulting to production avoids accidental dev settings on the server.
# - If you need to run development, override via environment:
#   DJANGO_SETTINGS_MODULE=votebem.settings.production
# Defensive default and validation of DJANGO_SETTINGS_MODULE.
#
# Context: The container may receive an environment value like
# "votebem.settings.production" (module not present in this repo), which
# causes a hard crash (ModuleNotFoundError) and a restart loop. To make
# runtime resilient, we:
#  1) default to production if the variable is not set; and
#  2) if a module name is set but does not exist, force production.
#
# This keeps the app online even if a stale .env overrides the variable.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')
_settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')
if importlib.util.find_spec(_settings_module) is None:
    # Fallback to production to avoid container crash
    os.environ['DJANGO_SETTINGS_MODULE'] = 'votebem.settings.production'

application = get_wsgi_application()
