from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages                      # NOVO
from django.core.exceptions import PermissionDenied       # NOVO
from django.db.models import Case, When, Value, IntegerField, Count, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from .models import (
    Championship,
    ChampionshipStaff,
    StatusChampionship,
    StatusRegistration,
    Registration,
    Team,
    RoleStaff,
    User
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
            'css': 'btn-card-results', 'url': reverse('championship:management-championship-dashboard'),
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

@login_required
def manager_championship(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/manager.html', {
            'page_obj': page_obj,
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