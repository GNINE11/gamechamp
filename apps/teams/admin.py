from django.contrib import admin

from .models import (
    Invite,
    Team,
    TeamMembership,
)


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    fields = ("player", "role", "joined_at")
    readonly_fields = ("joined_at",)


class InviteInline(admin.TabularInline):
    model = Invite
    extra = 0
    fields = ("invited_player", "proposed_role", "status", "created_at", "responded_at")
    readonly_fields = ("created_at", "responded_at")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "tag", "captain", "public_recruitment", "created_at")
    search_fields = ("name", "tag", "captain__username")
    list_filter = ("public_recruitment", "created_at")
    readonly_fields = ("created_at",)
    inlines = [TeamMembershipInline, InviteInline]

    fieldsets = (
        ("Informações básicas", {
            "fields": ("name", "tag", "description", "captain")
        }),
        ("Identidade visual", {
            "fields": ("logo", "banner", "primary_color", "accent_color")
        }),
        ("Configurações", {
            "fields": ("public_recruitment", "region", "primary_game", "social_url")
        }),
        ("Datas", {
            "fields": ("created_at",)
        }),
    )


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("team", "player", "role", "joined_at")
    search_fields = ("team__name", "player__username", "role")
    list_filter = ("team", "joined_at")
    readonly_fields = ("joined_at",)


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("team", "invited_player", "proposed_role", "status", "created_at", "responded_at")
    search_fields = ("team__name", "invited_player__username", "proposed_role")
    list_filter = ("status", "team", "created_at")
    readonly_fields = ("created_at", "responded_at")
