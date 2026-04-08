"""Django admin configuration for game app."""
from django.contrib import admin
from game.models import GameSession, Player


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'host', 'created_at')
    search_fields = ('session_id', 'host')


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'player_id', 'character', 'score', 'joined_at')
    search_fields = ('name', 'player_id')
    list_filter = ('character', 'joined_at')
