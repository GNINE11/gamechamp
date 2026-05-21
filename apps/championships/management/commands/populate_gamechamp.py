from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.championships.models import (
    Championship,
    ChampionshipStaff,
    MatchFormat,
    PlayoffFormat,
    Registration,
    RoleStaff,
    SeedingMethodChampionship,
    StageFormat,
    StatusChampionship,
    StatusRegistration,
    TiebreakerCriterion,
    TiebreakerRule,
)
from apps.matches.models import GameFormat, GameResult, GameStatus, Group, GroupStanding, Match, Phase
from apps.teams.models import Invite, InviteStatus, Team


class Command(BaseCommand):
    help = "Popula o banco com dados de exemplo para testar o GameChamp."

    def handle(self, *args, **options):
        today = timezone.localdate()
        password = "gamechamp123"

        users = self.create_users(password)
        teams = self.create_teams(users)
        self.create_invites(users, teams)
        championship = self.create_championship(users["alice"], today)
        self.create_staff(championship, users)
        self.create_tiebreakers(championship)
        self.create_registrations(championship, teams)
        groups = self.create_groups(championship, teams)
        self.create_matches(championship, groups, teams, today)

        self.stdout.write(self.style.SUCCESS("Dados de exemplo criados/atualizados com sucesso."))
        self.stdout.write(f"Usuarios seedados usam a senha: {password}")

    def create_users(self, password):
        seed_users = {
            "alice": {
                "username": "seed_alice",
                "email": "alice.seed@example.com",
                "bio": "Capita estrategista.",
                "ranking_score": 1800,
            },
            "bruno": {
                "username": "seed_bruno",
                "email": "bruno.seed@example.com",
                "bio": "Entry fragger.",
                "ranking_score": 1620,
            },
            "clara": {
                "username": "seed_clara",
                "email": "clara.seed@example.com",
                "bio": "IGL focada em torneios.",
                "ranking_score": 1710,
            },
            "diego": {
                "username": "seed_diego",
                "email": "diego.seed@example.com",
                "bio": "Suporte flex.",
                "ranking_score": 1490,
            },
            "erica": {
                "username": "seed_erica",
                "email": "erica.seed@example.com",
                "bio": "Sniper.",
                "ranking_score": 1930,
            },
            "felipe": {
                "username": "seed_felipe",
                "email": "felipe.seed@example.com",
                "bio": "Coach e analista.",
                "ranking_score": 1550,
            },
        }

        users = {}
        for key, data in seed_users.items():
            username = data.pop("username")
            user, _ = User.objects.update_or_create(username=username, defaults=data)
            user.set_password(password)
            user.save(update_fields=["password"])
            users[key] = user

        return users

    def create_teams(self, users):
        team_data = {
            "dragons": {
                "name": "Seed Dragons",
                "captain": users["alice"],
                "members": [users["alice"], users["bruno"]],
            },
            "ninjas": {
                "name": "Seed Ninjas",
                "captain": users["clara"],
                "members": [users["clara"], users["diego"]],
            },
            "titans": {
                "name": "Seed Titans",
                "captain": users["erica"],
                "members": [users["erica"], users["felipe"]],
            },
            "falcons": {
                "name": "Seed Falcons",
                "captain": users["felipe"],
                "members": [users["felipe"], users["alice"]],
            },
        }

        teams = {}
        for key, data in team_data.items():
            members = data.pop("members")
            team, _ = Team.objects.update_or_create(
                name=data["name"],
                defaults={"captain": data["captain"]},
            )
            for member in members:
                team.add_member(member)
            teams[key] = team

        return teams

    def create_invites(self, users, teams):
        Invite.objects.update_or_create(
            team=teams["dragons"],
            invited_player=users["erica"],
            defaults={"status": InviteStatus.PENDING},
        )
        Invite.objects.update_or_create(
            team=teams["ninjas"],
            invited_player=users["bruno"],
            defaults={"status": InviteStatus.ACCEPTED},
        )

    def create_championship(self, owner, today):
        championship, _ = Championship.objects.update_or_create(
            name="Seed CS2 Cup",
            defaults={
                "game": "Counter-Strike 2",
                "status": StatusChampionship.OPEN,
                "max_teams": 4,
                "start_date": today + timedelta(days=7),
                "stage_format": StageFormat.GROUP_THEN_PLAYOFFS,
                "group_count": 2,
                "teams_per_group": 2,
                "teams_advancing_per_group": 1,
                "group_match_format": MatchFormat.BO1,
                "playoff_format": PlayoffFormat.SINGLE_ELIMINATION,
                "playoff_match_format": MatchFormat.BO3,
                "final_match_format": MatchFormat.BO5,
                "third_place_match": True,
                "seeding_method": SeedingMethodChampionship.RANDOM,
                "created_by": owner,
            },
        )
        return championship

    def create_staff(self, championship, users):
        ChampionshipStaff.objects.update_or_create(
            championship=championship,
            user=users["alice"],
            defaults={"role": RoleStaff.OWNER},
        )
        ChampionshipStaff.objects.update_or_create(
            championship=championship,
            user=users["felipe"],
            defaults={"role": RoleStaff.MODERATOR},
        )

    def create_tiebreakers(self, championship):
        criteria = [
            (1, TiebreakerCriterion.POINTS),
            (2, TiebreakerCriterion.WINS),
            (3, TiebreakerCriterion.ROUND_DIFF),
        ]
        for priority, criterion in criteria:
            TiebreakerRule.objects.update_or_create(
                championship=championship,
                priority=priority,
                defaults={"criterion": criterion},
            )

    def create_registrations(self, championship, teams):
        for team in teams.values():
            Registration.objects.update_or_create(
                championship=championship,
                team=team,
                defaults={"status": StatusRegistration.APPROVED},
            )

    def create_groups(self, championship, teams):
        group_a, _ = Group.objects.update_or_create(championship=championship, name="A")
        group_b, _ = Group.objects.update_or_create(championship=championship, name="B")

        standings = [
            (group_a, teams["dragons"], 1, 0, 3, 13, 8, 5, 1),
            (group_a, teams["titans"], 0, 1, 0, 8, 13, -5, 2),
            (group_b, teams["ninjas"], 1, 0, 3, 13, 10, 3, 1),
            (group_b, teams["falcons"], 0, 1, 0, 10, 13, -3, 2),
        ]
        for group, team, wins, losses, points, won, lost, diff, position in standings:
            GroupStanding.objects.update_or_create(
                group=group,
                team=team,
                defaults={
                    "wins": wins,
                    "losses": losses,
                    "points": points,
                    "rounds_won": won,
                    "rounds_lost": lost,
                    "round_diff": diff,
                    "position": position,
                },
            )

        return {"a": group_a, "b": group_b}

    def create_matches(self, championship, groups, teams, today):
        group_match, _ = Match.objects.update_or_create(
            championship=championship,
            phase=Phase.GROUP,
            group=groups["a"],
            round_number=1,
            team_a=teams["dragons"],
            team_b=teams["titans"],
            defaults={
                "match_format": GameFormat.BO1,
                "winner": teams["dragons"],
                "status": GameStatus.FINISHED,
                "scheduled_at": today + timedelta(days=8),
            },
        )
        GameResult.objects.update_or_create(
            match_id=group_match,
            game_number=1,
            defaults={
                "winner": teams["dragons"],
                "score_a": 13,
                "score_b": 8,
                "map_name": "Mirage",
            },
        )

        Match.objects.update_or_create(
            championship=championship,
            phase=Phase.PLAYOFF,
            playoff_round=1,
            round_number=2,
            team_a=teams["dragons"],
            team_b=teams["ninjas"],
            defaults={
                "match_format": GameFormat.BO3,
                "winner": None,
                "status": GameStatus.SCHEDULED,
                "scheduled_at": today + timedelta(days=10),
            },
        )
