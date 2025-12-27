from django.urls import path
from . import views

app_name = 'voting'

urlpatterns = [
    path('', views.VotacoesDisponiveisView.as_view(), name='votacoes_disponiveis'),
    # Alias para a rota antiga/esperada: /voting/votacoes_disponiveis/
    path('votacoes_disponiveis/', views.VotacoesDisponiveisView.as_view(), name='votacoes_disponiveis_legacy'),
    path('pesquisar/', views.VotacoesPesquisaView.as_view(), name='votacoes_pesquisa'),
    path('votacao/<int:pk>/', views.VotacaoDetailView.as_view(), name='votacao_detail'),
    path('votar/<int:votacao_id>/', views.VotarView.as_view(), name='votar'),
    path('votar/<int:votacao_id>/delete/', views.DeleteVotoView.as_view(), name='voto_delete'),
    path('meus-votos/', views.MeusVotosView.as_view(), name='meus_votos'),
    # Exibir o Ranking Personalizado em /voting/ranking/
    path('ranking/', views.PersonalizedRankingView.as_view(), name='ranking'),
    path('ranking-personalizado/', views.PersonalizedRankingView.as_view(), name='ranking_personalizado'),
    # Ajuste do parâmetro para combinar com pk_url_kwarg='congressman_id' na view
    path('congressman/<int:congressman_id>/', views.CongressmanDetailView.as_view(), name='congressman_detail'),
    # Public subpage for official votes via app
    path('votos/oficiais/', views.votos_oficiais_app_public, name='votos_oficiais_app'),
    path('referencias/list/', views.referencias_list_public, name='referencias_list_public'),
]
