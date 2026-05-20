from django.db import models
from django.core.exceptions import ValidationError

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

    status = models.CharField(
        "Status do campeonato",
        max_length=11,
        choices=StatusChampionship.choices,
        default=StatusChampionship.DRAFT
    )

    max_teams = models.PositiveIntegerField("Número máximo de times")

    start_date = models.DateField(
        "Data de início",
        null=True,
        blank=True,
    )

    stage_format = models.CharField(
        "Formato do campeonato",
        max_length=19,
        choices=StageFormat.choices
    )

    group_count = models.PositiveIntegerField(
        "Número de grupos",
        null=True,
        blank=True,
        help_text="Para pontos corridos: deve ser 1. Para fase de grupos: defina a quantidade de grupos."
    )

    teams_per_group = models.PositiveIntegerField(
        "Número de times por grupo",
        null=True,
        blank=True,
        help_text="Em pontos corridos deve ser igual ao número máximo de times."
    )

    teams_advancing_per_group = models.PositiveIntegerField(
        "Número de times que avançam por grupo",
        null=True,
        blank=True,
        help_text="Em pontos corridos deve ser 0."
    )

    group_match_format = models.CharField(
        "Formato das partidas no grupo",
        max_length=3,
        choices=MatchFormat.choices,
        null=True,
        blank=True,
    )

    playoff_format = models.CharField(
        "Formato do playoff",
        max_length=18,
        choices=PlayoffFormat.choices,
        null=True,
        blank=True,
    )

    playoff_match_format = models.CharField(
        "Formato das partidas no playoff",
        max_length=3,
        choices=MatchFormat.choices,
        null=True,
        blank=True,
    )

    final_match_format = models.CharField(
        "Formato da partida na final",
        max_length=3,
        choices=MatchFormat.choices,
        null=True,
        blank=True,
    )

    third_place_match = models.BooleanField("Disputa de 3º lugar", default=False)

    seeding_method = models.CharField(
        "Método de ranqueamento",
        max_length=6,
        choices=SeedingMethodChampionship.choices,
        default=SeedingMethodChampionship.RANDOM
    )

    # Creio que precisa de um champion = chave estrangeira de teams

    created_at = models.DateTimeField("Data de criação", auto_now_add=True)

    #created_by = chave estrangeira de users


    def clean(self):
        super().clean()
        errors = {}

        # Validações gerais
        if self.max_teams and self.max_teams < 2:
            errors["max_teams"] = "O campeonato deve ter pelo menos 2 times."
        
        if self.status != StatusChampionship.DRAFT and not self.start_date:
            errors["start_date"] = "Data de início é obrigatória quando o campeonato não está em rascunho."

        # Fase de grupos exige configurações de grupos
        if self.stage_format == StageFormat.GROUP_THEN_PLAYOFFS:
            if not self.group_count:
                errors["group_count"] = ("Informe a quantidade de grupos.")
            if not self.teams_per_group:
                errors["teams_per_group"] = ("Informe a quantidade de times por grupo.")
            if not self.teams_advancing_per_group:
                errors["teams_advancing_per_group"] = ("Informe quantos times avançam por grupo.")
            if not self.group_match_format:
                errors["group_match_format"] = ("Informe o formato das partidas da fase de grupos.")
            if not self.playoff_format:
                errors["playoff_format"] = ("Informe o formato do playoff.")

             
            if (self.teams_advancing_per_group and self.teams_per_group and self.teams_advancing_per_group > self.teams_per_group):
                errors["teams_advancing_per_group"] = ("Não pode avançar mais times do que existem no grupo.")

            if (self.group_count and self.teams_per_group and (self.group_count * self.teams_per_group) > self.max_teams):
                errors["teams_per_group"] = ("A quantidade total de times dos grupos não pode ultrapassar o máximo de times.")
        
        
        elif self.stage_format in (StageFormat.SINGLE_ELIMINATION, StageFormat.DOUBLE_ELIMINATION):
            # Formatos eliminatórios devem ter campos de grupos nulos
            if self.group_count is not None:
                errors["group_count"] = f"O formato {self.get_stage_format_display()} não utiliza grupos."
            if self.teams_per_group is not None:
                errors["teams_per_group"] = "Campos de grupo não devem ser preenchidos para este formato."
            if self.teams_advancing_per_group is not None:
                errors["teams_advancing_per_group"] = "Campos de grupo não devem ser preenchidos para este formato."
            if self.group_match_format is not None:
                errors["group_match_format"] = "Campos de grupo não devem ser preenchidos para este formato."

            # Campos obrigatórios de playoff
            if not self.playoff_format:
                errors["playoff_format"] = "Informe o formato do playoff."
            if not self.playoff_match_format:
                errors["playoff_match_format"] = "Informe o formato das partidas do playoff."
            if not self.final_match_format:
                errors["final_match_format"] = "Informe o formato da partida final."

            # Inconsistência: formato do campeonato não pode divergir do formato do playoff
            if self.stage_format == StageFormat.SINGLE_ELIMINATION and self.playoff_format == PlayoffFormat.DOUBLE_ELIMINATION:
                errors["playoff_format"] = "Formato de eliminação simples não pode ter playoff em eliminação dupla."
            elif self.stage_format == StageFormat.DOUBLE_ELIMINATION and self.playoff_format == PlayoffFormat.SINGLE_ELIMINATION:
                errors["playoff_format"] = "Formato de eliminação dupla não pode ter playoff em eliminação simples."


        # Pontos corridos: um único grupo com todos os times
        elif self.stage_format == StageFormat.ROUND_ROBIN:
            if self.group_count != 1:
                errors["group_count"] = "Para pontos corridos, o número de grupos deve ser 1."

            if not self.teams_per_group:
                errors["teams_per_group"] = "Informe a quantidade de times por grupo (deve ser igual ao máximo de times)."
            elif self.teams_per_group != self.max_teams:
                errors["teams_per_group"] = f"Em pontos corridos, todos os times ficam no mesmo grupo. Portanto, times por grupo deve ser {self.max_teams}."

            if self.teams_advancing_per_group is None:
                errors["teams_advancing_per_group"] = "Informe quantos times avançam (para pontos corridos, deve ser 0)."
            elif self.teams_advancing_per_group != 0:
                errors["teams_advancing_per_group"] = "Pontos corridos não possuem playoff. Defina avanço como 0."
            

            if not self.group_match_format:
                errors["group_match_format"] = "Informe o formato das partidas."
            
            # Pontos corridos devem ter campos de playoffs nulos
            if self.playoff_format is not None:
                errors["playoff_format"] = "Pontos corridos não possuem fase eliminatória."
            if self.playoff_match_format is not None:
                errors["playoff_match_format"] = "Pontos corridos não possuem fase eliminatória."
            if self.final_match_format is not None:
                errors["final_match_format"] = "Pontos corridos não possuem fase eliminatória."
            if self.third_place_match:
                errors["third_place_match"] = "Pontos corridos não possuem disputa de 3º lugar."
        

        if errors:
            raise ValidationError(errors)
    

    class Meta:
        verbose_name = "Campeonato"
        verbose_name_plural = "Campeonatos"
        ordering = ["-created_at"]


    def __str__(self):
        return f"{self.name} ({self.game})"



