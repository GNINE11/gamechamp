from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
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
from apps.teams.models import Team


class Command(BaseCommand):
    help = "Popula o banco com um campeonato completo de exemplo para testar o GameChamp."

    def handle(self, *args, **options):
        today = timezone.localdate()
        password = "gamechamp123"

        with transaction.atomic():
            self.clear_existing_seed_data()
            users = self.create_users(password)
            teams = self.create_teams(users)
            championship = self.create_championship(users["owner"], today)
            self.create_staff(championship, users)
            self.create_tiebreakers(championship)
            self.create_registrations(championship, teams)
            groups, advancing_teams, next_date, next_round = self.create_group_stage(
                championship,
                teams,
                today + timedelta(days=1),
            )
            champion = self.create_double_elimination_playoff(
                championship,
                advancing_teams,
                next_date,
                next_round,
            )
            championship.status = StatusChampionship.FINISHED
            championship.champion = champion
            championship.full_clean()
            championship.save(update_fields=["status", "champion"])

        self.stdout.write(self.style.SUCCESS("Campeonato completo criado com sucesso."))
        self.stdout.write(f"Usuarios seedados usam a senha: {password}")
        self.stdout.write(f"Campeonato: {championship.name}")
        self.stdout.write(f"Equipes inscritas: {len(teams)}")
        self.stdout.write(f"Grupos criados: {len(groups)}")
        self.stdout.write(f"Campeao: {champion.name}")

    def clear_existing_seed_data(self):
        Championship.objects.filter(name__startswith="Seed ").delete()
        Team.objects.filter(name__startswith="Seed ").delete()
        User.objects.filter(username__startswith="seed_").delete()

    def create_users(self, password):
        users = {
            "owner": User.objects.create_user(
                username="seed_owner",
                email="owner.seed@example.com",
                password=password,
                bio="Organizador do campeonato seed.",
                ranking_score=2200,
            ),
            "moderator": User.objects.create_user(
                username="seed_moderator",
                email="moderator.seed@example.com",
                password=password,
                bio="Moderador do campeonato seed.",
                ranking_score=1900,
            ),
        }

        for index in range(1, 17):
            users[f"captain_{index:02d}"] = User.objects.create_user(
                username=f"seed_captain_{index:02d}",
                email=f"captain{index:02d}.seed@example.com",
                password=password,
                bio=f"Capitao da equipe seed {index:02d}.",
                ranking_score=1500 + index * 25,
            )

        return users

    def create_teams(self, users):
        team_names = [
            "Seed Dragons",
            "Seed Ninjas",
            "Seed Titans",
            "Seed Falcons",
            "Seed Phoenix",
            "Seed Vikings",
            "Seed Wolves",
            "Seed Sharks",
            "Seed Rangers",
            "Seed Knights",
            "Seed Hunters",
            "Seed Eclipse",
            "Seed Quantum",
            "Seed Aurora",
            "Seed Venom",
            "Seed Storm",
        ]

        teams = []
        for index, name in enumerate(team_names, start=1):
            team = Team.objects.create(
                name=name,
                captain=users[f"captain_{index:02d}"],
            )
            teams.append(team)

        return teams

    def create_championship(self, owner, today):
        championship = Championship(
            name="Seed Major Completo",
            game="Counter-Strike 2",
            status=StatusChampionship.OPEN,
            max_teams=16,
            start_date=today + timedelta(days=1),
            stage_format=StageFormat.GROUP_THEN_PLAYOFFS,
            group_count=4,
            teams_per_group=4,
            teams_advancing_per_group=2,
            group_match_format=MatchFormat.BO1,
            playoff_format=PlayoffFormat.DOUBLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            third_place_match=False,
            seeding_method=SeedingMethodChampionship.MANUAL,
            created_by=owner,
        )
        championship.full_clean()
        championship.save()
        return championship

    def create_staff(self, championship, users):
        ChampionshipStaff.objects.create(
            championship=championship,
            user=users["owner"],
            role=RoleStaff.OWNER,
        )
        ChampionshipStaff.objects.create(
            championship=championship,
            user=users["moderator"],
            role=RoleStaff.MODERATOR,
        )

    def create_tiebreakers(self, championship):
        criteria = [
            (1, TiebreakerCriterion.POINTS),
            (2, TiebreakerCriterion.WINS),
            (3, TiebreakerCriterion.ROUND_DIFF),
            (4, TiebreakerCriterion.ROUNDS_WON),
            (5, TiebreakerCriterion.WIN_RATE),
        ]
        for priority, criterion in criteria:
            TiebreakerRule.objects.create(
                championship=championship,
                priority=priority,
                criterion=criterion,
            )

    def create_registrations(self, championship, teams):
        for team in teams:
            registration = Registration(
                championship=championship,
                team=team,
                status=StatusRegistration.APPROVED,
            )
            registration.full_clean()
            registration.save()

    def create_group_stage(self, championship, teams, start_date):
        groups = []
        advancing_teams = []
        scheduled_at = start_date
        round_number = 1

        for group_index, group_name in enumerate(["A", "B", "C", "D"]):
            group = Group.objects.create(championship=championship, name=group_name)
            groups.append(group)
            group_teams = teams[group_index * 4:(group_index + 1) * 4]
            records = {
                team: {"wins": 0, "losses": 0, "rounds_won": 0, "rounds_lost": 0}
                for team in group_teams
            }

            for first_index, team_a in enumerate(group_teams):
                for team_b in group_teams[first_index + 1:]:
                    winner = team_a
                    loser = team_b
                    records[winner]["wins"] += 1
                    records[winner]["rounds_won"] += 13
                    records[winner]["rounds_lost"] += 8
                    records[loser]["losses"] += 1
                    records[loser]["rounds_won"] += 8
                    records[loser]["rounds_lost"] += 13

                    self.create_finished_match(
                        championship=championship,
                        team_a=team_a,
                        team_b=team_b,
                        winner=winner,
                        match_format=GameFormat.BO1,
                        phase=Phase.GROUP,
                        round_number=round_number,
                        scheduled_at=scheduled_at,
                        group=group,
                    )
                    scheduled_at += timedelta(days=1)
                    round_number += 1

            ordered_group_teams = sorted(
                group_teams,
                key=lambda team: (
                    records[team]["wins"],
                    records[team]["rounds_won"] - records[team]["rounds_lost"],
                    records[team]["rounds_won"],
                ),
                reverse=True,
            )
            advancing_teams.extend(ordered_group_teams[:2])
            self.create_group_standings(group, ordered_group_teams, records)

        return groups, advancing_teams, scheduled_at, round_number

    def create_group_standings(self, group, ordered_teams, records):
        for position, team in enumerate(ordered_teams, start=1):
            record = records[team]
            standing = GroupStanding(
                group=group,
                team=team,
                wins=record["wins"],
                losses=record["losses"],
                points=record["wins"] * 3,
                rounds_won=record["rounds_won"],
                rounds_lost=record["rounds_lost"],
                round_diff=record["rounds_won"] - record["rounds_lost"],
                position=position,
            )
            standing.full_clean()
            standing.save()

    def create_double_elimination_playoff(self, championship, seeds, scheduled_at, round_number):
        def playoff_match(team_a, team_b, winner, playoff_round):
            nonlocal scheduled_at, round_number
            match = self.create_finished_match(
                championship=championship,
                team_a=team_a,
                team_b=team_b,
                winner=winner,
                match_format=GameFormat.BO3,
                phase=Phase.PLAYOFF,
                round_number=round_number,
                scheduled_at=scheduled_at,
                playoff_round=playoff_round,
            )
            scheduled_at += timedelta(days=1)
            round_number += 1
            return match

        upper_quarters = [
            playoff_match(seeds[0], seeds[7], seeds[0], 1),
            playoff_match(seeds[2], seeds[5], seeds[2], 1),
            playoff_match(seeds[4], seeds[3], seeds[4], 1),
            playoff_match(seeds[6], seeds[1], seeds[6], 1),
        ]
        lower_round_one = [
            playoff_match(
                upper_quarters[0].team_b,
                upper_quarters[1].team_b,
                upper_quarters[0].team_b,
                2,
            ),
            playoff_match(
                upper_quarters[2].team_b,
                upper_quarters[3].team_b,
                upper_quarters[3].team_b,
                2,
            ),
        ]
        upper_semis = [
            playoff_match(
                upper_quarters[0].winner,
                upper_quarters[1].winner,
                upper_quarters[0].winner,
                3,
            ),
            playoff_match(
                upper_quarters[2].winner,
                upper_quarters[3].winner,
                upper_quarters[2].winner,
                3,
            ),
        ]
        lower_round_two = [
            playoff_match(
                lower_round_one[0].winner,
                upper_semis[1].team_b,
                upper_semis[1].team_b,
                4,
            ),
            playoff_match(
                lower_round_one[1].winner,
                upper_semis[0].team_b,
                upper_semis[0].team_b,
                4,
            ),
        ]
        lower_semifinal = playoff_match(
            lower_round_two[0].winner,
            lower_round_two[1].winner,
            lower_round_two[1].winner,
            5,
        )
        upper_final = playoff_match(
            upper_semis[0].winner,
            upper_semis[1].winner,
            upper_semis[0].winner,
            5,
        )
        lower_final = playoff_match(
            lower_semifinal.winner,
            upper_final.team_b,
            upper_final.team_b,
            6,
        )

        grand_final = self.create_finished_match(
            championship=championship,
            team_a=upper_final.winner,
            team_b=lower_final.winner,
            winner=upper_final.winner,
            match_format=GameFormat.BO5,
            phase=Phase.GRAND_FINAL,
            round_number=round_number,
            scheduled_at=scheduled_at,
        )

        return grand_final.winner

    def create_finished_match(
        self,
        championship,
        team_a,
        team_b,
        winner,
        match_format,
        phase,
        round_number,
        scheduled_at,
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
            winner=winner,
            status=GameStatus.FINISHED,
            scheduled_at=scheduled_at,
        )
        match.full_clean()
        match.save()

        games_to_win = {
            GameFormat.BO1: 1,
            GameFormat.BO3: 2,
            GameFormat.BO5: 3,
        }[match_format]

        for game_number in range(1, games_to_win + 1):
            winner_is_team_a = winner == team_a
            result = GameResult(
                match_id=match,
                winner=winner,
                game_number=game_number,
                score_a=13 if winner_is_team_a else 8,
                score_b=8 if winner_is_team_a else 13,
                map_name=f"Seed Map {game_number}",
            )
            result.full_clean()
            result.save()

        return match
