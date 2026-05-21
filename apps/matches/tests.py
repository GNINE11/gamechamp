from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.championships.models import (
    Championship,
    MatchFormat,
    PlayoffFormat,
    Registration,
    StageFormat,
    StatusChampionship,
    StatusRegistration,
)
from apps.teams.models import Team

from .models import GameFormat, GameResult, GameStatus, Group, GroupStanding, Match, Phase


class MatchTestCase(TestCase):
    def create_user(self, username):
        return User.objects.create_user(username=username, password="testpass123")

    def create_team(self, name):
        return Team.objects.create(name=name, captain=self.create_user(f"{name.lower()}_captain"))

    def create_championship(self):
        return Championship.objects.create(
            name="Winter Cup",
            game="Valorant",
            status=StatusChampionship.OPEN,
            max_teams=4,
            start_date=date(2026, 6, 1),
            stage_format=StageFormat.ROUND_ROBIN,
            group_count=1,
            teams_per_group=4,
            teams_advancing_per_group=0,
            group_match_format=MatchFormat.BO1,
            created_by=self.create_user("owner"),
        )

    def create_match(self, **overrides):
        championship = overrides.pop("championship", None) or self.create_championship()
        team_a = overrides.pop("team_a", None) or self.create_team("Alpha")
        team_b = overrides.pop("team_b", None) or self.create_team("Bravo")
        group = overrides.pop("group", None)
        data = {
            "championship": championship,
            "match_format": GameFormat.BO1,
            "phase": Phase.PLAYOFF,
            "group": group,
            "round_number": 1,
            "team_a": team_a,
            "team_b": team_b,
            "winner": None,
            "status": GameStatus.SCHEDULED,
            "scheduled_at": date(2026, 6, 2),
        }
        data.update(overrides)
        return Match.objects.create(**data)


class GroupModelTest(MatchTestCase):
    def test_str_shows_group_and_championship(self):
        championship = self.create_championship()
        group = Group.objects.create(championship=championship, name="A")

        self.assertEqual(str(group), f"Grupo: A\nCampeonato: {championship}")


class MatchModelTest(MatchTestCase):
    def test_str_shows_match_details(self):
        championship = self.create_championship()
        team_a = self.create_team("Alpha")
        team_b = self.create_team("Bravo")
        match = self.create_match(
            championship=championship,
            team_a=team_a,
            team_b=team_b,
            winner=team_a,
            status=GameStatus.FINISHED,
        )

        self.assertIn("Alpha vs Bravo", str(match))
        self.assertIn(f"Winner: {team_a}", str(match))

    def test_clean_rejects_same_team_on_both_sides(self):
        team = self.create_team("Alpha")
        match = self.create_match(team_a=team, team_b=team)

        with self.assertRaises(ValidationError):
            match.full_clean()

    def test_clean_requires_group_for_group_phase(self):
        match = self.create_match(phase=Phase.GROUP, group=None)

        with self.assertRaises(ValidationError):
            match.full_clean()

    def test_clean_rejects_group_for_playoff_phase(self):
        championship = self.create_championship()
        group = Group.objects.create(championship=championship, name="A")
        match = self.create_match(championship=championship, phase=Phase.PLAYOFF, group=group)

        with self.assertRaises(ValidationError):
            match.full_clean()

    def test_clean_allows_group_match_with_group(self):
        championship = self.create_championship()
        group = Group.objects.create(championship=championship, name="A")
        match = self.create_match(championship=championship, phase=Phase.GROUP, group=group)

        match.full_clean()


