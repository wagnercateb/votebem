from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, View
from django.contrib import messages
from django.db.models import Count, Q, Sum, Case, When, IntegerField, F, Value, CharField
from django.db.models.functions import Coalesce, Upper, Trim
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from .models import VotacaoVoteBem, Voto, Proposicao, ProposicaoVotacao, Congressman, CongressmanVote, Referencia
from .forms import VotoForm
from users.models import UserProfile
import json

class VotacoesDisponiveisView(ListView):
    """List available voting sessions"""
    model = VotacaoVoteBem
    template_name = 'voting/votacoes_disponiveis.html'
    context_object_name = 'votacoes'
    paginate_by = 200
    
    def get_queryset(self):
        # Show voting sessions that are marked active and have started.
        # Even if the end date is in the past, keep them listed but they will render as "Inativa".
        now = timezone.now()
        # Prefetch proposição and its temas to avoid N+1 when rendering cards
        return VotacaoVoteBem.objects.filter(
            ativo=True,
            no_ar_desde__lte=now
        ).select_related('proposicao_votacao__proposicao') \
         .prefetch_related('proposicao_votacao__proposicao__proposicaotema_set__tema') \
         .annotate(
             sort_order_is_null=Case(
                 When(sort_order__isnull=True, then=1),
                 default=0,
                 output_field=IntegerField(),
             )
         ).order_by('sort_order_is_null', 'sort_order', '-data_hora_votacao')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate total active votings (ignoring pagination)
        now = timezone.now()
        context['total_active_count'] = VotacaoVoteBem.objects.filter(
            ativo=True,
            no_ar_desde__lte=now
        ).filter(
            Q(no_ar_ate__isnull=True) | Q(no_ar_ate__gte=now)
        ).count()

        if self.request.user.is_authenticated:
            # Get user's votes to show which ones they've already voted on
            # Return a dict {votacao_id: voto_value} to allow displaying "Votei Sim/Não"
            user_votes_qs = Voto.objects.filter(user=self.request.user).values('votacao_id', 'voto')
            user_votes = {item['votacao_id']: item['voto'] for item in user_votes_qs}
            context['user_votes'] = user_votes
        else:
            context['user_votes'] = {}

        # Grouping helper flags for template rendering:
        # Determine if the current page has any cards already voted by the user,
        # so we can show the "Já votadas" subtitle only when applicable.
        try:
            current_items = list(context.get('page_obj').object_list) if context.get('page_obj') else list(context.get('votacoes', []))
        except Exception:
            current_items = list(context.get('votacoes', []))
        voted_set = set(context['user_votes'])
        context['has_voted_cards_on_page'] = any(getattr(item, 'id', None) in voted_set for item in current_items)
        context['has_unvoted_cards_on_page'] = any(getattr(item, 'id', None) not in voted_set for item in current_items)
        return context



class VotacaoDetailView(DetailView):
    """Detail view for a specific voting session"""
    model = VotacaoVoteBem
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
        context['can_vote'] = (
            self.request.user.is_authenticated and votacao.is_active() and user_vote is None
        )
        
        # contagem de votos Votebem, comentei porque decidi não mostrar mais na página de votação Votebem
        # # Get voting statistics
        # context['total_votos'] = votacao.get_total_votos_populares()
        # context['votos_sim'] = votacao.get_votos_sim_populares()
        # context['votos_nao'] = votacao.get_votos_nao_populares()
        # try:
        #     context['votos_abstencao'] = votacao.get_votos_abstencao_populares()
        # except Exception:
        #     context['votos_abstencao'] = 0

        # Related votações from the same proposição (via proposicao_votacao -> proposicao)
        try:
            proposicao_id = getattr(votacao.proposicao_votacao.proposicao, 'id_proposicao', None)
        except Exception:
            proposicao_id = None
        related_votacoes = []
        if proposicao_id:
            related_votacoes = (
                VotacaoVoteBem.objects
                .select_related('proposicao_votacao__proposicao')
                .filter(proposicao_votacao__proposicao_id=proposicao_id)
                .exclude(id=votacao.id)
                .order_by('id')[:2]
            )
        context['related_votacoes'] = related_votacoes

        # Referências externas vinculadas à votação oficial da proposição
        # Usa relação 1:N em Referencia(proposicao_votacao) para listar links explicativos
        try:
            referencias = Referencia.objects.select_related('divulgador').filter(proposicao_votacao=votacao.proposicao_votacao).order_by('-created_at')
        except Exception:
            referencias = []
        context['referencias'] = referencias
        context['referencias_count'] = len(referencias) if hasattr(referencias, '__len__') else referencias.count() if hasattr(referencias, 'count') else 0

        return context

