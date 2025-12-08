from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import import_string
import os


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        try:
            from allauth.socialaccount.models import SocialApp
            from django.contrib.sites.models import Site
            from django.db.utils import OperationalError, ProgrammingError
            site = Site.objects.get(id=getattr(settings, 'SITE_ID', 1))
            client_id = os.environ.get('GOOGLE_CLIENT_ID') or getattr(settings, 'GOOGLE_CLIENT_ID', None)
            secret = os.environ.get('GOOGLE_CLIENT_SECRET') or getattr(settings, 'GOOGLE_CLIENT_SECRET', None)
            if client_id and secret:
                apps_for_site = SocialApp.objects.filter(provider='google', sites=site).order_by('id')
                if apps_for_site:
                    primary = apps_for_site[0]
                    if primary.client_id != client_id or primary.secret != secret:
                        primary.client_id = client_id
                        primary.secret = secret
                        primary.save(update_fields=['client_id', 'secret'])
                    if site not in primary.sites.all():
                        primary.sites.add(site)
                    for extra in apps_for_site[1:]:
                        try:
                            extra.sites.remove(site)
                        except Exception:
                            pass
                else:
                    existing = SocialApp.objects.filter(provider='google').order_by('id').first()
                    if existing:
                        if existing.client_id != client_id or existing.secret != secret:
                            existing.client_id = client_id
                            existing.secret = secret
                            existing.save(update_fields=['client_id', 'secret'])
                        if site not in existing.sites.all():
                            existing.sites.add(site)
                    else:
                        app = SocialApp.objects.create(provider='google', name='Google', client_id=client_id, secret=secret, key='')
                        app.sites.add(site)
        except (OperationalError, ProgrammingError):
            pass
