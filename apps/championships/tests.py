from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.teams.models import Team

from .models import (
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


class ChampionshipTestCase(TestCase):
    def create_user(self, username="owner"):
        return User.objects.create_user(username=username, password="testpass123")

    def create_team(self, name="Alpha", captain=None):
        captain = captain or self.create_user(f"{name.lower()}_captain")
        return Team.objects.create(name=name, captain=captain)

    def create_championship(self, **overrides):
        created_by = overrides.pop("created_by", None) or self.create_user()
        data = {
            "name": "Winter Cup",
            "game": "Valorant",
            "status": StatusChampionship.DRAFT,
            "max_teams": 4,
            "stage_format": StageFormat.ROUND_ROBIN,
            "group_count": 1,
            "teams_per_group": 4,
            "teams_advancing_per_group": 0,
            "group_match_format": MatchFormat.BO1,
            "seeding_method": SeedingMethodChampionship.RANDOM,
            "created_by": created_by,
        }
        data.update(overrides)
        return Championship.objects.create(**data)


class ChampionshipModelTest(ChampionshipTestCase):
    def test_str_shows_name_and_game(self):
        championship = self.create_championship(name="Major", game="CS2")

        self.assertEqual(str(championship), "Major (CS2)")

    def test_clean_requires_at_least_two_teams(self):
        championship = self.create_championship(max_teams=1)

        with self.assertRaises(ValidationError):
            championship.full_clean()

    def test_clean_requires_start_date_when_not_draft(self):
        championship = self.create_championship(status=StatusChampionship.OPEN, start_date=None)

        with self.assertRaises(ValidationError):
            championship.full_clean()

    def test_clean_allows_open_championship_with_start_date(self):
        championship = self.create_championship(
            status=StatusChampionship.OPEN,
            start_date=date(2026, 6, 1),
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
        )

        championship.full_clean()


class ChampionshipStaffModelTest(ChampionshipTestCase):
    def test_str_shows_user_role_and_championship(self):
        championship = self.create_championship()
        staff = ChampionshipStaff.objects.create(
            user=championship.created_by,
            championship=championship,
            role=RoleStaff.OWNER,
        )

        self.assertEqual(str(staff), "owner - Dono - Winter Cup")

    def test_clean_allows_only_one_owner_per_championship(self):
        championship = self.create_championship()
        ChampionshipStaff.objects.create(
            user=championship.created_by,
            championship=championship,
            role=RoleStaff.OWNER,
        )
        second_owner = ChampionshipStaff(
            user=self.create_user("second_owner"),
            championship=championship,
            role=RoleStaff.OWNER,
        )

        with self.assertRaises(ValidationError):
            second_owner.full_clean()


class TiebreakerRuleModelTest(ChampionshipTestCase):
    def test_str_shows_priority_and_criterion_display(self):
        championship = self.create_championship()
        rule = TiebreakerRule.objects.create(
            championship=championship,
            priority=1,
            criterion=TiebreakerCriterion.POINTS,
        )

        self.assertEqual(str(rule), "1 - Pontos")

    def test_clean_rejects_duplicate_priority_in_championship(self):
        championship = self.create_championship()
        TiebreakerRule.objects.create(
            championship=championship,
            priority=1,
            criterion=TiebreakerCriterion.POINTS,
        )
        duplicate_priority = TiebreakerRule(
            championship=championship,
            priority=1,
            criterion=TiebreakerCriterion.WINS,
        )

        with self.assertRaises(ValidationError):
            duplicate_priority.full_clean()

    def test_clean_rejects_duplicate_criterion_in_championship(self):
        championship = self.create_championship()
        TiebreakerRule.objects.create(
            championship=championship,
            priority=1,
            criterion=TiebreakerCriterion.POINTS,
        )
        duplicate_criterion = TiebreakerRule(
            championship=championship,
            priority=2,
            criterion=TiebreakerCriterion.POINTS,
        )

        with self.assertRaises(ValidationError):
            duplicate_criterion.full_clean()


class RegistrationModelTest(ChampionshipTestCase):
    def create_open_championship(self, **overrides):
        defaults = {
            "status": StatusChampionship.OPEN,
            "start_date": date(2026, 6, 1),
        }
        defaults.update(overrides)
        return self.create_championship(**defaults)

    def test_str_shows_team_championship_and_status(self):
        championship = self.create_open_championship()
        team = self.create_team()
        registration = Registration.objects.create(championship=championship, team=team)

        self.assertEqual(
            str(registration),
            f"{team} - {championship} ({StatusRegistration.PENDING})",
        )

    def test_clean_requires_open_championship(self):
        championship = self.create_championship(status=StatusChampionship.DRAFT)
        team = self.create_team()
        registration = Registration(championship=championship, team=team)

        with self.assertRaises(ValidationError):
            registration.full_clean()

    def test_clean_rejects_duplicate_team_registration(self):
        championship = self.create_open_championship()
        team = self.create_team()
        Registration.objects.create(championship=championship, team=team)
        duplicate = Registration(championship=championship, team=team)

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_clean_rejects_approval_when_championship_is_full(self):
        championship = self.create_open_championship(max_teams=2)
        Registration.objects.create(
            championship=championship,
            team=self.create_team("Alpha"),
            status=StatusRegistration.APPROVED,
        )
        Registration.objects.create(
            championship=championship,
            team=self.create_team("Bravo"),
            status=StatusRegistration.APPROVED,
        )
        extra_registration = Registration(
            championship=championship,
            team=self.create_team("Charlie"),
            status=StatusRegistration.APPROVED,
        )

        with self.assertRaises(ValidationError):
            extra_registration.full_clean()
