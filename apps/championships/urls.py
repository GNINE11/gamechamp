from django.urls import path
from . import views

app_name = 'championship'

urlpatterns = [
    path('inicio/', views.list_available_championships, name='available-championship-list'),
    
    path('meus-campeonatos/', views.list_my_championships, name='my-championship-list'),

    path('campeonatos/gestao/', views.list_management_championships, name='management-championship-list'),
    path('campeonatos/gestao/criar/', views.create_championship, name='management-championship-create'),
    path('campeonatos/gestao/<int:championship_id>/dashboard/', views.manager_championship, name='management-championship-dashboard'),
    path('campeonatos/gestao/<int:championship_id>/editar/', views.edit_championship, name='management-championship-edit'),
    path('campeonatos/<int:championship_id>/staff/', views.staff_management, name='management-championship-staff'),
    path('campeonatos/<int:championship_id>/chaveamento/', views.structure_championship, name='championship-structure'),
    path('campeonatos/<int:championship_id>/inscrever/', views.register_championship, name='championship-register'),
    path('campeonatos/<int:championship_id>/cancelar-inscricao/', views.cancel_registration, name='championship-cancel-registration'),

    path('campeonatos/aprovar-times', views.team_approval, name='championship-team-approval'),
]
