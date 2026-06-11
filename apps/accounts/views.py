from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from apps.championships.models import Championship, Registration, StatusChampionship
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum

from .forms import SignupForm, EditProfileForm, LoginForm

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# SIGNUP
# ─────────────────────────────────────────────────────────────────────────────

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("championship:available-championship-list")

    form = SignupForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Cadastro realizado com sucesso {user.username}! Faça login para continuar.")
        return redirect("accounts:login")

    return render(request, "accounts/pages/signup.html", {"form": form})


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("championship:available-championship-list")

    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():

        identifier = form.cleaned_data["username"].strip()
        password = form.cleaned_data["password"]

        user = authenticate(
            request,
            username=identifier,
            password=password
        )

        if user is None:
            try:
                u = User.objects.get(email=identifier)

                user = authenticate(
                    request,
                    username=u.username,
                    password=password
                )

            except User.DoesNotExist:
                pass

        if user:
            login(request, user)

            next_url = request.GET.get(
                "next",
                "championship:available-championship-list"
            )

            return redirect(next_url)

        form.add_error(
            None,
            "Usuário ou senha incorretos."
        )

    return render(request,"accounts/pages/login.html",{"form": form})


# ─────────────────────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    from apps.matches.models import Match, GameStatus, GameResult, GroupStanding
    from apps.teams.models import Team
 
    user       = request.user
    user_teams = Team.objects.filter(members=user)
    user_team_ids = set(user_teams.values_list("pk", flat=True))
 
    # ── Campeonatos do usuário ────────────────────────────────────────────
    championships = (
        Championship.objects
        .filter(registrations__team__in=user_teams)
        .distinct()
        .order_by("status", "-created_at")
    )
 
    # ── Últimas 5 partidas encerradas ─────────────────────────────────────
    recent_matches_qs = Match.objects.filter(
        Q(team_a__in=user_teams) | Q(team_b__in=user_teams),
        status=GameStatus.FINISHED,
    ).select_related("team_a", "team_b", "winner", "championship").order_by("-scheduled_at")[:5]
 
    recent_matches = []
    for m in recent_matches_qs:
        sa = GameResult.objects.filter(match_id=m, winner=m.team_a).count()
        sb = GameResult.objects.filter(match_id=m, winner=m.team_b).count()
        user_won = m.winner_id in user_team_ids if m.winner_id else False
        opponent = m.team_b if m.team_a_id in user_team_ids else m.team_a
 
        recent_matches.append({
            "match"    : m,
            "score_a"  : sa,
            "score_b"  : sb,
            "user_won" : user_won,
            "opponent" : opponent,
        })
 
    # ── Estatísticas / Troféus ────────────────────────────────────────────
 
    # 1. Campeonatos vencidos (usuário estava em um time campeão)
    championships_won = Championship.objects.filter(
        champion__members=user,
        champion__isnull=False,
    ).distinct().count()
 
    # 2. Total de partidas disputadas
    total_matches = Match.objects.filter(
        Q(team_a__in=user_teams) | Q(team_b__in=user_teams),
        team_a__isnull=False,
        team_b__isnull=False,
    ).distinct().count()
 
    # 3. Total de vitórias
    total_wins = Match.objects.filter(
        winner__members=user,
        winner__isnull=False,
    ).count()
 
    # 4. Total de rounds vencidos via GroupStanding
    total_rounds_won = (
        GroupStanding.objects.filter(team__members=user)
        .aggregate(total=Sum("rounds_won"))["total"] or 0
    )
 
    stats = {
        "championships_won": championships_won,
        "total_matches"    : total_matches,
        "total_wins"       : total_wins,
        "total_rounds_won" : total_rounds_won,
    }
 
    return render(request, "accounts/pages/profile.html", {
        "recent_matches": recent_matches,
        "championships" : championships,
        "stats"         : stats,
    })
 

# ─────────────────────────────────────────────────────────────────────────────
# EDIT PROFILE
# ─────────────────────────────────────────────────────────────────────────────
 
@login_required
def edit_profile_view(request):
    user = request.user
 
    if request.method == "POST":
        form = EditProfileForm(
            user,
            request.POST,
            request.FILES,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado com sucesso!")
            # Se trocou a senha, faz login novamente para não deslogar
            from django.contrib.auth import update_session_auth_hash
            if form.cleaned_data.get("password"):
                update_session_auth_hash(request, user)
            return redirect("accounts:profile")
    else:
        form = EditProfileForm(user, initial={
            "first_name": user.first_name,
            "last_name" : user.last_name,
            "username"  : user.username,
            "email"     : user.email,
            "bio"       : getattr(user, "bio", ""),
        })
 
    return render(request, "accounts/pages/edit_profile.html", {"form": form})