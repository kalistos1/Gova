from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.authentication import JWTAuthentication
import requests
import logging
from typing import Dict, Any, Optional
from rest_framework import serializers

from .models import Message, Notification, RecipientGroup
from .serializers import (
    MessageSerializer, MessageCreateSerializer,
    MessageResponseSerializer, NotificationSerializer,
    RecipientGroupSerializer
)
from .permissions import IsStateOfficial
from core.models import AuditLog

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for message listings."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

def transcribe_voice(voice_data: bytes, language: str = 'en') -> str:
    """Transcribe voice data to text using OpenRouter API.
    
    Args:
        voice_data: Raw voice data bytes.
        language: Language code (en, ig, pidgin).
        
    Returns:
        Transcribed text.
        
    Raises:
        requests.RequestException: If transcription fails.
    """
    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/transcribe',
            files={'audio': voice_data},
            data={'language': language},
            headers={
                'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                'Content-Type': 'multipart/form-data',
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()['text']
    except requests.RequestException as e:
        logger.error(f'Voice transcription failed: {str(e)}')
        raise

@api_view(['POST'])
@permission_classes([AllowAny])
def message_create(request):
    """Create a new message (anonymous or authenticated).
    
    Supports both text messages and voice recordings. For voice recordings,
    the audio file will be transcribed using OpenRouter AI.
    
    Args:
        request: HTTP request object containing:
            - query: Text message (optional if voiceData provided)
            - voiceData: Voice recording file (optional)
            - language: Language code for transcription (en, ig, pidgin)
            - location: Location ID (optional)
            - landmark: Landmark ID (optional)
            
    Returns:
        Created message data in camelCase format:
            {
                'messageId': str,
                'query': str,
                'contentType': str,  # 'text' or 'voice'
                'transcriptionConfidence': float,  # 0.0 to 1.0
                'location': str,
                'landmark': str,
                'isAnonymous': bool,
                'createdAt': str,
                ...
            }
            
    Raises:
        400: If neither query nor voiceData provided,
             or if neither location nor landmark provided,
             or if transcription fails.
        503: If transcription service unavailable.
    """
    serializer = MessageCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create message
        message = serializer.save(
            user=request.user if request.user.is_authenticated else None,
            is_anonymous=not request.user.is_authenticated
        )
        
        # Log action
        AuditLog.objects.create(
            action='MESSAGE_CREATED',
            user=request.user if request.user.is_authenticated else None,
            details={
                'message_id': str(message.id),
                'content_type': message.content_type,
                'is_anonymous': message.is_anonymous,
                'has_voice': bool(request.FILES.get('voiceData')),
                'language': request.data.get('language', 'en')
            }
        )
        
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
        
    except serializers.ValidationError as e:
        # Handle validation errors (including transcription errors)
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        # Log unexpected errors
        logger.error(f'Message creation failed: {str(e)}')
        AuditLog.objects.create(
            action='MESSAGE_CREATION_FAILED',
            user=request.user if request.user.is_authenticated else None,
            details={
                'error': str(e),
                'has_voice': bool(request.FILES.get('voiceData')),
                'language': request.data.get('language', 'en')
            }
        )
        return Response(
            {'error': 'An unexpected error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def message_list(request):
    """List messages for the authenticated user.
    
    Args:
        request: HTTP request object containing query parameters:
            - parent: Filter by parent message ID
            - is_read: Filter by read status
            
    Returns:
        Paginated list of messages in camelCase format.
    """
    queryset = Message.objects.select_related(
        'user', 'parent'
    ).prefetch_related(
        'replies'
    ).filter(
        Q(user=request.user) | Q(parent__user=request.user)
    )
    
    # Apply filters
    parent_id = request.query_params.get('parent')
    if parent_id:
        queryset = queryset.filter(parent_id=parent_id)
        
    is_read = request.query_params.get('is_read')
    if is_read is not None:
        queryset = queryset.filter(is_read=is_read.lower() == 'true')
    
    # Apply pagination
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    serializer = MessageSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStateOfficial])
def message_response(request, pk):
    """Send a response to a message (state officials only).
    
    Args:
        request: HTTP request object containing response data.
        pk: UUID of the parent message.
            
    Returns:
        Created response message in camelCase format.
        
    Raises:
        404: If parent message not found.
        403: If user lacks permission.
        400: If response data invalid.
    """
    parent = get_object_or_404(
        Message.objects.select_related('user'),
        pk=pk
    )
    
    serializer = MessageResponseSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # Create response
    response = serializer.save(
        user=request.user,
        parent=parent
    )
    
    # Mark parent as read
    parent.is_read = True
    parent.save(update_fields=['is_read'])
    
    # Log action
    AuditLog.objects.create(
        action='Message Response Sent',
        user=request.user,
        details=f'Response to message {parent.id} sent by {request.user.get_full_name()}'
    )
    
    return Response(
        MessageSerializer(response).data,
        status=status.HTTP_201_CREATED
    )

@api_view(['POST'])
@permission_classes([IsAdminUser])
def notification_create(request):
    """Create and send a notification (admins only).
    
    Args:
        request: HTTP request object containing:
            - title: Notification title
            - message: Notification content
            - target_type: 'user' or 'group'
            - target_id: User ID or group ID
            - priority: 'low', 'medium', 'high'
            
    Returns:
        Created notification data in camelCase format.
        
    Raises:
        400: If target_type or target_id invalid.
        404: If target not found.
    """
    serializer = NotificationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # Create notification
    notification = serializer.save(sender=request.user)
    
    # Log action
    AuditLog.objects.create(
        action='Notification Sent',
        user=request.user,
        details=f'Notification {notification.id} sent to {notification.target_type} {notification.target_id}'
    )
    
    return Response(
        serializer.data,
        status=status.HTTP_201_CREATED
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recipient_group_list(request):
    """List recipient groups (authenticated users only).
    
    Args:
        request: HTTP request object.
            
    Returns:
        Paginated list of recipient groups in camelCase format.
    """
    queryset = RecipientGroup.objects.all()
    
    # Apply pagination
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    serializer = RecipientGroupSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)