class GroupStandingModelTest(MatchTestCase):
    def test_str_shows_team_group_and_points(self):
        championship = self.create_championship()
        group = Group.objects.create(championship=championship, name="A")
        team = self.create_team("Alpha")
        standing = GroupStanding.objects.create(
            group=group,
            team=team,
            points=3,
            rounds_won=13,
            rounds_lost=8,
            round_diff=5,
        )

        self.assertEqual(str(standing), f"{team} — Grupo {group} (3 pts)")

    def test_clean_rejects_inconsistent_round_diff(self):
        championship = self.create_championship()
        group = Group.objects.create(championship=championship, name="A")
        team = self.create_team("Alpha")
        standing = GroupStanding(
            group=group,
            team=team,
            rounds_won=13,
            rounds_lost=8,
            round_diff=2,
        )

        with self.assertRaises(ValidationError):
            standing.full_clean()

    def test_clean_rejects_duplicate_group_team(self):
        championship = self.create_championship()
        group = Group.objects.create(championship=championship, name="A")
        team = self.create_team("Alpha")
        GroupStanding.objects.create(group=group, team=team)
        duplicate = GroupStanding(group=group, team=team)

        with self.assertRaises(ValidationError):
            duplicate.full_clean()


class GameResultModelTest(MatchTestCase):
    def test_str_shows_match_game_number_and_score(self):
        team_a = self.create_team("Alpha")
        team_b = self.create_team("Bravo")
        match = self.create_match(team_a=team_a, team_b=team_b)
        result = GameResult.objects.create(
            match_id=match,
            winner=team_a,
            game_number=1,
            score_a=13,
            score_b=8,
            map_name="Ascent",
        )

        self.assertIn("Game 1 | 13x8", str(result))

    def test_clean_requires_winner_to_be_one_of_match_teams(self):
        team_a = self.create_team("Alpha")
        team_b = self.create_team("Bravo")
        outsider = self.create_team("Charlie")
        match = self.create_match(team_a=team_a, team_b=team_b)
        result = GameResult(
            match_id=match,
            winner=outsider,
            game_number=1,
            score_a=13,
            score_b=8,
        )

        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_clean_rejects_duplicate_game_number_in_same_match(self):
        team_a = self.create_team("Alpha")
        team_b = self.create_team("Bravo")
        match = self.create_match(team_a=team_a, team_b=team_b)
        GameResult.objects.create(
            match_id=match,
            winner=team_a,
            game_number=1,
            score_a=13,
            score_b=8,
        )
        duplicate = GameResult(
            match_id=match,
            winner=team_b,
            game_number=1,
            score_a=8,
            score_b=13,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()


class CompleteChampionshipFlowTest(MatchTestCase):
    def create_complete_championship(self):
        return Championship.objects.create(
            name="GameChamp Major Completo",
            game="Valorant",
            status=StatusChampionship.OPEN,
            max_teams=16,
            start_date=date(2026, 7, 1),
            stage_format=StageFormat.GROUP_THEN_PLAYOFFS,
            group_count=4,
            teams_per_group=4,
            teams_advancing_per_group=2,
            group_match_format=MatchFormat.BO1,
            playoff_format=PlayoffFormat.DOUBLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            created_by=self.create_user("complete_owner"),
        )

    def create_registered_teams(self, championship, amount=16):
        teams = []

        for index in range(1, amount + 1):
            team = self.create_team(f"Equipe {index:02d}")
            registration = Registration(
                championship=championship,
                team=team,
                status=StatusRegistration.APPROVED,
            )
            registration.full_clean()
            registration.save()
            teams.append(team)

        return teams

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
                map_name=f"Mapa {game_number}",
            )
            result.full_clean()
            result.save()

        return match

    def create_group_stage(self, championship, teams):
        group_names = ["A", "B", "C", "D"]
        groups = []
        advancing_teams = []
        scheduled_at = championship.start_date
        global_round = 1

        for group_index, name in enumerate(group_names):
            group = Group.objects.create(championship=championship, name=name)
            groups.append(group)
            group_teams = teams[group_index * 4:(group_index + 1) * 4]
            records = {
                team: {"wins": 0, "losses": 0, "won": 0, "lost": 0}
                for team in group_teams
            }

            for first_index, team_a in enumerate(group_teams):
                for team_b in group_teams[first_index + 1:]:
                    winner = team_a
                    loser = team_b
                    records[winner]["wins"] += 1
                    records[winner]["won"] += 13
                    records[winner]["lost"] += 8
                    records[loser]["losses"] += 1
                    records[loser]["won"] += 8
                    records[loser]["lost"] += 13

                    self.create_finished_match(
                        championship=championship,
                        team_a=team_a,
                        team_b=team_b,
                        winner=winner,
                        match_format=GameFormat.BO1,
                        phase=Phase.GROUP,
                        group=group,
                        round_number=global_round,
                        scheduled_at=scheduled_at,
                    )
                    scheduled_at += timedelta(days=1)
                    global_round += 1

            ordered_group_teams = sorted(
                group_teams,
                key=lambda team: (
                    records[team]["wins"],
                    records[team]["won"] - records[team]["lost"],
                    records[team]["won"],
                ),
                reverse=True,
            )
            advancing_teams.extend(ordered_group_teams[:2])

            for position, team in enumerate(ordered_group_teams, start=1):
                record = records[team]
                standing = GroupStanding(
                    group=group,
                    team=team,
                    wins=record["wins"],
                    losses=record["losses"],
                    points=record["wins"] * 3,
                    rounds_won=record["won"],
                    rounds_lost=record["lost"],
                    round_diff=record["won"] - record["lost"],
                    position=position,
                )
                standing.full_clean()
                standing.save()

        return groups, advancing_teams, scheduled_at, global_round

    def create_double_elimination_playoff(
        self,
        championship,
        seeds,
        scheduled_at,
        global_round,
    ):
        def playoff_match(team_a, team_b, winner, playoff_round):
            nonlocal scheduled_at, global_round
            match = self.create_finished_match(
                championship=championship,
                team_a=team_a,
                team_b=team_b,
                winner=winner,
                match_format=GameFormat.BO3,
                phase=Phase.PLAYOFF,
                round_number=global_round,
                scheduled_at=scheduled_at,
                playoff_round=playoff_round,
            )
            scheduled_at += timedelta(days=1)
            global_round += 1
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
            round_number=global_round,
            scheduled_at=scheduled_at,
        )

        return grand_final.winner

    def assert_double_elimination_losses(self, championship, seeds, champion):
        playoff_matches = Match.objects.filter(
            championship=championship,
            phase__in=[Phase.PLAYOFF, Phase.GRAND_FINAL],
        )
        losses_by_team = {team.id: 0 for team in seeds}

        for match in playoff_matches:
            for team in [match.team_a, match.team_b]:
                if team.id in losses_by_team and match.winner_id != team.id:
                    losses_by_team[team.id] += 1

        self.assertEqual(losses_by_team[champion.id], 0)
        for team in seeds:
            if team != champion:
                self.assertEqual(losses_by_team[team.id], 2)

    def test_complete_16_team_group_stage_and_double_elimination_championship(self):
        championship = self.create_complete_championship()
        teams = self.create_registered_teams(championship)

        groups, advancing_teams, next_date, next_round = self.create_group_stage(championship, teams)
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

        self.assertEqual(Team.objects.count(), 16)
        self.assertEqual(championship.stage_format, StageFormat.GROUP_THEN_PLAYOFFS)
        self.assertEqual(championship.playoff_format, PlayoffFormat.DOUBLE_ELIMINATION)
        self.assertEqual(
            Registration.objects.filter(
                championship=championship,
                status=StatusRegistration.APPROVED,
            ).count(),
            16,
        )
        self.assertEqual(len(groups), 4)
        self.assertEqual(len(advancing_teams), 8)
        self.assertEqual(
            GroupStanding.objects.filter(group__championship=championship).count(),
            16,
        )
        self.assertEqual(
            Match.objects.filter(championship=championship, phase=Phase.GROUP).count(),
            24,
        )
        self.assertEqual(
            Match.objects.filter(championship=championship, phase=Phase.PLAYOFF).count(),
            13,
        )
        self.assertEqual(
            Match.objects.filter(championship=championship, phase=Phase.GRAND_FINAL).count(),
            1,
        )
        self.assertEqual(
            Match.objects.filter(championship=championship, status=GameStatus.FINISHED).count(),
            38,
        )
        self.assertEqual(
            GameResult.objects.filter(match_id__championship=championship).count(),
            53,
        )
        self.assert_double_elimination_losses(championship, advancing_teams, champion)
        self.assertEqual(championship.champion, teams[0])
