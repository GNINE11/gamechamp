from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("cadastro/",      views.signup_view,       name="signup"),
    path("entrar/",        views.login_view,         name="login"),
    path("sair/",          views.logout_view,        name="logout"),
    path("perfil/",        views.profile_view,       name="profile"),
    path("perfil/editar/", views.edit_profile_view,  name="edit-profile"),
]