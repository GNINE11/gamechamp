from django.contrib import admin
from .models import(
    Championship,
    ChampionshipStaff,
    TiebreakerRule,
    Registration,
    RoleStaff,
)

class TiebreakerRuleInline(admin.TabularInline):
    model = TiebreakerRule
    extra = 1

@admin.register(Championship)
class ChampionshipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "game",
        "status",
        "stage_format",
        "max_teams",
        "start_date",
        "created_by",
    )

    list_filter = (
        "status",
        "stage_format",
        "game",
    )

    search_fields = (
        "name",
        "game",
    )

    fieldsets = (
        ('Informações básicas', {
            'fields': ('name', 'game', 'max_teams', 'stage_format', 'status', 'start_date')
        }),
        ('Configurações de grupos', {
            'fields': ('group_count', 'teams_per_group', 'teams_advancing_per_group', 'group_match_format'),
            'description': 'Configure os campos de acordo com o formato escolhido.',
        }),
        ('Configurações de playoff', {
            'fields': ('playoff_format', 'playoff_match_format', 'final_match_format', 'third_place_match'),
            'classes': ('collapse',),
            'description': 'Preencha apenas se houver fase eliminatória (não preencher em "Pontos corridos").'
        }),
        ('Outros', {
            'fields': ('seeding_method',)
        }),
    )

    inlines = [TiebreakerRuleInline]

    def save_model(self, request, obj, form, change):

        is_new = obj.pk is None

        if is_new:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

        # Cria owner automaticamente
        if is_new:
            ChampionshipStaff.objects.create(
                championship=obj,
                user=request.user,
                role=RoleStaff.OWNER
            )


@admin.register(ChampionshipStaff)
class ChampionshipStaffAdmin(admin.ModelAdmin):
    list_display = (
        "championship",
        "user",
        "role",
        "added_at",
    )

    list_filter = (
        "championship",
        "user",
        "role",
    )

    search_fields = (
        "championship__name",
        "user__username ",
        "role",
    )


@admin.register(TiebreakerRule)
class TiebreakerRuleAdmin(admin.ModelAdmin):
    list_display = (
        "championship",
        "priority",
        "criterion",
    )

    list_filter = (
        "championship",
        "criterion",
    )

    search_fields = (
        "championship",
    )


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "championship",
        "team",
        "status",
        "registered_at",
    )

    list_filter = (
        "status",
        "championship",
        "team",
        "registered_at",
    )

    search_fields = (
        "championship__name",
        "team__name",
    )