class VotarView(LoginRequiredMixin, View):
    """Handle voting action"""
    
    def post(self, request, votacao_id):
        votacao = get_object_or_404(VotacaoVoteBem, id=votacao_id)
        
        # Check if voting is still active
        if not votacao.is_active():
            messages.error(request, 'Esta votação não está mais ativa.')
            return redirect('voting:votacao_detail', pk=votacao_id)
        
        # Check if user has already voted
        if Voto.objects.filter(user=request.user, votacao=votacao).exists():
            messages.error(request, 'Você já votou nesta votação.')
            return redirect('voting:votacao_detail', pk=votacao_id)
        
        # Get the vote choice as integer (-1, 0, 1)
        voto_raw = request.POST.get('voto')
        try:
            voto_choice = int(voto_raw)
        except Exception:
            voto_choice = None
        if voto_choice not in (-1, 0, 1):
            messages.error(request, 'Opção de voto inválida.')
            return redirect('voting:votacao_detail', pk=votacao_id)

        # Get peso importance (1, 3, 8). Default to 1 if missing/invalid
        peso_raw = request.POST.get('peso')
        try:
            peso_val = int(peso_raw)
        except Exception:
            peso_val = 1
        if peso_val not in (1, 3, 8):
            peso_val = 1

        # Create the vote with weight
        Voto.objects.create(
            user=request.user,
            votacao=votacao,
            voto=voto_choice,
            peso=peso_val,
        )
        
        # Update user profile with vote record
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        profile.add_voto(votacao_id)
        
        label = {1: 'SIM', -1: 'NÃO', 0: 'ABSTENÇÃO'}.get(voto_choice, str(voto_choice))
        messages.success(request, f'Seu voto "{label}" foi registrado com sucesso!')
        return redirect('voting:votacao_detail', pk=votacao_id)

class DeleteVotoView(LoginRequiredMixin, View):
    """Handle deletion of the user's own vote for a specific voting session"""

    def post(self, request, votacao_id):
        votacao = get_object_or_404(VotacaoVoteBem, id=votacao_id)

        # Only allow deleting the authenticated user's own vote
        try:
            voto = Voto.objects.get(user=request.user, votacao=votacao)
        except Voto.DoesNotExist:
            messages.error(request, 'Você não possui voto registrado nesta votação.')
            return redirect('voting:votacao_detail', pk=votacao_id)

        # Delete the vote
        voto.delete()

        # Attempt to remove record from user profile votos_gravados
        try:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            ids = profile.get_votos_list()
            if votacao_id in ids:
                ids = [vid for vid in ids if vid != votacao_id]
                profile.votos_gravados = ''.join(f'{vid}.' for vid in ids)
                profile.save()
        except Exception:
            # Profile update is non-critical for deletion flow; ignore errors
            pass

        messages.success(request, 'Seu voto foi excluído. Você pode votar novamente.')
        return redirect('voting:votacao_detail', pk=votacao_id)

