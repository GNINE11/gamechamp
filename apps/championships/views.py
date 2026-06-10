from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages                      # NOVO
from django.core.exceptions import PermissionDenied, ValidationError       # NOVO
from django.db.models import Case, When, Value, IntegerField, Count, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from apps.matches.models import Match, GameResult, GameStatus 
from .models import (
    Championship,
    ChampionshipStaff,
    StatusChampionship,
    StatusRegistration,
    Registration,
    Team,
    RoleStaff,
    User,
    MatchFormat,
)


_MODE_CONFIG = {
    'public': {
        'page_label': 'Descubra novos desafios',
        'page_title': 'Campeonatos Disponíveis',
        'show_fab':   False,
    },
    'my': {
        'page_label': 'Suas participações',
        'page_title': 'Meus Campeonatos',
        'show_fab':   False,
    },
    'management': {
        'page_label': 'Campeonatos que você gerencia',
        'page_title': 'Área da Staff',
        'show_fab': True,
    },
}
 
_PH_CLASS = {
    StatusChampionship.OPEN:        'card-ph-open',
    StatusChampionship.IN_PROGRESS: 'card-ph-live',
    StatusChampionship.FINISHED:    'card-ph-finished',
    StatusChampionship.DRAFT:       'card-ph-finished',
}
 
# ── Lógica do CTA ─────────────────────────────────────────────────────────────
 
def _compute_cta(champ, mode, reg_status):
    """
    Retorna um dict descrevendo o botão de ação do card, ou None se não houver ação.
    Toda a lógica fica aqui — o template só renderiza o que recebe.
    """
    s = champ.status
 
    if mode == 'management':
        return {
            'label': 'Gerenciar', 'icon': 'settings',
            'css': 'btn-card-results',
            'url': reverse('championship:management-championship-dashboard', args=[champ.pk]),
            'is_form': False, 'disabled': False,
        }

         
 
    if mode == 'my':
        if reg_status == StatusRegistration.PENDING:
            return {
                'label': 'Cancelar Inscrição', 'icon': 'cancel',
                'css': 'btn-card-waitlist', 'url': '#',   # TODO: url 'cancel_registration'
                'is_form': True, 'disabled': False,
            }
        if s == StatusChampionship.IN_PROGRESS:
            return {
                'label': 'Ver Chaveamento', 'icon': 'chevron_right',
                'css': 'btn-card-live', 'url': reverse('championship:my-championship-structure'),        # TODO: url 'bracket'
                'is_form': False, 'disabled': False,
            }
        if s == StatusChampionship.FINISHED:
            return {
                'label': 'Ver Resultados', 'icon': 'history',
                'css': 'btn-card-results', 'url': reverse('championship:my-championship-structure'),     # TODO: url 'bracket'
                'is_form': False, 'disabled': False,
            }
        return None
 
    # mode == 'public'
    if s == StatusChampionship.IN_PROGRESS:
        return {
            'label': 'Ver Chaveamento ao Vivo', 'icon': 'chevron_right',
            'css': 'btn-card-live', 'url': reverse('championship:available-championship-structure'),            # TODO: url 'bracket'
            'is_form': False, 'disabled': False,
        }
    if s == StatusChampionship.FINISHED:
        return {
            'label': 'Ver Resultados', 'icon': 'history',
            'css': 'btn-card-results', 'url': reverse('championship:available-championship-structure'),         # TODO: url 'bracket'
            'is_form': False, 'disabled': False,
        }
    if s == StatusChampionship.OPEN:
        if reg_status in (StatusRegistration.APPROVED, StatusRegistration.PENDING):
            return {
                'label': 'Cancelar Inscrição', 'icon': 'cancel',
                'css': 'btn-card-waitlist', 'url': '#',    # TODO: url 'cancel_registration'
                'is_form': True, 'disabled': False,
            }
        if champ.approved_count >= champ.max_teams:
            return {
                'label': 'Lista de Espera', 'icon': 'hourglass_empty',
                'css': 'btn-card-waitlist', 'url': None,
                'is_form': False, 'disabled': True,
            }
        return {
            'label': 'Inscrever Time', 'icon': 'add_circle',
            'css': 'btn-card-register', 'url': '#',        # TODO: url 'register_championship'
            'is_form': False, 'disabled': False,
        }
 
    return None
 
 
# ── Helpers de queryset ───────────────────────────────────────────────────────
 
def get_my_championships(user):
    return (
        Championship.objects.filter(
            Q(registrations__team__members=user) |
            Q(registrations__team__captain=user)
        )
        .distinct()
    )
 
 
