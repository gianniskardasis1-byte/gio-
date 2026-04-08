# Sketchit Django

A multiplayer drawing and guessing game made with Django + WebSockets, served through Channels.

## Setup

1. **Navigate to the project directory:**
   ```bash
   cd sketchit_django
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Daphne ASGI server:**
   ```bash
   pip install daphne
   ```

4. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser (optional, for admin):**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

   Or use Daphne for proper WebSocket support:
   ```bash
   daphne -b 0.0.0.0 -p 8000 sketchit.asgi:application
   ```

7. **Access the game:**
   - Open your browser to `http://localhost:8000`
   - Share the server URL with your classmates to join!

## How to Play

- **Host Game:** Create a game session that others can join
- **Join Game:** Connect to an existing game session using the server IP
- **Quick Play:** Start a single-player test game instantly

## Features

- Draw and guess multiplayer gameplay
- Real-time drawing synchronization via WebSockets
- Character customization
- Score tracking and leaderboard
- Round-based gameplay with timed rounds

## Project Structure

```
sketchit_django/
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── sketchit/             # Main Django project
│   ├── settings.py       # Django settings
│   ├── asgi.py          # ASGI config for WebSockets
│   ├── urls.py          # URL routing
│   └── wsgi.py          # WSGI config
└── game/                # Game app
    ├── models.py        # Database models
    ├── views.py         # Views
    ├── consumers.py     # WebSocket consumers
    ├── routing.py       # WebSocket routing
    ├── admin.py         # Admin interface
    ├── templates/       # HTML templates
    │   └── index.html   # Main game UI
    └── static/          # Static files
        └── ui.js        # Game client logic
```

## Deploying to Production

For production deployment, consider using:
- Gunicorn with Daphne for ASGI
- PostgreSQL database
- Redis for channel layers
- Proper ALLOWED_HOSTS configuration
- HTTPS/SSL certificates
- Environment variables for secrets

See Django documentation for more deployment options.
