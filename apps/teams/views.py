from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MembershipRoleForm, TeamForm, TeamInviteForm
from .models import Invite, InviteStatus, Team, TeamMembership


def _team_queryset():
    return Team.objects.select_related("captain").prefetch_related("memberships__player")


def _captain_redirect(request, team):
    if team.captain_id != request.user.id:
        messages.error(request, "Apenas o capitão pode gerenciar esta equipe.")
        return redirect("teams:teams-detail", pk=team.pk)
    return None


def _first_form_error(form):
    for field_errors in form.errors.values():
        if field_errors:
            return field_errors[0]
    return "Confira os dados informados."


def _team_match_stats(team):
    from apps.matches.models import GameResult, GameStatus, Match

    finished_matches = Match.objects.filter(
        Q(team_a=team) | Q(team_b=team),
        status=GameStatus.FINISHED,
    ).select_related("team_a", "team_b", "winner", "championship").order_by("-scheduled_at", "-id")

    total_matches = finished_matches.count()
    total_wins = finished_matches.filter(winner=team).count()
    win_rate = round((total_wins / total_matches) * 100, 1) if total_matches else 0

    win_streak = 0
    for match in finished_matches:
        if match.winner_id == team.id:
            win_streak += 1
        else:
            break

    recent_matches = []
    for match in finished_matches[:5]:
        score_a = GameResult.objects.filter(match_id=match, winner=match.team_a).count()
        score_b = GameResult.objects.filter(match_id=match, winner=match.team_b).count()
        opponent = match.team_b if match.team_a_id == team.id else match.team_a
        recent_matches.append({
            "match": match,
            "opponent": opponent,
            "score_a": score_a,
            "score_b": score_b,
            "won": match.winner_id == team.id,
        })

    return {
        "total_matches": total_matches,
        "total_wins": total_wins,
        "win_rate": win_rate,
        "win_streak": win_streak,
        "recent_matches": recent_matches,
    }


@login_required
def teams_home(request):
    team = Team.objects.filter(members=request.user).order_by("name").first()
    if team:
        return redirect("teams:teams-detail", pk=team.pk)
    return redirect("teams:teams-create")


@login_required
def create_team(request):
    form = TeamForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        team = form.save(commit=False)
        team.captain = request.user
        team.save()
        messages.success(request, "Equipe criada com sucesso.")
        return redirect("teams:teams-detail", pk=team.pk)

    return render(request, "teams/pages/create.html", {"form": form})


@login_required
def team_detail(request, pk):
    team = get_object_or_404(_team_queryset(), pk=pk)
    memberships = list(team.memberships.select_related("player").order_by("joined_at"))
    stats = _team_match_stats(team)
    registrations = team.registrations.select_related("championship").order_by("-registered_at")[:4]

    return render(request, "teams/pages/detail.html", {
        "team": team,
        "memberships": memberships,
        "stats": stats,
        "registrations": registrations,
        "is_captain": team.captain_id == request.user.id,
    })


@login_required
def edit_team(request, pk):
    team = get_object_or_404(_team_queryset(), pk=pk)
    captain_response = _captain_redirect(request, team)
    if captain_response:
        return captain_response

    form = TeamForm(request.POST or None, request.FILES or None, instance=team)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Equipe atualizada com sucesso.")
        return redirect("teams:teams-detail", pk=team.pk)

    return render(request, "teams/pages/edit.html", {
        "team": team,
        "form": form,
    })


@login_required
def manage_members(request, pk):
    team = get_object_or_404(_team_queryset(), pk=pk)
    captain_response = _captain_redirect(request, team)
    if captain_response:
        return captain_response

    return render(request, "teams/pages/manage_members.html", {
        "team": team,
        "memberships": team.memberships.select_related("player").order_by("joined_at"),
        "pending_invites": team.invites.filter(status=InviteStatus.PENDING).select_related("invited_player"),
        "invite_form": TeamInviteForm(team),
        "role_form": MembershipRoleForm(),
    })


