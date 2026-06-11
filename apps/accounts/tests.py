from django.test import TestCase
from django.urls import reverse

from .models import User


class UserModelTest(TestCase):
    def test_user_str_shows_username_and_ranking_score(self):
        user = User.objects.create_user(
            username="player_one",
            password="testpass123",
            ranking_score=42,
        )

        self.assertEqual(str(user), "player_one - 42")

    def test_user_default_ranking_score_is_zero(self):
        user = User.objects.create_user(username="rookie", password="testpass123")

        self.assertEqual(user.ranking_score, 0)
        self.assertEqual(user.bio, "")


class EditProfileViewTest(TestCase):
    def test_edit_profile_saves_without_changing_username(self):
        user = User.objects.create_user(
            username="player_one",
            email="player@example.com",
            password="Strongpass123",
            first_name="Player",
        )
        self.client.login(username="player_one", password="Strongpass123")

        response = self.client.post(reverse("accounts:edit-profile"), {
            "first_name": "Player Updated",
            "last_name": "",
            "username": "player_one",
            "email": "player@example.com",
            "bio": "Nova bio",
            "current_password": "",
            "password": "",
            "confirm_password": "",
        })

        user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(user.username, "player_one")
        self.assertEqual(user.first_name, "Player Updated")
        self.assertEqual(user.bio, "Nova bio")
