"""
Reusable mixins for access control in administrative (gerencial) views.

`StaffRequiredMixin` is designed for class-based views (CBVs) that belong
to the `/gerencial/` namespace. It ensures that:
  - The user is authenticated (via `LoginRequiredMixin`).
  - The user has `is_staff=True` (via `UserPassesTestMixin`).

Use this in any future CBVs under `gerencial` to keep authorization
declarations close to the view while remaining consistent with
route-level gating performed in `voting/admin_urls.py`.

Example:

    from django.views.generic import TemplateView
    from voting.mixins import StaffRequiredMixin

    class GerencialExampleView(StaffRequiredMixin, TemplateView):
        template_name = "gerencial/example.html"

This mixin complements the `staff_member_required` wrapper in URLs and
provides a clear per-view policy that is easy to maintain and test.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    CBV mixin that requires `request.user.is_staff`.

    - Redirects anonymous users to the login view (via LoginRequiredMixin).
    - Raises 403 (PermissionDenied) for authenticated non-staff users.

    Note: This mirrors `django.contrib.admin.views.decorators.staff_member_required`
    for CBVs, improving clarity when used directly on views.
    """

    def test_func(self):
        # Only staff users pass this test.
        user = getattr(self, "request", None)
        user = getattr(user, "user", None)
        return bool(user and user.is_authenticated and user.is_staff)

    def handle_no_permission(self):
        # If authenticated but not staff, return 403 to avoid confusing redirects.
        if getattr(self.request, "user", None) and self.request.user.is_authenticated:
            raise PermissionDenied("Staff access required")
        # Otherwise defer to LoginRequiredMixin to redirect to login.
        return super().handle_no_permission()

