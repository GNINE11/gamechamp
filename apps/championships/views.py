from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Case, When, Value, IntegerField, Count, Q
from .models import (
    Championship,
    ChampionshipStaff,
    StatusChampionship,
    StatusRegistration
)

def get_my_championships(user):
    return (
        Championship.objects
        .filter(
            registrations__status=StatusRegistration.APPROVED
        )
        .filter(
            Q(registrations__team__members=user) |
            Q(registrations__team__captain=user)
        )
        .distinct()
    )


def build_championship_qs(*, user=None, mode="public"):
    qs = Championship.objects.all()

    if mode == "public":
        qs = qs.exclude(status=StatusChampionship.DRAFT)
    elif mode == "my":
        qs = get_my_championships(user)
    elif mode == "created":
        qs = qs.filter(created_by=user)

    qs = qs.annotate(
        status_order=Case(
            When(status=StatusChampionship.DRAFT, then=Value(1)),
            When(status=StatusChampionship.OPEN, then=Value(2)),
            When(status=StatusChampionship.IN_PROGRESS, then=Value(3)),
            When(status=StatusChampionship.FINISHED, then=Value(4)),
            output_field=IntegerField(),
        ),
        approved_count=Count(
            'registrations',
            filter=Q(registrations__status='APPROVED'),
        ),
    ).order_by('status_order', 'start_date', '-created_at')

    return qs


@login_required
def list_available_championships(request):
    qs = build_championship_qs(mode="public")

    page_obj = Paginator(qs, 9).get_page(request.GET.get('page', 1))

    return render(request, 'championship/list.html', {
        'page_obj': page_obj,
    })

@login_required
def list_my_championships(request):
    qs = build_championship_qs(user=request.user, mode="my")

    page_obj = Paginator(qs, 9).get_page(request.GET.get('page', 1))

    return render(request, 'championship/list.html', {
        'page_obj': page_obj,
    })


@login_required
def list_created_championships(request):
    qs = build_championship_qs(user=request.user, mode="created")

    page_obj = Paginator(qs, 9).get_page(request.GET.get('page', 1))

    return render(request, 'championship/list.html', {
        'page_obj': page_obj,
    })


@login_required
def detail_championship(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/detail.html', {
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
def team_approval(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/team_approval.html', {
            'page_obj': page_obj,
        })