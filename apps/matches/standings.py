"""
apps/matches/standings.py

Computa a classificação dos grupos de um campeonato.
Usado pelo bracket.py e diretamente pelo structure_championship view.
"""
from .models import Group, GroupStanding
from apps.championships.models import StatusChampionship


def _classification_status(rank, advancing, total, champ_status):
    """
    Retorna a string de status de classificação de um time em um grupo.

    'classified'  → já garantiu vaga
    'disputed'    → posição em disputa (ainda há jogos pendentes)
    'eliminated'  → fora
    None          → campeonato ainda não terminou / sem critério definido
    """
    if advancing <= 0:
        return None

    if rank <= advancing:
        return 'classified'

    finished = champ_status == StatusChampionship.FINISHED
    if finished:
        return 'eliminated'

    # Ainda em andamento: posições logo abaixo da linha de corte ficam "em disputa"
    # (simplificação conservadora — assume que qualquer um no top advancing+1 pode subir)
    if rank == advancing + 1:
        return 'disputed'

    return 'eliminated'


def get_group_standings(championship):
    """
    Retorna lista de grupos com suas classificações anotadas.

    Estrutura retornada:
    [
        {
            'group': Group,
            'standings': [GroupStanding, ...],   # ordenado por position / points / round_diff
            'advancing_count': int,
        },
        ...
    ]

    Cada GroupStanding recebe o atributo dinâmico `.classification_status`
    ('classified' | 'disputed' | 'eliminated' | None).
    """
    groups = (
        Group.objects
        .filter(championship=championship)
        .prefetch_related('groupstanding_set__team')
        .order_by('name')
    )

    advancing = championship.teams_advancing_per_group or 0
    total_per_group = championship.teams_per_group or 0

    result = []
    for group in groups:
        standings = list(
            group.groupstanding_set
            .select_related('team')
            .order_by('position', '-points', '-round_diff', '-rounds_won')
        )

        for i, s in enumerate(standings):
            s.classification_status = _classification_status(
                rank=i + 1,
                advancing=advancing,
                total=total_per_group,
                champ_status=championship.status,
            )

        result.append({
            'group': group,
            'standings': standings,
            'advancing_count': advancing,
        })

    return result