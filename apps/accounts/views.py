from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def login(request):
    return render(request, 'accounts/pages/login.html')

def signup(request):
    return render(request, 'accounts/pages/signup.html')

def profile(request):
    return render(request, 'accounts/pages/profile.html')

def edit_profile(request):
    return render(request, 'accounts/pages/edit_profile.html')

