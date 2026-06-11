from datetime import date
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.matches.models import GameResult, Group, GroupStanding, Match, Phase
from apps.teams.models import Team
from apps.championships.services import ensure_championship_structure

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


class ChampionshipViewTest(ChampionshipTestCase):
    def championship_payload(self, **overrides):
        data = {
            "name": "Premier Cup",
            "game": "Valorant",
            "status": StatusChampionship.OPEN,
            "max_teams": 8,
            "start_date": "2026-06-20",
            "stage_format": StageFormat.SINGLE_ELIMINATION,
            "group_count": "",
            "teams_per_group": "",
            "teams_advancing_per_group": "",
            "group_match_format": "",
            "playoff_format": PlayoffFormat.SINGLE_ELIMINATION,
            "playoff_match_format": MatchFormat.BO1,
            "final_match_format": MatchFormat.BO3,
            "seeding_method": SeedingMethodChampionship.RANDOM,
        }
        data.update(overrides)
        return data

    def add_owner(self, championship, user=None):
        return ChampionshipStaff.objects.create(
            championship=championship,
            user=user or championship.created_by,
            role=RoleStaff.OWNER,
        )

    def test_available_championship_filters_use_get_params(self):
        user = self.create_user("filter_user")
        target = self.create_championship(
            created_by=self.create_user("filter_owner_a"),
            name="Valorant Masters",
            game="Valorant",
            status=StatusChampionship.OPEN,
            start_date=date(2026, 6, 20),
            stage_format=StageFormat.SINGLE_ELIMINATION,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO1,
            final_match_format=MatchFormat.BO3,
        )
        self.create_championship(
            created_by=self.create_user("filter_owner_b"),
            name="League Finals",
            game="League of Legends",
            status=StatusChampionship.FINISHED,
            start_date=date(2026, 6, 21),
            stage_format=StageFormat.DOUBLE_ELIMINATION,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.DOUBLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO1,
            final_match_format=MatchFormat.BO3,
        )
        self.client.login(username=user.username, password="testpass123")

        response = self.client.get(reverse("championship:available-championship-list"), {
            "q": "masters",
            "game": "Valorant",
            "status": StatusChampionship.OPEN,
            "stage_format": StageFormat.SINGLE_ELIMINATION,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [target])
        self.assertIn("q=masters", response.context["filter_query"])
        self.assertEqual(response.context["filters"]["status"], StatusChampionship.OPEN)

    def test_available_championship_ignores_draft_status_filter(self):
        user = self.create_user("draft_filter_user")
        visible = self.create_championship(
            created_by=self.create_user("draft_filter_owner_a"),
            name="Open Cup",
            status=StatusChampionship.OPEN,
            start_date=date(2026, 6, 20),
        )
        self.create_championship(
            created_by=self.create_user("draft_filter_owner_b"),
            name="Draft Cup",
            status=StatusChampionship.DRAFT,
        )
        self.client.login(username=user.username, password="testpass123")

        response = self.client.get(
            reverse("championship:available-championship-list"),
            {"status": StatusChampionship.DRAFT},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [visible])
        self.assertEqual(response.context["filters"]["status"], "")

    def test_create_championship_starts_as_draft_and_adds_owner(self):
        owner = self.create_user("create_owner")
        self.client.login(username=owner.username, password="testpass123")

        response = self.client.post(
            reverse("championship:management-championship-create"),
            self.championship_payload(status=StatusChampionship.IN_PROGRESS, start_date=""),
        )

        championship = Championship.objects.get(name="Premier Cup")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(championship.status, StatusChampionship.DRAFT)
        self.assertEqual(championship.created_by, owner)
        self.assertTrue(
            ChampionshipStaff.objects.filter(
                championship=championship,
                user=owner,
                role=RoleStaff.OWNER,
            ).exists()
        )

    def test_only_owner_can_edit_championship(self):
        owner = self.create_user("edit_owner")
        moderator = self.create_user("edit_mod")
        championship = self.create_championship(created_by=owner)
        self.add_owner(championship, owner)
        ChampionshipStaff.objects.create(
            championship=championship,
            user=moderator,
            role=RoleStaff.MODERATOR,
        )
        self.client.login(username=moderator.username, password="testpass123")

        response = self.client.get(reverse("championship:management-championship-edit", args=[championship.pk]))

        self.assertEqual(response.status_code, 403)

    def test_edit_to_in_progress_generates_matches(self):
        owner = self.create_user("transition_owner")
        championship = self.create_championship(
            created_by=owner,
            status=StatusChampionship.OPEN,
            start_date=date(2026, 6, 20),
            stage_format=StageFormat.SINGLE_ELIMINATION,
            max_teams=8,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO1,
            final_match_format=MatchFormat.BO3,
        )
        self.add_owner(championship, owner)
        self.client.login(username=owner.username, password="testpass123")

        response = self.client.post(
            reverse("championship:management-championship-edit", args=[championship.pk]),
            self.championship_payload(name=championship.name, status=StatusChampionship.IN_PROGRESS),
        )

        championship.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(championship.status, StatusChampionship.IN_PROGRESS)
        self.assertEqual(Match.objects.filter(championship=championship).count(), 7)

    def test_registration_and_cancel_use_selected_captained_team(self):
        captain = self.create_user("multi_captain")
        championship = self.create_championship(
            created_by=self.create_user("reg_owner"),
            status=StatusChampionship.OPEN,
            start_date=date(2026, 6, 20),
        )
        team_a = self.create_team("Team A", captain=captain)
        team_b = self.create_team("Team B", captain=captain)
        self.client.login(username=captain.username, password="testpass123")

        register_response = self.client.post(
            reverse("championship:championship-register", args=[championship.pk]),
            {"team_id": team_b.pk},
        )

        self.assertEqual(register_response.status_code, 302)
        registration = Registration.objects.get(championship=championship)
        self.assertEqual(registration.team, team_b)
        self.assertEqual(registration.status, StatusRegistration.PENDING)

        cancel_response = self.client.post(
            reverse("championship:championship-cancel-registration", args=[championship.pk]),
            {"team_id": team_b.pk},
        )

        self.assertEqual(cancel_response.status_code, 302)
        self.assertFalse(Registration.objects.filter(championship=championship, team__in=[team_a, team_b]).exists())

    def test_structure_requires_running_or_finished_championship(self):
        user = self.create_user("structure_user")
        championship = self.create_championship(created_by=user, status=StatusChampionship.DRAFT)
        self.client.login(username=user.username, password="testpass123")

        response = self.client.get(reverse("championship:championship-structure", args=[championship.pk]))

        self.assertEqual(response.status_code, 403)

    def test_structure_view_renders_generated_matches(self):
        user = self.create_user("structure_owner")
        championship = self.create_championship(
            created_by=user,
            status=StatusChampionship.IN_PROGRESS,
            start_date=date(2026, 6, 20),
            stage_format=StageFormat.SINGLE_ELIMINATION,
            max_teams=4,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO1,
            final_match_format=MatchFormat.BO3,
        )
        ensure_championship_structure(championship)
        self.client.login(username=user.username, password="testpass123")

        response = self.client.get(reverse("championship:championship-structure", args=[championship.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chaveamento")
        self.assertContains(response, "A definir")

    def test_generation_without_registered_teams_creates_placeholder_matches(self):
        championship = self.create_championship(
            status=StatusChampionship.IN_PROGRESS,
            start_date=date(2026, 6, 20),
            stage_format=StageFormat.SINGLE_ELIMINATION,
            max_teams=4,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO1,
            final_match_format=MatchFormat.BO3,
        )

        result = ensure_championship_structure(championship)

        self.assertEqual(result["created"], 3)
        self.assertEqual(Match.objects.filter(championship=championship, team_a__isnull=True, team_b__isnull=True).count(), 3)


class PopulateGameChampCommandTest(TestCase):
    def run_command(self):
        out = StringIO()
        call_command("populate_gamechamp", stdout=out)
        return out.getvalue()

    def test_populate_gamechamp_creates_seed_championships_with_matches_when_needed(self):
        output = self.run_command()

        championship = Championship.objects.get(name="Seed Double Elim Finished")

        self.assertIn("Todos os campeonatos foram criados com sucesso.", output)
        self.assertEqual(championship.status, StatusChampionship.FINISHED)
        self.assertEqual(championship.stage_format, StageFormat.DOUBLE_ELIMINATION)
        self.assertEqual(championship.playoff_format, PlayoffFormat.DOUBLE_ELIMINATION)
        self.assertIsNotNone(championship.champion)
        self.assertEqual(Championship.objects.filter(name__startswith="Seed ").count(), 9)
        self.assertEqual(Team.objects.filter(name__startswith="Seed ").count(), 20)
        self.assertEqual(User.objects.filter(username__startswith="seed_").count(), 62)
        self.assertEqual(
            Registration.objects.filter(
                championship=championship,
                status=StatusRegistration.APPROVED,
            ).count(),
            8,
        )
        self.assertEqual(Group.objects.filter(championship=championship).count(), 0)
        self.assertEqual(GroupStanding.objects.filter(group__championship=championship).count(), 0)
        self.assertEqual(Match.objects.filter(championship=championship, phase=Phase.PLAYOFF).count(), 13)
        self.assertEqual(Match.objects.filter(championship=championship, phase=Phase.GRAND_FINAL).count(), 1)
        self.assertTrue(Match.objects.filter(championship=championship, playoff_round__lt=0).exists())
        for seeded in Championship.objects.filter(
            name__startswith="Seed ",
            status__in=[StatusChampionship.IN_PROGRESS, StatusChampionship.FINISHED],
        ):
            self.assertTrue(Match.objects.filter(championship=seeded).exists(), seeded.name)

    def test_populate_gamechamp_can_be_run_again_without_duplicating_seed_data(self):
        self.run_command()
        self.run_command()

        championship = Championship.objects.get(name="Seed Double Elim Finished")

        self.assertEqual(Championship.objects.filter(name__startswith="Seed ").count(), 9)
        self.assertEqual(Team.objects.filter(name__startswith="Seed ").count(), 20)
        self.assertEqual(User.objects.filter(username__startswith="seed_").count(), 62)
        self.assertEqual(Registration.objects.filter(championship=championship).count(), 8)
        self.assertEqual(Match.objects.filter(championship=championship).count(), 14)
