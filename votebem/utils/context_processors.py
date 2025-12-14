"""
Template context processors for exposing selected settings to templates.

This adds `SOCIAL_LOGIN_ENABLED` to the template context so templates can
conditionally render social login sections in a safe, deploy-controlled way.
"""

from django.conf import settings
import logging


def social_login_settings(request):
    logger = logging.getLogger("votebem")

    def _provider_available(provider: str) -> bool:
        cfg = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
        app_cfg = (cfg.get(provider) or {}).get("APP") or {}
        client_id = (app_cfg.get("client_id") or "").strip()
        secret = (app_cfg.get("secret") or "").strip()
        try:
            from allauth.socialaccount.models import SocialApp
            site_id = getattr(settings, "SITE_ID", None)
            qs = SocialApp.objects.filter(provider=provider)
            count = None
            if site_id:
                qs = qs.filter(sites__id=site_id)
            count = qs.count()
            if count and count != 1:
                ok = False
            elif count == 1:
                ok = True
            else:
                ok = bool(client_id and secret)
            if getattr(settings, "SOCIAL_LOGIN_ENABLED", True) and not ok:
                logger.warning(
                    "Social login provider unavailable",
                    extra={
                        "provider": provider,
                        "site_id": site_id,
                        "app_credentials_present": bool(client_id and secret),
                        "socialapp_count_for_site": count,
                        "path": getattr(request, "path", None),
                    },
                )
            return ok
        except Exception:
            return False

    base_enabled = getattr(settings, "SOCIAL_LOGIN_ENABLED", True)
    google_ok = _provider_available("google")
    facebook_ok = _provider_available("facebook")
    enabled = bool(base_enabled) and (google_ok or facebook_ok)

    logger.info(
        "Social login context",
        extra={
            "base_enabled": bool(base_enabled),
            "google_available": google_ok,
            "facebook_available": facebook_ok,
            "path": getattr(request, "path", None),
        },
    )

    return {
        "SOCIAL_LOGIN_ENABLED": enabled,
        "SOCIAL_GOOGLE_AVAILABLE": bool(base_enabled) and google_ok,
        "SOCIAL_FACEBOOK_AVAILABLE": bool(base_enabled) and facebook_ok,
    }
