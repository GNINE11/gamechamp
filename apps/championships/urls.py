from django.urls import path
from . import views

app_name = 'championship'

urlpatterns = [
    path('inicio/', views.list_available_championships, name='available-championship-list'),

    path('meus-campeonatos/', views.list_my_championships, name='my-championship-list'),

    path('campeonatos-criados/', views.list_created_championships, name='created-championship-list'),

    path('campeonatos/detalhes', views.detail_championship, name='championship-detail'),
    path('campeonatos/gerenciar', views.manager_championship, name='championship-manager'),
    path('campeonatos/aprovar-times', views.team_approval, name='championship-team-approval'),
]