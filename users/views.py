from django.shortcuts import render, redirect
import logging
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.views.generic import CreateView, TemplateView, UpdateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
from .models import UserProfile
from .forms import UserProfileForm, UserUpdateForm, UserRegisterForm
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

class RegisterView(CreateView):
    """User registration view"""
    form_class = UserRegisterForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('users:login')
    
    def form_valid(self, form):
        user = form.save(commit=False)
        user.email = form.cleaned_data.get('email')
        user.is_active = False
        user.save()
        UserProfile.objects.create(user=user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        activation_link = self.request.build_absolute_uri(
            reverse_lazy('users:activate', kwargs={'uidb64': uid, 'token': token})
        )
        subject = 'VoteBem - Confirmação de e-mail'
        message = f'Olá {user.username},\n\nClique no link para ativar sua conta:\n{activation_link}\n\nSe você não solicitou, ignore este e-mail.'
        try:
            send_mail(
                subject,
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@votebem.com'),
                [user.email],
                fail_silently=False
            )
            messages.success(self.request, 'Conta criada! Verifique seu e-mail para ativar a conta.')
        except Exception:
            logger.exception('Erro ao enviar e-mail de ativação para o usuário %s', user.pk)
            messages.error(
                self.request,
                'Conta criada, mas houve um problema ao enviar o e-mail de ativação. '
                'Entre em contato com o suporte para concluir a ativação.'
            )
        return redirect(self.success_url)

def activate_account(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        user = None
    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=['is_active'])
        messages.success(request, 'Sua conta foi ativada! Agora você pode entrar.')
        return redirect('users:login')
    messages.error(request, 'Link de ativação inválido ou expirado.')
    return redirect('users:register')

class ProfileView(LoginRequiredMixin, TemplateView):
    """User profile view with editing capabilities"""
    template_name = 'users/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Forms
        if 'user_form' not in context:
            context['user_form'] = UserUpdateForm(instance=user)
        if 'profile_form' not in context:
            context['profile_form'] = UserProfileForm(instance=profile)
            
        context['profile'] = profile
        
        # Statistics
        context['user_stats'] = {
            'total_votos': user.voto_set.count() if hasattr(user, 'voto_set') else 0,
            'total_enquetes': user.enquete_set.count() if hasattr(user, 'enquete_set') else 0,
            'respostas_enquetes': user.respostaenquete_set.count() if hasattr(user, 'respostaenquete_set') else 0,
            'pontos_ranking': profile.pontos_ranking
        }
        
        return context

    def post(self, request, *args, **kwargs):
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Seu perfil foi atualizado com sucesso!')
            return redirect('users:profile')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
            return self.render_to_response(self.get_context_data(user_form=user_form, profile_form=profile_form))

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
