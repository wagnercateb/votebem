"""
Template context processors for exposing selected settings to templates.

This adds `SOCIAL_LOGIN_ENABLED` to the template context so templates can
conditionally render social login sections in a safe, deploy-controlled way.
"""

from django.conf import settings


def social_login_settings(request):
    def _provider_available(provider: str) -> bool:
        cfg = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
        app_cfg = (cfg.get(provider) or {}).get("APP") or {}
        client_id = (app_cfg.get("client_id") or "").strip()
        secret = (app_cfg.get("secret") or "").strip()
        if client_id and secret:
            return True
        try:
            from allauth.socialaccount.models import SocialApp
            site_id = getattr(settings, "SITE_ID", None)
            qs = SocialApp.objects.filter(provider=provider)
            if site_id:
                qs = qs.filter(sites__id=site_id)
            return qs.count() == 1
        except Exception:
            return False

    base_enabled = getattr(settings, "SOCIAL_LOGIN_ENABLED", True)
    google_ok = _provider_available("google")
    facebook_ok = _provider_available("facebook")
    enabled = bool(base_enabled) and (google_ok or facebook_ok)

    return {
        "SOCIAL_LOGIN_ENABLED": enabled,
        "SOCIAL_GOOGLE_AVAILABLE": bool(base_enabled) and google_ok,
        "SOCIAL_FACEBOOK_AVAILABLE": bool(base_enabled) and facebook_ok,
    }
