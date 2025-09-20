from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.HomeView.as_view(), name='index'),
    path('newsletter-signup/', views.NewsletterSignupView.as_view(), name='newsletter_signup'),
    path('contato/', views.ContactView.as_view(), name='contact'),
]