class TiebreakerRule(models.Model):
    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name="tiebreaker_rules"
    )

    priority = models.PositiveIntegerField("Prioridade do critério de desempate")

    criterion = models.CharField(
        "Critério de desempate",
        max_length=12,
        choices=TiebreakerCriterion.choices
    )


    def clean(self):
        super().clean()
        errors = {}

        # Garantir que não exista outra regra com a mesma prioridade no mesmo campeonato
        if self.championship_id:
            qs = TiebreakerRule.objects.filter(championship=self.championship, priority=self.priority)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors["priority"] = f"Já existe uma regra de desempate com prioridade {self.priority} para este campeonato."

        # Evitar critérios duplicados no mesmo campeonato
        if self.championship_id:
            qs_criterion = TiebreakerRule.objects.filter(championship=self.championship, criterion=self.criterion)
            if self.pk:
                qs_criterion = qs_criterion.exclude(pk=self.pk)
            if qs_criterion.exists():
                errors["criterion"] = f"O critério '{self.get_criterion_display()}' já foi definido para este campeonato."


        # Campeonato talvez tenha que estar em rascunho ou com inscrições abertas para poder adicionar critérios
        
        if errors:
            raise ValidationError(errors)


    class Meta:
        verbose_name = "Regra de Desempate"
        verbose_name_plural = "Regras de Desempate"
        ordering = ["championship__name", "priority"]


    def __str__(self):
        return f"{self.priority} - {self.criterion}"



class Registration(models.Model):
    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name="registrations"
    )
    
    # team = chave estrangeira de teams

    status = models.CharField(
        "Status da inscrição",
        max_length=8,
        choices=StatusRegistration.choices,
        default=StatusRegistration.PENDING
    )

    registered_at = models.DateTimeField(
        "Data da inscrição",
        auto_now_add=True
    )


    def clean(self):
        super().clean()
        errors = {}

        # Verifica se o campeonato está com inscrições abertas
        if self.championship_id and self.championship.status != StatusChampionship.OPEN:
            errors["championship"] = "Inscrições permitidas apenas quando o campeonato está com status 'Inscrições abertas'."

        # Validação ao aprovar uma inscrição
        if self.status == StatusRegistration.APPROVED:
            approved_count = self.championship.registrations.filter(status=StatusRegistration.APPROVED).count()
            if self.pk:
                old = Registration.objects.get(pk=self.pk)
                if old.status == StatusRegistration.APPROVED:
                    approved_count -= 1
            if approved_count >= self.championship.max_teams:
                errors["status"] = f"Limite máximo de times ({self.championship.max_teams}) já atingido. Não é possível aprovar mais inscrições."


        # Quando o campo team existir:
        # if self.team_id:
        #     if Registration.objects.filter(championship=self.championship, team=self.team).exclude(pk=self.pk).exists():
        #         errors["team"] = "Este time já possui uma inscrição para este campeonato."

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = "Inscrição"
        verbose_name_plural = "Inscrições"
        ordering = ["-registered_at"]


    def __str__(self):
        return f"Inscrição #{self.id} - {self.status}"