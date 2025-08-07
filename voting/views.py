from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, View
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from .models import VotacaoDisponivel, Voto, Proposicao
from users.models import UserProfile

class VotacoesDisponiveisView(ListView):
    """List available voting sessions"""
    model = VotacaoDisponivel
    template_name = 'voting/votacoes_disponiveis.html'
    context_object_name = 'votacoes'
    paginate_by = 20
    
    def get_queryset(self):
        # Only show active voting sessions
        now = timezone.now()
        return VotacaoDisponivel.objects.filter(
            ativo=True,
            no_ar_desde__lte=now
        ).filter(
            Q(no_ar_ate__isnull=True) | Q(no_ar_ate__gte=now)
        ).select_related('proposicao').order_by('-no_ar_desde')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Get user's votes to show which ones they've already voted on
            user_votes = Voto.objects.filter(user=self.request.user).values_list('votacao_id', flat=True)
            context['user_votes'] = list(user_votes)
        else:
            context['user_votes'] = []
        return context

class VotacaoDetailView(DetailView):
    """Detail view for a specific voting session"""
    model = VotacaoDisponivel
    template_name = 'voting/votacao_detail.html'
    context_object_name = 'votacao'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        votacao = self.get_object()
        
        # Check if user has already voted
        user_vote = None
        if self.request.user.is_authenticated:
            try:
                user_vote = Voto.objects.get(user=self.request.user, votacao=votacao)
            except Voto.DoesNotExist:
                pass
        
        context['user_vote'] = user_vote
        context['can_vote'] = votacao.is_active() and user_vote is None
        
        # Get voting statistics
        context['total_votos'] = votacao.get_total_votos_populares()
        context['votos_sim'] = votacao.get_votos_sim_populares()
        context['votos_nao'] = votacao.get_votos_nao_populares()
        
        return context

class VotarView(LoginRequiredMixin, View):
    """Handle voting action"""
    
    def post(self, request, votacao_id):
        votacao = get_object_or_404(VotacaoDisponivel, id=votacao_id)
        
        # Check if voting is still active
        if not votacao.is_active():
            messages.error(request, 'Esta votação não está mais ativa.')
            return redirect('voting:votacao_detail', pk=votacao_id)
        
        # Check if user has already voted
        if Voto.objects.filter(user=request.user, votacao=votacao).exists():
            messages.error(request, 'Você já votou nesta votação.')
            return redirect('voting:votacao_detail', pk=votacao_id)
        
        # Get the vote choice
        voto_choice = request.POST.get('voto')
        if voto_choice not in ['SIM', 'NAO', 'ABSTENCAO']:
            messages.error(request, 'Opção de voto inválida.')
            return redirect('voting:votacao_detail', pk=votacao_id)
        
        # Create the vote
        Voto.objects.create(
            user=request.user,
            votacao=votacao,
            voto=voto_choice
        )
        
        # Update user profile with vote record
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        profile.add_voto(votacao_id)
        
        messages.success(request, f'Seu voto "{voto_choice}" foi registrado com sucesso!')
        return redirect('voting:votacao_detail', pk=votacao_id)

class MeusVotosView(LoginRequiredMixin, ListView):
    """List user's votes"""
    model = Voto
    template_name = 'voting/meus_votos.html'
    context_object_name = 'votos'
    paginate_by = 20
    
    def get_queryset(self):
        return Voto.objects.filter(user=self.request.user).select_related('votacao__proposicao').order_by('-created_at')

class RankingView(ListView):
    """Show voting statistics and rankings"""
    model = VotacaoDisponivel
    template_name = 'voting/ranking.html'
    context_object_name = 'votacoes'
    paginate_by = 10
    
    def get_queryset(self):
        return VotacaoDisponivel.objects.annotate(
            total_votos=Count('voto')
        ).filter(total_votos__gt=0).order_by('-total_votos')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get top voters
        from django.contrib.auth.models import User
        top_voters = User.objects.annotate(
            total_votos=Count('voto')
        ).filter(total_votos__gt=0).order_by('-total_votos')[:10]
        
        context['top_voters'] = top_voters
        return context
