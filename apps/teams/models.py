from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class InviteStatus(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    ACCEPTED = "ACCEPTED", "Aceito"
    DECLINED = "DECLINED", "Recusado"
    CANCELLED = "CANCELLED", "Cancelado"


class Team(models.Model):
    name = models.CharField("Nome da equipe", max_length = 100)
    logo = models.ImageField("Logo", upload_to = "team_logos", blank = True, null = True)
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete = models.CASCADE,
        related_name = "captained_teams",
        verbose_name = "Capitão"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through = "TeamMembership",
        related_name = "teams",
        verbose_name = "Membros"
    )
    created_at = models.DateTimeField("Data de criação", auto_now_add = True)

    def clean(self):
        super().clean()

        if self.pk and self.captain_id:
            captain_is_member = self.memberships.filter(player_id = self.captain_id).exists()

            if not captain_is_member:
                raise ValidationError({
                    "captain": "O capitão precisa ser membro da equipe."
                })

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        TeamMembership.objects.get_or_create(team = self, player = self.captain)

    def add_member(self, player):
        return TeamMembership.objects.get_or_create(team = self, player = player)

    def remove_member(self, player):
        if player == self.captain:
            raise ValidationError("O capitão não pode ser removido da equipe.")

        return self.memberships.filter(player = player).delete()

    def transfer_captaincy(self, new_captain):
        if not self.memberships.filter(player = new_captain).exists():
            raise ValidationError("A capitania só pode ser transferida para um membro da equipe.")

        self.captain = new_captain
        self.full_clean()
        self.save(update_fields = ["captain"])

    class Meta:
        verbose_name = "Equipe"
        verbose_name_plural = "Equipes"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete = models.CASCADE,
        related_name = "memberships",
        verbose_name = "Equipe"
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete = models.CASCADE,
        related_name = "team_memberships",
        verbose_name = "Jogador"
    )
    joined_at = models.DateTimeField("Data de entrada", auto_now_add = True)

    def clean(self):
        super().clean()
        errors = {}

        if self.team_id and self.player_id:
            membership_exists = TeamMembership.objects.filter(
                team = self.team,
                player = self.player
            )

            if self.pk:
                membership_exists = membership_exists.exclude(pk = self.pk)

            if membership_exists.exists():
                errors["player"] = "Este jogador já faz parte da equipe."

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = "Membro da Equipe"
        verbose_name_plural = "Membros das Equipes"
        ordering = ["team__name", "player__username"]
        constraints = [
            models.UniqueConstraint(fields = ["team", "player"], name = "unique_team_player")
        ]

    def __str__(self):
        return f"{self.player} - {self.team}"


class Invite(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete = models.CASCADE,
        related_name = "invites",
        verbose_name = "Equipe"
    )
    invited_player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete = models.CASCADE,
        related_name = "team_invites",
        verbose_name = "Jogador convidado"
    )
    status = models.CharField(
        "Status do convite",
        max_length = 9,
        choices = InviteStatus.choices,
        default = InviteStatus.PENDING
    )
    created_at = models.DateTimeField("Data do convite", auto_now_add = True)
    responded_at = models.DateTimeField("Data da resposta", blank = True, null = True)

    def clean(self):
        super().clean()
        errors = {}

        if self.team_id and self.invited_player_id and self.status == InviteStatus.PENDING:
            if self.team.captain_id == self.invited_player_id:
                errors["invited_player"] = "O capitão já faz parte da equipe."

            if self.team.memberships.filter(player = self.invited_player).exists():
                errors["invited_player"] = "Este jogador já faz parte da equipe."

            pending_invite_exists = Invite.objects.filter(
                team = self.team,
                invited_player = self.invited_player,
                status = InviteStatus.PENDING
            )

            if self.pk:
                pending_invite_exists = pending_invite_exists.exclude(pk = self.pk)

            if pending_invite_exists.exists():
                errors["invited_player"] = "Este jogador já possui um convite pendente para esta equipe."

        if self.status == InviteStatus.PENDING and self.responded_at:
            errors["responded_at"] = "Convites pendentes não devem ter data de resposta."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.status == InviteStatus.PENDING:
            self.responded_at = None
        elif not self.responded_at:
            self.responded_at = timezone.now()

        super().save(*args, **kwargs)

        if self.status == InviteStatus.ACCEPTED:
            TeamMembership.objects.get_or_create(team = self.team, player = self.invited_player)

    def _validate_pending_status(self):
        if self.status != InviteStatus.PENDING:
            raise ValidationError("Apenas convites pendentes podem ser respondidos.")

    def accept(self):
        self._validate_pending_status()
        self.status = InviteStatus.ACCEPTED
        self.responded_at = timezone.now()
        self.full_clean()
        self.save(update_fields = ["status", "responded_at"])

    def decline(self):
        self._validate_pending_status()
        self.status = InviteStatus.DECLINED
        self.responded_at = timezone.now()
        self.full_clean()
        self.save(update_fields = ["status", "responded_at"])

    def cancel(self):
        self._validate_pending_status()
        self.status = InviteStatus.CANCELLED
        self.responded_at = timezone.now()
        self.full_clean()
        self.save(update_fields = ["status", "responded_at"])

    class Meta:
        verbose_name = "Convite"
        verbose_name_plural = "Convites"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.team} -> {self.invited_player} ({self.status})"
