from django.shortcuts import redirect
from django.conf import settings
from django.urls import reverse
from decouple import config

class SiteLockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if lock is enabled
        # We cast to bool. 'True', 'true', '1', 'yes', 'on' are True.
        is_locked = config('SITE_LOCK_ENABLED', default=False, cast=bool)

        if not is_locked:
            return self.get_response(request)

        # If locked, check if user has unlocked the session
        if request.session.get('site_unlocked'):
            return self.get_response(request)

        # Define paths to exclude from locking
        path = request.path
        
        # Get the lock URL
        try:
            lock_url = reverse('site_lock')
        except:
            # Fallback if URL is not yet registered (during startup/migration)
            lock_url = '/site-lock/'

        # Allow access to the lock page itself
        if path == lock_url:
            return self.get_response(request)

        # Allow access to static and media files
        if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
            return self.get_response(request)

        # Allow access to public references list (API)
        if path.startswith('/voting/referencias/list/'):
            return self.get_response(request)

        # Redirect all other requests to the lock page
        # We pass the current path as 'next' so we can redirect back after unlock
        return redirect(f'{lock_url}?next={path}')
