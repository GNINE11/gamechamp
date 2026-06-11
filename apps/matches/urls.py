from django.urls import path
from . import views

app_name = "matches"
 
urlpatterns = [
    path("perfil/historico/", views.list_matches_history, name="history"),
    path("<int:pk>/", views.match_details, name="detail"),
]