from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.championships.models import (
    Championship,
    MatchFormat,
    StageFormat,
    StatusChampionship,
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
