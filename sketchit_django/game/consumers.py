"""WebSocket consumers for the game."""
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer

WORDS = [
    "cat", "dog", "house", "tree", "sun", "moon", "car", "fish",
    "bird", "flower", "star", "heart", "boat", "plane", "apple",
    "banana", "pizza", "guitar", "camera", "clock", "umbrella",
    "rainbow", "mountain", "beach", "robot", "rocket", "dragon",
    "castle", "butterfly", "snowman", "bicycle", "bridge", "diamond",
    "elephant", "fire", "ghost", "hat", "ice cream", "jungle",
    "key", "lamp", "mushroom", "ocean", "penguin", "queen",
    "snake", "tornado", "volcano", "waterfall", "zebra", "sword",
    "crown", "skull", "cactus", "donut", "egg", "frog", "grapes",
    "helicopter", "island", "jellyfish", "kite", "lion", "mermaid",
    "ninja", "octopus", "pirate", "rose", "spider", "treasure",
    "unicorn", "wizard", "angel", "bomb", "candle", "dice",
]


class GameConsumer(AsyncWebsocketConsumer):
    """Handle WebSocket connections for the game."""
    
    async def connect(self):
        """Handle new WebSocket connection."""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'game_{self.session_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'join':
                await self.handle_join(data)
            elif message_type == 'draw_line':
                await self.handle_draw_line(data)
            elif message_type == 'guess':
                await self.handle_guess(data)
            # Add more message type handlers as needed
            else:
                # Broadcast to room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_message',
                        'message': data
                    }
                )
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'error': 'Invalid JSON'}))
    
    async def handle_join(self, data):
        """Handle player join message."""
        message = {
            'type': 'player_joined',
            'player_id': data.get('player_id'),
            'name': data.get('name'),
            'character': data.get('character')
        }
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_message',
                'message': message
            }
        )
    
    async def handle_draw_line(self, data):
        """Handle draw line message."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_message',
                'message': data
            }
        )
    
    async def handle_guess(self, data):
        """Handle guess message."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_message',
                'message': data
            }
        )
    
    async def game_message(self, event):
        """Send game message to WebSocket."""
        await self.send(text_data=json.dumps(event['message']))