def build_championship_qs(*, user=None, mode='public'):
    qs = Championship.objects.all()

    if mode == 'public':
        qs = qs.exclude(status=StatusChampionship.DRAFT)

    elif mode == 'my':
        qs = get_my_championships(user)

    elif mode == 'management':
        qs = qs.filter(staff_members__user=user).distinct()

    approved_count_subquery = (
        Registration.objects
        .filter(
            championship=OuterRef('pk'),
            status=StatusRegistration.APPROVED,
        )
        .values('championship')
        .annotate(total=Count('id'))
        .values('total')[:1]
    )

    return qs.annotate(
        status_order=Case(
            When(status=StatusChampionship.DRAFT, then=Value(1)),
            When(status=StatusChampionship.OPEN, then=Value(2)),
            When(status=StatusChampionship.IN_PROGRESS, then=Value(3)),
            When(status=StatusChampionship.FINISHED, then=Value(4)),
            output_field=IntegerField(),
        ),
        approved_count=Coalesce(
            Subquery(approved_count_subquery),
            0,
        ),
    ).order_by('status_order', 'start_date', '-created_at',)
 
 
def _get_reg_status_map(championships, user):
    """Uma única query: championship_id → status da inscrição do usuário."""
    ids = [c.pk for c in championships]
    rows = (
        Registration.objects
        .filter(
            championship_id__in=ids,
            team__in=Team.objects.filter(Q(members=user) | Q(captain=user)),
        )
        .values('championship_id', 'status')
    )
    return {r['championship_id']: r['status'] for r in rows}
 
 
def _attach_card_data(page_obj, mode, user=None):
    """Adiciona ph_class e cta em cada championship do page_obj."""
    reg_map = _get_reg_status_map(page_obj.object_list, user) if user else {}
    for champ in page_obj.object_list:
        champ.ph_class = _PH_CLASS.get(champ.status, 'card-ph-finished')
        champ.cta = _compute_cta(champ, mode, reg_map.get(champ.pk))
 
 
# ── Views ─────────────────────────────────────────────────────────────────────
 
@login_required
def list_available_championships(request):
    mode = 'public'
    page_obj = Paginator(build_championship_qs(mode=mode), 9).get_page(request.GET.get('page', 1))
    _attach_card_data(page_obj, mode, user=request.user)
    return render(request, 'championship/list.html', {'page_obj': page_obj, 'mode': mode, **_MODE_CONFIG[mode]})
 
 
@login_required
def list_my_championships(request):
    mode = 'my'
    page_obj = Paginator(build_championship_qs(user=request.user, mode=mode), 9).get_page(request.GET.get('page', 1))
    _attach_card_data(page_obj, mode, user=request.user)
    return render(request, 'championship/list.html', {'page_obj': page_obj, 'mode': mode, **_MODE_CONFIG[mode]})
 
 
@login_required
def list_management_championships(request):
    mode = 'management'
    page_obj = Paginator(build_championship_qs(user=request.user, mode=mode), 9).get_page(request.GET.get('page', 1))
    _attach_card_data(page_obj, mode)   # management não precisa de reg_map
    return render(request, 'championship/list.html', {'page_obj': page_obj, 'mode': mode, **_MODE_CONFIG[mode]})
 

@login_required
def structure_championship(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/structure.html', {
            'page_obj': page_obj,
        })

_BEST_OF_WINS = {
    'BO1': 1,
    'BO3': 2,
    'BO5': 3,
}
 
# Total de games possíveis em cada formato (para montar o formulário de placar)
_BEST_OF_MAX_GAMES = {
    'BO1': 1,
    'BO3': 3,
    'BO5': 5,
}
 
 
def _build_match_card(match):
    """Anexa dados auxiliares (placar agregado, lista de games) ao objeto Match."""
    games = list(match.gameresult_set.all())  # já vem prefetched e ordenado
    score_a = sum(1 for g in games if g.winner_id == match.team_a_id)
    score_b = sum(1 for g in games if g.winner_id == match.team_b_id)
 
    by_number = {g.game_number: g for g in games}
    max_games = _BEST_OF_MAX_GAMES.get(match.match_format, 1)
 
    match.games = games
    match.score_a = score_a
    match.score_b = score_b
    match.max_games = max_games
    match.game_rows = [
        by_number.get(n) or type('EmptyGame', (), {
            'game_number': n, 'score_a': '', 'score_b': '', 'map_name': '',
        })()
        for n in range(1, max_games + 1)
    ]
    match.is_live = match.status == GameStatus.ONGOING
    match.is_finished = match.status == GameStatus.FINISHED
    match.is_scheduled = match.status == GameStatus.SCHEDULED
    return match
 
 
