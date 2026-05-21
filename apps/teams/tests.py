from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User

from .models import Invite, InviteStatus, Team, TeamMembership


class TeamModelTest(TestCase):
    def setUp(self):
        self.captain = User.objects.create_user("captain", password="testpass123")
        self.player = User.objects.create_user("player", password="testpass123")
        self.other_player = User.objects.create_user("other", password="testpass123")

    def test_team_save_adds_captain_as_member(self):
        team = Team.objects.create(name="Alpha", captain=self.captain)

        self.assertEqual(str(team), "Alpha")
        self.assertTrue(team.memberships.filter(player=self.captain).exists())
        self.assertIn(self.captain, team.members.all())

    def test_add_member_is_idempotent(self):
        team = Team.objects.create(name="Alpha", captain=self.captain)

        membership, created = team.add_member(self.player)
        duplicate_membership, duplicate_created = team.add_member(self.player)

        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(membership, duplicate_membership)
        self.assertEqual(team.memberships.filter(player=self.player).count(), 1)

    def test_remove_member_does_not_allow_removing_captain(self):
        team = Team.objects.create(name="Alpha", captain=self.captain)

        with self.assertRaises(ValidationError):
            team.remove_member(self.captain)

    def test_remove_member_deletes_non_captain_membership(self):
        team = Team.objects.create(name="Alpha", captain=self.captain)
        team.add_member(self.player)

        deleted_count, _ = team.remove_member(self.player)

        self.assertEqual(deleted_count, 1)
        self.assertFalse(team.memberships.filter(player=self.player).exists())

    def test_transfer_captaincy_requires_existing_member(self):
        team = Team.objects.create(name="Alpha", captain=self.captain)

        with self.assertRaises(ValidationError):
            team.transfer_captaincy(self.player)

    def test_transfer_captaincy_updates_captain_when_player_is_member(self):
        team = Team.objects.create(name="Alpha", captain=self.captain)
        team.add_member(self.player)

        team.transfer_captaincy(self.player)

        team.refresh_from_db()
        self.assertEqual(team.captain, self.player)

    def test_clean_requires_captain_to_be_member(self):
        team = Team.objects.create(name="Alpha", captain=self.captain)
        team.captain = self.player

        with self.assertRaises(ValidationError):
            team.full_clean()


class TeamMembershipModelTest(TestCase):
    def test_str_includes_player_and_team(self):
        captain = User.objects.create_user("captain", password="testpass123")
        team = Team.objects.create(name="Alpha", captain=captain)
        membership = TeamMembership.objects.get(team=team, player=captain)

        self.assertEqual(str(membership), f"{captain} - {team}")

    def test_clean_rejects_duplicate_membership(self):
        captain = User.objects.create_user("captain", password="testpass123")
        team = Team.objects.create(name="Alpha", captain=captain)
        duplicate = TeamMembership(team=team, player=captain)

        with self.assertRaises(ValidationError):
            duplicate.full_clean()


class InviteModelTest(TestCase):
    def setUp(self):
        self.captain = User.objects.create_user("captain", password="testpass123")
        self.player = User.objects.create_user("player", password="testpass123")
        self.other_player = User.objects.create_user("other", password="testpass123")
        self.team = Team.objects.create(name="Alpha", captain=self.captain)

    def test_str_shows_team_player_and_status(self):
        invite = Invite.objects.create(team=self.team, invited_player=self.player)

        self.assertEqual(str(invite), f"{self.team} -> {self.player} ({InviteStatus.PENDING})")

    def test_pending_invite_cannot_target_current_member(self):
        self.team.add_member(self.player)
        invite = Invite(team=self.team, invited_player=self.player)

        with self.assertRaises(ValidationError):
            invite.full_clean()

    def test_pending_invite_cannot_be_duplicated(self):
        Invite.objects.create(team=self.team, invited_player=self.player)
        duplicate = Invite(team=self.team, invited_player=self.player)

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_pending_invite_clears_response_date_on_save(self):
        invite = Invite.objects.create(
            team=self.team,
            invited_player=self.player,
            responded_at="2026-01-01T00:00:00Z",
        )

        self.assertIsNone(invite.responded_at)

    def test_accept_adds_invited_player_to_team(self):
        invite = Invite.objects.create(team=self.team, invited_player=self.player)

        invite.accept()

        invite.refresh_from_db()
        self.assertEqual(invite.status, InviteStatus.ACCEPTED)
        self.assertIsNotNone(invite.responded_at)
        self.assertTrue(self.team.memberships.filter(player=self.player).exists())

    def test_decline_sets_status_and_response_date(self):
        invite = Invite.objects.create(team=self.team, invited_player=self.player)

        invite.decline()

        invite.refresh_from_db()
        self.assertEqual(invite.status, InviteStatus.DECLINED)
        self.assertIsNotNone(invite.responded_at)

    def test_cancel_sets_status_and_response_date(self):
        invite = Invite.objects.create(team=self.team, invited_player=self.player)

        invite.cancel()

        invite.refresh_from_db()
        self.assertEqual(invite.status, InviteStatus.CANCELLED)
        self.assertIsNotNone(invite.responded_at)

    def test_only_pending_invites_can_be_answered(self):
        invite = Invite.objects.create(
            team=self.team,
            invited_player=self.player,
            status=InviteStatus.DECLINED,
        )

        with self.assertRaises(ValidationError):
            invite.accept()
