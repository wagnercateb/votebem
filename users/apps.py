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
                app, _ = SocialApp.objects.get_or_create(provider='google', name='Google', defaults={'client_id': client_id, 'secret': secret, 'key': ''})
                if app.client_id != client_id or app.secret != secret:
                    app.client_id = client_id
                    app.secret = secret
                    app.save(update_fields=['client_id', 'secret'])
                if site not in app.sites.all():
                    app.sites.add(site)
        except (OperationalError, ProgrammingError):
            pass