@login_required
def invitations(request):
    received_invites = Invite.objects.filter(
        invited_player=request.user,
    ).select_related("team", "team__captain").order_by("-created_at")

    sent_invites = Invite.objects.filter(
        team__captain=request.user,
    ).select_related("team", "invited_player").order_by("-created_at")

    return render(request, "teams/pages/invitations.html", {
        "received_invites": received_invites,
        "sent_invites": sent_invites,
        "received_pending_count": received_invites.filter(status=InviteStatus.PENDING).count(),
        "sent_pending_count": sent_invites.filter(status=InviteStatus.PENDING).count(),
        "pending_status": InviteStatus.PENDING,
    })


@login_required
@require_POST
def send_invite(request, pk):
    team = get_object_or_404(_team_queryset(), pk=pk)
    captain_response = _captain_redirect(request, team)
    if captain_response:
        return captain_response

    form = TeamInviteForm(team, request.POST)
    if form.is_valid():
        invite = form.save()
        messages.success(request, f"Convite enviado para {invite.invited_player.username}.")
    else:
        messages.error(request, _first_form_error(form))

    return redirect("teams:teams-members", pk=team.pk)


@login_required
@require_POST
def accept_invite(request, pk):
    invite = get_object_or_404(Invite.objects.select_related("team"), pk=pk, invited_player=request.user)
    try:
        invite.accept()
        messages.success(request, f"Você entrou na equipe {invite.team.name}.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))

    return redirect("teams:teams-invitations")


@login_required
@require_POST
def decline_invite(request, pk):
    invite = get_object_or_404(Invite, pk=pk, invited_player=request.user)
    try:
        invite.decline()
        messages.success(request, "Convite recusado.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))

    return redirect("teams:teams-invitations")


@login_required
@require_POST
def cancel_invite(request, pk):
    invite = get_object_or_404(Invite.objects.select_related("team"), pk=pk, team__captain=request.user)
    try:
        invite.cancel()
        messages.success(request, "Convite cancelado.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))

    return redirect(request.POST.get("next") or "teams:teams-invitations")


@login_required
@require_POST
def remove_member(request, pk, membership_pk):
    team = get_object_or_404(_team_queryset(), pk=pk)
    captain_response = _captain_redirect(request, team)
    if captain_response:
        return captain_response

    membership = get_object_or_404(TeamMembership.objects.select_related("player"), pk=membership_pk, team=team)
    try:
        team.remove_member(membership.player)
        messages.success(request, f"{membership.player.username} foi removido da equipe.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))

    return redirect("teams:teams-members", pk=team.pk)


@login_required
@require_POST
def promote_member(request, pk, membership_pk):
    team = get_object_or_404(_team_queryset(), pk=pk)
    captain_response = _captain_redirect(request, team)
    if captain_response:
        return captain_response

    membership = get_object_or_404(TeamMembership.objects.select_related("player"), pk=membership_pk, team=team)
    try:
        team.transfer_captaincy(membership.player)
        messages.success(request, f"{membership.player.username} agora é capitão da equipe.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("teams:teams-members", pk=team.pk)

    return redirect("teams:teams-detail", pk=team.pk)


@login_required
@require_POST
def update_member_role(request, pk, membership_pk):
    team = get_object_or_404(_team_queryset(), pk=pk)
    captain_response = _captain_redirect(request, team)
    if captain_response:
        return captain_response

    membership = get_object_or_404(TeamMembership, pk=membership_pk, team=team)
    form = MembershipRoleForm(request.POST)
    if form.is_valid():
        membership.role = form.cleaned_data["role"].strip() or "Jogador"
        membership.save(update_fields=["role"])
        messages.success(request, "Função atualizada.")
    else:
        messages.error(request, _first_form_error(form))

    return redirect("teams:teams-members", pk=team.pk)


@login_required
@require_POST
def delete_team(request, pk):
    team = get_object_or_404(_team_queryset(), pk=pk)
    captain_response = _captain_redirect(request, team)
    if captain_response:
        return captain_response

    team_name = team.name
    team.delete()
    messages.success(request, f"A equipe {team_name} foi excluída.")
    return redirect("teams:teams-home")
