from django.urls import path
from . import views

app_name = 'voting'

urlpatterns = [
    path('', views.VotacoesDisponiveisView.as_view(), name='votacoes_disponiveis'),
    path('votacao/<int:pk>/', views.VotacaoDetailView.as_view(), name='votacao_detail'),
    path('votar/<int:votacao_id>/', views.VotarView.as_view(), name='votar'),
    path('meus-votos/', views.MeusVotosView.as_view(), name='meus_votos'),
    path('ranking/', views.RankingView.as_view(), name='ranking'),
    path('ranking-personalizado/', views.PersonalizedRankingView.as_view(), name='ranking_personalizado'),
    path('congressman/<int:pk>/', views.CongressmanDetailView.as_view(), name='congressman_detail'),
]