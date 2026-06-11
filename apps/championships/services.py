from django.db import transaction
from django.utils import timezone

from apps.matches.models import GameStatus, Group, GroupStanding, Match, Phase

from .models import PlayoffFormat, Registration, StageFormat, StatusRegistration


GROUP_NAMES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _approved_teams(championship):
    return [
        registration.team
        for registration in (
            Registration.objects
            .filter(championship=championship, status=StatusRegistration.APPROVED)
            .select_related("team")
            .order_by("registered_at", "pk")
        )
    ]


def _fill_slots(teams, size):
    return list(teams[:size]) + [None] * max(size - len(teams), 0)


def _group_name(index):
    if index < len(GROUP_NAMES):
        return GROUP_NAMES[index]
    return str(index + 1)


def _create_match(
    *,
    championship,
    match_format,
    phase,
    round_number,
    scheduled_at,
    team_a=None,
    team_b=None,
    group=None,
    playoff_round=None,
):
    match = Match(
        championship=championship,
        match_format=match_format,
        phase=phase,
        group=group,
        playoff_round=playoff_round,
        round_number=round_number,
        team_a=team_a,
        team_b=team_b,
        status=GameStatus.SCHEDULED,
        scheduled_at=scheduled_at,
    )
    match.full_clean()
    match.save()
    return match


def _create_group_structure(championship, teams, start_round, scheduled_at):
    group_count = championship.group_count or 1
    teams_per_group = championship.teams_per_group or championship.max_teams
    slots = _fill_slots(teams, group_count * teams_per_group)
    round_number = start_round
    matches_created = 0

    for index in range(group_count):
        group, _ = Group.objects.get_or_create(
            championship=championship,
            name=_group_name(index),
        )
        group_slots = slots[index * teams_per_group:(index + 1) * teams_per_group]

        for position, team in enumerate(group_slots, start=1):
            if team is None:
                continue
            GroupStanding.objects.get_or_create(
                group=group,
                team=team,
                defaults={"position": position},
            )

        for first in range(teams_per_group):
            for second in range(first + 1, teams_per_group):
                _create_match(
                    championship=championship,
                    match_format=championship.group_match_format,
                    phase=Phase.GROUP,
                    group=group,
                    round_number=round_number,
                    scheduled_at=scheduled_at,
                    team_a=group_slots[first],
                    team_b=group_slots[second],
                )
                round_number += 1
                matches_created += 1

    return round_number, matches_created


def _create_single_elimination(championship, teams, slot_count, start_round, scheduled_at):
    slots = _fill_slots(teams, slot_count)
    round_number = start_round
    playoff_round = 1
    matches_created = 0
    match_count = slot_count // 2

    while match_count >= 1:
        is_final = match_count == 1
        phase = Phase.GRAND_FINAL if is_final else Phase.PLAYOFF
        match_format = championship.final_match_format if is_final else championship.playoff_match_format

        for index in range(match_count):
            team_a = slots[index * 2] if playoff_round == 1 else None
            team_b = slots[index * 2 + 1] if playoff_round == 1 else None
            _create_match(
                championship=championship,
                match_format=match_format,
                phase=phase,
                round_number=round_number,
                scheduled_at=scheduled_at,
                team_a=team_a,
                team_b=team_b,
                playoff_round=None if is_final else playoff_round,
            )
            round_number += 1
            matches_created += 1

        match_count //= 2
        playoff_round += 1

    if championship.third_place_match and slot_count >= 4:
        _create_match(
            championship=championship,
            match_format=championship.playoff_match_format,
            phase=Phase.PLAYOFF,
            round_number=round_number,
            scheduled_at=scheduled_at,
            playoff_round=playoff_round,
        )
        round_number += 1
        matches_created += 1

    return round_number, matches_created


def _create_double_elimination(championship, teams, slot_count, start_round, scheduled_at):
    slots = _fill_slots(teams, slot_count)
    round_number = start_round
    matches_created = 0

    match_count = slot_count // 2
    playoff_round = 1
    while match_count >= 1:
        for index in range(match_count):
            team_a = slots[index * 2] if playoff_round == 1 else None
            team_b = slots[index * 2 + 1] if playoff_round == 1 else None
            _create_match(
                championship=championship,
                match_format=championship.playoff_match_format,
                phase=Phase.PLAYOFF,
                round_number=round_number,
                scheduled_at=scheduled_at,
                team_a=team_a,
                team_b=team_b,
                playoff_round=playoff_round,
            )
            round_number += 1
            matches_created += 1
        match_count //= 2
        playoff_round += 1

    lower_match_count = slot_count // 4
    lower_round = -1
    while lower_match_count >= 1:
        for _repeat in range(2):
            for _index in range(lower_match_count):
                _create_match(
                    championship=championship,
                    match_format=championship.playoff_match_format,
                    phase=Phase.PLAYOFF,
                    round_number=round_number,
                    scheduled_at=scheduled_at,
                    playoff_round=lower_round,
                )
                round_number += 1
                matches_created += 1
            lower_round -= 1
        lower_match_count //= 2

    if championship.third_place_match and slot_count >= 4:
        _create_match(
            championship=championship,
            match_format=championship.playoff_match_format,
            phase=Phase.PLAYOFF,
            round_number=round_number,
            scheduled_at=scheduled_at,
            playoff_round=lower_round,
        )
        round_number += 1
        matches_created += 1

    _create_match(
        championship=championship,
        match_format=championship.final_match_format,
        phase=Phase.GRAND_FINAL,
        round_number=round_number,
        scheduled_at=scheduled_at,
    )
    matches_created += 1

    return round_number + 1, matches_created


def _create_playoff_structure(championship, teams, slot_count, start_round, scheduled_at):
    if championship.playoff_format == PlayoffFormat.DOUBLE_ELIMINATION or championship.stage_format == StageFormat.DOUBLE_ELIMINATION:
        return _create_double_elimination(championship, teams, slot_count, start_round, scheduled_at)
    return _create_single_elimination(championship, teams, slot_count, start_round, scheduled_at)


@transaction.atomic
def ensure_championship_structure(championship):
    if Match.objects.filter(championship=championship).exists():
        return {"created": 0, "skipped": True}

    teams = _approved_teams(championship)
    scheduled_at = championship.start_date or timezone.localdate()
    round_number = 1
    created = 0

    if championship.stage_format == StageFormat.ROUND_ROBIN:
        round_number, group_created = _create_group_structure(championship, teams, round_number, scheduled_at)
        created += group_created

    elif championship.stage_format == StageFormat.GROUP_THEN_PLAYOFFS:
        round_number, group_created = _create_group_structure(championship, teams, round_number, scheduled_at)
        created += group_created

        playoff_slots = (championship.group_count or 0) * (championship.teams_advancing_per_group or 0)
        _round_number, playoff_created = _create_playoff_structure(
            championship,
            [],
            playoff_slots,
            round_number,
            scheduled_at,
        )
        created += playoff_created

    elif championship.stage_format == StageFormat.SINGLE_ELIMINATION:
        _round_number, playoff_created = _create_single_elimination(
            championship,
            teams,
            championship.max_teams,
            round_number,
            scheduled_at,
        )
        created += playoff_created

    elif championship.stage_format == StageFormat.DOUBLE_ELIMINATION:
        _round_number, playoff_created = _create_double_elimination(
            championship,
            teams,
            championship.max_teams,
            round_number,
            scheduled_at,
        )
        created += playoff_created

    return {"created": created, "skipped": False}
