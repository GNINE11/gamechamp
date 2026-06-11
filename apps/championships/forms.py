from django import forms
from django.core.exceptions import ValidationError

from apps.matches.models import Match

from .models import (
    Championship,
    MatchFormat,
    PlayoffFormat,
    SeedingMethodChampionship,
    StageFormat,
    StatusChampionship,
)


STRUCTURE_FIELDS = {
    "max_teams",
    "stage_format",
    "group_count",
    "teams_per_group",
    "teams_advancing_per_group",
    "group_match_format",
    "playoff_format",
    "playoff_match_format",
    "final_match_format",
    "third_place_match",
}


def _is_power_of_two(value):
    return value and value > 1 and value & (value - 1) == 0


class ChampionshipForm(forms.ModelForm):
    class Meta:
        model = Championship
        fields = (
            "name",
            "game",
            "status",
            "max_teams",
            "start_date",
            "stage_format",
            "group_count",
            "teams_per_group",
            "teams_advancing_per_group",
            "group_match_format",
            "playoff_format",
            "playoff_match_format",
            "final_match_format",
            "third_place_match",
            "seeding_method",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, is_create=False, **kwargs):
        self.is_create = is_create
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            css_class = "champ-form-control"
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "champ-form-check"
            field.widget.attrs["class"] = css_class

        if is_create:
            self.fields.pop("status", None)
        else:
            self.fields["status"].choices = StatusChampionship.choices

        self.fields["seeding_method"].initial = (
            self.instance.seeding_method
            if self.instance and self.instance.pk
            else SeedingMethodChampionship.RANDOM
        )

    def clean(self):
        cleaned = super().clean()
        stage_format = cleaned.get("stage_format")
        max_teams = cleaned.get("max_teams")
        status = StatusChampionship.DRAFT if self.is_create else cleaned.get("status")

        if status != StatusChampionship.DRAFT and not cleaned.get("start_date"):
            self.add_error("start_date", "Data de inicio e obrigatoria fora do rascunho.")

        if max_teams and max_teams < 2:
            self.add_error("max_teams", "O campeonato deve ter pelo menos 2 times.")

        if self.instance and self.instance.pk and Match.objects.filter(championship=self.instance).exists():
            for field_name in STRUCTURE_FIELDS:
                old_value = getattr(self.instance, field_name)
                new_value = cleaned.get(field_name)
                if old_value != new_value:
                    self.add_error(
                        field_name,
                        "Nao e possivel alterar a estrutura depois que partidas foram geradas.",
                    )

        if stage_format == StageFormat.ROUND_ROBIN:
            self._clean_round_robin(cleaned, max_teams)
        elif stage_format == StageFormat.SINGLE_ELIMINATION:
            self._clean_elimination(cleaned, max_teams, PlayoffFormat.SINGLE_ELIMINATION)
        elif stage_format == StageFormat.DOUBLE_ELIMINATION:
            self._clean_elimination(cleaned, max_teams, PlayoffFormat.DOUBLE_ELIMINATION)
        elif stage_format == StageFormat.GROUP_THEN_PLAYOFFS:
            self._clean_groups_then_playoffs(cleaned, max_teams)

        return cleaned

    def _clean_round_robin(self, cleaned, max_teams):
        cleaned["group_count"] = 1
        cleaned["teams_per_group"] = max_teams
        cleaned["teams_advancing_per_group"] = 0
        cleaned["playoff_format"] = None
        cleaned["playoff_match_format"] = None
        cleaned["final_match_format"] = None
        cleaned["third_place_match"] = False

        if not cleaned.get("group_match_format"):
            self.add_error("group_match_format", "Informe o formato das partidas.")

    def _clean_elimination(self, cleaned, max_teams, playoff_format):
        cleaned["group_count"] = None
        cleaned["teams_per_group"] = None
        cleaned["teams_advancing_per_group"] = None
        cleaned["group_match_format"] = None
        cleaned["playoff_format"] = playoff_format

        if max_teams and not _is_power_of_two(max_teams):
            self.add_error("max_teams", "Eliminatorias precisam de um numero de times em potencia de 2.")

        if not cleaned.get("playoff_match_format"):
            self.add_error("playoff_match_format", "Informe o formato do playoff.")

        if not cleaned.get("final_match_format"):
            self.add_error("final_match_format", "Informe o formato da final.")

    def _clean_groups_then_playoffs(self, cleaned, max_teams):
        group_count = cleaned.get("group_count")
        teams_per_group = cleaned.get("teams_per_group")
        advancing = cleaned.get("teams_advancing_per_group")

        required_fields = (
            "group_count",
            "teams_per_group",
            "teams_advancing_per_group",
            "group_match_format",
            "playoff_format",
            "playoff_match_format",
            "final_match_format",
        )
        for field_name in required_fields:
            if cleaned.get(field_name) in (None, ""):
                self.add_error(field_name, "Campo obrigatorio para grupos + playoffs.")

        if group_count and teams_per_group and max_teams and group_count * teams_per_group != max_teams:
            raise ValidationError("A quantidade de grupos multiplicada pelos times por grupo deve bater com o total de times.")

        if advancing and teams_per_group and advancing >= teams_per_group:
            self.add_error(
                "teams_advancing_per_group",
                "O numero de classificados precisa ser menor que o numero de times no grupo.",
            )

        playoff_slots = (group_count or 0) * (advancing or 0)
        if playoff_slots and not _is_power_of_two(playoff_slots):
            self.add_error(
                "teams_advancing_per_group",
                "O total de classificados para playoffs precisa ser potencia de 2.",
            )

    def save(self, commit=True):
        championship = super().save(commit=False)
        if self.is_create:
            championship.status = StatusChampionship.DRAFT
        if commit:
            championship.full_clean()
            championship.save()
            self.save_m2m()
        return championship
