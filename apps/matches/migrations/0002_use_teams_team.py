# Generated manually for teams integration.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0001_initial"),
        ("teams", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="gameresult",
            options={
                "verbose_name": "Resultado da Partida",
                "verbose_name_plural": "Resultado das Partidas",
            },
        ),
        migrations.AlterModelOptions(
            name="groupstanding",
            options={
                "verbose_name": "Classificação",
                "verbose_name_plural": "Classificações",
            },
        ),
        migrations.AlterField(
            model_name="groupstanding",
            name="position",
            field=models.IntegerField(blank=True, null=True, verbose_name="Posição"),
        ),
        migrations.AlterField(
            model_name="match",
            name="team_a",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="matches_as_team_a",
                to="teams.team",
                verbose_name="Time A",
            ),
        ),
        migrations.AlterField(
            model_name="match",
            name="team_b",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="matches_as_team_b",
                to="teams.team",
                verbose_name="Time B",
            ),
        ),
        migrations.AlterField(
            model_name="match",
            name="winner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="matches_won",
                to="teams.team",
                verbose_name="Vencedor",
            ),
        ),
        migrations.AlterField(
            model_name="groupstanding",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="teams.team",
                verbose_name="Time",
            ),
        ),
        migrations.AlterField(
            model_name="gameresult",
            name="winner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                to="teams.team",
                verbose_name="Vencedor",
            ),
        ),
        migrations.DeleteModel(
            name="Team",
        ),
    ]
