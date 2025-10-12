from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q
from .models import Enquete, RespostaEnquete
from voting.models import Proposicao, VotacaoDisponivel
from .forms import EnqueteForm, RespostaEnqueteForm

class EnqueteListView(ListView):
    """List published polls"""
    model = Enquete
    template_name = 'polls/enquete_list.html'
    context_object_name = 'enquetes'
    paginate_by = 20
    
    def get_queryset(self):
        return Enquete.objects.filter(estado=10).select_related('autor', 'proposicao').order_by('-criada_em')

class MinhasEnquetesView(LoginRequiredMixin, ListView):
    """List user's own polls"""
    model = Enquete
    template_name = 'polls/minhas_enquetes.html'
    context_object_name = 'enquetes'
    paginate_by = 20
    
    def get_queryset(self):
        return Enquete.objects.filter(autor=self.request.user).select_related('proposicao').order_by('estado', 'criada_em')

class EnqueteDetailView(DetailView):
    """Detail view for a specific poll"""
    model = Enquete
    template_name = 'polls/enquete_detail.html'
    context_object_name = 'enquete'
    
    def get_queryset(self):
        # Show published polls to everyone, but allow authors to see their own unpublished polls
        if self.request.user.is_authenticated:
            return Enquete.objects.filter(
                Q(estado=10) | Q(autor=self.request.user)
            ).select_related('autor', 'proposicao')
        else:
            return Enquete.objects.filter(estado=10).select_related('autor', 'proposicao')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enquete = self.get_object()
        
        # Check if user has already responded
        user_response = None
        if self.request.user.is_authenticated:
            try:
                user_response = RespostaEnquete.objects.get(user=self.request.user, enquete=enquete)
            except RespostaEnquete.DoesNotExist:
                pass
        
        context['user_response'] = user_response
        context['can_respond'] = enquete.is_published() and user_response is None and self.request.user.is_authenticated
        if context['can_respond']:
            # Provide the response form to the template
            context['form'] = RespostaEnqueteForm()
        
        # Get response statistics
        context['total_respostas'] = enquete.get_total_respostas()
        context['respostas_sim'] = enquete.get_respostas_sim()
        context['respostas_nao'] = enquete.get_respostas_nao()
        context['percentual_sim'] = enquete.get_percentual_sim()
        context['percentual_nao'] = enquete.get_percentual_nao()

        # Related voting and proposition external URL
        votacao_relacionada = None
        proposicao_url = None
        if enquete.proposicao:
            votacao_relacionada = (
                VotacaoDisponivel.objects
                .filter(proposicao=enquete.proposicao)
                .order_by('-ativo', '-no_ar_desde', '-created_at')
                .first()
            )
            if enquete.proposicao.id_proposicao:
                proposicao_url = (
                    f"http://www.camara.gov.br/proposicoesWeb/fichadetramitacao?idProposicao={enquete.proposicao.id_proposicao}"
                )
        context['votacao_relacionada'] = votacao_relacionada
        context['proposicao_url'] = proposicao_url
        
        return context

class EnqueteCreateView(LoginRequiredMixin, CreateView):
    """Create a new poll"""
    model = Enquete
    form_class = EnqueteForm
    template_name = 'polls/enquete_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        proposicao_id = self.kwargs.get('proposicao_id')
        if proposicao_id:
            initial['proposicao'] = proposicao_id
        return initial
    
    def form_valid(self, form):
        form.instance.autor = self.request.user
        messages.success(self.request, 'Enquete criada com sucesso!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('polls:enquete_detail', kwargs={'pk': self.object.pk})

class EnqueteUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing poll"""
    model = Enquete
    form_class = EnqueteForm
    template_name = 'polls/enquete_form.html'
    
    def get_queryset(self):
        # Only allow authors to edit their own polls
        return Enquete.objects.filter(autor=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Enquete atualizada com sucesso!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('polls:enquete_detail', kwargs={'pk': self.object.pk})

class EnqueteDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a poll"""
    model = Enquete
    template_name = 'polls/enquete_confirm_delete.html'
    success_url = reverse_lazy('polls:minhas_enquetes')
    
    def get_queryset(self):
        # Only allow authors to delete their own polls
        return Enquete.objects.filter(autor=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Enquete excluída com sucesso!')
        return super().delete(request, *args, **kwargs)

class ResponderEnqueteView(LoginRequiredMixin, View):
    """Handle poll response"""
    
    def post(self, request, enquete_id):
        enquete = get_object_or_404(Enquete, id=enquete_id, estado=10)
        
        # Check if user has already responded
        if RespostaEnquete.objects.filter(user=request.user, enquete=enquete).exists():
            messages.error(request, 'Você já respondeu a esta enquete.')
            return redirect('polls:enquete_detail', pk=enquete_id)
        
        # Get the response choice
        resposta_choice = request.POST.get('resposta')
        if resposta_choice not in ['SIM', 'NAO', 'NEUTRO']:
            messages.error(request, 'Opção de resposta inválida.')
            return redirect('polls:enquete_detail', pk=enquete_id)
        
        # Get optional comment
        comentario = request.POST.get('comentario', '').strip()
        
        # Create the response
        RespostaEnquete.objects.create(
            user=request.user,
            enquete=enquete,
            resposta=resposta_choice,
            comentario=comentario if comentario else None
        )
        
        messages.success(request, f'Sua resposta "{resposta_choice}" foi registrada com sucesso!')
        return redirect('polls:enquete_detail', pk=enquete_id)
