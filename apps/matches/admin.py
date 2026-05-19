from django.contrib import admin
from .models import (
    Group,
    Match,
    GroupStanding,
    GameResult
)
# Register your models here.
class GameResultInline(admin.TabularInline):
    """
    Exibe os games individuais (game 1, 2, 3...) diretamente
    na página da partida — essencial para registrar resultados
    de uma BO3/BO5 sem sair da tela.
    """
    model = GameResult
    extra = 1
    fields = ("game_number", "score_a", "score_b", "winner", "map_name")


class GroupStandingInline(admin.TabularInline):
    """
    Exibe a classificação dos times dentro da página do grupo —
    permite ver e editar a tabela do grupo sem navegação extra.
    """
    model = GroupStanding
    extra = 0
    fields = ("team", "points", "wins", "losses", "draws", "round_diff", "position")


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "championship")
    search_fields = ("name", "championship__name")
    list_filter = ("championship",)
    inlines = [GroupStandingInline]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("championship", "phase", "match_format", "team_a", "team_b", "winner", "status", "scheduled_at")
    search_fields = ("team_a__name", "team_b__name", "championship__name")
    list_filter = ("status", "phase", "match_format", "championship")
    inlines = [GameResultInline]

    def get_search_results(self, request, queryset, search_term):
        """
        Garante que a busca por nome de time funciona
        mesmo com related fields.
        """
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct


@admin.register(GroupStanding)
class GroupStandingAdmin(admin.ModelAdmin):
    list_display = ("team", "group", "points", "wins", "losses", "draws", "round_diff", "position")
    search_fields = ("team__name", "group__name")
    list_filter = ("group__championship", "group")


@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ("match", "game_number", "score_a", "score_b", "winner", "map_name")
    search_fields = ("winner__name", "match__championship__name")
    list_filter = ("match__championship", "match__phase")