@login_required
def manager_championship(request, championship_id):
    championship = get_object_or_404(
        Championship.objects.annotate(
            approved_count=Count(
                'registrations',
                filter=Q(registrations__status=StatusRegistration.APPROVED),
            ),
        ),
        pk=championship_id,
    )
 
    # Apenas staff do campeonato pode acessar
    is_staff_member = ChampionshipStaff.objects.filter(
        championship=championship,
        user=request.user,
    ).exists()
 
    if not is_staff_member:
        raise PermissionDenied("Você não faz parte da staff deste campeonato.")
 
    # ── POST: ações de gestão ───────────────────────────────────────────
    if request.method == 'POST':
        action = request.POST.get('action')
 
        # Aprovar / rejeitar inscrição
        if action in ('approve_registration', 'reject_registration'):
            reg = get_object_or_404(
                Registration,
                pk=request.POST.get('registration_id'),
                championship=championship,
            )
            new_status = (
                StatusRegistration.APPROVED if action == 'approve_registration'
                else StatusRegistration.REJECTED
            )
            try:
                reg.status = new_status
                reg.full_clean()
                reg.save()
                messages.success(request, f'Inscrição de "{reg.team}" atualizada.')
            except ValidationError as e:
                messages.error(request, " ".join(sum(e.message_dict.values(), [])))
 
        # Alterar status de uma partida (forçar início / encerrar)
        elif action == 'set_match_status':
            match = get_object_or_404(
                Match, pk=request.POST.get('match_id'), championship=championship,
            )
            new_status = request.POST.get('new_status')
            if new_status in GameStatus.values:
                match.status = new_status
                match.save(update_fields=['status'])
                messages.success(request, f"Status da partida #{match.pk} atualizado.")
 
        # Atualizar placar (games) de uma partida
        elif action == 'update_match_scores':
            match = get_object_or_404(
                Match, pk=request.POST.get('match_id'), championship=championship,
            )
 
            game_numbers = request.POST.getlist('game_number')
            scores_a = request.POST.getlist('score_a')
            scores_b = request.POST.getlist('score_b')
            maps = request.POST.getlist('map_name')
 
            # Recria os GameResults a partir do formulário
            GameResult.objects.filter(match_id=match).delete()
 
            wins_a, wins_b = 0, 0
            for num, sa, sb, map_name in zip(game_numbers, scores_a, scores_b, maps):
                sa, sb = int(sa or 0), int(sb or 0)
                if sa == sb:
                    continue  # ignora games empatados/incompletos
 
                winner = match.team_a if sa > sb else match.team_b
                if winner_id := getattr(winner, 'pk', None):
                    GameResult.objects.create(
                        match_id=match,
                        winner=winner,
                        game_number=int(num),
                        score_a=sa,
                        score_b=sb,
                        map_name=map_name,
                    )
                    if winner_id == match.team_a_id:
                        wins_a += 1
                    else:
                        wins_b += 1
 
            needed = _BEST_OF_WINS.get(match.match_format, 1)
            if wins_a >= needed or wins_b >= needed:
                match.winner = match.team_a if wins_a > wins_b else match.team_b
                match.status = GameStatus.FINISHED
            elif wins_a or wins_b:
                match.status = GameStatus.ONGOING
            match.save()
 
            messages.success(request, f"Placar da partida #{match.pk} atualizado.")
 
        return redirect('championship:management-championship-dashboard', championship_id=championship.pk)
 
    # ── GET: monta o dashboard ──────────────────────────────────────────
 
    pending_registrations = (
        Registration.objects
        .filter(championship=championship, status=StatusRegistration.PENDING)
        .select_related('team')
        .order_by('registered_at')[:10]
    )

    pending_registrations_count = Registration.objects.filter(
        championship=championship,
        status=StatusRegistration.PENDING
    ).count()
 
    matches_qs = (
        Match.objects
        .filter(championship=championship)
        .select_related('team_a', 'team_b', 'winner')
        .prefetch_related('gameresult_set')
    )
 
    live_matches = [_build_match_card(m) for m in matches_qs.filter(status=GameStatus.ONGOING)]
    upcoming_matches = [_build_match_card(m) for m in matches_qs.filter(status=GameStatus.SCHEDULED).order_by('scheduled_at')[:6]]
    finished_matches = [_build_match_card(m) for m in matches_qs.filter(status=GameStatus.FINISHED).order_by('-scheduled_at')[:6]]
 
    total_matches = matches_qs.count()
    finished_count = matches_qs.filter(status=GameStatus.FINISHED).count()
    live_count = len(live_matches)
    next_match = matches_qs.filter(status=GameStatus.SCHEDULED).order_by('scheduled_at').first()
 
    staff_members = (
        ChampionshipStaff.objects
        .filter(championship=championship)
        .select_related('user')
        .order_by('-role', 'added_at')
    )
 
    return render(request, 'championship/manager.html', {
        'championship': championship,
        'pending_registrations': pending_registrations,
        'pending_registrations_count': pending_registrations_count,
        'live_matches': live_matches,
        'upcoming_matches': upcoming_matches,
        'finished_matches': finished_matches,
        'total_matches': total_matches,
        'finished_count': finished_count,
        'live_count': live_count,
        'next_match': next_match,
        'staff_members': staff_members,
        'best_of_choices': MatchFormat.choices,
        'game_status_choices': GameStatus.choices,
    })
 

