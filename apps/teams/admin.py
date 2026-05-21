from django.contrib import admin

from .models import (
    Invite,
    Team,
    TeamMembership,
)


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    fields = ("player", "joined_at")
    readonly_fields = ("joined_at",)


class InviteInline(admin.TabularInline):
    model = Invite
    extra = 0
    fields = ("invited_player", "status", "created_at", "responded_at")
    readonly_fields = ("created_at", "responded_at")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "captain", "created_at")
    search_fields = ("name", "captain__username")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)
    inlines = [TeamMembershipInline, InviteInline]

    fieldsets = (
        ("Informações básicas", {
            "fields": ("name", "logo", "captain")
        }),
        ("Datas", {
            "fields": ("created_at",)
        }),
    )


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("team", "player", "joined_at")
    search_fields = ("team__name", "player__username")
    list_filter = ("team", "joined_at")
    readonly_fields = ("joined_at",)


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("team", "invited_player", "status", "created_at", "responded_at")
    search_fields = ("team__name", "invited_player__username")
    list_filter = ("status", "team", "created_at")
    readonly_fields = ("created_at", "responded_at")
