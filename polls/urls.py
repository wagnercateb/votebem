from django.urls import path
from . import views

app_name = 'polls'

urlpatterns = [
    path('', views.EnqueteListView.as_view(), name='enquete_list'),
    path('minhas/', views.MinhasEnquetesView.as_view(), name='minhas_enquetes'),
    path('criar/', views.EnqueteCreateView.as_view(), name='enquete_create'),
    path('criar/<int:proposicao_id>/', views.EnqueteCreateView.as_view(), name='enquete_create_proposicao'),
    path('<int:pk>/', views.EnqueteDetailView.as_view(), name='enquete_detail'),
    path('<int:pk>/editar/', views.EnqueteUpdateView.as_view(), name='enquete_edit'),
    path('<int:pk>/excluir/', views.EnqueteDeleteView.as_view(), name='enquete_delete'),
    path('<int:enquete_id>/responder/', views.ResponderEnqueteView.as_view(), name='responder_enquete'),
]