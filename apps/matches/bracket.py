"""
apps/matches/bracket.py

Constrói os dados do chaveamento de um campeonato para renderização no template.
Suporta: SINGLE_ELIMINATION, DOUBLE_ELIMINATION, GROUP_THEN_PLAYOFFS, ROUND_ROBIN.
"""
from collections import defaultdict
from .models import Match, GameResult, Phase, GameStatus
from apps.championships.models import PlayoffFormat, StageFormat


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_scores(match):
    """
    Retorna (score_a, score_b) contando vitórias de games individuais
    pelo GameResult. Fallback para (0, 0) se não houver resultados ainda.
    """
    results = GameResult.objects.filter(match_id=match)
    score_a = results.filter(winner=match.team_a).count() if match.team_a else 0
    score_b = results.filter(winner=match.team_b).count() if match.team_b else 0
    return score_a, score_b


_ROUND_LABELS = {
    1:  'Final',
    2:  'Semifinal',
    4:  'Quartas de Final',
    8:  'Oitavas de Final',
    16: 'Décimos de Final',
}

_TIER_CLASSES = ['round-qf', 'round-sf', 'round-fin']  # últimas 3 rodadas, de trás pra frente


def _label_for_round(match_count, is_final):
    if is_final:
        return 'Final'
    return _ROUND_LABELS.get(match_count, f'Rodada ({match_count} partidas)')


def _tier_class(index_from_end):
    """index_from_end=0 → última rodada (Final), 1 → penúltima, etc."""
    return _TIER_CLASSES[min(index_from_end, len(_TIER_CLASSES) - 1)]


def _chunk_pairs(matches, is_final):
    """
    Agrupa as partidas de uma rodada em pares, para que o template possa
    desenhar os conectores do chaveamento entre uma rodada e a próxima.
    A rodada final (ou rodadas com 1 partida) não precisa de pares.
    """
    if is_final or len(matches) < 2:
        return [[m] for m in matches]
    return [matches[j:j + 2] for j in range(0, len(matches), 2)]


# ── Bracket principal ─────────────────────────────────────────────────────────

def _format_match(match):
    score_a, score_b = _get_scores(match)
    return {
        'id':       match.pk,
        'team_a':   match.team_a,
        'team_b':   match.team_b,
        'score_a':  score_a,
        'score_b':  score_b,
        'winner':   match.winner,
        'status':   match.status,
        'is_tbd_a': match.team_a is None,
        'is_tbd_b': match.team_b is None,
        'is_final': match.phase == Phase.GRAND_FINAL,
        'scheduled_at': match.scheduled_at,
    }


