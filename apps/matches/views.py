from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from apps.matches.models import Match, GameStatus, GameResult, GroupStanding
from apps.teams.models import Team
from apps.championships.models import Championship


# ─────────────────────────────────────────────────────────────────────────────
# HISTÓRICO DE PARTIDAS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def list_matches_history(request):
    """
    Lista paginada de todas as partidas encerradas dos times do usuário,
    com filtros por torneio, time e resultado.
    """
    user       = request.user
    user_teams = Team.objects.filter(members=user)
    user_team_ids = set(user_teams.values_list("pk", flat=True))

    # Queryset base: partidas encerradas onde o usuário participou
    qs = Match.objects.filter(
        Q(team_a__in=user_teams) | Q(team_b__in=user_teams),
        status=GameStatus.FINISHED,
    ).select_related("team_a", "team_b", "winner", "championship").order_by("-scheduled_at")

    # ── Filtros ────────────────────────────────────────────────────────────
    tournament_id = request.GET.get("tournament")
    team_id       = request.GET.get("team")
    period        = request.GET.get("period", "all")
    result        = request.GET.get("result", "")

    if tournament_id:
        qs = qs.filter(championship_id=tournament_id)

    if team_id:
        qs = qs.filter(Q(team_a_id=team_id) | Q(team_b_id=team_id))

    if period == "30":
        from django.utils import timezone
        import datetime
        qs = qs.filter(scheduled_at__gte=timezone.now() - datetime.timedelta(days=30))
    elif period == "90":
        from django.utils import timezone
        import datetime
        qs = qs.filter(scheduled_at__gte=timezone.now() - datetime.timedelta(days=90))

    # Anota user_won antes de filtrar por resultado
    matches_raw = list(qs)
    enriched = []
    for m in matches_raw:
        user_won = m.winner_id in user_team_ids if m.winner_id else False
        enriched.append((m, user_won))

    if result == "win":
        enriched = [(m, w) for m, w in enriched if w]
    elif result == "loss":
        enriched = [(m, w) for m, w in enriched if not w]

    # ── Monta lista final com dados de score ──────────────────────────────
    matches_list = []
    for m, user_won in enriched:
        sa = GameResult.objects.filter(match_id=m, winner=m.team_a).count()
        sb = GameResult.objects.filter(match_id=m, winner=m.team_b).count()
        # Injeta atributo dinâmico para o template
        m.score_a  = sa
        m.score_b  = sb
        m.user_won = user_won
        matches_list.append(m)

    # ── Paginação ─────────────────────────────────────────────────────────
    paginator = Paginator(matches_list, 10)
    page_obj  = paginator.get_page(request.GET.get("page"))

    # ── Stats do header ───────────────────────────────────────────────────
    total_matches = len(matches_list)
    total_wins    = sum(1 for m in matches_list if m.user_won)
    win_rate      = round((total_wins / total_matches * 100)) if total_matches else 0

    # ── Dados para os selects de filtro ──────────────────────────────────
    tournaments = Championship.objects.filter(
        match__in=qs
    ).distinct()
    teams = user_teams

    return render(request, "matches/pages/match_history.html", {
        "matches"      : page_obj,
        "tournaments"  : tournaments,
        "teams"        : teams,
        "total_matches": total_matches,
        "win_rate"     : win_rate,
    })


# ─────────────────────────────────────────────────────────────────────────────
# DETALHES DE UMA PARTIDA
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def match_details(request, pk):
    """
    Exibe os detalhes de uma partida específica.
    Calcula H2H entre os dois times e verifica se o usuário pode registrar resultado.
    """
    match = get_object_or_404(
        Match.objects.select_related(
            "team_a", "team_b", "winner", "championship"
        ).prefetch_related("teams"),
        pk=pk,
    )

    user       = request.user
    user_teams = Team.objects.filter(members=user)

    # ── Permissão para registrar resultado ───────────────────────────────
    can_submit = (
        match.status != GameStatus.FINISHED
        and user_teams.filter(pk__in=[match.team_a_id, match.team_b_id]).exists()
    )

    # ── Head to Head entre team_a e team_b ───────────────────────────────
    h2h_matches = Match.objects.filter(
        Q(team_a=match.team_a, team_b=match.team_b) |
        Q(team_a=match.team_b, team_b=match.team_a),
        status=GameStatus.FINISHED,
    ).exclude(pk=match.pk)

    h2h_wins   = h2h_matches.filter(winner=match.team_a).count()
    h2h_losses = h2h_matches.filter(winner=match.team_b).count()
    h2h_draws  = h2h_matches.filter(winner__isnull=True).count()
    h2h_total  = h2h_wins + h2h_losses + h2h_draws
    h2h_rate   = round(h2h_wins / h2h_total * 100) if h2h_total else 0

    h2h = {
        "wins"    : h2h_wins,
        "losses"  : h2h_losses,
        "draws"   : h2h_draws,
        "win_rate": h2h_rate,
    }

    # ── Placar atual (rounds/maps ganhos por cada time) ───────────────────
    score_a = GameResult.objects.filter(match_id=match, winner=match.team_a).count()
    score_b = GameResult.objects.filter(match_id=match, winner=match.team_b).count()
    match.score_a = score_a
    match.score_b = score_b

    return render(request, "matches/pages/match_details.html", {
        "match"     : match,
        "h2h"       : h2h,
        "can_submit": can_submit,
    })


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRAR RESULTADO (placeholder — implementar conforme formulário)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def register_match_result(request):
    return render(request, "matches/pages/record_result.html")