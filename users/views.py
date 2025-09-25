from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.views.generic import CreateView, TemplateView, UpdateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
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

class RankingView(ListView):
    """User ranking view showing users ordered by participation points"""
    model = User
    template_name = 'users/ranking.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        # Get users with their profiles and order by ranking points
        return User.objects.select_related('userprofile').annotate(
            vote_count=Count('voto', distinct=True),
            enquete_count=Count('enquete', distinct=True)
        ).filter(
            Q(vote_count__gt=0) | Q(enquete_count__gt=0)
        ).order_by('-userprofile__pontos_ranking', '-vote_count', '-enquete_count')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        users = self.get_queryset()
        
        # Get top 3 users for podium display
        context['top_users'] = users[:3]
        
        # Get current user's position if logged in
        if self.request.user.is_authenticated:
            try:
                user_position = list(users.values_list('id', flat=True)).index(self.request.user.id) + 1
                context['user_position'] = user_position
            except ValueError:
                context['user_position'] = None
        
        return context
