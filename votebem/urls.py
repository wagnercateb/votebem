"""
URL configuration for votebem project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import FileResponse
from pathlib import Path
from .health import health_check
def favicon_view(request):
    icon_path = Path(settings.BASE_DIR) / 'favicon.ico'
    return FileResponse(open(icon_path, 'rb'), content_type='image/x-icon')

def favicon_png_view(request):
    icon_path = Path(settings.BASE_DIR) / 'favicon.png'
    return FileResponse(open(icon_path, 'rb'), content_type='image/png')

urlpatterns = [
    # Administrative interface with namespace
    path('gerencial/', include('voting.admin_urls')),
    # Django admin
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('users/', include('users.urls')),
    path('voting/', include('voting.urls')),
    path('polls/', include('polls.urls')),
    path('home/', include('home.urls')),
    path('health/', health_check, name='health_check'),
    path('favicon.ico', favicon_view, name='favicon'),
    path('favicon.png', favicon_png_view, name='favicon_png'),
    path('', RedirectView.as_view(url='/home/', permanent=False)),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Add Django Debug Toolbar URLs
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
