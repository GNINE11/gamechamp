from django.db import models
#from apps.championships.models import (
#   Championship,
#   Team)

# Create your models here.
class GameFormat(models.TextChoices):
    BO1 = "BO1", "Best of 1"
    BO3 = "BO3", "Best of 3"
    BO5 = "BO5", "Best of 5"


class Phase(models.TextChoices):
    GROUP = "GROUP", "Grupos"
    PLAYOFF = "PLAYOFF", "Playoff"
    GRAND_FINAL = "GRAND_FINAL", "Grande Final"


class GameStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Agendado"
    ONGOING = "ONGOING", "Em Andamento"
    FINISHED = "FINISHED", "Encerrado"


class Group(models.Model):
    championship = models.ForeignKey("Championship", on_delete = models.CASCADE, verbose_name = "Campeonato") #completar aqui quando importar championship
    name = models.CharField("Nome", max_length = 50)

    class Meta:
        verbose_name = "Grupo"

    def __str__(self):
        return f"Grupo: {self.name}\nCampeonato: {self.championship}"


class Match(models.Model):
    championship = models.ForeignKey("Championship", on_delete = models.CASCADE, verbose_name = "Campeonato") #completar aqui quando importar championship
    match_format = models.CharField("Formato", max_length = 5, choices = GameFormat.choices)
    phase = models.CharField("Fase", max_length = 12, choices = Phase.choices)
    group = models.ForeignKey(Group, on_delete = models.SET_NULL, verbose_name = "Grupo", blank = True, null = True)
    playoff_round = models.IntegerField("Rodada do Playoff", blank = True, null = True)
    round_number = models.IntegerField("Rodada")
    team_a = models.ForeignKey("Time", on_delete = models.SET_NULL, blank = True, null = True, verbose_name = "Time A")#copletar quando importar TIME
    team_b = models.ForeignKey("Time", on_delete = models.SET_NULL, blank = True, null = True, verbose_name = "Time B")#copletar quando importar TIME
    winner = models.ForeignKey("Time", on_delete = models.SET_NULL, blank = True, null = True, verbose_name = "Vencedor")#copletar quando importar TIME
    status = models.CharField("Status", max_length = 12, choices = GameStatus.choices)
    scheduled_at = models.DateField("Agendado Para", blank = True, null = True)

    class Meta:
        verbose_name = "Partida"
        ordering = ["scheduled_at"]
    
    def __str__(self):
        return f"{self.championship} - {self.group} - {self.match_format}\n{self.team_a} vs {self.team_b}\nWinner: {self.winner}"



class GroupStanding(models.Model):#tabela intermediaria entre grupo e time
    group = models.ForeignKey(Group, on_delete = models.CASCADE, verbose_name = "Grupo")
    team = models.ForeignKey("Time", on_delete = models.CASCADE, verbose_name = "Time")#copletar quando importar TIME
    wins = models.IntegerField("Vitórias", default = 0)
    losses = models.IntegerField("Derrotas", default = 0)
    draws = models.IntegerField("Empates", blank = True, null = True)
    points = models.IntegerField("Pontuação", default = 0)
    rounds_won = models.IntegerField("Rounds Vencidos", default = 0)
    rounds_lost = models.IntegerField("Rounds Perdidos", default = 0)
    round_diff = models.IntegerField("Diferença de Rounds", default=0)
    position = models.IntegerField("Ponsição", blank = True, null = True)
    
    
    class Meta:
        verbose_name = "Classificação"
        constraints = [
            models.UniqueConstraint(fields = ["group", "team"], name = "unique_group_team")
        ]
    
    def __str__(self):
        return f"{self.team} — Grupo {self.group} ({self.points} pts)"


class GameResult(models.Model):#tabela intermediaria entre match e time
    match_id = models.ForeignKey(Match, on_delete = models.CASCADE, verbose_name = "Partida") 
    winner = models.ForeignKey("Time", on_delete = models.RESTRICT, verbose_name = "Vencedor")#copletar quando importar TIME
    game_number = models.IntegerField("Número da Partida")
    score_a = models.IntegerField("Pontuação Time A", default=0)
    score_b = models.IntegerField("Pontuação Time B", default=0)
    map_name = models.CharField("Mapa", max_length = 80, blank = True)

    class Meta:
        verbose_name = "Resulado da Partida"
        constraints = [
            models.UniqueConstraint(fields=["match_id", "game_number"], name="unique_match_number")
        ]

    def __str__(self):
        return f"{self.match} — Game {self.game_number} | {self.score_a}x{self.score_b}"