class MeusVotosView(LoginRequiredMixin, ListView):
    """List user's votes"""
    model = Voto
    template_name = 'voting/meus_votos.html'
    context_object_name = 'votos'
    paginate_by = 20
    
    def get_queryset(self):
        # Use updated path via ProposicaoVotacao -> Proposicao
        return (
            Voto.objects
            .filter(user=self.request.user)
            .select_related('votacao__proposicao_votacao__proposicao')
            .order_by('-created_at')
        )

class RankingView(ListView):
    """Show voting statistics and rankings"""
    model = VotacaoVoteBem
    template_name = 'voting/ranking.html'
    context_object_name = 'votacoes'
    paginate_by = 10
    
    def get_queryset(self):
        return VotacaoVoteBem.objects.annotate(
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
    """
    Personalized ranking view equivalent to vb14_RankingPersonalizado.php

    Enhancements:
    - Persist selected UFs in a cookie so users don't need to select every visit
    - Allow selecting multiple UFs and support a "select all states" option
    """
    model = Congressman
    template_name = 'voting/ranking_personalizado.html'
    context_object_name = 'congressmen_ranking'
    # Disable pagination to show all results as requested
    paginate_by = None

    # Valid Brazilian UFs list used for selection and validation
    AVAILABLE_UFS = [
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
        'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
        'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
    ]

    # Cookie name to store ranking UF selection
    COOKIE_NAME = 'ranking_ufs'
    COOKIE_MAX_AGE = 60 * 60 * 24 * 180  # 180 days

    def _resolve_selection(self, request):
        """
        Compute the selected UFs and whether "all" is selected, using this priority:
        1) Explicit GET params: multi-select 'ufs' and/or 'all=1'
        2) Cookie 'ranking_ufs': 'ALL' or comma-separated UFs
        3) User profile UF as a single default

        Returns (selected_ufs_list, all_selected_bool, should_set_cookie_bool)
        """
        # Read GET params
        raw_ufs = request.GET.getlist('ufs')
        single_uf = request.GET.get('uf')  # backward-compat single UF
        all_param = request.GET.get('all')

        # Normalize and validate UFs from GET
        selected_from_get = set()
        if single_uf:
            selected_from_get.add(single_uf.strip().upper())
        for uf in raw_ufs:
            selected_from_get.add(uf.strip().upper())
        selected_from_get = [uf for uf in selected_from_get if uf in self.AVAILABLE_UFS]

        # Determine if GET indicates 'all'
        all_selected_get = bool(all_param) and str(all_param) not in ('0', 'false', 'False')

        # If GET provided selection, we will set the cookie
        if all_selected_get or selected_from_get:
            return selected_from_get, all_selected_get, True

        # Otherwise, try cookie
        cookie_val = request.COOKIES.get(self.COOKIE_NAME)
        if cookie_val:
            if cookie_val.upper() == 'ALL':
                return [], True, False
            try:
                cookie_ufs = [uf.strip().upper() for uf in cookie_val.split(',') if uf.strip()]
                cookie_ufs = [uf for uf in cookie_ufs if uf in self.AVAILABLE_UFS]
                if cookie_ufs:
                    return cookie_ufs, False, False
            except Exception:
                # Ignore malformed cookie and fall back to profile
                pass

        # Fallback to user profile UF
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.uf in self.AVAILABLE_UFS:
                return [profile.uf], False, False
        except UserProfile.DoesNotExist:
            pass

        # No selection available
        return [], False, False

    def get(self, request, *args, **kwargs):
        """Compute selection upfront and persist to cookie when explicitly provided."""
        self.selected_ufs, self.all_selected, self.should_set_cookie = self._resolve_selection(request)
        response = super().get(request, *args, **kwargs)

        # Persist selection when provided via GET
        if self.should_set_cookie:
            cookie_value = 'ALL' if self.all_selected else ','.join(self.selected_ufs)
            response.set_cookie(
                self.COOKIE_NAME,
                cookie_value,
                max_age=self.COOKIE_MAX_AGE,
                samesite='Lax'
            )
        return response

    def get_queryset(self):
        """Filter congressmen by selected UFs, or all if requested; annotate scores."""
        user = self.request.user

        # No selection -> empty queryset until user chooses
        if not self.all_selected and not self.selected_ufs:
            return Congressman.objects.none()

        # Base queryset: either all active or active from selected UFs
        base_qs = Congressman.objects.filter(ativo=True)
        if not self.all_selected:
            base_qs = base_qs.filter(uf__in=self.selected_ufs)

        # Annotate with compatibility score and compared votes
        # Annotate ranking values and a normalized party string to ensure consistent grouping in the template.
        # The normalized party uses TRIM + UPPER and falls back to empty string when null using Value('').
        queryset = base_qs.annotate(
            total_score=Coalesce(
                Sum(
                    Case(
                        # When user voted 1 (SIM) and congressman voted 1 (SIM)
                        When(
                            congressmanvote__proposicao_votacao__votacaovotebem__voto__user=user,
                            congressmanvote__proposicao_votacao__votacaovotebem__voto__voto=1,
                            congressmanvote__voto=1,
                            then=F('congressmanvote__proposicao_votacao__votacaovotebem__voto__peso')
                        ),
                        # When user voted -1 (NAO) and congressman voted -1 (NAO)
                        When(
                            congressmanvote__proposicao_votacao__votacaovotebem__voto__user=user,
                            congressmanvote__proposicao_votacao__votacaovotebem__voto__voto=-1,
                            congressmanvote__voto=-1,
                            then=F('congressmanvote__proposicao_votacao__votacaovotebem__voto__peso')
                        ),
                        # When user voted 0 (ABSTENCAO) and congressman voted 0 (ABSTENCAO)
                        When(
                            congressmanvote__proposicao_votacao__votacaovotebem__voto__user=user,
                            congressmanvote__proposicao_votacao__votacaovotebem__voto__voto=0,
                            congressmanvote__voto=0,
                            then=F('congressmanvote__proposicao_votacao__votacaovotebem__voto__peso')
                        ),
                        # Abstention-equivalence: treat congressman voto 4 as matching user abstention (0)
                        When(
                            congressmanvote__proposicao_votacao__votacaovotebem__voto__user=user,
                            congressmanvote__proposicao_votacao__votacaovotebem__voto__voto=0,
                            congressmanvote__voto=4,
                            then=F('congressmanvote__proposicao_votacao__votacaovotebem__voto__peso')
                        ),
                        default=0,
                        output_field=IntegerField()
                    )
                ),
                0
            ),
            # Normalized party name for stable grouping in template (avoids duplicates like 'PT' vs 'pt' vs 'PT ').
            # Use Value('') explicitly to avoid ORM interpreting '' as a field name.
            partido_norm=Coalesce(
                Upper(Trim(F('partido'))),
                Value(''),
                output_field=CharField(),
            ),
            total_votes_compared=Count(
                'congressmanvote',
                filter=Q(congressmanvote__proposicao_votacao__votacaovotebem__voto__user=user)
            )
        ).filter(total_votes_compared__gt=0).order_by('-total_score', 'partido_norm', 'nome')

        return queryset

    def get_context_data(self, **kwargs):
        """Expose selection and helper values for the template UI and pagination."""
        context = super().get_context_data(**kwargs)

        # Selection info
        context['available_ufs'] = self.AVAILABLE_UFS
        context['selected_ufs'] = self.selected_ufs
        context['all_selected'] = self.all_selected

        # Build query string to preserve selection across pagination links
        # Build query preserving selection (no pagination parameters)
        query_parts = []
        if self.all_selected:
            query_parts.append('all=1')
        elif self.selected_ufs:
            query_parts.extend([f"ufs={uf}" for uf in self.selected_ufs])
        context['current_query'] = '&'.join(query_parts)

        return context
    # No get_paginate_by override needed (pagination disabled)

class CongressmanDetailView(LoginRequiredMixin, DetailView):
    """Congressman detail view equivalent to vb16_DetalheRanking.php"""
    model = Congressman
    template_name = 'voting/congressman_detail.html'
    context_object_name = 'congressman'
    pk_url_kwarg = 'congressman_id'
    
    def get_object(self):
        congressman_id = self.kwargs.get('congressman_id')
        # Buscar por id_cadastro (ID oficial da Câmara) ou por PK local
        # Isso evita 404 quando o usuário usa um ID diferente do esperado
        return get_object_or_404(
            Congressman,
            Q(id_cadastro=congressman_id) | Q(pk=congressman_id)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        congressman = self.get_object()
        user = self.request.user
        
        # Get detailed voting comparison between user and congressman
        # This is equivalent to the getDetalheRanking function in PHP
        voting_details = []
        accumulated_points = 0
        # Track total possible points considering user's weight (peso) per compared vote.
        # This allows computing a signed compatibility in [-100, 100].
        total_possible_points = 0
        
        # Get all propositions where both user and congressman voted
        user_votes = Voto.objects.filter(user=user).select_related('votacao__proposicao_votacao__proposicao')
        
        for user_vote in user_votes:
            try:
                congressman_vote = CongressmanVote.objects.get(
                    congressman=congressman,
                    proposicao_votacao=user_vote.votacao.proposicao_votacao
                )
                
                # Calculate points based on vote agreement, weighted by user's peso.
                # Also accumulate the total possible points (sum of pesos) for compared votes
                # so we can compute a signed percentage (agreement vs disagreement).
                try:
                    peso_val = getattr(user_vote, 'peso', 1) or 1
                except Exception:
                    peso_val = 1

                # Every compared vote contributes its weight to the total possible points
                total_possible_points += peso_val

                # If votes match, add the weight to the accumulated points; otherwise add 0
                points = 0
                try:
                    # Ignore sentinel 2 ("Não Compareceu") when comparing congressman vs user vote
                    # Only consider real votes (-1, 0, 1) when comparing; ignore dummy (2) and absence (3)
                    # Abstention-equivalence: treat congressman voto 4 as abstention (0) for comparisons.
                    if congressman_vote.voto in (-1, 0, 1) and user_vote.voto == congressman_vote.voto:
                        points = peso_val
                    elif congressman_vote.voto == 4 and user_vote.voto == 0:
                        points = peso_val
                except Exception:
                    points = 0
                
                accumulated_points += points
                
                voting_details.append({
                    'titulo': user_vote.votacao.titulo,
                    # Adiciona resumo e id da VotacaoVoteBem para link local
                    'resumo': getattr(user_vote.votacao, 'resumo', ''),
                    'votacao_id': user_vote.votacao.id,
                    'ementa': user_vote.votacao.proposicao_votacao.proposicao.ementa,
                    'id_proposicao': user_vote.votacao.proposicao_votacao.proposicao.id_proposicao,
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
        # Total weighted points possible (denominator for signed compatibility)
        context['total_possible_points'] = total_possible_points
        # Total de votações comparadas (denominador para compatibilidade)
        context['total_votacoes_comparadas'] = len(voting_details)
        # Compatibilidade: acumulado / total comparações * 100, limitado a 100%
        try:
            total = context['total_votacoes_comparadas']
            if total > 0:
                pct = int(round((accumulated_points * 100.0) / total))
                context['compatibility_pct'] = min(100, pct)
            else:
                context['compatibility_pct'] = 0
        except Exception:
            context['compatibility_pct'] = 0
        
        # Signed compatibility percentage in [-100, 100] using weights (peso):
        # formula => 100 * (agreements - disagreements) / total_weight
        # which equals 100 * (2*agreements - total_weight) / total_weight
        try:
            denom = total_possible_points
            if denom and denom > 0:
                signed_pct = int(round(((accumulated_points * 2 - denom) * 100.0) / denom))
                # Clamp to [-100, 100]
                signed_pct = max(-100, min(100, signed_pct))
                context['signed_compatibility_pct'] = signed_pct
                # Compute a red→green gradient color based on signed percentage
                context['compatibility_color'] = self._gradient_color(signed_pct)
            else:
                context['signed_compatibility_pct'] = 0
                context['compatibility_color'] = self._gradient_color(0)
        except Exception:
            context['signed_compatibility_pct'] = 0
            context['compatibility_color'] = self._gradient_color(0)
        context['congressman_photo_url'] = congressman.get_foto_url()
        
        return context

    def _gradient_color(self, signed_pct: int) -> str:
        """
        Map signed compatibility percentage [-100, 100] to a red→green gradient.

        -100 → red (hue 0), 0 → yellow-ish (hue ~60), 100 → green (hue 120).
        Returns a CSS color string using HSL for smooth gradients.
        """
        try:
            val = max(-100, min(100, int(round(signed_pct))))
        except Exception:
            val = 0
        # Normalize to [0,1] and map to hue [0,120]
        # -100 => 0.0 => hue 0 (red)
        # +100 => 1.0 => hue 120 (green)
        normalized = (val + 100) / 200.0
        hue = int(round(120 * normalized))
        # Use high saturation and medium-lightness for visibility
        return f"hsl({hue}, 80%, 40%)"


class VotacoesPesquisaView(ListView):
    """Public search/list that supports Votações and Proposições via 'target' param (DRY)."""
    model = VotacaoVoteBem
    template_name = 'voting/votacoes_pesquisa.html'
    context_object_name = 'votacoes'
    paginate_by = 25

    def get_queryset(self):
        target = self.request.GET.get('target', 'votacoes')
        q = self.request.GET.get('q')
        tipo = self.request.GET.get('tipo')
        ano = self.request.GET.get('ano')
        ativo = self.request.GET.get('ativo')

        if target == 'proposicoes':
            # Search Proposicao table
            qs = Proposicao.objects.order_by('-created_at')
            if q:
                qs = qs.filter(
                    Q(titulo__icontains=q) |
                    Q(ementa__icontains=q)
                )
            if tipo:
                qs = qs.filter(tipo=tipo)
            if ano:
                try:
                    qs = qs.filter(ano=int(ano))
                except ValueError:
                    pass
            return qs
        else:
            # Default: search VotacaoVoteBem table
            qs = VotacaoVoteBem.objects.select_related('proposicao_votacao__proposicao').order_by('-no_ar_desde')
            if q:
                qs = qs.filter(
                    Q(titulo__icontains=q) |
                    Q(resumo__icontains=q) |
                    Q(proposicao_votacao__proposicao__titulo__icontains=q) |
                    Q(proposicao_votacao__proposicao__ementa__icontains=q)
                )
            if tipo:
                qs = qs.filter(proposicao_votacao__proposicao__tipo=tipo)
            if ano:
                try:
                    qs = qs.filter(proposicao_votacao__proposicao__ano=int(ano))
                except ValueError:
                    pass
            if ativo == 'sim':
                qs = qs.filter(ativo=True)
            elif ativo == 'nao':
                qs = qs.filter(ativo=False)
            return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.request.GET.get('target', 'votacoes')
        context['is_proposicoes'] = (target == 'proposicoes')
        context['target'] = target

        # Distinct tipos and anos for filters according to target
        if context['is_proposicoes']:
            tipos = list(
                Proposicao.objects.values_list('tipo', flat=True).distinct()
            )
            anos = list(
                Proposicao.objects.values_list('ano', flat=True).distinct()
            )
        else:
            tipos = list(
                VotacaoVoteBem.objects.values_list('proposicao_votacao__proposicao__tipo', flat=True)
                .distinct()
            )
            anos = list(
                VotacaoVoteBem.objects.values_list('proposicao_votacao__proposicao__ano', flat=True)
                .distinct()
            )

        context['tipos'] = sorted([t for t in tipos if t])
        context['anos'] = sorted([a for a in anos if a])
        # Preserve current filters
        context['q'] = self.request.GET.get('q', '')
        context['tipo_sel'] = self.request.GET.get('tipo', '')
        context['ano_sel'] = self.request.GET.get('ano', '')
        context['ativo_sel'] = self.request.GET.get('ativo', '')
        # Ensure template always has 'votacoes' list, regardless of target
        context['votacoes'] = context.get('object_list', [])
        return context

"""
Public subpage with official votes, filters and stats (client-side).
Accepts GET `votacao_id`, which can be either:
- `VotacaoVoteBem.id` (preferred), or
- `ProposicaoVotacao.id` (fallback when no VoteBem exists).
"""
def votos_oficiais_app_public(request):
    votacao_id = request.GET.get('votacao_id')
    votacao = None
    pv = None
    votos_data = []
    if votacao_id:
        try:
            vid = int(votacao_id)
        except (TypeError, ValueError):
            vid = None

        if vid is not None:
            # Try loading by VotacaoVoteBem.id first
            try:
                votacao = (
                    VotacaoVoteBem.objects
                    .select_related('proposicao_votacao__proposicao')
                    .get(pk=vid)
                )
                pv = votacao.proposicao_votacao
                registros = (
                    CongressmanVote.objects
                    .select_related('congressman')
                    .filter(proposicao_votacao=votacao.proposicao_votacao)
                )
            except VotacaoVoteBem.DoesNotExist:
                # Fallback: treat id as ProposicaoVotacao.id
                try:
                    pv = ProposicaoVotacao.objects.select_related('proposicao').get(pk=vid)
                    # If any VotacaoVoteBem exists for this PV, use it to populate header
                    votacao = (
                        VotacaoVoteBem.objects
                        .select_related('proposicao_votacao__proposicao')
                        .filter(proposicao_votacao=pv)
                        .first()
                    )
                    registros = (
                        CongressmanVote.objects
                        .select_related('congressman')
                        .filter(proposicao_votacao=pv)
                    )
                except ProposicaoVotacao.DoesNotExist:
                    registros = []
            except Exception:
                registros = []
            # Serialize votes
            for r in registros:
                votos_data.append({
                    'nome': r.congressman.nome,
                    'id_cadastro': r.congressman.id_cadastro,
                    'partido': r.congressman.partido or '',
                    'uf': r.congressman.uf or '',
                    'voto': r.get_voto_display_text(),
                })

    context = {
        'votacao': votacao,
        'pv': pv,
        'votos_json': json.dumps(votos_data, ensure_ascii=False),
    }
    return render(request, 'voting/votos_oficiais_app.html', context)

def referencias_list_public(request):
    pv_id = request.GET.get('pv_id')
    vv_id = request.GET.get('vv_id')
    pv = None
    vv = None
    if vv_id:
        try:
            vv = VotacaoVoteBem.objects.select_related('proposicao_votacao__proposicao').get(pk=int(vv_id))
        except Exception:
            vv = None
    if pv_id and not vv:
        try:
            pv = ProposicaoVotacao.objects.select_related('proposicao').get(pk=int(pv_id))
        except Exception:
            pv = None
    if not pv and not vv:
        return JsonResponse({'ok': False, 'error': 'Parâmetro pv_id ou vv_id é obrigatório.'}, status=400)
    if vv and not pv:
        pv = vv.proposicao_votacao
    qs = Referencia.objects.filter(proposicao_votacao=pv)
    if vv:
        qs = qs.filter(models.Q(votacao_votebem__isnull=True) | models.Q(votacao_votebem=vv))
    refs = qs.select_related('divulgador').order_by('-created_at')
    dados = []
    for r in refs:
        dados.append({
            'id': r.id,
            'url': r.url,
            'kind': r.kind,
            'title': r.title or '',
            'created_at': r.created_at.isoformat() if hasattr(r.created_at, 'isoformat') else str(r.created_at),
            'divulgador': ({
                'id': r.divulgador_id,
                'alias': r.divulgador.alias if r.divulgador and r.divulgador.alias else '',
                'icon_url': r.divulgador.icon_url if r.divulgador and r.divulgador.icon_url else '',
            } if r.divulgador_id else None),
        })
    return JsonResponse({'ok': True, 'pv_id': pv.id if pv else None, 'vv_id': vv.id if vv else None, 'dados': dados})

def _get_divulgador_for_user(user):
    from .models import Divulgador
    if not user or not getattr(user, 'email', None):
        return None
    try:
        return Divulgador.objects.select_related('user').get(email__iexact=user.email.strip())
    except Divulgador.DoesNotExist:
        return None

@login_required
def opinar(request):
    divulgador = _get_divulgador_for_user(request.user)
    if not divulgador:
        messages.error(request, 'Você não está cadastrado como divulgador.')
        return redirect('voting:votacoes_disponiveis')
    now = timezone.now()
    votacoes = (
        VotacaoVoteBem.objects
        .select_related('proposicao_votacao__proposicao')
        .annotate(
            sort_order_is_null=Case(
                When(sort_order__isnull=True, then=1),
                default=0,
                output_field=IntegerField(),
            )
        )
        .order_by('sort_order_is_null', 'sort_order', '-data_hora_votacao')
    )
    # Map existing referencia per vv for this divulgador
    refs = (
        Referencia.objects
        .filter(divulgador=divulgador)
        .select_related('votacao_votebem')
    )
    ref_by_vv = {r.votacao_votebem_id: r for r in refs if r.votacao_votebem_id}
    return render(request, 'voting/opinar.html', {
        'votacoes': votacoes,
        'divulgador': divulgador,
        'ref_by_vv': ref_by_vv,
        'now': now,
    })

@login_required
def opinar_referencia_save(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)
    divulgador = _get_divulgador_for_user(request.user)
    if not divulgador:
        return JsonResponse({'ok': False, 'error': 'Usuário não é divulgador.'}, status=403)
    vv_id = request.POST.get('vv_id')
    title = (request.POST.get('title') or '').strip()
    url = (request.POST.get('url') or '').strip()
    if not vv_id:
        return JsonResponse({'ok': False, 'error': 'vv_id é obrigatório.'}, status=400)
    try:
        vv = VotacaoVoteBem.objects.select_related('proposicao_votacao').get(pk=int(vv_id))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Votação inválida.'}, status=404)
    if not url:
        return JsonResponse({'ok': False, 'error': 'URL é obrigatória.'}, status=400)
    ref, created = Referencia.objects.get_or_create(
        divulgador=divulgador,
        votacao_votebem=vv,
        defaults={
            'proposicao_votacao': vv.proposicao_votacao,
            'url': url,
            'kind': Referencia.Kind.SOCIAL_MEDIA if 'youtu' in url else Referencia.Kind.WEB_PAGE,
            'title': title or None,
        }
    )
    if not created:
        ref.url = url
        ref.title = title or None
        ref.kind = Referencia.Kind.SOCIAL_MEDIA if 'youtu' in url else Referencia.Kind.WEB_PAGE
        ref.save(update_fields=['url', 'title', 'kind', 'updated_at'])
    return JsonResponse({'ok': True, 'ref_id': ref.id})

@login_required
def opinar_referencia_delete(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)
    divulgador = _get_divulgador_for_user(request.user)
    if not divulgador:
        return JsonResponse({'ok': False, 'error': 'Usuário não é divulgador.'}, status=403)
    vv_id = request.POST.get('vv_id')
    if not vv_id:
        return JsonResponse({'ok': False, 'error': 'vv_id é obrigatório.'}, status=400)
    try:
        ref = Referencia.objects.get(divulgador=divulgador, votacao_votebem_id=int(vv_id))
    except Referencia.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Referência não encontrada.'}, status=404)
    ref.delete()
    return JsonResponse({'ok': True})
