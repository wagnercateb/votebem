from django.contrib import admin
from .models import Enquete, RespostaEnquete

@admin.register(Enquete)
class EnqueteAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'autor', 'proposicao', 'estado', 'total_respostas', 'criada_em']
    list_filter = ['estado', 'criada_em', 'proposicao']
    search_fields = ['titulo', 'pergunta', 'autor__username']
    readonly_fields = ['criada_em', 'atualizada_em']
    list_editable = ['estado']
    
    def total_respostas(self, obj):
        return obj.get_total_respostas()
    total_respostas.short_description = 'Total de Respostas'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('autor', 'proposicao')

@admin.register(RespostaEnquete)
class RespostaEnqueteAdmin(admin.ModelAdmin):
    list_display = ['user', 'enquete', 'resposta', 'tem_comentario', 'created_at']
    list_filter = ['resposta', 'created_at', 'enquete__proposicao']
    search_fields = ['user__username', 'enquete__titulo', 'comentario']
    readonly_fields = ['created_at']
    
    def tem_comentario(self, obj):
        return bool(obj.comentario)
    tem_comentario.boolean = True
    tem_comentario.short_description = 'Tem Comentário'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'enquete__proposicao')
