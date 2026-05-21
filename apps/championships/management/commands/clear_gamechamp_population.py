from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.championships.models import Championship
from apps.teams.models import Team


class Command(BaseCommand):
    help = "Remove os dados de exemplo criados pelo comando populate_gamechamp."

    def handle(self, *args, **options):
        championships_deleted, _ = Championship.objects.filter(name__startswith="Seed ").delete()
        teams_deleted, _ = Team.objects.filter(name__startswith="Seed ").delete()
        users_deleted, _ = User.objects.filter(username__startswith="seed_").delete()

        self.stdout.write(self.style.SUCCESS("Dados de exemplo removidos com sucesso."))
        self.stdout.write(f"Campeonatos removidos: {championships_deleted}")
        self.stdout.write(f"Equipes removidas: {teams_deleted}")
        self.stdout.write(f"Usuarios removidos: {users_deleted}")
