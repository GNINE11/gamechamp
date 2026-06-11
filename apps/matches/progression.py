"""
apps/matches/progression.py

Progressão automática do bracket e atualização da tabela de grupos.

Chamado após cada partida finalizada em update_match_scores.
Responsabilidades:
  1. Propagar o vencedor para a próxima partida (single e double elimination).
  2. Atualizar GroupStanding quando a partida é de fase de grupos.
  3. Semear o bracket de playoffs com os classificados quando toda a fase
     de grupos for concluída (GROUP_THEN_PLAYOFFS).
  4. Encerrar o campeonato e registrar o grande campeão quando a grande
     final for concluída.
"""

from django.db import transaction

from .models import GameResult, GameStatus, GroupStanding, Match, Phase


# ── 1. Atualização da tabela de grupos ───────────────────────────────────────

def _wins_losses_from_results(match):
    """
    Conta wins/losses de games individuais a partir dos GameResults.
    Retorna (wins_a, wins_b).
    """
    results = GameResult.objects.filter(match_id=match)
    wins_a = results.filter(winner=match.team_a).count() if match.team_a else 0
    wins_b = results.filter(winner=match.team_b).count() if match.team_b else 0
    return wins_a, wins_b


def _update_group_standing(match):
    """
    Atualiza GroupStanding para ambos os times após uma partida de grupos
    ser encerrada. Adiciona vitória/derrota e diferença de rounds.
    """
    if not (match.group and match.winner and match.team_a and match.team_b):
        return

    wins_a, wins_b = _wins_losses_from_results(match)

    winner_team  = match.winner
    loser_team   = match.team_b if match.winner == match.team_a else match.team_a

    # Rounds marcados/sofridos por cada lado (soma dos scores individuais)
    results = GameResult.objects.filter(match_id=match)
    rounds_scored_a = sum(r.score_a for r in results)
    rounds_scored_b = sum(r.score_b for r in results)

    def _update(team, rounds_won_delta, rounds_lost_delta, is_winner):
        standing, _ = GroupStanding.objects.get_or_create(
            group=match.group,
            team=team,
            defaults={"wins": 0, "losses": 0, "points": 0,
                      "rounds_won": 0, "rounds_lost": 0, "round_diff": 0},
        )
        if is_winner:
            standing.wins   += 1
            standing.points += 3
        else:
            standing.losses += 1

        standing.rounds_won  += rounds_won_delta
        standing.rounds_lost += rounds_lost_delta
        standing.round_diff   = standing.rounds_won - standing.rounds_lost
        standing.save()

    _update(match.team_a,
            rounds_won_delta=rounds_scored_a,
            rounds_lost_delta=rounds_scored_b,
            is_winner=(match.winner == match.team_a))

    _update(match.team_b,
            rounds_won_delta=rounds_scored_b,
            rounds_lost_delta=rounds_scored_a,
            is_winner=(match.winner == match.team_b))

    # Recalcula posições dentro do grupo
    _recalculate_positions(match.group)


def _recalculate_positions(group):
    """
    Ordena os standings do grupo por pontos desc, round_diff desc, rounds_won desc
    e grava a posição de cada time.
    """
    standings = list(
        GroupStanding.objects
        .filter(group=group)
        .order_by("-points", "-round_diff", "-rounds_won")
    )
    for pos, standing in enumerate(standings, start=1):
        if standing.position != pos:
            standing.position = pos
            standing.save(update_fields=["position"])


# ── 2. Propagação no bracket (single elimination) ───────────────────────────

