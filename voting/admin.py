from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Proposicao, ProposicaoVotacao, VotacaoDisponivel, Voto, Congressman, CongressmanVote

@admin.register(Proposicao)
class ProposicaoAdmin(admin.ModelAdmin):
    list_display = ['id_proposicao', 'titulo_truncado', 'tipo', 'numero', 'ano', 'autor', 'estado', 'created_at']
    list_filter = ['tipo', 'ano', 'estado', 'created_at']
    search_fields = ['titulo', 'ementa', 'autor', 'id_proposicao']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 50
    inlines = []
    
    def titulo_truncado(self, obj):
        return obj.titulo[:80] + "..." if len(obj.titulo) > 80 else obj.titulo
    titulo_truncado.short_description = 'Título'

class ProposicaoVotacaoInline(admin.TabularInline):
    model = ProposicaoVotacao
    extra = 0
    fields = ['votacao_sufixo', 'descricao']
    readonly_fields = []

# Attach inline to ProposicaoAdmin
ProposicaoAdmin.inlines = [ProposicaoVotacaoInline]

@admin.register(ProposicaoVotacao)
class ProposicaoVotacaoAdmin(admin.ModelAdmin):
    list_display = ['proposicao', 'votacao_sufixo', 'descricao', 'created_at']
    list_filter = ['proposicao__tipo', 'proposicao__ano']
    search_fields = ['proposicao__titulo', 'proposicao__id_proposicao', 'descricao']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(VotacaoDisponivel)
class VotacaoDisponivelAdmin(admin.ModelAdmin):
    list_display = ['titulo_truncado', 'proposicao_link', 'ativo', 'no_ar_desde', 'no_ar_ate', 'total_votos_populares', 'votos_oficiais']
    # Atualizado: referenciar via proposicao_votacao -> proposicao
    list_filter = ['ativo', 'no_ar_desde', 'no_ar_ate', 'proposicao_votacao__proposicao__tipo']
    search_fields = ['proposicao_votacao__proposicao__titulo', 'titulo', 'proposicao_votacao__proposicao__id_proposicao']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['ativo']
    date_hierarchy = 'no_ar_desde'
    
    def titulo_truncado(self, obj):
        return obj.titulo[:60] + "..." if len(obj.titulo) > 60 else obj.titulo
    titulo_truncado.short_description = 'Título da Votação'
    
    def proposicao_link(self, obj):
        # Exibe link para a Proposição via ProposicaoVotacao, se disponível
        if obj.proposicao_votacao and obj.proposicao_votacao.proposicao:
            prop = obj.proposicao_votacao.proposicao
            url = reverse('admin:voting_proposicao_change', args=[prop.pk])
            return format_html('<a href="{}">{}</a>', url, str(prop)[:50])
        return "—"
    proposicao_link.short_description = 'Proposição'
    
    def total_votos_populares(self, obj):
        return obj.get_total_votos_populares()
    total_votos_populares.short_description = 'Votos Populares'
    
    def votos_oficiais(self, obj):
        return f"SIM: {obj.sim_oficial} | NÃO: {obj.nao_oficial}"
    votos_oficiais.short_description = 'Votação oficial'

@admin.register(Voto)
class VotoAdmin(admin.ModelAdmin):
    list_display = ['user', 'votacao_link', 'voto', 'created_at']
    # Atualizado: caminho via votacao -> proposicao_votacao -> proposicao
    list_filter = ['voto', 'created_at', 'votacao__proposicao_votacao__proposicao__tipo']
    search_fields = ['user__username', 'user__email', 'votacao__proposicao_votacao__proposicao__titulo']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def votacao_link(self, obj):
        url = reverse('admin:voting_votacaodisponivel_change', args=[obj.votacao.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.votacao)[:50])
    votacao_link.short_description = 'Votação'
    
    def get_queryset(self, request):
        # Otimiza com select_related seguindo nova relação
        return super().get_queryset(request).select_related('user', 'votacao__proposicao_votacao__proposicao')

@admin.register(Congressman)
class CongressmanAdmin(admin.ModelAdmin):
    list_display = ['nome', 'partido', 'uf', 'ativo', 'total_votos', 'foto_preview', 'created_at']
    list_filter = ['partido', 'uf', 'ativo', 'created_at']
    search_fields = ['nome', 'partido', 'id_cadastro']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['ativo']
    list_per_page = 100
    
    def total_votos(self, obj):
        return obj.congressmanvote_set.count()
    total_votos.short_description = 'Total de Votos'
    
    def foto_preview(self, obj):
        if obj.foto_url or obj.id_cadastro:
            foto_url = obj.get_foto_url()
            return format_html('<img src="{}" width="30" height="30" style="border-radius: 50%;" />', foto_url)
        return "Sem foto"
    foto_preview.short_description = 'Foto'

@admin.register(CongressmanVote)
class CongressmanVoteAdmin(admin.ModelAdmin):
    list_display = ['congressman', 'proposicao_link', 'voto_display', 'created_at']
    # Atualizado: referenciar tipo/título via proposicao_votacao -> proposicao
    list_filter = ['voto', 'created_at', 'congressman__partido', 'congressman__uf', 'proposicao_votacao__proposicao__tipo']
    search_fields = ['congressman__nome', 'proposicao_votacao__proposicao__titulo', 'proposicao_votacao__proposicao__id_proposicao']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def proposicao_link(self, obj):
        # Link seguro para a Proposição através da relação nova
        if obj.proposicao_votacao and obj.proposicao_votacao.proposicao:
            prop = obj.proposicao_votacao.proposicao
            url = reverse('admin:voting_proposicao_change', args=[prop.pk])
            return format_html('<a href="{}">{}</a>', url, str(prop)[:50])
        return "—"
    proposicao_link.short_description = 'Proposição'
    
    def voto_display(self, obj):
        return obj.get_voto_display_text()
    voto_display.short_description = 'Voto'
    
    def get_queryset(self, request):
        # Ajusta select_related para nova FK
        return super().get_queryset(request).select_related('congressman', 'proposicao_votacao__proposicao')
