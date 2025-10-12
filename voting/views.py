from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, View
from django.contrib import messages
from django.db.models import Count, Q, Sum, Case, When, IntegerField, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from .models import VotacaoDisponivel, Voto, Proposicao, Congressman, CongressmanVote
from .forms import VotoForm
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

class PersonalizedRankingView(LoginRequiredMixin, ListView):
    """Personalized ranking view equivalent to vb14_RankingPersonalizado.php"""
    model = Congressman
    template_name = 'voting/ranking_personalizado.html'
    context_object_name = 'congressmen_ranking'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        user_uf = None
        
        # Get user's UF from profile or session
        try:
            user_profile = UserProfile.objects.get(user=user)
            user_uf = user_profile.uf
        except UserProfile.DoesNotExist:
            pass
        
        # If no UF in profile, try to get from GET parameter
        if not user_uf:
            user_uf = self.request.GET.get('uf')
        
        if not user_uf:
            return Congressman.objects.none()
        
        # Get congressmen from user's state with their scores
        # This query calculates the score based on how often the congressman voted
        # the same way as the user on the same propositions
        queryset = Congressman.objects.filter(uf=user_uf, ativo=True)
        
        # Annotate with score calculation
        queryset = queryset.annotate(
            total_score=Coalesce(
                Sum(
                    Case(
                        # When user voted SIM and congressman voted 1 (SIM)
                        When(
                            congressmanvote__proposicao__voto__user=user,
                            congressmanvote__proposicao__voto__voto='SIM',
                            congressmanvote__voto=1,
                            then=1
                        ),
                        # When user voted NAO and congressman voted -1 (NAO)
                        When(
                            congressmanvote__proposicao__voto__user=user,
                            congressmanvote__proposicao__voto__voto='NAO',
                            congressmanvote__voto=-1,
                            then=1
                        ),
                        # When user voted ABSTENCAO and congressman voted 0 (ABSTENCAO)
                        When(
                            congressmanvote__proposicao__voto__user=user,
                            congressmanvote__proposicao__voto__voto='ABSTENCAO',
                            congressmanvote__voto=0,
                            then=1
                        ),
                        default=0,
                        output_field=IntegerField()
                    )
                ),
                0
            ),
            total_votes_compared=Count(
                'congressmanvote',
                filter=Q(congressmanvote__proposicao__voto__user=user)
            )
        ).filter(total_votes_compared__gt=0).order_by('-total_score', 'nome')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's UF
        user_uf = None
        try:
            user_profile = UserProfile.objects.get(user=self.request.user)
            user_uf = user_profile.uf
        except UserProfile.DoesNotExist:
            pass
        
        if not user_uf:
            user_uf = self.request.GET.get('uf')
        
        context['user_uf'] = user_uf
        context['available_ufs'] = [
            'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
            'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
            'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
        ]
        
        return context

class CongressmanDetailView(LoginRequiredMixin, DetailView):
    """Congressman detail view equivalent to vb16_DetalheRanking.php"""
    model = Congressman
    template_name = 'voting/congressman_detail.html'
    context_object_name = 'congressman'
    pk_url_kwarg = 'congressman_id'
    
    def get_object(self):
        congressman_id = self.kwargs.get('congressman_id')
        return get_object_or_404(Congressman, id_cadastro=congressman_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        congressman = self.get_object()
        user = self.request.user
        
        # Get detailed voting comparison between user and congressman
        # This is equivalent to the getDetalheRanking function in PHP
        voting_details = []
        accumulated_points = 0
        
        # Get all propositions where both user and congressman voted
        user_votes = Voto.objects.filter(user=user).select_related('votacao__proposicao')
        
        for user_vote in user_votes:
            try:
                congressman_vote = CongressmanVote.objects.get(
                    congressman=congressman,
                    proposicao=user_vote.votacao.proposicao
                )
                
                # Calculate points based on vote agreement
                points = 0
                if user_vote.voto == 'SIM' and congressman_vote.voto == 1:
                    points = 1
                elif user_vote.voto == 'NAO' and congressman_vote.voto == -1:
                    points = 1
                elif user_vote.voto == 'ABSTENCAO' and congressman_vote.voto == 0:
                    points = 1
                
                accumulated_points += points
                
                voting_details.append({
                    'titulo': user_vote.votacao.titulo,
                    'ementa': user_vote.votacao.proposicao.ementa,
                    'id_proposicao': user_vote.votacao.proposicao.id_proposicao,
                    'data_votacao': user_vote.votacao.data_hora_votacao,
                    'voto_congressman': congressman_vote.get_voto_display_text(),
                    'voto_user': user_vote.get_voto_display(),
                    'data_user_vote': user_vote.created_at,
                    'points': points,
                    'accumulated_points': accumulated_points,
                })
                
            except CongressmanVote.DoesNotExist:
                # Congressman didn't vote on this proposition
                continue
        
        context['voting_details'] = voting_details
        context['total_accumulated_points'] = accumulated_points
        context['congressman_photo_url'] = congressman.get_foto_url()
        
        return context


class VotacoesPesquisaView(ListView):
    """Public search/list of all voting sessions with filters"""
    model = VotacaoDisponivel
    template_name = 'voting/votacoes_pesquisa.html'
    context_object_name = 'votacoes'
    paginate_by = 25

    def get_queryset(self):
        qs = VotacaoDisponivel.objects.select_related('proposicao').order_by('-no_ar_desde')

        q = self.request.GET.get('q')
        tipo = self.request.GET.get('tipo')
        ano = self.request.GET.get('ano')
        ativo = self.request.GET.get('ativo')

        if q:
            qs = qs.filter(
                Q(titulo__icontains=q) |
                Q(resumo__icontains=q) |
                Q(proposicao__titulo__icontains=q) |
                Q(proposicao__ementa__icontains=q)
            )

        if tipo:
            qs = qs.filter(proposicao__tipo=tipo)

        if ano:
            try:
                qs = qs.filter(proposicao__ano=int(ano))
            except ValueError:
                pass

        if ativo == 'sim':
            qs = qs.filter(ativo=True)
        elif ativo == 'nao':
            qs = qs.filter(ativo=False)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Distinct tipos and anos for filters
        tipos = list(
            VotacaoDisponivel.objects.values_list('proposicao__tipo', flat=True)
            .distinct()
        )
        anos = list(
            VotacaoDisponivel.objects.values_list('proposicao__ano', flat=True)
            .distinct()
        )
        context['tipos'] = sorted([t for t in tipos if t])
        context['anos'] = sorted([a for a in anos if a])
        # Preserve current filters
        context['q'] = self.request.GET.get('q', '')
        context['tipo_sel'] = self.request.GET.get('tipo', '')
        context['ano_sel'] = self.request.GET.get('ano', '')
        context['ativo_sel'] = self.request.GET.get('ativo', '')
        return context
