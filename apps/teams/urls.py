from django.urls import path

from . import views


app_name = "teams"

urlpatterns = [
    path("equipes/", views.teams_home, name="teams-home"),
    path("equipes/criar/", views.create_team, name="teams-create"),
    path("equipes/convites/", views.invitations, name="teams-invitations"),
    path("equipes/convites/<int:pk>/aceitar/", views.accept_invite, name="teams-invite-accept"),
    path("equipes/convites/<int:pk>/recusar/", views.decline_invite, name="teams-invite-decline"),
    path("equipes/convites/<int:pk>/cancelar/", views.cancel_invite, name="teams-invite-cancel"),
    path("equipes/<int:pk>/", views.team_detail, name="teams-detail"),
    path("equipes/<int:pk>/editar/", views.edit_team, name="teams-edit"),
    path("equipes/<int:pk>/membros/", views.manage_members, name="teams-members"),
    path("equipes/<int:pk>/convidar/", views.send_invite, name="teams-invite-send"),
    path("equipes/<int:pk>/membros/<int:membership_pk>/remover/", views.remove_member, name="teams-member-remove"),
    path("equipes/<int:pk>/membros/<int:membership_pk>/promover/", views.promote_member, name="teams-member-promote"),
    path("equipes/<int:pk>/membros/<int:membership_pk>/cargo/", views.update_member_role, name="teams-member-role"),
    path("equipes/<int:pk>/excluir/", views.delete_team, name="teams-delete"),
]
