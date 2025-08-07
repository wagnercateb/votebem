from django.contrib import admin
from .models import Proposicao, VotacaoDisponivel, Voto

@admin.register(Proposicao)
class ProposicaoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo', 'created_at']
    list_filter = ['tipo', 'created_at']
    search_fields = ['titulo', 'ementa']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(VotacaoDisponivel)
class VotacaoDisponivelAdmin(admin.ModelAdmin):
    list_display = ['proposicao', 'ativo', 'no_ar_desde', 'no_ar_ate', 'total_votos']
    list_filter = ['ativo', 'no_ar_desde', 'no_ar_ate']
    search_fields = ['proposicao__titulo', 'titulo']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['ativo']
    
    def total_votos(self, obj):
        return obj.voto_set.count()
    total_votos.short_description = 'Total de Votos'

@admin.register(Voto)
class VotoAdmin(admin.ModelAdmin):
    list_display = ['user', 'votacao', 'voto', 'created_at']
    list_filter = ['voto', 'created_at', 'votacao__proposicao']
    search_fields = ['user__username', 'votacao__proposicao__titulo']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'votacao__proposicao')
