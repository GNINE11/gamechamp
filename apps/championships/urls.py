from django.urls import path
from . import views

app_name = 'championship'

urlpatterns = [
    path('campeonatos/', views.list_championship, name='championship-list'),
    path('campeonatos/detalhes', views.detail_championship, name='championship-detail'),
    path('campeonatos/gerenciar', views.manager_championship, name='championship-manager'),
    path('campeonatos/aprovar-times', views.team_approval, name='championship-team-approval'),
]