def _next_single_elim_match(finished_match):
    """
    Determina a próxima partida no bracket de single elimination.

    Convenção usada em services._create_single_elimination:
      - As partidas de uma rodada são criadas em sequência (round_number crescente).
      - Na rodada seguinte, há metade das partidas.
      - O slot da próxima partida é: índice_atual // 2, onde o índice é a posição
        da partida dentro de sua playoff_round (ordenada por round_number).

    Retorna a instância Match da próxima partida, ou None.
    """
    if finished_match.phase == Phase.GRAND_FINAL:
        return None

    current_round = finished_match.playoff_round
    if current_round is None:
        return None

    next_round = current_round + 1

    # Partidas da rodada atual (em ordem)
    current_round_matches = list(
        Match.objects
        .filter(
            championship=finished_match.championship,
            phase=Phase.PLAYOFF,
            playoff_round=current_round,
        )
        .order_by("round_number")
    )

    try:
        my_index = [m.pk for m in current_round_matches].index(finished_match.pk)
    except ValueError:
        return None

    next_slot = my_index // 2  # par/ímpar → mesmo slot na próxima rodada

    # A próxima rodada pode ser PLAYOFF ou GRAND_FINAL
    next_round_matches = list(
        Match.objects
        .filter(
            championship=finished_match.championship,
            phase__in=[Phase.PLAYOFF, Phase.GRAND_FINAL],
            playoff_round=next_round,
        )
        .order_by("round_number")
    ) or list(
        Match.objects
        .filter(
            championship=finished_match.championship,
            phase=Phase.GRAND_FINAL,
            playoff_round=None,
        )
        .order_by("round_number")
    )

    if not next_round_matches:
        return None

    if next_slot < len(next_round_matches):
        return next_round_matches[next_slot]

    # Se só existe 1 partida na próxima rodada (final), usa ela
    return next_round_matches[0]


def _place_winner_in_match(next_match, winner):
    """
    Insere o vencedor no slot disponível (team_a ou team_b) da próxima partida.
    Se team_a já estiver preenchido, usa team_b.
    Não substitui um time já definido — apenas preenche slots vazios.
    """
    if next_match is None or winner is None:
        return

    changed = False
    if next_match.team_a is None:
        next_match.team_a = winner
        changed = True
    elif next_match.team_b is None and next_match.team_a != winner:
        next_match.team_b = winner
        changed = True

    if changed:
        next_match.save(update_fields=["team_a", "team_b"])


def _propagate_single_elim(finished_match):
    """Propaga o vencedor no bracket de single elimination."""
    next_match = _next_single_elim_match(finished_match)
    _place_winner_in_match(next_match, finished_match.winner)


# ── 3. Propagação no bracket (double elimination) ───────────────────────────

def _propagate_double_elim(finished_match):
    """
    Propaga o vencedor (e o perdedor) no bracket de double elimination.

    Convenção (ver services._create_double_elimination):
      - Upper bracket: playoff_round > 0
      - Lower bracket: playoff_round < 0
      - Grand final: phase == GRAND_FINAL

    Regras:
      - Vencedor do upper → próxima rodada do upper (mesma lógica de single).
      - Perdedor do upper → lower bracket (rodada negativa correspondente).
      - Vencedor do lower → próxima rodada do lower.
      - Vencedor da última rodada do lower → Grand Final.
    """
    if finished_match.phase == Phase.GRAND_FINAL:
        return

    winner = finished_match.winner
    loser  = (
        finished_match.team_b
        if winner == finished_match.team_a
        else finished_match.team_a
    )

    pr = finished_match.playoff_round or 0

    if pr > 0:
        # ── Upper bracket ─────────────────────────────────────────────
        # Vencedor avança no upper
        next_upper = _next_upper_match(finished_match)
        _place_winner_in_match(next_upper, winner)

        # Perdedor cai no lower
        next_lower = _drop_to_lower(finished_match)
        _place_winner_in_match(next_lower, loser)

    else:
        # ── Lower bracket ─────────────────────────────────────────────
        next_lower = _next_lower_match(finished_match)
        if next_lower is not None:
            _place_winner_in_match(next_lower, winner)
        else:
            # Chegou à final do lower → vai para a Grand Final
            gf = _get_grand_final(finished_match.championship)
            _place_winner_in_match(gf, winner)


