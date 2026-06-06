from django.urls import path
from . import views

app_name = "accounts"
app_name = "matches"

urlpatterns = [
    path('historico-de-partidas/', views.list_matches_history, name='matches-list'),
    path('registrar-resultado/', views.register_match_result, name='register-match-result'),
    path('detalhes-da-partida/', views.match_details, name='match-details'),

]