import shutil
import tempfile
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User

from .forms import TeamForm, TeamInviteForm
from .models import Invite, InviteStatus, Team, TeamMembership


TEST_MEDIA_ROOT = tempfile.mkdtemp()
ONE_PIXEL_GIF = (
    b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def test_image(name):
    return SimpleUploadedFile(name, ONE_PIXEL_GIF, content_type="image/gif")


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


class TeamFormTest(TestCase):
    def test_team_form_validates_tag_and_hex_colors(self):
        form = TeamForm(data={
            "name": "Alpha",
            "tag": "AB",
            "primary_color": "purple",
            "accent_color": "#4cd7f6",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("tag", form.errors)
        self.assertIn("primary_color", form.errors)


class TeamInviteFormTest(TestCase):
    def setUp(self):
        self.captain = User.objects.create_user("captain_form", email="captain@example.com", password="testpass123")
        self.player = User.objects.create_user("player_form", email="player@example.com", password="testpass123")
        self.member = User.objects.create_user("member_form", email="member@example.com", password="testpass123")
        self.team = Team.objects.create(name="Form Alpha", captain=self.captain)
        self.team.add_member(self.member)

    def test_invite_form_rejects_unknown_player(self):
        form = TeamInviteForm(self.team, data={"player": "missing"})

        self.assertFalse(form.is_valid())
        self.assertIn("player", form.errors)

    def test_invite_form_rejects_existing_member(self):
        form = TeamInviteForm(self.team, data={"player": self.member.username})

        self.assertFalse(form.is_valid())
        self.assertIn("player", form.errors)

    def test_invite_form_rejects_duplicate_pending_invite(self):
        Invite.objects.create(team=self.team, invited_player=self.player)
        form = TeamInviteForm(self.team, data={"player": self.player.email})

        self.assertFalse(form.is_valid())
        self.assertIn("player", form.errors)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class TeamViewsTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.captain = User.objects.create_user("captain_view", email="captain_view@example.com", password="testpass123")
        self.member = User.objects.create_user("member_view", email="member_view@example.com", password="testpass123")
        self.player = User.objects.create_user("player_view", email="player_view@example.com", password="testpass123")
        self.other = User.objects.create_user("other_view", email="other_view@example.com", password="testpass123")
        self.team = Team.objects.create(name="View Alpha", captain=self.captain)
        self.membership, _ = self.team.add_member(self.member, role="Support")

    def test_team_pages_render_for_captain(self):
        self.client.login(username="captain_view", password="testpass123")

        urls = [
            reverse("teams:teams-create"),
            reverse("teams:teams-detail", kwargs={"pk": self.team.pk}),
            reverse("teams:teams-edit", kwargs={"pk": self.team.pk}),
            reverse("teams:teams-members", kwargs={"pk": self.team.pk}),
            reverse("teams:teams-invitations"),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_create_team_persists_extra_fields_and_captain_membership(self):
        self.client.login(username="other_view", password="testpass123")

        response = self.client.post(reverse("teams:teams-create"), {
            "name": "Neon Squad",
            "tag": "nsg",
            "description": "Time competitivo.",
            "public_recruitment": "on",
            "region": "Brasil",
            "primary_game": "Valorant",
            "social_url": "https://example.com/neon",
            "primary_color": "#abcdef",
            "accent_color": "#123456",
        })

        team = Team.objects.get(name="Neon Squad")
        self.assertRedirects(response, reverse("teams:teams-detail", kwargs={"pk": team.pk}))
        self.assertEqual(team.tag, "NSG")
        self.assertEqual(team.description, "Time competitivo.")
        self.assertEqual(team.primary_color, "#abcdef")
        self.assertTrue(team.public_recruitment)
        self.assertEqual(team.captain, self.other)
        self.assertTrue(team.memberships.filter(player=self.other).exists())

    def test_create_team_uploads_logo_and_banner(self):
        self.client.login(username="other_view", password="testpass123")

        response = self.client.post(reverse("teams:teams-create"), {
            "name": "Media Squad",
            "tag": "MED",
            "primary_color": "#abcdef",
            "accent_color": "#123456",
            "logo": test_image("logo.gif"),
            "banner": test_image("banner.gif"),
        })

        team = Team.objects.get(name="Media Squad")
        self.assertRedirects(response, reverse("teams:teams-detail", kwargs={"pk": team.pk}))
        self.assertTrue(team.logo.name.startswith("team_logos/"))
        self.assertTrue(team.banner.name.startswith("team_banners/"))
        self.assertTrue(Path(team.logo.path).exists())
        self.assertTrue(Path(team.banner.path).exists())

    def test_non_captain_cannot_edit_remove_promote_or_cancel_invites(self):
        invite = Invite.objects.create(team=self.team, invited_player=self.player)
        self.client.login(username="member_view", password="testpass123")

        edit_response = self.client.post(reverse("teams:teams-edit", kwargs={"pk": self.team.pk}), {
            "name": "Changed",
            "tag": "CHG",
            "primary_color": "#d0bcff",
            "accent_color": "#4cd7f6",
        })
        self.team.refresh_from_db()
        self.assertRedirects(edit_response, reverse("teams:teams-detail", kwargs={"pk": self.team.pk}))
        self.assertEqual(self.team.name, "View Alpha")

        remove_response = self.client.post(reverse("teams:teams-member-remove", kwargs={
            "pk": self.team.pk,
            "membership_pk": self.membership.pk,
        }))
        self.assertRedirects(remove_response, reverse("teams:teams-detail", kwargs={"pk": self.team.pk}))
        self.assertTrue(TeamMembership.objects.filter(pk=self.membership.pk).exists())

        promote_response = self.client.post(reverse("teams:teams-member-promote", kwargs={
            "pk": self.team.pk,
            "membership_pk": self.membership.pk,
        }))
        self.assertRedirects(promote_response, reverse("teams:teams-detail", kwargs={"pk": self.team.pk}))
        self.team.refresh_from_db()
        self.assertEqual(self.team.captain, self.captain)

        cancel_response = self.client.post(reverse("teams:teams-invite-cancel", kwargs={"pk": invite.pk}))
        invite.refresh_from_db()
        self.assertEqual(cancel_response.status_code, 404)
        self.assertEqual(invite.status, InviteStatus.PENDING)

    def test_invite_accept_creates_membership_with_proposed_role(self):
        self.client.login(username="captain_view", password="testpass123")
        response = self.client.post(reverse("teams:teams-invite-send", kwargs={"pk": self.team.pk}), {
            "player": self.player.username,
            "proposed_role": "Entry Fragger",
            "message": "Venha jogar com a gente.",
        })

        self.assertRedirects(response, reverse("teams:teams-members", kwargs={"pk": self.team.pk}))
        invite = Invite.objects.get(team=self.team, invited_player=self.player)
        self.assertEqual(invite.message, "Venha jogar com a gente.")
        self.assertEqual(invite.proposed_role, "Entry Fragger")

        self.client.logout()
        self.client.login(username="player_view", password="testpass123")
        accept_response = self.client.post(reverse("teams:teams-invite-accept", kwargs={"pk": invite.pk}))

        self.assertRedirects(accept_response, reverse("teams:teams-invitations"))
        invite.refresh_from_db()
        membership = TeamMembership.objects.get(team=self.team, player=self.player)
        self.assertEqual(invite.status, InviteStatus.ACCEPTED)
        self.assertEqual(membership.role, "Entry Fragger")

    def test_decline_and_cancel_invites_update_status(self):
        decline_invite = Invite.objects.create(team=self.team, invited_player=self.player)
        cancel_invite = Invite.objects.create(team=self.team, invited_player=self.other)

        self.client.login(username="player_view", password="testpass123")
        decline_response = self.client.post(reverse("teams:teams-invite-decline", kwargs={"pk": decline_invite.pk}))
        self.assertRedirects(decline_response, reverse("teams:teams-invitations"))
        decline_invite.refresh_from_db()
        self.assertEqual(decline_invite.status, InviteStatus.DECLINED)

        self.client.logout()
        self.client.login(username="captain_view", password="testpass123")
        cancel_response = self.client.post(reverse("teams:teams-invite-cancel", kwargs={"pk": cancel_invite.pk}))
        self.assertRedirects(cancel_response, reverse("teams:teams-invitations"))
        cancel_invite.refresh_from_db()
        self.assertEqual(cancel_invite.status, InviteStatus.CANCELLED)
