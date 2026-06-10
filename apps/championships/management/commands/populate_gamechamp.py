from datetime import timedelta
import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.championships.models import (
    Championship,
    ChampionshipStaff,
    MatchFormat,
    PlayoffFormat,
    Registration,
    RoleStaff,
    SeedingMethodChampionship,
    StageFormat,
    StatusChampionship,
    StatusRegistration,
    TiebreakerCriterion,
    TiebreakerRule,
)
from apps.matches.models import GameFormat, GameResult, GameStatus, Group, GroupStanding, Match, Phase
from apps.teams.models import Team, TeamMembership


class Command(BaseCommand):
    help = "Popula o banco com múltiplos campeonatos de exemplo, com times lotados (4-5 membros) e formatos variados."

    def handle(self, *args, **options):
        today = timezone.localdate()
        password = "gamechamp123"

        with transaction.atomic():
            self.clear_existing_seed_data()
            users = self.create_users(password)
            teams = self.create_teams_with_members(users, password)
            championships = self.create_championships(teams, users["owner"], today)

        self.stdout.write(self.style.SUCCESS("Todos os campeonatos foram criados com sucesso."))
        self.stdout.write(f"Usuários seedados usam a senha: {password}")
        for champ in championships:
            self.stdout.write(f" - {champ.name} ({champ.get_status_display()}) - {champ.get_stage_format_display()}")

    def clear_existing_seed_data(self):
        Championship.objects.filter(name__startswith="Seed ").delete()
        Team.objects.filter(name__startswith="Seed ").delete()
        User.objects.filter(username__startswith="seed_").delete()

    def create_users(self, password):
        users = {
            "owner": User.objects.create_user(
                username="seed_owner",
                email="owner.seed@example.com",
                password=password,
                bio="Organizador dos campeonatos seed.",
                ranking_score=2200,
            ),
            "moderator": User.objects.create_user(
                username="seed_moderator",
                email="moderator.seed@example.com",
                password=password,
                bio="Moderador dos campeonatos seed.",
                ranking_score=1900,
            ),
        }

        # 20 capitães
        for index in range(1, 21):
            users[f"captain_{index:02d}"] = User.objects.create_user(
                username=f"seed_captain_{index:02d}",
                email=f"captain{index:02d}.seed@example.com",
                password=password,
                bio=f"Capitão da equipe seed {index:02d}.",
                ranking_score=1500 + index * 25,
            )

        # 40 membros comuns
        for index in range(1, 41):
            users[f"member_{index:02d}"] = User.objects.create_user(
                username=f"seed_member_{index:02d}",
                email=f"member{index:02d}.seed@example.com",
                password=password,
                bio=f"Membro de time seed.",
                ranking_score=1200 + (index % 20) * 30,
            )

        return users

    def create_teams_with_members(self, users, password):
        team_names = [
            "Seed Dragons", "Seed Ninjas", "Seed Titans", "Seed Falcons",
            "Seed Phoenix", "Seed Vikings", "Seed Wolves", "Seed Sharks",
            "Seed Rangers", "Seed Knights", "Seed Hunters", "Seed Eclipse",
            "Seed Quantum", "Seed Aurora", "Seed Venom", "Seed Storm",
            "Seed Thunder", "Seed Blaze", "Seed Glacier", "Seed Inferno"
        ]

        all_members = [users[f"member_{i:02d}"] for i in range(1, 41)]
        teams = []

        for idx, name in enumerate(team_names, start=1):
            captain = users[f"captain_{idx:02d}"]
            team = Team.objects.create(name=name, captain=captain)
            TeamMembership.objects.get_or_create(team=team, player=captain)

            num_members = random.randint(3, 4)
            available_members = [m for m in all_members if m != captain]
            chosen_members = random.sample(available_members, min(num_members, len(available_members)))
            for member in chosen_members:
                TeamMembership.objects.get_or_create(team=team, player=member)

            teams.append(team)

        return teams

    def create_championships(self, teams, owner, today):
        championships = []

        # 1. Campeonato ABERTO com Fase de Grupos + Playoffs (16 times, 30% ocupado)
        champ1 = self.create_basic_championship(
            name="Seed Major Open - 1/2",
            owner=owner,
            start_date=today + timedelta(days=5),
            stage_format=StageFormat.GROUP_THEN_PLAYOFFS,
            max_teams=16,
            group_count=4,
            teams_per_group=4,
            teams_advancing_per_group=2,
            group_match_format=MatchFormat.BO1,
            playoff_format=PlayoffFormat.DOUBLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            third_place_match=False,
            final_status=StatusChampionship.OPEN,
        )
        self.create_staff(champ1, owner)
        self.create_tiebreakers(champ1)
        self.create_registrations_partial(champ1, teams[:16], occupancy=0.3)
        championships.append(champ1)

        # 2. Campeonato EM ANDAMENTO - Eliminação simples (8 times)
        champ2 = self.create_basic_championship(
            name="Seed Single Elim Live",
            owner=owner,
            start_date=today - timedelta(days=2),
            stage_format=StageFormat.SINGLE_ELIMINATION,
            max_teams=8,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            third_place_match=True,
            final_status=StatusChampionship.IN_PROGRESS,
        )
        self.create_staff(champ2, owner)
        self.create_tiebreakers(champ2)
        self.create_registrations_full(champ2, teams[:8])
        self.create_single_elimination_in_progress(champ2, teams[:8], today - timedelta(days=1))
        champ2.status = StatusChampionship.IN_PROGRESS
        champ2.save(update_fields=["status"])
        championships.append(champ2)

        # 3. Campeonato FINALIZADO - Dupla eliminação (8 times)
        champ3 = self.create_basic_championship(
            name="Seed Double Elim Finished",
            owner=owner,
            start_date=today - timedelta(days=10),
            stage_format=StageFormat.DOUBLE_ELIMINATION,
            max_teams=8,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.DOUBLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            third_place_match=True,
            final_status=StatusChampionship.FINISHED,
        )
        self.create_staff(champ3, owner)
        self.create_tiebreakers(champ3)
        self.create_registrations_full(champ3, teams[:8])
        champion = self.create_double_elimination_playoff(champ3, teams[:8], today - timedelta(days=9), 1)
        champ3.status = StatusChampionship.FINISHED
        champ3.champion = champion
        champ3.save(update_fields=["status", "champion"])
        championships.append(champ3)

        # 4. Campeonato FINALIZADO - Pontos corridos (6 times)
        champ4 = self.create_basic_championship(
            name="Seed Round Robin Finished",
            owner=owner,
            start_date=today - timedelta(days=15),
            stage_format=StageFormat.ROUND_ROBIN,
            max_teams=6,
            group_count=1,
            teams_per_group=6,
            teams_advancing_per_group=0,
            group_match_format=MatchFormat.BO3,
            playoff_format=None,
            playoff_match_format=None,
            final_match_format=None,
            third_place_match=False,
            final_status=StatusChampionship.FINISHED,
        )
        self.create_staff(champ4, owner)
        self.create_tiebreakers(champ4)
        self.create_registrations_full(champ4, teams[8:14])
        champion = self.create_round_robin(champ4, teams[8:14], today - timedelta(days=14))
        champ4.status = StatusChampionship.FINISHED
        champ4.champion = champion
        champ4.save(update_fields=["status", "champion"])
        championships.append(champ4)

        # 5. Campeonato ABERTO - Eliminação simples (8 times, 30% ocupado)
        champ5 = self.create_basic_championship(
            name="Seed Single Elim Open",
            owner=owner,
            start_date=today + timedelta(days=8),
            stage_format=StageFormat.SINGLE_ELIMINATION,
            max_teams=8,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO1,
            final_match_format=MatchFormat.BO3,
            third_place_match=False,
            final_status=StatusChampionship.OPEN,
        )
        self.create_staff(champ5, owner)
        self.create_tiebreakers(champ5)
        self.create_registrations_partial(champ5, teams[:8], occupancy=0.3)
        championships.append(champ5)

        # 6. NOVO CAMPEONATO ABERTO - Fase de grupos + playoffs, com 2 aprovados e 18 pendentes
        champ6 = self.create_basic_championship(
            name="Seed Major Open - 2/2",
            owner=owner,
            start_date=today + timedelta(days=80),
            stage_format=StageFormat.GROUP_THEN_PLAYOFFS,
            max_teams=20,
            group_count=4,
            teams_per_group=5,
            teams_advancing_per_group=2,
            group_match_format=MatchFormat.BO1,
            playoff_format=PlayoffFormat.DOUBLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            third_place_match=False,
            final_status=StatusChampionship.OPEN,
        )
        self.create_staff(champ6, owner)
        self.create_tiebreakers(champ6)
        self.create_registrations_mixed(champ6, teams, approved_count=2, pending_count=18)
        championships.append(champ6)

        # 7. Campeonato FINALIZADO - 4 times, eliminação simples (sem 3º lugar)
        champ7 = self.create_basic_championship(
            name="Seed Single Elim 4 Teams - Finished",
            owner=owner,
            start_date=today - timedelta(days=5),
            stage_format=StageFormat.SINGLE_ELIMINATION,
            max_teams=4,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            third_place_match=False,
            final_status=StatusChampionship.FINISHED,
        )
        self.create_staff(champ7, owner)
        self.create_tiebreakers(champ7)
        self.create_registrations_full(champ7, teams[16:20])  # últimos 4 times
        champion = self.create_4team_single_elim_finished(champ7, teams[16:20], today - timedelta(days=4), third_place=False)
        champ7.status = StatusChampionship.FINISHED
        champ7.champion = champion
        champ7.save(update_fields=["status", "champion"])
        championships.append(champ7)

        # 8. Campeonato FINALIZADO - 4 times, eliminação simples + disputa de 3º lugar
        champ8 = self.create_basic_championship(
            name="Seed Single Elim 4 Teams - Finished (3rd place)",
            owner=owner,
            start_date=today - timedelta(days=6),
            stage_format=StageFormat.SINGLE_ELIMINATION,
            max_teams=4,
            group_count=None,
            teams_per_group=None,
            teams_advancing_per_group=None,
            group_match_format=None,
            playoff_format=PlayoffFormat.SINGLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            third_place_match=True,
            final_status=StatusChampionship.FINISHED,
        )
        self.create_staff(champ8, owner)
        self.create_tiebreakers(champ8)
        self.create_registrations_full(champ8, teams[12:16])  # times 13-16
        champion = self.create_4team_single_elim_finished(champ8, teams[12:16], today - timedelta(days=5), third_place=True)
        champ8.status = StatusChampionship.FINISHED
        champ8.champion = champion
        champ8.save(update_fields=["status", "champion"])
        championships.append(champ8)

        # 9. Campeonato EM ANDAMENTO - 8 times, fase de grupos (finalizada) + eliminação dupla (playoff em andamento)
        champ9 = self.create_basic_championship(
            name="Seed Groups + Double Elim Live",
            owner=owner,
            start_date=today - timedelta(days=3),
            stage_format=StageFormat.GROUP_THEN_PLAYOFFS,
            max_teams=8,
            group_count=2,
            teams_per_group=4,
            teams_advancing_per_group=2,
            group_match_format=MatchFormat.BO1,
            playoff_format=PlayoffFormat.DOUBLE_ELIMINATION,
            playoff_match_format=MatchFormat.BO3,
            final_match_format=MatchFormat.BO5,
            third_place_match=True,
            final_status=StatusChampionship.IN_PROGRESS,
        )
        self.create_staff(champ9, owner)
        self.create_tiebreakers(champ9)
        self.create_registrations_full(champ9, teams[:8])
        # Fase de grupos finalizada
        advancing_teams = self.create_group_stage_finished(champ9, teams[:8], today - timedelta(days=2))
        # Playoff de dupla eliminação em andamento (quartas da upper finalizadas, resto agendado)
        self.create_double_elim_playoff_in_progress(champ9, advancing_teams, today - timedelta(days=1))
        champ9.status = StatusChampionship.IN_PROGRESS
        champ9.save(update_fields=["status"])
        championships.append(champ9)

        return championships

    # ------------------ MÉTODOS AUXILIARES EXISTENTES ------------------
    def create_basic_championship(self, name, owner, start_date, stage_format, max_teams,
                                   group_count, teams_per_group, teams_advancing_per_group,
                                   group_match_format, playoff_format, playoff_match_format,
                                   final_match_format, third_place_match, final_status):
        champ = Championship(
            name=name,
            game="Counter-Strike 2",
            status=StatusChampionship.OPEN,
            max_teams=max_teams,
            start_date=start_date,
            stage_format=stage_format,
            group_count=group_count,
            teams_per_group=teams_per_group,
            teams_advancing_per_group=teams_advancing_per_group,
            group_match_format=group_match_format,
            playoff_format=playoff_format,
            playoff_match_format=playoff_match_format,
            final_match_format=final_match_format,
            third_place_match=third_place_match,
            seeding_method=SeedingMethodChampionship.MANUAL,
            created_by=owner,
        )
        champ.full_clean()
        champ.save()
        return champ

    def create_staff(self, championship, owner):
        ChampionshipStaff.objects.create(
            championship=championship,
            user=owner,
            role=RoleStaff.OWNER,
        )
        mod_user = User.objects.filter(username="seed_moderator").first()
        if mod_user:
            ChampionshipStaff.objects.create(
                championship=championship,
                user=mod_user,
                role=RoleStaff.MODERATOR,
            )

    def create_tiebreakers(self, championship):
        criteria = [
            (1, TiebreakerCriterion.POINTS),
            (2, TiebreakerCriterion.WINS),
            (3, TiebreakerCriterion.ROUND_DIFF),
            (4, TiebreakerCriterion.ROUNDS_WON),
            (5, TiebreakerCriterion.WIN_RATE),
        ]
        for priority, criterion in criteria:
            TiebreakerRule.objects.create(
                championship=championship,
                priority=priority,
                criterion=criterion,
            )

    def create_registrations_full(self, championship, teams):
        for team in teams:
            reg = Registration(championship=championship, team=team, status=StatusRegistration.APPROVED)
            reg.full_clean()
            reg.save()

    def create_registrations_partial(self, championship, all_teams, occupancy=0.3):
        max_teams = championship.max_teams
        num_approved = int(max_teams * occupancy)
        if num_approved < 1:
            num_approved = 1
        approved_teams = random.sample(all_teams, min(num_approved, len(all_teams)))
        for team in approved_teams:
            reg = Registration(championship=championship, team=team, status=StatusRegistration.APPROVED)
            reg.full_clean()
            reg.save()

    def create_registrations_mixed(self, championship, all_teams, approved_count, pending_count):
        total_needed = approved_count + pending_count
        if total_needed > len(all_teams):
            raise ValueError(f"Total de inscrições ({total_needed}) excede o número de times disponíveis ({len(all_teams)}).")
        selected_teams = random.sample(all_teams, total_needed)
        for i, team in enumerate(selected_teams):
            status = StatusRegistration.APPROVED if i < approved_count else StatusRegistration.PENDING
            reg = Registration(championship=championship, team=team, status=status)
            reg.full_clean()
            reg.save()

    # ------------------ MÉTODOS DE CRIAÇÃO DE PARTIDAS ------------------
    def create_finished_match(self, championship, team_a, team_b, winner, match_format, phase,
                               round_number, scheduled_at, group=None, playoff_round=None):
        match = Match(
            championship=championship,
            match_format=match_format,
            phase=phase,
            group=group,
            playoff_round=playoff_round,
            round_number=round_number,
            team_a=team_a,
            team_b=team_b,
            winner=winner,
            status=GameStatus.FINISHED,
            scheduled_at=scheduled_at,
        )
        match.full_clean()
        match.save()
        games_to_win = {GameFormat.BO1: 1, GameFormat.BO3: 2, GameFormat.BO5: 3}[match_format]
        for game_number in range(1, games_to_win + 1):
            winner_is_team_a = (winner == team_a)
            GameResult.objects.create(
                match_id=match,
                winner=winner,
                game_number=game_number,
                score_a=13 if winner_is_team_a else 8,
                score_b=8 if winner_is_team_a else 13,
                map_name=f"Seed Map {game_number}",
            )
        return match

    def create_scheduled_match(self, championship, team_a, team_b, match_format, phase,
                                round_number, scheduled_at, group=None, playoff_round=None):
        match = Match(
            championship=championship,
            match_format=match_format,
            phase=phase,
            group=group,
            playoff_round=playoff_round,
            round_number=round_number,
            team_a=team_a,
            team_b=team_b,
            status=GameStatus.SCHEDULED,
            scheduled_at=scheduled_at,
        )
        match.full_clean()
        match.save()
        return match

    def create_double_elimination_playoff(self, championship, seeds, scheduled_at, round_number):
        def playoff_match(team_a, team_b, winner, playoff_round):
            nonlocal scheduled_at, round_number
            match = self.create_finished_match(
                championship=championship,
                team_a=team_a,
                team_b=team_b,
                winner=winner,
                match_format=GameFormat.BO3,
                phase=Phase.PLAYOFF,
                round_number=round_number,
                scheduled_at=scheduled_at,
                playoff_round=playoff_round,
            )
            scheduled_at += timedelta(days=1)
            round_number += 1
            return match

        upper_quarters = [
            playoff_match(seeds[0], seeds[7], seeds[0], 1),
            playoff_match(seeds[2], seeds[5], seeds[2], 1),
            playoff_match(seeds[4], seeds[3], seeds[4], 1),
            playoff_match(seeds[6], seeds[1], seeds[6], 1),
        ]
        lower_round_one = [
            playoff_match(upper_quarters[0].team_b, upper_quarters[1].team_b, upper_quarters[0].team_b, 2),
            playoff_match(upper_quarters[2].team_b, upper_quarters[3].team_b, upper_quarters[3].team_b, 2),
        ]
        upper_semis = [
            playoff_match(upper_quarters[0].winner, upper_quarters[1].winner, upper_quarters[0].winner, 3),
            playoff_match(upper_quarters[2].winner, upper_quarters[3].winner, upper_quarters[2].winner, 3),
        ]
        lower_round_two = [
            playoff_match(lower_round_one[0].winner, upper_semis[1].team_b, upper_semis[1].team_b, 4),
            playoff_match(lower_round_one[1].winner, upper_semis[0].team_b, upper_semis[0].team_b, 4),
        ]
        lower_semifinal = playoff_match(lower_round_two[0].winner, lower_round_two[1].winner, lower_round_two[1].winner, 5)
        upper_final = playoff_match(upper_semis[0].winner, upper_semis[1].winner, upper_semis[0].winner, 5)
        lower_final = playoff_match(lower_semifinal.winner, upper_final.team_b, upper_final.team_b, 6)
        grand_final = self.create_finished_match(
            championship=championship,
            team_a=upper_final.winner,
            team_b=lower_final.winner,
            winner=upper_final.winner,
            match_format=GameFormat.BO5,
            phase=Phase.GRAND_FINAL,
            round_number=round_number,
            scheduled_at=scheduled_at,
        )
        return grand_final.winner

    def create_single_elimination_in_progress(self, championship, seeds, start_date):
        scheduled_at = start_date
        round_number = 1
        quarters = []
        bracket = [(seeds[0], seeds[7]), (seeds[2], seeds[5]), (seeds[4], seeds[3]), (seeds[6], seeds[1])]
        winners = [seeds[0], seeds[2], seeds[4], seeds[6]]
        for (a, b), winner in zip(bracket, winners):
            match = self.create_finished_match(
                championship, a, b, winner, GameFormat.BO3, Phase.PLAYOFF,
                round_number, scheduled_at, playoff_round=1
            )
            quarters.append(match)
            scheduled_at += timedelta(days=1)
            round_number += 1
        semis = []
        semi_winners = [seeds[0], seeds[4]]
        for i in range(2):
            a = quarters[i*2].winner
            b = quarters[i*2+1].winner
            match = self.create_finished_match(
                championship, a, b, semi_winners[i], GameFormat.BO3, Phase.PLAYOFF,
                round_number, scheduled_at, playoff_round=2
            )
            semis.append(match)
            scheduled_at += timedelta(days=1)
            round_number += 1
        final = self.create_scheduled_match(
            championship, semis[0].winner, semis[1].winner, GameFormat.BO5, Phase.GRAND_FINAL,
            round_number, scheduled_at
        )
        if championship.third_place_match:
            self.create_finished_match(
                championship, semis[0].team_b, semis[1].team_b, semis[0].team_b, GameFormat.BO3,
                Phase.PLAYOFF, round_number+1, scheduled_at + timedelta(days=1), playoff_round=3
            )
        return final

    def create_round_robin(self, championship, teams, start_date):
        group = Group.objects.create(championship=championship, name="Único")
        scheduled_at = start_date
        round_num = 1
        records = {team: {"wins": 0, "losses": 0, "rounds_won": 0, "rounds_lost": 0} for team in teams}
        for i, team_a in enumerate(teams):
            for team_b in teams[i+1:]:
                score_a = team_a.captain.ranking_score if team_a.captain else 1500
                score_b = team_b.captain.ranking_score if team_b.captain else 1500
                winner = team_a if score_a >= score_b else team_b
                loser = team_b if winner == team_a else team_a
                records[winner]["wins"] += 1
                records[winner]["rounds_won"] += 13
                records[winner]["rounds_lost"] += 8
                records[loser]["losses"] += 1
                records[loser]["rounds_won"] += 8
                records[loser]["rounds_lost"] += 13
                self.create_finished_match(
                    championship, team_a, team_b, winner, championship.group_match_format,
                    Phase.GROUP, round_num, scheduled_at, group=group
                )
                scheduled_at += timedelta(days=1)
                round_num += 1
        ordered = sorted(teams, key=lambda t: (records[t]["wins"], records[t]["rounds_won"] - records[t]["rounds_lost"], records[t]["rounds_won"]), reverse=True)
        for pos, team in enumerate(ordered, 1):
            r = records[team]
            GroupStanding.objects.create(
                group=group, team=team, wins=r["wins"], losses=r["losses"],
                points=r["wins"]*3, rounds_won=r["rounds_won"], rounds_lost=r["rounds_lost"],
                round_diff=r["rounds_won"] - r["rounds_lost"], position=pos
            )
        return ordered[0]

    # ------------------ NOVOS MÉTODOS PARA OS CAMPEONATOS ADICIONAIS ------------------
    def create_4team_single_elim_finished(self, championship, seeds, start_date, third_place=False):
        """Cria uma chave de eliminação simples com 4 times, todas as partidas finalizadas."""
        scheduled_at = start_date
        round_number = 1
        # Semifinais
        semi1 = self.create_finished_match(
            championship, seeds[0], seeds[3], seeds[0], championship.playoff_match_format,
            Phase.PLAYOFF, round_number, scheduled_at, playoff_round=1
        )
        scheduled_at += timedelta(days=1)
        round_number += 1
        semi2 = self.create_finished_match(
            championship, seeds[1], seeds[2], seeds[1], championship.playoff_match_format,
            Phase.PLAYOFF, round_number, scheduled_at, playoff_round=1
        )
        scheduled_at += timedelta(days=1)
        round_number += 1
        # Final
        final = self.create_finished_match(
            championship, semi1.winner, semi2.winner, semi1.winner, championship.final_match_format,
            Phase.GRAND_FINAL, round_number, scheduled_at
        )
        if third_place:
            scheduled_at += timedelta(days=1)
            self.create_finished_match(
                championship, semi1.team_b, semi2.team_b, semi1.team_b, championship.playoff_match_format,
                Phase.PLAYOFF, round_number+1, scheduled_at, playoff_round=2
            )
        return final.winner

    def create_group_stage_finished(self, championship, teams, start_date):
        """Cria fase de grupos completa com 2 grupos de 4, avançam 2 por grupo. Retorna lista dos 4 classificados."""
        groups_data = []
        advancing = []
        scheduled_at = start_date
        round_number = 1
        # Grupo A (times 0-3)
        group_a = Group.objects.create(championship=championship, name="A")
        group_a_teams = teams[:4]
        # Grupo B (times 4-7)
        group_b = Group.objects.create(championship=championship, name="B")
        group_b_teams = teams[4:8]
        for group, group_teams in [(group_a, group_a_teams), (group_b, group_b_teams)]:
            records = {team: {"wins": 0, "losses": 0, "rounds_won": 0, "rounds_lost": 0} for team in group_teams}
            # Todos os confrontos dentro do grupo (turno único)
            for i, team_a in enumerate(group_teams):
                for team_b in group_teams[i+1:]:
                    # Define vencedor baseado no ranking_score do capitão
                    score_a = team_a.captain.ranking_score if team_a.captain else 1500
                    score_b = team_b.captain.ranking_score if team_b.captain else 1500
                    winner = team_a if score_a >= score_b else team_b
                    loser = team_b if winner == team_a else team_a
                    records[winner]["wins"] += 1
                    records[winner]["rounds_won"] += 13
                    records[winner]["rounds_lost"] += 8
                    records[loser]["losses"] += 1
                    records[loser]["rounds_won"] += 8
                    records[loser]["rounds_lost"] += 13
                    self.create_finished_match(
                        championship, team_a, team_b, winner, championship.group_match_format,
                        Phase.GROUP, round_number, scheduled_at, group=group
                    )
                    scheduled_at += timedelta(days=1)
                    round_number += 1
            # Ordena e cria standings
            ordered = sorted(group_teams, key=lambda t: (records[t]["wins"], records[t]["rounds_won"] - records[t]["rounds_lost"], records[t]["rounds_won"]), reverse=True)
            for pos, team in enumerate(ordered, 1):
                r = records[team]
                GroupStanding.objects.create(
                    group=group, team=team, wins=r["wins"], losses=r["losses"],
                    points=r["wins"]*3, rounds_won=r["rounds_won"], rounds_lost=r["rounds_lost"],
                    round_diff=r["rounds_won"] - r["rounds_lost"], position=pos
                )
            advancing.extend(ordered[:2])
        return advancing  # 4 times

    def create_double_elim_playoff_in_progress(self, championship, seeds, start_date):
        """
        Cria playoff de dupla eliminação com 4 times (seeds classificados).
        Upper bracket semifinals são finalizadas. Os vencedores vão para upper final (agendada).
        Os perdedores vão para lower bracket semifinal (agendada).
        """
        scheduled_at = start_date
        round_number = 1
        # Upper bracket semifinais (finalizadas)
        ub_semi1 = self.create_finished_match(
            championship, seeds[0], seeds[3], seeds[0], championship.playoff_match_format,
            Phase.PLAYOFF, round_number, scheduled_at, playoff_round=1
        )
        scheduled_at += timedelta(days=1)
        round_number += 1
        ub_semi2 = self.create_finished_match(
            championship, seeds[1], seeds[2], seeds[1], championship.playoff_match_format,
            Phase.PLAYOFF, round_number, scheduled_at, playoff_round=1
        )
        scheduled_at += timedelta(days=1)
        round_number += 1
        # Upper final (agendada)
        ub_final = self.create_scheduled_match(
            championship, ub_semi1.winner, ub_semi2.winner, championship.playoff_match_format,
            Phase.PLAYOFF, round_number, scheduled_at, playoff_round=2
        )
        scheduled_at += timedelta(days=1)
        round_number += 1
        # Lower bracket round 1 (perdedores das upper semis) - agendada
        lb_round1 = self.create_scheduled_match(
            championship, ub_semi1.team_b, ub_semi2.team_b, championship.playoff_match_format,
            Phase.PLAYOFF, round_number, scheduled_at, playoff_round=3
        )
        scheduled_at += timedelta(days=1)
        round_number += 1
        # Lower final (vencedor do lower round 1 vs perdedor da upper final) - agendada
        # (deixamos agendada, sem definir times ainda pois dependem de resultados)
        # Para simplificar, criamos uma partida agendada com times None? O modelo não permite team_a/team_b nulos?
        # Vamos criar com placeholders (os times serão definidos depois manualmente ou ignoramos)
        # Como o objetivo é apenas popular, podemos criar a partida com os times que irão competir (assumindo resultados)
        # Vamos supor que o perdedor da upper final é ub_semi2.winner (por exemplo) e o vencedor do lower é ub_semi1.team_b
        # Para não complicar, criamos uma partida agendada com times fixos (qualquer um)
        lb_final = self.create_scheduled_match(
            championship, lb_round1.team_a, ub_final.team_b, championship.playoff_match_format,
            Phase.PLAYOFF, round_number, scheduled_at, playoff_round=4
        )
        scheduled_at += timedelta(days=1)
        round_number += 1
        # Grand final (agendada)
        grand_final = self.create_scheduled_match(
            championship, ub_final.team_a, lb_final.team_a, championship.final_match_format,
            Phase.GRAND_FINAL, round_number, scheduled_at
        )
        # Disputa de 3º lugar (se houver) - agendada
        if championship.third_place_match:
            scheduled_at += timedelta(days=1)
            self.create_scheduled_match(
                championship, ub_semi1.team_b, ub_semi2.team_b, championship.playoff_match_format,
                Phase.PLAYOFF, round_number+1, scheduled_at, playoff_round=5
            )