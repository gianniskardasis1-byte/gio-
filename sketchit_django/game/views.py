"""Game views."""
from django.shortcuts import render


def index(request):
    """Serve the main game page."""
    return render(request, 'index.html')


def game(request):
    """Serve the game page."""
    return render(request, 'index.html')