def _next_upper_match(finished_match):
    """Próxima partida no upper bracket (mesmo algoritmo do single elim)."""
    current_round = finished_match.playoff_round
    next_round    = current_round + 1

    current_matches = list(
        Match.objects
        .filter(
            championship=finished_match.championship,
            playoff_round=current_round,
        )
        .order_by("round_number")
    )
    try:
        my_index = [m.pk for m in current_matches].index(finished_match.pk)
    except ValueError:
        return None

    next_matches = list(
        Match.objects
        .filter(
            championship=finished_match.championship,
            playoff_round=next_round,
        )
        .order_by("round_number")
    )
    if not next_matches:
        return None

    next_slot = my_index // 2
    return next_matches[next_slot] if next_slot < len(next_matches) else next_matches[0]


def _drop_to_lower(upper_match):
    """
    Encontra a partida do lower bracket onde o perdedor do upper deve cair.

    Convenção: a primeira rodada do lower (-1) recebe os perdedores da rodada 1
    do upper, a segunda (-2) recebe os perdedores da rodada 2, etc.
    O mapeamento é playoff_round_upper → playoff_round_lower = -playoff_round_upper.
    """
    lower_round = -upper_match.playoff_round

    lower_matches = list(
        Match.objects
        .filter(
            championship=upper_match.championship,
            playoff_round=lower_round,
        )
        .order_by("round_number")
    )
    if not lower_matches:
        return None

    # Encontra a posição no upper para mapear ao slot correto no lower
    upper_round_matches = list(
        Match.objects
        .filter(
            championship=upper_match.championship,
            playoff_round=upper_match.playoff_round,
        )
        .order_by("round_number")
    )
    try:
        my_index = [m.pk for m in upper_round_matches].index(upper_match.pk)
    except ValueError:
        return lower_matches[0]

    # O lower pode ter o dobro de sub-rodadas por round; mapeia pelo índice
    slot = my_index % len(lower_matches)
    return lower_matches[slot]


def _next_lower_match(finished_match):
    """Próxima partida no lower bracket."""
    current_round = finished_match.playoff_round  # negativo
    # Lower rounds ficam cada vez mais próximos de 0 em valor absoluto:
    # -1 → -2 → -3... mas a convenção de _create_double_elimination cria dois
    # sub-rounds por rodada. A próxima rodada tem número mais negativo.
    next_round = current_round - 1

    next_matches = list(
        Match.objects
        .filter(
            championship=finished_match.championship,
            playoff_round=next_round,
        )
        .order_by("round_number")
    )
    return next_matches[0] if next_matches else None


def _get_grand_final(championship):
    return (
        Match.objects
        .filter(championship=championship, phase=Phase.GRAND_FINAL)
        .first()
    )


# ── 4. Finalização do campeonato ─────────────────────────────────────────────

def _maybe_finish_championship(match):
    """
    Se a partida encerrada for a Grande Final, registra o grande campeão
    no campeonato e muda seu status para FINISHED.
    """
    if match.phase != Phase.GRAND_FINAL or not match.winner:
        return

    from apps.championships.models import StatusChampionship  # import local p/ evitar circular

    championship = match.championship
    championship.champion = match.winner          # campo ForeignKey → Team
    championship.status   = StatusChampionship.FINISHED
    championship.save(update_fields=["champion", "status"])


def _all_group_matches_finished(championship):
    """Retorna True se todas as partidas de fase de grupos estão encerradas."""
    return not Match.objects.filter(
        championship=championship,
        phase=Phase.GROUP,
    ).exclude(status=GameStatus.FINISHED).exists()


