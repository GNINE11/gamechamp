from django.db import models

# TABELAS: Championship, TiebreakerRule, Registration

# ENUMS Championship
class StatusChampionship(models.TextChoices):
    DRAFT = "DRAFT", "Rascunho"
    OPEN = "OPEN", "Inscrições abertas"
    IN_PROGRESS = "IN_PROGRESS", "Em andamento"
    FINISHED = "FINISHED", "Finalizado"


class StageFormat(models.TextChoices):
    SINGLE_ELIMINATION = "SINGLE_ELIMINATION", "Eliminação simples"
    DOUBLE_ELIMINATION = "DOUBLE_ELIMINATION", "Eliminação dupla"
    ROUND_ROBIN = "ROUND_ROBIN", "Pontos corridos"
    GROUP_THEN_PLAYOFFS = "GROUP_THEN_PLAYOFFS", "Fase de grupos + playoffs"


class PlayoffFormat(models.TextChoices):
    SINGLE_ELIMINATION = "SINGLE_ELIMINATION", "Eliminação simples"
    DOUBLE_ELIMINATION = "DOUBLE_ELIMINATION", "Eliminação dupla"


class MatchFormat(models.TextChoices):
    BO1 = "BO1", "Melhor de 1"
    BO3 = "BO3", "Melhor de 3"
    BO5 = "BO5", "Melhor de 5"


class SeedingMethodChampionship(models.TextChoices):
    RANDOM = "RANDOM", "Aleatório"
    MANUAL = "MANUAL", "Manual"



# ENUMS Tiebreaker_rules
class TiebreakerCriterion(models.TextChoices):
    POINTS = "POINTS", "Pontos"
    WINS = "WINS", "Vitórias"
    HEAD_TO_HEAD = "HEAD_TO_HEAD", "Confronto direto"
    ROUND_DIFF = "ROUND_DIFF", "Saldo de rounds"
    ROUNDS_WON = "ROUNDS_WON", "Rounds vencidos"
    WIN_RATE = "WIN_RATE", "Taxa de vitória"



# ENUMS Registration
class StatusRegistration(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    APPROVED = "APPROVED", "Aprovada"
    REJECTED = "REJECTED", "Rejeitada"



# TABELAS
class Championship(models.Model):
    name = models.CharField("Nome do campeonato", max_length=100)
    game = models.CharField("Nome do jogo", max_length=100)
    status = models.CharField("Status do campeonato", max_length=11, choices=StatusChampionship.choices, default=StatusChampionship.DRAFT)
    max_teams = models.PositiveIntegerField("Número máximo de times")
    start_date = models.DateField("Data de início", null=True, blank=True)
    stage_format = models.CharField("Formato do campeonato", max_length=19, choices=StageFormat.choices)
    group_count = models.PositiveIntegerField("Número de grupos", null=True, blank=True)
    teams_per_group = models.PositiveIntegerField("Número de times por grupo", null=True, blank=True)
    teams_advancing_per_group = models.PositiveIntegerField("Número de times que avançam por grupo", null=True, blank=True)
    group_match_format = models.CharField("Formato das partidas no grupo", max_length=3, choices=MatchFormat.choices, null=True, blank=True)
    playoff_format = models.CharField("Formato do playoff", max_length=18, choices=PlayoffFormat.choices, null=True, blank=True)
    playoff_match_format = models.CharField("Formato das partidas no playoff", max_length=3, choices=MatchFormat.choices, null=True, blank=True)
    final_match_format = models.CharField("Formato da partida na final", max_length=3, choices=MatchFormat.choices, null=True, blank=True)
    third_place_match = models.BooleanField("Disputa de 3º lugar", default=False)
    seeding_method = models.CharField("Método de ranqueamento", max_length=6, choices=SeedingMethodChampionship.choices, default=SeedingMethodChampionship.RANDOM)
    created_at = models.DateTimeField("Data de criação", auto_now_add=True)
    #created_by_id = chave estrangeira de users

    class Meta:
        verbose_name = "Campeonato"
        verbose_name_plural = "Campeonatos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.game})"



class TiebreakerRule(models.Model):
    championship= models.ForeignKey(Championship, on_delete=models.CASCADE, related_name="tiebreaker_rules")
    priority = models.PositiveIntegerField("Prioridade do critério de desempate")
    criterion = models.CharField("Critério de desempate", max_length=12, choices=TiebreakerCriterion.choices)

    class Meta:
        verbose_name = "Regra de Desempate"
        verbose_name_plural = "Regras de Desempate"
        ordering = ["priority"]

    def __str__(self):
        return f"{self.priority} - {self.criterion}"



class Registration(models.Model):
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE, related_name="registrations")
    #team_id = chave estrangeira de teams
    status = models.CharField("Status da inscrição", max_length=8, choices=StatusRegistration.choices, default=StatusRegistration.PENDING)
    registered_at = models.DateTimeField("Data da inscrição", auto_now_add=True)

    class Meta:
        verbose_name = "Inscrição"
        verbose_name_plural = "Inscrições"
        ordering = ["-registered_at"]

    def __str__(self):
        return f"Inscrição #{self.id} - {self.status}"