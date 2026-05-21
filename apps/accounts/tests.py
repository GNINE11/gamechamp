from django.test import TestCase

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
