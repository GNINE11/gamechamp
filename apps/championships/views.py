from collections import defaultdict
from urllib.parse import urlencode

from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from apps.matches.progression import on_match_finished
from django.contrib import messages                      # NOVO
from django.core.exceptions import PermissionDenied, ValidationError       # NOVO
from django.db.models import Case, When, Value, IntegerField, Count, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_POST
from apps.matches.bracket import get_structure_context
from apps.matches.models import Match, GameResult, GameStatus 
from .forms import ChampionshipForm
from .models import (
    Championship,
    ChampionshipStaff,
    StatusChampionship,
    StatusRegistration,
    Registration,
    Team,
    RoleStaff,
    StageFormat,
    User,
    MatchFormat,
)
from .services import ensure_championship_structure


_FILTER_STATUS_LABELS = {
    StatusChampionship.DRAFT: 'Rascunho',
    StatusChampionship.OPEN: 'Abertos',
    StatusChampionship.IN_PROGRESS: 'Ao Vivo',
    StatusChampionship.FINISHED: 'Finalizados',
}


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
 
def _compute_cta(champ, mode, user_context=None):
    """
    Retorna um dict descrevendo o botão de ação do card, ou None se não houver ação.
    Toda a lógica fica aqui — o template só renderiza o que recebe.
    """
    s = champ.status
    user_context = user_context or {}
    registrations = user_context.get('registrations', [])
    captained_teams = user_context.get('captained_teams', [])
    active_registrations = [
        registration for registration in registrations
        if registration.status in (StatusRegistration.PENDING, StatusRegistration.APPROVED)
    ]
    registered_team_ids = {registration.team_id for registration in registrations}
    available_teams = [team for team in captained_teams if team.pk not in registered_team_ids]
 
    if mode == 'management':
        return {
            'label': 'Gerenciar', 'icon': 'settings',
            'css': 'btn-card-results',
            'url': reverse('championship:management-championship-dashboard', args=[champ.pk]),
            'is_form': False, 'disabled': False,
        }

         
 
    if mode == 'my':
        if s == StatusChampionship.OPEN and active_registrations:
            return {
                'label': 'Cancelar Inscrição', 'icon': 'cancel',
                'css': 'btn-card-waitlist',
                'url': reverse('championship:championship-cancel-registration', args=[champ.pk]),
                'is_form': True,
                'disabled': False,
                'team_options': [registration.team for registration in active_registrations],
                'team_id': active_registrations[0].team_id,
            }
        if s == StatusChampionship.IN_PROGRESS:
            return {
                'label': 'Ver Chaveamento', 'icon': 'chevron_right',
                'css': 'btn-card-live', 'url': reverse('championship:championship-structure', args=[champ.pk]),
                'is_form': False, 'disabled': False,
            }
        if s == StatusChampionship.FINISHED:
            return {
                'label': 'Ver Resultados', 'icon': 'history',
                'css': 'btn-card-results', 'url': reverse('championship:championship-structure', args=[champ.pk]),
                'is_form': False, 'disabled': False,
            }
        return None
 
    # mode == 'public'
    if s == StatusChampionship.IN_PROGRESS:
        return {
            'label': 'Ver Chaveamento ao Vivo', 'icon': 'chevron_right',
            'css': 'btn-card-live', 'url': reverse('championship:championship-structure', args=[champ.pk]),
            'is_form': False, 'disabled': False,
        }
    if s == StatusChampionship.FINISHED:
        return {
            'label': 'Ver Resultados', 'icon': 'history',
            'css': 'btn-card-results', 'url': reverse('championship:championship-structure', args=[champ.pk]),
            'is_form': False, 'disabled': False,
        }
    if s == StatusChampionship.OPEN:
        if active_registrations:
            return {
                'label': 'Cancelar Inscrição', 'icon': 'cancel',
                'css': 'btn-card-waitlist',
                'url': reverse('championship:championship-cancel-registration', args=[champ.pk]),
                'is_form': True,
                'disabled': False,
                'team_options': [registration.team for registration in active_registrations],
                'team_id': active_registrations[0].team_id,
            }
        if not captained_teams:
            return {
                'label': 'Crie uma Equipe', 'icon': 'groups',
                'css': 'btn-card-waitlist', 'url': None,
                'is_form': False, 'disabled': True,
            }
        if not available_teams:
            return {
                'label': 'Inscrição indisponível', 'icon': 'block',
                'css': 'btn-card-waitlist', 'url': None,
                'is_form': False, 'disabled': True,
            }
        is_waitlist = champ.approved_count >= champ.max_teams
        return {
            'label': 'Entrar na Lista' if is_waitlist else 'Inscrever Time',
            'icon': 'hourglass_empty' if is_waitlist else 'add_circle',
            'css': 'btn-card-register',
            'url': reverse('championship:championship-register', args=[champ.pk]),
            'is_form': True,
            'disabled': False,
            'team_options': available_teams,
            'team_id': available_teams[0].pk,
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
 
 
def _base_championship_qs(*, user=None, mode='public'):
    qs = Championship.objects.all()

    if mode == 'public':
        qs = qs.exclude(status=StatusChampionship.DRAFT)

    elif mode == 'my':
        qs = get_my_championships(user).exclude(status=StatusChampionship.DRAFT)

    elif mode == 'management':
        qs = qs.filter(staff_members__user=user).distinct()

    return qs


def _clean_championship_filters(params, *, mode, game_options):
    filters = {
        'q': params.get('q', '').strip(),
        'game': params.get('game', '').strip(),
        'status': params.get('status', '').strip(),
        'stage_format': params.get('stage_format', '').strip(),
    }

    if filters['game'] not in game_options:
        filters['game'] = ''

    valid_statuses = set(StatusChampionship.values)
    if mode != 'management':
        valid_statuses.discard(StatusChampionship.DRAFT)
    if filters['status'] not in valid_statuses:
        filters['status'] = ''

    if filters['stage_format'] not in set(StageFormat.values):
        filters['stage_format'] = ''

    return filters


def _filter_context(request, *, user=None, mode='public'):
    base_qs = _base_championship_qs(user=user, mode=mode)
    game_options = list(
        base_qs
        .exclude(game='')
        .order_by('game')
        .values_list('game', flat=True)
        .distinct()
    )
    filters = _clean_championship_filters(request.GET, mode=mode, game_options=game_options)
    active_filters = {key: value for key, value in filters.items() if value}

    status_values = [
        StatusChampionship.OPEN,
        StatusChampionship.IN_PROGRESS,
        StatusChampionship.FINISHED,
    ]
    if mode == 'management':
        status_values.insert(0, StatusChampionship.DRAFT)

    return {
        'filters': filters,
        'filter_query': urlencode(active_filters),
        'game_options': game_options,
        'status_options': [
            {'value': value, 'label': _FILTER_STATUS_LABELS[value]}
            for value in status_values
        ],
        'stage_format_options': [
            {'value': value, 'label': label}
            for value, label in StageFormat.choices
        ],
    }


def build_championship_qs(*, user=None, mode='public', filters=None):
    qs = _base_championship_qs(user=user, mode=mode)
    filters = filters or {}

    if filters.get('q'):
        qs = qs.filter(Q(name__icontains=filters['q']) | Q(game__icontains=filters['q']))

    if filters.get('game'):
        qs = qs.filter(game=filters['game'])

    if filters.get('status'):
        qs = qs.filter(status=filters['status'])

    if filters.get('stage_format'):
        qs = qs.filter(stage_format=filters['stage_format'])

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
 
 
def _get_user_registration_context(championships, user):
    ids = [c.pk for c in championships]
    captained_teams = list(Team.objects.filter(captain=user).order_by('name'))
    registrations_by_championship = defaultdict(list)
    registrations = (
        Registration.objects
        .filter(
            championship_id__in=ids,
            team__in=captained_teams,
        )
        .select_related('team')
        .order_by('registered_at', 'pk')
    )
    for registration in registrations:
        registrations_by_championship[registration.championship_id].append(registration)
    return captained_teams, registrations_by_championship
 
 
def _attach_card_data(page_obj, mode, user=None):
    """Adiciona ph_class e cta em cada championship do page_obj."""
    captained_teams, registrations_by_championship = (
        _get_user_registration_context(page_obj.object_list, user) if user else ([], {})
    )
    for champ in page_obj.object_list:
        champ.ph_class = _PH_CLASS.get(champ.status, 'card-ph-finished')
        champ.cta = _compute_cta(champ, mode, {
            'captained_teams': captained_teams,
            'registrations': registrations_by_championship.get(champ.pk, []),
        })
 
 
# ── Views ─────────────────────────────────────────────────────────────────────
 
@login_required
def list_available_championships(request):
    mode = 'public'
    filter_context = _filter_context(request, mode=mode)
    page_obj = Paginator(build_championship_qs(mode=mode, filters=filter_context['filters']), 9).get_page(request.GET.get('page', 1))
    _attach_card_data(page_obj, mode, user=request.user)
    return render(request, 'championship/list.html', {'page_obj': page_obj, 'mode': mode, **filter_context, **_MODE_CONFIG[mode]})
 
 
@login_required
def list_my_championships(request):
    mode = 'my'
    filter_context = _filter_context(request, user=request.user, mode=mode)
    page_obj = Paginator(build_championship_qs(user=request.user, mode=mode, filters=filter_context['filters']), 9).get_page(request.GET.get('page', 1))
    _attach_card_data(page_obj, mode, user=request.user)
    return render(request, 'championship/list.html', {'page_obj': page_obj, 'mode': mode, **filter_context, **_MODE_CONFIG[mode]})
 
 
@login_required
def list_management_championships(request):
    mode = 'management'
    filter_context = _filter_context(request, user=request.user, mode=mode)
    page_obj = Paginator(build_championship_qs(user=request.user, mode=mode, filters=filter_context['filters']), 9).get_page(request.GET.get('page', 1))
    _attach_card_data(page_obj, mode, user=request.user)
    return render(request, 'championship/list.html', {'page_obj': page_obj, 'mode': mode, **filter_context, **_MODE_CONFIG[mode]})
 

@login_required
def create_championship(request):
    if request.method == 'POST':
        form = ChampionshipForm(request.POST, is_create=True)
        if form.is_valid():
            championship = form.save(commit=False)
            championship.created_by = request.user
            championship.status = StatusChampionship.DRAFT
            championship.full_clean()
            championship.save()
            ChampionshipStaff.objects.create(
                championship=championship,
                user=request.user,
                role=RoleStaff.OWNER,
            )
            messages.success(request, "Campeonato criado como rascunho.")
            return redirect('championship:management-championship-dashboard', championship_id=championship.pk)
    else:
        form = ChampionshipForm(is_create=True, initial={
            'stage_format': StageFormat.SINGLE_ELIMINATION,
            'max_teams': 8,
            'playoff_format': 'SINGLE_ELIMINATION',
            'playoff_match_format': MatchFormat.BO1,
            'final_match_format': MatchFormat.BO3,
        })

    return render(request, 'championship/form.html', {
        'form': form,
        'form_mode': 'create',
        'page_label': 'Gestão',
        'page_title': 'Cadastrar Campeonato',
    })


def _require_owner(championship, user):
    is_owner = ChampionshipStaff.objects.filter(
        championship=championship,
        user=user,
        role=RoleStaff.OWNER,
    ).exists()
    if not is_owner:
        raise PermissionDenied("Apenas o dono pode editar este campeonato.")


@login_required
def edit_championship(request, championship_id):
    championship = get_object_or_404(Championship, pk=championship_id)
    _require_owner(championship, request.user)
    old_status = championship.status

    if request.method == 'POST':
        form = ChampionshipForm(request.POST, instance=championship)
        if form.is_valid():
            championship = form.save()
            if championship.status in (StatusChampionship.IN_PROGRESS, StatusChampionship.FINISHED):
                result = ensure_championship_structure(championship)
                if old_status != championship.status or result['created']:
                    messages.success(
                        request,
                        f"Campeonato atualizado. Estrutura pronta com {result['created']} partida(s) nova(s).",
                    )
                else:
                    messages.success(request, "Campeonato atualizado.")
            else:
                messages.success(request, "Campeonato atualizado.")
            return redirect('championship:management-championship-dashboard', championship_id=championship.pk)
    else:
        form = ChampionshipForm(instance=championship)

    return render(request, 'championship/form.html', {
        'form': form,
        'form_mode': 'edit',
        'championship': championship,
        'page_label': 'Gestão',
        'page_title': f'Editar {championship.name}',
    })


@login_required
def structure_championship(request, championship_id):
    championship = get_object_or_404(Championship, pk=championship_id)
    if championship.status not in (StatusChampionship.IN_PROGRESS, StatusChampionship.FINISHED):
        raise PermissionDenied("O chaveamento so pode ser visualizado com o campeonato em andamento ou finalizado.")

    context = get_structure_context(championship)
    context.update({
        'page_label': championship.game,
        'page_title': championship.name,
    })
    return render(request, 'championship/structure.html', context)


def _redirect_back(request):
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'championship:available-championship-list')


