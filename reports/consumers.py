"""WebSocket consumers for real-time report updates."""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .models import Report
from .serializers import ReportSerializer
import asyncio

logger = logging.getLogger(__name__)

class ReportConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for report updates."""
    
    HEARTBEAT_INTERVAL = 30  # seconds
    MAX_CONNECTIONS_PER_USER = 5
    RATE_LIMIT_MESSAGES = 60  # messages per minute
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Get report ID from URL route
            self.report_id = self.scope['url_route']['kwargs']['report_id']
            self.room_group_name = f'report_{self.report_id}'
            
            # Check authentication
            if not self.scope.get('user') or self.scope['user'].is_anonymous:
                raise PermissionDenied("Authentication required")
            
            # Check connection limit
            connection_key = f'ws_connections:{self.scope["user"].id}'
            connections = await self.get_connection_count(connection_key)
            if connections >= self.MAX_CONNECTIONS_PER_USER:
                raise PermissionDenied("Maximum connections exceeded")
            
            # Increment connection count
            await self.increment_connection_count(connection_key)
            
            # Check if report exists and user has permission
            if not await self.can_view_report():
                raise PermissionDenied("Permission denied")
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Send initial report data
            report_data = await self.get_report_data()
            await self.send(json.dumps({
                'type': 'report_data',
                'data': report_data
            }))
            
            # Start heartbeat
            self.heartbeat_task = asyncio.create_task(self.heartbeat())
            
        except (ObjectDoesNotExist, PermissionDenied) as e:
            logger.warning(f"WebSocket connection failed: {str(e)}")
            await self.close(code=4003)
        except Exception as e:
            logger.error(f"Unexpected error in WebSocket connection: {str(e)}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            # Cancel heartbeat
            if hasattr(self, 'heartbeat_task'):
                self.heartbeat_task.cancel()
            
            # Decrement connection count
            if hasattr(self.scope, 'user') and self.scope['user'].is_authenticated:
                connection_key = f'ws_connections:{self.scope["user"].id}'
                await self.decrement_connection_count(connection_key)
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        except Exception as e:
            logger.error(f"Error in WebSocket disconnection: {str(e)}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            # Check rate limit
            rate_key = f'ws_rate:{self.scope["user"].id}'
            if not await self.check_rate_limit(rate_key):
                await self.send(json.dumps({
                    'type': 'error',
                    'message': 'Rate limit exceeded'
                }))
                return
            
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'subscribe_updates':
                await self.send(json.dumps({
                    'type': 'subscription_success',
                    'message': 'Subscribed to report updates'
                }))
            elif message_type == 'heartbeat':
                await self.send(json.dumps({
                    'type': 'heartbeat',
                    'timestamp': timezone.now().isoformat()
                }))
            else:
                await self.send(json.dumps({
                    'type': 'error',
                    'message': 'Unsupported message type'
                }))
                
        except json.JSONDecodeError:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Invalid message format'
            }))
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
    
    async def heartbeat(self):
        """Send periodic heartbeat to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                await self.send(json.dumps({
                    'type': 'heartbeat',
                    'timestamp': timezone.now().isoformat()
                }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat error: {str(e)}")
            await self.close(code=4000)
    
    @database_sync_to_async
    def get_connection_count(self, key: str) -> int:
        """Get current connection count for user."""
        return cache.get(key, 0)
    
    @database_sync_to_async
    def increment_connection_count(self, key: str):
        """Increment connection count for user."""
        cache.set(key, cache.get(key, 0) + 1, timeout=3600)
    
    @database_sync_to_async
    def decrement_connection_count(self, key: str):
        """Decrement connection count for user."""
        count = cache.get(key, 1)
        if count > 0:
            cache.set(key, count - 1, timeout=3600)
    
    @database_sync_to_async
    def check_rate_limit(self, key: str) -> bool:
        """Check if user has exceeded rate limit."""
        count = cache.get(key, 0)
        if count >= self.RATE_LIMIT_MESSAGES:
            return False
        cache.set(key, count + 1, timeout=60)
        return True
    
    @database_sync_to_async
    def can_view_report(self):
        """Check if user can view the report."""
        try:
            report = Report.objects.get(id=self.report_id)
            user = self.scope['user']
            
            # Check user permissions based on roles
            if user.is_superuser or user.is_staff:
                return True
            
            if report.created_by == user:
                return True
                
            if user.role in ['STATE_OFFICIAL', 'LGA_OFFICIAL']:
                return True
                
            return False
            
        except Report.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_report_data(self):
        """Get serialized report data."""
        report = Report.objects.get(id=self.report_id)
        serializer = ReportSerializer(report)
        return serializer.data
    
    async def report_update(self, event):
        """Handle report update events."""
        try:
            # Send report update to WebSocket
            await self.send(json.dumps({
                'type': 'report_update',
                'data': event['data']
            }))
        except Exception as e:
            logger.error(f"Error sending report update: {str(e)}")
            await self.close(code=4000) 