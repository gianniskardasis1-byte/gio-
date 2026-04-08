"""
URL configuration for sketchit project.
"""
from django.urls import path
from game import views

urlpatterns = [
    path('', views.index, name='index'),
    path('game/', views.game, name='game'),
]