@login_required
@require_POST
def register_championship(request, championship_id):
    championship = get_object_or_404(Championship, pk=championship_id)
    if championship.status != StatusChampionship.OPEN:
        messages.error(request, "Este campeonato nao esta com inscricoes abertas.")
        return _redirect_back(request)

    captained_teams = Team.objects.filter(captain=request.user).order_by('name')
    team_id = request.POST.get('team_id')
    if team_id:
        team = captained_teams.filter(pk=team_id).first()
    elif captained_teams.count() == 1:
        team = captained_teams.first()
    else:
        team = None

    if not team:
        messages.error(request, "Escolha uma equipe que voce lidera para se inscrever.")
        return _redirect_back(request)

    registration = Registration(championship=championship, team=team, status=StatusRegistration.PENDING)
    try:
        registration.full_clean()
        registration.save()
        messages.success(request, f"{team.name} foi inscrita e aguarda aprovacao.")
    except ValidationError as exc:
        if hasattr(exc, 'message_dict'):
            error_messages = sum(exc.message_dict.values(), [])
        else:
            error_messages = exc.messages
        messages.error(request, " ".join(error_messages))

    return _redirect_back(request)


@login_required
@require_POST
def cancel_registration(request, championship_id):
    championship = get_object_or_404(Championship, pk=championship_id)
    if championship.status != StatusChampionship.OPEN:
        messages.error(request, "Inscricoes so podem ser canceladas enquanto o campeonato esta aberto.")
        return _redirect_back(request)

    registrations = Registration.objects.filter(
        championship=championship,
        team__captain=request.user,
        status__in=(StatusRegistration.PENDING, StatusRegistration.APPROVED),
    ).select_related('team')

    team_id = request.POST.get('team_id')
    if team_id:
        registrations = registrations.filter(team_id=team_id)

    registration = registrations.first()
    if not registration:
        messages.error(request, "Nenhuma inscricao cancelavel foi encontrada.")
        return _redirect_back(request)

    team_name = registration.team.name
    registration.delete()
    messages.success(request, f"Inscricao de {team_name} cancelada.")
    return _redirect_back(request)

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
    staff_membership = ChampionshipStaff.objects.filter(
        championship=championship,
        user=request.user,
    ).first()
 
    if not staff_membership:
        raise PermissionDenied("Você não faz parte da staff deste campeonato.")
    is_owner = staff_membership.role == RoleStaff.OWNER
 
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

        # Reabrir uma partida encerrada (volta para ONGOING e limpa o vencedor)
        elif action == 'reopen_match':
            match = get_object_or_404(
                Match, pk=request.POST.get('match_id'), championship=championship,
            )
            match.status = GameStatus.ONGOING
            match.winner = None
            match.save(update_fields=['status', 'winner'])
            messages.success(request, f"Partida #{match.pk} reaberta. Edite o placar normalmente.")
 
        # Atualizar placar (games) de uma partida
        elif action == 'update_match_scores':
            match = get_object_or_404(
                Match, pk=request.POST.get('match_id'), championship=championship,
            )
 
            game_numbers = request.POST.getlist('game_number')
            scores_a     = request.POST.getlist('score_a')
            scores_b     = request.POST.getlist('score_b')
            maps         = request.POST.getlist('map_name')
 
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
                match.save()
                on_match_finished(match)   # ← LINHA NOVA
            elif wins_a or wins_b:
                match.status = GameStatus.ONGOING
                match.save()
            else:
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
    upcoming_matches = [_build_match_card(m) for m in matches_qs.filter(status=GameStatus.SCHEDULED).order_by('scheduled_at')]
    finished_matches = [_build_match_card(m) for m in matches_qs.filter(status=GameStatus.FINISHED).order_by('-scheduled_at')]
 
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
        'is_owner': is_owner,
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
