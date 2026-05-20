from django.db import models
from apps.championships.models import Championship
#Team
from django.core.exceptions import ValidationError


# Create your models here.
class Team(models.Model):#classe temporaria apenas para teste
    name = models.CharField("Nome", max_length = 100)

    def __str__(self):
        return self.name

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
    championship = models.ForeignKey(Championship, on_delete = models.CASCADE, verbose_name = "Campeonato") #completar aqui quando importar championship
    name = models.CharField("Nome", max_length = 50)
    teams = models.ManyToManyField(
        Team,
        through="GroupStanding",
        verbose_name="Times",
        related_name="groups"
    )

    class Meta:
        verbose_name = "Grupo"

    def __str__(self):
        return f"Grupo: {self.name}\nCampeonato: {self.championship}"


class Match(models.Model):
    championship = models.ForeignKey(Championship, on_delete = models.CASCADE, verbose_name = "Campeonato") #completar aqui quando importar championship
    match_format = models.CharField("Formato", max_length = 5, choices = GameFormat.choices)
    phase = models.CharField("Fase", max_length = 12, choices = Phase.choices)
    group = models.ForeignKey(Group, on_delete = models.SET_NULL, verbose_name = "Grupo", blank = True, null = True)
    playoff_round = models.IntegerField("Rodada do Playoff", blank = True, null = True)
    round_number = models.IntegerField("Rodada")
    team_a = models.ForeignKey(Team, on_delete = models.SET_NULL, blank = True, null = True, verbose_name = "Time A", related_name="matches_as_team_a")#copletar quando importar TIME
    team_b = models.ForeignKey(Team, on_delete = models.SET_NULL, blank = True, null = True, verbose_name = "Time B", related_name="matches_as_team_b")#copletar quando importar TIME
    winner = models.ForeignKey(Team, on_delete = models.SET_NULL, blank = True, null = True, verbose_name = "Vencedor", related_name="matches_won")#copletar quando importar TIME
    status = models.CharField("Status", max_length = 12, choices = GameStatus.choices)
    teams = models.ManyToManyField(
        Team,
        through="GameResult",
        verbose_name="Times",
        related_name="game_results"
    )
    scheduled_at = models.DateField("Agendado Para", blank = True, null = True)
    

    def clean(self):
        # 1. Time A e Time B não podem ser o mesmo
        if(self.team_a and self.team_b and self.team_a == self.team_b):
            raise ValidationError("Time A e Time B não podem ser o mesmo time.")

        # 2. Partida de grupo exige grupo definido
        if(self.phase == Phase.GROUP and self.group is None):
            raise ValidationError("Partidas de fase de grupos precisam ter um grupo definido.")

        # 3. Partida de playoff não pode ter grupo
        if(self.phase in [Phase.PLAYOFF, Phase.GRAND_FINAL] and self.group is not None):
            raise ValidationError("Partidas de playoff e grand final não devem ter grupo.")
        
    class Meta:
        verbose_name = "Partida"
        ordering = ["scheduled_at"]
    
    def __str__(self):
        return f"{self.championship} - {self.group} - {self.match_format}\n{self.team_a} vs {self.team_b}\nWinner: {self.winner}"



class GroupStanding(models.Model):#tabela intermediaria entre grupo e time
    group = models.ForeignKey(Group, on_delete = models.CASCADE, verbose_name = "Grupo")
    team = models.ForeignKey(Team, on_delete = models.CASCADE, verbose_name = "Time")#copletar quando importar TIME
    wins = models.IntegerField("Vitórias", default = 0)
    losses = models.IntegerField("Derrotas", default = 0)
    draws = models.IntegerField("Empates", blank = True, null = True)
    points = models.IntegerField("Pontuação", default = 0)
    rounds_won = models.IntegerField("Rounds Vencidos", default = 0)
    rounds_lost = models.IntegerField("Rounds Perdidos", default = 0)
    round_diff = models.IntegerField("Diferença de Rounds", default=0)
    position = models.IntegerField("Posição", blank = True, null = True)
    
    def clean(self):
        # round_diff deve ser consistente com rounds_won e rounds_lost
        if(self.round_diff != self.rounds_won - self.rounds_lost):
            raise ValidationError("Diferença de rounds inconsistente com rounds vencidos e perdidos.")
    
    class Meta:
        verbose_name = "Classificação"
        verbose_name_plural = "Classificações"
        constraints = [
            models.UniqueConstraint(fields = ["group", "team"], name = "unique_group_team")
        ]
    
    def __str__(self):
        return f"{self.team} — Grupo {self.group} ({self.points} pts)"


class GameResult(models.Model):#tabela intermediaria entre match e time
    match_id = models.ForeignKey(Match, on_delete = models.CASCADE, verbose_name = "Partida") 
    winner = models.ForeignKey(Team, on_delete = models.RESTRICT, verbose_name = "Vencedor")#copletar quando importar TIME
    game_number = models.IntegerField("Número da Partida")
    score_a = models.IntegerField("Pontuação Time A", default=0)
    score_b = models.IntegerField("Pontuação Time B", default=0)
    map_name = models.CharField("Mapa", max_length = 80, blank = True)

    def clean(self):
        # Vencedor deve ser um dos times da partida
        match = self.match_id
        if(self.winner not in [match.team_a, match.team_b]):
            raise ValidationError("O vencedor deve ser um dos times da partida.")

    class Meta:
        verbose_name = "Resultado da Partida"
        verbose_name_plural = "Resultado das Partidas"

        constraints = [
            models.UniqueConstraint(fields=["match_id", "game_number"], name="unique_match_number")
        ]

    def __str__(self):
        return f"{self.match} — Game {self.game_number} | {self.score_a}x{self.score_b}"