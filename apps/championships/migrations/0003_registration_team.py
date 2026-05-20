# Generated manually for teams integration.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("championships", "0002_alter_tiebreakerrule_options_and_more"),
        ("teams", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="registration",
            name="team",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="registrations",
                to="teams.team",
                verbose_name="Equipe",
            ),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="registration",
            constraint=models.UniqueConstraint(
                fields=("championship", "team"),
                name="unique_championship_team",
            ),
        ),
    ]
