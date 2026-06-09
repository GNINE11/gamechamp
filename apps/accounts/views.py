from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from apps.championships.models import Championship, Registration, StatusChampionship
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from .forms import SignupForm, EditProfileForm

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

    error = None

    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password   = request.POST.get("password", "")

        # Aceita tanto username quanto e-mail
        user = authenticate(request, username=identifier, password=password)
        if user is None:
            # Tenta via e-mail
            try:
                u = User.objects.get(email=identifier)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                pass

        if user:
            login(request, user)
            next_url = request.GET.get("next", "championship:available-championship-list")
            return redirect(next_url)
        else:
            error = "Usuário ou senha incorretos."

    return render(request, "accounts/pages/login.html", {"error": error})


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
    """
    Exibe o perfil do usuário logado.
    Template espera: user (request.user), recent_matches
    """
    from apps.matches.models import Match, GameStatus, GameResult
    from apps.teams.models import Team

    user       = request.user
    user_teams = Team.objects.filter(members=user)
    championships = Championship.objects.filter(registrations__team__in=user_teams).distinct().order_by("status","-created_at")

    # Últimas 3 partidas encerradas dos times do usuário
    recent_matches_qs = Match.objects.filter(
        Q(team_a__in=user_teams) | Q(team_b__in=user_teams),
        status=GameStatus.FINISHED,
    ).select_related("team_a", "team_b", "winner", "championship").order_by("-scheduled_at")[:5]

    user_team_ids = set(user_teams.values_list("pk", flat=True))

    recent_matches = []
    for m in recent_matches_qs:
        sa = GameResult.objects.filter(match_id=m, winner=m.team_a).count()
        sb = GameResult.objects.filter(match_id=m, winner=m.team_b).count()
        user_won = m.winner_id in user_team_ids if m.winner_id else False

        # Determina o adversário (o time que NÃO é do usuário)
        if m.team_a_id in user_team_ids:
            opponent = m.team_b
        else:
            opponent = m.team_a

        recent_matches.append({
            "match"    : m,
            "score_a"  : sa,
            "score_b"  : sb,
            "user_won" : user_won,
            "opponent" : opponent,
        })

    return render(request, "accounts/pages/profile.html", {
        "recent_matches": recent_matches,
        "championships": championships,
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
            if form.cleaned_data.get("new_password"):
                update_session_auth_hash(request, user)
            return redirect("accounts:profile")
    else:
        form = EditProfileForm(user, initial={
            "full_name": user.get_full_name(),
            "username" : user.username,
            "email"    : user.email,
            "bio"      : getattr(user, "bio", ""),
        })

    return render(request, "accounts/pages/edit_profile.html", {"form": form})