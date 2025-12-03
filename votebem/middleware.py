"""
Staff-only guard middleware for the "/gerencial/" administrative area.

Overview
--------
- Intercepts every request whose path starts with "/gerencial/".
- Requires the user to be authenticated and have `is_staff=True`.
- If the user is not authenticated or not staff, redirects to the Django admin
  login at `/admin/login/` with a `next` query parameter so that, after
  successful login, the user is returned to the originally requested URL.

Design Rationale
----------------
- Centralized enforcement: Rather than decorating individual views with
  `@staff_member_required`, a middleware ensures consistent policy across all
  routes under the "/gerencial/" prefix.
- Minimal intrusion: No changes are required to each view; future additions
  under the "/gerencial/" path are automatically protected.
- Admin login: Using the admin login reinforces the staff-only requirement and
  avoids funneling non-staff users through general user login flows.

Registration
------------
- Add `votebem.middleware.StaffOnlyGerencialMiddleware` to `MIDDLEWARE` in
  settings immediately after `django.contrib.auth.middleware.AuthenticationMiddleware`.

Testing Notes
-------------
- Unauthenticated access to `/gerencial/*` should yield a 302 redirect to
  `/admin/login/?next=/gerencial/...`.
- Authenticated non-staff users should also be redirected to admin login.
- Authenticated staff users should pass through and receive normal responses
  from the target views.
"""

from django.shortcuts import redirect


class StaffOnlyGerencialMiddleware:
    """
    Middleware enforcing staff-only access for all "/gerencial/" URLs.

    Behavior:
    - If `request.path` starts with "/gerencial/":
      - Allow only authenticated users with `is_staff=True`.
      - Otherwise, issue a redirect to `/admin/login/` with `next` set to the
        originally requested path.
    - For all other paths, pass the request through unchanged.
    """

    def __init__(self, get_response):
        # Store the next middleware or view handler in the chain.
        self.get_response = get_response

    def __call__(self, request):
        # Defensive read of the request path; default to empty string if absent.
        path = request.path or ""

        # Enforce staff-only policy for the administrative area.
        if path.startswith("/gerencial/"):
            user = getattr(request, "user", None)

            # Require authenticated staff; otherwise redirect to admin login.
            if not (user and user.is_authenticated and getattr(user, "is_staff", False)):
                login_url = "/admin/login/"
                return redirect(f"{login_url}?next={path}")

        # Continue normal processing for non-admin paths or authorized users.
        return self.get_response(request)