def _seed_bracket_from_groups(championship):
    """
    Popula as partidas da fase de playoffs com os classificados dos grupos.

    Convenção esperada (criada em services._create_group_then_playoffs):
      - As partidas de playoffs têm phase=PLAYOFF (ou GRAND_FINAL) e
        team_a / team_b ainda NULL (TBD).
      - Os slots são preenchidos em ordem: classificados ordenados por
        posição dentro de cada grupo, intercalando grupos para evitar que
        times do mesmo grupo se encontrem na primeira rodada.

    Exemplo com 2 grupos (A e B) e 2 classificados cada:
      Slot 1 → 1º do grupo A
      Slot 2 → 1º do grupo B
      Slot 3 → 2º do grupo A
      Slot 4 → 2º do grupo B
    """
    from apps.matches.models import Group  # import local p/ evitar circular

    groups = list(
        Group.objects.filter(championship=championship).order_by('name')
    )
    if not groups:
        return

    qualifiers_per_group = championship.teams_advancing_per_group or 1

    # Monta lista de classificados: [[1ºA, 1ºB, ...], [2ºA, 2ºB, ...], ...]
    classified_by_position = []
    for pos in range(1, qualifiers_per_group + 1):
        row = []
        for group in groups:
            standing = (
                GroupStanding.objects
                .filter(group=group, position=pos)
                .select_related('team')
                .first()
            )
            if standing and standing.team:
                row.append(standing.team)
        classified_by_position.append(row)

    # Achata intercalando por grupo: 1ºA, 1ºB, 2ºA, 2ºB, ...
    seeds = [team for row in classified_by_position for team in row]

    if not seeds:
        return

    # Partidas de playoff na primeira rodada (menor playoff_round > 0),
    # ordenadas por round_number para garantir ordem determinística.
    first_round = (
        Match.objects
        .filter(
            championship=championship,
            phase=Phase.PLAYOFF,
            playoff_round=1,
        )
        .order_by('round_number')
    )

    # Fallback: se não há playoff_round=1 (estrutura sem numeração),
    # pega todas as partidas de PLAYOFF sem times definidos.
    if not first_round.exists():
        first_round = (
            Match.objects
            .filter(
                championship=championship,
                phase=Phase.PLAYOFF,
                team_a__isnull=True,
                team_b__isnull=True,
            )
            .order_by('round_number')
        )

    slot = 0
    for match in first_round:
        changed = False
        if match.team_a is None and slot < len(seeds):
            match.team_a = seeds[slot]
            slot += 1
            changed = True
        if match.team_b is None and slot < len(seeds):
            match.team_b = seeds[slot]
            slot += 1
            changed = True
        if changed:
            match.save(update_fields=['team_a', 'team_b'])


# ── 5. Entry point ────────────────────────────────────────────────────────────

@transaction.atomic
def on_match_finished(match):
    """
    Ponto de entrada chamado imediatamente após match.save() quando
    match.status == GameStatus.FINISHED.

    Executa em ordem:
      1. Atualiza GroupStanding (se fase de grupos).
      1b. Semeia o bracket de playoffs (se toda a fase de grupos encerrou).
      2. Propaga o vencedor no bracket (se fase eliminatória).
      3. Finaliza o campeonato (se Grande Final).
    """
    if match.status != GameStatus.FINISHED or not match.winner:
        return

    from apps.championships.models import StageFormat, PlayoffFormat  # import local

    championship = match.championship
    fmt = championship.stage_format

    # 1. Tabela de grupos
    if match.phase == Phase.GROUP:
        _update_group_standing(match)
        # Quando a última partida de grupos encerra, semeia o bracket de playoffs.
        if (
            fmt == StageFormat.GROUP_THEN_PLAYOFFS
            and _all_group_matches_finished(championship)
        ):
            _seed_bracket_from_groups(championship)
        return  # partidas de grupo não propagam no bracket de eliminação

    # 2. Propagação no bracket
    is_double = (
        fmt == StageFormat.DOUBLE_ELIMINATION
        or (
            fmt == StageFormat.GROUP_THEN_PLAYOFFS
            and championship.playoff_format == PlayoffFormat.DOUBLE_ELIMINATION
        )
    )

    if is_double:
        _propagate_double_elim(match)
    else:
        _propagate_single_elim(match)

    # 3. Finalização do campeonato