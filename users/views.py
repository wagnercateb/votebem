from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.views.generic import CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import UserProfile
from .forms import UserProfileForm

class RegisterView(CreateView):
    """User registration view"""
    form_class = UserCreationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('voting:votacoes_disponiveis')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Create user profile
        UserProfile.objects.create(user=self.object)
        # Log the user in
        login(self.request, self.object)
        messages.success(self.request, 'Conta criada com sucesso!')
        return response

class ProfileView(LoginRequiredMixin, TemplateView):
    """User profile view"""
    template_name = 'users/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        return context

class ProfileEditView(LoginRequiredMixin, UpdateView):
    """Edit user profile view"""
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'users/profile_edit.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    def form_valid(self, form):
        messages.success(self.request, 'Perfil atualizado com sucesso!')
        return super().form_valid(form)
