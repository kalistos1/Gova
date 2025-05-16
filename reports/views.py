from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count, Avg
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
    
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from rest_framework import status, viewsets, permissions, mixins
from rest_framework.decorators import (
    api_view, permission_classes, parser_classes,
    action, throttle_classes
)
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from django.core.files.storage import default_storage
import os
import uuid
from django.db import transaction
from django.core.cache import cache
from asgiref.sync import sync_to_async
from django.db.models.functions import TruncDate


from .models import Report, AuditLog, ReportComment
from .serializers import (
    ReportSerializer,
    ReportCreateSerializer,
    ReportCommentSerializer,
    NINVerificationSerializer,
    BVNVerificationSerializer,
    PaymentInitializationSerializer,
    USSDRequestSerializer,
    SMSRequestSerializer,
    VoiceTranscriptionSerializer,
    ReportStatisticsSerializer,
    ReportUpdateSerializer,
    ReportAssignmentSerializer,
    ReportTranslationSerializer,
)
from .permissions import (
    IsVerifiedUser,
    CanInitializePayment,
    CanVerifyPayment,
    CanTranscribeVoiceNote,
    CanSendSMS,
    CanHandleUSSD,
    IsLGAOfficial,
    IsStateOfficial,
    CanAssignReports,
    CanTranslateReports,
)
from .utils import (
    sanitize_text,
    extract_location_from_exif,
    generate_ai_summary,
    calculate_ai_priority,
    translate_text,
    sanitize_phone_number,
    validate_file_extension,
    get_file_upload_path,
    get_report_statistics,
    get_similar_reports,
    notify_officials,
    notify_reporter,
)
from .integrations.openrouter import OpenRouterAI
from .integrations.verifyme import VerifyMeClient
from .integrations.flutterwave import FlutterwaveClient
from .integrations.africas_talking import AfricasTalkingClient
from core.ai_agents import AIProcessingError
from core.notifications import RewardNotificationService
from core.models import Location, Landmark

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for report listings."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class BurstRateThrottle(UserRateThrottle):
    """Throttle for burst requests."""
    rate = '60/minute'

class SustainedRateThrottle(UserRateThrottle):
    """Throttle for sustained requests."""
    rate = '1000/day'

class AnonBurstRateThrottle(AnonRateThrottle):
    """Throttle for anonymous burst requests."""
    rate = '30/minute'

class AnonSustainedRateThrottle(AnonRateThrottle):
    """Throttle for anonymous sustained requests."""
    rate = '500/day'

@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([AnonBurstRateThrottle, AnonSustainedRateThrottle])
def report_list(request):
    """List all reports with filtering and pagination.
    
    Args:
        request: HTTP request object containing query parameters.
            - status: Filter by report status
            - category: Filter by report category
            - location: Filter by location ID
            - submission_channel: Filter by submission channel
            - language: Filter by submission language
            - priority: Filter by priority level
            - search: Search in title and description
            - start_date: Filter by date range start
            - end_date: Filter by date range end
            
    Returns:
        Paginated list of reports in camelCase format.
    """
    queryset = Report.objects.select_related(
        'lga', 'assigned_to'
    ).prefetch_related('comments')
    
    # Apply filters
    status = request.query_params.get('status')
    category = request.query_params.get('category')
    location = request.query_params.get('location')
    submission_channel = request.query_params.get('submission_channel')
    language = request.query_params.get('language')
    priority = request.query_params.get('priority')
    search = request.query_params.get('search')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if status:
        queryset = queryset.filter(status=status)
    if category:
        queryset = queryset.filter(category=category)
    if location:
        queryset = queryset.filter(location_id=location)
    if submission_channel:
        queryset = queryset.filter(submission_channel=submission_channel)
    if language:
        queryset = queryset.filter(submission_language=language)
    if priority:
        queryset = queryset.filter(priority=priority)
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)
        
    # Apply pagination
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    serializer = ReportSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([AnonBurstRateThrottle, AnonSustainedRateThrottle])
def report_detail(request, pk):
    """Retrieve a specific report by ID.
    
    Args:
        request: HTTP request object.
        pk: UUID of the report to retrieve.
            
    Returns:
        Report data in camelCase format.
        
    Raises:
        404: If report not found.
        403: If user lacks permission.
    """
    report = get_object_or_404(
        Report.objects.select_related(
            'lga', 'assigned_to'
        ).prefetch_related('comments'),
        pk=pk
    )

    # Check if user has permission to view this report
    if report.is_anonymous:
        # Anonymous reports are public
        pass
    elif not request.user.is_authenticated:
        # Non-anonymous reports require authentication
        return Response(
            {'error': 'Authentication required to view this report'},
            status=status.HTTP_403_FORBIDDEN
        )
    elif (request.user != report.reporter and 
          request.user != report.assigned_to and
          not request.user.is_staff and
          not hasattr(request.user, 'is_lga_official') and
          not hasattr(request.user, 'is_state_official')):
        # Only allow access to:
        # - The reporter
        # - Assigned official
        # - Staff members
        # - LGA officials
        # - State officials
        return Response(
            {'error': 'You do not have permission to view this report'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = ReportSerializer(report)
    return Response(serializer.data)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsLGAOfficial | IsStateOfficial])
