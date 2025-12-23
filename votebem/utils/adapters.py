from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.models import SocialApp
import logging
import uuid


class CustomAccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        """
        Generates a username based on the user's first name.
        Falls back to email prefix or UUID if needed.
        Ensures uniqueness.
        """
        if user.username:
            return

        from allauth.utils import generate_unique_username
        from django.utils.text import slugify

        candidates = []
        
        first_name = getattr(user, 'first_name', '')
        if first_name:
            clean_first_name = slugify(first_name)
            if clean_first_name:
                candidates.append(clean_first_name)
        
        # If we don't have a first name candidate, try email
        if not candidates:
            email = getattr(user, 'email', '')
            if email:
                try:
                    candidates.append(email.split('@')[0])
                except IndexError:
                    pass
        
        # If we still don't have a candidate, use UUID
        if not candidates:
            candidates.append(str(uuid.uuid4()))
        
        user.username = generate_unique_username(candidates)

class SafeSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_app(self, request, provider):
        logger = logging.getLogger("votebem")
        site = get_current_site(request)
        qs = SocialApp.objects.filter(provider=provider, sites=site)
        if qs.exists():
            try:
                return qs.get()
            except Exception:
                app = qs.order_by("id").first()
                logger.warning(
                    "Multiple SocialApp matched; using first",
                    extra={"provider": provider, "site_id": site.id, "chosen_app_id": app.id},
                )
                return app
        qs2 = SocialApp.objects.filter(provider=provider)
        if qs2.exists():
            try:
                return qs2.get()
            except Exception:
                app = qs2.order_by("id").first()
                logger.warning(
                    "Multiple SocialApp provider-only; using first",
                    extra={"provider": provider, "site_id": site.id, "chosen_app_id": app.id},
                )
                return app
        cfg = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
        app_cfg = (cfg.get(provider) or {}).get("APP") or {}
        client_id = (app_cfg.get("client_id") or "").strip()
        secret = (app_cfg.get("secret") or "").strip()
        if client_id and secret:
            return SocialApp(provider=provider, name=provider.title(), client_id=client_id, secret=secret, key="")
        return super().get_app(request, provider)
