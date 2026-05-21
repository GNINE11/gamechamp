from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.championships.models import Championship
from apps.teams.models import Team


class Command(BaseCommand):
    help = "Remove os dados de exemplo criados pelo comando populate_gamechamp."

    def handle(self, *args, **options):

        championships_qs = Championship.objects.filter(name__startswith="Seed ")
        teams_qs = Team.objects.filter(name__startswith="Seed ")
        users_qs = User.objects.filter(username__startswith="seed_")

        championships_count = championships_qs.count()
        teams_count = teams_qs.count()
        users_count = users_qs.count()

        championships_qs.delete()
        teams_qs.delete()
        users_qs.delete()

        self.stdout.write(
            self.style.SUCCESS("Dados de exemplo removidos com sucesso.")
        )

        self.stdout.write(
            f"Campeonatos removidos: {championships_count}"
        )

        self.stdout.write(
            f"Equipes removidas: {teams_count}"
        )

        self.stdout.write(
            f"Usuarios removidos: {users_count}"
        )
