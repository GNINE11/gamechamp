from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class User(AbstractUser):
    avatar = models.ImageField("Avatar", upload_to = "accounts/userAvatarMock", blank = True, null = True)
    bio = models.TextField("Bio", blank = True)
    created_at = models.DateTimeField("Data de Criação", auto_now_add = True)
    ranking_score = models.IntegerField("Pontuação", default = 0)


    def __str__(self):
        return f"{self.username} - {self.ranking_score}"
