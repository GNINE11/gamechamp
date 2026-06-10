from django.urls import path
from . import views

app_name = 'championship'

urlpatterns = [
    path('inicio/', views.list_available_championships, name='available-championship-list'),
    path('inicio/chaveamento/', views.structure_championship, name='available-championship-structure'),
    
    path('meus-campeonatos/', views.list_my_championships, name='my-championship-list'),
    path('meus-campeonatos/chaveamento/', views.structure_championship, name='my-championship-structure'),

    path('campeonatos/gestao/', views.list_management_championships, name='management-championship-list'),
    path('campeonatos/gestao/<int:championship_id>/dashboard/', views.manager_championship, name='management-championship-dashboard'),
    path('campeonatos/<int:championship_id>/staff/', views.staff_management, name='management-championship-staff'),

    path('campeonatos/aprovar-times', views.team_approval, name='championship-team-approval'),
]