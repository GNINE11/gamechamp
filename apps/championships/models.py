from django.db import models
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.teams.models import Team

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



# ENUMS Championship_Staff
class RoleStaff(models.TextChoices):
    OWNER = "OWNER", "Dono"
    MODERATOR = "MODERATOR", "Moderador"



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

    champion = models.ForeignKey(
        Team,
        on_delete=models.RESTRICT,
        related_name="championships_won",
        verbose_name="Campeão",
        null=True,
        blank=True,
    )

    staff = models.ManyToManyField(
        User,
        through="ChampionshipStaff",
        related_name="staffed_championships"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        related_name="created_championships",
        verbose_name="Criado por"
    )

    created_at = models.DateTimeField("Data de criação", auto_now_add=True)

    

    def clean(self):
        super().clean()
        errors = {}

        # Validações gerais
        if self.max_teams and self.max_teams < 2:
            errors["max_teams"] = ("O campeonato deve ter pelo menos 2 times.")

        if (self.status != StatusChampionship.DRAFT and not self.start_date):
            errors["start_date"] = ("Data de início é obrigatória quando o campeonato não está em rascunho.")

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = "Campeonato"
        verbose_name_plural = "Campeonatos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.game})"


class ChampionshipStaff(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="championship_staff_roles",
        verbose_name="Usuário"
    )

    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name="staff_members",
        verbose_name="Campeonato"
    )

    role = models.CharField(
        "Função",
        max_length=9,
        choices=RoleStaff.choices,
        default=RoleStaff.MODERATOR
    )

    added_at = models.DateTimeField(
        "Adicionado às",
        auto_now_add=True
    )

    def clean(self):
        super().clean()
        errors = {}

        if self.role == RoleStaff.OWNER:
            qs_owner = ChampionshipStaff.objects.filter(
                championship=self.championship,
                role=RoleStaff.OWNER
            )

            if self.pk:
                qs_owner = qs_owner.exclude(pk=self.pk)

            if qs_owner.exists():
                errors["role"] = (
                    "Este campeonato já possui um owner."
                )

        if errors:
            raise ValidationError(errors)


    class Meta:
        verbose_name = "Membro da Staff"
        verbose_name_plural = "Membros da Staff"
        ordering = ["championship", "role"]


    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.get_role_display()} - "
            f"{self.championship.name}"
        )


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
        return (f"{self.priority} - "f"{self.get_criterion_display()}")


class Registration(models.Model):
    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name="registrations"
    )

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="Equipe"
    )

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


        if self.championship_id and self.team_id:
            qs = Registration.objects.filter(championship=self.championship, team=self.team)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors["team"] = "Este time já possui uma inscrição para este campeonato."

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = "Inscrição"
        verbose_name_plural = "Inscrições"
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(fields=["championship", "team"], name="unique_championship_team")
        ]


    def __str__(self):
        return f"{self.team} - {self.championship} ({self.status})"
