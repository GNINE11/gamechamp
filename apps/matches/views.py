from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def list_matches_history(request):
    return render(request, 'matches/pages/match_history.html')


def register_match_result(request):
    return render(request, 'matches/pages/record_result.html')


def match_details(request):
    return render(request, 'matches/pages/match_details.html')
