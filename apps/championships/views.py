from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.shortcuts import render
from .models import (
    Championship,
    ChampionshipStaff,
)

# Create your views here.
def list_championship(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/list.html', {
            'page_obj': page_obj,
        })

def detail_championship(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/detail.html', {
            'page_obj': page_obj,
        })

def manager_championship(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/manager.html', {
            'page_obj': page_obj,
        })

def team_approval(request):
    qs = Championship.objects.all()
    paginator = Paginator(qs, per_page=10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'championship/team_approval.html', {
            'page_obj': page_obj,
        })