@login_required
def staff_management(request, championship_id):
    championship = get_object_or_404(Championship, pk=championship_id)
 
    # Membro de staff do usuário logado neste campeonato (None se não for staff)
    my_membership = ChampionshipStaff.objects.filter(
        championship=championship,
        user=request.user,
    ).first()
 
    is_owner = bool(my_membership and my_membership.role == RoleStaff.OWNER)
 
    # Apenas staff pode acessar a página
    if not my_membership:
        raise PermissionDenied("Você não faz parte da staff deste campeonato.")
 
    if request.method == 'POST':
        action = request.POST.get('action')
 
        # ── Adicionar membro ──────────────────────────────────────────
        if action == 'add_member':
            if not is_owner:
                raise PermissionDenied("Apenas o Dono pode adicionar membros.")
 
            username = request.POST.get('username', '').strip()
            target_user = (
                User.objects
                .filter(Q(username__iexact=username) | Q(email__iexact=username))
                .first()
            )
 
            if not target_user:
                messages.error(request, f'Usuário "{username}" não encontrado.')
            elif ChampionshipStaff.objects.filter(championship=championship, user=target_user).exists():
                messages.error(request, f'"{target_user.username}" já faz parte da staff.')
            else:
                ChampionshipStaff.objects.create(
                    championship=championship,
                    user=target_user,
                    role=RoleStaff.MODERATOR,
                )
                messages.success(request, f'"{target_user.username}" adicionado como Moderador.')
 
        # ── Remover membro ────────────────────────────────────────────
        elif action == 'remove_member':
            if not is_owner:
                raise PermissionDenied("Apenas o Dono pode remover membros.")
 
            target_id = request.POST.get('target_user_id')
            target_membership = ChampionshipStaff.objects.filter(
                championship=championship,
                user_id=target_id,
            ).first()
 
            if not target_membership:
                messages.error(request, "Membro não encontrado.")
            elif target_membership.role == RoleStaff.OWNER:
                messages.error(request, "O Dono não pode ser removido. Transfira a posse primeiro.")
            else:
                username = target_membership.user.username
                target_membership.delete()
                messages.success(request, f'"{username}" foi removido da staff.')
 
        # ── Transferir posse ──────────────────────────────────────────
        elif action == 'transfer_ownership':
            if not is_owner:
                raise PermissionDenied("Apenas o Dono pode transferir a posse.")
 
            target_id = request.POST.get('target_user_id')
            new_owner_membership = ChampionshipStaff.objects.filter(
                championship=championship,
                user_id=target_id,
            ).first()
 
            if not new_owner_membership or new_owner_membership.role != RoleStaff.MODERATOR:
                messages.error(request, "Só é possível transferir a posse para um Moderador da staff.")
            else:
                # Garante que apenas 1 owner exista por vez
                ChampionshipStaff.objects.filter(
                    championship=championship,
                    role=RoleStaff.OWNER,
                ).update(role=RoleStaff.MODERATOR)
 
                new_owner_membership.role = RoleStaff.OWNER
                new_owner_membership.save()
 
                messages.success(
                    request,
                    f'A posse foi transferida para "{new_owner_membership.user.username}".'
                )
 
        return redirect('championship:management-championship-staff', championship_id=championship.pk)
 
    # ── GET: lista de staff ────────────────────────────────────────────
    qs = (
        ChampionshipStaff.objects
        .filter(championship=championship)
        .select_related('user')
        .order_by('-role', 'added_at')  # OWNER ('O') vem antes de MODERATOR ('M') em ordem desc
    )
 
    paginator = Paginator(qs, per_page=10)
    page_obj = paginator.get_page(request.GET.get('page', 1))
 
    return render(request, 'championship/staff_management.html', {
        'championship': championship,
        'staff_members': page_obj,
        'page_obj': page_obj,
        'is_owner': is_owner,
    })


@login_required
def team_approval(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/team_approval.html', {
            'page_obj': page_obj,
        })