# Django project configuration

This Django project is configured for the Sketchit multiplayer game with WebSocket support via Django Channels.

## Quick Start Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server with WebSocket support
daphne -b 0.0.0.0 -p 8000 sketchit.asgi:application

# Access at http://localhost:8000
```

## Key Components

- **Channels**: Enables WebSocket connections for real-time game updates
- **Daphne**: ASGI server that supports both HTTP and WebSocket protocols
- **Django ORM**: For storing game sessions and player data

## Architecture

The game uses a WebSocket-based architecture where:
1. Players connect to the game server
2. All drawing actions broadcast to other players in real-time
3. Chat/guess messages synchronized across all clients
4. Game state managed centrally on the server

## Configuration Files

- `settings.py`: Django settings with Channels configured
- `asgi.py`: ASGI application with WebSocket routing
- `routing.py`: WebSocket URL patterns and consumer mapping
- `consumers.py`: WebSocket handlers for game logic
