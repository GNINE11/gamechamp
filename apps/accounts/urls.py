from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('perfil/', views.profile, name='profile'),
    path('perfil/editar-perfil/', views.edit_profile, name='edit-profile')
]