def report_update(request, pk):
    """Update report status and assignment (LGA/State officials only).
    
    Args:
        request: HTTP request object containing update data.
        pk: UUID of the report to update.
            
    Returns:
        Updated report data in camelCase format.
        
    Raises:
        404: If report not found.
        403: If user lacks permission.
        400: If update data is invalid.
    """
    report = get_object_or_404(
        Report.objects.select_related(
            'lga', 'assigned_to'
        ),
        pk=pk
    )
    
    # Only allow updating status and assigned_to
    allowed_fields = {'status', 'assigned_to', 'priority'}
    if not all(field in allowed_fields for field in request.data.keys()):
        return Response(
            {'error': 'Only status, priority and assigned_to fields can be updated'},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    serializer = ReportSerializer(report, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    report = serializer.save()
    
    # Log action
    AuditLog.objects.create(
        report=report,
        action='Report Updated',
        user=request.user,
        old_value=serializer._initial_data,
        new_value=serializer.validated_data
    )
    
    return Response(serializer.data)

class ReportViewSet(viewsets.ModelViewSet):
    """ViewSet for managing reports."""
    
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Get the list of reports based on user role and filters."""
        queryset = Report.objects.select_related(
            'lga', 'assigned_to', 'reporter'
        ).prefetch_related('comments', 'audit_logs')
        
        # Apply filters
        filters = {}
        
        # Status filter
        status = self.request.query_params.get('status')
        if status:
            filters['status'] = status
            
        # Category filter
        category = self.request.query_params.get('category')
        if category:
            filters['category'] = category
            
        # LGA filter
        lga = self.request.query_params.get('lga')
        if lga:
            filters['lga_id'] = lga
            
        # Priority filter
        priority = self.request.query_params.get('priority')
        if priority:
            filters['priority'] = priority
            
        # Date range filter
        start_date = self.request.query_params.get('start_date')
        if start_date:
            filters['created_at__gte'] = start_date
            
        end_date = self.request.query_params.get('end_date')
        if end_date:
            filters['created_at__lte'] = end_date
            
        # Search filter
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(address__icontains=search)
            )
        
        # Apply role-based filtering
        user = self.request.user
        if not user.is_authenticated:
            # Anonymous users can only see public reports
            filters['is_anonymous'] = True
        elif user.is_staff:
            # Staff can see all reports
            pass
        elif hasattr(user, 'is_state_official') and user.is_state_official:
            # State officials can see all reports in their state
            pass
        elif hasattr(user, 'is_lga_official') and user.is_lga_official:
            # LGA officials can only see reports in their LGA
            filters['lga'] = user.lga
        else:
            # Regular users can only see their own reports and public reports
            queryset = queryset.filter(
                Q(reporter=user) | Q(is_anonymous=True)
            )
        
        return queryset.filter(**filters)
    
    def get_serializer_class(self):
        """Get the appropriate serializer based on the action."""
        if self.action == 'create':
            return ReportCreateSerializer
        elif self.action == 'update':
            return ReportUpdateSerializer
        elif self.action == 'assign':
            return ReportAssignmentSerializer
        elif self.action == 'translate':
            return ReportTranslationSerializer
        return ReportSerializer
    
    def get_permissions(self):
        """Get the appropriate permissions based on the action."""
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        elif self.action == 'create':
            permission_classes = [AllowAny]
        elif self.action == 'update':
            permission_classes = [IsAuthenticated, IsLGAOfficial | IsStateOfficial]
        elif self.action == 'assign':
            permission_classes = [IsAuthenticated, CanAssignReports]
        elif self.action == 'translate':
            permission_classes = [IsAuthenticated, CanTranslateReports]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @transaction.atomic
    async def perform_create(self, serializer):
        """Create a new report with AI processing and notifications.
        
        Args:
            serializer: The validated serializer instance.
            
        Raises:
            ValidationError: If report data is invalid.
            AIProcessingError: If AI processing fails.
            MediaProcessingError: If media processing fails.
            NotificationError: If notification sending fails.
        """
        try:
            # Extract data
            description = serializer.validated_data.get('description', '')
            images = serializer.validated_data.get('images', [])
            videos = serializer.validated_data.get('videos', [])
            voice_notes = serializer.validated_data.get('voice_notes', [])
            
            # Process media files
            try:
                if images:
                    processed_images = await process_images(images)
                    serializer.validated_data['images'] = processed_images
                    
                if videos:
                    processed_videos = await process_videos(videos)
                    serializer.validated_data['videos'] = processed_videos
                    
                if voice_notes:
                    processed_voice_notes = await process_voice_notes(voice_notes)
                    serializer.validated_data['voice_notes'] = processed_voice_notes
                    
            except MediaProcessingError as e:
                logger.error(
                    'Media processing failed',
                    extra={
                        'error': str(e),
                        'user_id': self.request.user.id if self.request.user.is_authenticated else None
                    }
                )
                raise
            
            # AI processing
            if settings.ENABLE_AI_PROCESSING:
                try:
                    ai_client = OpenRouterAI()
                    
                    # Generate summary
                    try:
                        summary = await ai_client.generate_summary(description)
                        if summary:
                            serializer.validated_data['ai_summary'] = summary
                    except AIProcessingError as e:
                        logger.warning(
                            'AI summary generation failed',
                            extra={
                                'error': str(e),
                                'user_id': self.request.user.id if self.request.user.is_authenticated else None
                            }
                        )
                        # Continue without summary
                    
                    # Calculate priority
                    try:
                        priority_score = await ai_client.calculate_priority(description)
                        if priority_score:
                            serializer.validated_data['ai_priority_score'] = priority_score
                            
                            # Update priority based on AI score
                            if priority_score >= 0.8:
                                serializer.validated_data['priority'] = 'URGENT'
                            elif priority_score >= 0.6:
                                serializer.validated_data['priority'] = 'HIGH'
                            elif priority_score >= 0.4:
                                serializer.validated_data['priority'] = 'MEDIUM'
                            else:
                                serializer.validated_data['priority'] = 'LOW'
                    except AIProcessingError as e:
                        logger.warning(
                            'AI priority calculation failed',
                            extra={
                                'error': str(e),
                                'user_id': self.request.user.id if self.request.user.is_authenticated else None
                            }
                        )
                        # Keep default priority
                    
                except Exception as e:
                    logger.error(
                        'AI processing failed',
                        extra={
                            'error': str(e),
                            'user_id': self.request.user.id if self.request.user.is_authenticated else None
                        }
                    )
                    # Continue without AI processing
            
            # Save the report
            try:
                report = await sync_to_async(serializer.save)()
            except Exception as e:
                logger.error(
                    'Failed to save report',
                    extra={
                        'error': str(e),
                        'user_id': self.request.user.id if self.request.user.is_authenticated else None,
                        'data': serializer.validated_data
                    }
                )
                raise ValidationError(_('Failed to create report'))
            
            # Send notifications
            try:
                await send_report_notifications(report)
            except NotificationError as e:
                logger.error(
                    'Failed to send notifications',
                    extra={
                        'error': str(e),
                        'report_id': report.id,
                        'user_id': self.request.user.id if self.request.user.is_authenticated else None
                    }
                )
                # Continue without notifications
            
            # Log action
            try:
                await sync_to_async(AuditLog.objects.create)(
                    action='Report Created',
                    user=self.request.user if self.request.user.is_authenticated else None,
                    details={
                        'report_id': str(report.id),
                        'title': report.title,
                        'category': report.category,
                        'priority': report.priority,
                        'has_media': bool(images or videos or voice_notes),
                        'ai_processed': settings.ENABLE_AI_PROCESSING
                    }
                )
            except Exception as e:
                logger.error(
                    'Failed to create audit log',
                    extra={
                        'error': str(e),
                        'report_id': report.id,
                        'user_id': self.request.user.id if self.request.user.is_authenticated else None
                    }
                )
                # Continue without audit log
            
            return report
            
        except ValidationError:
            raise
        except (AIProcessingError, MediaProcessingError, NotificationError):
            raise
        except Exception as e:
            logger.error(
                'Unexpected error during report creation',
                extra={
                    'error': str(e),
                    'user_id': self.request.user.id if self.request.user.is_authenticated else None,
                    'data': serializer.validated_data
                },
                exc_info=True
            )
            raise ValidationError(_('An unexpected error occurred'))
    
    @action(detail=True, methods=['post'])
    @permission_classes([IsAuthenticated])
    def add_comment(self, request, pk=None):
        """Add a comment to a report."""
        report = self.get_object()
        
        serializer = ReportCommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                report=report,
                user=request.user,
                is_official=hasattr(request.user, 'is_lga_official') or
                           hasattr(request.user, 'is_state_official')
            )
            
            # Create audit log entry
            AuditLog.objects.create(
                report=report,
                action='Comment Added',
                user=request.user,
                new_value={'content': serializer.data['content']}
            )
            
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
   

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanAssignReports])
    async def assign(self, request, pk=None):  # Changed to async def
        """Assign a report to an official."""
        report = await sync_to_async(self.get_object)()  # Convert synchronous call to async
        serializer = ReportAssignmentSerializer(data=request.data)
        
        if serializer.is_valid():
            old_assigned_to = report.assigned_to
            report.assigned_to = serializer.validated_data['assigned_to']
            report.assigned_at = await sync_to_async(timezone.now)()  # Async timezone.now
            await sync_to_async(report.save)()  # Async save
            
            # Create audit log entry
            await sync_to_async(AuditLog.objects.create)(
                report=report,
                action='Report Assigned',
                user=request.user,
                old_value={'assigned_to': str(old_assigned_to) if old_assigned_to else None},
                new_value={'assigned_to': str(report.assigned_to)}
            )
            
            # Notify the assigned official
            if report.assigned_to:
                await notify_officials(report, [report.assigned_to])  # Now valid with await
                
            return Response({'status': 'report assigned'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    @permission_classes([IsAuthenticated, CanTranslateReports])
    async def translate(self, request, pk=None):
        """Translate report content to a different language."""
        report = self.get_object()
        serializer = ReportTranslationSerializer(data=request.data)
        
        if serializer.is_valid():
            target_language = serializer.validated_data['target_language']
            
            # Translate description
            translated_description = await translate_text(
                report.description,
                'en',
                target_language
            )
            
            # Translate title
            translated_title = await translate_text(
                report.title,
                'en',
                target_language
            )
            
            return Response({
                'title': translated_title,
                'description': translated_description
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    @permission_classes([CanTranscribeVoiceNote])
    async def transcribe_voice_note(self, request, pk=None):
        """Transcribe a voice note to text."""
        report = self.get_object()
        serializer = VoiceTranscriptionSerializer(data=request.data)
        
        if serializer.is_valid():
            voice_note_url = serializer.validated_data['voice_note_url']
            source_language = serializer.validated_data.get('source_language', 'en')
            
            ai_client = OpenRouterAI()
            transcription = await ai_client.transcribe_voice_note(
                voice_note_url,
                source_language
            )
            
            if transcription:
                return Response({'transcription': transcription})
            return Response(
                {'error': 'Transcription failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    @permission_classes([CanInitializePayment])
    async def initialize_payment(self, request, pk=None):
        """Initialize payment for a report."""
        report = self.get_object()
        serializer = PaymentInitializationSerializer(data=request.data)
        
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            email = serializer.validated_data['email']
            phone = serializer.validated_data.get('phone')
            name = serializer.validated_data.get('name')
            
            payment_client = FlutterwaveClient()
            result = await payment_client.initialize_payment(
                amount=amount,
                email=email,
                phone=phone,
                name=name
            )
            
            if result['status'] == 'success':
                # Update report payment info
                report.payment_status = 'PENDING'
                report.payment_amount = amount
                report.transaction_reference = result['data']['tx_ref']
                report.save()
                
                # Create audit log entry
                AuditLog.objects.create(
                    report=report,
                    action='Payment Initialized',
                    user=request.user if request.user.is_authenticated else None,
                    new_value={
                        'amount': str(amount),
                        'tx_ref': result['data']['tx_ref']
                    }
                )
                
                return Response(result)
            return Response(
                {'error': result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    @permission_classes([CanVerifyPayment])
    async def verify_payment(self, request, pk=None):
        """Verify payment for a report."""
        report = self.get_object()
        
        if not report.transaction_id:
            return Response(
                {'error': 'No transaction ID found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_client = FlutterwaveClient()
        result = await payment_client.verify_payment(report.transaction_id)
        
        if result['status'] == 'success':
            # Update report payment status
            report.payment_status = 'PAID'
            report.payment_date = timezone.now()
            report.save()
            
            # Create audit log entry
            AuditLog.objects.create(
                report=report,
                action='Payment Verified',
                user=request.user if request.user.is_authenticated else None,
                new_value={
                    'status': 'PAID',
                    'transaction_id': report.transaction_id
                }
            )
            
            return Response(result)
        return Response(
            {'error': 'Payment verification failed'},
            status=status.HTTP_400_BAD_REQUEST
        )


    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsLGAOfficial | IsStateOfficial])
    async def statistics(self, request):  # Changed to async def
        """Get report statistics.
        
        Args:
            request: HTTP request object.
            
        Returns:
            Response: Report statistics in camelCase format.
            
        Raises:
            ValidationError: If date range is invalid.
            PermissionDenied: If user lacks required permissions.
            APIError: If statistics calculation fails.
        """
        try:
            # Get date range
            try:
                end_date = request.query_params.get('end_date')
                end_date = await sync_to_async(timezone.datetime.fromisoformat)(end_date) if end_date else await sync_to_async(timezone.now)()
                
                days = request.query_params.get('days', '30')
                days = int(days)
                if days < 1 or days > 365:
                    raise ValidationError(_('Days must be between 1 and 365'))
                    
                start_date = end_date - timedelta(days=days)
                
            except (ValueError, TypeError) as e:
                logger.error(
                    'Invalid date parameters',
                    extra={
                        'error': str(e),
                        'params': request.query_params,
                        'user_id': request.user.id
                    }
                )
                raise ValidationError(_('Invalid date parameters'))
                
            # Get LGA filter for LGA officials
            lga = None
            if hasattr(request.user, 'is_lga_official') and request.user.is_lga_official:
                lga = request.user.lga
                
            # Calculate statistics
            try:
                stats = await get_report_statistics(start_date, end_date, lga)  # Now valid
            except Exception as e:
                logger.error(
                    'Failed to calculate statistics',
                    extra={
                        'error': str(e),
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'lga_id': lga.id if lga else None,
                        'user_id': request.user.id
                    },
                    exc_info=True
                )
                raise APIError(_('Failed to calculate statistics'))
                
            # Cache results
            try:
                cache_key = f'report_stats:{request.user.id}:{start_date.date()}:{end_date.date()}'
                await sync_to_async(cache.set)(cache_key, stats, timeout=3600)  # Cache for 1 hour
            except Exception as e:
                logger.warning(
                    'Failed to cache statistics',
                    extra={
                        'error': str(e),
                        'user_id': request.user.id
                    }
                )
                # Continue without caching
                
            # Log access
            try:
                await sync_to_async(AuditLog.objects.create)(
                    action='Statistics Viewed',
                    user=request.user,
                    details={
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'lga_id': lga.id if lga else None,
                        'days': days
                    }
                )
            except Exception as e:
                logger.error(
                    'Failed to log statistics access',
                    extra={
                        'error': str(e),
                        'user_id': request.user.id
                    }
                )
                # Continue without logging
                
            serializer = ReportStatisticsSerializer(stats)
            return Response(serializer.data)
            
        except ValidationError:
            raise
        except PermissionDenied:
            raise
        except APIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(
                'Unexpected error getting statistics',
                extra={
                    'error': str(e),
                    'user_id': request.user.id
                },
                exc_info=True
            )
            return Response(
                {'error': _('An unexpected error occurred')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    @action(detail=True, methods=['get'])
    def similar(self, request, pk=None):
        """Get similar reports."""
        report = self.get_object()
        similar_reports = get_similar_reports(report)
        serializer = ReportSerializer(similar_reports, many=True)
        return Response(serializer.data)

class VerificationViewSet(viewsets.ViewSet):
    """ViewSet for identity verification."""
    
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BurstRateThrottle]
    
    @action(detail=False, methods=['post'])
    async def verify_nin(self, request):
        """Verify NIN number."""
        serializer = NINVerificationSerializer(data=request.data)
        
        if serializer.is_valid():
            nin = serializer.validated_data['nin']
            
            verify_client = VerifyMeClient()
            result = await verify_client.verify_nin(nin)
            
            if result['status'] == 'success':
                # Update user verification status
                request.user.nin_verified = True
                request.user.nin_verification_date = timezone.now()
                request.user.save()
                
                return Response(result)
            return Response(
                {'error': result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    async def verify_bvn(self, request):
        """Verify BVN number."""
        serializer = BVNVerificationSerializer(data=request.data)
        
        if serializer.is_valid():
            bvn = serializer.validated_data['bvn']
            
            verify_client = VerifyMeClient()
            result = await verify_client.verify_bvn(bvn)
            
            if result['status'] == 'success':
                # Update user verification status
                request.user.bvn_verified = True
                request.user.bvn_verification_date = timezone.now()
                request.user.save()
                
                return Response(result)
            return Response(
                {'error': result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class USSDViewSet(viewsets.ViewSet):
    """ViewSet for USSD functionality."""
    
    permission_classes = [CanHandleUSSD]
    throttle_classes = [AnonBurstRateThrottle]
    
    def create(self, request):
        """Handle USSD requests."""
        serializer = USSDRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            session_id = serializer.validated_data['session_id']
            phone_number = serializer.validated_data['phone_number']
            text = serializer.validated_data['text']
            
            ussd_client = AfricasTalkingClient()
            response = ussd_client.handle_ussd(
                session_id=session_id,
                phone_number=phone_number,
                text=text
            )
            
            return Response(response)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SMSViewSet(viewsets.ViewSet):
    """ViewSet for SMS functionality."""
    
    permission_classes = [CanSendSMS]
    throttle_classes = [BurstRateThrottle]
    
    @action(detail=False, methods=['post'])
    async def send_sms(self, request):
        """Send SMS message."""
        serializer = SMSRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            to = serializer.validated_data['to']
            message = serializer.validated_data['message']
            
            sms_client = AfricasTalkingClient()
            result = await sms_client.send_sms(
                to=to,
                message=message
            )
            
            if result['status'] == 'success':
                return Response(result)
            return Response(
                {'error': result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MediaUploadViewSet(viewsets.ViewSet):
    """ViewSet for handling media uploads."""
    
    parser_classes = [MultiPartParser, FormParser, FileUploadParser]
    permission_classes = [IsAuthenticated]
    throttle_classes = [BurstRateThrottle]
    
    def _handle_upload(self, file, folder, allowed_types, max_size):
        """Handle file upload with validation."""
        if not file:
            return None, 'No file provided'
            
        if not validate_file_extension(file, allowed_types):
            return None, f'Invalid file type. Allowed types: {", ".join(allowed_types)}'
            
        if file.size > max_size:
            return None, f'File too large. Maximum size: {max_size/1024/1024}MB'
            
        try:
            path = get_file_upload_path(file, folder)
            default_storage.save(path, file)
            return path, None
        except Exception as e:
            logger.error(f'File upload error: {str(e)}')
            return None, 'File upload failed'
    
    @action(detail=False, methods=['post'])
    def upload_image(self, request):
        """Upload an image file."""
        file = request.FILES.get('file')
        path, error = self._handle_upload(
            file=file,
            folder='images',
            allowed_types=['jpg', 'jpeg', 'png'],
            max_size=5 * 1024 * 1024  # 5MB
        )
        
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
            
        # Extract location from EXIF if available
        location = extract_location_from_exif(file)
        
        return Response({
            'url': path,
            'location': location
        })
    
    @action(detail=False, methods=['post'])
    def upload_video(self, request):
        """Upload a video file."""
        file = request.FILES.get('file')
        path, error = self._handle_upload(
            file=file,
            folder='videos',
            allowed_types=['mp4', 'mov', 'avi'],
            max_size=50 * 1024 * 1024  # 50MB
        )
        
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'url': path})
    
    @action(detail=False, methods=['post'])
    def upload_voice(self, request):
        """Upload a voice note."""
        file = request.FILES.get('file')
        path, error = self._handle_upload(
            file=file,
            folder='voice_notes',
            allowed_types=['mp3', 'wav', 'm4a'],
            max_size=10 * 1024 * 1024  # 10MB
        )
        
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'url': path})

# HTML Template View Functions

def reports_list_view(request):
    """View function for listing all reports."""
    # Get all reports
    reports = Report.objects.all().order_by('-created_at')
    
    # Apply filters
    category = request.GET.get('category')
    if category:
        reports = reports.filter(category=category)
    
    status_filter = request.GET.get('status')
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    location = request.GET.get('location')
    if location:
        reports = reports.filter(location__id=location)
    
    # Paginate reports
    paginator = Paginator(reports, 12)  # 12 reports per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories and locations for filter dropdowns
    categories = []  # Replace with: Category.objects.all()
    locations = Location.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'locations': locations,
        'current_filters': {
            'category': category,
            'status': status_filter,
            'location': location,
        },
    }
    
    return render(request, 'reports/list.html', context)

def reports_search_view(request):
    """HTMX view for searching reports."""
    query = request.GET.get('q', '')
    
    if not query:
        return HttpResponse('')
    
    # Search reports
    reports = Report.objects.filter(
        Q(title__icontains=query) | 
        Q(description__icontains=query)
    ).order_by('-created_at')[:10]
    
    return render(request, 'reports/partials/search_results.html', {'reports': reports})

@login_required
def report_create_view(request):
    """View function for creating a new report."""
    if request.method == 'POST':
        # Process form data
        title = request.POST.get('title')
        description = request.POST.get('description')
        category = request.POST.get('category')
        location_id = request.POST.get('location')
        is_anonymous = request.POST.get('is_anonymous') == 'on'
        
        # Create report
        report = Report.objects.create(
            title=title,
            description=description,
            category=category,
            location_id=location_id,
            reporter=request.user,
            is_anonymous=is_anonymous,
            submission_channel='web'
        )
        
        # Handle image upload
        if 'image' in request.FILES:
            # Process image
            pass
        
        # Redirect to report detail page
        messages.success(request, 'Report submitted successfully.')
        return redirect('reports:detail', report_id=report.id)
    
    # Get categories and locations for form
    categories = []  # Replace with: Category.objects.all()
    locations = Location.objects.all()
    
    context = {
        'categories': categories,
        'locations': locations,
    }
    
    return render(request, 'reports/create.html', context)

def report_detail_view(request, report_id):
    """View function for viewing a report's details."""
    # Get report
    report = get_object_or_404(Report, id=report_id)
    
    # Get comments
    comments = report.comments.all().order_by('-created_at')
    
    # Get similar reports
    similar_reports = Report.objects.filter(
        category=report.category
    ).exclude(id=report_id).order_by('-created_at')[:3]
    
    context = {
        'report': report,
        'comments': comments,
        'similar_reports': similar_reports,
    }
    
    return render(request, 'reports/detail.html', context)

@login_required
def report_edit_view(request, report_id):
    """View function for editing a report."""
    # Get report
    report = get_object_or_404(Report, id=report_id)
    
    # Check if user is allowed to edit
    if report.reporter != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to edit this report.')
        return redirect('reports:detail', report_id=report_id)
    
    if request.method == 'POST':
        # Process form data
        title = request.POST.get('title')
        description = request.POST.get('description')
        category = request.POST.get('category')
        location_id = request.POST.get('location')
        
        # Update report
        report.title = title
        report.description = description
        report.category = category
        report.location_id = location_id
        report.save()
        
        # Redirect to report detail page
        messages.success(request, 'Report updated successfully.')
        return redirect('reports:detail', report_id=report_id)
    
    # Get categories and locations for form
    categories = []  # Replace with: Category.objects.all()
    locations = Location.objects.all()
    
    context = {
        'report': report,
        'categories': categories,
        'locations': locations,
    }
    
    return render(request, 'reports/edit.html', context)

@login_required
@require_POST
def report_delete_view(request, report_id):
    """View function for deleting a report."""
    # Get report
    report = get_object_or_404(Report, id=report_id)
    
    # Check if user is allowed to delete
    if report.reporter != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to delete this report.')
        return redirect('reports:detail', report_id=report_id)
    
    # Delete report
    report.delete()
    
    messages.success(request, 'Report deleted successfully.')
    return redirect('reports:list')

@login_required
@require_POST
def report_add_comment_view(request, report_id):
    """HTMX view for adding a comment to a report."""
    # Get report
    report = get_object_or_404(Report, id=report_id)
    
    # Add comment
    comment_text = request.POST.get('comment', '')
    
    if comment_text:
        ReportComment.objects.create(
            report=report,
            user=request.user,
            text=comment_text
        )
    
    # Get updated comments
    comments = report.comments.all().order_by('-created_at')
    
    return render(request, 'reports/partials/comments.html', {'comments': comments})

@login_required
@require_POST
def report_support_view(request, report_id):
    """HTMX view for supporting a report."""
    # Get report
    report = get_object_or_404(Report, id=report_id)
    
    # Toggle support
    is_supported = report.supporters.filter(id=request.user.id).exists()
    if is_supported:
        report.supporters.remove(request.user)
    else:
        report.supporters.add(request.user)
    
    # Return updated support count
    support_count = report.supporters.count()
    is_supported = not is_supported
    
    return JsonResponse({
        'support_count': support_count,
        'is_supported': is_supported,
    })

@login_required
@require_POST
def report_update_status_view(request, report_id):
    """HTMX view for updating the status of a report."""
    # Get report
    report = get_object_or_404(Report, id=report_id)
    
    # Check if user is allowed to update status
    if not request.user.is_staff and not hasattr(request.user, 'is_lga_official') and not hasattr(request.user, 'is_state_official'):
        return HttpResponse('Unauthorized', status=403)
    
    # Update status
    new_status = request.POST.get('status')
    if new_status in dict(Report.STATUS_CHOICES).keys():
        report.status = new_status
        report.save()
    
    return render(request, 'reports/partials/status_badge.html', {'report': report})

@login_required
@require_POST
def report_upload_media_view(request):
    """HTMX view for uploading media files for a report."""
    file = request.FILES.get('file')
    
    if file:
        # Process file upload
        # Save file to storage
        file_path = default_storage.save(f'reports/media/{file.name}', file)
        file_url = default_storage.url(file_path)
        
        return JsonResponse({
            'url': file_url,
        })
    
    return JsonResponse({'error': 'No file provided.'}, status=400)


class PaymentViewSet(viewsets.ViewSet):
    """ViewSet for handling payments."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [BurstRateThrottle]
    
    @action(detail=False, methods=['post'])
    async def initialize_payment(self, request):
        """Initialize payment for a report."""
        serializer = PaymentInitializationSerializer(data=request.data)
        
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            email = serializer.validated_data['email']
            phone = serializer.validated_data.get('phone')
            name = serializer.validated_data.get('name')
            
            payment_client = FlutterwaveClient()
            result = await payment_client.initialize_payment(
                amount=amount,
                email=email,
                phone=phone,
                name=name
            )
            
            if result['status'] == 'success':
                return Response(result)
            return Response(
                {'error': result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)