"""
Template context processors for exposing selected settings to templates.

This adds `SOCIAL_LOGIN_ENABLED` to the template context so templates can
conditionally render social login sections in a safe, deploy-controlled way.
"""

from django.conf import settings


def social_login_settings(request):
    """Expose `SOCIAL_LOGIN_ENABLED` boolean to all templates.

    - When False (e.g., in production during remediation), templates can hide
      social login buttons to avoid runtime errors from misconfigured providers.
    - When True (default in base settings), templates render social login.
    """
    return {
        "SOCIAL_LOGIN_ENABLED": getattr(settings, "SOCIAL_LOGIN_ENABLED", True)
    }

