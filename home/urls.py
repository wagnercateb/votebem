from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.HomeView.as_view(), name='index'),
    path('newsletter-signup/', views.NewsletterSignupView.as_view(), name='newsletter_signup'),
    path('contato/', views.ContactView.as_view(), name='contact'),
    path('quem-somos/', views.AboutView.as_view(), name='about'),
    path('faq/', views.FAQView.as_view(), name='faq'),
    path('termos-de-uso/', views.TermsView.as_view(), name='terms'),
    path('politica-de-privacidade/', views.PrivacyView.as_view(), name='privacy'),
]