def get_bracket_rounds(championship):
    """
    Retorna lista de rodadas do chaveamento (PLAYOFF + GRAND_FINAL).

    Cada rodada:
    {
        'label':           str,
        'tier_class':      str,       # CSS class para colorir o header
        'matches':         [dict],    # lista de _format_match()
        'connector_pairs': [int],     # range para o template iterar e desenhar SVG
    }
    """
    playoff_matches = list(
        Match.objects
        .filter(championship=championship, phase__in=[Phase.PLAYOFF, Phase.GRAND_FINAL])
        .select_related('team_a', 'team_b', 'winner')
        .order_by('playoff_round', 'round_number')
    )

    max_round = max([m.playoff_round or 0 for m in playoff_matches] or [0])
    rounds_map = defaultdict(list)
    for m in playoff_matches:
        key = max_round + 1 if m.phase == Phase.GRAND_FINAL else m.playoff_round
        rounds_map[key].append(m)

    if not rounds_map:
        return []

    sorted_keys = sorted(rounds_map.keys())
    total = len(sorted_keys)
    rounds = []

    for i, key in enumerate(sorted_keys):
        matches = rounds_map[key]
        index_from_end = total - 1 - i
        is_final = (index_from_end == 0)

        formatted = [_format_match(m) for m in matches]
        rounds.append({
            'label':           _label_for_round(len(formatted), is_final),
            'tier_class':      _tier_class(index_from_end),
            'matches':         formatted,
            'pairs':           _chunk_pairs(formatted, is_final),
            'spacing':         2 ** i,
            # connector_pairs: cada par de partidas desta rodada gera 1 par de conectores
            # A última rodada não precisa de conector.
            'connector_pairs': list(range(max(len(formatted) // 2, 1))) if not is_final else [],
        })

    return rounds


# ── Double elimination ────────────────────────────────────────────────────────

def get_double_elim_bracket(championship):
    """
    Separa as partidas em upper bracket, lower bracket e grand final.

    Retorna:
    {
        'upper': [rounds],
        'lower': [rounds],
        'grand_final': match_dict | None,
    }

    Por convenção, playoff_round > 0 → upper; playoff_round < 0 → lower;
    phase == GRAND_FINAL → grand final.
    Ajuste conforme a convenção que você usar ao criar as partidas.
    """
    all_matches = (
        Match.objects
        .filter(championship=championship, phase__in=[Phase.PLAYOFF, Phase.GRAND_FINAL])
        .select_related('team_a', 'team_b', 'winner')
        .order_by('playoff_round', 'round_number')
    )

    upper_map   = defaultdict(list)
    lower_map   = defaultdict(list)
    grand_final = None

    for m in all_matches:
        if m.phase == Phase.GRAND_FINAL:
            grand_final = _format_match(m)
        elif m.playoff_round and m.playoff_round > 0:
            upper_map[m.playoff_round].append(m)
        elif m.playoff_round and m.playoff_round < 0:
            lower_map[abs(m.playoff_round)].append(m)

    def _to_rounds(rounds_map):
        keys = sorted(rounds_map.keys())
        total = len(keys)
        result = []
        for i, k in enumerate(keys):
            matches = rounds_map[k]
            index_from_end = total - 1 - i
            is_final = (index_from_end == 0)
            formatted = [_format_match(m) for m in matches]
            result.append({
                'label':           _label_for_round(len(formatted), is_final),
                'tier_class':      _tier_class(index_from_end),
                'matches':         formatted,
                'pairs':           _chunk_pairs(formatted, is_final),
                'spacing':         2 ** i,
                'connector_pairs': list(range(max(len(formatted) // 2, 1))) if not is_final else [],
            })
        return result

    return {
        'upper':       _to_rounds(upper_map),
        'lower':       _to_rounds(lower_map),
        'grand_final': grand_final,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def get_structure_context(championship):
    """
    Ponto de entrada principal.
    Retorna o contexto completo para o template structure.html.
    """
    fmt = championship.stage_format

    has_groups  = fmt in (StageFormat.ROUND_ROBIN, StageFormat.GROUP_THEN_PLAYOFFS)
    has_bracket = fmt in (
        StageFormat.SINGLE_ELIMINATION,
        StageFormat.DOUBLE_ELIMINATION,
        StageFormat.GROUP_THEN_PLAYOFFS,
    )
    is_double_elim = (
        fmt == StageFormat.DOUBLE_ELIMINATION
        or (
            fmt == StageFormat.GROUP_THEN_PLAYOFFS
            and championship.playoff_format == PlayoffFormat.DOUBLE_ELIMINATION
        )
    )

    ctx = {
        'championship':  championship,
        'stage_format':  fmt,
        'has_groups':    has_groups,
        'has_bracket':   has_bracket,
        'is_double_elim': is_double_elim,
        'default_view':  'grupos' if has_groups else 'chaveamento',
    }

    if has_groups:
        from .standings import get_group_standings
        ctx['groups'] = get_group_standings(championship)

    if has_bracket:
        if is_double_elim:
            ctx['double_elim'] = get_double_elim_bracket(championship)
        else:
            ctx['bracket_rounds'] = get_bracket_rounds(championship)

    return ctx