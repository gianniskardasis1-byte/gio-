"""Game models."""
from django.db import models


class GameSession(models.Model):
    """Store game session information."""
    session_id = models.CharField(max_length=100, unique=True)
    host = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Game {self.session_id}"


class Player(models.Model):
    """Store player information."""
    player_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    character = models.CharField(max_length=50)
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.character})"
