"""
Administrative URL configuration (namespace: `gerencial`).

This module now applies route-level access control by wrapping every
administrative endpoint with `staff_member_required`. This ensures that
only authenticated users with `is_staff=True` can access any URL under
`/gerencial/`, without relying on global middleware path interception.

Why this approach:
- Keeps authorization closest to the resource (each route).
- Avoids accidental redirects or interference with unrelated pages.
- Plays nicely with CSRF and diagnostics.

Notes:
- Several views in `admin_views.py` already use `@staff_member_required`
  or a custom `@admin_required` decorator; wrapping here is intentionally
  redundant for defense-in-depth and consistency.
"""
from django.urls import path
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.conf import settings
from . import admin_views

app_name = 'gerencial'

urlpatterns = [
    # Root subpage for Votação oficial via App
    # Root subpage for Votação oficial via App
    # Route-level gate: requires authenticated staff
    path('', staff_member_required(admin_views.votos_oficiais_app), name='votos_oficiais_app'),
    # Dashboard
    path('dashboard/', staff_member_required(admin_views.admin_dashboard), name='dashboard'),
    
    # Proposições
    path('proposicoes/statistics/', staff_member_required(admin_views.proposicoes_statistics), name='proposicoes_statistics'),
    path('proposicoes/list/', staff_member_required(admin_views.proposicoes_list), name='proposicoes_list'),
    path('proposicao/add/', staff_member_required(admin_views.proposicao_add), name='proposicao_add'),
    path('proposicao/import/', staff_member_required(admin_views.proposicao_import), name='proposicao_import'),
    path('proposicao/edit/', staff_member_required(admin_views.proposicao_edit_choose), name='proposicao_edit_choose'),
    path('proposicao/<int:pk>/edit/', staff_member_required(admin_views.proposicao_edit), name='proposicao_edit'),
    path('proposicoes/atualizar-temas/', staff_member_required(admin_views.proposicoes_atualizar_temas), name='proposicoes_atualizar_temas'),
    path('votacao/<int:pk>/edit/', staff_member_required(admin_views.votacao_edit), name='votacao_edit'),
    
    # Votações
    path('votacoes/management/', staff_member_required(admin_views.votacoes_management), name='votacoes_management'),
    path('votacoes/list/', staff_member_required(admin_views.votacoes_management), name='votacoes_list'),  # Placeholder
    path('proposicao-votacoes/management/', staff_member_required(admin_views.proposicao_votacoes_management), name='proposicao_votacoes_management'),
    # Lista votações oficiais armazenadas (ProposicaoVotacao) com contagem de votos individuais
    path('votacoes/oficiais/', staff_member_required(admin_views.votacoes_oficiais_list), name='votacoes_oficiais_list'),
    path('votacao/create/', staff_member_required(admin_views.votacao_create), name='votacao_create'),
    path('votacao/<int:pk>/obter-votacao/', staff_member_required(admin_views.votacao_obter_votacao), name='votacao_obter_votacao'),
    # Nova tela: obter votações por período
    path('votacoes/por-periodo/', staff_member_required(admin_views.votacoes_por_periodo), name='votacoes_por_periodo'),
    
    # Usuários
    path('users/management/', staff_member_required(admin_views.users_management), name='users_management'),
    path('users/list/', staff_member_required(admin_views.users_management), name='users_list'),  # Placeholder
    path('users/profiles/', staff_member_required(admin_views.users_management), name='users_profiles'),  # Placeholder

    # Congressistas
    path('congressistas/list/', staff_member_required(admin_views.users_management), name='congressistas_list'),  # Placeholder
    path('congressista/create/', staff_member_required(admin_views.users_management), name='congressista_create'),  # Placeholder
    path('votos/oficiais/', staff_member_required(admin_views.users_management), name='votos_oficiais'),  # Placeholder
    path('congressistas/update/', staff_member_required(admin_views.congressistas_update), name='congressistas_update'),
    
    # Dados
    path('data/import-export/', staff_member_required(admin_views.data_import_export), name='data_import_export'),
    path('votos/populares/', staff_member_required(admin_views.data_import_export), name='votos_populares'),  # Placeholder
    
    # Enquetes
    path('enquetes/list/', staff_member_required(admin_views.data_import_export), name='enquetes_list'),  # Placeholder
    path('enquetes/respostas/', staff_member_required(admin_views.data_import_export), name='enquetes_respostas'),  # Placeholder
    path('enquete/create/', staff_member_required(admin_views.data_import_export), name='enquete_create'),  # Placeholder
    
    # AJAX endpoints
    path('camara-admin/', staff_member_required(admin_views.camara_admin), name='camara_admin'),
    path('ajax/proposicao-search/', staff_member_required(admin_views.ajax_proposicao_search), name='ajax_proposicao_search')
    ,
    path('ajax/proposicao-votacoes/', staff_member_required(admin_views.ajax_proposicao_votacoes), name='ajax_proposicao_votacoes')
    ,
    path('ajax/import-congress-votes/', staff_member_required(admin_views.ajax_import_congress_votes), name='ajax_import_congress_votes')
    ,
    path('ajax/proposicao-votacao/update-prioridade/', staff_member_required(admin_views.ajax_update_proposicao_votacao_prioridade), name='ajax_update_proposicao_votacao_prioridade')
    ,
    path('ajax/proposicao-votacao/delete/', staff_member_required(admin_views.ajax_delete_proposicao_votacao), name='ajax_delete_proposicao_votacao')
    ,
    # Referências (CRUD) vinculadas a ProposicaoVotacao
    path('ajax/referencias/list/', staff_member_required(admin_views.ajax_referencias_list), name='ajax_referencias_list'),
    path('ajax/referencias/create/', staff_member_required(admin_views.ajax_referencias_create), name='ajax_referencias_create'),
    path('ajax/referencias/update/', staff_member_required(admin_views.ajax_referencias_update), name='ajax_referencias_update'),
    path('ajax/referencias/delete/', staff_member_required(admin_views.ajax_referencias_delete), name='ajax_referencias_delete'),
    # Background task status polling
    path('ajax/task-status/', admin_views.ajax_task_status, name='ajax_task_status'),
    # RAG tool page (staff only)
    path('rag-tool/', staff_member_required(admin_views.rag_tool), name='rag_tool'),
]
