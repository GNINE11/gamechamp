import re

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import Invite, InviteStatus, Team


User = get_user_model()

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
TAG_RE = re.compile(r"^[A-Za-z0-9]{3,4}$")


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = (
            "name",
            "tag",
            "logo",
            "banner",
            "description",
            "public_recruitment",
            "region",
            "primary_game",
            "social_url",
            "primary_color",
            "accent_color",
        )

    def clean_tag(self):
        tag = (self.cleaned_data.get("tag") or "").strip().upper()
        if tag and not TAG_RE.match(tag):
            raise ValidationError("A tag deve ter 3 ou 4 caracteres alfanuméricos.")
        return tag

    def clean_primary_color(self):
        return self._clean_hex_color("primary_color", "#d0bcff")

    def clean_accent_color(self):
        return self._clean_hex_color("accent_color", "#4cd7f6")

    def _clean_hex_color(self, field_name, fallback):
        value = (self.cleaned_data.get(field_name) or fallback).strip()
        if not HEX_COLOR_RE.match(value):
            raise ValidationError("Informe uma cor no formato hexadecimal, como #d0bcff.")
        return value.lower()


class TeamInviteForm(forms.Form):
    player = forms.CharField(max_length=150, label="Jogador")
    proposed_role = forms.CharField(max_length=80, required=False, label="Função proposta")
    message = forms.CharField(widget=forms.Textarea, required=False, label="Mensagem")

    def __init__(self, team, *args, **kwargs):
        self.team = team
        self.invited_player = None
        super().__init__(*args, **kwargs)

    def clean_player(self):
        identifier = (self.cleaned_data.get("player") or "").strip()
        try:
            player = User.objects.get(Q(username__iexact=identifier) | Q(email__iexact=identifier))
        except User.DoesNotExist as exc:
            raise ValidationError("Não encontramos um jogador com este username ou e-mail.") from exc
        except User.MultipleObjectsReturned as exc:
            raise ValidationError("Mais de um jogador corresponde a este identificador.") from exc

        invite = Invite(
            team=self.team,
            invited_player=player,
            message=(self.data.get("message") or "").strip(),
            proposed_role=(self.data.get("proposed_role") or "").strip(),
        )
        try:
            invite.full_clean()
        except ValidationError as exc:
            errors = exc.message_dict.get("invited_player") if hasattr(exc, "message_dict") else exc.messages
            raise ValidationError(errors) from exc

        self.invited_player = player
        return identifier

    def save(self):
        invite = Invite(
            team=self.team,
            invited_player=self.invited_player,
            message=self.cleaned_data.get("message", "").strip(),
            proposed_role=self.cleaned_data.get("proposed_role", "").strip(),
            status=InviteStatus.PENDING,
        )
        invite.full_clean()
        invite.save()
        return invite


class MembershipRoleForm(forms.Form):
    role = forms.CharField(max_length=80, required=False, label="Função")
