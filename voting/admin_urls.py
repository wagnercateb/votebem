"""
URLs for the administrative interface (administrativo namespace)
"""
from django.urls import path
from . import admin_views

app_name = 'gerencial'

urlpatterns = [
    # Dashboard
    path('dashboard/', admin_views.admin_dashboard, name='dashboard'),
    
    # Proposições
    path('proposicoes/statistics/', admin_views.proposicoes_statistics, name='proposicoes_statistics'),
    path('proposicoes/list/', admin_views.proposicoes_list, name='proposicoes_list'),
    path('proposicao/add/', admin_views.proposicao_add, name='proposicao_add'),
    path('proposicao/<int:pk>/edit/', admin_views.proposicao_edit, name='proposicao_edit'),
    path('votacao/<int:pk>/edit/', admin_views.votacao_edit, name='votacao_edit'),
    
    # Votações
    path('votacoes/management/', admin_views.votacoes_management, name='votacoes_management'),
    path('votacoes/list/', admin_views.votacoes_management, name='votacoes_list'),  # Placeholder
    path('votacao/create/', admin_views.votacoes_management, name='votacao_create'),  # Placeholder
    
    # Usuários
    path('users/management/', admin_views.users_management, name='users_management'),
    path('users/list/', admin_views.users_management, name='users_list'),  # Placeholder
    path('users/profiles/', admin_views.users_management, name='users_profiles'),  # Placeholder
    
    # Congressistas
    path('congressistas/list/', admin_views.users_management, name='congressistas_list'),  # Placeholder
    path('congressista/create/', admin_views.users_management, name='congressista_create'),  # Placeholder
    path('votos/oficiais/', admin_views.users_management, name='votos_oficiais'),  # Placeholder
    
    # Dados
    path('data/import-export/', admin_views.data_import_export, name='data_import_export'),
    path('votos/populares/', admin_views.data_import_export, name='votos_populares'),  # Placeholder
    
    # Enquetes
    path('enquetes/list/', admin_views.data_import_export, name='enquetes_list'),  # Placeholder
    path('enquetes/respostas/', admin_views.data_import_export, name='enquetes_respostas'),  # Placeholder
    path('enquete/create/', admin_views.data_import_export, name='enquete_create'),  # Placeholder
    
    # AJAX endpoints
    path('camara-admin/', admin_views.camara_admin, name='camara_admin'),
    path('ajax/proposicao-search/', admin_views.ajax_proposicao_search, name='ajax_proposicao_search')
]